"""trackq.py IN.kicad_pcb [OUT.kicad_pcb --fix] [--nets-file F.json] [--region x0,y0,x1,y1] [--report R.json]
                [--detour 1.25] [--top 25]

Track economy check (user rule 2026-10-02 18:05: "check the turns or ... the area of the track so that you are using
the least amount of track to connect to something by making sure that it follows a simple line or 45 degrees").

Every routed net is cut into CHAINS: runs of track on one layer between terminals (a pad of the net, a via, a T
junction or a dead end). For each chain:
  length       - copper centre-line length
  octile       - the shortest octilinear (0/45/90) distance between its two ends = the least track possible
  detour       - length / octile
  bends        - direction changes; the least possible is 0 (ends aligned on 0/45/90) or 1
  area         - width x length (copper)
  violations   - non-octilinear segment, 90-degree or acute bend, collinear split (mergeable), sliver < 0.1 mm
A chain is WASTEFUL when detour > --detour (default 1.25, and > 0.3 mm extra) or bends > least + 1.
With --fix, a wasteful chain is replaced by the shortest legal octilinear path between its ends: a straight
segment when the ends are aligned, else the two one-bend doglegs (diagonal-first / straight-first), checked against
this board's rule model (mr.py: pairwise DRU clearances with courtyard exemptions, rule-area bans, edge clearance).
KiCad python, scratch copies only."""
import collections
import json
import math
import os
import shutil
import sys

import pcbnew
from shapely.geometry import LineString, Point, box

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mr  # noqa: E402

argv = sys.argv[1:]


def opt(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


src = argv[0]
fix = '--fix' in argv
dst = argv[1] if fix else None
DET = float(opt('--detour', '1.25'))
region = box(*[float(v) for v in opt('--region').split(',')]) if opt('--region') else None
only = set(json.load(open(opt('--nets-file')))) if opt('--nets-file') else None
Q = 1e-4


def key(x, y):
    return (round(x / Q), round(y / Q))


def octile(dx, dy):
    dx, dy = abs(dx), abs(dy)
    return max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)


def ang(a, c):
    return math.degrees(math.atan2(c[1] - a[1], c[0] - a[0])) % 360


def is_oct(a):
    r = a % 45
    return r < 0.5 or r > 44.5


def turn(a1, a2):
    t = abs(a2 - a1) % 360
    return min(t, 360 - t)


B = mr.Board(src, ('*',)) if fix else None
b = B.b if fix else pcbnew.LoadBoard(src)
L = {n: b.GetLayerID(n) for n in mr.SIG}
lname = {v: k for k, v in L.items()}
# terminals: pad copper and vias per net
pads = collections.defaultdict(list)       # (net, layer) -> [polygon]
for f in b.GetFootprints():
    for p in f.Pads():
        n = p.GetNetname()
        if not n:
            continue
        for ln, lid in L.items():
            if p.IsOnLayer(lid):
                pads[(n, ln)].append(mr.poly_of(p.GetEffectivePolygon(lid, pcbnew.ERROR_INSIDE)))
vias = collections.defaultdict(set)        # net -> {key}
segs = collections.defaultdict(list)       # (net, layer) -> [track]
for t in b.GetTracks():
    n = t.GetNetname()
    if t.GetClass() == 'PCB_VIA':
        c = t.GetPosition()
        vias[n].add(key(c.x / 1e6, c.y / 1e6))
        continue
    if t.GetClass() != 'PCB_TRACK':
        continue
    ln = lname.get(t.GetLayer())
    if ln is None or n == 'GND' or (only and n not in only):
        continue
    segs[(n, ln)].append(t)


def chains_of(net, ln, tracks):
    adj = collections.defaultdict(list)
    pt = {}
    for t in tracks:
        a = (t.GetStart().x / 1e6, t.GetStart().y / 1e6)
        c = (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)
        ka, kc = key(*a), key(*c)
        if ka == kc:
            continue
        pt[ka], pt[kc] = a, c
        adj[ka].append((kc, t))
        adj[kc].append((ka, t))
    pl = pads.get((net, ln), [])

    def terminal(k):
        if len(adj[k]) != 2 or k in vias.get(net, ()):
            return True
        p = Point(*pt[k])
        return any(g.distance(p) < 1e-3 for g in pl)
    used = set()
    out = []
    for k0 in list(adj):
        if not terminal(k0):
            continue
        for k1, t in adj[k0]:
            if id(t) in used:
                continue
            chain = [k0]
            ts = []
            prev, cur, tt = k0, k1, t
            while True:
                used.add(id(tt))
                ts.append(tt)
                chain.append(cur)
                if terminal(cur):
                    break
                nxt = [(k, t2) for k, t2 in adj[cur] if id(t2) not in used]
                if not nxt:
                    break
                prev, (cur, tt) = cur, nxt[0]
            out.append(([pt[k] for k in chain], ts))
    return out


def legal_path(net, ln, pts, w, own_ids):
    """pts: polyline; checks every segment against other-net copper with the pairwise rule, bans, edge"""
    c = mr.cls(net)
    hs_like = c in ('HighSpeed_Digital', 'HighSpeed_Clock', 'Analog_Precision', 'Ref_Kelvin', 'RF_Input', 'RF_50R',
                    'Power_Buck_SW')
    e1 = (1.0 if hs_like else 0.5) + w / 2
    bans = B.bans(net)
    for a, cpt in zip(pts, pts[1:]):
        line = LineString([a, cpt])
        sg = line.buffer(w / 2, 8)
        if not B.outline.buffer(-e1 + w / 2).contains(line):
            ex_edge = B.exempt_geo['EDGE']
            if not (hs_like and ex_edge.intersects(sg) and B.outline.buffer(-(0.5 + w / 2)).contains(line)):
                return False
        ex = frozenset(k for k, e in B.exempt_geo.items() if not e.is_empty and e.intersects(sg))
        if 'NK' in ex:
            pass
        for item in bans:
            if item[0] == 'VIAHOLE':
                continue
            g, lays, tb, vb = item
            if tb and ln in lays and g.intersects(sg):
                return False
        for i in B.trees[ln].query(sg.buffer(2.1)):
            geo, n2, kind = B.items[ln][i]
            if n2 == net or id(geo) in own_ids:
                continue
            if geo.distance(line) < w / 2 + mr.need(net, n2, kind, ex) - 1e-4:
                return False
    return True


def candidates(a, c):
    dx, dy = c[0] - a[0], c[1] - a[1]
    adx, ady = abs(dx), abs(dy)
    sx, sy = (1 if dx >= 0 else -1), (1 if dy >= 0 else -1)
    if adx < 1e-4 or ady < 1e-4 or abs(adx - ady) < 1e-4:
        return [[a, c]]
    m = min(adx, ady)
    d1 = (a[0] + sx * m, a[1] + sy * m)              # diagonal first
    d2 = (c[0] - sx * m, c[1] - sy * m)              # straight first, diagonal last
    return [[a, d1, c], [a, d2, c]]


rows = []
fixed = 0
remove, add = [], []
for (net, ln), tracks in sorted(segs.items()):
    for pts, ts in chains_of(net, ln, tracks):
        if region is not None and not any(region.contains(Point(*p)) for p in pts):
            continue
        length = sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(pts, pts[1:]))
        octl = octile(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1])
        angs = [ang(p, q) for p, q in zip(pts, pts[1:])]
        turns = [turn(x, y) for x, y in zip(angs, angs[1:])]
        bends = sum(1 for t in turns if t > 0.5)
        least = 0 if len(candidates(pts[0], pts[-1])) == 1 else 1
        viol = []
        if any(not is_oct(a_) for a_ in angs):
            viol.append('non-octilinear')
        if any(t > 45.5 for t in turns):
            viol.append('90deg-or-acute')
        if any(t <= 0.5 for t in turns):
            viol.append('collinear-split')
        if any(math.hypot(q[0] - p[0], q[1] - p[1]) < 0.1 for p, q in zip(pts, pts[1:])) and len(pts) > 2:
            viol.append('sliver')
        w = ts[0].GetWidth() / 1e6
        area = sum(t.GetWidth() / 1e6 * t.GetLength() / 1e6 for t in ts)
        waste = (length > DET * octl and length - octl > 0.3) or bends > least + 1
        row = {'net': net, 'layer': ln, 'from': [round(v, 3) for v in pts[0]], 'to': [round(v, 3) for v in pts[-1]],
               'len': round(length, 3), 'octile': round(octl, 3), 'detour': round(length / octl, 3) if octl > 1e-6 else 1.0,
               'bends': bends, 'least_bends': least, 'area_mm2': round(area, 4), 'violations': viol, 'wasteful': waste}
        # chains shorter than 0.25 mm are pad-entry pieces: a 1-bend replacement only adds a sliver - leave them
        if fix and length >= 0.25 and (waste or viol) and len(set(round(t.GetWidth() / 1e3) for t in ts)) == 1:
            own = set()
            for t in ts:
                a_ = (t.GetStart().x / 1e6, t.GetStart().y / 1e6)
                c_ = (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)
                g_ = LineString([a_, c_]).buffer(t.GetWidth() / 2e6, 8)
                for i in B.trees[ln].query(g_):
                    geo, n2, kind = B.items[ln][i]
                    if n2 == net and kind == 'track' and geo.equals_exact(g_, 1e-6):
                        own.add(id(geo))
            best = None
            for cand in candidates(pts[0], pts[-1]):
                cl = sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(cand, cand[1:]))
                cb = len(cand) - 2
                if cl < length - 0.05 or (cl <= length + 0.01 and cb < bends) or (viol and cl <= length + 0.01):
                    if legal_path(net, ln, cand, w, own) and (best is None or cl < best[0]):
                        best = (cl, cand)
            if best:
                row['fixed'] = {'len': round(best[0], 3), 'bends': len(best[1]) - 2}
                fixed += 1
                remove += ts
                for p, q in zip(best[1], best[1][1:]):
                    add.append((net, ln, p, q, w))
                # new copper becomes an obstacle for the following chains
                for p, q in zip(best[1], best[1][1:]):
                    B.items[ln].append((LineString([p, q]).buffer(w / 2, 8), net, 'track'))
                B.rebuild()
        rows.append(row)
tot = len(rows)
waste = [r for r in rows if r['wasteful']]
vi = collections.Counter(v for r in rows for v in r['violations'])
print(f"trackq: {tot} chains | track {sum(r['len'] for r in rows):.1f} mm vs least {sum(r['octile'] for r in rows):.1f} mm "
      f"| bends {sum(r['bends'] for r in rows)} (least {sum(r['least_bends'] for r in rows)}) | copper "
      f"{sum(r['area_mm2'] for r in rows):.2f} mm2 | wasteful {len(waste)} | violations {dict(vi)}")
for r in sorted(waste, key=lambda r: -(r['len'] - r['octile']))[:int(opt('--top', '25'))]:
    print(f"   {r['net'].split('/')[-1][:22]:22s} {r['layer']:6s} {r['from']}->{r['to']} len {r['len']:.2f} least "
          f"{r['octile']:.2f} bends {r['bends']}/{r['least_bends']} {' '.join(r['violations'])}"
          f"{'  FIXED ' + str(r['fixed']) if 'fixed' in r else ''}")
if fix:
    for t in remove:
        b.Remove(t)
    for net, ln, p, q, w in add:
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(int(round(p[0] * 1e6)), int(round(p[1] * 1e6))))
        t.SetEnd(pcbnew.VECTOR2I(int(round(q[0] * 1e6)), int(round(q[1] * 1e6))))
        t.SetWidth(int(round(w * 1e6)))
        t.SetLayer(L[ln])
        t.SetNet(b.FindNet(net))
        b.Add(t)
    if os.path.normcase(os.path.realpath(dst)).startswith(mr.PROTECTED):
        sys.exit('refusing to write into the project folder')
    pcbnew.SaveBoard(dst, b)
    for ext in ('.kicad_pro', '.kicad_dru'):
        s = os.path.splitext(src)[0] + ext
        if os.path.isfile(s):
            shutil.copy2(s, os.path.splitext(dst)[0] + ext)
    print(f"trackq --fix: {fixed} chains straightened -> {dst}")
if opt('--report'):
    json.dump(rows, open(opt('--report'), 'w'), indent=1)

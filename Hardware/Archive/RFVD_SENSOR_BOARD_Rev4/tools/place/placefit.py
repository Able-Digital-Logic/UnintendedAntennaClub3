"""placefit.py IN.kicad_pcb OUT.kicad_pcb --part REF:x0,y0,x1,y1[:rots] [--part ...] --conn SPEC [--conn ...]
                 [--rip NET,NET] [--step 0.1] [--keep 25] [--report R.json] [--height-ok REF,REF] [--edge-min MM]

Routability-scored placement (user rules 2026-10-02: placement first; datasheet-sensitive parts at their pins, the
others 'a bit further away than mathematically correct' when that makes the routing work; via-in-pad first).
Parts are placed one after another (greedy, in the order given). For each part every legal pose in its window
(grid --step, rotations, same side) is generated with spot.py-style legality (courtyards 0.02 mm apart, outline,
footprint-ban rule areas, pads clear other copper by the exact pairwise rule model, holes 0.25) and the --keep poses
closest to the window centre are SCORED by routing the part's connections with mr.py (exact DRU model, octilinear,
via-first): score = sum of path costs (mm, vias weighted), unroutable = +1000 each. The best pose is kept, its routes
committed, then the next part is placed. Connection SPECs (pads written REF.PAD; the part being placed is the one
whose pad appears):
    U8.14-C46.1      route the island holding U8.14 to C46 pad 1
    C46.2-VIA        via-in-pad legal at C46 pad 2 (GND pads: the plane via) - else +1000
    R18.1-NET        route R18 pad 1 to the nearest island of its net
--rip removes every track / via of those nets touching the parts' pads or lying inside the windows (and the parts'
GND pad vias) before placing. KiCad python, scratch copies only."""
import fnmatch
import json
import math
import os
import shutil
import sys
import time

import pcbnew
from shapely import affinity
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import mr  # noqa: E402

BAN_PATS = ('K4_TFT_LOOP', 'K11_*', 'K6_B_RF_END', 'K10B_HSE_SHADOW', 'K12_*', 'K13_U402_VIAFIELD', 'K16_DISP_LANE', 'K7_H?')
argv = sys.argv[1:]


def opts(k):
    return [argv[i + 1] for i, a in enumerate(argv) if a == k]


def opt(k, d=None):
    v = opts(k)
    return v[0] if v else d


src, dst = argv[0], argv[1]
if os.path.normcase(os.path.realpath(dst)).startswith(mr.PROTECTED):
    sys.exit('refusing to write into the project folder')
STEP = float(opt('--step', '0.1'))
KEEP = int(opt('--keep', '25'))
parts = []
FLIP = set()          # REF:window:rots:flip -> the part is placed on the OTHER side
for spec in opts('--part'):
    f = spec.split(':')
    rots = [float(v) for v in f[2].split('/')] if len(f) > 2 and f[2] else None
    parts.append((f[0], tuple(float(v) for v in f[1].split(',')), rots))
    if len(f) > 3 and f[3] == 'flip':
        FLIP.add(f[0])
conns = opts('--conn')
rip = set((opt('--rip') or '').split(',')) - {''}
base = os.path.splitext(dst)[0]
w0 = base + '_pf0.kicad_pcb'
w1 = base + '_pf1.kicad_pcb'


def copy_side(s_, d_):
    for ext in ('.kicad_pro', '.kicad_dru'):
        a = os.path.splitext(s_)[0] + ext
        if os.path.isfile(a):
            shutil.copy2(a, os.path.splitext(d_)[0] + ext)


STAGE = opt('--stage')
refs = [p[0] for p in parts]
TJ = base + '_pf_tmpl.json'
RJ = base + '_pf_res.json'
if STAGE == 'apply':
    res = json.load(open(RJ))
    out = pcbnew.LoadBoard(base + '_pf0.kicad_pcb')
    for r, (x, y, rot) in res['poses'].items():
        fp = next(f for f in out.GetFootprints() if f.GetReference() == r)
        fp.SetPosition(pcbnew.VECTOR2I(int(round(x * 1e6)), int(round(y * 1e6))))
        fp.SetOrientationDegrees(rot)
    for v in res['vias']:
        vv = pcbnew.PCB_VIA(out)
        vv.SetPosition(pcbnew.VECTOR2I(v['x'], v['y']))
        vv.SetWidth(v['d'])
        vv.SetDrill(v['h'])
        vv.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        vv.SetNet(out.FindNet(v['net']))
        out.Add(vv)
    for t in res['tracks']:
        n_ = pcbnew.PCB_TRACK(out)
        n_.SetStart(pcbnew.VECTOR2I(t['a'][0], t['a'][1]))
        n_.SetEnd(pcbnew.VECTOR2I(t['c'][0], t['c'][1]))
        n_.SetWidth(t['w'])
        n_.SetLayer(out.GetLayerID(t['layer']))
        n_.SetNet(out.FindNet(t['net']))
        out.Add(n_)
    pcbnew.SaveBoard(dst, out)
    for ext in ('.kicad_pro', '.kicad_dru'):
        a = os.path.splitext(src)[0] + ext
        if os.path.isfile(a):
            shutil.copy2(a, os.path.splitext(dst)[0] + ext)
    print(f"placefit apply: {len(res['poses'])} poses, {len(res['tracks'])} tracks, {len(res['vias'])} vias -> {dst}")
    sys.exit(0)
if STAGE != 'rip':
    import subprocess
    r_ = subprocess.run([sys.executable, os.path.abspath(__file__)] + argv + ['--stage', 'rip'], capture_output=True, text=True)
    print(chr(10).join(l for l in r_.stdout.splitlines() if 'memory leak' not in l and 'image handler' not in l))
    if r_.returncode != 0:
        print(r_.stderr[-2000:])
        sys.exit('rip stage failed')
# ---- 0. rip (child process)
if STAGE == 'rip':
  b = pcbnew.LoadBoard(src)
  wins = unary_union([box(*w) for _, w, _ in parts])
  pad_geo = []
  for r in refs:
      fp = b.FindFootprintByReference(r)
      for p in fp.Pads():
          lid = pcbnew.B_Cu if fp.IsFlipped() else pcbnew.F_Cu
          pad_geo.append((mr.poly_of(p.GetEffectivePolygon(lid, pcbnew.ERROR_OUTSIDE)), p.GetNetname()))
  # every non-GND net of a moving part loses the copper touching its pads (it would dangle at the old pad) and is
  # restored afterwards like the --rip nets
  # flipped parts: mirror them in place (same origin) before the templates are taken, so w0 carries them flipped
  for f_ in [f_ for f_ in b.GetFootprints() if f_.GetReference() in FLIP]:
      f_.Flip(f_.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
  # ---- 1. part templates, then a model without the parts
  tmpl = {}
  for r in refs:
      fp = b.FindFootprintByReference(r)
      if hasattr(fp, 'BuildCourtyardCaches'):
          fp.BuildCourtyardCaches()
      side = 'B' if fp.IsFlipped() else 'F'
      lid = pcbnew.B_Cu if side == 'B' else pcbnew.F_Cu
      tmpl[r] = {'side': side, 'ln': 'B.Cu' if side == 'B' else 'F.Cu',
                 'o': (fp.GetPosition().x / 1e6, fp.GetPosition().y / 1e6), 'r0': fp.GetOrientationDegrees(),
                 'court': mr.poly_of(fp.GetCourtyard(pcbnew.B_CrtYd if side == 'B' else pcbnew.F_CrtYd)),
                 'pads': [(p.GetNumber(), p.GetNetname(), mr.poly_of(p.GetEffectivePolygon(lid, pcbnew.ERROR_OUTSIDE)),
                           (p.GetPosition().x / 1e6, p.GetPosition().y / 1e6)) for p in fp.Pads()]}
  rip_explicit = set(rip)
  rip |= set(nn for _, nn in pad_geo if nn and nn != 'GND')
  pcbnew.ZONE_FILLER(b).Fill(b.Zones())
  b.BuildConnectivity()
  conn0 = b.GetConnectivity()
  before_isl = {}
  for f in b.GetFootprints():
      for p in f.Pads():
          if p.GetNetname() in rip:
              before_isl.setdefault(p.GetNetname(), [])
              grp = frozenset(q.GetParentFootprint().GetReference() + '.' + q.GetNumber()
                              for q in [p] + [it.Cast() if hasattr(it, 'Cast') else it for it in conn0.GetConnectedItems(p)]
                              if q.GetClass() == 'PAD')
              if grp not in before_isl[p.GetNetname()]:
                  before_isl[p.GetNetname()].append(grp)
  json.dump({n: len(v) for n, v in before_isl.items()}, open(base + '_pf_before.json', 'w'))
  kill = []
  for t in b.GetTracks():
      n = t.GetNetname()
      if t.GetClass() == 'PCB_VIA':
          c = t.GetPosition()
          g = Point(c.x / 1e6, c.y / 1e6).buffer(t.GetWidth(pcbnew.F_Cu) / 2e6)
      else:
          from shapely.geometry import LineString
          g = LineString([(t.GetStart().x / 1e6, t.GetStart().y / 1e6), (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)]).buffer(t.GetWidth() / 2e6)
      touch = any(pg.intersects(g) and pn == n for pg, pn in pad_geo)
      # --rip nets: copper touching the parts or inside the windows; the parts' other nets: only copper touching them
      if (n in rip_explicit and (touch or g.intersects(wins))) or (n in rip and touch) or (n == 'GND' and touch and t.GetClass() == 'PCB_VIA'):
          kill.append(t)
  for t in kill:
      b.Remove(t)
  print(f"placefit: ripped {len(kill)} items of {sorted(set(rip))} + GND pad vias")
  pcbnew.SaveBoard(w0, b)
  copy_side(src, w0)
  for f in [f for f in b.GetFootprints() if f.GetReference() in refs]:
      b.Remove(f)
  pcbnew.SaveBoard(w1, b)
  copy_side(src, w1)
  from shapely import wkt as _w
  json.dump({r: {'side': t['side'], 'ln': t['ln'], 'o': t['o'], 'r0': t['r0'], 'court': t['court'].wkt,
                 'pads': [(n_, nn, g.wkt, c) for n_, nn, g, c in t['pads']]} for r, t in tmpl.items()}, open(TJ, 'w'))
  sys.exit(0)
from shapely import wkt as _w
tmpl = {r: {'side': t['side'], 'ln': t['ln'], 'o': tuple(t['o']), 'r0': t['r0'], 'court': _w.loads(t['court']),
            'pads': [(n_, nn, _w.loads(g), tuple(c)) for n_, nn, g, c in t['pads']]} for r, t in json.load(open(TJ)).items()}
B = mr.Board(w1, ('*',))
R = mr.Router(B)
have0 = set()
for t in B.b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        have0.add(('v', t.GetPosition().x, t.GetPosition().y, t.GetNetname()))
    else:
        have0.add(('t', t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y, t.GetLayer(), t.GetNetname()))
side_court = {'F': [], 'B': []}
for f in B.b.GetFootprints():
    s_ = 'B' if f.IsFlipped() else 'F'
    g = mr.poly_of(f.GetCourtyard(pcbnew.B_CrtYd if s_ == 'B' else pcbnew.F_CrtYd))
    if not g.is_empty:
        side_court[s_].append(g)
bans = {'F': [], 'B': []}
for z in B.b.Zones():
    if z.GetIsRuleArea() and (any(fnmatch.fnmatchcase(z.GetZoneName(), p) for p in BAN_PATS) or z.GetDoNotAllowFootprints()):
        g = mr.poly_of(z.Outline())
        for s_, lid in (('F', pcbnew.F_Cu), ('B', pcbnew.B_Cu)):
            if z.IsOnLayer(lid):
                bans[s_].append(g)
for f in B.b.GetFootprints():
    for z in f.Zones():
        if z.GetIsRuleArea() and z.GetDoNotAllowFootprints():
            g = mr.poly_of(z.Outline())
            for s_, lid in (('F', pcbnew.F_Cu), ('B', pcbnew.B_Cu)):
                if z.IsOnLayer(lid):
                    bans[s_].append(g)
inner = B.outline.buffer(-0.3)
# B-side height windows (K9 battery pouch <= 0.55 mm, K8 shield bay <= 0.6 mm; not expressible in the DRU): a part that
# is outside a window must not move into it - same gate as tools/layout/padalign.py. --height-ok REF,REF exempts parts
# whose (documented) height fits the window.
HWIN = [mr.poly_of(z.Outline()) for z in B.b.Zones() if z.GetIsRuleArea() and z.GetZoneName() in ('K9_BATT_WINDOW', 'K8_SHIELD_BAY')]
HOK = set((opt('--height-ok') or '').split(',')) - {''}
# Edge clearance (user rule 2026-10-02: parts that are not edge-bound keep away from the board edge): a pose may not
# bring the courtyard closer than --edge-min mm to the outline than the part already was.
EDGE_MIN = float(opt('--edge-min', '0'))
_ps = pcbnew.SHAPE_POLY_SET()
B.b.GetBoardPolygonOutlines(_ps, False)
EDGE = mr.poly_of(_ps).boundary


def pose(r, x, y, rot):
    t = tmpl[r]
    ox, oy = t['o']
    dr = (rot - t['r0']) % 360

    def tf(g):
        return affinity.translate(affinity.rotate(g, -dr, origin=(ox, oy)), x - ox, y - oy)

    def tp(xy):
        return tf(Point(xy)).coords[0]
    return tf(t['court']), [(num, net, tf(g), tp(c)) for num, net, g, c in t['pads']]


def legal(r, court, pads):
    s_ = tmpl[r]['side']
    ln = tmpl[r]['ln']
    if not inner.contains(court):
        return 'outline'
    if any(g.distance(court) < 0.02 for g in side_court[s_]):
        return 'courtyard'
    for r2 in refs:
        if r2 != r and r2 not in placed and tmpl[r2]['side'] == s_ and tmpl[r2]['court'].distance(court) < 0.02:
            return 'courtyard:' + r2
    if any(g.intersects(court) for g in bans[s_]):
        return 'ban-area'
    if s_ == 'B' and r not in HOK and any(g.intersects(court) and not g.intersects(tmpl[r]['court']) for g in HWIN):
        return 'height-window'
    if EDGE_MIN > 0:
        d_ = court.distance(EDGE)
        if d_ < EDGE_MIN and d_ < tmpl[r]['court'].distance(EDGE) - 1e-6:
            return 'edge-clearance'
    for num, net, g, c in pads:
        ex = frozenset(k for k, e in B.pexempt.items() if e.intersects(g))
        for i in B.trees[ln].query(g.buffer(2.1)):
            geo, n2, kind = B.items[ln][i]
            if n2 == net and net:
                continue
            if geo.distance(g) < mr.need(net, n2, kind, ex) + 0.005:
                return f'copper:{n2.split("/")[-1]}'
        for i in B.htree.query(g.buffer(1.0)):
            hp, hr, hn = B.holes[i]
            if hn != net and hp.distance(g) < hr + 0.25:
                return 'hole'
    return None


def insert(r, pads):
    """add the posed part's pads to the obstacle model; returns an undo token"""
    ln = tmpl[r]['ln']
    tok = []
    for num, net, g, c in pads:
        B.items[ln].append((g, net, 'pad'))
        tok.append((ln, len(B.items[ln]) - 1))
    B.rebuild()
    return tok


def remove(tok):
    for ln, i in sorted(tok, key=lambda t: -t[1]):
        del B.items[ln][i]
    B.rebuild()


placed = {}       # ref -> (x, y, rot, pads)


def pad_island(r, num, pads):
    for n_, net, g, c in pads:
        if n_ == num:
            I = {ln: Polygon() for ln in mr.SIG}
            I[tmpl[r]['ln']] = g
            I['__pads__'] = [c]
            return net, I
    raise KeyError(f'{r}.{num}')


def find_island(net, ref, num):
    """island of an existing (not re-placed) pad, or of an already placed part's pad merged into the model"""
    if ref in placed:
        return pad_island(ref, num, placed[ref][3])[1]
    fp = B.b.FindFootprintByReference(ref)
    p = next(q for q in fp.Pads() if q.GetNumber() == num)
    xy = (p.GetPosition().x / 1e6, p.GetPosition().y / 1e6)
    for I in R.islands(net):
        if any(abs(a - xy[0]) < 1e-3 and abs(b_ - xy[1]) < 1e-3 for a, b_ in I.get('__pads__', [])):
            return I
    return None


def path_cost(segs, vias):
    return sum(math.hypot(c[0] - a[0], c[1] - a[1]) for _, a, c, _ in segs) + 1.0 * len(vias)


def esc_cost(net, I, ln_hint):
    el = 'B.Cu' if mr.cls(net) in ('Analog_Precision', 'Ref_Kelvin', 'RF_Input', 'RF_50R') else 'In3.Cu'
    T = {ln: Polygon() for ln in mr.SIG}
    own = unary_union([v for k_, v in I.items() if not k_.startswith('__') and not v.is_empty])
    T[el] = Point(I['__pads__'][0]).buffer(3.0).difference(own.buffer(0.35))
    T['__pads__'] = []
    return R.route_pair(net, I, T)


def score(r, pads, commit=False):
    total = 0.0
    detail = []
    for spec in conns:
        a_, _, b_ = spec.partition('-')
        if b_ == 'ESC' and a_.split('.')[0] in refs and a_.split('.')[0] not in placed and a_.split('.')[0] != r:
            # the boxed part moves later: score this pose by its pad's escape with the part at its original pose
            br, bn = a_.split('.')
            ob = tmpl[br]
            court_b, pads_b = pose(br, ob['o'][0], ob['o'][1], ob['r0'])
            tok_b = insert(br, pads_b)
            try:
                netb, Ib = pad_island(br, bn, pads_b)
                res, why = esc_cost(netb, Ib, None)
            finally:
                remove(tok_b)
            if res is None:
                total += 1000
                detail.append(f'{a_}:esc(orig) FAIL')
            else:
                c_ = path_cost(res[0], res[1])
                total += c_
                detail.append(f'{a_}:esc(orig) {c_:.2f}')
            continue
        if b_ == 'ESC' and a_.split('.')[0] not in refs:
            # a fixed part's boxed pad: does this pose let it escape? (evaluated for every mover; committed once, by
            # the last mover)
            fr, fn = a_.split('.')
            fpp = next((q for q in B.b.FindFootprintByReference(fr).Pads() if q.GetNumber() == fn), None)
            if fpp is None:
                continue
            I = find_island(fpp.GetNetname(), fr, fn)
            if I is None:
                continue
            if any(not I[ln].is_empty for ln in ('In3.Cu',)) and len(set(I.get('__pads__', []))) > 1:
                continue
            res, why = esc_cost(fpp.GetNetname(), I, None)
            if res is None:
                total += 1000
                detail.append(f'{a_}:esc FAIL')
            else:
                c_ = path_cost(res[0], res[1])
                total += c_
                detail.append(f'{a_}:esc {c_:.2f}')
                if commit and r == refs[-1]:
                    R.commit(fpp.GetNetname(), res[0], res[1])
            continue
        ends = [a_, b_]
        mine = [e for e in ends if e.split('.')[0] == r]
        if not mine:
            continue
        me = mine[0]
        other = b_ if me == a_ else a_
        net, I = pad_island(r, me.split('.')[1], pads)
        if other == 'VIA':
            ok = R.via_legal_exact(net, Point(I['__pads__'][0]), *mr.VIA.get(mr.cls(net), (0.45, 0.2)), B.bans(net))
            total += 0 if ok else 1000
            detail.append(f'{me}:via {"ok" if ok else "NO"}')
            if ok and commit:
                x, y = I['__pads__'][0]
                vd, vh = mr.VIA.get(mr.cls(net), (0.45, 0.2))
                R.commit(net, [], [(x, y, vd, vh)])
            continue
        if other == 'ESC':
            # escapability: stub + via from this pad to any free In3 cell within 3 mm (B for nets kept off In3)
            el = 'B.Cu' if mr.cls(net) in ('Analog_Precision', 'Ref_Kelvin', 'RF_Input', 'RF_50R') else 'In3.Cu'
            T = {ln: Polygon() for ln in mr.SIG}
            T[el] = Point(I['__pads__'][0]).buffer(3.0).difference(I[tmpl[r]['ln']].buffer(0.35))
            T['__pads__'] = []
            res, why = R.route_pair(net, I, T)
            if res is None:
                total += 1000
                detail.append(f'{me}:esc FAIL')
            else:
                c_ = path_cost(res[0], res[1])
                total += c_
                detail.append(f'{me}:esc {c_:.2f}')
                if commit:
                    R.commit(net, res[0], res[1])
            continue
        if other == 'NET':
            cand = [J for J in R.islands(net) if not J.get('__pads__') or True]
            gI = I[tmpl[r]['ln']]
            best = None
            for J in cand:
                gJ = unary_union([v for k_, v in J.items() if not k_.startswith('__') and not v.is_empty])
                if gJ.is_empty or gJ.distance(gI) < 1e-6:
                    continue
                d = gJ.distance(gI)
                if best is None or d < best[0]:
                    best = (d, J)
            if best is None:
                detail.append(f'{me}:net none')
                continue
            T = best[1]
        else:
            oref, onum = other.split('.')
            if oref in refs and oref not in placed:
                continue           # evaluated when that part is placed
            T = find_island(net, oref, onum)
            if T is None:
                total += 1000
                detail.append(f'{me}->{other}: island?')
                continue
        res, why = R.route_pair(net, I, T)
        if res is None:
            total += 1000
            detail.append(f'{me}->{other}: FAIL')
        else:
            c_ = path_cost(res[0], res[1])
            total += c_
            detail.append(f'{me}->{other}: {c_:.2f}')
            if commit:
                R.commit(net, res[0], res[1])
    return total, detail


report = {}
for r, win, rots in parts:
    ts = time.time()
    t = tmpl[r]
    x0, y0, x1, y1 = win
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rl = rots if rots is not None else [t['r0']]
    cands = []
    why = {}
    nx, ny = int((x1 - x0) / STEP) + 1, int((y1 - y0) / STEP) + 1
    for i in range(nx):
        for j in range(ny):
            x, y = x0 + i * STEP, y0 + j * STEP
            for rot in rl:
                court, pads = pose(r, x, y, rot)
                w = legal(r, court, pads)
                if w:
                    why[w] = why.get(w, 0) + 1
                    continue
                cands.append((math.hypot(x - cx, y - cy), x, y, rot, court, pads))
    cands.sort(key=lambda c: c[0])
    if not cands:
        # keep the original pose (if it is still legal) and route its connections from there
        ox_, oy_ = t['o']
        court, pads = pose(r, ox_, oy_, t['r0'])
        w_ = legal(r, court, pads)
        print(f"  {r}: no legal pose in window; blockers {sorted(why.items(), key=lambda kv: -kv[1])[:6]}; "
              f"kept at its original pose ({'legal' if w_ is None else 'ILLEGAL: ' + w_})")
        insert(r, pads)
        side_court[t['side']].append(court)
        placed[r] = (ox_, oy_, t['r0'], pads)
        sc2, det2 = score(r, pads, commit=True)
        report[r] = {'ok': w_ is None and sc2 < 1000, 'kept': True, 'score': round(sc2, 2), 'detail': det2}
        print(f"     routes from the original pose: {det2}")
        continue
    # spread the evaluated poses over the window: take every k-th legal pose so the --keep budget covers it
    k = max(1, len(cands) // KEEP)
    pool = cands[::k][:KEEP]
    best = None
    for d, x, y, rot, court, pads in pool:
        tok = insert(r, pads)
        sc, det = score(r, pads)
        remove(tok)
        if best is None or sc < best[0]:
            best = (sc, x, y, rot, court, pads, det)
    sc, x, y, rot, court, pads, det = best
    if sc >= 1000:
        # no pose in the window routes all its connections: never commit an unroutable pose - keep the original one
        ox_, oy_ = t['o']
        court, pads = pose(r, ox_, oy_, t['r0'])
        w_ = legal(r, court, pads)
        print(f"  {r}: {len(cands)} legal poses, scored {len(pool)}, none routes all connections (best {det}); "
              f"kept at its original pose ({'legal' if w_ is None else 'ILLEGAL: ' + w_})")
        insert(r, pads)
        side_court[t['side']].append(court)
        placed[r] = (ox_, oy_, t['r0'], pads)
        sc2, det2 = score(r, pads, commit=True)
        report[r] = {'ok': False, 'kept': True, 'unroutable_window': True, 'score': round(sc2, 2), 'detail': det2}
        print(f"     routes from the original pose: {det2}")
        continue
    insert(r, pads)
    side_court[t['side']].append(court)
    placed[r] = (x, y, rot, pads)
    sc2, det2 = score(r, pads, commit=True)
    print(f"  {r}: {len(cands)} legal poses, scored {len(pool)}; best ({x:.3f},{y:.3f}) rot {rot:.0f} score {sc:.2f} "
          f"{det2} ({time.time() - ts:.0f} s)")
    report[r] = {'ok': sc < 1000, 'x': round(x, 4), 'y': round(y, 4), 'rot': rot % 360, 'score': round(sc, 2), 'detail': det2}
# ---- 2b. every ripped net back to (at most) its island count before the rip
before_isl = json.load(open(base + '_pf_before.json'))
for n_, k_ in sorted(before_isl.items()):
    for _ in range(30):
        isl_ = R.islands(n_)
        # the re-placed parts' pads are not in the model's pad list: a placed pad no copper reaches is an island too
        loose = []
        for r, (x, y, rot, pads) in placed.items():
            for num, net, g, c in pads:
                if net == n_ and not any(not I[tmpl[r]['ln']].is_empty and I[tmpl[r]['ln']].intersects(g)
                                         for I in isl_):
                    loose.append((r, num, pads))
        if len(isl_) + len(loose) <= k_:
            break
        if loose:
            r, num, pads = loose[0]
            _, A_ = pad_island(r, num, pads)
            gA = A_[tmpl[r]['ln']]
            cand = []
            for I in isl_:
                gI = unary_union([v for kk, v in I.items() if not kk.startswith('__') and not v.is_empty])
                if not gI.is_empty:
                    cand.append((gI.distance(gA), I))
            if not cand:
                break
            d_, T_ = min(cand, key=lambda t: t[0])
            res, why = R.route_pair(n_, A_, T_)
        elif len(isl_) >= 2:
            gs = [unary_union([v for kk, v in I.items() if not kk.startswith('__') and not v.is_empty]) for I in isl_]
            d_, i_, j_ = min((gs[i].distance(gs[j]), i, j) for i in range(len(isl_)) for j in range(i + 1, len(isl_)))
            res, why = R.route_pair(n_, isl_[i_], isl_[j_])
        else:
            break
        if res is None:
            print(f"  restore {n_.split('/')[-1]}: {why} (gap {d_:.2f})")
            break
        R.commit(n_, res[0], res[1])
        print(f"  restore {n_.split('/')[-1]}: joined (gap {d_:.2f})")
# ---- 3. write: poses + the committed routes (items of the model board that are new) -> JSON -> apply child process
newt, newv = [], []
for t in B.b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        k_ = ('v', t.GetPosition().x, t.GetPosition().y, t.GetNetname())
        if k_ not in have0:
            newv.append({'x': t.GetPosition().x, 'y': t.GetPosition().y, 'd': t.GetWidth(pcbnew.F_Cu), 'h': t.GetDrill(), 'net': t.GetNetname()})
    else:
        k_ = ('t', t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y, t.GetLayer(), t.GetNetname())
        if k_ not in have0:
            newt.append({'a': [t.GetStart().x, t.GetStart().y], 'c': [t.GetEnd().x, t.GetEnd().y], 'w': t.GetWidth(),
                         'layer': B.b.GetLayerName(t.GetLayer()), 'net': t.GetNetname()})
json.dump({'poses': {r: [x, y, rot] for r, (x, y, rot, pads) in placed.items()}, 'tracks': newt, 'vias': newv}, open(RJ, 'w'))
import subprocess
r_ = subprocess.run([sys.executable, os.path.abspath(__file__)] + argv + ['--stage', 'apply'], capture_output=True, text=True)
print(chr(10).join(l for l in r_.stdout.splitlines() if 'memory leak' not in l and 'image handler' not in l))
if r_.returncode != 0:
    print(r_.stderr[-2000:])
if opt('--report'):
    json.dump(report, open(opt('--report'), 'w'), indent=1)
print(f"placefit: {sum(1 for v in report.values() if v.get('ok'))} of {len(parts)} parts placed, {len(newt) + len(newv)} track/via items added -> {dst}")

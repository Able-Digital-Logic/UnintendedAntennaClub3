"""fanout.py IN.kicad_pcb OUT.kicad_pcb REF PIN[:in|out|any] ... [--margin 0.01] [--max-len 2.2] [--report R.json]
                [--box x0,y0,x1,y1]

Escape-pattern solver for fine-pitch packages (user rules 2026-10-02: via first, least track, straight or 45 degrees).
For every listed pin of REF it enumerates escapes from the pin's inner or outer end:
    stub straight along the pin axis for a, an optional single 45-degree jog of j (left or right), then straight for b,
    ending in a 0.45/0.20 via (POFV)  -> octilinear, at most two bends, shortest first;
then a depth-first search with backtracking assigns one escape per pin so that every stub and via clears
  * all existing copper of other nets with this board's pairwise rule model (mr.py need(): DRU class clearances,
    HS/clock/SW/RF/analog spacing, courtyard exemptions per item like KiCad's intersectsCourtyard), rule-area bans,
    holes (hole-to-copper 0.25, hole-to-hole 0.25), the board edge,
  * the escapes already chosen for the other pins (same model, + --margin).
Pins are solved most-constrained first. Stub width = the net's class width, or its neck width inside the IC courtyard
(DRU neck-down rules). The chosen copper is written to OUT; the router then joins each via to its destination.
KiCad python, scratch copies only."""
import itertools
import json
import math
import os
import shutil
import sys

import pcbnew
from shapely.geometry import LineString, Point, box
from shapely.strtree import STRtree

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import mr  # noqa: E402

argv = sys.argv[1:]


def opt(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


src, dst, ref = argv[0], argv[1], argv[2]
specs = [a for a in argv[3:] if not a.startswith('--') and argv[argv.index(a) - 1] not in
         ('--margin', '--max-len', '--report', '--box', '--nodes', '--seconds', '--order', '--cands', '--tries', '--keep')]
MARG = float(opt('--margin', '0.01'))
MAXL = float(opt('--max-len', '2.2'))
CLIP = box(*[float(v) for v in opt('--box').split(',')]) if opt('--box') else None
VD, VH = 0.45, 0.2
B = mr.Board(src, ('*',))
R = mr.Router(B)
b = B.b
from shapely.prepared import prep
PEX = {k: prep(e) for k, e in B.exempt_geo.items() if not e.is_empty}
fp = b.FindFootprintByReference(ref)
lay = 'B.Cu' if fp.IsFlipped() else 'F.Cu'
LID = B.L[lay]
court = B.court.get(ref)
fc = fp.GetPosition()
fcx, fcy = fc.x / 1e6, fc.y / 1e6
pins = {}
for p in fp.Pads():
    pins[p.GetNumber()] = p


def pin_axis(p):
    """unit vector along the pad's long axis pointing AWAY from the package centre, and the inner/outer end points"""
    g = mr.poly_of(p.GetEffectivePolygon(LID, pcbnew.ERROR_INSIDE))
    x0, y0, x1, y1 = g.bounds
    cx, cy = p.GetPosition().x / 1e6, p.GetPosition().y / 1e6
    if (x1 - x0) >= (y1 - y0):
        ux, uy = (1.0, 0.0) if cx > fcx else (-1.0, 0.0)
        outer = (x1 if ux > 0 else x0, cy)
        inner = (x0 if ux > 0 else x1, cy)
    else:
        ux, uy = (0.0, 1.0) if cy > fcy else (0.0, -1.0)
        outer = (cx, y1 if uy > 0 else y0)
        inner = (cx, y0 if uy > 0 else y1)
    return (ux, uy), inner, outer, g


DBG = []


def item_clear(net, geo_line, w, kind_self, extra):
    """geo_line: LineString (track centre) or Point (via centre); w: width (track) or diameter (via)"""
    shape = geo_line.buffer(w / 2, 8)
    ex = frozenset(k for k, e in PEX.items() if e.intersects(shape))
    for ln in ([lay] if kind_self == 'track' else list(mr.SIG)):
        for i in B.trees[ln].query(shape.buffer(2.1)):
            geo, n2, kind = B.items[ln][i]
            if n2 == net:
                continue
            if geo.distance(geo_line) - w / 2 < mr.need(net, n2, kind, ex) + MARG:
                if len(DBG) < 6 and '--debug' in sys.argv:
                    DBG.append((kind_self, list(geo_line.coords)[:2], ln, n2.split('/')[-1], kind, round(geo.distance(geo_line) - w / 2, 3), mr.need(net, n2, kind, ex)))
                return False
    for g2, n2, kind2, lays2 in extra:
        if n2 == net:
            continue
        if kind_self == 'track' and lay not in lays2:
            continue
        exx = frozenset(k for k, e in PEX.items() if (e.intersects(shape) or e.intersects(g2)))
        if g2.distance(shape) < mr.need(net, n2, kind2, exx) + MARG:
            return False
    for item in B.bans(net):
        if item[0] == 'VIAHOLE':
            if kind_self == 'via' and item[1].distance(geo_line) < item[2] + VD / 2:
                return False
            continue
        g, lays, tb, vb = item
        if kind_self == 'track' and tb and lay in lays and g.intersects(shape):
            return False
        if kind_self == 'via' and vb and g.intersects(shape):
            return False
    return True


def cand_paths(num, mode):
    p = pins[num]
    net = p.GetNetname()
    (ux, uy), inner, outer, g = pin_axis(p)
    w_c = mr.width_of(net)
    w_n = mr.neck_of(net)
    out = []
    pcx, pcy = p.GetPosition().x / 1e6, p.GetPosition().y / 1e6
    r2 = math.sqrt(0.5)
    dirs = [(1, 0), (r2, r2), (0, 1), (-r2, r2), (-1, 0), (-r2, -r2), (0, -1), (r2, -r2)]
    for dx, dy in dirs:
        # outward = away from the package centre (dot > 0); inward = toward it
        dot = (pcx - fcx) * dx + (pcy - fcy) * dy
        side = 'out' if dot > 0 else 'in'
        if mode != 'any' and side != mode:
            continue
        # support point of the pad polygon in direction d, pulled 0.05 inside
        coords = list(g.exterior.coords)
        best_ = max(coords, key=lambda q: q[0] * dx + q[1] * dy)
        mx = max(q[0] * dx + q[1] * dy for q in coords)
        sup = [q for q in coords if q[0] * dx + q[1] * dy > mx - 1e-3]
        sx = sum(q[0] for q in sup) / len(sup)
        sy = sum(q[1] for q in sup) / len(sup)
        if not g.buffer(1e-3).contains(Point(sx, sy)):
            sx, sy = best_
        # axis directions: stay on the pad's own centre line (the polygon approximation is not symmetric)
        if abs(dx) < 1e-6 and g.buffer(1e-3).contains(Point(pcx, sy)):
            sx = pcx
        if abs(dy) < 1e-6 and g.buffer(1e-3).contains(Point(sx, pcy)):
            sy = pcy
        sx, sy = sx - dx * 0.05, sy - dy * 0.05
        px, py = -dy, dx
        diag = abs(dx) > 1e-6 and abs(dy) > 1e-6
        for a in [0.1 + 0.1 * k for k in range(0, 16)]:
            for j in [0.0] + [0.1 * k for k in range(1, 6)]:
                for sgn in ((1,) if j == 0 else (1, -1)):
                    for bb in ([0.0] if j == 0 else [0.0] + [0.1 * k for k in range(1, 7)]):
                        pts = [(sx, sy), (sx + dx * a, sy + dy * a)]
                        if j > 0:
                            q = pts[-1]
                            # 45-degree jog: rotate the direction by +/-45 degrees
                            if diag:
                                jx, jy = (dx if sgn > 0 else 0.0, dy if sgn < 0 else 0.0)
                                n_ = math.hypot(jx, jy)
                                jx, jy = jx / n_, jy / n_
                            else:
                                jx, jy = (dx + px * sgn) * r2, (dy + py * sgn) * r2
                            pts.append((q[0] + jx * j * 1.41421356, q[1] + jy * j * 1.41421356))
                            if bb > 0:
                                q = pts[-1]
                                pts.append((q[0] + dx * bb, q[1] + dy * bb))
                        L = sum(math.hypot(q[0] - p_[0], q[1] - p_[1]) for p_, q in zip(pts, pts[1:]))
                        if L > MAXL:
                            continue
                        via = pts[-1]
                        if CLIP is not None and not CLIP.contains(Point(via)):
                            continue
                        bends = (1 if j > 0 else 0) + (1 if j > 0 and bb > 0 else 0)
                        out.append((L + 0.3 * bends, side, pts, via))
    out.sort(key=lambda c: c[0])
    return net, w_c, w_n, out


def width_for(net, seg_line, w_c, w_n):
    return w_n if (court is not None and seg_line.buffer(w_n / 2).intersects(court)) else w_c


modes = {}
for s in specs:
    n, _, m = s.partition(':')
    modes[n] = m or 'any'
cands = {}
for n, m in modes.items():
    net, w_c, w_n, cs = cand_paths(n, m)
    good = []
    why = {'track': 0, 'via_clear': 0, 'via_exact': 0}
    for cost, side, pts, via in cs:
        ok = True
        segs = []
        for a_, c_ in zip(pts, pts[1:]):
            ln_ = LineString([a_, c_])
            w = width_for(net, ln_, w_c, w_n)
            if not item_clear(net, ln_, w, 'track', []):
                ok = False
                break
            segs.append((ln_, w))
        if not ok:
            why['track'] += 1
            continue
        vd_, vh_ = mr.VIA.get(mr.cls(net), (VD, VH))
        if not item_clear(net, Point(via), vd_, 'via', []):
            why['via_clear'] += 1
            continue
        if not R.via_legal_exact(net, Point(via), vd_, vh_, B.bans(net)):
            why['via_exact'] += 1
            continue
        good.append((cost, side, segs, via))
        if len(good) >= int(opt('--keep', '150')):
            break
    cands[n] = (net, good)
    if DBG:
        for d_ in DBG:
            print('     dbg', d_)
        DBG.clear()
    print(f"  pin {n:3s} {net.split('/')[-1][:16]:16s} {len(good)} legal escapes" + ('' if good else f'  (rejected: {why}, {len(cs)} candidates)'))
order = sorted(cands, key=lambda n: len(cands[n][1]))
if opt('--order'):
    pref = opt('--order').split(',')
    order = [n for n in pref if n in cands] + [n for n in order if n not in pref]
chosen = {}


def compatible(n, cand, placed):
    net, _ = cands[n]
    cost, side, segs, via = cand
    extra = []
    for n2, (c2) in placed.items():
        net2 = cands[n2][0]
        _, _, segs2, via2 = c2
        for l2, w2 in segs2:
            extra.append((l2.buffer(w2 / 2, 8), net2, 'track', {lay}))
        extra.append((Point(via2).buffer(mr.VIA.get(mr.cls(net2), (VD, VH))[0] / 2, 16), net2, 'via', set(mr.SIG)))
    for ln_, w in segs:
        if not item_clear(net, ln_, w, 'track', extra):
            return False
    if not item_clear(net, Point(via), mr.VIA.get(mr.cls(net), (VD, VH))[0], 'via', extra):
        return False
    for n2, c2 in placed.items():
        if Point(c2[3]).distance(Point(via)) < VH + 0.25 + MARG:      # hole to hole (centre distance)
            return False
    return True


sys.setrecursionlimit(10000)
best = {'n': -1, 'sol': None}
nodes = [0]
LIMIT = int(opt('--nodes', '60000'))
import time as _t
T0 = _t.time()
TLIM = float(opt('--seconds', '300'))


def dfs(i, placed):
    nodes[0] += 1
    if len(placed) > best['n']:
        best['n'], best['sol'] = len(placed), dict(placed)
    if i == len(order) or nodes[0] > LIMIT or _t.time() - T0 > TLIM:
        return
    if len(placed) + (len(order) - i) <= best['n']:
        return                       # bound: cannot beat the best
    n = order[i]
    tried = 0
    for cand in cands[n][1][:int(opt('--cands', '40'))]:
        if tried >= int(opt('--tries', '12')):
            break
        if compatible(n, cand, placed):
            tried += 1
            placed[n] = cand
            dfs(i + 1, placed)
            del placed[n]
            if best['n'] == len(order) or nodes[0] > LIMIT or _t.time() - T0 > TLIM:
                return
    dfs(i + 1, placed)               # leave pin n to the router


dfs(0, {})
sol = best['sol'] or {}
print(f"fanout: {len(sol)} of {len(order)} pins escaped ({nodes[0]} search nodes)")
rep = {}
for n, (cost, side, segs, via) in sol.items():
    net = cands[n][0]
    nobj = b.FindNet(net)
    for ln_, w in segs:
        (ax, ay), (cx, cy) = ln_.coords[0], ln_.coords[-1]
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(int(round(ax * 1e6)), int(round(ay * 1e6))))
        t.SetEnd(pcbnew.VECTOR2I(int(round(cx * 1e6)), int(round(cy * 1e6))))
        t.SetWidth(int(round(w * 1e6)))
        t.SetLayer(LID)
        t.SetNet(nobj)
        b.Add(t)
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I(int(round(via[0] * 1e6)), int(round(via[1] * 1e6))))
    vd_, vh_ = mr.VIA.get(mr.cls(net), (VD, VH))
    v.SetWidth(int(vd_ * 1e6))
    v.SetDrill(int(vh_ * 1e6))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(nobj)
    b.Add(v)
    rep[n] = {'net': net, 'side': side, 'via': [round(via[0], 3), round(via[1], 3)],
              'segs': [[[round(v, 4) for v in l.coords[0]], [round(v, 4) for v in l.coords[-1]], round(w, 3)] for l, w in segs],
              'len': round(sum(l.length for l, _ in segs), 3), 'bends': max(0, len(segs) - 1)}
    print(f"   pin {n:3s} {net.split('/')[-1][:16]:16s} {side:3s} via ({via[0]:.3f},{via[1]:.3f}) len {rep[n]['len']:.2f} bends {rep[n]['bends']}")
for n in order:
    if n not in sol:
        print(f"   pin {n:3s} {cands[n][0].split('/')[-1][:16]:16s} UNSOLVED ({len(cands[n][1])} legal alone)")
pcbnew.SaveBoard(dst, b)
for ext in ('.kicad_pro', '.kicad_dru'):
    s = os.path.splitext(src)[0] + ext
    if os.path.isfile(s):
        shutil.copy2(s, os.path.splitext(dst)[0] + ext)
if opt('--report'):
    json.dump(rep, open(opt('--report'), 'w'), indent=1)

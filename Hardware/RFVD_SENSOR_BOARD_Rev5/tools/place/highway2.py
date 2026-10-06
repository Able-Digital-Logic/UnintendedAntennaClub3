"""highway2.py IN.kicad_pcb OUT.kicad_pcb [--gain 0.06] [--min-excess 0.6] [--passes A,B] [--limit N] [--report R.json]

Topology-safe signal-highway clean-up (user request 2026-10-02 night: clean tracks, no zig-zags or weird geometry,
move blocking vias, one dominant direction per layer / region). Router preferences from the environment (mr.py):
MR_DIRPREF, MR_DIR_PERP, MR_DIR_DIAG, MR_T45, MR_MARGIN.

Every routed net (Default / HighSpeed_Digital / Harness_IO, minus protected buses) is cut into CHAINS: runs of track on
one layer between terminals (pads, vias, T-junctions, dead ends).
  pass A  chain straightening: a chain whose cost exceeds its ideal by > --min-excess is ripped and re-routed between
          the SAME two terminal points (layer changes allowed); kept only if the cost drops by >= --gain.
  pass B  via relocation: a via joining exactly two chains (a pass-through layer change) is ripped with both chains
          and the far terminals are re-joined (the router may place the layer change anywhere); kept only if cheaper.
Cost = length x direction multiplier (preferred axis 1, 45 deg MR_DIR_DIAG, perpendicular MR_DIR_PERP, non-octilinear
2.0) + MR_T45 per segment + 1.2 per via - the router's own weights. Terminals never move, so connectivity is
preserved; any failure restores the old copper. One board load (removed items are kept alive: see highway.py)."""
import collections
import fnmatch
import json
import math
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import mr  # noqa: E402
import pcbnew  # noqa: E402
from shapely.geometry import LineString, Point, Polygon  # noqa: E402

argv = sys.argv[1:]


def opt(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


src, dst = argv[0], argv[1]
if os.path.normcase(os.path.realpath(dst)).startswith(mr.PROTECTED):
    sys.exit('refusing to write into the project folder')
GAIN = float(opt('--gain', '0.06'))
MINX = float(opt('--min-excess', '0.6'))
PASSES = (opt('--passes') or 'A,B').split(',')
LIMIT = int(opt('--limit', '100000'))
OK_CLS = ('Default', 'HighSpeed_Digital', 'Harness_IO')
SKIP_PATS = ('*SD_*', '*PSRAM*', '*EXTADC*', '*ADC_*', 'USB_*', '*BUCK_SYNC*', '*TP_RST*', '*LCD_RST*')
work = dst + '.hw2.kicad_pcb'
shutil.copy2(src, work)
for ext in ('.kicad_pro', '.kicad_dru'):
    s_ = os.path.splitext(src)[0] + ext
    if os.path.isfile(s_):
        shutil.copy2(s_, os.path.splitext(dst)[0] + ext)
B = mr.Board(work, ('*',))
R = mr.Router(B)
b = B.b
T45 = float(os.environ.get('MR_T45', '0.35'))
VIAC = 1.2
LC = {'F.Cu': float(os.environ.get('MR_LC_F', '1.15')), 'In3.Cu': float(os.environ.get('MR_LC_IN3', '1.0')),
      'B.Cu': float(os.environ.get('MR_LC_B', '1.15'))}


def seg_mul(ln, a, c):
    dx, dy = c[0] - a[0], c[1] - a[1]
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return 1.0
    regs, dflt = mr.DIRPREF.get(ln, ([], None))
    mx, my = (a[0] + c[0]) / 2, (a[1] + c[1]) / 2
    ax = dflt
    for (x0, y0, x1, y1), a_ in regs:
        if x0 <= mx <= x1 and y0 <= my <= y1:
            ax = a_
            break
    horiz, vert = abs(dy) < 1e-4, abs(dx) < 1e-4
    diag = abs(abs(dx) - abs(dy)) < 1e-3
    if not (horiz or vert or diag):
        return 2.0
    if ax is None:
        return 1.0
    if (ax == 'H' and horiz) or (ax == 'V' and vert):
        return 1.0
    return mr.DIR_DIAG if diag else mr.DIR_PERP


def cost_mm(segs, nvias):
    """segs: [(ln, (x,y) mm, (x,y) mm)]"""
    return sum(math.hypot(c[0] - a[0], c[1] - a[1]) * seg_mul(ln, a, c) * LC.get(ln, 1.0) for ln, a, c in segs) \
        + T45 * len(segs) + VIAC * nvias


def ideal_cost(ln, p, q):
    """cheapest conceivable cost between two points on one layer: octilinear distance at multiplier 1"""
    dx, dy = abs(q[0] - p[0]), abs(q[1] - p[1])
    return (max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)) * LC.get(ln, 1.0) + T45


def snapshot(net):
    tr, vi = [], []
    for t in b.GetTracks():
        if t.GetNetname() != net:
            continue
        if t.GetClass() == 'PCB_VIA':
            c = t.GetPosition()
            vi.append((c.x, c.y, t.GetWidth(pcbnew.F_Cu), t.GetDrill()))
        else:
            ln = b.GetLayerName(t.GetLayer())
            tr.append((ln, (t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y), t.GetWidth()))
    return tr, vi


def remove_items(net, tr_params, vi_params):
    want_t = set(tr_params)
    want_v = set((x, y) for x, y, d, h in vi_params)
    kill = []
    for t in b.GetTracks():
        if t.GetNetname() != net:
            continue
        if t.GetClass() == 'PCB_VIA':
            c = t.GetPosition()
            if (c.x, c.y) in want_v:
                kill.append(('v', t, c.x, c.y, t.GetWidth(pcbnew.F_Cu)))
        else:
            k = (b.GetLayerName(t.GetLayer()), (t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y), t.GetWidth())
            if k in want_t:
                kill.append(('t', t) + k)
    for item in kill:
        if item[0] == 'v':
            _, t, x, y, d = item
            bb = tuple(round(v, 5) for v in Point(x / 1e6, y / 1e6).buffer(d / 2e6, 16).bounds)
            for ln in mr.SIG:
                for i, (geo, n2, k2) in enumerate(B.items[ln]):
                    if n2 == net and k2 == 'via' and tuple(round(v, 5) for v in geo.bounds) == bb:
                        del B.items[ln][i]
                        break
            for i, (hp, hr, hn) in enumerate(B.holes):
                if hn == net and abs(hp.x - x / 1e6) < 1e-6 and abs(hp.y - y / 1e6) < 1e-6:
                    del B.holes[i]
                    break
        else:
            _, t, ln, a, c, w = item
            bb = tuple(round(v, 5) for v in LineString([(a[0] / 1e6, a[1] / 1e6), (c[0] / 1e6, c[1] / 1e6)]).buffer(w / 2e6, 8).bounds)
            if ln in B.items:
                for i, (geo, n2, k2) in enumerate(B.items[ln]):
                    if n2 == net and k2 == 'track' and tuple(round(v, 5) for v in geo.bounds) == bb:
                        del B.items[ln][i]
                        break
    for item in kill:
        b.Remove(item[1])
        item[1].thisown = 0
        mr._GRAVE.append(item[1])
    B.rebuild()
    return len(kill)


def add_items(net, tr_params, vi_params):
    nobj = b.FindNet(net)
    for ln, a, c, w in tr_params:
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(int(a[0]), int(a[1])))
        t.SetEnd(pcbnew.VECTOR2I(int(c[0]), int(c[1])))
        t.SetWidth(int(w))
        t.SetLayer(b.GetLayerID(ln))
        t.SetNet(nobj)
        b.Add(t)
        if ln in B.items:
            B.items[ln].append((LineString([(a[0] / 1e6, a[1] / 1e6), (c[0] / 1e6, c[1] / 1e6)]).buffer(w / 2e6, 8), net, 'track'))
    for x, y, d, h in vi_params:
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
        v.SetWidth(int(d))
        v.SetDrill(int(h))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(nobj)
        b.Add(v)
        g = Point(x / 1e6, y / 1e6).buffer(d / 2e6, 16)
        for ln in mr.SIG:
            B.items[ln].append((g, net, 'via'))
        B.holes.append((Point(x / 1e6, y / 1e6), h / 2e6, net))
    B.rebuild()


def chains_of(net, tr, vi):
    """chains on each layer between terminals -> [(layer, [track idx], end_point_a, end_point_b)] (nm points)"""
    pads_pts = []
    for p in B.pads_by_net.get(net, []):
        for lid in (pcbnew.F_Cu, pcbnew.B_Cu):
            if p.IsOnLayer(lid):
                pads_pts.append((b.GetLayerName(lid), mr.poly_of(p.GetEffectivePolygon(lid, pcbnew.ERROR_OUTSIDE)).buffer(0.005)))
    vset = set((x, y) for x, y, d, h in vi)
    deg = collections.Counter()
    adj = collections.defaultdict(list)
    for i, (ln, a, c, w) in enumerate(tr):
        for e in (a, c):
            deg[(ln, e)] += 1
            adj[(ln, e)].append(i)

    def is_term(ln, e):
        if deg[(ln, e)] != 2 or e in vset:
            return True
        pt = Point(e[0] / 1e6, e[1] / 1e6)
        return any(pl == ln and pg.contains(pt) for pl, pg in pads_pts)
    used = set()
    out = []
    for i, (ln, a, c, w) in enumerate(tr):
        if i in used:
            continue
        chain = [i]
        used.add(i)
        ends = []
        for start in (a, c):
            e, cur = start, i
            while not is_term(ln, e):
                nxt = [k for k in adj[(ln, e)] if k != cur and k not in used]
                if not nxt:
                    break
                k = nxt[0]
                used.add(k)
                chain.append(k)
                _, a2, c2, w2 = tr[k]
                e = c2 if a2 == e else a2
                cur = k
            ends.append(e)
        if len(set(tr[k][3] for k in chain)) != 1:
            continue                         # mixed widths (necks): leave alone
        out.append((ln, chain, ends[0], ends[1]))
    return out


def route_between(net, ln_a, pa, ln_b, pb, w):
    """route between two terminal points (mm) on their layers; returns (segs, vias) or None"""
    A = {l: Polygon() for l in mr.SIG}
    Bi = {l: Polygon() for l in mr.SIG}
    A[ln_a] = Point(pa).buffer(max(w / 2, 0.03), 8)
    Bi[ln_b] = Point(pb).buffer(max(w / 2, 0.03), 8)
    A['__pads__'] = []
    Bi['__pads__'] = []
    res, why = R.route_pair(net, A, Bi)
    if res is None:
        return None
    segs, vias, w_ = res
    # stitch exact terminal points (the router ends on a grid cell inside the terminal disc)
    segs = list(segs)
    if segs:
        ln0, a0, c0, ww0 = segs[0]
        if math.hypot(a0[0] - pa[0], a0[1] - pa[1]) > 1e-6 and ln0 == ln_a:
            segs.insert(0, (ln_a, pa, a0, ww0))
        ln1, a1, c1, ww1 = segs[-1]
        if math.hypot(c1[0] - pb[0], c1[1] - pb[1]) > 1e-6 and ln1 == ln_b:
            segs.append((ln_b, c1, pb, ww1))
    return segs, vias


def to_params(segs, vias, w_nm):
    tp = [(ln, (int(round(a[0] * 1e6)), int(round(a[1] * 1e6))), (int(round(c[0] * 1e6)), int(round(c[1] * 1e6))), w_nm)
          for ln, a, c, ww in segs if math.hypot(c[0] - a[0], c[1] - a[1]) > 1e-6]
    vp = [(int(round(x * 1e6)), int(round(y * 1e6)), int(round(vd * 1e6)), int(round(vh * 1e6))) for x, y, vd, vh in vias]
    return tp, vp


def non_octilinear(tp):
    for ln, a, c, w in tp:
        dx, dy = abs(c[0] - a[0]), abs(c[1] - a[1])
        if dx > 1000 and dy > 1000 and abs(dx - dy) > 1000:
            return True
    return False


nets = []
for net in sorted(B.pads_by_net):
    if not net or net == 'GND' or net.startswith('unconnected'):
        continue
    if mr.cls(net) not in OK_CLS or any(fnmatch.fnmatchcase(net, p) or fnmatch.fnmatchcase(net.split('/')[-1], p) for p in SKIP_PATS):
        continue
    nets.append(net)
report = []
stats = collections.Counter()
t0 = time.time()
for net in nets:
    if 'A' in PASSES:
        tr, vi = snapshot(net)
        work_list = []
        for ln, chain, ea, eb in chains_of(net, tr, vi):
            segs = [(tr[k][0], (tr[k][1][0] / 1e6, tr[k][1][1] / 1e6), (tr[k][2][0] / 1e6, tr[k][2][1] / 1e6)) for k in chain]
            c_old = cost_mm(segs, 0)
            pa, pb = (ea[0] / 1e6, ea[1] / 1e6), (eb[0] / 1e6, eb[1] / 1e6)
            if pa == pb:
                continue
            excess = c_old - ideal_cost(ln, pa, pb)
            if excess > MINX:
                work_list.append((excess, ln, chain, ea, eb, c_old))
        work_list.sort(reverse=True)
        for excess, ln, chain, ea, eb, c_old in work_list[:LIMIT]:
            tr, vi = snapshot(net)
            old = [x for x in tr if x in [tr0 for tr0 in tr]]
            # re-find the chain's segments by geometry (snapshot order may shift after edits)
            chain_params = []
            tr_set = set(tr)
            for k in chain:
                pass
            cur_chains = [c_ for c_ in chains_of(net, tr, vi) if set([c_[2], c_[3]]) == set([ea, eb]) and c_[0] == ln]
            if not cur_chains:
                continue
            _, chain2, _, _ = cur_chains[0]
            chain_params = [tr[k] for k in chain2]
            w_nm = chain_params[0][3]
            pa, pb = (ea[0] / 1e6, ea[1] / 1e6), (eb[0] / 1e6, eb[1] / 1e6)
            before = len(R.islands(net))
            remove_items(net, chain_params, [])
            r_ = route_between(net, ln, pa, ln, pb, w_nm / 1e6)
            kept = False
            if r_ is not None:
                tp, vp = to_params(r_[0], r_[1], w_nm)
                c_new = cost_mm([(l_, (a[0] / 1e6, a[1] / 1e6), (c[0] / 1e6, c[1] / 1e6)) for l_, a, c, w in tp], len(vp))
                if c_new <= c_old * (1 - GAIN) and not non_octilinear(tp):
                    add_items(net, tp, vp)
                    if len(R.islands(net)) <= before:
                        kept = True
                        stats['A_kept'] += 1
                        stats['A_saved'] += c_old - c_new
                    else:
                        remove_items(net, tp, vp)
            if not kept:
                add_items(net, chain_params, [])
                stats['A_rejected'] += 1
    if 'B' in PASSES:
        tr, vi = snapshot(net)
        chs = chains_of(net, tr, vi)
        for x, y, d, h in vi:
            v = (x, y)
            att = [c_ for c_ in chs if v in (c_[2], c_[3])]
            if len(att) != 2 or att[0][0] == att[1][0]:
                continue
            # pass-through via: both chains end here on different layers; the via must not sit in a pad
            pt = Point(x / 1e6, y / 1e6)
            if any(pg.contains(pt) for p in B.pads_by_net.get(net, []) for pg in
                   [mr.poly_of(p.GetEffectivePolygon(pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu, pcbnew.ERROR_OUTSIDE))]):
                continue
            (l1, ch1, a1, b1), (l2, ch2, a2, b2) = att
            far1 = b1 if a1 == v else a1
            far2 = b2 if a2 == v else a2
            tr, vi_now = snapshot(net)
            if (x, y) not in [(xx, yy) for xx, yy, dd, hh in vi_now]:
                continue
            p1 = [tr[k] for k in ch1 if k < len(tr)]
            p2 = [tr[k] for k in ch2 if k < len(tr)]
            if not p1 or not p2 or len(set(t[3] for t in p1 + p2)) != 1:
                continue
            seg_old = [(t[0], (t[1][0] / 1e6, t[1][1] / 1e6), (t[2][0] / 1e6, t[2][1] / 1e6)) for t in p1 + p2]
            c_old = cost_mm(seg_old, 1)
            before = len(R.islands(net))
            remove_items(net, p1 + p2, [(x, y, d, h)])
            r_ = route_between(net, l1, (far1[0] / 1e6, far1[1] / 1e6), l2, (far2[0] / 1e6, far2[1] / 1e6), p1[0][3] / 1e6)
            kept = False
            if r_ is not None:
                tp, vp = to_params(r_[0], r_[1], p1[0][3])
                c_new = cost_mm([(l_, (a[0] / 1e6, a[1] / 1e6), (c[0] / 1e6, c[1] / 1e6)) for l_, a, c, w in tp], len(vp))
                if c_new <= c_old * (1 - GAIN) and not non_octilinear(tp):
                    add_items(net, tp, vp)
                    if len(R.islands(net)) <= before:
                        kept = True
                        stats['B_kept'] += 1
                        stats['B_saved'] += c_old - c_new
                    else:
                        remove_items(net, tp, vp)
            if not kept:
                add_items(net, p1 + p2, [(x, y, d, h)])
                stats['B_rejected'] += 1
            tr, vi = snapshot(net)
            chs = chains_of(net, tr, vi)
    print(f"  {net.split('/')[-1]:24s} A kept {stats['A_kept']:4d} B kept {stats['B_kept']:4d}  ({time.time() - t0:.0f} s)")
    sys.stdout.flush()
pcbnew.SaveBoard(dst, b)
if opt('--report'):
    json.dump(dict(stats), open(opt('--report'), 'w'), indent=1)
print(f"highway2: chains straightened {stats['A_kept']} (rejected {stats['A_rejected']}), vias relocated "
      f"{stats['B_kept']} (rejected {stats['B_rejected']}), cost saved A {stats['A_saved']:.0f} B {stats['B_saved']:.0f} -> {dst}")

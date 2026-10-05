"""highway.py IN.kicad_pcb OUT.kicad_pcb [--gain 0.08] [--max-len-growth 1.35] [--nets N1,N2] [--limit N] [--report R.json]

Signal-highway clean-up (user request 2026-10-02 night: clean tracks, no zig-zags or weird geometry, move blocking
vias, one dominant direction per layer / region so the board is not cut into islands).

Router preferences come from the environment (mr.py): MR_DIRPREF (e.g. 'In3.Cu:V;B.Cu:H;F.Cu:V@118,52,165,95.6|H'),
MR_DIR_PERP / MR_DIR_DIAG (cost multipliers off the preferred axis), MR_T45 (bend penalty), MR_MARGIN.
For every candidate net (Default / HighSpeed_Digital / Harness_IO, minus protected buses), worst geometry first:
  1. its routed copper is ripped EXCEPT pin escape stubs (a track <= 1.2 mm with an end in one of the net's pads) and
     via-in-pad / stub-end vias, so fine-pitch escapes stay;
  2. the net's islands are re-joined nearest pair first with mr.py (exact DRU model, octilinear, direction-preferred);
  3. the new copper is KEPT only if the net is back to its island count, its geometry cost (length x direction
     multiplier + bends + vias, the same weights the router uses) drops by >= --gain, and its length grows by at most
     --max-len-growth; otherwise the old copper is restored exactly.
One board load; restores rebuild the old items from saved parameters. KiCad python, scratch copies only."""
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
from shapely.geometry import LineString, Point  # noqa: E402

argv = sys.argv[1:]


def opt(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


src, dst = argv[0], argv[1]
if os.path.normcase(os.path.realpath(dst)).startswith(mr.PROTECTED):
    sys.exit('refusing to write into the project folder')
GAIN = float(opt('--gain', '0.08'))
GROW = float(opt('--max-len-growth', '1.35'))
LIMIT = int(opt('--limit', '100000'))
ONLY = set((opt('--nets') or '').split(',')) - {''}
OK_CLS = ('Default', 'HighSpeed_Digital', 'Harness_IO')
SKIP_PATS = ('*SD_*', '*PSRAM*', '*EXTADC*', '*ADC_*', 'USB_*', '*BUCK_SYNC*', '*TP_RST*', '*LCD_RST*')
work = dst + '.hw.kicad_pcb'
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


def seg_mul(ln, a, c):
    dx, dy = c[0] - a[0], c[1] - a[1]
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
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
        return 2.0                                  # not octilinear: always worth replacing
    if ax is None:
        return 1.0
    if (ax == 'H' and horiz) or (ax == 'V' and vert):
        return 1.0
    return mr.DIR_DIAG if diag else mr.DIR_PERP


def cost_of(segs, vias):
    L = sum(math.hypot(c[0] - a[0], c[1] - a[1]) for ln, a, c, w in segs)
    C = sum(math.hypot(c[0] - a[0], c[1] - a[1]) * seg_mul(ln, a, c) for ln, a, c, w in segs)
    return C + T45 * len(segs) + VIAC * len(vias), L


def net_items(net):
    tr, vi = [], []
    for t in b.GetTracks():
        if t.GetNetname() != net:
            continue
        if t.GetClass() == 'PCB_VIA':
            c = t.GetPosition()
            vi.append((c.x, c.y, t.GetWidth(pcbnew.F_Cu), t.GetDrill()))
        else:
            tr.append((b.GetLayerName(t.GetLayer()), (t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y), t.GetWidth()))
    return tr, vi


def mm_segs(tr):
    return [(ln, (a[0] / 1e6, a[1] / 1e6), (c[0] / 1e6, c[1] / 1e6), w / 1e6) for ln, a, c, w in tr]


def keepers(net, tr, vi):
    """pin escapes stay: from every pad of the net, follow the connected track chain (any layer change ends it) up to
    the first via or ESC_MAX mm, and keep those segments and that via; vias inside pads stay too"""
    ESC_MAX = 2.8
    pads = []
    for p in B.pads_by_net.get(net, []):
        for lid in (pcbnew.F_Cu, pcbnew.B_Cu):
            if p.IsOnLayer(lid):
                pads.append((b.GetLayerName(lid), mr.poly_of(p.GetEffectivePolygon(lid, pcbnew.ERROR_OUTSIDE)).buffer(0.01)))
    vpos = {(round(x / 1e6, 4), round(y / 1e6, 4)): j for j, (x, y, d, h) in enumerate(vi)}
    ends = {}
    for i, (ln, a, c, w) in enumerate(tr):
        for e in (a, c):
            ends.setdefault((ln, round(e[0] / 1e6, 4), round(e[1] / 1e6, 4)), []).append(i)
    keep_t, keep_v = set(), set()
    for j, (x, y, d, h) in enumerate(vi):
        pt = Point(x / 1e6, y / 1e6)
        if any(pg.contains(pt) for _, pg in pads):
            keep_v.add(j)
    for i, (ln, a, c, w) in enumerate(tr):
        for e_in, e_out in ((a, c), (c, a)):
            pin = Point(e_in[0] / 1e6, e_in[1] / 1e6)
            if not any(pl == ln and pg.contains(pin) for pl, pg in pads):
                continue
            # walk away from the pad
            chain = [i]
            L = math.hypot(c[0] - a[0], c[1] - a[1]) / 1e6
            cur, far = i, e_out
            ok = False
            while True:
                key = (round(far[0] / 1e6, 4), round(far[1] / 1e6, 4))
                if key in vpos:
                    keep_v.add(vpos[key])
                    ok = True
                    break
                if any(pl == ln and pg.contains(Point(far[0] / 1e6, far[1] / 1e6)) for pl, pg in pads):
                    ok = True                      # reached another pad of the net (a local link) - keep it
                    break
                nxt = [k for k in ends.get((ln, key[0], key[1]), []) if k != cur and k not in chain]
                if len(nxt) != 1:
                    break
                k = nxt[0]
                ln2, a2, c2, w2 = tr[k]
                L += math.hypot(c2[0] - a2[0], c2[1] - a2[1]) / 1e6
                if L > ESC_MAX:
                    break
                chain.append(k)
                far = c2 if (round(a2[0] / 1e6, 4), round(a2[1] / 1e6, 4)) == key else a2
                cur = k
            if ok:
                keep_t.update(chain)
    return keep_t, keep_v


def remove_items(net, tr_params, vi_params):
    """remove board items of net matching the parameter tuples (fresh proxies from GetTracks), from board + model"""
    want_t = set((ln, a, c, w) for ln, a, c, w in tr_params)
    want_v = set((x, y) for x, y, d, h in vi_params)
    kill = []
    for t in b.GetTracks():
        if t.GetNetname() != net:
            continue
        if t.GetClass() == 'PCB_VIA':
            c = t.GetPosition()
            if (c.x, c.y) in want_v:
                kill.append(('v', t, c.x, c.y, t.GetWidth(pcbnew.F_Cu), t.GetDrill()))
        else:
            k = (b.GetLayerName(t.GetLayer()), (t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y), t.GetWidth())
            if k in want_t:
                kill.append(('t',) + (t,) + k)
    for item in kill:
        if item[0] == 'v':
            _, t, x, y, d, h = item
            g = Point(x / 1e6, y / 1e6).buffer(d / 2e6, 16)
            bb = tuple(round(v, 5) for v in g.bounds)
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
            g = LineString([(a[0] / 1e6, a[1] / 1e6), (c[0] / 1e6, c[1] / 1e6)]).buffer(w / 2e6, 8)
            bb = tuple(round(v, 5) for v in g.bounds)
            if ln in B.items:
                for i, (geo, n2, k2) in enumerate(B.items[ln]):
                    if n2 == net and k2 == 'track' and tuple(round(v, 5) for v in geo.bounds) == bb:
                        del B.items[ln][i]
                        break
    for item in kill:
        b.Remove(item[1])
        # keep the removed C++ object alive: freeing it leaves dangling pointers in KiCad's connectivity data and
        # later SWIG calls return untyped SwigPyObjects (found 2026-10-02)
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


def commit_params(net, segs, vias):
    """route result -> parameter tuples in nm (as add_items expects)"""
    tp = [(ln, (int(round(a[0] * 1e6)), int(round(a[1] * 1e6))), (int(round(c[0] * 1e6)), int(round(c[1] * 1e6))), int(round(w * 1e6)))
          for ln, a, c, w in segs if abs(a[0] - c[0]) > 1e-9 or abs(a[1] - c[1]) > 1e-9]
    vp = [(int(round(x * 1e6)), int(round(y * 1e6)), int(round(vd * 1e6)), int(round(vh * 1e6))) for x, y, vd, vh in vias]
    return tp, vp


# candidates
cands = []
for net in sorted(B.pads_by_net):
    if not net or net == 'GND' or net.startswith('unconnected'):
        continue
    if ONLY and net not in ONLY and net.split('/')[-1] not in ONLY:
        continue
    if mr.cls(net) not in OK_CLS or any(fnmatch.fnmatchcase(net, p) or fnmatch.fnmatchcase(net.split('/')[-1], p) for p in SKIP_PATS):
        continue
    tr, vi = net_items(net)
    if not tr:
        continue
    C, L = cost_of(mm_segs(tr), vi)
    if L < 2.0:
        continue
    cands.append((C - L, C, L, net))         # worst excess (direction + bends + vias) first
cands.sort(reverse=True)
print(f"highway: {len(cands)} candidate nets; prefs {os.environ.get('MR_DIRPREF', '')} perp {mr.DIR_PERP} diag {mr.DIR_DIAG} t45 {T45}")
rep = []
done = 0
for excess, C0, L0, net in cands[:LIMIT]:
    ts = time.time()
    tr, vi = net_items(net)
    kt, kv = keepers(net, tr, vi)
    rip_t = [x for i, x in enumerate(tr) if i not in kt]
    rip_v = [x for j, x in enumerate(vi) if j not in kv]
    if not rip_t and not rip_v:
        continue
    before = len(R.islands(net))
    remove_items(net, rip_t, rip_v)
    new_t, new_v = [], []
    ok = True
    for _ in range(40):
        isl = R.islands(net)
        if len(isl) <= before:
            break
        from shapely.ops import unary_union
        gs = [unary_union([v for k_, v in I.items() if not k_.startswith('__') and not v.is_empty]) for I in isl]
        d, i, j = min((gs[i].distance(gs[j]), i, j) for i in range(len(isl)) for j in range(i + 1, len(isl)))
        res, why = R.route_pair(net, isl[i], isl[j])
        if res is None:
            ok = False
            break
        tp, vp = commit_params(net, res[0], res[1])
        add_items(net, tp, vp)
        new_t += tp
        new_v += vp
    kept_t = [x for i, x in enumerate(tr) if i in kt]
    kept_v = [x for j, x in enumerate(vi) if j in kv]
    C1, L1 = cost_of(mm_segs(kept_t + new_t), kept_v + new_v)
    good = ok and len(R.islands(net)) <= before and C1 <= C0 * (1 - GAIN) and L1 <= L0 * GROW + 2.0
    if not good:
        remove_items(net, new_t, new_v)
        add_items(net, rip_t, rip_v)
    else:
        done += 1
    rep.append({'net': net, 'kept': good, 'cost': [round(C0, 1), round(C1, 1)], 'len': [round(L0, 1), round(L1, 1)],
                'vias': [len(vi), len(kept_v) + len(new_v)], 'routed': ok})
    print(f"  {'KEEP' if good else 'keep old'} {net.split('/')[-1]:22s} cost {C0:7.1f} -> {C1:7.1f}  len {L0:6.1f} -> {L1:6.1f}  "
          f"vias {len(vi)} -> {len(kept_v) + len(new_v)}{'' if ok else '  (re-route failed)'} ({time.time() - ts:.0f} s)")
    sys.stdout.flush()
    if done and done % 10 == 0:
        pcbnew.SaveBoard(work, b)
pcbnew.SaveBoard(dst, b)
if opt('--report'):
    json.dump(rep, open(opt('--report'), 'w'), indent=1)
print(f"highway: {done} of {len(rep)} nets re-routed cleaner -> {dst}")

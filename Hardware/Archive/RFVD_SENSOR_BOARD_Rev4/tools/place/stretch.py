"""stretch.py IN.kicad_pcb OUT.kicad_pcb [--left L --right R] [--carry REF,REF ...] [--nudge REF[,REF]:dx,dy ...]
                 [--notch-left Y0,Y1[,R]] [--dry-run]
Widen the board (user request 2026-10-02: +2.5 mm on each side so parts get more edge clearance). Everything keeps its
absolute position, except edge-bound groups (--carry, e.g. the USB-C receptacle with its ESD / filter parts), which
move with their edge as rigid groups. Their connections are STRETCHED, not re-routed: all copper stays, and each pad
contact gets a straight horizontal insert from the moved pad back to the copper it touched, so the routing topology is
kept. New overlaps between moved pads and other copper are not checked here - run DRC.

  * Edge.Cuts: points left of the board centre move -L in x, right of it +R (lines, arcs).
  * Zones and rule areas: board-wide ones (bbox >= 90 % of the width) move every outline vertex within 4 mm of the old
    left / right edge (corner arcs included); smaller ones only vertices within 1 mm of the edge. Hole boss keep-outs
    (K7_*, K11_H*) stay with the holes; K12_<member>_* areas move with their group.
  * Carried group: only the member footprints move (and K12_<member>_* areas). Copper stays; each contact between a
    member pad and same-net copper gets a straight insert from the moved contact point back to the old one.
  * --nudge REF[,REF]:dx,dy moves a group by an explicit small vector with the same stretched contacts (clears a
    courtyard overlap or a keep-out without ripping anything; pass-through pads keep both of their tracks).
  * --notch-left Y0,Y1[,R] (user choice 2026-10-02 'port notch'): between Y0 and Y1 the left edge stays at its old x
    (edge-bound ports stay flush without moving); the steps get R mm fillets (default 0.5, milling bit radius).
Writes OUT (+ .kicad_pro / .kicad_dru), zones refilled. --dry-run prints the plan only. KiCad python."""
import math
import os
import shutil
import sys

import pcbnew
from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import mr  # noqa: E402

argv = sys.argv[1:]


def opt(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


def opts(k):
    return [argv[i + 1] for i, a in enumerate(argv) if a == k]


src, dst = argv[0], argv[1]
if os.path.normcase(os.path.realpath(dst)).startswith(mr.PROTECTED):
    sys.exit('refusing to write into the project folder')
L = float(opt('--left', '0'))
R = float(opt('--right', '0'))
DRY = '--dry-run' in argv
groups = [(g.split(','), None) for g in opts('--carry')]
for g in opts('--nudge'):
    r_, v_ = g.split(':')
    groups.append((r_.split(','), tuple(float(q) for q in v_.split(','))))
NOTCH = [float(v) for v in opt('--notch-left').split(',')] if opt('--notch-left') else None
GRAVE = []
b = pcbnew.LoadBoard(src)
bb = b.GetBoardEdgesBoundingBox()
X0, X1 = bb.GetX() / 1e6, (bb.GetX() + bb.GetWidth()) / 1e6
XM, W = (X0 + X1) / 2, X1 - X0
print(f"stretch: outline x {X0:.3f}..{X1:.3f} ({W:.2f} mm) -> {X0 - L:.3f}..{X1 + R:.3f} ({W + L + R:.2f} mm)")
CU = list(b.GetEnabledLayers().CuStack())


def V(x, y):
    return pcbnew.VECTOR2I(int(round(x * 1e6)), int(round(y * 1e6)))


def dx_for(x):
    return -L if x < XM else R


def short(n):
    return n.split('/')[-1]


def geo(t):
    if t.GetClass() == 'PCB_VIA':
        c = t.GetPosition()
        g = Point(c.x / 1e6, c.y / 1e6).buffer(t.GetWidth(pcbnew.F_Cu) / 2e6, 16)
        top, bot = t.TopLayer(), t.BottomLayer()
        return {l_: g for l_ in CU if CU.index(top) <= CU.index(l_) <= CU.index(bot)}
    if t.GetClass() == 'PCB_ARC':
        pts = [(t.GetStart().x / 1e6, t.GetStart().y / 1e6), (t.GetMid().x / 1e6, t.GetMid().y / 1e6), (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)]
    else:
        pts = [(t.GetStart().x / 1e6, t.GetStart().y / 1e6), (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)]
    return {t.GetLayer(): LineString(pts).buffer(t.GetWidth() / 2e6, 8)}


def touch(ga, gb):
    return any(l_ in gb and ga[l_].intersects(gb[l_]) for l_ in ga)


# ---------------------------------------------------------------- 1. plan the carried groups
# Only the member footprints move. All copper stays where it is; every contact between a member pad and same-net
# copper (a track end in the pad, a via in the pad, a track crossing the pad) gets one straight insert on that layer
# from the moved contact point back to the original one. Inserts are horizontal (octilinear) and run through the
# area the part vacated.
plan = []
for grp, vec in groups:
    fps = [b.FindFootprintByReference(r) for r in grp]
    if any(f is None for f in fps):
        sys.exit(f'unknown reference in {grp}')
    cx = sum(f.GetPosition().x for f in fps) / len(fps) / 1e6
    mv, mvy = (dx_for(cx), 0.0) if vec is None else vec
    nets = set(p.GetNetname() for f in fps for p in f.Pads() if p.GetNetname())
    stat = [(t, geo(t)) for t in b.GetTracks() if t.GetNetname() in nets]
    width_of = {}
    for t, _ in stat:
        if t.GetClass() != 'PCB_VIA':
            n = t.GetNetname()
            width_of[n] = min(width_of.get(n, t.GetWidth()), t.GetWidth())
    contacts = {}       # (layer, net, x, y) -> width; one per (pad, layer, connected piece of static copper)
    for f in fps:
        for p in f.Pads():
            n = p.GetNetname()
            if not n:
                continue
            for l_ in CU:
                if not p.IsOnLayer(l_):
                    continue
                pg = mr.poly_of(p.GetEffectivePolygon(l_, pcbnew.ERROR_OUTSIDE))
                hits = []           # (item index, contact point, width)
                for k, (t, gt) in enumerate(stat):
                    if t.GetNetname() != n or l_ not in gt or not gt[l_].intersects(pg):
                        continue
                    if t.GetClass() == 'PCB_VIA':
                        c = t.GetPosition()
                        hits.append((k, (c.x / 1e6, c.y / 1e6), width_of.get(n, 200000)))
                        continue
                    ends = [(t.GetStart().x / 1e6, t.GetStart().y / 1e6), (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)]
                    inn = [e for e in ends if pg.buffer(1e-3).contains(Point(e))]
                    if inn:
                        hits.append((k, inn[0], t.GetWidth()))
                    else:
                        x_ = LineString(ends).intersection(pg)
                        if not x_.is_empty:
                            hits.append((k, (x_.centroid.x, x_.centroid.y), t.GetWidth()))
                # group the touching static items into connected pieces (without the pad)
                parent = {h[0]: h[0] for h in hits}

                def root(x):
                    while parent[x] != x:
                        parent[x] = parent[parent[x]]
                        x = parent[x]
                    return x
                ks = [h[0] for h in hits]
                for i1 in range(len(ks)):
                    for i2 in range(i1 + 1, len(ks)):
                        if touch(stat[ks[i1]][1], stat[ks[i2]][1]):
                            parent[root(ks[i1])] = root(ks[i2])
                pieces = {}
                for k, C, w in hits:
                    pieces.setdefault(root(k), []).append((C, w))
                for pts in pieces.values():
                    # the contact deepest towards the moved pad: the insert lands there and the rest of the piece hangs on it
                    # the contact deepest in the move direction: the insert lands there, the rest of the piece hangs on it
                    nrm = math.hypot(mv, mvy) or 1.0
                    C, w = min(pts, key=lambda q: -(q[0][0] * mv + q[0][1] * mvy) / nrm)
                    w = min(q[1] for q in pts)
                    key = (l_, n, round(C[0], 4), round(C[1], 4))
                    contacts[key] = min(contacts.get(key, w), w)
    zs = [z for z in b.Zones() if z.GetIsRuleArea() and any(z.GetZoneName().startswith(f'K12_{r}_') for r in grp)]
    plan.append({'refs': grp, 'move': mv, 'movey': mvy, 'contacts': contacts, 'zones': zs})
    print(f"group {grp}: move ({mv:+.2f},{mvy:+.2f}) mm; {len(contacts)} pad contacts get a {math.hypot(mv, mvy):.2f} mm insert; "
          f"rule areas {[z.GetZoneName() for z in zs]}")
    for (l_, n, x, y), w in sorted(contacts.items(), key=lambda kv: (kv[0][1], kv[0][3])):
        print(f"   {short(n):14s} {b.GetLayerName(l_):6s} ({x:.2f},{y:.2f}) w{w / 1e6:.2f}")
if DRY:
    sys.exit(0)

# ---------------------------------------------------------------- 2. apply the carried groups
nins = 0
for g in plan:
    mv, mvy = g['move'], g['movey']
    for r in g['refs']:
        f = b.FindFootprintByReference(r)
        p = f.GetPosition()
        f.SetPosition(pcbnew.VECTOR2I(p.x + int(round(mv * 1e6)), p.y + int(round(mvy * 1e6))))
    for z in g['zones']:
        z.Move(V(mv, mvy))
    for (l_, n, x, y), w in g['contacts'].items():
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(V(x + mv, y + mvy))
        t.SetEnd(V(x, y))
        t.SetWidth(int(w))
        t.SetLayer(l_)
        t.SetNet(b.FindNet(n))
        b.Add(t)
        nins += 1
print(f"stretch: {nins} inserts added")

# ---------------------------------------------------------------- 3. outline
for d in list(b.GetDrawings()):
    if d.GetLayer() != pcbnew.Edge_Cuts:
        continue
    st = d.GetShapeStr().lower()
    if st.startswith('arc'):
        d.Move(V(dx_for(d.GetArcMid().x / 1e6), 0))
    elif st.startswith('line') or st.startswith('segment'):
        s_, e_ = d.GetStart(), d.GetEnd()
        d.SetStart(V(s_.x / 1e6 + dx_for(s_.x / 1e6), s_.y / 1e6))
        d.SetEnd(V(e_.x / 1e6 + dx_for(e_.x / 1e6), e_.y / 1e6))
    else:
        sys.exit(f'Edge.Cuts shape {st} not handled')

if NOTCH:
    y0n, y1n = NOTCH[0], NOTCH[1]
    rr = NOTCH[2] if len(NOTCH) > 2 else 0.5
    xl_new = None
    left_line = None
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts and d.GetShapeStr().lower().startswith(('line', 'segment')):
            s_, e_ = d.GetStart(), d.GetEnd()
            if abs(s_.x - e_.x) < 1000 and s_.x / 1e6 < XM:
                left_line, xl_new = d, s_.x / 1e6
    if left_line is None:
        sys.exit('notch: left edge line not found')
    ya, yb = sorted((left_line.GetStart().y / 1e6, left_line.GetEnd().y / 1e6))
    if not (ya + rr < y0n - rr and y1n + rr < yb - rr):
        sys.exit('notch: outside the straight part of the left edge')
    xo = xl_new + L                 # the old edge x (kept inside the notch)
    wdt = left_line.GetWidth()
    b.Remove(left_line)
    left_line.thisown = 0
    GRAVE.append(left_line)

    def seg(p, q):
        g_ = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT)
        g_.SetStart(V(*p))
        g_.SetEnd(V(*q))
        g_.SetLayer(pcbnew.Edge_Cuts)
        g_.SetWidth(wdt)
        b.Add(g_)

    def arc(p, m, q):
        g_ = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_ARC)
        g_.SetArcGeometry(V(*p), V(*m), V(*q))
        g_.SetLayer(pcbnew.Edge_Cuts)
        g_.SetWidth(wdt)
        b.Add(g_)
    k = rr * (1 - math.sqrt(0.5))   # arc midpoint inset for a 90 degree fillet
    # top part of the new edge, convex fillet into the step, step, concave fillet down into the notch
    seg((xl_new, ya), (xl_new, y0n - rr))
    arc((xl_new, y0n - rr), (xl_new + k, y0n - k), (xl_new + rr, y0n))
    seg((xl_new + rr, y0n), (xo - rr, y0n))
    arc((xo - rr, y0n), (xo - k, y0n + k), (xo, y0n + rr))
    seg((xo, y0n + rr), (xo, y1n - rr))
    arc((xo, y1n - rr), (xo - k, y1n - k), (xo - rr, y1n))
    seg((xo - rr, y1n), (xl_new + rr, y1n))
    arc((xl_new + rr, y1n), (xl_new + k, y1n + k), (xl_new, y1n + rr))
    seg((xl_new, y1n + rr), (xl_new, yb))
    print(f"stretch: left notch y {y0n:.2f}..{y1n:.2f}: edge stays at x {xo:.3f} (fillets r {rr})")

# ---------------------------------------------------------------- 4. zones / rule areas reaching the old edges
carried = set(z.m_Uuid.AsString() for g in plan for z in g['zones'])
nz = []
for z in b.Zones():
    name = z.GetZoneName()
    if z.m_Uuid.AsString() in carried or (z.GetIsRuleArea() and (name.startswith('K7_') or name.startswith('K11_H'))):
        continue
    zb = z.GetBoundingBox()
    band = 4.0 if zb.GetWidth() / 1e6 >= 0.9 * W else 1.0
    ol = z.Outline()
    moved = False
    for i in range(ol.TotalVertices()):
        v = ol.CVertex(i)
        x = v.x / 1e6
        if x <= X0 + band:
            ol.SetVertex(i, V(x - L, v.y / 1e6))
            moved = True
        elif x >= X1 - band:
            ol.SetVertex(i, V(x + R, v.y / 1e6))
            moved = True
    if moved:
        nz.append(name or ('net ' + short(z.GetNetname())) + '@' + '/'.join(b.GetLayerName(l_) for l_ in z.GetLayerSet().CuStack())[:20])
print(f"stretch: {len(nz)} zones / rule areas extended: {nz}")
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(dst, b)
for ext in ('.kicad_pro', '.kicad_dru'):
    a_ = os.path.splitext(src)[0] + ext
    if os.path.isfile(a_):
        shutil.copy2(a_, os.path.splitext(dst)[0] + ext)
print(f"stretch -> {dst}")

"""cutcap.py BOARD W CLR CUT [CUT ...]   CUT = h:Y:X0:X1 or v:X:Y0:Y1   (2026-10-03, routing guide)
Cut capacity: along a straight cut line, the free intervals where a W mm track crossing the cut keeps CLR mm from
all other copper on that layer (pads, tracks, vias, holes + 0.1, non-GND fills, board edge 0.5, rule areas that ban
tracks on that layer, and the DRU lane / partition rules for a generic signal net that owns no lane: the mr.py
LANE_OWNERS areas (K15-K20, K16, K17, K10, K6, K11, K7), K3, and AFE_PARTITION on F/B (aggressor classes)).
Capacity of an interval = floor((len) / (W + CLR)) + 1 tracks. Read only."""
import fnmatch
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mr
import pcbnew
from shapely.geometry import LineString, Point, Polygon, box as sbox
from shapely.ops import unary_union
b = pcbnew.LoadBoard(sys.argv[1]); W, CLR = float(sys.argv[2]), float(sys.argv[3])
def polys(ps):
    out = []
    for i in range(ps.OutlineCount()):
        ch = ps.Outline(i)
        pts = [(ch.CPoint(k).x / 1e6, ch.CPoint(k).y / 1e6) for k in range(ch.PointCount())]
        if len(pts) > 2: out.append(Polygon(pts).buffer(0))
    return out
ps = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(ps, False)
inside = unary_union(polys(ps)).buffer(-(0.5 + W / 2))
blk = {}
for L in ('F.Cu', 'In3.Cu', 'B.Cu'):
    lid = b.GetLayerID(L); obs = []
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            c = t.GetPosition(); obs.append(Point(c.x / 1e6, c.y / 1e6).buffer(t.GetWidth(pcbnew.F_Cu) / 2e6, 10))
        elif t.GetLayer() == lid:
            obs.append(LineString([(t.GetStart().x / 1e6, t.GetStart().y / 1e6), (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)]).buffer(t.GetWidth() / 2e6, 4))
    for f in b.GetFootprints():
        for p in f.Pads():
            c = p.GetPosition()
            if p.IsOnLayer(lid): obs += polys(p.GetEffectivePolygon(lid, pcbnew.ERROR_OUTSIDE))
            if p.GetDrillSize().x > 0: obs.append(Point(c.x / 1e6, c.y / 1e6).buffer(p.GetDrillSize().x / 2e6 + 0.1, 12))
    for z in b.Zones():
        if not z.GetIsRuleArea() and z.IsOnLayer(lid) and z.GetNetname() not in ('GND', ''):
            obs += polys(z.GetFilledPolysList(lid))
    g = unary_union(obs).buffer(W / 2 + CLR, 6)
    kos = []
    for z in b.Zones():
        if z.GetIsRuleArea() and z.GetDoNotAllowTracks() and z.IsOnLayer(lid): kos += polys(z.Outline())
    for f in b.GetFootprints():
        for z in f.Zones():
            if z.GetIsRuleArea() and z.GetDoNotAllowTracks() and z.IsOnLayer(lid): kos += polys(z.Outline())
    for z in b.Zones():
        if not z.GetIsRuleArea(): continue
        nm = z.GetZoneName()
        lays = None
        for pat, (ls, tr_ok, via_ok) in mr.LANE_OWNERS.items():
            if fnmatch.fnmatchcase(nm, pat):
                lays = ls if tr_ok is not None else []
                break
        if nm.startswith('K3_RF_CORRIDOR'): lays = ['F.Cu', 'B.Cu']
        if nm == 'AFE_PARTITION': lays = ['F.Cu', 'B.Cu']
        if lays and L in lays: kos += polys(z.Outline())
    if kos: g = g.union(unary_union(kos).buffer(W / 2, 4))
    blk[L] = inside.difference(g)
for cut in sys.argv[4:]:
    k, c, a0, a1 = cut.split(':'); c, a0, a1 = float(c), float(a0), float(a1)
    ln = LineString([(a0, c), (a1, c)]) if k == 'h' else LineString([(c, a0), (c, a1)])
    tot = 0; parts = []
    for L in ('F.Cu', 'In3.Cu', 'B.Cu'):
        fr = ln.intersection(blk[L])
        segs = [fr] if fr.geom_type == 'LineString' else [q for q in getattr(fr, 'geoms', []) if q.geom_type == 'LineString']
        iv = []
        for s in segs:
            if s.is_empty: continue
            cs = sorted(q[0] if k == 'h' else q[1] for q in s.coords)
            n = int((cs[-1] - cs[0]) / (W + CLR) + 1e-9) + 1
            iv.append((cs[0], cs[-1], n))
        cap = sum(i[2] for i in iv); tot += cap
        parts.append(f"   {L:7s} cap {cap:3d}: " + ', '.join(f"{i[0]:.2f}-{i[1]:.2f}({i[2]})" for i in sorted(iv)))
    nm = f"y={c}" if k == 'h' else f"x={c}"
    print(f"cut {nm} [{a0}..{a1}]  total capacity {tot}")
    print('\n'.join(parts))

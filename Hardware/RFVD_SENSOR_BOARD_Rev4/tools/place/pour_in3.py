"""pour_in3.py IN.kicad_pcb OUT.kicad_pcb NET [--exclude AREA1,AREA2] [--margin 1.0] [--clr 0.2] [--minw 0.25]

Buried power feed (user rule: use the planes correctly): one copper zone of NET on In3.Cu (between the In2 and In4 GND
planes = buried plane capacitance, shielded from both faces), lowest priority, filling the board outline minus
--exclude rule areas (default AFE_PARTITION, K3_RF_CORRIDOR: no digital power under the precision analog / RF front
end) minus a --margin from the edge. It fills around every In3 signal track (KiCad's filler applies all clearances)
and joins every NET via it touches; islands that reach no via are dropped. Run it after the In3 signal routing.
Needs DRU patch 6 (planes_gnd_only exempts Power_* pours on In3). Reports the islands of NET before/after."""
import os
import shutil
import sys

import pcbnew
from shapely.geometry import Polygon
from shapely.ops import unary_union

argv = sys.argv[1:]


def opt(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


src, dst, net = argv[0], argv[1], argv[2]
excl = (opt('--exclude') or 'AFE_PARTITION,K3_RF_CORRIDOR').split(',')
margin = float(opt('--margin', '1.0'))
b = pcbnew.LoadBoard(src)


def poly(ps):
    out = []
    for i in range(ps.OutlineCount()):
        ch = ps.Outline(i)
        pts = [(ch.CPoint(k).x / 1e6, ch.CPoint(k).y / 1e6) for k in range(ch.PointCount())]
        if len(pts) >= 3:
            out.append(Polygon(pts).buffer(0))
    return unary_union(out) if out else Polygon()


ps = pcbnew.SHAPE_POLY_SET()
b.GetBoardPolygonOutlines(ps, True)
area = poly(ps).buffer(-margin)
for z in b.Zones():
    if z.GetIsRuleArea() and any(z.GetZoneName().startswith(e) for e in excl):
        area = area.difference(poly(z.Outline()).buffer(0.5))
geoms = [area] if area.geom_type == 'Polygon' else list(getattr(area, 'geoms', []))
nobj = b.FindNet(net)
lid = b.GetLayerID('In3.Cu')
made = 0
for g in geoms:
    if g.is_empty or g.area < 4.0:
        continue
    z = pcbnew.ZONE(b)
    z.SetLayer(lid)
    z.SetNet(nobj)
    z.SetAssignedPriority(0)
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetMinThickness(int(float(opt('--minw', '0.25')) * 1e6))
    z.SetLocalClearance(int(float(opt('--clr', '0.2')) * 1e6))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetZoneName(f"PWR_{net.split('/')[-1]}_In3")
    o = z.Outline()
    o.NewOutline()
    for x, y in list(g.exterior.coords)[:-1]:
        o.Append(int(round(x * 1e6)), int(round(y * 1e6)))
    for hole in g.interiors:
        o.NewHole()
        for x, y in list(hole.coords)[:-1]:
            o.Append(int(round(x * 1e6)), int(round(y * 1e6)))
    b.Add(z)
    made += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
filled = sum(poly(z.GetFilledPolysList(lid)).area for z in b.Zones() if z.GetZoneName().startswith('PWR_') and z.IsOnLayer(lid))
pcbnew.SaveBoard(dst, b)
for ext in ('.kicad_pro', '.kicad_dru'):
    s = os.path.splitext(src)[0] + ext
    if os.path.isfile(s):
        shutil.copy2(s, os.path.splitext(dst)[0] + ext)
print(f"pour_in3: {made} zone(s) of {net} on In3, filled area {filled:.0f} mm2 -> {dst}")

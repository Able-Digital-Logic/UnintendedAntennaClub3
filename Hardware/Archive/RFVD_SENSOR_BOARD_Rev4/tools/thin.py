"""thin.py IN.kicad_pcb OUT.kicad_pcb [--dmin 4.0] [--report R.json]
Thin the free GND stitching-via field before routing (stitching goes in LAST; restitch.py refills it after routing).
EMC rulebook (tools/jev_s1/projects/rfvd_emc_rulebook.md) items kept unconditionally:
  R21  every GND via in or tracked to a GND pad (pad vias)
  R17  stitching vias within 1.2 mm (centre-centre) of a fast-net (HighSpeed_*) signal via (layer-change return)
  R17  vias at connector grounds: within 1.5 mm of a GND pad of J*/BNC footprints
  R17/R47/R48  vias around the switchers: within 3.0 mm of U6, L1, U301, L301 GND pads
  R10  RF path side grounds: within 2.0 mm of RF_Input / RF_50R copper
  GND-only cells/lanes (K11_*, K10B_*, K6_*, K17_*) and the AFE partition: no other net may route there anyway
The rest of the free field is thinned to a minimum spacing of --dmin (default 4.0 mm, denser than the rulebook's
optional 7-10 mm grid). KiCad python, scratch copies only."""
import fnmatch
import json
import math
import os
import shutil
import sys

import pcbnew
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
NETS = json.load(open(os.path.join(HERE, 'an', 'nets.json')))
_GRAVE = []


def cls(n):
    return NETS.get(n, {'class': 'Default'})['class'].split(',')[0]


def zone_poly(z):
    o = z.Outline()
    ps = []
    for i in range(o.OutlineCount()):
        ch = o.Outline(i)
        pts = [(ch.CPoint(k).x / 1e6, ch.CPoint(k).y / 1e6) for k in range(ch.PointCount())]
        if len(pts) >= 3:
            ps.append(Polygon(pts).buffer(0))
    return unary_union(ps) if ps else Polygon()


def main():
    argv = sys.argv[1:]
    src, dst = argv[0], argv[1]
    dmin = float(argv[argv.index('--dmin') + 1]) if '--dmin' in argv else 4.0
    b = pcbnew.LoadBoard(src)
    gpads = [p for f in b.GetFootprints() for p in f.Pads() if p.GetNetname() == 'GND']
    ends = set()
    for t in b.GetTracks():
        if t.GetClass() != 'PCB_VIA' and t.GetNetname() == 'GND':
            ends.add((t.GetStart().x, t.GetStart().y))
            ends.add((t.GetEnd().x, t.GetEnd().y))
    fast_vias = [Point(t.GetPosition().x / 1e6, t.GetPosition().y / 1e6) for t in b.GetTracks()
                 if t.GetClass() == 'PCB_VIA' and cls(t.GetNetname()).startswith('HighSpeed')]
    conn_pads, sw_pads = [], []
    for f in b.GetFootprints():
        r = f.GetReference()
        for p in f.Pads():
            if p.GetNetname() != 'GND':
                continue
            c = Point(p.GetPosition().x / 1e6, p.GetPosition().y / 1e6)
            if r.startswith('J') or r.startswith('BNC'):
                conn_pads.append(c.buffer(max(p.GetSize().x, p.GetSize().y) / 2e6 + 1.5))
            if r in ('U6', 'L1', 'U301', 'L301'):
                sw_pads.append(c.buffer(max(p.GetSize().x, p.GetSize().y) / 2e6 + 3.0))
    conn_g = unary_union(conn_pads) if conn_pads else Polygon()
    sw_g = unary_union(sw_pads) if sw_pads else Polygon()
    rf = []
    for t in b.GetTracks():
        if cls(t.GetNetname()) in ('RF_Input', 'RF_50R'):
            if t.GetClass() == 'PCB_VIA':
                rf.append(Point(t.GetPosition().x / 1e6, t.GetPosition().y / 1e6).buffer(2.0))
            else:
                rf.append(LineString([(t.GetStart().x / 1e6, t.GetStart().y / 1e6),
                                      (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)]).buffer(2.0 + t.GetWidth() / 2e6))
    for f in b.GetFootprints():
        for p in f.Pads():
            if cls(p.GetNetname()) in ('RF_Input', 'RF_50R'):
                rf.append(Point(p.GetPosition().x / 1e6, p.GetPosition().y / 1e6).buffer(2.0 + max(p.GetSize().x, p.GetSize().y) / 2e6))
    rf_g = unary_union(rf) if rf else Polygon()
    cells = []
    for z in b.Zones():
        if z.GetIsRuleArea() and any(fnmatch.fnmatchcase(z.GetZoneName(), pat) for pat in
                                     ('K11_*', 'K10B_*', 'K6_*', 'K17_*', 'AFE_PARTITION')):
            cells.append(zone_poly(z))
    cell_g = unary_union(cells) if cells else Polygon()
    keep, cand = [], []
    why = {}
    for t in b.GetTracks():
        if t.GetClass() != 'PCB_VIA' or t.GetNetname() != 'GND':
            continue
        p = t.GetPosition()
        pt = Point(p.x / 1e6, p.y / 1e6)
        if (p.x, p.y) in ends or any(pd.HitTest(p) for pd in gpads):
            reason = 'pad'
        elif any(pt.distance(v) <= 1.2 for v in fast_vias):
            reason = 'R17 return'
        elif conn_g.contains(pt):
            reason = 'connector'
        elif sw_g.contains(pt):
            reason = 'switcher'
        elif rf_g.contains(pt):
            reason = 'RF'
        elif cell_g.contains(pt):
            reason = 'GND cell/AFE'
        else:
            reason = None
        if reason:
            keep.append((t, pt))
            why[reason] = why.get(reason, 0) + 1
        else:
            cand.append((t, pt))
    # Poisson-disk thinning of the free field (deterministic: sweep in raster order)
    kept_pts = [pt for _, pt in keep]
    from shapely.strtree import STRtree
    removed = 0
    cand.sort(key=lambda tp: (round(tp[1].y, 1), tp[1].x))
    kept_free = []
    for t, pt in cand:
        near = [q for q in kept_pts if abs(q.x - pt.x) < dmin and abs(q.y - pt.y) < dmin and q.distance(pt) < dmin]
        if near:
            b.Remove(t)
            _GRAVE.append(t)
            removed += 1
        else:
            kept_pts.append(pt)
            kept_free.append(pt)
    pcbnew.SaveBoard(dst, b)
    for ext in ('.kicad_pro', '.kicad_dru'):
        s = os.path.splitext(src)[0] + ext
        if os.path.isfile(s):
            shutil.copy2(s, os.path.splitext(dst)[0] + ext)
    print(f"thin: kept {len(keep)} mandated GND vias {why}; free field {len(cand)} -> {len(kept_free)} "
          f"(removed {removed}, dmin {dmin} mm)")


if __name__ == '__main__':
    main()

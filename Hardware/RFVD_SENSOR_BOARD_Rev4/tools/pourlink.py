"""pourlink.py IN.kicad_pcb OUT.kicad_pcb [--classes Power_Battery,Power_Digital,Power_Analog] [--report R.json]

Joins the open islands of power nets with copper POURS on F.Cu/B.Cu instead of thin tracks: for the closest island
pair a corridor polygon (the islands' copper grown by 0.4 mm plus a 2.4/3.6 mm wide band between them) becomes a zone of
that net (priority 5, above the GND outer fills; solid pad connection; min width 0.3 mm; clearances resolved by KiCad's
own engine from the net classes and the DRU, so the analog/SW/HS spacing rules hold). The zone is kept only when one
filled island of it touches both islands; otherwise it is removed and the next width/layer is tried. In1/In2/In4 stay
pure GND planes; In3 stays signal-only. KiCad python, scratch copies only."""
import json
import os
import shutil
import sys

import pcbnew
from shapely.geometry import LineString, Polygon
from shapely.ops import nearest_points, unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mr  # noqa: E402

_GRAVE = []


def poly_from_set(ps):
    return mr.poly_of(ps)


def main():
    argv = sys.argv[1:]

    def opt(k, d=None):
        return argv[argv.index(k) + 1] if k in argv else d
    src, dst = argv[0], argv[1]
    if os.path.normcase(os.path.realpath(dst)).startswith(mr.PROTECTED):
        sys.exit('refusing to write into the project folder')
    classes = (opt('--classes') or 'Power_Battery,Power_Digital,Power_Analog').split(',')
    B = mr.Board(src)
    b = B.b
    R = mr.Router(B)
    L = {'F.Cu': pcbnew.F_Cu, 'B.Cu': pcbnew.B_Cu}
    nets = [n for n in B.pads_by_net if mr.cls(n) in classes]
    if opt('--nets'):
        want = opt('--nets').split(',')
        nets = [n for n in nets if n in want or n.split('/')[-1] in want]
    report = []
    filler = pcbnew.ZONE_FILLER(b)
    for net in sorted(nets):
        for attempt in range(12):
            isl = R.islands(net)
            if len(isl) < 2:
                break
            geos = [unary_union([v for k_, v in I.items() if k_ != '__pads__' and not v.is_empty]) for I in isl]
            best = None
            for i in range(len(isl)):
                for j in range(i + 1, len(isl)):
                    d = geos[i].distance(geos[j])
                    if best is None or d < best[0]:
                        best = (d, i, j)
            d, i, j = best
            if d > 12.0:
                report.append({'net': net, 'ok': False, 'why': f'gap {d:.1f} mm too long for a pour'})
                break
            pa, pb = nearest_points(geos[i], geos[j])
            done = False
            for ln in ('B.Cu', 'F.Cu'):
                A_l, B_l = isl[i][ln], isl[j][ln]
                if A_l.is_empty or B_l.is_empty:
                    # the island has no copper on this layer: the pour cannot touch it
                    continue
                qa, qb = nearest_points(A_l, B_l)
                for wid in (2.4, 3.6, 5.0, 'hull'):
                    if wid == 'hull':      # Jev s1_route_plan: these supplies are pour_or_plane nets
                        # LOCAL hull only: the parts of both islands within 3 mm of the gap (an island can span the
                        # board - r19 made a 4000 mm2 +3V3_D pour over all of F.Cu)
                        loc = unary_union([A_l.intersection(qa.buffer(3.0)), B_l.intersection(qb.buffer(3.0))])
                        corr = loc.convex_hull.buffer(1.0).intersection(B.outline.buffer(-0.5))
                        if corr.area > 60.0:
                            continue
                    else:
                        corr = unary_union([LineString([(qa.x, qa.y), (qb.x, qb.y)]).buffer(wid / 2, cap_style=1),
                                            A_l.buffer(0.4), B_l.buffer(0.4)]).intersection(B.outline.buffer(-0.5))
                    polys = mr.polys_iter(corr.buffer(0))
                    if not polys:
                        continue
                    poly = max(polys, key=lambda p: p.area)
                    if poly.area > 60.0:
                        continue
                    z = pcbnew.ZONE(b)
                    z.SetLayer(L[ln])
                    z.SetNet(b.FindNet(net))
                    z.SetAssignedPriority(5)
                    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
                    z.SetMinThickness(int(0.3e6))
                    z.SetLocalClearance(int(mr.CLASS_CLR.get(mr.cls(net), 0.15) * 1e6))
                    z.SetZoneName(f"PWR_{net.split('/')[-1]}_{attempt}")
                    o = z.Outline()
                    o.NewOutline()
                    for x, y in list(poly.exterior.coords)[:-1]:
                        o.Append(int(round(x * 1e6)), int(round(y * 1e6)))
                    b.Add(z)
                    filler.Fill([z])
                    fp = poly_from_set(z.GetFilledPolysList(L[ln]))
                    ok = any(piece.intersects(A_l) and piece.intersects(B_l) for piece in mr.polys_iter(fp))
                    if ok:
                        report.append({'net': net, 'ok': True, 'layer': ln, 'width': wid, 'gap': round(d, 2)})
                        print(f"  pour {net} on {ln} ({wid} mm corridor, gap {d:.2f} mm)")
                        sys.stdout.flush()
                        done = True
                        break
                    b.Remove(z)
                    _GRAVE.append(z)
                if done:
                    break
            if not done:
                report.append({'net': net, 'ok': False, 'why': f'no pour joins the islands (gap {d:.2f} mm)'})
                break
    filler.Fill(b.Zones())
    pcbnew.SaveBoard(dst, b)
    for ext in ('.kicad_pro', '.kicad_dru'):
        s = os.path.splitext(src)[0] + ext
        if os.path.isfile(s):
            shutil.copy2(s, os.path.splitext(dst)[0] + ext)
    ok = sum(1 for r in report if r['ok'])
    print(f"pourlink: {ok} links poured, {len(report) - ok} not")
    for r in report:
        if not r['ok']:
            print('  --', r['net'], r['why'])
    if opt('--report'):
        json.dump(report, open(opt('--report'), 'w'), indent=1)


if __name__ == '__main__':
    main()

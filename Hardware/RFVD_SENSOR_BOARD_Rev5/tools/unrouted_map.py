"""unrouted_map.py BOARD.kicad_pcb OUT_PREFIX
Lists every missing connection of the board (KiCad connectivity after zone fill) and draws an 'unrouted map':
board outline, pads (F red / B blue), existing tracks faint, and one straight ratsnest line per missing connection
between the closest points of the two copper islands, coloured by group (LCD/J4, EXP/J11, power/charger, other).
Writes OUT_PREFIX.csv (net, group, gap mm, island A parts, island B parts, endpoints) and OUT_PREFIX.png.
Run with KiCad's python:  "C:/Program Files/KiCad/10.0/bin/python.exe" tools/unrouted_map.py RFVD_SENSOR_BOARD.kicad_pcb outputs/unrouted
"""
import csv
import sys

import pcbnew
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import nearest_points, unary_union

src, prefix = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(src)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.BuildConnectivity()
conn = b.GetConnectivity()

POWER = {'VSYS', 'VBAT_PACK', 'CHG_BAT', 'REGN', 'SDRV', '+3V3_D', 'VBAT_RTC', 'VBUS_DET', 'CHG_INT_N', 'USB_DP',
         'USB_DM', 'QON_N', 'VBUS', '+3V3_UI', '+5V_A'}


def group(n):
    s = n.split('/')[-1]
    if 'LCD' in s:
        return 'LCD bus / J4'
    if s.startswith('EXP'):
        return 'Expansion / J11'
    if s in POWER:
        return 'Power / charger'
    if s == 'GND':
        return 'GND (plane vias)'
    return 'Other'


def poly(ps):
    out = []
    for i in range(ps.OutlineCount()):
        ch = ps.Outline(i)
        pts = [(ch.CPoint(k).x / 1e6, ch.CPoint(k).y / 1e6) for k in range(ch.PointCount())]
        if len(pts) >= 3:
            out.append(Polygon(pts).buffer(0))
    return unary_union(out) if out else Polygon()


def item_geo(it):
    it = it.Cast() if hasattr(it, 'Cast') else it
    cl = it.GetClass()
    if cl == 'PAD':
        lid = pcbnew.F_Cu if it.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
        return poly(it.GetEffectivePolygon(lid, pcbnew.ERROR_INSIDE))
    if cl == 'PCB_VIA':
        c = it.GetPosition()
        return Point(c.x / 1e6, c.y / 1e6).buffer(it.GetWidth(pcbnew.F_Cu) / 2e6)
    if cl in ('PCB_TRACK', 'PCB_ARC'):
        return LineString([(it.GetStart().x / 1e6, it.GetStart().y / 1e6),
                           (it.GetEnd().x / 1e6, it.GetEnd().y / 1e6)]).buffer(it.GetWidth() / 2e6)
    return None


pads_by_net = {}
for f in b.GetFootprints():
    for p in f.Pads():
        n = p.GetNetname()
        if n and not n.startswith('unconnected'):
            pads_by_net.setdefault(n, []).append(p)
rows = []
for net, pads in sorted(pads_by_net.items()):
    seen, isl = set(), []
    for p in pads:
        if p.m_Uuid.AsString() in seen:
            continue
        items = [p] + list(conn.GetConnectedItems(p))
        geos, refs = [], set()
        for it in items:
            it = it.Cast() if hasattr(it, 'Cast') else it
            if it.GetClass() == 'PAD':
                seen.add(it.m_Uuid.AsString())
                refs.add(f"{it.GetParentFootprint().GetReference()}.{it.GetNumber()}")
            g = item_geo(it)
            if g is not None and not g.is_empty:
                geos.append(g)
        isl.append((unary_union(geos), sorted(refs)))
    if len(isl) < 2:
        continue
    # spanning connections between islands (Prim on the island distance graph)
    inside, rest = [0], list(range(1, len(isl)))
    while rest:
        best = None
        for i in inside:
            for j in rest:
                d = isl[i][0].distance(isl[j][0])
                if best is None or d < best[0]:
                    best = (d, i, j)
        d, i, j = best
        pa, pb = nearest_points(isl[i][0], isl[j][0])
        rows.append({'net': net, 'group': group(net), 'gap_mm': round(d, 2),
                     'island_A': ' '.join(isl[i][1][:8]) + (' ...' if len(isl[i][1]) > 8 else ''),
                     'island_B': ' '.join(isl[j][1][:8]) + (' ...' if len(isl[j][1]) > 8 else ''),
                     'ax': round(pa.x, 3), 'ay': round(pa.y, 3), 'bx': round(pb.x, 3), 'by': round(pb.y, 3)})
        inside.append(j)
        rest.remove(j)
with open(prefix + '.csv', 'w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ['net'])
    w.writeheader()
    for r in sorted(rows, key=lambda r: (r['group'], r['net'])):
        w.writerow(r)
# map
ps = pcbnew.SHAPE_POLY_SET()
b.GetBoardPolygonOutlines(ps, True)
outline = poly(ps)
x0, y0, x1, y1 = outline.bounds
S = 16.0
W, H = int((x1 - x0 + 4) * S), int((y1 - y0 + 4) * S)
im = Image.new('RGB', (W, H), (250, 250, 250))
dr = ImageDraw.Draw(im, 'RGBA')
P = lambda x, y: ((x - x0 + 2) * S, (y - y0 + 2) * S)
for g in getattr(outline, 'geoms', [outline]):
    dr.polygon([P(x, y) for x, y in g.exterior.coords], fill=(232, 240, 228), outline=(60, 60, 60))
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        continue
    a, c = t.GetStart(), t.GetEnd()
    dr.line([P(a.x / 1e6, a.y / 1e6), P(c.x / 1e6, c.y / 1e6)], fill=(150, 150, 150, 70), width=1)
for f in b.GetFootprints():
    for p in f.Pads():
        lid = pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
        g = poly(p.GetEffectivePolygon(lid, pcbnew.ERROR_INSIDE))
        for q in getattr(g, 'geoms', [g]):
            if q.is_empty:
                continue
            dr.polygon([P(x, y) for x, y in q.exterior.coords], fill=(200, 80, 80, 120) if lid == pcbnew.F_Cu else (80, 110, 210, 120))
COL = {'LCD bus / J4': (230, 120, 0), 'Expansion / J11': (150, 0, 200), 'Power / charger': (220, 0, 0),
       'Other': (0, 140, 60), 'GND (plane vias)': (120, 120, 120)}
for r in rows:
    col = COL[r['group']]
    dr.line([P(r['ax'], r['ay']), P(r['bx'], r['by'])], fill=col + (230,), width=3)
    for x, y in ((r['ax'], r['ay']), (r['bx'], r['by'])):
        px, py = P(x, y)
        dr.ellipse([px - 4, py - 4, px + 4, py + 4], outline=col, width=2)
try:
    font = ImageFont.truetype('arial.ttf', 16)
except Exception:
    font = ImageFont.load_default()
ly = 8
for k, col in COL.items():
    n = sum(1 for r in rows if r['group'] == k)
    dr.rectangle([8, ly, 26, ly + 14], fill=col)
    dr.text((32, ly - 1), f'{k}: {n}', fill=(20, 20, 20), font=font)
    ly += 20
im.save(prefix + '.png')
print(f"unrouted_map: {len(rows)} missing connections -> {prefix}.csv / {prefix}.png")

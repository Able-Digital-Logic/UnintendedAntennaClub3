"""layer_images.py BOARD.kicad_pcb OUT_DIR [--px 20]
One image per copper layer, showing only that layer's copper (zone fills after a fresh fill, tracks, pads on that
layer, via barrels as rings) plus every footprint's courtyard outline and reference for orientation. Footprints on
the viewed side are drawn bright; the other side is dim. Colours: copper of each layer in its KiCad colour, GND copper
darker, board outline white. KiCad python (read-only)."""
import os
import sys

import pcbnew
from PIL import Image, ImageDraw, ImageFont

argv = sys.argv[1:]
src, out = argv[0], argv[1]
S = float(argv[argv.index('--px') + 1]) if '--px' in argv else 20.0
os.makedirs(out, exist_ok=True)
b = pcbnew.LoadBoard(src)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
bb = b.GetBoardEdgesBoundingBox()
X0, Y0 = bb.GetLeft() / 1e6 - 1.0, bb.GetTop() / 1e6 - 3.0
W, H = int((bb.GetWidth() / 1e6 + 2) * S), int((bb.GetHeight() / 1e6 + 4) * S)
LAYERS = [('F.Cu', (200, 52, 52)), ('In1.Cu', (127, 200, 127)), ('In2.Cu', (206, 125, 44)), ('In3.Cu', (79, 203, 203)),
          ('In4.Cu', (219, 98, 139)), ('B.Cu', (77, 127, 196))]
try:
    font = ImageFont.truetype('arial.ttf', max(9, int(S * 0.42)))
    title = ImageFont.truetype('arialbd.ttf', max(14, int(S * 0.9)))
except Exception:
    font = title = ImageFont.load_default()


def P(x, y):
    return ((x - X0) * S, (y - Y0) * S)


def polys(ps):
    out_ = []
    for i in range(ps.OutlineCount()):
        ch = ps.Outline(i)
        pts = [P(ch.CPoint(k).x / 1e6, ch.CPoint(k).y / 1e6) for k in range(ch.PointCount())]
        holes = []
        for h in range(ps.HoleCount(i)):
            hc = ps.Hole(i, h)
            holes.append([P(hc.CPoint(k).x / 1e6, hc.CPoint(k).y / 1e6) for k in range(hc.PointCount())])
        out_.append((pts, holes))
    return out_


ps = pcbnew.SHAPE_POLY_SET()
b.GetBoardPolygonOutlines(ps, True)
outline = polys(ps)
for name, col in LAYERS:
    lid = b.GetLayerID(name)
    im = Image.new('RGB', (W, H), (14, 16, 20))
    dr = ImageDraw.Draw(im, 'RGBA')
    for pts, holes in outline:
        dr.polygon(pts, fill=(28, 32, 38))
    dim = tuple(int(c * 0.55) for c in col)
    # zone fills on this layer (GND planes appear as solid copper with antipads)
    for z in b.Zones():
        if z.GetIsRuleArea() or not z.IsOnLayer(lid):
            continue
        zc = dim if z.GetNetname() == 'GND' else col
        for pts, holes in polys(z.GetFilledPolysList(lid)):
            if len(pts) >= 3:
                dr.polygon(pts, fill=zc + (255,))
            for hp in holes:
                if len(hp) >= 3:
                    dr.polygon(hp, fill=(28, 32, 38, 255))
    # tracks
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA' or t.GetLayer() != lid:
            continue
        a, c = t.GetStart(), t.GetEnd()
        w = max(1, int(round(t.GetWidth() / 1e6 * S)))
        dr.line([P(a.x / 1e6, a.y / 1e6), P(c.x / 1e6, c.y / 1e6)], fill=col + (255,), width=w)
        r = w / 2
        for q in (a, c):
            px, py = P(q.x / 1e6, q.y / 1e6)
            dr.ellipse([px - r, py - r, px + r, py + r], fill=col + (255,))
    # pads on this layer
    for f in b.GetFootprints():
        for p in f.Pads():
            if not p.IsOnLayer(lid):
                continue
            for pts, holes in polys(p.GetEffectivePolygon(lid, pcbnew.ERROR_INSIDE)):
                if len(pts) >= 3:
                    dr.polygon(pts, fill=(235, 200, 90, 255) if p.GetNetname() != 'GND' else (170, 150, 80, 255))
            if p.GetDrillSize().x > 0:
                c = p.GetPosition()
                rh = p.GetDrillSize().x / 2e6 * S
                px, py = P(c.x / 1e6, c.y / 1e6)
                dr.ellipse([px - rh, py - rh, px + rh, py + rh], fill=(10, 10, 10, 255))
    # vias: copper ring on every layer they cross (inner GND planes show their antipads around non-GND vias)
    for t in b.GetTracks():
        if t.GetClass() != 'PCB_VIA':
            continue
        c = t.GetPosition()
        px, py = P(c.x / 1e6, c.y / 1e6)
        rv = t.GetWidth(pcbnew.F_Cu) / 2e6 * S
        rh = t.GetDrill() / 2e6 * S
        connected = t.GetNetname() == 'GND' or name in ('F.Cu', 'In3.Cu', 'B.Cu')
        if connected:
            dr.ellipse([px - rv, py - rv, px + rv, py + rv], fill=(230, 230, 230, 255) if t.GetNetname() != 'GND' else (120, 220, 120, 255))
        dr.ellipse([px - rh, py - rh, px + rh, py + rh], fill=(10, 10, 10, 255))
    # footprints: courtyards + references
    side_b = name == 'B.Cu'
    for f in b.GetFootprints():
        fb = f.IsFlipped()
        cy = f.GetCourtyard(pcbnew.B_CrtYd if fb else pcbnew.F_CrtYd)
        bright = (fb == side_b) if name in ('F.Cu', 'B.Cu') else False
        oc = (255, 255, 255, 230) if bright else ((200, 200, 200, 120) if not fb else (150, 170, 220, 110))
        for pts, holes in polys(cy):
            if len(pts) >= 2:
                dr.line(pts + [pts[0]], fill=oc, width=2 if bright else 1)
        px, py = P(f.GetPosition().x / 1e6, f.GetPosition().y / 1e6)
        dr.text((px, py), f.GetReference(), fill=(255, 255, 255, 235) if bright else (210, 210, 210, 150), font=font, anchor='mm')
    for pts, holes in outline:
        dr.line(pts + [pts[0]], fill=(255, 255, 255), width=2)
    note = {'F.Cu': 'top copper (components on F bright)', 'In1.Cu': 'inner 1: solid GND plane',
            'In2.Cu': 'inner 2: solid GND plane (In3 reference)', 'In3.Cu': 'inner 3: buried signal / power layer',
            'In4.Cu': 'inner 4: solid GND plane', 'B.Cu': 'bottom copper (components on B bright), viewed from the top'}[name]
    dr.text((8, 6), f"{name} - {note}", fill=(255, 255, 255), font=title)
    fn = os.path.join(out, f"layer_{LAYERS.index((name, col)) + 1}_{name.replace('.', '_')}.png")
    im.save(fn)
    print('wrote', fn)

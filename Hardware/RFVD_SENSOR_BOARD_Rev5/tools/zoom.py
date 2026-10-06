"""Zoomed render: zoom.py board out.png x0 y0 x1 y1 [px_per_mm] [side F|B|FB] [--layer LAYER]
Pads labelled with number and net, courtyards, rule areas, tracks (F red, In3 magenta, B blue), vias, board outline.
--net NET[,NET]: draw those nets' copper and pads on top in bright green / cyan (all layers).
--layer LAYER: single-layer congestion view instead (that layer's copper and zone fills, every via barrel and
drilled pad and that layer's pads; replaces place/layer_render.py, 2026-10-02). --net highlights apply here too.
--grid: millimetre grid with coordinate labels (for reading hand-route coordinates, 2026-10-03).
--free W[,CLR]: with --layer, shade in dark green where the centre line of a new W mm track keeps CLR mm (default 0.15)
from every other copper item of that layer (pads, tracks, vias, non-GND fills, holes): the open corridors for hand
routing. GND pours are not obstacles (they re-fill). Visual aid only - pen.py --check / DRC give the exact verdict.
--open CSV: draw the missing connections from unrouted_map.py's CSV (closest points of the two islands) as yellow
lines with end circles and the net name; with --net only those nets (2026-10-03, routing-guide maps)."""
import csv
import sys
import pcbnew
from PIL import Image, ImageDraw, ImageFont
argv = sys.argv[1:]
OPEN = None
if '--open' in argv:
    i_ = argv.index('--open')
    OPEN = list(csv.DictReader(open(argv[i_ + 1], encoding='utf-8')))
    argv = argv[:i_] + argv[i_ + 2:]
LAYER = argv[argv.index('--layer') + 1] if '--layer' in argv else None
if LAYER:
    i_ = argv.index('--layer')
    argv = argv[:i_] + argv[i_ + 2:]
HL = set(argv[argv.index('--net') + 1].split(',')) if '--net' in argv else set()
if HL:
    i_ = argv.index('--net')
    argv = argv[:i_] + argv[i_ + 2:]
GRID = '--grid' in argv
argv = [a for a in argv if a != '--grid']
FREE = None
if '--free' in argv:
    i_ = argv.index('--free')
    FREE = [float(v) for v in argv[i_ + 1].split(',')]
    argv = argv[:i_] + argv[i_ + 2:]
src, out = argv[0], argv[1]
x0, y0, x1, y1 = map(float, argv[2:6])
S = float(argv[6]) if len(argv) > 6 else 60
sides = argv[7] if len(argv) > 7 else 'FB'
b = pcbnew.LoadBoard(src)
HLC = [(0, 230, 60, 255), (0, 200, 255, 255), (255, 0, 200, 255), (255, 255, 255, 255)]


def hl_col(net):
    n = net.split('/')[-1]
    return HLC[sorted(HL).index(n) % len(HLC)] if n in HL else None


def draw_open(draw, P, fnt, col=(255, 230, 0, 255)):
    """missing connections as lines between the two closest island points, labelled with the short net name"""
    if not OPEN:
        return
    for r in OPEN:
        n = r['net'].split('/')[-1]
        if HL and n not in HL:
            continue
        a = (float(r['ax']), float(r['ay']))
        e = (float(r['bx']), float(r['by']))
        draw.line([P(*a), P(*e)], fill=col, width=2)
        for q in (a, e):
            px, py = P(*q)
            draw.ellipse([px - 5, py - 5, px + 5, py + 5], outline=col, width=2)
        # label at the end that lies inside the window (if any), else at the midpoint
        lx, ly = next((q for q in (a, e) if x0 <= q[0] <= x1 and y0 <= q[1] <= y1), ((a[0] + e[0]) / 2, (a[1] + e[1]) / 2))
        px, py = P(lx, ly)
        draw.text((px + 6, py + 2), n, fill=col, font=fnt)


def grid(draw, P, fnt, dark):
    import math
    step = 1.0 if S >= 25 else 2.0
    lab = step if S >= 40 else 2 * step
    col = (70, 70, 80, 255) if dark else (205, 205, 205, 255)
    tc = (170, 170, 190) if dark else (110, 110, 110)
    x = math.ceil(x0 / step) * step
    while x <= x1:
        draw.line([P(x, y0), P(x, y1)], fill=col, width=1)
        if abs(x / lab - round(x / lab)) < 1e-6:
            draw.text((P(x, y0)[0] + 2, 2), f"{x:g}", fill=tc, font=fnt)
        x += step
    y = math.ceil(y0 / step) * step
    while y <= y1:
        draw.line([P(x0, y), P(x1, y)], fill=col, width=1)
        if abs(y / lab - round(y / lab)) < 1e-6:
            draw.text((2, P(x0, y)[1] + 1), f"{y:g}", fill=tc, font=fnt)
        y += step


if LAYER:
    lid = b.GetLayerID(LAYER)
    im = Image.new('RGB', (int((x1 - x0) * S), int((y1 - y0) * S)), (12, 12, 16))
    d_ = ImageDraw.Draw(im, 'RGBA')
    P_ = lambda x, y: ((x - x0) * S, (y - y0) * S)
    try:
        f_ = ImageFont.truetype('arial.ttf', max(9, int(S * 0.16)))
    except Exception:
        f_ = ImageFont.load_default()
    if FREE:
        import numpy as np
        from shapely.geometry import LineString, Point, Polygon, box as sbox
        from shapely.ops import unary_union
        fw, fc = FREE[0], (FREE[1] if len(FREE) > 1 else 0.15)
        grow = fw / 2 + fc
        win = sbox(x0 - 3, y0 - 3, x1 + 3, y1 + 3)
        obs = []

        def polys(ps):
            out = []
            for i in range(ps.OutlineCount()):
                ch = ps.Outline(i)
                pts = [(ch.CPoint(k).x / 1e6, ch.CPoint(k).y / 1e6) for k in range(ch.PointCount())]
                if len(pts) > 2:
                    out.append(Polygon(pts).buffer(0))
            return out
        for t in b.GetTracks():
            if t.GetClass() == 'PCB_VIA':
                c = t.GetPosition()
                g = Point(c.x / 1e6, c.y / 1e6).buffer(t.GetWidth(pcbnew.F_Cu) / 2e6, 12)
            elif t.GetLayer() == lid:
                g = LineString([(t.GetStart().x / 1e6, t.GetStart().y / 1e6), (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)]).buffer(t.GetWidth() / 2e6, 6)
            else:
                continue
            if g.intersects(win):
                obs.append(g)
        for f in b.GetFootprints():
            for p in f.Pads():
                c = p.GetPosition()
                if not win.contains(Point(c.x / 1e6, c.y / 1e6)):
                    continue
                if p.IsOnLayer(lid):
                    obs += polys(p.GetEffectivePolygon(lid, pcbnew.ERROR_OUTSIDE))
                if p.GetDrillSize().x > 0:
                    obs.append(Point(c.x / 1e6, c.y / 1e6).buffer(p.GetDrillSize().x / 2e6 + 0.1, 12))
        for z in b.Zones():
            if not z.GetIsRuleArea() and z.IsOnLayer(lid) and z.GetNetname() not in ('GND', ''):
                obs += polys(z.GetFilledPolysList(lid))
        ps = pcbnew.SHAPE_POLY_SET()
        b.GetBoardPolygonOutlines(ps, False)
        inside = unary_union(polys(ps)).buffer(-(0.5 + fw / 2))
        blocked = unary_union(obs).buffer(grow, 6)
        free_g = inside.difference(blocked).intersection(sbox(x0, y0, x1, y1))
        for q in (free_g.geoms if hasattr(free_g, 'geoms') else [free_g]):
            if q.is_empty or q.geom_type != 'Polygon':
                continue
            d_.polygon([P_(x, y) for x, y in q.exterior.coords], fill=(20, 95, 40, 255))
            for ring in q.interiors:
                d_.polygon([P_(x, y) for x, y in ring.coords], fill=(12, 12, 16, 255))
    if GRID:
        grid(d_, P_, f_, True)
    for z in b.Zones():
        if z.GetIsRuleArea() or not z.IsOnLayer(lid) or z.GetNetname() in ('GND', ''):
            continue
        ps = z.GetFilledPolysList(lid)
        for i in range(ps.OutlineCount()):
            ch = ps.Outline(i)
            pts = [P_(ch.CPoint(k).x / 1e6, ch.CPoint(k).y / 1e6) for k in range(ch.PointCount())]
            if len(pts) > 2:
                d_.polygon(pts, fill=(255, 150, 40, 120))
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            c = t.GetPosition()
            r = t.GetWidth(pcbnew.F_Cu) / 2e6 * S
            px, py = P_(c.x / 1e6, c.y / 1e6)
            d_.ellipse([px - r, py - r, px + r, py + r], fill=(60, 200, 90, 255) if t.GetNetname() == 'GND' else (250, 220, 60, 255))
        elif t.GetLayer() == lid:
            s_, e_ = t.GetStart(), t.GetEnd()
            d_.line([P_(s_.x / 1e6, s_.y / 1e6), P_(e_.x / 1e6, e_.y / 1e6)], fill=hl_col(t.GetNetname()) or (255, 150, 40, 255), width=max(1, int(t.GetWidth() / 1e6 * S)))
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.IsOnLayer(lid):
                ps = p.GetEffectivePolygon(lid, pcbnew.ERROR_OUTSIDE)
                for i in range(ps.OutlineCount()):
                    ch = ps.Outline(i)
                    pts = [P_(ch.CPoint(k).x / 1e6, ch.CPoint(k).y / 1e6) for k in range(ch.PointCount())]
                    if len(pts) > 2:
                        hc = hl_col(p.GetNetname())
                        d_.polygon(pts, fill=hc or ((60, 140, 70, 230) if p.GetNetname() == 'GND' else (150, 150, 165, 230)),
                                   outline=(255, 255, 255, 120))
                if S >= 40:
                    c = p.GetPosition()
                    px, py = P_(c.x / 1e6, c.y / 1e6)
                    d_.text((px - 8, py - 6), f"{f.GetReference()}.{p.GetNumber()}", fill=(0, 0, 0), font=f_)
            if p.GetDrillSize().x > 0:
                c = p.GetPosition()
                r = p.GetDrillSize().x / 2e6 * S + 2
                px, py = P_(c.x / 1e6, c.y / 1e6)
                d_.ellipse([px - r, py - r, px + r, py + r], outline=(0, 200, 255, 255))
    draw_open(d_, P_, f_)
    im.save(out)
    print('saved', out, im.size)
    sys.exit(0)
img = Image.new('RGB', (int((x1 - x0) * S), int((y1 - y0) * S)), 'white')
dr = ImageDraw.Draw(img, 'RGBA')
try:
    font = ImageFont.truetype('arial.ttf', max(9, int(S * 0.16)))
    fbig = ImageFont.truetype('arialbd.ttf', max(11, int(S * 0.3)))
except Exception:
    font = fbig = ImageFont.load_default()
P = lambda x, y: ((x - x0) * S, (y - y0) * S)
if GRID:
    grid(dr, P, font, False)
def short(n):
    return n.split('/')[-1].replace('Net-(', '').replace(')', '')[:14]
# board outline
for d in b.GetDrawings():
    if d.GetLayer() == pcbnew.Edge_Cuts:
        if d.GetShapeStr().lower().startswith('arc'):
            m_ = d.GetArcMid()
            pts_ = [d.GetStart(), m_, d.GetEnd()]
        else:
            pts_ = [d.GetStart(), d.GetEnd()]
        dr.line([P(q.x / 1e6, q.y / 1e6) for q in pts_], fill=(120, 120, 0, 255), width=2)
# rule areas
for z in b.Zones():
    if z.GetIsRuleArea():
        o = z.Outline()
        for i in range(o.OutlineCount()):
            ch = o.Outline(i)
            pts = [P(ch.CPoint(k).x / 1e6, ch.CPoint(k).y / 1e6) for k in range(ch.PointCount())]
            if len(pts) > 2:
                dr.polygon(pts, outline=(0, 160, 0, 255))
# tracks
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        c = t.GetPosition(); r = t.GetWidth(pcbnew.F_Cu) / 2e6 * S
        x, y = P(c.x / 1e6, c.y / 1e6)
        dr.ellipse([x - r, y - r, x + r, y + r], fill=(90, 90, 90, 200))
        continue
    L = b.GetLayerName(t.GetLayer())
    if (L == 'F.Cu' and 'F' in sides) or (L == 'B.Cu' and 'B' in sides) or L == 'In3.Cu':
        col = {'F.Cu': (220, 0, 0, 160), 'B.Cu': (0, 60, 220, 160), 'In3.Cu': (170, 0, 170, 160)}[L]
        dr.line([P(t.GetStart().x / 1e6, t.GetStart().y / 1e6), P(t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)], fill=col,
                width=max(1, int(t.GetWidth() / 1e6 * S)))
for f in b.GetFootprints():
    side = 'B' if f.IsFlipped() else 'F'
    if side not in sides:
        continue
    cy = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)
    for i in range(cy.OutlineCount()):
        ch = cy.Outline(i)
        pts = [P(ch.CPoint(k).x / 1e6, ch.CPoint(k).y / 1e6) for k in range(ch.PointCount())]
        if len(pts) > 2:
            dr.polygon(pts, outline=(0, 0, 0, 255) if side == 'F' else (0, 0, 160, 255))
    for p in f.Pads():
        sh = p.GetEffectivePolygon(pcbnew.F_Cu if side == 'F' else pcbnew.B_Cu) if hasattr(p, 'GetEffectivePolygon') else None
        bb = p.GetBoundingBox()
        col = (240, 180, 50, 200) if side == 'F' else (120, 170, 255, 200)
        if p.GetNetname() == 'GND':
            col = (150, 210, 150, 200)
        dr.rectangle([P(bb.GetX() / 1e6, bb.GetY() / 1e6), P((bb.GetX() + bb.GetWidth()) / 1e6, (bb.GetY() + bb.GetHeight()) / 1e6)], fill=col, outline=(0, 0, 0, 120))
        c = p.GetPosition()
        x, y = P(c.x / 1e6, c.y / 1e6)
        if x0 <= c.x / 1e6 <= x1 and y0 <= c.y / 1e6 <= y1:
            dr.text((x - 8, y - 6), f"{p.GetNumber()}:{short(p.GetNetname())}", fill=(0, 0, 0), font=font)
    c = f.GetPosition()
    x, y = P(c.x / 1e6, c.y / 1e6)
    dr.text((x + 4, y - 22), f.GetReference() + ('(B)' if side == 'B' else ''), fill=(120, 0, 0) if side == 'F' else (0, 0, 140), font=fbig)
if HL:
    cols = [(0, 230, 60, 255), (0, 200, 255, 255), (255, 120, 0, 255), (255, 0, 200, 255)]
    hl = sorted(HL)
    for t in b.GetTracks():
        n = t.GetNetname().split('/')[-1]
        if n not in HL:
            continue
        col = cols[hl.index(n) % len(cols)]
        if t.GetClass() == 'PCB_VIA':
            c = t.GetPosition()
            r = t.GetWidth(pcbnew.F_Cu) / 2e6 * S
            x, y = P(c.x / 1e6, c.y / 1e6)
            dr.ellipse([x - r, y - r, x + r, y + r], outline=col, width=3)
        else:
            dr.line([P(t.GetStart().x / 1e6, t.GetStart().y / 1e6), P(t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)], fill=col,
                    width=max(2, int(t.GetWidth() / 1e6 * S)))
    for f in b.GetFootprints():
        for p in f.Pads():
            n = p.GetNetname().split('/')[-1]
            if n in HL:
                bb = p.GetBoundingBox()
                dr.rectangle([P(bb.GetX() / 1e6, bb.GetY() / 1e6), P((bb.GetX() + bb.GetWidth()) / 1e6, (bb.GetY() + bb.GetHeight()) / 1e6)],
                             outline=cols[hl.index(n) % len(cols)], width=3)
draw_open(dr, P, fbig, (200, 120, 0, 255))
img.save(out)
print('saved', out, img.size)

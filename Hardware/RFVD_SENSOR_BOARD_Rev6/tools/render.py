"""Render a board (F and B side by side) with courtyards, pads, refs, rule areas and tracks. KiCad python."""
import sys, math
import pcbnew
from PIL import Image, ImageDraw, ImageFont
src, out = sys.argv[1], sys.argv[2]
S = float(sys.argv[3]) if len(sys.argv) > 3 else 14.0   # px per mm
b = pcbnew.LoadBoard(src)
bb = b.GetBoardEdgesBoundingBox()
X0, Y0, W, H = bb.GetX()/1e6, bb.GetY()/1e6, bb.GetWidth()/1e6, bb.GetHeight()/1e6
pad = 2
img = Image.new('RGB', (int((2*W + 3*pad) * S), int((H + 2*pad) * S) + 30), 'white')
dr = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype('arial.ttf', max(9, int(S*0.55)))
    big = ImageFont.truetype('arialbd.ttf', 20)
except Exception:
    font = big = ImageFont.load_default()
def P(x, y, side):
    ox = pad if side == 'F' else (W + 2*pad)
    return ((x - X0 + ox) * S, (y - Y0 + pad) * S + 30)
for side, title in (('F', 'TOP (F.Cu)'), ('B', 'BOTTOM (B.Cu, seen from top)')):
    dr.text(P(X0, Y0 - 1.9, side), title, fill='black', font=big)
    dr.rectangle([P(X0, Y0, side), P(X0+W, Y0+H, side)], outline='black', width=2)
    # rule areas
    for z in b.Zones():
        if not z.GetIsRuleArea():
            continue
        lays = [b.GetLayerName(l) for l in z.GetLayerSet().CuStack()]
        if ('F.Cu' if side == 'F' else 'B.Cu') not in lays:
            continue
        name = z.GetZoneName()
        col = (0, 150, 0) if name.startswith('AFE') else (200, 120, 0) if name.startswith('BR') else (160, 160, 160)
        o = z.Outline()
        for i in range(o.OutlineCount()):
            ch = o.Outline(i)
            pts = [P(ch.CPoint(k).x/1e6, ch.CPoint(k).y/1e6, side) for k in range(ch.PointCount())]
            if len(pts) > 2:
                dr.polygon(pts, outline=col, width=3 if name.startswith('AFE') else 1)
        if name and not name.startswith('AFE'):
            c = z.GetBoundingBox().GetCenter()
            dr.text(P(c.x/1e6, c.y/1e6, side), name[:14], fill=col, font=font)
    # tracks
    for t in b.GetTracks():
        ln = b.GetLayerName(t.GetLayer()) if t.GetClass() != 'PCB_VIA' else ''
        if t.GetClass() == 'PCB_VIA':
            if side == 'F':
                p = P(t.GetPosition().x/1e6, t.GetPosition().y/1e6, side); r = 0.25*S
                dr.ellipse([p[0]-r, p[1]-r, p[0]+r, p[1]+r], outline=(120, 120, 120))
            continue
        if ln != ('F.Cu' if side == 'F' else 'B.Cu') and not (ln == 'In3.Cu' and side == 'F'):
            continue
        col = (200, 0, 0) if ln == 'F.Cu' else (0, 0, 200) if ln == 'B.Cu' else (180, 0, 180)
        dr.line([P(t.GetStart().x/1e6, t.GetStart().y/1e6, side), P(t.GetEnd().x/1e6, t.GetEnd().y/1e6, side)],
                fill=col, width=max(1, int(t.GetWidth()/1e6*S)))
    # footprints
    for f in b.GetFootprints():
        fs = 'B' if f.IsFlipped() else 'F'
        if fs != side:
            continue
        cy = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)
        drawn = False
        if cy.OutlineCount():
            ch = cy.Outline(0)
            pts = [P(ch.CPoint(k).x/1e6, ch.CPoint(k).y/1e6, side) for k in range(ch.PointCount())]
            if len(pts) > 2:
                dr.polygon(pts, outline=(0, 0, 0)); drawn = True
        for p in f.Pads():
            bbp = p.GetBoundingBox()
            dr.rectangle([P(bbp.GetX()/1e6, bbp.GetY()/1e6, side), P((bbp.GetX()+bbp.GetWidth())/1e6, (bbp.GetY()+bbp.GetHeight())/1e6, side)],
                         fill=(230, 180, 60) if p.GetNetname() not in ('GND',) else (150, 200, 150))
        c = f.GetPosition()
        dr.text(P(c.x/1e6 - 0.6, c.y/1e6 - 0.5, side), f.GetReference(), fill=(0, 0, 0), font=font)
img.save(out)
print('saved', out, img.size)

"""restitch.py IN.kicad_pcb OUT.kicad_pcb [--dmin 2.5] [--grid 0.25]
Refill the GND stitching-via field AFTER routing (thin.py removed the free field before routing).
1. raster sweep (grid --grid mm): a 0.45/0.20 POFV GND via goes wherever it is legal by mr.py's exact rule model
   (pairwise DRU clearances with courtyard exemptions, 0.20 hole-to-copper, 0.25 hole-to-hole, lane/AFE/boss via bans,
   0.5 mm edge) and no GND via is closer than --dmin (default 2.5 mm, ~6x denser than the rulebook's optional grid)
2. rulebook R21: every F.Cu/B.Cu GND fill island gets at least 2 vias (search inside the island, spacing relaxed)
KiCad python, scratch copies only."""
import math
import os
import shutil
import sys

import pcbnew
from shapely.geometry import Point

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mr  # noqa: E402

VD, VH = 0.45, 0.2


def main():
    argv = sys.argv[1:]
    src, dst = argv[0], argv[1]
    dmin = float(argv[argv.index('--dmin') + 1]) if '--dmin' in argv else 2.5
    grid = float(argv[argv.index('--grid') + 1]) if '--grid' in argv else 0.25
    if os.path.normcase(os.path.realpath(dst)).startswith(mr.PROTECTED):
        sys.exit('refusing to write into the project folder')
    B = mr.Board(src)
    b = B.b
    R = mr.Router(B)
    gnd = b.FindNet('GND')
    bans = B.bans('GND')
    cell = dmin
    hashv = {}

    def hkey(x, y):
        return (int(x // cell), int(y // cell))

    def near(x, y, d):
        kx, ky = hkey(x, y)
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                for (px, py) in hashv.get((kx + i, ky + j), ()):
                    if (px - x) ** 2 + (py - y) ** 2 < d * d:
                        return True
        return False

    def add_pt(x, y):
        hashv.setdefault(hkey(x, y), []).append((x, y))

    allvias = []
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            p = t.GetPosition()
            allvias.append((p.x / 1e6, p.y / 1e6))
            if t.GetNetname() == 'GND':
                add_pt(p.x / 1e6, p.y / 1e6)
    vh = {}
    for (x, y) in allvias:
        vh.setdefault((int(x // 1.0), int(y // 1.0)), []).append((x, y))

    def hole_ok(x, y):       # hole-to-hole 0.25 against every via (same net included)
        kx, ky = int(x // 1.0), int(y // 1.0)
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                for (px, py) in vh.get((kx + i, ky + j), ()):
                    if (px - x) ** 2 + (py - y) ** 2 < (VH + 0.25) ** 2:
                        return False
        return True

    def place(x, y):
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(pcbnew.VECTOR2I(int(round(x * 1e6)), int(round(y * 1e6))))
        v.SetWidth(int(VD * 1e6))
        v.SetDrill(int(VH * 1e6))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(gnd)
        b.Add(v)
        add_pt(x, y)
        vh.setdefault((int(x // 1.0), int(y // 1.0)), []).append((x, y))

    x0, y0, x1, y1 = B.outline.bounds
    added = 0
    ny = int((y1 - y0) / grid) + 1
    nx = int((x1 - x0) / grid) + 1
    for j in range(ny):
        y = y0 + j * grid
        xs = range(nx) if j % 2 == 0 else range(nx - 1, -1, -1)
        for i in xs:
            x = x0 + i * grid
            if near(x, y, dmin) or not hole_ok(x, y):
                continue
            if R.via_legal_exact('GND', Point(x, y), VD, VH, bans):
                place(x, y)
                added += 1
    # R21: every outer GND fill island needs >= 2 vias
    filler = pcbnew.ZONE_FILLER(b)
    filler.Fill(b.Zones())
    fixed = short = 0
    gv = [(t.GetPosition().x / 1e6, t.GetPosition().y / 1e6) for t in b.GetTracks()
          if t.GetClass() == 'PCB_VIA' and t.GetNetname() == 'GND']
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != 'GND':
            continue
        for lid in (pcbnew.F_Cu, pcbnew.B_Cu):
            if not z.IsOnLayer(lid):
                continue
            fp = mr.poly_of(z.GetFilledPolysList(lid))
            for isl in mr.polys_iter(fp):
                if isl.area < 0.5:
                    continue
                inside = [p for p in gv if isl.contains(Point(p))]
                need = 2 - len(inside)
                if need <= 0:
                    continue
                bx = isl.bounds
                cands = []
                yy = bx[1]
                while yy <= bx[3]:
                    xx = bx[0]
                    while xx <= bx[2]:
                        pt = Point(xx, yy)
                        if isl.buffer(-VD / 2).contains(pt):
                            cands.append((xx, yy))
                        xx += 0.1
                    yy += 0.1
                got = 0
                for (xx, yy) in cands:
                    if got >= need:
                        break
                    if near(xx, yy, 0.8) or not hole_ok(xx, yy):
                        continue
                    if R.via_legal_exact('GND', Point(xx, yy), VD, VH, bans):
                        place(xx, yy)
                        gv.append((xx, yy))
                        got += 1
                        added += 1
                if got >= need:
                    fixed += 1
                else:
                    short += 1
    filler.Fill(b.Zones())
    pcbnew.SaveBoard(dst, b)
    for ext in ('.kicad_pro', '.kicad_dru'):
        s = os.path.splitext(src)[0] + ext
        if os.path.isfile(s):
            shutil.copy2(s, os.path.splitext(dst)[0] + ext)
    print(f"restitch: {added} GND vias added (dmin {dmin} mm); outer-fill islands fixed {fixed}, still < 2 vias {short}")


if __name__ == '__main__':
    main()

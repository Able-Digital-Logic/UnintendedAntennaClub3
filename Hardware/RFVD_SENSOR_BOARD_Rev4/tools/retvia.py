"""retvia.py IN.kicad_pcb OUT.kicad_pcb | retvia.py --check BOARD.kicad_pcb  - EMC rulebook R17: every via of a fast net (HighSpeed_Digital,
HighSpeed_Clock) gets a GND via within 1.0 mm (centre to centre) so the return current changes reference plane right
beside the signal. GND vias are 0.45/0.20 POFV (no-surcharge minimum) and need no track (In1/In2/In4 are GND planes).
Sites: 8 octilinear directions x 0.60-1.00 mm; legality from mr.py's rule model (pairwise DRU clearances, 0.20 hole to
copper, 0.25 hole to hole, via-ban areas incl. lanes/AFE/bosses, edge 0.55). KiCad python, scratch copies only."""
import math
import os
import shutil
import sys

import pcbnew
from shapely.geometry import Point

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mr  # noqa: E402

FAST = ('HighSpeed_Digital', 'HighSpeed_Clock')
GATE = {'HighSpeed_Clock': 1.0, 'HighSpeed_Digital': 1.5}   # critique P1-2: R17 gate thresholds (mm, centre to centre)


def check_gate(path):
    """read-only R17 gate: every via of a fast net needs a GND via (or a GND through-hole pad) within GATE[class]."""
    b = pcbnew.LoadBoard(path)
    gnd = [(t.GetPosition().x / 1e6, t.GetPosition().y / 1e6) for t in b.GetTracks()
           if t.GetClass() == 'PCB_VIA' and t.GetNetname() == 'GND']
    gnd += [(p.GetPosition().x / 1e6, p.GetPosition().y / 1e6) for f in b.GetFootprints() for p in f.Pads()
            if p.GetNetname() == 'GND' and p.GetDrillSize().x > 0]
    bad, n = [], 0
    for t in b.GetTracks():
        if t.GetClass() != 'PCB_VIA':
            continue
        try:
            cls = t.GetNet().GetNetClassName()
        except Exception:
            cls = ''
        lim = next((v for k, v in GATE.items() if k in cls), None)
        if lim is None:
            continue
        n += 1
        x, y = t.GetPosition().x / 1e6, t.GetPosition().y / 1e6
        d = min((math.hypot(x - gx, y - gy) for gx, gy in gnd), default=99)
        if d > lim:
            bad.append((d, t.GetNetname(), cls, round(x, 3), round(y, 3), lim))
    bad.sort(reverse=True)
    print(f'R17 gate: {n} fast-net vias, {len(bad)} without a GND via within the limit '
          f'(clock {GATE["HighSpeed_Clock"]} mm, digital {GATE["HighSpeed_Digital"]} mm)')
    for d, net, cls, x, y, lim in bad[:60]:
        print(f'  {net.split("/")[-1]:24s} {cls:26s} ({x}, {y})  nearest GND {d:.2f} > {lim}')
    return len(bad)
VD, VH = 0.45, 0.2


def main():
    if sys.argv[1] == '--check':
        sys.exit(1 if check_gate(sys.argv[2]) else 0)
    src, dst = sys.argv[1], sys.argv[2]
    if os.path.normcase(os.path.realpath(dst)).startswith(mr.PROTECTED):
        sys.exit('refusing to write into the project folder')
    B = mr.Board(src)
    b = B.b
    gnd_net = b.FindNet('GND')
    bans = B.bans('GND')
    inner = B.outline.buffer(-(0.55 + VD / 2))

    def legal(v):
        if not inner.contains(v):
            return False
        vg = v.buffer(VD / 2, 24)
        for item in bans:
            if item[0] == 'VIAHOLE':
                _, pt, rr = item
                if pt.distance(v) < rr + VD / 2:
                    return False
            elif item[3] and item[0].intersects(vg):
                return False
        ex = frozenset(k for k, e in B.exempt_geo.items() if not e.is_empty and e.intersects(vg))
        for ln in mr.SIG:
            for i in B.trees[ln].query(v.buffer(2.6)):
                g, n2, kind = B.items[ln][i]
                if n2 == 'GND':
                    if kind == 'via' and g.distance(v) < 0.0:
                        return False
                    continue
                d = g.distance(v)
                if d < VD / 2 + mr.need('GND', n2, kind, ex) or d < VH / 2 + 0.2:
                    return False
        for i in B.htree.query(v.buffer(1.5)):
            hp, hr, hn = B.holes[i]
            if hp.distance(v) < hr + VH / 2 + 0.25:
                return False
        return True

    gvias = [Point(t.GetPosition().x / 1e6, t.GetPosition().y / 1e6) for t in b.GetTracks()
             if t.GetClass() == 'PCB_VIA' and t.GetNetname() == 'GND']
    sig = [t for t in b.GetTracks() if t.GetClass() == 'PCB_VIA' and mr.cls(t.GetNetname()) in FAST]
    added = missing = 0
    miss = []
    for sv in sig:
        c = Point(sv.GetPosition().x / 1e6, sv.GetPosition().y / 1e6)
        if any(c.distance(g) <= 1.0 for g in gvias):
            continue
        ok = None
        for d in (0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0):
            for a in range(0, 360, 45):
                v = Point(c.x + d * math.cos(math.radians(a)), c.y + d * math.sin(math.radians(a)))
                if legal(v):
                    ok = v
                    break
            if ok:
                break
        if ok is None:
            missing += 1
            miss.append(f"{sv.GetNetname()}@({c.x:.2f},{c.y:.2f})")
            continue
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(pcbnew.VECTOR2I(int(round(ok.x * 1e6)), int(round(ok.y * 1e6))))
        v.SetWidth(int(VD * 1e6)); v.SetDrill(int(VH * 1e6))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(gnd_net)
        b.Add(v)
        B.add_item(v)
        B.rebuild()
        gvias.append(ok)
        added += 1
    pcbnew.SaveBoard(dst, b)
    for ext in ('.kicad_pro', '.kicad_dru'):
        s = os.path.splitext(src)[0] + ext
        if os.path.isfile(s):
            shutil.copy2(s, os.path.splitext(dst)[0] + ext)
    print(f"R17 return vias: {len(sig)} fast-net vias, {added} GND vias added, {missing} without a legal site")
    for m in miss[:30]:
        print('   no site:', m)


if __name__ == '__main__':
    main()

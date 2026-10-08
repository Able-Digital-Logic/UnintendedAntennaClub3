"""chg_copper.py IN.kicad_pcb OUT.kicad_pcb
Hand-designed BQ25798 (U301) power copper, TI SLUSDV2C rev C 8.4 adapted to this board (U301 rotated 90 deg: the power
pins VSYS 25 / SW2 26 / GND 27 / SW1 28 / PMID 29 face left; L301 sits 1.2 mm to their left; K5_L301_BODY bans pours
(not tracks/vias) over the inductor; corner pins 1 STAT and 24 SDRV are L-shaped pads covering the column corners).
  SW2  pin 26 -> 0.25 neck (inside the U301 courtyard: v3_w_chg_sw_neck) -> 0.5 mm 45-degree leg into L301 pad 2
  SW1  pin 28 -> same, mirrored, into L301 pad 1
  VSYS pin 25 -> 0.2 neck (w_power_neckdown_in_ic) -> 0.5 mm leg up past the SDRV corner -> C313.1, C318.1, C317.1
  PMID pin 29 -> 0.2 neck, 45 deg -> 0.5 mm leg down past the STAT corner -> C306.1, C309.1
  CHG_BAT pins 22/23 -> F pour above the top row -> C319.1, C320.1
  BTST caps: C310 / C311 on B.Cu under the L301 pads, SW side joined by ONE via in both pads (via-in-pad, POFV; allowed
  by v3_allow_chg_boot_vias inside the C310/C311 courtyards)
Every track and via is checked against the board's pairwise rule model (mr.py: DRU clearances with courtyard exemptions)
before it is added; a violation is printed and the item is skipped. KiCad python, scratch copies only."""
import os
import shutil
import sys

import pcbnew
from shapely.geometry import LineString, Point

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import mr  # noqa: E402

src, dst = sys.argv[1], sys.argv[2]
B = mr.Board(src, ('*',))
b = B.b
R = mr.Router(B)
SW1, SW2, PMID = 'Net-(U301-SW1)', 'Net-(U301-SW2)', 'Net-(U301-PMID)'
VSYS, BAT = 'VSYS', '/Battery, charger and USB-C/CHG_BAT'
F = 'F.Cu'
TRACKS = [
    # (net, layer, width, [points])
    (SW2, F, 0.25, [(142.70, 111.493), (141.75, 111.493)]),
    (SW2, F, 0.50, [(141.75, 111.493), (141.45, 111.193)]),
    (SW1, F, 0.25, [(142.70, 112.393), (141.75, 112.393)]),
    (SW1, F, 0.50, [(141.75, 112.393), (141.45, 112.693)]),
    (VSYS, F, 0.20, [(142.70, 111.043), (142.10, 111.043)]),
    (VSYS, F, 0.50, [(142.10, 110.80), (142.10, 109.20)]),
    (VSYS, F, 0.50, [(142.10, 108.40), (143.20, 108.40)]),
    (VSYS, F, 0.50, [(142.10, 109.55), (139.20, 109.55), (138.90, 109.25)]),
    (PMID, F, 0.20, [(142.70, 112.843), (142.40, 112.843), (142.10, 113.143)]),
    (PMID, F, 0.50, [(142.10, 113.143), (142.10, 114.80), (142.90, 114.80)]),
]
VIAS = [
    # (net, x, y, d, drill) - stacked via-in-pad: L301 pad (F) + C310/C311 pad (B)
    (SW1, 140.72, 113.30, 0.45, 0.2),
    (SW2, 140.42, 110.76, 0.45, 0.2),
]
ZONES = [
    (BAT, 11, [(143.48, 108.15), (148.40, 108.15), (148.40, 109.50), (144.12, 109.50), (144.12, 109.95), (143.48, 109.95)]),
]


def seg_ok(net, ln, a, c, w):
    line = LineString([a, c])
    sg = line.buffer(w / 2, 8)
    ex = frozenset(k for k, e in B.exempt_geo.items() if not e.is_empty and e.intersects(sg))
    bad = []
    for i in B.trees[ln].query(sg.buffer(2.1)):
        geo, n2, kind = B.items[ln][i]
        if n2 == net:
            continue
        d = geo.distance(line) - w / 2
        need = mr.need(net, n2, kind, ex)
        if d < need - 1e-4:
            bad.append(f"{n2.split('/')[-1]}({kind}) gap {d:.3f} < {need}")
    for item in B.bans(net):
        if item[0] != 'VIAHOLE' and item[2] and ln in item[1] and item[0].intersects(sg):
            bad.append('rule-area ban')
    return bad


ok = 0
for net, ln, w, pts in TRACKS:
    for a, c in zip(pts, pts[1:]):
        bad = seg_ok(net, ln, a, c, w)
        if bad:
            print(f"  REJECT {net.split('/')[-1]} {a}->{c} w{w}: {'; '.join(bad[:4])}")
            continue
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(int(round(a[0] * 1e6)), int(round(a[1] * 1e6))))
        t.SetEnd(pcbnew.VECTOR2I(int(round(c[0] * 1e6)), int(round(c[1] * 1e6))))
        t.SetWidth(int(round(w * 1e6)))
        t.SetLayer(B.L[ln])
        t.SetNet(b.FindNet(net))
        b.Add(t)
        B.add_item(t)
        B.rebuild()
        ok += 1
for net, x, y, d, h in VIAS:
    if not R.via_legal_exact(net, Point(x, y), d, h, B.bans(net)):
        print(f"  REJECT via {net} at ({x},{y})")
        continue
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I(int(round(x * 1e6)), int(round(y * 1e6))))
    v.SetWidth(int(d * 1e6))
    v.SetDrill(int(h * 1e6))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(b.FindNet(net))
    b.Add(v)
    B.add_item(v)
    B.rebuild()
    ok += 1
for net, prio, pts in ZONES:
    z = pcbnew.ZONE(b)
    z.SetLayer(pcbnew.F_Cu)
    z.SetNet(b.FindNet(net))
    z.SetAssignedPriority(prio)
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetMinThickness(int(0.2e6))
    z.SetLocalClearance(int(0.2e6))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetZoneName('CHG_' + net.split('/')[-1])
    o = z.Outline()
    o.NewOutline()
    for x, y in pts:
        o.Append(int(round(x * 1e6)), int(round(y * 1e6)))
    b.Add(z)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(dst, b)
for ext in ('.kicad_pro', '.kicad_dru'):
    s = os.path.splitext(src)[0] + ext
    if os.path.isfile(s):
        shutil.copy2(s, os.path.splitext(dst)[0] + ext)
print(f"chg_copper: {ok} items added -> {dst}")

"""straddle.py IN OUT REF NET:PIN+PIN:VD/VH ... : one via-in-pad straddling two adjacent same-net pins (POFV), after
removing GND ring vias/stubs that gndvip.py attached to those pins. Legality checked with mr.py's rule model."""
import sys, shutil, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import pcbnew
import mr
from shapely.geometry import Point
src, dst, ref = sys.argv[1], sys.argv[2], sys.argv[3]
b = pcbnew.LoadBoard(src)
fp = b.FindFootprintByReference(ref)
pads = {p.GetNumber(): p for p in fp.Pads()}
specs = []
for s in sys.argv[4:]:
    net, pp, sz = s.split(':')
    a, c = pp.split('+')
    vd, vh = (float(v) for v in sz.split('/'))
    specs.append((net, a, c, vd, vh))
    # drop stubs/vias of this net that touch the two pads (ring vias from gndvip)
    kill = {}
    tracks = list(b.GetTracks())
    vias_at = {}
    for v in tracks:
        if v.GetClass() == 'PCB_VIA':
            vias_at.setdefault((v.GetPosition().x, v.GetPosition().y, v.GetNetname()), []).append(v)
    for num in (a, c):
        g = mr.poly_of(pads[num].GetEffectivePolygon(pcbnew.F_Cu, pcbnew.ERROR_OUTSIDE)).buffer(0.01)
        inside = lambda q: g.contains(Point(q.x / 1e6, q.y / 1e6))
        for t in tracks:
            if t.GetClass() == 'PCB_VIA' or t.GetNetname() != pads[num].GetNetname():
                continue
            st, en = t.GetStart(), t.GetEnd()
            if inside(st) or inside(en):
                far = en if inside(st) else st
                kill[t.m_Uuid.AsString()] = t
                for v in vias_at.get((far.x, far.y, t.GetNetname()), []):
                    kill[v.m_Uuid.AsString()] = v
                    print('  removed ring via', far.x / 1e6, far.y / 1e6)
    for t in kill.values():
        b.Remove(t)
tmp = dst + '.tmp.kicad_pcb'
pcbnew.SaveBoard(tmp, b)
B = mr.Board(tmp, ('*',))
R = mr.Router(B)
b = B.b
fp = b.FindFootprintByReference(ref)
pads = {p.GetNumber(): p for p in fp.Pads()}
for net, a, c, vd, vh in specs:
    pa, pc = pads[a].GetPosition(), pads[c].GetPosition()
    x, y = (pa.x + pc.x) / 2e6, (pa.y + pc.y) / 2e6
    netname = pads[a].GetNetname()
    ok = R.via_legal_exact(netname, Point(x, y), vd, vh, B.bans(netname))
    print(f"  {netname} straddle via {a}+{c} at ({x:.3f},{y:.3f}) {vd}/{vh}: {'legal' if ok else 'ILLEGAL'}")
    if ok:
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(pcbnew.VECTOR2I(int(round(x * 1e6)), int(round(y * 1e6))))
        v.SetWidth(int(vd * 1e6)); v.SetDrill(int(vh * 1e6))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(b.FindNet(netname))
        b.Add(v); B.add_item(v); B.rebuild()
pcbnew.SaveBoard(dst, b)
os.remove(tmp)
for ext in ('.kicad_pro', '.kicad_dru'):
    s_ = os.path.splitext(src)[0] + ext
    if os.path.isfile(s_):
        shutil.copy2(s_, os.path.splitext(dst)[0] + ext)

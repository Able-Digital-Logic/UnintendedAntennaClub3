"""corridor_rip.py IN OUT x0,y0,x1,y1 [--keep PAT,PAT] [--layers In3.Cu] [--report R.json]
Clears a routing corridor for a priority bus (net ordering, 2026-10-02): every track on --layers (default In3.Cu)
that touches the box is removed, unless its net matches a --keep pattern (the priority bus itself), is GND, or belongs
to a protected class (switch nodes, battery power, RF, precision analog, references, clocks). Vias left with no track
on any layer and outside every pad are removed too; vias that still carry F/B copper stay (they become the
re-route start points). Writes the list of affected nets (re-route them AFTER the bus). Scratch copies only."""
import fnmatch
import json
import os
import shutil
import sys

import pcbnew
from shapely.geometry import LineString, Point, box

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import mr  # noqa: E402

argv = sys.argv[1:]


def opt(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


src, dst = argv[0], argv[1]
bx = box(*[float(v) for v in argv[2].split(',')])
keep = [p for p in (opt('--keep') or '').split(',') if p]
layers = (opt('--layers') or 'In3.Cu').split(',')
PROT = ('Power_Buck_SW', 'Power_Battery', 'RF_Input', 'RF_50R', 'Analog_Precision', 'Ref_Kelvin', 'HighSpeed_Clock')
b = pcbnew.LoadBoard(src)
lids = {b.GetLayerID(l) for l in layers}


def kept(n):
    if not n or n == 'GND' or mr.cls(n) in PROT:
        return True
    return any(fnmatch.fnmatchcase(n, p) or fnmatch.fnmatchcase(n.split('/')[-1], p) for p in keep)


tracks = list(b.GetTracks())
kill = {}
for t in tracks:
    if t.GetClass() == 'PCB_VIA' or t.GetLayer() not in lids or kept(t.GetNetname()):
        continue
    g = LineString([(t.GetStart().x / 1e6, t.GetStart().y / 1e6), (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)])
    if g.intersects(bx):
        kill[t.m_Uuid.AsString()] = t
nets = sorted(set(t.GetNetname() for t in kill.values()))
# vias that no longer touch any remaining track and sit in no pad
pads = [(p, p.GetNetname()) for f in b.GetFootprints() for p in f.Pads()]
for v in tracks:
    if v.GetClass() != 'PCB_VIA' or v.GetNetname() not in nets:
        continue
    c = v.GetPosition()
    r = v.GetWidth(pcbnew.F_Cu) / 2e6
    held = False
    for t in tracks:
        if t.GetClass() == 'PCB_VIA' or t.m_Uuid.AsString() in kill or t.GetNetname() != v.GetNetname():
            continue
        for e in (t.GetStart(), t.GetEnd()):
            if ((e.x - c.x) ** 2 + (e.y - c.y) ** 2) ** 0.5 / 1e6 <= r + 1e-3:
                held = True
                break
        if held:
            break
    if not held:
        pt = Point(c.x / 1e6, c.y / 1e6)
        for p, pn in pads:
            if pn == v.GetNetname():
                lid = pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
                if mr.poly_of(p.GetEffectivePolygon(lid, pcbnew.ERROR_OUTSIDE)).contains(pt):
                    held = True
                    break
    if not held:
        kill[v.m_Uuid.AsString()] = v
for t in kill.values():
    b.Remove(t)
pcbnew.SaveBoard(dst, b)
for ext in ('.kicad_pro', '.kicad_dru'):
    s_ = os.path.splitext(src)[0] + ext
    if os.path.isfile(s_):
        shutil.copy2(s_, os.path.splitext(dst)[0] + ext)
if opt('--report'):
    json.dump(nets, open(opt('--report'), 'w'), indent=1)
print(f"corridor_rip: removed {len(kill)} items of {len(nets)} nets: {[n.split('/')[-1] for n in nets]}")

"""applyposes.py IN.kicad_pcb OUT.kicad_pcb POSES.json [POSES.json ...]
Set footprint poses on a board (the one tool for this since 2026-10-02; replaces setpos.py, applymoves.py, flip.py).
POSES.json is either a placefit result ({"poses": {REF: [x, y, rot]}}) or a move list ({REF: {"x", "y", "rot",
"side": "F"|"B"}}); a side change flips the part first. Copper is NOT touched: run place/prerip.py first for parts
whose old tracks must go. Refuses when a moved courtyard overlaps another courtyard (0.02 mm). KiCad python, scratch
copies only."""
import json
import os
import shutil
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mr  # noqa: E402

src, dst = sys.argv[1], sys.argv[2]
if os.path.normcase(os.path.realpath(dst)).startswith(mr.PROTECTED):
    sys.exit('refusing to write into the project folder')
b = pcbnew.LoadBoard(src)
poses = {}
for p in sys.argv[3:]:
    j = json.load(open(p))
    if 'poses' in j:
        poses.update({r: (v[0], v[1], v[2], None) for r, v in j['poses'].items()})
    else:
        poses.update({r: (v['x'], v['y'], v.get('rot', 0), v.get('side')) for r, v in j.items() if isinstance(v, dict)})
for r, (x, y, rot, side) in poses.items():
    fp = b.FindFootprintByReference(r)
    if fp is None:
        sys.exit(f'no footprint {r}')
    if side and side != ('B' if fp.IsFlipped() else 'F'):
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetPosition(pcbnew.VECTOR2I(int(round(x * 1e6)), int(round(y * 1e6))))
    fp.SetOrientationDegrees(rot)
    print(f"  {r} -> ({x:.3f},{y:.3f}) rot {rot:.0f}{' side ' + side if side else ''}")
bad = []
moved = set(poses)
cs = {}
for f in b.GetFootprints():
    if hasattr(f, 'BuildCourtyardCaches'):
        f.BuildCourtyardCaches()
    s_ = 'B' if f.IsFlipped() else 'F'
    cs[f.GetReference()] = (s_, mr.poly_of(f.GetCourtyard(pcbnew.B_CrtYd if s_ == 'B' else pcbnew.F_CrtYd)))
for r in moved:
    s_, g = cs[r]
    for r2, (s2, g2) in cs.items():
        if r2 != r and s2 == s_ and not g.is_empty and not g2.is_empty and g.buffer(0.02).intersects(g2) and \
                g.buffer(0.02).intersection(g2).area > 1e-4:
            bad.append((r, r2))
if bad:
    sys.exit(f'courtyard overlaps after applying poses: {bad}')
pcbnew.SaveBoard(dst, b)
for ext in ('.kicad_pro', '.kicad_dru'):
    a = os.path.splitext(src)[0] + ext
    if os.path.isfile(a):
        shutil.copy2(a, os.path.splitext(dst)[0] + ext)
print(f"applyposes: {len(poses)} poses -> {dst}")

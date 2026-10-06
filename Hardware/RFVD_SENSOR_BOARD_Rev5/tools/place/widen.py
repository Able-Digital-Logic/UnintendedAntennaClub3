"""widen.py IN OUT NET=WIDTH [NET=WIDTH ...] [--min W]
Widens the existing tracks of the nets in place (keeps the topology and connectivity): every segment narrower than
WIDTH is set to WIDTH when the wider copper still clears every other net with mr.py's exact pairwise rule model
(courtyard exemptions at the segment); otherwise the widest legal value >= --min (default: the current width) in
0.01 mm steps is used, and the segment is reported. KiCad python, scratch copies only."""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import mr  # noqa: E402
import pcbnew  # noqa: E402
from shapely.geometry import LineString  # noqa: E402

argv = sys.argv[1:]
src, dst = argv[0], argv[1]
want = {}
for a in argv[2:]:
    if '=' in a:
        n, w = a.split('=')
        want[n] = float(w)
B = mr.Board(src, ('*',))
b = B.b
done = part = 0
short = []
for t in list(b.GetTracks()):
    if t.GetClass() == 'PCB_VIA':
        continue
    n = t.GetNetname()
    key = n if n in want else n.split('/')[-1] if n.split('/')[-1] in want else None
    if key is None:
        continue
    w_target = want[key]
    w0 = t.GetWidth() / 1e6
    if w0 >= w_target - 1e-6:
        continue
    ln = b.GetLayerName(t.GetLayer())
    line = LineString([(t.GetStart().x / 1e6, t.GetStart().y / 1e6), (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)])
    best = None
    w = w_target
    while w >= w0 - 1e-9:
        g = line.buffer(w / 2, 8)
        ex = frozenset(k for k, e in B.pexempt.items() if e.intersects(g))
        ok = True
        for i in B.trees[ln].query(g.buffer(2.1)):
            geo, n2, kind = B.items[ln][i]
            if n2 == n:
                continue
            if geo.distance(g) < mr.need(n, n2, kind, ex) + 0.005:
                ok = False
                break
        if ok:
            best = w
            break
        w = round(w - 0.01, 3)
    if best is not None and best > w0 + 1e-9:
        t.SetWidth(int(round(best * 1e6)))
        if best >= w_target - 1e-6:
            done += 1
        else:
            part += 1
            short.append((n.split('/')[-1], ln, round(best, 3), [round(c, 2) for c in line.coords[0]]))
    elif best is None or best <= w0 + 1e-9:
        short.append((n.split('/')[-1], ln, w0, [round(c, 2) for c in line.coords[0]]))
pcbnew.SaveBoard(dst, b)
for ext in ('.kicad_pro', '.kicad_dru'):
    s_ = os.path.splitext(src)[0] + ext
    if os.path.isfile(s_):
        shutil.copy2(s_, os.path.splitext(dst)[0] + ext)
print(f"widen: {done} segments at full width, {part} partially widened, {len(short)} still narrow")
for s in short[:40]:
    print('   narrow:', s)

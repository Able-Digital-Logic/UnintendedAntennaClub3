"""openregion.py BOARD OPEN.json [--ycut 92]: classify missing connections by where their islands sit."""
import sys, json, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); op = json.load(open(sys.argv[2]))
ycut = float(sys.argv[sys.argv.index('--ycut') + 1]) if '--ycut' in sys.argv else 92.0
pos = {}
for f in b.GetFootprints():
    for p in f.Pads():
        pos[f"{f.GetReference()}.{p.GetNumber()}"] = p.GetPosition().y / 1e6
cnt = {'upper': 0, 'lower': 0, 'cross': 0}
up = []
for net, v in op.items():
    if net == 'GND':
        continue
    sides = []
    for isl in v['parts']:
        ys = [pos.get(n) for n in isl if n in pos]
        sides.append('U' if ys and max(ys) < ycut else ('L' if ys and min(ys) >= ycut else 'X'))
    m = v['missing']
    if all(s == 'U' for s in sides):
        cnt['upper'] += m; up.append((net, m))
    elif all(s == 'L' for s in sides):
        cnt['lower'] += m
    else:
        cnt['cross'] += m
print(cnt)
print('upper-only nets:', sorted(up, key=lambda x: -x[1])[:40])

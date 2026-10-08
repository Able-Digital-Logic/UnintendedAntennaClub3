"""drcnear.py BOARD.kicad_pcb [x0,y0,x1,y1] [--base BASE_DRC.json]
KiCad DRC (project rules, zones refilled) on a scratch copy, printed for one area: every error / warning with an item
inside the box, plus the unconnected items there. With --base, only violations that are not in the base report are
shown (new ones). Without a box: totals only. Writes BOARD_drcnear.json. Read-only for the board."""
import collections
import json
import os
import re
import subprocess
import sys

KCLI = r'C:/Program Files/KiCad/10.0/bin/kicad-cli.exe'
argv = sys.argv[1:]
board = os.path.abspath(argv[0])
box = None
if len(argv) > 1 and not argv[1].startswith('--'):
    box = tuple(float(v) for v in argv[1].split(','))
base = argv[argv.index('--base') + 1] if '--base' in argv else None
out = os.path.splitext(board)[0] + '_drcnear.json'
r = subprocess.run([KCLI, 'pcb', 'drc', '--all-track-errors', '--severity-all', '--refill-zones', '--format', 'json', '-o', out, board],
                   capture_output=True, text=True)
rep = json.load(open(out, encoding='utf-8'))


def key(v):
    return (v['type'], tuple(re.sub(r'length [0-9.]+ mm', '', i.get('description', '')) for i in v.get('items', [])))


seen = collections.Counter()
if base and os.path.isfile(base):
    seen = collections.Counter(key(v) for v in json.load(open(base, encoding='utf-8'))['violations'])


def inside(v):
    if box is None:
        return True
    x0, y0, x1, y1 = box
    return any(x0 <= i['pos']['x'] <= x1 and y0 <= i['pos']['y'] <= y1 for i in v.get('items', []))


viol = rep['violations']
sev = collections.Counter(v['severity'] for v in viol)
print(f"DRC: {sev.get('error', 0)} errors, {sev.get('warning', 0)} warnings, {len(rep.get('unconnected_items', []))} unconnected")
shown = 0
for v in viol:
    k = key(v)
    if seen[k] > 0:
        seen[k] -= 1
        continue
    if not inside(v) or (box is None and not base):
        continue
    m = re.search(r"rule '([^']+)'", v.get('description', ''))
    print(f"  {v['severity'][:4]} {v['type']:20s} {(m.group(1) if m else '-'):26s} " +
          ' | '.join(f"{i.get('description', '')[:55]} @({i['pos']['x']:.2f},{i['pos']['y']:.2f})" for i in v.get('items', [])))
    shown += 1
if box:
    for u in rep.get('unconnected_items', []):
        items = u.get('items', [])
        if any(box[0] <= i['pos']['x'] <= box[2] and box[1] <= i['pos']['y'] <= box[3] for i in items):
            print('  open ' + ' | '.join(f"{i.get('description', '')[:50]} @({i['pos']['x']:.2f},{i['pos']['y']:.2f})" for i in items))
print(f"drcnear: {shown} violation(s) shown{' (new vs base)' if base else ''}")

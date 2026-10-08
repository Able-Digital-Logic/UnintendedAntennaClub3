"""drcsum.py BOARD.kicad_pcb OUTDIR [BASE_DRC.json]: sign-off DRC (all rules) on a scratch copy + summary vs a base report."""
import collections, json, os, subprocess, sys
PY = r"C:/Program Files/KiCad/10.0/bin/python.exe"
SIGNOFF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "drc_signoff.py")
board, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
os.makedirs(out, exist_ok=True)
bd = os.path.dirname(board)
stem = os.path.splitext(os.path.basename(board))[0]
# drc_signoff wants a folder with exactly one .kicad_pro: stage a clean folder
stage = os.path.join(out, 'stage')
os.makedirs(stage, exist_ok=True)
for f in os.listdir(stage):
    if os.path.isfile(os.path.join(stage, f)):
        os.remove(os.path.join(stage, f))
import shutil
for ext in ('.kicad_pcb', '.kicad_pro', '.kicad_dru'):
    shutil.copy2(os.path.join(bd, stem + ext), os.path.join(stage, 'B' + ext))
# the project footprint library: from the board's folder, else from the handoff project next to this tool (2026-10-04)
for src in (bd, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')):
    if os.path.isfile(os.path.join(src, 'fp-lib-table')) and os.path.isdir(os.path.join(src, 'libraries')):
        shutil.copy2(os.path.join(src, 'fp-lib-table'), stage)
        if not os.path.isdir(os.path.join(stage, 'libraries')):
            shutil.copytree(os.path.join(src, 'libraries'), os.path.join(stage, 'libraries'),
                            ignore=shutil.ignore_patterns('3dmodels'))
        break
if len(os.path.abspath(stage)) > 120:
    print(f'note: long stage path ({len(os.path.abspath(stage))} chars): KiCad may not open the project footprint '
          'library (Windows MAX_PATH) and then reports false lib_footprint_issues')
r = subprocess.run([PY, SIGNOFF, '--board-dir', stage, '--out', os.path.join(out, 'so')], capture_output=True, text=True)
print('\n'.join(l for l in r.stdout.splitlines() if 'DRC' in l or 'SIGN' in l))
rep = json.load(open(os.path.join(out, 'so', 'drc_signoff.json'), encoding='utf-8'))
def rule_of(v):
    import re
    m = re.search(r"rule '([^']+)'", v.get('description', ''))
    return m.group(1) if m else '-'
def key(v):
    return (v['severity'], v['type'], rule_of(v))
cur = collections.Counter(key(v) for v in rep['violations'] if 'sentinel' not in v.get('description', ''))
base = None
if len(sys.argv) > 3 and os.path.isfile(sys.argv[3]):
    b = json.load(open(sys.argv[3], encoding='utf-8'))
    base = collections.Counter(key(v) for v in b['violations'] if 'sentinel' not in v.get('description', ''))
print(f"errors {sum(n for k, n in cur.items() if k[0] == 'error')} | warnings {sum(n for k, n in cur.items() if k[0] == 'warning')} | unconnected {len(rep.get('unconnected_items', []))}")
for k, n in sorted(cur.items(), key=lambda kv: (kv[0][0] != 'error', -kv[1])):
    d = n - (base.get(k, 0) if base else 0)
    if k[0] == 'error' or abs(d) > 0:
        print(f"  {k[0]:8} {n:4} ({'+' if d >= 0 else ''}{d}) {k[1]:28} {k[2]}")
bytype = collections.Counter(v['type'] for v in rep['violations'] if 'sentinel' not in v.get('description', ''))
for t, n in sorted(bytype.items()):
    if n >= 199:  # kicad-cli reports at most 199 violations per type (RULES-05)
        print(f"  TRUNCATED: {t} hit KiCad's 199-per-type report cap; the real count is unknown")
json.dump(rep, open(os.path.join(out, 'drc.json'), 'w'), indent=0)

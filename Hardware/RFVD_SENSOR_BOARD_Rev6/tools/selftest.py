"""selftest.py BOARD.kicad_pcb [--drc]
Smoke test of the active toolset before it is trusted with a board (user rule 2026-10-02: check tools before use).
Runs on a scratch copy next to the board (BOARD_selftest.*), never on the board itself:
  1. every tool compiles;
  2. query.py part / net / near / zones / edge / free answer;
  3. metrics.py of the board against itself shows no difference;
  4. placeaudit.py (--only on a few parts) writes its CSV / summary;
  5. place/stretch.py --dry-run plans the outline change;
  6. place/prerip.py on one 2-pin part changes ONLY that part's nets (metrics check);
  7. (--drc) drcsum.py runs.
Prints PASS / FAIL per step and exits non-zero on any failure. KiCad python."""
import glob
import os
import py_compile
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
board = os.path.abspath(sys.argv[1])
stem = os.path.splitext(board)[0]
work = stem + '_selftest.kicad_pcb'
for ext in ('.kicad_pcb', '.kicad_pro', '.kicad_dru'):
    if os.path.isfile(stem + ext):
        shutil.copy2(stem + ext, os.path.splitext(work)[0] + ext)
env = dict(os.environ, PYTHONIOENCODING='utf-8')
fails = []


def run(name, args, must=(), timeout=900):
    r = subprocess.run([PY] + args, capture_output=True, text=True, env=env, timeout=timeout)
    out = r.stdout + r.stderr
    ok = r.returncode == 0 and all(m in out for m in must)
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok:
        fails.append(name)
        print('      ' + '\n      '.join([l for l in out.splitlines() if 'memory leak' not in l and 'image handler' not in l][-12:]))
    return out


# 1. compile
bad = []
for p in glob.glob(os.path.join(HERE, '*.py')) + glob.glob(os.path.join(HERE, 'place', '*.py')):
    try:
        py_compile.compile(p, doraise=True)
    except Exception as e:
        bad.append(f'{os.path.basename(p)}: {e}')
print(f"{'PASS' if not bad else 'FAIL'}  compile {len(glob.glob(os.path.join(HERE, '*.py')) + glob.glob(os.path.join(HERE, 'place', '*.py')))} tools")
if bad:
    fails.append('compile')
    print('      ' + '\n      '.join(bad))
Q = os.path.join(HERE, 'query.py')
# 2. query
import pcbnew  # noqa: E402
b = pcbnew.LoadBoard(work)
two = next(f for f in b.GetFootprints() if len(list(f.Pads())) == 2 and all(p.GetNetname() and p.GetNetname() != 'GND' for p in f.Pads())
           and not f.IsDNP())
ref = two.GetReference()
net = next(iter(two.Pads())).GetNetname().split('/')[-1]
x, y = two.GetPosition().x / 1e6, two.GetPosition().y / 1e6
side = 'B' if two.IsFlipped() else 'F'
del b
run('query part', [Q, 'part', work, ref], must=(ref,))
run('query net', [Q, 'net', work, net], must=('pad ' + ref,))
run('query near', [Q, 'near', work, f'{net}@{x},{y}'], must=('mm',))
run('query zones', [Q, 'zones', work], must=('layers',))
run('query edge', [Q, 'edge', work, '--within', '1'], must=('outline x',))
run('query free', [Q, 'free', work, ref, side, f'{x - 3},{y - 3},{x + 3},{y + 3}', f'{x},{y}'], must=('spots shown',))
# 3. metrics self-diff
out = run('metrics self', [os.path.join(HERE, 'place', 'metrics.py'), work, work], must=('worse {}',))
# 4. placeaudit
pre = os.path.splitext(work)[0] + '_audit'
run('placeaudit', [os.path.join(HERE, 'placeaudit.py'), work, '--out', pre, '--only', ref], must=('placeaudit:',))
if not (os.path.isfile(pre + '_connections.csv') and os.path.isfile(pre + '_summary.md')):
    fails.append('placeaudit outputs')
    print('FAIL  placeaudit outputs missing')
# 4b. dsgap (live datasheet gaps)
run('dsgap selftest', [os.path.join(HERE, 'dsgap.py'), '--selftest'], must=('dsgap selftest OK',))
run('dsgap board', [os.path.join(HERE, 'dsgap.py'), work, '--warn', '--out', os.path.splitext(work)[0] + '_dsgap.md'], must=('parts measured',))
# 5. stretch dry run
run('stretch dry-run', [os.path.join(HERE, 'place', 'stretch.py'), work, work + '.x.kicad_pcb', '--left', '1', '--right', '1', '--dry-run'], must=('outline x',))
# 6. prerip touches only the part's nets
pr = os.path.splitext(work)[0] + '_prerip.kicad_pcb'
run('prerip', [os.path.join(HERE, 'place', 'prerip.py'), work, pr, ref], must=('prerip ->',))
out = run('prerip metrics', [os.path.join(HERE, 'place', 'metrics.py'), work, pr])
worse = out.split('worse', 1)[-1].split('\n')[0] if 'worse' in out else ''
nets_part = set(p.GetNetname() for p in pcbnew.LoadBoard(work).FindFootprintByReference(ref).Pads())
import ast  # noqa: E402
try:
    w = ast.literal_eval(worse.strip())
    extra = [n for n in w if n not in nets_part]
except Exception:
    extra = ['(could not parse)']
print(f"{'PASS' if not extra else 'FAIL'}  prerip changed only {ref}'s nets" + (f' (also {extra})' if extra else ''))
if extra:
    fails.append('prerip scope')
# 7. drc
if '--drc' in sys.argv:
    run('drcsum', [os.path.join(HERE, 'drcsum.py'), work, os.path.splitext(work)[0] + '_drc'], must=('full DRC',))
for f in glob.glob(os.path.splitext(work)[0] + '*'):
    try:
        os.remove(f) if os.path.isfile(f) else None
    except OSError:
        pass
print('selftest:', 'ALL PASS' if not fails else f'{len(fails)} FAILED: {fails}')
sys.exit(1 if fails else 0)

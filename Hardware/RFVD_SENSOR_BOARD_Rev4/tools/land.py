"""land.py SRC_PROJECT_DIR MASTER_DIR --expect-sha SHA10 --tag TAG [--dry-run]   (2026-10-04)
Lands a verified scratch result (e.g. a tools/replay.py OUT_DIR) on the master project folder:
  1. refuses unless the master board's sha256 starts with SHA10 (nobody changed it since the batch was verified)
     and no KiCad lock file (~*.lck) is present;
  2. backs up every master file it will overwrite to MASTER/backups/before_TAG/ (same relative paths);
  3. copies ONLY project files that differ: *.kicad_sch referenced from the root, .kicad_pcb/.kicad_pro/.kicad_dru,
     fp-lib-table / sym-lib-table, and libraries/** (symbols, footprints, 3D models);
  4. re-hashes every copied file and prints old -> new hashes. Never deletes master files.
The files it copies were written by Konnect (schematics, libraries, project) and by pen.py/sync.py (board) on the
scratch copy; nothing is hand-edited. Plain python."""
import hashlib
import os
import re
import shutil
import sys

argv = sys.argv[1:]
src, dst = os.path.abspath(argv[0]), os.path.abspath(argv[1])
sha = argv[argv.index('--expect-sha') + 1]
tag = argv[argv.index('--tag') + 1]
dry = '--dry-run' in argv
STEM = 'RFVD_SENSOR_BOARD'


def h(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


mb = os.path.join(dst, STEM + '.kicad_pcb')
if not h(mb).startswith(sha):
    sys.exit(f'REFUSED: master board sha {h(mb)[:10]} != expected {sha}')
locks = [f for f in os.listdir(dst) if f.endswith('.lck') or f.startswith('~')]
if locks:
    sys.exit(f'REFUSED: KiCad lock files present (close KiCad first): {locks}')
files = [STEM + e for e in ('.kicad_pcb', '.kicad_pro', '.kicad_dru')] + ['fp-lib-table', 'sym-lib-table']
todo, seen = [STEM + '.kicad_sch'], set()
while todo:
    s = todo.pop()
    if s in seen:
        continue
    seen.add(s)
    p = os.path.join(src, s)
    if os.path.isfile(p):
        todo += re.findall(r'\(property "Sheetfile" "([^"]+)"', open(p, encoding='utf-8').read())
files += sorted(seen)
for dp, dn, fn in os.walk(os.path.join(src, 'libraries')):
    for f in fn:
        files.append(os.path.relpath(os.path.join(dp, f), src))
changed = []
for rel in files:
    a, b = os.path.join(src, rel), os.path.join(dst, rel)
    if not os.path.isfile(a):
        continue
    if os.path.isfile(b) and h(a) == h(b):
        continue
    changed.append(rel)
print(f'{len(changed)} file(s) differ:' + ''.join(f'\n  {c}' for c in changed))
if dry or not changed:
    sys.exit(0)
bk = os.path.join(dst, 'backups', f'before_{tag}')
for rel in changed:
    b = os.path.join(dst, rel)
    if os.path.isfile(b):
        os.makedirs(os.path.dirname(os.path.join(bk, rel)), exist_ok=True)
        shutil.copy2(b, os.path.join(bk, rel))
for rel in changed:
    a, b = os.path.join(src, rel), os.path.join(dst, rel)
    old = h(b)[:10] if os.path.isfile(b) else '(new)'
    os.makedirs(os.path.dirname(b), exist_ok=True)
    shutil.copy2(a, b)
    if h(a) != h(b):
        sys.exit(f'COPY FAILED for {rel}')
    print(f'  landed {rel}: {old} -> {h(b)[:10]}')
print(f'backup of the overwritten files: {bk}')

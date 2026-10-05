"""replay.py BASE_PROJECT_DIR OUT_DIR MANIFEST.json [MANIFEST2.json ...]  (2026-10-04)
Applies one or more change packages to a fresh copy of a project and runs every gate. KiCad python.

A package is a folder with manifest.json:
  {
   "name": "G1-parts",
   "konnect": "konnect.json",          # Konnect MCP calls (list of {name, arguments}); "{PROJ}" in any string = project dir
   "pre_pen": ["e_pre1.json"],          # pen.py edit lists applied to the board BEFORE the sync (e.g. delete copper)
   "sync": {"place": "place.json", "delete": ["R21"], "swap": []},   # tools/place/sync.py after the schematic edits
   "pen": ["e1.json", "e2.json"],       # pen.py edit lists applied AFTER the sync
   "expected": "expected.json",         # {"removed_refs": [], "added_refs": [], "net_changes": {NET: [[ref, pin], ...] or null}}
   "dru_patch": "patch.py",             # optional: python patch.py IN.kicad_dru OUT.kicad_dru (rules text edits, run after pen)
   "dru_sideaware": true,               # optional: run tools/dru_sideaware.py on the final board of this package
   "drc_allow_grow": ["track_width"]    # optional: DRC types that may grow ON PURPOSE (new rules expose real errors)
  }
DRU changes follow the scoped exception: the sign-off sentinel proves the patched file parses (checked here too).
Paths in the manifest are relative to its folder. Packages are applied in the order given. Konnect runs through the
session harness (env KONNECT_HARNESS = path to konnect_mcp_t.mjs, KONNECT_EXE = the rfvd2 build).

Gates printed at the end (exit 1 if any FAIL):
  ERC        no errors (excluded ones are fine); warnings listed
  NETLIST    the netlist diff vs the base equals the union of the packages' expected net_changes / ref lists
  PARITY     sync.py --dry-run on the result reports nothing to change and nothing unresolved
  METRICS    place/metrics.py: no net worse, except nets named in expected net_changes
  DRC        kicad-cli DRC in OUT_DIR (zones refilled): no error type grows vs the base; counts printed
Keep OUT_DIR on a short path (e.g. %LOCALAPPDATA%/Temp/rw/...): long paths break KiCad's footprint library loading."""
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
KCLI = r'C:/Program Files/KiCad/10.0/bin/kicad-cli.exe'
STEM = 'RFVD_SENSOR_BOARD'
base, outd = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
manifests = [os.path.abspath(m) for m in sys.argv[3:]]
env = dict(os.environ, PYTHONIOENCODING='utf-8', MSYS_NO_PATHCONV='1')
fails = []


def sh(cmd, name, must_ok=True, timeout=3600):
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
    out = '\n'.join(l for l in (r.stdout + r.stderr).splitlines() if 'memory leak' not in l and 'image handler' not in l)
    if r.returncode != 0 and must_ok:
        print(f'FAIL step {name}:\n' + out[-3000:])
        sys.exit(1)
    return out


def copy_project(src, dst):
    if os.path.exists(dst):
        shutil.rmtree(dst)
    os.makedirs(dst)
    for f in os.listdir(src):
        p = os.path.join(src, f)
        if f.endswith(('.kicad_sch', '.kicad_pcb', '.kicad_pro', '.kicad_dru')) or f in ('fp-lib-table', 'sym-lib-table'):
            shutil.copy2(p, dst)
    shutil.copytree(os.path.join(src, 'libraries'), os.path.join(dst, 'libraries'))


def netlist(proj, out):
    sh([KCLI, 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', out, os.path.join(proj, STEM + '.kicad_sch')], 'netlist')
    r = ET.parse(out).getroot()
    nets = {n.get('name'): sorted((x.get('ref'), x.get('pin')) for x in n.iter('node')) for n in r.iter('net')}
    refs = {c.get('ref') for c in r.iter('comp')}
    return nets, refs


def drc(proj, out):
    sh([KCLI, 'pcb', 'drc', '--all-track-errors', '--severity-all', '--refill-zones', '--format', 'json', '-o', out,
        os.path.join(proj, STEM + '.kicad_pcb')], 'drc', must_ok=False)
    d = json.load(open(out, encoding='utf-8'))
    return Counter((v['severity'], v['type']) for v in d['violations']), len(d.get('unconnected_items', []))


# ---- baseline (a pristine copy, so DRC/netlist run under the same path length)
basecopy = outd + '_base'
copy_project(base, basecopy)
os.makedirs(outd, exist_ok=True)
base_nets, base_refs = netlist(basecopy, os.path.join(basecopy, 'net.xml'))
base_drc, base_unc = drc(basecopy, os.path.join(basecopy, 'drc.json'))

copy_project(base, outd)
board = os.path.join(outd, STEM + '.kicad_pcb')
# intermediate boards go to their own folder: saving X.tmp.kicad_pcb inside the project makes KiCad leave a second
# root schematic there, and Konnect then refuses the next package's schematic edits (2026-10-04)
TMPD = os.path.join(outd, '_tmp')
os.makedirs(TMPD, exist_ok=True)
TMPB = os.path.join(TMPD, STEM + '.kicad_pcb')
expect_nets, exp_removed, exp_added, net_deltas = {}, set(), set(), {}
allow_grow = set()
harness = os.environ.get('KONNECT_HARNESS')
for m in manifests:
    md = os.path.dirname(m)
    man = json.load(open(m, encoding='utf-8'))
    name = man.get('name', os.path.basename(md))
    print(f'== package {name}')
    if man.get('konnect'):
        calls = json.load(open(os.path.join(md, man['konnect']), encoding='utf-8'))
        txt = json.dumps(calls).replace('{PROJ}', outd.replace('\\', '/'))
        cf = os.path.join(outd, f'_konnect_{name}.json')
        open(cf, 'w', encoding='utf-8').write(txt)
        res_f = cf.replace('.json', '.out.json')
        sh(['node', harness, cf, res_f], f'konnect {name}', must_ok=False, timeout=7200)
        res = json.load(open(res_f, encoding='utf-8'))
        bad = [r for r in res if r.get('isError')]
        print(f'   konnect: {len(res)} calls, {len(bad)} errors')
        if bad or len(res) != len(calls):
            print('FAIL konnect:\n   ' + '\n   '.join(f"{r['call']}: {r['text'][:300]}" for r in bad[:5]))
            sys.exit(1)
    for e in man.get('pre_pen', []):
        print('   ' + sh([PY, os.path.join(HERE, 'place', 'pen.py'), board, TMPB, os.path.join(md, e)],
                        f'pre_pen {e}').splitlines()[-1])
        shutil.move(TMPB, board)
    if man.get('sync') is not None:
        s = man['sync']
        nl = os.path.join(outd, f'_net_{name}.xml')
        netlist(outd, nl)
        cmd = [PY, os.path.join(HERE, 'place', 'sync.py'), board, nl, TMPB]
        if s.get('place'):
            cmd += ['--place', os.path.join(md, s['place'])]
        if s.get('delete'):
            cmd += ['--delete', ','.join(s['delete'])]
        if s.get('swap'):
            cmd += ['--swap', ','.join(s['swap'])]
        o = sh(cmd, f'sync {name}')
        print('   sync: ' + ' | '.join(l for l in o.splitlines() if l.startswith(('ADD', 'DEL', 'SWAP', '  ORPHAN'))))
        shutil.move(TMPB, board)
    for e in man.get('pen', []):
        o = sh([PY, os.path.join(HERE, 'place', 'pen.py'), board, TMPB, os.path.join(md, e)], f'pen {e}')
        print('   ' + ' | '.join(l for l in o.splitlines() if l.startswith(('pen:', 'check:')) or 'CHECK' in l))
        shutil.move(TMPB, board)
    dru = os.path.join(outd, STEM + '.kicad_dru')
    if man.get('dru_patch'):
        sh([PY, os.path.join(md, man['dru_patch']), dru, dru + '.new'], f'dru_patch {name}')
        shutil.move(dru + '.new', dru)
        print(f'   dru_patch: {man["dru_patch"]} applied')
    if man.get('dru_sideaware'):
        o = sh([PY, os.path.join(HERE, 'dru_sideaware.py'), dru, dru + '.new', board], f'dru_sideaware {name}')
        shutil.move(dru + '.new', dru)
        print('   ' + o.strip().splitlines()[-1])
    allow_grow.update(man.get('drc_allow_grow', []))
    if man.get('expected'):
        ex = json.load(open(os.path.join(md, man['expected']), encoding='utf-8'))
        # Each package states the full node list it expects for a net, relative to the BASE. Several packages may
        # change the same net (GND, VSYS, ...), so compose them as deltas: nodes added / removed versus the base.
        for k, v in ex.get('net_changes', {}).items():
            base_set = set(tuple(x) for x in base_nets.get(k, []))
            new_set = set() if v is None else set(tuple(x) for x in v)
            d = net_deltas.setdefault(k, {'add': set(), 'rem': set(), 'null': False})
            d['add'] |= new_set - base_set
            d['rem'] |= base_set - new_set
            d['null'] = d['null'] or v is None
        exp_removed |= set(ex.get('removed_refs', []))
        exp_added |= set(ex.get('added_refs', []))
shutil.rmtree(TMPD, ignore_errors=True)

# compose the expected final node list of every net any package changes: base - removed + added; nodes of parts
# that some package removes disappear from every net
for k, d in net_deltas.items():
    final = (set(tuple(x) for x in base_nets.get(k, [])) - d['rem']) | d['add']
    final = {n for n in final if n[0] not in exp_removed}
    expect_nets[k] = sorted(final) if final else None
# ---- gates
print('== gates')
erc_out = os.path.join(outd, 'erc.json')
sh([KCLI, 'sch', 'erc', '--format', 'json', '--severity-all', '-o', erc_out, os.path.join(outd, STEM + '.kicad_sch')], 'erc')
erc = json.load(open(erc_out, encoding='utf-8'))
ev = [v for s_ in erc['sheets'] for v in s_['violations'] if not v.get('excluded')]
errs = [v for v in ev if v['severity'] == 'error']
print(f"ERC      {'PASS' if not errs else 'FAIL'}: {len(errs)} errors, {len(ev) - len(errs)} warnings "
      f"{dict(Counter(v['type'] for v in ev))}")
if errs:
    fails.append('ERC')
    for v in errs[:10]:
        print('   ', v['type'], v['description'], [i['description'] for i in v['items']])

new_nets, new_refs = netlist(outd, os.path.join(outd, 'net.xml'))
changed = {n for n in set(base_nets) | set(new_nets) if base_nets.get(n) != new_nets.get(n)}
def only_removed_refs(n):
    a, b2 = set(tuple(x) for x in base_nets.get(n, [])), set(tuple(x) for x in new_nets.get(n, []))
    return b2 <= a and all(x[0] in exp_removed for x in a - b2)
unexpected = sorted(n for n in changed if n not in expect_nets and not only_removed_refs(n))
wrong = sorted(n for n, v in expect_nets.items() if (sorted(tuple(x) for x in new_nets.get(n, [])) or None) != v)
missing_change = []  # covered by 'wrong' (compares every expected net with the result)
rem, add = base_refs - new_refs, new_refs - base_refs
ref_bad = (rem != exp_removed) or (add != exp_added)
ok = not unexpected and not wrong and not ref_bad and not missing_change
print(f"NETLIST  {'PASS' if ok else 'FAIL'}: {len(changed)} nets changed; refs removed {sorted(rem)} added {sorted(add)}")
if not ok:
    fails.append('NETLIST')
    for n in unexpected[:30]:
        print(f'    unexpected change {n}: {base_nets.get(n)} -> {new_nets.get(n)}')
    for n in wrong[:30]:
        print(f'    expected {n} = {expect_nets[n]}, got {new_nets.get(n)}')
    if ref_bad:
        print(f'    refs expected removed {sorted(exp_removed)} added {sorted(exp_added)}')

os.makedirs(os.path.join(outd, '_chk'), exist_ok=True)
o = sh([PY, os.path.join(HERE, 'place', 'sync.py'), board, os.path.join(outd, 'net.xml'), os.path.join(outd, '_chk', STEM + '.kicad_pcb'), '--dry-run'],
       'parity', must_ok=False)
lines = [l for l in o.splitlines() if l.startswith(('ADD', 'DEL', 'SWAP', 'UPD', 'UNRESOLVED', '  '))
         and 'field ' not in l]
par_ok = not lines
print(f"PARITY   {'PASS' if par_ok else 'FAIL'}" + ('' if par_ok else ':\n    ' + '\n    '.join(lines[:30])))
if not par_ok:
    fails.append('PARITY')

o = sh([PY, os.path.join(HERE, 'place', 'metrics.py'), os.path.join(basecopy, STEM + '.kicad_pcb'), board], 'metrics')
worse_line = next((l for l in o.splitlines() if 'worse' in l), '')
print('METRICS  ' + ' | '.join(l.split('/')[-1] for l in o.splitlines() if 'unconnected' in l))
try:
    worse = eval(worse_line.split('worse', 1)[1].strip())
except Exception:
    worse = {}
bad_worse = {n: v for n, v in worse.items() if n not in expect_nets}
print(f"         {'PASS' if not bad_worse else 'FAIL'}: worse nets outside the expected changes: {bad_worse}")
if bad_worse:
    fails.append('METRICS')

new_drc, new_unc = drc(outd, os.path.join(outd, 'drc.json'))
grew = {k: (base_drc.get(k, 0), v) for k, v in new_drc.items() if k[0] == 'error' and v > base_drc.get(k, 0)
        and k[1] not in allow_grow}
if allow_grow:
    print(f'DRC      allowed to grow on purpose: {sorted(allow_grow)}')
    so = sh([PY, os.path.join(HERE, 'drc_signoff.py'), '--board-dir', outd, '--out', os.path.join(outd, '_so')],
            'signoff sentinel', must_ok=False)
    if 'sentinel' in so and 'ERROR' in so:
        print('DRC      FAIL: the rules file did not load (sentinel missing)')
        fails.append('DRU-PARSE')
print(f"DRC      {'PASS' if not grew else 'FAIL'}: errors {sum(v for k, v in new_drc.items() if k[0] == 'error')} "
      f"(base {sum(v for k, v in base_drc.items() if k[0] == 'error')}), warnings "
      f"{sum(v for k, v in new_drc.items() if k[0] == 'warning')} (base {sum(v for k, v in base_drc.items() if k[0] == 'warning')}), "
      f"unconnected {new_unc} (base {base_unc})")
for k in sorted(set(new_drc) | set(base_drc)):
    if new_drc.get(k, 0) != base_drc.get(k, 0):
        print(f'    {k[0]:7s} {k[1]:30s} {base_drc.get(k, 0):4d} -> {new_drc.get(k, 0):4d}')
if grew:
    fails.append('DRC')
print('replay: ' + ('ALL GATES PASS' if not fails else f'FAILED {fails}') + f' -> {board}')
sys.exit(1 if fails else 0)

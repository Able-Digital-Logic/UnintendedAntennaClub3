"""release_zip.py [PROJECT_DIR] --tag NAME [--date YYYY-MM-DD] [--signoff DRC_SIGNOFF.json] [--out DIR] [--note TEXT] [--dry-run]
Clean GitHub-ready release zip of the board (user rule 2026-10-03: one at EVERY checkpoint, "just the board stuff and
some documentation"). Run tools/make_outputs.py first so the outputs match the board. KiCad python, read-only on the
project (writes only the zip).

Contents (under RFVD_SENSOR_BOARD/ inside the zip):
  KiCad project   .kicad_pro/.kicad_pcb/.kicad_dru, the root schematic + every sheet it references (recursively, so
                  unreferenced sheets such as Trigger are left out), sym-lib-table, fp-lib-table, libraries/
  outputs/        schematic PDF, layer PDF, BOMs, JLCPCB BOM + CPL, positions, DRC report, unrouted list + map
  renders/        3D top / bottom
  docs/           BOARD_OVERVIEW.md, FIRMWARE_NOTES.md, DATASHEET_CHECKS.md
  README.md       generated: status numbers measured on the board (routed X/total, GND islands, DRC from the outputs
                  report, sign-off from --signoff if given)
  .gitignore      KiCad backups, locks, caches, prl
Excluded: tools/, backups/, scratch, .kicad_prl, models/ (unreferenced), renders history, internal docs and logs.
Checks before writing: every 3D model path used by the board resolves to a stock KiCad model or to a file in the zip;
every footprint library in fp-lib-table and symbol library in sym-lib-table is in the zip; every referenced sheet
exists. Any failure aborts (no zip)."""
import collections
import datetime
import json
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[1:]


def opt(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


pos_args = [a for i, a in enumerate(argv) if not a.startswith('--') and (i == 0 or argv[i - 1] not in
                                                                         ('--tag', '--date', '--signoff', '--out', '--note'))]
proj = os.path.abspath(pos_args[0] if pos_args else os.path.join(HERE, '..'))
tag = opt('--tag')
if not tag:
    sys.exit('--tag NAME is required (e.g. cp1-schematic-fixes)')
date = opt('--date', datetime.date.today().isoformat())
outdir = os.path.abspath(opt('--out', os.path.join(proj, '..', 'RFVD_SENSOR_BOARD_RELEASES')))
STEM = 'RFVD_SENSOR_BOARD'
ROOT = 'RFVD_SENSOR_BOARD/'
problems = []
files = []  # (abs path, arc path)


def add(rel, required=True):
    p = os.path.join(proj, rel)
    if os.path.isfile(p):
        files.append((p, ROOT + rel.replace('\\', '/')))
    elif required:
        problems.append(f'missing file: {rel}')


# ---- KiCad project
for ext in ('.kicad_pro', '.kicad_pcb', '.kicad_dru'):
    add(STEM + ext)
for t in ('sym-lib-table', 'fp-lib-table'):
    add(t)
# referenced sheets, recursively from the root schematic
sheets, todo = [], [STEM + '.kicad_sch']
while todo:
    s = todo.pop()
    if s in sheets:
        continue
    sheets.append(s)
    p = os.path.join(proj, s)
    if not os.path.isfile(p):
        problems.append(f'referenced sheet missing: {s}')
        continue
    txt = open(p, encoding='utf-8').read()
    todo += re.findall(r'\(property "Sheetfile" "([^"]+)"', txt)
for s in sheets:
    add(s)
unref = sorted(f for f in os.listdir(proj) if f.endswith('.kicad_sch') and f not in sheets)
# libraries/
for dp, dn, fn in os.walk(os.path.join(proj, 'libraries')):
    dn[:] = [d for d in dn if d not in ('__pycache__',)]
    for f in fn:
        if f.endswith(('.bak', '.lck')) or f.startswith('~') or f.startswith('_autosave'):
            continue
        rel = os.path.relpath(os.path.join(dp, f), proj)
        add(rel)
arcs = {a for _, a in files}
# library tables must resolve inside the zip
for t in ('sym-lib-table', 'fp-lib-table'):
    p = os.path.join(proj, t)
    if os.path.isfile(p):
        for name, uri in re.findall(r'\(lib \(name "([^"]+)"\) \(type "[^"]+"\) \(uri "([^"]+)"', open(p, encoding='utf-8').read()):
            if not uri.startswith('${KIPRJMOD}/'):
                problems.append(f'{t}: library {name} is not project-relative: {uri}')
                continue
            r = ROOT + uri[len('${KIPRJMOD}/'):]
            if r not in arcs and not any(a.startswith(r + '/') for a in arcs):
                problems.append(f'{t}: library {name} ({uri}) is not in the zip')
# 3D models used by the board and the project footprints
model_uses = collections.Counter()
srcs = [os.path.join(proj, STEM + '.kicad_pcb')] + [p for p, a in files if a.endswith('.kicad_mod')]
for p in srcs:
    if os.path.isfile(p):
        for m in re.findall(r'\(model "([^"]+)"', open(p, encoding='utf-8').read()):
            model_uses[m] += 1
for m in model_uses:
    if m.startswith('${KICAD10_3DMODEL_DIR}/') or m.startswith('${KICAD9_3DMODEL_DIR}/'):
        continue  # stock KiCad model, installed with KiCad
    if m.startswith('${KIPRJMOD}/'):
        if ROOT + m[len('${KIPRJMOD}/'):] not in arcs:
            problems.append(f'3D model not in the zip: {m}')
    else:
        problems.append(f'3D model path is not portable: {m}')

# ---- outputs, renders, docs
OUTS = ['RFVD_schematic.pdf', 'RFVD_board_layers.pdf', 'RFVD_BOM_grouped.csv', 'RFVD_BOM_per_reference.csv',
        'RFVD_JLCPCB_BOM.csv', 'RFVD_JLCPCB_CPL.csv', 'RFVD_positions_all.csv', 'RFVD_DRC_report.rpt',
        'RFVD_DRC_report.json', 'RFVD_unrouted.csv', 'RFVD_unrouted.png']
for f in OUTS:
    add('outputs/' + f)
add('outputs/RFVD_JLCPCB_CPL_rotation_check.csv', required=False)  # parts whose CPL rotation was corrected
for f in ('RFVD_3D_top.png', 'RFVD_3D_bottom.png'):
    add('renders/' + f)
add('docs/BOARD_OVERVIEW.md')
add('docs/FIRMWARE_NOTES.md', required=False)
add('docs/DATASHEET_CHECKS.md', required=False)  # every IC against its datasheet (DONE criterion 2)
add('docs/ROUTING_FINISH_GUIDE.md', required=False)  # how to finish the open links by hand (generated table in section 0)
add('docs/LEAD_GUI_STEPS.md', required=False)
add('docs/PLACEMENT_DATASHEET_CHECK.md', required=False)  # placement vs each datasheet layout guide, measured (DONE criterion 3)

# ---- status numbers, measured
import pcbnew  # noqa: E402

board = pcbnew.LoadBoard(os.path.join(proj, STEM + '.kicad_pcb'))
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
board.BuildConnectivity()
conn = board.GetConnectivity()
npads = collections.Counter()
islands = collections.Counter()
seen = set()
for fp in board.GetFootprints():
    for p in fp.Pads():
        n = p.GetNetname()
        if not n or n.startswith('unconnected-') or p.GetNetCode() <= 0:
            continue
        npads[n] += 1
        k = p.m_Uuid.AsString()
        if k in seen:
            continue
        seen.add(k)
        for it in conn.GetConnectedItems(p):
            it = it.Cast() if hasattr(it, 'Cast') else it
            if it.GetClass() == 'PAD':
                seen.add(it.m_Uuid.AsString())
        islands[n] += 1
total = sum(v - 1 for n, v in npads.items() if v > 1 and n != 'GND')
missing = sum(islands[n] - 1 for n, v in npads.items() if v > 1 and n != 'GND')
gnd_isl = max(0, islands.get('GND', 1) - 1)
nfp = len(list(board.GetFootprints()))
nf = sum(1 for f in board.GetFootprints() if not f.IsFlipped())
ntr = sum(1 for t in board.GetTracks() if t.Type() != pcbnew.PCB_VIA_T)
nvia = sum(1 for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T)
drcj = os.path.join(proj, 'outputs', 'RFVD_DRC_report.json')
drc = json.load(open(drcj, encoding='utf-8')) if os.path.isfile(drcj) else None
if drc:
    errs = sum(1 for v in drc['violations'] if v['severity'] == 'error')
    warns = sum(1 for v in drc['violations'] if v['severity'] == 'warning')
    unc = len(drc.get('unconnected_items', []))
    bytype = collections.Counter(v['type'] for v in drc['violations'] if v['severity'] == 'error')
    drc_line = f"{errs} errors ({', '.join(f'{k} x{v}' for k, v in bytype.most_common()) or 'none'}), {warns} warnings, {unc} unconnected"
    pcb_m = os.path.getmtime(os.path.join(proj, STEM + '.kicad_pcb'))
    if os.path.getmtime(drcj) < pcb_m:
        problems.append('outputs/RFVD_DRC_report.json is older than the board: run tools/make_outputs.py first')
else:
    drc_line = 'not generated'
so = opt('--signoff')
if so:
    # same test as drc_signoff.py: violations naming one of the '#SIGNOFF ' rules of the project DRU
    names = re.findall(r'^#SIGNOFF \(rule\s+"?([^"\s)]+)', open(os.path.join(proj, STEM + '.kicad_dru'), encoding='utf-8').read(), re.M)
    sj = json.load(open(so, encoding='utf-8'))
    hits = [v for v in sj['violations'] if any("rule '%s'" % n in v['description'] for n in names)]
    serr = sum(1 for v in hits if v['severity'] == 'error')
    so_line = (f'PASS ({len(names)} #SIGNOFF EMC rules, {len(hits) - serr} warnings)' if not serr
               else f'FAIL: {serr} errors from the {len(names)} #SIGNOFF rules')
    if os.path.getmtime(so) < os.path.getmtime(os.path.join(proj, STEM + '.kicad_pcb')):
        problems.append('--signoff report is older than the board: re-run tools/drcsum.py')
else:
    so_line = 'not run for this release'

readme = f"""# RFVD SENSOR-D main board (KiCad 10)

Release `{tag}`, {date}.

Battery-powered RF-induced-voltage recorder: an ADL5511 envelope/RMS detector, an AD7380 ADC and an STM32H743 MCU,
with microSD logging, a 2.4" display, a BQ25798 2S charger and a Samtec expansion mezzanine. The board summary is in
[`docs/BOARD_OVERVIEW.md`](docs/BOARD_OVERVIEW.md).

## Status (measured on this board)

| Item | Value |
|---|---|
| Outline | 52.05 x 90.05 mm, 6 layers (JLC06161H-3313: F / GND / GND / signal / GND / B), all vias resin-filled and capped |
| Parts | {nfp} footprints ({nf} top / {nfp - nf} bottom) |
| Routing | **{total - missing} of {total}** signal and power connections routed; {missing} missing; GND islands: {gnd_isl} |
| Copper | {ntr} track segments, {nvia} vias |
| DRC (project rules, `outputs/RFVD_DRC_report.*`) | {drc_line} |
| EMC sign-off rules | {so_line} |
{('| Note | ' + opt('--note') + ' |') if opt('--note') else ''}

{'**Not ready for fabrication yet:** routing is incomplete. Gerbers and drill files are deliberately not included.' if missing or (drc and errs) else 'Routing is complete and DRC has no errors. Generate Gerbers and drill files from the board with the JLC plug-in or `kicad-cli pcb export gerbers` / `drill`.'}

## Open in KiCad

Open `RFVD_SENSOR_BOARD.kicad_pro` in KiCad 10. The custom symbols, footprints and 3D models are in `libraries/`, with
project-relative paths. All other models are KiCad's stock models.

## Files

| Path | Contents |
|---|---|
| `RFVD_SENSOR_BOARD.kicad_pro / .kicad_pcb / .kicad_dru` | Project, board and custom design rules (EMC and JLC rules) |
| `*.kicad_sch` | Schematic: root plus {len(sheets) - 1} sheets |
| `libraries/` | Project symbol and footprint libraries, and 3D models |
| `outputs/` | Schematic PDF, multi-page layer PDF, BOMs, JLCPCB BOM and CPL, positions, DRC report, list and map of missing connections |
| `renders/` | 3D renders, top and bottom |
| `docs/` | Board overview, the firmware settings the hardware depends on (`FIRMWARE_NOTES.md`) and the datasheet check of every IC (`DATASHEET_CHECKS.md`) |
"""
gitignore = """# KiCad
*.kicad_prl
*-backups/
_autosave-*
*.lck
~*.lck
fp-info-cache
*.bak
*.kicad_pcb-bak
*.kicad_sch-bak
# OS
.DS_Store
Thumbs.db
"""

print(f'project  {proj}')
print(f'sheets   {len(sheets)} referenced; not referenced (left out): {unref or "none"}')
print(f'files    {len(files)}; 3D models used {len(model_uses)} '
      f'({sum(1 for m in model_uses if m.startswith("${KIPRJMOD}"))} project, rest stock)')
print(f'status   routed {total - missing}/{total}, GND islands {gnd_isl}, DRC {drc_line}, sign-off {so_line}')
if problems:
    print('ABORT, problems:\n  ' + '\n  '.join(problems))
    sys.exit(1)
if '--dry-run' in argv:
    print('dry run: nothing written')
    sys.exit(0)
os.makedirs(outdir, exist_ok=True)
zpath = os.path.join(outdir, f'{STEM}_release_{date}_{tag}.zip')
if os.path.exists(zpath):
    sys.exit(f'{zpath} exists: use a new --tag')
with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
    for p, a in files:
        z.write(p, a)
    z.writestr(ROOT + 'README.md', readme)
    z.writestr(ROOT + '.gitignore', gitignore)
print(f'zip      {zpath} ({os.path.getsize(zpath) / 1e6:.1f} MB, {len(files) + 2} files)')

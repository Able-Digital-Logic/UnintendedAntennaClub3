"""make_outputs.py [PROJECT_DIR] [--bom] [--skip-renders]
Regenerates every handoff output from the board in PROJECT_DIR (default: this tool's parent folder), so outputs always
match the board (one tool for the job, 2026-10-02):
  outputs/RFVD_DRC_report.rpt / .json      kicad-cli pcb drc --severity-all --refill-zones (project DRU)
  outputs/RFVD_unrouted.csv / .png          tools/unrouted_map.py
  outputs/RFVD_positions_all.csv            kicad-cli pcb export pos (csv, mm, both sides)
  outputs/RFVD_JLCPCB_CPL.csv               Designator, Mid X, Mid Y, Layer, Rotation (from the position file)
  outputs/RFVD_board_layers.pdf             kicad-cli pcb export pdf --mode-multipage (copper, silk, fab + outline)
  outputs/RFVD_placement_audit_*            tools/placeaudit.py --png
  renders/RFVD_3D_top.png / _bottom.png     kicad-cli pcb render (skipped with --skip-renders)
  renders/layer_*.png                       tools/layer_images.py (skipped with --skip-renders)
  outputs/RFVD_schematic.pdf                kicad-cli sch export pdf, every run (2026-10-04)
  outputs/RFVD_BOM_grouped.csv / _per_reference.csv / RFVD_JLCPCB_BOM.csv   kicad-cli sch export bom, every run
         (2026-10-03): DNP from KiCad's attribute, one designator per entry, JLC BOM grouped by LCSC number; the CPL is
         then cut to exactly the JLC BOM designators. FAIL if a fitted part has no LCSC number or no board position.
         (--bom is still accepted and does nothing extra.)
Never writes the board. Run with KiCad's python."""
import csv
import glob
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[1:]
proj = os.path.abspath(next((a for a in argv if not a.startswith('--')), os.path.join(HERE, '..')))
KCLI = r'C:/Program Files/KiCad/10.0/bin/kicad-cli.exe'
PY = sys.executable
board = os.path.join(proj, 'RFVD_SENSOR_BOARD.kicad_pcb')
out = os.path.join(proj, 'outputs')
ren = os.path.join(proj, 'renders')
os.makedirs(out, exist_ok=True)
os.makedirs(ren, exist_ok=True)
env = dict(os.environ, PYTHONIOENCODING='utf-8')
steps = []


def run(name, cmd, timeout=900):
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
    ok = r.returncode == 0
    tail = [l for l in (r.stdout + r.stderr).splitlines() if l.strip() and 'memory leak' not in l and 'image handler' not in l][-3:]
    steps.append((name, ok, tail))
    print(f"{'OK  ' if ok else 'FAIL'} {name}" + ('' if ok else ':\n     ' + '\n     '.join(tail)))
    return ok


run('DRC report', [KCLI, 'pcb', 'drc', '--all-track-errors', '--severity-all', '--refill-zones', '--format', 'report', '-o', os.path.join(out, 'RFVD_DRC_report.rpt'), board])
run('DRC json', [KCLI, 'pcb', 'drc', '--all-track-errors', '--severity-all', '--refill-zones', '--format', 'json', '-o', os.path.join(out, 'RFVD_DRC_report.json'), board])
run('unrouted map', [PY, os.path.join(HERE, 'unrouted_map.py'), board, os.path.join(out, 'RFVD_unrouted')])
pos = os.path.join(out, 'RFVD_positions_all.csv')
if run('positions', [KCLI, 'pcb', 'export', 'pos', '--side', 'both', '--format', 'csv', '--units', 'mm', '-o', pos, board]):
    rows = list(csv.DictReader(open(pos, encoding='utf-8')))
    # JLC rotation corrections (tools/jlc_rotations.csv, from JLCKicadTools; critique P1-11): top (rot + c) % 360,
    # bottom ((180 - ((rot - c) % 360)) % 360). The list of corrected parts is written for the JLC preview check.
    import re as _re
    rot_db = []
    rdb = os.path.join(HERE, 'jlc_rotations.csv')
    if os.path.isfile(rdb):
        for rr in csv.DictReader(l for l in open(rdb, encoding='utf-8') if not l.startswith('#')):
            rot_db.append((_re.compile(rr['pattern']), float(rr['rotation']), float(rr['offset_x']), float(rr['offset_y'])))
    corrected = []
    with open(os.path.join(out, 'RFVD_JLCPCB_CPL.csv'), 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        for r in rows:
            top = r['Side'].lower() == 'top'
            rot, x, y = float(r['Rot']), float(r['PosX']), float(r['PosY'])
            hit = None
            for rx, c, ox, oy in rot_db:  # the LAST matching pattern wins, as in JLCKicadTools' FixRotations
                if rx.match(r.get('Package', '')):
                    hit = (c, ox, oy)
            if hit:
                c, ox, oy = hit
                rot = (rot + c) % 360 if top else (rot - c) % 360
                x, y = x + ox, y + oy
            if not top:
                rot = (180 - rot) % 360
            if hit:
                corrected.append((r['Ref'], r.get('Package', ''), 'Top' if top else 'Bottom', float(r['Rot']), rot))
            w.writerow([r['Ref'], f"{x:.6f}mm", f"{y:.6f}mm", 'Top' if top else 'Bottom', f"{rot:.6f}"])
    with open(os.path.join(out, 'RFVD_JLCPCB_CPL_rotation_check.csv'), 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['Designator', 'Package', 'Layer', 'KiCad_rot', 'JLC_rot'])
        w.writerows(corrected)
    print(f"     CPL: {len(rows)} placements, {len(corrected)} rotation-corrected (list: RFVD_JLCPCB_CPL_rotation_check.csv; "
          f"bottom parts use JLC's 180-rot convention)")
run('layer PDF', [KCLI, 'pcb', 'export', 'pdf', '--mode-multipage', '--layers',
                  'F.Cu,In1.Cu,In2.Cu,In3.Cu,In4.Cu,B.Cu,F.Silkscreen,B.Silkscreen,F.Fab,B.Fab,User.Drawings',
                  '--common-layers', 'Edge.Cuts', '-o', os.path.join(out, 'RFVD_board_layers.pdf'), board])
run('placement audit', [PY, os.path.join(HERE, 'placeaudit.py'), board, '--out', os.path.join(out, 'RFVD_placement_audit'), '--png'], timeout=1800)
if '--skip-renders' not in argv:
    for side in ('top', 'bottom'):
        run(f'3D {side}', [KCLI, 'pcb', 'render', '--side', side, '--width', '2000', '--height', '3400', '--quality', 'high',
                           '-o', os.path.join(ren, f'RFVD_3D_{side}.png'), board], timeout=1200)
    run('layer images', [PY, os.path.join(HERE, 'layer_images.py'), board, ren])
# ---- BOMs, every run (2026-10-03). DNP is KiCad's own attribute ${DNP}: a custom field named "DNP" shadowed it and
# dropped the fitted FB1 damper C100/R109 from the JLC BOM. Designators are listed one by one (no "C105-C107"
# ranges), which is the plain comma-separated form JLC's BOM import expects. The JLC BOM and CPL are built from the
# same rows: CPL = exactly the JLC BOM designators (no DNP parts, test points or jumpers).
sch = os.path.join(proj, 'RFVD_SENSOR_BOARD.kicad_sch')
run('schematic PDF', [KCLI, 'sch', 'export', 'pdf', '-o', os.path.join(out, 'RFVD_schematic.pdf'), sch])
FIELDS =['Reference', 'Value', 'Footprint', '${QUANTITY}', '${DNP}', 'Manufacturer', 'MPN', 'LCSC', 'JLCPCB_PN', 'Function',
          'Description', 'Distributor', 'Unit_Cost_USD', 'Sourcing_Status', 'Source_URL', 'Datasheet']
LABELS = ['References', 'Value', 'Footprint', 'Qty', 'DNP', 'Manufacturer', 'MPN', 'LCSC', 'JLCPCB_PN', 'Function',
          'Description', 'Distributor', 'Unit_Cost_USD', 'Sourcing_Status', 'Source_URL', 'Datasheet']
bom_common = ['--fields', ','.join(FIELDS), '--labels', ','.join(LABELS), '--ref-range-delimiter', '']
run('BOM grouped', [KCLI, 'sch', 'export', 'bom', *bom_common, '--group-by', 'Value,Footprint,MPN,${DNP}',
                    '-o', os.path.join(out, 'RFVD_BOM_grouped.csv'), sch])
run('BOM per reference', [KCLI, 'sch', 'export', 'bom', *bom_common, '-o', os.path.join(out, 'RFVD_BOM_per_reference.csv'), sch])
fitted_csv = os.path.join(out, '_fitted_tmp.csv')
if run('BOM fitted', [KCLI, 'sch', 'export', 'bom', *bom_common, '--exclude-dnp', '-o', fitted_csv, sch]):
    rows = list(csv.DictReader(open(fitted_csv, encoding='utf-8')))
    os.remove(fitted_csv)
    by_lcsc, missing = {}, []
    for r in rows:
        lcsc = (r['LCSC'] or r['JLCPCB_PN'] or '').strip()
        refs = [x.strip() for x in r['References'].split(',') if x.strip()]
        if not lcsc:
            missing += refs
            continue
        e = by_lcsc.setdefault(lcsc, dict(value=r['Value'], fp=r['Footprint'].split(':')[-1], mfr=r['Manufacturer'],
                                          mpn=r['MPN'], refs=[]))
        e['refs'] += refs
    with open(os.path.join(out, 'RFVD_JLCPCB_BOM.csv'), 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #', 'Manufacturer', 'MPN'])
        for lcsc, e in sorted(by_lcsc.items(), key=lambda kv: kv[1]['refs'][0]):
            w.writerow([e['value'], ','.join(e['refs']), e['fp'], lcsc, e['mfr'], e['mpn']])
    bom_refs = {x for e in by_lcsc.values() for x in e['refs']}
    ok = not missing
    steps.append(('JLC BOM: every fitted part has an LCSC number', ok, missing))
    print(f"{'OK  ' if ok else 'FAIL'} JLC BOM: {len(by_lcsc)} lines, {len(bom_refs)} placed parts"
          + ('' if ok else f'; fitted parts WITHOUT an LCSC number: {missing}'))
    cpl = os.path.join(out, 'RFVD_JLCPCB_CPL.csv')
    if os.path.isfile(cpl):
        crow = list(csv.DictReader(open(cpl, encoding='utf-8')))
        keep = [r for r in crow if r['Designator'] in bom_refs]
        with open(cpl, 'w', newline='', encoding='utf-8') as fh:
            w = csv.DictWriter(fh, fieldnames=list(crow[0].keys()))
            w.writeheader()
            w.writerows(keep)
        not_placed = sorted(bom_refs - {r['Designator'] for r in keep})
        ok = not not_placed
        steps.append(('CPL covers every JLC BOM designator', ok, not_placed))
        print(f"{'OK  ' if ok else 'FAIL'} CPL: {len(keep)} placements (dropped {len(crow) - len(keep)} DNP / test point / jumper rows)"
              + ('' if ok else f'; BOM parts with no board position: {not_placed}'))
bad = [s for s in steps if not s[1]]
print('make_outputs:', 'all outputs regenerated' if not bad else f'{len(bad)} step(s) failed: {[s[0] for s in bad]}')
sys.exit(1 if bad else 0)

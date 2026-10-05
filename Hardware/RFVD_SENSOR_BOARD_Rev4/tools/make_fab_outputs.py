#!/usr/bin/env python3
"""make_fab_outputs.py - JLCPCB fabrication package for RFVD SENSOR-D Rev A (fix plan P1-10).

Python port of the useful parts of scratchpad v6/fab/make_fab_outputs.sh (2026-10-01). Run with KiCad 10's python:
  "C:/Program Files/KiCad/10.0/bin/python.exe" make_fab_outputs.py SOURCE OUT_DIR [options]

  SOURCE   a .kicad_pcb: the board project (RFVD_SENSOR_BOARD.kicad_pcb) or a panel written by make_panel.py.
           It is only read; everything happens on a copy in OUT_DIR/work.
  OUT_DIR  a NEW folder outside the project tree.

Steps
  1. copy the source project files to OUT_DIR/work (pcb, pro, dru; for a board also the schematics, libraries and
     library tables, so DRC can run the schematic-parity test);
  2. DRC on the copy as saved; for a board: refill the zones on the copy, save it, DRC again (with schematic parity),
     then DRC once more with the '#SIGNOFF ' rules of the .kicad_dru switched on in a second copy (the live rules park
     them as comments so the interactive router stays fast). A panel is never refilled: make_panel.py already built it
     from a refilled board, and a refill with the panel outline could change the board fills;
  3. remove solder paste from every pad of a do-not-populate footprint (kicad-cli has no option for it; JLC cuts the
     stencil from our paste layers);
  4. Gerber X2: F.Cu, In1.Cu, In2.Cu, In3.Cu, In4.Cu, B.Cu, F/B.Paste, F/B.Silkscreen, F/B.Mask, Edge.Cuts
     (13 files, Protel extensions, soldermask subtracted from silkscreen, 6-digit precision) + Gerber job file;
  5. Excellon drill files, PTH and NPTH separate, absolute origin, mm, decimal, oval holes in 'alternate' mode
     (JLC KiCad guide); drill map (PDF) and drill report go to reports/, not into the upload zip;
  6. IPC-D-356 netlist for a single board only (a multi-board panel shares net names between the copies, so its
     IPC-D-356 would claim that copy 1 and copy 2 are connected);
  7. zip of the Gerbers + drill files for upload;
  8. optional --cpl/--bom: copied into the package after a designator check (single board: tools/make_outputs.py
     files; panel: make_panel.py files);
  9. fab-notes drawing (PDF): Edge.Cuts + the fab_notes.txt block on User.Comments, for the record;
 10. checks (PASS / WARN / FAIL / INFO) -> reports/check_fab_outputs.txt and .json.
Exit: 0 no FAIL, 1 at least one FAIL (all outputs are still written unless --strict), 2 usage error.
"""
import argparse
import collections
import csv
import glob
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile

import pcbnew

KCLI_DEFAULT = r'C:/Program Files/KiCad/10.0/bin/kicad-cli.exe'
TO, MM = pcbnew.ToMM, pcbnew.FromMM
HERE = os.path.dirname(os.path.abspath(__file__))
GERBER_LAYERS = 'F.Cu,In1.Cu,In2.Cu,In3.Cu,In4.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts'
X2_NEED = {'Copper,L1,Top', 'Copper,L2,Inr', 'Copper,L3,Inr', 'Copper,L4,Inr', 'Copper,L5,Inr', 'Copper,L6,Bot',
           'Soldermask,Top', 'Soldermask,Bot', 'Paste,Top', 'Paste,Bot', 'Legend,Top', 'Legend,Bot', 'Profile,NP'}
STACKUP_3313 = (0.0994, 0.55, 0.1088, 0.55, 0.0994)          # JLC06161H-3313 dielectrics, F..B
PANEL_REF = re.compile(r'^(MB|TH|FID)\d+$')


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


class Pkg:
    def __init__(self, a):
        self.a = a
        self.res = []
        self.log = []

    def chk(self, name, ok, detail='', level='FAIL'):
        self.res.append(('PASS' if ok else level, name, str(detail)))
        if not ok and level == 'FAIL' and self.a.strict:
            self.finish()
            sys.exit(1)

    def info(self, name, detail):
        self.res.append(('INFO', name, str(detail)))

    def run(self, name, cmd, timeout=1800, ok_codes=(0,)):
        t0 = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        tail = [l for l in (r.stdout + r.stderr).splitlines() if l.strip() and 'memory leak' not in l and 'image handler' not in l]
        self.log.append('%s: rc %d, %.1f s %s' % (name, r.returncode, time.time() - t0, ' | '.join(tail[-2:])))
        print('  %-34s rc %d (%.0f s)' % (name, r.returncode, time.time() - t0))
        return r.returncode in ok_codes, tail

    def finish(self):
        rep = os.path.join(self.a.out_dir, 'reports')
        os.makedirs(rep, exist_ok=True)
        w = max(len(x[1]) for x in self.res) if self.res else 10
        lines = ['%-4s  %-*s  %s' % (s, w, n, d) for s, n, d in self.res]
        nf = sum(1 for s, _, _ in self.res if s == 'FAIL')
        nw = sum(1 for s, _, _ in self.res if s == 'WARN')
        npass = sum(1 for s, _, _ in self.res if s == 'PASS')
        lines.append('\n%d FAIL, %d WARN, %d PASS' % (nf, nw, npass))
        with open(os.path.join(rep, 'check_fab_outputs.txt'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n\nsteps:\n' + '\n'.join(self.log) + '\n')
        with open(os.path.join(rep, 'check_fab_outputs.json'), 'w', encoding='utf-8') as f:
            json.dump(dict(results=self.res, steps=self.log, fail=nf, warn=nw, passed=npass), f, indent=1)
        print('\n'.join(lines))
        return nf


def drc_summary(path):
    j = json.load(open(path, encoding='utf-8'))
    v = j.get('violations', []) + j.get('unconnected_items', []) + j.get('schematic_parity', [])
    errs = collections.Counter(x.get('type') for x in v if x.get('severity') == 'error')
    warns = collections.Counter(x.get('type') for x in v if x.get('severity') == 'warning')
    return dict(errors=sum(errs.values()), error_types=dict(errs.most_common()), warnings=sum(warns.values()),
                unconnected=len(j.get('unconnected_items', [])), parity=len(j.get('schematic_parity', [])))


def strip_dnp_paste(pcb):
    b = pcbnew.LoadBoard(pcb)
    stripped, fps = [], []
    for fp in b.GetFootprints():
        if not fp.IsDNP():
            continue
        fps.append(fp.GetReference())
        for p in fp.Pads():
            if p.IsOnLayer(pcbnew.F_Paste) or p.IsOnLayer(pcbnew.B_Paste):
                ls = p.GetLayerSet()
                ls.RemoveLayer(pcbnew.F_Paste)
                ls.RemoveLayer(pcbnew.B_Paste)
                p.SetLayerSet(ls)
                stripped.append('%s.%s' % (fp.GetReference(), p.GetNumber()))
    if stripped:
        b.Save(pcb)
    return fps, stripped


def gerber_flashes(path):
    t = open(path, errors='ignore').read()
    fs = re.search(r'%FSLAX(\d)(\d)Y', t)
    dec = int(fs.group(2)) if fs else 6
    return [(int(m.group(1)) / 10 ** dec, int(m.group(2)) / 10 ** dec) for m in re.finditer(r'X(-?\d+)Y(-?\d+)D03', t)]


def drill_hits(path):
    tools, hits, cur = {}, collections.Counter(), None
    for line in open(path, errors='ignore'):
        m1 = re.match(r'^T(\d+)C([\d.]+)', line)
        if m1:
            tools[m1.group(1)] = round(float(m1.group(2)), 3)
            continue
        m2 = re.match(r'^T(\d+)\s*$', line)
        if m2:
            cur = m2.group(1)
            continue
        if cur and line.startswith('X') and cur in tools:
            hits[tools[cur]] += 1
    return hits


def mask_webs(b, lim):
    """Solder-mask web between openings of pads on DIFFERENT nets (port of v6 maskweb.py; exact for round/oval/
    rect/roundrect pads, bounding box for custom pads). Returns sorted [(web, padA, padB, side)] below lim."""
    def inner_poly(p, layer):
        sh = p.GetShape(layer)
        sx, sy = TO(p.GetSize(layer).x), TO(p.GetSize(layer).y)
        r = 0.0
        if sh == pcbnew.PAD_SHAPE_ROUNDRECT:
            r = TO(p.GetRoundRectCornerRadius(layer))
        elif sh in (pcbnew.PAD_SHAPE_OVAL, pcbnew.PAD_SHAPE_CIRCLE):
            r = min(sx, sy) / 2
        elif sh not in (pcbnew.PAD_SHAPE_RECTANGLE,):
            bb = p.GetBoundingBox()
            hx, hy = TO(bb.GetWidth()) / 2, TO(bb.GetHeight()) / 2
            cx, cy = TO(bb.GetCenter().x), TO(bb.GetCenter().y)
            return [(cx - hx, cy - hy), (cx + hx, cy - hy), (cx + hx, cy + hy), (cx - hx, cy + hy)], 0.0
        hx, hy = max(sx / 2 - r, 0), max(sy / 2 - r, 0)
        a = math.radians(p.GetOrientation().AsDegrees())
        c, s = math.cos(a), math.sin(a)
        X, Y = TO(p.GetPosition().x), TO(p.GetPosition().y)
        return [(X + x * c + y * s, Y - x * s + y * c) for x, y in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy))], r

    def seg_pt(p, a, b_):
        ax, ay = a
        bx, by = b_
        px, py = p
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
        return math.hypot(px - ax - t * dx, py - ay - t * dy)

    def pdist(A, B):
        d = float('inf')
        for P, Q in ((A, B), (B, A)):
            for v in P:
                for i in range(len(Q)):
                    d = min(d, seg_pt(v, Q[i], Q[(i + 1) % len(Q)]))
        return d
    out = []
    for layer, mlayer, side in ((pcbnew.F_Cu, pcbnew.F_Mask, 'F'), (pcbnew.B_Cu, pcbnew.B_Mask, 'B')):
        pads = []
        for fp in b.GetFootprints():
            for p in fp.Pads():
                if p.IsOnLayer(layer) and p.IsOnLayer(mlayer) and p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                    poly, r = inner_poly(p, layer)
                    e = TO(p.GetSolderMaskExpansion(layer))
                    xs, ys = [q[0] for q in poly], [q[1] for q in poly]
                    pads.append(('%s.%s' % (fp.GetReference(), p.GetNumber()), p.GetNetname(), poly, r + e,
                                 (min(xs) - r - e, min(ys) - r - e, max(xs) + r + e, max(ys) + r + e)))
        grid = collections.defaultdict(list)
        for i, pd in enumerate(pads):
            bb = pd[4]
            for gx in range(int((bb[0] - lim) // 1), int((bb[2] + lim) // 1) + 1):
                for gy in range(int((bb[1] - lim) // 1), int((bb[3] + lim) // 1) + 1):
                    grid[(gx, gy)].append(i)
        seen = set()
        for idx in grid.values():
            for ii in range(len(idx)):
                for jj in range(ii + 1, len(idx)):
                    i, j = idx[ii], idx[jj]
                    if (i, j) in seen:
                        continue
                    seen.add((i, j))
                    A, B = pads[i], pads[j]
                    if A[1] == B[1] and A[1]:
                        continue
                    ba, bb_ = A[4], B[4]
                    if ba[2] + lim < bb_[0] or bb_[2] + lim < ba[0] or ba[3] + lim < bb_[1] or bb_[3] + lim < ba[1]:
                        continue
                    web = pdist(A[2], B[2]) - A[3] - B[3]
                    if web < lim - 1e-6:
                        out.append((round(web, 3), A[0], B[0], side))
    return sorted(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('source', help='.kicad_pcb (board or make_panel.py panel), or a folder holding exactly one')
    ap.add_argument('out_dir', help='new output folder outside the project tree')
    ap.add_argument('--cpl', help='JLC CPL to package (single: tools/make_outputs.py; panel: make_panel.py)')
    ap.add_argument('--bom', help='JLC BOM to package')
    ap.add_argument('--notes', default=os.path.join(HERE, 'fab_notes.txt'), help='fab-notes text for the record PDF')
    ap.add_argument('--no-signoff', action='store_true', help='skip the DRC with the #SIGNOFF rules switched on')
    ap.add_argument('--strict', action='store_true', help='stop at the first FAIL')
    ap.add_argument('--kicad-cli', default=KCLI_DEFAULT)
    a = ap.parse_args()
    K = a.kicad_cli
    if not os.path.isfile(K):
        print('ERROR: kicad-cli not found: %s' % K); sys.exit(2)
    src = os.path.abspath(a.source)
    if os.path.isdir(src):
        c = [f for f in glob.glob(os.path.join(src, '*.kicad_pcb')) if not f.endswith('_Prev.kicad_pcb')]
        if len(c) != 1:
            print('ERROR: %s holds %d .kicad_pcb files' % (src, len(c))); sys.exit(2)
        src = c[0]
    if not os.path.isfile(src):
        print('ERROR: no such board %s' % src); sys.exit(2)
    a.out_dir = out = os.path.abspath(a.out_dir)
    src_dir, base = os.path.dirname(src), os.path.splitext(os.path.basename(src))[0]
    nout, nsrc = os.path.normcase(out), os.path.normcase(src_dir)
    if 'RFVD_Authoritative' in out.replace('\\', '/') or nout == nsrc or nout.startswith(nsrc + os.sep):
        print('ERROR: OUT_DIR must be outside the project tree and outside the source folder'); sys.exit(2)
    if os.path.exists(out):
        print('ERROR: OUT_DIR %s exists - use a new folder' % out); sys.exit(2)
    if glob.glob(os.path.join(src_dir, '~*.lck')) or glob.glob(os.path.join(src_dir, '*.lck')):
        print('NOTE: a KiCad lock file exists next to the source: only the last SAVED state is packaged')
    P = Pkg(a)
    work, rep, jlc = os.path.join(out, 'work'), os.path.join(out, 'reports'), os.path.join(out, 'jlc')
    ger = os.path.join(jlc, 'gerbers')
    for d in (work, rep, ger):
        os.makedirs(d, exist_ok=True)
    src_hash = sha256(src)

    # ------------------------------------------------------------------ 1. copy
    for ext in ('.kicad_pcb', '.kicad_pro', '.kicad_dru'):
        f = os.path.join(src_dir, base + ext)
        if os.path.isfile(f):
            shutil.copy2(f, work)
    B = os.path.join(work, base + '.kicad_pcb')
    b0 = pcbnew.LoadBoard(B)
    panel_fps = [fp.GetReference() for fp in b0.GetFootprints() if PANEL_REF.match(fp.GetReference())]
    is_panel = bool(panel_fps)
    # make_panel.py keeps the board references in every copy, so the copy count is the highest reference multiplicity
    mult = collections.Counter(fp.GetReference() for fp in b0.GetFootprints() if not PANEL_REF.match(fp.GetReference()))
    copies = max(mult.values()) if mult else 1
    if is_panel:
        prep = os.path.join(src_dir, 'panel_report.json')
        if os.path.isfile(prep):
            shutil.copy2(prep, rep)
    else:
        for f in glob.glob(os.path.join(src_dir, '*.kicad_sch')) + [os.path.join(src_dir, n) for n in ('sym-lib-table', 'fp-lib-table')]:
            if os.path.isfile(f):
                shutil.copy2(f, work)
        if os.path.isdir(os.path.join(src_dir, 'libraries')):
            shutil.copytree(os.path.join(src_dir, 'libraries'), os.path.join(work, 'libraries'))
    del b0
    with open(os.path.join(rep, 'manifest.txt'), 'w', encoding='utf-8') as f:
        r = subprocess.run([K, 'version'], capture_output=True, text=True)
        f.write('source: %s\nsha256: %s\npackaged: %s\nkicad-cli: %s\nkind: %s (%d board copies)\n' % (
            src, src_hash, time.strftime('%Y-%m-%dT%H:%M:%S'), r.stdout.strip(), 'panel' if is_panel else 'board', copies))
    print('source %s (%s, %d copies) -> %s' % (src, 'panel' if is_panel else 'board', copies, out))

    # ------------------------------------------------------------------ 2. DRC
    drc = {}
    ok, _ = P.run('DRC saved state', [K, 'pcb', 'drc', '--all-track-errors', '--format', 'json', '--severity-all', '--units', 'mm', '-o',
                                      os.path.join(rep, 'drc_saved.json'), B], ok_codes=(0, 5))
    if os.path.isfile(os.path.join(rep, 'drc_saved.json')):
        drc['saved'] = drc_summary(os.path.join(rep, 'drc_saved.json'))
    if not is_panel:
        parity = ['--schematic-parity'] if glob.glob(os.path.join(work, '*.kicad_sch')) else []
        P.run('DRC refill + save copy', [K, 'pcb', 'drc', '--all-track-errors', '--refill-zones', '--save-board', '--format', 'json', '--severity-all',
                                         '--units', 'mm', *parity, '-o', os.path.join(rep, 'drc_refilled.json'), B], ok_codes=(0, 5))
        if os.path.isfile(os.path.join(rep, 'drc_refilled.json')):
            drc['refilled'] = drc_summary(os.path.join(rep, 'drc_refilled.json'))
        dru = os.path.join(work, base + '.kicad_dru')
        if not a.no_signoff and os.path.isfile(dru):
            so = os.path.join(out, 'work_signoff')
            os.makedirs(so, exist_ok=True)
            for ext in ('.kicad_pcb', '.kicad_pro'):
                shutil.copy2(os.path.join(work, base + ext), so)
            txt = open(dru, encoding='utf-8').read()
            n_so = len(re.findall(r'(?m)^#SIGNOFF ', txt))
            open(os.path.join(so, base + '.kicad_dru'), 'w', encoding='utf-8').write(re.sub(r'(?m)^#SIGNOFF ', '', txt))
            P.run('DRC sign-off rules (%d lines)' % n_so, [K, 'pcb', 'drc', '--all-track-errors', '--format', 'json', '--severity-all', '--units', 'mm',
                                                          '-o', os.path.join(rep, 'drc_signoff.json'), os.path.join(so, base + '.kicad_pcb')],
                  ok_codes=(0, 5))
            if os.path.isfile(os.path.join(rep, 'drc_signoff.json')):
                drc['signoff'] = drc_summary(os.path.join(rep, 'drc_signoff.json'))
                drc['signoff']['signoff_lines_enabled'] = n_so

    # ------------------------------------------------------------------ 3. DNP paste
    dnp_fps, stripped = strip_dnp_paste(B)

    # ------------------------------------------------------------------ 4.-7. Gerbers, drill, IPC-D-356, zip
    P.run('Gerber X2 (13 layers)', [K, 'pcb', 'export', 'gerbers', '--layers', GERBER_LAYERS, '--subtract-soldermask',
                                    '--precision', '6', '-o', ger + os.sep, B])
    P.run('Excellon PTH/NPTH', [K, 'pcb', 'export', 'drill', '--format', 'excellon', '--drill-origin', 'absolute',
                                '--excellon-units', 'mm', '--excellon-zeros-format', 'decimal', '--excellon-oval-format', 'alternate',
                                '--excellon-separate-th', '-o', ger + os.sep, B])
    maps = os.path.join(rep, 'drill_map')
    os.makedirs(maps, exist_ok=True)
    P.run('drill map (PDF) + report', [K, 'pcb', 'export', 'drill', '--format', 'excellon', '--drill-origin', 'absolute',
                                       '--excellon-units', 'mm', '--excellon-zeros-format', 'decimal', '--excellon-oval-format', 'alternate',
                                       '--excellon-separate-th', '--generate-map', '--map-format', 'pdf', '--generate-report',
                                       '--report-path', os.path.join(rep, 'drill_report.txt'), '-o', maps + os.sep, B])
    for f in glob.glob(os.path.join(maps, '*.drl')):           # the map run repeats the drill files; keep only the maps
        os.remove(f)
    if copies == 1:
        P.run('IPC-D-356', [K, 'pcb', 'export', 'ipcd356', '-o', os.path.join(ger, base + '.d356'), B])
    else:
        P.info('IPC-D-356', 'not written: the %d board copies share net names, so a panel netlist would join them' % copies)
    zf = os.path.join(jlc, base + '_JLC_gerbers.zip')
    with zipfile.ZipFile(zf, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(ger)):
            z.write(os.path.join(ger, f), f)

    # ------------------------------------------------------------------ 8. CPL / BOM
    if a.cpl or a.bom:
        for f in (a.cpl, a.bom):
            if f and os.path.isfile(f):
                shutil.copy2(f, jlc)

    # ------------------------------------------------------------------ 9. fab-notes drawing
    if os.path.isfile(a.notes):
        fn = os.path.join(out, 'work_notes')
        os.makedirs(fn, exist_ok=True)
        nb_path = os.path.join(fn, base + '.kicad_pcb')
        shutil.copy2(B, nb_path)
        for ext in ('.kicad_pro',):
            if os.path.isfile(os.path.join(work, base + ext)):
                shutil.copy2(os.path.join(work, base + ext), fn)
        nb = pcbnew.LoadBoard(nb_path)
        bb = nb.GetBoardEdgesBoundingBox()
        t = pcbnew.PCB_TEXT(nb)
        t.SetLayer(pcbnew.Cmts_User)
        t.SetText(open(a.notes, encoding='utf-8').read().rstrip().replace('\t', '    '))
        t.SetTextSize(pcbnew.VECTOR2I(MM(1.2), MM(1.2)))
        t.SetTextThickness(MM(0.15))
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
        t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_TOP)
        t.SetPosition(pcbnew.VECTOR2I(bb.GetRight() + MM(8), bb.GetY()))
        nb.Add(t)
        nb.Save(nb_path)
        P.run('fab-notes PDF', [K, 'pcb', 'export', 'pdf', '--layers', 'Edge.Cuts,User.Comments', '--mode-single',
                                '--scale', '0', '-o', os.path.join(rep, base + '_fab_notes.pdf'), nb_path])

    # ------------------------------------------------------------------ 10. checks
    b = pcbnew.LoadBoard(B)
    txt = open(B, encoding='utf-8').read()
    nCu = b.GetCopperLayerCount()
    P.chk('copper layers = 6 (board file)', nCu == 6, nCu)
    diels = re.findall(r'\(layer "dielectric \d+"(.*?)\n\t\t\t\)', txt, re.S)
    dth = [float(re.search(r'\(thickness ([\d.]+)\)', x).group(1)) for x in diels if re.search(r'\(thickness ([\d.]+)\)', x)]
    P.chk('stackup = JLC06161H-3313 dielectrics %s mm' % (STACKUP_3313,), len(dth) == 5 and all(abs(x - y) < 1e-4 for x, y in zip(dth, STACKUP_3313)), dth)
    mats = re.findall(r'\(material "([^"]+)"\)', txt[:30000])
    P.info('stackup materials (board file)', mats)
    lt = re.findall(r'\(loss_tangent ([\d.]+)\)', txt[:30000])
    P.chk('dielectric loss tangents set (P1-13: dielectric 3 is 0 in the file)', all(float(x) > 0 for x in lt), lt, 'WARN')
    P.info('board thickness (setup)', '%.4f mm' % TO(b.GetDesignSettings().GetBoardThickness()))
    for lay in ('In1.Cu', 'In2.Cu', 'In4.Cu'):
        gz = [z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname() == 'GND' and z.IsOnLayer(b.GetLayerID(lay))]
        P.chk('GND plane zone on %s' % lay, bool(gz))
    m = re.search(r'\(copper_finish "([^"]*)"\)', txt)
    P.chk('copper_finish ENIG (board setup)', bool(m) and m.group(1) == 'ENIG', m.group(1) if m else 'none')
    P.chk('via protection flags (filling yes) (capping yes) = IPC-4761 VII (P1-13; the order form carries the requirement)',
          re.search(r'\(filling yes\)', txt) is not None and re.search(r'\(capping yes\)', txt) is not None,
          'filling %s, capping %s' % (re.findall(r'\(filling (\w+)\)', txt)[:1], re.findall(r'\(capping (\w+)\)', txt)[:1]), 'WARN')
    ds = b.GetDesignSettings()
    P.chk('solder mask expansion 0 (P1-12, JLC LDI 1:1)', abs(TO(ds.m_SolderMaskExpansion)) < 1e-6, '%.3f mm' % TO(ds.m_SolderMaskExpansion), 'WARN')
    j10 = [fp for fp in b.GetFootprints() if fp.GetReference() == 'J10']
    sh = [p for fp in j10 for p in fp.Pads() if p.GetNumber() == 'SH' and p.GetDrillSize().x > 0]
    P.chk('J10 shell legs pasted (pin-in-paste, P1-12)', bool(sh) and all(p.IsOnLayer(pcbnew.F_Paste) for p in sh),
          '%d J10 x 4 SH legs, %d with F.Paste' % (len(j10), sum(p.IsOnLayer(pcbnew.F_Paste) for p in sh)), 'WARN')
    thin = [g for g in b.GetDrawings() if g.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and g.GetClass() == 'PCB_SHAPE' and TO(g.GetWidth()) < 0.15 - 1e-6]
    for fp in b.GetFootprints():
        thin += [g for g in fp.GraphicalItems() if g.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and g.GetClass() == 'PCB_SHAPE' and TO(g.GetWidth()) < 0.15 - 1e-6]
    P.chk('silkscreen lines >= 0.15 mm (JLC minimum; P1-9)', not thin, '%d thinner items' % len(thin), 'WARN')
    small = [(d.GetText(), round(TO(d.GetTextHeight()), 2), round(TO(d.GetTextThickness()), 2)) for d in b.GetDrawings()
             if d.GetClass() == 'PCB_TEXT' and d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and (TO(d.GetTextHeight()) < 1.0 - 1e-6 or TO(d.GetTextThickness()) < 0.15 - 1e-6)]
    P.chk('silkscreen texts >= 1.0 mm high, >= 0.15 mm stroke (JLC; P1-9)', not small, small, 'WARN')

    # holes
    vias = [t for t in b.GetTracks() if t.GetClass() == 'PCB_VIA']
    vsz = collections.Counter((round(TO(v.GetWidth(pcbnew.F_Cu)), 3), round(TO(v.GetDrillValue()), 3)) for v in vias)
    P.info('vias (diameter/drill: count)', ', '.join('%.2f/%.2f: %d' % (k[0], k[1], n) for k, n in sorted(vsz.items())) + ' = %d' % len(vias))
    P.chk('all via drills <= 0.50 mm (JLC: epoxy-filled holes "should not be larger than 0.5 mm")', all(k[1] <= 0.5 for k in vsz), sorted(vsz))
    P.chk('all vias through (no blind/buried/micro)', all(v.GetViaType() == pcbnew.VIATYPE_THROUGH for v in vias))
    ph = collections.Counter()
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetDrillSize().x > 0:
                ph[('NPTH' if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH else 'PTH', round(TO(p.GetDrillSize().x), 3), round(TO(p.GetDrillSize().y), 3))] += 1
    P.info('pad holes (kind, drill x, drill y: count)', ', '.join('%s %.3fx%.3f: %d' % (k[0], k[1], k[2], n) for k, n in sorted(ph.items())))
    pth = glob.glob(os.path.join(ger, '*-PTH.drl'))
    npth = glob.glob(os.path.join(ger, '*-NPTH.drl'))
    P.chk('separate PTH and NPTH Excellon files', len(pth) == 1 and len(npth) == 1, [os.path.basename(x) for x in pth + npth])
    if pth and npth:
        hp, hn = drill_hits(pth[0]), drill_hits(npth[0])
        exp_pth = collections.Counter()
        for (d_, dr), n in vsz.items():
            exp_pth[dr] += n
        for (kind, dx, dy), n in ph.items():
            if kind == 'PTH':
                exp_pth[round(min(dx, dy), 3)] += n
        P.chk('PTH drill hits per tool == vias + plated pad holes in the file', dict(hp) == dict(exp_pth), 'drill %s vs file %s' % (dict(sorted(hp.items())), dict(sorted(exp_pth.items()))))
        P.info('NPTH drill hits per tool', dict(sorted(hn.items())))
        tot = sum(hp.values()) + sum(hn.values())
        bb = b.GetBoardEdgesBoundingBox()
        area = TO(bb.GetWidth()) * TO(bb.GetHeight())
        P.chk('hole density < 150,000 holes/m2 (JLC extra cost above)', tot / area * 1e6 < 150000,
              '%d holes on %.1f x %.1f mm = %.0f /m2' % (tot, TO(bb.GetWidth()), TO(bb.GetHeight()), tot / area * 1e6), 'WARN')
        if is_panel:
            P.chk('panel: 4 tooling holes 2.00 mm in the NPTH file', hn.get(2.0, 0) == 4, hn.get(2.0))
            nb_ = sum(1 for fp in b.GetFootprints() if fp.GetReference().startswith('MB') for p in fp.Pads())
            P.chk('panel: mouse-bite holes 0.60 mm in the NPTH file == MB pads', hn.get(0.6, 0) == nb_, '%s vs %d' % (hn.get(0.6), nb_))

    # Gerbers + job
    found, files = set(), {}
    for f in glob.glob(os.path.join(ger, '*.g*')):
        head = open(f, errors='ignore').read(800)
        m = re.search(r'%TF\.FileFunction,([^*]*)\*%', head)
        if m:
            found.add(m.group(1))
            files[m.group(1)] = os.path.basename(f)
    P.chk('Gerber X2 layer set complete (13 files)', X2_NEED <= found, 'missing %s' % sorted(X2_NEED - found))
    job = glob.glob(os.path.join(ger, '*.gbrjob'))
    if job:
        j = json.load(open(job[0], encoding='utf-8'))
        gs = j.get('GeneralSpecs', {})
        P.chk('Gerber job: LayerNumber = 6', gs.get('LayerNumber') == 6, gs.get('LayerNumber'))
        P.chk('Gerber job: Finish = ENIG', gs.get('Finish') == 'ENIG', gs.get('Finish'))
        sz = gs.get('Size', {})
        P.chk('Gerber job: size >= 70 x 70 mm (JLC Standard PCBA single board or panel)', sz.get('X', 0) >= 70 and sz.get('Y', 0) >= 70, sz,
              'FAIL' if is_panel else 'WARN')
        diel = [x for x in j.get('MaterialStackup', []) if x.get('Type') == 'Dielectric']
        P.chk('Gerber job: dielectrics = JLC06161H-3313', [round(float(x.get('Thickness', 0)), 4) for x in diel] == list(STACKUP_3313),
              [x.get('Thickness') for x in diel])
    else:
        P.chk('Gerber job file present', False)

    # paste on DNP pads
    fl = []
    for key in ('Paste,Top', 'Paste,Bot'):
        if key in files:
            fl += gerber_flashes(os.path.join(ger, files[key]))
    flset = {(round(x, 3), round(y, 3)) for x, y in fl}
    hits = []
    for fp in b.GetFootprints():
        if not fp.IsDNP():
            continue
        for p in fp.Pads():
            c = p.GetPosition()
            if (round(TO(c.x), 3), round(-TO(c.y), 3)) in flset:
                hits.append('%s.%s' % (fp.GetReference(), p.GetNumber()))
    P.chk('no paste on do-not-populate pads (paste Gerbers)', not hits, 'DNP footprints %s (x%d); paste removed on the copy from %d pads; flashes still on %s'
          % (sorted(set(dnp_fps)), copies, len(stripped), hits))

    # mask webs
    mw10 = mask_webs(b, 0.10)
    P.chk('solder-mask webs >= 0.10 mm between different nets as plotted (JLC green 1 oz dam)', not mw10,
          '%d below 0.10 mm, by footprint %s' % (len(mw10), dict(collections.Counter(re.sub(r'_\d+$', '', x[1].split('.')[0]) for x in mw10))), 'WARN')

    # S04: no copper between the Y2 pads on its own layer (SII SC-16S / ABS05 'no pattern under the crystal')
    s04 = []
    for y2 in [fp for fp in b.GetFootprints() if fp.GetReference() == 'Y2']:
        lay = y2.GetLayer()
        pads = list(y2.Pads())
        if len(pads) >= 2:
            p1, p2 = pads[0].GetPosition(), pads[1].GetPosition()
            pts = [pcbnew.VECTOR2I(int(p1.x + (p2.x - p1.x) * f), int(p1.y + (p2.y - p1.y) * f)) for f in (0.35, 0.5, 0.65)]
            trk = [t for t in b.GetTracks() if t.GetClass() in ('PCB_TRACK', 'PCB_ARC') and t.GetLayer() == lay and any(t.HitTest(q, MM(0.05)) for q in pts)]
            via = [t for t in b.GetTracks() if t.GetClass() == 'PCB_VIA' and any(t.HitTest(q, MM(0.05)) for q in pts)]
            opad = [p for fp in b.GetFootprints() if fp.m_Uuid.AsString() != y2.m_Uuid.AsString() for p in fp.Pads() if p.IsOnLayer(lay) and any(p.HitTest(q, MM(0.05)) for q in pts)]
            zon = [z.GetNetname() for z in b.Zones() if not z.GetIsRuleArea() and z.IsOnLayer(lay) and any(z.HitTestFilledArea(lay, q) for q in pts)]
            s04.append('Y2 at (%.2f, %.2f) %s: tracks %d, vias %s, pads %d, pours %s' % (
                TO(y2.GetPosition().x), TO(y2.GetPosition().y), y2.GetLayerName(), len(trk),
                ['%s (%.3f, %.3f) %.2f/%.2f' % (v.GetNetname(), TO(v.GetPosition().x), TO(v.GetPosition().y), TO(v.GetWidth(pcbnew.F_Cu)), TO(v.GetDrillValue())) for v in via],
                len(opad), zon) if (trk or via or opad or zon) else '')
    if s04:
        bad = [x for x in s04 if x]
        P.chk('S04: no copper between the Y2 pads on its layer (SII SC-16S / ABS05 "no pattern under the crystal"; tracks, vias, pads, pours)',
              not bad, bad, 'WARN')

    # DRC
    for k, d in drc.items():
        P.info('DRC %s' % k, d)
    if not is_panel:
        d = drc.get('refilled', {})
        P.chk('DRC (refilled copy, project rules + schematic parity): 0 errors', d.get('errors', 1) == 0,
              '%s errors %s; %s unconnected; %s parity items (all severities)' % (d.get('errors'), d.get('error_types'), d.get('unconnected'), d.get('parity')))
        if 'signoff' in drc:
            d = drc['signoff']
            P.chk('DRC with the %d #SIGNOFF rules: 0 errors' % d.get('signoff_lines_enabled', 0), d.get('errors', 1) == 0,
                  '%s errors %s' % (d.get('errors'), d.get('error_types')))
        if 'saved' in drc and 'refilled' in drc:
            P.chk('saved zone fill is current (DRC saved == refilled error count)', drc['saved']['errors'] == drc['refilled']['errors'],
                  'saved %s vs refilled %s errors: refill and save before plotting from the project' % (drc['saved']['errors'], drc['refilled']['errors']), 'WARN')
    else:
        P.info('panel DRC', 'see panel_report.json (make_panel.py --drc classifies inherited / shared-net / NEW violations)')

    # CPL / BOM
    if a.cpl and a.bom and os.path.isfile(a.cpl) and os.path.isfile(a.bom):
        bom_refs = [x.strip() for r in csv.DictReader(open(a.bom, encoding='utf-8-sig')) for x in r['Designator'].split(',') if x.strip()]
        cpl_refs = [r['Designator'] for r in csv.DictReader(open(a.cpl, encoding='utf-8-sig'))]
        P.chk('BOM designators == CPL designators, each once', set(bom_refs) == set(cpl_refs) and len(bom_refs) == len(set(bom_refs)) and len(cpl_refs) == len(set(cpl_refs)),
              'BOM %d, CPL %d, BOM-only %s, CPL-only %s' % (len(bom_refs), len(cpl_refs), sorted(set(bom_refs) - set(cpl_refs))[:6], sorted(set(cpl_refs) - set(bom_refs))[:6]))
        # every CPL row must sit on a placed footprint of THIS file (position and side); panel rows are REF_<copy>
        cpl_rows = list(csv.DictReader(open(a.cpl, encoding='utf-8-sig')))
        placed = [fp for fp in b.GetFootprints() if not fp.IsDNP() and not (fp.GetAttributes() & (pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_BOARD_ONLY))]
        byref = collections.defaultdict(list)
        for fp in placed:
            byref[fp.GetReference()].append((TO(fp.GetPosition().x), -TO(fp.GetPosition().y), fp.IsFlipped()))
        miss, used = [], collections.Counter()
        for r in cpl_rows:
            base_ref = re.sub(r'_\d+$', '', r['Designator']) if copies > 1 else r['Designator']
            x, y = float(r['Mid X'].replace('mm', '')), float(r['Mid Y'].replace('mm', ''))
            hit = [c for c in byref.get(base_ref, []) if abs(c[0] - x) < 0.005 and abs(c[1] - y) < 0.005 and c[2] == r['Layer'].lower().startswith('b')]
            if hit:
                used[(base_ref, hit[0][:2])] += 1
            else:
                miss.append(r['Designator'])
        unused = sum(len(v) for v in byref.values()) - len(used)
        P.chk('every CPL row sits on a placed footprint of this file (position, side) and every placed footprint has one row',
              not miss and unused == 0 and all(n == 1 for n in used.values()),
              '%d rows, %d placed footprints, rows without a footprint %s, footprints without a row %d' % (len(cpl_rows), len(placed), miss[:6], unused))

    P.info('outputs', sorted(os.path.relpath(f, out) for f in glob.glob(os.path.join(out, 'jlc', '**', '*'), recursive=True) if os.path.isfile(f)))
    P.chk('source file unchanged', sha256(src) == src_hash)
    nf = P.finish()
    print('\nUpload (only after the lead approves): %s  +  the CPL/BOM in %s' % (zf, jlc))
    sys.exit(1 if nf else 0)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""make_panel.py - JLC Standard-PCBA panel for RFVD SENSOR-D Rev A (fix plan P1-10, decision D27).

Run with KiCad 10's python (needs pcbnew, shapely and PIL, as the handoff tools/ do):
  "C:/Program Files/KiCad/10.0/bin/python.exe" make_panel.py BOARD.kicad_pcb OUT_DIR [options]

The input board is only read. Everything is written below OUT_DIR, which must not be the board's own folder.

Steps
  1. Copy the board's project files (.kicad_pcb/.kicad_pro/.kicad_dru) to OUT_DIR/board_refilled/ and refill the zones
     there (kicad-cli pcb drc --refill-zones --save-board). The saved fill of a working board can be stale: on base_cp2a
     the saved fill gave 69 clearance errors that a refill removes. --no-refill keeps the saved fill.
  2. Build the panel from that copy:
     - N x 1 copies (--cols, default 2) of the REAL outline: the four r = 3 mm corners and the W-edge notch are kept;
     - copies alternate 0 / 180 deg (--same-orientation turns this off). Every board then has the same tab positions
       (board-local W 64.5/78.5, E 90.74/104.74 by default; the E pair is symmetric about the board centre so the
       centre gap pairs E edge with E edge), each board is held on both sides over y 62-107, and a panel loaded
       180 deg wrong still puts every part on matching pads;
     - routed gaps (--gap, JLC: "The spacing between boards should be >= 2 mm");
     - rails on the two outer 90 mm edges (--rail, JLC SMT recommendation 5 mm; widened if the panel would be under
       --min-size, JLC Standard PCBA panel minimum 70 x 70 mm);
     - mouse-bite tabs at the board-local tab lists --tabs-w / --tabs-e (JLC: 0.60 mm holes, 0.35-0.4 mm hole edge to
       hole edge, 5-8 holes per set, holes extending one third into the board);
     - 3 fiducials per side on F AND B (1.0 mm copper, 2.0 mm mask opening, centred 3.85 mm from the panel edge);
     - 4 x 2.0 mm NPTH tooling holes on the rails, one corner offset by --tool-offset;
     - footprint references stay as they are in every copy (the .kicad_dru has rules keyed on references such as
       H1-H4 and U301; renaming them made DRC report 400 false errors). The copy suffix _<n> exists only in the
       panel CPL/BOM.
  3. Check every tab against the board: component courtyards >= --min-courtyard (3.0 mm), copper (pads, tracks, vias)
     >= --min-copper (1.0 mm), zone fill to the bite holes >= the board's hole clearance; MLCCs closer than
     --advise (5.0 mm) are listed. Check the tab spans sit on straight edges, the panel is >= --min-size in both
     directions, no courtyard leaves its board outline, and the new Edge.Cuts closes.
  4. --cpl/--bom: write the panel CPL and BOM ("Complete File": one CPL row per placement on the panel, designators
     REF_<n>) from the single-board JLC CPL/BOM written by tools/make_outputs.py, then cross-check them against the
     panel's own kicad-cli position export.
  5. --drc: kicad-cli DRC on the refilled board and on the panel; every panel violation is classified as inherited
     from the board, a shared-net artefact (the copies share net names), or NEW. Any NEW error fails the run.
  6. --render: kicad-cli 3D renders (top, bottom) and a 2D PNG of the panel with the tab keep-outs.
  --suggest prints, for every straight edge, where a tab would pass the checks, then exits.

Exit codes: 0 ok, 2 usage or input error, 3 tab/geometry check failed, 4 CPL/BOM check failed, 5 NEW DRC errors.
"""
import argparse
import collections
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys

import pcbnew
from shapely.geometry import LineString, Point, Polygon

KCLI_DEFAULT = r'C:/Program Files/KiCad/10.0/bin/kicad-cli.exe'
FID_LIB = r'C:/Program Files/KiCad/10.0/share/kicad/footprints/Fiducial.pretty'
FID_NAME = 'Fiducial_1mm_Mask2mm'
MM, TO = pcbnew.FromMM, pcbnew.ToMM
PANEL_REFS = re.compile(r'^(MB|TH|FID)\d+$')


def V(x, y):
    return pcbnew.VECTOR2I(int(round(x)), int(round(y)))


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


def run(cmd, timeout=1800):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    tail = [l for l in (r.stdout + r.stderr).splitlines() if l.strip() and 'memory leak' not in l]
    return r.returncode, tail


def dup(item):
    try:
        d = item.Duplicate(False)
    except TypeError:
        d = item.Duplicate()
    return d.Cast() if hasattr(d, 'Cast') else d


# ----------------------------------------------------------------------------------------------- outline geometry
def edge_shapes(board):
    return [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts and d.GetClass() == 'PCB_SHAPE']


def shape_points(sh, n_arc=48):
    """Polyline (mm) of an Edge.Cuts shape, in drawing order start -> end."""
    s, e = sh.GetStart(), sh.GetEnd()
    if sh.GetShape() == pcbnew.SHAPE_T_SEGMENT:
        return [(TO(s.x), TO(s.y)), (TO(e.x), TO(e.y))]
    if sh.GetShape() == pcbnew.SHAPE_T_ARC:
        c, m = sh.GetCenter(), sh.GetArcMid()
        cx, cy, r = TO(c.x), TO(c.y), TO(sh.GetRadius())
        a0 = math.atan2(TO(s.y) - cy, TO(s.x) - cx)
        a1 = math.atan2(TO(e.y) - cy, TO(e.x) - cx)
        am = math.atan2(TO(m.y) - cy, TO(m.x) - cx)
        span = (a1 - a0) % (2 * math.pi)
        if (am - a0) % (2 * math.pi) > span:
            span -= 2 * math.pi
        return [(cx + r * math.cos(a0 + span * i / n_arc), cy + r * math.sin(a0 + span * i / n_arc)) for i in range(n_arc + 1)]
    raise ValueError('unsupported Edge.Cuts shape %s (only segments and arcs are handled)' % sh.SHAPE_T_asString())


def outline_polygon(shapes):
    """Chain the Edge.Cuts shapes into closed loops; return (largest loop polygon, number of loops)."""
    segs = [shape_points(s) for s in shapes]
    key = lambda p: (round(p[0], 4), round(p[1], 4))
    used, loops = [False] * len(segs), []
    for i0 in range(len(segs)):
        if used[i0]:
            continue
        used[i0] = True
        pts = list(segs[i0])
        while key(pts[-1]) != key(pts[0]):
            for j in range(len(segs)):
                if used[j]:
                    continue
                if key(segs[j][0]) == key(pts[-1]):
                    pts += segs[j][1:]
                    used[j] = True
                    break
                if key(segs[j][-1]) == key(pts[-1]):
                    pts += segs[j][::-1][1:]
                    used[j] = True
                    break
            else:
                raise ValueError('Edge.Cuts does not close near (%.4f, %.4f)' % pts[-1])
        loops.append(Polygon(pts))
    loops.sort(key=lambda p: -p.area)
    return loops[0], len(loops)


def straight_spans(shapes, x_mm, tol=1e-4):
    out = []
    for s in shapes:
        if s.GetShape() != pcbnew.SHAPE_T_SEGMENT:
            continue
        a, b = s.GetStart(), s.GetEnd()
        if abs(TO(a.x) - x_mm) < tol and abs(TO(b.x) - x_mm) < tol:
            out.append(tuple(sorted((TO(a.y), TO(b.y)))))
    return sorted(out)


# ----------------------------------------------------------------------------------------------- board items (local)
def polys_of(ps):
    out = []
    for i in range(ps.OutlineCount()):
        o = ps.Outline(i)
        pts = [(TO(o.CPoint(k).x), TO(o.CPoint(k).y)) for k in range(o.PointCount())]
        if len(pts) >= 3:
            pg = Polygon(pts)
            out.append(pg if pg.is_valid else pg.buffer(0))
    return out


def is_component(fp):
    a = fp.GetAttributes()
    return not (fp.IsDNP() or (a & pcbnew.FP_EXCLUDE_FROM_BOM) or (a & pcbnew.FP_EXCLUDE_FROM_POS_FILES) or (a & pcbnew.FP_BOARD_ONLY))


def collect_items(board):
    """Polygons of the board in local (board) coordinates for the tab checks."""
    items = collections.defaultdict(list)       # kind -> [(label, polygon)]
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        lib = str(fp.GetFPID().GetLibItemName())
        comp = is_component(fp)
        for lay in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            for pg in polys_of(fp.GetCourtyard(lay)):
                items['courtyard_all'].append((ref, pg))
                if comp:
                    items['courtyard'].append((ref, pg))
                    if ref.startswith('C') and lib.startswith('C_'):
                        items['mlcc'].append((ref, pg))
        for p in fp.Pads():
            ps = pcbnew.SHAPE_POLY_SET()
            for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
                if p.IsOnLayer(lay):
                    p.TransformShapeToPolygon(ps, lay, 0, MM(0.005), pcbnew.ERROR_OUTSIDE)
            for pg in polys_of(ps):
                items['copper'].append(('%s.%s' % (ref, p.GetNumber()), pg))
            if p.GetDrillSize().x > 0:
                c = p.GetPosition()
                r = TO(max(p.GetDrillSize().x, p.GetDrillSize().y)) / 2
                items['copper'].append(('%s.%s hole' % (ref, p.GetNumber()), Point(TO(c.x), TO(c.y)).buffer(r, 16)))
    for t in board.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            c = t.GetPosition()
            items['copper'].append(('via %s' % t.GetNetname(), Point(TO(c.x), TO(c.y)).buffer(TO(t.GetWidth(pcbnew.F_Cu)) / 2, 16)))
        elif t.GetClass() == 'PCB_ARC':
            s, m, e = t.GetStart(), t.GetMid(), t.GetEnd()
            ls = LineString([(TO(s.x), TO(s.y)), (TO(m.x), TO(m.y)), (TO(e.x), TO(e.y))])
            items['copper'].append(('arc %s %s' % (t.GetLayerName(), t.GetNetname()), ls.buffer(TO(t.GetWidth()) / 2, 8)))
        else:
            s, e = t.GetStart(), t.GetEnd()
            ls = LineString([(TO(s.x), TO(s.y)), (TO(e.x), TO(e.y))]) if (s.x, s.y) != (e.x, e.y) else Point(TO(s.x), TO(s.y))
            items['copper'].append(('track %s %s' % (t.GetLayerName(), t.GetNetname()), ls.buffer(TO(t.GetWidth()) / 2, 8)))
    for z in board.Zones():
        if z.GetIsRuleArea():
            continue
        for lay in z.GetLayerSet().CuStack():
            if z.HasFilledPolysForLayer(lay):
                for pg in polys_of(z.GetFilledPolysList(lay)):
                    items['fill'].append(('%s %s' % (board.GetLayerName(lay), z.GetNetname()), pg))
    return items


def nearest(items, geom, maxd=12.0):
    best, lab, close = 99.0, '', []
    gb = geom.bounds
    for l, pg in items:
        b = pg.bounds
        if b[0] > gb[2] + maxd or b[2] < gb[0] - maxd or b[1] > gb[3] + maxd or b[3] < gb[1] - maxd:
            continue
        d = geom.distance(pg)
        close.append((d, l))
        if d < best:
            best, lab = d, l
    return best, lab, sorted(close)


# ----------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('board')
    ap.add_argument('out_dir')
    ap.add_argument('--name', default=None, help='panel basename (default <board>_panel)')
    ap.add_argument('--cols', type=int, default=2)
    ap.add_argument('--same-orientation', action='store_true', help='do not rotate every second copy by 180 deg')
    ap.add_argument('--gap', type=float, default=2.0)
    ap.add_argument('--rail', type=float, default=5.0)
    ap.add_argument('--min-size', type=float, default=70.0)
    ap.add_argument('--tabs-w', default='64.5,78.5', help='tab centres (board y, mm) on the board W edge')
    ap.add_argument('--tabs-e', default='90.7434,104.7434', help='tab centres (board y, mm) on the board E edge')
    ap.add_argument('--tab-width', type=float, default=5.0)
    ap.add_argument('--holes', type=int, default=5)
    ap.add_argument('--hole-d', type=float, default=0.60)
    ap.add_argument('--hole-pitch', type=float, default=0.95)
    ap.add_argument('--bite-inset', type=float, default=1.0 / 3, help='fraction of the hole diameter inside the board')
    ap.add_argument('--tool-d', type=float, default=2.0)
    ap.add_argument('--tool-edge', type=float, default=5.0, help='tooling-hole centre distance from the top/bottom panel edge')
    ap.add_argument('--tool-offset', type=float, default=5.0, help='extra offset of the bottom-right tooling hole')
    ap.add_argument('--fid-edge', type=float, default=3.85, help='fiducial centre distance from the outer rail edge')
    ap.add_argument('--fid-y', default='20,-20,30', help='fiducial y offsets: left rail from top, left rail from bottom (neg), right rail from top')
    ap.add_argument('--min-courtyard', type=float, default=3.0)
    ap.add_argument('--min-copper', type=float, default=1.0)
    ap.add_argument('--advise', type=float, default=5.0)
    ap.add_argument('--no-refill', action='store_true')
    ap.add_argument('--cpl', help='single-board JLC CPL (tools/make_outputs.py outputs/RFVD_JLCPCB_CPL.csv)')
    ap.add_argument('--bom', help='single-board JLC BOM (tools/make_outputs.py outputs/RFVD_JLCPCB_BOM.csv)')
    ap.add_argument('--drc', action='store_true', help='DRC the refilled board and the panel and classify the panel violations')
    ap.add_argument('--render', action='store_true', help='3D renders + 2D PNG of the panel (copies libraries/ for the 3D models)')
    ap.add_argument('--suggest', action='store_true', help='print where tabs would pass the checks and exit')
    ap.add_argument('--kicad-cli', default=KCLI_DEFAULT)
    a = ap.parse_args()

    src = os.path.abspath(a.board)
    if not os.path.isfile(src) or not src.endswith('.kicad_pcb'):
        print('ERROR: not a .kicad_pcb file: %s' % src)
        sys.exit(2)
    src_dir, base = os.path.dirname(src), os.path.splitext(os.path.basename(src))[0]
    out = os.path.abspath(a.out_dir)
    if os.path.normcase(out) == os.path.normcase(src_dir):
        print('ERROR: OUT_DIR must not be the board folder')
        sys.exit(2)
    name = a.name or base + '_panel'
    os.makedirs(out, exist_ok=True)
    src_hash = sha256(src)
    report = dict(input=dict(board=src, sha256=src_hash), errors=[], warnings=[])
    err, warn = report['errors'], report['warnings']

    # ---------------- 1. refilled copy -------------------------------------------------------------------
    work = os.path.join(out, 'board_refilled')
    os.makedirs(work, exist_ok=True)
    for ext in ('.kicad_pcb', '.kicad_pro', '.kicad_dru'):
        if os.path.isfile(os.path.join(src_dir, base + ext)):
            shutil.copy2(os.path.join(src_dir, base + ext), os.path.join(work, base + ext))
    bfile = os.path.join(work, base + '.kicad_pcb')
    if not a.no_refill:
        rc, tail = run([a.kicad_cli, 'pcb', 'drc', '--all-track-errors', '--refill-zones', '--save-board', '--format', 'json', '--severity-all',
                        '--units', 'mm', '-o', os.path.join(work, 'drc_board_refilled.json'), bfile])
        if rc not in (0, 5) or not os.path.isfile(os.path.join(work, 'drc_board_refilled.json')):
            print('ERROR: refill failed:', tail); sys.exit(2)
        report['refill'] = 'kicad-cli pcb drc --refill-zones --save-board on %s' % bfile
    else:
        warn.append('zones NOT refilled (--no-refill): the panel uses the saved fill of the input board')
    b = pcbnew.LoadBoard(bfile)
    shapes = edge_shapes(b)
    poly, nloops = outline_polygon(shapes)
    if nloops != 1:
        warn.append('Edge.Cuts has %d closed loops (cut-outs?); only the outer loop is used for the checks' % nloops)
    x0, y0, x1, y1 = poly.bounds
    W, H = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    lw = TO(shapes[0].GetWidth()) if shapes else 0.05
    report['board'] = dict(outline_x=[round(x0, 4), round(x1, 4)], outline_y=[round(y0, 4), round(y1, 4)],
                           width=round(W, 4), height=round(H, 4), edge_line_width=lw,
                           bbox_incl_line=[round(W + lw, 3), round(H + lw, 3)], copper_layers=b.GetCopperLayerCount())
    spans = {'W': straight_spans(shapes, x0), 'E': straight_spans(shapes, x1)}
    report['board']['straight_edges'] = {k: [[round(p, 4), round(q, 4)] for p, q in v] for k, v in spans.items()}
    items = collect_items(b)
    ds = b.GetDesignSettings()
    hole_clr = TO(ds.m_HoleClearance)
    inset = a.bite_inset * a.hole_d
    xedge = {'W': x0, 'E': x1}

    def tab_check(edge, y, width):
        """Clearance of a tab (perforation line on the local edge) in board coordinates."""
        x = xedge[edge]
        line = LineString([(x, y - width / 2), (x, y + width / 2)])
        res = dict(edge=edge, y=round(y, 4))
        on = [s for s in spans[edge] if s[0] - 1e-6 <= y - width / 2 and y + width / 2 <= s[1] + 1e-6]
        res['on_straight_edge'] = bool(on)
        if on:
            res['margin_to_edge_end'] = round(min(y - width / 2 - on[0][0], on[0][1] - y - width / 2), 3)
        for kind in ('courtyard', 'mlcc', 'copper', 'fill'):
            d, lab, close = nearest(items[kind], line)
            res[kind] = [round(d, 3), lab]
            if kind in ('courtyard', 'mlcc'):
                res[kind + '_within_advise'] = [[round(dd, 2), ll] for dd, ll in close if dd < a.advise]
        res['fill_to_bite_hole'] = round(res['fill'][0] - inset, 3)
        ok = (res['on_straight_edge'] and res.get('margin_to_edge_end', 0) >= 0.2 and res['courtyard'][0] >= a.min_courtyard
              and res['copper'][0] >= a.min_copper and res['fill_to_bite_hole'] >= hole_clr - 1e-6)
        res['ok'] = ok
        return res

    if a.suggest:
        for edge in ('W', 'E'):
            print('=== %s edge x = %.4f (straight spans %s)' % (edge, xedge[edge], spans[edge]))
            for lo, hi in spans[edge]:
                y = lo + a.tab_width / 2 + 0.2
                while y <= hi - a.tab_width / 2 - 0.2 + 1e-9:
                    r = tab_check(edge, y, a.tab_width)
                    if r['ok']:
                        print('  y %7.2f  courtyard %5.2f %-7s mlcc %5.2f %-6s copper %5.2f fill->hole %4.2f' % (
                            y, r['courtyard'][0], r['courtyard'][1], r['mlcc'][0], r['mlcc'][1], r['copper'][0], r['fill_to_bite_hole']))
                    y += 0.5
        sys.exit(0)

    # ---------------- 2. layout -------------------------------------------------------------------------
    cols = max(1, a.cols)
    rot = [180 if (not a.same_orientation and k % 2 == 1) else 0 for k in range(cols)]
    dxs = [k * (W + a.gap) for k in range(cols)]
    inner = cols * W + (cols - 1) * a.gap
    rail = max(a.rail, (a.min_size - inner - 2 * a.gap) / 2.0)
    X0, X1 = x0 - a.gap - rail, x0 + inner + a.gap + rail
    Y0, Y1 = y0, y1
    PW, PH = X1 - X0, Y1 - Y0
    report['panel'] = dict(name=name, cols=cols, rotation=rot, dx=[round(d, 4) for d in dxs], gap=a.gap, rail=round(rail, 4),
                           x=[round(X0, 4), round(X1, 4)], y=[round(Y0, 4), round(Y1, 4)],
                           size_mm=[round(PW, 3), round(PH, 3)], size_incl_line_mm=[round(PW + lw, 3), round(PH + lw, 3)])
    if min(PW, PH) < a.min_size - 1e-9:
        err.append('panel %.3f x %.3f mm is below the %.0f mm minimum' % (PW, PH, a.min_size))

    def to_panel(k, x, y):
        if rot[k]:
            x, y = 2 * cx - x, 2 * cy - y
        return x + dxs[k], y

    def side_of(k, edge):                      # panel side ('L' / 'R') of a local edge of copy k
        return ('L' if edge == 'W' else 'R') if rot[k] == 0 else ('R' if edge == 'W' else 'L')

    def local_edge(k, side):
        return [e for e in ('W', 'E') if side_of(k, e) == side][0]

    tabs_local = {'W': [float(v) for v in a.tabs_w.split(',') if v.strip()], 'E': [float(v) for v in a.tabs_e.split(',') if v.strip()]}
    # gaps: ('railL', None, 0) ... ('mid', k, k+1) ... ('railR', last, None)
    gaps = [('railL', None, 0)] + [('mid', k, k + 1) for k in range(cols - 1)] + [('railR', cols - 1, None)]
    tabs = []                                   # dict(gap, y, left=(k|None), right=(k|None))
    for g, kl, kr in gaps:
        ys = []
        if kl is not None:
            e = local_edge(kl, 'R')
            ys += [to_panel(kl, xedge[e], yl)[1] for yl in tabs_local[e]]
        if kr is not None:
            e = local_edge(kr, 'L')
            ys += [to_panel(kr, xedge[e], yl)[1] for yl in tabs_local[e]]
        merged = []
        for y in sorted(ys):
            if merged and abs(y - merged[-1][-1]) < 0.05:
                merged[-1].append(y)
            else:
                merged.append([y])
        for grp in merged:
            tabs.append(dict(gap=g, y=sum(grp) / len(grp), left=kl, right=kr))

    # tab checks on every board side a tab touches (local coordinates)
    cache = {}
    for t in tabs:
        t['checks'] = []
        for k, side in ((t['left'], 'R'), (t['right'], 'L')):
            if k is None:
                continue
            e = local_edge(k, side)
            yl = t['y'] if rot[k] == 0 else 2 * cy - t['y']
            key = (e, round(yl, 3))
            if key not in cache:
                cache[key] = tab_check(e, yl, a.tab_width)
            c = dict(cache[key])
            c['copy'] = k + 1
            t['checks'].append(c)
            if not c['ok']:
                err.append('tab %s y %.2f: copy %d %s edge (local y %.2f) fails: on_straight=%s courtyard %s copper %s fill->hole %s'
                           % (t['gap'], t['y'], k + 1, e, yl, c['on_straight_edge'], c['courtyard'], c['copper'], c['fill_to_bite_hole']))
            for dd, ll in c['mlcc_within_advise']:
                warn.append('tab %s y %.2f: MLCC %s %.2f mm from the perforation line (copy %d, advisory < %.1f mm)' % (t['gap'], t['y'], ll, dd, k + 1, a.advise))

    # every courtyard must stay inside its own board outline (nothing may hang into a gap or a rail)
    over = []
    for ref, pg in items['courtyard_all']:
        if not pg.within(poly.buffer(1e-3)):
            out_d = pg.difference(poly).area
            if out_d > 1e-4:
                over.append((ref, round(out_d, 4)))
    report['courtyards_outside_outline'] = over
    if over:
        err.append('courtyards outside the board outline: %s' % over)

    # ---------------- 3. build ---------------------------------------------------------------------------
    C = V(MM(cx), MM(cy))
    orig_fps = list(b.GetFootprints())
    orig_tracks = list(b.GetTracks())
    orig_zones = list(b.Zones())
    orig_draw = [d for d in b.GetDrawings() if d.GetLayer() != pcbnew.Edge_Cuts]
    single = {fp.GetReference(): (TO(fp.GetPosition().x), TO(fp.GetPosition().y), fp.IsFlipped(), fp.GetOrientationDegrees())
              for fp in orig_fps}
    nets_items = set()                       # nets with at least one connectable item (for the panel DRC count)
    for fp in orig_fps:
        nets_items.update(p.GetNetname() for p in fp.Pads() if p.GetNetCode() > 0)
    nets_items.update(t.GetNetname() for t in orig_tracks if t.GetNetCode() > 0)
    nets_items.update(z.GetNetname() for z in orig_zones if not z.GetIsRuleArea() and z.GetNetCode() > 0)

    def place(item, k):
        if rot[k]:
            item.Rotate(C, pcbnew.EDA_ANGLE(180.0, pcbnew.DEGREES_T))
        if dxs[k]:
            item.Move(V(MM(dxs[k]), 0))

    for k in range(1, cols):
        for fp in orig_fps:
            d = dup(fp)
            place(d, k)
            b.Add(d)
        for t in orig_tracks:
            d = dup(t); place(d, k); b.Add(d)
        for z in orig_zones:
            d = dup(z); place(d, k); b.Add(d)
        for g in orig_draw:
            d = dup(g); place(d, k); b.Add(d)

    # Edge.Cuts: board outlines (cut at the tabs), rails, tab sides
    W_NM = MM(lw)
    new_edges = []

    def seg(p, q):
        s = pcbnew.PCB_SHAPE(b)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetStart(V(*p)); s.SetEnd(V(*q)); s.SetWidth(W_NM)
        b.Add(s); new_edges.append(s)

    half = MM(a.tab_width / 2)
    tab_iv = collections.defaultdict(list)     # (x_nm) -> [(ylo_nm, yhi_nm)]
    edge_x_nm = {}                              # (k, side) -> x_nm
    for k in range(cols):
        for side, e in (('L', local_edge(k, 'L')), ('R', local_edge(k, 'R'))):
            edge_x_nm[(k, side)] = int(round(MM(to_panel(k, xedge[e], cy)[0])))
    railL_x, railR_x = int(round(MM(X0 + rail))), int(round(MM(X1 - rail)))
    for t in tabs:
        yc = int(round(MM(t['y'])))
        xl = railL_x if t['left'] is None else edge_x_nm[(t['left'], 'R')]
        xr = railR_x if t['right'] is None else edge_x_nm[(t['right'], 'L')]
        t['x_nm'] = (xl, xr)
        t['y_nm'] = (yc - half, yc + half)
        tab_iv[xl].append((yc - half, yc + half))
        tab_iv[xr].append((yc - half, yc + half))
        seg((xl, yc - half), (xr, yc - half))
        seg((xl, yc + half), (xr, yc + half))

    def cut_vertical(x, ylo, yhi):
        pieces, cur = [], ylo
        for a_, b_ in sorted(tab_iv.get(x, [])):
            if b_ <= ylo or a_ >= yhi:
                continue
            if a_ > cur:
                pieces.append((cur, a_))
            cur = max(cur, b_)
        if cur < yhi:
            pieces.append((cur, yhi))
        return pieces

    for s in shapes:                            # originals: removed, re-added per copy
        b.Remove(s)
    used_iv = collections.Counter()
    for k in range(cols):
        for s in shapes:
            d = dup(s)
            place(d, k)
            if d.GetShape() == pcbnew.SHAPE_T_SEGMENT and d.GetStart().x == d.GetEnd().x and d.GetStart().x in tab_iv:
                x = d.GetStart().x
                ylo, yhi = sorted((d.GetStart().y, d.GetEnd().y))
                for p, q in cut_vertical(x, ylo, yhi):
                    seg((x, p), (x, q))
                for iv in tab_iv[x]:
                    if ylo <= iv[0] and iv[1] <= yhi:
                        used_iv[(x, iv)] += 1
            else:
                b.Add(d); new_edges.append(d)
    X0n, X1n, Y0n, Y1n = int(round(MM(X0))), int(round(MM(X1))), int(round(MM(Y0))), int(round(MM(Y1)))
    for xo, xi in ((X0n, railL_x), (X1n, railR_x)):
        seg((xo, Y0n), (xo, Y1n))
        seg((xo, Y0n), (xi, Y0n))
        seg((xo, Y1n), (xi, Y1n))
        for p, q in cut_vertical(xi, Y0n, Y1n):
            seg((xi, p), (xi, q))
        for iv in tab_iv[xi]:
            used_iv[(xi, iv)] += 1
    missing = [(TO(x), TO(iv[0]), TO(iv[1])) for x, ivs in tab_iv.items() for iv in ivs if used_iv[(x, iv)] == 0]
    if missing:
        err.append('tab spans not on a straight edge of their board/rail: %s' % missing)
    ends = collections.Counter()
    for s in new_edges:
        for p in (s.GetStart(), s.GetEnd()):
            ends[(p.x, p.y)] += 1
    odd = [(TO(x), TO(y)) for (x, y), n in ends.items() if n % 2]
    report['edge_cuts'] = dict(items=len(new_edges), open_endpoints=odd)
    if odd:
        err.append('panel Edge.Cuts is open at %s' % odd[:6])

    # ---------------- 4. panel features -------------------------------------------------------------------
    ATTR = pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_BOARD_ONLY
    counter = collections.Counter()

    def npth_fp(prefix, holes_mm, dia):
        counter[prefix] += 1
        fp = pcbnew.FOOTPRINT(b)
        fp.SetReference('%s%d' % (prefix, counter[prefix]))
        fp.SetValue('PANEL_NPTH_%.2f' % dia)
        fp.SetPosition(V(MM(holes_mm[0][0]), MM(holes_mm[0][1])))
        for hx, hy in holes_mm:
            pad = pcbnew.PAD(fp)
            pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
            try:
                pad.SetShape(pcbnew.PADSTACK.ALL_LAYERS, pcbnew.PAD_SHAPE_CIRCLE)
                pad.SetSize(pcbnew.PADSTACK.ALL_LAYERS, V(MM(dia), MM(dia)))
            except (TypeError, AttributeError):
                pad.SetShape(pcbnew.F_Cu, pcbnew.PAD_SHAPE_CIRCLE)
                pad.SetSize(pcbnew.F_Cu, V(MM(dia), MM(dia)))
            pad.SetDrillSize(V(MM(dia), MM(dia)))
            pad.SetLayerSet(pcbnew.PAD.UnplatedHoleMask())
            pad.SetPosition(V(MM(hx), MM(hy)))
            pad.SetNumber('')
            fp.Add(pad)
        fp.SetAttributes(ATTR)
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        b.Add(fp)
        return fp

    bites = []
    off = a.hole_d / 2 - inset                     # hole centre outside the board edge by this much
    for t in tabs:
        yc = t['y']
        ys = [yc + (j - (a.holes - 1) / 2) * a.hole_pitch for j in range(a.holes)]
        t['bite_rows'] = []
        for k, side in ((t['left'], 'R'), (t['right'], 'L')):
            if k is None:
                continue
            xe = TO(edge_x_nm[(k, side)])
            xh = xe + off if side == 'R' else xe - off
            fp = npth_fp('MB', [(xh, y) for y in ys], a.hole_d)
            bites.append(fp.GetReference())
            t['bite_rows'].append(dict(ref=fp.GetReference(), copy=k + 1, x=round(xh, 4), y=[round(y, 4) for y in ys]))
    ends_web = (a.tab_width - (a.holes - 1) * a.hole_pitch - a.hole_d) / 2
    report['mouse_bites'] = dict(hole_d=a.hole_d, pitch=a.hole_pitch, web=round(a.hole_pitch - a.hole_d, 3), end_web=round(ends_web, 3),
                                 holes_per_row=a.holes, inside_board=round(inset, 3), rows=len(bites))
    if ends_web < 0.2:
        err.append('tab too narrow for %d holes (end web %.2f mm)' % (a.holes, ends_web))

    th = [(X0 + rail / 2, Y0 + a.tool_edge), (X0 + rail / 2, Y1 - a.tool_edge),
          (X1 - rail / 2, Y0 + a.tool_edge), (X1 - rail / 2, Y1 - a.tool_edge - a.tool_offset)]
    for p in th:
        npth_fp('TH', [p], a.tool_d)
    fy = [float(v) for v in a.fid_y.split(',')]
    fids = [(X0 + a.fid_edge, Y0 + fy[0] if fy[0] >= 0 else Y1 + fy[0]),
            (X0 + a.fid_edge, Y0 + fy[1] if fy[1] >= 0 else Y1 + fy[1]),
            (X1 - a.fid_edge, Y0 + fy[2] if fy[2] >= 0 else Y1 + fy[2])]
    nfid = 0
    for side in ('F', 'B'):
        for fx, fyy in fids:
            nfid += 1
            fp = pcbnew.FootprintLoad(FID_LIB, FID_NAME)
            if fp is None:
                print('ERROR: cannot load %s/%s' % (FID_LIB, FID_NAME)); sys.exit(2)
            b.Add(fp)
            fp.SetReference('FID%d' % nfid)
            fp.SetPosition(V(MM(fx), MM(fyy)))
            if side == 'B':
                fp.Flip(V(MM(fx), MM(fyy)), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
            fp.SetAttributes(ATTR)
            fp.Reference().SetVisible(False)
            fp.Value().SetVisible(False)
    report['tooling_holes'] = [[round(x, 3), round(y, 3)] for x, y in th]
    report['fiducials'] = dict(xy=[[round(x, 3), round(y, 3)] for x, y in fids], sides=['F', 'B'], copper_d=1.0, mask_d=2.0)
    # panel-feature spacing: fiducials and tooling holes vs tabs and each other
    feats = [('TH', Point(p).buffer(a.tool_d / 2)) for p in th] + [('FID', Point(p).buffer(1.0)) for p in fids]   # FID: 2 mm mask opening
    tab_boxes = [Polygon([(TO(t['x_nm'][0]), t['y'] - a.tab_width / 2), (TO(t['x_nm'][1]), t['y'] - a.tab_width / 2),
                          (TO(t['x_nm'][1]), t['y'] + a.tab_width / 2), (TO(t['x_nm'][0]), t['y'] + a.tab_width / 2)]) for t in tabs]
    for nm, g in feats:
        dmin = min(g.distance(tb) for tb in tab_boxes) if tab_boxes else 99
        if dmin < 1.0:
            err.append('%s at %s is %.2f mm from a tab' % (nm, tuple(round(c, 2) for c in g.centroid.coords[0]), dmin))
    for i in range(len(feats)):
        for j in range(i + 1, len(feats)):
            if feats[i][1].distance(feats[j][1]) < 1.0:
                err.append('%s and %s closer than 1 mm' % (feats[i][0], feats[j][0]))
    # on a rail, and the copper (tooling: hole wall) >= the board copper-to-edge clearance from every rail edge
    edge_clr = TO(ds.m_CopperEdgeClearance)
    for nm, g in [('TH', Point(p).buffer(a.tool_d / 2)) for p in th] + [('FID copper', Point(p).buffer(0.5)) for p in fids]:
        c = g.centroid
        rail_l = X0 <= c.x <= X0 + rail
        rail_r = X1 - rail <= c.x <= X1
        if not (rail_l or rail_r):
            err.append('%s at (%.2f, %.2f) is not on a rail' % (nm, c.x, c.y))
            continue
        xr0 = X0 if rail_l else X1 - rail
        m = min(g.bounds[0] - xr0, xr0 + rail - g.bounds[2], g.bounds[1] - Y0, Y1 - g.bounds[3])
        if m < (edge_clr if nm.startswith('FID') else 0.5) - 1e-6:
            err.append('%s at (%.2f, %.2f) is %.2f mm from a rail edge' % (nm, c.x, c.y, m))

    # ---------------- 5. save ------------------------------------------------------------------------------
    pcb_out = os.path.join(out, name + '.kicad_pcb')
    if os.path.normcase(os.path.abspath(pcb_out)) == os.path.normcase(src):
        print('ERROR: refusing to overwrite the input'); sys.exit(2)
    b.Save(pcb_out)
    for ext in ('.kicad_pro', '.kicad_dru'):
        s_ = os.path.join(src_dir, base + ext)
        if os.path.isfile(s_):
            shutil.copy2(s_, os.path.join(out, name + ext))
    # panel features follow JLC's panel rules, not the board pad rule fab_pad_hole_to_hole (0.45 mm): JLC mouse bites are
    # 0.35-0.4 mm hole edge to hole edge (min 0.3 mm). The rule is appended to the panel's DRU COPY only.
    dru = os.path.join(out, name + '.kicad_dru')
    if os.path.isfile(dru):
        with open(dru, 'a', encoding='utf-8') as f:
            f.write('\n# --- appended by make_panel.py (panel copy only): JLC mouse-bite spacing 0.35-0.4 mm, min 0.3 mm\n'
                    '(rule "panel_mouse_bite_hole_to_hole"\n'
                    '   (condition "A.memberOfFootprint(\'MB*\') && B.memberOfFootprint(\'MB*\')")\n'
                    '   (constraint hole_to_hole (min 0.3mm)))\n')
    # re-load the saved panel for the geometry check of the real Edge.Cuts
    pb = pcbnew.LoadBoard(pcb_out)
    ps = pcbnew.SHAPE_POLY_SET()
    ok_outline = pb.GetBoardPolygonOutlines(ps, False)
    report['panel_outline'] = dict(kicad_outline_ok=bool(ok_outline), outlines=ps.OutlineCount(),
                                   holes=sum(ps.HoleCount(i) for i in range(ps.OutlineCount())),
                                   area_mm2=round(ps.Area() / 1e12, 2))
    if not ok_outline or ps.OutlineCount() != 1:
        err.append('KiCad cannot build one closed panel outline (outlines=%d)' % ps.OutlineCount())
    # holes per area (JLC surcharge above 150,000 holes per m2)
    nh = sum(1 for t in pb.GetTracks() if t.GetClass() == 'PCB_VIA') + sum(1 for fp in pb.GetFootprints() for p in fp.Pads() if p.GetDrillSize().x > 0)
    report['holes'] = dict(count=nh, per_m2=round(nh / (PW * PH) * 1e6), jlc_threshold=150000)
    report['footprints'] = dict(total=len(list(pb.GetFootprints())), mouse_bite_rows=len(bites), tooling=len(th), fiducials=nfid)
    report['tabs'] = [dict(gap=t['gap'], y=round(t['y'], 4), left_copy=None if t['left'] is None else t['left'] + 1,
                           right_copy=None if t['right'] is None else t['right'] + 1,
                           x=[round(TO(t['x_nm'][0]), 4), round(TO(t['x_nm'][1]), 4)], bites=t['bite_rows'],
                           checks=t['checks']) for t in tabs]

    # ---------------- 6. CPL / BOM ---------------------------------------------------------------------------
    rc_cpl = 0
    if a.cpl or a.bom:
        if not (a.cpl and a.bom):
            print('ERROR: --cpl and --bom go together'); sys.exit(2)
        rc_cpl = panel_cpl_bom(a, single, out, name, pcb_out, cols, rot, dxs, cx, cy, x0, x1, report)

    # ---------------- 7. DRC ---------------------------------------------------------------------------------
    rc_drc = 0
    if a.drc:
        rc_drc = panel_drc(a, out, work, base, pcb_out, cols, rot, dxs, cx, cy, x0, x1, nets_items, report)

    # ---------------- 8. renders ------------------------------------------------------------------------------
    if a.render:
        render(a, src_dir, out, name, pcb_out, pb, tabs, report)

    report['input']['sha256_after'] = sha256(src)
    if report['input']['sha256_after'] != src_hash:
        err.append('INPUT BOARD CHANGED - this must never happen')
    with open(os.path.join(out, 'panel_report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=1)
    print_summary(report)
    if err:
        sys.exit(3)
    if rc_cpl:
        sys.exit(4)
    if rc_drc:
        sys.exit(5)
    sys.exit(0)


# --------------------------------------------------------------------------------------------------- CPL / BOM
def read_csv(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def mmval(s):
    return float(str(s).strip().replace('mm', ''))


def panel_cpl_bom(a, single, out, name, pcb_out, cols, rot, dxs, cx, cy, x0, x1, report):
    res = dict(errors=[], warnings=[])

    def dname(ref, k):                    # JLC: "Each reference designator appears only once" -> suffix per copy
        return ref if cols == 1 else '%s_%d' % (ref, k + 1)
    rows = read_csv(a.cpl)
    bom = read_csv(a.bom)
    need = {'Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'}
    if not need <= set(rows[0].keys()):
        res['errors'].append('CPL header %s lacks %s' % (list(rows[0].keys()), need))
    # the single CPL must describe THIS board: positions = footprint positions (pos files are y-up), side = flip
    stale = []
    for r in rows:
        fp = single.get(r['Designator'])
        if fp is None:
            stale.append('%s not on the board' % r['Designator']); continue
        x, y = mmval(r['Mid X']), mmval(r['Mid Y'])
        fx, fy = fp[0], -fp[1]
        if abs(x - fx) > 0.005 or abs(y - fy) > 0.005:
            stale.append('%s CPL (%.3f, %.3f) vs board (%.3f, %.3f)' % (r['Designator'], x, y, fx, fy))
        if (r['Layer'].lower().startswith('b')) != fp[2]:
            stale.append('%s layer %s vs board %s' % (r['Designator'], r['Layer'], 'Bottom' if fp[2] else 'Top'))
    if stale:
        res['errors'].append('single-board CPL does not match the board (%d): %s' % (len(stale), stale[:8]))
    # panel CPL: one row per placement, designator REF_<copy>
    prow = []
    for k in range(cols):
        for r in rows:
            x, ypos = mmval(r['Mid X']), mmval(r['Mid Y'])
            yb = -ypos
            if rot[k]:
                x, yb = 2 * cx - x, 2 * cy - yb
            x += dxs[k]
            prow.append(dict(Designator=dname(r['Designator'], k), x=x, y=-yb, Layer=r['Layer'],
                             rot=(float(r['Rotation']) + rot[k]) % 360, base=r['Designator'], copy=k + 1))
    cpl_out = os.path.join(out, name + '_JLC_CPL.csv')
    with open(cpl_out, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        for p in prow:
            w.writerow([p['Designator'], '%.6fmm' % p['x'], '%.6fmm' % p['y'], p['Layer'], '%.6f' % p['rot']])
    # panel BOM: same lines, designators expanded per copy; JLC: "Each BOM line should contain no more than 200
    # reference designators" -> split longer lines
    bom_out = os.path.join(out, name + '_JLC_BOM.csv')
    hdr = list(bom[0].keys())
    nlines, maxrefs, split = 0, 0, 0
    bom_refs = []
    with open(bom_out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=hdr)
        w.writeheader()
        for r in bom:
            refs = [x.strip() for x in r['Designator'].split(',') if x.strip()]
            pref = [dname(x, k) for k in range(cols) for x in refs]
            chunks = [pref[i:i + 200] for i in range(0, len(pref), 200)]
            split += len(chunks) - 1
            for ch in chunks:
                rr = dict(r); rr['Designator'] = ','.join(ch); w.writerow(rr)
                nlines += 1; maxrefs = max(maxrefs, len(ch)); bom_refs += ch
    cpl_refs = [p['Designator'] for p in prow]
    dupc = [x for x, n in collections.Counter(cpl_refs).items() if n > 1]
    dupb = [x for x, n in collections.Counter(bom_refs).items() if n > 1]
    if dupc: res['errors'].append('duplicate CPL designators %s' % dupc[:8])
    if dupb: res['errors'].append('duplicate BOM designators %s' % dupb[:8])
    sb, sc = set(bom_refs), set(cpl_refs)
    if sb != sc:
        res['errors'].append('BOM vs CPL designators differ: BOM-only %s CPL-only %s' % (sorted(sb - sc)[:8], sorted(sc - sb)[:8]))
    if len(prow) != cols * len(rows):
        res['errors'].append('row count %d != %d x %d' % (len(prow), cols, len(rows)))
    # JLC: "the minimum distance between any two different reference designators is not less than 0.2 mm"
    pts = sorted((p['x'], p['y'], p['Designator'], p['Layer']) for p in prow)
    dmin, pair = 1e9, None
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            if pts[j][0] - pts[i][0] > dmin:
                break
            d = math.hypot(pts[j][0] - pts[i][0], pts[j][1] - pts[i][1])
            if d < dmin:
                dmin, pair = d, (pts[i][2], pts[j][2], pts[i][3], pts[j][3])
    res['min_designator_spacing_mm'] = [round(dmin, 3), pair]
    if dmin <= 0.2:
        res['errors'].append('designators %s are %.3f mm apart (JLC: > 0.2 mm)' % (pair, dmin))
    # cross-check against the panel's own position export
    pos_out = os.path.join(out, name + '_positions_kicad.csv')
    rc, tail = run([a.kicad_cli, 'pcb', 'export', 'pos', '--side', 'both', '--format', 'csv', '--units', 'mm', '-o', pos_out, pcb_out])
    if rc != 0 or not os.path.isfile(pos_out):
        res['errors'].append('panel pos export failed: %s' % tail)
    else:
        # the panel keeps the board references in every copy: assign each position row to its copy by x
        pos, unplaced = {}, []
        for r in read_csv(pos_out):
            px = float(r['PosX'])
            ks = [k for k in range(cols) if dxs[k] + x0 - 1.0 <= px <= dxs[k] + x1 + 1.0]
            if len(ks) == 1:
                pos[dname(r['Ref'], ks[0])] = r
            else:
                unplaced.append(r['Ref'])
        bad = ['position rows outside every copy: %s' % unplaced[:6]] if unplaced else []
        for p in prow:
            q = pos.get(p['Designator'])
            if q is None:
                bad.append('%s missing in the panel pos file' % p['Designator']); continue
            if abs(float(q['PosX']) - p['x']) > 0.001 or abs(float(q['PosY']) - p['y']) > 0.001:
                bad.append('%s pos (%s, %s) vs CPL (%.4f, %.4f)' % (p['Designator'], q['PosX'], q['PosY'], p['x'], p['y']))
            if (q['Side'].lower() == 'bottom') != p['Layer'].lower().startswith('b'):
                bad.append('%s side %s vs %s' % (p['Designator'], q['Side'], p['Layer']))
        # raw KiCad rotation of copy n minus copy 1 must equal the copy rotation (the JLC correction is additive)
        for p in prow:
            if p['copy'] == 1:
                continue
            q1, qn = pos.get(dname(p['base'], 0)), pos.get(p['Designator'])
            if q1 and qn:
                dr = (float(qn['Rot']) - float(q1['Rot']) - rot[p['copy'] - 1]) % 360
                if min(dr, 360 - dr) > 0.01:
                    bad.append('%s raw rotation %s vs copy 1 %s' % (p['Designator'], qn['Rot'], q1['Rot']))
        res['crosscheck_vs_panel_pos'] = dict(checked=len(prow), mismatches=len(bad), first=bad[:8])
        if bad:
            res['errors'].append('panel CPL disagrees with the panel position file in %d rows' % len(bad))
    res.update(cpl=cpl_out, bom=bom_out, cpl_rows=len(prow), single_rows=len(rows), bom_lines=nlines,
               max_refs_per_line=maxrefs, lines_split=split,
               designator_format='<REF>_<copy>, copy 1 = left board' if cols > 1 else 'unchanged (one board per panel)')
    report['cpl_bom'] = res
    return 1 if res['errors'] else 0


# --------------------------------------------------------------------------------------------------- DRC
REF_RE = re.compile(r'\b([A-Z]+[0-9]+)_[0-9]+\b')


def panel_drc(a, out, work, base, pcb_out, cols, rot, dxs, cx, cy, x0, x1, nets_items, report):
    """Classify the panel DRC against the board DRC.
    The copies share net names, so KiCad sees each net as 2 x (its board clusters). The unconnected list then has
    exactly cols x U_board + (cols - 1) x N_nets entries when no copy lost or gained a connection (a net with c clusters
    on the board has cols*c clusters, i.e. cols*c - 1 ratsnest edges). Which cluster pairs KiCad links can change
    (nearer clusters now exist across the centre gap), so unconnected items are tested by that count, not one by one.
    Net-length and skew rules sum both copies of a shared net and are reported separately."""
    res = dict()
    bjson = os.path.join(work, 'drc_board.json')
    pjson = os.path.join(out, 'drc_panel.json')
    rc1, t1 = run([a.kicad_cli, 'pcb', 'drc', '--all-track-errors', '--format', 'json', '--severity-all', '--units', 'mm', '-o', bjson,
                   os.path.join(work, base + '.kicad_pcb')])
    rc2, t2 = run([a.kicad_cli, 'pcb', 'drc', '--all-track-errors', '--format', 'json', '--severity-all', '--units', 'mm', '-o', pjson, pcb_out])
    if not (os.path.isfile(bjson) and os.path.isfile(pjson)):
        report['drc'] = dict(error='DRC did not run: %s %s' % (t1, t2))
        return 1
    bj, pj = json.load(open(bjson, encoding='utf-8')), json.load(open(pjson, encoding='utf-8'))

    def norm(desc):
        return REF_RE.sub(r'\1', desc)

    def vlist(j):
        return [('unconnected_items' if k == 'unconnected_items' else v.get('type'), v.get('severity'), v) for k in ('violations', 'unconnected_items')
                for v in j.get(k, [])]
    # board violations keyed by (type, sorted positions, normalised descriptions)
    def key_of(typ, v, k_copy=None):
        pts = []
        for it in v.get('items', []):
            x, y = it['pos']['x'], it['pos']['y']
            if k_copy is not None:
                x -= dxs[k_copy]
                if rot[k_copy]:
                    x, y = 2 * cx - x, 2 * cy - y
            pts.append((round(x, 2), round(y, 2), norm(it.get('description', ''))))
        return (typ, tuple(sorted(pts)))
    bkeys = collections.Counter(key_of(t, v) for t, s, v in vlist(bj))
    bdesc = collections.Counter((t, v.get('description')) for t, s, v in vlist(bj))
    NETLEVEL = {'length_out_of_range', 'skew_out_of_range', 'diff_pair_uncoupled_length_too_long'}
    cls = collections.Counter()
    new = []
    unconn_panel = 0
    for typ, sev, v in vlist(pj):
        its = v.get('items', [])
        copies = set()
        panel_feat = False
        for it in its:
            x = it['pos']['x']
            desc = it.get('description', '')
            hit = [k for k in range(cols) if dxs[k] + x0 - 0.3 <= x <= dxs[k] + x1 + 0.3]
            if re.search(r'\b(MB|TH|FID)\d+\b', desc) or not hit:     # a panel footprint, or an item in a rail / gap / tab
                panel_feat = True
            copies.update(hit)
        if panel_feat:
            cls[('NEW (panel feature)', typ, sev)] += 1; new.append((typ, sev, v.get('description'), [i.get('description') for i in its][:3]))
            continue
        if typ == 'unconnected_items':
            unconn_panel += 1
            cls[('unconnected (tested by count below)', typ, sev)] += 1
            continue
        if typ in NETLEVEL:
            # net-level rules: KiCad anchors the report on any item of the net, so match by the rule text instead
            if cols > 1:
                cls[('net-level length/skew (nets shared across copies)', typ, sev)] += 1
                continue
            if bdesc.get((typ, v.get('description')), 0) > 0:
                bdesc[(typ, v.get('description'))] -= 1
                cls[('inherited from the board', typ, sev)] += 1
                continue
        if len(copies) == 1:
            k = copies.pop()
            kk = key_of(typ, v, k)
            if bkeys.get(kk, 0) > 0:
                cls[('inherited from the board', typ, sev)] += 1
                continue
        cls[('NEW (not on the board)', typ, sev)] += 1
        new.append((typ, sev, v.get('description'), [i.get('description') for i in its][:3]))
    bcount = collections.Counter((t, s) for t, s, v in vlist(bj))
    ub = len(bj.get('unconnected_items', []))
    expect = cols * ub + (cols - 1) * len(nets_items)
    res['unconnected_count_test'] = dict(board=ub, nets_with_items=len(nets_items), expected=expect, panel=unconn_panel,
                                         ok=unconn_panel == expect)
    if unconn_panel != expect:
        new.append(('unconnected_items', 'error', 'panel has %d unconnected items, expected %d x %d + %d x %d = %d: a copy gained or lost a connection'
                    % (unconn_panel, cols, ub, cols - 1, len(nets_items), expect), []))
    res['board_counts'] = {'%s/%s' % k: n for k, n in sorted(bcount.items())}
    res['panel_classes'] = {'%s | %s/%s' % k: n for k, n in sorted(cls.items())}
    res['new'] = new[:60]
    res['new_errors'] = sum(1 for t, s, d, i in new if s == 'error')
    res['new_warnings'] = sum(1 for t, s, d, i in new if s != 'error')
    res['board_json'], res['panel_json'] = bjson, pjson
    report['drc'] = res
    return 1 if res['new_errors'] else 0


# --------------------------------------------------------------------------------------------------- renders
def render(a, src_dir, out, name, pcb_out, pb, tabs, report):
    rr = dict()
    lib_src = os.path.join(src_dir, 'libraries')
    lib_dst = os.path.join(out, 'libraries')
    if os.path.isdir(lib_src) and not os.path.isdir(lib_dst):
        shutil.copytree(lib_src, lib_dst)
    for side in ('top', 'bottom'):
        png = os.path.join(out, '%s_3D_%s.png' % (name, side))
        rc, tail = run([a.kicad_cli, 'pcb', 'render', '--side', side, '--width', '2400', '--height', '1900', '--quality', 'high',
                        '--background', 'opaque', '-o', png, pcb_out], timeout=1800)
        rr['3d_' + side] = png if os.path.isfile(png) else 'failed: %s' % tail
    # 2D: outline, NPTH, fiducials, courtyards (F red, B blue), copper pads (grey), tab keep-out boxes (orange)
    try:
        from PIL import Image, ImageDraw
        S = 14.0
        bb = pb.GetBoardEdgesBoundingBox()
        ox, oy = TO(bb.GetX()) - 3, TO(bb.GetY()) - 3
        Wpx, Hpx = int((TO(bb.GetWidth()) + 6) * S), int((TO(bb.GetHeight()) + 6) * S)
        img = Image.new('RGB', (Wpx, Hpx), 'white')
        d = ImageDraw.Draw(img)
        P = lambda x, y: ((x - ox) * S, (y - oy) * S)
        ps = pcbnew.SHAPE_POLY_SET()
        pb.GetBoardPolygonOutlines(ps, False)
        for i in range(ps.OutlineCount()):
            o = ps.Outline(i)
            d.polygon([P(TO(o.CPoint(k).x), TO(o.CPoint(k).y)) for k in range(o.PointCount())], fill=(214, 232, 200), outline='black')
            for h in range(ps.HoleCount(i)):
                hh = ps.Hole(i, h)
                d.polygon([P(TO(hh.CPoint(k).x), TO(hh.CPoint(k).y)) for k in range(hh.PointCount())], fill='white', outline='black')
        for t in tabs:
            ya, yb = t['y'] - a.tab_width / 2, t['y'] + a.tab_width / 2
            xa, xb = TO(t['x_nm'][0]), TO(t['x_nm'][1])
            d.rectangle([P(xa - a.min_courtyard, ya), P(xb + a.min_courtyard, yb)], outline=(255, 140, 0), width=2)
        for fp in pb.GetFootprints():
            ref = fp.GetReference()
            for lay, col in ((pcbnew.F_CrtYd, (200, 0, 0)), (pcbnew.B_CrtYd, (0, 0, 220))):
                cyd = fp.GetCourtyard(lay)
                for i in range(cyd.OutlineCount()):
                    o = cyd.Outline(i)
                    pts = [P(TO(o.CPoint(k).x), TO(o.CPoint(k).y)) for k in range(o.PointCount())]
                    if len(pts) > 2:
                        d.polygon(pts, outline=col)
            for p in fp.Pads():
                c = p.GetPosition()
                if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                    r = TO(p.GetDrillSize().x) / 2
                    d.ellipse([P(TO(c.x) - r, TO(c.y) - r), P(TO(c.x) + r, TO(c.y) + r)], fill='black')
                elif PANEL_REFS.match(ref):
                    r = 0.5
                    d.ellipse([P(TO(c.x) - 1.0, TO(c.y) - 1.0), P(TO(c.x) + 1.0, TO(c.y) + 1.0)], outline=(0, 120, 0), width=2)
                    d.ellipse([P(TO(c.x) - r, TO(c.y) - r), P(TO(c.x) + r, TO(c.y) + r)], fill=(190, 140, 0))
        png2 = os.path.join(out, '%s_2D.png' % name)
        img.save(png2)
        rr['2d'] = png2
    except Exception as e:
        rr['2d'] = 'failed: %s' % e
    report['renders'] = rr


def print_summary(r):
    p = r['panel']
    print('panel %s: %d x 1, rotation %s, %.3f x %.3f mm (incl. edge line %.3f x %.3f), rail %.3f mm, gap %.1f mm'
          % (p['name'], p['cols'], p['rotation'], p['size_mm'][0], p['size_mm'][1], p['size_incl_line_mm'][0], p['size_incl_line_mm'][1], p['rail'], p['gap']))
    print('board outline %s x %s mm (centre line; %s incl. the %.2f mm line); copper layers %d' % (
        r['board']['width'], r['board']['height'], r['board']['bbox_incl_line'], r['board']['edge_line_width'], r['board']['copper_layers']))
    for t in r['tabs']:
        cs = '; '.join('copy %d %s-edge local y %.2f: courtyard %.2f %s, MLCC %.2f %s, copper %.2f, fill->hole %.2f%s' % (
            c['copy'], c['edge'], c['y'], c['courtyard'][0], c['courtyard'][1], c['mlcc'][0], c['mlcc'][1], c['copper'][0],
            c['fill_to_bite_hole'], '' if c['ok'] else ' FAIL') for c in t['checks'])
        print('  tab %-5s y %7.2f x %s: %s' % (t['gap'], t['y'], t['x'], cs))
    print('mouse bites:', r['mouse_bites'])
    print('tooling holes:', r['tooling_holes'], ' fiducials (F and B):', r['fiducials']['xy'])
    print('Edge.Cuts:', r['edge_cuts'], ' KiCad outline:', r.get('panel_outline'))
    print('holes:', r['holes'])
    if 'cpl_bom' in r:
        c = r['cpl_bom']
        print('CPL/BOM: %s rows (single %s), BOM %s lines (max %s refs/line, %s split), min designator spacing %s, cross-check %s, errors %s'
              % (c.get('cpl_rows'), c.get('single_rows'), c.get('bom_lines'), c.get('max_refs_per_line'), c.get('lines_split'),
                 c.get('min_designator_spacing_mm'), c.get('crosscheck_vs_panel_pos'), c['errors']))
    if 'drc' in r:
        d = r['drc']
        print('DRC board:', d.get('board_counts'))
        print('DRC panel classes:')
        for k, n in d.get('panel_classes', {}).items():
            print('   %5d  %s' % (n, k))
        print('unconnected count test:', d.get('unconnected_count_test'))
        print('DRC NEW errors %s, NEW warnings %s' % (d.get('new_errors'), d.get('new_warnings')))
        for n in d.get('new', [])[:20]:
            print('   NEW', n)
    if 'renders' in r:
        print('renders:', r['renders'])
    for w in r['warnings']:
        print('WARN ', w)
    for e in r['errors']:
        print('ERROR', e)
    print('input sha256 before %s after %s' % (r['input']['sha256'][:12], r['input'].get('sha256_after', '?')[:12]))


if __name__ == '__main__':
    main()

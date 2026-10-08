"""pen.py IN.kicad_pcb OUT.kicad_pcb EDITS.json
Hand-layout executor (user rule 2026-10-03: no auto-routers; decide every move and track by hand and let tools only
execute and verify). Applies an explicit, ordered edit list - nothing is searched or optimised:

  {"move":   "REF", "x": 140.1, "y": 98.2, "rot": 90, "side": "F|B"}      footprint pose (side change = flip)
  {"del":    "NET", "box": [x0, y0, x1, y1], "layers": ["In3.Cu"], "vias": true}
                                         remove that net's tracks lying fully inside the box (and vias inside it)
  {"delseg": "NET", "a": [x, y], "b": [x, y], "layer": "F.Cu"}            remove one segment (ends within 0.02 mm)
  {"delvia": "NET", "at": [x, y]}                                         remove one via (within 0.02 mm)
  {"track":  "NET", "layer": "In3.Cu", "w": 0.15, "pts": [[x, y], ...]}  consecutive segments through the points
             optional "r": 0.5 rounds every interior corner with a tangent arc of that radius (mm); the corner
             points stay the octilinear construction lines, the copper follows the arcs (2026-10-04)
  {"arc":    "NET", "layer": "F.Cu", "w": 0.15, "start": [x, y], "mid": [x, y], "end": [x, y]}  one arc (2026-10-04)
  {"via":    "NET", "at": [x, y], "d": 0.45, "drill": 0.2}                through via F.Cu-B.Cu
  {"movetext": "RF IN", "layer": "F.Silkscreen", "x": 139.0, "y": 57.0, "rot": 0}   move a board text (2026-10-03)
  {"fpattr": "J6", "exclude_pos": true, "exclude_bom": true, "dnp": false}    footprint fab attributes (2026-10-03)
  {"setup": {"solder_mask_expansion": 0.0}}  board setup values the API exposes (2026-10-04)
  {"rulearea": "K6_B_RF_END", "layers": ["B.Cu"], "pts": [[x, y], ...], "no_tracks": false, "no_vias": false,
   "no_pads": false, "no_pour": false, "no_footprints": false, "replace": false}     named rule area (2026-10-04)
  {"ruleflags": "K7_H1", "no_vias": true, "shift": [dx, dy]}                         flags / shift of a named area
  {"deltext": "RF IN", "layer": "F.Silkscreen"}                                delete a board text (2026-10-03)
  {"addtext": "CAL", "layer": "F.Silkscreen", "x": 148.5, "y": 55.2, "rot": 90, "size": 1.0, "stroke": 0.15}
                                         add a board text; B.* layers are mirrored (2026-10-03); optional
                                         "justify": "left"|"right" anchors a multi-line note at its top-left/-right
  {"addrect": "B.Silkscreen", "start": [x, y], "end": [x, y], "w": 0.15}   unfilled graphic rectangle (2026-10-04)
  {"titleblock": {"date": "2026-10-04"}}   title-block fields: date (feeds ${ISSUE_DATE}), rev, title, company,
                                         comment1..9 (2026-10-04)
  {"padpaste": "J10", "pads": ["SH"], "margin": 0.15}   pin-in-paste: paste layer + local paste margin on the
                                         footprint's plated through-hole pads of those numbers (2026-10-04)
Every segment must be horizontal, vertical or 45 degrees (octilinear rule) or the edit is refused. Track points and
via centres within 0.01 mm of an existing track end or via of the same net are snapped onto it exactly: a joint that
is off by a few hundred nm is a T-junction to KiCad and trips the track_angle rule. Net names may be short (last path
element). Copies .kicad_pro / .kicad_dru. Verify with tools/drcnear.py and place/metrics.py.

  pen.py --check BOARD.kicad_pcb EDITS.json
measures every "track" / "via" of the list (already on BOARD) against the mr.py rule model: other-net copper with
the class / DRU clearance, rule-area bans, plated / bare holes, board edge. Prints each shortfall with the measured and
required gap; nothing is changed. Write mode runs it automatically on OUT (child process: one board per process).
KiCad python, scratch copies only."""
import json
import math
import os
import shutil
import subprocess
import sys

import pcbnew

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import mr  # noqa: E402


def fillet(pts, r):
    """Octilinear polyline -> pieces ('seg', a, b) / ('arc', a, mid, b) with every interior corner rounded by a
    tangent arc of radius r (mm). Exits when a leg is too short for the arcs at both of its ends."""
    def sub(p, q):
        return (p[0] - q[0], p[1] - q[1])

    def unit(v):
        n = math.hypot(*v)
        return (v[0] / n, v[1] / n)

    def add(p, v, s):
        return (p[0] + v[0] * s, p[1] + v[1] * s)

    pts = [tuple(p) for p in pts]
    corner = {}
    for k in range(1, len(pts) - 1):
        u0, u1 = unit(sub(pts[k], pts[k - 1])), unit(sub(pts[k + 1], pts[k]))
        dot = max(-1.0, min(1.0, u0[0] * u1[0] + u0[1] * u1[1]))
        phi = math.acos(dot)                      # deflection: 0 straight, pi/4 one 45-degree bend
        if phi < 1e-6:
            continue
        if math.pi - phi < 1e-3:
            sys.exit(f'fillet: track reverses at {pts[k]}')
        d = r * math.tan(phi / 2)
        t0, t1 = add(pts[k], u0, -d), add(pts[k], u1, d)
        nv = unit((u1[0] - dot * u0[0], u1[1] - dot * u0[1]))
        o = add(t0, nv, r)
        mid = add(o, unit(sub(pts[k], o)), r)
        corner[k] = (t0, mid, t1, d)
    for k in range(len(pts) - 1):
        need = (corner[k][3] if k in corner else 0) + (corner[k + 1][3] if k + 1 in corner else 0)
        if need > math.hypot(*sub(pts[k + 1], pts[k])) + 1e-6:
            sys.exit(f'fillet: leg {pts[k]}->{pts[k + 1]} is shorter than its arcs need ({need:.3f} mm at r {r})')
    out, start = [], pts[0]
    for k in range(1, len(pts)):
        if k in corner:
            t0, mid, t1, _ = corner[k]
            if math.hypot(*sub(t0, start)) > 1e-6:
                out.append(('seg', start, t0))
            out.append(('arc', t0, mid, t1))
            start = t1
        elif k == len(pts) - 1 or math.hypot(*sub(pts[k], start)) > 1e-6:
            out.append(('seg', start, pts[k]))
            start = pts[k]
    return out


def arc_points(a, m, c, n=16):
    """Points along the circular arc a -> m -> c (for clearance checks)."""
    (x1, y1), (x2, y2), (x3, y3) = a, m, c
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-12:
        return [a, c]
    ux = ((x1 ** 2 + y1 ** 2) * (y2 - y3) + (x2 ** 2 + y2 ** 2) * (y3 - y1) + (x3 ** 2 + y3 ** 2) * (y1 - y2)) / d
    uy = ((x1 ** 2 + y1 ** 2) * (x3 - x2) + (x2 ** 2 + y2 ** 2) * (x1 - x3) + (x3 ** 2 + y3 ** 2) * (x2 - x1)) / d
    R = math.hypot(x1 - ux, y1 - uy)
    a1, am, a3 = (math.atan2(p[1] - uy, p[0] - ux) for p in (a, m, c))
    sweep = (a3 - a1) % (2 * math.pi)
    if (am - a1) % (2 * math.pi) > sweep:      # the arc runs the other way round
        sweep -= 2 * math.pi
    return [(ux + R * math.cos(a1 + sweep * i / n), uy + R * math.sin(a1 + sweep * i / n)) for i in range(n + 1)]


def pieces(e):
    """(label, centre-line points) for every copper piece of a 'track' or 'arc' edit."""
    if 'arc' in e:
        return [(f"arc {e['arc']} {e['layer']} {e['start']}->{e['end']}", arc_points(e['start'], e['mid'], e['end']))]
    if e.get('r'):
        return [(f"{e['track']} {e['layer']} {p[1]}->{p[-1]}", [p[1], p[2]] if p[0] == 'seg' else arc_points(*p[1:]))
                for p in fillet(e['pts'], e['r'])]
    return [(f"{e['track']} {e['layer']} {a}->{c}", [a, c]) for a, c in zip(e['pts'], e['pts'][1:])]


def check(path, ej):
    from shapely.geometry import LineString, Point
    B = mr.Board(path)
    names = {}
    for n in B.b.GetNetsByName().keys():
        names[str(n)] = str(n)
        names.setdefault(str(n).split('/')[-1], str(n))
    bad = 0

    def areas_at(geom, layer):
        return sorted({nm for nm, lst in B.areas.items() for g, zl, *_ in lst if layer in zl and g.intersects(geom)})

    def report(what, msg):
        nonlocal bad
        bad += 1
        print(f"  CHECK {what}: {msg}")

    for e in json.load(open(ej, encoding='utf-8')):
        if 'track' in e or 'arc' in e:
            net, layer, w = names[e.get('track', e.get('arc'))], e['layer'], e['w']
            bans = [x for x in B.bans(net) if x[0] != 'VIAHOLE']
            for what, line in pieces(e):
                geom = LineString(line).buffer(w / 2, 16)
                ex = frozenset(k for k, pe in B.pexempt.items() if pe.intersects(geom))
                for i in B.trees[layer].query(geom.buffer(3.1)):
                    g2, n2, kind = B.items[layer][i]
                    if n2 == net:
                        continue
                    d, req = geom.distance(g2), mr.need(net, n2, kind, ex)
                    if d < req - 0.001:
                        report(what, f"{d:.3f} < {req:.3f} mm to {kind} {n2.split('/')[-1]}")
                for g, lays, tb, vb in bans:
                    if tb and layer in lays and g.intersects(geom):
                        report(what, f"track banned here (areas {areas_at(geom, layer)})")
                if not B.outline.buffer(-0.5).contains(geom):
                    report(what, 'closer than 0.5 mm to the board edge')
        elif 'via' in e:
            net, (x, y), vd, vh = names[e['via']], e['at'], e.get('d', 0.45), e.get('drill', 0.2)
            v = Point(x, y)
            vg = v.buffer(vd / 2, 24)
            what = f"via {e['via']} ({x}, {y})"
            ex = frozenset(k for k, pe in B.pexempt.items() if pe.intersects(vg))
            for ln in mr.SIG:
                for i in B.trees[ln].query(v.buffer(3.1)):
                    g2, n2, kind = B.items[ln][i]
                    if n2 == net:
                        continue
                    d, req = vg.distance(g2), mr.need(net, n2, kind, ex)
                    if d < req - 0.001:
                        report(what, f"{ln} {d:.3f} < {req:.3f} mm to {kind} {n2.split('/')[-1]}")
                    elif g2.distance(v) < vh / 2 + 0.2:
                        report(what, f"{ln} copper of {n2.split('/')[-1]} {g2.distance(v) - vh / 2:.3f} < 0.200 mm from the hole")
            for i in B.htree.query(v.buffer(2.0)):
                hp, hr, hn = B.holes[i]
                if hp.distance(v) > 0.005 and hp.distance(v) < hr + vh / 2 + 0.25:
                    report(what, f"hole {hp.distance(v) - hr - vh / 2:.3f} < 0.250 mm from the hole at ({hp.x:.2f}, {hp.y:.2f})")
            for item in B.bans(net):
                if item[0] == 'VIAHOLE':
                    if item[1].distance(v) < item[2] + vd / 2:
                        report(what, 'inside a mounting-hole via keep-out')
                elif item[3] and item[0].intersects(vg):
                    report(what, f"via banned here (areas {sorted({nm for ln in mr.SIG for nm in areas_at(vg, ln)})})")
            if not B.outline.buffer(-(0.5 + vd / 2)).contains(v):
                report(what, 'closer than 0.5 mm to the board edge')
    print(f"check: {bad} shortfall(s)")
    return bad


if sys.argv[1] == '--check':
    sys.exit(1 if check(sys.argv[2], sys.argv[3]) else 0)

src, dst, ej = sys.argv[1], sys.argv[2], sys.argv[3]
if os.path.normcase(os.path.realpath(dst)).startswith(mr.PROTECTED):
    sys.exit('refusing to write into the project folder')
edits = json.load(open(ej, encoding='utf-8'))
b = pcbnew.LoadBoard(src)
GRAVE = []
nets = {}
for n in b.GetNetsByName().keys():
    s = str(n)
    nets[s] = s
    nets.setdefault(s.split('/')[-1], s)


def NET(n):
    full = nets.get(n)
    if full is None:
        sys.exit(f'no such net {n}')
    return b.FindNet(full)


def V(x, y):
    return pcbnew.VECTOR2I(int(round(x * 1e6)), int(round(y * 1e6)))


def near(p, x, y, tol=0.02):
    return abs(p.x / 1e6 - x) <= tol and abs(p.y / 1e6 - y) <= tol


def snap(ni, x, y, tol=0.01):
    """Exact position of the nearest same-net track end / via within tol (mm), else (x, y)."""
    best = None
    for t in b.GetTracks():
        if t.GetNetCode() != ni.GetNetCode():
            continue
        for p in ((t.GetPosition(),) if t.GetClass() == 'PCB_VIA' else (t.GetStart(), t.GetEnd())):
            d = math.hypot(p.x / 1e6 - x, p.y / 1e6 - y)
            if d <= tol and (best is None or d < best[0]):
                best = (d, pcbnew.VECTOR2I(p.x, p.y))
    if best and best[0] > 0:
        print(f"    snap ({x}, {y}) -> ({best[1].x / 1e6:.6f}, {best[1].y / 1e6:.6f})")
    return best[1] if best else V(x, y)


def kill(t):
    b.Remove(t)
    t.thisown = 0
    GRAVE.append(t)


for i, e in enumerate(edits):
    if 'move' in e:
        f = b.FindFootprintByReference(e['move'])
        if f is None:
            sys.exit(f'edit {i}: no footprint {e["move"]}')
        side = e.get('side')
        if side and side != ('B' if f.IsFlipped() else 'F'):
            f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        f.SetPosition(V(e['x'], e['y']))
        if 'rot' in e:
            f.SetOrientationDegrees(e['rot'])
        print(f"  move {e['move']} -> ({e['x']}, {e['y']}) rot {e.get('rot', f.GetOrientationDegrees())}")
    elif 'del' in e:
        net = NET(e['del']).GetNetname()
        x0, y0, x1, y1 = e['box']
        lays = set(e.get('layers', [])) or None
        n = 0
        for t in list(b.GetTracks()):
            if t.GetNetname() != net:
                continue
            if t.GetClass() == 'PCB_VIA':
                if e.get('vias', True) and x0 <= t.GetPosition().x / 1e6 <= x1 and y0 <= t.GetPosition().y / 1e6 <= y1:
                    kill(t)
                    n += 1
                continue
            if lays and b.GetLayerName(t.GetLayer()) not in lays:
                continue
            ok = all(x0 <= p.x / 1e6 <= x1 and y0 <= p.y / 1e6 <= y1 for p in (t.GetStart(), t.GetEnd()))
            if ok:
                kill(t)
                n += 1
        print(f"  del {e['del']} in {e['box']}: {n} items")
    elif 'delseg' in e:
        net = NET(e['delseg']).GetNetname()
        (ax, ay), (bx, by) = e['a'], e['b']
        hit = [t for t in b.GetTracks() if t.GetClass() != 'PCB_VIA' and t.GetNetname() == net
               and b.GetLayerName(t.GetLayer()) == e['layer']
               and ((near(t.GetStart(), ax, ay) and near(t.GetEnd(), bx, by)) or (near(t.GetStart(), bx, by) and near(t.GetEnd(), ax, ay)))]
        if not hit:
            # merged track (KiCad 'merge collinear segments', 2026-10-03): the span a-b may be part of one longer
            # collinear segment. Cut exactly a-b out of it and keep the remainders, so lists written before a
            # merge still apply.
            def on_seg(t, x, y, tol=0.003):
                sx, sy, ex, ey = t.GetStart().x / 1e6, t.GetStart().y / 1e6, t.GetEnd().x / 1e6, t.GetEnd().y / 1e6
                L = math.hypot(ex - sx, ey - sy)
                if L < 1e-9:
                    return None
                u = ((x - sx) * (ex - sx) + (y - sy) * (ey - sy)) / L ** 2
                d = abs((ex - sx) * (sy - y) - (sx - x) * (ey - sy)) / L
                return u if d <= tol and -1e-6 <= u <= 1 + 1e-6 else None
            cand = [t for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK' and t.GetNetname() == net
                    and b.GetLayerName(t.GetLayer()) == e['layer'] and on_seg(t, ax, ay) is not None
                    and on_seg(t, bx, by) is not None]
            if not cand and math.hypot(bx - ax, by - ay) < 0.01:
                # a sub-10-um sliver that a collinear merge already absorbed: nothing left to delete
                print(f"  delseg {e['delseg']} {e['layer']} {e['a']}->{e['b']}: sliver already gone (merged), skipped")
                continue
            if len(cand) != 1:
                sys.exit(f'edit {i}: delseg matched 0 segments exactly and {len(cand)} merged segments')
            t = cand[0]
            ua, ub = sorted((on_seg(t, ax, ay), on_seg(t, bx, by)))
            s, en = t.GetStart(), t.GetEnd()
            pts = lambda u: pcbnew.VECTOR2I(int(round(s.x + (en.x - s.x) * u)), int(round(s.y + (en.y - s.y) * u)))  # noqa: E731
            pieces = [(s, pts(ua)), (pts(ub), en)]
            for p0, p1 in pieces:
                if math.hypot(p1.x - p0.x, p1.y - p0.y) > 100:  # keep remainders longer than 0.1 um
                    n2 = pcbnew.PCB_TRACK(b)
                    n2.SetStart(p0)
                    n2.SetEnd(p1)
                    n2.SetWidth(t.GetWidth())
                    n2.SetLayer(t.GetLayer())
                    n2.SetNet(t.GetNet())
                    b.Add(n2)
            kill(t)
            print(f"  delseg {e['delseg']} {e['layer']} {e['a']}->{e['b']} (cut out of a merged segment)")
            continue
        if len(hit) != 1:
            sys.exit(f'edit {i}: delseg matched {len(hit)} segments')
        kill(hit[0])
        print(f"  delseg {e['delseg']} {e['layer']} {e['a']}->{e['b']}")
    elif 'delvia' in e:
        net = NET(e['delvia']).GetNetname()
        x, y = e['at']
        hit = [t for t in b.GetTracks() if t.GetClass() == 'PCB_VIA' and t.GetNetname() == net and near(t.GetPosition(), x, y)]
        if len(hit) != 1:
            sys.exit(f'edit {i}: delvia matched {len(hit)} vias')
        kill(hit[0])
        print(f"  delvia {e['delvia']} at {e['at']}")
    elif 'track' in e:
        ni = NET(e['track'])
        pts = e['pts']
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            dx, dy = bx - ax, by - ay
            if not (abs(dx) < 1e-6 or abs(dy) < 1e-6 or abs(abs(dx) - abs(dy)) < 1e-4):
                sys.exit(f'edit {i}: segment {[ax, ay]}->{[bx, by]} is not octilinear')
        if e.get('r'):
            # filleted: straight runs between tangent points plus one arc per corner; only the two ends snap
            parts = fillet(pts, e['r'])
            end0, end1 = snap(ni, *pts[0]), snap(ni, *pts[-1])
            P = lambda p: end0 if p == tuple(pts[0]) else end1 if p == tuple(pts[-1]) else V(*p)  # noqa: E731
            for p in parts:
                t = pcbnew.PCB_TRACK(b) if p[0] == 'seg' else pcbnew.PCB_ARC(b)
                t.SetStart(P(p[1]))
                if p[0] == 'arc':
                    t.SetMid(V(*p[2]))
                t.SetEnd(P(p[-1]))
                t.SetWidth(int(round(e['w'] * 1e6)))
                t.SetLayer(b.GetLayerID(e['layer']))
                t.SetNet(ni)
                b.Add(t)
            print(f"  track {e['track']} {e['layer']} w{e['w']} r{e['r']}: {sum(p[0] == 'seg' for p in parts)} segments"
                  f" + {sum(p[0] == 'arc' for p in parts)} arcs")
            continue
        vp = [snap(ni, x, y) for x, y in pts]
        for pa, pb in zip(vp, vp[1:]):
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(pa)
            t.SetEnd(pb)
            t.SetWidth(int(round(e['w'] * 1e6)))
            t.SetLayer(b.GetLayerID(e['layer']))
            t.SetNet(ni)
            b.Add(t)
        print(f"  track {e['track']} {e['layer']} w{e['w']} {len(pts) - 1} segments, "
              f"{sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(pts, pts[1:])):.2f} mm")
    elif 'arc' in e:
        ni = NET(e['arc'])
        t = pcbnew.PCB_ARC(b)
        t.SetStart(snap(ni, *e['start']))
        t.SetMid(V(*e['mid']))
        t.SetEnd(snap(ni, *e['end']))
        t.SetWidth(int(round(e['w'] * 1e6)))
        t.SetLayer(b.GetLayerID(e['layer']))
        t.SetNet(ni)
        b.Add(t)
        print(f"  arc {e['arc']} {e['layer']} w{e['w']} {e['start']} -> {e['end']}")
    elif 'via' in e:
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(snap(NET(e['via']), *e['at']))
        v.SetWidth(int(round(e.get('d', 0.45) * 1e6)))
        v.SetDrill(int(round(e.get('drill', 0.2) * 1e6)))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(NET(e['via']))
        b.Add(v)
        print(f"  via {e['via']} at {e['at']}")
    elif 'movetext' in e:
        # board-level text (not a footprint field), matched by its exact string and layer
        hit = [d for d in b.GetDrawings() if d.GetClass() in ('PCB_TEXT', 'PTEXT') and d.GetText() == e['movetext']
               and (not e.get('layer') or b.GetLayerName(d.GetLayer()) == e['layer'])]
        if len(hit) != 1:
            sys.exit(f'edit {i}: movetext matched {len(hit)} texts')
        old = hit[0].GetPosition()
        hit[0].SetPosition(V(e['x'], e['y']))
        if 'rot' in e:
            hit[0].SetTextAngleDegrees(e['rot'])
        print(f"  movetext '{e['movetext']}' ({old.x / 1e6:.3f}, {old.y / 1e6:.3f}) -> ({e['x']}, {e['y']})")
    elif 'rulearea' in e:
        # named rule area (keep-out): polygon pts, copper/tech layers, bans. 'replace': remove an area of that name first.
        name = e['rulearea']
        old = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetZoneName() == name]
        if old and not e.get('replace'):
            sys.exit(f'edit {i}: rule area {name} exists (set "replace": true)')
        for z in old:
            kill(z)
        z = pcbnew.ZONE(b)
        z.SetIsRuleArea(True)
        z.SetZoneName(name)
        ls = pcbnew.LSET()
        for ln in e['layers']:
            ls.AddLayer(b.GetLayerID(ln))
        z.SetLayerSet(ls)
        z.SetDoNotAllowTracks(bool(e.get('no_tracks', False)))
        z.SetDoNotAllowVias(bool(e.get('no_vias', False)))
        z.SetDoNotAllowPads(bool(e.get('no_pads', False)))
        z.SetDoNotAllowZoneFills(bool(e.get('no_pour', False)))
        z.SetDoNotAllowFootprints(bool(e.get('no_footprints', False)))
        ol = z.Outline()
        ol.NewOutline()
        for x, y in e['pts']:
            ol.Append(int(round(x * 1e6)), int(round(y * 1e6)))
        b.Add(z)
        print(f"  rulearea {name} on {e['layers']}: {len(e['pts'])} pts" + (' (replaced)' if old else '') +
              ', bans ' + ','.join(k for k in ('no_tracks', 'no_vias', 'no_pads', 'no_pour', 'no_footprints') if e.get(k)))
    elif 'delrulearea' in e:
        hit = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetZoneName() == e['delrulearea']]
        if len(hit) != 1:
            sys.exit(f'edit {i}: delrulearea matched {len(hit)} rule areas named {e["delrulearea"]}')
        kill(hit[0])
        print(f"  delrulearea {e['delrulearea']}")
    elif 'ruleflags' in e:
        hit = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetZoneName() == e['ruleflags']]
        if len(hit) != 1:
            sys.exit(f'edit {i}: ruleflags matched {len(hit)} rule areas named {e["ruleflags"]}')
        z = hit[0]
        setters = {'no_tracks': z.SetDoNotAllowTracks, 'no_vias': z.SetDoNotAllowVias, 'no_pads': z.SetDoNotAllowPads,
                   'no_pour': z.SetDoNotAllowZoneFills, 'no_footprints': z.SetDoNotAllowFootprints}
        for k, v in e.items():
            if k in setters:
                setters[k](bool(v))
        if 'shift' in e:  # translate the whole area by [dx, dy] mm (e.g. re-centre on a hole)
            z.Move(pcbnew.VECTOR2I(int(round(e['shift'][0] * 1e6)), int(round(e['shift'][1] * 1e6))))
        print(f"  ruleflags {e['ruleflags']}: " + ', '.join(f'{k}={v}' for k, v in e.items() if k != 'ruleflags'))
    elif 'setup' in e:
        # board-setup values the python API exposes (mm): solder_mask_expansion, solder_mask_min_width,
        # solder_mask_to_copper_clearance. The stackup and via filling/capping are not exposed (GUI only).
        ds = b.GetDesignSettings()
        # (the DRC minimums such as min silk text height live in .kicad_pro, not the board: set those via Konnect)
        names = {'solder_mask_expansion': 'm_SolderMaskExpansion', 'solder_mask_min_width': 'm_SolderMaskMinWidth',
                 'solder_mask_to_copper_clearance': 'm_SolderMaskToCopperClearance'}
        for k, v in e['setup'].items():
            if k not in names:
                sys.exit(f'edit {i}: unknown setup key {k}')
            old = getattr(ds, names[k]) / 1e6
            setattr(ds, names[k], int(round(v * 1e6)))
            print(f"  setup {k}: {old} -> {v} mm")
    elif 'deltext' in e:
        hit = [d for d in b.GetDrawings() if d.GetClass() in ('PCB_TEXT', 'PTEXT') and d.GetText() == e['deltext']
               and (not e.get('layer') or b.GetLayerName(d.GetLayer()) == e['layer'])]
        if len(hit) != 1:
            sys.exit(f'edit {i}: deltext matched {len(hit)} texts')
        kill(hit[0])
        print(f"  deltext '{e['deltext']}'")
    elif 'addtext' in e:
        t = pcbnew.PCB_TEXT(b)
        t.SetText(e['addtext'])
        t.SetLayer(b.GetLayerID(e.get('layer', 'F.Silkscreen')))
        t.SetPosition(V(e['x'], e['y']))
        h = int(round(e.get('size', 1.0) * 1e6))
        t.SetTextSize(pcbnew.VECTOR2I(h, h))
        t.SetTextThickness(int(round(e.get('stroke', 0.15) * 1e6)))
        t.SetTextAngleDegrees(e.get('rot', 0))
        if e.get('layer', 'F.Silkscreen').startswith('B.'):
            t.SetMirrored(True)
        if e.get('justify') in ('left', 'right'):  # multi-line notes: the anchor is the first line's start / end
            t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT if e['justify'] == 'left' else pcbnew.GR_TEXT_H_ALIGN_RIGHT)
            t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_TOP)
            t.SetPosition(V(e['x'], e['y']))
        b.Add(t)
        print(f"  addtext '{e['addtext']}' {e.get('layer', 'F.Silkscreen')} at ({e['x']}, {e['y']}) rot {e.get('rot', 0)}")
    elif 'addrect' in e:
        # unfilled graphic rectangle on a board layer (silk S/N box, drawing frames)
        s = pcbnew.PCB_SHAPE(b)
        s.SetShape(pcbnew.SHAPE_T_RECT)
        s.SetLayer(b.GetLayerID(e['addrect']))
        s.SetStart(V(*e['start']))
        s.SetEnd(V(*e['end']))
        s.SetWidth(int(round(e.get('w', 0.15) * 1e6)))
        s.SetFilled(False)
        b.Add(s)
        print(f"  addrect {e['addrect']} {e['start']} - {e['end']} w {e.get('w', 0.15)}")
    elif 'titleblock' in e:
        # title-block fields (date feeds ${ISSUE_DATE} on the silkscreen): date, rev, title, company, comment1..9
        tb = b.GetTitleBlock()
        for k, v in e['titleblock'].items():
            if k == 'date':
                tb.SetDate(v)
            elif k == 'rev':
                tb.SetRevision(v)
            elif k == 'title':
                tb.SetTitle(v)
            elif k == 'company':
                tb.SetCompany(v)
            elif k.startswith('comment') and k[7:].isdigit():
                tb.SetComment(int(k[7:]) - 1, v)
            else:
                sys.exit(f'edit {i}: unknown titleblock key {k}')
        b.SetTitleBlock(tb)
        print('  titleblock ' + ', '.join(f'{k}={v!r}' for k, v in e['titleblock'].items()))
    elif 'padpaste' in e:
        # pin-in-paste: add the paste layer of the footprint's side to its plated through-hole pads with the given
        # number (e.g. the USB-C shell tabs "SH") and set their local paste margin (mm; positive = overprint)
        f = b.FindFootprintByReference(e['padpaste'])
        if f is None:
            sys.exit(f'edit {i}: no footprint {e["padpaste"]}')
        paste = pcbnew.B_Paste if f.IsFlipped() else pcbnew.F_Paste
        hit = [p for p in f.Pads() if p.GetNumber() in e['pads'] and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
        if not hit:
            sys.exit(f'edit {i}: no plated pads {e["pads"]} on {e["padpaste"]}')
        for p in hit:
            ls = p.GetLayerSet()
            ls.AddLayer(paste)
            p.SetLayerSet(ls)
            p.SetLocalSolderPasteMargin(int(round(e.get('margin', 0.0) * 1e6)))
        print(f"  padpaste {e['padpaste']} pads {e['pads']}: {len(hit)} PTH pad(s) + {b.GetLayerName(paste)}, margin {e.get('margin', 0.0)} mm")
    elif 'fpzone_from_lib' in e:
        # copy the footprint's own (keep-out) zone settings from its library copy, zone by zone in order; the
        # outline and position stay as placed. Clears lib_footprint_mismatch caused by legacy zone parameters.
        f = b.FindFootprintByReference(e['fpzone_from_lib'])
        fid = f.GetFPID()
        lib = pcbnew.FootprintLoad(os.path.join(e['lib_dir'], str(fid.GetLibNickname()) + '.pretty'), str(fid.GetLibItemName()))
        if lib is None:
            sys.exit(f'edit {i}: library footprint not found for {e["fpzone_from_lib"]}')
        zs, ls = list(f.Zones()), list(lib.Zones())
        if len(zs) != len(ls):
            sys.exit(f'edit {i}: {len(zs)} zones on the board, {len(ls)} in the library')
        for z, lz in zip(zs, ls):
            z.SetMinThickness(lz.GetMinThickness())
            z.SetThermalReliefGap(lz.GetThermalReliefGap())
            z.SetThermalReliefSpokeWidth(lz.GetThermalReliefSpokeWidth())
            z.SetIslandRemovalMode(lz.GetIslandRemovalMode())
            z.SetPadConnection(lz.GetPadConnection())
            z.SetLocalClearance(lz.GetLocalClearance())
        print(f"  fpzone_from_lib {e['fpzone_from_lib']}: {len(zs)} zone(s) set from {fid.GetUniStringLibId()}")
    elif 'lockall' in e:
        # {"lockall": true, "tracks": true, "except": ["REF", ...]}: lock every footprint (and, with tracks, every
        # track, arc and via) so a later push-and-shove pass cannot drag finished placement or copper (P1-24, 2026-10-04)
        skip = set(e.get('except', []))
        nf = nt = 0
        for f in b.GetFootprints():
            if f.GetReference() not in skip and not f.IsLocked():
                f.SetLocked(True)
                nf += 1
        if e.get('tracks'):
            for t in b.GetTracks():
                if not t.IsLocked():
                    t.SetLocked(True)
                    nt += 1
        print(f"  lockall: {nf} footprints" + (f", {nt} tracks/vias" if e.get('tracks') else '') + ' newly locked')
    elif 'fpattr' in e:
        # footprint fabrication attributes: exclude_pos (position/CPL files), exclude_bom, dnp
        f = b.FindFootprintByReference(e['fpattr'])
        if f is None:
            sys.exit(f'edit {i}: no footprint {e["fpattr"]}')
        bits = {'exclude_pos': pcbnew.FP_EXCLUDE_FROM_POS_FILES, 'exclude_bom': pcbnew.FP_EXCLUDE_FROM_BOM}
        a = f.GetAttributes()
        for k, bit in bits.items():
            if k in e:
                a = (a | bit) if e[k] else (a & ~bit)
        f.SetAttributes(a)
        if 'dnp' in e:
            f.SetDNP(bool(e['dnp']))
        print(f"  fpattr {e['fpattr']}: " + ', '.join(f'{k}={e[k]}' for k in ('exclude_pos', 'exclude_bom', 'dnp') if k in e))
    else:
        sys.exit(f'edit {i}: unknown {e}')
pcbnew.SaveBoard(dst, b)
for ext in ('.kicad_pro', '.kicad_dru'):
    a = os.path.splitext(src)[0] + ext
    if os.path.isfile(a):
        shutil.copy2(a, os.path.splitext(dst)[0] + ext)
print(f"pen: {len(edits)} edits -> {dst}")
if any('track' in e or 'via' in e or 'arc' in e for e in edits):
    r = subprocess.run([sys.executable, os.path.abspath(__file__), '--check', dst, ej], capture_output=True, text=True)
    print('\n'.join(ln for ln in r.stdout.splitlines() if 'CHECK' in ln or ln.startswith('check:')))

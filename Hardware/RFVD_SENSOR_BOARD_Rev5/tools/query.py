"""query.py - read-only board inspection, one tool with subcommands (replaces whois/netcu/nearcu/tdiff/zlist/
edgescan/freespot scratch helpers, 2026-10-02). KiCad python; never writes a board.

  query.py part  BOARD REF[,REF...]            value, footprint, side, pose, DNP, pad nets, datasheet rule (sensitivity.json)
  query.py net   BOARD NET [NET...]            pads, tracks (layer, ends, width) and vias of the nets (short names ok)
  query.py near  BOARD NET@x,y [...]           nearest copper (pad / track / via) of NET to the point
  query.py diff  A.kicad_pcb B.kicad_pcb [NET...]   copper items only in A / only in B (each board in its own process)
  query.py zones BOARD                         rule areas: layers, bbox, bans
  query.py edge  BOARD [--within 3]            outline items and footprints whose courtyard is within N mm of the real edge
  query.py free  BOARD REF SIDE x0,y0,x1,y1 tx,ty [--step 0.25] [--copper] [--limit 12]
                                               legal courtyard spots for REF on SIDE (F|B) nearest (tx,ty): outline - 0.3,
                                               courtyards 0.02 apart, footprint keep-outs, B-side height windows.
                                               --copper: every pad must also keep the class clearance from other-net copper
                                               (tracks, vias, pads, non-GND fills) - spots a hand move can really use.
"""
import json
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SENS = os.path.join(HERE, '..', 'docs', 'sensitivity.json')
# footprint keep-out rule areas (DRU v3_keepout_F/B_footprints, v3_K7_boss_no_footprint) and B-side height windows
BAN_PATS = ('K4_TFT_LOOP', 'K11_*', 'K6_B_RF_END', 'K10B_HSE_SHADOW', 'K12_*', 'K13_U402_VIAFIELD', 'K16_DISP_LANE', 'K7_H?')
HWIN_NAMES = ('K9_BATT_WINDOW', 'K8_SHIELD_BAY')


def short(n):
    return n.split('/')[-1]


def side_of(f):
    return 'B' if f.IsFlipped() else 'F'


_CCACHE = {}


def courtyard(f):
    """courtyard polygon of f on its own side (cached per pose; boards are not edited by query users)"""
    import pcbnew
    import mr
    p = f.GetPosition()
    k = (f.GetReference(), p.x, p.y, f.GetOrientationDegrees(), f.IsFlipped())
    if k not in _CCACHE:
        if hasattr(f, 'BuildCourtyardCaches'):
            f.BuildCourtyardCaches()
        _CCACHE[k] = mr.poly_of(f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd))
    return _CCACHE[k]


_KCACHE = {}


def keepouts(b):
    """footprint keep-out polygons per side, and the B-side height windows (cached per board object)"""
    if id(b) in _KCACHE:
        return _KCACHE[id(b)]
    import fnmatch
    import pcbnew
    import mr
    bans = {'F': [], 'B': []}
    hwin = []
    for z in b.Zones():
        if not z.GetIsRuleArea():
            continue
        name = z.GetZoneName()
        g = mr.poly_of(z.Outline())
        if name in HWIN_NAMES:
            hwin.append(g)
        if any(fnmatch.fnmatchcase(name, p) for p in BAN_PATS) or z.GetDoNotAllowFootprints():
            for s_, lid in (('F', pcbnew.F_Cu), ('B', pcbnew.B_Cu)):
                if z.IsOnLayer(lid):
                    bans[s_].append(g)
    _KCACHE[id(b)] = (bans, hwin)
    return bans, hwin


def copper_index(b, skip_ref):
    """other copper per layer for pad-vs-copper checks: {layer_id: (STRtree, [(geom, net, kind)])}"""
    import pcbnew
    import mr
    from shapely.geometry import LineString, Point
    from shapely.strtree import STRtree
    items = {}
    lids = list(b.GetEnabledLayers().CuStack())
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            c = t.GetPosition()
            g = Point(c.x / 1e6, c.y / 1e6).buffer(t.GetWidth(pcbnew.F_Cu) / 2e6, 12)
            for lid in lids:
                items.setdefault(lid, []).append((g, t.GetNetname(), 'via'))
        else:
            g = LineString([(t.GetStart().x / 1e6, t.GetStart().y / 1e6), (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)]).buffer(t.GetWidth() / 2e6, 6)
            items.setdefault(t.GetLayer(), []).append((g, t.GetNetname(), 'track'))
    for f in b.GetFootprints():
        if f.GetReference() == skip_ref:
            continue
        for p in f.Pads():
            for lid in lids:
                if p.IsOnLayer(lid):
                    items.setdefault(lid, []).append((mr.poly_of(p.GetEffectivePolygon(lid, pcbnew.ERROR_OUTSIDE)), p.GetNetname(), 'pad'))
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetname() in ('GND', ''):
            continue
        for lid in lids:
            if z.IsOnLayer(lid):
                items.setdefault(lid, []).append((mr.poly_of(z.GetFilledPolysList(lid)), z.GetNetname(), 'pad'))
    return {lid: (STRtree([g for g, _, _ in lst]), lst) for lid, lst in items.items()}


def pad_shapes(b, fp, side):
    """[(layer_id, poly relative to the footprint origin, mirrored for a side change, net)] of fp's copper pads"""
    import pcbnew
    import mr
    from shapely import affinity
    o = fp.GetPosition()
    out = []
    for p in fp.Pads():
        for lid in (pcbnew.F_Cu, pcbnew.B_Cu):
            if not p.IsOnLayer(lid):
                continue
            g = affinity.translate(mr.poly_of(p.GetEffectivePolygon(lid, pcbnew.ERROR_OUTSIDE)), -o.x / 1e6, -o.y / 1e6)
            nl = lid
            if side != side_of(fp):
                g = affinity.scale(g, -1, 1, origin=(0, 0))
                nl = pcbnew.B_Cu if lid == pcbnew.F_Cu else pcbnew.F_Cu
            out.append((nl, g, p.GetNetname()))
    return out


def free_spots(b, ref, side, win, target, step=0.25, rots=(0, 90, 180, 270), limit=12, min_sep=1.0, copper=False):
    """legal courtyard poses of REF on SIDE inside win=(x0,y0,x1,y1), nearest target first: [(dist, x, y, rot)].
    copper=True also requires every pad at the pose to keep the class clearance (mr.need) from other-net copper
    (tracks, vias, other pads, non-GND fills); the part's own old tracks are same-net and allowed."""
    from shapely import affinity
    from shapely.geometry import box
    from shapely.strtree import STRtree
    fp = b.FindFootprintByReference(ref)
    s0 = side_of(fp)
    c_now = courtyard(fp)
    o = fp.GetPosition()
    ox, oy, r0 = o.x / 1e6, o.y / 1e6, fp.GetOrientationDegrees()
    c0 = affinity.translate(c_now, -ox, -oy)
    if side != s0:
        c0 = affinity.scale(c0, -1, 1, origin=(0, 0))
    cu = copper_index(b, ref) if copper else None
    pads0 = pad_shapes(b, fp, side) if copper else []

    def copper_ok(x, y, rot):
        import mr
        for lid, g0, net in pads0:
            g = affinity.translate(affinity.rotate(g0, -(rot - r0), origin=(0, 0)), x, y)
            if lid not in cu:
                continue
            tree, lst = cu[lid]
            for k in tree.query(g.buffer(1.0)):
                g2, n2, kind = lst[k]
                if n2 != net and g.distance(g2) < mr.need(net, n2, kind, frozenset()) - 1e-3:
                    return False
        return True
    others = [courtyard(f) for f in b.GetFootprints() if f.GetReference() != ref and side_of(f) == side]
    bans, hwin = keepouts(b)
    obst = [g for g in others if not g.is_empty] + bans[side]
    tree = STRtree(obst)
    bb = b.GetBoardEdgesBoundingBox()
    inner = box(bb.GetX() / 1e6, bb.GetY() / 1e6, (bb.GetX() + bb.GetWidth()) / 1e6, (bb.GetY() + bb.GetHeight()) / 1e6).buffer(-0.3)
    in_win_now = [g.intersects(c_now) for g in hwin] if side == 'B' and s0 == 'B' else [False] * len(hwin)
    res = []
    x0, y0, x1, y1 = win
    nx, ny = int((x1 - x0) / step) + 1, int((y1 - y0) / step) + 1
    for rot in rots:
        cr = affinity.rotate(c0, -(rot - r0), origin=(0, 0))
        for i in range(nx):
            for j in range(ny):
                x, y = x0 + i * step, y0 + j * step
                g = affinity.translate(cr, x, y)
                if not inner.contains(g):
                    continue
                g2 = g.buffer(0.02)
                if any(obst[k].intersects(g2) for k in tree.query(g2)):
                    continue
                if side == 'B' and any(w.intersects(g) and not was for w, was in zip(hwin, in_win_now)):
                    continue
                res.append((math.hypot(x - target[0], y - target[1]), x, y, rot))
    res.sort()
    out = []
    for d, x, y, rot in res:
        if any(math.hypot(x - a, y - c) < min_sep for _, a, c, _ in out):
            continue
        if copper and not copper_ok(x, y, rot):
            continue
        out.append((d, x, y, rot))
        if len(out) >= limit:
            break
    return out


def cmd_part(b, refs):
    import pcbnew
    sens = json.load(open(SENS, encoding='utf-8'))['parts'] if os.path.isfile(SENS) else {}
    for f in b.GetFootprints():
        r = f.GetReference()
        if r not in refs:
            continue
        p = f.GetPosition()
        pads = ' '.join(f"{pd.GetNumber()}:{short(pd.GetNetname())}" for pd in f.Pads())
        fld = {}
        for k in ('MPN', 'Function'):
            try:
                v = f.GetFieldText(k) if f.HasField(k) else ''
            except Exception:
                v = ''
            if v:
                fld[k] = v[:90]
        s = sens.get(r, {})
        print(f"{r:6s} {f.GetValue()[:22]:22s} {f.GetFPIDAsString().split(':')[-1][:30]:30s} {side_of(f)} "
              f"({p.x / 1e6:.2f},{p.y / 1e6:.2f}) r{f.GetOrientationDegrees():.0f} dnp={f.IsDNP()} locked={f.IsLocked()}\n"
              f"       pads {pads}\n       rule sens={s.get('sensitivity', '')} anchor={s.get('anchor', '')} "
              f"max={s.get('max_mm', '')} gap={s.get('gap_mm', '')} routing={str(s.get('routing', ''))[:80]}\n       {fld}")


def cmd_net(b, nets):
    for net in nets:
        print('==', net)
        for f in b.GetFootprints():
            for p in f.Pads():
                if short(p.GetNetname()) == net or p.GetNetname() == net:
                    print(f'  pad {f.GetReference()}.{p.GetNumber()} {side_of(f)} ({p.GetPosition().x / 1e6:.2f},{p.GetPosition().y / 1e6:.2f})')
        for t in b.GetTracks():
            if short(t.GetNetname()) != net and t.GetNetname() != net:
                continue
            if t.GetClass() == 'PCB_VIA':
                print(f'  via ({t.GetPosition().x / 1e6:.2f},{t.GetPosition().y / 1e6:.2f})')
            else:
                print(f'  {b.GetLayerName(t.GetLayer())} ({t.GetStart().x / 1e6:.2f},{t.GetStart().y / 1e6:.2f})->'
                      f'({t.GetEnd().x / 1e6:.2f},{t.GetEnd().y / 1e6:.2f}) w{t.GetWidth() / 1e6:.2f}{" arc" if t.GetClass() == "PCB_ARC" else ""}')


def cmd_near(b, queries):
    for q in queries:
        net, xy = q.split('@')
        x, y = map(float, xy.split(','))
        best = []
        for f in b.GetFootprints():
            for p in f.Pads():
                if short(p.GetNetname()) == net:
                    c = p.GetPosition()
                    best.append((math.hypot(c.x / 1e6 - x, c.y / 1e6 - y), f'pad {f.GetReference()}.{p.GetNumber()} {side_of(f)}', c.x / 1e6, c.y / 1e6))
        for t in b.GetTracks():
            if short(t.GetNetname()) != net:
                continue
            if t.GetClass() == 'PCB_VIA':
                c = t.GetPosition()
                best.append((math.hypot(c.x / 1e6 - x, c.y / 1e6 - y), 'via', c.x / 1e6, c.y / 1e6))
            else:
                a, e = t.GetStart(), t.GetEnd()
                ax, ay, ex, ey = a.x / 1e6, a.y / 1e6, e.x / 1e6, e.y / 1e6
                dx, dy = ex - ax, ey - ay
                L = dx * dx + dy * dy
                u = 0 if L == 0 else max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / L))
                best.append((math.hypot(ax + u * dx - x, ay + u * dy - y), f'track {b.GetLayerName(t.GetLayer())} w{t.GetWidth() / 1e6:.2f}', ax + u * dx, ay + u * dy))
        best.sort()
        print(net, (x, y), [f'{d:.1f}mm {k} ({px:.1f},{py:.1f})' for d, k, px, py in best[:4]])


def dump_copper(path):
    import pcbnew
    b = pcbnew.LoadBoard(path)
    out = []
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            out.append(['v', t.GetNetname(), t.GetPosition().x, t.GetPosition().y, t.GetWidth(pcbnew.F_Cu)])
        else:
            out.append(['t', t.GetNetname(), b.GetLayerName(t.GetLayer()), t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y, t.GetWidth()])
    return out


def cmd_diff(a, b_, nets):
    def run(p):
        r = subprocess.run([sys.executable, os.path.abspath(__file__), '_dump', p], capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(r.stderr[-800:])
        return set(tuple(x) for x in json.loads(r.stdout.strip().splitlines()[-1]))
    A, B = run(a), run(b_)
    for tag, S in (('only in A', A - B), ('only in B', B - A)):
        rows = sorted(x for x in S if not nets or short(x[1]) in nets)
        print(tag, len(S), 'shown', len(rows))
        for x in rows:
            if x[0] == 'v':
                print('  via', short(x[1]), f'({x[2] / 1e6:.2f},{x[3] / 1e6:.2f}) d{x[4] / 1e6:.2f}')
            else:
                print('  trk', short(x[1]), x[2], f'({x[3] / 1e6:.2f},{x[4] / 1e6:.2f})->({x[5] / 1e6:.2f},{x[6] / 1e6:.2f}) w{x[7] / 1e6:.2f}')


def cmd_zones(b):
    for z in b.Zones():
        if not z.GetIsRuleArea():
            continue
        bb = z.GetBoundingBox()
        print(f"{z.GetZoneName():24s} layers {[b.GetLayerName(l) for l in z.GetLayerSet().CuStack()][:6]} "
              f"bbox ({bb.GetX() / 1e6:.1f},{bb.GetY() / 1e6:.1f})-({(bb.GetX() + bb.GetWidth()) / 1e6:.1f},{(bb.GetY() + bb.GetHeight()) / 1e6:.1f}) "
              f"fp_ban={z.GetDoNotAllowFootprints()} trk_ban={z.GetDoNotAllowTracks()} via_ban={z.GetDoNotAllowVias()}")


def cmd_edge(b, within):
    import pcbnew
    print('Edge.Cuts items:')
    for d in b.GetDrawings():
        if d.GetLayer() != pcbnew.Edge_Cuts:
            continue
        s, e = d.GetStart(), d.GetEnd()
        extra = ''
        if d.GetShapeStr().lower().startswith('arc'):
            m = d.GetArcMid()
            extra = f' mid ({m.x / 1e6:.3f},{m.y / 1e6:.3f})'
        print(f'  {d.GetShapeStr():10s} ({s.x / 1e6:.3f},{s.y / 1e6:.3f}) -> ({e.x / 1e6:.3f},{e.y / 1e6:.3f}){extra}')
    bb = b.GetBoardEdgesBoundingBox()
    x0, x1 = bb.GetX() / 1e6, (bb.GetX() + bb.GetWidth()) / 1e6
    print(f'outline x {x0:.3f}..{x1:.3f} ({x1 - x0:.2f} mm) y {bb.GetY() / 1e6:.3f}..{(bb.GetY() + bb.GetHeight()) / 1e6:.3f} ({bb.GetHeight() / 1e6:.2f} mm)')
    import mr
    ps = pcbnew.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(ps, False)
    edge = mr.poly_of(ps).boundary
    print(f'footprints whose courtyard is within {within} mm of the real board edge (notches included)')
    rows = []
    for f in b.GetFootprints():
        g = courtyard(f)
        if g.is_empty:
            continue
        d = g.distance(edge)
        if d < within:
            gx0, gy0, gx1, gy1 = g.bounds
            rows.append((d, f))
    for d, f in sorted(rows, key=lambda t: t[0]):
        g = courtyard(f)
        gx0, gy0, gx1, gy1 = g.bounds
        print(f'   {f.GetReference():6s} {side_of(f)} {f.GetValue()[:18]:18s} court x {gx0:.2f}-{gx1:.2f} y {gy0:.2f}-{gy1:.2f}  edge gap {d:.2f}')


def main():
    a = sys.argv[1:]
    if not a or a[0] in ('-h', '--help'):
        print(__doc__)
        return
    cmd = a[0]
    if cmd == '_dump':
        print(json.dumps(dump_copper(a[1])))
        return
    if cmd == 'diff':
        cmd_diff(a[1], a[2], set(a[3:]))
        return
    import pcbnew
    b = pcbnew.LoadBoard(a[1])
    if cmd == 'part':
        cmd_part(b, set(a[2].split(',')))
    elif cmd == 'net':
        cmd_net(b, a[2:])
    elif cmd == 'near':
        cmd_near(b, a[2:])
    elif cmd == 'zones':
        cmd_zones(b)
    elif cmd == 'edge':
        cmd_edge(b, float(a[a.index('--within') + 1]) if '--within' in a else 3.0)
    elif cmd == 'free':
        step = float(a[a.index('--step') + 1]) if '--step' in a else 0.25
        win = tuple(map(float, a[4].split(',')))
        tgt = tuple(map(float, a[5].split(',')))
        sp = free_spots(b, a[2], a[3], win, tgt, step, copper='--copper' in a, limit=int(a[a.index('--limit') + 1]) if '--limit' in a else 12)
        for d, x, y, rot in sp:
            print(f'{a[2]} {a[3]} ({x:.2f},{y:.2f}) rot {rot} dist {d:.1f}')
        print(f'{len(sp)} spots shown')
    else:
        sys.exit(f'unknown command {cmd}\n' + __doc__)


if __name__ == '__main__':
    main()

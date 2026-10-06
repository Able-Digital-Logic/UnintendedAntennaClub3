"""ripfix.py IN.kicad_pcb OUT.kicad_pcb TARGET ... [--pen 0.6] [--protect NET,NET] [--report R.json] [--grid 0.05]

Priority rip-up and reroute (user rules 2026-10-02: complete routing, least track, EMC rules exact).
TARGET = REF.PIN            route the island holding that pad to the nearest other island of its net
       | REF.PIN>REF2.PIN2  ... to the island holding REF2.PIN2
For each target:
  1. route with every other net's TRACKS and VIAS as soft obstacles (crossing costs --pen per 0.05 mm cell, a via in
     one 6 x pen) - pads, pours, rule areas and protected nets stay hard,
  2. rip exactly the tracks / vias the new path violates (pairwise rule model of mr.py, with the courtyard exemptions
     at their location), commit the path,
  3. re-route every ripped net island pair by pair (hard obstacles only); prune dangling stubs of the ripped nets,
  4. accept only if every ripped net is back to (at most) its island count before the rip; otherwise revert.
Ripped GND vias / stubs are not re-routed (planes; gndvip re-adds pad vias in run_post). KiCad python, scratch only."""
import json
import math
import os
import shutil
import sys
import time

import pcbnew
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import mr  # noqa: E402

argv = sys.argv[1:]


def opt(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


OPTS = ('--pen', '--protect', '--report', '--grid', '--depth', '--esc-r', '--allow')
TRUST = '--trust' in argv     # diagnostics only: skip the in-process safety check (verify with metrics.py)
src, dst = argv[0], argv[1]
targets = [a for i, a in enumerate(argv[2:], 2) if not a.startswith('--') and argv[i - 1] not in OPTS]
PEN = float(opt('--pen', '0.6'))
GRID = float(opt('--grid', '0.05'))
PROTECT = set((opt('--protect') or '').split(',')) - {''}
DEPTH = int(opt('--depth', '2'))
ESC_R = float(opt('--esc-r', '3.0'))
# never ripped: switch nodes / battery / RF, the precision analog + reference nets, clocks, and the datasheet-critical
# short nets (LSE crystal PC14/PC15, HSE PH0 / Y1 out, VCAP) whose length must not grow
PROT_CLS = ('Power_Buck_SW', 'Power_Battery', 'RF_Input', 'RF_50R', 'Analog_Precision', 'Ref_Kelvin', 'HighSpeed_Clock')
PROTECT |= {'Net-(U8-PC14)', 'Net-(U8-PC15)', 'Net-(U8-PH0)', 'Net-(Y1-OUT)', '/STM32H743 controller/VCAP'}
if os.path.normcase(os.path.realpath(dst)).startswith(mr.PROTECTED):
    sys.exit('refusing to write into the project folder')
work = dst + '.rf.kicad_pcb'
shutil.copy2(src, work)
for ext in ('.kicad_pro', '.kicad_dru'):
    s = os.path.splitext(src)[0] + ext
    if os.path.isfile(s):
        shutil.copy2(s, os.path.splitext(work)[0] + ext)
        shutil.copy2(s, os.path.splitext(dst)[0] + ext)


ALLOW = set((opt('--allow') or '').split(',')) - {''}


def rippable(n, net, chain=frozenset()):
    if n in ALLOW or n.split('/')[-1] in ALLOW:
        return n != net and n not in chain
    return n != net and n not in chain and n not in PROTECT and mr.cls(n) not in PROT_CLS and not n.startswith('unconnected')


def geom_of(t):
    if t.GetClass() == 'PCB_VIA':
        c = t.GetPosition()
        return Point(c.x / 1e6, c.y / 1e6).buffer(t.GetWidth(pcbnew.F_Cu) / 2e6, 16)
    a, c = t.GetStart(), t.GetEnd()
    return LineString([(a.x / 1e6, a.y / 1e6), (c.x / 1e6, c.y / 1e6)]).buffer(t.GetWidth() / 2e6, 8)


def key_of(t):
    if t.GetClass() == 'PCB_VIA':
        c = t.GetPosition()
        return ('via', round(c.x / 1e6, 4), round(c.y / 1e6, 4), t.GetNetname())
    a, c = t.GetStart(), t.GetEnd()
    return ('trk', t.GetLayer(), round(a.x / 1e6, 4), round(a.y / 1e6, 4), round(c.x / 1e6, 4), round(c.y / 1e6, 4),
            t.GetNetname())


def drop_from_model(B, objs):
    """remove the given board items from mr's obstacle model (matched by net + kind + exact bounds), then from the
    board. objs: list of pcbnew items collected BEFORE any removal."""
    gone = []
    for t in objs:
        g = geom_of(t)
        bb = tuple(round(v, 5) for v in g.bounds)
        net = t.GetNetname()
        kind = 'via' if t.GetClass() == 'PCB_VIA' else 'track'
        lays = mr.SIG if kind == 'via' else [B.b.GetLayerName(t.GetLayer())]
        for ln in lays:
            if ln not in B.items:
                continue
            for i, (geo, n2, k2) in enumerate(B.items[ln]):
                if n2 == net and k2 == kind and tuple(round(v, 5) for v in geo.bounds) == bb:
                    del B.items[ln][i]
                    break
        if kind == 'via':
            c = t.GetPosition()
            for i, (hp, hr, hn) in enumerate(B.holes):
                if hn == net and abs(hp.x - c.x / 1e6) < 1e-5 and abs(hp.y - c.y / 1e6) < 1e-5:
                    del B.holes[i]
                    break
        gone.append(t)
    for t in gone:
        B.b.Remove(t)
        t.thisown = 0            # keep alive (see highway.py): freed removed items corrupt KiCad's connectivity
        mr._GRAVE.append(t)
    B.rebuild()


def isl_index(isl, xy):
    for k, I in enumerate(isl):
        for p in I.get('__pads__', []):
            if abs(p[0] - xy[0]) < 1e-3 and abs(p[1] - xy[1]) < 1e-3:
                return k
    return None


def igeo(I):
    return unary_union([v for k_, v in I.items() if not k_.startswith('__') and not v.is_empty])


def violated(B, net, segs, vias, w, chain=frozenset()):
    """board items of other (rippable) nets that the new copper violates."""
    b = B.b
    path = {ln: [] for ln in mr.SIG}
    for ln, a, c, ww in segs:
        path[ln].append(LineString([a, c]).buffer(ww / 2, 8))
    vg = [Point(x, y).buffer(vd / 2, 16) for x, y, vd, vh in vias]
    for ln in mr.SIG:
        path[ln] += vg
    allp = unary_union([g for ln in mr.SIG for g in path[ln]]) if any(path.values()) else None
    if allp is None:
        return []
    zone = allp.buffer(2.2)
    out = []
    for t in b.GetTracks():
        n2 = t.GetNetname()
        if n2 == net:
            continue
        g = geom_of(t)
        if not g.intersects(zone):
            continue
        kind = 'via' if t.GetClass() == 'PCB_VIA' else 'track'
        lays = mr.SIG if kind == 'via' else [b.GetLayerName(t.GetLayer())]
        ex = frozenset(k for k, e in B.pexempt.items() if e.intersects(g))
        bad = False
        for ln in lays:
            if ln not in path:
                continue
            for pg in path[ln]:
                if pg.distance(g) < mr.need(net, n2, kind, ex) - 1e-4:
                    bad = True
                    break
            if bad:
                break
        if not bad and kind == 'via':
            c = t.GetPosition()
            for x, y, vd, vh in vias:
                if math.hypot(x - c.x / 1e6, y - c.y / 1e6) < vh / 2 + t.GetDrill() / 2e6 + 0.25 - 1e-4:
                    bad = True
        if bad:
            if not rippable(n2, net, chain):
                return None          # would need to rip protected copper: the soft model should have prevented it
            out.append(t)
    return out


def prune(B, nets):
    """remove dangling track ends (an end touching no pad, via or other track of its net) of the given nets."""
    b = B.b
    removed = 0
    for _ in range(30):
        b.BuildConnectivity()
        ends = {}
        objs = [t for t in b.GetTracks() if t.GetNetname() in nets]
        pads = [p for f in b.GetFootprints() for p in f.Pads() if p.GetNetname() in nets]
        dead = []
        for t in objs:
            if t.GetClass() == 'PCB_VIA':
                continue
            for e in (t.GetStart(), t.GetEnd()):
                pt = Point(e.x / 1e6, e.y / 1e6)
                ok = False
                for p in pads:
                    if p.GetNetname() == t.GetNetname() and p.IsOnLayer(t.GetLayer()) and \
                            mr.poly_of(p.GetEffectivePolygon(t.GetLayer(), pcbnew.ERROR_OUTSIDE)).buffer(1e-3).contains(pt):
                        ok = True
                        break
                if not ok:
                    for o in objs:
                        if o is t or o.GetNetname() != t.GetNetname():
                            continue
                        if o.GetClass() == 'PCB_VIA':
                            c = o.GetPosition()
                            if math.hypot(c.x / 1e6 - pt.x, c.y / 1e6 - pt.y) <= o.GetWidth(pcbnew.F_Cu) / 2e6 + 1e-3:
                                ok = True
                                break
                        elif o.GetLayer() == t.GetLayer():
                            seg = LineString([(o.GetStart().x / 1e6, o.GetStart().y / 1e6), (o.GetEnd().x / 1e6, o.GetEnd().y / 1e6)])
                            if seg.distance(pt) <= o.GetWidth() / 2e6:
                                ok = True
                                break
                if not ok:
                    # zones of the net (pours) also hold an end
                    for z in b.Zones():
                        if not z.GetIsRuleArea() and z.GetNetname() == t.GetNetname() and z.IsOnLayer(t.GetLayer()) and \
                                mr.poly_of(z.GetFilledPolysList(t.GetLayer())).contains(pt):
                            ok = True
                            break
                if not ok:
                    dead.append(t)
                    break
        # vias touching nothing but at most one track end are dangling too
        for v in objs:
            if v.GetClass() != 'PCB_VIA':
                continue
            c = v.GetPosition()
            r = v.GetWidth(pcbnew.F_Cu) / 2e6
            n_t = sum(1 for o in objs if o.GetClass() != 'PCB_VIA' and o.GetNetname() == v.GetNetname() and any(
                math.hypot(e.x / 1e6 - c.x / 1e6, e.y / 1e6 - c.y / 1e6) <= r + 1e-3 for e in (o.GetStart(), o.GetEnd())))
            on_pad = any(p.GetNetname() == v.GetNetname() and mr.poly_of(p.GetEffectivePolygon(
                pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu, pcbnew.ERROR_OUTSIDE)).contains(Point(c.x / 1e6, c.y / 1e6))
                for p in pads)
            in_zone = any(not z.GetIsRuleArea() and z.GetNetname() == v.GetNetname() and any(
                z.IsOnLayer(lid) and mr.poly_of(z.GetFilledPolysList(lid)).contains(Point(c.x / 1e6, c.y / 1e6))
                for lid in z.GetLayerSet().CuStack()) for z in b.Zones())
            if n_t == 0 and not on_pad and not in_zone:
                dead.append(v)
        if not dead:
            break
        seen = set()
        uniq = []
        for t in dead:
            k = t.m_Uuid.AsString()
            if k not in seen:
                seen.add(k)
                uniq.append(t)
        drop_from_model(B, uniq)
        removed += len(uniq)
    return removed


def board_metrics(b):
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    """(U, E): KiCad's unconnected-connection count, and the number of non-GND pads carrying tracks / vias
    (an escape is progress even before its net connects). A fix is kept only if U drops (ESC: E grows) and E never
    shrinks - the safety net against a rip-up that silently breaks or strips another net."""
    b.BuildConnectivity()
    conn = b.GetConnectivity()
    U = conn.GetUnconnectedCount(False)
    E = 0
    for f in b.GetFootprints():
        for p in f.Pads():
            n = p.GetNetname()
            if not n or n == 'GND' or n.startswith('unconnected'):
                continue
            for it in conn.GetConnectedItems(p):
                it = it.Cast() if hasattr(it, 'Cast') else it
                if it.GetClass() in ('PCB_TRACK', 'PCB_ARC', 'PCB_VIA'):
                    E += 1
                    break
    return U, E


def soft_set(B, net, chain=frozenset()):
    soft = set()
    via_pts = {}
    for t in B.b.GetTracks():
        if t.GetClass() == 'PCB_VIA' and rippable(t.GetNetname(), net, chain):
            c = t.GetPosition()
            via_pts[(round(c.x / 1e6, 4), round(c.y / 1e6, 4))] = t.GetNetname()
    for ln in mr.SIG:
        for geo, n2, kind in B.items[ln]:
            if kind in ('track', 'via') and rippable(n2, net, chain):
                soft.add(id(geo))
    for hp, hr, hn in B.holes:
        if via_pts.get((round(hp.x, 4), round(hp.y, 4))) == hn:
            soft.add(id(hp))
    return soft


def nearest_pair(isl):
    gs = [igeo(I) for I in isl]
    return min((gs[i].distance(gs[j]), i, j) for i in range(len(isl)) for j in range(i + 1, len(isl)))


def copper_pads(B, net):
    """pads of net that carry tracks / vias (escapes count)"""
    B.b.BuildConnectivity()
    conn = B.b.GetConnectivity()
    out = []
    for p in B.pads_by_net.get(net, []):
        for it in conn.GetConnectedItems(p):
            it = it.Cast() if hasattr(it, 'Cast') else it
            if it.GetClass() in ('PCB_TRACK', 'PCB_ARC', 'PCB_VIA'):
                out.append(p)
                break
    return out


def esc_target(R, net, pad):
    """(A, T): the pad's island and an escape target - any free cell of the inner signal layer (B for nets kept
    off In3) within ESC_R of the pad, outside the pad's own island"""
    axy = (pad.GetPosition().x / 1e6, pad.GetPosition().y / 1e6)
    isl = R.islands(net)
    ia = isl_index(isl, axy)
    if ia is None:
        return None
    el = 'B.Cu' if mr.cls(net) in ('Analog_Precision', 'Ref_Kelvin', 'RF_Input', 'RF_50R') else 'In3.Cu'
    own = igeo(isl[ia]).buffer(0.35)
    T = {ln: Polygon() for ln in mr.SIG}
    T[el] = Point(axy).buffer(ESC_R).difference(own)
    T['__pads__'] = []
    return isl[ia], T


def rip_route(R, B, net, A, T, depth, chain, log):
    """route A -> T for net; with depth > 0 other nets' tracks/vias may be ripped (and are re-routed with depth-1).
    Returns True when the path is committed and every ripped net is back to its island count."""
    res, why = R.route_pair(net, A, T)
    if res is not None:
        R.commit(net, res[0], res[1])
        return True
    if depth <= 0:
        log.append(f"{net.split('/')[-1]}: {why}")
        return False
    res, why = R.route_pair(net, A, T, soft_ids=soft_set(B, net, chain), soft_pen=PEN)
    if res is None:
        log.append(f"{net.split('/')[-1]}: no path even with rip-up ({why})")
        return False
    segs, vias, w = res
    victims = violated(B, net, segs, vias, w, chain)
    if victims is None:
        log.append(f"{net.split('/')[-1]}: path needs protected copper")
        return False
    vnets = sorted(set(t.GetNetname() for t in victims) - {'GND'})
    before = {n: len(R.islands(n)) for n in vnets}
    had = {n: copper_pads(B, n) for n in vnets}
    log.append(f"{net.split('/')[-1]}: rips {len(victims)} items of "
               f"{[n.split('/')[-1] for n in sorted(set(t.GetNetname() for t in victims))]}")
    drop_from_model(B, victims)
    R.commit(net, segs, vias)
    for n in vnets:
        if not rejoin(R, B, n, before[n], depth - 1, chain | {net}, log):
            return False
    prune(B, set(vnets))
    # escapes the rip took away (a lone pin's stub + via: no island count changes) are rebuilt
    for n in vnets:
        now = set(p.m_Uuid.AsString() for p in copper_pads(B, n))
        for p in had[n]:
            if p.m_Uuid.AsString() in now:
                continue
            at = esc_target(R, n, p)
            if at is None or not rip_route(R, B, n, at[0], at[1], depth - 1, chain | {net}, log):
                log.append(f"   re-escape {n.split('/')[-1]} failed")
                return False
            log.append(f"   re-escaped {n.split('/')[-1]}")
    return True


def rejoin(R, B, net, limit, depth, chain, log):
    for _ in range(40):
        isl = R.islands(net)
        if len(isl) <= limit:
            return True
        d, i, j = nearest_pair(isl)
        if not rip_route(R, B, net, isl[i], isl[j], depth, chain, log):
            log.append(f"   rejoin {net.split('/')[-1]} failed (gap {d:.2f})")
            return False
    return len(R.islands(net)) <= limit


report = []
for tg in targets:
    B = mr.Board(work, ('*',))
    R = mr.Router(B, grid=GRID)
    b = B.b
    if tg.startswith('ESCN:'):
        # ESCN:NET@REF - escape REF's pad on NET (resolved on the current board)
        nm, _, rf = tg[5:].partition('@')
        fp_ = b.FindFootprintByReference(rf)
        pd_ = next((q for q in fp_.Pads() if q.GetNetname() == nm or q.GetNetname().split('/')[-1] == nm), None) if fp_ else None
        if pd_ is None:
            print(f"{tg}: pad not found")
            continue
        tg = f"ESC:{rf}.{pd_.GetNumber()}"
    esc = tg.startswith('ESC:')
    spec = tg[4:] if (esc or tg.startswith('NET:')) else tg
    if tg.startswith('NET:'):
        net = next((n for n in B.pads_by_net if n == spec or n.split('/')[-1] == spec), None)
        if net is None:
            print(f"{tg}: no such net")
            continue
        isl = R.islands(net)
        if len(isl) < 2:
            print(f"{tg}: already complete")
            continue
        _, ia, ib = nearest_pair(isl)
        T = isl[ib]
    else:
        a_ref, a_pin = spec.split('>')[0].split('.')
        pad = next(p for p in b.FindFootprintByReference(a_ref).Pads() if p.GetNumber() == a_pin)
        net = pad.GetNetname()
        axy = (pad.GetPosition().x / 1e6, pad.GetPosition().y / 1e6)
        isl = R.islands(net)
        ia = isl_index(isl, axy)
        if ia is None:
            print(f"{tg}: pad island not found")
            continue
        if esc:
            # escape target: any free cell of the inner signal layer (B for nets kept off In3) within ESC_R of the
            # pad, outside the pad's own island - the path is the pin stub + one via; intermod joins the via later
            if len(set(isl[ia]['__pads__'])) > 1 or not isl[ia]['In3.Cu'].is_empty:
                print(f"{tg}: pad already has an escape / local copper")
                continue
            _, T = esc_target(R, net, pad)
        else:
            if '>' in spec:
                t_ref, t_pin = spec.split('>')[1].split('.')
                tp = next(p for p in b.FindFootprintByReference(t_ref).Pads() if p.GetNumber() == t_pin)
                ib = isl_index(isl, (tp.GetPosition().x / 1e6, tp.GetPosition().y / 1e6))
            else:
                ga = igeo(isl[ia])
                cand = [(ga.distance(igeo(I)), k) for k, I in enumerate(isl) if k != ia]
                ib = min(cand)[1] if cand else None
            if ib is None or ib == ia:
                print(f"{tg}: nothing to do ({len(isl)} islands)")
                continue
            T = isl[ib]
    n_before = len(isl)
    ts = time.time()
    log = []
    U0, E0 = board_metrics(b)
    ok = rip_route(R, B, net, isl[ia], T, DEPTH, frozenset(), log)
    for l_ in log:
        print('   ' + l_)
    if ok:
        U1, E1 = board_metrics(b)
        good = (U1 <= U0 and E1 > E0) if (esc and net != 'GND') else (U1 < U0 and E1 >= E0)
        if TRUST:
            good = True
        if not good:
            print(f"   safety check failed: unconnected {U0}->{U1}, pads with copper {E0}->{E1}")
            ok = False
    if ok:
        after = len(R.islands(net))
        pcbnew.SaveBoard(work, b)
        print(f"{tg} {net.split('/')[-1]}: OK islands {n_before}->{after} ({time.time() - ts:.0f} s)")
        report.append({'target': tg, 'net': net, 'ok': True, 'log': log, 'islands': [n_before, after]})
    else:
        print(f"{tg} {net.split('/')[-1]}: reverted ({time.time() - ts:.0f} s)")
        report.append({'target': tg, 'net': net, 'ok': False, 'log': log})
    sys.stdout.flush()
shutil.copy2(work, dst)
if opt('--report'):
    json.dump(report, open(opt('--report'), 'w'), indent=1)
print(f"ripfix: {sum(1 for r in report if r['ok'])} of {len(report)} targets fixed -> {dst}")

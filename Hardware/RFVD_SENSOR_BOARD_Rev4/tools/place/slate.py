"""slate.py IN.kicad_pcb OUT.kicad_pcb --layer In3.Cu [--min-len 1.0] [--report R.json]

Clean-slate re-lay of one routing layer into 'signal highways' (user request 2026-10-02 night).
All chains on --layer of the ordinary signal nets (Default / HighSpeed_Digital / Harness_IO, minus protected buses;
a chain = run of track between terminals: pads, vias, T-junctions) are lifted AT ONCE, then re-laid one by one between
the SAME two end points, longest run along the layer's preferred axis first, with the router's direction preference
(MR_DIRPREF / MR_DIR_PERP / MR_DIR_DIAG), bend penalty (MR_T45) and bundling reward (MR_BUNDLE) - so the long runs form
parallel lanes and the short ones fit around them.
  round 1: the chain must stay on --layer (no new vias);
  round 2 (chains that failed): layer changes allowed;
  round 3 (still failing): the OLD chain is put back if it is still legal against the new copper.
Anything still unplaced is reported as LOST; the caller must reject the result unless LOST == 0 (metrics.py check).
Terminals never move, so connectivity is unchanged when nothing is lost. KiCad python, scratch copies only."""
import collections
import fnmatch
import json
import math
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
argv = sys.argv[1:]


def opt(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


SRC0, DST0 = argv[0], argv[1]
src, dst = SRC0, DST0
LAYER = opt('--layer', 'In3.Cu')
MAXIT = int(opt('--iters', '4'))
FORCE = '--no-force' not in argv
MINLEN = float(opt('--min-len', '1.0'))
# reuse highway2's model helpers (snapshot, chains_of, remove/add, route_between, costs) without running its passes
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'highway2.py'), encoding='utf-8').read()
_cut = _src.index('nets = []')
sys.argv = ['highway2.py', src, dst + '.slate_work.kicad_pcb']
exec(compile(_src[:_cut], 'highway2_head', 'exec'))
import pcbnew  # noqa: E402,F811
from shapely.geometry import LineString, Point  # noqa: E402,F811

ORDER_AXIS = None
regs, dflt = mr.DIRPREF.get(LAYER, ([], None))
ORDER_AXIS = dflt
nets = []
for net in sorted(B.pads_by_net):
    if not net or net == 'GND' or net.startswith('unconnected'):
        continue
    if mr.cls(net) not in OK_CLS or any(fnmatch.fnmatchcase(net, p) or fnmatch.fnmatchcase(net.split('/')[-1], p) for p in SKIP_PATS):
        continue
    nets.append(net)
lifted = []      # (net, chain_params, ea, eb, width)
for net in nets:
    tr, vi = snapshot(net)
    for ln, chain, ea, eb in chains_of(net, tr, vi):
        if ln != LAYER:
            continue
        params = [tr[k] for k in chain]
        L = sum(math.hypot(t[2][0] - t[1][0], t[2][1] - t[1][1]) for t in params) / 1e6
        if L < MINLEN or ea == eb:
            continue
        lifted.append((net, params, ea, eb, params[0][3]))
t0 = time.time()
old_cost = 0.0
for net, params, ea, eb, w in lifted:
    old_cost += cost_mm([(t[0], (t[1][0] / 1e6, t[1][1] / 1e6), (t[2][0] / 1e6, t[2][1] / 1e6)) for t in params], 0)
by_net = collections.defaultdict(list)
for item in lifted:
    by_net[item[0]].append(item)
for net, items in by_net.items():
    remove_items(net, [t for it in items for t in it[1]], [])
print(f"slate {LAYER}: lifted {len(lifted)} chains of {len(by_net)} nets (old cost {old_cost:.0f}); axis {ORDER_AXIS}")


def span(it):
    (x0, y0), (x1, y1) = it[2], it[3]
    if ORDER_AXIS == 'V':
        return abs(y1 - y0)
    if ORDER_AXIS == 'H':
        return abs(x1 - x0)
    return math.hypot(x1 - x0, y1 - y0)


def place_all(order):
    """place chains in this order (round 1 same layer, round 2 any layer, round 3 old copper if legal);
    returns (added_params, lost, cost)"""
    added = []                  # (net, tp, vp) everything this attempt added (new or restored)
    cost = 0.0
    queue = list(order)
    for rnd in (1, 2):
        R.layers = [LAYER] if rnd == 1 else all_layers
        nxt = []
        for net, params, ea, eb, w in queue:
            pa, pb = (ea[0] / 1e6, ea[1] / 1e6), (eb[0] / 1e6, eb[1] / 1e6)
            r_ = route_between(net, LAYER, pa, LAYER, pb, w / 1e6)
            if r_ is None:
                nxt.append((net, params, ea, eb, w))
                continue
            tp, vp = to_params(r_[0], r_[1], w)
            if non_octilinear(tp):
                nxt.append((net, params, ea, eb, w))
                continue
            add_items(net, tp, vp)
            added.append((net, tp, vp, (net, params, ea, eb, w)))
            cost += cost_mm([(l_, (a[0] / 1e6, a[1] / 1e6), (c[0] / 1e6, c[1] / 1e6)) for l_, a, c, ww in tp], len(vp))
        queue = nxt
    R.layers = all_layers
    lost = []
    for net, params, ea, eb, w in queue:
        ok = True
        for ln, a, c, ww in params:
            g = LineString([(a[0] / 1e6, a[1] / 1e6), (c[0] / 1e6, c[1] / 1e6)]).buffer(ww / 2e6, 8)
            ex = frozenset(k for k, e in B.pexempt.items() if e.intersects(g))
            for i in B.trees[ln].query(g.buffer(3.1)):
                geo, n2, kind = B.items[ln][i]
                if n2 != net and geo.distance(g) < mr.need(net, n2, kind, ex) - 1e-4:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            add_items(net, params, [])
            added.append((net, params, [], None))          # old copper: fixed from now on
            cost += cost_mm([(t[0], (t[1][0] / 1e6, t[1][1] / 1e6), (t[2][0] / 1e6, t[2][1] / 1e6)) for t in params], 0)
        else:
            lost.append((net, params, ea, eb, w))
    # round 4: force the old copper of a lost chain back, rip only the NEW chains that conflict with it and re-lay them
    # (any layer, else their own old copper); old copper is never ripped, so this only shrinks the lost list
    if lost and FORCE:
        still = []
        for net, params, ea, eb, w in lost:
            geos = [(ln, LineString([(a[0] / 1e6, a[1] / 1e6), (c[0] / 1e6, c[1] / 1e6)]).buffer(ww / 2e6, 8)) for ln, a, c, ww in params]
            conflicts = []
            for k, (n2, tp2, vp2, spec2) in enumerate(added):
                if n2 == net or spec2 is None:
                    continue
                hit = False
                for ln2, a2, c2, w2 in tp2:
                    g2 = LineString([(a2[0] / 1e6, a2[1] / 1e6), (c2[0] / 1e6, c2[1] / 1e6)]).buffer(w2 / 2e6, 8)
                    for ln, g in geos:
                        if ln == ln2 and g.distance(g2) < mr.need(net, n2, 'track', frozenset()) + 0.01:
                            hit = True
                            break
                    if hit:
                        break
                if not hit:
                    for x2, y2, d2, h2 in vp2:
                        gv = Point(x2 / 1e6, y2 / 1e6).buffer(d2 / 2e6, 16)
                        if any(g.distance(gv) < mr.need(net, n2, 'via', frozenset()) + 0.01 for ln, g in geos):
                            hit = True
                            break
                if hit:
                    conflicts.append(k)
            if len(conflicts) > 4:
                still.append((net, params, ea, eb, w))
                continue
            victims = [added[k] for k in conflicts]
            for k in sorted(conflicts, reverse=True):
                del added[k]
            unplace([(n2, tp2, vp2) for n2, tp2, vp2, sp in victims])
            add_items(net, params, [])
            added.append((net, params, [], None))
            R.layers = all_layers
            for n2, tp2, vp2, (vn, vparams, vea, veb, vw) in victims:
                r_ = route_between(vn, LAYER, (vea[0] / 1e6, vea[1] / 1e6), LAYER, (veb[0] / 1e6, veb[1] / 1e6), vw / 1e6)
                if r_ is not None:
                    tp3, vp3 = to_params(r_[0], r_[1], vw)
                    if not non_octilinear(tp3):
                        add_items(vn, tp3, vp3)
                        added.append((vn, tp3, vp3, (vn, vparams, vea, veb, vw)))
                        continue
                # fall back to the victim's own old copper if legal now
                okv = True
                for ln, a, c, ww in vparams:
                    g = LineString([(a[0] / 1e6, a[1] / 1e6), (c[0] / 1e6, c[1] / 1e6)]).buffer(ww / 2e6, 8)
                    ex = frozenset(e for e, pg in B.pexempt.items() if pg.intersects(g))
                    for i in B.trees[ln].query(g.buffer(3.1)):
                        geo, n3, kind = B.items[ln][i]
                        if n3 != vn and geo.distance(g) < mr.need(vn, n3, kind, ex) - 1e-4:
                            okv = False
                            break
                    if not okv:
                        break
                if okv:
                    add_items(vn, vparams, [])
                    added.append((vn, vparams, [], None))
                else:
                    still.append((vn, vparams, vea, veb, vw))
        lost = still
    return added, lost, cost


def unplace(added):
    by = collections.defaultdict(lambda: ([], []))
    for item in added:
        net, tp, vp = item[0], item[1], item[2]
        by[net][0].extend(tp)
        by[net][1].extend(vp)
    for net, (tp, vp) in by.items():
        remove_items(net, tp, vp)


all_layers = list(R.layers)
order = sorted(lifted, key=span, reverse=True)
best = None
for it in range(MAXIT):
    added, lost, cost = place_all(order)
    print(f"  iteration {it + 1}: lost {len(lost)}, cost {cost:.0f} ({time.time() - t0:.0f} s)")
    sys.stdout.flush()
    if best is None or (len(lost), cost) < (best[0], best[1]):
        best = (len(lost), cost, it)
    if not lost:
        break
    if it == MAXIT - 1:
        break
    # negotiate: the chains that could not be placed go first next time
    lost_keys = set((n, ea, eb) for n, p, ea, eb, w in lost)
    unplace(added)
    order = [x for x in lost] + [x for x in order if (x[0], x[2], x[3]) not in lost_keys]
placed = [a for a in added]
queue = lost
new_cost = cost
pcbnew.SaveBoard(DST0, b)
for ext in ('.kicad_pro', '.kicad_dru'):
    s_ = os.path.splitext(SRC0)[0] + ext
    if os.path.isfile(s_):
        shutil.copy2(s_, os.path.splitext(DST0)[0] + ext)
rep = {'layer': LAYER, 'lifted': len(lifted), 'placed': len(placed), 'lost': [[n, list(ea), list(eb)] for n, p, ea, eb, w in lost],
       'cost_old': round(old_cost, 1), 'cost_new': round(new_cost, 1)}
if opt('--report'):
    json.dump(rep, open(opt('--report'), 'w'), indent=1)
print(f"slate {LAYER}: placed {len(placed)}, LOST {len(lost)}; cost {old_cost:.0f} -> {new_cost:.0f} -> {DST0}")

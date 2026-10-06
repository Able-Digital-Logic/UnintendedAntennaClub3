"""merge.py BASE.kicad_pcb X.kicad_pcb Y.kicad_pcb OUT.kicad_pcb [--diff-only]
Merge the copper that X added or removed relative to BASE into Y (X and Y are two branches grown in parallel from
BASE, e.g. a routing pass and a rip-up pass). Per net, all-or-nothing:
  * X's removed items (rip-ups) are removed from Y if they are still there,
  * X's new tracks / vias are added to Y only if EVERY one of them clears Y's copper of other nets with mr.py's exact
    pairwise rule model (holes included) - otherwise the whole net change is skipped and reported.
Footprint moves are NOT merged (merge boards whose X branch moved no parts). Runs the BASE/X diff in a child process
(KiCad python loads at most two boards per process safely). KiCad python, scratch copies only."""
import json
import math
import os
import shutil
import subprocess
import sys

argv = sys.argv[1:]
base, xb, yb, dst = argv[:4]
SKIP = set((argv[argv.index('--skip-nets') + 1] if '--skip-nets' in argv else '').split('|')) - {''}
DJ = os.path.splitext(dst)[0] + '_mergediff.json'

if '--diff-only' in argv:
    import pcbnew

    def items(b):
        out = {}
        for t in b.GetTracks():
            if t.GetClass() == 'PCB_VIA':
                k = ('v', t.GetPosition().x, t.GetPosition().y, t.GetNetname(), t.GetWidth(pcbnew.F_Cu), t.GetDrill())
            else:
                k = ('t', t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y, b.GetLayerName(t.GetLayer()),
                     t.GetNetname(), t.GetWidth())
            out[k] = 1
        return out
    a = items(pcbnew.LoadBoard(base))
    x = items(pcbnew.LoadBoard(xb))
    json.dump({'add': [list(k) for k in x if k not in a], 'remove': [list(k) for k in a if k not in x]}, open(DJ, 'w'))
    sys.exit(0)

r = subprocess.run([sys.executable, os.path.abspath(__file__), base, xb, yb, dst, '--diff-only'], capture_output=True, text=True)
if r.returncode != 0:
    print(r.stderr[-2000:])
    sys.exit('diff failed')
diff = json.load(open(DJ))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import mr  # noqa: E402
import pcbnew  # noqa: E402
from shapely.geometry import LineString, Point  # noqa: E402

B = mr.Board(yb, ('*',))
b = B.b
by_net = {}
for k in diff['add']:
    by_net.setdefault(k[3] if k[0] == 'v' else k[6], {'add': [], 'remove': []})['add'].append(k)
for k in diff['remove']:
    by_net.setdefault(k[3] if k[0] == 'v' else k[6], {'add': [], 'remove': []})['remove'].append(k)
ytr = {}
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        k = ('v', t.GetPosition().x, t.GetPosition().y, t.GetNetname(), t.GetWidth(pcbnew.F_Cu), t.GetDrill())
    else:
        k = ('t', t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y, b.GetLayerName(t.GetLayer()), t.GetNetname(), t.GetWidth())
    ytr[k] = t


def geom(k):
    if k[0] == 'v':
        return Point(k[1] / 1e6, k[2] / 1e6).buffer(k[4] / 2e6, 16)
    return LineString([(k[1] / 1e6, k[2] / 1e6), (k[3] / 1e6, k[4] / 1e6)]).buffer(k[7] / 2e6, 8)


import math as _m


def rule_ok(net, k):
    """rules beyond clearance (2026-10-02, after KiCadRoutingTools output broke them): class / net width (neck inside
    the NK exemption areas), via size per class, octilinear angle, rule-area bans (lanes, GND-only cells, AFE partition
    for noisy nets, hole keep-outs)"""
    c = mr.cls(net)
    if k[0] == 'v':
        vd, vh = mr.VIA.get(c, (0.45, 0.2))
        if k[4] / 1e6 < vd - 1e-6 or k[5] / 1e6 < vh - 1e-6:
            return f'via {k[4] / 1e6:.2f}/{k[5] / 1e6:.2f} < {vd}/{vh}'
        g = Point(k[1] / 1e6, k[2] / 1e6).buffer(k[4] / 2e6, 16)
        for item in BANS.setdefault(net, B.bans(net)):
            if item[0] == 'VIAHOLE':
                if item[1].distance(Point(k[1] / 1e6, k[2] / 1e6)) < item[2] + k[4] / 2e6:
                    return 'via in hole keep-out'
            elif item[3] and item[0].intersects(g):
                return 'via in banned area'
        return None
    a_, c_ = (k[1] / 1e6, k[2] / 1e6), (k[3] / 1e6, k[4] / 1e6)
    ang = _m.degrees(_m.atan2(c_[1] - a_[1], c_[0] - a_[0])) % 45.0
    if min(ang, 45.0 - ang) > 0.6 and _m.hypot(c_[0] - a_[0], c_[1] - a_[1]) > 0.02:
        return 'not octilinear'
    g = LineString([a_, c_]).buffer(k[7] / 2e6, 8)
    ex = frozenset(e for e, pg in B.pexempt.items() if pg.intersects(g))
    wmin = mr.neck_of(net) if 'NK' in ex else mr.width_of(net)
    if k[7] / 1e6 < wmin - 1e-6:
        return f'width {k[7] / 1e6:.2f} < {wmin}'
    for item in BANS.setdefault(net, B.bans(net)):
        if item[0] == 'VIAHOLE':
            continue
        geo, lays, tb, vb = item
        if tb and k[5] in lays and geo.intersects(g):
            return 'track in banned area'
    return None


BANS = {}


def try_net(net, ch):
    """check every addition of this net against the current merged model; apply removals + additions if all clear"""
    for k in ch['add']:
        w_ = rule_ok(net, k)
        if w_:
            return False, w_
    rem = [ytr[tuple(k)] for k in ch['remove'] if tuple(k) in ytr and ytr[tuple(k)] is not None]
    rem_bb = set()
    for t in rem:
        k_ = None
    for k in ch['add']:
        g = geom(k)
        lays = mr.SIG if k[0] == 'v' else [k[5]]
        ex = frozenset(e for e, pg in B.pexempt.items() if pg.intersects(g))
        kind = 'via' if k[0] == 'v' else 'track'
        for ln in lays:
            if ln not in B.trees:
                continue
            for i in B.trees[ln].query(g.buffer(3.1)):
                geo, n2, kd = B.items[ln][i]
                if n2 == net:
                    continue
                if geo.distance(g) < mr.need(net, n2, kd, ex) - 1e-4:
                    return False, f'{kind} vs {n2.split("/")[-1]} on {ln}'
        if kind == 'via':
            c = Point(k[1] / 1e6, k[2] / 1e6)
            for i in B.htree.query(c.buffer(1.5)):
                hp, hr, hn = B.holes[i]
                if hn != net and hp.distance(c) < hr + k[5] / 2e6 + 0.25 - 1e-4:
                    return False, f'hole vs {hn.split("/")[-1]}'
    # apply: removals (board + model), then additions
    for kk in ch['remove']:
        t = ytr.get(tuple(kk))
        if t is None:
            continue
        g = geom(tuple(kk))
        bb = tuple(round(v, 5) for v in g.bounds)
        kind = 'via' if kk[0] == 'v' else 'track'
        for ln in (mr.SIG if kind == 'via' else [kk[5]]):
            if ln not in B.items:
                continue
            for i, (geo, n2, k2) in enumerate(B.items[ln]):
                if n2 == net and k2 == kind and tuple(round(v, 5) for v in geo.bounds) == bb:
                    del B.items[ln][i]
                    break
        if kind == 'via':
            for i, (hp, hr, hn) in enumerate(B.holes):
                if hn == net and abs(hp.x - kk[1] / 1e6) < 1e-5 and abs(hp.y - kk[2] / 1e6) < 1e-5:
                    del B.holes[i]
                    break
        b.Remove(t)
        t.thisown = 0
        mr._GRAVE.append(t)
        ytr[tuple(kk)] = None
    nobj = b.FindNet(net)
    for k in ch['add']:
        if k[0] == 'v':
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(pcbnew.VECTOR2I(k[1], k[2]))
            v.SetWidth(k[4])
            v.SetDrill(k[5])
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNet(nobj)
            b.Add(v)
            # model geometry from the known coordinates (getters on fresh SWIG objects can return untyped proxies)
            gv = Point(k[1] / 1e6, k[2] / 1e6).buffer(k[4] / 2e6, 16)
            for ln_ in mr.SIG:
                B.items[ln_].append((gv, net, 'via'))
            B.holes.append((Point(k[1] / 1e6, k[2] / 1e6), k[5] / 2e6, net))
        else:
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(pcbnew.VECTOR2I(k[1], k[2]))
            t.SetEnd(pcbnew.VECTOR2I(k[3], k[4]))
            t.SetLayer(b.GetLayerID(k[5]))
            t.SetWidth(k[7])
            t.SetNet(nobj)
            b.Add(t)
            if k[5] in B.items:
                B.items[k[5]].append((LineString([(k[1] / 1e6, k[2] / 1e6), (k[3] / 1e6, k[4] / 1e6)]).buffer(k[7] / 2e6, 8),
                                      net, 'track'))
    B.rebuild()
    return True, ''


# fixed point: a net whose additions collide with copper another X-net removes is retried after that net merged
pending = {n: c for n, c in by_net.items() if n not in SKIP and n.split('/')[-1] not in SKIP}
if SKIP:
    print(f'merge: skipping {len(by_net) - len(pending)} net(s) by request')
ok_n = 0
last_why = {}
while True:
    progress = False
    for net in sorted(list(pending)):
        ok, why = try_net(net, pending[net])
        if ok:
            ok_n += 1
            del pending[net]
            progress = True
        else:
            last_why[net] = why
    if not progress:
        break
skip_n = len(pending)
skipped = [(n, last_why.get(n, '')) for n in sorted(pending)]
pcbnew.SaveBoard(dst, b)
for ext in ('.kicad_pro', '.kicad_dru'):
    s_ = os.path.splitext(yb)[0] + ext
    if os.path.isfile(s_):
        shutil.copy2(s_, os.path.splitext(dst)[0] + ext)
print(f"merge: {ok_n} net changes merged, {skip_n} skipped -> {dst}")
for n, w in skipped:
    print(f"   skipped {n.split('/')[-1]}: {w}")

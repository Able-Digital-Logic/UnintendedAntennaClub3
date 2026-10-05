"""netclean.py IN.kicad_pcb OUT.kicad_pcb NET[,NET...] [--dry]
Removes SURPLUS copper of the given nets - no routing, nothing new is drawn (2026-10-03 hand-layout pass):
  * dead ends: tracks / vias that lead to no pad (debris left by earlier passes),
  * duplicate paths: of two or more copper paths between the same pads only the shortest is kept.
Method: the net's copper is a graph (tracks incl. arcs, vias, pads; items touch when their copper overlaps on a common
layer). A Steiner tree is grown from one pad, adding each time the shortest copper path to the nearest pad not yet
joined (lengths = track length, 0.5 mm per via). Everything off the tree is surplus. Zone fills of the net count as
copper the tree may use (items touching a fill are kept). --dry lists only. Verify with place/metrics.py (no net may
lose a pad). KiCad python, scratch copies only."""
import heapq
import math
import os
import shutil
import sys

import pcbnew
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import mr  # noqa: E402

argv = sys.argv[1:]
src, dst = argv[0], argv[1]
want = argv[2].split(',')
DRY = '--dry' in argv
if os.path.normcase(os.path.realpath(dst)).startswith(mr.PROTECTED):
    sys.exit('refusing to write into the project folder')
b = pcbnew.LoadBoard(src)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
CU = list(b.GetEnabledLayers().CuStack())
GRAVE = []
total_removed = 0
total_len = 0.0


def arcpts(t):
    s, m, e = t.GetStart(), t.GetMid(), t.GetEnd()
    return [(s.x / 1e6, s.y / 1e6), (m.x / 1e6, m.y / 1e6), (e.x / 1e6, e.y / 1e6)]


for want_net in want:
    full = next((str(n) for n in b.GetNetsByName().keys() if str(n) == want_net or str(n).split('/')[-1] == want_net), None)
    if full is None:
        print(f'{want_net}: no such net')
        continue
    items = []          # (kind, obj, {layer: geom}, length)
    for t in b.GetTracks():
        if t.GetNetname() != full:
            continue
        if t.GetClass() == 'PCB_VIA':
            c = t.GetPosition()
            g = Point(c.x / 1e6, c.y / 1e6).buffer(t.GetWidth(pcbnew.F_Cu) / 2e6, 16)
            items.append(('via', t, {l_: g for l_ in CU if CU.index(t.TopLayer()) <= CU.index(l_) <= CU.index(t.BottomLayer())}, 0.5))
        else:
            pts = arcpts(t) if t.GetClass() == 'PCB_ARC' else [(t.GetStart().x / 1e6, t.GetStart().y / 1e6), (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)]
            ls = LineString(pts)
            items.append(('trk', t, {t.GetLayer(): ls.buffer(t.GetWidth() / 2e6, 8)}, ls.length))
    pads = []
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() == full:
                pads.append(('pad', p, {l_: mr.poly_of(p.GetEffectivePolygon(l_, pcbnew.ERROR_OUTSIDE)) for l_ in CU if p.IsOnLayer(l_)}, 0.0))
    zones = []
    for z in b.Zones():
        if not z.GetIsRuleArea() and z.GetNetname() == full:
            zones.append(('zone', z, {l_: mr.poly_of(z.GetFilledPolysList(l_)) for l_ in CU if z.IsOnLayer(l_)}, 0.0))
    nodes = items + pads + zones
    n = len(nodes)
    adj = [[] for _ in range(n)]
    for la in CU:
        idx = [i for i, nd in enumerate(nodes) if la in nd[2] and not nd[2][la].is_empty]
        if not idx:
            continue
        tree = STRtree([nodes[i][2][la] for i in idx])
        for k, i in enumerate(idx):
            for j_ in tree.query(nodes[i][2][la]):
                j = idx[j_]
                if j > i and nodes[i][2][la].intersects(nodes[j][2][la]):
                    adj[i].append(j)
                    adj[j].append(i)
    pad_ids = [i for i, nd in enumerate(nodes) if nd[0] == 'pad']
    if len(pad_ids) < 2:
        print(f'{want_net}: fewer than 2 pads, skipped')
        continue
    # one Steiner tree per copper island (a split net keeps every island; only copper that joins no pad, or a
    # longer duplicate path inside an island, is surplus)
    in_tree, joined = set(), set()
    for start in pad_ids:
        if start in joined:
            continue
        comp_tree = {start}
        joined.add(start)
        while True:
            dist = {i: 0.0 for i in comp_tree}
            prev = {}
            pq = [(0.0, i) for i in comp_tree]
            heapq.heapify(pq)
            target = None
            while pq:
                d, u = heapq.heappop(pq)
                if d > dist.get(u, math.inf):
                    continue
                if nodes[u][0] == 'pad' and u not in joined:
                    target = u
                    break
                for v in adj[u]:
                    nd = d + nodes[v][3]
                    if nd < dist.get(v, math.inf) - 1e-9:
                        dist[v] = nd
                        prev[v] = u
                        heapq.heappush(pq, (nd, v))
            if target is None:
                break
            joined.add(target)
            u = target
            while u not in comp_tree:
                comp_tree.add(u)
                u = prev[u]
        in_tree |= comp_tree
    # islands: pads that share a tree
    unreached = []
    keep = set(in_tree)
    # copper touching a zone fill stays (pours re-fill around it; it may be the zone's own feed)
    for i, nd in enumerate(nodes):
        if nd[0] in ('trk', 'via') and any(nodes[j][0] == 'zone' for j in adj[i]):
            keep.add(i)
    surplus = [i for i, nd in enumerate(nodes) if nd[0] in ('trk', 'via') and i not in keep]
    slen = sum(nodes[i][3] for i in surplus if nodes[i][0] == 'trk')
    print(f"{want_net}: {len(pad_ids)} pads, {len(items)} copper items, "
          f"surplus {len(surplus)} items ({slen:.1f} mm of track)")
    for i in surplus:
        kd, o = nodes[i][0], nodes[i][1]
        if kd == 'via':
            print(f"   - via ({o.GetPosition().x / 1e6:.2f},{o.GetPosition().y / 1e6:.2f})")
        else:
            print(f"   - {b.GetLayerName(o.GetLayer())} ({o.GetStart().x / 1e6:.2f},{o.GetStart().y / 1e6:.2f})->({o.GetEnd().x / 1e6:.2f},{o.GetEnd().y / 1e6:.2f})")
    if not DRY:
        for i in surplus:
            o = nodes[i][1]
            b.Remove(o)
            o.thisown = 0
            GRAVE.append(o)
    total_removed += len(surplus)
    total_len += slen
if not DRY:
    pcbnew.SaveBoard(dst, b)
    for ext in ('.kicad_pro', '.kicad_dru'):
        a = os.path.splitext(src)[0] + ext
        if os.path.isfile(a):
            shutil.copy2(a, os.path.splitext(dst)[0] + ext)
print(f"netclean: {total_removed} surplus items ({total_len:.1f} mm) {'listed' if DRY else 'removed -> ' + dst}")

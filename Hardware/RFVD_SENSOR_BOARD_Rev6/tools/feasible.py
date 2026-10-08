"""feasible.py BOARD UNROUTED.csv OUT.json [--only NET,...] [--win x0,y0,x1,y1] [--margin 4] [--band]   (2026-10-03)
--band: full board width, from 3 mm above the upper gap end to the bottom edge (no detours through the analog half).
UNROUTED.csv = outputs/RFVD_unrouted.csv (tools/unrouted_map.py); regenerate it after routing.
Geometric feasibility of each missing connection on the CURRENT board (no routing, nothing written).
  free(L)  = centre-line space for this net's W track on layer L: board (edge 0.5; 1.0 for HS/analog/RF/SW) minus
             every other-net item buffered by W/2 + mr.need() (pairwise DRU clearance), minus drilled holes (+0.2),
             minus rule areas that ban this net's tracks on L.
  (the pairwise clearance uses the mr.py courtyard exemptions of the existing item's location, e.g. no HS 0.2 or
   analog 1.0 inside U* / U8 courtyards, as the DRU conditions do)
  V        = legal via-centre space (0.45/0.20; 0.6/0.3 for Power_Battery): every other-net item on F/In3/B buffered
             by vd/2 + need + 0.012, holes by hr + vh/2 + 0.25, via-ban areas, mounting holes 1.9 mm (mr via rules,
             without the courtyard exemptions, so conservative).
  Graph    : nodes = connected components of free(L); two components on different layers are joined where
             c1 & c2 & V is non-empty (a via fits there). Island copper joins the components it touches.
  Result   : 'direct L' (one component touches both islands), else the layer sequence with the fewest vias
             (e.g. F > In3 > B) with a representative via spot per layer change, else 'blocked'.
             reach A / B = size of the free space each island can reach (small = boxed in at that end).
Each connection is checked alone (routes drawn earlier use up space). Read only. KiCad python."""
import collections
import csv
import json
import math
import os
import sys
import time
os.environ['MR_AFE_IN3'] = '1'          # project decision 1: digital nets may run on In3 under the AFE partition
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mr  # noqa: E402
from shapely.geometry import Point, Polygon, box  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

a = sys.argv[1:]


def opt(k, d=None):
    return a[a.index(k) + 1] if k in a else d


only = set(opt('--only').split(',')) if opt('--only') else None
WIN = tuple(float(v) for v in opt('--win').split(',')) if opt('--win') else None
MARG = float(opt('--margin', 4))
BAND = '--band' in a      # full board width, from 3 mm above the upper gap end down to the bottom edge
B = mr.Board(a[0], ('*',))
R = mr.Router(B)
rows = list(csv.DictReader(open(a[1], encoding='utf-8')))
EDGE1 = ('HighSpeed_Digital', 'HighSpeed_Clock', 'Analog_Precision', 'Ref_Kelvin', 'RF_Input', 'RF_50R', 'Power_Buck_SW')


def comps(g):
    return [q for q in (g.geoms if hasattr(g, 'geoms') else [g]) if q.geom_type == 'Polygon' and not q.is_empty and q.area > 1e-6]


out, isl_cache = [], {}
for r in rows:
    N = r['net']
    if only and N.split('/')[-1] not in only:
        continue
    t0 = time.time()
    W = mr.width_of(N)
    c = mr.cls(N)
    A = (float(r['ax']), float(r['ay']))
    Z = (float(r['bx']), float(r['by']))
    if N not in isl_cache:
        isl_cache[N] = R.islands(N)
    isl = isl_cache[N]

    def find(pt):
        P = Point(pt)
        return min(isl, key=lambda d: min((d[ln].distance(P) for ln in mr.SIG if not d[ln].is_empty), default=9e9))
    IA, IZ = find(A), find(Z)
    if BAND:
        win = box(115.0, min(A[1], Z[1]) - 3.0, 168.0, 143.2)
    else:
        win = box(*WIN) if WIN else box(min(A[0], Z[0]) - MARG, min(A[1], Z[1]) - MARG, max(A[0], Z[0]) + MARG,
                                        max(A[1], Z[1]) + MARG)
    bans = B.bans(N)
    edge = 1.0 if c in EDGE1 else 0.5
    vd, vh = mr.VIA.get(c, (0.45, 0.2))
    free, vobs = {}, []
    for L in mr.SIG:
        groups = collections.defaultdict(list)
        for i in B.trees[L].query(win):
            geo, n2, kind = B.items[L][i]
            if n2 == N:
                continue
            # courtyard exemptions (mr.EXEMPT: U*, U8 analog, CLK, ...) where the existing item lies, as mr does per cell
            ex = frozenset(k for k, e in B.pexempt.items() if e.intersects(geo))
            groups[round(mr.need(N, n2, kind, ex), 3)].append(geo)
        obs = []
        for cc, gs in groups.items():
            u = unary_union(gs)
            obs.append(u.buffer(W / 2 + cc, 6))
            vobs.append(u.buffer(vd / 2 + cc + 0.012, 6))
        oh = [pt.buffer(hr + 0.2 + W / 2, 12) for pt, hr, hn in (B.holes[i] for i in B.htree.query(win)) if hn != N]
        if oh:
            obs.append(unary_union(oh))
        for it in bans:
            if it[0] == 'VIAHOLE':
                continue
            g, lays, tb, vb = it
            if tb and L in lays and g.intersects(win):
                obs.append(g.buffer(W / 2, 4))
        free[L] = comps(B.outline.buffer(-(edge + W / 2)).intersection(win).difference(unary_union(obs)))
    vh_obs = [pt.buffer(hr + vh / 2 + 0.25, 12) for pt, hr, hn in (B.holes[i] for i in B.htree.query(win))]
    if vh_obs:
        vobs.append(unary_union(vh_obs))
    for it in bans:
        if it[0] == 'VIAHOLE':
            vobs.append(it[1].buffer(it[2] + vd / 2, 24))
        elif it[3] and it[0].intersects(win):
            vobs.append(it[0].buffer(vd / 2, 6))
    V = B.outline.buffer(-(0.5 + vd / 2)).intersection(win).difference(unary_union(vobs))
    adj = collections.defaultdict(list)
    Ls = list(mr.SIG)
    for i1, L1 in enumerate(Ls):
        for L2 in Ls[i1 + 1:]:
            for k1, q1 in enumerate(free[L1]):
                vq = q1.intersection(V)
                if vq.is_empty:
                    continue
                for k2, q2 in enumerate(free[L2]):
                    if not vq.intersects(q2):
                        continue
                    x = vq.intersection(q2)
                    if x.is_empty or x.area < 1e-5:
                        continue
                    rp = x.representative_point()
                    adj[(L1, k1)].append(((L2, k2), (round(rp.x, 2), round(rp.y, 2))))
                    adj[(L2, k2)].append(((L1, k1), (round(rp.x, 2), round(rp.y, 2))))
    srcA = [(L, k) for L in mr.SIG if not IA[L].is_empty for k, q in enumerate(free[L]) if q.intersects(IA[L])]
    srcZ = set((L, k) for L in mr.SIG if not IZ[L].is_empty for k, q in enumerate(free[L]) if q.intersects(IZ[L]))
    direct = sorted(set(L for (L, k) in srcA if (L, k) in srcZ))
    prev = {n: None for n in srcA}
    dq = collections.deque(srcA)
    hit = None
    while dq:
        n = dq.popleft()
        if n in srcZ:
            hit = n
            break
        for m, vp in adj[n]:
            if m not in prev:
                prev[m] = (n, vp)
                dq.append(m)
    path = []
    if hit:
        n = hit
        while prev[n] is not None:
            p, vp = prev[n]
            path.append((p[0], vp, n[0]))
            n = p
        path.reverse()
    if path:
        seq = path[0][0].replace('.Cu', '') + ''.join(f" >via {s[1]}> {s[2].replace('.Cu', '')}" for s in path)
    else:
        seq = hit[0].replace('.Cu', '') if hit else None

    def reach(src):
        ext = 0.0
        for (L, k) in src:
            x0, y0, x1, y1 = free[L][k].bounds
            ext = max(ext, math.hypot(x1 - x0, y1 - y0))
        return round(ext, 2)
    rec = {'net': N, 'class': c, 'w': W, 'gap': float(r['gap_mm']), 'A': r['island_A'], 'B': r['island_B'], 'a': A, 'b': Z,
           'direct': direct, 'route': seq, 'vias': len(path), 'reach_a': reach(srcA), 'reach_b': reach(list(srcZ)),
           'win': [round(v, 1) for v in win.bounds], 'sec': round(time.time() - t0, 1)}
    out.append(rec)
    res = ('DIRECT ' + ','.join(d.replace('.Cu', '') for d in direct)) if direct else (('route ' + seq) if seq else 'BLOCKED')
    print(f"{N.split('/')[-1]:17s} gap {rec['gap']:5.1f}  {res}  [reach A {rec['reach_a']} B {rec['reach_b']} mm] ({rec['sec']} s)", flush=True)
json.dump(out, open(a[2], 'w'), indent=1)

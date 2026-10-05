"""reroute.py IN.kicad_pcb OUT.kicad_pcb TRACKQ_REPORT.json [--min-len 2.0] [--max 25] [--region x0,y0,x1,y1]
                [--t45 0.6]

Least-track rip-up and re-route (user rule 2026-10-02 18:05: least track, simple straight / 45-degree paths).
Takes the WASTEFUL chains of a trackq.py report that its dogleg pass could not fix (long runs with many bends or a large
detour), and for each one: removes the chain, re-routes the gap between its two ends with mr.py (exact rule model,
octilinear, bend penalty MR_T45, via-in-pad first) and KEEPS the new copper only if it is not longer than the old run
and has fewer bends; otherwise the old copper is restored unchanged. One chain at a time, board reloaded in between so
the obstacle model always matches the copper. KiCad python, scratch copies only."""
import json
import math
import os
import shutil
import sys

import pcbnew
from shapely.geometry import LineString, Point, box

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
argv = sys.argv[1:]


def opt(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


src, dst, repp = argv[0], argv[1], argv[2]
os.environ['MR_T45'] = opt('--t45', '0.6')
import mr  # noqa: E402

MINL = float(opt('--min-len', '2.0'))
MAXN = int(opt('--max', '25'))
region = box(*[float(v) for v in opt('--region').split(',')]) if opt('--region') else None
rows = json.load(open(repp))
cands = [r for r in rows if r['wasteful'] and 'fixed' not in r and r['len'] >= MINL]
if region is not None:
    cands = [r for r in cands if region.contains(Point(*r['from'])) or region.contains(Point(*r['to']))]
cands.sort(key=lambda r: -(r['len'] - r['octile'] + 0.3 * (r['bends'] - r['least_bends'])))
cands = cands[:MAXN]
print(f"reroute: {len(cands)} chains to try")
work = dst + '.work.kicad_pcb'
shutil.copy2(src, work)
for ext in ('.kicad_pro', '.kicad_dru'):
    s = os.path.splitext(src)[0] + ext
    if os.path.isfile(s):
        shutil.copy2(s, os.path.splitext(work)[0] + ext)
        shutil.copy2(s, os.path.splitext(dst)[0] + ext)
kept = 0
if '--worker' in argv:
    wi = int(opt('--worker'))
    cands = [cands[wi]]
    work = src
    for ci, r in enumerate(cands):
        net, ln = r['net'], r['layer']
        a, c = tuple(r['from']), tuple(r['to'])
        b = pcbnew.LoadBoard(work)
        if not hasattr(b, 'GetLayerID'):
            print(f"  skip {net.split('/')[-1]}: could not load {work}")
            continue
        lid = b.GetLayerID(ln)
        # collect the chain's tracks: walk from a to c over same-net tracks on the layer
        tr = [t for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK' and t.GetNetname() == net and t.GetLayer() == lid]
        key = lambda q: (round(q[0], 3), round(q[1], 3))
        adj = {}
        for t in tr:
            s_ = key((t.GetStart().x / 1e6, t.GetStart().y / 1e6))
            e_ = key((t.GetEnd().x / 1e6, t.GetEnd().y / 1e6))
            adj.setdefault(s_, []).append((e_, t))
            adj.setdefault(e_, []).append((s_, t))
        start, goal = key(a), key(c)
        if start not in adj or goal not in adj:
            print(f"  skip {net.split('/')[-1]}: chain ends not found")
            continue
        # BFS over degree-2 path
        prev = {start: None}
        q = [start]
        while q:
            u = q.pop(0)
            if u == goal:
                break
            for v, t in adj.get(u, []):
                if v not in prev:
                    prev[v] = (u, t)
                    q.append(v)
        if goal not in prev:
            print(f"  skip {net.split('/')[-1]}: no path between chain ends")
            continue
        chain = []
        u = goal
        while prev[u] is not None:
            u0, t = prev[u]
            chain.append(t)
            u = u0
        old = [(t.GetStart(), t.GetEnd(), t.GetWidth(), t.GetLayer()) for t in chain]
        old_len = sum(t.GetLength() / 1e6 for t in chain)
        old_bends = r['bends']
        for t in chain:
            b.Remove(t)
        tmp = dst + f'.tmp{ci}.kicad_pcb'
        pcbnew.SaveBoard(tmp, b)
        for ext in ('.kicad_pro', '.kicad_dru'):
            s = os.path.splitext(src)[0] + ext
            if os.path.isfile(s):
                shutil.copy2(s, os.path.splitext(tmp)[0] + ext)
        try:
            B = mr.Board(tmp, ('*',))
        except Exception as e:
            print(f"  skip {net.split('/')[-1]}: board reload failed ({e})")
            continue
        R = mr.Router(B)
        # long spans: weighted A* keeps the search bounded (path within MR_EPS of optimal)
        span = math.hypot(c[0] - a[0], c[1] - a[1])
        R.eps = 1.3 if span > 8 else 1.0
        R.max_pops = 3000000 if span > 8 else 1200000
        isl = R.islands(net)

        def which(pt):
            best = None
            for i, I in enumerate(isl):
                g = [v for k_, v in I.items() if not k_.startswith('__') and not v.is_empty]
                d = min((x.distance(Point(pt)) for x in g), default=9e9)
                if best is None or d < best[0]:
                    best = (d, i)
            return best[1] if best and best[0] < 0.3 else None
        ia, ic = which(a), which(c)
        if ia is None or ic is None or ia == ic:
            print(f"  skip {net.split('/')[-1]}: ends {ia}/{ic} not separate islands after removal")
            os.remove(tmp)
            continue
        res, why = R.route_pair(net, isl[ia], isl[ic])
        ok = False
        if res is not None:
            segs, vias, w = res
            new_len = sum(math.hypot(cc[0] - aa[0], cc[1] - aa[1]) for _, aa, cc, _ in segs)
            new_bends = max(0, len(segs) - 1 - len(vias))
            if new_len <= old_len + 0.05 and new_bends < old_bends and len(vias) <= 2:
                R.commit(net, segs, vias)
                nw = dst + f'.w{ci}.kicad_pcb'
                pcbnew.SaveBoard(nw, B.b)
                for ext in ('.kicad_pro', '.kicad_dru'):
                    s_ = os.path.splitext(src)[0] + ext
                    if os.path.isfile(s_):
                        shutil.copy2(s_, os.path.splitext(nw)[0] + ext)
                work = nw
                ok = True
                kept += 1
                print(f"  KEEP {net.split('/')[-1][:20]:20s} {ln} len {old_len:.2f}->{new_len:.2f} bends {old_bends}->{new_bends} vias {len(vias)}")
        if not ok:
            print(f"  keep old {net.split('/')[-1][:20]:20s} {ln} ({why if res is None else 'new route not better'})")
        os.remove(tmp)

    if kept:
        shutil.copy2(work, dst)
        print('WORKER_KEPT')
    sys.exit(0)
import subprocess
cur = src
for ci in range(len(cands)):
    out = dst + f'.s{ci}.kicad_pcb'
    r = subprocess.run([sys.executable, os.path.abspath(__file__), cur, out, repp, '--worker', str(ci)] +
                       [a for a in argv[3:] if a != '--worker'], capture_output=True, text=True)
    lines = [l for l in r.stdout.splitlines() if 'memory leak' not in l and 'image handler' not in l and l.strip()]
    for l in lines:
        if l != 'WORKER_KEPT' and not l.startswith('reroute:'):
            print(l)
    if 'WORKER_KEPT' in r.stdout and os.path.isfile(out):
        for ext in ('.kicad_pro', '.kicad_dru'):
            s_ = os.path.splitext(src)[0] + ext
            if os.path.isfile(s_):
                shutil.copy2(s_, os.path.splitext(out)[0] + ext)
        cur = out
        kept += 1
    elif r.returncode:
        print('  worker error:', (r.stderr or '')[-400:])
    sys.stdout.flush()
shutil.copy2(cur, dst)
print(f"reroute: {kept} of {len(cands)} chains replaced")

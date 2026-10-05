"""diagpairs.py BOARD OUT.json [--grid 0.1] [--pops 400000] [--nets N1,N2]
For every incomplete non-GND net, its closest island pair is routed A->B and B->A with no module (foreign) rules and a
pop budget. A search that EXHAUSTS early (pops << budget) proves its start side sits in a pocket (boxed escape); both
sides large and still no path = a barrier between them (congestion: rip-up needed); 'ok' = routable as is.
Each island is described by its parts. KiCad python, read only."""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
argv = sys.argv[1:]


def opt(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


os.environ['MR_MAX_POPS'] = opt('--pops', '400000')
os.environ.setdefault('MR_EPS', '1.6')
import mr  # noqa: E402
import pcbnew  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

src, outp = argv[0], argv[1]
B = mr.Board(src, ('*',))
R = mr.Router(B, grid=float(opt('--grid', '0.1')))
ref_at = {}
for f in B.b.GetFootprints():
    for p in f.Pads():
        ref_at[(round(p.GetPosition().x / 1e6, 4), round(p.GetPosition().y / 1e6, 4))] = f.GetReference()
want = set((opt('--nets') or '').split(',')) - {''}
nets = sorted(n for n in B.pads_by_net if n and n != 'GND' and not n.startswith('unconnected'))
out = []
for net in nets:
    if want and net not in want and net.split('/')[-1] not in want:
        continue
    isl = R.islands(net)
    if len(isl) < 2:
        continue
    gs = [unary_union([v for k, v in I.items() if not k.startswith('__') and not v.is_empty]) for I in isl]
    d, i, j = min((gs[a].distance(gs[b]), a, b) for a in range(len(isl)) for b in range(a + 1, len(isl)))
    parts = lambda I: sorted(set(ref_at.get((round(x, 4), round(y, 4)), '?') for x, y in I.get('__pads__', [])))
    ts = time.time()
    r1, w1 = R.route_pair(net, isl[i], isl[j])
    if r1 is not None:
        verdict = 'ok'
        w2 = ''
    else:
        r2, w2 = R.route_pair(net, isl[j], isl[i])
        p1 = int(w1.split('(')[1].split()[0]) if '(' in w1 else -1
        p2 = int(w2.split('(')[1].split()[0]) if '(' in w2 else -1
        lim = int(os.environ['MR_MAX_POPS'])
        small = 30000
        if 0 <= p1 < small and 0 <= p2 < small:
            verdict = 'both-boxed'
        elif 0 <= p1 < small:
            verdict = 'A-boxed'
        elif 0 <= p2 < small:
            verdict = 'B-boxed'
        elif p1 >= lim or p2 >= lim:
            verdict = 'budget'
        else:
            verdict = 'barrier'
    row = {'net': net, 'gap': round(d, 2), 'verdict': verdict, 'A': parts(isl[i]), 'B': parts(isl[j]), 'why': [w1, w2],
           's': round(time.time() - ts, 1)}
    out.append(row)
    print(f"{net.split('/')[-1]:20s} gap {d:6.2f}  {verdict:10s} A={','.join(row['A'])[:30]:30s} B={','.join(row['B'])[:30]:30s} {w1} | {w2}")
    sys.stdout.flush()
json.dump(out, open(outp, 'w'), indent=1)

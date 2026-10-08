"""modroute.py IN.kicad_pcb OUT.kicad_pcb AUDIT.json [--clusters U301,...] [--buf 0.8] [--regions R.json]
                [--report REP.json] [--skip-power] [--only-power] [--maxtries 12]

Module-LOCAL routing under the user's rules (2026-10-02):
  * every module routes its own nets INSIDE its own region (no copper outside it, so no foreign tracks under other
    modules); region = union of the module parts' courtyards, buffered by --buf (default 0.8 mm) and closed;
  * via-in-pad first (mr.py MR_VIP_COST), straight / 45-degree paths with a bend penalty (MR_T45);
  * signals before power (QFN fan-in), GND never (pad vias + planes).
Modules = Jev s1_layout_audit anchors (an IC/connector plus every passive Jev says serves one of its pins).
Writes the module regions (WKT) for the inter-module pass (intermod.py) and for renders. KiCad python."""
import collections
import json
import os
import shutil
import sys
import time

import pcbnew
from shapely import wkt
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import mr  # noqa: E402

argv = sys.argv[1:]
src, dst, auditp = argv[0], argv[1], argv[2]


def opt(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


BUF = float(opt('--buf', '0.8'))
audit = json.load(open(auditp))
mods = collections.defaultdict(set)
for it in audit['items']:
    a = (it.get('anchor') or 'none').split('.')[0]
    if a != 'none':
        mods[a].add(it['item'])
        mods[a].add(a)
order = (opt('--clusters') or 'U301,J11,J4,J3,U8,U402,U302,U403,U9,U10,J8,J10,U401,Q201,Q203,U303,U702,U701,J2,D3,'
         'Q301,Q303,SW4,D301,U2,U13,U6,U7,U1,U3,U4,U5,U11,U304,Y1,Y2,J1,J300,J6').split(',')
B = mr.Board(src, ('*',))
R = mr.Router(B, grid=0.05)
b = B.b
ref_of = {}
for f in b.GetFootprints():
    for p in f.Pads():
        ref_of[(round(p.GetPosition().x / 1e6, 4), round(p.GetPosition().y / 1e6, 4))] = f.GetReference()


def isl_refs(I):
    return set(ref_of.get((round(x, 4), round(y, 4)), '?') for x, y in I.get('__pads__', []))


regions = {}
for m, refs in mods.items():
    gs = [B.court[r] for r in refs if r in B.court]
    if gs:
        regions[m] = unary_union(gs).buffer(BUF).buffer(0.5).buffer(-0.5).intersection(B.outline)
if opt('--regions'):
    json.dump({m: g.wkt for m, g in regions.items()}, open(opt('--regions'), 'w'))
report = []
maxtries = int(opt('--maxtries', '12'))
for m in order:
    refs = mods.get(m)
    if not refs or m not in regions:
        continue
    reg = regions[m]
    nets = collections.Counter()
    for r in refs:
        f = b.FindFootprintByReference(r)
        if f is None:
            continue
        for p in f.Pads():
            n = p.GetNetname()
            if n and n != 'GND' and not n.startswith('unconnected'):
                nets[n] += 1
    is_pwr = lambda n: mr.cls(n).startswith('Power') or mr.cls(n) == 'Ground'
    todo = sorted((n for n, c in nets.items() if c >= 2), key=lambda n: (is_pwr(n), n))
    # --first N1,N2: these nets go first, in this order (bootstrap / supply pins that only fit one way)
    if opt('--first'):
        first = [f_ for f_ in opt('--first').split(',')]
        key_ = lambda n: next((i for i, f_ in enumerate(first) if n == f_ or n.split('/')[-1] == f_), len(first))
        todo = sorted(todo, key=lambda n: (key_(n), is_pwr(n), n))
    if '--skip-power' in argv:
        todo = [n for n in todo if not is_pwr(n)]
    if '--only-power' in argv:
        todo = [n for n in todo if is_pwr(n)]
    ok = fail = 0
    t0 = time.time()
    for net in todo:
        skip = set()
        tries = 0
        while tries < maxtries:
            isl = [I for I in R.islands(net)]
            # an island takes part when it holds a pad of this module that lies inside the module region
            cand = [I for I in isl if isl_refs(I) & refs]
            if len(cand) < 2:
                break
            best = None
            for a in range(len(cand)):
                for c in range(a + 1, len(cand)):
                    Ia, Ic = cand[a], cand[c]
                    key = (frozenset(Ia['__pads__']), frozenset(Ic['__pads__']))
                    if key in skip:
                        continue
                    ga = unary_union([v for k_, v in Ia.items() if not k_.startswith('__') and not v.is_empty])
                    gc = unary_union([v for k_, v in Ic.items() if not k_.startswith('__') and not v.is_empty])
                    d = ga.distance(gc)
                    if best is None or d < best[0]:
                        best = (d, Ia, Ic, key)
            if best is None:
                break
            d, Ia, Ic, key = best
            tries += 1
            ts = time.time()
            res, why = R.route_pair(net, Ia, Ic, region=reg)
            dt = time.time() - ts
            if res is None:
                skip.add(key)
                fail += 1
                report.append({'module': m, 'net': net, 'ok': False, 'why': why, 'gap': round(d, 2), 's': round(dt, 1)})
                print(f"  {m:5s} FAIL {net.split('/')[-1]:22s} {why} ({d:.2f} mm, {dt:.1f} s)")
                continue
            segs, vias, w = res
            R.commit(net, segs, vias)
            ok += 1
            report.append({'module': m, 'net': net, 'ok': True, 'segs': len(segs), 'vias': len(vias),
                           'gap': round(d, 2), 's': round(dt, 1)})
    print(f"module {m}: {len(refs)} parts, {len(todo)} nets, {ok} routed, {fail} failed, {time.time() - t0:.0f} s")
    sys.stdout.flush()
pcbnew.SaveBoard(dst, b)
for ext in ('.kicad_pro', '.kicad_dru'):
    s = os.path.splitext(src)[0] + ext
    if os.path.isfile(s):
        shutil.copy2(s, os.path.splitext(dst)[0] + ext)
if opt('--report'):
    json.dump(report, open(opt('--report'), 'w'), indent=1)
print(f"modroute: {sum(1 for r in report if r['ok'])} routed, {sum(1 for r in report if not r['ok'])} failed")

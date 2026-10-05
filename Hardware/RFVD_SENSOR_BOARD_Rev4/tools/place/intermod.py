"""intermod.py IN.kicad_pcb OUT.kicad_pcb AUDIT.json [--buf 0.8] [--pen 0.6] [--nets-file F.json] [--report R.json]
                [--ymin 92] [--order short|long]

Inter-module routing (user rules 2026-10-02): after every module routed its own nets locally, only the signals that
LEAVE a module remain. They are joined island pair by island pair with mr.py (exact DRU rule model, octilinear,
via-in-pad first, bend penalty), with every OTHER module's region declared foreign:
  * no tracks on F.Cu / B.Cu and no vias inside a foreign module (its surface belongs to its own local copper),
  * In3.Cu (buried between the In2 and In4 GND planes) may pass under a foreign module at --pen mm extra cost per mm.
Module regions = union of the module parts' courtyards (Jev s1_layout_audit anchors) buffered by --buf.
GND is skipped (pad vias + planes). Nets are taken shortest-gap first. KiCad python, scratch copies only."""
import collections
import json
import math
import os
import shutil
import sys
import time

import pcbnew
from shapely.geometry import Point
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import mr  # noqa: E402

argv = sys.argv[1:]
src, dst, auditp = argv[0], argv[1], argv[2]


def opt(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


BUF = float(opt('--buf', '0.8'))
BAN = set((opt('--ban') or 'F.Cu,B.Cu').split(',')) - {''}
SOFT = float(opt('--soft', '0'))
PEN = float(opt('--pen', '0.6'))
YMIN = float(opt('--ymin', '-1e9'))
audit = json.load(open(auditp))
mods = collections.defaultdict(set)
for it in audit['items']:
    a = (it.get('anchor') or 'none').split('.')[0]
    if a != 'none':
        mods[a].add(it['item'])
        mods[a].add(a)
B = mr.Board(src, ('*',))
R = mr.Router(B, grid=float(opt('--grid', '0.05')))
# long connections: a second, coarse router (grid --grid-long, default 0.1 mm) - the obstacles are inflated by the full
# pairwise clearance + half width, so a coarse grid only removes some legal paths, never adds illegal ones
RL = mr.Router(B, grid=float(opt('--grid-long', '0.1')))
LONG = float(opt('--long', '12'))
b = B.b
regions = {}
for m, refs in mods.items():
    gs = [B.court[r] for r in refs if r in B.court]
    if gs:
        regions[m] = unary_union(gs).buffer(BUF).buffer(0.5).buffer(-0.5).intersection(B.outline)
mod_of = {}
for m, refs in mods.items():
    for r in refs:
        mod_of.setdefault(r, set()).add(m)
ref_at = {}
for f in b.GetFootprints():
    for p in f.Pads():
        ref_at[(round(p.GetPosition().x / 1e6, 4), round(p.GetPosition().y / 1e6, 4))] = f.GetReference()


def isl_mods(I):
    out = set()
    for x, y in I.get('__pads__', []):
        r = ref_at.get((round(x, 4), round(y, 4)))
        if r:
            out |= mod_of.get(r, set())
    return out


if opt('--nets-file'):
    nets = json.load(open(opt('--nets-file')))
else:
    nets = sorted(n for n in B.pads_by_net if n and n != 'GND' and not n.startswith('unconnected'))
report = []
work = []
for net in nets:
    isl = R.islands(net)
    if len(isl) < 2:
        continue
    pads_y = [y for I in isl for _, y in I.get('__pads__', [])]
    if pads_y and max(pads_y) < YMIN:
        continue
    geos = [unary_union([v for k_, v in I.items() if not k_.startswith('__') and not v.is_empty]) for I in isl]
    gap = min(geos[i].distance(geos[j]) for i in range(len(isl)) for j in range(i + 1, len(isl)))
    work.append((gap, net))
work.sort(reverse=(opt('--order') == 'long'))
print(f"intermod: {len(work)} nets with open connections")
for gap0, net in work:
    tries = 0
    skip = set()
    while tries < 14:
        isl = R.islands(net)
        if len(isl) < 2:
            break
        geos = [unary_union([v for k_, v in I.items() if not k_.startswith('__') and not v.is_empty]) for I in isl]
        sigs = [frozenset(I.get('__pads__', [])) for I in isl]
        best = None
        for i in range(len(isl)):
            for j in range(i + 1, len(isl)):
                if (sigs[i], sigs[j]) in skip:
                    continue
                d = geos[i].distance(geos[j])
                if best is None or d < best[0]:
                    best = (d, i, j)
        if best is None:
            break
        d, i, j = best
        own = isl_mods(isl[i]) | isl_mods(isl[j])
        # regions overlap: a pin of its own module may also lie in a neighbour's region - the own modules' regions
        # are never foreign
        foreign_g = unary_union([g for m, g in regions.items() if m not in own]).difference(
            unary_union([regions[m] for m in own if m in regions]))
        tries += 1
        ts = time.time()
        rr = RL if d > LONG else R
        if '--soft-only' in argv and SOFT:
            res, why = None, 'skipped hard'
        else:
            res, why = rr.route_pair(net, isl[i], isl[j], foreign=(foreign_g, BAN, PEN))
        if res is None and SOFT and d <= 60:
            # second try: foreign module surfaces allowed at a high per-mm cost (exception, not the rule)
            res, why2 = rr.route_pair(net, isl[i], isl[j], foreign=(foreign_g, set(), SOFT))
            if res is not None:
                why = 'ok (soft)'
                print(f"  soft {net.split('/')[-1]:24s} crossed a foreign module surface")
        dt = time.time() - ts
        if res is None:
            skip.add((sigs[i], sigs[j]))
            report.append({'net': net, 'ok': False, 'why': why, 'gap': round(d, 2), 's': round(dt, 1)})
            print(f"  FAIL {net.split('/')[-1]:24s} {why} (gap {d:.2f} mm, {dt:.1f} s)")
            continue
        segs, vias, w = res
        R.commit(net, segs, vias)
        if rr is RL:
            RL.B = R.B
        report.append({'net': net, 'ok': True, 'segs': len(segs), 'vias': len(vias), 'gap': round(d, 2),
                       'len': round(sum(math.hypot(c[0] - a[0], c[1] - a[1]) for _, a, c, _ in segs), 2)})
        print(f"  ok   {net.split('/')[-1]:24s} {len(segs)} segs {len(vias)} vias (gap {d:.2f}, {dt:.1f} s)")
        sys.stdout.flush()
pcbnew.SaveBoard(dst, b)
for ext in ('.kicad_pro', '.kicad_dru'):
    s = os.path.splitext(src)[0] + ext
    if os.path.isfile(s):
        shutil.copy2(s, os.path.splitext(dst)[0] + ext)
if opt('--report'):
    json.dump(report, open(opt('--report'), 'w'), indent=1)
ok = sum(1 for r in report if r['ok'])
print(f"intermod: {ok} routed, {len(report) - ok} failed")

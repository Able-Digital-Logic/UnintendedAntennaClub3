"""revert_nets.py BASE.kicad_pcb NEW.kicad_pcb OUT.kicad_pcb NET [NET ...]
Selective revert (lossless fallback for clean-up passes): the listed nets get their BASE copper back in NEW; every
other net whose NEW copper would conflict with that (mr.py pairwise rules) is reverted too, repeated until the set is
closed. Since BASE was legal, the closure always exists. KiCad python (BASE copper read in a child process)."""
import json
import os
import shutil
import subprocess
import sys

argv = sys.argv[1:]
base, new, dst = argv[0], argv[1], argv[2]
DST0 = dst
seeds = [a for a in argv[3:] if not a.startswith('--')]
DJ = os.path.splitext(dst)[0] + '_basecopper.json'
if '--dump' in argv:
    import pcbnew
    b = pcbnew.LoadBoard(base)
    out = {}
    for t in b.GetTracks():
        n = t.GetNetname()
        e = out.setdefault(n, {'t': [], 'v': []})
        if t.GetClass() == 'PCB_VIA':
            c = t.GetPosition()
            e['v'].append([c.x, c.y, t.GetWidth(pcbnew.F_Cu), t.GetDrill()])
        else:
            e['t'].append([b.GetLayerName(t.GetLayer()), [t.GetStart().x, t.GetStart().y], [t.GetEnd().x, t.GetEnd().y], t.GetWidth()])
    json.dump(out, open(DJ, 'w'))
    sys.exit(0)
r = subprocess.run([sys.executable, os.path.abspath(__file__), base, new, dst, '--dump'], capture_output=True, text=True)
if r.returncode != 0:
    sys.exit('dump failed: ' + r.stderr[-800:])
BASEC = json.load(open(DJ))
# model helpers from highway2 (one board load: NEW)
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'highway2.py'), encoding='utf-8').read()
_cut = _src.index('nets = []')
sys.argv = ['highway2.py', new, dst + '.rv_work.kicad_pcb']
exec(compile(_src[:_cut], 'highway2_head', 'exec'))
from shapely.geometry import LineString, Point  # noqa: E402,F811


def full(n):
    return next((k for k in B.pads_by_net if k == n or k.split('/')[-1] == n), n)


S = set(full(n) for n in seeds)
removed = set()
for _ in range(50):
    # take the NEW copper of every net in S out of the model
    for n in S - removed:
        tr, vi = snapshot(n)
        remove_items(n, tr, vi)
        removed.add(n)
    # does the BASE copper of S conflict with anything left?
    grow = set()
    for n in S:
        bc = BASEC.get(n, {'t': [], 'v': []})
        geoms = [(ln, LineString([(a[0] / 1e6, a[1] / 1e6), (c[0] / 1e6, c[1] / 1e6)]).buffer(w / 2e6, 8), 'track') for ln, a, c, w in bc['t']]
        geoms += [(ln, Point(x / 1e6, y / 1e6).buffer(d / 2e6, 16), 'via') for x, y, d, h in bc['v'] for ln in mr.SIG]
        for ln, g, kind in geoms:
            if ln not in B.trees:
                continue
            ex = frozenset(k for k, e in B.pexempt.items() if e.intersects(g))
            for i in B.trees[ln].query(g.buffer(3.1)):
                geo, n2, k2 = B.items[ln][i]
                if n2 == n or n2 in S or k2 == 'pad':
                    continue
                if geo.distance(g) < mr.need(n, n2, k2, ex) - 1e-4:
                    grow.add(n2)
    if not grow:
        break
    S |= grow
    print(f"  revert set grows by {sorted(x.split('/')[-1] for x in grow)}")
for n in S:
    bc = BASEC.get(n, {'t': [], 'v': []})
    add_items(n, [(ln, tuple(a), tuple(c), w) for ln, a, c, w in bc['t']], [tuple(v) for v in bc['v']])
pcbnew.SaveBoard(DST0, b)
for ext in ('.kicad_pro', '.kicad_dru'):
    s_ = os.path.splitext(new)[0] + ext
    if os.path.isfile(s_):
        shutil.copy2(s_, os.path.splitext(DST0)[0] + ext)
print(f"revert_nets: {len(S)} net(s) back to BASE copper: {sorted(x.split('/')[-1] for x in S)} -> {DST0}")

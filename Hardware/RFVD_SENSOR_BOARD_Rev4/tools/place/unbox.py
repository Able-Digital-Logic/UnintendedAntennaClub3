"""unbox.py IN.kicad_pcb OUT.kicad_pcb NET@REF [NET@REF ...] [--reach 1.6] [--move 1.6] [--max-movers 4]
Automated 'scored placement per component' (user rule 2026-10-02) for boxed connection ends: for each boxed pad
(REF's pad on NET) the movable parts around it - REF itself when movable, plus parts with a pad or courtyard within
--reach mm of the pad (2/3/4-pad passives, low/medium sensitivity, never fixed parts, ICs, connectors, crystals,
inductors) - are re-placed by placefit.py inside +-move mm windows (4 rotations), scored by:
    the boxed pad escaping to the inner layer (REF.pad-ESC), every GND pad of a mover taking a via (-VIA),
    and every connection the movers had restored afterwards (placefit's restore step).
The result is kept only if KiCad's unconnected count does not rise, the pads-with-copper count does not fall and no
net loses connectivity (metrics.py); otherwise the board stays as it was. Endpoints are processed in order on the
evolving board. KiCad python (placefit / metrics in child processes). Scratch copies only."""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
argv = sys.argv[1:]


def opt(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


src, dst = argv[0], argv[1]
OPTS = ('--reach', '--move', '--max-movers', '--sens')
ends = [a for i, a in enumerate(argv[2:], 2) if '@' in a and argv[i - 1] not in OPTS]
REACH = float(opt('--reach', '1.6'))
MOVE = float(opt('--move', '1.6'))
MAXM = int(opt('--max-movers', '4'))
G = os.path.dirname(HERE)
sens = json.load(open(os.path.join(HERE, 'sensitivity.json')))['parts']
FIXED = set(json.load(open(r'C:/Users/gabor/Documents/RFVDProject_SeniorDsgn/RFVD_Authoritative/tools/jev_s1/projects/rfvd.json')).get('fixed_parts', []))
cur = os.path.splitext(dst)[0] + '_ub_cur.kicad_pcb'


def copy_board(a, b_):
    shutil.copy2(a, b_)
    for ext in ('.kicad_pro', '.kicad_dru'):
        s_ = os.path.splitext(a)[0] + ext
        if os.path.isfile(s_):
            shutil.copy2(s_, os.path.splitext(b_)[0] + ext)


def run(args, timeout=3600):
    r = subprocess.run([PY] + args, capture_output=True, text=True, timeout=timeout,
                       env=dict(os.environ, MSYS_NO_PATHCONV='1', PYTHONIOENCODING='utf-8'))
    return r.returncode, '\n'.join(l for l in r.stdout.splitlines() if 'memory leak' not in l and 'image handler' not in l), r.stderr


def movers_for(board, net, ref):
    """query the board (child process) for the boxed pad and the movable parts around it"""
    code = r'''
import sys, json, pcbnew
sys.path.insert(0, r"%s")
import mr
from shapely.geometry import Point
b = pcbnew.LoadBoard(r"%s")
net, ref, reach = %r, %r, %f
f = b.FindFootprintByReference(ref)
p = next((q for q in f.Pads() if q.GetNetname() == net or q.GetNetname().split('/')[-1] == net), None)
if p is None:
    print(json.dumps(None)); sys.exit(0)
pc = Point(p.GetPosition().x / 1e6, p.GetPosition().y / 1e6)
out = {'pad': p.GetNumber(), 'xy': [pc.x, pc.y], 'net': p.GetNetname(), 'near': []}
for g in b.GetFootprints():
    r = g.GetReference()
    side = 'B' if g.IsFlipped() else 'F'
    cy = mr.poly_of(g.GetCourtyard(pcbnew.B_CrtYd if side == 'B' else pcbnew.F_CrtYd))
    d = cy.distance(pc) if not cy.is_empty else 99
    if d <= reach:
        out['near'].append([r, side, g.GetPosition().x / 1e6, g.GetPosition().y / 1e6, len(list(g.Pads())),
                            [[q.GetNumber(), q.GetNetname()] for q in g.Pads()], round(d, 3)])
print(json.dumps(out))
''' % (G, board, net, ref, REACH)
    r = subprocess.run([PY, '-c', code], capture_output=True, text=True, env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    line = [l for l in r.stdout.splitlines() if l.startswith('{') or l == 'null']
    return json.loads(line[-1]) if line else None


def movable(ref, npads):
    if ref in FIXED or ref[:1] in ('U', 'J', 'Y', 'L', 'H', 'Q', 'D', 'F', 'K', 'S') or npads > 8:
        return False
    s = sens.get(ref, {}).get('sensitivity', 'low')
    return s in ('low', 'medium')


def metrics(a, b_):
    code, out, err = run([os.path.join(HERE, 'metrics.py'), a, b_])
    lines = out.splitlines()
    nums = []
    for l in lines[:2]:
        try:
            u = int(l.split('unconnected ')[1].split(',')[0])
            e = int(l.split('pads with copper ')[1].split(',')[0])
            nums.append((u, e))
        except Exception:
            nums.append(None)
    worse = '{}'
    for l in lines:
        if ' worse ' in l:
            worse = l.split(' worse ')[1].strip()
    return nums, worse


copy_board(src, cur)
log = []
for end in ends:
    net, ref = end.split('@')
    info = movers_for(cur, net, ref)
    if not info:
        print(f"{end}: pad not found")
        continue
    cands = []
    for r, side, x, y, npad, nets, d in sorted(info['near'], key=lambda t: t[6]):
        if movable(r, npad):
            cands.append((r, x, y, nets))
    cands = cands[:MAXM]
    if not cands:
        print(f"{end}: nothing movable near the pad")
        log.append({'end': end, 'ok': False, 'why': 'no movers'})
        continue
    # neighbours first (nearest first), the boxed part itself last; growing mover sets, first improvement wins
    nb = [c for c in cands if c[0] != ref]
    own = [c for c in cands if c[0] == ref]
    sets = ([own] if own else []) + [nb[:k] + own for k in range(1, len(nb) + 1)]
    kept_ = False
    for mv in sets:
        args = [os.path.join(HERE, 'placefit.py'), cur, os.path.splitext(dst)[0] + '_ub_try.kicad_pcb']
        for r, x, y, nets in mv:
            args += ['--part', f"{r}:{x - MOVE:.3f},{y - MOVE:.3f},{x + MOVE:.3f},{y + MOVE:.3f}:0/90/180/270"]
        # the boxed pad must escape (scored for every mover pose); every other non-GND pad of a mover must reach
        # its net again from the new pose (so a pose that strands a connection loses)
        args += ['--conn', f"{ref}.{info['pad']}-ESC"]
        for r, x, y, nets in mv:
            for num, nn in nets:
                if nn and nn != 'GND' and not nn.startswith('unconnected') and not (r == ref and num == info['pad']):
                    args += ['--conn', f"{r}.{num}-NET"]
        args += ['--step', '0.1', '--keep', '25']
        code, out, err = run(args)
        try_b = os.path.splitext(dst)[0] + '_ub_try.kicad_pcb'
        if code != 0 or not os.path.isfile(try_b):
            print(f"{end}: placefit failed {err[-600:]}")
            continue
        nums, worse = metrics(cur, try_b)
        (u0, e0), (u1, e1) = nums if all(nums) else ((0, 0), (1, 0))
        good = u1 <= u0 and e1 >= e0 and worse == '{}' and (u1 < u0 or e1 > e0)
        print(f"{end}: movers {[c[0] for c in mv]} -> unconnected {u0}->{u1}, pads-with-copper {e0}->{e1}, "
              f"worse {worse} => {'KEEP' if good else 'reject'}")
        for l in out.splitlines():
            if l.startswith('  ') and ('best' in l or 'no legal' in l):
                print('    ' + l.strip()[:150])
        sys.stdout.flush()
        if good:
            copy_board(try_b, cur)
            log.append({'end': end, 'ok': True, 'movers': [c[0] for c in mv], 'u': [u0, u1], 'e': [e0, e1]})
            kept_ = True
            break
    if not kept_:
        log.append({'end': end, 'ok': False, 'movers': [c[0] for c in cands]})
copy_board(cur, dst)
json.dump(log, open(os.path.splitext(dst)[0] + '_unbox.json', 'w'), indent=1)
print(f"unbox: {sum(1 for l in log if l['ok'])} of {len(log)} ends improved -> {dst}")

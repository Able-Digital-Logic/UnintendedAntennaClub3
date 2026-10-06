"""dru_sideaware.py SRC.kicad_dru DST.kicad_dru BOARD.kicad_pcb   (2026-10-04, critique P0-5 / RULES-01)
Makes the courtyard-based exemptions of the DRU layer-correct.

KiCad 10.0.6 facts (probed by the critique, work/verify-RULES-01):
  - A.intersectsCourtyard('R') tests R's mounted-side courtyard but ignores the copper layer of item A, so an exemption
    meant for copper inside an IC's F courtyard also applies to In3/B copper under that IC (204 hidden errors on m17).
  - intersectsFrontCourtyard / intersectsBackCourtyard are NOT board-side aware (a B-side J11 matches Front, never
    Back), so they cannot fix it.
Fix: every rule that uses intersectsCourtyard(...) and has no (layer ...) clause is split into three copies:
  __F  (layer "F.Cu"): each pattern expanded to the matching refs mounted on F (vias keep the pattern itself),
  __B  (layer "B.Cu"): the same for refs mounted on B,
  __I  (layer inner):  only vias keep the exemption (a via spans every layer).
Because the expansion freezes today's sides, two side-guard assertion rules are appended: they fail DRC if any of the
expanded refs is flipped later (then re-run this tool). Rules that already have a (layer ...) clause, comments and
#SIGNOFF lines are copied unchanged. Write only to a scratch copy; land with the DRU scoped exception (sentinel A/B
DRC, atomic write, hash check)."""
import fnmatch
import re
import sys

import pcbnew

src, dst, pcb = sys.argv[1:4]
b = pcbnew.LoadBoard(pcb)
side = {fp.GetReference(): ('B' if fp.IsFlipped() else 'F') for fp in b.GetFootprints()}
lines = open(src, encoding='utf-8').read().split('\n')
blocks, cur = [], None
for ln in lines:
    if ln.startswith('(rule '):
        if cur:
            blocks.append(cur)
        cur = [ln]
    elif cur is not None and ln.startswith('   '):
        cur.append(ln)
    else:
        if cur:
            blocks.append(cur)
            cur = None
        blocks.append(ln)
if cur:
    blocks.append(cur)

used = {'F': set(), 'B': set()}


def expand(who, pat, s):
    refs = sorted(r for r, sd in side.items() if sd == s and fnmatch.fnmatchcase(r, pat))
    used[s].update(refs)
    via = "(%s.Type == 'Via' && %s.intersectsCourtyard('%s'))" % (who, who, pat)
    if not refs:
        return '(' + via + ')'
    return '(' + via + ' || ' + ' || '.join("%s.intersectsCourtyard('%s')" % (who, r) for r in refs) + ')'


out, n = [], 0
for bl in blocks:
    if isinstance(bl, str):
        out.append(bl)
        continue
    body = '\n'.join(bl)
    if 'intersectsCourtyard' not in body or '(layer' in body:
        out.append(body)
        continue
    n += 1
    name = re.match(r'\(rule "([^"]+)"', bl[0]).group(1)
    for suf, lay, s in (('F', '"F.Cu"', 'F'), ('B', '"B.Cu"', 'B'), ('I', 'inner', None)):
        if s:
            nb = re.sub(r"(A|B)\.intersectsCourtyard\('([^']+)'\)", lambda m: expand(m.group(1), m.group(2), s), body)
        else:
            nb = re.sub(r"(A|B)\.intersectsCourtyard\('([^']+)'\)",
                        lambda m: "(%s.Type == 'Via' && %s.intersectsCourtyard('%s'))" % (m.group(1), m.group(1), m.group(2)), body)
        nb = nb.replace('(rule "%s"' % name, '(rule "%s__%s"\n   (layer %s)' % (name, suf, lay), 1)
        out.append(nb)

guard = ['', '# ---- side guards for the side-aware courtyard exemptions above (dru_sideaware.py). If a part listed here',
         '# ---- is flipped, these assertions fail: re-run tools/dru_sideaware.py on the new board.']
for s, layer in (('F', 'F.Cu'), ('B', 'B.Cu')):
    refs = sorted(used[s])
    if refs:
        cond = ' || '.join("A.Reference == '%s'" % r for r in refs)
        guard.append('(rule "zz_side_guard_%s"\n   (condition "A.Type == \'Footprint\' && (%s)")\n'
                     '   (constraint assertion "A.Layer == \'%s\'")\n   (severity error))' % (s, cond, layer))
open(dst, 'w', encoding='utf-8', newline='\n').write('\n'.join(out).rstrip('\n') + '\n' + '\n'.join(guard) + '\n')
print(f'split {n} rules into F/B/inner copies; side guards: F {len(used["F"])} refs, B {len(used["B"])} refs -> {dst}')

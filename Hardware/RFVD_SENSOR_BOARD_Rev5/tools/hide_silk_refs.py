"""hide_silk_refs.py IN.kicad_pcb OUT.kicad_pcb
Removes every reference designator from the silkscreen (user request 2026-10-02): each footprint's Reference field on
F.Silkscreen / B.Silkscreen is hidden, and any extra footprint text on a silkscreen layer that shows the reference
(${REFERENCE} or the literal designator) is hidden too. Designators on the fab layers stay (assembly drawings).
Prints before / after counts. KiCad python; run it on a board KiCad does not have open."""
import os
import shutil
import sys

import pcbnew

src, dst = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(src)
SILK = (pcbnew.F_SilkS, pcbnew.B_SilkS)


def silk_refs(board):
    n = 0
    for f in board.GetFootprints():
        r = f.Reference()
        if r.IsVisible() and r.GetLayer() in SILK:
            n += 1
        for it in f.GraphicalItems():
            if it.GetClass() in ('PCB_TEXT', 'FP_TEXT') and it.GetLayer() in SILK and it.IsVisible():
                t = it.GetText()
                if '${REFERENCE}' in t or t == f.GetReference():
                    n += 1
    return n


before = silk_refs(b)
for f in b.GetFootprints():
    r = f.Reference()
    if r.GetLayer() in SILK:
        r.SetVisible(False)
    for it in f.GraphicalItems():
        if it.GetClass() in ('PCB_TEXT', 'FP_TEXT') and it.GetLayer() in SILK:
            t = it.GetText()
            if '${REFERENCE}' in t or t == f.GetReference():
                it.SetVisible(False)
after = silk_refs(b)
pcbnew.SaveBoard(dst, b)
if os.path.normcase(os.path.abspath(src)) != os.path.normcase(os.path.abspath(dst)):
    for ext in ('.kicad_pro', '.kicad_dru'):
        s_ = os.path.splitext(src)[0] + ext
        if os.path.isfile(s_):
            shutil.copy2(s_, os.path.splitext(dst)[0] + ext)
print(f"hide_silk_refs: visible silkscreen designators {before} -> {after} ({dst})")

"""kipy_vias.py PLAN.json [--apply] [--fix-nets FINAL_PLAN_VIAS.json]

User-approved kicad-python scope (2026-09-29): DELETE vias / MOVE vias only, over KiCad's IPC on the live board,
dry-run first, applied as ONE undo step (one commit), then saved and verified from the file + DRC.
  default (dry run): lists the plan's del_vias that are present on the open board (matched by UUID, then by
                     net + position) and what would be removed.
  --apply          : removes exactly those vias inside one begin_commit/push_commit (one undo step).
Run with the Python that has kipy (py -3.12)."""
import json
import sys

from kipy import KiCad
from kipy.board_types import Via

argv = sys.argv[1:]
plan = json.load(open(argv[0]))
apply_ = '--apply' in argv
kicad = KiCad()
board = kicad.get_board()
vias = board.get_vias()
by_uuid = {str(v.id.value): v for v in vias}
want = plan['del_vias']
hit, miss = [], []
for d in want:
    v = by_uuid.get(d['uuid'])
    if v is None:
        # fall back to net + position (UUIDs can change if the board was re-saved through another path)
        for c in vias:
            if (c.net.name == d['net'] and abs(c.position.x / 1e6 - d['x']) < 1e-3
                    and abs(c.position.y / 1e6 - d['y']) < 1e-3):
                v = c
                break
    (hit if v is not None else miss).append((d, v))
print(f"board vias {len(vias)} | to delete {len(want)}: found {len(hit)}, missing {len(miss)}")
for d, v in hit[:12]:
    print(f"   del {d['net'][:24]:24s} ({d['x']:.3f},{d['y']:.3f}) {d['d']}/{d['drill']}")
if miss:
    print('   missing (already gone?):', [(m['net'], m['x'], m['y']) for m, _ in miss[:10]])
if apply_ and hit:
    commit = board.begin_commit()
    board.remove_items([v for _, v in hit])
    board.push_commit(commit, f"RFVD transfer: remove {len(hit)} vias replaced by the scratch layout")
    print(f"removed {len(hit)} vias in one undo step")

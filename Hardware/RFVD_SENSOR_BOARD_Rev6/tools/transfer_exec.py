"""transfer_exec.py PLAN.json BOARD PHASE OUT_CALLS.json
Turns a transfer_plan.py work list into Konnect MCP call batches for konnect_call.py.
  PHASE closed : flip_component for side changes, then set_component_placements (chunks of 60) for every moved or
                 flipped part (absolute x, y, rotation) - works on a closed board file (Konnect guarded file edit).
  PHASE live   : delete_trace (by project UUID) for removed tracks, route_trace for added tracks, add_via for added
                 vias - needs the board open in KiCad (IPC). Removed vias are NOT here (no Konnect tool; done with
                 kicad-python under the user-approved 'delete vias' scope).
BOARD is the board path Konnect should edit (the project board, or a test copy)."""
import json
import sys

plan_p, board, phase, out = sys.argv[1:5]
plan = json.load(open(plan_p))
calls = []
if phase == 'closed':
    calls.append({"tool": "load_toolset", "args": {"name": ["placement", "pcb_components"]}})
    for ref, s in sorted(plan['flips'].items()):
        calls.append({"tool": "flip_component", "args": {"board": board, "reference": ref,
                                                            "layer": "B.Cu" if s['side'] == 'B' else "F.Cu"}})
    items = [{"reference": r, "x": s['x'], "y": s['y'], "rotation": s['rot']}
             for r, s in sorted({**plan['moves'], **plan['flips']}.items())]
    for i in range(0, len(items), 60):
        calls.append({"tool": "set_component_placements", "args": {"board": board, "placements": items[i:i + 60]}})
elif phase == 'live':
    calls.append({"tool": "load_toolset", "args": {"name": ["pcb_routing"]}})
    for t in plan['del_tracks']:
        calls.append({"tool": "delete_trace", "args": {"board": board, "uuid": t['uuid']}})
    for t in plan['add_tracks']:
        calls.append({"tool": "route_trace", "args": {"board": board, "net_name": t['net'], "layer": t['layer'],
                                                      "x1": t['a'][0], "y1": t['a'][1], "x2": t['c'][0], "y2": t['c'][1],
                                                      "width": t['w']}})
    # vias AFTER every track: KiCad re-nets an IPC-created via from the copper it touches (a via that touches no
    # same-net copper yet, e.g. inside a GND pour, became GND in the 2026-10-02 test) - verify all via nets after saving
    for v in plan['add_vias']:
        calls.append({"tool": "add_via", "args": {"board": board, "net_name": v['net'], "x": v['x'], "y": v['y'],
                                                  "drill": v['drill'], "pad_size": v['d']}})
json.dump(calls, open(out, 'w'), indent=1)
print(f"{phase}: {len(calls)} calls -> {out}")

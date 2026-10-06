"""Per-net islands (unrouted connections = islands - 1) after refilling zones. Scratch copies only. KiCad python.
usage: unconn.py board.kicad_pcb out.json [--no-fill]"""
import sys, json, collections
import pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
if '--no-fill' not in sys.argv:
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.BuildConnectivity()
conn = b.GetConnectivity()
conn.RecalculateRatsnest()
total = conn.GetUnconnectedCount(False)
pads_by_net = collections.defaultdict(list)
for f in b.GetFootprints():
    for p in f.Pads():
        if p.GetNetCode() > 0 and not p.GetNetname().startswith('unconnected-'):
            pads_by_net[p.GetNetname()].append(p)
res = {}
for n, pads in pads_by_net.items():
    if len(pads) < 2:
        continue
    key = lambda p: (p.GetParentFootprint().GetReference(), p.GetNumber(), p.GetPosition().x, p.GetPosition().y)
    seen, islands = set(), []
    for p in pads:
        if key(p) in seen:
            continue
        isl = {key(p)}
        for q in conn.GetConnectedItems(p):
            if q.GetClass() == 'PAD':
                isl.add(key(q))
        seen |= isl
        islands.append(sorted(f"{k[0]}.{k[1]}" for k in isl))
    if len(islands) > 1:
        res[n] = {'islands': len(islands), 'missing': len(islands) - 1, 'parts': islands}
miss = sum(v['missing'] for v in res.values())
print(f"kicad unconnected {total} | nets incomplete {len(res)} of {len(pads_by_net)} | missing connections {miss}")
json.dump(res, open(sys.argv[2], 'w'), indent=1)

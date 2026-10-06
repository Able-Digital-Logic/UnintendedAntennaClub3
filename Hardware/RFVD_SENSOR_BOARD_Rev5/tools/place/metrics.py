"""metrics.py BOARD... : unconnected count (KiCad ratsnest), pads with copper, and per-net island counts diff vs the first board."""
import sys
import pcbnew
res = []
for f_ in sys.argv[1:]:
    b = pcbnew.LoadBoard(f_)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.BuildConnectivity()
    conn = b.GetConnectivity()
    U = conn.GetUnconnectedCount(False)
    E = 0
    isl = {}
    seen = set()
    for f in b.GetFootprints():
        for p in f.Pads():
            n = p.GetNetname()
            if not n or n.startswith('unconnected'):
                continue
            items = list(conn.GetConnectedItems(p))
            if n != 'GND' and any((it.Cast() if hasattr(it, 'Cast') else it).GetClass() in ('PCB_TRACK', 'PCB_ARC', 'PCB_VIA') for it in items):
                E += 1
            k = p.m_Uuid.AsString()
            if k in seen:
                continue
            seen.add(k)
            for it in items:
                it = it.Cast() if hasattr(it, 'Cast') else it
                if it.GetClass() == 'PAD':
                    seen.add(it.m_Uuid.AsString())
            isl[n] = isl.get(n, 0) + 1
    res.append((f_, U, E, isl))
    print(f"{f_}: unconnected {U}, pads with copper {E}, nets incomplete {sum(1 for v in isl.values() if v > 1)}")
base = res[0][3]
for f_, U, E, isl in res[1:]:
    worse = {n: (base.get(n), v) for n, v in isl.items() if v > base.get(n, 1)}
    better = {n: (base.get(n), v) for n, v in isl.items() if v < base.get(n, 1)}
    print(f"{f_} vs {res[0][0]}: worse {worse}\n   better {better}")

"""netisl.py BOARD NET... : KiCad connectivity islands of each net (pads per island) - after zone fill."""
import sys
import pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.BuildConnectivity()
conn = b.GetConnectivity()
for want in sys.argv[2:]:
    nets = [n for n in b.GetNetsByName().keys() if str(n) == want or str(n).split('/')[-1] == want]
    for n in nets:
        n = str(n)
        pads = [p for f in b.GetFootprints() for p in f.Pads() if p.GetNetname() == n]
        seen, isl = set(), []
        for p in pads:
            k = p.m_Uuid.AsString()
            if k in seen:
                continue
            items = [p] + list(conn.GetConnectedItems(p))
            grp = []
            for it in items:
                it = it.Cast() if hasattr(it, 'Cast') else it
                if it.GetClass() == 'PAD':
                    seen.add(it.m_Uuid.AsString())
                    grp.append(it.GetParentFootprint().GetReference() + '.' + it.GetNumber())
            isl.append(sorted(set(grp)))
        print(f"{n.split('/')[-1]:20s} {len(isl)} island(s): " + ' | '.join(' '.join(g) for g in isl))

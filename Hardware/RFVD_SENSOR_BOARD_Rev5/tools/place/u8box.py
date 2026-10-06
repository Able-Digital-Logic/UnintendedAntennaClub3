"""u8box.py BOARD IC [--corr 2.2] [--lat 0.45]: open pins of IC (no track/via attached) with the copper and parts in
their outward escape corridor, and the copper attached to each blocking part (what a move would strand)."""
import sys, math, collections
import pcbnew
from shapely.geometry import box, Point, LineString
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))))
import mr
argv = sys.argv[1:]
def opt(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d
src, ic = argv[0], argv[1]
CORR = float(opt('--corr', '2.2')); LAT = float(opt('--lat', '0.45'))
b = pcbnew.LoadBoard(src)
b.BuildConnectivity()
conn = b.GetConnectivity()
u = b.FindFootprintByReference(ic)
cx, cy = u.GetPosition().x / 1e6, u.GetPosition().y / 1e6
padgeo = []
for f in b.GetFootprints():
    for p in f.Pads():
        for lid, ln in ((pcbnew.F_Cu, 'F'), (pcbnew.B_Cu, 'B')):
            if p.IsOnLayer(lid):
                padgeo.append((f.GetReference(), p.GetNumber(), ln, p.GetNetname(), mr.poly_of(p.GetEffectivePolygon(lid, pcbnew.ERROR_OUTSIDE))))
trk = []
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        c = t.GetPosition(); trk.append(('via', 'FB', t.GetNetname(), Point(c.x/1e6, c.y/1e6).buffer(t.GetWidth(pcbnew.F_Cu)/2e6)))
    else:
        ln = b.GetLayerName(t.GetLayer())
        trk.append(('trk', ln, t.GetNetname(), LineString([(t.GetStart().x/1e6, t.GetStart().y/1e6), (t.GetEnd().x/1e6, t.GetEnd().y/1e6)]).buffer(t.GetWidth()/2e6)))
def attached(f):
    out = collections.Counter()
    for p in f.Pads():
        for it in conn.GetConnectedItems(p):
            it = it.Cast() if hasattr(it, 'Cast') else it
            if it.GetClass() in ('PCB_TRACK', 'PCB_ARC', 'PCB_VIA'):
                out[(p.GetNumber(), p.GetNetname().split('/')[-1], it.GetClass()[4:])] += 1
    return dict(out)
blockers = set()
for p in sorted(u.Pads(), key=lambda q: int(q.GetNumber()) if q.GetNumber().isdigit() else 999):
    net = p.GetNetname()
    if not net or net.startswith('unconnected') or net == 'GND':
        continue
    its = [it for it in conn.GetConnectedItems(p) if (it.Cast() if hasattr(it,'Cast') else it).GetClass() in ('PCB_TRACK','PCB_ARC','PCB_VIA')]
    if its:
        continue
    px, py = p.GetPosition().x/1e6, p.GetPosition().y/1e6
    dx, dy = px-cx, py-cy
    ux, uy = ((1 if dx > 0 else -1), 0) if abs(dx) > abs(dy) else (0, (1 if dy > 0 else -1))
    g = mr.poly_of(p.GetEffectivePolygon(pcbnew.F_Cu, pcbnew.ERROR_INSIDE))
    x0, y0, x1, y1 = g.bounds
    end = (x1 if ux > 0 else x0, py) if ux else (px, y1 if uy > 0 else y0)
    ex, ey = end[0]+ux*CORR, end[1]+uy*CORR
    if ux:
        cor = box(min(end[0], ex), py-LAT, max(end[0], ex), py+LAT)
    else:
        cor = box(px-LAT, min(end[1], ey), px+LAT, max(end[1], ey))
    hits = []
    for ref, num, ln, n2, gg in padgeo:
        if ref == ic or not gg.intersects(cor):
            continue
        c = gg.centroid
        t = (c.x-end[0])*ux + (c.y-end[1])*uy
        hits.append(f"{ref}.{num}{ln}:{n2.split('/')[-1]}{'*' if n2 == net else ''}@{t:.2f}")
        blockers.add(ref)
    for kind, ln, n2, gg in trk:
        if gg.intersects(cor) and n2 != net:
            c = gg.centroid
            hits.append(f"{kind}{ln[:2]}:{n2.split('/')[-1]}")
    print(f"{ic}.{p.GetNumber():>3s} {net.split('/')[-1]:18s} out=({ux},{uy}) end=({end[0]:.3f},{end[1]:.3f}) :: {' '.join(hits) if hits else '-'}")
print()
for r in sorted(blockers):
    f = b.FindFootprintByReference(r)
    print(f"{r:6s} {'B' if f.IsFlipped() else 'F'} ({f.GetPosition().x/1e6:.3f},{f.GetPosition().y/1e6:.3f}) rot {f.GetOrientationDegrees():.0f} pads {[(q.GetNumber(), q.GetNetname().split('/')[-1]) for q in f.Pads()]} attached {attached(f)}")

"""icband.py BOARD IC [--out 1.7] [--in 1.0]: parts whose pads/courtyards lie in IC's pin escape bands (outer band:
pin outer end .. +out mm; inner band: pin inner end .. -in mm), with datasheet sensitivity and attached copper."""
import sys, json, collections
import pcbnew
from shapely.geometry import box
from shapely.ops import unary_union
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))))
import mr
argv = sys.argv[1:]
def opt(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d
src, ic = argv[0], argv[1]
OUT = float(opt('--out', '1.7')); IN = float(opt('--in', '1.0'))
sens = json.load(open(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), 'sensitivity.json')))['parts']
b = pcbnew.LoadBoard(src)
b.BuildConnectivity(); conn = b.GetConnectivity()
u = b.FindFootprintByReference(ic)
cx, cy = u.GetPosition().x/1e6, u.GetPosition().y/1e6
outer, inner = [], []
for p in u.Pads():
    g = mr.poly_of(p.GetEffectivePolygon(pcbnew.F_Cu, pcbnew.ERROR_INSIDE))
    x0, y0, x1, y1 = g.bounds
    px, py = p.GetPosition().x/1e6, p.GetPosition().y/1e6
    dx, dy = px-cx, py-cy
    if abs(dx) > abs(dy):
        s = 1 if dx > 0 else -1
        o = (x1, x1+OUT) if s > 0 else (x0-OUT, x0); i_ = (x0-IN, x0) if s > 0 else (x1, x1+IN)
        outer.append(box(o[0], y0-0.1, o[1], y1+0.1)); inner.append(box(i_[0], y0-0.1, i_[1], y1+0.1))
    else:
        s = 1 if dy > 0 else -1
        o = (y1, y1+OUT) if s > 0 else (y0-OUT, y0); i_ = (y0-IN, y0) if s > 0 else (y1, y1+IN)
        outer.append(box(x0-0.1, o[0], x1+0.1, o[1])); inner.append(box(x0-0.1, i_[0], x1+0.1, i_[1]))
OB, IB = unary_union(outer), unary_union(inner)
rows = []
for f in b.GetFootprints():
    r = f.GetReference()
    if r == ic: continue
    side = 'B' if f.IsFlipped() else 'F'
    lid = pcbnew.B_Cu if side == 'B' else pcbnew.F_Cu
    pads = unary_union([mr.poly_of(q.GetEffectivePolygon(lid, pcbnew.ERROR_OUTSIDE)) for q in f.Pads() if q.IsOnLayer(lid)] or [box(0,0,0,0)])
    hit_o, hit_i = pads.intersection(OB).area, pads.intersection(IB).area
    if hit_o < 1e-4 and hit_i < 1e-4: continue
    att = collections.Counter()
    for q in f.Pads():
        n = q.GetNetname()
        if n == 'GND': continue
        for it in conn.GetConnectedItems(q):
            it = it.Cast() if hasattr(it, 'Cast') else it
            if it.GetClass() in ('PCB_TRACK','PCB_ARC','PCB_VIA'):
                att[n.split('/')[-1]] += 1
    s = sens.get(r, {})
    rows.append((r, side, s.get('sensitivity','?'), s.get('max_mm'), s.get('anchor'), s.get('gap_mm'), round(hit_o,3), round(hit_i,3),
                 [q.GetNetname().split('/')[-1] for q in f.Pads()], dict(att), s.get('role','')[:40]))
for row in sorted(rows, key=lambda r: ({'low':0,'medium':1,'high':2,'critical':3}.get(r[2],4), r[0])):
    print(f"{row[0]:6s} {row[1]} {row[2]:8s} max {row[3]} anchor {row[4]} gap {row[5]} | outer {row[6]} inner {row[7]} | pads {row[8]} | copper {row[9]} | {row[10]}")

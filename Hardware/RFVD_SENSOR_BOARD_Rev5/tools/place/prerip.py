"""prerip.py IN.kicad_pcb OUT.kicad_pcb REF[,REF...] [--keep-net NET,...]
   or: prerip.py IN.kicad_pcb OUT.kicad_pcb --prune-nets NET[,NET...]   (only prune dangling copper of those nets)
   or: prerip.py IN.kicad_pcb OUT.kicad_pcb --rip-at NET@x,y,r [--rip-at ...]  (remove NET's tracks/vias touching the
       disc, then prune: clears a local DRC problem so ripfix can re-route that piece)
Pre-step for moving parts (placement audit 2026-10-02): every non-GND track / via touching a pad of the listed parts
is removed, then the dangling remains of those nets are pruned back to the next junction / pad / via / zone
(iteratively: a track end touching nothing of its net, a via holding fewer than two items). Nothing else is touched.
KiCad python, scratch copies only (removed items kept alive: SWIG graveyard)."""
import math
import os
import shutil
import sys

import pcbnew
from shapely.geometry import LineString, Point

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mr  # noqa: E402

argv = sys.argv[1:]
src, dst = argv[0], argv[1]
if os.path.normcase(os.path.realpath(dst)).startswith(mr.PROTECTED):
    sys.exit('refusing to write into the project folder')
PRUNE_ONLY = argv[argv.index('--prune-nets') + 1].split(',') if '--prune-nets' in argv else None
RIP_AT = []
for i_, a_ in enumerate(argv):
    if a_ == '--rip-at':
        n_, xyr = argv[i_ + 1].split('@')
        RIP_AT.append((n_, tuple(float(v) for v in xyr.split(','))))
if RIP_AT and PRUNE_ONLY is None:
    PRUNE_ONLY = [n_ for n_, _ in RIP_AT]
refs = [] if PRUNE_ONLY else argv[2].split(',')
keep = set()
if '--keep-net' in argv:
    keep = set(argv[argv.index('--keep-net') + 1].split(','))
GRAVE = []
b = pcbnew.LoadBoard(src)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())


def tgeo(t):
    if t.GetClass() == 'PCB_VIA':
        c = t.GetPosition()
        return Point(c.x / 1e6, c.y / 1e6).buffer(t.GetWidth(pcbnew.F_Cu) / 2e6, 16)
    return LineString([(t.GetStart().x / 1e6, t.GetStart().y / 1e6), (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)]).buffer(t.GetWidth() / 2e6, 8)


pad_geo = []
nets = set()
for r in refs:
    fp = b.FindFootprintByReference(r)
    if fp is None:
        sys.exit(f'no footprint {r}')
    for p in fp.Pads():
        n = p.GetNetname()
        if not n or n == 'GND' or n in keep or n.startswith('unconnected'):
            continue
        nets.add(n)
        for lid in (pcbnew.F_Cu, pcbnew.B_Cu):
            if p.IsOnLayer(lid):
                pad_geo.append((lid, mr.poly_of(p.GetEffectivePolygon(lid, pcbnew.ERROR_OUTSIDE)), n))
if PRUNE_ONLY:
    allnets = set(t.GetNetname() for t in b.GetTracks())
    nets = set(n for n in allnets if n in PRUNE_ONLY or n.split('/')[-1] in PRUNE_ONLY)
kill = []
for t in b.GetTracks():
    n = t.GetNetname()
    if n not in nets:
        continue
    g = tgeo(t)
    for lid, pg, pn in pad_geo:
        if pn == n and (t.GetClass() == 'PCB_VIA' or t.GetLayer() == lid) and pg.intersects(g):
            kill.append(t)
            break
for n_, (x_, y_, r_) in RIP_AT:
    disc = Point(x_, y_).buffer(r_, 24)
    for t in b.GetTracks():
        if (t.GetNetname() == n_ or t.GetNetname().split('/')[-1] == n_) and tgeo(t).intersects(disc) and t not in kill:
            kill.append(t)
for t in kill:
    b.Remove(t)
    t.thisown = 0
    GRAVE.append(t)
print(f"prerip: removed {len(kill)} items touching {refs or [a for a, _ in RIP_AT]} on {sorted(x.split('/')[-1] for x in nets)}")
# ---- prune dangling remains of those nets (true geometric connectivity: tracks incl. arcs, vias, pads, zone fills)
CU = [l_ for l_ in b.GetEnabledLayers().CuStack()]


def arcpts(t):
    s_, m_, e_ = t.GetStart(), t.GetMid(), t.GetEnd()
    ax, ay, mx, my, ex, ey = s_.x / 1e6, s_.y / 1e6, m_.x / 1e6, m_.y / 1e6, e_.x / 1e6, e_.y / 1e6
    d = 2 * (ax * (my - ey) + mx * (ey - ay) + ex * (ay - my))
    if abs(d) < 1e-12:
        return [(ax, ay), (ex, ey)]
    ux = ((ax * ax + ay * ay) * (my - ey) + (mx * mx + my * my) * (ey - ay) + (ex * ex + ey * ey) * (ay - my)) / d
    uy = ((ax * ax + ay * ay) * (ex - mx) + (mx * mx + my * my) * (ax - ex) + (ex * ex + ey * ey) * (mx - ax)) / d
    r_ = math.hypot(ax - ux, ay - uy)
    a0, a1, am = math.atan2(ay - uy, ax - ux), math.atan2(ey - uy, ex - ux), math.atan2(my - uy, mx - ux)

    def norm(x):
        return x % (2 * math.pi)
    sweep = norm(a1 - a0)
    if norm(am - a0) > sweep:
        sweep -= 2 * math.pi
    return [(ux + r_ * math.cos(a0 + sweep * k / 24), uy + r_ * math.sin(a0 + sweep * k / 24)) for k in range(25)]


def geo_of(t):
    if t.GetClass() == 'PCB_VIA':
        c = t.GetPosition()
        g = Point(c.x / 1e6, c.y / 1e6).buffer(t.GetWidth(pcbnew.F_Cu) / 2e6, 16)
        top, bot = t.TopLayer(), t.BottomLayer()
        ls = [l_ for l_ in CU if CU.index(top) <= CU.index(l_) <= CU.index(bot)]
        return {l_: g for l_ in ls}
    pts = arcpts(t) if t.GetClass() == 'PCB_ARC' else [(t.GetStart().x / 1e6, t.GetStart().y / 1e6), (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)]
    return {t.GetLayer(): LineString(pts).buffer(t.GetWidth() / 2e6, 8)}


fixed = {}       # pads and zone fills per (net, layer)
for p in [p for f in b.GetFootprints() for p in f.Pads() if p.GetNetname() in nets]:
    for l_ in CU:
        if p.IsOnLayer(l_):
            fixed.setdefault((p.GetNetname(), l_), []).append(mr.poly_of(p.GetEffectivePolygon(l_, pcbnew.ERROR_OUTSIDE)))
for z in b.Zones():
    if not z.GetIsRuleArea() and z.GetNetname() in nets:
        for l_ in CU:
            if z.IsOnLayer(l_):
                fixed.setdefault((z.GetNetname(), l_), []).append(mr.poly_of(z.GetFilledPolysList(l_)))
total = 0
for _ in range(80):
    objs = [t for t in b.GetTracks() if t.GetNetname() in nets]
    G_ = [(t, geo_of(t)) for t in objs]
    dead = []
    for i, (t, gt) in enumerate(G_):
        n = t.GetNetname()
        if t.GetClass() == 'PCB_VIA':
            if any(g.intersects(gt[l_]) for l_ in gt for g in fixed.get((n, l_), [])):
                continue
            touch = []
            for j, (o, go) in enumerate(G_):
                if j == i or o.GetNetname() != n:
                    continue
                if any(l_ in go and go[l_].intersects(gt[l_]) for l_ in gt):
                    touch.append(o)
            if len(touch) >= 2:
                continue
            if len(touch) == 1 and touch[0].GetClass() != 'PCB_VIA':
                o = touch[0]
                c = t.GetPosition()
                r = t.GetWidth(pcbnew.F_Cu) / 2e6
                ends_in = any(math.hypot(e.x / 1e6 - c.x / 1e6, e.y / 1e6 - c.y / 1e6) <= r + o.GetWidth() / 2e6 for e in (o.GetStart(), o.GetEnd()))
                if not ends_in:
                    continue        # a track passes through the via: not dangling
            if len(touch) == 1 and touch[0].GetClass() == 'PCB_VIA':
                continue
            dead.append(t)
            continue
        l_ = t.GetLayer()
        for e in (t.GetStart(), t.GetEnd()):
            disc = Point(e.x / 1e6, e.y / 1e6).buffer(max(t.GetWidth() / 2e6 - 0.005, 0.01), 8)
            ok = any(g.intersects(disc) for g in fixed.get((n, l_), []))
            if not ok:
                for j, (o, go) in enumerate(G_):
                    if j != i and o.GetNetname() == n and l_ in go and go[l_].intersects(disc):
                        ok = True
                        break
            if not ok:
                dead.append(t)
                break
    if not dead:
        break
    for t in dead:
        b.Remove(t)
        t.thisown = 0
        GRAVE.append(t)
    total += len(dead)
print(f"prerip: pruned {total} dangling items")
pcbnew.SaveBoard(dst, b)
for ext in ('.kicad_pro', '.kicad_dru'):
    a = os.path.splitext(src)[0] + ext
    if os.path.isfile(a):
        shutil.copy2(a, os.path.splitext(dst)[0] + ext)
print(f"prerip -> {dst}")

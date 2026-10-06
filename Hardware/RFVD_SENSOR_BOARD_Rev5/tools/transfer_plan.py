"""transfer_plan.py PROJECT.kicad_pcb FINAL.kicad_pcb OUT.json  (read-only, KiCad python)

Diff between the real project board and the final scratch board, as the work list for the Konnect transfer:
  moves     footprints whose position / rotation changed (same side)   -> Konnect set_component_placements
  flips     footprints that changed side                                -> Konnect flip_component (+ placement)
  del_tracks / add_tracks   (net, layer, start, end, width) multiset diff; deletions carry the project UUID
                                                                         -> Konnect delete_trace / route_trace
  del_vias / add_vias       (net, position, diameter, drill)             -> kipy (approved scope: delete vias) / Konnect add_via
  add_zones / del_zones     copper zones by (name, net, layers, outline) -> Konnect add_zone / (manual)
Nothing is written to either board."""
import collections
import json
import sys

import pcbnew

P, S, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
bp = pcbnew.LoadBoard(P)
bs = pcbnew.LoadBoard(S)
R4 = lambda v: round(v / 1e6, 4)


def parts(b):
    return {f.GetReference(): {'x': R4(f.GetPosition().x), 'y': R4(f.GetPosition().y),
                               'rot': round(f.GetOrientationDegrees() % 360, 3), 'side': 'B' if f.IsFlipped() else 'F'}
            for f in b.GetFootprints()}


def tracks(b):
    out = collections.defaultdict(list)
    for t in b.GetTracks():
        if t.GetClass() != 'PCB_TRACK':
            continue
        a = (R4(t.GetStart().x), R4(t.GetStart().y))
        c = (R4(t.GetEnd().x), R4(t.GetEnd().y))
        a, c = (a, c) if a <= c else (c, a)
        k = (t.GetNetname(), b.GetLayerName(t.GetLayer()), a, c, R4(t.GetWidth()))
        out[k].append(t.m_Uuid.AsString())
    return out


def vias(b):
    out = collections.defaultdict(list)
    for t in b.GetTracks():
        if t.GetClass() != 'PCB_VIA':
            continue
        k = (t.GetNetname(), R4(t.GetPosition().x), R4(t.GetPosition().y), R4(t.GetWidth(pcbnew.F_Cu)), R4(t.GetDrill()))
        out[k].append(t.m_Uuid.AsString())
    return out


def zones(b):
    out = {}
    for z in b.Zones():
        if z.GetIsRuleArea():
            continue
        o = z.Outline()
        pts = []
        for i in range(o.OutlineCount()):
            ch = o.Outline(i)
            pts.append([(R4(ch.CPoint(k).x), R4(ch.CPoint(k).y)) for k in range(ch.PointCount())])
        lays = sorted(b.GetLayerName(l) for l in z.GetLayerSet().CuStack())
        out[(z.GetZoneName(), z.GetNetname(), tuple(lays), json.dumps(pts))] = {
            'name': z.GetZoneName(), 'net': z.GetNetname(), 'layers': lays, 'outline': pts,
            'priority': z.GetAssignedPriority(), 'min_width': R4(z.GetMinThickness()),
            'clearance': R4(z.GetLocalClearance() or 0)}
    return out


pp, ps = parts(bp), parts(bs)
moves, flips = {}, {}
for r, s in ps.items():
    p = pp.get(r)
    if p is None:
        continue
    if p['side'] != s['side']:
        flips[r] = s
    elif abs(p['x'] - s['x']) > 1e-4 or abs(p['y'] - s['y']) > 1e-4 or abs(p['rot'] - s['rot']) > 0.01:
        moves[r] = s
tp, ts = tracks(bp), tracks(bs)
del_tracks, add_tracks = [], []
for k in set(tp) | set(ts):
    n_p, n_s = len(tp.get(k, [])), len(ts.get(k, []))
    if n_p > n_s:
        for u in tp[k][:n_p - n_s]:
            del_tracks.append({'uuid': u, 'net': k[0], 'layer': k[1], 'a': k[2], 'c': k[3], 'w': k[4]})
    elif n_s > n_p:
        for _ in range(n_s - n_p):
            add_tracks.append({'net': k[0], 'layer': k[1], 'a': k[2], 'c': k[3], 'w': k[4]})
vp, vs = vias(bp), vias(bs)
del_vias, add_vias = [], []
for k in set(vp) | set(vs):
    n_p, n_s = len(vp.get(k, [])), len(vs.get(k, []))
    if n_p > n_s:
        for u in vp[k][:n_p - n_s]:
            del_vias.append({'uuid': u, 'net': k[0], 'x': k[1], 'y': k[2], 'd': k[3], 'drill': k[4]})
    elif n_s > n_p:
        for _ in range(n_s - n_p):
            add_vias.append({'net': k[0], 'x': k[1], 'y': k[2], 'd': k[3], 'drill': k[4]})
zp, zs = zones(bp), zones(bs)
add_zones = [v for k, v in zs.items() if k not in zp]
del_zones = [v for k, v in zp.items() if k not in zs]
plan = {'project': P, 'final': S, 'moves': moves, 'flips': flips, 'del_tracks': del_tracks, 'add_tracks': add_tracks,
        'del_vias': del_vias, 'add_vias': add_vias, 'add_zones': add_zones, 'del_zones': del_zones}
json.dump(plan, open(OUT, 'w'), indent=1)
print(f"transfer plan: {len(moves)} moves, {len(flips)} flips | tracks -{len(del_tracks)} +{len(add_tracks)} | "
      f"vias -{len(del_vias)} +{len(add_vias)} | zones +{len(add_zones)} -{len(del_zones)}")

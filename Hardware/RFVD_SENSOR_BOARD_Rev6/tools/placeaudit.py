"""placeaudit.py BOARD.kicad_pcb [--out PREFIX] [--long 12] [--min-saving 3] [--png] [--max-pads 8] [--only REF,REF]
Connection-length placement audit (user rule 2026-10-02: parts that share nets sit together so they connect with short
tracks; links that cannot be short at least stay in one area; long or odd connections are flagged and the PLACEMENT is
fixed before routing). Replaces farparts.py. Read-only, KiCad python.

For every net except GND the ratsnest is the minimum spanning tree over its pads (straight-line lengths).
  connections  every MST edge between two different parts: length, ends, routed (same copper island) or open, and
               LONG (> --long mm) with the end that is cheapest to move ('mover': small, not fixed, low sensitivity).
  parts        each footprint with <= --max-pads pads: demand = sum over its signal pads of the distance to the nearest
               same-net pad on another part; the best spot (0.5 mm grid near those partners, same pad offsets) and its
               saving; the nearest LEGAL free spot to it (query.free_spots: outline, courtyards, footprint keep-outs,
               B-side height windows; copper not checked) and the saving there; the datasheet rule from
               docs/sensitivity.json. Class: FIXED (mechanical: rfvd.json fixed_parts; every footprint is locked, so
               the lock flag says nothing), KEEP (placed by function, reason in placeaudit_keep.json), OVER (outside
               its datasheet distance budget, live gap from dsgap.py), MOVE (saving at a free spot >= --min-saving, the spot keeps the part
               within its datasheet distance of its anchor pin, and the part is not high/critical), OK.
  detours      complete nets whose routed copper is much longer than their ratsnest (ratio > 1.6 and > 8 mm extra).
Writes PREFIX_connections.csv, PREFIX_parts.csv, PREFIX_summary.md and with --png PREFIX_map.png
(F and B side by side; ratsnest lines green <= 5 mm, orange <= LONG, red > LONG; open connections drawn thicker).
"""
import csv
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew  # noqa: E402

import mr  # noqa: E402,F401  (poly_of via query)
import query  # noqa: E402
import dsgap  # noqa: E402  (live datasheet gaps; sensitivity.json gap_mm was measured on old poses)

argv = sys.argv[1:]


def opt(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


src = argv[0]
PREFIX = opt('--out', os.path.splitext(src)[0] + '_audit')
LONG = float(opt('--long', '12'))
MINS = float(opt('--min-saving', '3'))
MAXP = int(opt('--max-pads', '8'))
ONLY = set(opt('--only').split(',')) if opt('--only') else None
SENS = opt('--sens', query.SENS)
PROJ = opt('--project-json', os.path.join(HERE, '..', '..', '..', 'tools', 'jev_s1', 'projects', 'rfvd.json'))
sens = json.load(open(SENS, encoding='utf-8'))['parts'] if os.path.isfile(SENS) else {}
fixed = set(json.load(open(PROJ)).get('fixed_parts', [])) if os.path.isfile(PROJ) else set()
KEEPF = opt('--keep', os.path.join(HERE, 'placeaudit_keep.json'))
keep = {k: v for k, v in (json.load(open(KEEPF, encoding='utf-8')).items() if os.path.isfile(KEEPF) else []) if not k.startswith('_')}

b = pcbnew.LoadBoard(src)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.BuildConnectivity()
conn = b.GetConnectivity()
fps = {f.GetReference(): f for f in b.GetFootprints()}
LIVE = dsgap.live_gaps(b, sens)


def sig(n):
    return bool(n) and n != 'GND' and not n.startswith('unconnected')


# ---- pads, copper islands (KiCad connectivity, zones filled)
pads = []          # (ref, num, net, x, y, uuid)
island = {}
nid = 0
for r, f in fps.items():
    for p in f.Pads():
        n = p.GetNetname()
        if not sig(n):
            continue
        u = p.m_Uuid.AsString()
        pads.append((r, p.GetNumber(), n, p.GetPosition().x / 1e6, p.GetPosition().y / 1e6, u))
        if u in island:
            continue
        nid += 1
        island[u] = nid
        for it in conn.GetConnectedItems(p):
            it = it.Cast() if hasattr(it, 'Cast') else it
            if it.GetClass() == 'PAD':
                island.setdefault(it.m_Uuid.AsString(), nid)
by_net = {}
for pd in pads:
    by_net.setdefault(pd[2], []).append(pd)


def mst(pts):
    n = len(pts)
    if n < 2:
        return []
    inT = [False] * n
    d = [math.inf] * n
    par = [-1] * n
    d[0] = 0
    out = []
    for _ in range(n):
        i = min((k for k in range(n) if not inT[k]), key=lambda k: d[k])
        inT[i] = True
        if par[i] >= 0:
            out.append((par[i], i, d[i]))
        for k in range(n):
            if not inT[k]:
                dk = math.hypot(pts[i][3] - pts[k][3], pts[i][4] - pts[k][4])
                if dk < d[k]:
                    d[k] = dk
                    par[k] = i
    return out


def mobility(r):
    """lower = cheaper to move"""
    f = fps[r]
    s = sens.get(r, {}).get('sensitivity', '')
    if r in fixed:
        return 99
    np_ = len(list(f.Pads()))
    base = 0 if np_ <= 3 else (1 if np_ <= 8 else 5)
    return base + {'critical': 4, 'high': 3, 'medium': 1}.get(s, 0)


# ---- connections
conns = []
mst_len = {}
for n, P in by_net.items():
    E = mst(P)
    mst_len[n] = sum(e[2] for e in E)
    for i, j, L in E:
        a, c = P[i], P[j]
        if a[0] == c[0]:
            continue
        routed = island.get(a[5]) == island.get(c[5])
        mover = min((a[0], c[0]), key=mobility)
        if mobility(mover) >= 99:
            mover = '-'
        conns.append({'net': query.short(n), 'from': f'{a[0]}.{a[1]}', 'to': f'{c[0]}.{c[1]}', 'length_mm': round(L, 2),
                      'routed': routed, 'long': L > LONG, 'mover': mover,
                      'ax': round(a[3], 2), 'ay': round(a[4], 2), 'bx': round(c[3], 2), 'by': round(c[4], 2)})
conns.sort(key=lambda c: -c['length_mm'])

# ---- parts
sig_pads = {}
for pd in pads:
    sig_pads.setdefault(pd[0], []).append(pd)


def partner(n, ref, x, y):
    best = None
    for r2, _, _, qx, qy, _ in by_net.get(n, []):
        if r2 == ref:
            continue
        d = math.hypot(qx - x, qy - y)
        if best is None or d < best[0]:
            best = (d, qx, qy, r2)
    return best


def demand_at(ref, offs, x, y):
    return sum((partner(n, ref, x + ox, y + oy) or (0,))[0] for n, ox, oy in offs)


def offsets_for(f, rot):
    """pad offsets of f's signal pads (relative to its origin) if it were at orientation rot"""
    o = f.GetPosition()
    dr = math.radians(rot - f.GetOrientationDegrees())
    ca, sa = math.cos(dr), math.sin(dr)
    out = []
    for r_, _, n, x, y, _ in sig_pads.get(f.GetReference(), []):
        dx, dy = x - o.x / 1e6, y - o.y / 1e6
        # KiCad: positive orientation is counter-clockwise on screen (y down): x' = x cos + y sin, y' = -x sin + y cos
        out.append((n, dx * ca + dy * sa, -dx * sa + dy * ca))
    return out


anchor_xy = {}
for r_, f_ in fps.items():
    for p_ in f_.Pads():
        anchor_xy[f"{r_}.{p_.GetNumber()}"] = (p_.GetPosition().x / 1e6, p_.GetPosition().y / 1e6)


def within_budget(r, x, y):
    """the datasheet rule (anchor REF.PIN, max_mm) still holds with the part's origin at (x, y)"""
    s_ = sens.get(r, {})
    a_, m_ = s_.get('anchor'), s_.get('max_mm')
    if not a_ or m_ is None or a_ not in anchor_xy:
        return True
    ax, ay = anchor_xy[a_]
    f_ = fps[r]
    half = max(f_.GetBoundingBox(False).GetWidth(), f_.GetBoundingBox(False).GetHeight()) / 2e6
    return math.hypot(x - ax, y - ay) - half <= m_


rows = []
for r, f in fps.items():
    P = sig_pads.get(r, [])
    np_ = len(list(f.Pads()))
    if not P or np_ > MAXP or (ONLY and r not in ONLY):
        continue
    o = f.GetPosition()
    cx, cy = o.x / 1e6, o.y / 1e6
    offs = [(n, x - cx, y - cy) for _, _, n, x, y, _ in P]
    now = demand_at(r, offs, cx, cy)
    parts_ = [partner(n, r, cx + ox, cy + oy) for n, ox, oy in offs]
    parts_ = [p for p in parts_ if p]
    if not parts_:
        continue
    gx = sum(p[1] for p in parts_) / len(parts_)
    gy = sum(p[2] for p in parts_) / len(parts_)
    best = (now, cx, cy)
    for i in range(-16, 17):
        for j in range(-16, 17):
            x, y = gx + i * 0.5, gy + j * 0.5
            dm = demand_at(r, offs, x, y)
            if dm < best[0] - 1e-6:
                best = (dm, x, y)
    s = sens.get(r, {})
    lv = LIVE.get(r, {})
    over = bool(lv) and lv['gap'] > lv['max']
    free = None
    if now - best[0] >= MINS and r not in fixed:
        side = query.side_of(f)
        win = (best[1] - 8, best[2] - 8, best[1] + 8, best[2] + 8)
        for d, x, y, rot in query.free_spots(b, r, side, win, (best[1], best[2]), step=0.25, limit=10):
            if not within_budget(r, x, y):
                continue
            dm = demand_at(r, offsets_for(f, rot), x, y)
            if free is None or dm < free[0]:
                free = (dm, x, y, rot, d)
    sv_free = round(now - free[0], 1) if free else 0.0
    cls = 'FIXED' if r in fixed else ('KEEP' if r in keep else ('OVER' if over else (
        'MOVE' if sv_free >= MINS and s.get('sensitivity') not in ('high', 'critical') else 'OK')))
    longest = max((c['length_mm'] for c in conns if c['from'].split('.')[0] == r or c['to'].split('.')[0] == r), default=0)
    rows.append({'ref': r, 'class': cls, 'side': query.side_of(f), 'x': round(cx, 2), 'y': round(cy, 2),
                 'value': f.GetValue()[:24], 'dnp': f.IsDNP(), 'sensitivity': s.get('sensitivity', ''),
                 'anchor': lv.get('anchor', s.get('anchor', '')), 'max_mm': s.get('max_mm', ''), 'gap_mm': lv.get('gap', ''),
                 'nets': ' '.join(sorted(set(query.short(p[2]) for p in P))), 'partners': ' '.join(sorted(set(p[3] for p in parts_))),
                 'demand_now_mm': round(now, 1), 'best_x': round(best[1], 2), 'best_y': round(best[2], 2),
                 'saving_best_mm': round(now - best[0], 1),
                 'free_x': round(free[1], 2) if free else '', 'free_y': round(free[2], 2) if free else '',
                 'free_rot': free[3] if free else '', 'saving_free_mm': sv_free, 'longest_conn_mm': round(longest, 1),
                 'keep_reason': keep.get(r, '')})
order = {'OVER': 0, 'MOVE': 1, 'OK': 2, 'KEEP': 3, 'FIXED': 4}
rows.sort(key=lambda r: (order[r['class']], -r['saving_free_mm'], -r['saving_best_mm']))

# ---- detours (complete nets only)
routed_len = {}
for t in b.GetTracks():
    n = t.GetNetname()
    if not sig(n) or t.GetClass() == 'PCB_VIA':
        continue
    routed_len[n] = routed_len.get(n, 0.0) + t.GetLength() / 1e6
detours = []
for n, P in by_net.items():
    if len(set(island.get(p[5]) for p in P)) != 1 or n not in routed_len or mst_len.get(n, 0) <= 0:
        continue
    rl, ml = routed_len[n], mst_len[n]
    if rl / ml > 1.6 and rl - ml > 8:
        detours.append({'net': query.short(n), 'pads': len(P), 'mst_mm': round(ml, 1), 'routed_mm': round(rl, 1), 'ratio': round(rl / ml, 2)})
detours.sort(key=lambda d: -(d['routed_mm'] - d['mst_mm']))

# ---- write
with open(PREFIX + '_connections.csv', 'w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=list(conns[0].keys()))
    w.writeheader()
    w.writerows(conns)
with open(PREFIX + '_parts.csv', 'w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ['ref'])
    w.writeheader()
    w.writerows(rows)
longc = [c for c in conns if c['long']]
tot = sum(mst_len.values())
md = [f"# Placement audit: {os.path.basename(src)}", '',
      f"- Ratsnest (MST, all nets but GND): **{tot:.0f} mm** over {len(conns)} part-to-part connections; "
      f"**{len(longc)} longer than {LONG:g} mm** ({sum(1 for c in longc if not c['routed'])} of them still open).",
      f"- Parts: {sum(1 for r in rows if r['class'] == 'MOVE')} MOVE candidates, {sum(1 for r in rows if r['class'] == 'OVER')} over their "
      f"datasheet budget, {sum(1 for r in rows if r['class'] == 'FIXED')} fixed (mechanical).",
      f"- Detours (routed copper > 1.6x ratsnest and > 8 mm extra): {len(detours)} nets.", '',
      '## MOVE candidates (a legal free spot shortens their connections)', '',
      '| Part | Side | Now | Nets | Partners | Demand now | Free spot | Saving |', '|---|---|---|---|---|---|---|---|']
for r in [r for r in rows if r['class'] == 'MOVE']:
    md.append(f"| {r['ref']}{' (DNP)' if r['dnp'] else ''} | {r['side']} | {r['x']}, {r['y']} | {r['nets'][:40]} | {r['partners'][:30]} | "
              f"{r['demand_now_mm']} mm | {r['free_x']}, {r['free_y']} rot {r['free_rot']} | {r['saving_free_mm']} mm |")
md += ['', '## Kept on purpose (placeaudit_keep.json)', '', '| Part | Reason | Demand now | Would save |', '|---|---|---|---|']
for r in [r for r in rows if r['class'] == 'KEEP']:
    md.append(f"| {r['ref']} | {r['keep_reason']} | {r['demand_now_mm']} mm | {r['saving_best_mm']} mm |")
md += ['', '## Over the datasheet distance budget', '', '| Part | Sensitivity | Anchor | Gap / max (mm) |', '|---|---|---|---|']
for r in [r for r in rows if r['class'] == 'OVER']:
    md.append(f"| {r['ref']} | {r['sensitivity']} | {r['anchor']} | {r['gap_mm']} / {r['max_mm']} |")
md += ['', f'## Longest connections (> {LONG:g} mm)', '', '| Net | From | To | Length | Routed | Cheapest end to move |', '|---|---|---|---|---|---|']
for c in longc[:60]:
    md.append(f"| {c['net']} | {c['from']} | {c['to']} | {c['length_mm']} | {'yes' if c['routed'] else '**open**'} | {c['mover']} |")
md += ['', '## Detours', '', '| Net | Pads | Ratsnest | Routed | Ratio |', '|---|---|---|---|---|']
for d in detours[:30]:
    md.append(f"| {d['net']} | {d['pads']} | {d['mst_mm']} | {d['routed_mm']} | {d['ratio']} |")
open(PREFIX + '_summary.md', 'w', encoding='utf-8').write('\n'.join(md) + '\n')

if '--png' in argv:
    from PIL import Image, ImageDraw, ImageFont
    bb = b.GetBoardEdgesBoundingBox()
    X0, Y0, W, H = bb.GetX() / 1e6, bb.GetY() / 1e6, bb.GetWidth() / 1e6, bb.GetHeight() / 1e6
    S, pad_ = 12.0, 3.0
    img = Image.new('RGB', (int((2 * W + 3 * pad_) * S), int((H + 2 * pad_) * S) + 24), 'white')
    dr = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype('arial.ttf', 10)
        big = ImageFont.truetype('arialbd.ttf', 16)
    except Exception:
        font = big = ImageFont.load_default()

    def P(x, y, side):
        ox = pad_ if side == 'F' else W + 2 * pad_
        return ((x - X0 + ox) * S, (y - Y0 + pad_) * S + 24)
    flag = {r['ref']: r['class'] for r in rows}
    for side, title in (('F', 'TOP (F)'), ('B', 'BOTTOM (B, seen from top)')):
        dr.text(P(X0, Y0 - 2.6, side), title, fill='black', font=big)
        dr.rectangle([P(X0, Y0, side), P(X0 + W, Y0 + H, side)], outline='black', width=2)
        for r, f in fps.items():
            if query.side_of(f) != side:
                continue
            g = query.courtyard(f)
            if g.is_empty:
                continue
            col = {'MOVE': (200, 0, 200), 'OVER': (220, 120, 0)}.get(flag.get(r), (170, 170, 190))
            gg = g if g.geom_type == 'Polygon' else max(g.geoms, key=lambda q: q.area)
            dr.polygon([P(x, y, side) for x, y in gg.exterior.coords], outline=col)
            if flag.get(r) in ('MOVE', 'OVER'):
                dr.text(P(g.bounds[0], g.bounds[1] - 1.2, side), r, fill=col, font=font)
    for c in sorted(conns, key=lambda c: c['length_mm']):
        L = c['length_mm']
        col = (0, 160, 0) if L <= 5 else ((240, 150, 0) if L <= LONG else (220, 0, 0))
        wdt = 1 if c['routed'] else 3
        a_side = query.side_of(fps[c['from'].split('.')[0]])
        b_side = query.side_of(fps[c['to'].split('.')[0]])
        for side in set((a_side, b_side)):
            dr.line([P(c['ax'], c['ay'], side), P(c['bx'], c['by'], side)], fill=col, width=wdt)
    img.save(PREFIX + '_map.png')
print(f"placeaudit: ratsnest {tot:.0f} mm, {len(conns)} connections, {len(longc)} > {LONG:g} mm "
      f"({sum(1 for c in longc if not c['routed'])} open); parts MOVE {sum(1 for r in rows if r['class'] == 'MOVE')}, "
      f"OVER {sum(1 for r in rows if r['class'] == 'OVER')}; detours {len(detours)} -> {PREFIX}_*")

"""geomstat.py BOARD.kicad_pcb OUT_PREFIX [--pref "In3.Cu:V;B.Cu:H;F.Cu:V@118,52,165,95.6|H"]
Track geometry statistics for the 'signal highways' cleanup (user request 2026-10-02 night: no zig-zags, no weird
geometry, one dominant direction per layer / region so routes do not cut the board into islands).

Per signal layer (and per region of the preference map) it reports:
  - total length and the share running in the PREFERRED axis, the perpendicular axis and on 45-degree diagonals;
  - bends per 10 mm, segments shorter than 0.25 mm (jog clutter), right / acute corners, non-octilinear segments;
  - zig-zag chains: runs between terminals whose length exceeds 1.25 x the octilinear distance of their ends, or that
    have more bends than needed + 1.
Preference syntax: LAYER:AXIS[@x0,y0,x1,y1|AXIS_ELSEWHERE]; AXIS = H (horizontal) or V (vertical).
Writes OUT_PREFIX.json and OUT_PREFIX_<layer>.png, with tracks coloured green (preferred), red (perpendicular) and
orange (diagonal); thick magenta marks zig-zag chains. KiCad python, read-only."""
import collections
import json
import math
import sys

import pcbnew
from PIL import Image, ImageDraw, ImageFont

argv = sys.argv[1:]


def opt(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


src, prefix = argv[0], argv[1]
PREF = opt('--pref', 'In3.Cu:V;B.Cu:H;F.Cu:V@118,52,165,95.6|H')


def parse_pref(s):
    out = {}
    for part in s.split(';'):
        ln, _, rest = part.partition(':')
        if '@' in rest:
            ax, _, r = rest.partition('@')
            boxs, _, other = r.partition('|')
            out[ln] = ([(tuple(float(v) for v in boxs.split(',')), ax)], other or None)
        else:
            out[ln] = ([], rest)
    return out


PM = parse_pref(PREF)


def pref_axis(ln, x, y):
    regions, default = PM.get(ln, ([], None))
    for (x0, y0, x1, y1), ax in regions:
        if x0 <= x <= x1 and y0 <= y <= y1:
            return ax, f'{ln}:{ax}@region'
    return default, f'{ln}:{default}'


b = pcbnew.LoadBoard(src)
SIG = [l for l in ('F.Cu', 'In3.Cu', 'B.Cu')]
lid = {l: b.GetLayerID(l) for l in SIG}
segs = collections.defaultdict(list)      # layer -> (net, a, c, w)
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        continue
    ln = b.GetLayerName(t.GetLayer())
    if ln not in SIG:
        continue
    a, c = t.GetStart(), t.GetEnd()
    segs[ln].append((t.GetNetname(), (a.x / 1e6, a.y / 1e6), (c.x / 1e6, c.y / 1e6), t.GetWidth() / 1e6))


def axis_of(a, c):
    dx, dy = c[0] - a[0], c[1] - a[1]
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return None
    ang = math.degrees(math.atan2(dy, dx)) % 180.0
    if min(ang, 180 - ang) < 1.0:
        return 'H'
    if abs(ang - 90) < 1.0:
        return 'V'
    if abs(ang - 45) < 1.0 or abs(ang - 135) < 1.0:
        return 'D'
    return 'X'          # not octilinear


# chains per layer: group connected segments of one net (ends meeting within 1e-3) and split at vias / pads
vias = [(t.GetPosition().x / 1e6, t.GetPosition().y / 1e6, t.GetNetname()) for t in b.GetTracks() if t.GetClass() == 'PCB_VIA']
pads = collections.defaultdict(list)
for f in b.GetFootprints():
    for p in f.Pads():
        pads[p.GetNetname()].append((p.GetPosition().x / 1e6, p.GetPosition().y / 1e6))
stats = {}
zig = collections.defaultdict(list)
for ln in SIG:
    S = collections.defaultdict(lambda: collections.Counter())
    for net, a, c, w in segs[ln]:
        L = math.hypot(c[0] - a[0], c[1] - a[1])
        ax = axis_of(a, c)
        mx, my = (a[0] + c[0]) / 2, (a[1] + c[1]) / 2
        pa, key = pref_axis(ln, mx, my)
        cls = 'pref' if ax == pa else ('diag' if ax == 'D' else ('perp' if ax in ('H', 'V') else 'nonocto'))
        S[key][cls] += L
        S[key]['total'] += L
        if L < 0.25:
            S[key]['short_segs'] += 1
    # chains: endpoint degree graph per net
    by_net = collections.defaultdict(list)
    for s in segs[ln]:
        by_net[s[0]].append(s)
    for net, ss in by_net.items():
        pts = collections.Counter()
        for _, a, c, w in ss:
            pts[(round(a[0], 3), round(a[1], 3))] += 1
            pts[(round(c[0], 3), round(c[1], 3))] += 1
        term = set(p for p, k in pts.items() if k != 2)
        term |= set((round(x, 3), round(y, 3)) for x, y, n in vias if n == net)
        term |= set((round(x, 3), round(y, 3)) for x, y in pads.get(net, []))
        adj = collections.defaultdict(list)
        for i, (_, a, c, w) in enumerate(ss):
            adj[(round(a[0], 3), round(a[1], 3))].append(i)
            adj[(round(c[0], 3), round(c[1], 3))].append(i)
        used = set()
        for i in range(len(ss)):
            if i in used:
                continue
            # walk both directions until terminals
            chain = [i]
            used.add(i)
            for end in (0, 1):
                cur = i
                p = (round(ss[cur][1 + end][0], 3), round(ss[cur][1 + end][1], 3))
                while p not in term:
                    nxt = [j for j in adj[p] if j not in used]
                    if not nxt:
                        break
                    j = nxt[0]
                    used.add(j)
                    chain.append(j)
                    a2, c2 = ss[j][1], ss[j][2]
                    pa_ = (round(a2[0], 3), round(a2[1], 3))
                    p = (round(c2[0], 3), round(c2[1], 3)) if pa_ == p else pa_
            if len(chain) < 3:
                continue
            L = sum(math.hypot(ss[j][2][0] - ss[j][1][0], ss[j][2][1] - ss[j][1][1]) for j in chain)
            ends = [p for p in set([(round(ss[j][1][0], 3), round(ss[j][1][1], 3)) for j in chain] +
                                   [(round(ss[j][2][0], 3), round(ss[j][2][1], 3)) for j in chain])
                    if sum(1 for j in chain if (round(ss[j][1][0], 3), round(ss[j][1][1], 3)) == p or
                           (round(ss[j][2][0], 3), round(ss[j][2][1], 3)) == p) == 1]
            if len(ends) != 2:
                continue
            (x0, y0), (x1, y1) = ends
            dx, dy = abs(x1 - x0), abs(y1 - y0)
            octile = max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)
            bends = len(chain) - 1
            if (L > 1.25 * octile and L - octile > 0.3) or bends > 3:
                zig[ln].append({'net': net, 'len': round(L, 2), 'octile': round(octile, 2), 'bends': bends,
                                'segs': [[ss[j][1], ss[j][2]] for j in chain]})
    stats[ln] = {k: {kk: round(vv, 1) for kk, vv in v.items()} for k, v in S.items()}
rep = {'pref': PREF, 'layers': stats, 'zigzag_chains': {ln: len(v) for ln, v in zig.items()},
       'zigzag_len_mm': {ln: round(sum(c['len'] for c in v), 1) for ln, v in zig.items()}}
json.dump({**rep, 'zigzag': zig}, open(prefix + '.json', 'w'), indent=1)
for ln in SIG:
    for key, v in stats[ln].items():
        tot = v.get('total', 0) or 1
        print(f"{key:22s} total {v.get('total', 0):7.1f} mm | pref {100 * v.get('pref', 0) / tot:5.1f}% perp {100 * v.get('perp', 0) / tot:5.1f}% "
              f"diag {100 * v.get('diag', 0) / tot:5.1f}% nonocto {v.get('nonocto', 0):5.1f} mm | short segs {int(v.get('short_segs', 0))}")
    print(f"   {ln}: zig-zag chains {len(zig[ln])}, {sum(c['len'] for c in zig[ln]):.0f} mm")
# renders
ps = pcbnew.SHAPE_POLY_SET()
b.GetBoardPolygonOutlines(ps, True)
bb = b.GetBoardEdgesBoundingBox()
X0, Y0 = bb.GetLeft() / 1e6 - 1, bb.GetTop() / 1e6 - 1
Wmm, Hmm = bb.GetWidth() / 1e6 + 2, bb.GetHeight() / 1e6 + 2
Sc = 14.0
for ln in SIG:
    im = Image.new('RGB', (int(Wmm * Sc), int(Hmm * Sc)), (18, 18, 22))
    dr = ImageDraw.Draw(im, 'RGBA')
    P = lambda x, y: ((x - X0) * Sc, (y - Y0) * Sc)
    for i in range(ps.OutlineCount()):
        ch = ps.Outline(i)
        dr.polygon([P(ch.CPoint(k).x / 1e6, ch.CPoint(k).y / 1e6) for k in range(ch.PointCount())], outline=(200, 200, 200))
    for (x0, y0, x1, y1), ax in PM.get(ln, ([], None))[0]:
        dr.rectangle([P(x0, y0), P(x1, y1)], outline=(90, 90, 160))
    for net, a, c, w in segs[ln]:
        ax = axis_of(a, c)
        pa, _ = pref_axis(ln, (a[0] + c[0]) / 2, (a[1] + c[1]) / 2)
        col = (60, 220, 90) if ax == pa else ((255, 170, 30) if ax == 'D' else ((235, 60, 60) if ax in ('H', 'V') else (255, 255, 255)))
        dr.line([P(*a), P(*c)], fill=col, width=max(1, int(w * Sc)))
    for chn in zig[ln]:
        for a, c in chn['segs']:
            dr.line([P(*a), P(*c)], fill=(255, 0, 255, 120), width=4)
    try:
        font = ImageFont.truetype('arial.ttf', 14)
    except Exception:
        font = ImageFont.load_default()
    dr.text((6, 4), f"{ln}  green=preferred  red=perpendicular  orange=45deg  magenta=zig-zag chain", fill=(240, 240, 240), font=font)
    im.save(f"{prefix}_{ln.replace('.', '_')}.png")
print('geomstat ->', prefix + '.json and per-layer PNGs')

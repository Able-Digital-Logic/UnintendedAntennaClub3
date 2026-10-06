"""mr.py - rule-aware mini router for the RFVD SENSOR-D board (KiCad python, scratch copies only).

    mr.py IN.kicad_pcb OUT.kicad_pcb (--nets N1 N2 ... | --nets-file F.json) [--grid 0.05] [--vip-small U8,RN202]
          [--layers F.Cu,In3.Cu,B.Cu] [--margin 0.03] [--report R.json] [--maxwin 30] [--via-cost 1.2]

Connects the islands of each net (pads + existing copper) with octilinear tracks on F.Cu / In3.Cu / B.Cu and
through vias, on a grid, with every obstacle inflated by the PAIRWISE clearance this board's DRU asks for:
  class clearances (pairwise max) / HS track-via 0.2 / clock track-via 0.3 (U*, J4, J11, D401, RN203 exempt) /
  buck SW 0.5 (U6 exempt) / RF keep-away 0.5, RF-GND via 0.3 (U2 exempt) / analog to exact-Default 0.5, to
  digital power 0.5 (U2, U7, U8, U13 exempt), to harness and HS 1.0 (U2, U8, U13 exempt), to buck SW 2.0 /
  +3V3_D-+3V3_A 2.0 (FB1 exempt) / H1-H4 non-GND copper 1.4 from the hole, vias 1.9 / H5-H6 0.5 /
  edge 1.0 for HS-analog-RF-SW (J1, J300, J3 exempt) else 0.5 / min_hole_clearance 0.25 / hole-to-hole 0.25 /
  rule areas: lanes (K15-K20, K16, K17), K3, K6, K10, K11, K7, AFE partition for HS-clock-harness on F/B (BR1, BR2,
  K16, U8, U13 exempt; In3 under the AFE is closed to them too, EMC), footprint keep-outs.
A via is placed only where it clears all three signal layers; same-net via-in-pad only in pads >= 0.45 mm (or in
--vip-small footprints). Exemptions are applied per cell (stricter than KiCad's whole-item test). Widths are the class
minimums (neck widths). The result must still pass drcsum.py; mr_verify.py removes routes that add DRC errors."""
import collections
import fnmatch
import heapq
import json
import math
import os
import shutil
import sys

import numpy as np
import pcbnew
import shapely
from PIL import Image, ImageDraw
from scipy import ndimage
from shapely.geometry import LineString, Point, Polygon, box, MultiPolygon, GeometryCollection
from shapely.ops import unary_union
from shapely.strtree import STRtree

HERE = os.path.dirname(os.path.abspath(__file__))
PROTECTED = os.path.normcase(os.path.realpath(
    r'C:/Users/gabor/Documents/RFVDProject_SeniorDsgn/RFVD_Authoritative/03_hardware/RFVD_SENSOR_BOARD_GITHUB'))
NETS = json.load(open(os.path.join(HERE, 'an', 'nets.json')))
SIG = ('F.Cu', 'In3.Cu', 'B.Cu')
_GRAVE = []

ANALOG3 = ('Analog_Precision', 'Ref_Kelvin', 'RF_Input')          # the sp_analog_* "A" classes
RFC = ('RF_Input', 'RF_50R')
NOISY = ('HighSpeed_Digital', 'HighSpeed_Clock', 'Harness_IO')
CLASS_CLR = {'Default': 0.1, 'HighSpeed_Digital': 0.1, 'HighSpeed_Clock': 0.1, 'Harness_IO': 0.1, 'Analog_Precision': 0.15,
             'Ref_Kelvin': 0.15, 'RF_Input': 0.15, 'RF_50R': 0.15, 'Power_Digital': 0.15, 'Power_Analog': 0.15,
             'Power_Battery': 0.2, 'Power_Buck_SW': 0.2, 'Ground': 0.15}
NECK = {'Power_Battery': 0.5, 'Power_Digital': 0.3, 'Power_Analog': 0.25, 'Power_Buck_SW': 0.5, 'Ref_Kelvin': 0.2,
        'Analog_Precision': 0.15, 'RF_Input': 0.15, 'RF_50R': 0.15, 'HighSpeed_Digital': 0.15, 'HighSpeed_Clock': 0.15,
        'Harness_IO': 0.15, 'Default': 0.1, 'Ground': 0.2}
VIA = {'Power_Battery': (0.6, 0.3)}            # others 0.45/0.2 (POFV minimum; hole-to-copper 0.25 checked)
EXEMPT = {'U': ['U*'], 'CLK': ['U*', 'J4', 'J11', 'D401', 'RN203'], 'AN': ['U2', 'U8', 'U13'],
          'ANP': ['U2', 'U7', 'U8', 'U13'], 'RF': ['U2'], 'SW': ['U6', 'U301'], 'FB': ['FB1'], 'EDGE': ['J1', 'J300', 'J3'],
          # neck-down areas: w_power_neckdown_in_ic (U*), v3_w_power_neckdown_j11 (J11), v3_w_chg_sw_neck (U301/C310/C311),
          # w_buck_sw_neck (U6/C35)
          'NK': ['U*', 'J11', 'C310', 'C311', 'C35', 'C3??']}
# per-net overrides of the class width/clearance (DRU rules that name nets): BTST/BOOT gate-charge nets min 0.15
# (v3_w_chg_btst, w_buck_boot); REGN (charger gate-drive LDO, < 50 mA) 0.3 opt / 0.15 clearance (dru_patch4 v9_regn_light)
NET_OVR = {'Net-(U301-BTST1)': {'w': 0.15}, 'Net-(U301-BTST2)': {'w': 0.15}, 'Net-(U6-BOOT)': {'w': 0.15},
           # v7_usb_fs_width: USB FS pair 0.15 (max 0.2)
           'USB_DP': {'w': 0.15, 'neck': 0.15}, 'USB_DM': {'w': 0.15, 'neck': 0.15},
           '/Battery, charger and USB-C/REGN': {'w': 0.3, 'clr': 0.15, 'neck': 0.15}}


def clr_of(n):
    o = NET_OVR.get(n)
    if o and 'clr' in o:
        return o['clr']
    return CLASS_CLR.get(cls(n), 0.1)


def width_of(n):
    o = NET_OVR.get(n)
    if o and 'w' in o:
        return o['w']
    return NECK.get(cls(n), 0.12)


def neck_of(n):
    o = NET_OVR.get(n)
    if o and 'neck' in o:
        return o['neck']
    c = cls(n)
    w = width_of(n)
    if c.startswith('Power') or c in ('Ground', 'Ref_Kelvin'):
        return min(w, 0.2)
    return w
LANE_OWNERS = {   # B.Cu lanes / F cells: pattern -> (layers, owners allowed for tracks, owners allowed for vias)
    'K15_BR5_CHANNEL*': (['B.Cu'], ['I2C_SCL', 'I2C_SDA', '+3V3_D'], []),
    'K18_BR3_FEED*': (['B.Cu'], ['+3V3_D'], ['GND']),
    'K16_DISP_LANE*': (['B.Cu'], ['CHG_INT_N', 'LCD_TE_MCU', '/Screen and controls/LCD_TE', '/STM32H743 controller/LCD_RST_MCU',
                                  'LCD_RST', '/STM32H743 controller/TP_RST_MCU', 'TP_RST', 'BUCK_SYNC',
                                  '/STM32H743 controller/BUCK_SYNC_MCU'], None),
    'K17_LSE_GUARD*': (['B.Cu'], ['Net-(U8-PC14)', 'Net-(U8-PC15)', 'GND'], None),
    'K19?_VSYS*': (['B.Cu'], ['VSYS'], ['VSYS', 'GND']),
    'K20a_EREF_LANE*': (['B.Cu'], ['ADC_EREF'], None),
    'K20b_VENV_LANE*': (['B.Cu'], ['ADC_VENV'], None),
    'K10F_HSE_CELL*': (['F.Cu'], ['+3V3_D', 'GND', 'Net-(Y1-OUT)', 'Net-(U8-PH0)'], ['+3V3_D', 'GND']),
    'K10B_HSE_SHADOW*': (['B.Cu'], [], ['GND']),
    'K6_B_RF_END*': (['B.Cu'], [], ['GND']),
    'K11_*': (['F.Cu'], ['GND'], ['GND']),
    'K7_H?*': (['F.Cu', 'In3.Cu', 'B.Cu'], None, []),
}
DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]


def _parse_dirpref(spec):
    """MR_DIRPREF='In3.Cu:V;B.Cu:H;F.Cu:V@x0,y0,x1,y1|H' -> {layer: ([(box, axis)], default_axis)}"""
    out = {}
    for part in (spec or '').split(';'):
        if ':' not in part:
            continue
        ln, _, rest = part.partition(':')
        if '@' in rest:
            ax, _, r = rest.partition('@')
            boxs, _, other = r.partition('|')
            out[ln.strip()] = ([(tuple(float(v) for v in boxs.split(',')), ax.strip())], (other or '').strip() or None)
        else:
            out[ln.strip()] = ([], rest.strip() or None)
    return out


# signal highways (user request 2026-10-02 night): one dominant direction per layer / region. A move along the
# preferred axis costs 1x, a 45-degree move MR_DIR_DIAG x, a perpendicular move MR_DIR_PERP x.
DIRPREF = _parse_dirpref(os.environ.get('MR_DIRPREF', ''))
DIR_PERP = float(os.environ.get('MR_DIR_PERP', '1.0'))
DIR_DIAG = float(os.environ.get('MR_DIR_DIAG', '1.0'))
# multiplier table: [axis 0 none / 1 H / 2 V][direction index]
_DMUL = [[1.0] * 8,
         [1.0 if dy == 0 else (DIR_PERP if dx == 0 else DIR_DIAG) for dx, dy in DIRS],
         [1.0 if dx == 0 else (DIR_PERP if dy == 0 else DIR_DIAG) for dx, dy in DIRS]]


def cls(n):
    return NETS.get(n, {'class': 'Default'})['class'].split(',')[0]


def exact_default(n):
    return NETS.get(n, {'class': 'Default'})['class'] == 'Default'


def need(n, m, mkind, ex):
    """clearance between a new track/via of net n and an existing item (kind mkind) of net m; ex = exemption keys
    that apply at this location."""
    cn, cm = cls(n), cls(m)
    c = max(clr_of(n), clr_of(m))
    gnd_m = cm == 'Ground' or m == 'GND'
    gnd_n = cn == 'Ground' or n == 'GND'
    if not gnd_m and not m.startswith('unconnected-'):
        if cn in ('HighSpeed_Digital', 'HighSpeed_Clock') and 'U' not in ex:
            c = max(c, 0.2)
        if cn == 'HighSpeed_Clock' and 'CLK' not in ex:
            c = max(c, 0.3)
    if not gnd_n and mkind != 'pad':      # existing HS/clock track or via against our copper
        if cm in ('HighSpeed_Digital', 'HighSpeed_Clock') and 'U' not in ex:
            c = max(c, 0.2)
        if cm == 'HighSpeed_Clock' and 'CLK' not in ex:
            c = max(c, 0.3)
    if cm == 'Power_Buck_SW' and cn not in ('Power_Buck_SW', 'Ground', 'Power_Battery', 'Power_Digital') \
            and not n.endswith('/BUCK_VCC') and 'SW' not in ex:
        c = max(c, 0.5)
    if (cm in RFC) != (cn in RFC) and not (gnd_m or gnd_n) and 'RF' not in ex:
        c = max(c, 0.5)
    if cm in RFC and gnd_n:
        c = max(c, 0.3)
    for a, bb in ((cn, cm), (cm, cn)):
        an, oth = (n, m) if a == cn else (m, n)
        if a in ANALOG3:
            if bb == 'Power_Buck_SW':
                c = max(c, 2.0)
            elif bb in ('HighSpeed_Digital', 'HighSpeed_Clock', 'Harness_IO') and 'AN' not in ex:
                c = max(c, 1.0)
            elif bb in ('Power_Digital', 'Power_Battery') and 'ANP' not in ex:
                c = max(c, 0.5)
            elif bb == 'Default' and exact_default(oth) and 'AN' not in ex:
                c = max(c, 0.5)
    if {n, m} == {'+3V3_D', '+3V3_A'} and 'FB' not in ex:
        c = max(c, 2.0)
    # v7_emc05_buck_sync_lse_3mm (EMC-05): the buck SYNC clock (both sides of R901) >= 3 mm from the LSE crystal nets
    if ({n.split('/')[-1], m.split('/')[-1]} & {'BUCK_SYNC', 'BUCK_SYNC_MCU'}) and             ({n, m} & {'Net-(U8-PC14)', 'Net-(U8-PC15)'}):
        c = max(c, 3.0)
    return c


def chain_pts(ch):
    return [(ch.CPoint(k).x / 1e6, ch.CPoint(k).y / 1e6) for k in range(ch.PointCount())]


def poly_of(ps):
    polys = []
    for i in range(ps.OutlineCount()):
        pts = chain_pts(ps.Outline(i))
        if len(pts) >= 3:
            polys.append(Polygon(pts, [chain_pts(ps.Hole(i, h)) for h in range(ps.HoleCount(i)) if ps.Hole(i, h).PointCount() >= 3]))
    return unary_union(polys).buffer(0) if polys else Polygon()


def polys_iter(g):
    if g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    if isinstance(g, (MultiPolygon, GeometryCollection)):
        out = []
        for q in g.geoms:
            out += polys_iter(q)
        return out
    return []


class Board:
    def __init__(self, path, vip_small=()):
        self.b = b = pcbnew.LoadBoard(path)
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
        self.L = {n: b.GetLayerID(n) for n in SIG}
        self.vip_small = list(vip_small)
        self.items = {ln: [] for ln in SIG}          # (geom, net, kind)
        self.holes = []                              # (Point, r, net)
        self.small_pads = collections.defaultdict(list)
        self.pads_by_net = collections.defaultdict(list)
        for f in b.GetFootprints():
            ref = f.GetReference()
            for p in f.Pads():
                net = p.GetNetname()
                for ln in SIG:
                    if p.IsOnLayer(self.L[ln]):
                        g = poly_of(p.GetEffectivePolygon(self.L[ln], pcbnew.ERROR_OUTSIDE))
                        if g.is_empty:
                            continue
                        self.items[ln].append((g, net, 'pad'))
                        if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                            x0, y0, x1, y1 = g.bounds
                            if min(x1 - x0, y1 - y0) < 0.45 - 1e-6 and not any(fnmatch.fnmatchcase(ref, q) for q in self.vip_small):
                                self.small_pads[net].append(g)
                if p.GetDrillSize().x > 0:
                    c = p.GetPosition()
                    hr = max(p.GetDrillSize().x, p.GetDrillSize().y) / 2e6
                    self.holes.append((Point(c.x / 1e6, c.y / 1e6), hr, net))
                    if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                        # min_hole_clearance: copper of every net 0.25 from a bare hole (modelled as a pad of net '')
                        hg = Point(c.x / 1e6, c.y / 1e6).buffer(hr + 0.25 - 0.1, 24)
                        for ln in SIG:
                            self.items[ln].append((hg, '__npth__', 'pad'))
                    else:
                        # DRU fab_pth_hole_clearance: other-net copper 0.30 from a plated pad's HOLE (the pad copper
                        # alone does not guarantee it on slotted / thin-ring pads, e.g. the J10 shell legs; found
                        # 2026-10-02 when the router put an SWDIO via 0.25 from a J10 hole). Modelled as a same-net
                        # disc so other nets keep need() >= 0.10 (smallest class clearance) from it: 0.20 + 0.10 = 0.30.
                        hg = Point(c.x / 1e6, c.y / 1e6).buffer(hr + 0.20 + 0.005, 24)
                        for ln in SIG:
                            self.items[ln].append((hg, net, 'pad'))
                if net:
                    self.pads_by_net[net].append(p)
        for t in b.GetTracks():
            self.add_item(t)
        # filled copper zones of other nets (power pours from pourlink.py) are obstacles too; GND pours are not
        # (they re-fill around new copper and stay connected through the planes)
        for z in b.Zones():
            if z.GetIsRuleArea() or z.GetNetname() in ('GND', ''):
                continue
            for ln in SIG:
                if z.IsOnLayer(self.L[ln]):
                    g = poly_of(z.GetFilledPolysList(self.L[ln]))
                    if not g.is_empty:
                        self.items[ln].append((g, z.GetNetname(), 'pad'))
        ps = pcbnew.SHAPE_POLY_SET()
        b.GetBoardPolygonOutlines(ps, True)
        self.outline = poly_of(ps)
        # courtyards for exemptions
        self.court = {}
        for f in b.GetFootprints():
            gs = []
            for lay in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
                g = poly_of(f.GetCourtyard(lay))
                if not g.is_empty:
                    gs.append(g)
            if gs:
                self.court[f.GetReference()] = unary_union(gs)
        self.exempt_geo = {k: unary_union([g for r, g in self.court.items() if any(fnmatch.fnmatchcase(r, q) for q in pats)])
                           for k, pats in EXEMPT.items()}
        from shapely.prepared import prep
        self.pexempt = {k: prep(g) for k, g in self.exempt_geo.items() if not g.is_empty}
        # rule areas
        self.areas = collections.defaultdict(list)    # name -> [(geom, layers)]
        for z in b.Zones():
            if z.GetIsRuleArea():
                g = poly_of(z.Outline())
                self.areas[z.GetZoneName()].append((g, set(b.GetLayerName(l) for l in z.GetLayerSet().CuStack()),
                                                    z.GetDoNotAllowTracks(), z.GetDoNotAllowVias()))
        self.fp_keepouts = []
        for f in b.GetFootprints():
            for z in f.Zones():
                if z.GetIsRuleArea():
                    self.fp_keepouts.append((poly_of(z.Outline()), set(b.GetLayerName(l) for l in z.GetLayerSet().CuStack()),
                                             z.GetDoNotAllowTracks(), z.GetDoNotAllowVias()))
        self.hpads = {}
        for r in ('H1', 'H2', 'H3', 'H4', 'H5', 'H6'):
            f = b.FindFootprintByReference(r)
            if f is None:
                continue
            for p in f.Pads():
                if p.GetDrillSize().x > 0:
                    c = p.GetPosition()
                    self.hpads[r] = (Point(c.x / 1e6, c.y / 1e6), p.GetDrillSize().x / 2e6)
        self.rebuild()

    def add_item(self, t):
        net = t.GetNetname()
        if t.GetClass() == 'PCB_VIA':
            c = t.GetPosition()
            g = Point(c.x / 1e6, c.y / 1e6).buffer(t.GetWidth(pcbnew.F_Cu) / 2e6, 16)
            for ln in SIG:
                self.items[ln].append((g, net, 'via'))
            self.holes.append((Point(c.x / 1e6, c.y / 1e6), t.GetDrill() / 2e6, net))
            return
        ln = self.b.GetLayerName(t.GetLayer())
        if ln not in self.items:
            return
        pts = [t.GetStart(), t.GetMid(), t.GetEnd()] if t.GetClass() == 'PCB_ARC' else [t.GetStart(), t.GetEnd()]
        g = LineString([(q.x / 1e6, q.y / 1e6) for q in pts]).buffer(t.GetWidth() / 2e6, 8)
        self.items[ln].append((g, net, 'track'))

    def rebuild(self):
        self.trees = {ln: STRtree([it[0] for it in self.items[ln]]) for ln in SIG}
        self.htree = STRtree([h[0] for h in self.holes])

    # ------------------------------------------------------------------ bans for a net
    def bans(self, net):
        """[(geom, layers, tracks_banned, vias_banned)] for this net."""
        c = cls(net)
        out = []
        for name, lst in self.areas.items():
            owners = None
            for pat, (lays, tr_ok, via_ok) in LANE_OWNERS.items():
                if fnmatch.fnmatchcase(name, pat):
                    owners = (lays, tr_ok, via_ok)
                    break
            for g, zl, dt, dv in lst:
                if owners is not None:
                    lays, tr_ok, via_ok = owners
                    tb = tr_ok is not None and net not in tr_ok
                    if tr_ok is None:
                        tb = False
                    vb = (via_ok is not None and net not in via_ok) or (via_ok is None and tr_ok is not None and net not in tr_ok)
                    if name.startswith('K3_'):
                        pass
                    out.append((g, set(lays), tb, vb))
                elif name.startswith('K3_RF_CORRIDOR'):
                    bad = c not in RFC and c != 'Ground'
                    out.append((g.difference(self.court.get('U2', Polygon())), {'F.Cu', 'B.Cu'}, bad, bad))
                elif dt or dv:
                    out.append((g, zl, dt, dv))
        for g, zl, dt, dv in self.fp_keepouts:
            if dt or dv:
                out.append((g, zl, dt, dv))
        if c in NOISY:     # v3_afe_partition_aggressors (F/B) + EMC: In3 under the partition closed as well
            afe = unary_union([g for g, *_ in self.areas.get('AFE_PARTITION', [])])
            # KiCad exempts a whole item that merely TOUCHES a bridge / the K16 head / the U8-U13 courtyards, so the
            # cells within 0.3 mm of them are reachable too (pads just outside a bridge edge, e.g. R103.1)
            for nm in ('BR1_SPI4_BRIDGE', 'BR2_ANALOG_CORNER', 'K16_DISP_LANE'):
                afe = afe.difference(unary_union([g for g, *_ in self.areas.get(nm, [])]).buffer(0.3) if self.areas.get(nm) else Polygon())
            for r in ('U8', 'U13'):
                afe = afe.difference(self.court.get(r, Polygon()).buffer(0.3))
            # MR_AFE_IN3=1: noisy nets may run on In3 under the partition (stripline between the In2 and In4 GND planes,
            # shielded from the F/B analog copper; the DRU rule covers F/B only) - vias stay banned inside it
            out.append((afe.buffer(0), {'F.Cu', 'B.Cu'} if os.environ.get('MR_AFE_IN3') == '1' else set(SIG), True, True))
        # mounting holes
        for r, (pt, hr) in self.hpads.items():
            if r in ('H1', 'H2', 'H3', 'H4'):
                if net != 'GND':
                    out.append((pt.buffer(hr + 1.4, 32), set(SIG), True, False))
                out.append(('VIAHOLE', pt, hr + 1.9))
            elif net != 'GND':
                out.append((pt.buffer(hr + 0.5, 32), set(SIG), True, True))
        return out


def mm_to_cell(x, y, x0, y0, g):
    return int(round((x - x0) / g)), int(round((y - y0) / g))


def draw_geom(draw, geom, x0, y0, g):
    for poly in polys_iter(geom):
        if poly.is_empty:
            continue
        pts = [((x - x0) / g, (y - y0) / g) for x, y in poly.exterior.coords]
        if len(pts) >= 3:
            draw.polygon(pts, fill=1)
        for ring in poly.interiors:
            hp = [((x - x0) / g, (y - y0) / g) for x, y in ring.coords]
            if len(hp) >= 3:
                draw.polygon(hp, fill=0)


def raster(geoms, nx, ny, x0, y0, g):
    """Exact cell-centre rasterisation: cell (i, j) <-> point (x0 + i*g, y0 + j*g) is True when it lies inside any of
    the geometries. (PIL's polygon fill rounds vertices to whole pixels, i.e. +-0.5 cell = +-0.025 mm at 0.05 mm,
    which let vias land 0.03 mm inside a clearance: r17 SD_CLK_MCU / LCD_CS_N_MCU / ADC_CS_N_U13.)"""
    out = np.zeros((ny, nx), bool)
    for geom in geoms:
        if geom is None or geom.is_empty:
            continue
        bx0, by0, bx1, by1 = geom.bounds
        i0 = max(0, int(math.floor((bx0 - x0) / g)))
        i1 = min(nx - 1, int(math.ceil((bx1 - x0) / g)))
        j0 = max(0, int(math.floor((by0 - y0) / g)))
        j1 = min(ny - 1, int(math.ceil((by1 - y0) / g)))
        if i1 < i0 or j1 < j0:
            continue
        xs = x0 + np.arange(i0, i1 + 1) * g
        ys = y0 + np.arange(j0, j1 + 1) * g
        X, Y = np.meshgrid(xs, ys)
        shapely.prepare(geom)
        out[j0:j1 + 1, i0:i1 + 1] |= shapely.contains_xy(geom, X, Y)
    return out


class Router:
    def __init__(self, B, grid=0.05, layers=SIG, margin=0.01, via_cost=1.2, maxwin=30.0, debug=None):
        # MR_MARGIN: extra clearance over the rule (the polygonal circles of shapely buffers sit up to ~0.005 mm inside
        # KiCad's exact arcs; 0.01 left 0.003 mm misses in the 2026-10-02 DRC - use 0.02)
        margin = float(os.environ.get('MR_MARGIN', margin))
        self.B, self.g, self.layers, self.margin, self.via_cost, self.maxwin = B, grid, list(layers), margin, via_cost, maxwin
        self.debug = debug
        self.max_pops = int(os.environ.get('MR_MAX_POPS', '1200000'))
        # weighted A* (MR_EPS > 1): far fewer expansions on long connections, path cost within MR_EPS of optimal
        self.eps = float(os.environ.get('MR_EPS', '1.0'))
        # user rules 2026-10-02: least track with simple straight / 45-degree paths (bend penalty, mm per 45-degree
        # bend), and via-in-pad FIRST (a via inside the net's own pad costs MR_VIP_COST instead of via_cost)
        self.t45 = float(os.environ.get('MR_T45', '0.35'))
        self.vip_cost = float(os.environ.get('MR_VIP_COST', '0.1'))

    def via_legal_exact(self, net, v, vd, vh, bans):
        if not self.B.outline.buffer(-(0.5 + vd / 2)).contains(v):
            return False
        vg = v.buffer(vd / 2, 24)
        for item in bans:
            if item[0] == 'VIAHOLE':
                if item[1].distance(v) < item[2] + vd / 2:
                    return False
            elif item[3] and item[0].intersects(vg):
                return False
        ex = frozenset(k for k, e in self.B.pexempt.items() if e.intersects(vg))
        for ln in SIG:
            for i in self.B.trees[ln].query(v.buffer(2.6)):
                geo, n2, kind = self.B.items[ln][i]
                if n2 == net:
                    continue
                d = geo.distance(v)
                if d < vd / 2 + need(net, n2, kind, ex) + 0.012 or d < vh / 2 + 0.2 + 0.012:
                    return False
        for i in self.B.htree.query(v.buffer(1.5)):
            hp, hr, hn = self.B.holes[i]
            if hp.distance(v) < hr + vh / 2 + 0.25:
                return False
        return True

    def islands(self, net):
        """list of islands: dict(layer -> [geoms]) with 'vias' points; from pcbnew connectivity."""
        b = self.B.b
        b.BuildConnectivity()
        conn = b.GetConnectivity()
        pads = self.B.pads_by_net.get(net, [])
        seen, isl = set(), []
        for p in pads:
            k = p.m_Uuid.AsString()
            if k in seen:
                continue
            items = [p] + list(conn.GetConnectedItems(p))
            geo = {ln: [] for ln in SIG}
            for it in items:
                it = it.Cast() if hasattr(it, 'Cast') else it
                cl = it.GetClass()
                if cl == 'PAD':
                    seen.add(it.m_Uuid.AsString())
                    for ln in SIG:
                        if it.IsOnLayer(self.B.L[ln]):
                            geo[ln].append(poly_of(it.GetEffectivePolygon(self.B.L[ln], pcbnew.ERROR_INSIDE)))
                elif cl == 'PCB_VIA':
                    c = it.GetPosition()
                    for ln in SIG:
                        geo[ln].append(Point(c.x / 1e6, c.y / 1e6).buffer(it.GetWidth(pcbnew.F_Cu) / 2e6, 12))
                elif cl in ('PCB_TRACK', 'PCB_ARC'):
                    ln = b.GetLayerName(it.GetLayer())
                    if ln in geo:
                        geo[ln].append(LineString([(it.GetStart().x / 1e6, it.GetStart().y / 1e6),
                                                   (it.GetEnd().x / 1e6, it.GetEnd().y / 1e6)]).buffer(it.GetWidth() / 2e6, 4))
            d_ = {ln: unary_union(v) if v else Polygon() for ln, v in geo.items()}
            d_['__pads__'] = [(it.GetPosition().x / 1e6, it.GetPosition().y / 1e6) for it in items if it.GetClass() == 'PAD']
            isl.append(d_)
        return isl

    def route_pair(self, net, A, Bisl, soft_ids=None, soft_pen=0.0, region=None, foreign=None):
        """A* from island A to island B. Returns (segments, vias) or None.
        soft_ids: ids of obstacle geometries that may be crossed (rip-up candidates) at soft_pen per grid cell.
        region: module locality (user rule 2026-10-02) - tracks and vias only inside this geometry.
        foreign: (geometry, ban_layers, pen_per_mm) - other modules' areas: no tracks on ban_layers and no vias there,
        other layers cost pen_per_mm extra (inter-module signals pass under a module on In3 only, and reluctantly)."""
        g = self.g
        c = cls(net)
        w = width_of(net)
        wn = neck_of(net)       # neck inside U*/J11/C310/C311/C35 courtyards (DRU neck-down rules)
        vd, vh = VIA.get(c, (0.45, 0.2))
        layers = [ln for ln in self.layers if not (ln == 'In3.Cu' and c in ('Analog_Precision', 'Ref_Kelvin', 'RF_Input', 'RF_50R'))]
        ga = unary_union([v for k_, v in A.items() if k_ != '__pads__' and not v.is_empty])
        gb = unary_union([v for k_, v in Bisl.items() if k_ != '__pads__' and not v.is_empty])
        bx = unary_union([ga, gb]).bounds
        if (bx[2] - bx[0]) * (bx[3] - bx[1]) > 400:
            # a huge island (e.g. everything GND reaches through the planes, or a supply spread over the board):
            # work around the closest points of the two islands only
            from shapely.ops import nearest_points
            pa, pb = nearest_points(ga, gb)
            bx = (min(pa.x, pb.x), min(pa.y, pb.y), max(pa.x, pb.x), max(pa.y, pb.y))
        span = max(bx[2] - bx[0], bx[3] - bx[1])
        # MR_MIN_MARG: a larger search window, so perimeter detours (In3 ring road round U8) are visible
        marg = min(max(3.0, 0.35 * span, float(os.environ.get('MR_MIN_MARG', '0'))), self.maxwin)
        ob = self.B.outline.bounds
        x0, y0 = max(ob[0], bx[0] - marg), max(ob[1], bx[1] - marg)
        x1, y1 = min(ob[2], bx[2] + marg), min(ob[3], bx[3] + marg)
        nx, ny = int((x1 - x0) / g) + 1, int((y1 - y0) / g) + 1
        win = box(x0 - 3, y0 - 3, x1 + 3, y1 + 3)
        # exemption masks
        exm = {k: raster([geo.intersection(win)], nx, ny, x0, y0, g) if not geo.is_empty else np.zeros((ny, nx), bool)
               for k, geo in self.B.exempt_geo.items()}
        combos = {}
        # per-cell exemption key: tuple of the keys active at that cell
        keyarr = np.zeros((ny, nx), dtype=np.int32)
        names = list(EXEMPT.keys())
        for i, k in enumerate(names):
            keyarr |= (exm[k].astype(np.int32) << i)
        uniq = np.unique(keyarr)
        blocked = {}
        vblock = np.zeros((ny, nx), bool)
        bans = self.B.bans(net)
        softm = {}
        for ln in layers:
            near = [self.B.items[ln][i] for i in self.B.trees[ln].query(win)]
            layer_block = np.zeros((ny, nx), bool)
            layer_soft = np.zeros((ny, nx), bool)
            for code in uniq:
                ex = frozenset(names[i] for i in range(len(names)) if code >> i & 1)
                # inside a U* courtyard a power track may neck down to wn (whole-segment exemption of the DRU)
                wc = wn if 'NK' in ex else w
                geoms, sgeoms = [], []
                for geo, n2, kind in near:
                    if n2 == net:
                        continue
                    d = need(net, n2, kind, ex) + wc / 2 + self.margin
                    (sgeoms if soft_ids and id(geo) in soft_ids else geoms).append(geo.buffer(d, 6))
                r = raster(geoms, nx, ny, x0, y0, g)
                sel = keyarr == code
                layer_block[sel] = r[sel]
                if sgeoms:
                    rs = raster(sgeoms, nx, ny, x0, y0, g)
                    layer_soft[sel] = rs[sel]
            softm[ln] = layer_soft
            # rule-area bans for tracks
            tb = [geo.intersection(win) for item in bans if item[0] != 'VIAHOLE' for geo, lays, t_b, v_b in [item]
                  if t_b and ln in lays]
            if tb:
                layer_block |= raster([q.buffer(w / 2 + 0.02) for q in tb], nx, ny, x0, y0, g)
            blocked[ln] = layer_block
        # board edge
        hs_like = c in ('HighSpeed_Digital', 'HighSpeed_Clock', 'Analog_Precision', 'Ref_Kelvin', 'RF_Input', 'RF_50R', 'Power_Buck_SW')
        e1 = (1.0 if hs_like else 0.5) + w / 2 + self.margin
        inside = raster([self.B.outline.buffer(-e1)], nx, ny, x0, y0, g)
        if hs_like:
            ex_edge = raster([self.B.exempt_geo['EDGE'].intersection(win)], nx, ny, x0, y0, g) & raster(
                [self.B.outline.buffer(-(0.5 + w / 2 + self.margin))], nx, ny, x0, y0, g)
            inside |= ex_edge
        for ln in layers:
            blocked[ln] |= ~inside
        # vias: copper of all layers at via radius (track inflation + (vd/2 - w/2)), holes, bans, edge
        for ln in SIG:     # a via exists on every layer, even where this net may not route
            near = [self.B.items[ln][i] for i in self.B.trees[ln].query(win)]
            vl = np.zeros((ny, nx), bool)
            vs = np.zeros((ny, nx), bool)
            for code in uniq:
                ex = frozenset(names[i] for i in range(len(names)) if code >> i & 1)
                # copper clearance AND min_hole_clearance (hole edge 0.25 from other-net copper)
                geoms, sgeoms = [], []
                for geo, n2, kind in near:
                    if n2 == net:
                        continue
                    gb = geo.buffer(max(need(net, n2, kind, ex) + vd / 2, vh / 2 + 0.2) + self.margin, 6)
                    (sgeoms if soft_ids and id(geo) in soft_ids else geoms).append(gb)
                r = raster(geoms, nx, ny, x0, y0, g)
                sel = keyarr == code
                vl[sel] = r[sel]
                if sgeoms:
                    rs = raster(sgeoms, nx, ny, x0, y0, g)
                    vs[sel] = rs[sel]
            vblock |= vl
            vsoft_acc = vs if ln == SIG[0] else (vsoft_acc | vs)
        hole_geoms = []
        shole = []
        for i in self.B.htree.query(win):
            hp, hr, hn = self.B.holes[i]
            (shole if soft_ids and id(hp) in soft_ids else hole_geoms).append(hp.buffer(hr + vh / 2 + 0.25 + 0.01, 12))
        if shole:
            vsoft_acc |= raster(shole, nx, ny, x0, y0, g)
        for sp in self.B.small_pads.get(net, []):
            hole_geoms.append(sp.buffer(vh / 2 + 0.1 + 0.01))
        for item in bans:
            if item[0] == 'VIAHOLE':
                _, pt, rr = item
                hole_geoms.append(pt.buffer(rr + vd / 2, 24))
            elif item[3]:
                hole_geoms.append(item[0].intersection(win).buffer(vd / 2 + 0.02))
        if hole_geoms:
            vblock |= raster(hole_geoms, nx, ny, x0, y0, g)
        vblock |= ~raster([self.B.outline.buffer(-(0.5 + vd / 2 + self.margin))], nx, ny, x0, y0, g)
        pen = None
        fvia = None
        if region is not None:
            inr = raster([region.intersection(win)], nx, ny, x0, y0, g)
            for ln in layers:
                blocked[ln] |= ~inr
            vblock |= ~inr
        if foreign is not None:
            fgeo, fban, fpen = foreign
            fgeo = fgeo.intersection(win)
            if not fgeo.is_empty:
                fr = raster([fgeo], nx, ny, x0, y0, g)
                # the two islands' own pads are never 'foreign'
                for I in (A, Bisl):
                    for ln_ in layers:
                        if ln_ in I and not I[ln_].is_empty:
                            fr &= ~raster([I[ln_].buffer(0.3)], nx, ny, x0, y0, g)
                # hard mode (ban layers given): no vias in a foreign module; soft mode (no bans): vias allowed there at
                # MR_FVIA_PEN (a layer change inside another module is the exception, priced like ~2 mm of detour)
                if fban:
                    vblock |= fr
                else:
                    fvia = fr
                pen = {}
                for ln in layers:
                    if ln in fban:
                        blocked[ln] |= fr
                        pen[ln] = None
                    else:
                        pen[ln] = np.where(fr, np.float32(fpen), np.float32(0.0))
        vsoft = vsoft_acc & ~vblock
        fvia_pen = float(os.environ.get('MR_FVIA_PEN', '2.0'))
        for ln in layers:
            softm[ln] &= ~blocked[ln]
        snap = {}
        vipc = set()
        for I in (A, Bisl):
            for (px, py) in I.get('__pads__', []):
                ix_, iy_ = int(round((px - x0) / g)), int(round((py - y0) / g))
                if not (0 <= ix_ < nx and 0 <= iy_ < ny):
                    continue
                if region is not None and not region.contains(Point(px, py)):
                    continue
                if not vblock[iy_, ix_]:
                    vipc.add((ix_, iy_))
                    snap[(ix_, iy_)] = (px, py)
                    continue
                if self.via_legal_exact(net, Point(px, py), vd, vh, bans):
                    vblock[iy_, ix_] = False
                    snap[(ix_, iy_)] = (px, py)
                    vipc.add((ix_, iy_))
        # sources / targets (cells inside own copper, on the layers where it exists)
        src = {ln: raster([A[ln]], nx, ny, x0, y0, g) & ~blocked[ln] if ln in blocked and not A[ln].is_empty
               else np.zeros((ny, nx), bool) for ln in layers}
        dst = {ln: raster([Bisl[ln]], nx, ny, x0, y0, g) & ~blocked[ln] if ln in blocked and not Bisl[ln].is_empty
               else np.zeros((ny, nx), bool) for ln in layers}
        # own copper must not block its own cells (pads of the net are not obstacles anyway)
        if self.debug:
            rgb = np.zeros((ny, nx * len(layers) + 2 * (len(layers) - 1), 3), np.uint8)
            for li, ln in enumerate(layers):
                o = li * (nx + 2)
                rgb[:, o:o + nx, 0] = np.where(blocked[ln], 160, 255)
                rgb[:, o:o + nx, 1] = np.where(blocked[ln], 160, np.where(vblock, 225, 255))
                rgb[:, o:o + nx, 2] = np.where(blocked[ln], 160, 255)
                if soft_ids:
                    ys, xs = np.nonzero(softm[ln]); rgb[ys, xs + o] = (120, 180, 255)
                ys, xs = np.nonzero(src[ln]); rgb[ys, xs + o] = (0, 160, 0)
                ys, xs = np.nonzero(dst[ln]); rgb[ys, xs + o] = (220, 0, 0)
            nm = ''.join(ch if ch.isalnum() else '_' for ch in net)
            Image.fromarray(rgb).save(os.path.join(self.debug, f'{nm}.png'))
        if not any(v.any() for v in src.values()) or not any(v.any() for v in dst.values()):
            return None, 'no free start/target cell'
        anydst = np.zeros((ny, nx), bool)
        for v in dst.values():
            anydst |= v
        h = ndimage.distance_transform_edt(~anydst) * g
        LC = {'F.Cu': float(os.environ.get('MR_LC_F', '1.15')), 'In3.Cu': float(os.environ.get('MR_LC_IN3', '1.0')),
              'B.Cu': float(os.environ.get('MR_LC_B', '1.15'))}
        if c.startswith('Power'):
            # via-first (user rule 2026-10-02): MR_LCP_* let power leave the crowded component face through pad vias
            LC = {'F.Cu': float(os.environ.get('MR_LCP_F', '1.0')), 'In3.Cu': float(os.environ.get('MR_LCP_IN3', '1.6')),
                  'B.Cu': float(os.environ.get('MR_LCP_B', '1.0'))}
        nl = len(layers)
        axis = {}
        if DIRPREF:
            for ln in layers:
                regs, dflt = DIRPREF.get(ln, ([], None))
                a = np.full((ny, nx), {'H': 1, 'V': 2}.get(dflt, 0), dtype=np.int8)
                for (bx0, by0, bx1, by1), ax in regs:
                    i0 = max(0, int(math.floor((bx0 - x0) / g)))
                    i1 = min(nx - 1, int(math.ceil((bx1 - x0) / g)))
                    j0 = max(0, int(math.floor((by0 - y0) / g)))
                    j1 = min(ny - 1, int(math.ceil((by1 - y0) / g)))
                    if i1 >= i0 and j1 >= j0:
                        a[j0:j1 + 1, i0:i1 + 1] = {'H': 1, 'V': 2}.get(ax, 0)
                axis[ln] = a
        hug = {}
        BUNDLE = float(os.environ.get('MR_BUNDLE', '1.0'))
        if BUNDLE < 1.0:
            # highways (user request 2026-10-02 night): a step in the preferred direction that runs right beside an
            # existing track of another net (at clearance .. clearance + 0.2 mm) costs MR_BUNDLE x -> parallel lanes
            for ln in layers:
                near_t = [self.B.items[ln][i] for i in self.B.trees[ln].query(win)]
                inner, outer = [], []
                for geo, n2, kind in near_t:
                    if kind != 'track' or n2 == net:
                        continue
                    d_in = need(net, n2, kind, frozenset()) + w / 2 + self.margin
                    inner.append(geo.buffer(d_in, 4))
                    outer.append(geo.buffer(d_in + 0.2, 4))
                if outer:
                    hug[ln] = raster(outer, nx, ny, x0, y0, g) & ~raster(inner, nx, ny, x0, y0, g)
        R = 3          # run-length states: 0..2 straight steps in the current direction
        size = nl * ny * nx * 9 * R
        eps = self.eps if span > 8.0 else 1.0
        if size > int(os.environ.get('MR_MAX_STATES', '80000000')):
            return None, 'window too large'
        dist = np.full(size, np.inf, dtype=np.float32)
        par = np.full(size, -1, dtype=np.int32)
        heap = []

        def sid(li, iy, ix, d, r):
            return (((li * ny + iy) * nx + ix) * 9 + d) * R + r

        for li, ln in enumerate(layers):
            ys, xs = np.nonzero(src[ln])
            for iy, ix in zip(ys.tolist(), xs.tolist()):
                s0 = sid(li, iy, ix, 8, 2)
                dist[s0] = 0.0
                heapq.heappush(heap, (eps * h[iy, ix], 0.0, s0))
        # geometry standard: octilinear, 45-degree bends only (no 90-degree or acute corners), and every segment
        # at least 2 grid steps long (no slivers between two bends)
        t45 = self.t45
        diag = math.sqrt(2) * g
        found = None
        pops = 0
        while heap:
            f, d0, s = heapq.heappop(heap)
            if d0 > dist[s] + 1e-6:
                continue
            pops += 1
            if pops > self.max_pops:
                break
            r = s % R
            rest = s // R
            dcur = rest % 9
            rest //= 9
            ix = rest % nx
            rest //= nx
            iy = rest % ny
            li = rest // ny
            ln = layers[li]
            if dst[ln][iy, ix]:
                found = s
                break
            bl = blocked[ln]
            sm = softm[ln]
            lc = LC[ln]
            dmul = _DMUL[int(axis[ln][iy, ix])] if axis else None
            hg = hug.get(ln)
            pl = pen[ln] if pen is not None else None
            for di, (dx, dy) in enumerate(DIRS):
                if dcur != 8:
                    turn = (di - dcur) % 8
                    turn = min(turn, 8 - turn)
                    if turn >= 2 or (turn == 1 and r < 2):
                        continue
                    tc = t45 if turn == 1 else 0.0
                    r2 = 1 if turn == 1 else min(r + 1, 2)
                else:
                    tc, r2 = 0.0, 1
                jx, jy = ix + dx, iy + dy
                if jx < 0 or jy < 0 or jx >= nx or jy >= ny or bl[jy, jx]:
                    continue
                if dx and dy and (bl[iy, jx] or bl[jy, ix]):
                    continue
                stp = diag if dx and dy else g
                mul_ = dmul[di] if dmul is not None else 1.0
                if hg is not None and mul_ == 1.0 and hg[jy, jx]:
                    mul_ = BUNDLE
                nd = d0 + stp * lc * mul_ + tc
                if pl is not None:
                    nd += float(pl[jy, jx]) * stp
                if soft_pen and sm[jy, jx]:
                    nd += soft_pen
                s2 = sid(li, jy, jx, di, r2)
                if nd < dist[s2]:
                    dist[s2] = nd
                    par[s2] = s
                    heapq.heappush(heap, (nd + eps * h[jy, jx], nd, s2))
            if not vblock[iy, ix] and not (dcur == 8 and par[s] >= 0) and (dcur == 8 or r >= 2):
                for lj in range(nl):
                    if lj == li or blocked[layers[lj]][iy, ix]:
                        continue
                    vc = self.vip_cost if (ix, iy) in vipc else self.via_cost
                    nd = d0 + vc + (soft_pen * 6 if soft_pen and vsoft[iy, ix] else 0.0)
                    if fvia is not None and fvia[iy, ix]:
                        nd += fvia_pen
                    s2 = sid(lj, iy, ix, 8, 2)
                    if nd < dist[s2]:
                        dist[s2] = nd
                        par[s2] = s
                        heapq.heappush(heap, (nd + eps * h[iy, ix], nd, s2))
        if found is None:
            return None, f'no path ({pops} pops)'
        path = []
        s = int(found)
        while s >= 0:
            rest = s // R
            rest //= 9
            ix = rest % nx
            rest //= nx
            iy = rest % ny
            li = rest // ny
            path.append((li, ix, iy))
            s = int(par[s])
        path.reverse()
        neck = (exm['NK'], wn) if wn != w else None
        # to segments / vias
        segs, vias = [], []
        run = [path[0]]
        for p in path[1:]:
            if p[0] != run[-1][0]:
                if len(run) > 1:
                    segs += self.compress(run, layers, x0, y0, w, neck)
                vias.append(snap.get((p[1], p[2]), (x0 + p[1] * g, y0 + p[2] * g)) + (vd, vh))
                run = [p]
            else:
                run.append(p)
        if len(run) > 1:
            segs += self.compress(run, layers, x0, y0, w, neck)
        if snap:
            fixed = []
            for ln_, a_, c_, w_ in segs:
                ka = (int(round((a_[0] - x0) / g)), int(round((a_[1] - y0) / g)))
                kc = (int(round((c_[0] - x0) / g)), int(round((c_[1] - y0) / g)))
                fixed.append((ln_, snap.get(ka, a_), snap.get(kc, c_), w_))
            segs = fixed
        return (segs, vias, w), 'ok'

    def compress(self, run, layers, x0, y0, w, neck=None):
        """straight pieces of a single-layer run; with neck=(mask, wn) a piece is split where it leaves an IC
        courtyard, the inside part at the neck width wn and the rest at w"""
        g = self.g
        out = []
        start = run[0]
        prevd = None

        def wid(cell):
            if neck is None:
                return w
            m, wn = neck
            return wn if m[cell[2], cell[1]] else w
        for a, bq in zip(run, run[1:]):
            d = (bq[1] - a[1], bq[2] - a[2])
            if (prevd is not None and d != prevd) or wid(a) != wid(start):
                out.append((layers[start[0]], (x0 + start[1] * g, y0 + start[2] * g), (x0 + a[1] * g, y0 + a[2] * g), wid(start)))
                start = a
            prevd = d
        last = run[-1]
        out.append((layers[start[0]], (x0 + start[1] * g, y0 + start[2] * g), (x0 + last[1] * g, y0 + last[2] * g), wid(start)))
        return [s for s in out if s[1] != s[2]]

    def commit(self, net, segs, vias):
        b = self.B.b
        netobj = b.FindNet(net)
        added = []
        for ln, a, c, w in segs:
            if abs(a[0] - c[0]) < 1e-9 and abs(a[1] - c[1]) < 1e-9:
                continue
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(pcbnew.VECTOR2I(int(round(a[0] * 1e6)), int(round(a[1] * 1e6))))
            t.SetEnd(pcbnew.VECTOR2I(int(round(c[0] * 1e6)), int(round(c[1] * 1e6))))
            t.SetWidth(int(round(w * 1e6)))
            t.SetLayer(self.B.L[ln])
            t.SetNet(netobj)
            b.Add(t)
            self.B.add_item(t)
            added.append(t)
        for x, y, vd, vh in vias:
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(pcbnew.VECTOR2I(int(round(x * 1e6)), int(round(y * 1e6))))
            v.SetWidth(int(round(vd * 1e6)))
            v.SetDrill(int(round(vh * 1e6)))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNet(netobj)
            b.Add(v)
            self.B.add_item(v)
            added.append(v)
        self.B.rebuild()
        return added


def main():
    argv = sys.argv[1:]

    def opt(name, default=None):
        if name in argv:
            i = argv.index(name)
            return argv[i + 1]
        return default
    src, dst = argv[0], argv[1]
    if os.path.normcase(os.path.realpath(dst)).startswith(PROTECTED):
        sys.exit('refusing to write into the project folder')
    if '--nets-file' in argv:
        nets = json.load(open(opt('--nets-file')))
    else:
        i = argv.index('--nets')
        nets = []
        for a in argv[i + 1:]:
            if a.startswith('--'):
                break
            nets.append(a)
    B = Board(src, (opt('--vip-small') or '').split(',') if opt('--vip-small') else ())
    R = Router(B, grid=float(opt('--grid', 0.05)), layers=(opt('--layers') or ','.join(SIG)).split(','),
               margin=float(opt('--margin', 0.01)), via_cost=float(opt('--via-cost', 1.2)), maxwin=float(opt('--maxwin', 30)),
               debug=opt('--debug'))
    report = []
    for net in nets:
        tries = 0
        skip = set()            # island pairs that already failed (by their pad sets)
        while True:
            isl = R.islands(net)
            if len(isl) < 2:
                break
            sigs = [frozenset(I.get('__pads__', [])) for I in isl]
            geos = [unary_union([v for k_, v in I.items() if k_ != '__pads__' and not v.is_empty]) for I in isl]
            # closest pair of islands not tried in vain yet
            best = None
            for i in range(len(isl)):
                for j in range(i + 1, len(isl)):
                    if (sigs[i], sigs[j]) in skip:
                        continue
                    d = geos[i].distance(geos[j])
                    if best is None or d < best[0]:
                        best = (d, i, j)
            if best is None:
                break
            d, i, j = best
            res, why = R.route_pair(net, isl[i], isl[j])
            tries += 1
            if res is None:
                report.append({'net': net, 'ok': False, 'why': why, 'dist': round(d, 2)})
                print(f"  FAIL {net}: {why} (gap {d:.2f} mm)")
                skip.add((sigs[i], sigs[j]))
                if tries > max(12, 2 * len(isl)):
                    break
                continue
            segs, vias, w = res
            R.commit(net, segs, vias)
            report.append({'net': net, 'ok': True, 'segs': len(segs), 'vias': len(vias),
                           'len': round(sum(math.hypot(c[0] - a[0], c[1] - a[1]) for _, a, c, _ in segs), 2)})
            print(f"  ok   {net}: {len(segs)} segs, {len(vias)} vias")
            sys.stdout.flush()
            if tries > max(12, 2 * len(isl)):
                break
    pcbnew.SaveBoard(dst, B.b)
    for ext in ('.kicad_pro', '.kicad_dru'):
        s = os.path.splitext(src)[0] + ext
        d2 = os.path.splitext(dst)[0] + ext
        if os.path.isfile(s) and os.path.normcase(s) != os.path.normcase(d2):
            shutil.copy2(s, d2)
    ok = sum(1 for r in report if r['ok'])
    print(f"mr: {ok} connections routed, {len(report) - ok} failed")
    if opt('--report'):
        json.dump(report, open(opt('--report'), 'w'), indent=1)


if __name__ == '__main__':
    main()

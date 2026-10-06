"""drcfix.py IN.kicad_pcb DRC.json OUT.kicad_pcb [--dry]
Mechanical fixes driven by a KiCad DRC report (kicad-cli pcb drc --format json, e.g. drcsum.py's drc_signoff.json):
  * a GND via / GND track that takes part in shorting_items, items_not_allowed, hole_clearance or clearance against
    another net's item is removed, with the GND stubs that only served it (gndvip.py re-adds plane vias legally);
  * via_diameter / hole_size violations of rule fab_via_window -> via resized to 0.50 / 0.30 (the rule's floor).
Everything else is listed for the router / placement tools. Items are matched by type + net + position (0.01 mm).
KiCad python, scratch copies only."""
import json
import math
import os
import re
import shutil
import sys

import pcbnew

argv = sys.argv[1:]
src, rep, dst = argv[0], argv[1], argv[2]
dry = '--dry' in argv
d = json.load(open(rep))
b = pcbnew.LoadBoard(src)
tracks = list(b.GetTracks())


def find(desc, pos):
    """board track/via matching a DRC item description like 'Via [GND] on F.Cu - B.Cu' at pos"""
    m = re.match(r'(Via|Track|Arc) \[(.*?)\]', desc)
    if not m:
        return None
    kind, net = m.group(1), m.group(2)
    x, y = pos['x'], pos['y']
    best = None
    for t in tracks:
        if t.GetNetname() != net:
            continue
        if kind == 'Via' and t.GetClass() == 'PCB_VIA':
            dd = math.hypot(t.GetPosition().x / 1e6 - x, t.GetPosition().y / 1e6 - y)
        elif kind != 'Via' and t.GetClass() != 'PCB_VIA':
            # DRC reports a track by one end or its centre
            a, c = t.GetStart(), t.GetEnd()
            pts = [(a.x / 1e6, a.y / 1e6), (c.x / 1e6, c.y / 1e6), ((a.x + c.x) / 2e6, (a.y + c.y) / 2e6)]
            dd = min(math.hypot(px - x, py - y) for px, py in pts)
        else:
            continue
        if dd < 0.011 and (best is None or dd < best[0]):
            best = (dd, t)
    return best[1] if best else None


kill = {}
resize = {}
rest = []
for v in d.get('violations', []):
    if v.get('severity') != 'error':
        continue
    typ = v.get('type')
    its = v.get('items', [])
    desc = v.get('description', '')
    if typ in ('via_diameter', 'hole_size') and 'fab_via_window' in desc and '--no-resize' not in argv:
        t = find(its[0]['description'], its[0]['pos'])
        if t is not None:
            resize[t.m_Uuid.AsString()] = t
            continue
    if typ in ('shorting_items', 'items_not_allowed', 'hole_clearance', 'clearance', 'solder_mask_bridge'):
        gnd = [i for i in its if re.match(r'(Via|Track|Arc) \[GND\]', i.get('description', ''))]
        if gnd and (len(its) == 1 or len(gnd) < len(its)):
            for i in gnd:
                t = find(i['description'], i['pos'])
                if t is not None:
                    kill[t.m_Uuid.AsString()] = t
            continue
    rest.append((typ, desc[:90], [(i.get('description', '')[:60], round(i['pos']['x'], 2), round(i['pos']['y'], 2)) for i in its]))
# a removed GND via takes the GND stub tracks ending on it (and only on it) along
for t in list(kill.values()):
    if t.GetClass() != 'PCB_VIA':
        continue
    p = t.GetPosition()
    for s in tracks:
        if s.GetClass() == 'PCB_VIA' or s.GetNetname() != 'GND':
            continue
        if s.GetStart() == p or s.GetEnd() == p:
            if s.GetLength() / 1e6 <= 1.0:
                kill[s.m_Uuid.AsString()] = s
print(f"drcfix: remove {len(kill)} GND items, resize {len(resize)} vias to 0.5/0.3; {len(rest)} errors left for other tools")
for k, t in kill.items():
    c = t.GetPosition() if t.GetClass() == 'PCB_VIA' else t.GetStart()
    print(f"   remove {t.GetClass()[4:]} GND at ({c.x / 1e6:.3f},{c.y / 1e6:.3f})")
for k, t in resize.items():
    print(f"   resize via {t.GetNetname().split('/')[-1]} at ({t.GetPosition().x / 1e6:.3f},{t.GetPosition().y / 1e6:.3f})")
for r in rest:
    print('   left:', r[0], '|', r[1], r[2])
if not dry:
    for t in resize.values():
        t.SetWidth(int(0.5e6))
        t.SetDrill(int(0.3e6))
    for t in kill.values():
        b.Remove(t)
    pcbnew.SaveBoard(dst, b)
    for ext in ('.kicad_pro', '.kicad_dru'):
        s_ = os.path.splitext(src)[0] + ext
        if os.path.isfile(s_):
            shutil.copy2(s_, os.path.splitext(dst)[0] + ext)
    print('saved', dst)

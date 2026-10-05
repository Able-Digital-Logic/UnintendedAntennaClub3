"""sync.py BOARD.kicad_pcb NETLIST.xml OUT.kicad_pcb [--place PLACE.json] [--delete REF,..] [--swap REF,..] [--dry-run]
Schematic -> board update without the GUI (KiCad's 'Update PCB from Schematic' / F8), on a scratch copy (2026-10-04).
NETLIST.xml = `kicad-cli sch export netlist --format kicadxml` of the project root schematic.

Matching: a board footprint belongs to a schematic component when its path (/sheet-uuid/symbol-uuid) matches; the
reference is the fallback. For every schematic component that is on the board (not exclude_from_board):
  - missing on the board: ADDED from its library footprint only if PLACE.json gives the pose
    {REF: {"x": .., "y": .., "rot": .., "side": "F"|"B"}}; otherwise reported as unresolved. Added parts get the symbol
    path, sheet name/file, reference, value, fields, DNP / BOM / position attributes and pad nets. Their silkscreen
    reference is hidden, as on the rest of this board (designators stay on the fab layer).
  - present: reference, value, fields, DNP and exclude-from-BOM attributes are synced, and pad nets are set from the
    netlist. A footprint-ID change is applied only when REF is listed in --swap (pose, nets and path kept); otherwise
    it is reported as unresolved.
Board footprints with no schematic component are deleted only when listed in --delete; otherwise unresolved.
Copper (tracks, vias, zones) is never touched. Tracks and vias left on nets that no longer exist in the netlist are
listed: re-net or delete them with pen.py. Library footprints come from the project fp-lib-table (${KIPRJMOD}) and
KiCad's stock footprint folder. Exit 1 when anything is unresolved (nothing written unless --force-partial).
KiCad python."""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

import pcbnew

argv = sys.argv[1:]


def opt(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


board_in, netlist, out = argv[0], argv[1], argv[2]
PLACE = json.load(open(opt('--place'), encoding='utf-8')) if opt('--place') else {}
DELETE = set(filter(None, (opt('--delete', '') or '').split(',')))
SWAP = set(filter(None, (opt('--swap', '') or '').split(',')))
DRY = '--dry-run' in argv
STOCK = r'C:/Program Files/KiCad/10.0/share/kicad/footprints'
SKIP_FIELDS = {'Sheetname', 'Sheetfile', 'ki_keywords', 'ki_fp_filters', 'ki_description', 'dnp', 'exclude_from_bom',
               'exclude_from_board', 'exclude_from_sim', 'exclude_from_pos_files', 'Reference', 'Value', 'Footprint',
               'Datasheet', 'Description'}

proj = os.path.dirname(os.path.abspath(board_in))
libmap = {}
fpt = os.path.join(proj, 'fp-lib-table')
if os.path.isfile(fpt):
    for nick, uri in re.findall(r'\(lib \(name "([^"]+)"\) \(type "[^"]+"\) \(uri "([^"]+)"', open(fpt, encoding='utf-8').read()):
        libmap[nick] = uri.replace('${KIPRJMOD}', proj)


def lib_path(nick):
    return libmap.get(nick) or os.path.join(STOCK, nick + '.pretty')


# ---- netlist
root = ET.parse(netlist).getroot()
comps = {}
for c in root.iter('comp'):
    ref = c.get('ref')
    props = {p.get('name'): (p.get('value') if p.get('value') is not None else '') for p in c.iter('property')}
    sp = c.find('sheetpath')
    ts = (c.findtext('tstamps') or '').split()
    comps[ref] = dict(ref=ref, value=c.findtext('value') or '', footprint=c.findtext('footprint') or '',
                      datasheet=c.findtext('datasheet') or '', description=c.findtext('description') or '',
                      props=props, path=(sp.get('tstamps') if sp is not None else '/') + (ts[0] if ts else ''),
                      sheetname=(sp.get('names') if sp is not None else '/'), sheetfile=props.get('Sheetfile', ''))
pin_net = {}
for n in root.iter('net'):
    for nd in n.iter('node'):
        pin_net[(nd.get('ref'), nd.get('pin'))] = n.get('name')

b = pcbnew.LoadBoard(board_in)
board_nets = {str(k): v for k, v in b.GetNetsByName().items()}


def board_net_name(name):
    """netlist name -> the board's spelling: inside KiCad's generated names 'Net-(...)' / 'unconnected-(...)' a '/'
    taken from a pin name is written '{slash}' on the board (e.g. Net-(U5-Trim{slash}NR))."""
    if name in board_nets:
        return name
    for pre in ('unconnected-(', 'Net-('):
        if name.startswith(pre):
            return pre + name[len(pre):].replace('/', '{slash}')
    return name


def get_net(name):
    nm = board_net_name(name)
    ni = b.FindNet(nm)
    if ni is None:
        ni = pcbnew.NETINFO_ITEM(b, nm)
        b.Add(ni)
        board_nets[nm] = ni
        log.append(f'  net + {nm}')
    return ni


log, unresolved = [], []
by_path = {f.GetPath().AsString(): f for f in b.GetFootprints()}
by_ref = {f.GetReference(): f for f in b.GetFootprints()}
matched = set()


def set_meta(f, c):
    """reference, value, fields, attributes, path and sheet from the schematic component; returns the changes."""
    ch = []
    if f.GetReference() != c['ref']:
        ch.append(f"ref {f.GetReference()} -> {c['ref']}")
        f.SetReference(c['ref'])
    if f.GetValue() != c['value']:
        ch.append(f"value {f.GetValue()!r} -> {c['value']!r}")
        f.SetValue(c['value'])
    for name, val in list(c['props'].items()) + [('Datasheet', c['datasheet']), ('Description', c['description'])]:
        if name in SKIP_FIELDS and name not in ('Datasheet', 'Description'):
            continue
        existed = f.HasField(name)
        cur = f.GetFieldText(name) if existed else None
        if cur != val:
            if cur is not None or val:
                ch.append(f"field {name}")
            f.SetField(name, val)
            if not existed:
                # a field created here must stay hidden, as KiCad's own Update PCB does; a new field is visible by
                # default and would print on the silkscreen (un-mirrored on B parts) - found 2026-10-04
                for fld in f.GetFields():
                    if fld.GetName() == name:
                        fld.SetVisible(False)
    dnp = 'dnp' in c['props']
    if f.IsDNP() != dnp:
        ch.append(f'dnp -> {dnp}')
        f.SetDNP(dnp)
    a = f.GetAttributes()
    want_bom = 'exclude_from_bom' in c['props']
    if bool(a & pcbnew.FP_EXCLUDE_FROM_BOM) != want_bom:
        a = (a | pcbnew.FP_EXCLUDE_FROM_BOM) if want_bom else (a & ~pcbnew.FP_EXCLUDE_FROM_BOM)
        ch.append(f'exclude_bom -> {want_bom}')
    f.SetAttributes(a)
    if f.GetPath().AsString() != c['path']:
        ch.append(f"path -> {c['path']}")
        f.SetPath(pcbnew.KIID_PATH(c['path']))
    if c['sheetname'] and f.GetSheetname() != c['sheetname']:
        f.SetSheetname(c['sheetname'])
    if c['sheetfile'] and f.GetSheetfile() != c['sheetfile']:
        f.SetSheetfile(c['sheetfile'])
    return ch


def set_nets(f, ref):
    ch = []
    for p in f.Pads():
        num = p.GetNumber()
        if not num:
            continue
        want = pin_net.get((ref, num))
        cur = p.GetNetname()
        if want is None:
            if cur:
                ch.append(f'pad {num}: {cur} -> (none)')
                p.SetNetCode(0)
            continue
        if cur != board_net_name(want):
            ch.append(f'pad {num}: {cur or "(none)"} -> {want}')
            p.SetNet(get_net(want))
    return ch


def load_fp(fpid):
    nick, name = fpid.split(':', 1)
    fp = pcbnew.FootprintLoad(lib_path(nick), name)
    if fp is None:
        raise RuntimeError(f'footprint {fpid} not found in {lib_path(nick)}')
    fp.SetFPIDAsString(fpid)
    return fp


def hide_silk_ref(f):
    r = f.Reference()
    if b.GetLayerName(r.GetLayer()).endswith('Silkscreen'):
        r.SetVisible(False)


for ref, c in sorted(comps.items()):
    if 'exclude_from_board' in c['props']:
        continue
    f = by_path.get(c['path']) or by_ref.get(ref)
    if f is None:
        pose = PLACE.get(ref)
        if not pose:
            unresolved.append(f'{ref}: on the schematic, not on the board (give its pose in --place)')
            continue
        if not c['footprint']:
            unresolved.append(f'{ref}: no footprint assigned')
            continue
        fp = load_fp(c['footprint'])
        b.Add(fp)
        if pose.get('side', 'F') == 'B':
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetPosition(pcbnew.VECTOR2I(int(round(pose['x'] * 1e6)), int(round(pose['y'] * 1e6))))
        fp.SetOrientationDegrees(pose.get('rot', 0))
        set_meta(fp, c)
        nets = set_nets(fp, ref)
        hide_silk_ref(fp)
        log.append(f"ADD {ref} {c['footprint']} at ({pose['x']}, {pose['y']}) rot {pose.get('rot', 0)} {pose.get('side', 'F')}; "
                   + '; '.join(nets))
        matched.add(ref)
        continue
    matched.add(f.GetReference())
    cur_fpid = f.GetFPID().GetUniStringLibId()
    if c['footprint'] and cur_fpid != c['footprint']:
        if ref in SWAP:
            fp = load_fp(c['footprint'])
            b.Add(fp)
            if f.IsFlipped():
                fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
            fp.SetPosition(f.GetPosition())
            fp.SetOrientation(f.GetOrientation())
            b.Remove(f)
            f.thisown = 0
            set_meta(fp, c)
            nets = set_nets(fp, ref)
            hide_silk_ref(fp)
            log.append(f'SWAP {ref} {cur_fpid} -> {c["footprint"]}; ' + '; '.join(nets))
            continue
        unresolved.append(f'{ref}: footprint {cur_fpid} on the board, {c["footprint"]} in the schematic (allow with --swap)')
        continue
    ch = set_meta(f, c) + set_nets(f, ref)
    if ch:
        log.append(f'UPD {ref}: ' + '; '.join(ch))

for f in list(b.GetFootprints()):
    ref = f.GetReference()
    c = comps.get(ref)
    if c is not None and 'exclude_from_board' not in c['props']:
        continue
    if any(cc['path'] == f.GetPath().AsString() for cc in comps.values()):
        continue
    if ref in DELETE:
        b.Remove(f)
        f.thisown = 0
        log.append(f'DEL {ref}')
    elif f.GetPath().AsString() in ('', '/') and ref.startswith(('H', 'MH', 'FID', 'LOGO', 'G')):
        continue  # board-only items (mounting holes, logos)
    else:
        unresolved.append(f'{ref}: on the board, not in the schematic (allow with --delete)')

# copper on nets that are no longer used by any pad
live = {p.GetNetname() for f in b.GetFootprints() for p in f.Pads()}
orphan = {}
for t in b.GetTracks():
    n = t.GetNetname()
    if n and n not in live:
        orphan[n] = orphan.get(n, 0) + 1
print('\n'.join(log) or 'no changes')
for n, k in sorted(orphan.items()):
    print(f'  ORPHAN COPPER: {k} tracks/vias on net {n} (no pad uses it any more)')
if unresolved:
    print('UNRESOLVED:\n  ' + '\n  '.join(unresolved))
if DRY:
    print('dry run: nothing written')
    sys.exit(1 if unresolved else 0)
if unresolved and '--force-partial' not in argv:
    sys.exit('not written: resolve the items above (or --force-partial)')
pcbnew.SaveBoard(out, b)
for ext in ('.kicad_pro', '.kicad_dru'):
    s = os.path.splitext(board_in)[0] + ext
    if os.path.isfile(s):
        import shutil
        shutil.copy2(s, os.path.splitext(out)[0] + ext)
print(f'sync -> {out}')

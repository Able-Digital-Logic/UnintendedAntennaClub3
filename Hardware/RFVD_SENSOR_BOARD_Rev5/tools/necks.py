"""necks.py BOARD.kicad_pcb [--max 1.0] [--csv OUT.csv]   (2026-10-04, critique P0-5 chain check)
Lists power "necks": runs of track narrower than the class minimum (Power_Battery 0.5, Power_Digital 0.3,
Power_Analog 0.25 mm). The DRU rules v11_neck_len_* cap each narrow SEGMENT at 1.0 mm. This tool adds the chain check
they cannot do: consecutive narrow segments of one net are joined at shared end points (on any layer, so a via
continues the chain) and their lengths are summed. A chain longer than --max is a neck to widen (P1-6).
Excluded as in the DRU: REGN, the PACK_RAW Kelvin sense track inside the J2 courtyard, VBAT_RTC, and the VBAT_PACK
feed inside the U303/C326 courtyards.
Exit 1 if any chain is over --max. KiCad python, read-only.
  python necks.py --selftest"""
import collections
import csv
import sys

LIMITS = (('Power_Battery', 0.5), ('Power_Digital', 0.3), ('Power_Analog', 0.25))


def class_limit(ncname):
    for name, lim in LIMITS:
        if name in ncname.split(','):
            return name, lim
    return None, None


def chains(segs, tol=0.01):
    """segs: list of dicts with net, a, b (mm tuples), length. Groups segments of one net that share an end point."""
    parent = list(range(len(segs)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    ends = collections.defaultdict(list)
    for i, s in enumerate(segs):
        for p in (s['a'], s['b']):
            ends[(s['net'], round(p[0] / tol), round(p[1] / tol))].append(i)
    for idx in ends.values():
        for j in idx[1:]:
            ri, rj = find(idx[0]), find(j)
            if ri != rj:
                parent[rj] = ri
    groups = collections.defaultdict(list)
    for i in range(len(segs)):
        groups[find(i)].append(segs[i])
    return list(groups.values())


def collect(board):
    import pcbnew
    mm = pcbnew.ToMM
    court = {}
    for ref in ('J2', 'U303', 'C326'):
        f = board.FindFootprintByReference(ref)
        if f is not None:
            court[ref] = f
    segs = []
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            continue
        cname, lim = class_limit(t.GetNetClassName())
        if not cname or mm(t.GetWidth()) >= lim - 1e-6:
            continue
        net = t.GetNetname()
        short = net.split('/')[-1]
        if short in ('REGN', 'VBAT_RTC'):
            continue
        mid = pcbnew.VECTOR2I((t.GetStart().x + t.GetEnd().x) // 2, (t.GetStart().y + t.GetEnd().y) // 2)

        def inside(ref):
            f = court.get(ref)
            if f is None:
                return False
            layer = pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd
            return f.GetCourtyard(layer).Contains(mid)
        if short == 'PACK_RAW' and inside('J2'):
            continue
        if short == 'VBAT_PACK' and (inside('U303') or inside('C326')):
            continue
        segs.append({'net': net, 'cls': cname, 'layer': board.GetLayerName(t.GetLayer()), 'w': round(mm(t.GetWidth()), 3),
                     'a': (mm(t.GetStart().x), mm(t.GetStart().y)), 'b': (mm(t.GetEnd().x), mm(t.GetEnd().y)),
                     'length': mm(t.GetLength())})
    return segs


def selftest():
    s = [{'net': 'A', 'a': (0, 0), 'b': (0.8, 0), 'length': 0.8}, {'net': 'A', 'a': (0.8, 0), 'b': (1.6, 0), 'length': 0.8},
         {'net': 'A', 'a': (5, 5), 'b': (5.5, 5), 'length': 0.5}, {'net': 'B', 'a': (1.6, 0), 'b': (2, 0), 'length': 0.4}]
    g = sorted((round(sum(x['length'] for x in c), 3), c[0]['net']) for c in chains(s))
    assert g == [(0.4, 'B'), (0.5, 'A'), (1.6, 'A')], g
    assert class_limit('Power_Digital,Default') == ('Power_Digital', 0.3) and class_limit('Default') == (None, None)
    print('necks selftest OK')


def main():
    argv = sys.argv[1:]
    if '--selftest' in argv:
        return selftest()
    import pcbnew
    mx = float(argv[argv.index('--max') + 1]) if '--max' in argv else 1.0
    out = argv[argv.index('--csv') + 1] if '--csv' in argv else None
    segs = collect(pcbnew.LoadBoard(argv[0]))
    rows = []
    for c in chains(segs):
        tot = sum(x['length'] for x in c)
        if tot > mx:
            xs = [p[0] for x in c for p in (x['a'], x['b'])]
            ys = [p[1] for x in c for p in (x['a'], x['b'])]
            rows.append({'net': c[0]['net'], 'class': c[0]['cls'], 'length_mm': round(tot, 2), 'segments': len(c),
                         'widths': '/'.join(sorted({str(x['w']) for x in c})), 'layers': '/'.join(sorted({x['layer'] for x in c})),
                         'bbox': '(%.2f, %.2f)-(%.2f, %.2f)' % (min(xs), min(ys), max(xs), max(ys))})
    rows.sort(key=lambda r: -r['length_mm'])
    for r in rows:
        print('%-36s %-14s %6.2f mm  %2d seg  w %-9s %-16s %s' % (r['net'][-36:], r['class'], r['length_mm'], r['segments'],
                                                             r['widths'], r['layers'], r['bbox']))
    print('necks: %d narrow segments, %d chains over %.1f mm, %.1f mm in total' % (
        len(segs), len(rows), mx, sum(r['length_mm'] for r in rows)))
    if out:
        with open(out, 'w', newline='', encoding='utf-8') as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ['net'])
            w.writeheader()
            w.writerows(rows)
    sys.exit(1 if rows else 0)


if __name__ == '__main__':
    main()

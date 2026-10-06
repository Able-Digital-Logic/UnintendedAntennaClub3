"""finish_guide.py FEASIBLE.json UNROUTED.csv OUT.md [--unblock UNBLOCK.json] [--title TEXT]   (2026-10-04)
Writes the open-link tables of docs/ROUTING_FINISH_GUIDE.md from tools/feasible.py output (one entry per missing link)
and outputs/RFVD_unrouted.csv (its 'group' column = work package).

Per link: net, class / width, both ends (pads and the closest points of the two copper islands), gap, and the verdict:
DIRECT <layer> | ROUTE <layer >via (x, y)> layer ...> | BLOCKED, plus how far the free space reaches from each end.
--unblock: {"NET": "cheapest unblock move with coordinates", ...} for the BLOCKED rows (from the routing reports).
  python finish_guide.py --selftest"""
import csv
import io
import json
import sys


def table(feas, groups, unblock):
    by = {}
    for f in feas:
        net = f['net']
        g = groups.get((net, round(f['a'][0], 1), round(f['a'][1], 1))) or groups.get(net) or 'Other'
        by.setdefault(g, []).append(f)
    out, n_direct, n_route, n_block = [], 0, 0, 0
    for g in sorted(by):
        out.append(f'\n### {g} ({len(by[g])} links)\n')
        out.append('| Net | Class / width | End A (pads, point) | End B (pads, point) | Gap mm | Verdict and suggested path |')
        out.append('|---|---|---|---|---|---|')
        for f in sorted(by[g], key=lambda x: x['net']):
            if f.get('direct'):
                v = 'DIRECT ' + ', '.join(f['direct']); n_direct += 1
            elif f.get('route'):
                v = f"ROUTE {f['route']} ({f.get('vias', '?')} vias)"; n_route += 1
            else:
                v = f"**BLOCKED** (free space reaches {f.get('reach_a')} / {f.get('reach_b')} mm from the ends)"
                if unblock.get(f['net'].split('/')[-1]):
                    v += '. Unblock: ' + unblock[f['net'].split('/')[-1]]
                n_block += 1
            out.append(f"| {f['net'].split('/')[-1]} | {f.get('class', '')} {f.get('w', '')} | {f['A']} ({f['a'][0]:.2f}, {f['a'][1]:.2f}) "
                       f"| {f['B']} ({f['b'][0]:.2f}, {f['b'][1]:.2f}) | {f['gap']:.1f} | {v} |")
    head = (f'**{len(feas)} open links: {n_direct} direct, {n_route} routable with the path shown, {n_block} blocked.** '
            'Paths are legal free-space corridors found by `tools/feasible.py` against every DRU clearance, rule area and '
            'via ban. They are a guide for the interactive router, not finished geometry: route them octilinear with fillets '
            'on clocks and strobes, and add a GND return via at every layer change of a fast net (R17).')
    return head, '\n'.join(out)


def main(argv):
    if '--selftest' in argv:
        feas = [{'net': '/X/A', 'class': 'Default', 'w': 0.12, 'gap': 3.0, 'A': 'U1.1', 'B': 'R1.2', 'a': [1, 2], 'b': [3, 4],
                 'direct': ['In3'], 'route': '', 'vias': 0},
                {'net': 'B', 'class': 'HighSpeed_Digital', 'w': 0.15, 'gap': 9.0, 'A': 'U2.1', 'B': 'J1.2', 'a': [5, 6], 'b': [7, 8],
                 'direct': [], 'route': '', 'reach_a': 1.0, 'reach_b': 2.0}]
        head, body = table(feas, {'A': 'G1', 'B': 'G2'}, {'B': 'move R9 to (1, 2)'})
        assert '1 direct, 0 routable with the path shown, 1 blocked' in head
        assert '| A | Default 0.12 |' in body and 'Unblock: move R9 to (1, 2)' in body and '### G2 (1 links)' in body
        print('finish_guide selftest OK')
        return
    feas = json.load(io.open(argv[1], encoding='utf-8'))
    groups = {}
    for r in csv.DictReader(io.open(argv[2], encoding='utf-8')):
        groups[(r['net'], round(float(r['ax']), 1), round(float(r['ay']), 1))] = r['group']
        groups.setdefault(r['net'], r['group'])
    unblock = {}
    if '--unblock' in argv:
        unblock = json.load(io.open(argv[argv.index('--unblock') + 1], encoding='utf-8'))
    title = argv[argv.index('--title') + 1] if '--title' in argv else 'Open links'
    head, body = table(feas, groups, unblock)
    io.open(argv[3], 'w', encoding='utf-8', newline='\n').write(f'## {title}\n\n{head}\n{body}\n')
    print(f'finish_guide: {len(feas)} links -> {argv[3]}')


if __name__ == '__main__':
    main(sys.argv)

"""List the free text notes (text / text_box) of a KiCad schematic project, read-only.

Used to find stale sheet notes and to build Konnect note-fix packages
(batch_delete by uuid + add_schematic_text at the same place, size and justify).

usage:
  python sch_notes.py <project_dir> [--grep REGEX] [--json out.json]
  python sch_notes.py --selftest
"""
import argparse
import glob
import io
import json
import os
import re
import sys


def tokens(s):
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c in ' \t\r\n':
            i += 1
        elif c in '()':
            yield c
            i += 1
        elif c == '"':
            j, buf = i + 1, []
            while s[j] != '"':
                if s[j] == '\\':
                    nxt = s[j + 1]
                    buf.append({'n': '\n', 't': '\t', '"': '"', '\\': '\\'}.get(nxt, nxt))
                    j += 2
                else:
                    buf.append(s[j])
                    j += 1
            yield ('str', ''.join(buf))
            i = j + 1
        else:
            j = i
            while j < n and s[j] not in ' \t\r\n()"':
                j += 1
            yield ('sym', s[i:j])
            i = j


def parse(s):
    stack, cur = [], []
    for t in tokens(s):
        if t == '(':
            stack.append(cur)
            cur = []
        elif t == ')':
            done, cur = cur, stack.pop()
            cur.append(done)
        else:
            cur.append(t[1])
    return cur[0]


def child(node, name):
    for c in node[1:]:
        if isinstance(c, list) and c and c[0] == name:
            return c
    return None


def notes(sexpr, sheet):
    out = []
    for c in sexpr[1:]:
        if not (isinstance(c, list) and c and c[0] in ('text', 'text_box')):
            continue
        at = child(c, 'at') or child(c, 'start')
        eff = child(c, 'effects') or []
        font = child(eff, 'font') if eff else None
        size = child(font, 'size') if font else None
        just = child(eff, 'justify') if eff else None
        uid = child(c, 'uuid')
        out.append({
            'sheet': sheet, 'kind': c[0], 'text': c[1],
            'x': float(at[1]) if at else None, 'y': float(at[2]) if at else None,
            'rot': float(at[3]) if at and len(at) > 3 else 0.0,
            'size': float(size[1]) if size else None,
            'justify': ' '.join(just[1:]) if just else '',
            'uuid': uid[1] if uid else None,
        })
    return out


def project_notes(proj):
    res = []
    for p in sorted(glob.glob(os.path.join(proj, '*.kicad_sch'))):
        res += notes(parse(io.open(p, encoding='utf-8').read()), os.path.basename(p))
    return res


def selftest():
    s = ('(kicad_sch (version 1) (text "a \\"q\\" b\\nline2" (exclude_from_sim no) (at 1.27 2.54 0)'
         ' (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid "u-1"))'
         ' (text_box "box" (at 5 6 0) (size 10 2) (effects (font (size 1 1))) (uuid "u-2")))')
    r = notes(parse(s), 'X.kicad_sch')
    assert r[0]['text'] == 'a "q" b\nline2' and r[0]['x'] == 1.27 and r[0]['justify'] == 'left bottom'
    assert r[0]['uuid'] == 'u-1' and r[0]['size'] == 1.27
    assert r[1]['kind'] == 'text_box' and r[1]['uuid'] == 'u-2'
    print('sch_notes selftest OK')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('proj', nargs='?')
    ap.add_argument('--grep')
    ap.add_argument('--json')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    res = project_notes(a.proj)
    if a.grep:
        rx = re.compile(a.grep, re.I)
        res = [r for r in res if rx.search(r['text'])]
    if a.json:
        json.dump(res, io.open(a.json, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    for r in res:
        first = r['text'].replace('\n', ' | ')
        print('%-24s %s (%.2f, %.2f) s%.2f %-12s %s\n    %s' % (
            r['sheet'], r['kind'], r['x'], r['y'], r['size'] or 0, r['justify'], r['uuid'], first[:400]))
    print('%d notes' % len(res), file=sys.stderr)


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""Turn a puller bundle (line_YYYY-MM_raw.json.gz) into
   1) out/line_YYYY-MM.json.gz  -> input for mk_line.py (dashboard)
   2) out/sheet_YYYY-MM.json    -> rows for the yearly Google Sheet (summary / messages / notes) + metrics
Usage: python3 tools/line/line_month.py line_2026-09_raw.json.gz OUTDIR"""
import json, gzip, sys, os, re, collections, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from convert import conv, OWN, TAG, TZ, st_of
BOT = 'U38b62d24ef14a84a048cd6633fc15d21'
TH = {'01': 'ม.ค.', '02': 'ก.พ.', '03': 'มี.ค.', '04': 'เม.ย.', '05': 'พ.ค.', '06': 'มิ.ย.', '07': 'ก.ค.', '08': 'ส.ค.',
      '09': 'ก.ย.', '10': 'ต.ค.', '11': 'พ.ย.', '12': 'ธ.ค.'}

def G1(b):
    out = []
    for g in re.findall(r'G\s*\d+', b):
        g = g.replace(' ', '')
        if g not in out: out.append(g)
    return out

def TY(gs):
    if not gs: return ''
    tape = 'G000' in gs; live = any(x != 'G000' for x in gs)
    return 'สด + เทป' if tape and live else 'เทปย้อนหลัง' if tape else 'เรียนสด'

def sumrow(r, lab):
    rem = 'ทักมาแล้วหาย' if r['hanging'] else ('ไม่เคยได้คุยกับแอดมิน' if r['nohuman'] else '')
    row = [lab, r['name'], r['id'], 'https://chat.line.biz/%s/chat/%s' % (BOT, r['id']), r['st'], ' / '.join(r['tags']),
           r['own'] or '', ' / '.join(r['admins']), r['c'], r['h'], r['b'], r['from'], r['to'], r['first'], r['med'], r['worst']]
    if rem: row.append(rem)
    return row

def msgrows(rooms, year):
    parts = {1: [], 2: [], 3: []}
    for r in sorted(rooms, key=lambda r: (r['from'] or '')):
        for t, w, x in r['tr']:
            d = int(t[3:5]); p = 1 if d <= 10 else 2 if d <= 20 else 3
            snd = 'ลูกค้า' if w == 'C' else 'บอท' if w == 'B' else 'แอดมิน'
            parts[p].append([r['name'], r['id'], '%s-%s' % (year, t[:5]), t[6:], snd, '' if w in ('C', 'B') else w,
                             x.replace('\n', '\\n'), r['st']])
    return parts

def reg_of(notes_in_month):
    per = collections.defaultdict(collections.Counter)
    for cid, n in notes_in_month:
        if not G1(n[4]): continue
        c = collections.Counter(x.replace(' ', '') for x in re.findall(r'G\s*\d+', n[4]))
        for k, v in c.items(): per[cid][k] = max(per[cid][k], v)
    return dict(rooms=len(per), live=sum(1 for c in per.values() if any(k != 'G000' for k in c)),
                tape=sum(1 for c in per.values() if 'G000' in c), regs=sum(sum(c.values()) for c in per.values()),
                notes=len(notes_in_month))

def main(src, outdir):
    A = json.load(gzip.open(src, 'rt', encoding='utf-8'))
    mo = A['month']; lo, hi = A['from'], A['to']; lab = '%s %s' % (TH[mo[5:]], mo[:4])
    rooms = [y for y in (conv(x, lo, hi) for x in A['raw']) if y]
    os.makedirs(outdir, exist_ok=True)
    with gzip.open(os.path.join(outdir, 'line_%s.json.gz' % mo), 'wt', encoding='utf-8') as f:
        json.dump({'month': mo, 'botId': BOT, 'rooms': rooms}, f, ensure_ascii=False)
    info = {cid: (v[0], [TAG.get(t, t) for t in v[1]]) for cid, v in A.get('info', {}).items()}
    for r in rooms: info[r['id']] = (r['name'], r['tags'])
    inm = sorted([(cid, n) for cid, L in A.get('notes', {}).items() for n in L
                  if datetime.datetime.fromtimestamp(n[2] / 1000, TZ).strftime('%Y-%m') == mo], key=lambda x: x[1][2])
    NT = []
    for cid, n in inm:
        d = datetime.datetime.fromtimestamp(n[2] / 1000, TZ); g = G1(n[4]); nm, tags = info.get(cid, ('', []))
        NT.append([nm, cid, 'https://chat.line.biz/%s/chat/%s' % (BOT, cid), d.strftime('%Y-%m-%d'), d.strftime('%H:%M'),
                   OWN.get(n[1], 'ทีมงานที่ออกไปแล้ว'), ' '.join(g), TY(g), st_of(tags), n[4].replace('\n', '\\n')])
    out = dict(month=mo, label=lab, sum=[sumrow(r, lab) for r in sorted(rooms, key=lambda r: (r['from'] or ''))],
               msg={str(k): v for k, v in msgrows(rooms, mo[:4]).items()}, notes=NT, reg=reg_of(inm),
               stats=dict(rooms=len(rooms), msgs=sum(len(r['tr']) for r in rooms)))
    json.dump(out, open(os.path.join(outdir, 'sheet_%s.json' % mo), 'w'), ensure_ascii=False)
    print(json.dumps({'month': mo, 'rooms': len(rooms), 'msgs': out['stats']['msgs'],
                      'msg_parts': {k: len(v) for k, v in out['msg'].items()}, 'notes': len(NT), 'reg': out['reg']}, ensure_ascii=False))

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'out')

# -*- coding: utf-8 -*-
"""Turn the LINE pull into src/line_2026-08.json and add its entry to src/agg.json.

Run from the hub folder (needs src/agg.json to already exist, i.e. after unpack.py).
Usage: python3 mk_line.py line_2026-08.json.gz
"""
import sys, json, gzip, collections, statistics as st

SRC = sys.argv[1] if len(sys.argv) > 1 else 'line_2026-08.json.gz'
with gzip.open(SRC, 'rt', encoding='utf-8') as f:
    payload = json.load(f)
rooms = payload['rooms']
month = payload.get('month', '2026-08')
BOT = payload.get('botId', '')

def secs(s):
    if not s or s == '—':
        return None
    n, u = s.split()
    return int(n) * (60 if u == 'นาที' else 1)

# ---- shared text dictionary: bot boilerplate repeats hundreds of times ----
freq = collections.Counter()
for r in rooms:
    for _, _, t in r['tr']:
        freq[t] += 1
dict_list = [t for t, n in freq.most_common() if n >= 2 and len(t) > 12]
dict_idx = {t: i for i, t in enumerate(dict_list)}

out_rooms = []
for r in rooms:
    tr = [[t, w, (dict_idx[x] if x in dict_idx else x)] for t, w, x in r['tr']]
    out_rooms.append({
        'n': r['name'], 'id': r['id'], 'tg': r['tags'], 'ow': r['own'], 'ad': r['admins'],
        'c': r['c'], 'h': r['h'], 'b': r['b'], 'f': r['from'], 't': r['to'],
        'r1': secs(r['first']), 'rm': secs(r['med']), 'rw': secs(r['worst']),
        'st': r['st'], 'nh': 1 if r['nohuman'] else 0, 'hg': 1 if r['hanging'] else 0,
        'tr': tr})

data = {'bot': BOT, 'dict': dict_list, 'rooms': out_rooms}
json.dump(data, open('src/line_%s.json' % month, 'w', encoding='utf-8'),
          separators=(',', ':'), ensure_ascii=False)

# ---------------- aggregate ----------------
firsts = [secs(r['first']) for r in rooms]
firsts = sorted(x for x in firsts if x is not None)
meds = sorted(x for x in (secs(r['med']) for r in rooms) if x is not None)
admin_rooms, admin_msgs = collections.Counter(), collections.Counter()
tags = collections.Counter()
hours, days = collections.Counter(), collections.Counter()
for r in rooms:
    for a in r['admins']:
        admin_rooms[a] += 1
    for t, w, x in r['tr']:
        if w not in ('C', 'B'):
            admin_msgs[w] += 1
        if w == 'C':
            hours[int(t[6:8])] += 1
            days[t[:5]] += 1
    for t in r['tags']:
        tags[t] += 1

agg_entry = {
    'threads': len(rooms),
    'msgs': sum(len(r['tr']) for r in rooms),
    'cust': sum(r['c'] for r in rooms),
    'adm': sum(r['h'] for r in rooms),
    'bot': sum(r['b'] for r in rooms),
    'won': sum(1 for r in rooms if r['st'] == 'สมัครแล้ว'),
    'open': sum(1 for r in rooms if r['st'] == 'ยังไม่สมัคร'),
    'sysonly': sum(1 for r in rooms if r['st'] == 'ถามกับระบบ'),
    'notag': sum(1 for r in rooms if r['st'] == 'ไม่ติดแท็ก'),
    'notyped': sum(1 for r in rooms if r['nohuman']),
    'unans': sum(1 for r in rooms if r['hanging']),
    'first_med': firsts[len(firsts) // 2] if firsts else None,
    'first_p90': firsts[int(len(firsts) * .9)] if firsts else None,
    'med_med': meds[len(meds) // 2] if meds else None,
    'admins': [[a, admin_rooms[a], admin_msgs.get(a, 0)] for a, _ in admin_rooms.most_common()],
    'tags': tags.most_common(),
    'hours': [[h, hours.get(h, 0)] for h in range(24)],
    'days': sorted(days.items()),
}

agg = json.load(open('src/agg.json', encoding='utf-8'))
agg.setdefault('line', {})[month] = agg_entry
keys = sorted(agg['line'].keys())
agg['linekeys'] = keys
TH = {'01': 'มกราคม', '02': 'กุมภาพันธ์', '03': 'มีนาคม', '04': 'เมษายน', '05': 'พฤษภาคม',
      '06': 'มิถุนายน', '07': 'กรกฎาคม', '08': 'สิงหาคม', '09': 'กันยายน', '10': 'ตุลาคม',
      '11': 'พฤศจิกายน', '12': 'ธันวาคม'}
SH = {'01': 'ม.ค.', '02': 'ก.พ.', '03': 'มี.ค.', '04': 'เม.ย.', '05': 'พ.ค.', '06': 'มิ.ย.',
      '07': 'ก.ค.', '08': 'ส.ค.', '09': 'ก.ย.', '10': 'ต.ค.', '11': 'พ.ย.', '12': 'ธ.ค.'}
for k in keys:
    y, m = k.split('-')
    agg.setdefault('mlabel', {}).setdefault(k, '%s %s' % (TH[m], y))
    agg.setdefault('mshort', {}).setdefault(k, '%s %s' % (SH[m], y[2:]))
json.dump(agg, open('src/agg.json', 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)

import os
print('src/line_%s.json  %s bytes' % (month, format(os.path.getsize('src/line_%s.json' % month), ',')))
print('rooms %d · msgs %d · dict %d entries' % (len(rooms), agg_entry['msgs'], len(dict_list)))
print('agg.line[%s] added · linekeys=%s' % (month, keys))

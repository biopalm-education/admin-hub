# -*- coding: utf-8 -*-
"""T3: link the rooms that name matching (T1/T2 in match_month.py) could not - by time alone.

usage: python3 tools/fb_links/match_timeonly.py <fb_threads.json> [--write]
Run from the repo root after unpack.py and after match_month.py has done every month.

A still-unlinked room gets a thread only when EXACTLY ONE inbox thread that no other room uses
has its last-activity minute equal to the room's latest message minute (across every month).
Covers: customers who renamed, and rooms our API data calls "ผู้ใช้ Facebook" (the Graph API hides
the name; Business Suite still shows the real one). Nothing else is used.

Why time alone is safe here: once T1/T2 have run, only ~1% of inbox threads are unused. Backtest on
the 17,441 rooms already linked by name+time (24 ก.ย. 2026): an unused thread sat on the same minute as
a room's last message in 34 rooms = 0.19%, so a wrong unique candidate is ~1 in 500 at worst.
Rooms with no candidate are left alone (thread outside the main inbox, or customer wrote after the pull).
"""
import json, sys, collections, importlib.util, os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('mm', os.path.join(HERE, 'match_month.py'))
mm = importlib.util.module_from_spec(spec); spec.loader.exec_module(mm)

th = json.load(open(sys.argv[1], encoding='utf-8'))['rows']
agg = json.load(open('src/agg.json', encoding='utf-8'))
fb = agg.get('fbuid', {})
months = mm.load_months()
last, mos = {}, collections.defaultdict(set)
for k, chats in months.items():
    b = mm.month_base(k)
    for r in chats:
        mos[r[19]].add(k)
        if r[18]:
            last[r[19]] = max(last.get(r[19], 0), b + max(x[0] for x in r[18]))
used = set(fb.values())
bymin = collections.defaultdict(list)
for x in th:
    bymin[int(x[2]) // 60000 - mm.EPOCH_MIN].append(str(x[0]))
new, per = {}, collections.Counter()
for g in sorted(last):
    if g in fb:
        continue
    c = [i for i in bymin.get(last[g], []) if i not in used]
    if len(c) == 1:
        new[g] = c[0]
cnt = collections.Counter(new.values())
new = {g: v for g, v in new.items() if cnt[v] == 1}
for g in new:
    for k in mos[g]:
        per[k] += 1
print('T3 rooms %d  · room-months %s' % (len(new), ' '.join('%s:%d' % kv for kv in sorted(per.items()))))
if '--write' in sys.argv:
    m = dict(fb); m.update(new)
    assert len(set(m.values())) == len(m), 'duplicate account id'
    agg['fbuid'] = m
    json.dump(agg, open('src/agg.json', 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    print('fbuid %d -> %d' % (len(fb), len(m)))

# -*- coding: utf-8 -*-
"""T4: near-miss rooms - name matches ONE inbox thread but the inbox time is 1-5 min OLDER than our last message.

usage: python3 tools/fb_links/match_nearmiss.py <fb_threads.json> [--write] [--max 5]
Run after match_month.py (T1/T2) and match_timeonly.py (T3).

T1/T2 never use an inbox time older than our data. For these rooms the gap is only a few minutes -
most likely our last line is something Business Suite does not count as thread activity (automation /
system line), not a different customer. Approved by the user 24 ก.ย. 2026 ("เอาเท่าที่ใส่ได้") with the rule:
  - one of the room's names == the title of EXACTLY ONE inbox thread, and that thread is unused
  - no other room of ours ever used that name
  - 0 < (our last minute - inbox minute) <= 5
A 104-minute gap was seen and is deliberately NOT covered.
"""
import json, sys, collections, importlib.util, os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('mm', os.path.join(HERE, 'match_month.py'))
mm = importlib.util.module_from_spec(spec); spec.loader.exec_module(mm)
MAXGAP = int(sys.argv[sys.argv.index('--max') + 1]) if '--max' in sys.argv else 5

th = json.load(open(sys.argv[1], encoding='utf-8'))['rows']
agg = json.load(open('src/agg.json', encoding='utf-8'))
fb = agg.get('fbuid', {})
months = mm.load_months()
last, names, mos = {}, collections.defaultdict(set), collections.defaultdict(set)
for k, chats in months.items():
    b = mm.month_base(k)
    for r in chats:
        g = r[19]; names[g].add(mm.norm(r[0])); mos[g].add(k)
        if r[18]:
            last[g] = max(last.get(g, 0), b + max(x[0] for x in r[18]))
owners = collections.defaultdict(set)
for g, ns in names.items():
    for n in ns:
        owners[n].add(g)
used = set(fb.values())
byn = collections.defaultdict(list)
for x in th:
    byn[mm.norm(x[1])].append((str(x[0]), int(x[2]) // 60000 - mm.EPOCH_MIN))
new, per = {}, collections.Counter()
for g in sorted(last):
    if g in fb:
        continue
    hits = [(n, h) for n in names[g] for h in byn.get(n, ())]
    if len(hits) != 1:
        continue
    n, (fid, t) = hits[0]
    if fid in used or owners[n] != {g}:
        continue
    if 0 < last[g] - t <= MAXGAP:
        new[g] = fid
cnt = collections.Counter(new.values())
new = {g: v for g, v in new.items() if cnt[v] == 1}
for g in new:
    for k in mos[g]:
        per[k] += 1
print('T4 rooms %d  · room-months %s' % (len(new), ' '.join('%s:%d' % kv for kv in sorted(per.items()))))
if '--write' in sys.argv:
    m = dict(fb); m.update(new)
    assert len(set(m.values())) == len(m), 'duplicate account id'
    agg['fbuid'] = m
    json.dump(agg, open('src/agg.json', 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    print('fbuid %d -> %d' % (len(fb), len(m)))

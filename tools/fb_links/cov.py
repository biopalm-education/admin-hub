# -*- coding: utf-8 -*-
"""agg['fblinkcov'] = {month: [rooms with a direct Inbox link, all rooms]} for every src/fb_*.json.

The page's Facebook note reads this ("มีลิงก์ตรงแล้ว a จาก b ห้อง"). A room counts as linked when
its thread id (row[19]) is a key of agg['fbuid']. Runs in tools/auto/refresh.py after build_fu.py,
so the counts follow each morning's data. Run from anywhere; paths resolve from the repo root.
"""
import json, glob, os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AP = os.path.join(ROOT, 'src', 'agg.json')
agg = json.load(open(AP, encoding='utf-8'))
fbuid = agg.get('fbuid', {})
cov = {}
for p in sorted(glob.glob(os.path.join(ROOT, 'src', 'fb_*.json'))):
    k = os.path.basename(p)[3:10]
    gids = {r[19] for r in json.load(open(p, encoding='utf-8'))['chats']}
    cov[k] = [sum(1 for g in gids if g in fbuid), len(gids)]
agg['fblinkcov'] = cov
json.dump(agg, open(AP, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
print('fblinkcov ' + ' · '.join('%s %d/%d' % (k, a, b) for k, (a, b) in cov.items()))

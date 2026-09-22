# -*- coding: utf-8 -*-
"""Cross-month reply carry (admin-hub, Sep 22 2026).

The dashboard keeps one row per chat per month, so a customer who writes late on the 31st and gets
an admin reply on the 1st used to count as "แอดมินไม่ได้ตอบเอง" in the first month.  For every
Facebook / Instagram row with no admin reply inside its own month, this looks for the first admin
message (role 1) in LATER months of the same thread; if it comes within 7 days of the row's first
customer message, the gap in minutes is stored in r[44] and build_v4.py uses it as the first-reply
time.  Replies that come more than 7 days later answer a new round, not this month's question, and
are ignored here (the follow-up page reads the whole thread anyway).

Run AFTER fix_roles.py / the refresh pull, BEFORE build_v4.py.
"""
import json, glob, datetime, collections, gc

T0 = datetime.datetime(2026, 1, 1)
LIMIT = 7 * 1440
def base(mo): return int((datetime.datetime(int(mo[:4]), int(mo[5:7]), 1) - T0).total_seconds() // 60)

def admin_times(rows_by_month):
    hum = collections.defaultdict(list)
    for mo, rows in rows_by_month:
        b = base(mo)
        for c in rows:
            hum[str(c[19])] += [b + m[0] for m in c[18] if m[1] == 1]
    return hum

def apply(mo, rows, hum):
    b = base(mo); n = 0
    for c in rows:
        while len(c) < 45: c.append(None)
        c[44] = None
        cm = [b + m[0] for m in c[18] if m[1] == 0]
        if not cm or any(m[1] == 1 and b + m[0] >= cm[0] for m in c[18]): continue
        later = [h for h in hum[str(c[19])] if h > cm[0]]
        if later and min(later) - cm[0] <= LIMIT:
            c[44] = int(min(later) - cm[0]); n += 1
    return n

# Facebook: one month file in memory at a time (the sandbox has ~1 GB)
FB = sorted(glob.glob('src/fb_*.json')); hum = collections.defaultdict(list)
for p in FB:
    f = json.load(open(p, encoding='utf-8'))
    for k, v in admin_times([(p[-12:-5], f['chats'])]).items(): hum[k] += v
    del f; gc.collect()
n = 0
for p in FB:
    f = json.load(open(p, encoding='utf-8')); n += apply(p[-12:-5], f['chats'], hum)
    json.dump(f, open(p, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False); del f; gc.collect()
del hum
ig = json.load(open('src/ig_all.json', encoding='utf-8'))
L = [(mo, ig['months'][mo]['leads']) for mo in sorted(ig['months'])]
hum = admin_times(L); m = sum(apply(mo, rows, hum) for mo, rows in L)
json.dump(ig, open('src/ig_all.json', 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
print('cross-month replies carried: fb', n, 'ig', m)

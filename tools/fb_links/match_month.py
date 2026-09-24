# -*- coding: utf-8 -*-
"""Match one month's Facebook rooms to Business Suite inbox threads -> agg['fbuid'].

usage: python3 tools/fb_links/match_month.py <fb_threads.json> <YYYY-MM> [--write]
  fb_threads.json = {"rows": [[threadFBID, title, timestamp_ms, threadType, threadID], ...]}
  harvested from Business Suite (see HANDOFF.md). NEVER commit that file - it holds customer names.

T1: a name the room ever used (normalised) == inbox title AND inbox last-activity minute ==
    the room's latest message minute across every month; exactly one candidate.
T2: no time match, but the name is unique on both sides and the inbox time is newer than
    the newest message anywhere in our data (the customer wrote after the pull).
Never uses an inbox time older than our data, never re-uses a threadFBID, leaves the rest unlinked.
Run from the repo root after unpack.py.
"""
import json, glob, sys, re, unicodedata, calendar
from datetime import datetime, timezone
from collections import defaultdict

EPOCH_MIN = int(datetime(2025, 12, 31, 17, 0, tzinfo=timezone.utc).timestamp()) // 60   # 2026-01-01 00:00 Thai

def norm(s):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', s or '').strip().lower())

def month_base(k):                       # minutes from 2026-01-01 Thai to the first of month k
    y, m = map(int, k.split('-'))
    return int((datetime(y, m, 1) - datetime(2026, 1, 1)).total_seconds()) // 60

def load_months():
    out = {}
    for p in sorted(glob.glob('src/fb_*.json')):
        out[p[7:14]] = json.load(open(p, encoding='utf-8'))['chats']
    return out

def match(threads, month, months, fbuid):
    last, names = {}, defaultdict(set)
    gmax = 0
    for k, chats in months.items():
        b = month_base(k)
        for r in chats:
            g = r[19]
            names[g].add(norm(r[0]))
            if r[18]:
                t = b + max(x[0] for x in r[18])
                last[g] = max(last.get(g, 0), t)
                gmax = max(gmax, t)
    inbox = []                                 # (fbid, normname, minute)
    for row in threads:
        inbox.append((str(row[0]), norm(row[1]), int(row[2]) // 60000 - EPOCH_MIN))
    by_name = defaultdict(list)
    for x in inbox:
        by_name[x[1]].append(x)
    gids_by_name = defaultdict(set)
    for g, ns in names.items():
        for n in ns:
            gids_by_name[n].add(g)
    used = set(fbuid.values())
    todo = [r[19] for r in months[month] if r[19] not in fbuid]
    t1, t2 = {}, {}
    for g in todo:
        if g not in last:
            continue
        cands = {x[0] for n in names[g] for x in by_name.get(n, ()) if x[2] == last[g]}
        if len(cands) == 1:
            t1[g] = cands.pop()
    taken = used | set(t1.values())
    for g in todo:
        if g in t1 or g not in last:
            continue
        hits = [x for n in names[g] for x in by_name.get(n, ())]
        ns = [n for n in names[g] if n in by_name]
        if len(hits) != 1 or len(ns) != 1 or len(gids_by_name[ns[0]]) != 1:
            continue
        x = hits[0]
        if x[2] > gmax and x[0] not in taken:
            t2[g] = x[0]
    # drop any fbid claimed twice
    cnt = defaultdict(int)
    for v in list(t1.values()) + list(t2.values()):
        cnt[v] += 1
    t1 = {g: v for g, v in t1.items() if cnt[v] == 1 and v not in used}
    t2 = {g: v for g, v in t2.items() if cnt[v] == 1 and v not in used}
    return t1, t2

if __name__ == '__main__':
    th = json.load(open(sys.argv[1], encoding='utf-8'))['rows']
    month = sys.argv[2]
    agg = json.load(open('src/agg.json', encoding='utf-8'))
    fbuid = agg.get('fbuid', {})
    months = load_months()
    t1, t2 = match(th, month, months, fbuid)
    print('%s  T1 %d  T2 %d' % (month, len(t1), len(t2)))
    if '--write' in sys.argv:
        new = dict(fbuid); new.update(t1); new.update(t2)
        assert len(set(new.values())) == len(new), 'duplicate account id'
        agg['fbuid'] = new
        json.dump(agg, open('src/agg.json', 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
        print('fbuid %d -> %d' % (len(fbuid), len(new)))

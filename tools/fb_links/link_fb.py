# -*- coding: utf-8 -*-
"""Match harvested Business Suite thread ids to Facebook chats in the dashboard.

Input  : the "ลิงก์แชท FB" sheet tab via the Apps Script v3 (act=links)
         -> {links: [[threadFBID, inbox title, last-msg ts in ms], ...]}  (latest per id)
Output : merges {graph thread id (row[19]): threadFBID} into agg['fbuid'],
         NEVER dropping ids that are already there (104 verified July rooms).

Matching (tools/fb_links/HANDOFF.md):
  1. name equal on both sides AND unique on both sides                    -> accept
  2. name duplicated: prefer the chat whose last message time is <= the
     inbox timestamp and closest to it (inbox ts is the whole thread's
     last message, so our last message can never be later by much)        -> accept if a single
     candidate lands within TOL, else leave for manual verification
  3. anything still ambiguous is written to tools/fb_links/ambiguous.json
     to be checked by opening the link (see HANDOFF)

Run in the workbench after unpack.py, before build.py.
"""
import json, glob, datetime, collections, unicodedata, hashlib, urllib.request, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
T0 = datetime.datetime(2026, 1, 1)
TH = datetime.timezone(datetime.timedelta(hours=7))
TOL_MIN = 3 * 24 * 60          # our last message may lag the inbox's by up to 3 days


def base(mo):
    return int((datetime.datetime(int(mo[:4]), int(mo[5:7]), 1) - T0).total_seconds() // 60)


def norm(s):
    s = unicodedata.normalize('NFKC', (s or '')).strip().lower()
    return ' '.join(s.split())


def mins_to_ms(m):
    """absolute minutes since 2026-01-01 Thai local -> epoch ms"""
    return int((T0.replace(tzinfo=TH) + datetime.timedelta(minutes=m)).timestamp() * 1000)


def fetch_links(agg):
    tok = hashlib.sha256(('bp-ov|' + open(ROOT + '/secret.txt').read().strip()).encode()).hexdigest()
    url = '%s?t=%s&act=links' % (agg['ovurl'], tok)
    return json.loads(urllib.request.urlopen(url, timeout=180).read().decode()).get('links', [])


def thread_index():
    """graph thread id -> {name, last (epoch ms)} across every month file"""
    th = {}
    for p in sorted(glob.glob(ROOT + '/src/fb_*.json')):
        mo = p[-12:-5]
        b = base(mo)
        f = json.load(open(p, encoding='utf-8'))
        for c in f['chats']:
            gid = str(c[19])
            last = max((m[0] for m in c[18]), default=None)
            e = th.setdefault(gid, {'name': c[0], 'last': 0})
            if c[0]:
                e['name'] = c[0]          # latest month wins -> newest stored name
            if last is not None:
                e['last'] = max(e['last'], mins_to_ms(b + last))
        del f
    return th


def match(links, th, have):
    by_name_dash = collections.defaultdict(list)
    for gid, e in th.items():
        by_name_dash[norm(e['name'])].append(gid)
    by_name_inbox = collections.defaultdict(list)
    for fbid, title, ts in links:
        by_name_inbox[norm(title)].append((str(fbid), ts))

    new, amb, miss = {}, [], []
    used = set(have.values())
    for name, cands in by_name_inbox.items():
        dash = by_name_dash.get(name, [])
        if not dash:
            miss += [c[0] for c in cands]
            continue
        if len(cands) == 1 and len(dash) == 1:
            gid, fbid = dash[0], cands[0][0]
            if gid in have:
                continue
            new[gid] = fbid
            continue
        # duplicated name -> time match
        for fbid, ts in cands:
            fits = [g for g in dash if g not in have and g not in new
                    and th[g]['last'] <= ts + 60000
                    and ts - th[g]['last'] <= TOL_MIN * 60000]
            fits.sort(key=lambda g: ts - th[g]['last'])
            if len(fits) == 1:
                new[fits[0]] = fbid
            elif fits:
                amb.append({'fbid': fbid, 'name': name, 'ts': ts,
                            'candidates': [{'gid': g, 'last': th[g]['last']} for g in fits[:6]]})
            else:
                miss.append(fbid)
    return new, amb, miss, used


def main():
    agg = json.load(open(ROOT + '/src/agg.json', encoding='utf-8'))
    have = dict(agg.get('fbuid', {}))
    before = len(have)
    links = fetch_links(agg)
    th = thread_index()
    new, amb, miss, _ = match(links, th, have)

    # never drop what is already there
    have.update(new)
    agg['fbuid'] = have
    json.dump(agg, open(ROOT + '/src/agg.json', 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump(amb, open(ROOT + '/tools/fb_links/ambiguous.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('links in sheet : %d' % len(links))
    print('fbuid before   : %d' % before)
    print('newly matched  : %d' % len(new))
    print('fbuid after    : %d' % len(have))
    print('ambiguous      : %d  (tools/fb_links/ambiguous.json)' % len(amb))
    print('no chat found  : %d' % len(miss))


if __name__ == '__main__':
    main()

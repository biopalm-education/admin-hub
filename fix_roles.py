# -*- coding: utf-8 -*-
"""Re-label who sent each of OUR messages, using Meta's own sender tag instead of the old
"text repeated >= 5 times = สำเร็จรูป" guess.   (admin-hub, Sep 22 2026)

Why: the old rule lumped three different things under "สำเร็จรูป" (role 2):
  bot / auto-responses · saved replies an admin clicked by hand · photos an admin sent.
Meta tags every Facebook message with where it was sent from:
  source:mobile  -> a person pressed send in the Business Suite / Pages app      => admin (role 1)
  source:web     -> automations (instant reply, ice-breakers, keyword replies, scheduled
                    follow-ups, slip bot) + the occasional admin on a desktop
  source:pages:private_reply -> comment auto-replies
On 400 recent threads 2,076 of 5,788 "สำเร็จรูป" messages were in fact sent from mobile.

Facebook rule (role 3 = Meta system lines is untouched):
  mobile                                   -> 1 admin
  web / private_reply / chat               -> 2 automatic, EXCEPT a one-off text (old role 1) sent
                                              2+ minutes after the customer's last message and not a
                                              known bot pattern -> 1 (admin working on a desktop)
  no tag / message not found in the re-pull -> keep the old role
Instagram has no sender tag in its API, so each saved-reply text is classed by how the SAME text
behaves on Facebook (>= 90% mobile -> admin text, >= 90% web -> bot text; needs >= 5 sends);
texts never seen on Facebook fall back to timing (2+ minutes after the customer = admin).
Attachments inherit the class of our nearest text within 3 minutes.

Input : src/ from unpack.py + fb_tags.jsonl ({"t": thread id, "m": [[abs minute, is_page, src, text30]]})
        -- produced by the one-off re-pull; daily runs tag messages natively (tools/auto/refresh.py).
Output: rewrites roles + counts r[7] (admin) / r[8] (automatic) / r[10] (first admin reply, s)
        in src/fb_*.json and src/ig_all.json; agg['txtclass'] (used by refresh.py for Instagram)
        and agg['rolefix'] (before/after counts). Run BEFORE build_v4.py.
"""
import json, glob, re, sys, datetime, collections, gc

TAGS = sys.argv[1] if len(sys.argv) > 1 else 'fb_tags.jsonl'
T0 = datetime.datetime(2026, 1, 1)
WEBBOT = re.compile(r'สถานะ\s*[:：]\s*ตรวจสอบสลิป|เราช่วยติวชีวะ|ยินดีให้คำปรึกษา|ติวชีวะ A-Level กับพี่|เพิ่งติดตามเพจ|ตอบกลับโฆษณา|กำหนดการสนทนา|transfer request|responding to a user comment|ตอบกลับความคิดเห็น')
ATT = ('[รูป/ไฟล์แนบ]', '[ไฟล์แนบ]', '[รูปภาพ]', '[สติกเกอร์]', '[ข้อความที่ IG ไม่รองรับ]')
def base(mo): return int((datetime.datetime(int(mo[:4]), int(mo[5:7]), 1) - T0).total_seconds() // 60)
def tx_of(d): return lambda x: d[x] if isinstance(x, int) and 0 <= x < len(d) else (x if isinstance(x, str) else '')

def recount(c, t):
    """refresh r[7] / r[8] / r[10] from the (new) roles"""
    ms = c[18]
    c[7] = sum(1 for m in ms if m[1] == 1)
    c[8] = sum(1 for m in ms if m[1] == 2)
    c0 = next((m[0] for m in ms if m[1] == 0), None)
    a = next((m[0] for m in ms if m[1] == 1 and c0 is not None and m[0] >= c0), None)
    c[10] = -1 if a is None else int(a - c0) * 60

# ---------- Facebook ----------
tags = {}
for l in open(TAGS, encoding='utf-8'):
    try: o = json.loads(l)
    except Exception: continue
    idx = collections.defaultdict(list)
    for m in o['m']:
        if m[1]: idx[m[0]].append(m)
    tags[str(o['t'])] = idx
print('threads with tags', len(tags))

STAT = collections.Counter(); TXT = collections.defaultdict(lambda: [0, 0])   # text30 -> [mobile, web]
for p in sorted(glob.glob('src/fb_*.json')):
    mo = p[-12:-5]; b = base(mo); f = json.load(open(p, encoding='utf-8')); t = tx_of(f['dict'])
    for c in f['chats']:
        idx = tags.get(str(c[19]))
        used = set(); lc = None; changed = False
        for m in c[18]:
            r = m[1]
            if r == 0: lc = m[0]; continue
            if r == 3: continue
            s = str(t(m[2])).strip(); k = s[:30]
            cand = idx.get(b + m[0], []) if idx else []
            hit = next((x for x in cand if id(x) not in used and x[3] == k), None) or next((x for x in cand if id(x) not in used), None)
            if hit is None: STAT['nomatch'] += 1; continue
            used.add(id(hit)); src = hit[2]
            if src == 'm': new = 1; TXT[k][0] += 1
            elif src in ('w', 'p', 'c'):
                TXT[k][1] += 1
                desk = r == 1 and lc is not None and m[0] - lc >= 2 and s not in ATT and not WEBBOT.search(s)
                new = 1 if desk else 2
            else: STAT['notag'] += 1; continue
            STAT['%d>%d' % (r, new)] += 1
            if new != r: m[1] = new; changed = True
        if changed: recount(c, t); STAT['chats_changed'] += 1
    json.dump(f, open(p, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    print(mo, dict(STAT)); del f; gc.collect()
del tags; gc.collect()

# texts whose Facebook behaviour is clear-cut -> reused for Instagram (and by refresh.py)
agg = json.load(open('src/agg.json', encoding='utf-8'))
cls = dict(agg.get('txtclass') or {})
for k, (mob, web) in TXT.items():
    n = mob + web
    if n >= 5 and k not in ATT and len(k) >= 8:
        if mob >= 0.9 * n: cls[k] = 1
        elif web >= 0.9 * n: cls[k] = 0
print('text classes', len(cls), 'admin', sum(cls.values()))

# ---------- Instagram ----------
ig = json.load(open('src/ig_all.json', encoding='utf-8')); t = tx_of(ig['dict']); IS = collections.Counter()
for mo, blk in ig['months'].items():
    for c in blk['leads']:
        ms = c[18]; lc = None; new = [None] * len(ms)
        for i, m in enumerate(ms):
            if m[1] == 0: lc = m[0]; continue
            if m[1] == 3: continue
            s = str(t(m[2])).strip()
            if s in ATT: continue
            k = s[:30]
            if k in cls: new[i] = cls[k]; IS['byFB'] += 1
            elif m[1] == 2: new[i] = 1 if (lc is not None and m[0] - lc >= 2) else 0; IS['byTime'] += 1
            else: new[i] = 1; IS['typed'] += 1
        for i, m in enumerate(ms):                      # attachments follow our nearest text
            if m[1] in (1, 2) and str(t(m[2])).strip() in ATT:
                nb = [j for j in range(len(ms)) if new[j] is not None and abs(ms[j][0] - m[0]) <= 3]
                new[i] = new[min(nb, key=lambda j: abs(j - i))] if nb else (1 if m[1] == 1 else 0); IS['att'] += 1
        ch = False
        for i, m in enumerate(ms):
            if new[i] is None: continue
            r2 = 1 if new[i] else 2
            IS['%d>%d' % (m[1], r2)] += 1
            if r2 != m[1]: m[1] = r2; ch = True
        if ch: recount(c, t); IS['chats_changed'] += 1
json.dump(ig, open('src/ig_all.json', 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
print('IG', dict(IS))

agg['txtclass'] = cls
agg['rolefix'] = {'fb': dict(STAT), 'ig': dict(IS), 'at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
json.dump(agg, open('src/agg.json', 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)

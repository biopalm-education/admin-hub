# -*- coding: utf-8 -*-
"""Follow-up list (admin-hub "แชทที่ยังไม่มีแอดมินตอบ"): Facebook / Instagram chats where the
customer got ONLY automatic replies (auto-responder, saved replies, bot) and no admin has
typed anything since the customer's latest round.

"Admin replied" = any message with role 1. Since fix_roles.py (Sep 22 2026) role 1 means a PERSON
sent it — typed or a saved reply clicked by hand (Facebook: Meta's source:mobile tag; Instagram: the
same text's behaviour on Facebook) — and role 2 is genuinely automatic. Attachments/empty never count.

Thread level, stitched across months by thread id (chat row [19]), so a chat leaves the
list as soon as an admin types after the customer's latest message in any later pull.

  wait   = days from the customer's LAST message to the end of the data (agg v4end)
  shown  = wait >= 7 days, split 7-29 days / 30+ days in the page (<7 counted only)
  prior  = 1 when an admin had typed in this thread before this unanswered round
  kind   = stage of the thread's latest month: ad (ปุ่มโฆษณาอย่างเดียว) · menu (ทักทาย/เมนู/แค่ขอบคุณ)
           ask (พิมพ์ถามเอง) · other (นักเรียนเดิม/เรื่องอื่น) · give (Giveaway)

  hist   = [date, fb 7-29, fb 30+, ig 7-29, ig 30+] per build, carried over from the last publish,
           so the page can show whether the 30+ pile is actually shrinking week to week

Writes src/followup.json (then runs build_pay.py, which adds the payment follow-up list). Run AFTER build_v5.py / post_v5_speed.py, BEFORE build.py.
Memory-lean on purpose: one month file in memory at a time (the Composio sandbox has ~1 GB).
"""
import json, glob, re, datetime, collections, gc

SYS = re.compile(r'^\x01|Facebook สร้างแชทนี้ขึ้น|คุณกำลังตอบกลับความคิดเห็น|replied to a post|ได้ตอบกลับโพสต์|ตอบกลับโฆษณา$|^ตั้งระยะข้อมูลลูกค้า')
NOISE = set(['▶ กดปุ่ม', 'เมนูหลัก', 'You received a message', '[รูป/ไฟล์แนบ]', '[รูปภาพ]', '[สติกเกอร์]', '(emoji)', '[ไฟล์]', '[ไฟล์แนบ]', '[ตอบกลับสตอรี่]',
             '[ข้อความที่ IG ไม่รองรับ]', '[วิดีโอ]', '[เสียง]', ''])
TAGS = [('ม.ต้น', r'ม\.?\s?ต้น|มต้น|ม\.\s?[1-3](?!\d)|ม[1-3](?!\d)'),
        ('ม.ปลาย', r'ม\.?\s?ปลาย|มปลาย|ม\.\s?[4-6](?!\d)|ม[4-6](?!\d)'),
        ('สอวน.', r'สอวน|ค่าย\s?1|โอลิมปิก|IJSO'),
        ('สอบเข้า', r'สอบเข้า|MWIT|KVIS|เตรียมอุดม|มหิดลวิทย|กำเนิดวิทย'),
        ('A-Level', r'A-?Level|TCAS|หมอ|แพทย์'),
        ('ราคา/โปร', r'ราคา|ค่าเรียน|เท่าไ|กี่บาท|โปร|ส่วนลด'),
        ('ตารางเรียน', r'ตาราง|วันไหน|กี่โมง|เริ่มเรียน'),
        ('สมัคร/ชำระ', r'สมัคร|ลงทะเบียน|ชำระ|โอน|จ่าย'),
        ('รูปแบบเรียน', r'onsite|online|ออนไลน์|เรียนสด|เทป|ย้อนหลัง'),
        ('นักเรียนเดิม', r'ลิ้ง|ลิงก์|ลิงค์|เข้าเรียน|รหัสผ่าน|ชีท|เอกสาร|ใบเสร็จ')]
TAGS = [(n, re.compile(p, re.I)) for n, p in TAGS]
LOW = re.compile(r'^[\s\.\,!?~😊🙏❤️👍🥰💕❣️🏻]*(สวัสดี|หวัดดี|ขอบคุณ|ขอบคุน|ค่ะ|คะ|ครับ|คับ|ค่า|ok|โอเค|รับทราบ|จ้า|ใช่|ได้|เรียบร้อย)?\s*(ค่ะ|คะ|ครับ|คับ|ค่า|นะคะ|นะครับ|มากค่ะ|มากครับ|มาก ๆ|มากๆ|มาก|เลยค่ะ|จ้า|ะ|บ)?[\s\.\,!?~😊🙏❤️👍🥰💕❣️🏻]*$', re.I)
# ---- follow-up quality (Sep 22 2026): is this round worth an admin's time? ----
#   A ถามจริง      the customer typed a real message (4+ chars, not just hi/thanks) that is about a
#                  course, a grade, an existing-student need, or is phrased as a question
#   B กดปุ่มสนใจ   no real typing, but pressed a course button (ad button or course menu)
#   C ไม่ต้องตาม   only stickers / photos / story replies / greetings / thanks / short unclear text
BTN_COURSE = set(['สนใจลงเรียน ม.ต้น', 'สนใจลงเรียน ม.ปลาย', 'สอบถามตารางเรียนทั้งม.ต้น และม.ปลาย', 'สนใจลงเรียนคอร์ส ม.ต้น',
    'สนใจคอร์สเตรียม สอวน.', 'สนใจคอร์สเตรียม สอวน. ชีวะค่าย1', 'สนใจคอร์สพื้นฐานชีวะ ม.4', 'สนใจคอร์สพื้นฐานชีวะ ม.5',
    'สนใจคอร์สพื้นฐานชีวะ ม.6', 'ค่าเรียนเท่าไร', 'มีโปรโมชั่นหรือไม่', 'ชำระเงินแบบไหนได้บ้าง', 'ชำระเงินได้อย่างไร',
    'หลักสูตรเรียนชีววิทยามีราคาเท่าไร?', 'คอร์สเรียนมีราคาเท่าไร', 'มีคอร์สเรียนอะไรบ้าง', 'ช่วยแนะนำคอร์สเรียน',
    'รายละเอียดคอร์ส', 'รายละเอียด', 'สมัครเรียน', 'คอร์ส ม.ต้น', 'คอร์ส ม.ปลาย', 'คอร์สม.ต้น', 'คอร์สม.ปลาย', 'ยืนยันการลงทะเบียน',
    'เทป RERUN', 'คอร์สทั้งหมด', 'คอร์สเรียนทั้งหมด', 'คอร์ส ONLINE', 'Onsite สด', 'Onsite', 'Online', 'Online : Google meet',
    'วิธีการสมัครเรียน', 'แผนการเรียน ม.ต้น', 'สอบถามรายละเอียด', 'โปรโมชั่น', 'ติดต่อแอดมิน', 'ต้องการติดต่อแอดมิน',
    # LINE OA rich-menu / card buttons (Sep 22 2026)
    'แผนการเรียน ม.ปลาย', 'คอร์ส RERUN', 'ตัวอย่างคอร์สเรียน', 'รีวิวคอร์สเรียน', 'เงื่อนไข และอายุคอร์สเรียน', 'ขั้นตอนการเข้าเรียน',
    'วิธีการเข้าเรียนย้อนหลัง', 'ไม่ได้รับลิ้งค์เข้าเรียนผ่าน E-mail', 'ยืนยันข้อมูลถูกต้อง'])
# LINE buttons that are an existing student's real problem -> treated like a typed request (tier A)
BTN_NEED = set(['ไม่ได้รับลิ้งค์เข้าเรียนผ่าน E-mail', 'วิธีการเข้าเรียนย้อนหลัง', 'ขั้นตอนการเข้าเรียน', 'ติดต่อแอดมิน', 'ต้องการติดต่อแอดมิน'])
COURSE = re.compile(r'สนใจ|ซิ่ว|ชีวะ|ชีววิทยา|คอร์ส|คอส|ครอส|ราคา|ค่าเรียน|สมัคร|เท่าไ|กี่บาท|โปร|ตาราง|ลงเรียน|เรียน|สอวน|IJSO|A-?Level|สอบ|MWIT|KVIS|เตรียมอุดม|onsite|online|ออนไลน์|เทป|ติว|โมดูล|module|ม\.?\s?[1-6]|ม\.?\s?ต้น|ม\.?\s?ปลาย|ป\.?\s?[1-6]|ลิ้ง|ลิงก์|ลิงค์|รหัสผ่าน|ชีท|เอกสาร|ใบเสร็จ|เลื่อน|โอน|ชำระ|จ่าย', re.I)
QUEST = re.compile(r'\?|ไหม|มั้ย|มั๊ย|หรือเปล่า|ยังไง|อย่างไร|อะไร|เมื่อไ|ที่ไหน|ได้บ้าง|สอบถาม|ขอทราบ|อยาก|ต้องการ|แนะนำ|รบกวน', re.I)
DECLINE = re.compile(r'ไม่มีอะไร|ไม่สนใจ|ไม่เอา|ไม่ต้องส่ง|ไม่ต้องการ|ยกเลิก|หยุดส่ง|เลิกส่ง|ส่งผิด|ทักผิด|กดผิด')
def quality(said):
    if any(DECLINE.search(x) for x in said): return 'C'     # the customer said no -> nothing to follow up
    real = [x for x in said if x not in BTN_COURSE and not LOW.match(x) and len(x.strip()) >= 4 and not x.startswith('[')]
    if any(COURSE.search(x) or QUEST.search(x) for x in real): return 'A'
    if any(x in BTN_NEED for x in said): return 'A'
    if any(x in BTN_COURSE for x in said): return 'B'
    return 'C'

KIND = {'V': 'ad', 'H': 'menu', 'T': 'ask', 'Q': 'ask', 'W': 'ask', 'O': 'other', 'S': 'other', 'G': 'give'}
T0 = datetime.datetime(2026, 1, 1)

def tx_of(d): return lambda x: d[x] if isinstance(x, int) and 0 <= x < len(d) else (x if isinstance(x, str) else '')
def base(mo): return int((datetime.datetime(int(mo[:4]), int(mo[5:7]), 1) - T0).total_seconds() // 60)
def stamp(mi): return (T0 + datetime.timedelta(minutes=mi)).strftime('%Y-%m-%d %H:%M')

agg = json.load(open('src/agg.json', encoding='utf-8'))
END = agg.get('v4end') or 0
try: OLD = json.load(open('src/followup.json', encoding='utf-8'))
except Exception: OLD = {}
PRE = {'fb': set((OLD.get('pre') or {}).get('fb', [])), 'ig': set((OLD.get('pre') or {}).get('ig', [])), 'line': set()}
try:
    for k, v in json.load(open('pre2026.json', encoding='utf-8')).items(): PRE[k] |= set(v)
except Exception: pass
STATUS = {}
del agg; gc.collect()

def feed(th, mo, rows, t):
    b = base(mo)
    for c in rows:
        e = th.setdefault(str(c[19]), {'name': '', 'm': [], 'st': None, 'src': None, 'mo': mo})
        e['name'] = c[0] or e['name']; e['st'] = c[37]; e['src'] = c[26]; e['mo'] = mo
        e.setdefault('per', []).append([mo, sum(1 for m in c[18] if m[1] == 1), sum(1 for m in c[18] if m[1] == 0)])
        for m in c[18]:
            s = str(t(m[2])).strip()
            r = m[1]
            if SYS.search(s): continue          # Meta system lines never count for either side
            if r == 0: e['m'].append((b + m[0], 0, s))
            elif r == 1: e['m'].append((b + m[0], 1, ''))
            elif r in (2, 3) and s not in NOISE: e['m'].append((b + m[0], 2, s[:160]))

def finish(th, ch):
    """Reads the WHOLE thread (all months stitched) and decides where it stands at the end of the data:
       won      closed with a verified slip
       answered an admin replied after the customer's latest message -> ball is with the customer
       closing  the customer's latest round is only thanks / ok / sticker / photo after an admin had
                already talked -> the conversation ended politely, nothing to follow up
       waiting  the customer's latest round got automatic replies only -> listed (prior = had an admin
                before, in 2026 or earlier)"""
    out = []; st = collections.Counter()
    for tid, e in th.items():
        ms = e['m']
        cus = [x for x in ms if x[1] == 0]
        if not cus: continue
        ms.sort(key=lambda x: x[0])
        hum = [x[0] for x in ms if x[1] == 1]
        lastH = hum[-1] if hum else None
        prior = bool(hum) or tid in PRE[ch]
        if e['st'] == 'W': st['won'] += 1; continue
        ep = [x for x in cus if lastH is None or x[0] > lastH]
        if not ep: st['answered'] += 1; continue          # an admin replied after the customer's last message
        said = [x[2] for x in ep if x[2] not in NOISE]
        if prior and all(LOW.match(x) for x in said): st['closing'] += 1; continue
        auto = [x for x in ms if x[1] == 2 and x[0] >= ep[0][0]]   # all role-2 after this round = automatic by construction
        lastC = ep[-1][0]
        seen = []
        for x in ep:
            if x[2] not in NOISE and x[2] not in seen: seen.append(x[2])
        joined = ' '.join(seen)
        kind = KIND.get(e['st'], 'ask')
        if kind == 'ask' and all(LOW.match(x) for x in seen): kind = 'menu'   # only greetings / thanks
        d0 = T0 + datetime.timedelta(minutes=lastC)
        wk = (d0 - datetime.timedelta(days=d0.weekday())).strftime('%Y-%m-%d')
        q = quality(said)
        st['noise' if q == 'C' else ('waiting_prior' if prior else 'waiting_never')] += 1
        out.append([tid, e['name'] or '', kind, round((END - lastC) / 1440.0, 1),
                    stamp(ep[0][0]), stamp(lastC), wk, len(ep), ' | '.join(seen)[:400],
                    [n for n, rx in TAGS if rx.search(joined)],
                    (auto[-1][2] if auto else ''), len(auto), 1 if prior else 0, e['src'] or 'organic', e['mo'], q])
    out.sort(key=lambda r: r[5], reverse=True)
    STATUS[ch] = dict(st)
    return out

th = collections.OrderedDict()
for p in sorted(glob.glob('src/fb_*.json')):
    f = json.load(open(p, encoding='utf-8')); feed(th, p[-12:-5], f['chats'], tx_of(f['dict'])); del f; gc.collect()
FB = finish(th, 'fb')
THR = {'fb': {k: e['per'] for k, e in th.items() if len(e['per']) > 1}}
del th; gc.collect()

ig = json.load(open('src/ig_all.json', encoding='utf-8')); t = tx_of(ig['dict']); th = collections.OrderedDict()
for mo in sorted(ig['months']): feed(th, mo, ig['months'][mo]['leads'], t)
del ig; gc.collect()
IG = finish(th, 'ig')
THR['ig'] = {k: e['per'] for k, e in th.items() if len(e['per']) > 1}
del th
# one chat across months: {channel: {thread id: [[month, admin msgs, customer msgs], ...]}} (2+ months only)
json.dump(THR, open('src/threads.json', 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
print('multi-month threads', {k: len(v) for k, v in THR.items()}, 'status', STATUS)

# ---- LINE OA (Sep 22 2026) -------------------------------------------------------------------
# LINE is pulled by hand once a month (src/line_YYYY-MM.json, rooms[].tr = [["MM-DD HH:MM", who, text]]),
# who = 'C' customer · 'B' bot / auto-response · anything else = the admin's own name (LINE says who sent it).
# Same whole-thread logic as Facebook/Instagram, stitched by room id across months. "wait" is counted to the
# END OF THE LATEST LINE MONTH (not to today), because nothing after that month has been pulled yet.
LN = []; LEND = None; LBOT = ''
lfiles = sorted(glob.glob('src/line_*.json'))
if lfiles:
    th = collections.OrderedDict(); ADM = {}; LMAX = 0
    for pth in lfiles:
        mo = pth[-12:-5]; f = json.load(open(pth, encoding='utf-8')); t = tx_of(f['dict']); LBOT = f.get('bot') or LBOT
        y = int(mo[:4])
        for r in f['rooms']:
            e = th.setdefault(r['id'], {'name': '', 'm': [], 'st': None, 'src': 'line', 'mo': mo})
            e['name'] = r.get('n') or e['name']; e['st'] = r.get('sg'); e['mo'] = mo
            e['ow'] = r.get('ow') or ''; e['reg'] = 1 if any('สมัครแล้ว' in x for x in (r.get('tg') or [])) else 0
            e['tg'] = r.get('tg') or []
            nh = 0; nc = 0
            for m in r['tr']:
                try: ts = int((datetime.datetime(y, int(m[0][:2]), int(m[0][3:5]), int(m[0][6:8]), int(m[0][9:11])) - T0).total_seconds() // 60)
                except Exception: continue
                sx = str(t(m[2])).strip(); who = m[1]; LMAX = max(LMAX, ts)
                if who == 'C': e['m'].append((ts, 0, sx)); nc += 1
                elif who == 'B':
                    if sx not in NOISE: e['m'].append((ts, 2, sx[:160]))
                else:
                    e['m'].append((ts, 1, '')); nh += 1; ADM.setdefault(r['id'], collections.Counter())[who] += 1
            e.setdefault('per', []).append([mo, nh, nc])
        del f; gc.collect()
    lm = lfiles[-1][-12:-5]; ly, lmn = int(lm[:4]), int(lm[5:7])
    nxt = datetime.datetime(ly + (lmn == 12), lmn % 12 + 1, 1)
    LEND = int((nxt - T0).total_seconds() // 60) - 1                     # 23:59 on the last day of that month
    # Sep 23 2026: a month pulled part-way (e.g. ก.ย. 1-22) must not age every room to the 30th -> end = last message seen
    if LMAX and LMAX < LEND: LEND = LMAX
    END_SAVE = END; END = LEND
    LN = finish(th, 'line')
    END = END_SAVE
    for r in LN:
        e = th[r[0]]
        r += [e.get('ow') or '', e.get('reg') or 0, [a for a, _ in ADM.get(r[0], collections.Counter()).most_common()]]
    THR['line'] = {k: e['per'] for k, e in th.items() if len(e['per']) > 1}
    json.dump(THR, open('src/threads.json', 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    del th; gc.collect()
    print('line', len(LN), 'end', stamp(LEND), 'status', STATUS.get('line'))

# weekly history of the headline counts (never-admin chats only), carried over from the
# previously published followup.json that unpack.py restores — one point per data-end date
def heads(L):
    z = [r for r in L if not r[12] and r[2] != 'give' and r[15] != 'C']   # only rounds worth following up
    return [sum(1 for r in z if 7 <= r[3] < 30), sum(1 for r in z if r[3] >= 30)]
hist = OLD.get('hist', [])
day = stamp(END)[:10]
def heads_ln(L):   # LINE: almost every room has met an admin, so the headline counts include those rooms
    z = [r for r in L if r[15] != 'C']
    return [sum(1 for r in z if 7 <= r[3] < 30), sum(1 for r in z if r[3] >= 30)]
hist = [h for h in hist if h[0] != day] + [[day] + heads(FB) + heads(IG) + heads_ln(LN)]
hist = sorted(hist)[-120:]

COLS = ['tid', 'name', 'kind', 'wait', 'first', 'last', 'week', 'n', 'said', 'tags', 'auto', 'nauto', 'prior', 'src', 'mo', 'q',
        'owner', 'reg', 'admins']   # last three: LINE only
json.dump({'end': stamp(END), 'hist': hist, 'status': STATUS, 'pre': {k: sorted(v) for k, v in PRE.items()},
           'cols': COLS, 'fb': FB, 'ig': IG, 'line': LN, 'lend': stamp(LEND) if LEND else None, 'lbot': LBOT},
          open('src/followup.json', 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
for ch, L in (('fb', FB), ('ig', IG), ('line', LN)):
    c = collections.Counter(('<7' if r[3] < 7 else ('7-29' if r[3] < 30 else '30+'), r[12], r[15]) for r in L if r[2] != 'give')
    print(ch, len(L), sorted(c.items()))

# ---- payment follow-up (Sep 23 2026): chats sent a price with no verified slip after it -> key "pay" ----
del FB, IG, LN; gc.collect()
try:
    import build_pay; build_pay.main()
except Exception as ex:          # the auto-reply list above is already saved; never let the payment list break it
    print('build_pay FAILED', repr(ex))

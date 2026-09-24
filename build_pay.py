# -*- coding: utf-8 -*-
"""Payment follow-up list (admin-hub "Follow up · ตามโอนเงิน", Sep 23 2026).

A chat is listed when OUR side (admin, saved reply or automation - never the customer) sent a price
and no verified slip came back AFTER that quote:
  quote  = PRICE (amount + บาท/฿/.- , "ค่าเรียน <n>", "ราคา <n>") or BILL ("ยอดชำระ", "สรุปรายละเอียด",
           the BioPalm account number / เลขบัญชี)
  paid   = "ตรวจสอบสลิปสำเร็จ" or receiver "บจก. ไบโอปาล์ม" in any message at/after the FIRST quote of the
           open round; LINE rooms tagged "สมัครแล้ว" also count as paid
Whole thread, all months stitched by thread id (same as build_fu.py).

  g (group, first match wins)
             R ลูกค้าตอบแล้ว·รอแอดมิน  the customer wrote something real after the quote and no admin has answered it
             A สรุปยอดแล้ว·รอโอน      BILL was sent (customer had agreed; only the transfer is missing)
             B คุยต่อหลังได้ราคา       the customer replied after the quote, the admin answered, then silence
             C ได้ราคาแล้วเงียบ         nothing real from the customer after the quote
             F ตามแล้ว·รอลูกค้า        (Sep 23 2026) an admin followed up and the customer has not answered yet;
                                       after FU_DUE days of silence the chat falls back to A/B/C with due=1
  follow-up  a PERSON's message (role 1) sent while the customer is silent: at least FU_GAP after the
             customer's last line and after the anchor quote, and nobody from the customer since our
             previous message. A price card re-sent this way is a follow-up, not a new quote, so it no
             longer resets the age. Messages within 30 min of each other count as one follow-up.
  anchor     the quote the age is counted from = the latest quote that was NOT a follow-up
  flow       where last week's / yesterday's list went: judge() again on the thread cut at END-7d / END-1d
             X ไม่ต้องตาม              customer declined / wants to think after the quote, or we moved the chat to LINE
  wait       days from the LAST quote to the end of the data
  ball       'c' = the customer wrote after the quote and no admin answered yet -> reply first
Writes key "pay" into src/followup.json (run right after build_fu.py; build_fu.py calls it itself).
"""
import json, glob, re, datetime, collections, gc
T0 = datetime.datetime(2026, 1, 1)
def base(mo): return int((datetime.datetime(int(mo[:4]), int(mo[5:7]), 1) - T0).total_seconds() // 60)
def stamp(mi): return (T0 + datetime.timedelta(minutes=mi)).strftime('%Y-%m-%d %H:%M')
def tx_of(d): return lambda x: d[x] if isinstance(x, int) and 0 <= x < len(d) else (x if isinstance(x, str) else '')
PRICE = re.compile(r'\d{1,3},\d{3}\s*(บาท|฿|\.-)|\d{4,5}\s*(บาท|฿|\.-)|ค่าเรียน\s*[:：]?\s*\d|ราคา\s*[:：]?\s*\d')
BILL = re.compile(r'ยอดชำระ|สรุปรายละเอียด|166-?3-?63464-?6|เลขที่บัญชี|เลขบัญชี')
AMT = re.compile(r'(\d{1,3},\d{3}|\d{4,5})(?:\.\d+)?\s*(?:บาท|฿|\.-)')
SLIP = re.compile(r'ตรวจสอบสลิปสำเร็จ|ชื่อผู้รับ\s*[:：]\s*(บจก\.?\s*ไบโอปาล์ม|BIOPALM)', re.I)
TOLINE = re.compile(r'line\.me|lin\.ee|@biopalm|แอด\s?ไลน์|ทัก\s?ไลน์|ทาง\s?ไลน์|ทาง\s?LINE|แอด\s?LINE|ทัก\s?LINE', re.I)
DECLINE = re.compile(r'ไม่สนใจ|ไม่เอา|ไม่ต้องส่ง|ไม่ต้องการ|ยกเลิก|หยุดส่ง|เลิกส่ง|ส่งผิด|ทักผิด|กดผิด|ขอคิดดูก่อน|ไว้ก่อน|แพง|ขอบคุณ.*ไม่')
SYS = re.compile(r'^\x01|Facebook สร้างแชทนี้ขึ้น|คุณกำลังตอบกลับความคิดเห็น|replied to a post|ได้ตอบกลับโพสต์|ตอบกลับโฆษณา$|^ตั้งระยะข้อมูลลูกค้า')
NOISE = set(['▶ กดปุ่ม', 'เมนูหลัก', 'You received a message', '[รูป/ไฟล์แนบ]', '[รูปภาพ]', '[สติกเกอร์]', '(emoji)', '[ไฟล์]', '[ไฟล์แนบ]',
             '[ตอบกลับสตอรี่]', '[ข้อความที่ IG ไม่รองรับ]', '[วิดีโอ]', '[เสียง]', ''])
import importlib.util, sys, io, contextlib
LOW = re.compile(r'^[\s\.\,!?~😊🙏❤️👍🥰💕❣️🏻]*(สวัสดี|หวัดดี|ขอบคุณ|ขอบคุน|ค่ะ|คะ|ครับ|คับ|ค่า|ok|โอเค|รับทราบ|จ้า|ใช่|ได้|เรียบร้อย)?\s*(ค่ะ|คะ|ครับ|คับ|ค่า|นะคะ|นะครับ|มากค่ะ|มากครับ|มาก ๆ|มากๆ|มาก|เลยค่ะ|จ้า|ะ|บ)?[\s\.\,!?~😊🙏❤️👍🥰💕❣️🏻]*$', re.I)
BTN = set(['สนใจลงเรียน ม.ต้น', 'สนใจลงเรียน ม.ปลาย', 'สอบถามตารางเรียนทั้งม.ต้น และม.ปลาย', 'สนใจลงเรียนคอร์ส ม.ต้น', 'สนใจคอร์สเตรียม สอวน.',
    'สนใจคอร์สเตรียม สอวน. ชีวะค่าย1', 'สนใจคอร์สพื้นฐานชีวะ ม.4', 'สนใจคอร์สพื้นฐานชีวะ ม.5', 'สนใจคอร์สพื้นฐานชีวะ ม.6', 'ค่าเรียนเท่าไร',
    'มีโปรโมชั่นหรือไม่', 'ชำระเงินแบบไหนได้บ้าง', 'ชำระเงินได้อย่างไร', 'หลักสูตรเรียนชีววิทยามีราคาเท่าไร?', 'คอร์สเรียนมีราคาเท่าไร',
    'มีคอร์สเรียนอะไรบ้าง', 'ช่วยแนะนำคอร์สเรียน', 'รายละเอียดคอร์ส', 'รายละเอียด', 'สมัครเรียน', 'คอร์ส ม.ต้น', 'คอร์ส ม.ปลาย', 'คอร์สม.ต้น',
    'คอร์สม.ปลาย', 'ยืนยันการลงทะเบียน', 'เทป RERUN', 'คอร์สทั้งหมด', 'คอร์สเรียนทั้งหมด', 'คอร์ส ONLINE', 'Onsite สด', 'Onsite', 'Online',
    'Online : Google meet', 'วิธีการสมัครเรียน', 'แผนการเรียน ม.ต้น', 'สอบถามรายละเอียด', 'โปรโมชั่น', 'ติดต่อแอดมิน', 'ต้องการติดต่อแอดมิน',
    'แผนการเรียน ม.ปลาย', 'คอร์ส RERUN', 'ตัวอย่างคอร์สเรียน', 'รีวิวคอร์สเรียน', 'เงื่อนไข และอายุคอร์สเรียน', 'ขั้นตอนการเข้าเรียน',
    'วิธีการเข้าเรียนย้อนหลัง', 'ไม่ได้รับลิ้งค์เข้าเรียนผ่าน E-mail', 'ยืนยันข้อมูลถูกต้อง'])
TAGS = [('ม.ต้น', r'ม\.?\s?ต้น|มต้น|ม\.\s?[1-3](?!\d)|ม[1-3](?!\d)|Module\s?[1-4]'), ('ม.ปลาย', r'ม\.?\s?ปลาย|มปลาย|ม\.\s?[4-6](?!\d)|ม[4-6](?!\d)'),
        ('สอวน.', r'สอวน|ค่าย\s?1|โอลิมปิก|IJSO'), ('สอบเข้า', r'สอบเข้า|MWIT|KVIS|เตรียมอุดม|มหิดลวิทย|กำเนิดวิทย'), ('A-Level', r'A-?Level|TCAS|หมอ|แพทย์'),
        ('Onsite', r'onsite|ออนไซต์|เรียนสด'), ('Online', r'online|ออนไลน์|google meet'), ('เทป', r'เทป|rerun|ย้อนหลัง')]
TAGS = [(n, re.compile(p, re.I)) for n, p in TAGS]
QUEST = re.compile(r'\?|ไหม|มั้ย|มั๊ย|หรือเปล่า|ยังไง|อย่างไร|อะไร|เมื่อไ|ที่ไหน|ได้บ้าง|สอบถาม|ขอทราบ|อยาก|ต้องการ|แนะนำ|รบกวน|เท่าไ|กี่บาท|ได้ไหม|หรอ|เหรอ', re.I)
COURSE = re.compile(r'สนใจ|คอร์ส|คอส|ครอส|ราคา|ค่าเรียน|สมัคร|ลงเรียน|ตาราง|เรียน|สอวน|IJSO|A-?Level|สอบ|MWIT|KVIS|onsite|online|ออนไลน์|เทป|โมดูล|module|ม\.?\s?[1-6]|ผ่อน|โปร|ส่วนลด', re.I)
POLITE = re.compile(r'ขอบคุณ|ขอบคุน|โอเค|\bok\b|รับทราบ|ได้ค่ะ|ได้ครับ|ได้ค่า|ค่ะ$|ครับ$', re.I)
PAIDSAY = re.compile(r'โอนแล้ว|โอนเรียบร้อย|โอนไปแล้ว|แนบสลิป|ชำระแล้ว|ชำระเรียบร้อย|จ่ายแล้ว')
STUDENT = re.compile(r'ไฟล์|ลิ้ง|ลิงก์|ลิงค์|เข้าเรียน|รหัสผ่าน|password|ชีท|ใบเสร็จ|ใบกำกับ|ดาวน์โหลด|ไม่ได้รับอีเมล|e-?mail', re.I)
THINK = re.compile(r'ขอ(ถาม|ปรึกษา|คุย|คิด)\S*ก่อน|ส่งให้\S*ดู|ไว้ก่อน|เดี๋ยว\S*(บอก|แจ้ง|ติดต่อ)|ปรึกษา')
MOVED = re.compile(r'ทัก(ไป)?แล้ว|แอด(ไป)?แล้ว|add แล้ว', re.I)
def asks(s): return not THINK.search(s) and real(s) and (QUEST.search(s) or COURSE.search(s)) and not (POLITE.search(s) and not QUEST.search(s) and len(s) < 30)
BUY = re.compile(r'สมัคร|ลงเรียน|ลงคอร์ส|เอาคอร์ส|เอาอันนี้|โอน|จ่าย|ชำระ|สรุปยอด|ขอเลขบัญชี|ผ่อน|บัตรเครดิต', re.I)

def real(s): return s and s not in NOISE and s not in BTN and not LOW.match(s) and len(s.strip()) >= 3 and not s.startswith('[')

FU_GAP = 12 * 60        # minutes of customer silence before an admin message counts as a follow-up
FU_DUE = 7 * 1440       # a follow-up the customer ignored for this long -> due for the next round
FU_MERGE = 30           # admin messages this close together are one follow-up

def rounds(ms, i0, i1):
    """walk ms[i0:i1] (the open round) -> anchor index, follow-up times"""
    anchor = None; fus = []; lastC = -10**9; cust_since_our = True
    for i in range(i0, i1):
        t, r, x = ms[i]
        if r == 0:
            if x not in NOISE: lastC = t; cust_since_our = True
            continue
        isq = bool(PRICE.search(x) or BILL.search(x))
        isfu = (r == 1 and anchor is not None and not cust_since_our and t - lastC >= FU_GAP and t - ms[anchor][0] >= FU_GAP)
        if isfu:
            if fus and t - fus[-1] < FU_MERGE: fus[-1] = t
            else: fus.append(t)
        elif isq:
            anchor = i; fus = []
        cust_since_our = False
    return anchor, fus

def judge(ms, end, extra=None, cut=None):
    """ms: [(minute, role, text)] role 0 customer · 1 admin (person) · 2 automation, sorted.
       cut: look at the thread as it stood at minute `cut` (flow tables)"""
    if cut is not None:
        ms = [x for x in ms if x[0] <= cut]; end = cut   # LINE 'สมัครแล้ว' tag has no date -> tagged rooms stay out of the flow too
    cus = [x for x in ms if x[1] == 0]
    if not cus: return None, 'nocus'
    q = [i for i, x in enumerate(ms) if x[1] != 0 and (PRICE.search(x[2]) or BILL.search(x[2]))]
    if not q: return None, 'noquote'
    sl = [i for i, x in enumerate(ms) if SLIP.search(x[2])]
    lastSlip = sl[-1] if sl else -1
    q = [i for i in q if i > lastSlip]
    if not q:
        # paid: was the round before the slip followed up?
        prev = sl[-2] if len(sl) > 1 else -1
        pq = [i for i, x in enumerate(ms) if prev < i < lastSlip and x[1] != 0 and (PRICE.search(x[2]) or BILL.search(x[2]))]
        fu = rounds(ms, pq[0], lastSlip)[1] if pq else []
        return {'paidat': ms[lastSlip][0], 'fu': fu}, ('paid_fu' if fu else 'paid')
    if extra and extra.get('reg'): return {'paidat': None, 'fu': []}, 'paid'
    anchor, fus = rounds(ms, q[0], len(ms))
    if anchor is None: anchor = q[-1]
    first, last = ms[q[0]], ms[anchor]
    after = ms[anchor + 1:]
    bill = any(BILL.search(ms[i][2]) for i in q)
    amt = ''
    for i in reversed(q):
        m = AMT.findall(ms[i][2])
        if m: amt = ' · '.join(dict.fromkeys(a + ' บาท' for a in m[:3])); break
    csaid = [x[2] for x in cus if real(x[2])]
    cafter = [x for x in after if x[1] == 0 and x[2] not in NOISE]
    hafter = [x for x in after if x[1] == 1]
    flags = []
    if sl: flags.append('เคยโอนแล้ว')
    if any(TOLINE.search(x[2]) for x in ms[q[0]:] if x[1] != 0): flags.append('ชวนไปคุย LINE')
    if any(BUY.search(x[2]) for x in cus if real(x[2])): flags.append('ลูกค้าพูดถึงการสมัคร/โอน')
    dec = any(DECLINE.search(x[2]) for x in cafter)
    lastH = hafter[-1][0] if hafter else -1
    tail = [x for x in cafter if x[0] > lastH]                       # customer lines nobody has answered yet
    ball = 'c' if any(asks(x[2]) for x in tail) else 'a'
    creal = [x for x in cafter if real(x[2]) and not (POLITE.search(x[2]) and len(x[2]) < 30 and not QUEST.search(x[2]))]
    lastCust = cafter[-1][0] if cafter else -1
    fu_open = bool(fus) and fus[-1] > lastCust                      # we followed up and the customer has not answered since
    due = 0
    if any(PAIDSAY.search(x[2]) for x in cafter): g = 'X'; flags.append('ลูกค้าแจ้งว่าโอนแล้ว (ไม่มีสลิปจากบอท — เช็กยอด)')
    elif any(STUDENT.search(x[2]) for x in cafter if real(x[2])): g = 'X'; flags.append('ดูเป็นนักเรียนแล้ว (ถามเรื่องไฟล์/ลิงก์เข้าเรียน)')
    elif dec: g = 'X'; flags.append('ลูกค้าปฏิเสธ/ขอคิดก่อน')
    elif 'ชวนไปคุย LINE' in flags and (not creal or any(MOVED.search(x[2]) for x in cafter)): g = 'X'
    elif ball == 'c': g = 'R'
    elif fu_open and end - fus[-1] < FU_DUE: g = 'F'
    else:
        g = 'A' if bill else ('B' if creal else 'C')
        if fu_open: due = 1
    bg = g if g not in ('F',) else ('A' if bill else ('B' if creal else 'C'))
    joined = ' '.join(csaid)
    row = dict(wait=round((end - last[0]) / 1440.0, 1), q0=stamp(first[0]), q1=stamp(last[0]), last=stamp(ms[-1][0]),
               lastc=stamp(cus[-1][0]), g=g, bill=1 if bill else 0, amt=amt, qt=last[2].replace('\n', ' ')[:160], nq=len(q),
               said=' | '.join(dict.fromkeys(csaid))[-140:], after=' | '.join(x[2] for x in cafter)[-200:], ball=ball,
               tags=[n for n, rx in TAGS if rx.search(joined + ' ' + last[2])], flags=flags, who=last[1],
               nfu=len(fus), fu1=stamp(fus[-1]) if fus else '', due=due, bg=bg, fus=fus, lastc_m=cus[-1][0])
    return row, g

COLS = ['tid', 'name', 'g', 'wait', 'q0', 'q1', 'last', 'lastc', 'bill', 'amt', 'qt', 'nq', 'said', 'after', 'ball', 'tags', 'flags', 'src', 'owner', 'week',
        'nfu', 'fu1', 'due', 'bg']
TODO = ('R', 'A', 'B', 'C')
OLD = collections.defaultdict(collections.Counter)   # quotes older than 90 days: counted, not listed (keeps followup.json small)
FLOW = collections.defaultdict(dict)
FUSTAT = collections.defaultdict(collections.Counter)
def finish(th, end, ch, out, stat):
    now = {}
    for tid, e in th.items():
        e['m'].sort(key=lambda x: x[0])
        r, why = judge(e['m'], end, e)
        stat[ch]['paid' if why == 'paid_fu' else why] += 1
        if why in ('paid', 'paid_fu'):
            now[tid] = ('paid', r and r['paidat'])
            if why == 'paid_fu': stat[ch]['paid_fu'] += 1
            continue
        if not r: continue
        now[tid] = (r['g'], r['wait'], r['fus'], r['lastc_m'])
        # the group the chat would be in without the follow-up (so a due chat shows where it came from)
        if r['wait'] >= 90: OLD[ch][r['g']] += 1; continue
        d0 = datetime.datetime.strptime(r['q1'], '%Y-%m-%d %H:%M'); wk = (d0 - datetime.timedelta(days=d0.weekday())).strftime('%Y-%m-%d')
        out.append([tid, e.get('n') or '', r['g'], r['wait'], r['q0'], r['q1'], r['last'], r['lastc'], r['bill'], r['amt'], r['qt'], r['nq'],
                    r['said'], r['after'], r['ball'], r['tags'], r['flags'], e.get('src') or '', e.get('ow') or '', wk,
                    r['nfu'], r['fu1'], r['due'], r['bg']])
        if r['fus']:
            FUSTAT[ch]['fu_any'] += 1
            if end - r['fus'][-1] < 7 * 1440: FUSTAT[ch]['fu_7d'] += 1
    out.sort(key=lambda r: r[5], reverse=True)
    # ---- flow: the to-do list as it stood 1 / 7 days ago, and where each of those chats is now ----
    for days in (1, 7):
        cut = end - days * 1440
        start = {}
        for tid, e in th.items():
            r, why = judge(e['m'], end, e, cut)
            if r and why in TODO and 1 <= r['wait'] < 90: start[tid] = r
        endset = {tid for tid, n in now.items() if n[0] in TODO and 1 <= n[1] < 90}
        res = collections.defaultdict(list)
        for tid, r0 in start.items():
            n = now.get(tid)
            if tid in endset:                                      # still on today's to-do list
                if n[3] > cut and n[0] in ('R', 'B') and n[3] > r0['lastc_m']: k = 'reply'
                elif n[2] and n[2][-1] > cut: k = 'fudue'
                else: k = 'still'
            elif not n: k = 'aged'
            elif n[0] == 'paid': k = 'paid'
            elif n[0] == 'X': k = 'x'
            elif n[0] == 'F': k = 'fu'
            else: k = 'aged'                                       # older than 90 days now
            res[k].append([tid, th[tid].get('n') or ''])
        new = [[tid, th[tid].get('n') or ''] for tid in endset if tid not in start]
        fuw = [tid for tid, n in now.items() if n[0] not in ('paid',) and n[2] and n[2][-1] > cut]
        paidw = [tid for tid, n in now.items() if n[0] == 'paid' and n[1] and n[1] > cut]
        FLOW[ch][str(days)] = {'from': stamp(cut), 'to': stamp(end), 'new': new,
                               'out': {k: v for k, v in res.items()}, 'fuwin': len(fuw), 'paidwin': len(paidw)}

# ---- (Sep 23 2026) third list: "คุยแล้วไม่ถึงราคา" — asked about a course, an admin answered, no price was ever sent ----
GRADE = re.compile(r'ม\.?\s?[1-6]|ป\.?\s?[1-6]|ม\.ต้น|ม\.ปลาย|มัธยม|ประถม|ซิ่ว|ปี\s?[1-4]|dek\s?\d', re.I)
ASKC = re.compile(r'คอร์ส|คอส|ครอส|ราคา|ค่าเรียน|สมัคร|เท่าไ|กี่บาท|โปร|ตาราง|ลงเรียน|สอวน|IJSO|A-?Level|สอบเข้า|MWIT|KVIS|เตรียมอุดม|onsite|online|ออนไลน์|เรียนสด|เทป|โมดูล|module', re.I)
NP_TODO = ('A', 'B')
REGD = re.compile(r'(?<!ถ้า)(?<!หลัง)(?<!ก่อน)สมัคร(?:คอร์ส|คอส|เรียน|\s){0,3}(?:ไป)?แล้ว|ซื้อคอร์ส(?:ไป)?แล้ว|ลงทะเบียน(?:ไป)?แล้ว')   # "หนูสมัครคอร์สไปแล้ว ต้องเข้าเรียนที่ไหน"
def judge_np(ms, end, extra=None, cut=None):
    """whole thread; in the list when the customer typed about a course, an ADMIN (person) answered the customer's latest
       real message, and our side never sent a price / payment summary in the open round (after the last verified slip).
       anchor = the admin's first answer after the customer's latest real message; age = days since that answer.
       A บอกชั้น/คอร์สแล้ว (grade AND course/price/schedule words) · B ถามเรื่องคอร์สทั่วไป · F ตามแล้ว · X ไม่ต้องตาม"""
    if cut is not None:
        ms = [x for x in ms if x[0] <= cut]; end = cut
    if extra and extra.get('reg'): return None, 'reg'
    sl = [i for i, x in enumerate(ms) if SLIP.search(x[2])]
    i0 = sl[-1] + 1 if sl else 0
    if any(x[1] != 0 and (PRICE.search(x[2]) or BILL.search(x[2])) for x in ms[i0:]): return None, 'quoted'
    rnd = ms[i0:]
    creal = [x for x in rnd if x[1] == 0 and real(x[2]) and not (POLITE.search(x[2]) and len(x[2]) < 30 and not QUEST.search(x[2]))]
    if not creal: return None, 'nocus'
    joined = ' '.join(x[2] for x in creal)
    if not ASKC.search(joined) and not COURSE.search(joined): return None, 'noint'
    lastR = creal[-1][0]
    ans = [x for x in rnd if x[1] == 1 and x[0] >= lastR]
    if not ans: return None, 'waiting'
    anchor = ans[0][0]
    fus = []; lastC = lastR; since = False
    for t, r, x in rnd:
        if t <= anchor: continue
        if r == 0:
            if x not in NOISE: lastC = t; since = True
            continue
        if r == 1 and not since and t - lastC >= FU_GAP and t - anchor >= FU_GAP:
            if fus and t - fus[-1] < FU_MERGE: fus[-1] = t
            else: fus.append(t)
        since = False
    cafter = [x for x in rnd if x[1] == 0 and x[0] > anchor and x[2] not in NOISE]
    recent = [x[2] for x in creal[-8:]] + [x[2] for x in cafter]
    flags = []
    if sl: flags.append('เคยโอนแล้ว')
    if any(TOLINE.search(x[2]) for x in rnd if x[1] != 0 and x[0] >= lastR): flags.append('ชวนไปคุย LINE')
    if any(BUY.search(x) for x in recent): flags.append('ลูกค้าพูดถึงการสมัคร/โอน')
    lastCust = cafter[-1][0] if cafter else lastR
    fu_open = bool(fus) and fus[-1] > lastCust
    due = 0
    alltx = joined + ' ' + ' '.join(x[2] for x in cafter)      # grade often comes in the reply after the admin's answer ("ม.3ค่ะ")
    hot = bool(GRADE.search(alltx) and ASKC.search(alltx))
    if any(PAIDSAY.search(x) for x in recent): g = 'X'; flags.append('ลูกค้าแจ้งว่าโอนแล้ว (เช็กยอด)')
    elif any(STUDENT.search(x) for x in recent) and not ASKC.search(' '.join(recent[-3:])): g = 'X'; flags.append('ดูเป็นนักเรียนแล้ว (ถามเรื่องไฟล์/ลิงก์เข้าเรียน)')
    elif any(REGD.search(x) for x in recent): g = 'X'; flags.append('ลูกค้าบอกว่าสมัครแล้ว (เช็กชื่อในระบบ)')
    elif any(DECLINE.search(x) for x in recent): g = 'X'; flags.append('ลูกค้าปฏิเสธ/ขอคิดก่อน')
    elif 'ชวนไปคุย LINE' in flags: g = 'X'
    elif fu_open and end - fus[-1] < FU_DUE: g = 'F'
    else:
        g = 'A' if hot else 'B'
        if fu_open: due = 1
    bg = g if g != 'F' else ('A' if hot else 'B')
    row = dict(wait=round((end - anchor) / 1440.0, 1), q0=stamp(creal[0][0]), q1=stamp(anchor), last=stamp(ms[-1][0]),
               lastc=stamp(lastCust), g=g, qt=ans[0][2].replace('\n', ' ')[:160], nq=len(ans),
               said=' | '.join(dict.fromkeys(x[2] for x in creal))[-160:], after=' | '.join(x[2] for x in cafter)[-200:],
               tags=[n for n, rx in TAGS if rx.search(joined)], flags=flags,
               nfu=len(fus), fu1=stamp(fus[-1]) if fus else '', due=due, fus=fus, lastc_m=lastCust, bg=bg)
    return row, g

NPOLD = collections.defaultdict(collections.Counter); NPFLOW = collections.defaultdict(dict); NPSTAT = collections.defaultdict(collections.Counter)
def finish_np(th, end, ch, out):
    now = {}
    for tid, e in th.items():
        r, why = judge_np(e['m'], end, e)
        NPSTAT[ch][why] += 1
        if not r: continue
        now[tid] = (r['g'], r['wait'], r['fus'], r['lastc_m'])
        if r['wait'] >= 90: NPOLD[ch][r['g']] += 1; continue
        d0 = datetime.datetime.strptime(r['q1'], '%Y-%m-%d %H:%M'); wk = (d0 - datetime.timedelta(days=d0.weekday())).strftime('%Y-%m-%d')
        out.append([tid, e.get('n') or '', r['g'], r['wait'], r['q0'], r['q1'], r['last'], r['lastc'], 0, '', r['qt'], r['nq'],
                    r['said'], r['after'], 'a', r['tags'], r['flags'], e.get('src') or '', e.get('ow') or '', wk,
                    r['nfu'], r['fu1'], r['due'], r['bg']])
        if r['fus'] and end - r['fus'][-1] < 7 * 1440: NPSTAT[ch]['fu_7d'] += 1
    out.sort(key=lambda r: r[5], reverse=True)
    endset = {tid for tid, n in now.items() if n[0] in NP_TODO and 1 <= n[1] < 90}
    for days in (1, 7):
        cut = end - days * 1440
        start = {}
        for tid, e in th.items():
            r, why = judge_np(e['m'], end, e, cut)
            if r and why in NP_TODO and 1 <= r['wait'] < 90: start[tid] = r
        res = collections.defaultdict(list)
        for tid, r0 in start.items():
            n = now.get(tid)
            if tid in endset:
                k = 'fudue' if (n[2] and n[2][-1] > cut) else 'still'
            else:
                pr, pw = judge(th[tid]['m'], end, th[tid])
                if pw in ('paid', 'paid_fu'): k = 'paid'
                elif pr: k = 'quoted'
                elif not n:
                    k = 'waiting' if judge_np(th[tid]['m'], end, th[tid])[1] == 'waiting' else 'aged'
                elif n[0] == 'X': k = 'x'
                elif n[0] == 'F': k = 'fu'
                else: k = 'aged'
            res[k].append([tid, th[tid].get('n') or ''])
        NPFLOW[ch][str(days)] = {'from': stamp(cut), 'to': stamp(end), 'new': [[t, th[t].get('n') or ''] for t in endset if t not in start],
                                 'out': dict(res)}

def main():
    F = json.load(open('src/followup.json', encoding='utf-8'))
    agg = json.load(open('src/agg.json', encoding='utf-8')); END = agg.get('v4end') or 0; del agg
    stat = collections.defaultdict(collections.Counter); PAY = {}; NP = {'fb': [], 'ig': [], 'line': []}
    th = {}
    for p in sorted(glob.glob('src/fb_*.json')):
        mo = p[-12:-5]; f = json.load(open(p, encoding='utf-8')); t = tx_of(f['dict']); b = base(mo)
        for c in f['chats']:
            e = th.setdefault(str(c[19]), {'n': '', 'm': [], 'src': ''}); e['n'] = c[0] or e['n']; e['src'] = c[26] or e['src']
            for m in c[18]:
                s = str(t(m[2])).strip()
                if SYS.search(s): continue
                e['m'].append((b + m[0], m[1] if m[1] in (0, 1) else 2, s))
        del f; gc.collect()
    PAY['fb'] = []; finish(th, END, 'fb', PAY['fb'], stat); NP['fb'] = []; finish_np(th, END, 'fb', NP['fb']); del th; gc.collect()
    ig = json.load(open('src/ig_all.json', encoding='utf-8')); t = tx_of(ig['dict']); th = {}
    for mo in sorted(ig['months']):
        b = base(mo)
        for c in ig['months'][mo]['leads']:
            e = th.setdefault(str(c[19]), {'n': '', 'm': [], 'src': ''}); e['n'] = c[0] or e['n']; e['src'] = c[26] or e['src']
            for m in c[18]:
                s = str(t(m[2])).strip()
                if SYS.search(s): continue
                e['m'].append((b + m[0], m[1] if m[1] in (0, 1) else 2, s))
    del ig; gc.collect()
    PAY['ig'] = []; finish(th, END, 'ig', PAY['ig'], stat); NP['ig'] = []; finish_np(th, END, 'ig', NP['ig']); del th; gc.collect()
    PAY['line'] = []
    lf = sorted(glob.glob('src/line_*.json'))
    if lf and F.get('lend'):
        LE = int((datetime.datetime.strptime(F['lend'], '%Y-%m-%d %H:%M') - T0).total_seconds() // 60)
        th = {}
        for p in lf:
            mo = p[-12:-5]; f = json.load(open(p, encoding='utf-8')); t = tx_of(f['dict']); y = int(mo[:4])
            for r in f['rooms']:
                e = th.setdefault(r['id'], {'n': '', 'm': [], 'src': 'line'}); e['n'] = r.get('n') or e['n']; e['ow'] = r.get('ow') or ''
                e['reg'] = 1 if any('สมัครแล้ว' in x for x in (r.get('tg') or [])) else 0
                for m in r['tr']:
                    try: ts = int((datetime.datetime(y, int(m[0][:2]), int(m[0][3:5]), int(m[0][6:8]), int(m[0][9:11])) - T0).total_seconds() // 60)
                    except Exception: continue
                    w = m[1]; e['m'].append((ts, 0 if w == 'C' else (2 if w == 'B' else 1), str(t(m[2])).strip()))
            del f; gc.collect()
        finish(th, LE, 'line', PAY['line'], stat); finish_np(th, LE, 'line', NP['line']); del th; gc.collect()
    F['pay'] = PAY; F['paycols'] = COLS; F['paystat'] = {k: dict(v) for k, v in stat.items()}; F['pay90'] = {k: dict(v) for k, v in OLD.items()}
    F['payflow'] = {k: v for k, v in FLOW.items()}; F['payfu'] = {k: dict(v) for k, v in FUSTAT.items()}
    F['np'] = NP; F['npflow'] = {k: v for k, v in NPFLOW.items()}; F['npstat'] = {k: dict(v) for k, v in NPSTAT.items()}; F['np90'] = {k: dict(v) for k, v in NPOLD.items()}
    # weekly history of the headline pile (A+B+C, 1-6 / 7-29 / 30-89 days) per channel
    day = (F.get('end') or '')[:10]
    def heads(L): z = [r for r in L if r[2] in TODO]; return [sum(1 for r in z if 1 <= r[3] < 7), sum(1 for r in z if 7 <= r[3] < 30), sum(1 for r in z if 30 <= r[3] < 90)]
    ph = [h for h in (F.get('payhist') or []) if h[0] != day] + [[day] + heads(PAY['fb']) + heads(PAY['ig']) + heads(PAY['line'])]
    F['payhist'] = sorted(ph)[-120:]
    json.dump(F, open('src/followup.json.tmp', 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    import os; os.replace('src/followup.json.tmp', 'src/followup.json')   # never leave a half-written file behind
    for ch, L in PAY.items():
        c = collections.Counter((r[2], '<1' if r[3] < 1 else '1-6' if r[3] < 7 else '7-29' if r[3] < 30 else '30-89' if r[3] < 90 else '90+') for r in L)
        print('pay', ch, len(L), sorted(c.items()), dict(stat[ch]))
    for ch, L in NP.items():
        c = collections.Counter((r[2], '<1' if r[3] < 1 else '1-6' if r[3] < 7 else '7-29' if r[3] < 30 else '30-89') for r in L)
        print('np', ch, len(L), sorted(c.items()), dict(NPSTAT[ch]))

if __name__ == '__main__':
    main()

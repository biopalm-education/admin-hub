# -*- coding: utf-8 -*-
"""v4 metrics: 4-stage course funnel, identical on Facebook / Instagram / LINE.

Run from the repo root after unpack.py (needs src/). Idempotent: rewrites the
per-chat stage fields and src/agg.json["v4"]. Then run build.py to re-encrypt.

Stage per chat (highest reached in that month's file):
  W ปิดการขาย    slip-check reply "สถานะ: ตรวจสอบสลิปสำเร็จ" whose receiver is
                 บจก. ไบโอปาล์ม เอ็ดดูเคชั่น / BIOPALM EDUCATION (one count per เลขอ้างอิง)
  Q ส่งราคาแล้ว  our side (admin typed or saved reply, never the LINE bot) sent a price,
                 "ค่าเรียน <n>", "ยอดชำระ" or the BioPalm account number
  T คุยแล้ว      customer typed something real, no price yet
  V ทักแล้วหาย   customer only pressed buttons / greetings / stickers
  X G S          not counted: no customer message · giveaway · LINE support for existing students
Intent: A = stated a grade AND asked about course/price/schedule · B = typed for real · C = neither
First reply (minutes): customer's first message in the month -> first message a human admin TYPED
after it (FB/IG role 1 · LINE named admin; saved replies and bots never count); -1 = no admin ever typed after.
Speed buckets: 0 <=5 min · 1 5-60 min · 2 >60 min · 3 no admin reply.
Fields: FB/IG chat rows r[37]=stage r[38]=intent r[39]=baht r[40]=first reply min · LINE rooms sg / it / rv / fr
"""
import json, glob, re

BTN = set(['สนใจลงเรียน ม.ต้น','สนใจลงเรียน ม.ปลาย','สอบถามตารางเรียนทั้งม.ต้น และม.ปลาย','สนใจคอร์สเตรียม สอวน.','สนใจลงเรียนคอร์ส ม.ต้น','ค่าเรียนเท่าไร','สนใจคอร์สพื้นฐานชีวะ ม.4','สนใจคอร์สพื้นฐานชีวะ ม.5','สนใจคอร์สพื้นฐานชีวะ ม.6','สนใจคอร์สเตรียม สอวน. ชีวะค่าย1','มีโปรโมชั่นหรือไม่','ชำระเงินแบบไหนได้บ้าง','หลักสูตรเรียนชีววิทยามีราคาเท่าไร?','ชำระเงินได้อย่างไร','คอร์สเรียนมีราคาเท่าไร','มีคอร์สเรียนอะไรบ้าง','รายละเอียดคอร์ส','รายละเอียด','สมัครเรียน','คอร์ส ม.ต้น','คอร์ส ม.ปลาย','ยืนยันการลงทะเบียน','เทป RERUN','คอร์สทั้งหมด','Online : Google meet','ช่วยแนะนำคอร์สเรียน','Onsite','Online','เชื่อมต่อบัญชีธนาคารของคุณเพื่อตรวจสอบความถูกต้องของสลิป','Connect your bank account to validate slips.',
 '▶ กดปุ่ม','โปรโมชั่น','ติดต่อแอดมิน','ต้องการติดต่อแอดมิน','Onsite สด','วิธีการสมัครเรียน','คอร์สเรียนทั้งหมด','คอร์ส ONLINE','แผนการเรียน ม.ต้น','สอบถามรายละเอียด','วิธีการเข้าเรียนย้อนหลัง','ขั้นตอนการเข้าเรียน','[รูปภาพ]','[สติกเกอร์]','(emoji)','[ไฟล์]','[รูป/ไฟล์แนบ]'])
LOW = re.compile(r'^[\s\.\,!?~😊🙏❤️👍🥰💕❣️🏻]*(สวัสดี|หวัดดี|ขอบคุณ|สนใจ|ค่ะ|คะ|ครับ|คับ|ค่า|ok|โอเค|รับทราบ|จ้า|ใช่|ได้)?\s*(ค่ะ|คะ|ครับ|คับ|ค่า|นะคะ|นะครับ|มากค่ะ|มากครับ|มาก|จ้า)?[\s\.\,!?~😊🙏❤️👍🥰💕❣️🏻]*$', re.I)
SLIP = re.compile(r'สถานะ\s*[:：]\s*ตรวจสอบสลิปสำเร็จ')
RCV = re.compile(r'ชื่อผู้รับ\s*[:：]\s*(บจก\.?\s*ไบโอปาล์ม|BIOPALM)', re.I)
REF = re.compile(r'เลขอ้างอิง\s*[:：]\s*(\S+)')
AMT = re.compile(r'ยอดเงิน\s*[:：]\s*([\d,]+\.?\d*)')
PRICE = re.compile(r'\d{1,3},\d{3}\s*(บาท|฿|\.-)|\d{4,5}\s*(บาท|฿|\.-)|ยอดชำระ|ค่าเรียน\s*[:：]?\s*\d|166-?3-?63464-?6|ราคา\s*[:：]?\s*\d')
GRADE = re.compile(r'ม\.?\s?[1-6]|ป\.?\s?[1-6]|ม\.ต้น|ม\.ปลาย|มัธยม|ประถม|ซิ่ว|ปี\s?[1-4]')
ASK = re.compile(r'คอร์ส|ราคา|ค่าเรียน|สมัคร|เท่าไร|เท่าไหร่|กี่บาท|โปร|ตาราง|ลงเรียน|สอวน|IJSO|A-?Level|สอบเข้า|MWIT|KVIS|เตรียมอุดม|onsite|online|ออนไลน์|เรียนสด|เทป', re.I)
SUPPORT = re.compile(r'ลิ้ง|ลิงก์|ลิงค์|เข้าเรียน|ย้อนหลัง|e-?mail|อีเมล|ชีท|เอกสาร|เลื่อน|ลาเรียน|ดูคลิป|รหัสผ่าน|password|ใบเสร็จ|ใบกำกับ', re.I)
TOPIC = re.compile(r'สนใจ|เรียน|รายละเอียด|เตรียมสอบ|โมดูล|module|ตอร์ส|คอส|ครอส|จอง|มต้น|มปลาย|ติว', re.I)
SEEN = set()

def slips(texts):
    out = {}
    for t in texts:
        if SLIP.search(t) or RCV.search(t):
            rf = REF.search(t); a = AMT.search(t)
            out[rf.group(1) if rf else t[:80]] = float(a.group(1).replace(',', '')) if a else 0.0
    return out

def judge(cus, ours, slip_texts, src=None):
    w = {k: v for k, v in slips(slip_texts).items() if k not in SEEN}
    SEEN.update(w.keys())
    sub = [t for t in cus if t and t not in BTN and not LOW.match(t)]
    j = ' '.join(sub)
    intent = 'A' if (GRADE.search(j) and ASK.search(j)) else ('B' if sub else 'C')
    quoted = any(PRICE.search(t) for t in ours)
    if w: st = 'W'
    elif not cus: st = 'X'
    elif not sub: st = 'V'
    elif quoted: st = 'Q'
    else: st = 'T'
    if st == 'T' and src not in ('ad', 'comment'):
        allc = ' '.join(cus)
        course = ASK.search(allc) or GRADE.search(allc) or TOPIC.search(allc)
        if not course or (SUPPORT.search(allc) and not ASK.search(allc)):
            st = 'O'   # typed for real, but not about a course (support, freebies, homework, activity...) -> other topic
    return st, intent, round(sum(w.values()))

EDGES = [1, 2, 3, 5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240, 360, 480, 720, 1080, 1440, 2880]

def bucket(fr):
    return 3 if fr is None or fr < 0 else (0 if fr <= 5 else (1 if fr <= 60 else 2))

SYS = re.compile(r'^\x01|คุณกำลังตอบกลับความคิดเห็น|replied to a post|ได้ตอบกลับโพสต์|ตอบกลับโฆษณา$')

def sysmsg(t):
    return bool(SYS.search(str(t or '')))

def first_reply(seq):
    """seq: [(minute, is_customer, is_human_admin)] in order"""
    c0 = next((m for m, c, h in seq if c), None)
    if c0 is None: return None
    a = next((m for m, c, h in seq if h and m >= c0), None)
    return -1 if a is None else int(a - c0)

def line_min(t):
    import datetime
    try:
        d = datetime.datetime.strptime('2026-' + t, '%Y-%m-%d %H:%M')
        return int(d.timestamp() // 60)
    except Exception:
        return None

def blank():
    return {'L': 0, 'V': 0, 'T': 0, 'Q': 0, 'W': 0, 'rev': 0, 'X': 0, 'G': 0, 'S': 0, 'O': 0, 'NA': 0, 'threads': 0,
            'I': {'A': [0, 0, 0], 'B': [0, 0, 0], 'C': [0, 0, 0]}, 'src': {},
            'rt': {'bins': [0] * (len(EDGES) + 1), 'b': [0, 0, 0, 0], 'mx': {k: [[0, 0] for _ in range(4)] for k in 'ABC'}}}

def tally(o, st, intent, rev, src=None, fr=None):
    o['threads'] += 1
    s = o['src'].setdefault(src, {'all': 0, 'L': 0, 'V': 0, 'T': 0, 'Q': 0, 'W': 0, 'rev': 0, 'O': 0, 'NA': 0, 'X': 0}) if src else None
    if s: s['all'] += 1
    if st != 'X' and (fr is None or fr < 0):
        o['NA'] += 1
        if s: s['NA'] += 1
    if st in ('X', 'G', 'S', 'O'):
        o[st] += 1
        if s: s['X' if st == 'X' else 'O'] += 1
        return
    b = bucket(fr); rt = o['rt']; rt['b'][b] += 1
    cell = rt['mx'][intent][b]; cell[0] += 1; cell[1] += st == 'W'
    if b != 3:
        rt['bins'][next((i for i, e in enumerate(EDGES) if fr < e), len(EDGES))] += 1
    o['L'] += 1; o[st] += 1; o['rev'] += rev
    i = o['I'][intent]; i[0] += 1; i[1] += st in ('Q', 'W'); i[2] += st == 'W'
    if s:
        s['L'] += 1; s[st] += 1; s['rev'] += rev

def tx_of(d):
    return lambda x: d[x] if isinstance(x, int) and 0 <= x < len(d) else (x if isinstance(x, str) else '')

def load(p):
    try: return json.load(open(p, encoding='utf-8'))
    except FileNotFoundError: return None

agg = load('src/agg.json'); ig = load('src/ig_all.json')
v4 = {'fb': {}, 'ig': {}, 'line': {}}
months = sorted(set([p[-12:-5] for p in glob.glob('src/fb_*.json')] + [p[-12:-5] for p in glob.glob('src/line_*.json')] + list(ig['months'].keys())))
for mo in months:   # chronological, so a slip already counted is never counted again later
    p = 'src/fb_%s.json' % mo; f = load(p)
    if f:
        tx = tx_of(f['dict']); o = blank()
        for c in f['chats']:
            while len(c) < 40: c.append(None)
            cus = [str(tx(m[2])).strip() for m in c[18] if m[1] == 0]
            ours = [str(tx(m[2])) for m in c[18] if m[1] in (1, 2)]
            st, it, rev = judge(cus, ours, ours + cus, c[26])
            if c[1] == 'G' and st != 'W': st = 'G'
            fr = first_reply([(m[0], m[1] == 0 and not sysmsg(tx(m[2])), m[1] == 1 and not sysmsg(tx(m[2]))) for m in c[18]])
            if (fr is None or fr < 0) and len(c) > 44 and c[44] is not None: fr = c[44]   # admin replied next month (stitch.py)
            c[37], c[38], c[39] = st, it, rev
            while len(c) < 41: c.append(None)
            c[40] = fr
            tally(o, st, it, rev, c[26] or 'organic', fr)
        v4['fb'][mo] = o
        json.dump(f, open(p, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
        del f
    if mo in ig['months']:
        tx = tx_of(ig['dict']); o = blank()
        for c in ig['months'][mo]['leads']:
            while len(c) < 40: c.append(None)
            cus = [str(tx(m[2])).strip() for m in c[18] if m[1] == 0]
            ours = [str(tx(m[2])) for m in c[18] if m[1] in (1, 2)]
            st, it, rev = judge(cus, ours, ours + cus, c[26])
            if c[1] == 'G' and st != 'W': st = 'G'
            fr = first_reply([(m[0], m[1] == 0 and not sysmsg(tx(m[2])), m[1] == 1 and not sysmsg(tx(m[2]))) for m in c[18]])
            if (fr is None or fr < 0) and len(c) > 44 and c[44] is not None: fr = c[44]   # admin replied next month (stitch.py)
            c[37], c[38], c[39] = st, it, rev
            while len(c) < 41: c.append(None)
            c[40] = fr
            tally(o, st, it, rev, c[26] or 'organic', fr)
        v4['ig'][mo] = o
    p = 'src/line_%s.json' % mo; f = load(p)
    if f:
        tx = tx_of(f['dict']); o = blank(); adm = {}
        for r in f['rooms']:
            tr = [(m[1], str(tx(m[2]))) for m in r['tr']]
            cus = [t.strip() for s, t in tr if s == 'C']
            ours = [t for s, t in tr if s not in ('C', 'B')]
            st, it, rev = judge(cus, ours, [t for s, t in tr if s != 'C'] + cus)
            if st in ('V', 'T') and SUPPORT.search(' '.join(cus)) and not ASK.search(' '.join(t for t in cus if t not in BTN)):
                st = 'S'
            seq = [(line_min(m[0]), m[1] == 'C', m[1] not in ('C', 'B')) for m in r['tr']]
            seq = [x for x in seq if x[0] is not None]
            fr = first_reply(seq)
            r['sg'], r['it'], r['rv'], r['fr'] = st, it, rev, fr
            tally(o, st, it, rev, None, fr)
            humans = [s for s, t in tr if s not in ('C', 'B')]
            for a in set(humans):
                adm.setdefault(a, {'rooms': 0, 'Q': 0, 'W': 0, 'rev': 0, 'msgs': 0})['rooms'] += 1
            for a in humans: adm[a]['msgs'] += 1
            if st in ('Q', 'W'):
                qa = next((s for s, t in tr if s not in ('C', 'B') and PRICE.search(t)), None)
                if qa: adm[qa]['Q'] += 1
            if st == 'W':
                cut = next((i for i, (s, t) in enumerate(tr) if SLIP.search(t)), len(tr))
                before = [s for s, t in tr[:cut] if s not in ('C', 'B')]
                cred = before[-1] if before else (humans[-1] if humans else None)
                if cred: adm[cred]['W'] += 1; adm[cred]['rev'] += rev
        o['adm'] = sorted([[k, v['rooms'], v['Q'], v['W'], v['rev'], v['msgs']] for k, v in adm.items()], key=lambda x: -x[1])
        v4['line'][mo] = o
        json.dump(f, open(p, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
        del f
json.dump(ig, open('src/ig_all.json', 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
agg['v4'] = v4
json.dump(agg, open('src/agg.json', 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
agg['v4edges'] = EDGES
json.dump(agg, open('src/agg.json', 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
for ch in v4:
    for mo, o in sorted(v4[ch].items()):
        print(ch, mo, 'speed', o['rt']['b'], 'A', o['rt']['mx']['A'])
        print(ch, mo, 'L', o['L'], 'V', o['V'], 'T', o['T'], 'Q', o['Q'], 'W', o['W'], 'rev', o['rev'], 'X', o['X'], 'S', o['S'], 'G', o['G'], o.get('adm', '')[:3] if ch == 'line' else '')


# ---------------- SPEED TABLES (admin-hub "ความเร็วตอบแชท") ----------------
# Per channel-month, funnel chats only (V/T/Q/W), keyed by when the customer's first message arrived (Thai time):
#   sp.b   5 buckets [chats, closed]: <15 · 15-30 · 30-60 · >60 min · no admin typed reply
#   sp.s   3 shifts 09-21 / 21-24 / 00-09: {n, w, b[5], bins[len(EDGES)+1]}
#   sp.bins first-reply histogram on EDGES (for medians) · sp.hr 24 hours x 9 counts, flattened:
#          <5, <15, <30, <=60, <120, <240, <480, >=480 min, no admin reply
def sp_bucket(fr):
    return 4 if fr is None or fr < 0 else (0 if fr < 15 else (1 if fr < 30 else (2 if fr <= 60 else 3)))
def hr_idx(fr):
    if fr is None or fr < 0: return 8
    for i, e in enumerate([5, 15, 30]):
        if fr < e: return i
    if fr <= 60: return 3
    for i, e in enumerate([120, 240, 480]):
        if fr < e: return 4 + i
    return 7
def shift_of(mod):
    h = mod // 60
    return 0 if 9 <= h < 21 else (1 if h >= 21 else 2)
def sp_blank():
    return {'b': [[0, 0] for _ in range(5)], 's': [{'n': 0, 'w': 0, 'b': [0] * 5, 'bins': [0] * (len(EDGES) + 1)} for _ in range(3)],
            'bins': [0] * (len(EDGES) + 1), 'hr': [0] * 216}
def sp_add(o, fr, mod, won):
    b = sp_bucket(fr); o['b'][b][0] += 1; o['b'][b][1] += won
    sh = o['s'][shift_of(mod)]; sh['n'] += 1; sh['w'] += won; sh['b'][b] += 1
    if b != 4:
        i = next((i for i, e in enumerate(EDGES) if fr < e), len(EDGES)); o['bins'][i] += 1; sh['bins'][i] += 1
    o['hr'][(mod // 60) * 9 + hr_idx(fr)] += 1

agg = load('src/agg.json')
for p in sorted(glob.glob('src/fb_*.json')):
    mo = p[-12:-5]; f = load(p); tx = tx_of(f['dict']); o = sp_blank()
    for c in f['chats']:
        if c[37] not in ('V', 'T', 'Q', 'W'): continue
        c0 = next((m[0] for m in c[18] if m[1] == 0 and not sysmsg(tx(m[2]))), None)
        if c0 is not None: sp_add(o, c[40], c0 % 1440, c[37] == 'W')
    agg['v4']['fb'][mo]['sp'] = o
ig = load('src/ig_all.json'); tx = tx_of(ig['dict'])
for mo, d in ig['months'].items():
    o = sp_blank()
    for c in d['leads']:
        if c[37] not in ('V', 'T', 'Q', 'W'): continue
        c0 = next((m[0] for m in c[18] if m[1] == 0 and not sysmsg(tx(m[2]))), None)
        if c0 is not None: sp_add(o, c[40], c0 % 1440, c[37] == 'W')
    agg['v4']['ig'][mo]['sp'] = o
for p in sorted(glob.glob('src/line_*.json')):
    mo = p[-12:-5]; f = load(p); o = sp_blank()
    for r in f['rooms']:
        if r.get('sg') not in ('V', 'T', 'Q', 'W'): continue
        t = next((m[0] for m in r['tr'] if m[1] == 'C'), None)
        if t:
            hh, mm = t.split(' ')[1].split(':'); sp_add(o, r.get('fr'), int(hh) * 60 + int(mm), r['sg'] == 'W')
    agg['v4']['line'][mo]['sp'] = o
json.dump(agg, open('src/agg.json', 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
print('speed tables', {ch: sorted(agg['v4'][ch].keys())[-1] + ' ' + str(agg['v4'][ch][sorted(agg['v4'][ch].keys())[-1]]['sp']['b']) for ch in agg['v4']})

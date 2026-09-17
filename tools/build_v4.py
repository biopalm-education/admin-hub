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
Fields: FB/IG chat rows r[37]=stage r[38]=intent r[39]=baht · LINE rooms sg / it / rv
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
SEEN = set()

def slips(texts):
    out = {}
    for t in texts:
        if SLIP.search(t) and RCV.search(t):
            rf = REF.search(t); a = AMT.search(t)
            out[rf.group(1) if rf else t[:80]] = float(a.group(1).replace(',', '')) if a else 0.0
    return out

def judge(cus, ours, slip_texts):
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
    return st, intent, round(sum(w.values()))

def blank():
    return {'L': 0, 'V': 0, 'T': 0, 'Q': 0, 'W': 0, 'rev': 0, 'X': 0, 'G': 0, 'S': 0, 'threads': 0,
            'I': {'A': [0, 0, 0], 'B': [0, 0, 0], 'C': [0, 0, 0]}, 'src': {}}

def tally(o, st, intent, rev, src=None):
    o['threads'] += 1
    if st in ('X', 'G', 'S'):
        o[st] += 1; return
    o['L'] += 1; o[st] += 1; o['rev'] += rev
    i = o['I'][intent]; i[0] += 1; i[1] += st in ('Q', 'W'); i[2] += st == 'W'
    if src:
        s = o['src'].setdefault(src, {'L': 0, 'V': 0, 'T': 0, 'Q': 0, 'W': 0, 'rev': 0})
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
            if c[1] == 'G':
                c[37], c[38], c[39] = 'G', 'C', 0; tally(o, 'G', 'C', 0); continue
            cus = [str(tx(m[2])).strip() for m in c[18] if m[1] == 0]
            ours = [str(tx(m[2])) for m in c[18] if m[1] in (1, 2)]
            st, it, rev = judge(cus, ours, ours + cus)
            c[37], c[38], c[39] = st, it, rev
            tally(o, st, it, rev, c[26] or 'organic')
        v4['fb'][mo] = o
        json.dump(f, open(p, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
        del f
    if mo in ig['months']:
        tx = tx_of(ig['dict']); o = blank()
        for c in ig['months'][mo]['leads']:
            while len(c) < 40: c.append(None)
            cus = [str(tx(m[2])).strip() for m in c[18] if m[1] == 0]
            ours = [str(tx(m[2])) for m in c[18] if m[1] in (1, 2)]
            st, it, rev = judge(cus, ours, ours + cus)
            c[37], c[38], c[39] = st, it, rev
            tally(o, st, it, rev, c[26] or 'organic')
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
            r['sg'], r['it'], r['rv'] = st, it, rev
            tally(o, st, it, rev)
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
for ch in v4:
    for mo, o in sorted(v4[ch].items()):
        print(ch, mo, 'L', o['L'], 'V', o['V'], 'T', o['T'], 'Q', o['Q'], 'W', o['W'], 'rev', o['rev'], 'X', o['X'], 'S', o['S'], 'G', o['G'], o.get('adm', '')[:3] if ch == 'line' else '')

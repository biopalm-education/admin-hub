# -*- coding: utf-8 -*-
"""v5: split the old "ทักมาแล้วหาย · กดปุ่ม" bucket (V) into

  V  ทักมาแล้วหาย   customer pressed ONLY ad buttons that Meta itself tagged
                    "ตอบกลับโฆษณา", typed nothing at all, pressed no menu button,
                    sent no image/sticker, and stayed silent for the whole window
  H  ทักทาย/กดเมนู  everything else that used to sit in V (menu buttons, greetings,
                    images, or an ad-looking text Meta never confirmed)
  F  is not a stage — a chat that came back inside the window simply lands in H

Two windows are produced: 14 days (default, "ข้อมูลล่าสุด") and 30 days
("ข้อมูลย้อนหลัง").  agg['v4'] carries the 14-day tally, agg['v4w30'] the 30-day one.
Instagram and LINE never get V: neither channel carries the Meta ad tag, so the
dashboard shows "—" for them.

Run AFTER build_v4.py, BEFORE build.py.  Idempotent.
"""
import json, glob, re, collections, datetime, bisect, copy

MARK  = re.compile(r'ตอบกลับโฆษณา')
LOW   = re.compile(r'^[\s\.\,!?~😊🙏❤️👍🥰💕❣️🏻]*(สวัสดี|หวัดดี|ขอบคุณ|ขอบคุน|ค่ะ|คะ|ครับ|คับ|ค่า|ok|โอเค|รับทราบ|จ้า|ใช่|ได้|เรียบร้อย)?\s*(ค่ะ|คะ|ครับ|คับ|ค่า|นะคะ|นะครับ|มากค่ะ|มากครับ|มาก|จ้า|ะ|บ)?[\s\.\,!?~😊🙏❤️👍🥰💕❣️🏻]*$', re.I)
MEDIA = set(['[รูป/ไฟล์แนบ]','[รูปภาพ]','[สติกเกอร์]','(emoji)','[ไฟล์]','[ไฟล์แนบ]',
             '[ตอบกลับสตอรี่]','[ข้อความที่ IG ไม่รองรับ]','[วิดีโอ]','[เสียง]',''])
AD_CORE = set(['สนใจลงเรียน ม.ต้น','สนใจลงเรียน ม.ปลาย','สอบถามตารางเรียนทั้งม.ต้น และม.ปลาย',
 'สนใจลงเรียนคอร์ส ม.ต้น','สนใจคอร์สเตรียม สอวน.','สนใจคอร์สเตรียม สอวน. ชีวะค่าย1',
 'สนใจคอร์สพื้นฐานชีวะ ม.4','สนใจคอร์สพื้นฐานชีวะ ม.5','สนใจคอร์สพื้นฐานชีวะ ม.6',
 'ค่าเรียนเท่าไร','มีโปรโมชั่นหรือไม่','ชำระเงินแบบไหนได้บ้าง','ชำระเงินได้อย่างไร',
 'หลักสูตรเรียนชีววิทยามีราคาเท่าไร?','คอร์สเรียนมีราคาเท่าไร','มีคอร์สเรียนอะไรบ้าง','ช่วยแนะนำคอร์สเรียน'])
MENU = set(['รายละเอียดคอร์ส','รายละเอียด','ยืนยันการลงทะเบียน','คอร์ส ม.ต้น','คอร์ส ม.ปลาย','สมัครเรียน',
 'โปรโมชั่น','ติดต่อแอดมิน','ต้องการติดต่อแอดมิน','Onsite สด','Onsite','Online','Online : Google meet',
 'เทป RERUN','คอร์สทั้งหมด','คอร์สเรียนทั้งหมด','คอร์ส ONLINE','วิธีการสมัครเรียน','วิธีการเข้าเรียนย้อนหลัง',
 'ขั้นตอนการเข้าเรียน','แผนการเรียน ม.ต้น','สอบถามรายละเอียด','เมนูหลัก','▶ กดปุ่ม',
 'เชื่อมต่อบัญชีธนาคารของคุณเพื่อตรวจสอบความถูกต้องของสลิป','Connect your bank account to validate slips.',
 'คอร์สม.ต้น','คอร์สม.ปลาย'])
WINS = (14, 30)
DEFAULT_WIN = 14

def kind(s):
    if s in AD_CORE: return 'ad'
    if s in MENU:    return 'menu'
    if s in MEDIA:   return 'media'
    if LOW.match(s): return 'low'
    return 'real'
def tx_of(d):
    return lambda x: d[x] if isinstance(x, int) and 0 <= x < len(d) else (x if isinstance(x, str) else '')
def load(p):
    try: return json.load(open(p, encoding='utf-8'))
    except FileNotFoundError: return None
def base(mo):
    y, m = int(mo[:4]), int(mo[5:7])
    return int((datetime.datetime(y, m, 1) - datetime.datetime(2026, 1, 1)).total_seconds() // 60)

FBM = sorted(p[-12:-5] for p in glob.glob('src/fb_*.json'))
agg = load('src/agg.json'); ig = load('src/ig_all.json')

# ---- pass 1: when did each thread next get a REAL typed customer message ----
realt = collections.defaultdict(list); END = [0]
def scan(tid, msgs, t, b):
    for m in msgs:
        END[0] = max(END[0], b + m[0])
        if m[1] == 0 and kind(str(t(m[2])).strip()) == 'real': realt[tid].append(b + m[0])
for mo in FBM:
    f = load('src/fb_%s.json' % mo); t = tx_of(f['dict']); b = base(mo)
    for c in f['chats']: scan('F' + str(c[19]), c[18], t, b)
    del f
tg = tx_of(ig['dict'])
for mo, blk in ig['months'].items():
    b = base(mo)
    for c in blk['leads']: scan('I' + str(c[19]), c[18], tg, b)
for k in realt: realt[k].sort()
def gap_of(tid, after):
    a = realt.get(tid)
    if not a: return None
    i = bisect.bisect_right(a, after)
    return (a[i] - after) if i < len(a) else None

# ---- pass 2: reclassify ----
def judge5(ch, c, t, b):
    """-> (stage_by_window {14:st,30:st}, pending {14:bool,30:bool})"""
    st = c[37]
    if st != 'V':                       # only the old V bucket is being re-cut
        return {w: st for w in WINS}, {w: False for w in WINS}
    if ch != 'fb':                      # IG/LINE carry no Meta ad tag
        return {w: 'H' for w in WINS}, {w: False for w in WINS}
    ms = [(m[0], m[1], str(t(m[2])).strip()) for m in c[18]]
    ks = [(mi, s, kind(s)) for mi, r, s in ms if r == 0]
    marked = 0
    for i, (mi, r, s) in enumerate(ms):
        if r != 0 or s not in AD_CORE: continue
        prev = [x for x in ms[max(0, i - 4):i] if x[1] != 0 and MARK.search(x[2])]
        if prev and 0 <= mi - prev[-1][0] <= 2: marked += 1
    pure = marked > 0 and not any(k in ('menu', 'media', 'low', 'real') for _, _, k in ks)
    if not pure:
        return {w: 'H' for w in WINS}, {w: False for w in WINS}
    lastb = max([mi for mi, _, k in ks if k in ('ad', 'menu')], default=None)
    gap = gap_of('F' + str(c[19]), b + lastb) if lastb is not None else None
    out, pend = {}, {}
    for w in WINS:
        out[w]  = 'V' if (gap is None or gap > w * 1440) else 'F'
        pend[w] = (lastb is not None and b + lastb + w * 1440 > END[0])
    return out, pend

# ---- tally (same shape as build_v4, plus H, and NA no longer counts V) ----
EDGES = agg.get('v4edges') or [1,2,3,5,10,15,20,30,45,60,90,120,180,240,360,480,720,1080,1440,2880]
def bucket(fr): return 3 if fr is None or fr < 0 else (0 if fr <= 5 else (1 if fr <= 60 else 2))
def blank():
    return {'L':0,'V':0,'H':0,'F':0,'T':0,'Q':0,'W':0,'rev':0,'X':0,'G':0,'S':0,'O':0,'NA':0,'P':0,'threads':0,
            'I':{'A':[0,0,0],'B':[0,0,0],'C':[0,0,0]},'src':{},
            'rt':{'bins':[0]*(len(EDGES)+1),'b':[0,0,0,0],'mx':{k:[[0,0] for _ in range(4)] for k in 'ABC'}}}
def tally(o, st, intent, rev, src=None, fr=None, pend=False):
    o['threads'] += 1
    s = o['src'].setdefault(src, {'all':0,'L':0,'V':0,'H':0,'F':0,'T':0,'Q':0,'W':0,'rev':0,'O':0,'NA':0,'X':0}) if src else None
    if s: s['all'] += 1
    if st not in ('X', 'V') and (fr is None or fr < 0):
        o['NA'] += 1
        if s: s['NA'] += 1
    if st == 'V' and pend: o['P'] += 1
    if st in ('X', 'G', 'S', 'O'):
        o[st] += 1
        if s: s['X' if st == 'X' else 'O'] += 1
        return
    b = bucket(fr); rt = o['rt']; rt['b'][b] += 1
    cell = rt['mx'][intent][b]; cell[0] += 1; cell[1] += st == 'W'
    if b != 3:
        rt['bins'][next((i for i, e in enumerate(EDGES) if fr < e), len(EDGES))] += 1
    o['L'] += 1; o[st] += 1; o['rev'] += rev
    i = o['I'][intent]; i[0] += 1; i[1] += st in ('Q','W'); i[2] += st == 'W'
    if s:
        s['L'] += 1; s[st] += 1; s['rev'] += rev

OUT = {w: {'fb': {}, 'ig': {}, 'line': {}} for w in WINS}
months = sorted(set(FBM + [p[-12:-5] for p in glob.glob('src/line_*.json')] + list(ig['months'].keys())))
for mo in months:
    p = 'src/fb_%s.json' % mo; f = load(p)
    if f:
        t = tx_of(f['dict']); b = base(mo); o = {w: blank() for w in WINS}
        for c in f['chats']:
            while len(c) < 44: c.append(None)
            sts, pend = judge5('fb', c, t, b)
            c[37] = sts[DEFAULT_WIN]
            c[41] = sts[30]; c[42] = 1 if pend[14] else 0; c[43] = 1 if pend[30] else 0
            for w in WINS: tally(o[w], sts[w], c[38], c[39], c[26] or 'organic', c[40], pend[w])
        for w in WINS: OUT[w]['fb'][mo] = o[w]
        json.dump(f, open(p, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
        del f
    if mo in ig['months']:
        b = base(mo); o = {w: blank() for w in WINS}
        for c in ig['months'][mo]['leads']:
            while len(c) < 44: c.append(None)
            sts, pend = judge5('ig', c, tg, b)
            c[37] = sts[DEFAULT_WIN]; c[41] = sts[30]; c[42] = 0; c[43] = 0
            for w in WINS: tally(o[w], sts[w], c[38], c[39], c[26] or 'organic', c[40], False)
        for w in WINS: OUT[w]['ig'][mo] = o[w]
    p = 'src/line_%s.json' % mo; f = load(p)
    if f:
        o = {w: blank() for w in WINS}
        for r in f['rooms']:
            st = 'H' if r.get('sg') == 'V' else r.get('sg')
            r['sg'] = st; r['sg30'] = st
            for w in WINS: tally(o[w], st, r.get('it') or 'C', r.get('rv') or 0, None, r.get('fr'), False)
        old = ((agg.get('v4') or {}).get('line') or {}).get(mo) or {}
        for w in WINS:
            if old.get('adm'): o[w]['adm'] = old['adm']
            OUT[w]['line'][mo] = o[w]
        json.dump(f, open(p, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
        del f

json.dump(ig, open('src/ig_all.json', 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
agg['v4'] = OUT[DEFAULT_WIN]
agg['v4w30'] = OUT[30]
agg['v4win'] = DEFAULT_WIN
agg['v4end'] = END[0]
agg['v4edges'] = EDGES
json.dump(agg, open('src/agg.json', 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)

for w in WINS:
    tot = collections.Counter()
    for ch in OUT[w]:
        for mo, o in OUT[w][ch].items():
            for k in ('V','H','F','T','Q','W','NA','P','L','threads'): tot[k] += o[k]
    print('W=%2d  V %5d  H %5d  F %4d  T %5d  Q %5d  W %4d  NA %5d  รอครบ %4d  L %6d  แชท %6d'
          % (w, tot['V'], tot['H'], tot['F'], tot['T'], tot['Q'], tot['W'], tot['NA'], tot['P'], tot['L'], tot['threads']))
print('ข้อมูลล่าสุด', (datetime.datetime(2026,1,1)+datetime.timedelta(minutes=END[0])).strftime('%Y-%m-%d %H:%M'))

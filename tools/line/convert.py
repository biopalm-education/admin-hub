# -*- coding: utf-8 -*-
"""Raw LINE events -> room rows in the mk_line.py payload format.
Port of the browser converter that reproduced the published May 2026 data byte-for-byte.
raw event = [ts_ms, role, bizId, msgType, text]; role c=customer p=postback a=sent f=follow u=unfollow"""
import datetime
TZ = datetime.timezone(datetime.timedelta(hours=7))
OWN = {"eb20c13e-704a-4ebb-8a4f-120827eff324": "Admin", "9465f64a-5032-4c87-9991-e21a9ca8e0c6": "K_kosol",
       "da775e00-3f7a-11ee-805d-d62662ffd727": "PPALM", "a0cbc6b7-12a1-4a6d-b179-dd53a87b8a35": "ARM",
       "c277a0b0-8b5d-11e9-b5ee-fa163e3af8d6": "BGs", "2082a0bb-78b8-4e3f-be2b-4460ad2c584f": "Gambumm",
       "1f94e460-3e87-11ea-bd9a-fa163eaabe5f": "NR", "099fd731-aab3-4a09-9892-334b6b9b3096": "PAT",
       "aa9d8310-a1a4-11eb-8e96-163d0215afca": "Miew",
       # แอดมินใหม่ ต.ค. 2026 (I Yu กับ Samleee) — 26 พ.ย. 2026 ใช้ชื่อที่แสดงใน LINE ไปก่อนตามที่เจ้าของสั่ง
       # เจ้าของจะบอกภายหลังว่าชื่อ LINE ไหนคือแอดมินคนไหน · ตอนนั้นแก้ชื่อที่นี่ แล้วรัน
       # tools/line/rename_admin.py src 'Cookie 🩻=<ชื่อจริง>' 'U 🪐=<ชื่อจริง>' ให้เดือนที่อยู่ในแดชบอร์ดแล้วตามไปด้วย
       "eb9a60b3-8a84-41a2-ac87-78ba1b609ee2": "Cookie 🩻",   # ชื่อ LINE · เริ่ม 5 ต.ค. 2026 · กะ 17–21 น.
       "88b10bb9-c2a2-466a-9185-51def4f41536": "U 🪐"}        # ชื่อ LINE · เริ่ม 22 ต.ค. 2026 · กะ 10–14 น.
# 26 พ.ย. 2026: ชื่อจริงของรหัสที่เคยแสดงเป็นอีโมจิ 🚲 = NR · 🌙 = Miew (เจ้าของยืนยัน)
# PPALM (พี่ปาล์ม) และ BGs (พี่บอล) ยังนับเป็น "คน" ในระดับห้อง (ห้องนั้นมีคนตอบแล้ว) แต่หน้าเว็บไม่นับในผลงานรายแอดมิน (ADM_EXCL ใน app.html)
TAG = {"agh6cwvpsg4pwtlq75zlptukai": "Q-ยังไม่สมัคร", "agko5ii7gu5qj63kxff76no5ai": "คอร์ส สอวน.",
       "agko5ijoxjpchguvvo22uvzzai": "คอร์ส IJSO", "agko5io6w5ghmdhz5m4hg22uai": "คอร์สสอบเข้า ม.4",
       "aglwd5uhmy7serziqodvuy5wai": "Q-ถามกับระบบ", "aglwoifbzyfklszijzxo62c3ai": "คอร์สเนื้อหา ม.ต้น",
       "aglwoilotzbgv47q2fxidbudai": "คอร์สเนื้อหา ม.ปลาย", "aglwoio4f75cmlafspg6vjkuai": "คอร์ส A-Level",
       "agmeobfxgl3al2256ucsmcooai": "แก๊งค์---รวมอ่านเงียบ", "agmizo66nlddeql7vu5nu3ivai": "Q-สมัครแล้ว",
       "agmmvivqh7yjkaxfbkv5kmdfai": "แก๊งค์--รวมตอบกลับ", "agnngfs6snhl3o7briy7zvlgai": "คอร์ส LAB"}
PH = {'image': '[รูปภาพ]', 'sticker': '[สติกเกอร์]', 'file': '[ไฟล์]', 'video': '[วิดีโอ]', 'audio': '[เสียง]'}

def tl(t):
    return datetime.datetime.fromtimestamp(t / 1000, TZ).strftime('%m-%d %H:%M')

def fmt(s):
    if s is None: return '—'
    s2 = round(s)                      # Python round = banker's, same as the original pipeline
    return '%d วิ' % s2 if s2 < 60 else '%d นาที' % round(s2 / 60)

def st_of(tags):
    return ('สมัครแล้ว' if 'Q-สมัครแล้ว' in tags else 'ยังไม่สมัคร' if 'Q-ยังไม่สมัคร' in tags
            else 'ถามกับระบบ' if 'Q-ถามกับระบบ' in tags else 'ไม่ติดแท็ก')

def conv(x, lo=None, hi=None):
    tr, ts = [], []
    for t, r, bz, ty, tx in x['ev']:
        if lo is not None and not (lo <= t < hi): continue
        if r in ('f', 'u'): continue
        if r == 'c': w, txt = 'C', (tx if ty == 'text' else PH.get(ty, '[%s]' % ty))
        elif r == 'p': w, txt = 'C', '▶ กดปุ่ม'
        else: w, txt = (OWN.get(bz, 'B') if bz else 'B'), (tx if ty == 'text' else PH.get(ty, '[%s]' % ty))
        tr.append([tl(t), w, txt]); ts.append((t, w))
    if not tr: return None
    hum = lambda w: w not in ('C', 'B')
    admins = []
    for _, w, _ in tr:
        if hum(w) and w not in admins: admins.append(w)
    waits, p = [], None
    for t, w in ts:
        if w == 'C':
            if p is None: p = t
        elif hum(w) and p is not None:
            waits.append((t - p) / 1000); p = None
    tf, c0 = None, None
    for t, w in ts:
        if c0 is None and w == 'C': c0 = t
        elif c0 is not None and hum(w): tf = (t - c0) / 1000; break
    s = sorted(waits)
    tags = [TAG.get(i, i) for i in x.get('tg', [])]
    lastC = max([i for i, (_, w) in enumerate(ts) if w == 'C'], default=-1)
    lastH = max([i for i, (_, w) in enumerate(ts) if hum(w)], default=-1)
    c = sum(1 for _, w, _ in tr if w == 'C'); h = sum(1 for _, w, _ in tr if hum(w)); b = sum(1 for _, w, _ in tr if w == 'B')
    return {'name': x.get('nm', ''), 'id': x['id'], 'tags': tags, 'own': OWN.get(x.get('as')) if x.get('as') else None,
            'admins': admins, 'c': c, 'h': h, 'b': b, 'from': tr[0][0], 'to': tr[-1][0],
            'first': fmt(s[0] if s else None), 'med': fmt(s[len(s) // 2] if s else None), 'worst': fmt(s[-1] if s else None),
            'truefirst': None if tf is None else round(tf, 3), 'st': st_of(tags),
            'nohuman': c > 0 and h == 0, 'hanging': lastC > lastH and h > 0, 'tr': tr}

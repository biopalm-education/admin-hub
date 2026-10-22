# -*- coding: utf-8 -*-
"""Tracking · ข้อความแจ้งเตือนเข้า LINE กลุ่ม (21 ต.ค. 2026)

  จันทร์ = สรุปสัปดาห์ที่แล้ว (จ.–อา.) · ศุกร์ = ความคืบหน้าสัปดาห์นี้ (จ.–พฤ.)
  ส่งเป็นข้อความเดียว (บับเบิลเดียว) รวม Facebook / Instagram / LINE OA จัดกลุ่มตามหัวข้อ — combined()
  ข้อความแยกช่องทาง (msgs) ยังเก็บไว้ให้หน้า Tracking แสดงตัวอย่าง
  ตัวเลขนับจากไทม์ไลน์รายวันใน ba.json ด้วยกฎเดียวกับหน้า Tracking (ba.js: baEval / baCount / baStatus)

  drafts(BA)         build_week.py เรียกตอนสร้าง src/ba.json -> BA["notice"] (หน้า Tracking แสดงตัวอย่างข้อความ)
  notice.py show [src/ba.json]     พิมพ์ข้อความทั้งสองแบบ
  notice.py send     GitHub Actions (.github/workflows/line-notice.yml) หลัง refresh-dashboard ทุกรอบ
      env ADMIN_SECRET (ตัวเดิม ใช้ถอดรหัส data/ba.json) · LINE_NOTICE_TOKEN · LINE_NOTICE_TO · KIND · SEND
      KIND=auto ส่งเฉพาะจันทร์/ศุกร์ (เวลาไทย) และต้องเป็นข้อมูลที่สร้างวันนี้ · mon / fri = ใช้แบบนั้นทันที
      SEND=1 ส่งจริง · อย่างอื่น = เช็กว่าถอดรหัส/สร้างข้อความได้ ไม่ส่ง · log ไม่พิมพ์เนื้อหาข้อความ (repo เป็น public)
      ยังไม่ตั้ง LINE_NOTICE_TOKEN / LINE_NOTICE_TO = ไม่ส่ง · ส่งซ้ำวันเดียวกันไม่ได้ (X-Line-Retry-Key ต่อวัน)
"""
import os, sys, json, math, bisect, datetime, uuid, base64, gzip, hashlib, urllib.request, urllib.error

PAGE = 'https://biopalm-education.github.io/admin-hub/#ba'          # หน้า Tracking (หน้าจริง ตั้งแต่ 21 ต.ค. 2026)
FOOT = '📊 ดูหน้า Tracking: ' + PAGE                                # บรรทัดปิดท้ายของทุกข้อความ
LISTS = ('ar', 'sp', 'np', 'pay', 'pz')
DONE = ('ans', 'smp', 'sum', 'paid', 'close')
ACT = ('fu', 'reans', 'requote', 'move')
FROM = {'sp': '2026-08-19', 'np': '2026-08-19', 'pay': '2026-08-19'}     # stage_rules.SAMPLE_FROM
LN = {'ar': ('🤖', 'บอทตอบ'), 'sp': ('🎬', 'ยังไม่แนบตัวอย่าง'), 'np': ('🗨️', 'ยังไม่สรุปจ่าย'),
      'pay': ('💸', 'ยังไม่โอน · แนบตัวอย่าง'), 'pz': ('🧾', 'ยังไม่โอน · ไม่แนบตัวอย่าง')}
CHS = ('fb', 'ig', 'line')
CHN = {'fb': 'Facebook', 'ig': 'Instagram', 'line': 'LINE OA'}
CHI = {'fb': '🔵', 'ig': '🟣', 'line': '🟢'}
TH_M = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']
TH = datetime.timezone(datetime.timedelta(hours=7))
STATUS = {2: ('great', '🎉', 'ดีขึ้นชัดเจน'), 1: ('good', '👍', 'ดีขึ้น'), 0: ('flat', '➖', 'ทรงตัว'), -1: ('push', '💪', 'ต้องเร่งอีกนิด')}


# ---------- engine (same as ba.js) ----------
def jround(x):                       # JavaScript Math.round
    return int(math.floor(x + 0.5))


def nf(n):
    return '{:,}'.format(int(n))


def days_txt(v):
    if v is None: return '—'
    if v <= 1: return 'ภายใน 1 วัน'
    r = math.floor(v * 10 + 0.5) / 10
    return '~%s วัน' % (int(r) if r == int(r) else r)


def prep(BA):
    """working copy: each chat's timeline split into (index, cut indexes, codes) — ba.json itself is left untouched"""
    P = {'_d0': datetime.date.fromisoformat(BA['d0']), 'built': BA.get('built') or '', 'ch': {}}
    for ch, C in BA['ch'].items():
        P['ch'][ch] = {'end': C['end'], 'endK': C['n'] - 1, 'aw': C['aw'], 'mp': C['mp'], 'nm': C['nm'],
                       'it': {l: [(f[0], f[1::2], f[2::2]) for f in (C.get('L') or {}).get(l, [])] for l in LISTS}}
    return P


def kday(BA, d):
    return (d - BA['_d0']).days


def man_for(mp, ke, kb):
    if not mp: return None
    for x in reversed(mp):
        if x[0] > kb: continue
        if x[1] == 'u': return None
        if x[0] > ke: return x
        return None if (x[3] != -1 and x[3] <= kb) else 'drop'
    return None


def bucket(out, fl, man):
    if out in DONE: return 'done'
    if out in ACT or man: return 'act'
    if (fl & 4) and not out: return 'act'
    if out == 'aged': return 'aged'
    if out == 'x': return 'skip'
    return 'cus' if out == 'cus' else 'none'


def evaluate(C, lst, ka, kb):
    rows = []
    aw, mp, nm = C['aw'], C['mp'], C['nm']
    for i, ks, cs in C['it'][lst]:
        if ks[0] > kb: continue
        j = bisect.bisect_right(ks, ka) - 1
        c0 = cs[j] if j >= 0 else None
        ke = -1
        if c0 and c0[0] == '+': ke = ka
        else:
            q = j + 1
            while q < len(ks) and ks[q] <= kb:
                if cs[q][0] == '+': ke = ks[q]; break
                q += 1
        if ke < 0: continue
        m = man_for(mp[i], ke, kb)
        if m == 'drop': continue
        cb = cs[bisect.bisect_right(ks, kb) - 1]
        on1 = cb[0] == '+'; on0 = ke == ka
        who, adm, touch = [], False, -1
        for w in (aw[i] or []):
            if ke < w[0] <= kb:
                adm = True
                if touch < 0: touch = w[0]
                for z in w[1:]:
                    n = nm[z] if z < len(nm) else ''
                    if n and n not in who: who.append(n)
        mk = ''
        if m:
            mk = m[1]
            if m[2] >= 0:
                n = nm[m[2]] if m[2] < len(nm) else ''
                if n and n not in who: who.append(n)
            if touch < 0 or m[0] < touch: touch = m[0]
        fl = (1 if on0 else 8) | (2 if on1 else 0) | (4 if adm else 0)
        out = '' if on1 else cb
        rows.append({'fl': fl, 'b': bucket(out, fl, mk), 'man': mk, 'who': who, 'touch': touch - ke if touch >= 0 else -1})
    return rows


def median(a):
    if not a: return None
    s = sorted(a); m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2


def count(rows):
    c = dict(S=0, N=0, done=0, act=0, cus=0, none=0, skip=0, aged=0, E=0, tN=0, tT=0); td = []
    for o in rows:
        if o['fl'] & 1: c['S'] += 1
        if o['fl'] & 8:
            c['N'] += 1; c['tN'] += 1
            if o['touch'] >= 0: c['tT'] += 1; td.append(o['touch'])
        c[o['b']] += 1
        if (o['fl'] & 2) and not o['man']: c['E'] += 1
    c['need'] = c['S'] + c['N'] - c['skip'] - c['aged']; c['h'] = c['done'] + c['act']
    c['pct'] = jround(c['h'] * 100 / c['need']) if c['need'] else None
    c['med'] = median(td) if len(td) >= 3 else None
    c['tPct'] = jround(c['tT'] * 100 / c['tN']) if c['tN'] else None
    return c


def status(c, p):
    s1 = s2 = s3 = 0
    if c['pct'] is not None and p and p['pct'] is not None and c['need'] >= 5 and p['need'] >= 5:
        d = c['pct'] - p['pct']; s1 = 1 if d >= 5 else (-1 if d <= -5 else 0)
    dd = c['E'] - c['S']
    if c['S'] + c['N'] >= 5: s2 = 1 if dd < 0 else (-1 if dd > max(2, c['S'] * 0.05) else 0)
    if c['med'] is not None and p and p['med'] is not None:
        d = c['med'] - p['med']; s3 = 1 if d <= -0.5 else (-1 if d >= 0.5 else 0)
    if not p: return {'sc': 0, 'e': '📍', 't': 'ช่วงแรกที่มีข้อมูล', 's': (0, s2, 0)}
    sc = s1 + s2 + s3
    k = 2 if sc >= 2 else (1 if sc == 1 else (0 if sc == 0 else -1))
    return {'sc': sc, 'e': STATUS[k][1], 't': STATUS[k][2], 's': (s1, s2, s3)}


def rng(BA, ch, lists, a, b):
    """a, b = dates (first and last day). None when the channel has no data in the range."""
    C = BA['ch'].get(ch)
    if not C: return None
    ka, kf = max(0, kday(BA, a)), kday(BA, b) + 1
    if ka >= C['endK'] or kf <= 0: return None
    kb = min(kf, C['endK'])
    rows = []
    for l in lists: rows += evaluate(C, l, ka, kb)
    return {'c': count(rows), 'rows': rows, 'part': kf > C['endK']}


# ---------- text ----------
def dlab(a, b):
    if a.month == b.month: return '%d–%d %s' % (a.day, b.day, TH_M[b.month - 1])
    return '%d %s–%d %s' % (a.day, TH_M[a.month - 1], b.day, TH_M[b.month - 1])


def end_txt(C):
    e = C['end']   # 'YYYY-MM-DD HH:MM' Thai
    d = datetime.date.fromisoformat(e[:10])
    return '%d %s %s น.' % (d.day, TH_M[d.month - 1], e[11:16])


def periods(today, kind):
    mon = today - datetime.timedelta(days=today.weekday())
    if kind == 'mon':
        a = mon - datetime.timedelta(days=7); b = a + datetime.timedelta(days=6)
    else:
        a = mon if today.weekday() >= 4 else mon - datetime.timedelta(days=7)
        b = a + datetime.timedelta(days=3)
    return a, b, a - datetime.timedelta(days=7), b - datetime.timedelta(days=7)


def headline(c, p, st, unit):
    pos, s = [], st['s']
    if s[0] > 0: pos.append('แอดมินจัดการได้ %d%% ของงาน ดีขึ้นจาก%s %d จุด' % (c['pct'], unit, c['pct'] - p['pct']))
    if s[1] > 0: pos.append('กองแชทค้างลดลง %s แชท' % nf(c['S'] - c['E']))
    if s[2] > 0: pos.append('แตะแชทใหม่เร็วขึ้น (%s จากเดิม %s)' % (days_txt(c['med']), days_txt(p['med'])))
    if p and c['h'] > p['h'] and c['h'] >= 5: pos.append('จัดการไป %s แชท มากกว่า%s %s แชท' % (nf(c['h']), unit, nf(c['h'] - p['h'])))
    if pos: return ' · '.join(pos[:2]) + (' — เยี่ยมมาก ทีมทำได้ดีขึ้นจริง ๆ 🎉' if st['sc'] >= 2 else ' — ทำต่อแบบนี้เลย 💪')
    if c['h']: return 'จัดการไปแล้ว %s แชท — ขอบคุณทุกคนที่ช่วยกันตามแชท 🙏' % nf(c['h'])
    return ''


def records(BA, ch, a, cur):
    """Monday only: best of the last 8 full weeks"""
    pts = []
    for w in range(1, 8):
        x = rng(BA, ch, LISTS, a - datetime.timedelta(days=7 * w), a - datetime.timedelta(days=7 * w - 6))
        if x and not x['part']: pts.append(x['c'])
    out = []
    if len(pts) < 5: return out
    n = len(pts) + 1
    if cur['pct'] is not None and all(x['pct'] is None or cur['pct'] > x['pct'] for x in pts): out.append('🏆 จัดการได้ดีที่สุดในรอบ %d สัปดาห์' % n)
    if cur['h'] > 0 and all(cur['h'] > x['h'] for x in pts): out.append('🏅 จัดการได้มากที่สุดในรอบ %d สัปดาห์' % n)
    if cur['med'] is not None and all(x['med'] is None or cur['med'] < x['med'] for x in pts): out.append('⚡ แตะแชทใหม่เร็วที่สุดในรอบ %d สัปดาห์' % n)
    if all(cur['E'] < x['E'] for x in pts): out.append('📉 แชทค้างน้อยที่สุดในรอบ %d สัปดาห์' % n)
    return out


def message(BA, ch, kind, today):
    a, b, pa, pb = periods(today, kind)
    C = BA['ch'].get(ch)
    head = '📣 Tracking · %s %s' % (CHI[ch], CHN[ch])
    when = ('สรุปสัปดาห์ %s (จ.–อา.)' if kind == 'mon' else 'ความคืบหน้าสัปดาห์นี้ %s (จ.–พฤ.)') % dlab(a, b)
    cur = rng(BA, ch, LISTS, a, b)
    if not cur:
        return '\n'.join([head, when, '', 'ยังไม่มีข้อมูลช่วงนี้%s — จะขึ้นหลังดึงข้อมูลรอบถัดไป' % (' (ข้อมูลถึง %s)' % end_txt(C) if C else ''), '', FOOT]), None
    prev = rng(BA, ch, LISTS, pa, pb)
    c, p = cur['c'], (prev['c'] if prev else None)
    st = status(c, p)
    unit = 'สัปดาห์ก่อน'
    L = [head, when + (' · นับถึง %s' % end_txt(C) if cur['part'] else ''),
         '%s %s · เทียบ%s' % (st['e'], st['t'], unit if kind == 'mon' else ' จ.–พฤ. สัปดาห์ก่อน'), '']
    if not c['S'] and not c['N']:
        L.append('ไม่มีแชทค้างในช่วงนี้ 🎉')
    else:
        d = c['E'] - c['S']
        L.append('ทุกหมวด')
        L.append('• แชทค้าง %s → %s (%s)' % (nf(c['S']), nf(c['E']), 'เท่าเดิม' if d == 0 else ('▼' + nf(-d) if d < 0 else '▲' + nf(d))))
        L.append('• แอดมินจัดการ %s แชท%s%s' % (nf(c['h']), ' = %d%% ของงาน' % c['pct'] if c['pct'] is not None else '',
                                               ' (เดิม %d%%)' % p['pct'] if p and p['pct'] is not None else ''))
        L.append('• แตะแชทใหม่ %s%s' % (days_txt(c['med']), ' (เดิม %s)' % days_txt(p['med']) if p and p['med'] is not None else ''))
        L.append('• 💬 ลูกค้าทักกลับรอตอบ %s · ⏳ ยังไม่มีใครแตะ %s' % (nf(c['cus']), nf(c['none'])))
        cats = []
        for l in LISTS:
            x = rng(BA, ch, (l,), a, b)
            if not x or (not x['c']['S'] and not x['c']['N']): continue
            px = rng(BA, ch, (l,), pa, pb)
            sx = status(x['c'], px['c'] if px else None)
            cats.append('%s %s %s → %s · %s %s' % (LN[l][0], LN[l][1], nf(x['c']['S']), nf(x['c']['E']),
                                                  '—' if x['c']['pct'] is None else '%d%%' % x['c']['pct'], sx['e']))
        if cats:
            L += ['', 'แยกหมวด · ค้างต้น → ปลาย · % จัดการ · สถานะ'] + cats
    hl = headline(c, p, st, unit) if p else ''
    extra = records(BA, ch, a, c) if kind == 'mon' and p else []
    who = {}
    for o in cur['rows']:
        if o['b'] in ('done', 'act'):
            for n in o['who']: who[n] = who.get(n, 0) + 1
    tail = []
    if hl: tail.append(hl)
    tail += extra
    if who: tail.append('👤 ใครจัดการ: ' + ' · '.join('%s %s' % (n, nf(who[n])) for n in sorted(who, key=lambda k: -who[k])))
    todo = []
    if c['cus']: todo.append('💬 ลูกค้าทักกลับ %s แชท' % nf(c['cus']))
    if c['none']: todo.append('⏳ แชทใหม่ที่ยังไม่มีใครแตะ')
    if todo: tail.append(('👉 สัปดาห์นี้เริ่มจาก ' if kind == 'mon' else '⏰ ก่อนเสาร์–อาทิตย์ ช่วยกันเคลียร์ ') + ' + '.join(todo))
    tail.append(FOOT)
    return '\n'.join(L + [''] + tail), {'all': [c[k] for k in ('S', 'N', 'done', 'act', 'cus', 'skip', 'aged', 'none', 'E')] + [c['med']]}


SHORT = {'fb': 'FB', 'ig': 'IG', 'line': 'LINE'}


def combined(BA, kind, today):
    """one LINE bubble, laid out for a phone: 4 sections, overall first then each channel (line-notice.yml sends this)"""
    a, b, pa, pb = periods(today, kind)
    R, miss = {}, {}
    for ch in CHS:
        C = BA['ch'].get(ch)
        if not C: continue
        cur = rng(BA, ch, LISTS, a, b)
        if not cur:
            miss[ch] = 'ยังไม่มีข้อมูล (ถึง %s)' % end_txt(C); continue
        prev = rng(BA, ch, LISTS, pa, pb)
        R[ch] = (cur['c'], prev['c'] if prev else None, ' (นับถึง %s)' % end_txt(C) if cur['part'] else '')
    mon = kind == 'mon'
    L = ['📣 Tracking · %s %s' % ('สรุปสัปดาห์' if mon else 'ความคืบหน้า', dlab(a, b)),
         '(จ.–อา. เทียบกับสัปดาห์ก่อน)' if mon else '(จ.–พฤ. เทียบกับ จ.–พฤ. สัปดาห์ก่อน)']
    BAR = '━━━━━━━━━━━━'

    def tot(cs):
        if not cs or any(x is None for x in cs): return None
        t = {k: sum(x[k] for x in cs) for k in ('S', 'E', 'h', 'need', 'cus', 'none')}
        t['pct'] = jround(t['h'] * 100 / t['need']) if t['need'] else None
        return t

    def arrow(c):
        d = c['E'] - c['S']
        return 'เท่าเดิม' if d == 0 else ('▼' + nf(-d) if d < 0 else '▲' + nf(d))

    def left(c, p):
        if c['pct'] is None: return '—'
        r = 100 - c['pct']
        if not p or p['pct'] is None: return '%d%%' % r
        d = r - (100 - p['pct'])
        return '%d%% (เดิม %d%%) %s' % (r, 100 - p['pct'], '➖' if d == 0 else ('▼%d 👍' % -d if d < 0 else '▲%d ⚠️' % d))

    def section(title, sub, D, fn, first=False):
        L.extend(['', BAR, title] + sub + ['', '📌 รวม ' + fn(tot([D[ch][0] for ch in D]), tot([D[ch][1] for ch in D])), ''])
        for ch in CHS:
            if ch in D: L.append('%s %s %s%s' % (CHI[ch], SHORT[ch], fn(D[ch][0], D[ch][1]), D[ch][2] if first else ''))
            elif first and ch in miss: L.append('%s %s %s' % (CHI[ch], SHORT[ch], miss[ch]))

    if R:
        section('📥 แชทค้าง', ['(ต้นสัปดาห์ → ปลายสัปดาห์)' if mon else '(วันจันทร์ → วันพฤหัส)'], R,
                lambda c, p: '%s → %s (%s)' % (nf(c['S']), nf(c['E']), arrow(c)), first=True)
        section('✅ ความคืบหน้า', ['(ตอบแล้ว · เหลือ · % ที่ยังเหลือ)'], R,
                lambda c, p: 'ตอบแล้ว %s · เหลือ %s\n   └ เหลือ %s' % (nf(c['h']), nf(c['cus'] + c['none']), left(c, p)))
        section('🔔 รอแอดมิน', ['💬 ลูกค้าทักกลับรอตอบ', '⏳ ยังไม่มีใครแตะ'], R,
                lambda c, p: '💬 %s · ⏳ %s' % (nf(c['cus']), nf(c['none'])))
        SP = {}
        for ch in ('fb', 'line'):
            if ch not in R: continue
            x = rng(BA, ch, ('sp',), a, b)
            if not x or (not x['c']['S'] and not x['c']['N']): continue
            px = rng(BA, ch, ('sp',), pa, pb)
            SP[ch] = (x['c'], px['c'] if px else None, '')
        if SP:
            section('🎬 แนบตัวอย่าง (FB + LINE)', ['(ยังไม่แนบ ต้น → ปลาย · % จัดการ)'], SP,
                    lambda c, p: '%s → %s (%s) · %s' % (nf(c['S']), nf(c['E']), arrow(c), '%d%%' % c['pct'] if c['pct'] is not None else '—'))
    else:
        L += [''] + ['%s %s %s' % (CHI[ch], SHORT[ch], miss[ch]) for ch in CHS if ch in miss]
    return '\n'.join(L + ['', BAR, '📊 ดูรายละเอียดหน้า Tracking', PAGE])


def drafts(BA, today=None):
    built = BA.get('built') or ''
    BA = prep(BA)
    if today is None: today = datetime.date.fromisoformat(built[:10])
    out = {'built': built}
    for kind in ('mon', 'fri'):
        a, b, _, _ = periods(today, kind)
        msgs, chk = {}, {}
        for ch in CHS:
            if ch not in BA['ch']: continue
            msgs[ch], chk[ch] = message(BA, ch, kind, today)
        out[kind] = {'a': a.isoformat(), 'b': b.isoformat(), 'lab': dlab(a, b), 'msgs': msgs, 'chk': chk,
                     'one': combined(BA, kind, today)}
    return out


# ---------- sending (GitHub Actions) ----------
def load_published():
    """data/ba.json from the checked-out repo, decrypted the way build.py sealed it"""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    man = json.load(open('manifest.json', encoding='utf-8'))
    path = (man.get('files') or {}).get('ba')
    if not path: raise SystemExit('ยังไม่มี data/ba.json ในหน้าเว็บ — รอรอบอัปเดตเช้า')
    sec = (os.environ.get('ADMIN_SECRET') or '').strip()
    if ':' not in sec: raise SystemExit('ไม่มี ADMIN_SECRET')
    key = hashlib.pbkdf2_hmac('sha256', sec.encode(), base64.b64decode(man['kdf']['s']), man['kdf']['n'], 32)
    blob = json.load(open(path.replace('./', '', 1), encoding='utf-8'))
    raw = AESGCM(key).decrypt(base64.b64decode(blob['i']), base64.b64decode(blob['c']), None)
    return json.loads(gzip.decompress(raw) if blob.get('z') == 'gzip' else raw)


def push(token, to, texts, retry_key):
    body = json.dumps({'to': to, 'messages': [{'type': 'text', 'text': t[:5000]} for t in texts[:5]]}).encode()
    req = urllib.request.Request('https://api.line.me/v2/bot/message/push', data=body, method='POST', headers={
        'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token, 'X-Line-Retry-Key': retry_key})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, ''
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')[:300]


def send():
    auto = (os.environ.get('KIND') or 'auto').strip() == 'auto'
    kind = 'auto' if auto else os.environ['KIND'].strip()
    dry = (os.environ.get('SEND') or '').strip() != '1'
    today = datetime.datetime.now(TH).date()
    if auto:
        kind = {0: 'mon', 4: 'fri'}.get(today.weekday())
        if not kind:
            print('วันนี้ไม่ใช่วันจันทร์/ศุกร์ — ไม่ส่ง'); return
    if kind not in ('mon', 'fri'): raise SystemExit('KIND ต้องเป็น auto / mon / fri')
    BA = load_published()
    built = BA.get('built') or ''
    if auto and built[:10] != today.isoformat():
        print('ข้อมูลยังไม่ใช่ของวันนี้ (สร้างเมื่อ %s) — ไม่ส่ง รอรอบอัปเดตเช้า' % built); return
    D = drafts(BA, today)[kind]
    texts = [D['one']]
    # repo is public, so is the Actions log: only sizes here, never the texts (they are on the Tracking page)
    print('ข้อมูลสร้างเมื่อ %s · แบบ%s · %s · ข้อความเดียว %d ช่องทาง %d ตัวอักษร' % (
          built, 'วันจันทร์' if kind == 'mon' else 'วันศุกร์', D['lab'], len(D['msgs']), len(D['one'])))
    if dry:
        print('ทดลอง — ไม่ส่ง (ดูข้อความได้ที่หน้า Tracking)'); return
    token, to = (os.environ.get('LINE_NOTICE_TOKEN') or '').strip(), (os.environ.get('LINE_NOTICE_TO') or '').strip()
    if not token or not to:
        print('ยังไม่ได้ตั้ง LINE_NOTICE_TOKEN / LINE_NOTICE_TO — ไม่ส่ง'); return
    # automatic runs: one key per day and kind, so a second refresh on the same day is refused by LINE (409) instead of
    # sending twice · a manual test run gets a fresh key
    rk = str(uuid.uuid5(uuid.NAMESPACE_URL, 'biopalm-tracking/%s/%s/%s' % (today.isoformat(), kind, to))) if auto else str(uuid.uuid4())
    code, err = push(token, to, texts, rk)
    if code == 200: print('ส่งเข้า LINE กลุ่มแล้ว (%d บับเบิล)' % len(texts))
    elif code == 409: print('วันนี้ส่งข้อความแบบนี้ไปแล้ว — ไม่ส่งซ้ำ')
    else: raise SystemExit('ส่งไม่สำเร็จ HTTP %s %s' % (code, err))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'show'
    if cmd == 'send': send()
    else:
        BA = json.load(open(sys.argv[2] if len(sys.argv) > 2 else 'src/ba.json', encoding='utf-8'))
        N = drafts(BA)
        for kind in ('mon', 'fri'):
            print('===== %s %s =====' % ('จันทร์' if kind == 'mon' else 'ศุกร์', N[kind]['lab']))
            print(N[kind]['one'] + '\n')

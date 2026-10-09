# -*- coding: utf-8 -*-
"""Weekly before / after for every Follow up list (admin-hub, 9 ต.ค. 2026) -> src/followup.json key "wk".

Why: the old "แชทค้างไปไหน" box compared today's list with the list 1 / 7 days ago and named why each chat left.
Checked on test threads (9 ต.ค. 2026), it mislabels real admin work:
  - sample / summary lists: the customer asked again and an admin answered within the last day -> shown as
    "หลุดเพราะเกิน 90 วัน" (grey, not counted); answered 2–6 days ago -> "ยังไม่มีใครตาม"
  - the customer asked again and nobody has answered yet -> counted as cleared ("ลูกค้าถามต่อ")
  - auto-reply list: the customer wrote again within 7 days -> counted as cleared ("กลายเป็นไม่ต้องตาม")
This script replays every thread day by day (Thai midnight cuts) over the last WEEKS weeks with the SAME rules the
lists use — build_fu.py for "บอทตอบ - ไม่มีแอดมินตอบ", build_pay.py for the other four — so for each Monday–Sunday
week it knows which chats were on each list at the start, which entered during the week, where each one stands at
the end of the week, and whether a person on our side wrote in the chat while it was on the list.

wk = {v, built, weeks: {ch: [[start, end, full], ...]}, end: {ch: stamp}, ids: {ch: [[thread id, name, LINE owner], ...]},
      rows: {ch: {list: [[row, ...] per week]}}, sum: {ch: {list: [counts per week]}}, check: {ch: {list: [mine, page]}},
      ov: number of manual moves merged into sum}
  row   [i, flags, out, sub, who, man]
  i     index into ids[ch]
  flags 1 listed at the week start · 2 listed at the week end · 4 a person on our side wrote while it was listed
        · 8 entered during the week
  out   where it went if it left the list ('' = still listed at the end):
          done  ans แอดมินตอบแล้ว · smp ส่งตัวอย่างแล้ว · sum ส่งสรุปยอดแล้ว · paid โอนแล้ว · close ลูกค้าปิดท้ายเอง
          act   fu ทักตามแล้ว · reans ตอบคำถามใหม่ (ยังไม่ขยับขั้น) · requote ส่งสรุปยอดรอบใหม่ · move ย้ายหมวด
          cus   ลูกค้าทักกลับ ยังไม่มีแอดมินตอบ · x ไม่ต้องตาม · aged เกิน 90 วัน
  sub   sub-group when it was first listed that week: ar nA nB pA pB (n = never had an admin, p = had one before ·
        A ถามจริง, B กดปุ่มสนใจ) · sp / np A บอกชั้น/คอร์สแล้ว, B ถามทั่วไป · pay / pz R ถามค้าง, A สรุปยอดแล้วเงียบ, B คุยต่อแล้วเงียบ
  who   admins who wrote while it was listed (LINE names every sender; Meta does not, so Facebook / Instagram only
        carry the name picked when a button was pressed)
  man   a button pressed while it was listed that week (✓ ตอบแล้ว / ✓ ตามแล้ว / ทำแล้ว -> 'act', ไม่ต้องตาม -> 'skip',
        shared sheet). A chat moved off the list by hand before the week and not written to since is left out, as on the page
  sum   per week: [S start, N entered, done, act, cus, skip, aged, none, E end] — the numbers the weekly LINE report sends.
        done = moved to the next step or closed · act = a person answered / followed up / pressed a button but it is
        still at this step · cus = the customer wrote back and nobody has answered · none = nobody touched it
Run after build_stage.py (needs src/followup.json written by build_fu.py / build_pay.py). Logs counts only.
"""
import os, re, json, glob, bisect, datetime, collections, gc, time, hashlib, urllib.request
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import build_pay as bp

# build_fu.py's rules (quality tiers, noise, greetings) without running build_fu's list build
_src = open('build_fu.py', encoding='utf-8').read()
_k = _src.find('\nagg = json.load(')
if _k < 0:
    raise SystemExit('build_week: build_fu.py layout changed — rules block not found, nothing written')
FU_RULES = {}
exec(compile(_src[:_k], 'build_fu.py', 'exec'), FU_RULES)
NOISE, LOW, quality, KIND = FU_RULES['NOISE'], FU_RULES['LOW'], FU_RULES['quality'], FU_RULES['KIND']

T0 = datetime.datetime(2026, 1, 1)
DAY = 1440
WEEKS = int(os.environ.get('WK_WEEKS') or 8)          # full weeks kept, plus the current week so far
LISTS = ('ar', 'sp', 'np', 'pay', 'pz')
DONE, ACT = ('ans', 'smp', 'sum', 'paid', 'close'), ('fu', 'reans', 'requote', 'move')


def base(mo): return int((datetime.datetime(int(mo[:4]), int(mo[5:7]), 1) - T0).total_seconds() // 60)
def stamp(mi): return (T0 + datetime.timedelta(minutes=mi)).strftime('%Y-%m-%d %H:%M')
def tx_of(d): return lambda x: d[x] if isinstance(x, int) and 0 <= x < len(d) else (x if isinstance(x, str) else '')
def mstamp(s): return int((datetime.datetime.strptime(s[:16], '%Y-%m-%d %H:%M') - T0).total_seconds() // 60)


# ---------- the five list rules, evaluated on a thread cut at minute `cut` ----------
PRE = {}


def J_ar(ms, cut, e, ch):
    """build_fu.py finish(): the customer's latest round got automatic replies only"""
    cus = [x for x in ms if x[1] == 0]
    if not cus: return None, 'nocus'
    if any(bp.SLIP.search(x[2]) for x in ms if x[1] != 0): return None, 'paid'
    hum = [x[0] for x in ms if x[1] == 1]
    lastH = hum[-1] if hum else None
    prior = bool(hum) or e['tid'] in PRE.get(ch, ())
    ep = [x for x in cus if lastH is None or x[0] > lastH]
    if not ep: return None, 'ans'
    said = [x[2] for x in ep if x[2] not in NOISE]
    if prior and all(LOW.match(x) for x in said): return None, 'close'
    if KIND.get(e['st']) == 'give': return None, 'give'
    q = quality(said)
    if q == 'C': return None, 'x'
    w = round((cut - ep[-1][0]) / 1440.0, 1)                # rounded like build_fu's list, so the counts match the page
    return {'wait': w, 'g': ('p' if prior else 'n') + q, '_a': ep[-1][0]}, ('on' if w >= 7 else 'young')


def J_sp(ms, cut, e, ch):
    bp.NEW = True
    return bp.judge_sp(ms, cut, e, cut)


def J_np(ms, cut, e, ch):
    bp.NEW = True; bp.NPSMP = True
    return bp.judge_np(ms, cut, e, cut)


def J_pay(ms, cut, e, ch):
    bp.NEW = True; bp.PAYSMP = True
    return bp.judge(ms, cut, e, cut)


def J_pz(ms, cut, e, ch):
    bp.NEW = True; bp.PAYSMP = False
    return bp.judge(ms, cut, e, cut)


def in_ar(r, w): return r['g'] if w == 'on' else None
def in_np(r, w): return w if (r is not None and w in bp.NP_TODO and 1 <= r['wait'] < 90) else None
def in_pay(r, w): return w if (r is not None and w in bp.TODO and 1 <= r['wait'] < 90) else None


JUDGE = {'ar': (J_ar, in_ar), 'sp': (J_sp, in_np), 'np': (J_np, in_np), 'pay': (J_pay, in_pay), 'pz': (J_pz, in_pay)}


def outcome(lst, st, e, t_in, t_end):
    """why a chat that was listed during the week is no longer listed at the week end"""
    r, w, _ = st
    if lst == 'ar':
        return {'ans': 'ans', 'paid': 'paid', 'close': 'close', 'young': 'cus'}.get(w, 'x')
    if lst in ('sp', 'np'):
        if w == 'sampled': return 'smp'
        if w == 'quoted':
            return 'paid' if any(bp.SLIP.search(x[2]) for x in e['m'] if t_in < x[0] <= t_end) else 'sum'
        if w in ('paidbefore', 'reg'): return 'paid'
        if w == 'waiting': return 'cus'
        if r is None: return 'x'
        if w == 'F': return 'fu'
        if w == 'X': return 'x'
        return 'reans' if r['wait'] < 1 else 'aged'
    if w in ('paid', 'paid_fu'): return 'paid'
    if w == 'split': return 'move'
    if r is None: return 'x'
    if w == 'F': return 'fu'
    if w == 'X': return 'x'
    return 'requote' if r['wait'] < 1 else 'aged'


def replay(lst, e, ch, cuts):
    """state of one thread at every cut. A thread with no new message since the previous cut keeps its result and
       only ages, so the rules run once per day that had a message (and again for 'F', whose 7-day window expires)"""
    J, inl = JUDGE[lst]
    ms, times = e['m'], e['t']
    out = []; prev = None; pidx = -1; pcut = None
    for c in cuts:
        idx = bisect.bisect_right(times, c)
        if prev is not None and idx == pidx and not (prev[0] is not None and prev[1] == 'F'):
            r, w = prev
            if r is not None and '_a' in r:
                # the anchor does not move without a new message -> age it exactly, rounded like the lists do
                r = dict(r); r['wait'] = round((c - r['_a']) / 1440.0, 1)
                if w in ('young', 'on'): w = 'on' if r['wait'] >= 7 else 'young'   # auto-reply list: 7 days of silence
        elif idx == 0:
            r, w = None, 'nocus'
        else:
            r, w = J(ms[:idx], c, e, ch)
            if r is not None and 'q1' in r and '_a' not in r: r['_a'] = mstamp(r['q1'])   # build_pay rows: age counts from q1
        prev = (r, w); pidx = idx; pcut = c
        out.append((r, w, inl(r, w) if r is not None else None))
    return out


# ---------- weeks ----------
def week_plan(end):
    """[(start, end, full)] Monday 00:00 Thai -> next Monday (or the data end for the current week), oldest first"""
    d = T0 + datetime.timedelta(minutes=end)
    mon = datetime.datetime(d.year, d.month, d.day) - datetime.timedelta(days=d.weekday())
    m0 = int((mon - T0).total_seconds() // 60)
    W = [(m0 - (k + 1) * 7 * DAY, m0 - k * 7 * DAY, 1) for k in range(WEEKS)][::-1]
    if end > m0: W.append((m0, end, 0))
    return W


def cut_list(W, end):
    c = set()
    for s, t, _ in W:
        x = s
        while x <= t:
            c.add(min(x, end)); x += DAY
        c.add(min(t, end))
    return sorted(c)


# ---------- threads ----------
def add(th, key, n, st, mi, role, text, who='', ow=None, reg=None):
    e = th.get(key)
    if e is None:
        e = th[key] = {'tid': key, 'n': '', 'm': [], 'adm': [], 'st': None, 'ow': '', 'reg': 0}
    if n: e['n'] = n
    if st is not None: e['st'] = st
    if ow is not None: e['ow'] = ow
    if reg is not None: e['reg'] = reg
    if mi is None: return
    e['m'].append((mi, role, text))
    if role == 1: e['adm'].append((mi, who))


def load_meta(ch):
    th = {}
    if ch == 'fb':
        for p in sorted(glob.glob('src/fb_*.json')):
            mo = p[-12:-5]; f = json.load(open(p, encoding='utf-8')); t = tx_of(f['dict']); b = base(mo)
            for c in f['chats']:
                key = str(c[19]); add(th, key, c[0], c[37] if len(c) > 37 else None, None, 0, '')
                for m in c[18]:
                    s = str(t(m[2])).strip()
                    if bp.SYS.search(s): continue
                    add(th, key, None, None, b + m[0], m[1] if m[1] in (0, 1) else 2, s)
            del f; gc.collect()
    else:
        ig = json.load(open('src/ig_all.json', encoding='utf-8')); t = tx_of(ig['dict'])
        for mo in sorted(ig['months']):
            b = base(mo)
            for c in ig['months'][mo]['leads']:
                key = str(c[19]); add(th, key, c[0], c[37] if len(c) > 37 else None, None, 0, '')
                for m in c[18]:
                    s = str(t(m[2])).strip()
                    if bp.SYS.search(s): continue
                    add(th, key, None, None, b + m[0], m[1] if m[1] in (0, 1) else 2, s)
        del ig; gc.collect()
    return th


def load_line():
    th = {}
    for p in sorted(glob.glob('src/line_*.json')):
        mo = p[-12:-5]; f = json.load(open(p, encoding='utf-8')); t = tx_of(f['dict']); y = int(mo[:4])
        for r in f['rooms']:
            key = str(r['id'])
            reg = 1 if any('สมัครแล้ว' in str(x) for x in (r.get('tg') or [])) else 0
            add(th, key, r.get('n'), r.get('sg'), None, 0, '', ow=r.get('ow') or '', reg=reg)
            for m in r.get('tr') or []:
                try:
                    ts = int((datetime.datetime(y, int(m[0][:2]), int(m[0][3:5]), int(m[0][6:8]), int(m[0][9:11])) - T0).total_seconds() // 60)
                except Exception:
                    continue
                w = m[1]; s = str(t(m[2])).strip()
                if w == 'C': add(th, key, None, None, ts, 0, s)
                elif w == 'B':
                    if s not in NOISE: add(th, key, None, None, ts, 2, s)
                else: add(th, key, None, None, ts, 1, s, who=str(w))
        del f; gc.collect()
    return th


# ---------- manual buttons (shared sheet) ----------
def manual_rows(agg):
    """[[ch, tid, last, st, why, by, at], ...] from the Apps Script store; [] if it cannot be read"""
    try:
        url = agg.get('ovurl')
        if not url or not os.path.exists('secret.txt'): return []
        tok = hashlib.sha256(('bp-ov|' + open('secret.txt', encoding='utf-8').read().strip()).encode()).hexdigest()
        j = json.loads(urllib.request.urlopen(url + '?t=' + tok, timeout=120).read().decode())
        return j.get('rows') or []
    except Exception as ex:
        print('build_week: manual moves not read (%s)' % type(ex).__name__)
        return []


def iso_min(s):
    """ISO time from the sheet (UTC 'Z' or with offset) -> minutes since 2026-01-01 Thai"""
    try:
        d = datetime.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
        if d.tzinfo is not None: d = d.astimezone(datetime.timezone(datetime.timedelta(hours=7))).replace(tzinfo=None)
        return int((d - T0).total_seconds() // 60)
    except Exception:
        return None


def manual_kind(st, why):
    if st in ('follow', 'clear'): return 'undo'
    if st != 'skip': return None
    return 'act' if re.match(r'^(ตอบแล้ว|ตามแล้ว|ทำแล้ว)', why or '') else 'skip'


def bucket(row):
    """done / act / cus / skip / aged / none. row[5] = button pressed while listed ('' / act / skip): pressing
       ไม่ต้องตาม after opening the chat is the admin handling it too, so both count as act"""
    out, fl, man = row[2], row[1], row[5] if len(row) > 5 else ''
    if out in DONE: return 'done'
    if out in ACT or man: return 'act'
    if fl & 4 and out == '': return 'act'
    if out == 'aged': return 'aged'
    if out == 'x': return 'skip'
    return 'cus' if out == 'cus' else 'none'


BI = {'done': 2, 'act': 3, 'cus': 4, 'skip': 5, 'aged': 6, 'none': 7}


def manual_for(MAN, ch, key, e, a0, a1):
    """the shared-sheet buttons for this chat around its time on the list this week:
       'drop'  pressed before it was listed and still in force (no customer message since) -> the page never showed it
       (kind, by)  pressed while it was listed this week
       None    nothing"""
    mv = MAN.get((ch, key))
    if not mv: return None
    for at, k, by in reversed(mv):
        if at > a1: continue
        if k == 'undo': return None
        if at > a0: return (k, by)
        return None if any(x[1] == 0 and at < x[0] <= a1 for x in e['m']) else 'drop'
    return None


# ---------- weekly report text (LINE group) ----------
TH_M = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']
LNAME = {'ar': '🤖 บอทตอบ ไม่มีแอดมินตอบ', 'sp': '🎬 ยังไม่แนบตัวอย่าง', 'np': '🗨️ แนบตัวอย่างแล้ว ยังไม่สรุปจ่าย',
         'pay': '💸 แนบตัวอย่าง+สรุปจ่ายแล้ว ยังไม่โอน', 'pz': '🧾 สรุปจ่ายแล้ว (ไม่แนบตัวอย่าง) ยังไม่โอน'}
SUBN = {'ar': {'nA': 'ไม่เคยมีแอดมินคุย · ถามจริง', 'nB': 'ไม่เคยมีแอดมินคุย · กดปุ่มสนใจ', 'pA': 'เคยคุยแล้ว · ถามรอบใหม่', 'pB': 'เคยคุยแล้ว · กดปุ่มรอบใหม่'},
        'sp': {'A': 'บอกชั้น/คอร์สแล้ว', 'B': 'ถามเรื่องคอร์สทั่วไป'}, 'np': {'A': 'บอกชั้น/คอร์สแล้ว', 'B': 'ถามเรื่องคอร์สทั่วไป'},
        'pay': {'R': 'ลูกค้าถามค้าง', 'A': 'สรุปยอดแล้ว ลูกค้าเงียบ', 'B': 'คุยต่อแล้วเงียบ', 'C': 'ได้ราคาแล้วเงียบ'}}
SUBN['pz'] = SUBN['pay']
CHN = {'fb': '🔵 Facebook', 'ig': '🟣 Instagram', 'line': '🟢 LINE OA'}
SITE = 'https://biopalm-education.github.io/admin-hub/'


def tlabel(s):
    """'2026-10-04 18:00' -> '4 ต.ค. 18:00'"""
    d = datetime.datetime.strptime(s[:16], '%Y-%m-%d %H:%M')
    return '%d %s %s' % (d.day, TH_M[d.month - 1], s[11:16])


def dlabel(s, e, full):
    a = datetime.datetime.strptime(s[:10], '%Y-%m-%d')
    b = datetime.datetime.strptime(e[:16], '%Y-%m-%d %H:%M')
    if full or (b.hour == 0 and b.minute == 0): b = b - datetime.timedelta(days=1)
    if a.month == b.month: return '%d–%d %s' % (a.day, b.day, TH_M[b.month - 1])
    return '%d %s–%d %s' % (a.day, TH_M[a.month - 1], b.day, TH_M[b.month - 1])


def count(rows):
    """[S, N, done, act, cus, skip, aged, none, E]. A chat an admin moved off the list by hand no longer counts in E
       (the page hides it the moment the button is pressed)"""
    c = [0] * 9
    for row in rows:
        c[0] += bool(row[1] & 1); c[1] += bool(row[1] & 8); c[BI[bucket(row)]] += 1
        c[8] += bool(row[1] & 2) and not row[5]
    return c


def line_of(name, c):
    S, N, dn, ac, cu, sk, ag, no, E = c
    need = S + N - sk - ag
    d = E - S
    dd = 'เท่าเดิม' if d == 0 else ('▼%d' % -d if d < 0 else '▲%d' % d)
    pct = ' · จัดการ %d%%' % round((dn + ac) * 100.0 / need) if need else ''
    return '%s: %d%s → ✅%d ✋%d 💬%d ⏳%d → %d %s%s' % (name, S, ('(+%d)' % N) if N else '', dn, ac, cu, no, E, dd, pct)


def report(WK):
    """one text bubble per channel for the latest full week of Facebook (the week the Monday report is about)"""
    W = WK['weeks'].get('fb') or []
    full = [i for i, w in enumerate(W) if w[2]]
    if not full: return None
    wi = full[-1]; s0 = W[wi][0]
    head = '📊 สรุป Follow up แอดมิน · สัปดาห์ %s %s\nอ่าน: ค้างต้นสัปดาห์ (+เข้าใหม่) → ✅เคลียร์แล้ว ✋ตอบ/ตามแล้ว 💬ลูกค้าทักกลับรอตอบ ⏳ยังไม่มีใครแตะ → ค้างปลายสัปดาห์' % (
        dlabel(W[wi][0], W[wi][1], 1), s0[:4])
    out = []; admins = collections.Counter()
    for ch in ('fb', 'ig', 'line'):
        CW = WK['weeks'].get(ch) or []
        j = next((k for k, w in enumerate(CW) if w[0] == s0), None)
        lines = [CHN[ch]]
        if j is None or not CW[j][2]:
            e = WK['end'].get(ch)
            lines.append('ยังไม่มีข้อมูลครบสัปดาห์นี้ (ข้อมูลถึง %s)' % (tlabel(e) if e else '-'))
        else:
            for l in LISTS:
                rows = WK['rows'][ch][l][j]
                lines.append(line_of(LNAME[l], count(rows)))
                subs = collections.defaultdict(list)
                for row in rows: subs[row[3]].append(row)
                for k, nm in SUBN[l].items():
                    if subs.get(k): lines.append('   └ ' + line_of(nm, count(subs[k])))
                for row in rows:
                    if bucket(row) in ('done', 'act'):
                        for n in row[4] or []: admins[n] += 1
        if ch == 'line' and j is not None and CW[j][2]:
            lines.append('(ข้อมูล LINE ถึง %s)' % tlabel(WK['end']['line']))
        out.append('\n'.join(lines))
    tail = []
    if admins:
        tail.append('👤 ใครจัดการไปกี่แชท (ชื่อจาก LINE + ปุ่มในแดชบอร์ด): ' + ' · '.join('%s %d' % kv for kv in admins.most_common()))
    tail.append('ดูรายชื่อแชท: %s → Follow up' % SITE)
    out[0] = head + '\n\n' + out[0]
    out[-1] = out[-1] + '\n\n' + '\n'.join(tail)
    return {'week': s0[:10], 'msgs': out}


def main():
    t_start = time.time()
    F = json.load(open('src/followup.json', encoding='utf-8'))
    agg = json.load(open('src/agg.json', encoding='utf-8'))
    END = {'fb': agg.get('v4end') or 0, 'ig': agg.get('v4end') or 0}
    if F.get('lend'): END['line'] = mstamp(F['lend'])
    for k, v in (F.get('pre') or {}).items(): PRE[k] = set(v)
    MAN = collections.defaultdict(list)
    ov = manual_rows(agg)
    for x in ov:
        if len(x) < 7: continue
        k = manual_kind(x[3], x[4]); at = iso_min(x[6])
        if k and at is not None: MAN[(x[0], str(x[1]))].append((at, k, x[5] or ''))
    for v in MAN.values(): v.sort()
    del agg; gc.collect()
    WK = {'v': 1, 'built': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).strftime('%Y-%m-%d %H:%M'),
          'weeks': {}, 'end': {}, 'ids': {}, 'rows': {}, 'sum': {}, 'check': {}, 'ov': 0}
    for ch in ('fb', 'ig', 'line'):
        if ch not in END or not END[ch]: continue
        th = load_line() if ch == 'line' else load_meta(ch)
        end = END[ch]; W = week_plan(end); cuts = cut_list(W, end); ci = {c: i for i, c in enumerate(cuts)}
        IDX = {}; ids = []; R = {l: [[] for _ in W] for l in LISTS}; now = collections.Counter()
        for key, e in th.items():
            e['m'].sort(key=lambda x: x[0]); e['adm'].sort()
            e['m'] = [x for x in e['m'] if x[0] <= end]
            if not any(x[1] == 0 for x in e['m']): continue
            e['t'] = [x[0] for x in e['m']]
            for lst in LISTS:
                st = replay(lst, e, ch, cuts)
                if st[-1][2]: now[lst] += 1
                for wi, (s, t, _) in enumerate(W):
                    i0, i1 = ci[s], ci[min(t, end)]
                    on0 = st[i0][2] is not None
                    entry = i0 if on0 else next((j for j in range(i0 + 1, i1 + 1) if st[j][2] is not None), None)
                    if entry is None: continue
                    on1 = st[i1][2] is not None
                    a0, a1 = cuts[entry], cuts[i1]
                    mv = manual_for(MAN, ch, key, e, a0, a1)
                    if mv == 'drop': continue
                    adm = [n for (tm, n) in e['adm'] if a0 < tm <= a1]
                    fl = (1 if on0 else 8) | (2 if on1 else 0) | (4 if adm else 0)
                    out = '' if on1 else outcome(lst, st[i1], e, a0, a1)
                    if key not in IDX:
                        IDX[key] = len(ids); ids.append([key, e['n'] or '', e.get('ow') or ''])
                    who = sorted(set(n for n in adm if n)) if ch == 'line' else []
                    man = ''
                    if mv:
                        man = mv[0]; WK['ov'] += 1
                        if mv[1] and mv[1] not in who: who.append(mv[1])
                    R[lst][wi].append([IDX[key], fl, out, st[entry][2], who, man])
        del th; gc.collect()
        # self-check: the replay at the data end must give the same lists the page shows
        page = {}
        L = F.get(ch) or []
        page['ar'] = sum(1 for r in L if r[3] >= 7 and r[15] != 'C' and r[2] != 'give')
        for lst, todo in (('sp', bp.NP_TODO), ('np', bp.NP_TODO), ('pay', bp.TODO), ('pz', bp.TODO)):
            page[lst] = sum(1 for r in ((F.get(lst) or {}).get(ch) or []) if r[2] in todo and 1 <= r[3] < 90)
        WK['check'][ch] = {l: [now[l], page[l]] for l in LISTS}
        WK['weeks'][ch] = [[stamp(s), stamp(min(t, end)), f] for s, t, f in W]
        WK['end'][ch] = stamp(end); WK['ids'][ch] = ids; WK['rows'][ch] = R
        WK['sum'][ch] = {l: [count(rows) for rows in R[l]] for l in LISTS}
        print('week %s end %s ids %d | %s' % (ch, stamp(end), len(ids),
              ' · '.join('%s now %d/page %d' % (l, now[l], page[l]) for l in LISTS)))
        for l in LISTS:
            s = WK['sum'][ch][l]
            print('  %-3s last full week S%d N%d done%d act%d cus%d skip%d aged%d none%d E%d' % ((l,) + tuple(s[-2] if len(s) > 1 else s[-1])))
    WK['report'] = report(WK)
    F['wk'] = WK
    json.dump(F, open('src/followup.json.wk-tmp', 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    os.replace('src/followup.json.wk-tmp', 'src/followup.json')
    print('build_week done in %.0fs · manual moves merged %d' % (time.time() - t_start, WK['ov']))


if __name__ == '__main__':
    main()

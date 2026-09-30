# -*- coding: utf-8 -*-
"""Chat stage for the admin team (admin-hub ข้อมูลดิบ, 30 ก.ย. 2026) — from ส.ค. 2026 onward.

Each chat row (FB/IG r[46], LINE room['s6']) gets one stage, reading the thread across months up to the end of that
month, CURRENT SALES ROUND only (after the latest verified slip; a sample sent in an earlier month of the round counts):
  N   บอทตอบ · ไม่มีแอดมินตอบ              no person from our side has ever replied
  A0  แอดมินตอบ · ยังไม่แนบตัวอย่าง
  A1  แนบตัวอย่างแล้ว · ยังไม่สรุปจ่าย
  A2  แนบตัวอย่าง · สรุปจ่ายแล้ว (ยังไม่โอน)
  B2  ไม่ได้แนบตัวอย่าง · สรุปจ่ายแล้ว (ยังไม่โอน)   e.g. returning students (ราคานักเรียนเก่า)
  W   จ่ายเงินแล้ว (สลิปผ่าน)                  build_v4 stage W in that month
  P   นักเรียนเก่า · เคยจ่ายเงินแล้ว            paid before (or LINE tag สมัครแล้ว) and no sample / summary card since
      (30 ก.ย.: checked on real data — without this, ~70–90% of the "สรุปจ่ายแล้ว" rows were returning students)
  ''  not counted: the customer never wrote (X) or Giveaway (G), or a month before STAGE_FROM
r[47] / room['s6i'] = [first sample of the round, sample types of the round 'clip,trial,other', first summary card of the
round, latest verified slip] ('YYYY-MM-DD HH:MM' or '')
agg['stg'][ch][month] = counts per stage (ส.ค.+) · agg['adm'][ch][month]['sum'] = rows whose month holds a
summary card (every month, for the quality table) · ['sumpaid'] = of those, how many sent a verified slip after the card
(any later month, up to the data end) · ['smp'] = rows whose month holds a sample ·
LINE ['sby'] = {admin: rooms where that admin sent the month's first summary card} (per-admin table).
Rules live in stage_rules.py. Run after build_adm.py, before build.py. Idempotent, one month file in memory at a time.
"""
import os, json, glob, datetime, collections
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from stage_rules import sample_at, summary_marks
from build_pay import SLIP          # the verified-slip line (same rule as the payment follow-up list)

STAGE_FROM = '2026-08'
T0 = datetime.datetime(2026, 1, 1)
SYS = ('\x01', 'Facebook สร้างแชทนี้ขึ้น', 'คุณกำลังตอบกลับความคิดเห็น', 'replied to a post', 'ได้ตอบกลับโพสต์')


def base(mo): return int((datetime.datetime(int(mo[:4]), int(mo[5:7]), 1) - T0).total_seconds() // 60)
def stamp(mi): return (T0 + datetime.timedelta(minutes=mi)).strftime('%Y-%m-%d %H:%M')
def tx_of(d): return lambda x: d[x] if isinstance(x, int) and 0 <= x < len(d) else (x if isinstance(x, str) else '')
def load(p):
    try: return json.load(open(p, encoding='utf-8'))
    except FileNotFoundError: return None
def dump(o, p):
    tmp = p + '.stg-tmp'
    json.dump(o, open(tmp, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    os.replace(tmp, p)


STATE = {}           # (channel, thread id) -> running flags through the months
STG = {'fb': {}, 'ig': {}, 'line': {}}
MON = {'fb': collections.defaultdict(lambda: [0, 0]), 'ig': collections.defaultdict(lambda: [0, 0]),
       'line': collections.defaultdict(lambda: [0, 0])}     # month -> [rows with a summary, rows with a sample]
FIRST = {'fb': collections.Counter(), 'ig': collections.Counter(), 'line': collections.Counter()}   # month of a thread's first sample
TYP = {'fb': collections.defaultdict(collections.Counter), 'ig': collections.defaultdict(collections.Counter), 'line': collections.defaultdict(collections.Counter)}
SBY = {}             # LINE month -> {admin name: rooms where that admin sent the first summary card of the month}
COH = []             # (channel, thread, month, minute of the month's first summary card, admin name or None)
LASTSLIP = {}        # (channel, thread) -> minute of the latest verified slip


def step(ch, tid, mo, st, msgs, reg=False):
    """msgs: [(minute, who, text, name)] who 'C' customer · 'H' person on our side · 'A' automation · name = LINE admin
       reg: LINE room tagged สมัครแล้ว. Updates the thread state, returns (stage, info) for this month row.
       Stages read the CURRENT SALES ROUND = everything after the latest verified slip (a customer who paid in May and
       writes again in Sep starts a new round; the old sample / summary card belonged to the finished purchase)."""
    s = STATE.setdefault((ch, tid), {'h': False, 'smp': '', 'typ': set(), 'sum': '', 'won': False,
                                     'slip': None, 'rsmp': None, 'rtyp': set(), 'rsum': None})
    msgs = sorted(msgs, key=lambda m: m[0])
    marks = set(summary_marks([(t, who != 'C', x) for t, who, x, _ in msgs]))
    had_smp = False
    tys = set()
    for i, (t, who, x, _) in enumerate(msgs):
        if SLIP.search(x):                       # payment verified -> the round closes, a new one starts after it
            s['slip'] = t; s['rsmp'] = None; s['rtyp'] = set(); s['rsum'] = None
            if t > LASTSLIP.get((ch, tid), -1): LASTSLIP[(ch, tid)] = t
            continue
        if who == 'H': s['h'] = True
        if who in ('H', 'A'):
            ty = sample_at(t, x)                 # samples count from 19 ส.ค. 2026 on
            if ty:
                had_smp = True; s['typ'].add(ty); tys.add(ty); s['rtyp'].add(ty)
                if not s['smp']: s['smp'] = stamp(t); FIRST[ch][s['smp'][:7]] += 1
                if s['rsmp'] is None: s['rsmp'] = t
        if i in marks:
            if not s['sum']: s['sum'] = stamp(t)
            if s['rsum'] is None: s['rsum'] = t
    for ty in tys: TYP[ch][mo][ty] += 1
    if marks:
        m0 = msgs[min(marks)]
        COH.append((ch, tid, mo, m0[0], m0[3] if (ch == 'line' and m0[1] == 'H') else None))
    if st == 'W': s['won'] = True
    MON[ch][mo][0] += bool(marks); MON[ch][mo][1] += had_smp
    info = [stamp(s['rsmp']) if s['rsmp'] is not None else '', ','.join(sorted(s['rtyp'])),
            stamp(s['rsum']) if s['rsum'] is not None else '', stamp(s['slip']) if s['slip'] is not None else '']
    if mo < STAGE_FROM or st in ('X', 'G') or st is None: return '', info
    if st == 'W': g = 'W'
    elif not s['h']: g = 'N'
    elif (s['slip'] is not None and s['rsmp'] is None and s['rsum'] is None) or \
         (reg and s['slip'] is None and not marks and not had_smp): g = 'P'     # existing student, no new sales round
    elif s['rsum'] is not None: g = 'A2' if s['rsmp'] is not None else 'B2'
    else: g = 'A1' if s['rsmp'] is not None else 'A0'
    c = STG[ch].setdefault(mo, {}); c[g] = c.get(g, 0) + 1
    return g, info


def fb_msgs(c, tx, b):
    out = []
    for m in c[18]:
        x = str(tx(m[2])); r = m[1]
        if r == 3 or x.startswith(SYS): continue
        out.append((b + m[0], 'C' if r == 0 else ('H' if r == 1 else 'A'), x, None))
    return out


def rows_fb_like(ch, mo, rows, tx):
    b = base(mo)
    for c in rows:
        while len(c) < 48: c.append(None)
        g, info = step(ch, str(c[19]), mo, c[37], fb_msgs(c, tx, b))
        c[46] = g or None; c[47] = info if (info[0] or info[2] or info[3]) else None


agg = load('src/agg.json')
months = sorted(set([p[-12:-5] for p in glob.glob('src/fb_*.json')] + [p[-12:-5] for p in glob.glob('src/line_*.json')]))
ig = load('src/ig_all.json')
if ig: months = sorted(set(months) | set(ig['months'].keys()))
for mo in months:
    p = 'src/fb_%s.json' % mo; f = load(p)
    if f:
        rows_fb_like('fb', mo, f['chats'], tx_of(f['dict'])); dump(f, p); del f
    if ig and mo in ig['months']:
        rows_fb_like('ig', mo, ig['months'][mo]['leads'], tx_of(ig['dict']))
    p = 'src/line_%s.json' % mo; f = load(p)
    if f:
        tx = tx_of(f['dict']); y = int(mo[:4])
        for r in f['rooms']:
            msgs = []
            for m in r.get('tr') or []:
                try:
                    t = int((datetime.datetime(y, int(m[0][:2]), int(m[0][3:5]), int(m[0][6:8]), int(m[0][9:11])) - T0).total_seconds() // 60)
                except Exception:
                    continue
                msgs.append((t, 'C' if m[1] == 'C' else ('A' if m[1] == 'B' else 'H'), str(tx(m[2])), m[1]))
            msgs.sort(key=lambda m: m[0])
            mk = summary_marks([(t, who != 'C', x) for t, who, x, _ in msgs])
            if mk and msgs[mk[0]][1] == 'H':          # LINE names the admin: credit whoever sent the room's first summary card this month
                sb = SBY.setdefault(mo, {}); nm = msgs[mk[0]][3]; sb[nm] = sb.get(nm, 0) + 1
            reg = any('สมัครแล้ว' in str(x) for x in (r.get('tg') or []))
            g, info = step('line', str(r.get('id')), mo, r.get('sg'), msgs, reg)
            r['s6'] = g or None; r['s6i'] = info if (info[0] or info[2] or info[3]) else None
        dump(f, p); del f
if ig: dump(ig, 'src/ig_all.json')

# follow-through: of the chats that got a summary card in month M, how many sent a verified slip AFTER that card
# (any later month, up to the data end) -> adm[ch][M]['sumpaid'] · LINE per admin -> ['sbypaid']
PAID = collections.defaultdict(int); SBYP = collections.defaultdict(lambda: collections.defaultdict(int))
for ch, tid, mo, t0, nm in COH:
    ok = LASTSLIP.get((ch, tid), -1) > t0
    PAID[(ch, mo)] += ok
    if nm: SBYP[mo][nm] += ok
agg['stg'] = STG
for ch in MON:
    for mo, (ns, nm) in MON[ch].items():
        a = ((agg.get('adm') or {}).get(ch) or {}).get(mo)
        if a is not None:
            a['sum'] = ns; a['smp'] = nm; a['sumpaid'] = PAID.get((ch, mo), 0)
            if ch == 'line': a['sby'] = SBY.get(mo, {}); a['sbypaid'] = dict(SBYP.get(mo, {}))
agg['stgfrom'] = STAGE_FROM
dump(agg, 'src/agg.json')
# log (counts only): stages of the last 2 months, rows with a summary / a sample (by type), month of each thread's first sample
for ch in STG:
    for mo in sorted(STG[ch])[-2:]:
        c = STG[ch][mo]; ty = TYP[ch][mo]
        print('stage %s %s %s | sum %d paid %d smp %d (%s)' % (ch, mo, ' '.join('%s=%d' % (k, c.get(k, 0)) for k in ('N', 'A0', 'A1', 'A2', 'B2', 'W', 'P')),
              MON[ch][mo][0], PAID.get((ch, mo), 0), MON[ch][mo][1], ' '.join('%s %d' % (k, ty[k]) for k in ('clip', 'trial', 'other') if ty[k])))
for ch in FIRST:
    print('first-sample %s: %s' % (ch, ' '.join('%s %d' % (k[2:], FIRST[ch][k]) for k in sorted(FIRST[ch]))))

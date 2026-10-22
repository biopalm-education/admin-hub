# -*- coding: utf-8 -*-
"""ดึง Meta Ads ทุกระดับ รายเดือน/รายวัน ลงชีต "ข้อมูล Meta Ads ..." (เพิ่มแท็บใหม่ ไม่แตะแท็บเดิม)

รันใน GitHub Actions ผ่าน Composio MCP ตัวเดียวกับ refresh-dashboard (secret COMPOSIO_API_KEY)
repo นี้ public: log บอกแค่ขั้นตอน จำนวนแถว และผลตรวจ (ตรง/ไม่ตรง) — ไม่พิมพ์ยอดเงิน ชื่อ ข้อความ หรือ ID
ID ของชีตและบัญชีโฆษณาไม่ได้เขียนไว้ในไฟล์นี้ — หาเองตอนรันแล้วเทียบกับ hash ด้านล่าง
"""
import os, re, sys, json, time, hashlib, threading, datetime as dt
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import composio_shim as S

SHEET_HASH = 'f9f3b35957058228bafcf2655714bb7cb2f11f8b32c5d28e2a94e3b3afa60bb8'
ACT_HASH = '08d8b72a01af222cdd8bdf0a1693ca700448249f2ba096b0b185c5c57d97a098'
SHEET_QUERY = 'ข้อมูล Meta Ads'
SINCE = os.environ.get('SINCE') or '2026-01-01'
UNTIL = os.environ.get('UNTIL') or '2026-10-21'
ONLY = set(x for x in (os.environ.get('ONLY') or '').split(',') if x)
LA = ZoneInfo('America/Los_Angeles'); BKK = ZoneInfo('Asia/Bangkok')
WORKERS = int(os.environ.get('WORKERS') or 4)
T0 = time.time()
SID = None; ACT = None


def log(*a):
    print('%5.0fs' % (time.time() - T0), *a, flush=True)


def _safe(err):
    s = str(err)
    s = re.sub(r'"(?:[^"\\]|\\.)*"', '"…"', s)
    s = re.sub(r"'(?:[^'\\]|\\.)*'", "'…'", s)
    s = re.sub(r'[฀-๿]+', '…', s)
    s = re.sub(r'\d{8,}', '<id>', s)
    s = re.sub(r'[A-Za-z0-9_\-]{25,}', '<id>', s)
    return s[:240]


class CallError(RuntimeError):
    pass


def call(slug, args, tries=3):
    res, err = S.run_composio_tool(slug, args, retry_params={'max_retries': tries, 'delay_ms': 3000})
    if err:
        raise CallError('%s: %s' % (slug, err))      # ข้อความดิบไว้ตัดสินใจ · ทุกจุดที่พิมพ์ผ่าน _safe แล้ว
    d = res.get('data')
    return d if d is not None else {}


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


# ---------------------------------------------------------------- เวลา
def months():
    out = []; d = dt.date.fromisoformat(SINCE); end = dt.date.fromisoformat(UNTIL)
    while d <= end:
        nxt = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        out.append((d.isoformat(), min(nxt - dt.timedelta(days=1), end).isoformat()))
        d = nxt
    return out


def spans(days):
    out = []; d = dt.date.fromisoformat(SINCE); end = dt.date.fromisoformat(UNTIL)
    while d <= end:
        e = min(d + dt.timedelta(days=days - 1), end)
        out.append((d.isoformat(), e.isoformat())); d = e + dt.timedelta(days=1)
    return out


# ---------------------------------------------------------------- ดึง insights
LEVEL_STATUS = {
    'ad': ['ACTIVE', 'PAUSED', 'DELETED', 'PENDING_REVIEW', 'DISAPPROVED', 'PREAPPROVED', 'PENDING_BILLING_INFO',
           'CAMPAIGN_PAUSED', 'ARCHIVED', 'ADSET_PAUSED', 'IN_PROCESS', 'WITH_ISSUES'],
    'adset': ['ACTIVE', 'PAUSED', 'DELETED', 'CAMPAIGN_PAUSED', 'ARCHIVED', 'IN_PROCESS', 'WITH_ISSUES'],
    'campaign': ['ACTIVE', 'PAUSED', 'DELETED', 'ARCHIVED', 'IN_PROCESS', 'WITH_ISSUES'],
}
NOFILTER = set()
STATS = {'calls': 0, 'shrink': 0}
_slock = threading.Lock()


def pull(level, fields, tinc, since, until, breakdowns=None, page=20, action_types=None):
    """ดึงทุกหน้า · คำตอบใหญ่เกิน → ลดขนาดหน้า · ผ่านติดกัน 8 ครั้ง → ขยายกลับ (ไม่เกิน 2 เท่าของค่าเริ่ม)"""
    out, after, size, fails, streak, cap = [], None, page, 0, 0, page * 2
    while True:
        args = {'object_id': ACT, 'level': level, 'fields': fields, 'time_increment': tinc, 'limit': size,
                'time_range': {'since': since, 'until': until}}
        filt = []
        if level in LEVEL_STATUS and level not in NOFILTER:
            filt.append({'field': level + '.effective_status', 'operator': 'IN', 'value': LEVEL_STATUS[level]})
        if action_types:
            filt.append({'field': 'action_type', 'operator': 'IN', 'value': action_types})
        if filt:
            args['filtering'] = filt
        if breakdowns:
            args['breakdowns'] = breakdowns
        if after:
            args['after'] = after
        try:
            d = call('METAADS_GET_INSIGHTS', args, tries=2)
            with _slock: STATS['calls'] += 1
        except CallError as e:
            msg = str(e)
            if 'effective_status' in msg and level not in NOFILTER:
                log('  ตัวกรองสถานะใช้ไม่ได้ที่ระดับ', level, '→ ดึงแบบไม่กรอง'); NOFILTER.add(level); continue
            fails += 1
            if any(k in msg for k in ('limit reached', '(#17)', '(#4)', '(#613)', '80000', '80004', 'too many calls', 'Too Many')):
                if fails > 12:
                    raise
                time.sleep(60)           # ติดโควตา Meta → พักแล้วลองต่อ
                continue
            if 'TOO_LARGE' in msg and size > 1:
                old = size; size = max(1, old // 2); cap = min(cap, old - 1); streak = 0
                with _slock: STATS['shrink'] += 1
                continue
            if action_types and fails == 2:
                log('  ตัวกรองประเภทผลลัพธ์ใช้ไม่ได้ (%s) → ดึงแบบไม่กรอง' % level); action_types = None
                continue
            if fails <= 4:
                time.sleep(10 * fails)
                continue
            raise
        fails = 0
        streak += 1
        if streak >= 8 and size < cap:
            size, streak = min(cap, int(size * 1.5) + 1), 0
        if not isinstance(d, dict) or 'data' not in d:
            raise CallError('METAADS_GET_INSIGHTS: คำตอบไม่มี data')
        out += d.get('data') or []
        pg = d.get('paging') or {}
        nxt = (pg.get('cursors') or {}).get('after')
        if not pg.get('next') or not nxt or nxt == after:
            break
        after = nxt
    return out


def pull_chunks(name, level, fields, tinc, chunks, **kw):
    t = time.time()
    with ThreadPoolExecutor(WORKERS) as ex:
        res = list(ex.map(lambda ch: pull(level, fields, tinc, ch[0], ch[1], **kw), chunks))
    rows = [r for part in res for r in part]
    log('ดึง %-14s %7d แถว  (%d ช่วง, %.0f วินาที, รวม %d คำขอ)' % (name, len(rows), len(chunks), time.time() - t, STATS['calls']))
    return rows


# ---------------------------------------------------------------- แปลงค่า
def num(x):
    if x is None or x == '':
        return ''
    try:
        v = float(x)
        return int(v) if v.is_integer() and abs(v) < 1e15 else v
    except Exception:
        return ''


def r4(x):
    return '' if x in ('', None) else round(float(x), 4)


def amap(lst):
    d = {}
    for a in (lst or []):
        try:
            d[a['action_type']] = float(a.get('value', 0))
        except Exception:
            pass
    return d


def lsum(lst):
    return num(sum(float(a.get('value', 0)) for a in lst)) if lst else ''


def lval(lst):
    return num(lst[0].get('value')) if lst else ''


def pick(a, *keys):
    for k in keys:
        if k in a:
            return num(a[k])
    return ''


def div(a, b, nd=4):
    try:
        a = float(a); b = float(b)
        return round(a / b, nd) if b else ''
    except Exception:
        return ''


CHAT = 'onsite_conversion.messaging_conversation_started_7d'
CONN = 'onsite_conversion.total_messaging_connection'
FIRST = 'onsite_conversion.messaging_first_reply'
LEAD_KEYS = ('lead', 'onsite_conversion.lead')
KEY_ACTIONS = [CHAT, CONN, FIRST, 'lead', 'onsite_conversion.lead', 'omni_purchase', 'post_engagement', 'video_view',
               'outbound_click']

M_COLS = ['Impressions (ครั้งที่แสดง)', 'Reach (คนที่เห็น)', 'Frequency (เห็นเฉลี่ยกี่ครั้ง/คน)', 'Spend (ยอดใช้จ่าย บาท)',
          'CPM (บาท/1,000 ครั้ง)', 'Clicks (คลิกทั้งหมด)', 'CTR (คลิก/ครั้งที่แสดง)', 'CPC (บาท/คลิก)',
          'Link clicks (คลิกลิงก์)', 'CTR ลิงก์', 'ต้นทุนต่อคลิกลิงก์ (บาท)', 'Unique clicks', 'Outbound clicks',
          'เริ่มแชท (7 วัน)', 'ต้นทุนต่อการเริ่มแชท (บาท)', 'การเชื่อมต่อแชททั้งหมด', 'ลูกค้าตอบกลับครั้งแรก',
          'ลีด', 'การซื้อ', 'การมีส่วนร่วมกับโพสต์', 'ดูวิดีโอ 3 วินาที', 'ThruPlay', 'ต้นทุนต่อ ThruPlay (บาท)']
V_COLS = ['ดูถึง 25%', 'ดูถึง 50%', 'ดูถึง 75%', 'ดูถึง 95%', 'ดูถึง 100%', 'ดู 30 วินาที', 'เวลาดูเฉลี่ย (วินาที)']
BD_COLS = [c for c in M_COLS if c not in ('Unique clicks', 'Outbound clicks', 'ThruPlay', 'ต้นทุนต่อ ThruPlay (บาท)')]
HOUR_COLS = ['Impressions (ครั้งที่แสดง)', 'Spend (ยอดใช้จ่าย บาท)', 'CPM (บาท/1,000 ครั้ง)', 'Clicks (คลิกทั้งหมด)',
             'CTR (คลิก/ครั้งที่แสดง)', 'CPC (บาท/คลิก)', 'Link clicks (คลิกลิงก์)', 'เริ่มแชท (7 วัน)', 'ต้นทุนต่อการเริ่มแชท (บาท)']

F_STD = ['date_start', 'date_stop', 'impressions', 'reach', 'frequency', 'spend', 'cpm', 'clicks', 'ctr', 'cpc',
         'inline_link_clicks', 'inline_link_click_ctr', 'cost_per_inline_link_click', 'unique_clicks',
         'outbound_clicks', 'actions', 'video_thruplay_watched_actions', 'cost_per_thruplay']
F_VID = ['video_p25_watched_actions', 'video_p50_watched_actions', 'video_p75_watched_actions',
         'video_p95_watched_actions', 'video_p100_watched_actions', 'video_30_sec_watched_actions',
         'video_avg_time_watched_actions']
F_BD = ['date_start', 'date_stop', 'impressions', 'reach', 'frequency', 'spend', 'cpm', 'clicks', 'ctr', 'cpc',
        'inline_link_clicks', 'inline_link_click_ctr', 'cost_per_inline_link_click', 'actions']
F_BD_HOUR = ['date_start', 'date_stop', 'impressions', 'spend', 'cpm', 'clicks', 'ctr', 'cpc', 'inline_link_clicks', 'actions']
IDS_AD = ['campaign_id', 'campaign_name', 'adset_id', 'adset_name', 'ad_id', 'ad_name']
IDS_AS = ['campaign_id', 'campaign_name', 'adset_id', 'adset_name']
IDS_C = ['campaign_id', 'campaign_name']


def metrics(r):
    a = amap(r.get('actions'))
    spend = num(r.get('spend'))
    chats = pick(a, CHAT)
    pct = lambda k: '' if num(r.get(k)) == '' else round(float(r[k]) / 100, 6)
    return {
        'Impressions (ครั้งที่แสดง)': num(r.get('impressions')),
        'Reach (คนที่เห็น)': num(r.get('reach')),
        'Frequency (เห็นเฉลี่ยกี่ครั้ง/คน)': r4(num(r.get('frequency'))),
        'Spend (ยอดใช้จ่าย บาท)': spend,
        'CPM (บาท/1,000 ครั้ง)': r4(num(r.get('cpm'))),
        'Clicks (คลิกทั้งหมด)': num(r.get('clicks')),
        'CTR (คลิก/ครั้งที่แสดง)': pct('ctr'),
        'CPC (บาท/คลิก)': r4(num(r.get('cpc'))),
        'Link clicks (คลิกลิงก์)': num(r.get('inline_link_clicks')),
        'CTR ลิงก์': pct('inline_link_click_ctr'),
        'ต้นทุนต่อคลิกลิงก์ (บาท)': r4(num(r.get('cost_per_inline_link_click'))),
        'Unique clicks': num(r.get('unique_clicks')),
        'Outbound clicks': lsum(r.get('outbound_clicks')),
        'เริ่มแชท (7 วัน)': chats,
        'ต้นทุนต่อการเริ่มแชท (บาท)': div(spend, chats),
        'การเชื่อมต่อแชททั้งหมด': pick(a, CONN),
        'ลูกค้าตอบกลับครั้งแรก': pick(a, FIRST),
        'ลีด': pick(a, *LEAD_KEYS),
        'การซื้อ': pick(a, 'omni_purchase'),
        'การมีส่วนร่วมกับโพสต์': pick(a, 'post_engagement'),
        'ดูวิดีโอ 3 วินาที': pick(a, 'video_view'),
        'ThruPlay': lval(r.get('video_thruplay_watched_actions')),
        'ต้นทุนต่อ ThruPlay (บาท)': r4(lval(r.get('cost_per_thruplay'))),
        'ดูถึง 25%': lval(r.get('video_p25_watched_actions')),
        'ดูถึง 50%': lval(r.get('video_p50_watched_actions')),
        'ดูถึง 75%': lval(r.get('video_p75_watched_actions')),
        'ดูถึง 95%': lval(r.get('video_p95_watched_actions')),
        'ดูถึง 100%': lval(r.get('video_p100_watched_actions')),
        'ดู 30 วินาที': lval(r.get('video_30_sec_watched_actions')),
        'เวลาดูเฉลี่ย (วินาที)': lval(r.get('video_avg_time_watched_actions')),
    }


def mrow(r, cols):
    m = metrics(r)
    return [m[c] for c in cols]


def dedupe(rows, keyf):
    seen = {}
    for r in rows:
        seen[keyf(r)] = r
    return list(seen.values())


def spend_key(r):
    try:
        return -float(r.get('spend') or 0)
    except Exception:
        return 0


def fsum(rows, key='spend'):
    return round(sum(float(r.get(key) or 0) for r in rows), 2)


ACTION_DESC = json.load(open(os.path.join(HERE, 'action_desc.json'), encoding='utf-8'))
TABS = {}
AD_FIRST_LAST = {}


# ---------------------------------------------------------------- สร้างตาราง
def build_monthly(adset_m, ad_m):
    rows = dedupe(adset_m, lambda r: (r['date_start'], r['adset_id']))
    rows.sort(key=lambda r: (r['date_start'], spend_key(r)))
    TABS['ชุดโฆษณารายเดือน'] = dict(
        title='ผลของแต่ละชุดโฆษณาแยกรายเดือน %s ถึง %s' % (SINCE, UNTIL),
        note='วันที่นับตามเวลาบัญชี (Los Angeles) · Reach บวกข้ามเดือนไม่ได้ · ชื่อเป็นชื่อปัจจุบัน ณ วันที่ดึง',
        header=['เดือน (เริ่ม)', 'เดือน (จบ)', 'Ad set ID', 'ชื่อชุดโฆษณา', 'Campaign ID', 'ชื่อแคมเปญ'] + M_COLS,
        rows=[[r['date_start'], r['date_stop'], r['adset_id'], r.get('adset_name', ''), r['campaign_id'],
               r.get('campaign_name', '')] + mrow(r, M_COLS) for r in rows])
    rows = dedupe(ad_m, lambda r: (r['date_start'], r['ad_id']))
    rows.sort(key=lambda r: (r['date_start'], spend_key(r)))
    TABS['โฆษณารายเดือน'] = dict(
        title='ผลของแต่ละโฆษณาแยกรายเดือน %s ถึง %s' % (SINCE, UNTIL),
        note='วันที่นับตามเวลาบัญชี (Los Angeles) · Reach บวกข้ามเดือนไม่ได้ · ข้อความโฆษณา/ครีเอทีฟอยู่แท็บ "โฆษณาและครีเอทีฟ" (จับคู่ด้วย Ad ID)',
        header=['เดือน (เริ่ม)', 'เดือน (จบ)', 'Ad ID', 'ชื่อโฆษณา', 'Ad set ID', 'ชื่อชุดโฆษณา', 'Campaign ID', 'ชื่อแคมเปญ'] + M_COLS + V_COLS,
        rows=[[r['date_start'], r['date_stop'], r['ad_id'], r.get('ad_name', ''), r['adset_id'], r.get('adset_name', ''),
               r['campaign_id'], r.get('campaign_name', '')] + mrow(r, M_COLS + V_COLS) for r in rows])


D_COLS = ['Impressions (ครั้งที่แสดง)', 'Reach (คนที่เห็น)', 'Frequency (เห็นเฉลี่ยกี่ครั้ง/คน)', 'Spend (ยอดใช้จ่าย บาท)',
          'CPM (บาท/1,000 ครั้ง)', 'Clicks (คลิกทั้งหมด)', 'CTR (คลิก/ครั้งที่แสดง)', 'CPC (บาท/คลิก)',
          'Link clicks (คลิกลิงก์)', 'CTR ลิงก์', 'ต้นทุนต่อคลิกลิงก์ (บาท)', 'เริ่มแชท (7 วัน)', 'ต้นทุนต่อการเริ่มแชท (บาท)',
          'การเชื่อมต่อแชททั้งหมด', 'ลูกค้าตอบกลับครั้งแรก', 'ลีด', 'การซื้อ', 'การมีส่วนร่วมกับโพสต์', 'ดูวิดีโอ 3 วินาที']
F_DAY = ['ad_id', 'date_start', 'impressions', 'reach', 'spend', 'clicks', 'inline_link_clicks', 'actions']


def day_row(r):
    a = amap(r.get('actions'))
    imp, reach, sp = num(r.get('impressions')), num(r.get('reach')), num(r.get('spend'))
    cl, lk, ch = num(r.get('clicks')), num(r.get('inline_link_clicks')), pick(a, CHAT)
    return [imp, reach, div(imp, reach), sp, div(float(sp or 0) * 1000, imp), cl, div(cl, imp, 6), div(sp, cl), lk,
            div(lk, imp, 6), div(sp, lk), ch, div(sp, ch), pick(a, CONN), pick(a, FIRST), pick(a, *LEAD_KEYS),
            pick(a, 'omni_purchase'), pick(a, 'post_engagement'), pick(a, 'video_view')]


def build_daily(ad_d, ad_m):
    names = {r['ad_id']: r for r in ad_m}
    rows = dedupe(ad_d, lambda r: (r['date_start'], r['ad_id']))
    rows.sort(key=lambda r: (r['date_start'], spend_key(r)))
    out = []
    for r in rows:
        n = names.get(r['ad_id'], {})
        if float(r.get('impressions') or 0) > 0:
            fl = AD_FIRST_LAST.setdefault(r['ad_id'], [r['date_start'], r['date_start']])
            fl[0] = min(fl[0], r['date_start']); fl[1] = max(fl[1], r['date_start'])
        out.append([r['date_start'], r['ad_id'], n.get('ad_name', ''), n.get('adset_id', ''), n.get('adset_name', ''),
                    n.get('campaign_id', ''), n.get('campaign_name', '')] + day_row(r))
    TABS['โฆษณารายวัน'] = dict(
        title='ผลของแต่ละโฆษณารายวัน %s ถึง %s (วันตามเวลาบัญชี LA)' % (SINCE, UNTIL),
        note='1 วันของบัญชี (LA) เริ่ม 14:00 น. เวลาไทย (15:00 น. ช่วง 1 ม.ค.-7 มี.ค.) · เทียบกับแชท: เอาเวลาแชท (ไทย) ลบ 14 ชม. (ลบ 15 ชม. ก่อน 8 มี.ค.) จะได้วันที่ในคอลัมน์ A · ค่าเฉลี่ย (CPM, CTR, CPC ฯลฯ) คำนวณจากยอดในแถว · สถิติวิดีโอละเอียดอยู่แท็บ โฆษณารายเดือน',
        header=['วันที่ (เวลาบัญชี LA)', 'Ad ID', 'ชื่อโฆษณา', 'Ad set ID', 'ชื่อชุดโฆษณา', 'Campaign ID', 'ชื่อแคมเปญ'] + D_COLS,
        rows=out)
    return out


def build_actions(camp_a):
    rows = dedupe(camp_a, lambda r: (r['date_start'], r['campaign_id']))
    rows.sort(key=lambda r: (r['date_start'], spend_key(r)))
    out = []
    for r in rows:
        A = amap(r.get('actions')); U = amap(r.get('unique_actions')); C = amap(r.get('cost_per_action_type'))
        CU = amap(r.get('cost_per_unique_action_type')); V = amap(r.get('action_values'))
        types = list(A) + [t for t in dict.fromkeys(list(U) + list(C) + list(CU) + list(V)) if t not in A]
        for t in types:
            out.append([r['date_start'], r['date_stop'], r['campaign_id'], r.get('campaign_name', ''), t, ACTION_DESC.get(t, ''),
                        num(A.get(t, '')), num(U.get(t, '')), r4(num(C.get(t, ''))), r4(num(CU.get(t, ''))), num(V.get(t, ''))])
    TABS['ผลลัพธ์ทุกประเภทรายเดือน'] = dict(
        title='ผลลัพธ์ทุกประเภทที่ Meta นับให้ แยกแคมเปญ รายเดือน %s ถึง %s' % (SINCE, UNTIL),
        note='คำอธิบายภาษาไทยแปลโดย Claude ช่องที่ว่างคือประเภทที่ยังไม่ได้แปล · นับตาม attribution ที่ตั้งไว้ในแต่ละชุดโฆษณา · เดือนนับตามเวลาบัญชี (LA)',
        header=['เดือน (เริ่ม)', 'เดือน (จบ)', 'Campaign ID', 'ชื่อแคมเปญ', 'ประเภทผลลัพธ์ (action_type)', 'คำอธิบาย', 'จำนวน',
                'จำนวน (คนไม่ซ้ำ)', 'ต้นทุนต่อครั้ง (บาท)', 'ต้นทุนต่อคนไม่ซ้ำ (บาท)', 'มูลค่า (บาท)'],
        rows=out)


def bd_rows(rows, dims, cols):
    rows = dedupe(rows, lambda r: (r['date_start'], r['campaign_id']) + tuple(str(r.get(d)) for d in dims))
    rows.sort(key=lambda r: (r['date_start'], r.get('campaign_name', ''), spend_key(r)))
    return [[r['date_start'], r['date_stop'], r['campaign_id'], r.get('campaign_name', '')] + [r.get(d, '') for d in dims] +
            mrow(r, cols) for r in rows]


def build_breakdowns(B):
    H = ['เดือน (เริ่ม)', 'เดือน (จบ)', 'Campaign ID', 'ชื่อแคมเปญ']
    TABS['อายุและเพศ แยกแคมเปญ'] = dict(
        title='แยกอายุกับเพศ ของแต่ละแคมเปญ รายเดือน', note='unknown คือ Meta ไม่ทราบอายุหรือเพศ · เดือนนับตามเวลาบัญชี (LA)',
        header=H + ['อายุ', 'เพศ'] + BD_COLS, rows=bd_rows(B['age'], ['age', 'gender'], BD_COLS))
    TABS['ประเทศและจังหวัด แยกแคมเปญ'] = dict(
        title='แยกประเทศ ของแต่ละแคมเปญ รายเดือน', note='ตารางที่ 2 (แยกจังหวัด/ภูมิภาค) อยู่ด้านล่าง',
        header=H + ['ประเทศ'] + BD_COLS, rows=bd_rows(B['country'], ['country'], BD_COLS),
        t2=dict(title='แยกจังหวัด/ภูมิภาค ของแต่ละแคมเปญ รายเดือน', header=H + ['จังหวัด/ภูมิภาค'] + BD_COLS,
                rows=bd_rows(B['region'], ['region'], BD_COLS)))
    TABS['แพลตฟอร์มและอุปกรณ์ แยกแคมเปญ'] = dict(
        title='แยกแพลตฟอร์ม ตำแหน่งที่แสดง และรุ่นอุปกรณ์ ของแต่ละแคมเปญ รายเดือน', note='ตารางที่ 2 (มือถือ/เดสก์ท็อป) อยู่ด้านล่าง',
        header=H + ['แพลตฟอร์ม', 'ตำแหน่ง', 'อุปกรณ์ที่เห็น'] + BD_COLS,
        rows=bd_rows(B['platform'], ['publisher_platform', 'platform_position', 'impression_device'], BD_COLS),
        t2=dict(title='แยกมือถือกับเดสก์ท็อป ของแต่ละแคมเปญ รายเดือน', header=H + ['ประเภทอุปกรณ์'] + BD_COLS,
                rows=bd_rows(B['device'], ['device_platform'], BD_COLS)))
    TABS['รายชั่วโมง แยกแคมเปญ'] = dict(
        title='แยกช่วงชั่วโมงของวัน ของแต่ละแคมเปญ รายเดือน',
        note='ชั่วโมงเป็นเวลาท้องถิ่นของผู้ชม (คนไทยคือเวลาไทย) Meta ไม่ให้ Reach ในมุมนี้',
        header=H + ['ช่วงเวลา (เวลาของผู้ชม)'] + HOUR_COLS,
        rows=bd_rows(B['hour'], ['hourly_stats_aggregated_by_audience_time_zone'], HOUR_COLS))


def find_key(o, key, out):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key:
                out.append(v)
            find_key(v, key, out)
    elif isinstance(o, list):
        for v in o:
            find_key(v, key, out)
    return out


def welcome_parts(raw):
    try:
        j = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return str(raw)[:5000], ''
    texts = [t for t in find_key(j, 'text', []) if isinstance(t, str) and t.strip()]
    texts += [t for t in find_key(j, 'greeting', []) if isinstance(t, str) and t.strip()]
    btn = []
    for lst in find_key(j, 'ice_breakers', []):
        for it in (lst or []):
            if isinstance(it, dict) and (it.get('title') or it.get('question')):
                t = str(it.get('title') or it.get('question'))
                if it.get('response'):
                    t += ' → ' + str(it['response'])
                btn.append(t)
    for lst in find_key(j, 'quick_replies', []):
        for it in (lst or []):
            if isinstance(it, dict) and it.get('title'):
                btn.append(str(it['title']))
    auto = [c for c in find_key(j, 'content', []) if isinstance(c, str) and c.strip()]
    if auto:
        btn.append('ข้อความที่ลูกค้ากดส่ง: ' + ' / '.join(dict.fromkeys(auto)))
    return '\n---\n'.join(dict.fromkeys(texts))[:5000], ' | '.join(dict.fromkeys(btn))[:3000]


def pretty(raw):
    if not raw:
        return ''
    try:
        return json.dumps(json.loads(raw) if isinstance(raw, str) else raw, ensure_ascii=False)
    except Exception:
        return str(raw)


def thai_time(s):
    try:
        return dt.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S%z').astimezone(BKK).strftime('%Y-%m-%d %H:%M')
    except Exception:
        return s or ''


def pull_creatives(ad_ids):
    out = {}
    fields = ['id', 'name', 'adset_id', 'campaign_id', 'effective_status', 'created_time', 'adset{destination_type}',
              'creative{id,object_type,page_welcome_message}']
    batches = [ad_ids[i:i + 3] for i in range(0, len(ad_ids), 3)]

    def one(b):
        try:
            d = call('METAADS_GET_MULTIPLE_OBJECTS', {'object_ids': b, 'fields': fields}, tries=3)
            return (d.get('results') if isinstance(d, dict) and isinstance(d.get('results'), dict) else d) or {}
        except CallError:
            res = {}
            for x in b:   # ก้อนพลาด → ทีละตัว
                try:
                    d = call('METAADS_GET_MULTIPLE_OBJECTS', {'object_ids': [x], 'fields': fields}, tries=3)
                    res.update((d.get('results') if isinstance(d.get('results'), dict) else d) or {})
                except CallError:
                    pass
            return res
    with ThreadPoolExecutor(WORKERS) as ex:
        for part in ex.map(one, batches):
            for k, v in (part or {}).items():
                if isinstance(v, dict) and v.get('id'):
                    out[str(k)] = v
    log('ดึง creatives       %7d จาก %d โฆษณา' % (len(out), len(ad_ids)))
    return out


def build_welcome(ads, ad_m):
    chats, names = {}, {}
    for r in ad_m:
        chats[r['ad_id']] = chats.get(r['ad_id'], 0) + amap(r.get('actions')).get(CHAT, 0)
        names[r['ad_id']] = r
    out = []
    for ad_id in sorted(names):
        v = ads.get(ad_id, {}); n = names[ad_id]
        cr = v.get('creative') or {}
        raw = cr.get('page_welcome_message') or (find_key(cr, 'page_welcome_message', []) or [''])[0]
        text, btn = welcome_parts(raw) if raw else ('', '')
        fl = AD_FIRST_LAST.get(ad_id, ['', ''])
        out.append([ad_id, v.get('name') or n.get('ad_name', ''), n.get('adset_id', ''), n.get('adset_name', ''),
                    n.get('campaign_id', ''), n.get('campaign_name', ''), v.get('effective_status', ''),
                    thai_time(v.get('created_time')), (v.get('adset') or {}).get('destination_type', ''), text, btn,
                    fl[0], fl[1], num(chats.get(ad_id, 0)), pretty(raw)[:5000]])
    out.sort(key=lambda x: (-(x[13] or 0), x[0]))
    TABS['ข้อความต้อนรับแชทของโฆษณา'] = dict(
        title='ข้อความต้อนรับใน Messenger ของแต่ละโฆษณา (ตัวเชื่อมแชทกับโฆษณา)',
        note='ใน FB chat log แชทที่มาจากโฆษณาจะมีข้อความระบบ "…ตอบกลับโฆษณา" ตามด้วยข้อความต้อนรับในคอลัมน์ J · ถ้าหลายโฆษณาใช้ข้อความเดียวกัน ให้แปลงเวลาแชทเป็นวันที่ LA (ลบ 14 ชม. / 15 ชม. ก่อน 8 มี.ค.) แล้วดูคอลัมน์ L-M และแท็บ "โฆษณารายวัน" ว่าวันนั้นโฆษณาไหนได้แชท',
        header=['Ad ID', 'ชื่อโฆษณา', 'Ad set ID', 'ชื่อชุดโฆษณา', 'Campaign ID', 'ชื่อแคมเปญ', 'สถานะจริง', 'สร้างเมื่อ (เวลาไทย)',
                'ปลายทาง', 'ข้อความต้อนรับ (ข้อความแรกที่ลูกค้าเห็นในแชท)', 'ปุ่มคำถาม / ตอบด่วน (→ คำตอบอัตโนมัติ)',
                'วันแรกที่แสดงผล (เวลาบัญชี LA)', 'วันสุดท้ายที่แสดงผล (เวลาบัญชี LA)', 'เริ่มแชทรวมทั้งช่วง (7 วัน)', 'ข้อความต้อนรับ (JSON ดิบ)'],
        rows=out)
    return sum(1 for r in out if r[9])


# ---------------------------------------------------------------- เขียนชีต
MAX_ROWS, MAX_BYTES = 800, 400000
ORDER = ['อ่านก่อน', 'บัญชีโฆษณา', 'รายวัน', 'แคมเปญ', 'แคมเปญรายเดือน', 'ชุดโฆษณา', 'ชุดโฆษณารายเดือน',
         'โฆษณาและครีเอทีฟ', 'โฆษณารายเดือน', 'โฆษณารายวัน', 'ข้อความต้อนรับแชทของโฆษณา',
         'ผลลัพธ์ทุกประเภท', 'ผลลัพธ์ทุกประเภทรายเดือน', 'อายุและเพศ', 'อายุและเพศ แยกแคมเปญ', 'ประเทศและจังหวัด',
         'ประเทศและจังหวัด แยกแคมเปญ', 'แพลตฟอร์มและอุปกรณ์', 'แพลตฟอร์มและอุปกรณ์ แยกแคมเปญ', 'รายชั่วโมง',
         'รายชั่วโมง แยกแคมเปญ', 'กลุ่มเป้าหมายที่บันทึก', 'ประวัติการแก้ไข', 'รูปภาพในบัญชี', 'แหล่งข้อมูล']


def q(t):
    return "'" + t.replace("'", "''") + "'"


def col(n):
    s = ''
    while n:
        n, r = divmod(n - 1, 26); s = chr(65 + r) + s
    return s


def cellv(v):
    if v is None:
        return ''
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v
    v = str(v)
    return v if len(v) <= 45000 else v[:45000] + ' …[ตัด]'


def tabs():
    d = call('GOOGLESHEETS_GET_SPREADSHEET_INFO', {'spreadsheet_id': SID,
             'fields': 'sheets.properties(sheetId,title,index,gridProperties(rowCount,columnCount))'})
    out = {}
    for s in d.get('sheets') or []:
        p = s.get('properties') or {}
        gp = p.get('gridProperties') or {}
        out[p.get('title')] = {'id': p.get('sheetId'), 'index': p.get('index', 0), 'rows': gp.get('rowCount', 0), 'cols': gp.get('columnCount', 0)}
    return out


def write(tab, rows, start):
    if not rows:
        return 0
    width = max(len(r) for r in rows)
    rows = [[cellv(v) for v in r] + [''] * (width - len(r)) for r in rows]
    i, n, calls, size, fails = 0, len(rows), 0, MAX_ROWS, 0
    while i < n:
        j = min(n, i + size)
        while j - i > 20 and len(json.dumps(rows[i:j])) > MAX_BYTES:
            j = i + max(20, (j - i) // 2)
        chunk = rows[i:j]
        rng = '%s!A%d:%s%d' % (q(tab), start + i, col(width), start + j - 1)
        try:
            d = call('GOOGLESHEETS_VALUES_UPDATE', {'spreadsheet_id': SID, 'range': rng, 'value_input_option': 'RAW',
                                                    'values': chunk, 'auto_expand_sheet': True}, tries=2)
            got = d.get('updatedRows') if isinstance(d, dict) else None
            if isinstance(got, int) and got < len(chunk):
                raise CallError('เขียนได้ %d จาก %d แถว' % (got, len(chunk)))
        except CallError:
            fails += 1
            if fails >= 6:
                raise
            size = max(20, len(chunk) // 2)
            time.sleep(5 * fails)
            continue
        calls += 1; fails = 0; i = j
    return calls


HDR = dict(bold=True, background_color='#1F3864', text_color='#FFFFFF', wrap_strategy='WRAP', vertical_alignment='MIDDLE', fontSize=10)


def nfmt(h):
    if h.startswith('CTR'):
        return ('PERCENT', '0.00%')
    if h.startswith('Frequency'):
        return ('NUMBER', '0.00')
    if any(h.startswith(p) for p in ('Spend', 'CPM', 'CPC', 'ต้นทุน', 'มูลค่า', 'เวลาดูเฉลี่ย')):
        return ('NUMBER', '#,##0.00')
    if any(h.startswith(p) for p in ('Impressions', 'Reach', 'Clicks', 'Link clicks', 'Unique', 'Outbound', 'เริ่มแชท',
                                     'การเชื่อมต่อ', 'ลูกค้าตอบกลับ', 'ลีด', 'การซื้อ', 'การมีส่วนร่วม', 'ดูวิดีโอ',
                                     'ThruPlay', 'ดูถึง', 'ดู 30', 'จำนวน')):
        return ('NUMBER', '#,##0')
    return None


def width_of(h):
    if h.startswith('ข้อความต้อนรับ (ข้อความแรก'):
        return 420
    if h.startswith('ปุ่มคำถาม') or h.startswith('ชั่วโมงที่มีคนเริ่มแชท') or h.startswith('ข้อความต้อนรับ (JSON'):
        return 260
    if h.startswith('ชื่อ'):
        return 220
    return 120


def fmt(tab, a1, **kw):
    args = {'spreadsheet_id': SID, 'sheet_name': tab, 'range': a1}
    args.update(kw)
    try:
        call('GOOGLESHEETS_FORMAT_CELL', args, tries=3)
    except CallError as e:
        log('  จัดรูปแบบไม่ผ่าน (ข้าม):', tab, _safe(e))


def style(tab, t, sheet_id):
    fmt(tab, 'A1', bold=True, fontSize=12, background_color='#FFFFFF')
    fmt(tab, 'A2', italic=True, text_color='#595959', background_color='#FFFFFF', fontSize=10)
    tables = [(t['header'], 4, 5, 4 + len(t['rows']))]
    if 't2' in t:
        r0 = 5 + len(t['rows']) + 2
        fmt(tab, 'A%d' % r0, bold=True, fontSize=12, background_color='#FFFFFF')
        tables.append((t['t2']['header'], r0 + 1, r0 + 2, r0 + 1 + len(t['t2']['rows'])))
    for hdr, hrow, d0, d1 in tables:
        fmt(tab, 'A%d:%s%d' % (hrow, col(len(hdr)), hrow), **HDR)
        if d1 < d0:
            continue
        i = 0
        while i < len(hdr):
            f = nfmt(hdr[i]); j = i
            while j + 1 < len(hdr) and nfmt(hdr[j + 1]) == f:
                j += 1
            if f:
                fmt(tab, '%s%d:%s%d' % (col(i + 1), d0, col(j + 1), d1), number_format_type=f[0], number_format_pattern=f[1],
                    background_color='#FFFFFF', fontSize=10)
            i = j + 1
    hdr = t['header']
    i = 0
    while i < len(hdr):
        w = width_of(hdr[i]); j = i
        while j + 1 < len(hdr) and width_of(hdr[j + 1]) == w:
            j += 1
        if w != 100:
            try:
                call('GOOGLESHEETS_UPDATE_DIMENSION_PROPERTIES', {'spreadsheet_id': SID, 'sheet_id': sheet_id, 'dimension': 'COLUMNS',
                                                                  'start_index': i, 'end_index': j + 1, 'pixel_size': w}, tries=2)
            except CallError:
                pass
        i = j + 1


def put_tab(tab):
    t = TABS[tab]
    n1 = len(t['rows'])
    total = 4 + n1 + ((3 + len(t['t2']['rows'])) if 't2' in t else 0)
    ncols = max(len(t['header']), len(t['t2']['header']) if 't2' in t else 0)
    cur = tabs()
    if tab in cur:
        call('GOOGLESHEETS_DELETE_SHEET', {'spreadsheetId': SID, 'sheetId': cur[tab]['id']})
    try:
        call('GOOGLESHEETS_ADD_SHEET', {'spreadsheet_id': SID, 'title': tab, 'force_unique': False,
                                        'properties': {'title': tab, 'gridProperties': {'rowCount': total + 5, 'columnCount': ncols,
                                                                                        'frozenRowCount': 4}}}, tries=1)
    except CallError:
        if tab not in tabs():          # สร้างสำเร็จแต่คำตอบหลุด → ใช้ต่อ
            raise
    sheet_id = tabs()[tab]['id']
    c = write(tab, [[t['title']], [t['note']], [''], t['header']], 1)
    c += write(tab, t['rows'], 5)
    if 't2' in t:
        r0 = 5 + n1 + 2
        c += write(tab, [[t['t2']['title']], t['t2']['header']], r0)
        c += write(tab, t['t2']['rows'], r0 + 2)
    style(tab, t, sheet_id)
    log('เขียน %-32s %7d แถว (%d ครั้ง)' % (tab, n1 + (len(t['t2']['rows']) if 't2' in t else 0), c))


def reorder():
    cur = tabs()
    present = [x for x in ORDER if x in cur] + sorted((x for x in cur if x not in ORDER), key=lambda x: cur[x]['index'])
    for i, title in enumerate(present):
        cur = tabs()
        if cur[title]['index'] != i:
            call('GOOGLESHEETS_UPDATE_SHEET_PROPERTIES', {'spreadsheetId': SID, 'updateSheetProperties': {
                'properties': {'sheetId': cur[title]['id'], 'index': i}, 'fields': 'index'}})


def vget(rng):
    d = call('GOOGLESHEETS_VALUES_GET', {'spreadsheet_id': SID, 'range': rng})
    return d.get('values') or []


NEW_TAB_LINES = [
    'ชุดโฆษณารายเดือน: ผลของแต่ละชุดโฆษณาแยกเดือน',
    'โฆษณารายเดือน: ผลของแต่ละโฆษณาแยกเดือน พร้อมสถิติวิดีโอ',
    'โฆษณารายวัน: ผลของแต่ละโฆษณารายวัน ตามวันของบัญชี (LA) ตัวเลขตรงกับ Ads Manager ใช้เทียบกับ chat log รายวัน',
    'ข้อความต้อนรับแชทของโฆษณา: ข้อความแรกที่ลูกค้าเห็นในแชทหลังกดโฆษณา ใช้จับคู่แชทกับโฆษณา',
    'ผลลัพธ์ทุกประเภทรายเดือน: ทุกประเภทผลลัพธ์ที่ Meta นับให้ แยกแคมเปญรายเดือน',
    'อายุและเพศ, ประเทศและจังหวัด, แพลตฟอร์มและอุปกรณ์, รายชั่วโมง "แยกแคมเปญ": มุมเดียวกับแท็บทั้งบัญชี แต่แยกแต่ละแคมเปญรายเดือน',
]
OBS_LINES = [
    '',
    'เชื่อมกับ chat log ใน Obsidian',
    'Ad ID, Ad set ID และ Campaign ID ไม่ซ้ำกันและไม่เปลี่ยนแม้เปลี่ยนชื่อ ใช้เป็นชื่อโน้ตหรือ property ได้',
    'แชท FB ที่มาจากโฆษณาจะมีข้อความระบบ "…ตอบกลับโฆษณา" ตามด้วยข้อความต้อนรับ ใช้ข้อความนั้นจับคู่กับแท็บ "ข้อความต้อนรับแชทของโฆษณา"',
    'วันที่ทุกแท็บโฆษณานับตามเวลาบัญชี (LA) ส่วน chat log เป็นเวลาไทย · แปลงเวลาแชทเป็นวันที่ LA: ลบ 14 ชม. (8 มี.ค.-31 ต.ค.) หรือ 15 ชม. (ก่อน 8 มี.ค.) เช่น แชท 13 ต.ค. 09:00 น. = วันที่ 12 ต.ค. ของบัญชี',
    'ถ้าหลายโฆษณาใช้ข้อความต้อนรับเดียวกัน ให้ดูวันที่ LA ของแชท เทียบช่วงที่โฆษณาแสดงผล (แท็บข้อความต้อนรับ คอลัมน์ L-M) และแท็บ "โฆษณารายวัน" ว่าวันนั้นโฆษณาไหนได้แชท',
]


def update_readme(pulled):
    vals = vget("'อ่านก่อน'!A1:A200")
    colv = [(r[0] if r else '') for r in vals]
    find = lambda p: next((i for i, v in enumerate(colv) if v.startswith(p)), None)
    i_title, i_pulled, i_src = find('ข้อมูล Meta Ads'), find('ดึงเมื่อ:'), find('แหล่งข้อมูล:')
    if i_title is not None:
        write('อ่านก่อน', [['ข้อมูล Meta Ads ม.ค.-ต.ค. 2026 ครบทุกระดับ: ทุกอย่างที่ดึงได้จากบัญชีโฆษณา แยกหมวดตามแท็บ']], i_title + 1)
    if i_pulled is not None and 'รอบ 2' not in colv[i_pulled]:
        write('อ่านก่อน', [[colv[i_pulled] + ' · แท็บที่เพิ่มรอบ 2 (รายเดือน/รายวันทุกระดับ) ดึงเมื่อ ' + pulled]], i_pulled + 1)
    if i_src is not None and not any(v.startswith('ชุดโฆษณารายเดือน:') for v in colv):
        call('GOOGLESHEETS_INSERT_DIMENSION', {'spreadsheet_id': SID, 'insert_dimension': {
            'range': {'sheet_id': tabs()['อ่านก่อน']['id'], 'dimension': 'ROWS', 'start_index': i_src, 'end_index': i_src + len(NEW_TAB_LINES)},
            'inherit_from_before': True}})
        write('อ่านก่อน', [[x] for x in NEW_TAB_LINES], i_src + 1)
    if not any(v.startswith('เชื่อมกับ chat log ใน Obsidian') for v in colv):
        last = len(vget("'อ่านก่อน'!A1:A200"))
        write('อ่านก่อน', [[x] for x in OBS_LINES], last + 1)
        fmt('อ่านก่อน', 'A%d' % (last + 2), bold=True, background_color='#FFFFFF', fontSize=10)


STATUS_KEY = 'สถานะงาน meta-ads-export'
_status_row = None


def set_status(text):
    """แถวสถานะในแท็บ แหล่งข้อมูล — ให้ผู้ใช้/Claude เห็นความคืบหน้าโดยไม่ต้องเปิด GitHub"""
    global _status_row
    try:
        if _status_row is None:
            vals = vget("'แหล่งข้อมูล'!A1:A400")
            _status_row = next((i + 1 for i, r in enumerate(vals) if r and r[0].startswith(STATUS_KEY)), len(vals) + 1)
        now = dt.datetime.now(BKK).strftime('%Y-%m-%d %H:%M')
        write('แหล่งข้อมูล', [[STATUS_KEY, text + ' (' + now + ' น.)']], _status_row)
    except Exception as e:
        log('เขียนสถานะไม่ได้:', _safe(e))


def update_sources(pulled, src_rows):
    set_status('เสร็จแล้ว')
    write('แหล่งข้อมูล', src_rows, _status_row + 1)


# ---------------------------------------------------------------- main
def main():
    global SID, ACT
    pulled = dt.datetime.now(BKK).strftime('%Y-%m-%d %H:%M น. (เวลาไทย)')
    # หาบัญชีโฆษณาและชีตจาก hash
    d = call('METAADS_GET_AD_ACCOUNTS', {'limit': 100, 'fields': 'id,name'})
    accts = d.get('data') if isinstance(d, dict) else d
    ACT = next((a['id'] for a in (accts or []) if sha(a.get('id', '')) == ACT_HASH), None)
    if not ACT:
        sys.exit('ไม่พบบัญชีโฆษณาที่ตรงกับ hash')
    d = call('GOOGLESHEETS_SEARCH_SPREADSHEETS', {'query': SHEET_QUERY, 'search_type': 'name', 'max_results': 50, 'include_trashed': False})
    cands = d.get('spreadsheets') or d.get('files') or []
    SID = next((x.get('id') or x.get('spreadsheetId') for x in cands
                if sha(str(x.get('id') or x.get('spreadsheetId') or '')) == SHEET_HASH), None)
    if not SID:
        sys.exit('ไม่พบชีตที่ตรงกับ hash (ค้นเจอ %d ไฟล์)' % len(cands))
    log('พบบัญชีโฆษณาและชีตแล้ว · ช่วง', SINCE, '-', UNTIL)
    set_status('กำลังดึงข้อมูลจาก Meta')

    M = months()
    acct = pull_chunks('acct_month', 'account', ['date_start', 'date_stop', 'impressions', 'spend', 'actions'], 'monthly', [(SINCE, UNTIL)],
                       page=12, action_types=[CHAT])
    adset_m = pull_chunks('adset_month', 'adset', IDS_AS + F_STD, 'monthly', M, page=12, action_types=KEY_ACTIONS)
    ad_m = pull_chunks('ad_month', 'ad', IDS_AD + F_STD + F_VID, 'monthly', M, page=8, action_types=KEY_ACTIONS)
    camp_a = pull_chunks('camp_actions', 'campaign', IDS_C + ['date_start', 'date_stop', 'spend', 'actions', 'unique_actions',
                         'cost_per_action_type', 'cost_per_unique_action_type', 'action_values'], 'monthly', M, page=2)
    B = {}
    for k, bd in [('age', ['age', 'gender']), ('country', ['country']), ('region', ['region']),
                  ('platform', ['publisher_platform', 'platform_position', 'impression_device']), ('device', ['device_platform'])]:
        B[k] = pull_chunks('bd_' + k, 'campaign', IDS_C + F_BD, 'monthly', M, breakdowns=bd, page=15, action_types=KEY_ACTIONS)
    B['hour'] = pull_chunks('bd_hour', 'campaign', IDS_C + F_BD_HOUR, 'monthly', M,
                            breakdowns=['hourly_stats_aggregated_by_audience_time_zone'], page=20, action_types=[CHAT])
    ad_d = pull_chunks('ad_day', 'ad', F_DAY, 1, spans(7), page=25, action_types=KEY_ACTIONS)
    ads = pull_creatives(sorted({r['ad_id'] for r in ad_m}))
    log('ดึงครบ · คำขอทั้งหมด %d · ลดขนาดหน้า %d ครั้ง' % (STATS['calls'], STATS['shrink']))
    set_status('ดึงครบแล้ว กำลังเขียนลงชีต')

    build_monthly(adset_m, ad_m); build_daily(ad_d, ad_m); build_actions(camp_a); build_breakdowns(B)
    n_wel = build_welcome(ads, ad_m)

    # ---- ตรวจยอด (ตัวเลขลงชีต ไม่ลง log)
    acct_sp = fsum(acct)
    checks = [('ชุดโฆษณารายเดือน', fsum(adset_m)), ('โฆษณารายเดือน', fsum(ad_m)), ('โฆษณารายวัน', fsum(ad_d)),
              ('อายุและเพศ แยกแคมเปญ', fsum(B['age'])), ('ประเทศ แยกแคมเปญ', fsum(B['country'])),
              ('จังหวัด แยกแคมเปญ', fsum(B['region'])), ('แพลตฟอร์ม แยกแคมเปญ', fsum(B['platform'])),
              ('อุปกรณ์ แยกแคมเปญ', fsum(B['device'])), ('รายชั่วโมง แยกแคมเปญ', fsum(B['hour'])),
              ('ผลลัพธ์ทุกประเภทรายเดือน', fsum(camp_a))]
    acct_chat = sum(amap(r.get('actions')).get(CHAT, 0) for r in acct)
    chat_checks = [('ชุดโฆษณารายเดือน', sum(amap(r.get('actions')).get(CHAT, 0) for r in adset_m)),
                   ('โฆษณารายเดือน', sum(amap(r.get('actions')).get(CHAT, 0) for r in ad_m)),
                   ('โฆษณารายวัน', sum(amap(r.get('actions')).get(CHAT, 0) for r in ad_d))]
    ok = {}
    for name, v in checks:
        ok[name] = abs(v - acct_sp) <= max(1.0, acct_sp * 0.0005)
        log('ตรวจยอดใช้จ่าย %-28s %s' % (name, 'ตรง' if ok[name] else 'ไม่ตรง'))
    chat_ok = {}
    for name, v in chat_checks:
        chat_ok[name] = abs(v - acct_chat) <= max(1, acct_chat * 0.002)
        log('ตรวจจำนวนเริ่มแชท %-25s %s' % (name, 'ตรง' if chat_ok[name] else 'ไม่ตรง'))
    log('โฆษณาที่มีข้อความต้อนรับ %d จาก %d' % (n_wel, len(TABS['ข้อความต้อนรับแชทของโฆษณา']['rows'])))

    # ---- เขียน
    for tab in ['ชุดโฆษณารายเดือน', 'โฆษณารายเดือน', 'โฆษณารายวัน', 'ข้อความต้อนรับแชทของโฆษณา',
                'ผลลัพธ์ทุกประเภทรายเดือน', 'อายุและเพศ แยกแคมเปญ', 'ประเทศและจังหวัด แยกแคมเปญ',
                'แพลตฟอร์มและอุปกรณ์ แยกแคมเปญ', 'รายชั่วโมง แยกแคมเปญ']:
        if not ONLY or tab in ONLY:
            put_tab(tab)
            set_status('กำลังเขียนลงชีต · เสร็จแท็บ ' + tab)
    reorder()
    req = 'ขอข้อมูลทั้งหมดครบทุกเดือน ทุกระดับ (ม.ค.-ต.ค. 2026) เพื่อนำไปเชื่อมกับ chat log ใน Obsidian'
    via = 'Composio (บัญชี metaads ของ biopalm_ads_read) ผ่าน GitHub Actions admin-hub (meta-ads-export) เขียนโดย Claude'
    tr = 'time_range=%s ถึง %s (เวลาบัญชี)' % (SINCE, UNTIL)
    cd = dict(chat_checks)
    def chk(*names):
        out = []
        for name in names:
            out.append('%s: ยอดใช้จ่าย %s บาท เทียบระดับบัญชี %s บาท (%s)' % (
                name, format(dict(checks).get(name, 0), ',.2f'), format(acct_sp, ',.2f'), 'ตรง' if ok.get(name) else 'ไม่ตรง'))
            if name in cd:
                out.append('เริ่มแชท %s เทียบระดับบัญชี %s (%s)' % (format(cd[name], ',.0f'), format(acct_chat, ',.0f'),
                                                               'ตรง' if chat_ok.get(name) else 'ไม่ตรง'))
        return ' · '.join(out)
    def L(tab):
        t = TABS[tab]; return len(t['rows']) + (len(t['t2']['rows']) if 't2' in t else 0)
    src = [
        ['ชุดโฆษณารายเดือน!A4', 'Meta Marketing API v26.0', 'GET /act_…/insights', via, req, 'level=adset, time_increment=monthly, ' + tr, pulled, 'ผู้ใช้', L('ชุดโฆษณารายเดือน'), 'แตกผลลัพธ์แชท/ลีด/ซื้อออกจาก actions CTR แปลงเป็นสัดส่วน', chk('ชุดโฆษณารายเดือน')],
        ['โฆษณารายเดือน!A4', 'Meta Marketing API v26.0', 'GET /act_…/insights', via, req, 'level=ad, time_increment=monthly, ' + tr, pulled, 'ผู้ใช้', L('โฆษณารายเดือน'), 'เหมือนด้านบน + สถิติวิดีโอ', chk('โฆษณารายเดือน')],
        ['โฆษณารายวัน!A4', 'Meta Marketing API v26.0', 'GET /act_…/insights', via, req, 'level=ad, time_increment=1, fields=impressions,reach,spend,clicks,inline_link_clicks,actions, ' + tr, pulled, 'ผู้ใช้', L('โฆษณารายวัน'), 'ชื่อโฆษณา/ชุด/แคมเปญเติมจากแท็บรายเดือนด้วย ID · ค่าเฉลี่ยคำนวณจากยอดในแถว', chk('โฆษณารายวัน')],
        ['ข้อความต้อนรับแชทของโฆษณา!A4', 'Meta Marketing API v26.0', 'GET /?ids=… fields=creative{page_welcome_message}', via, req, 'เฉพาะโฆษณาที่มีผลในช่วงนี้', pulled, 'ผู้ใช้', L('ข้อความต้อนรับแชทของโฆษณา'), 'แตกข้อความ ปุ่มคำถาม และคำตอบอัตโนมัติจาก JSON (เก็บ JSON ดิบไว้คอลัมน์สุดท้าย)', 'มีข้อความต้อนรับ %d โฆษณา' % n_wel],
        ['ผลลัพธ์ทุกประเภทรายเดือน!A4', 'Meta Marketing API v26.0', 'GET /act_…/insights', via, req, 'level=campaign, time_increment=monthly, fields=actions,unique_actions,cost_per_action_type,cost_per_unique_action_type,action_values, ' + tr, pulled, 'ผู้ใช้', L('ผลลัพธ์ทุกประเภทรายเดือน'), 'แถวละ 1 ประเภทผลลัพธ์ คำอธิบายภาษาไทยใช้ชุดเดียวกับแท็บ ผลลัพธ์ทุกประเภท', chk('ผลลัพธ์ทุกประเภทรายเดือน')],
        ['อายุและเพศ แยกแคมเปญ!A4', 'Meta Marketing API v26.0', 'GET /act_…/insights', via, req, 'level=campaign, breakdowns=age,gender, time_increment=monthly, ' + tr, pulled, 'ผู้ใช้', L('อายุและเพศ แยกแคมเปญ'), 'แตกผลลัพธ์แชทออกจาก actions', chk('อายุและเพศ แยกแคมเปญ')],
        ['ประเทศและจังหวัด แยกแคมเปญ!A4', 'Meta Marketing API v26.0', 'GET /act_…/insights', via, req, 'level=campaign, breakdowns=country และ region (ตาราง 2), time_increment=monthly, ' + tr, pulled, 'ผู้ใช้', L('ประเทศและจังหวัด แยกแคมเปญ'), 'แตกผลลัพธ์แชทออกจาก actions', chk('ประเทศ แยกแคมเปญ', 'จังหวัด แยกแคมเปญ')],
        ['แพลตฟอร์มและอุปกรณ์ แยกแคมเปญ!A4', 'Meta Marketing API v26.0', 'GET /act_…/insights', via, req, 'level=campaign, breakdowns=publisher_platform,platform_position,impression_device และ device_platform (ตาราง 2), time_increment=monthly, ' + tr, pulled, 'ผู้ใช้', L('แพลตฟอร์มและอุปกรณ์ แยกแคมเปญ'), 'แตกผลลัพธ์แชทออกจาก actions', chk('แพลตฟอร์ม แยกแคมเปญ', 'อุปกรณ์ แยกแคมเปญ')],
        ['รายชั่วโมง แยกแคมเปญ!A4', 'Meta Marketing API v26.0', 'GET /act_…/insights', via, req, 'level=campaign, breakdowns=hourly_stats_aggregated_by_audience_time_zone, time_increment=monthly, ' + tr, pulled, 'ผู้ใช้', L('รายชั่วโมง แยกแคมเปญ'), 'แตกผลลัพธ์แชทออกจาก actions', chk('รายชั่วโมง แยกแคมเปญ')],
    ]
    update_sources(pulled, src)
    update_readme(pulled)
    fails = {k: v[0] for k, v in S.FAILS.items()}
    log('เสร็จ · Composio พลาดชั่วคราวระหว่างทาง:', fails or 'ไม่มี')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print('ล้มเหลว:', type(e).__name__, _safe(e), flush=True)
        if SID:
            set_status('ล้มเหลว: ' + type(e).__name__ + ' ' + _safe(e))
        sys.exit(1)

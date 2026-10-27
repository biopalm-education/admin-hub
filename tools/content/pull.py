# -*- coding: utf-8 -*-
"""Insight คอนเทนต์ออร์แกนิก Facebook Page + Instagram (Biopalm) → Google Sheet + vault Obsidian (Content/)

ทุกโพสต์ตั้งแต่ SINCE (ค่าเริ่ม 1 ม.ค. 2026 เวลาไทย): ภาพเดี่ยว / อัลบั้ม / วิดีโอ / Reel / ข้อความ-ลิงก์
  FB : ยอดดู (post_media_view) · คนดูไม่ซ้ำ · reaction · คอมเมนต์ · แชร์
  IG : ยอดดู · reach · ไลก์ · คอมเมนต์ · เซฟ · แชร์ · interaction รวม · เข้าโปรไฟล์ · ฟอลโลว์ใหม่
       Reel เพิ่ม: เวลาดูเฉลี่ย · เวลาดูรวม · อัตราปัดทิ้งใน 3 วินาทีแรก
ผลลัพธ์
  * ชีต "Biopalm Content Insight — FB/IG 2026" (ข้อมูลดิบ เขียนทับทั้งแท็บทุกรอบ)
  * vault private biopalm-insight: Content/<FB|IG>/<เดือน>/<วันที่> <ช่องทาง> <ประเภท> <ID>.md (1 โพสต์ = 1 โน้ต)
    + Content/สรุปคอนเทนต์.md + .vault/content/posts.json

รันใน GitHub Actions (.github/workflows/obsidian-content.yml) ผ่าน Composio MCP ตัวเดียวกับงานอื่น (secret COMPOSIO_API_KEY)
repo นี้ public: log บอกแค่ขั้นตอนและจำนวน — ไม่พิมพ์ ID ข้อความโพสต์ หรือตัวเลข insight · ID เพจ/ชีต ไม่ได้เขียนไว้ในไฟล์ (เทียบ hash)
"""
import os, re, sys, json, time, hashlib, statistics as st, datetime as dt
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'meta_ads'))
import composio_shim as S

PAGE_HASH = '73025ff6d1ad9be87ec1ef93b274a8ce62bfbbcb64343d40d49c01cb5b7cceb1'
SHEET_HASH = '1083f419af879f018fb3894f00949c682e04f9a96db4519f2a39ac0b657ae59f'
SHEET_QUERY = 'Biopalm Content Insight'
VAULT_REPO = os.environ.get('VAULT_REPO') or 'biopalm-education/biopalm-insight'
OWNER, REPO = VAULT_REPO.split('/')
BKK = ZoneInfo('Asia/Bangkok')
SINCE = os.environ.get('SINCE') or '2026-01-01'
DRY = (os.environ.get('DRY_RUN') or '').strip().lower() in ('1', 'true', 'yes')
WORKERS = int(os.environ.get('WORKERS') or 3)
T0 = time.time()
STATS = {'calls': 0, 'shrink': 0, 'fb_ins_fail': 0, 'ig_ins_fail': 0, 'ig_ins_partial': 0, 'fb_no_caption': 0}
TH_M = ['', 'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']


def log(*a):
    print('%5.0fs' % (time.time() - T0), *a, flush=True)


def _safe(err):
    s = str(err)
    s = re.sub(r'"(?:[^"\\]|\\.)*"', '"…"', s)
    s = re.sub(r'[฀-๿]+', '…', s)
    s = re.sub(r'\d{8,}', '<id>', s)
    s = re.sub(r'[A-Za-z0-9_\-]{25,}', '<id>', s)
    return s[:200]


class CallError(RuntimeError):
    pass


def call(slug, args, tries=4):
    res, err = S.run_composio_tool(slug, args, retry_params={'max_retries': tries, 'delay_ms': 3000})
    STATS['calls'] += 1
    if err:
        raise CallError('%s: %s' % (slug, err))
    d = res.get('data')
    return d if d is not None else {}


def sha(s):
    return hashlib.sha256(str(s).encode()).hexdigest()


def rows_of(d):
    """รายการใน {'data': [...]} ที่อาจห่อหลายชั้น"""
    for _ in range(4):
        if isinstance(d, list):
            return d
        if isinstance(d, dict) and 'data' in d:
            d = d['data']
        else:
            return []
    return d if isinstance(d, list) else []


def after_of(d):
    for _ in range(4):
        if not isinstance(d, dict):
            return None
        p = d.get('paging')
        if isinstance(p, dict):
            return (p.get('cursors') or {}).get('after') if p.get('next') else None
        d = d.get('data')
    return None


def since_ts():
    return int(dt.datetime.fromisoformat(SINCE).replace(tzinfo=BKK).timestamp())


def to_bkk(s):
    s = str(s or '').replace('+0000', '+00:00')
    try:
        return dt.datetime.fromisoformat(s).astimezone(BKK)
    except ValueError:
        return None


# ---------------------------------------------------------------- รายการโพสต์
def paged(slug, base, limit, stop_before=None):
    out, after, seen = [], None, set()
    while True:
        args = dict(base, limit=limit)
        if after:
            args['after'] = after
        try:
            d = call(slug, args)
        except CallError as e:
            if 'TOO_LARGE' in str(e) and limit > 5:
                limit = max(5, limit // 2)
                STATS['shrink'] += 1
                continue
            raise
        items = rows_of(d)
        new = [x for x in items if isinstance(x, dict) and x.get('id') not in seen]
        for x in new:
            seen.add(x.get('id'))
        out.extend(new)
        after = after_of(d)
        if not items or not after or not new:
            break
        if stop_before:
            last = to_bkk(new[-1].get('created_time') or new[-1].get('timestamp'))
            if last and last < stop_before:
                break
    return out


def fb_posts(page, start):
    """โพสต์เพจ FB ตั้งแต่ start (ใหม่ → เก่า)
    FACEBOOK_GET_PAGE_POSTS ไม่มีช่อง 'after' — Composio ตัดทิ้งเงียบ ๆ แล้วคืนหน้าแรกซ้ำ (รอบแรกจึงได้แค่ 12 โพสต์)
    → ไล่ย้อนด้วย until = เวลาโพสต์เก่าสุดของหน้าก่อน · until รวมวินาทีนั้นด้วย จึงกรอง ID ซ้ำออก"""
    out, seen, limit, until, lite = [], set(), 10, None, False
    for _ in range(1000):                                  # กันวนไม่จบ
        args = {'page_id': page, 'fields': FB_FIELDS_LITE if lite else FB_FIELDS, 'since': str(since_ts()), 'limit': limit}
        if until is not None:
            args['until'] = str(until)
        try:
            d = call('FACEBOOK_GET_PAGE_POSTS', args)
        except CallError as e:
            if 'TOO_LARGE' in str(e) and limit > 1:       # แคปชันยาว คำตอบเกินขนาดที่ Composio ส่งกลับ
                limit = max(1, limit // 2)
                STATS['shrink'] += 1
                continue
            if 'TOO_LARGE' in str(e) and not lite:         # โพสต์เดียวยังใหญ่เกิน → เอาหน้านี้แบบไม่มีแคปชัน
                lite = True
                continue
            raise
        items = [x for x in rows_of(d) if isinstance(x, dict) and x.get('id')]
        ts = [t for t in (to_bkk(x.get('created_time')) for x in items) if t]
        new = [x for x in items if x['id'] not in seen]
        for x in new:
            seen.add(x['id'])
            if lite:
                x['_no_caption'] = True
                STATS['fb_no_caption'] += 1
        out.extend(new)
        if lite:
            lite = False
        elif limit < 10:
            limit = min(10, limit * 2)                     # ผ่านหน้าหนักแล้ว ค่อยขยายหน้ากลับ
        if not ts or min(ts) < start:
            break
        oldest = int(min(ts).timestamp())
        stuck = until is not None and oldest >= until       # ทั้งหน้าอยู่วินาทีเดียวกับ until เดิม
        if not new and not stuck:
            break                                          # ไม่มีโพสต์ใหม่แล้ว
        until = oldest - 1 if stuck else oldest            # stuck → ถอยอีก 1 วินาทีไม่ให้วนซ้ำ
    else:
        raise CallError('FB: หน้าเกิน 1000 รอบ')
    return out


def find_page():
    d = call('FACEBOOK_LIST_MANAGED_PAGES', {'fields': 'id,name', 'limit': 50})
    for p in rows_of(d):
        if sha(p.get('id', '')) == PAGE_HASH:
            return p['id']
    return None


FB_FIELDS = ('id,created_time,status_type,permalink_url,message,from{id},attachments{media_type,url},'
             'reactions.summary(true).limit(0),comments.summary(true).limit(0),shares')
FB_FIELDS_LITE = FB_FIELDS.replace('message,', '')


def fb_format(p):
    att = ((p.get('attachments') or {}).get('data') or [{}])[0] or {}
    mt = str(att.get('media_type') or '').lower()
    stt = str(p.get('status_type') or '')
    link = str(p.get('permalink_url') or '') + ' ' + str(att.get('url') or '')
    if mt == 'video' or stt == 'added_video':
        return 'Reel' if '/reel/' in link else 'วิดีโอ'
    if mt == 'album':
        return 'อัลบั้ม'
    if mt == 'photo' or stt == 'added_photos':
        return 'ภาพเดี่ยว'
    if stt == 'shared_story':
        return 'แชร์ต่อ'
    if mt in ('link', 'share') or stt == 'mobile_status_update':
        return 'ข้อความ/ลิงก์'
    return 'อื่น ๆ'


def ig_format(m):
    if m.get('media_product_type') == 'REELS':
        return 'Reel'
    return {'CAROUSEL_ALBUM': 'อัลบั้ม', 'IMAGE': 'ภาพเดี่ยว', 'VIDEO': 'วิดีโอ'}.get(m.get('media_type'), 'อื่น ๆ')


def group_of(f):
    return 'ภาพนิ่ง' if f in ('ภาพเดี่ยว', 'อัลบั้ม') else ('วิดีโอ' if f in ('Reel', 'วิดีโอ') else 'อื่น ๆ')


# ---------------------------------------------------------------- insight
def metric_map(d):
    out = {}
    for x in rows_of(d):
        if not isinstance(x, dict) or not x.get('name'):
            continue
        if x.get('period') not in (None, 'lifetime'):
            continue
        v = ((x.get('values') or [{}])[0] or {}).get('value')
        if v is None:
            v = (x.get('total_value') or {}).get('value')
        out[x['name']] = v
    return out


def fb_insight(pid):
    try:
        return metric_map(call('FACEBOOK_GET_POST_INSIGHTS', {'post_id': pid, 'metrics': 'post_media_view,post_total_media_view_unique',
                                                              'period': 'lifetime'}))
    except CallError:
        STATS['fb_ins_fail'] += 1
        return {}


IG_BASE = ['views', 'reach', 'likes', 'comments', 'saved', 'shares', 'total_interactions']
IG_FEED = ['profile_visits', 'follows']
IG_REEL = ['ig_reels_avg_watch_time', 'ig_reels_video_view_total_time', 'reels_skip_rate']


def ig_call(mid, metrics):
    return metric_map(call('INSTAGRAM_GET_IG_MEDIA_INSIGHTS', {'ig_media_id': mid, 'metric': metrics}, tries=2))


def ig_insight(m):
    extra = IG_REEL if m.get('media_product_type') == 'REELS' else (IG_FEED if m.get('media_type') in ('IMAGE', 'CAROUSEL_ALBUM') else [])
    try:
        return ig_call(m['id'], IG_BASE + extra)
    except CallError:
        pass
    out = {}
    try:
        out.update(ig_call(m['id'], IG_BASE))
    except CallError:
        STATS['ig_ins_fail'] += 1
        return {}
    for x in extra:                                   # เมตริกเสริมทีละตัว ตัวไหนไม่รองรับก็ข้าม
        try:
            out.update(ig_call(m['id'], [x]))
        except CallError:
            pass
    STATS['ig_ins_partial'] += 1
    return out


# ---------------------------------------------------------------- แปลงเป็นแถว
def first_line(t, n=120):
    t = re.sub(r'\s+', ' ', str(t or '')).strip()
    return t if len(t) <= n else t[:n].rstrip() + '…'


def num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def pct(a, b):
    return round(100.0 * a / b, 2) if a is not None and b else None


def build_fb(posts, page_id, ins):
    out = []
    for p in posts:
        fr = (p.get('from') or {}).get('id')
        if fr and fr != page_id:
            continue                                  # โพสต์ของคนอื่นบนหน้าเพจ
        t = to_bkk(p.get('created_time'))
        if not t or t < dt.datetime.fromisoformat(SINCE).replace(tzinfo=BKK):
            continue
        m = ins.get(p['id']) or {}
        rx = ((p.get('reactions') or {}).get('summary') or {}).get('total_count')
        cm = ((p.get('comments') or {}).get('summary') or {}).get('total_count')
        sh = (p.get('shares') or {}).get('count') or 0
        inter = sum(x for x in (rx, cm, sh) if isinstance(x, int))
        views, uniq = num(m.get('post_media_view')), num(m.get('post_total_media_view_unique'))
        f = fb_format(p)
        out.append(dict(platform='FB', posted=t.strftime('%Y-%m-%d %H:%M'), month=t.strftime('%Y-%m'), format=f, group=group_of(f),
                        post_id=p['id'], key=p['id'].split('_')[-1], link=p.get('permalink_url') or '',
                        caption='(แคปชันยาวเกินกว่าที่ดึงได้ — เปิดลิงก์โพสต์)' if p.get('_no_caption') else str(p.get('message') or ''), views=views, reach=uniq, likes=rx, comments=cm, shares=sh, saved=None,
                        interactions=inter, rate=pct(inter, uniq), profile_visits=None, follows=None,
                        avg_watch_s=None, watch_total_h=None, skip_rate=None))
    return out


def build_ig(media, ins):
    out = []
    for x in media:
        t = to_bkk(x.get('timestamp'))
        if not t or t < dt.datetime.fromisoformat(SINCE).replace(tzinfo=BKK):
            continue
        m = ins.get(x['id']) or {}
        f = ig_format(x)
        reach = num(m.get('reach'))
        inter = num(m.get('total_interactions'))
        aw, tt = num(m.get('ig_reels_avg_watch_time')), num(m.get('ig_reels_video_view_total_time'))
        out.append(dict(platform='IG', posted=t.strftime('%Y-%m-%d %H:%M'), month=t.strftime('%Y-%m'), format=f, group=group_of(f),
                        post_id=x['id'], key=x.get('shortcode') or x['id'], link=x.get('permalink') or '',
                        caption=str(x.get('caption') or ''), views=num(m.get('views')), reach=reach,
                        likes=num(m.get('likes')) if m.get('likes') is not None else x.get('like_count'),
                        comments=num(m.get('comments')) if m.get('comments') is not None else x.get('comments_count'),
                        shares=num(m.get('shares')), saved=num(m.get('saved')), interactions=inter, rate=pct(inter, reach),
                        profile_visits=num(m.get('profile_visits')), follows=num(m.get('follows')),
                        avg_watch_s=round(aw / 1000.0, 1) if aw is not None else None,
                        watch_total_h=round(tt / 3600000.0, 1) if tt is not None else None, skip_rate=num(m.get('reels_skip_rate'))))
    return out


# ---------------------------------------------------------------- Google Sheet
SID = None


def find_sheet():
    d = call('GOOGLESHEETS_SEARCH_SPREADSHEETS', {'query': SHEET_QUERY, 'search_type': 'name', 'max_results': 20, 'include_trashed': False})
    cands = (d.get('spreadsheets') or d.get('files') or []) if isinstance(d, dict) else []
    return next((x.get('id') or x.get('spreadsheetId') for x in cands
                 if sha(x.get('id') or x.get('spreadsheetId') or '') == SHEET_HASH), None)


def tabs():
    d = call('GOOGLESHEETS_GET_SPREADSHEET_INFO', {'spreadsheet_id': SID, 'fields': 'sheets.properties(sheetId,title,index,gridProperties(rowCount,columnCount))'})
    return {(s.get('properties') or {}).get('title'): s.get('properties') or {} for s in d.get('sheets') or []}


def q(tab):
    return "'%s'" % tab.replace("'", "''")


def col(n):
    s = ''
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def cell(v):
    if v is None:
        return ''
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)[:40000]


def write_tab(tab, rows):
    cur = tabs()
    if tab not in cur:
        if 'ชีต1' in cur and tab == 'คำอธิบาย':
            call('GOOGLESHEETS_UPDATE_SHEET_PROPERTIES', {'spreadsheetId': SID, 'updateSheetProperties': {
                'properties': {'sheetId': cur['ชีต1'].get('sheetId', 0), 'title': tab}, 'fields': 'title'}})
        else:
            try:
                call('GOOGLESHEETS_ADD_SHEET', {'spreadsheet_id': SID, 'title': tab, 'force_unique': False,
                                                'properties': {'title': tab, 'gridProperties': {'rowCount': len(rows) + 50,
                                                                                                'columnCount': max(len(r) for r in rows) + 2,
                                                                                                'frozenRowCount': 1}}}, tries=1)
            except CallError:
                if tab not in tabs():
                    raise
    else:
        call('GOOGLESHEETS_CLEAR_VALUES', {'spreadsheet_id': SID, 'range': '%s!A1:ZZ' % q(tab)})
    width = max(len(r) for r in rows)
    rows = [[cell(v) for v in r] + [''] * (width - len(r)) for r in rows]
    i, size = 0, 300
    while i < len(rows):
        j = min(len(rows), i + size)
        while j - i > 20 and len(json.dumps(rows[i:j], ensure_ascii=False)) > 180000:
            j = i + (j - i) // 2
        call('GOOGLESHEETS_VALUES_UPDATE', {'spreadsheet_id': SID, 'range': '%s!A%d:%s%d' % (q(tab), i + 1, col(width), j),
                                            'value_input_option': 'RAW', 'values': rows[i:j], 'auto_expand_sheet': True}, tries=3)
        i = j
    log('เขียนแท็บ %s · %d แถว' % (tab, len(rows) - 1))


FB_COLS = [('วันที่โพสต์ (เวลาไทย)', 'posted'), ('เดือน', 'month'), ('ภาพนิ่ง/วิดีโอ', 'group'), ('ประเภท', 'format'), ('Post ID', 'post_id'),
           ('ลิงก์', 'link'), ('ข้อความโพสต์ (ตัดสั้น)', 'cap'), ('ยอดดู', 'views'), ('คนดูไม่ซ้ำ', 'reach'), ('Reaction', 'likes'),
           ('คอมเมนต์', 'comments'), ('แชร์', 'shares'), ('Interaction รวม', 'interactions'), ('Interaction ต่อคนดู (%)', 'rate')]
IG_COLS = [('วันที่โพสต์ (เวลาไทย)', 'posted'), ('เดือน', 'month'), ('ภาพนิ่ง/วิดีโอ', 'group'), ('ประเภท', 'format'), ('Media ID', 'post_id'),
           ('Shortcode (ท้ายลิงก์)', 'key'), ('ลิงก์', 'link'), ('แคปชัน (ตัดสั้น)', 'cap'), ('ยอดดู', 'views'), ('Reach', 'reach'),
           ('ไลก์', 'likes'), ('คอมเมนต์', 'comments'), ('เซฟ', 'saved'), ('แชร์', 'shares'), ('Interaction รวม', 'interactions'),
           ('Interaction ต่อ reach (%)', 'rate'), ('เข้าโปรไฟล์', 'profile_visits'), ('ฟอลโลว์ใหม่', 'follows'),
           ('Reel ดูเฉลี่ย (วินาที)', 'avg_watch_s'), ('Reel เวลาดูรวม (ชม.)', 'watch_total_h'), ('Reel ปัดทิ้งใน 3 วิ (%)', 'skip_rate')]


def table_rows(rows, cols):
    out = [[h for h, _ in cols]]
    for r in rows:
        r = dict(r, cap=first_line(r['caption'], 150))
        out.append([r.get(k) for _, k in cols])
    return out


def med(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(st.median(xs), 1) if xs else None


def monthly_rows(allrows):
    out = [['ช่องทาง', 'เดือน', 'ภาพนิ่ง/วิดีโอ', 'จำนวนโพสต์', 'ยอดดูรวม', 'ยอดดูมัธยฐานต่อโพสต์', 'Interaction รวม', 'Interaction มัธยฐานต่อโพสต์']]
    keys = sorted({(r['platform'], r['month'], r['group']) for r in allrows})
    for k in keys:
        rs = [r for r in allrows if (r['platform'], r['month'], r['group']) == k]
        out.append(list(k) + [len(rs), sum(r['views'] or 0 for r in rs), med([r['views'] for r in rs]),
                              sum(r['interactions'] or 0 for r in rs), med([r['interactions'] for r in rs])])
    return out


def about_rows(stamp, nfb, nig):
    return [['Biopalm Content Insight — FB/IG'],
            ['ดึงล่าสุด', stamp],
            ['ช่วงโพสต์', 'ตั้งแต่ %s (เวลาไทย) ถึงวันที่ดึง' % SINCE],
            ['จำนวนโพสต์', 'FB %d · IG %d' % (nfb, nig)],
            ['อัปเดต', 'อัตโนมัติทุกสัปดาห์ (GitHub Actions: admin-hub → obsidian-content) เขียนทับทั้งแท็บทุกรอบ — อย่าพิมพ์ข้อมูลเองในแท็บเหล่านี้'],
            ['ใน Obsidian', 'vault Biopalm-Insight → Content/ (1 โพสต์ = 1 โน้ต ชื่อไฟล์มี ID) + Content/สรุปคอนเทนต์'],
            [''],
            ['คำ', 'ความหมาย'],
            ['ยอดดู', 'FB: post_media_view = จำนวนครั้งที่โพสต์แสดงบนจอ · IG: views = จำนวนครั้งที่เล่น/แสดง (ตัวเลขชุดใหม่ของ Meta แทน impressions ที่เลิกใช้)'],
            ['คนดูไม่ซ้ำ / Reach', 'จำนวนบัญชีที่เห็นโพสต์อย่างน้อย 1 ครั้ง (ค่าประมาณจาก Meta)'],
            ['Interaction รวม', 'FB: reaction + คอมเมนต์ + แชร์ · IG: ไลก์ + เซฟ + คอมเมนต์ + แชร์ (ตัวเลขของ IG เอง)'],
            ['Interaction ต่อคนดู / ต่อ reach', 'Interaction รวม ÷ คนดูไม่ซ้ำ (หรือ reach) × 100'],
            ['ภาพนิ่ง / วิดีโอ', 'ภาพนิ่ง = ภาพเดี่ยว + อัลบั้ม · วิดีโอ = Reel + วิดีโอ · อื่น ๆ = ข้อความ/ลิงก์/แชร์ต่อ'],
            ['Reel ปัดทิ้งใน 3 วิ', 'สัดส่วนการเล่นที่ถูกปัดผ่านภายใน 3 วินาทีแรก (ยิ่งต่ำยิ่งดี)'],
            ['ข้อจำกัด', 'FB วิดีโอ: ยังไม่มีเวลาดู/ยอดดู 3 วินาที (ดึงผ่านเครื่องมือที่มีไม่ได้) · Stories ย้อนหลังไม่ได้ · ตัวเลขเป็นยอดสะสมถึงวันที่ดึง โพสต์ใหม่จะยังเพิ่มอีก'],
            ['ช่องว่าง', 'ช่องว่าง = Meta ไม่ส่งตัวเลขนั้นให้โพสต์นั้น (ไม่ใช่ 0)']]


# ---------------------------------------------------------------- vault
def yv(v):
    if v is None:
        return ''
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return str(v)
    return json.dumps(str(v), ensure_ascii=False)


def fmt_n(v, d=0):
    if v is None:
        return '–'
    return ('{:,.%df}' % d).format(v)


def date_th(s):
    d = dt.datetime.strptime(s[:10], '%Y-%m-%d')
    return '%d %s %d' % (d.day, TH_M[d.month], d.year)


def note_name(r):
    return '%s %s %s %s' % (r['posted'][:10], r['platform'], r['format'].replace('/', '-'), r['key'])


def note_path(r):
    return 'Content/%s/%s/%s.md' % (r['platform'], r['month'], note_name(r))


def post_note(r, stamp):
    props = [('type', 'content'), ('platform', r['platform']), ('format', r['format']), ('group', r['group']), ('posted', r['posted']),
             ('month', r['month']), ('post_id', r['post_id'])]
    if r['platform'] == 'IG':
        props.append(('shortcode', r['key']))
    props += [('link', r['link']), ('views', r['views']), ('reach', r['reach']), ('likes', r['likes']), ('comments', r['comments']),
              ('shares', r['shares']), ('saved', r['saved']), ('interactions', r['interactions']), ('interaction_rate', r['rate']),
              ('profile_visits', r['profile_visits']), ('follows', r['follows']), ('avg_watch_s', r['avg_watch_s']),
              ('skip_rate', r['skip_rate']), ('pulled', stamp)]
    fm = '---\n' + '\n'.join('%s: %s' % (k, yv(v)) for k, v in props if not (v is None and k in (
        'saved', 'profile_visits', 'follows', 'avg_watch_s', 'skip_rate', 'shortcode'))) + '\n---\n'
    cap = str(r['caption'] or '').strip()
    cap = cap if len(cap) <= 400 else cap[:400].rstrip() + '…'
    # บรรทัดแคปชันที่ขึ้นต้น "# " กลายเป็นหัวข้อใน Obsidian → ใส่ \ ให้เป็นตัวอักษรธรรมดา
    capq = '\n'.join('> ' + re.sub(r'^(\s*)#', r'\1\\#', ln) if re.match(r'\s*#{1,6}\s', ln) else '> ' + ln
                     for ln in cap.splitlines() if ln.strip()) or '> (ไม่มีข้อความ)'
    lab_reach = 'คนดูไม่ซ้ำ' if r['platform'] == 'FB' else 'Reach'
    lab_like = 'Reaction' if r['platform'] == 'FB' else 'ไลก์'
    rows = [('ยอดดู', fmt_n(r['views'])), (lab_reach, fmt_n(r['reach'])), (lab_like, fmt_n(r['likes'])), ('คอมเมนต์', fmt_n(r['comments'])),
            ('แชร์', fmt_n(r['shares']))]
    if r['platform'] == 'IG':
        rows += [('เซฟ', fmt_n(r['saved']))]
        if r['format'] in ('ภาพเดี่ยว', 'อัลบั้ม'):
            rows += [('เข้าโปรไฟล์', fmt_n(r['profile_visits'])), ('ฟอลโลว์ใหม่', fmt_n(r['follows']))]
    rows += [('Interaction รวม', fmt_n(r['interactions'])), ('Interaction ต่อ %s' % lab_reach, ('%.2f%%' % r['rate']) if r['rate'] is not None else '–')]
    if r['format'] == 'Reel' and r['platform'] == 'IG':
        rows += [('ดูเฉลี่ย', ('%.1f วินาที' % r['avg_watch_s']) if r['avg_watch_s'] is not None else '–'),
                 ('เวลาดูรวม', ('%.1f ชม.' % r['watch_total_h']) if r['watch_total_h'] is not None else '–'),
                 ('ปัดทิ้งใน 3 วินาทีแรก', ('%.1f%%' % r['skip_rate']) if r['skip_rate'] is not None else '–')]
    body = ['# %s · %s · %s' % (r['platform'], r['format'], date_th(r['posted'])), '',
            '[เปิดโพสต์](%s) · ID `%s`%s' % (r['link'], r['post_id'], (' · shortcode `%s`' % r['key']) if r['platform'] == 'IG' else ''), '',
            capq, '', '| ตัวเลข (สะสมถึง %s) | ค่า |' % stamp[:10], '|---|---:|'] + ['| %s | %s |' % x for x in rows] + [
            '', 'เดือนนี้: [[%s]] · ภาพรวม: [[สรุปคอนเทนต์]]' % r['month'],
            '', '_โน้ตนี้ระบบเขียนทับทุกสัปดาห์ — จดความคิดใน `บันทึกของฉัน/` แล้วลิงก์มาที่โน้ตนี้_']
    return fm + '\n'.join(body) + '\n'


def summary_note(fb, ig, stamp):
    allr = fb + ig
    L = ['---\ntype: content-summary\nupdated: %s\nsince: %s\n---\n' % (stamp, SINCE), '# สรุปคอนเทนต์ FB / IG (ออร์แกนิก)\n',
         'ข้อมูลโพสต์ตั้งแต่ %s ถึง %s · อัปเดตอัตโนมัติทุกสัปดาห์ (ระบบเขียนทับไฟล์นี้) · ตัวเลขดิบทุกโพสต์อยู่ในชีต "Biopalm Content Insight — FB/IG 2026"\n' % (date_th(SINCE), date_th(stamp)),
         'ค้นโพสต์: กด Ctrl/Cmd+O แล้วพิมพ์ ID (FB = ตัวเลขท้าย ID · IG = shortcode ท้ายลิงก์ instagram.com/p/…) · ตารางเรียง/กรองได้: `Bases/คอนเทนต์.base`\n',
         '## ภาพรวมแยกประเภท', '',
         '| ช่องทาง | ประเภท | โพสต์ | ยอดดูมัธยฐาน | คนดูไม่ซ้ำ/Reach มัธยฐาน | Interaction มัธยฐาน | Interaction ต่อคนดู มัธยฐาน |',
         '|---|---|---:|---:|---:|---:|---:|']
    for pf, rs0 in (('FB', fb), ('IG', ig)):
        for f in sorted({r['format'] for r in rs0}, key=lambda f: -sum(1 for r in rs0 if r['format'] == f)):
            rs = [r for r in rs0 if r['format'] == f]
            L.append('| %s | %s | %d | %s | %s | %s | %s |' % (pf, f, len(rs), fmt_n(med([r['views'] for r in rs])), fmt_n(med([r['reach'] for r in rs])),
                                                         fmt_n(med([r['interactions'] for r in rs])),
                                                         ('%.2f%%' % med([r['rate'] for r in rs])) if med([r['rate'] for r in rs]) is not None else '–'))
    L += ['', 'ใช้ค่ามัธยฐาน (โพสต์ตรงกลาง) แทนค่าเฉลี่ย เพราะโพสต์ไม่กี่ตัวที่ยอดพุ่งจะดึงค่าเฉลี่ยจนเพี้ยน · โพสต์ที่เพิ่งลงยังสะสมยอดไม่ครบ\n']
    reels = [r for r in ig if r['format'] == 'Reel']
    if reels:
        L += ['**IG Reel:** %d ตัว · ดูเฉลี่ยมัธยฐาน %s วินาที · ปัดทิ้งใน 3 วินาทีแรกมัธยฐาน %s%%\n' % (
            len(reels), fmt_n(med([r['avg_watch_s'] for r in reels]), 1), fmt_n(med([r['skip_rate'] for r in reels]), 1))]
    L += ['## รายเดือน', '', '| เดือน | FB โพสต์ | FB ยอดดูรวม | IG โพสต์ | IG ยอดดูรวม | แชท/แอดเดือนนี้ |', '|---|---:|---:|---:|---:|---|']
    for m in sorted({r['month'] for r in allr}):
        f = [r for r in fb if r['month'] == m]; g = [r for r in ig if r['month'] == m]
        L.append('| %s | %d | %s | %d | %s | [[%s]] |' % ('%s %s' % (TH_M[int(m[5:])], m[:4]), len(f), fmt_n(sum(r['views'] or 0 for r in f)),
                                                           len(g), fmt_n(sum(r['views'] or 0 for r in g)), m))
    L += ['', 'คอลัมน์สุดท้ายลิงก์ไปโน้ตเดือนใน `Monthly/` (ค่าแอด Meta + แชท FB/LINE เดือนเดียวกัน) — ดูคู่กับ [[1.2 ช่วงเวลาที่ลูกค้าทัก]]\n']

    def top(rs, key, n, title, fmtv):
        rs = [r for r in rs if r.get(key) is not None]
        rs.sort(key=lambda r: -r[key])
        out = ['### ' + title, '', '| # | วันที่ | ประเภท | ค่า | โพสต์ |', '|---:|---|---|---:|---|']
        for i, r in enumerate(rs[:n], 1):
            out.append('| %d | %s | %s | %s | [[%s\\|%s]] |' % (i, r['posted'][:10], r['format'], fmtv(r[key]), note_name(r),
                                                               first_line(r['caption'], 60).replace('|', '/').replace('[', '(').replace(']', ')') or r['key']))
        return out + ['']
    L += ['## โพสต์ที่ดีที่สุด', '']
    L += top(fb, 'views', 15, 'FB ยอดดูสูงสุด', fmt_n)
    L += top(ig, 'views', 15, 'IG ยอดดูสูงสุด', fmt_n)
    L += top([dict(r, ss=(r['saved'] or 0) + (r['shares'] or 0)) for r in ig], 'ss', 10, 'IG เซฟ + แชร์สูงสุด (คอนเทนต์ที่คนเก็บไว้/ส่งต่อ)', fmt_n)
    L += top([r for r in fb if (r['reach'] or 0) >= 500], 'rate', 10, 'FB Interaction ต่อคนดูสูงสุด (คนดู 500 ขึ้นไป)', lambda v: '%.2f%%' % v)
    L += top([r for r in ig if (r['reach'] or 0) >= 500], 'rate', 10, 'IG Interaction ต่อ reach สูงสุด (reach 500 ขึ้นไป)', lambda v: '%.2f%%' % v)
    L += ['## ข้อจำกัด', '- FB วิดีโอ/Reel: มีแค่ยอดดูและคนดูไม่ซ้ำ ยังไม่มีเวลาดูหรือยอดดู 3 วินาที (ดึงผ่านเครื่องมือที่มีไม่ได้)',
          '- Stories ย้อนหลังไม่ได้ (API ให้เฉพาะสตอรี่ที่ยังขึ้นอยู่ 24 ชม.)',
          '- ตัวเลขเป็นยอดสะสมถึงวันที่ดึง เทียบโพสต์ใหม่กับโพสต์เก่าต้องระวัง · ช่อง "–" = Meta ไม่ส่งตัวเลขนั้นมา (ไม่ใช่ 0)',
          '- ยังเชื่อมโพสต์กับแชทรายห้องไม่ได้ — ถ้าใส่ลิงก์ m.me/ig.me พร้อม `?ref=` ในโพสต์ จะนับได้ว่าแชทมาจากโพสต์ไหน (ดู [[02 แผนงาน]])']
    return '\n'.join(L) + '\n'


def commit(files, label):
    items = sorted(files.items())
    n = (len(items) + 59) // 60
    for i in range(n):
        part = items[i * 60:(i + 1) * 60]
        args = {'owner': OWNER, 'repo': REPO, 'branch': 'main', 'message': '%s (%d/%d)' % (label, i + 1, n),
                'upserts': [{'path': p, 'content': t, 'encoding': 'utf-8'} for p, t in part]}
        for attempt in range(4):
            try:
                call('GITHUB_COMMIT_MULTIPLE_FILES', args, tries=2)
                break
            except CallError as e:
                if 'TOO_LARGE' in str(e):
                    break                              # commit สำเร็จแต่คำตอบยาว
                if attempt == 3:
                    raise
                time.sleep(15 * (attempt + 1))
    log('commit ลง vault %d ไฟล์ (%d ครั้ง)' % (len(items), n))


# ---------------------------------------------------------------- main
def main():
    global SID
    stamp = dt.datetime.now(BKK).strftime('%Y-%m-%d %H:%M')
    page = find_page()
    if not page:
        sys.exit('ไม่พบเพจที่ตรงกับ hash')
    SID = find_sheet()
    if not SID:
        sys.exit('ไม่พบชีตที่ตรงกับ hash')
    start = dt.datetime.fromisoformat(SINCE).replace(tzinfo=BKK)
    fbp = fb_posts(page, start)
    log('FB โพสต์ %d · ไม่มีแคปชัน %d' % (len(fbp), STATS['fb_no_caption']))
    igm = paged('INSTAGRAM_GET_IG_USER_MEDIA', {'ig_user_id': 'me', 'since': since_ts(),
                                                'fields': 'id,caption,media_type,media_product_type,permalink,shortcode,timestamp,like_count,comments_count'},
                50, start)
    log('IG โพสต์ %d' % len(igm))
    with ThreadPoolExecutor(WORKERS) as ex:
        fins = dict(zip([p['id'] for p in fbp], ex.map(fb_insight, [p['id'] for p in fbp])))
    log('FB insight ครบ · ไม่ได้ %d' % STATS['fb_ins_fail'])
    with ThreadPoolExecutor(WORKERS) as ex:
        iins = dict(zip([m['id'] for m in igm], ex.map(ig_insight, igm)))
    log('IG insight ครบ · ไม่ได้ %d · ได้บางตัว %d' % (STATS['ig_ins_fail'], STATS['ig_ins_partial']))
    fb = sorted(build_fb(fbp, page, fins), key=lambda r: r['posted'], reverse=True)
    ig = sorted(build_ig(igm, iins), key=lambda r: r['posted'], reverse=True)
    log('แถวที่ใช้ FB %d · IG %d · คำขอทั้งหมด %d · ลดขนาดหน้า %d' % (len(fb), len(ig), STATS['calls'], STATS['shrink']))
    if not fb and not ig:
        sys.exit('ไม่ได้โพสต์เลย — ไม่เขียนทับของเดิม')
    if DRY:
        log('DRY_RUN: ไม่เขียนชีตและ vault')
        return
    write_tab('คำอธิบาย', about_rows(stamp, len(fb), len(ig)))
    write_tab('FB โพสต์', table_rows(fb, FB_COLS))
    write_tab('IG โพสต์', table_rows(ig, IG_COLS))
    write_tab('สรุปรายเดือน', monthly_rows(fb + ig))
    files = {note_path(r): post_note(r, stamp) for r in fb + ig}
    files['Content/สรุปคอนเทนต์.md'] = summary_note(fb, ig, stamp)
    files['.vault/content/posts.json'] = json.dumps({'pulled': stamp, 'since': SINCE, 'posts': fb + ig}, ensure_ascii=False, separators=(',', ':'))
    commit(files, 'content: insight โพสต์ FB/IG %s' % stamp)
    log('เสร็จ')


if __name__ == '__main__':
    main()

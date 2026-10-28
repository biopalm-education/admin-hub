# -*- coding: utf-8 -*-
"""Insight คอนเทนต์ออร์แกนิก Facebook Page + Instagram + TikTok + YouTube (Biopalm) → Google Sheet + vault Obsidian (Content/)

ทุกโพสต์ตั้งแต่ SINCE (ค่าเริ่ม 1 ม.ค. 2026 เวลาไทย): ภาพเดี่ยว / อัลบั้ม / วิดีโอ / Reel / ข้อความ-ลิงก์
  FB : ยอดดู (post_media_view) · คนดูไม่ซ้ำ · reaction · คอมเมนต์ · แชร์
  IG : ยอดดู · reach · ไลก์ · คอมเมนต์ · เซฟ · แชร์ · interaction รวม · เข้าโปรไฟล์ · ฟอลโลว์ใหม่
       Reel เพิ่ม: เวลาดูเฉลี่ย · เวลาดูรวม · อัตราปัดทิ้งใน 3 วินาทีแรก
  TikTok / YouTube: ดู video.py (ยอดดู · ไลก์ · คอมเมนต์ · แชร์ · ความยาว · ค่าแอด TikTok Ads / Google Ads)
ผลลัพธ์
  * ชีต "Biopalm Content Insight — FB/IG/TikTok/YouTube 2026" (ข้อมูลดิบ เขียนทับทั้งแท็บทุกรอบ)
  * vault private biopalm-insight: Content/<FB|IG|TikTok|YouTube>/<เดือน>/<วันที่> <ช่องทาง> <ประเภท> <ID>.md (1 โพสต์ = 1 โน้ต)
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
import video as V

PAGE_HASH = '73025ff6d1ad9be87ec1ef93b274a8ce62bfbbcb64343d40d49c01cb5b7cceb1'
ACT_HASH = '08d8b72a01af222cdd8bdf0a1693ca700448249f2ba096b0b185c5c57d97a098'   # บัญชีโฆษณาเดียวกับ meta_ads/export.py
SHEET_HASH = '1083f419af879f018fb3894f00949c682e04f9a96db4519f2a39ac0b657ae59f'
SHEET_QUERY = 'Biopalm Content Insight'
SHEET_TITLE = 'Biopalm Content Insight — FB/IG/TikTok/YouTube 2026'
PLAT = ['FB', 'IG', 'TikTok', 'YouTube']
VAULT_REPO = os.environ.get('VAULT_REPO') or 'biopalm-education/biopalm-insight'
OWNER, REPO = VAULT_REPO.split('/')
BKK = ZoneInfo('Asia/Bangkok')
SINCE = os.environ.get('SINCE') or '2026-01-01'
DRY = (os.environ.get('DRY_RUN') or '').strip().lower() in ('1', 'true', 'yes')
WORKERS = int(os.environ.get('WORKERS') or 3)
T0 = time.time()
STATS = {'calls': 0, 'shrink': 0, 'fb_ins_fail': 0, 'ig_ins_fail': 0, 'ig_ins_partial': 0, 'fb_no_caption': 0,
         'ads': 0, 'ad_creative_fail': 0}
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


# ---------------------------------------------------------------- โพสต์ไหนถูกนำไปทำแอด / boost
AD_STATUS = ['ACTIVE', 'PAUSED', 'DELETED', 'PENDING_REVIEW', 'DISAPPROVED', 'PREAPPROVED', 'PENDING_BILLING_INFO',
             'CAMPAIGN_PAUSED', 'ARCHIVED', 'ADSET_PAUSED', 'IN_PROCESS', 'WITH_ISSUES']


def month_spans():
    out, d = [], dt.date.fromisoformat(SINCE)
    end = dt.datetime.now(BKK).date()
    while d <= end:
        nxt = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        out.append((d.isoformat(), min(nxt - dt.timedelta(days=1), end).isoformat()))
        d = nxt
    return out


def ad_spend_month(act, since, until):
    """ค่าแอดต่อโฆษณาใน 1 เดือน (Meta ไม่ให้ดึงทั้งปีในคำขอเดียว: too many rows)"""
    out, after, limit, filt = {}, None, 100, True
    for _ in range(200):
        args = {'object_id': act, 'level': 'ad', 'fields': ['ad_id', 'spend'], 'limit': limit,
                'time_range': {'since': since, 'until': until}}
        if filt:   # รวมโฆษณาที่ลบ/เก็บถาวรแล้ว (ค่าเริ่มของ Meta ไม่นับ)
            args['filtering'] = [{'field': 'ad.effective_status', 'operator': 'IN', 'value': AD_STATUS}]
        if after:
            args['after'] = after
        try:
            d = call('METAADS_GET_INSIGHTS', args, tries=3)
        except CallError as e:
            if 'TOO_LARGE' in str(e) and limit > 10:
                limit //= 2
                continue
            if 'effective_status' in str(e) and filt:
                filt = False
                continue
            raise
        for r in rows_of(d):
            if isinstance(r, dict) and r.get('ad_id'):
                out[r['ad_id']] = out.get(r['ad_id'], 0.0) + float(r.get('spend') or 0)
        nxt = after_of(d)
        if not nxt or nxt == after:
            break
        after = nxt
    return out


def ad_creatives(ad_ids):
    """ad_id → (FB story id, IG media id) ที่โฆษณานั้นใช้"""
    fields = ['id', 'creative{effective_object_story_id,effective_instagram_media_id}']

    def one(b):
        try:
            d = call('METAADS_GET_MULTIPLE_OBJECTS', {'object_ids': b, 'fields': fields}, tries=3)
        except CallError:
            if len(b) == 1:
                STATS['ad_creative_fail'] += 1
                return {}
            h = len(b) // 2                                 # ก้อนพลาด → แบ่งครึ่ง
            r = one(b[:h])
            r.update(one(b[h:]))
            return r
        res = d.get('results') if isinstance(d, dict) and isinstance(d.get('results'), dict) else d
        out = {}
        if isinstance(res, dict):
            for k, v in res.items():
                if not isinstance(v, dict):
                    continue
                cr = v.get('creative') if isinstance(v.get('creative'), dict) else {}
                out[str(k)] = (cr.get('effective_object_story_id'), cr.get('effective_instagram_media_id'))
        return out
    out = {}
    batches = [ad_ids[i:i + 25] for i in range(0, len(ad_ids), 25)]
    with ThreadPoolExecutor(WORKERS) as ex:
        for part in ex.map(one, batches):
            out.update(part)
    return out


def ads_by_post():
    """{FB post id / IG media id: {'ads': จำนวนโฆษณา, 'spend': ค่าแอดรวมตั้งแต่ SINCE}} · ดึงไม่ได้ → None (งานหลักไปต่อ)"""
    try:
        d = call('METAADS_GET_AD_ACCOUNTS', {'limit': 100, 'fields': 'id,name'})
        act = next((a['id'] for a in rows_of(d) if isinstance(a, dict) and sha(a.get('id', '')) == ACT_HASH), None)
        if not act:
            log('ไม่พบบัญชีโฆษณาที่ตรงกับ hash — ข้ามป้าย "ทำแอด"')
            return None
        spend = {}
        for s, e in month_spans():
            for k, v in ad_spend_month(act, s, e).items():
                spend[k] = spend.get(k, 0.0) + v
        spend = {k: v for k, v in spend.items() if v > 0}
        STATS['ads'] = len(spend)
        cre = ad_creatives(sorted(spend))
    except CallError as e:
        log('ดึงข้อมูลแอดไม่ได้ (%s) — ข้ามป้าย "ทำแอด" รอบนี้' % _safe(e))
        return None
    out = {}
    for ad, (story, igm) in cre.items():
        for k in {x for x in (story, igm) if x}:
            o = out.setdefault(str(k), {'ads': 0, 'spend': 0.0})
            o['ads'] += 1
            o['spend'] += spend.get(ad, 0.0)
    log('แอดที่มีค่าใช้จ่าย %d · อ่าน creative ได้ %d · พลาด %d' % (len(spend), len(cre), STATS['ad_creative_fail']))
    return out


def annotate_ads(rows, adm):
    """ใส่ ads (จำนวนโฆษณาที่ใช้โพสต์นี้) และ ad_spend (บาท) · adm None = รอบนี้ไม่รู้ → None"""
    for r in rows:
        if adm is None:
            r['ads'] = r['ad_spend'] = None
            continue
        keys = fb_ad_keys({'id': r['post_id'], 'permalink_url': r['link']}) if r['platform'] == 'FB' else [r['post_id']]
        hit = [adm[k] for k in dict.fromkeys(keys) if k in adm]
        r['ads'] = sum(h['ads'] for h in hit)
        r['ad_spend'] = int(round(sum(h['spend'] for h in hit)))
    return rows


def organic(rows):
    """โพสต์ที่ไม่เคยนำไปทำแอด (ถ้ารอบนี้ไม่รู้ข้อมูลแอด = ทุกโพสต์)"""
    return [r for r in rows if not r.get('ads')]


def fb_ad_keys(p):
    """ID ที่โฆษณาอาจใช้อ้างโพสต์ FB: post id เต็ม + (Reel/วิดีโอ) page_videoId"""
    keys = [p['id']]
    page = p['id'].split('_')[0]
    m = re.search(r'/(?:reel|videos)/(\d+)', p.get('permalink_url') or '')
    if m:
        keys.append('%s_%s' % (page, m.group(1)))
    return keys


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
    return 'ภาพนิ่ง' if f in ('ภาพเดี่ยว', 'อัลบั้ม', 'ภาพสไลด์') else ('วิดีโอ' if f in ('Reel', 'วิดีโอ', 'Shorts', 'วิดีโอยาว', 'ไลฟ์') else 'อื่น ๆ')


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
           ('คอมเมนต์', 'comments'), ('แชร์', 'shares'), ('Interaction รวม', 'interactions'), ('Interaction ต่อคนดู (%)', 'rate'),
           ('โฆษณาที่ใช้โพสต์นี้ (ตัว)', 'ads'), ('ค่าแอดที่ใช้โพสต์นี้ (บาท)', 'ad_spend')]
IG_COLS = [('วันที่โพสต์ (เวลาไทย)', 'posted'), ('เดือน', 'month'), ('ภาพนิ่ง/วิดีโอ', 'group'), ('ประเภท', 'format'), ('Media ID', 'post_id'),
           ('Shortcode (ท้ายลิงก์)', 'key'), ('ลิงก์', 'link'), ('แคปชัน (ตัดสั้น)', 'cap'), ('ยอดดู', 'views'), ('Reach', 'reach'),
           ('ไลก์', 'likes'), ('คอมเมนต์', 'comments'), ('เซฟ', 'saved'), ('แชร์', 'shares'), ('Interaction รวม', 'interactions'),
           ('Interaction ต่อ reach (%)', 'rate'), ('เข้าโปรไฟล์', 'profile_visits'), ('ฟอลโลว์ใหม่', 'follows'),
           ('Reel ดูเฉลี่ย (วินาที)', 'avg_watch_s'), ('Reel เวลาดูรวม (ชม.)', 'watch_total_h'), ('Reel ปัดทิ้งใน 3 วิ (%)', 'skip_rate'),
           ('โฆษณาที่ใช้โพสต์นี้ (ตัว)', 'ads'), ('ค่าแอดที่ใช้โพสต์นี้ (บาท)', 'ad_spend')]
TT_COLS = [('วันที่โพสต์ (เวลาไทย)', 'posted'), ('เดือน', 'month'), ('ประเภท', 'format'), ('ความยาว (วินาที)', 'duration_s'), ('Video ID', 'post_id'),
           ('ลิงก์', 'link'), ('แคปชัน (ตัดสั้น)', 'cap'), ('ยอดดู', 'views'), ('ไลก์', 'likes'), ('คอมเมนต์', 'comments'), ('แชร์', 'shares'),
           ('Interaction รวม', 'interactions'), ('Interaction ต่อยอดดู (%)', 'rate'), ('โฆษณาที่ใช้คลิปนี้ (ตัว)', 'ads'), ('ค่าแอด (บาท)', 'ad_spend'),
           ('ยอดดูจากแอด', 'ad_views'), ('ยอดดูที่ไม่ใช่แอด (ประมาณ)', 'organic_views_est')]
YT_COLS = [('วันที่เผยแพร่ (เวลาไทย)', 'posted'), ('เดือน', 'month'), ('ประเภท', 'format'), ('ความยาว (วินาที)', 'duration_s'), ('Video ID', 'post_id'),
           ('ลิงก์', 'link'), ('ชื่อคลิป', 'title'), ('ยอดดู', 'views'), ('ไลก์', 'likes'), ('คอมเมนต์', 'comments'),
           ('Interaction รวม', 'interactions'), ('Interaction ต่อยอดดู (%)', 'rate'), ('โฆษณา Google Ads ที่ใช้คลิปนี้ (ตัว)', 'ads'),
           ('ค่าแอด (บาท)', 'ad_spend'), ('ยอดดูจากแอด', 'ad_views'), ('ยอดดูที่ไม่ใช่แอด (ประมาณ)', 'organic_views_est'),
           ('ผู้ชมแอดดูถึง 25% (%)', 'ad_p25'), ('ผู้ชมแอดดูถึง 50% (%)', 'ad_p50'), ('ผู้ชมแอดดูถึง 75% (%)', 'ad_p75'), ('ผู้ชมแอดดูจบ 100% (%)', 'ad_p100')]


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
    out = [['ช่องทาง', 'เดือน', 'ภาพนิ่ง/วิดีโอ', 'จำนวนโพสต์', 'ยอดดูรวม', 'ยอดดูมัธยฐานต่อโพสต์', 'Interaction รวม', 'Interaction มัธยฐานต่อโพสต์',
            'โพสต์ที่นำไปทำแอด', 'ยอดดูมัธยฐาน เฉพาะโพสต์ไม่ทำแอด']]
    keys = sorted({(r['platform'], r['month'], r['group']) for r in allrows})
    for k in keys:
        rs = [r for r in allrows if (r['platform'], r['month'], r['group']) == k]
        known = all(r.get('ads') is not None for r in rs)
        out.append(list(k) + [len(rs), sum(r['views'] or 0 for r in rs), med([r['views'] for r in rs]),
                              sum(r['interactions'] or 0 for r in rs), med([r['interactions'] for r in rs]),
                              sum(1 for r in rs if r.get('ads')) if known else None,
                              med([r['views'] for r in organic(rs)]) if known else None])
    return out


def about_rows(stamp, rows_by, states, ads_ok=True):
    def status(p):
        st = states.get(p) or {}
        if st.get('ok'):
            return 'ดึงสำเร็จรอบนี้ · %d คลิป%s' % (len(rows_by[p]), '' if st.get('ads_ok') else ' · ข้อมูลแอดรอบนี้ดึงไม่ได้ (ช่องแอดว่าง)')
        why = (' (%s)' % st['why']) if st.get('why') else ''
        if rows_by[p]:
            return 'รอบนี้ดึงไม่ได้%s — แท็บของช่องทางนี้ยังเป็นข้อมูลรอบ %s' % (why, st.get('stale') or 'ก่อน')
        return 'ยังไม่มีข้อมูล — ดึงไม่ได้%s · รอบถัดไประบบจะลองใหม่' % why
    tta, yta = (states.get('TikTok') or {}).get('account') or {}, (states.get('YouTube') or {}).get('account') or {}
    out = [['Biopalm Content Insight — FB / IG / TikTok / YouTube'],
           ['ดึงล่าสุด', stamp],
           ['ช่วงโพสต์', 'ตั้งแต่ %s (เวลาไทย) ถึงวันที่ดึง' % SINCE],
           ['จำนวนโพสต์', ' · '.join('%s %d' % (p, len(rows_by[p])) for p in PLAT)],
           ['TikTok', status('TikTok')],
           ['YouTube', status('YouTube')],
           ['อัปเดต', 'อัตโนมัติทุกสัปดาห์ (GitHub Actions: admin-hub → obsidian-content) เขียนทับทั้งแท็บทุกรอบ — อย่าพิมพ์ข้อมูลเองในแท็บเหล่านี้'],
           ['ใน Obsidian', 'vault Biopalm-Insight → Content/<ช่องทาง>/ (1 โพสต์ = 1 โน้ต ชื่อไฟล์มี ID) + Content/สรุปคอนเทนต์']]
    if tta:
        out.append(['บัญชี TikTok (ณ วันที่ดึง)', 'ผู้ติดตาม %s · ไลก์รวมทั้งบัญชี %s · คลิปทั้งหมด %s' % (
            fmt_n(tta.get('followers')), fmt_n(tta.get('likes_total')), fmt_n(tta.get('videos_total')))])
    if yta:
        out.append(['ช่อง YouTube (ณ วันที่ดึง)', 'ผู้ติดตาม %s · ยอดดูรวมทั้งช่อง %s · คลิปสาธารณะทั้งหมด %s' % (
            fmt_n(yta.get('subscribers')), fmt_n(yta.get('views_total')), fmt_n(yta.get('videos_total')))])
    out += [[''],
            ['คำ', 'ความหมาย'],
            ['ยอดดู', 'FB: post_media_view = จำนวนครั้งที่โพสต์แสดงบนจอ · IG: views = จำนวนครั้งที่เล่น/แสดง (ตัวเลขชุดใหม่ของ Meta แทน impressions ที่เลิกใช้) · '
                      'TikTok: view_count ของคลิป · YouTube: ยอดดูสาธารณะของคลิป · '
                      'ถ้าโพสต์ถูกนำไปทำแอด ยอดนี้รวมยอดจากแอดด้วย — นิยาม "ยอดดู" แต่ละแพลตฟอร์มไม่เหมือนกัน เทียบข้ามช่องทางตรง ๆ ไม่ได้'],
            ['โฆษณาที่ใช้โพสต์นี้ / ค่าแอด', ('จำนวนโฆษณาที่ใช้โพสต์นี้โดยตรงและค่าแอดรวมตั้งแต่ %s · FB/IG: Meta Ads (Boost หรือเลือกโพสต์เดิม) · '
                                             'TikTok: TikTok Ads Manager (Spark Ads — จับคู่จากชื่อแอดที่ขึ้นต้นด้วยแคปชันคลิป) · YouTube: Google Ads · '
                                             '0 = ไม่เคยทำแอด = ออร์แกนิกล้วน · ช่องว่าง = รอบนี้ดึงข้อมูลแอดไม่ได้ (ไม่ใช่ 0)' % SINCE) if ads_ok else
             'FB/IG: รอบนี้ดึงข้อมูลแอด Meta ไม่ได้ — ช่องว่างทั้งคอลัมน์ (ไม่ใช่ 0)'],
            ['ยอดดูจากแอด / ยอดดูที่ไม่ใช่แอด (ประมาณ)', 'TikTok: video_play_actions ของแอด · YouTube: TrueView views ของ Google Ads · '
                                                     'ยอดดูที่ไม่ใช่แอด = ยอดดูคลิป − ยอดดูจากแอด (ประมาณ เพราะแพลตฟอร์มนับไม่ตรงกัน 100%)'],
            ['ผู้ชมแอดดูถึง 25/50/75/100%', 'YouTube เท่านั้น: สัดส่วนการแสดงแอดที่ผู้ชมดูถึงจุดนั้น (จาก Google Ads) — ไม่ใช่ผู้ชมออร์แกนิก'],
            ['คนดูไม่ซ้ำ / Reach', 'FB/IG: จำนวนบัญชีที่เห็นโพสต์อย่างน้อย 1 ครั้ง (ค่าประมาณจาก Meta) · TikTok/YouTube: API ไม่ให้ตัวเลขนี้'],
            ['Interaction รวม', 'FB: reaction + คอมเมนต์ + แชร์ · IG: ไลก์ + เซฟ + คอมเมนต์ + แชร์ (ตัวเลขของ IG เอง) · TikTok: ไลก์ + คอมเมนต์ + แชร์ · YouTube: ไลก์ + คอมเมนต์'],
            ['Interaction ต่อคนดู / reach / ยอดดู', 'Interaction รวม ÷ (FB คนดูไม่ซ้ำ · IG reach · TikTok/YouTube ยอดดู) × 100'],
            ['ภาพนิ่ง / วิดีโอ', 'ภาพนิ่ง = ภาพเดี่ยว + อัลบั้ม (+ ภาพสไลด์ TikTok) · วิดีโอ = Reel + วิดีโอ + TikTok + YouTube · อื่น ๆ = ข้อความ/ลิงก์/แชร์ต่อ'],
            ['Shorts / วิดีโอยาว', 'YouTube API ไม่บอกตรง ๆ ว่าเป็น Shorts: ระบบเปิดลิงก์ youtube.com/shorts/<ID> ตรวจ (เปิดไม่ได้ → เดาจากความยาว ≤ 3 นาที)'],
            ['Reel ปัดทิ้งใน 3 วิ', 'สัดส่วนการเล่นที่ถูกปัดผ่านภายใน 3 วินาทีแรก (ยิ่งต่ำยิ่งดี)'],
            ['ข้อจำกัด', 'FB วิดีโอ: ยังไม่มีเวลาดู · TikTok: API ให้แค่ยอดดู/ไลก์/คอมเมนต์/แชร์ (ไม่มี reach เวลาดู ดูจบ — ดูใน TikTok Studio) และเฉพาะคลิปสาธารณะ · '
                         'YouTube: ช่องคอนเทนต์อยู่คนละอีเมล จึงได้แค่ตัวเลขสาธารณะ (ไม่มีเวลาดู/ซับใหม่รายคลิป) · Stories ย้อนหลังไม่ได้ · ตัวเลขเป็นยอดสะสมถึงวันที่ดึง โพสต์ใหม่จะยังเพิ่มอีก'],
            ['ช่องว่าง', 'ช่องว่าง = แพลตฟอร์มไม่ส่งตัวเลขนั้นให้โพสต์นั้น (ไม่ใช่ 0)']]
    return out


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


LAB = {'FB': ('คนดูไม่ซ้ำ', 'Reaction'), 'IG': ('Reach', 'ไลก์'), 'TikTok': (None, 'ไลก์'), 'YouTube': (None, 'ไลก์')}
AD_SRC = {'FB': 'Meta Ads', 'IG': 'Meta Ads', 'TikTok': 'TikTok Ads', 'YouTube': 'Google Ads'}


def fmt_dur(s):
    if s is None:
        return '–'
    return '%d:%02d นาที' % divmod(int(s), 60) if s >= 60 else '%d วินาที' % s


def post_note(r, stamp, others=()):
    pf = r['platform']
    props = [('type', 'content'), ('platform', pf), ('format', r['format']), ('group', r['group']), ('posted', r['posted']),
             ('month', r['month']), ('post_id', r['post_id'])]
    if pf == 'IG':
        props.append(('shortcode', r['key']))
    if pf == 'YouTube':
        props.append(('title', r.get('title')))
    props += [('link', r['link']), ('views', r['views']), ('reach', r['reach']), ('likes', r['likes']), ('comments', r['comments']),
              ('shares', r['shares']), ('saved', r['saved']), ('interactions', r['interactions']), ('interaction_rate', r['rate']),
              ('profile_visits', r['profile_visits']), ('follows', r['follows']), ('avg_watch_s', r['avg_watch_s']),
              ('skip_rate', r['skip_rate']), ('duration_s', r.get('duration_s')), ('ads', r.get('ads')), ('ad_spend', r.get('ad_spend')),
              ('ad_views', r.get('ad_views')), ('organic_views_est', r.get('organic_views_est')), ('ad_p100', r.get('ad_p100')), ('pulled', stamp)]
    opt = {'saved', 'profile_visits', 'follows', 'avg_watch_s', 'skip_rate', 'shortcode', 'ads', 'ad_spend', 'duration_s', 'ad_views',
           'organic_views_est', 'ad_p100', 'title'}
    if pf in ('TikTok', 'YouTube'):
        opt |= {'reach', 'shares'}
    fm = '---\n' + '\n'.join('%s: %s' % (k, yv(v)) for k, v in props if not (v is None and k in opt)) + '\n---\n'
    if r.get('ads') is None:
        adline = 'ทำแอด: รอบนี้ไม่ได้ตรวจ (ดึงข้อมูลแอดไม่ได้)'
    elif r['ads']:
        adline = ('**นำไปทำแอดแล้ว** (%s) %d โฆษณา · ค่าแอดรวม %s บาท (ตั้งแต่ %s) — ยอดดู/คนดูด้านล่างรวมส่วนที่มาจากแอดด้วย ไม่ใช่ออร์แกนิกล้วน'
                  % (AD_SRC[pf], r['ads'], fmt_n(r['ad_spend']), date_th(SINCE)))
        if r.get('ad_views') is not None and pf in ('TikTok', 'YouTube'):
            adline += '\n\nยอดดูจากแอด %s → ยอดดูที่ไม่ใช่แอด ≈ %s (ประมาณ)' % (fmt_n(r['ad_views']), fmt_n(r.get('organic_views_est')))
        if pf == 'YouTube' and r.get('ad_p25') is not None:
            adline += ' · ผู้ชมแอดดูถึง 25 / 50 / 75 / 100%%: %s / %s / %s / %s%%' % tuple(fmt_n(r.get(k), 1) for k in ('ad_p25', 'ad_p50', 'ad_p75', 'ad_p100'))
    else:
        adline = 'ไม่เคยนำไปทำแอด (ตั้งแต่ %s) — ตัวเลขด้านล่างเป็นออร์แกนิกล้วน' % date_th(SINCE)
    cap = str(r['caption'] or '').strip()
    cap = cap if len(cap) <= 400 else cap[:400].rstrip() + '…'
    # บรรทัดแคปชันที่ขึ้นต้น "# " กลายเป็นหัวข้อใน Obsidian → ใส่ \ ให้เป็นตัวอักษรธรรมดา
    capq = '\n'.join('> ' + re.sub(r'^(\s*)#', r'\1\\#', ln) if re.match(r'\s*#{1,6}\s', ln) else '> ' + ln
                     for ln in cap.splitlines() if ln.strip()) or '> (ไม่มีข้อความ)'
    lab_reach, lab_like = LAB[pf]
    rows = [('ยอดดู', fmt_n(r['views']))]
    if lab_reach:
        rows.append((lab_reach, fmt_n(r['reach'])))
    rows += [(lab_like, fmt_n(r['likes'])), ('คอมเมนต์', fmt_n(r['comments']))]
    if pf != 'YouTube':
        rows.append(('แชร์', fmt_n(r['shares'])))
    if pf == 'IG':
        rows += [('เซฟ', fmt_n(r['saved']))]
        if r['format'] in ('ภาพเดี่ยว', 'อัลบั้ม'):
            rows += [('เข้าโปรไฟล์', fmt_n(r['profile_visits'])), ('ฟอลโลว์ใหม่', fmt_n(r['follows']))]
    lab_rate = lab_reach or 'ยอดดู'
    rows += [('Interaction รวม', fmt_n(r['interactions'])), ('Interaction ต่อ %s' % lab_rate, ('%.2f%%' % r['rate']) if r['rate'] is not None else '–')]
    if r['format'] == 'Reel' and pf == 'IG':
        rows += [('ดูเฉลี่ย', ('%.1f วินาที' % r['avg_watch_s']) if r['avg_watch_s'] is not None else '–'),
                 ('เวลาดูรวม', ('%.1f ชม.' % r['watch_total_h']) if r['watch_total_h'] is not None else '–'),
                 ('ปัดทิ้งใน 3 วินาทีแรก', ('%.1f%%' % r['skip_rate']) if r['skip_rate'] is not None else '–')]
    if pf in ('TikTok', 'YouTube'):
        rows.append(('ความยาวคลิป', fmt_dur(r.get('duration_s'))))
    ids = '[เปิดโพสต์](%s) · ID `%s`%s' % (r['link'], r['post_id'], (' · shortcode `%s`' % r['key']) if pf == 'IG' else '')
    body = ['# %s · %s · %s' % (pf, r['format'], date_th(r['posted'])), '', ids, '', capq, '', adline, '',
            '| ตัวเลข (สะสมถึง %s) | ค่า |' % stamp[:10], '|---|---:|'] + ['| %s | %s |' % x for x in rows]
    if others:
        body += ['', 'โพสต์เดียวกันในช่องทางอื่น: ' + ' · '.join(
            '[[%s|%s]] (ยอดดู %s%s)' % (note_name(x), x['platform'], fmt_n(x['views']), ' · ทำแอด' if x.get('ads') else '')
            for x in sorted(others, key=lambda x: PLAT.index(x['platform'])))]
    body += ['', 'เดือนนี้: [[%s]] · ภาพรวม: [[สรุปคอนเทนต์]]' % r['month'],
             '', '_โน้ตนี้ระบบเขียนทับทุกสัปดาห์ — จดความคิดใน `บันทึกของฉัน/` แล้วลิงก์มาที่โน้ตนี้_']
    return fm + '\n'.join(body) + '\n'


def summary_note(rows_by, stamp, states, groups):
    fb, ig, tt, yt = (rows_by[p] for p in PLAT)
    allr = fb + ig + tt + yt
    kn = {p: bool(rows_by[p]) and all(r.get('ads') is not None for r in rows_by[p]) for p in PLAT}
    org = {p: organic(rows_by[p]) for p in PLAT}
    known = kn['FB'] and kn['IG']
    ofb, oig = org['FB'], org['IG']
    L = ['---\ntype: content-summary\nupdated: %s\nsince: %s\n---\n' % (stamp, SINCE), '# สรุปคอนเทนต์ FB / IG / TikTok / YouTube (ออร์แกนิก)\n',
         'ข้อมูลโพสต์ตั้งแต่ %s ถึง %s · อัปเดตอัตโนมัติทุกสัปดาห์ (ระบบเขียนทับไฟล์นี้) · ตัวเลขดิบทุกโพสต์อยู่ในชีต "%s"\n' % (date_th(SINCE), date_th(stamp), SHEET_TITLE),
         'ค้นโพสต์: กด Ctrl/Cmd+O แล้วพิมพ์ ID (FB = ตัวเลขท้าย ID · IG = shortcode ท้ายลิงก์ instagram.com/p/… · TikTok = เลขท้ายลิงก์ · YouTube = รหัส 11 ตัวท้ายลิงก์) · '
         'ตารางเรียง/กรองได้: `Bases/คอนเทนต์.base`\n']
    for p in ('TikTok', 'YouTube'):
        st = states.get(p) or {}
        if not st.get('ok'):
            why = (' (%s)' % st['why']) if st.get('why') else ''
            L += [('> [!warning] %s รอบนี้ดึงไม่ได้%s\n> ตัวเลข %s ในโน้ตนี้เป็นของรอบ %s — รอบถัดไประบบจะลองใหม่\n' % (p, why, p, st.get('stale') or 'ก่อน'))
                  if rows_by[p] else ('> [!warning] ยังไม่มีข้อมูล %s%s\n> รอบถัดไประบบจะลองใหม่ — ดู [[02 แผนงาน]]\n' % (p, why))]
    ad_bits = ['%s %d จาก %d' % (p, sum(1 for r in rows_by[p] if r.get('ads')), len(rows_by[p])) if kn[p] else '%s ไม่ได้ตรวจรอบนี้' % p
               for p in PLAT if rows_by[p]]
    L += ['> [!note] โพสต์ที่นำไปทำแอด\n> %s โพสต์ถูกนำไปทำแอด (FB/IG: Boost หรือเลือกโพสต์เดิมเป็นแอด · TikTok: Spark Ads · YouTube: Google Ads) — '
          'ยอดดูของโพสต์เหล่านี้รวมส่วนที่มาจากแอด **ตาราง "ภาพรวม" และ "โพสต์ที่ดีที่สุด" จึงนับเฉพาะโพสต์ที่ไม่เคยทำแอด (ออร์แกนิกล้วน)** '
          'ส่วนโพสต์ที่ทำแอดดูได้ในหัวข้อ "โพสต์ที่นำไปทำแอด"\n' % ' · '.join(ad_bits)]
    tta, yta = (states.get('TikTok') or {}).get('account') or {}, (states.get('YouTube') or {}).get('account') or {}
    if tta or yta:
        L += ['## บัญชี (ณ วันที่ดึง)', '', '| ช่องทาง | ผู้ติดตาม | ยอดรวมทั้งบัญชี | คลิปทั้งหมด |', '|---|---:|---|---:|']
        if tta:
            L.append('| TikTok | %s | ไลก์รวม %s | %s |' % (fmt_n(tta.get('followers')), fmt_n(tta.get('likes_total')), fmt_n(tta.get('videos_total'))))
        if yta:
            L.append('| YouTube | %s | ยอดดูรวม %s | %s |' % (fmt_n(yta.get('subscribers')), fmt_n(yta.get('views_total')), fmt_n(yta.get('videos_total'))))
        L.append('')
    L += ['## ภาพรวมแยกประเภท (ออร์แกนิกล้วน)', '',
          '| ช่องทาง | ประเภท | โพสต์ | ยอดดูมัธยฐาน | คนดูไม่ซ้ำ/Reach มัธยฐาน | Interaction มัธยฐาน | Interaction % มัธยฐาน | ทำแอด (ไม่นับ) |',
          '|---|---|---:|---:|---:|---:|---:|---:|']
    for pf in PLAT:
        all0, rs0 = rows_by[pf], org[pf]
        for f in sorted({r['format'] for r in all0}, key=lambda f: -sum(1 for r in all0 if r['format'] == f)):
            rs = [r for r in rs0 if r['format'] == f]
            mr = med([r['rate'] for r in rs])
            L.append('| %s | %s | %d | %s | %s | %s | %s | %s |' % (
                pf, f, len(rs), fmt_n(med([r['views'] for r in rs])), fmt_n(med([r['reach'] for r in rs])),
                fmt_n(med([r['interactions'] for r in rs])), ('%.2f%%' % mr) if mr is not None else '–',
                str(sum(1 for r in all0 if r['format'] == f and r.get('ads'))) if kn[pf] else '–'))
    L += ['', 'ใช้ค่ามัธยฐาน (โพสต์ตรงกลาง) แทนค่าเฉลี่ย เพราะโพสต์ไม่กี่ตัวที่ยอดพุ่งจะดึงค่าเฉลี่ยจนเพี้ยน · โพสต์ที่เพิ่งลงยังสะสมยอดไม่ครบ · '
          'Interaction %: FB ต่อคนดูไม่ซ้ำ · IG ต่อ reach · TikTok/YouTube ต่อยอดดู (2 ช่องทางนี้ไม่มี reach) · นิยาม "ยอดดู" แต่ละแพลตฟอร์มต่างกัน เทียบข้ามช่องทางให้ดูแนวโน้ม ไม่ใช่ตัวเลขตรง ๆ\n']
    reels = [r for r in oig if r['format'] == 'Reel']
    if reels:
        L += ['**IG Reel (ออร์แกนิกล้วน):** %d ตัว · ดูเฉลี่ยมัธยฐาน %s วินาที · ปัดทิ้งใน 3 วินาทีแรกมัธยฐาน %s%%\n' % (
            len(reels), fmt_n(med([r['avg_watch_s'] for r in reels]), 1), fmt_n(med([r['skip_rate'] for r in reels]), 1))]
    buckets = [(0, 30, '≤ 30 วิ'), (31, 60, '31–60 วิ'), (61, 90, '61–90 วิ'), (91, 180, '91 วิ – 3 นาที'), (181, 10 ** 9, 'เกิน 3 นาที')]
    vids = [('TikTok', [r for r in org['TikTok'] if r.get('duration_s')]), ('YouTube', [r for r in org['YouTube'] if r.get('duration_s')])]
    if any(rs for _, rs in vids):
        L += ['## ความยาวคลิปกับยอดดู (TikTok / YouTube · ออร์แกนิกล้วน)', '',
              '| ช่องทาง | ความยาว | คลิป | ยอดดูมัธยฐาน | Interaction % มัธยฐาน |', '|---|---|---:|---:|---:|']
        for pf, rs in vids:
            for lo, hi, lab in buckets:
                b = [r for r in rs if lo <= r['duration_s'] <= hi]
                if b:
                    mr = med([r['rate'] for r in b])
                    L.append('| %s | %s | %d | %s | %s |' % (pf, lab, len(b), fmt_n(med([r['views'] for r in b])), ('%.2f%%' % mr) if mr is not None else '–'))
        L += ['', 'กลุ่มที่มีคลิปน้อย (ต่ำกว่า ~5) อย่าเพิ่งสรุป\n']
    L += ['## รายเดือน FB / IG', '', '| เดือน | FB โพสต์ | FB ทำแอด | FB ยอดดูรวม | FB ยอดดูมัธยฐาน (ไม่ทำแอด) | IG โพสต์ | IG ทำแอด | IG ยอดดูรวม | แชท/แอดเดือนนี้ |',
          '|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for m in sorted({r['month'] for r in fb + ig}):
        f = [r for r in fb if r['month'] == m]; g = [r for r in ig if r['month'] == m]
        L.append('| %s | %d | %s | %s | %s | %d | %s | %s | [[%s]] |' % (
            '%s %s' % (TH_M[int(m[5:])], m[:4]), len(f), (str(sum(1 for r in f if r.get('ads')))) if known else '–',
            fmt_n(sum(r['views'] or 0 for r in f)), fmt_n(med([r['views'] for r in organic(f)])) if known else '–',
            len(g), (str(sum(1 for r in g if r.get('ads')))) if known else '–', fmt_n(sum(r['views'] or 0 for r in g)), m))
    L += ['', '"ยอดดูรวม" รวมโพสต์ที่ทำแอดด้วย (ยอดจากแอดปนอยู่) · คอลัมน์สุดท้ายลิงก์ไปโน้ตเดือนใน `Monthly/` (ค่าแอด Meta + แชท FB/LINE เดือนเดียวกัน) — ดูคู่กับ [[1.2 ช่วงเวลาที่ลูกค้าทัก]]\n']
    if tt or yt:
        L += ['## รายเดือน TikTok / YouTube', '',
              '| เดือน | TikTok คลิป | TikTok ทำแอด | TikTok ยอดดูรวม | TikTok ยอดดูมัธยฐาน (ไม่ทำแอด) | YouTube คลิป | YouTube ทำแอด | YouTube ยอดดูรวม | YouTube ยอดดูมัธยฐาน (ไม่ทำแอด) | แชท/แอดเดือนนี้ |',
              '|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
        for m in sorted({r['month'] for r in tt + yt}):
            a = [r for r in tt if r['month'] == m]; b = [r for r in yt if r['month'] == m]
            L.append('| %s | %d | %s | %s | %s | %d | %s | %s | %s | [[%s]] |' % (
                '%s %s' % (TH_M[int(m[5:])], m[:4]),
                len(a), str(sum(1 for r in a if r.get('ads'))) if kn['TikTok'] else '–', fmt_n(sum(r['views'] or 0 for r in a)),
                fmt_n(med([r['views'] for r in organic(a)])),
                len(b), str(sum(1 for r in b if r.get('ads'))) if kn['YouTube'] else '–', fmt_n(sum(r['views'] or 0 for r in b)),
                fmt_n(med([r['views'] for r in organic(b)])), m))
        L += ['', 'เดือนที่ไม่มีโน้ตใน `Monthly/` ลิงก์จะเป็นสีจาง (ยังไม่มีข้อมูลแอด Meta/แชทเดือนนั้น)\n']

    def top(rs, key, n, title, fmtv, extra=None, show_pf=False):
        rs = [r for r in rs if r.get(key) is not None]
        rs.sort(key=lambda r: -r[key])
        if not rs:
            return []
        head = '| # | วันที่ |%s ประเภท | ค่า |%s โพสต์ |' % (' ช่องทาง |' if show_pf else '', ' %s |' % extra[0] if extra else '')
        out = ['### ' + title, '', head, '|---:|---|%s---|---:|%s---|' % ('---|' if show_pf else '', '---:|' if extra else '')]
        for i, r in enumerate(rs[:n], 1):
            out.append('| %d | %s |%s %s | %s |%s [[%s\\|%s]] |' % (
                i, r['posted'][:10], (' %s |' % r['platform']) if show_pf else '', r['format'], fmtv(r[key]),
                (' %s |' % extra[1](r)) if extra else '', note_name(r),
                first_line(r.get('title') or r['caption'], 60).replace('|', '/').replace('[', '(').replace(']', ')') or r['key']))
        return out + ['']
    pct2 = lambda v: '%.2f%%' % v
    L += ['## โพสต์ที่ดีที่สุด — ออร์แกนิกล้วน', '']
    L += top(ofb, 'views', 15, 'FB ยอดดูสูงสุด', fmt_n)
    L += top(oig, 'views', 15, 'IG ยอดดูสูงสุด', fmt_n)
    L += top(org['TikTok'], 'views', 15, 'TikTok ยอดดูสูงสุด', fmt_n, ('ความยาว', lambda r: fmt_dur(r.get('duration_s'))))
    L += top([r for r in org['YouTube'] if r['format'] == 'Shorts'], 'views', 10, 'YouTube Shorts ยอดดูสูงสุด', fmt_n)
    L += top([r for r in org['YouTube'] if r['format'] != 'Shorts'], 'views', 10, 'YouTube วิดีโอยาว/ไลฟ์ ยอดดูสูงสุด', fmt_n,
             ('ความยาว', lambda r: fmt_dur(r.get('duration_s'))))
    L += top([dict(r, ss=(r['saved'] or 0) + (r['shares'] or 0)) for r in oig], 'ss', 10, 'IG เซฟ + แชร์สูงสุด (คอนเทนต์ที่คนเก็บไว้/ส่งต่อ)', fmt_n)
    L += top(org['TikTok'], 'shares', 10, 'TikTok แชร์สูงสุด (คอนเทนต์ที่คนส่งต่อ)', fmt_n, ('ยอดดู', lambda r: fmt_n(r['views'])))
    L += top([r for r in ofb if (r['reach'] or 0) >= 500], 'rate', 10, 'FB Interaction ต่อคนดูสูงสุด (คนดู 500 ขึ้นไป)', pct2)
    L += top([r for r in oig if (r['reach'] or 0) >= 500], 'rate', 10, 'IG Interaction ต่อ reach สูงสุด (reach 500 ขึ้นไป)', pct2)
    L += top([r for r in org['TikTok'] if (r['views'] or 0) >= 1000], 'rate', 10, 'TikTok Interaction ต่อยอดดูสูงสุด (ยอดดู 1,000 ขึ้นไป)', pct2)
    L += top([r for r in org['YouTube'] if (r['views'] or 0) >= 500], 'rate', 10, 'YouTube Interaction ต่อยอดดูสูงสุด (ยอดดู 500 ขึ้นไป)', pct2)
    if groups:
        gs = sorted(groups, key=lambda g: (-len(g), -sum(r['views'] or 0 for r in g)))   # ลงหลายช่องทางก่อน (FB+IG คู่กันเป็นปกติ)
        win = {}
        for g in gs:
            if len(g) >= 3 and not any(r.get('ads') for r in g):
                w = max(g, key=lambda r: r['views'] or 0)['platform']
                win[w] = win.get(w, 0) + 1
        L += ['## คลิป/โพสต์เดียวกันในหลายช่องทาง', '',
              'จับคู่จากข้อความต้นแคปชัน/ชื่อคลิปที่ตรงกัน และวันที่โพสต์ห่างไม่เกิน 60 วัน — **%d เรื่อง** ลง 2 ช่องทางขึ้นไป (ลงครบ 4 ช่องทาง %d เรื่อง) · '
              'ลง 3 ช่องทางขึ้นไป %d เรื่อง · ใช้ดูว่าเรื่องเดียวกันไปได้ดีที่ช่องทางไหน · ★ = โพสต์นั้นทำแอด (ยอดดูรวมแอด)\n' % (len(gs), sum(1 for g in gs if len(g) == 4), sum(1 for g in gs if len(g) >= 3))]
        if win:
            L += ['เรื่องที่ลง 3 ช่องทางขึ้นไปและไม่มีโพสต์ไหนทำแอด — ช่องทางที่ได้ยอดดูสูงสุด: ' +
                  ' · '.join('%s %d เรื่อง' % (p, win[p]) for p in PLAT if p in win) + ' (นิยามยอดดูต่างกัน ดูเป็นแนวโน้ม)\n']
        L += ['| เรื่อง | ' + ' | '.join(PLAT) + ' |', '|---|' + '---:|' * len(PLAT)]
        for g in gs[:25]:
            by = {r['platform']: r for r in g}
            first = min(g, key=lambda r: r['posted'])
            L.append('| %s | %s |' % (
                first_line(first.get('title') or first['caption'], 50).replace('|', '/').replace('[', '(').replace(']', ')'),
                ' | '.join(('[[%s\\|%s]]%s' % (note_name(by[p]), fmt_n(by[p]['views']), ' ★' if by[p].get('ads') else '')) if p in by else '–'
                           for p in PLAT)))
        L += ['', 'ตารางแสดง 25 เรื่อง เรียงตามจำนวนช่องทางที่ลง แล้วตามยอดดูรวม · แต่ละโน้ตโพสต์มีลิงก์ไปโพสต์เดียวกันในช่องทางอื่น (เห็นเป็นเส้นใน Graph)\n']
    ads = [r for r in allr if r.get('ads')]
    if ads:
        L += ['## โพสต์ที่นำไปทำแอด', '',
              'ยอดดูของโพสต์กลุ่มนี้รวมส่วนที่มาจากแอด — ใช้ดูว่าโพสต์ไหนถูกเลือกไปยิงแอด ไม่ใช่เทียบความแรงแบบออร์แกนิก · '
              'TikTok/YouTube มี "ยอดดูที่ไม่ใช่แอด (ประมาณ)" = ยอดดู − ยอดดูจากแอด · ผลแชท/ปิดการขายของแอด Meta ดูที่ `Ads/`\n']
        L += top(ads, 'ad_spend', 25, 'ค่าแอดสูงสุด (%d โพสต์)' % len(ads), lambda v: '%s บาท' % fmt_n(v),
                 ('ยอดดูรวม / ไม่ใช่แอด ≈', lambda r: fmt_n(r['views']) + ((' / ' + fmt_n(r.get('organic_views_est'))) if r.get('organic_views_est') is not None else '')),
                 show_pf=True)
        for p in ('TikTok', 'YouTube'):
            a = [r for r in rows_by[p] if r.get('ads')]
            if a:
                av = sum(r.get('ad_views') or 0 for r in a); tv = sum(r['views'] or 0 for r in a)
                L += ['**%s:** %d คลิปที่ทำแอด ค่าแอดรวม %s บาท · ยอดดูรวม %s ซึ่งมาจากแอด %s (%s)\n' % (
                    p, len(a), fmt_n(sum(r['ad_spend'] or 0 for r in a)), fmt_n(tv), fmt_n(av), ('%.0f%%' % (100.0 * av / tv)) if tv else '–')]
    L += ['## ข้อจำกัด', '- FB วิดีโอ/Reel: มีแค่ยอดดูและคนดูไม่ซ้ำ ยังไม่มีเวลาดูหรือยอดดู 3 วินาที (ดึงผ่านเครื่องมือที่มีไม่ได้)',
          '- TikTok: API ให้แค่ยอดดู/ไลก์/คอมเมนต์/แชร์ของคลิปสาธารณะ — ไม่มี reach เวลาดู ดูจบ แหล่งที่มา (ดูใน TikTok Studio) · ป้ายทำแอดนับเฉพาะแอดใน TikTok Ads Manager (ไม่รวม Promote ในแอป)',
          '- YouTube: ช่องคอนเทนต์อยู่คนละอีเมล จึงได้แค่ตัวเลขสาธารณะ ไม่มีเวลาดู/ซับใหม่รายคลิป · อัตราดูถึง 25–100% มีเฉพาะผู้ชมแอด (Google Ads) · '
          'ดึงผ่านโควตา YouTube ของ Composio ซึ่งใช้ร่วมกับคนอื่น บางรอบอาจเต็ม (ระบบใช้ตัวเลขรอบก่อนและเตือนด้านบน)',
          '- "ทำแอด" = มีโฆษณาที่ใช้โพสต์นั้นโดยตรงและมีค่าใช้จ่ายตั้งแต่ %s · แอดที่สร้างภาพ/ข้อความใหม่ในตัวจัดการโฆษณา (ไม่ได้ใช้โพสต์บนเพจ) ไม่ปนกับตัวเลขโพสต์ · '
          'ตัวเลขโพสต์ที่ทำแอดแยกส่วนออร์แกนิก/จากแอดไม่ได้ (FB/IG ให้แค่ยอดรวม · TikTok/YouTube ประมาณจากยอดดูของแอด)' % date_th(SINCE),
          '- Stories ย้อนหลังไม่ได้ (API ให้เฉพาะสตอรี่ที่ยังขึ้นอยู่ 24 ชม.)',
          '- ตัวเลขเป็นยอดสะสมถึงวันที่ดึง เทียบโพสต์ใหม่กับโพสต์เก่าต้องระวัง · ช่อง "–" = แพลตฟอร์มไม่ส่งตัวเลขนั้นมา (ไม่ใช่ 0)',
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
    adm = ads_by_post()
    annotate_ads(fb, adm)
    annotate_ads(ig, adm)
    if adm is not None:
        fa = [r for r in fb if r['ads']]
        log('โพสต์ที่นำไปทำแอด FB %d (Reel/วิดีโอ %d) · IG %d' % (len(fa), sum(1 for r in fa if r['group'] == 'วิดีโอ'),
                                                            sum(1 for r in ig if r['ads'])))
    V.init(sys.modules[__name__])
    cfg = V.vault_config()
    tt, tt_st = V.tiktok(cfg)
    yt, yt_st = V.youtube(cfg)
    states = {'TikTok': tt_st, 'YouTube': yt_st}
    rows_by = {'FB': fb, 'IG': ig, 'TikTok': tt, 'YouTube': yt}
    log('แถวที่ใช้ FB %d · IG %d · TikTok %d%s · YouTube %d%s · คำขอทั้งหมด %d · ลดขนาดหน้า %d' % (
        len(fb), len(ig), len(tt), '' if tt_st['ok'] else ' (รอบก่อน)', len(yt), '' if yt_st['ok'] else ' (รอบก่อน)',
        STATS['calls'], STATS['shrink']))
    if not fb and not ig:
        sys.exit('ไม่ได้โพสต์เลย — ไม่เขียนทับของเดิม')
    allr = fb + ig + tt + yt
    links, groups = V.crosspost(allr)
    log('โพสต์เดียวกันหลายช่องทาง %d เรื่อง' % len(groups))
    if DRY:
        log('DRY_RUN: ไม่เขียนชีตและ vault')
        return
    write_tab('คำอธิบาย', about_rows(stamp, rows_by, states, adm is not None))
    write_tab('FB โพสต์', table_rows(fb, FB_COLS))
    write_tab('IG โพสต์', table_rows(ig, IG_COLS))
    if tt_st['ok']:
        write_tab('TikTok โพสต์', table_rows(tt, TT_COLS))
    if yt_st['ok']:
        write_tab('YouTube วิดีโอ', table_rows(yt, YT_COLS))
    write_tab('สรุปรายเดือน', monthly_rows(allr))
    fresh = fb + ig + (tt if tt_st['ok'] else []) + (yt if yt_st['ok'] else [])   # ช่องทางที่ใช้ข้อมูลรอบก่อน → ไม่เขียนโน้ตทับ
    files = {note_path(r): post_note(r, stamp, links.get(r['post_id'], ())) for r in fresh}
    files['Content/สรุปคอนเทนต์.md'] = summary_note(rows_by, stamp, states, groups)
    clean = [{k: v for k, v in r.items() if not k.startswith('_')} for r in allr]
    files['.vault/content/posts.json'] = json.dumps({'pulled': stamp, 'since': SINCE, 'posts': clean,
                                                     'accounts': {p: states[p].get('account') or {} for p in states}},
                                                    ensure_ascii=False, separators=(',', ':'))
    commit(files, 'content: insight โพสต์ FB/IG/TikTok/YouTube %s' % stamp)
    log('เสร็จ')


if __name__ == '__main__':
    main()

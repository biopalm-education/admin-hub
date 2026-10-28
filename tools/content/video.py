# -*- coding: utf-8 -*-
"""TikTok + YouTube สำหรับ pull.py (insight คอนเทนต์) — เรียกผ่าน Composio MCP ตัวเดียวกับ FB/IG

TikTok  : Composio `tiktok` (TIKTOK_LIST_VIDEOS · TIKTOK_GET_USER_STATS) = คลิปสาธารณะ + ยอดดู/ไลก์/คอมเมนต์/แชร์
          ค่าแอด: Composio `tiktok_ads` รายงานรายโฆษณา (ad_name = แคปชันโพสต์ + "_…") → จับคู่กับคลิปด้วยแคปชัน
YouTube : อ่านข้อมูลสาธารณะของช่อง (ยอดดู/ไลก์/คอมเมนต์/ความยาว) ผ่าน Composio `youtube` หรือ API key ของเราเอง (secret YT_API_KEY ถ้ามี)
          — ช่องคอนเทนต์อยู่คนละอีเมล
          จึงไม่มีเวลาดู/ซับใหม่ · ค่าแอด + อัตราดูถึง 25/50/75/100% ของผู้ชมแอด: Composio `googleads` (GAQL รายคลิป)
แต่ละช่องทางพลาดได้โดยไม่ล้มงานหลัก: ดึงไม่ได้ → ใช้ตัวเลขรอบก่อนจาก vault (.vault/content/posts.json) และบอกในสรุป
ID บัญชีโฆษณา TikTok / ช่อง YouTube อ่านจาก vault private (.vault/content/config.json) — repo นี้ public จึงไม่เขียน ID ไว้ในไฟล์
log บอกแค่ขั้นตอนและจำนวน
"""
import os, re, json, base64, datetime as dt
import requests

P = None            # โมดูล pull.py (ตั้งใน init)
YT_KEY = (os.environ.get('YT_API_KEY') or '').strip()   # secret ของ repo (ถ้ามี) → เรียก YouTube API ตรง ไม่ใช้โควตาร่วมของ Composio
_PREV = {}          # posts.json รอบก่อน (โหลดเมื่อจำเป็น)


def init(pull_module):
    global P
    P = pull_module


def _start():
    return dt.datetime.fromisoformat(P.SINCE).replace(tzinfo=P.BKK)


def _today():
    return dt.datetime.now(P.BKK).date().isoformat()


def _int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _items(d, need='id'):
    """รายการ dict ตัวแรกที่มีคีย์ need (คำตอบ Composio ห่อไม่เหมือนกันทุกเครื่องมือ)"""
    if isinstance(d, list):
        if d and all(isinstance(x, dict) for x in d) and any(need in x for x in d):
            return d
        for x in d:
            r = _items(x, need)
            if r:
                return r
        return []
    if isinstance(d, dict):
        for k in ('items', 'videos', 'channels', 'data', 'results', 'response'):
            if k in d:
                r = _items(d[k], need)
                if r:
                    return r
    return []


# ---------------------------------------------------------------- vault: config + ข้อมูลรอบก่อน
def _vault_get(path):
    d = P.call('GITHUB_GET_REPOSITORY_CONTENT', {'owner': P.OWNER, 'repo': P.REPO, 'path': path}, tries=2)
    return d.get('content') if isinstance(d, dict) and 'content' in d else d


def vault_config():
    """{'tiktok_advertiser_id', 'youtube_channel_id'} จาก .vault/content/config.json · ไม่มี → {}"""
    try:
        c = _vault_get('.vault/content/config.json')
        raw = c.get('content') if isinstance(c, dict) else None
        if raw:
            t = ''.join(str(raw).split())
            return json.loads(base64.b64decode(t + '=' * (-len(t) % 4)).decode('utf-8'))
    except Exception as e:
        P.log('อ่าน config ใน vault ไม่ได้ (%s)' % P._safe(e))
    return {}


def prev_rows(platform):
    """แถวของช่องทางนี้จากรอบก่อน (posts.json ใน vault) · อ่านผ่าน download_url เพราะไฟล์ใหญ่เกินคำตอบ Composio"""
    if 'posts' not in _PREV:
        _PREV['posts'], _PREV['pulled'] = [], None
        try:
            lst = _vault_get('.vault/content')
            lst = lst if isinstance(lst, list) else []
            url = next((x.get('download_url') for x in lst if isinstance(x, dict) and x.get('name') == 'posts.json'), None)
            if url:
                r = requests.get(url, timeout=120)
                if r.status_code == 200:
                    j = r.json()
                    _PREV['posts'], _PREV['pulled'] = j.get('posts') or [], j.get('pulled')
        except Exception as e:
            P.log('อ่านข้อมูลรอบก่อนไม่ได้ (%s)' % P._safe(e))
    rows = [dict(r, _stale=True) for r in _PREV['posts'] if r.get('platform') == platform]
    return rows, _PREV.get('pulled')


# ---------------------------------------------------------------- จับคู่ข้อความ
def _norm(s):
    return re.sub(r'\s+', '', str(s or '')).lower()


def _prefix(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def match_key(text):
    """คีย์จับคู่คลิปเดียวกันข้ามช่องทาง: ตัวอักษรไทย/อังกฤษ/ตัวเลข 20 ตัวแรก ไม่นับ #แท็ก ลิงก์ เครื่องหมาย"""
    t = str(text or '').split('\n')[0] if len(str(text or '').split('\n')[0]) >= 12 else str(text or '')
    t = re.sub(r'https?://\S+|[#@]\S+', ' ', t.lower())
    t = re.sub(r'[^0-9a-zก-ฮะ-ฺเ-๎]', '', t)
    return t[:20] if len(t) >= 12 else None


# ---------------------------------------------------------------- TikTok
def tiktok_videos(start):
    out, seen, cur, n = [], set(), None, 20
    start_ts = int(start.timestamp())
    for _ in range(300):
        a = {'max_count': n}
        if cur:
            a['cursor'] = cur
        try:
            d = P.call('TIKTOK_LIST_VIDEOS', a)
        except P.CallError as e:
            if 'TOO_LARGE' in str(e) and n > 2:            # embed_html ยาว → ลดขนาดหน้า
                n = max(2, n // 2)
                P.STATS['shrink'] += 1
                continue
            raise
        err = d.get('error') if isinstance(d, dict) else None
        if isinstance(err, dict) and err.get('code') not in (None, '', 'ok'):
            raise P.CallError('TIKTOK_LIST_VIDEOS: %s' % str(err.get('code'))[:60])
        dd = d.get('data') if isinstance(d, dict) and isinstance(d.get('data'), dict) else d
        vids = [v for v in (dd.get('videos') or []) if isinstance(v, dict) and v.get('id')]
        new = [v for v in vids if v['id'] not in seen]
        for v in new:
            seen.add(v['id'])
        out.extend(new)
        if not dd.get('has_more') or not new or not dd.get('cursor'):
            break
        if min(_int(v.get('create_time')) or 0 for v in new) < start_ts:
            break
        cur = dd['cursor']
        if n < 20:
            n = min(20, n * 2)
    return out


def tiktok_account():
    try:
        d = P.call('TIKTOK_GET_USER_STATS', {'fields': ['follower_count', 'likes_count', 'video_count', 'username']}, tries=2)
        dd = d.get('data') if isinstance(d.get('data'), dict) else d
        u = dd.get('user') or {}
        return {'followers': _int(u.get('follower_count')), 'likes_total': _int(u.get('likes_count')),
                'videos_total': _int(u.get('video_count')), 'username': u.get('username')}
    except Exception:
        return {}


def build_tiktok(vids):
    out, start = [], _start()
    for v in vids:
        ts = _int(v.get('create_time'))
        if not ts:
            continue
        t = dt.datetime.fromtimestamp(ts, P.BKK)
        if t < start:
            continue
        dur = _int(v.get('duration'))
        views, likes, cm, sh = (_int(v.get(k)) for k in ('view_count', 'like_count', 'comment_count', 'share_count'))
        inter = sum(x for x in (likes, cm, sh) if x is not None)
        link = str(v.get('share_url') or '').split('?')[0] or 'https://www.tiktok.com/video/%s' % v['id']
        cap = str(v.get('video_description') or v.get('title') or '')
        out.append(dict(platform='TikTok', posted=t.strftime('%Y-%m-%d %H:%M'), month=t.strftime('%Y-%m'),
                        format='วิดีโอ' if dur else 'ภาพสไลด์', group='วิดีโอ' if dur else 'ภาพนิ่ง',
                        post_id=str(v['id']), key=str(v['id']), link=link, caption=cap, title=None,
                        views=views, reach=None, likes=likes, comments=cm, shares=sh, saved=None,
                        interactions=inter, rate=P.pct(inter, views), profile_visits=None, follows=None,
                        avg_watch_s=None, watch_total_h=None, skip_rate=None, duration_s=dur))
    return out


def _tiktok_report(adv, lifetime):
    out, page = [], 1
    while page <= 50:
        a = {'report_type': 'BASIC', 'data_level': 'AUCTION_AD', 'advertiser_id': str(adv), 'dimensions': ['ad_id'],
             'metrics': ['ad_name', 'spend', 'impressions', 'video_play_actions'], 'page_size': 200, 'page': page}
        if lifetime:
            a['query_lifetime'] = True
        else:
            a['start_date'], a['end_date'] = P.SINCE, _today()
        d = P.call('TIKTOK_ADS_GET_REPORT_INTEGRATED', a, tries=3)
        rows = d.get('rows') if isinstance(d, dict) else None
        if rows is None and isinstance(d, dict) and isinstance(d.get('data'), dict):
            d = d['data']
            rows = d.get('rows')
        out += [r for r in rows or [] if isinstance(r, dict)]
        pi = d.get('page_info') or {}
        if not d.get('has_more') and page >= int(pi.get('total_page') or 1):
            break
        page += 1
    return out


def tiktok_ads(adv, rows):
    """ใส่ ads / ad_spend / ad_views ให้แถว TikTok · คืน True ถ้ารู้ข้อมูลแอด"""
    if not adv:
        P.log('TikTok: ไม่มี tiktok_advertiser_id ใน config — ข้ามป้าย "ทำแอด"')
        return False
    try:
        try:
            rep = _tiktok_report(adv, False)
        except P.CallError:
            rep = _tiktok_report(adv, True)                 # ช่วงวันที่ยาวเกินที่ TikTok รับ → ตลอดอายุแอด
    except Exception as e:
        P.log('TikTok: ดึงรายงานแอดไม่ได้ (%s %s) — ข้ามป้าย "ทำแอด"' % (type(e).__name__, P._safe(e)))
        return False
    caps = [(r, _norm(r['caption'])) for r in rows]
    hit = miss = 0
    for r in rows:
        r.update(ads=0, ad_spend=0, ad_views=0)
    acc = {}
    for x in rep:
        m = x.get('metrics') or {}
        spend = float(m.get('spend') or 0)
        if spend <= 0:
            continue
        na = _norm(m.get('ad_name'))
        best, score = None, 0
        for r, nc in caps:
            if len(nc) < 8:
                continue
            p = _prefix(na, nc)
            if p >= min(len(nc), 25) and p > score:
                best, score = r, p
        if not best:
            miss += 1
            continue
        hit += 1
        a = acc.setdefault(best['post_id'], [0, 0.0, 0])
        a[0] += 1
        a[1] += spend
        a[2] += _int(m.get('video_play_actions')) or 0
    for r in rows:
        if r['post_id'] in acc:
            n, s, v = acc[r['post_id']]
            r.update(ads=n, ad_spend=int(round(s)), ad_views=v)
    P.log('TikTok แอดที่มีค่าใช้จ่าย %d · จับคู่คลิปได้ %d · ไม่พบคลิป %d' % (hit + miss, hit, miss))
    return True


def tiktok_month_spend(adv):
    """ค่าแอด TikTok ทั้งบัญชีรายเดือน (ตั้งแต่ SINCE) → {เดือน: {'spend', 'views'}} · views = ยอดเล่นวิดีโอจากแอด"""
    out = {}
    for s, e in P.month_spans():
        a = {'report_type': 'BASIC', 'data_level': 'AUCTION_ADVERTISER', 'advertiser_id': str(adv), 'dimensions': ['advertiser_id'],
             'metrics': ['spend', 'video_play_actions'], 'start_date': s, 'end_date': e, 'page_size': 10}
        d = P.call('TIKTOK_ADS_GET_REPORT_INTEGRATED', a, tries=3)
        rows = (d.get('rows') if isinstance(d, dict) else None) or ((d.get('data') or {}).get('rows') if isinstance(d, dict) else None) or []
        sp = sum(float((r.get('metrics') or {}).get('spend') or 0) for r in rows if isinstance(r, dict))
        vw = sum(_int((r.get('metrics') or {}).get('video_play_actions')) or 0 for r in rows if isinstance(r, dict))
        if sp or vw:
            out[s[:7]] = {'spend': int(round(sp)), 'views': vw}
    return out


def _month_spend(st, fn, label):
    try:
        st['month_spend'] = fn()
    except Exception as e:
        P.log('%s: ดึงค่าแอดรายเดือนไม่ได้ (%s)' % (label, type(e).__name__))


def tiktok(cfg):
    """→ (rows, state)"""
    st = {'ok': False, 'ads_ok': False, 'stale': None, 'account': {}}
    try:
        vids = tiktok_videos(_start())
        rows = sorted(build_tiktok(vids), key=lambda r: r['posted'], reverse=True)
        st['ok'] = True
        P.log('TikTok คลิป %d (ทั้งหมดที่อ่าน %d)' % (len(rows), len(vids)))
    except Exception as e:                                  # พลาดอะไรก็ตาม → ไม่ล้มงาน FB/IG
        st['why'] = 'เรียก TikTok ไม่สำเร็จ (ถ้าซ้ำหลายรอบ: เชื่อม Composio tiktok ใหม่)'
        P.log('TikTok: ดึงคลิปไม่ได้ (%s %s) — ใช้ตัวเลขรอบก่อน' % (type(e).__name__, P._safe(e)[:120]))
        rows, st['stale'] = prev_rows('TikTok')
        if cfg.get('tiktok_advertiser_id'):
            _month_spend(st, lambda: tiktok_month_spend(cfg['tiktok_advertiser_id']), 'TikTok')
        return rows, st
    st['account'] = tiktok_account()
    if cfg.get('tiktok_advertiser_id'):
        _month_spend(st, lambda: tiktok_month_spend(cfg['tiktok_advertiser_id']), 'TikTok')
    st['ads_ok'] = tiktok_ads(cfg.get('tiktok_advertiser_id'), rows)
    if not st['ads_ok']:
        for r in rows:
            r.update(ads=None, ad_spend=None, ad_views=None)
    for r in rows:
        r['organic_views_est'] = max(0, (r['views'] or 0) - (r.get('ad_views') or 0)) if r.get('views') is not None and r.get('ads') is not None else None
    return rows, st


# ---------------------------------------------------------------- YouTube
def iso_dur(s):
    m = re.match(r'^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$', str(s or ''))
    if not m:
        return None
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


SHORTS_3MIN = dt.datetime(2024, 10, 15, tzinfo=dt.timezone.utc)


def is_short(vid, dur, t):
    """Shorts ไม่มีช่องบอกใน API: ลองเปิด youtube.com/shorts/<id> (Shorts = 200, คลิปปกติ = ส่งต่อไป /watch)
    เปิดไม่ได้ → เดาจากความยาว (≤60 วิ หรือ ≤3 นาทีหลัง 15 ต.ค. 2024)"""
    if dur is None or dur > 180:
        return False
    try:
        r = requests.head('https://www.youtube.com/shorts/' + vid, allow_redirects=False, timeout=10,
                          headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            return True
        if r.status_code in (301, 302, 303, 307, 308) and '/watch' in (r.headers.get('location') or ''):
            return False
    except requests.RequestException:
        pass
    P.STATS['yt_shorts_guess'] = P.STATS.get('yt_shorts_guess', 0) + 1
    return dur <= 60 or (dur <= 180 and t >= SHORTS_3MIN)


def yt_api(endpoint, params):
    """YouTube Data API ด้วย API key ของเราเอง · error ไม่พิมพ์ URL (มี key อยู่ใน URL)"""
    try:
        r = requests.get('https://www.googleapis.com/youtube/v3/' + endpoint, params=dict(params, key=YT_KEY), timeout=60)
    except requests.RequestException as e:
        raise P.CallError('YouTube API %s' % type(e).__name__)
    if r.status_code != 200:
        why = ''
        try:
            why = ((r.json().get('error') or {}).get('errors') or [{}])[0].get('reason') or ''
        except Exception:
            pass
        raise P.CallError('YouTube API HTTP %d %s' % (r.status_code, str(why)[:40]))
    return r.json()


def yt_channel(cid):
    if YT_KEY:
        d = yt_api('channels', {'id': cid, 'part': 'snippet,statistics,contentDetails'})
    else:
        d = P.call('YOUTUBE_GET_CHANNEL_STATISTICS', {'id': cid, 'part': 'snippet,statistics,contentDetails'}, tries=2)
    it = next((x for x in _items(d) if x.get('id') == cid), None) or {}
    s = it.get('statistics') or {}
    up = ((it.get('contentDetails') or {}).get('relatedPlaylists') or {}).get('uploads') or ('UU' + cid[2:])
    return up, {'title': (it.get('snippet') or {}).get('title'), 'subscribers': None if s.get('hiddenSubscriberCount') else _int(s.get('subscriberCount')),
                'views_total': _int(s.get('viewCount')), 'videos_total': _int(s.get('videoCount'))}


def yt_ids(uploads, start):
    out, tok = [], None
    for _ in range(100):
        a = {'playlistId': uploads, 'part': 'contentDetails', 'maxResults': 50,
             'fields': 'items(contentDetails(videoId,videoPublishedAt)),nextPageToken'}
        if tok:
            a['pageToken'] = tok
        d = yt_api('playlistItems', a) if YT_KEY else P.call('YOUTUBE_LIST_PLAYLIST_ITEMS', a, tries=2)
        its = _items(d, 'contentDetails')
        old = 0
        for x in its:
            cd = x.get('contentDetails') or {}
            t = P.to_bkk(str(cd.get('videoPublishedAt') or '').replace('Z', '+00:00'))
            if cd.get('videoId') and (t is None or t >= start):
                out.append(cd['videoId'])
            elif t is not None:
                old += 1
        tok = d.get('nextPageToken') if isinstance(d, dict) else None
        if not tok or (its and old == len(its)):             # ทั้งหน้าเก่ากว่าช่วงที่ต้องการ
            break
    return list(dict.fromkeys(out))


def yt_details(ids):
    out, i, n = [], 0, (50 if YT_KEY else 10)
    parts = ['snippet', 'statistics', 'contentDetails', 'status', 'liveStreamingDetails']
    while i < len(ids):
        b = ids[i:i + n]
        try:
            if YT_KEY:
                d = yt_api('videos', {'id': ','.join(b), 'part': ','.join(parts), 'maxResults': 50})
            else:
                d = P.call('YOUTUBE_GET_VIDEO_DETAILS_BATCH', {'id': b, 'parts': parts}, tries=2)
        except P.CallError as e:
            if 'TOO_LARGE' in str(e) and n > 1:               # คำอธิบายคลิปยาว → ลดขนาดก้อน
                n = max(1, n // 2)
                P.STATS['shrink'] += 1
                continue
            raise
        out += [x for x in _items(d, 'snippet') if x.get('id') in b]
        i += len(b)
    return out


def build_youtube(items):
    out, start = [], _start()
    for it in items:
        sn, stt = it.get('snippet') or {}, it.get('statistics') or {}
        if ((it.get('status') or {}).get('privacyStatus') or 'public') != 'public':
            continue
        t = P.to_bkk(str(sn.get('publishedAt') or '').replace('Z', '+00:00'))
        if not t or t < start:
            continue
        vid = it['id']
        dur = iso_dur((it.get('contentDetails') or {}).get('duration'))
        live = bool(it.get('liveStreamingDetails')) or sn.get('liveBroadcastContent') in ('live', 'upcoming')
        f = 'ไลฟ์' if live else ('Shorts' if is_short(vid, dur, t) else 'วิดีโอยาว')
        views, likes, cm = _int(stt.get('viewCount')), _int(stt.get('likeCount')), _int(stt.get('commentCount'))
        inter = sum(x for x in (likes, cm) if x is not None)
        title = str(sn.get('title') or '')
        desc = str(sn.get('description') or '')
        out.append(dict(platform='YouTube', posted=t.strftime('%Y-%m-%d %H:%M'), month=t.strftime('%Y-%m'), format=f, group='วิดีโอ',
                        post_id=vid, key=vid, link=('https://www.youtube.com/shorts/%s' if f == 'Shorts' else 'https://www.youtube.com/watch?v=%s') % vid,
                        caption=(title + ('\n' + desc if desc.strip() else '')), title=title,
                        views=views, reach=None, likes=likes, comments=cm, shares=None, saved=None,
                        interactions=inter, rate=P.pct(inter, views), profile_visits=None, follows=None,
                        avg_watch_s=None, watch_total_h=None, skip_rate=None, duration_s=dur))
    return out


GAQL = ("SELECT video.id, ad_group_ad.ad.id, metrics.cost_micros, metrics.impressions, metrics.video_trueview_views, "
        "metrics.video_quartile_p25_rate, metrics.video_quartile_p50_rate, metrics.video_quartile_p75_rate, metrics.video_quartile_p100_rate "
        "FROM video WHERE segments.date BETWEEN '%s' AND '%s' AND metrics.impressions > 0")


def _gaql_span(s, e, acc, macc):
    try:
        d = P.call('GOOGLEADS_SEARCH_STREAM_GAQL', {'query': GAQL % (s, e)}, tries=3)
    except P.CallError as err:
        a, b = dt.date.fromisoformat(s), dt.date.fromisoformat(e)
        if 'TOO_LARGE' in str(err) and b > a:                 # คำตอบใหญ่เกิน → แบ่งครึ่งช่วงวันที่
            mid = a + (b - a) // 2
            _gaql_span(s, mid.isoformat(), acc, macc)
            _gaql_span((mid + dt.timedelta(days=1)).isoformat(), e, acc, macc)
            return
        raise
    for x in (d.get('results') if isinstance(d, dict) else None) or []:
        vid = ((x.get('video') or {}).get('id'))
        if not vid:
            continue
        m = x.get('metrics') or {}
        imp = _int(m.get('impressions')) or 0
        cost = (_int(m.get('costMicros')) or 0) / 1e6
        o = acc.setdefault(vid, {'ads': set(), 'spend': 0.0, 'impr': 0, 'views': 0, 'q': [0.0, 0.0, 0.0, 0.0]})
        if cost > 0:
            o['ads'].add(str(((x.get('adGroupAd') or {}).get('ad') or {}).get('id')))
        o['spend'] += cost
        o['impr'] += imp
        o['views'] += _int(m.get('videoTrueviewViews')) or 0
        mo = macc.setdefault(s[:7], {'spend': 0.0, 'views': 0})            # ทั้งบัญชี (รวมคลิปที่ลงก่อน SINCE)
        mo['spend'] += cost
        mo['views'] += _int(m.get('videoTrueviewViews')) or 0
        for i, k in enumerate(('videoQuartileP25Rate', 'videoQuartileP50Rate', 'videoQuartileP75Rate', 'videoQuartileP100Rate')):
            o['q'][i] += float(m.get(k) or 0) * imp


def gads_collect():
    """Google Ads แอดวิดีโอ รายเดือนตั้งแต่ SINCE → (รายคลิป, รายเดือนทั้งบัญชี)"""
    acc, macc = {}, {}
    for s, e in P.month_spans():
        _gaql_span(s, e, acc, macc)
    return acc, {m: {'spend': int(round(v['spend'])), 'views': v['views']} for m, v in sorted(macc.items()) if v['spend'] or v['views']}


def youtube_ads(rows, acc):
    """ค่าแอด Google Ads รายคลิปตั้งแต่ SINCE + อัตราดูถึง 25/50/75/100% (ของผู้ชมแอด) · acc None = ดึงไม่ได้ · คืน True ถ้ารู้ข้อมูลแอด"""
    if acc is None:
        for r in rows:
            r.update(ads=None, ad_spend=None, ad_views=None, ad_p25=None, ad_p50=None, ad_p75=None, ad_p100=None)
        return False
    n = 0
    for r in rows:
        o = acc.get(r['post_id'])
        if o and o['spend'] > 0:
            n += 1
            q = [round(100.0 * x / o['impr'], 1) if o['impr'] else None for x in o['q']]
            r.update(ads=len(o['ads']), ad_spend=int(round(o['spend'])), ad_views=o['views'],
                     ad_p25=q[0], ad_p50=q[1], ad_p75=q[2], ad_p100=q[3])
        else:
            r.update(ads=0, ad_spend=0, ad_views=0, ad_p25=None, ad_p50=None, ad_p75=None, ad_p100=None)
    P.log('YouTube คลิปที่ยิงแอดในช่วงนี้ %d (ทั้งบัญชี %d)' % (n, sum(1 for o in acc.values() if o['spend'] > 0)))
    return True


def youtube(cfg):
    """→ (rows, state)"""
    st = {'ok': False, 'ads_ok': False, 'stale': None, 'account': {}}
    acc = None
    try:
        acc, st['month_spend'] = gads_collect()                 # ไม่ใช้โควตา YouTube — ได้แม้ดึงรายการคลิปไม่ได้
    except Exception as e:
        P.log('YouTube: ดึง Google Ads ไม่ได้ (%s %s) — ข้ามป้าย "ทำแอด"' % (type(e).__name__, P._safe(e)))
    cid = cfg.get('youtube_channel_id')
    if not cid:
        P.log('YouTube: ไม่มี youtube_channel_id ใน config — ข้าม')
        rows, st['stale'] = prev_rows('YouTube')
        return rows, st
    try:
        up, st['account'] = yt_channel(cid)
        ids = yt_ids(up, _start())
        rows = sorted(build_youtube(yt_details(ids)), key=lambda r: r['posted'], reverse=True)
        st['ok'] = True
        P.log('YouTube คลิป %d (ผ่าน %s) · เดา Shorts จากความยาว %d' % (len(rows), 'API key ของเรา' if YT_KEY else 'Composio',
                                                                       P.STATS.get('yt_shorts_guess', 0)))
    except Exception as e:
        quota = 'quota' in str(e).lower()
        st['why'] = ('โควตา YouTube %s เต็ม' % ('ของ API key' if YT_KEY else 'ของ Composio (ใช้ร่วมกับผู้ใช้อื่น)')) if quota else 'เรียก YouTube ไม่สำเร็จ'
        P.log('YouTube: ดึงข้อมูลช่องไม่ได้ (%s%s) — ใช้ตัวเลขรอบก่อน' % (type(e).__name__, ' · quotaExceeded' if quota else ''))
        rows, st['stale'] = prev_rows('YouTube')
        return rows, st
    st['ads_ok'] = youtube_ads(rows, acc)
    for r in rows:
        r['organic_views_est'] = max(0, (r['views'] or 0) - (r.get('ad_views') or 0)) if r.get('views') is not None and r.get('ads') is not None else None
    return rows, st


# ---------------------------------------------------------------- คลิปเดียวกันหลายช่องทาง
def crosspost(rows, days=60):
    """{post_id: [แถวของช่องทางอื่นที่เป็นคลิป/โพสต์เดียวกัน]} + รายการกลุ่ม · จับคู่จากข้อความต้นแคปชัน/ชื่อคลิป และวันที่ห่างไม่เกิน days"""
    by = {}
    for r in rows:
        k = match_key(r.get('title') or r.get('caption'))
        if k:
            by.setdefault(k, []).append(r)
    links, groups = {}, []
    for k, rs in by.items():
        if len({r['platform'] for r in rs}) < 2:
            continue
        rs = sorted(rs, key=lambda r: r['posted'])
        t0 = dt.datetime.strptime(rs[0]['posted'][:10], '%Y-%m-%d')
        rs = [r for r in rs if (dt.datetime.strptime(r['posted'][:10], '%Y-%m-%d') - t0).days <= days]
        best = {}
        for r in rs:                                          # ช่องทางละ 1 (ยอดดูสูงสุด)
            if r['platform'] not in best or (r['views'] or 0) > (best[r['platform']]['views'] or 0):
                best[r['platform']] = r
        if len(best) < 2:
            continue
        g = list(best.values())
        groups.append(g)
        for r in g:
            links[r['post_id']] = [x for x in g if x is not r]
    return links, groups

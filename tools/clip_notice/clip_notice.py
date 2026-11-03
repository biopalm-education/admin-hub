# -*- coding: utf-8 -*-
"""แจ้งเตือนรายวัน · คลิปเทปบันทึกการสอนที่ "ตัดเสร็จแล้ว" (ปิดเสียงคำหยาบ + ตัด dead air) → LINE กลุ่ม Admin dashboard (v2 · 3 พ.ย. 2026)

ข้อความ: ตัดเสร็จวันนี้ (รายคลิป + ใช้เวลากี่วันหลังเรียนจบ) · รอบสัปดาห์ จ.–อา. ตามวันเรียน (วันจันทร์ = ปิดรอบสัปดาห์ก่อน)
         · คิวรอตัดรายคลิป + เวลาที่คาดว่าจะเสร็จ · QA ไม่ผ่าน + สาเหตุ · คลิปที่ระบบหยุดลองแล้ว
อ่านอย่างเดียว ไม่เขียนป้าย/ไฟล์ใด ๆ และไม่แตะ pipeline yt-uploader / line-notice.yml / tools/before_after
  - Drive «ต้นฉับบ» (บัญชี mkt) : ป้าย bp_* บนไฟล์ต้นฉบับ + JSON ผลตัด (bp_cutresult) + JSON คำตัดสิน (bp_decisions → หัวข้อ)
    + ป้ายใน «ต้นฉับบ/_ล้างแล้ว (auto)» (คลิปที่งานเคลียร์วันจันทร์ย้ายไปแล้ว นับเป็นตัดเสร็จ)
  - New_Control Sheet แท็บ Course + Closed Course : จับคู่คอร์สจาก "วันที่ + เวลา" ในชื่อไฟล์ (ทีมยังไม่ได้วางคลิปตอนแจ้ง)
ช่วงที่นับ "วันนี้" = หลังรอบที่ส่งสำเร็จครั้งก่อน (ประวัติรันของ workflow นี้) → ส่งพลาดวันไหน วันถัดไปรวมให้ ไม่ตกหล่น
เวลาคาดว่าจะเสร็จ = รอบถอดคำหยาบถัดไป (09:13 / 15:13 / 20:13 + ตัด ~15 นาที) หลังคำบรรยาย YouTube น่าจะพร้อม (ค่ากลางจริงย้อนหลัง)
กันโควตา LINE: ถ้าส่งแล้วเหลือไม่พอสำหรับ Tracking (จันทร์/ศุกร์) ที่เหลือของเดือน = ไม่ส่ง (รันขึ้นสีแดง)
repo นี้ public: log พิมพ์แค่จำนวน — ไม่พิมพ์ชื่อคลิป หัวข้อ ลิงก์ หรือ id

env  CLIP_ORIG_ID · CLIP_SHEET_ID (secret) · COMPOSIO_API_KEY · COMPOSIO_MCP_URL · LINE_NOTICE_TOKEN · LINE_NOTICE_TO_2
     SEND=1 ส่งจริง (อย่างอื่น = สร้างข้อความอย่างเดียว) · AUTO=1 รอบตั้งเวลา (กันส่งซ้ำวันเดียวกัน) · SINCE=ISO เวลาเริ่มนับ (ไม่บังคับ)
"""
import os, re, sys, json, uuid, calendar, statistics, datetime as dt
from concurrent.futures import ThreadPoolExecutor
import urllib.request, urllib.error

TH = dt.timezone(dt.timedelta(hours=7))
ORIG = (os.environ.get('CLIP_ORIG_ID') or '').strip()          # «ต้นฉับบ»
SHEET = (os.environ.get('CLIP_SHEET_ID') or '').strip()        # New_Control Sheet
DRIVE = os.environ.get('CLIP_DRIVE_ACCOUNT') or 'googledrive_strown-skyre'     # mkt.biopalm@gmail.com
SHEETS = os.environ.get('CLIP_SHEETS_ACCOUNT') or 'googlesheets_thrast-arrope'  # Google Sheets (mkt) อ่านอย่างเดียว
TABS = ('Course', 'Closed Course')
TOMB = '_ล้างแล้ว (auto)'
PIPE_START = dt.date(2026, 10, 16)       # ก่อนวันนี้อัป/ตัดด้วยมือ → ไม่นับเป็นคิว
STALE_DAYS = 2                           # คิวรอเกินนี้หลังเรียนจบ = ⚠️
MAX_CLUSTERS = 6
MAX_QUEUE_LINES = 10
PACK_H_DEFAULT = 13.0                    # ชม. จากคลิปเข้า Drive → พร้อมถอดคำหยาบ (อัป YouTube + คำบรรยาย + pack) ค่ากลาง 28 ต.ค.–3 พ.ย.
ROUNDS = ((9, 30), (15, 30), (20, 30))   # รอบถอดคำหยาบ 09:13 / 15:13 / 20:13 + ตัดเสร็จ ~15 นาที
CUT_ROUNDS = ((3, 30),) + ROUNDS         # + รอบสำรองของงานตัด 03:17
WF_FILE = 'clip-notice.yml'
BAR = '━━━━━━━━━━━━'
TH_M = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']
TH_D = ['จ.', 'อ.', 'พ.', 'พฤ.', 'ศ.', 'ส.', 'อา.']
DATE_RE = re.compile(r'^(\d{2})-(\d{2})-(\d{4})$')
CLIP_RE = re.compile(r'^(\d{2})-(\d{2})-(\d{4}) (\d{2})\.(\d{2})(?:-(\d+))?')
TIME_RE = re.compile(r'(\d{1,2})[.:](\d{2})\s*[-–]\s*\d{1,2}[.:]\d{2}')
STAGE_TXT = {'up': 'รออัป YouTube', 'yt': 'รอคำบรรยาย YouTube', 'tr': 'รอถอดคำหยาบ', 'cut': 'รอตัด'}

RUN = None        # run_composio_tool — ตั้งจากภายนอกได้ (workbench) · ไม่ตั้ง = ใช้ mcp.py
# อ่านอย่างเดียวเท่านั้น: เรียกได้แค่ 3 คำสั่งนี้ — คำสั่งอื่น (แก้/สร้าง/ลบ ชีต ไฟล์ โฟลเดอร์ ลิงก์) ถูกปฏิเสธในโค้ด
READ_ONLY = frozenset(('GOOGLEDRIVE_FIND_FILE', 'GOOGLEDRIVE_DOWNLOAD_FILE', 'GOOGLESHEETS_BATCH_GET'))


# ---------- Composio ----------
def call(slug, args, account):
    global RUN
    if slug not in READ_ONLY:
        raise RuntimeError('ไม่อนุญาต: %s (งานนี้อ่านอย่างเดียว)' % slug)
    if RUN is None:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from mcp import run_composio_tool
        RUN = run_composio_tool
    r, e = RUN(slug, args, account=account)
    if e:
        raise RuntimeError('%s ไม่สำเร็จ: %s' % (slug, str(e)[:120]))
    d = (r or {}).get('data') or {}
    return json.loads(json.dumps(d))     # SmartDict → dict ธรรมดา


def drive_list(q, fields):
    out, tok = [], None
    while True:
        a = {'q': q, 'fields': 'nextPageToken,files(%s)' % fields, 'pageSize': 200}
        if tok:
            a['pageToken'] = tok
        d = call('GOOGLEDRIVE_FIND_FILE', a, DRIVE)
        out += d.get('files') or []
        tok = d.get('nextPageToken')
        if not tok:
            return out


def drive_json(fid):
    import requests
    d = call('GOOGLEDRIVE_DOWNLOAD_FILE', {'fileId': fid}, DRIVE)
    c = d.get('downloaded_file_content') or {}
    url = c.get('s3url') if isinstance(c, dict) else None
    if not url:
        raise RuntimeError('ดาวน์โหลดไฟล์ JSON ไม่ได้')
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    r.encoding = 'utf-8'
    return json.loads(r.text)


# ---------- เวลา / รูปแบบ ----------
def parse_iso(s):
    try:
        t = dt.datetime.fromisoformat((s or '').replace('Z', '+00:00'))
        return t if t.tzinfo else t.replace(tzinfo=TH)
    except Exception:
        return None


def hms(sec):
    s = int(round(max(0, sec or 0)))
    h, m = divmod(s, 3600)
    m, s = divmod(m, 60)
    return '%d:%02d:%02d' % (h, m, s) if h else '%d:%02d' % (m, s)


def span(sec):
    """ระยะเวลาแบบคนอ่าน: 45 นาที / 21 ชม. / 2 วัน 1 ชม."""
    m = int(round(max(0, sec) / 60))
    if m < 60:
        return '%d นาที' % m
    h = int(round(m / 60))
    if h < 24:
        return '%d ชม.' % h
    d, h = divmod(h, 24)
    return '%d วัน%s' % (d, (' %d ชม.' % h) if h else '')


def thday(d, year=False):
    return '%s %d %s%s' % (TH_D[d.weekday()], d.day, TH_M[d.month - 1], (' %d' % d.year) if year else '')


def thtime(t):
    t = t.astimezone(TH)
    return '%s %s น.' % (thday(t.date()), t.strftime('%H:%M'))


def clip_label(name):
    m = CLIP_RE.match(name or '')
    if not m:
        return re.sub(r'\.mov$', '', name or '', flags=re.I)
    return '%s-%s %s.%s%s' % (m[1], m[2], m[4], m[5], (' ตอน ' + m[6]) if m[6] else '')


def clip_key(name):
    m = CLIP_RE.match(name or '')
    return (m[3], m[2], m[1], m[4], m[5], int(m[6] or 0)) if m else ('9999', name)


def link(fid):
    return 'https://drive.google.com/file/d/%s/view' % fid


def clusters(times, gap=60.0):
    """เวลาจุดปิดเสียง (วินาทีในไฟล์ตัด) → ช่วงที่อยู่ใกล้กัน [(เริ่ม, จบ, จำนวน)]"""
    out = []
    for t in sorted(times):
        if out and t - out[-1][1] <= gap:
            out[-1][1] = t
            out[-1][2] += 1
        else:
            out.append([t, t, 1])
    return out


def mute_text(times):
    if not times:
        return '🔇 ปิดเสียง 0 จุด'
    cl = clusters(times)
    parts = []
    for a, b, n in cl[:MAX_CLUSTERS]:
        if n == 1:
            parts.append(hms(a))
        elif b - a < 1:
            parts.append('%s (%d)' % (hms(a), n))
        else:
            parts.append('%s–%s (%d)' % (hms(a), hms(b), n))
    more = len(cl) - MAX_CLUSTERS
    return '🔇 ปิดเสียง %d จุด: %s%s' % (len(times), ' · '.join(parts), (' · …อีก %d ช่วง' % more) if more > 0 else '')


def next_round(t, rounds):
    t = t.astimezone(TH)
    for add in range(0, 4):
        d = t.date() + dt.timedelta(days=add)
        for h, m in rounds:
            x = dt.datetime(d.year, d.month, d.day, h, m, tzinfo=TH)
            if x > t:
                return x
    return t


# ---------- 1) สแกน «ต้นฉับบ» ----------
def stage(p):
    cs, ts = p.get('bp_cut_state'), p.get('bp_transcript_state')
    if cs == 'done' and p.get('bp_edit_id'):
        return 'done'
    if cs == 'qa_failed':
        return 'qa'
    if cs == 'gave_up' or ts == 'gave_up':
        return 'stuck'
    if ts == 'skipped':
        return 'skip'
    if p.get('bp_cutlist'):
        return 'cut'
    if p.get('bp_pack') or p.get('bp_decisions') or ts in ('await_ai', 'decided', 'failed'):
        return 'tr'
    if p.get('bp_youtube_id'):
        return 'tr' if p.get('bp_yt_captions') == 'ready' else 'yt'
    return 'up'


def scan():
    folders = drive_list("'%s' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false" % ORIG, 'id,name')
    days, tomb_id = [], None
    for fo in folders:
        m = DATE_RE.match(fo.get('name') or '')
        if m:
            days.append((dt.date(int(m[3]), int(m[2]), int(m[1])), fo['id']))
        elif fo.get('name') == TOMB:
            tomb_id = fo['id']

    def one(x):
        d, fid = x
        fs = drive_list("'%s' in parents and trashed = false and mimeType contains 'video/'" % fid,
                        'id,name,createdTime,properties,videoMediaMetadata(durationMillis)')
        return [(d, f) for f in fs]

    clips = []
    with ThreadPoolExecutor(3) as ex:
        for rows in ex.map(one, days):
            for d, f in rows:
                p = f.get('properties') or {}
                ms = int(((f.get('videoMediaMetadata') or {}).get('durationMillis')) or -1)
                if 0 <= ms < 60000:
                    continue                                    # สั้นกว่า 1 นาที = กดอัดผิด
                st = stage(p)
                if d < PIPE_START and st in ('up', 'yt'):
                    continue                                    # ก่อนเริ่ม pipeline
                clips.append({'id': f['id'], 'name': f.get('name') or '', 'day': d, 'p': p, 'stage': st,
                              'dur': ms / 1000.0 if ms > 0 else None, 'created': parse_iso(f.get('createdTime'))})
    # เวลาเรียนจบโดยประมาณ = เวลาในชื่อไฟล์ + ความยาวตอนนี้และตอนก่อนหน้า (คลิปที่ถูกแบ่งหลายตอน)
    by = {}
    for c in clips:
        m = CLIP_RE.match(c['name'])
        if m:
            by.setdefault(m.groups()[:5], []).append((int(m[6] or 0), c))
    for k, parts in by.items():
        m = CLIP_RE.match(parts[0][1]['name'])
        start = dt.datetime(int(m[3]), int(m[2]), int(m[1]), int(m[4]), int(m[5]), tzinfo=TH)
        acc = 0.0
        for n, c in sorted(parts, key=lambda x: x[0]):
            acc += c['dur'] or 0
            c['end'] = start + dt.timedelta(seconds=acc)
    tombs = []
    if tomb_id:
        for f in drive_list("'%s' in parents and trashed = false" % tomb_id, 'id,name'):
            m = CLIP_RE.match(f.get('name') or '')
            if m:
                tombs.append(dt.date(int(m[3]), int(m[2]), int(m[1])))
    return clips, tombs


# ---------- 2) ชีต: คอร์สจากวันที่ + เวลา ----------
def sheet_courses():
    courses = []
    for title in TABS:
        rows, r1, step = [], 1, 40
        while r1 < 1500:
            try:     # ค่าในช่องอย่างเดียว (ก้อนเล็ก) · คำตอบใหญ่เกินที่ MCP ส่งได้ = ลดจำนวนแถวต่อครั้ง
                d = call('GOOGLESHEETS_BATCH_GET', {
                    'spreadsheet_id': SHEET, 'ranges': ["'%s'!A%d:CZ%d" % (title, r1, r1 + step - 1)],
                    'valueRenderOption': 'FORMATTED_VALUE', 'dateTimeRenderOption': 'FORMATTED_STRING'}, SHEETS)
            except RuntimeError:
                if step > 10:
                    step //= 2
                    continue
                raise
            blk = [[str(v) for v in r] for r in (((d.get('valueRanges') or [{}])[0]).get('values') or [])]
            rows += blk + [[]] * (step - len(blk))
            if not any(blk):
                break
            r1 += step
        hi = next((i for i, r in enumerate(rows[:8]) if 'Folder Name' in [c.strip() for c in r]), None)
        if hi is None:
            raise RuntimeError('แท็บ %s: หาแถวหัวตารางไม่เจอ' % title)
        hdr = [c.strip() for c in rows[hi]]
        ix = {h: i for i, h in enumerate(hdr) if h}
        first_date = max(ix.values()) + 1
        for r in rows[hi + 1:]:
            g = lambda k: r[ix[k]] if k in ix and ix[k] < len(r) else ''
            if 'deleted' in (r[0] if r else '').lower() and hdr[0] == 'Loaded':
                continue
            codes = sorted(set(re.findall(r'G\d{3}', g('Line Group code') + ' ' + g('Folder Name'))))
            if not codes:
                continue
            dates = set()
            for c in r[first_date:]:
                m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})', c or '')
                if m:
                    dates.add(dt.date(int(m[3]), int(m[2]), int(m[1])))
            starts = [int(a) * 60 + int(b) for a, b in TIME_RE.findall(g('เวลา'))]
            name = ' '.join(g('Course Name').split())
            courses.append({'code': codes[0], 'name': name, 'dates': dates, 'starts': starts})
    return courses


def match_course(courses, name, day):
    m = CLIP_RE.match(name or '')
    if not m or not courses:
        return None
    t = int(m[4]) * 60 + int(m[5])
    cand = [c for c in courses if day in c['dates']]
    best, gap = None, None
    for c in cand:
        for s in c['starts']:
            g = abs(t - s)
            if gap is None or g < gap:
                best, gap = c, g
    if best is not None and gap <= 45:
        return best
    if len(cand) == 1 and not cand[0]['starts']:
        return cand[0]
    return None


def course_text(c):
    if not c:
        return '📚 ยังระบุคอร์สไม่ได้ (ดูจากวันเวลาในชีตไม่เจอ)'
    return '📚 %s %s' % (c['code'], c['name']) if c['name'] else '📚 ' + c['code']


# ---------- 3) รายละเอียดคลิป ----------
def qa_reason(cr, o, mode):
    q = o.get('qa') or {}
    why = []
    if q.get('mute_ok') is False:
        items = sorted(cr.get('mute') or [], key=lambda x: x.get('mute_start') or 0)
        loud = []
        for r, db in zip(cr.get('mute_ranges') or [], q.get('mute_db') or []):
            if db is not None and db > -60:
                it = next((x for x in items if r[0] - 0.05 <= (x.get('mute_start') or -1) <= r[1]), None)
                t = it.get('out_start_' + mode) if it else None
                loud.append('%s (%.0f dB)' % (hms(t), db) if t is not None else '%.0f dB' % db)
        why.append('จุดปิดเสียง %s ยังได้ยินเสียง' % ', '.join(loud[:4]) if loud else 'มีจุดปิดเสียงที่ยังไม่เงียบ')
    if q.get('dur_ok') is False:
        why.append('ความยาวไฟล์ไม่ตรงที่คำนวณ')
    if q.get('sync_ok') is False:
        why.append('เสียงกับภาพไม่ตรงกัน')
    if q.get('decode_errors_first60s'):
        why.append('ไฟล์มี error ช่วงต้น')
    return ' · '.join(why) or 'ไม่ผ่านการตรวจอัตโนมัติ'


def detail(c):
    p = c['p']
    cr = drive_json(p['bp_cutresult'])
    topic = ''
    if p.get('bp_decisions'):
        try:
            topic = (drive_json(p['bp_decisions']).get('topic') or '').strip()
        except Exception:
            topic = ''
    outs = cr.get('outputs') or []
    o = next((x for x in outs if x.get('file_id') and x.get('file_id') == p.get('bp_edit_id')), None) or (outs[-1] if outs else {})
    mode = o.get('mode') or p.get('bp_edit_mode') or 'copy'
    times = [m.get('out_start_' + mode) for m in (cr.get('mute') or []) if m.get('out_start_' + mode) is not None]
    return {'topic': topic, 'src': cr.get('source_duration') or 0, 'out': (o.get('qa') or {}).get('duration') or 0,
            'cut_s': o.get('cut_s') or 0, 'n_cut': o.get('n_cut') or 0, 'mutes': times,
            'file': p.get('bp_edit_id') or o.get('file_id'), 'at': parse_iso(cr.get('at')),
            'why': qa_reason(cr, o, mode) if c['stage'] == 'qa' else ''}


def pack_hours(clips, now):
    """ค่ากลางจริง: คลิปเข้า Drive → พร้อมถอดคำหยาบ (bp_pack_at) ของคลิป 14 วันล่าสุด"""
    v = [(parse_iso(c['p'].get('bp_pack_at')) - c['created']).total_seconds() / 3600 for c in clips
         if c['created'] and parse_iso(c['p'].get('bp_pack_at')) and (now.date() - c['day']).days <= 14]
    v = [x for x in v if 0 <= x <= 96]
    return statistics.median(v) if len(v) >= 3 else PACK_H_DEFAULT


def eta(c, now, pack_h):
    if c['stage'] == 'cut':
        return next_round(now, CUT_ROUNDS)
    if c['stage'] == 'tr':
        return next_round(now, ROUNDS)
    base = (c['created'] or now) + dt.timedelta(hours=pack_h)
    return next_round(max(now, base), ROUNDS)


def week_of(today):
    mon = today - dt.timedelta(days=today.weekday())
    if today.weekday() == 0:
        return mon - dt.timedelta(days=7), mon - dt.timedelta(days=1), True     # วันจันทร์ = ปิดรอบสัปดาห์ก่อน
    return mon, mon + dt.timedelta(days=6), False


def collect(since, until):
    clips, tombs = scan()
    new = [c for c in clips if c['stage'] == 'done' and since <= (parse_iso(c['p'].get('bp_edit_at')) or until) < until]
    qa = [c for c in clips if c['stage'] == 'qa' and c['p'].get('bp_cutresult')]
    show = new + qa
    with ThreadPoolExecutor(3) as ex:
        dets = list(ex.map(detail, show))
    for c, d in zip(show, dets):
        c['d'] = d
    courses = sheet_courses() if show else []
    for c in show:
        c['course'] = match_course(courses, c['name'], c['day'])
    pack_h = pack_hours(clips, until)
    queue = [c for c in clips if c['stage'] in ('up', 'yt', 'tr', 'cut')]
    for c in queue:
        c['eta'] = eta(c, until, pack_h)
    a, b, closing = week_of(until.date())
    wk = [c for c in clips if a <= c['day'] <= b and c['stage'] != 'skip']
    W = {'a': a, 'b': b, 'closing': closing, 'tomb': sum(1 for d in tombs if a <= d <= b),
         'done': [c for c in wk if c['stage'] == 'done'], 'wait': [c for c in wk if c['stage'] in ('up', 'yt', 'tr', 'cut')],
         'qa': [c for c in wk if c['stage'] == 'qa'], 'stuck': [c for c in wk if c['stage'] == 'stuck']}
    W['all'] = len(wk) + W['tomb']
    W['lag'] = [(parse_iso(c['p'].get('bp_edit_at')) - c['end']).total_seconds() for c in W['done']
                if c.get('end') and parse_iso(c['p'].get('bp_edit_at'))]
    key = lambda c: clip_key(c['name'])
    return {'new': sorted(new, key=key), 'qa': sorted(qa, key=key),
            'stuck': sorted([c for c in clips if c['stage'] == 'stuck'], key=key),
            'queue': sorted(queue, key=key), 'week': W, 'pack_h': pack_h, 'since': since, 'until': until}


# ---------- 4) ข้อความ ----------
def week_lines(W):
    rng = '%s – %s' % (thday(W['a']), thday(W['b']))
    head = ('📊 ปิดรอบสัปดาห์ %s' if W['closing'] else '📊 สัปดาห์นี้ %s') % rng
    done = len(W['done']) + W['tomb']
    L = [head + ' (นับตามวันเรียน)',
         'คลิปเข้า %d · ตัดเสร็จ %d · รอตัด %d%s%s' % (
             W['all'], done, len(W['wait']),
             (' · QA ไม่ผ่าน %d' % len(W['qa'])) if W['qa'] else '',
             (' · หยุดลอง %d' % len(W['stuck'])) if W['stuck'] else '')]
    if len(W['lag']) >= 2:
        L.append('⌛ ตัดเสร็จหลังเรียนจบ เฉลี่ย %s (เร็วสุด %s · ช้าสุด %s)' % (
            span(statistics.median(W['lag'])), span(min(W['lag'])), span(max(W['lag']))))
    elif W['lag']:
        L.append('⌛ ตัดเสร็จหลังเรียนจบ %s' % span(W['lag'][0]))
    return L


def build(D, today):
    now = D['until']
    head = ['🎬 คลิปเทปบันทึกการสอน · ตัดเสร็จ', '(ปิดเสียงคำหยาบ + ตัด dead air)',
            '📅 %s' % thday(today, True), '',
            '✅ ตัดเสร็จวันนี้ = %d คลิป' % len(D['new']),
            '(ตั้งแต่ %s)' % thtime(D['since']), ''] + week_lines(D['week'])
    blocks = []
    for i, c in enumerate(D['new'], 1):
        d = c['d']
        b = ['%d) %s' % (i, clip_label(c['name'])), course_text(c['course'])]
        if d['topic']:
            b.append('📝 ' + d['topic'])
        b.append('⏱ %s → %s (ตัด dead air %s · %d ช่วง)' % (hms(d['src']), hms(d['out']), hms(d['cut_s']), d['n_cut']))
        b.append(mute_text(d['mutes']))
        at = parse_iso(c['p'].get('bp_edit_at'))
        if at and c.get('end'):
            b.append('⌛ เสร็จหลังเรียนจบ %s' % span((at - c['end']).total_seconds()))
        b.append('▶️ ' + link(d['file']))
        blocks.append('\n'.join(b))
    tail = []
    q = D['queue']
    tail.append('⏳ รอตัด = %d คลิป' % len(q))
    if q:
        for c in q[:MAX_QUEUE_LINES]:
            waited = (now - c['end']).total_seconds() if c.get('end') else None
            late = waited is not None and waited > STALE_DAYS * 86400
            tail.append('%s %s · %s%s' % ('⚠️' if late else '•', clip_label(c['name']), STAGE_TXT[c['stage']],
                                          (' · รอมาแล้ว ' + span(waited)) if waited is not None and waited > 0 else ''))
            tail.append('   → คาดเสร็จ %s (อีก ~%s)' % (thtime(c['eta']), span((c['eta'] - now).total_seconds())))
        if len(q) > MAX_QUEUE_LINES:
            tail.append('…อีก %d คลิป' % (len(q) - MAX_QUEUE_LINES))
    tail.append('')
    if D['qa']:
        tail.append('⚠️ QA ไม่ผ่าน = %d คลิป' % len(D['qa']))
        tail.append('(ระบบตรวจไฟล์ตัดอัตโนมัติไม่ผ่าน · จะไม่ตัดซ้ำเอง ต้องมีคนดู)')
        for c in D['qa']:
            d = c['d']
            fresh = d['at'] and D['since'] <= d['at'] < D['until']
            tail.append('• %s%s · เรียน %s%s' % (clip_label(c['name']), ' 🆕' if fresh else '', thday(c['day']),
                                                (' · ตัด %s · รอคนดูมา %s' % (thday(d['at'].astimezone(TH).date()), span((now - d['at']).total_seconds())))
                                                if d['at'] else ''))
            tail.append('  สาเหตุ: ' + d['why'])
            if d['file']:
                tail.append('  ▶️ ' + link(d['file']))
    else:
        tail.append('⚠️ QA ไม่ผ่าน = 0')
    if D['stuck']:
        tail.append('🛑 ระบบหยุดลองแล้ว ต้องมีคนดู = %d' % len(D['stuck']))
        for c in D['stuck']:
            tail.append('• %s · เรียน %s' % (clip_label(c['name']), thday(c['day'])))
    foot = ['ℹ️ ไฟล์ตัดอยู่ใน «edit แล้ว» · ลิงก์ใช้ได้จนถึงรอบเคลียร์วันจันทร์ (หลังวางคลิปในคอร์สแล้ว)',
            '⌛ เวลาคาดเสร็จประมาณจากรอบถอดคำหยาบ 09:13 / 15:13 / 20:13 และเวลาจริงย้อนหลัง']
    return pack(head, blocks, tail, foot)


def pack(head, blocks, tail, foot, limit=4800, max_bubbles=5):
    """รวมเป็นบับเบิล (ข้อความละ ≤ 5,000 ตัวอักษร · ส่งครั้งเดียวได้ 5 บับเบิล = นับโควตา 1 ครั้ง)"""
    end = '\n'.join([BAR] + tail + [BAR] + foot)
    parts, cur = [], '\n'.join(head)
    for i, b in enumerate(blocks):
        piece = '\n' + BAR + '\n' + b if i == 0 else '\n\n' + b
        if len(cur) + len(piece) > limit:
            parts.append(cur)
            cur = '(ต่อ)\n' + b
        else:
            cur += piece
    if len(cur) + len(end) + 1 > limit:
        parts.append(cur)
        cur = end
    else:
        cur += '\n' + end
    parts.append(cur)
    if len(parts) > max_bubbles:
        parts = parts[:max_bubbles - 1] + ['…ข้อความยาวเกิน ดูไฟล์ที่เหลือใน «edit แล้ว»\n' + end]
    return parts


# ---------- 5) GitHub: เวลาที่ส่งสำเร็จครั้งก่อน ----------
def last_sent(now):
    import requests
    tok, repo, me = os.environ.get('GITHUB_TOKEN'), os.environ.get('GITHUB_REPOSITORY'), os.environ.get('GITHUB_RUN_ID', '')
    if tok and repo:
        r = requests.get('https://api.github.com/repos/%s/actions/workflows/%s/runs' % (repo, WF_FILE), timeout=30,
                         params={'status': 'success', 'per_page': 30},
                         headers={'Authorization': 'Bearer ' + tok, 'Accept': 'application/vnd.github+json'})
        if r.status_code == 200:
            for x in r.json().get('workflow_runs') or []:
                if str(x.get('id')) == me or 'ทดลอง' in (x.get('display_title') or ''):
                    continue
                t = parse_iso(x.get('run_started_at'))
                if t and t < now:
                    return t, 'รอบส่งก่อนหน้า'
        else:
            print('อ่านประวัติรันไม่ได้ HTTP %d — ใช้ 24 ชม. ล่าสุด' % r.status_code)
    return now - dt.timedelta(hours=24), '24 ชม. ล่าสุด'


# ---------- 6) LINE ----------
def line(method, path, token, body=None, retry_key=None):
    h = {'Authorization': 'Bearer ' + token}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h['Content-Type'] = 'application/json'
    if retry_key:
        h['X-Line-Retry-Key'] = retry_key
    req = urllib.request.Request('https://api.line.me' + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode('utf-8', 'replace')
            return r.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as e:
        return e.code, {'_err': e.read().decode('utf-8', 'replace')[:200]}


def tracking_left(today):
    """จำนวนรอบ Tracking (จันทร์/ศุกร์) ที่เหลือในเดือนนี้ นับวันนี้ด้วย"""
    last = calendar.monthrange(today.year, today.month)[1]
    return sum(1 for d in range(today.day, last + 1) if dt.date(today.year, today.month, d).weekday() in (0, 4))


def quota_ok(token, to, today):
    s1, q = line('GET', '/v2/bot/message/quota', token)
    s2, u = line('GET', '/v2/bot/message/quota/consumption', token)
    s3, m = line('GET', '/v2/bot/group/%s/members/count' % to, token)
    if s1 != 200 or s2 != 200 or s3 != 200:
        print('อ่านโควตา LINE ไม่ได้ (HTTP %s/%s/%s) — ไม่ส่ง กันโควตา Tracking' % (s1, s2, s3))
        return False
    if q.get('type') != 'limited':
        print('โควตา LINE: ไม่จำกัด')
        return True
    total, used, members = int(q.get('value') or 0), int(u.get('totalUsage') or 0), int(m.get('count') or 0)
    reserve = tracking_left(today) * members
    left = total - used - members
    print('โควตา LINE เดือนนี้: ใช้ %d/%d · สมาชิกกลุ่ม %d · กันไว้ให้ Tracking %d · หลังส่งเหลือ %d' % (used, total, members, reserve, left))
    return left >= reserve


def main():
    now = dt.datetime.now(TH)
    today = now.date()
    send = (os.environ.get('SEND') or '').strip() == '1'
    auto = (os.environ.get('AUTO') or '').strip() == '1'
    if not ORIG or not SHEET:
        raise SystemExit('ยังไม่ได้ตั้ง secret CLIP_ORIG_ID / CLIP_SHEET_ID')
    since = parse_iso(os.environ.get('SINCE') or '')
    src = 'กำหนดเอง'
    if not since:
        since, src = last_sent(now)
    D = collect(since, now)
    texts = build(D, today)
    W = D['week']
    # repo public → พิมพ์แค่จำนวน
    print('ช่วงนับ: %s (%.1f ชม.) · ตัดเสร็จใหม่ %d · QA ไม่ผ่าน %d · หยุดลอง %d · รอตัด %d · สัปดาห์: เข้า %d เสร็จ %d รอ %d · %d บับเบิล %d ตัวอักษร' % (
        src, (now - since).total_seconds() / 3600, len(D['new']), len(D['qa']), len(D['stuck']), len(D['queue']),
        W['all'], len(W['done']) + W['tomb'], len(W['wait']), len(texts), sum(len(t) for t in texts)))
    if not send:
        print('ทดลอง — ไม่ส่ง')
        return
    token = (os.environ.get('LINE_NOTICE_TOKEN') or '').strip()
    to = (os.environ.get('LINE_NOTICE_TO_2') or '').strip()
    if not token or not to:
        raise SystemExit('ยังไม่ได้ตั้ง LINE_NOTICE_TOKEN / LINE_NOTICE_TO_2')
    if not quota_ok(token, to, today):
        raise SystemExit('โควตา LINE ไม่พอ — ไม่ส่งแจ้งเตือนคลิปรอบนี้ (กันไว้ให้ Tracking) · คลิปจะรวมไปรอบถัดไป')
    rk = str(uuid.uuid5(uuid.NAMESPACE_URL, 'biopalm-clip-notice/%s/%s' % (today.isoformat(), to))) if auto else str(uuid.uuid4())
    code, err = line('POST', '/v2/bot/message/push', token,
                     {'to': to, 'messages': [{'type': 'text', 'text': t[:5000]} for t in texts[:5]]}, rk)
    if code == 200:
        print('ส่งเข้ากลุ่ม Admin dashboard แล้ว (%d บับเบิล)' % len(texts))
    elif code == 409:
        print('วันนี้ส่งแจ้งเตือนคลิปไปแล้ว — ไม่ส่งซ้ำ')
    else:
        raise SystemExit('ส่งไม่สำเร็จ HTTP %s' % code)


if __name__ == '__main__':
    main()

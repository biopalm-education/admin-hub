# -*- coding: utf-8 -*-
"""สร้างโน้ต Obsidian (Biopalm Insight) จากชีต Meta Ads + chat log แล้ว commit ลง repo private biopalm-insight

รันใน GitHub Actions (obsidian-vault.yml) — repo admin-hub เป็น public:
  * อ่านชีตอย่างเดียว ผ่าน Composio (tools/meta_ads/composio_shim.py ตัวเดิม · secret COMPOSIO_API_KEY เดิม)
  * เขียนเฉพาะ repo private biopalm-insight ผ่าน Composio GitHub (บัญชีเดิม) — ไม่ต้องตั้ง secret เพิ่ม
    (ถ้า VAULT_DIR เป็น git clone อยู่แล้ว จะเขียนไฟล์ลงโฟลเดอร์แทน ให้ workflow push เอง)
  * log พิมพ์แค่จำนวน/สถานะ ห้ามพิมพ์ชื่อหรือข้อความลูกค้า ห้ามพิมพ์คำตอบดิบจาก GitHub (มี token ในลิงก์)

ระบบเขียนทับทุกรอบ: Ads/  Monthly/  Sources/  Chats/FB/<เดือนที่ประมวลผล>/  .vault/  "05 สถานะระบบ.md"
โน้ต Monthly/ มีส่วนคอนเทนต์ FB/IG/TikTok/YouTube + ค่าแอด TikTok/Google Ads จาก .vault/content/monthly.json (งาน obsidian-content เขียน · ที่นี่อ่านอย่างเดียว)
สร้างให้ครั้งแรกถ้ายังไม่มี (แล้วไม่แตะอีก): Config/, Topics/, Templates/, Bases/, บันทึกของฉัน/
ไม่แตะเลย: เอกสาร 00-04 และไฟล์อื่นที่ผู้ใช้สร้าง
"""
import os, sys, re, json, time, shutil, statistics, hashlib, base64, tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
if os.environ.get('VAULT_MOCK'):
    sys.path.insert(0, os.environ['VAULT_MOCK'])
    from mock_composio import run_composio_tool          # ทดสอบในเครื่อง
else:
    sys.path.insert(0, os.path.join(HERE, '..', 'meta_ads'))
    from composio_shim import run_composio_tool

import yaml

VAULT_REPO = os.environ.get('VAULT_REPO') or 'biopalm-education/biopalm-insight'
OWNER, REPO = VAULT_REPO.split('/')
BRANCH = os.environ.get('VAULT_BRANCH') or 'main'
VAULT = os.path.abspath(os.environ.get('VAULT_DIR') or tempfile.mkdtemp(prefix='vault-'))
os.makedirs(VAULT, exist_ok=True)
MODE = 'git' if os.path.isdir(os.path.join(VAULT, '.git')) else 'api'
DRY_RUN = (os.environ.get('DRY_RUN') or '').strip().lower() in ('1', 'true', 'yes')
BKK = ZoneInfo('Asia/Bangkok')
LA = ZoneInfo('America/Los_Angeles')
NOW = datetime.now(BKK)
KEEP_CHAT_MONTHS = int(os.environ.get('KEEP_CHAT_MONTHS') or 3)
NOTE_STAGES = tuple((os.environ.get('FB_NOTE_STAGES') or 'S2,S3,S4,S5').split(','))
TH_ABBR = ['', 'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']
TH_FULL = ['', 'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน', 'กรกฎาคม', 'สิงหาคม',
           'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม']
STATUS = {'started': NOW.strftime('%Y-%m-%d %H:%M'), 'steps': [], 'warnings': []}


def log(*a):
    print(*a, flush=True)


def warn(msg):
    STATUS['warnings'].append(msg)
    log('  ! ' + msg)


class ToolError(Exception):
    pass


STATS = Counter()
_QUOTA = re.compile(r'429|quota exceeded|rate.?limit|too many requests|resource.?exhausted', re.I)


def call(slug, args):
    """เรียก Composio · ติดโควตา Google Sheets (โปรเจกต์ของ Composio ใช้ร่วมกันทุกคน จำกัดต่อนาที) → พักแล้วลองใหม่"""
    err = ''
    for attempt in range(8):
        res, err = run_composio_tool(slug, args)
        if not err:
            STATS['calls'] += 1
            return (res or {}).get('data') or {}
        err = str(err)
        if 'TOO_LARGE' in err or attempt == 7:
            break
        if _QUOTA.search(err):
            STATS['quota_waits'] += 1
            time.sleep(40 + 20 * attempt)
            continue
        if attempt >= 1:
            break
        STATS['retries'] += 1
        time.sleep(30)
    raise ToolError('%s: %s' % (slug, err[:160]))


# ---------------------------------------------------------------- Google Sheets
def col_letter(n):
    s = ''
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def batch_get(sid, ranges):
    d = call('GOOGLESHEETS_BATCH_GET', {'spreadsheet_id': sid, 'ranges': ranges})
    vrs = d.get('valueRanges') or []
    out = [vr.get('values') or [] for vr in vrs]
    while len(out) < len(ranges):
        out.append([])
    return out


def tabs_of(sid):
    d = call('GOOGLESHEETS_GET_SPREADSHEET_INFO', {
        'spreadsheet_id': sid, 'fields': 'sheets.properties(title,gridProperties(rowCount,columnCount))'})
    out = {}
    for s in d.get('sheets') or []:
        p = s.get('properties') or {}
        g = p.get('gridProperties') or {}
        out[p.get('title')] = (int(g.get('rowCount') or 0), int(g.get('columnCount') or 26))
    return out


def read_window(sid, tab, r1, r2, c1, c2):
    return batch_get(sid, ["'%s'!%s%d:%s%d" % (tab, c1, r1, c2, r2)])[0]


def read_cols(sid, tab, first, last, idxs, chunk, max_chunk=None):
    """อ่านเฉพาะคอลัมน์ idxs (เลขคอลัมน์เริ่ม 1) แถว first..last — 1 คำขอต่อช่วงแถว อ่านทีละช่วงตามลำดับ
    คำตอบใหญ่เกิน (TOO_LARGE) → ลดขนาดช่วงลงครึ่งหนึ่งแล้วใช้ขนาดนั้นต่อ · ผ่านติดกัน 3 ครั้ง → ค่อย ๆ เพิ่มกลับ
    (ไม่เกินขนาดที่เคยใหญ่เกินมาแล้ว)"""
    idxs = sorted(set(idxs))
    runs = []
    for i in idxs:
        if runs and i == runs[-1][1] + 1:
            runs[-1][1] = i
        else:
            runs.append([i, i])
    cap = max_chunk or chunk * 2
    out = {i: [] for i in idxs}
    r, size, streak = first, chunk, 0
    while r <= last:
        b = min(last, r + size - 1)
        try:
            parts = batch_get(sid, ["'%s'!%s%d:%s%d" % (tab, col_letter(a), r, col_letter(z), b) for a, z in runs])
        except ToolError as e:
            if 'TOO_LARGE' in str(e) and b > r:
                cap = min(cap, b - r)
                size, streak = max(1, (b - r + 1) // 2), 0
                STATS['shrink'] += 1
                continue
            raise
        n = b - r + 1
        for (a, z), p in zip(runs, parts):
            p = list(p)[:n] + [[]] * (n - len(p))        # แถวว่างท้ายช่วงถูกตัดทิ้ง → เติมให้ตรงตำแหน่ง
            for row in p:
                for i in range(a, z + 1):
                    j = i - a
                    out[i].append(row[j] if j < len(row) else '')
        r = b + 1
        streak += 1
        if streak >= 3 and size < cap:
            size, streak = min(cap, size * 3 // 2 + 1), 0
    return out


def find_header(sid, tab, tabinfo, match, head_scan=8):
    """หาแถวหัวตารางจากคอลัมน์ A (match = ข้อความหรือฟังก์ชัน) แล้วอ่านแถวหัวทั้งแถว"""
    if tab not in tabinfo:
        raise ToolError('ไม่พบแท็บ %s' % tab)
    ok = match if callable(match) else (lambda s: s == match)
    colA = read_window(sid, tab, 1, head_scan, 'A', 'A')
    hr = next((i + 1 for i, r in enumerate(colA) if r and ok(str(r[0]).strip())), None)
    if hr is None:
        raise ToolError('ไม่พบหัวตารางในแท็บ %s' % tab)
    head = read_window(sid, tab, hr, hr, 'A', col_letter(max(1, tabinfo[tab][1])))
    return hr, [str(h).strip() for h in (head[0] if head else [])]


def read_table(sid, tab, tabinfo, first_header, cols=None, heavy=(), chunk=500, heavy_chunk=40, head_scan=8):
    """อ่านตารางเฉพาะคอลัมน์ที่ใช้ (cols = ชื่อหัวคอลัมน์) · คอลัมน์ข้อความยาว (heavy) อ่านแยกทีละช่วงเล็ก"""
    hr, header = find_header(sid, tab, tabinfo, first_header, head_scan)
    nrows = tabinfo[tab][0]
    pos = {}
    for i, h in enumerate(header, 1):
        if h and h not in pos:
            pos[h] = i
    want = list(cols) if cols else [h for h in pos]
    missing = [c for c in want if c not in pos]
    if missing:
        warn('แท็บ %s ไม่มีคอลัมน์ %d รายการ: %s' % (tab, len(missing), ', '.join(missing)[:100]))
    names = [(c, pos[c]) for c in want if c in pos]
    light = [i for c, i in names if c not in heavy]
    data = {}
    if nrows > hr and names:
        if light:
            data.update(read_cols(sid, tab, hr + 1, nrows, light, chunk))
        for c, i in names:
            if c in heavy:
                data.update(read_cols(sid, tab, hr + 1, nrows, [i], heavy_chunk))
    out = []
    for k in range(max(0, nrows - hr)):
        d = {c: (data[i][k] if k < len(data.get(i, ())) else '') for c, i in names}
        if any(str(v).strip() for v in d.values()):
            for c in missing:
                d[c] = ''
            out.append(d)
    return header, out


def search_sheets(query):
    d = call('GOOGLESHEETS_SEARCH_SPREADSHEETS', {'query': query, 'search_type': 'name', 'max_results': 100})
    return [(s.get('name') or '', s.get('id'), s.get('modifiedTime') or '') for s in (d.get('spreadsheets') or [])]


def num(v):
    s = str(v if v is not None else '').replace(',', '').replace('%', '').replace('฿', '').strip()
    if s in ('', '-', '—'):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def norm(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


# ---------------------------------------------------------------- ชื่อ/กลุ่ม
def safe(s, n=90):
    s = str(s).replace('/', '-').replace('\\', '-').replace(':', ' ').replace('|', '-').replace('*', '')
    s = re.sub(r'[#^\[\]<>"?{}]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s[:n].rstrip(' .-')


def area_of(text):
    s = str(text).lower()
    prov = ('ต่าง' in s) or ('ตาง จว' in s)
    bkk = any(k in s for k in ('กทม', 'bkk', 'นนท', 'ปทุม'))
    if bkk and 'หาดใหญ่' in s:
        return 'กทม+หาดใหญ่'
    if prov and not bkk:
        return 'ต่างจังหวัด'
    if bkk:
        return 'กทม-ปริมณฑล'
    return 'ไม่ระบุ'


def course_of(n):
    for k in ('สอวน', 'ม.ปลาย', 'ม.ต้น', 'LAB', 'A-Level'):
        if k in n:
            return k
    return 'รวมทุกคอร์ส'


def platform_of(n):
    return 'IG' if 'IG' in str(n) else 'FB'


def yv(v):
    if v is None or v == '':
        return ''
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(round(v, 2)) if isinstance(v, float) else str(v)
    if isinstance(v, (list, tuple)):
        if not v:
            return '[]'
        return '\n' + '\n'.join('  - ' + json.dumps(str(i), ensure_ascii=False) for i in v)
    return json.dumps(str(v), ensure_ascii=False)


def front(d):
    return '---\n' + '\n'.join(('%s: %s' % (k, yv(v))).rstrip() for k, v in d.items()) + '\n---\n'


def fmt(x, d=0):
    try:
        return ('{:,.%df}' % d).format(x)
    except (TypeError, ValueError):
        return '-'


FILES = {}


def put(rel, text):
    FILES[rel] = text.strip('\n') + '\n'


# ---------------------------------------------------------------- Meta Ads
def load_meta():
    hits = [h for h in search_sheets('ข้อมูล Meta Ads') if h[0].startswith('ข้อมูล Meta Ads')]
    if not hits:
        raise ToolError('ไม่พบชีต ข้อมูล Meta Ads')
    hits.sort(key=lambda h: h[2], reverse=True)
    sid = os.environ.get('META_SHEET_ID') or hits[0][1]
    SOURCES['meta'] = [(next((h[0] for h in hits if h[1] == sid), 'Meta Ads'), sid)]
    T = tabs_of(sid)
    M = {}
    _, M['camps'] = read_table(sid, 'แคมเปญ', T, 'Campaign ID', cols=[
        'Campaign ID', 'ชื่อแคมเปญ', 'เป้าหมาย (objective)', 'สถานะจริง', 'วันเริ่ม (เวลาไทย)', 'วันจบ (เวลาไทย)',
        SPEND, CHATS, 'ลีด', BUYS, CPM], chunk=300)
    _, M['ads'] = read_table(sid, 'โฆษณาและครีเอทีฟ', T, 'Ad ID', cols=[
        'Ad ID', 'ชื่อโฆษณา', 'Ad set ID', 'ชื่อชุดโฆษณา', 'Campaign ID', 'ชื่อแคมเปญ', 'สถานะจริง', 'สร้างเมื่อ (เวลาไทย)',
        'ประเภทครีเอทีฟ', 'หัวข้อ (headline)', 'ปุ่ม CTA', 'ลิงก์ดูตัวอย่างโฆษณา', 'Quality ranking',
        SPEND, CHATS, 'ลีด', BUYS, PRIMARY], heavy=(PRIMARY,), chunk=300, heavy_chunk=40)
    _, M['welcome'] = read_table(sid, 'ข้อความต้อนรับแชทของโฆษณา', T, 'Ad ID', cols=[
        'Ad ID', 'ปลายทาง', 'วันแรกที่แสดงผล (เวลาบัญชี LA)', 'วันสุดท้ายที่แสดงผล (เวลาบัญชี LA)', W_TEXT, W_BTN,
        'ชื่อโฆษณา', 'Ad set ID', 'ชื่อชุดโฆษณา', 'Campaign ID', 'ชื่อแคมเปญ', 'สถานะจริง', 'สร้างเมื่อ (เวลาไทย)'],
        heavy=(W_TEXT, W_BTN), chunk=600, heavy_chunk=150)
    _, M['cmon'] = read_table(sid, 'แคมเปญรายเดือน', T, 'เดือน (เริ่ม)', cols=[
        'เดือน (เริ่ม)', 'Campaign ID', SPEND, CHATS, BUYS], chunk=1000)
    _, M['amon'] = read_table(sid, 'โฆษณารายเดือน', T, 'เดือน (เริ่ม)', cols=[
        'เดือน (เริ่ม)', 'Ad ID', SPEND, CHATS, BUYS, 'Campaign ID', 'ชื่อแคมเปญ', 'ลีด', IMPR], chunk=1500)
    _, acct = read_table(sid, 'บัญชีโฆษณา', T, 'เดือน (เริ่ม)', cols=[
        'เดือน (เริ่ม)', SPEND, CHATS, 'ลีด', BUYS, CPM], head_scan=40, chunk=100)
    M['acct'] = [r for r in acct if re.match(r'^\d{4}-\d{2}-\d{2}$', str(r.get('เดือน (เริ่ม)') or '').strip())]
    M['daily'] = load_daily(sid, T)
    fresh_meta(M)
    log('Meta: แคมเปญ %d · โฆษณา %d · ข้อความต้อนรับ %d · รายเดือน %d/%d · รายวัน %d แถว · คำขอ %d (ลดขนาด %d)' % (
        len(M['camps']), len(M['ads']), len(M['welcome']), len(M['cmon']), len(M['amon']), len(M['daily']),
        STATS['calls'], STATS['shrink']))
    return M


def load_daily(sid, T):
    tab = 'โฆษณารายวัน'
    try:
        hr, h = find_header(sid, tab, T, lambda s: s.startswith('วันที่'))
    except ToolError:
        warn('ไม่พบหัวตาราง โฆษณารายวัน — จับคู่แชทด้วยวันที่ไม่ได้')
        return {}
    try:
        ci_ad = h.index('Ad ID') + 1
        ci_ch = h.index(CHATS) + 1
    except ValueError:
        warn('คอลัมน์ Ad ID / เริ่มแชท ในแท็บโฆษณารายวันเปลี่ยนชื่อ')
        return {}
    cols = read_cols(sid, tab, hr + 1, T[tab][0], [1, ci_ad, ci_ch], 3000, 6000)
    out = {}
    for d, ad, ch in zip(cols[1], cols[ci_ad], cols[ci_ch]):
        d, ad, ch = str(d).strip(), str(ad).strip(), num(ch)
        if d and ad and ch:
            out[(d, ad)] = out.get((d, ad), 0) + ch
    return out


SPEND, CHATS, BUYS = 'Spend (ยอดใช้จ่าย บาท)', 'เริ่มแชท (7 วัน)', 'การซื้อ'
IMPR = 'Impressions (ครั้งที่แสดง)'


def fresh_meta(M):
    """แท็บรอบแรก (แคมเปญ · โฆษณาและครีเอทีฟ · แคมเปญรายเดือน · บัญชีโฆษณา) หยุดที่ 21 ต.ค. 2026
    ส่วนแท็บของงาน meta-ads-export (โฆษณารายเดือน · ข้อความต้อนรับ · โฆษณารายวัน) อัปเดตทุกคืนถึงเมื่อวานตามวัน LA
    → ยอดรวม/รายเดือนของบัญชี แคมเปญ และโฆษณา คิดใหม่จาก โฆษณารายเดือน (export ตรวจแล้วว่ารวมได้เท่าระดับบัญชี)
    → โฆษณา/แคมเปญที่ไม่มีในแท็บรอบแรก (สร้างหลัง 21 ต.ค.) เติมจากแท็บข้อความต้อนรับ ให้จับคู่แชทได้
    ค่าตั้ง (เป้าหมาย งบ ข้อความโฆษณา ฯลฯ) ยังมาจากแท็บรอบแรก · log พิมพ์แค่จำนวน"""
    amon = [r for r in M['amon'] if re.match(r'^\d{4}-\d{2}-\d{2}$', str(r.get('เดือน (เริ่ม)') or '').strip())]
    if not amon:
        warn('แท็บ โฆษณารายเดือน ว่าง — ใช้ยอดจากแท็บรอบแรก (ถึง 21 ต.ค. 2026)')
        return
    keys = (SPEND, CHATS, 'ลีด', BUYS, IMPR)
    by_ad, by_camp, by_cm, by_m = (defaultdict(lambda: dict.fromkeys(keys, 0.0)) for _ in range(4))
    cname = {}
    for r in amon:
        m = str(r.get('เดือน (เริ่ม)')).strip()
        aid, cid = str(r.get('Ad ID') or '').strip(), str(r.get('Campaign ID') or '').strip()
        if cid and str(r.get('ชื่อแคมเปญ') or '').strip():
            cname[cid] = str(r.get('ชื่อแคมเปญ')).strip()
        for k in keys:
            v = num(r.get(k))
            if aid:
                by_ad[aid][k] += v
            if cid:
                by_camp[cid][k] += v
                by_cm[(m, cid)][k] += v
            by_m[m][k] += v

    def cpm(d):
        return round(d[SPEND] * 1000 / d[IMPR], 2) if d[IMPR] else ''

    def put_tot(row, d):
        for k in (SPEND, CHATS, 'ลีด', BUYS):
            row[k] = round(d[k], 2)
    # โฆษณา: ยอดรวมใหม่ + โฆษณาที่ไม่มีในแท็บรอบแรก
    known = {str(r.get('Ad ID') or '').strip() for r in M['ads']}
    for r in M['ads']:
        aid = str(r.get('Ad ID') or '').strip()
        if aid in by_ad:
            put_tot(r, by_ad[aid])
    new_ads = 0
    for w in M['welcome']:
        aid = str(w.get('Ad ID') or '').strip()
        if not aid or aid in known:
            continue
        row = {k: w.get(k, '') for k in ('Ad ID', 'ชื่อโฆษณา', 'Ad set ID', 'ชื่อชุดโฆษณา', 'Campaign ID', 'ชื่อแคมเปญ',
                                       'สถานะจริง', 'สร้างเมื่อ (เวลาไทย)')}
        put_tot(row, by_ad.get(aid) or dict.fromkeys(keys, 0.0))
        M['ads'].append(row)
        known.add(aid)
        new_ads += 1
        cid = str(row.get('Campaign ID') or '').strip()
        if cid and str(row.get('ชื่อแคมเปญ') or '').strip():
            cname.setdefault(cid, str(row['ชื่อแคมเปญ']).strip())
    # แคมเปญ: ยอดรวมใหม่ + แคมเปญที่ไม่มีในแท็บรอบแรก
    kc = {str(r.get('Campaign ID') or '').strip() for r in M['camps']}
    for r in M['camps']:
        cid = str(r.get('Campaign ID') or '').strip()
        if cid in by_camp:
            put_tot(r, by_camp[cid])
            r[CPM] = cpm(by_camp[cid])
    new_camps = 0
    for cid, d in by_camp.items():
        if cid in kc or not d[SPEND]:
            continue
        row = {'Campaign ID': cid, 'ชื่อแคมเปญ': cname.get(cid, cid), CPM: cpm(d)}
        put_tot(row, d)
        M['camps'].append(row)
        new_camps += 1
    # รายเดือน: แทนเดือนที่มีใน โฆษณารายเดือน · เดือนอื่นคงของเดิม
    old = {(str(r.get('เดือน (เริ่ม)'))[:10], str(r.get('Campaign ID') or '').strip()): r for r in M['cmon']}
    for (m, cid), d in by_cm.items():
        row = old.setdefault((m, cid), {'เดือน (เริ่ม)': m, 'Campaign ID': cid})
        put_tot(row, d)
    M['cmon'] = list(old.values())
    acct = {str(r.get('เดือน (เริ่ม)'))[:7]: r for r in M['acct']}
    for m, d in by_m.items():
        row = acct.setdefault(m[:7], {'เดือน (เริ่ม)': m})
        put_tot(row, d)
        row[CPM] = cpm(d)
    M['acct'] = [acct[k] for k in sorted(acct)]
    last_day = max((d for d, _ in M.get('daily') or {}), default='')
    msg = 'Meta: ยอดรวม/รายเดือนคิดจากแท็บ โฆษณารายเดือน (%s ถึง %s) · ข้อมูลรายวันถึง %s (วัน LA) · เติมโฆษณาใหม่ %d · แคมเปญใหม่ %d' % (
        min(by_m)[:7], max(by_m)[:7], last_day or '-', new_ads, new_camps)
    STATUS['steps'].append(msg)
    log(msg)
CPM, PRIMARY = 'CPM (บาท/1,000 ครั้ง)', 'ข้อความหลัก (primary text)'
W_TEXT = 'ข้อความต้อนรับ (ข้อความแรกที่ลูกค้าเห็นในแชท)'
W_BTN = 'ปุ่มคำถาม / ตอบด่วน (→ คำตอบอัตโนมัติ)'


def build_ads_model(M):
    camps = {}
    for r in M['camps']:
        cid = str(r.get('Campaign ID') or '').strip()
        if not cid:
            continue
        camps[cid] = dict(id=cid, name=str(r.get('ชื่อแคมเปญ') or cid).strip(),
                          objective=str(r.get('เป้าหมาย (objective)') or ''), status=str(r.get('สถานะจริง') or ''),
                          start=str(r.get('วันเริ่ม (เวลาไทย)') or '')[:10], end=str(r.get('วันจบ (เวลาไทย)') or '')[:10],
                          spend=num(r.get('Spend (ยอดใช้จ่าย บาท)')), chats=num(r.get('เริ่มแชท (7 วัน)')),
                          leads=num(r.get('ลีด')), buys=num(r.get('การซื้อ')), cpm=num(r.get('CPM (บาท/1,000 ครั้ง)')),
                          ads=[], adsets=set())
    ads = {}
    for r in M['ads']:
        aid = str(r.get('Ad ID') or '').strip()
        if not aid:
            continue
        cid = str(r.get('Campaign ID') or '').strip()
        a = dict(id=aid, name=str(r.get('ชื่อโฆษณา') or aid).strip(), adset=str(r.get('ชื่อชุดโฆษณา') or '').strip(),
                 adset_id=str(r.get('Ad set ID') or '').strip(), cid=cid,
                 camp=str(r.get('ชื่อแคมเปญ') or '').strip(), status=str(r.get('สถานะจริง') or ''),
                 created=str(r.get('สร้างเมื่อ (เวลาไทย)') or '')[:10], ctype=str(r.get('ประเภทครีเอทีฟ') or ''),
                 text=str(r.get('ข้อความหลัก (primary text)') or ''), headline=str(r.get('หัวข้อ (headline)') or ''),
                 cta=str(r.get('ปุ่ม CTA') or ''), preview=str(r.get('ลิงก์ดูตัวอย่างโฆษณา') or ''),
                 quality=str(r.get('Quality ranking') or ''),
                 spend=num(r.get('Spend (ยอดใช้จ่าย บาท)')), chats=num(r.get('เริ่มแชท (7 วัน)')),
                 leads=num(r.get('ลีด')), buys=num(r.get('การซื้อ')),
                 welcome=None, dest='', labels=[], first='', last='')
        ads[aid] = a
        if cid not in camps:
            camps[cid] = dict(id=cid, name=a['camp'] or cid, objective='', status='', start='', end='',
                              spend=0, chats=0, leads=0, buys=0, cpm=0, ads=[], adsets=set())
        camps[cid]['ads'].append(aid)
        camps[cid]['adsets'].add(a['adset'])
    # ข้อความต้อนรับ → กลุ่ม (W01, W02, …) เรียงตามจำนวนแชท
    groups = {}
    for r in M['welcome']:
        aid = str(r.get('Ad ID') or '').strip()
        if aid not in ads:
            continue
        texts = [norm(t) for t in str(r.get(W_TEXT) or '').split('\n---\n') if norm(t)]
        labels = [norm(p.split('→')[0]) for p in str(r.get(W_BTN) or '').split(' | ') if norm(p.split('→')[0])]
        a = ads[aid]
        a['dest'] = str(r.get('ปลายทาง') or '')
        a['labels'] = labels
        a['first'] = str(r.get('วันแรกที่แสดงผล (เวลาบัญชี LA)') or '')[:10]
        a['last'] = str(r.get('วันสุดท้ายที่แสดงผล (เวลาบัญชี LA)') or '')[:10]
        if texts:
            key = tuple(texts)
            groups.setdefault(key, []).append(aid)
            a['welcome_key'] = key
    order = sorted(groups, key=lambda k: -sum(ads[x]['chats'] for x in groups[k]))
    wg = {}
    for i, k in enumerate(order, 1):
        code = 'W%02d' % i
        short = safe(k[0], 60)
        if len(short) >= 60 and ' ' in short:
            short = short.rsplit(' ', 1)[0]
        title = 'ข้อความต้อนรับ %s - %s' % (code, short)
        wg[k] = dict(code=code, title=title, texts=list(k), ads=groups[k])
        for aid in groups[k]:
            ads[aid]['welcome'] = wg[k]
    # ชื่อโน้ต
    for c in camps.values():
        c['title'] = 'แคมเปญ ' + safe(c['name'])
        names = [c['name']] + sorted(x for x in c['adsets'] if x)
        ar = area_of(c['name'])
        if ar == 'ไม่ระบุ':
            votes = Counter(area_of(n) for n in names[1:])
            votes.pop('ไม่ระบุ', None)
            ar = votes.most_common(1)[0][0] if votes else 'ไม่ระบุ'
        c['area'] = ar
        c['course'] = course_of(c['name'])
        c['platform'] = platform_of(c['name'])
    seen = set()
    for a in ads.values():
        t = safe('โฆษณา %s · %s · %s' % (a['id'][-10:-4], camps[a['cid']]['name'] if a['cid'] in camps else a['camp'], a['name']), 110)
        while t in seen:
            t += '+'
        seen.add(t)
        a['title'] = t
        a['area'] = area_of(a['adset'] + ' ' + a['camp'])
        if a['area'] == 'ไม่ระบุ' and a['cid'] in camps:
            a['area'] = camps[a['cid']]['area']
    return camps, ads, wg


def monthly_ad_stats(M):
    """รวมรายเดือนต่อโฆษณา/แคมเปญ + ช่วง 3 เดือนล่าสุด"""
    am, cm = defaultdict(dict), defaultdict(dict)
    for r in M['amon']:
        m = str(r.get('เดือน (เริ่ม)') or '')[:7]
        aid = str(r.get('Ad ID') or '').strip()
        if m and aid:
            am[aid][m] = (num(r.get('Spend (ยอดใช้จ่าย บาท)')), num(r.get('เริ่มแชท (7 วัน)')), num(r.get('การซื้อ')))
    for r in M['cmon']:
        m = str(r.get('เดือน (เริ่ม)') or '')[:7]
        cid = str(r.get('Campaign ID') or '').strip()
        if m and cid:
            cm[cid][m] = (num(r.get('Spend (ยอดใช้จ่าย บาท)')), num(r.get('เริ่มแชท (7 วัน)')), num(r.get('การซื้อ')))
    months = sorted({m for d in cm.values() for m in d} | {m for d in am.values() for m in d})
    last3 = months[-3:]
    return am, cm, months, last3


def sum3(d, last3):
    s = c = b = 0.0
    for m in last3:
        if m in d:
            s += d[m][0]; c += d[m][1]; b += d[m][2]
    return s, c, b


# ---------------------------------------------------------------- chat logs
def month_keys_from_title(name):
    m = re.search(r'—\s*(.+?)\s+(\d{4})\s*$', name)
    if not m:
        return []
    part, yr = m.group(1), int(m.group(2))
    idx = [i for i in range(1, 13) if TH_ABBR[i] in part]
    if not idx:
        return []
    if '–' in part or '-' in part:
        idx = list(range(min(idx), max(idx) + 1))
    return ['%04d-%02d' % (yr, i) for i in idx]


def find_fb_files():
    out = {}
    for name, sid, mod in search_sheets('Biopalm FB Chat Log'):
        if not name.startswith('Biopalm FB Chat Log'):
            continue
        for k in month_keys_from_title(name):
            if k not in out or mod > out[k][1]:
                out[k] = (sid, mod)
    return {k: v[0] for k, v in out.items()}


def parse_fb_overview(rows):
    """แท็บ สรุปภาพรวม (ไฟล์ละ 1–2 เดือน) → {YYYY-MM: {...}}"""
    res, cur = {}, None
    for r in rows:
        if not r:
            continue
        lab = str(r[0]).strip()
        val = r[1] if len(r) > 1 else ''
        note = r[2] if len(r) > 2 else ''
        if lab == 'ช่วงข้อมูล':
            mm = next((i for i in range(1, 13) if TH_FULL[i] in str(val)), None)
            yy = re.search(r'(\d{4})', str(val))
            if mm and yy:
                cur = '%s-%02d' % (yy.group(1), mm)
                res[cur] = {}
            continue
        if cur is None:
            continue
        d = res[cur]
        if lab == 'แชททั้งหมด':
            d['chats'] = num(val)
        elif lab == 'ปิดการขายได้':
            d['closed'] = num(val)
        elif lab.startswith('— ลีดจากโฆษณา'):
            d['ad_close'] = num(val)
            m = re.search(r'จาก\s*([\d,]+)', str(note))
            d['ad_leads'] = num(m.group(1)) if m else 0
        elif lab.startswith('— ลีดไม่ได้มาจากโฆษณา'):
            d['nonad_close'] = num(val)
            m = re.search(r'จาก\s*([\d,]+)', str(note))
            d['nonad_leads'] = num(m.group(1)) if m else 0
        elif lab == 'ทักใหม่ · มาจากโฆษณา':
            d['new_ad'] = num(val)
        elif lab == 'ทักใหม่ · ออร์แกนิก':
            d['new_organic'] = num(val)
        elif lab == 'ทักใหม่ · จากคอมเมนต์ใต้โพสต์':
            d['new_comment'] = num(val)
        elif lab == 'ลูกค้าเก่าทักกลับมาเอง':
            d['returning'] = num(val)
        elif lab == 'รวม แอดมินตามเอง':
            d['admin_follow'] = num(val)
    return res


def load_fb_overviews(files):
    out = {}
    for sid in sorted(set(files.values())):
        try:
            T = tabs_of(sid)
            if 'สรุปภาพรวม' not in T:
                continue
            rows = read_window(sid, 'สรุปภาพรวม', 1, 140, 'A', 'C')
            for k, v in parse_fb_overview(rows).items():
                if k not in out or len(v) > len(out[k]):
                    out[k] = v
        except ToolError as e:
            warn('อ่านสรุปภาพรวม FB ไม่ได้ 1 ไฟล์ (%s)' % str(e)[:60])
    return out


def load_line_ig(year):
    line, ig = {}, {}
    for name, sid, _ in search_sheets('Biopalm LINE Chat Log'):
        if name.strip() == 'Biopalm LINE Chat Log — %d' % year:
            SOURCES['line'] = [(name, sid)]
            try:
                rows = read_window(sid, 'สรุปภาพรวม (รายเดือน)', 1, 60, 'A', 'Z')
                hdr = next((r for r in rows if r and str(r[0]).strip() == 'ตัวชี้วัด'), None)
                if hdr:
                    cols = {}
                    for j, h in enumerate(hdr[1:], 1):
                        mm = next((i for i in range(1, 13) if str(h).startswith(TH_ABBR[i])), None)
                        if mm:
                            cols[j] = '%d-%02d' % (year, mm)
                    for r in rows:
                        lab = str(r[0]).strip() if r else ''
                        key = {'ห้องแชท': 'rooms', 'ปิดการขาย (สลิปตรวจสำเร็จ)': 'closed'}.get(lab)
                        if key:
                            for j, m in cols.items():
                                if j < len(r):
                                    line.setdefault(m, {}).setdefault(key, num(r[j]))
            except ToolError as e:
                warn('อ่านสรุป LINE ไม่ได้ (%s)' % str(e)[:60])
            break
    for name, sid, _ in search_sheets('Biopalm IG Chat Log'):
        if name.strip() == 'Biopalm IG Chat Log — %d' % year:
            SOURCES['ig'] = [(name, sid)]
            try:
                rows = read_window(sid, 'เทียบรายเดือน', 1, 60, 'A', 'Z')
                hdr = next((r for r in rows if r and str(r[0]).strip() == 'ตัวชี้วัด'), None)
                if hdr:
                    cols = {}
                    for j, h in enumerate(hdr[1:], 1):
                        mm = next((i for i in range(1, 13) if str(h).startswith(TH_FULL[i])), None)
                        if mm:
                            cols[j] = '%d-%02d' % (year, mm)
                    for r in rows:
                        lab = str(r[0]).strip() if r else ''
                        key = 'chats' if lab == 'แชททั้งหมด' else ('closed' if lab.startswith('ปิดการขาย') else None)
                        if key:
                            for j, m in cols.items():
                                if j < len(r) and key not in ig.get(m, {}):
                                    ig.setdefault(m, {})[key] = num(r[j])
            except ToolError as e:
                warn('อ่านสรุป IG ไม่ได้ (%s)' % str(e)[:60])
            break
    return line, ig


# ---------------------------------------------------------------- sentiment config (อ่านจาก vault)
DEFAULT_SENT = {
    'positive': ['ขอบคุณ', 'สนใจ', 'โอเค', 'ได้เลย', 'สมัคร', 'โอนแล้ว', 'ชอบ', 'ดีมาก', 'เยี่ยม', 'ประทับใจ', '🙏', '👍', '❤️'],
    'negative': ['แพง', 'ไม่สะดวก', 'ช้า', 'รอนาน', 'ไม่ตอบ', 'ผิดหวัง', 'ยกเลิก', 'คืนเงิน', 'ไม่ได้รับ', 'เข้าไม่ได้', 'งง'],
    'hesitant': ['ขอคิดก่อน', 'ขอปรึกษา', 'ปรึกษาผู้ปกครอง', 'ไว้ก่อน', 'ยังไม่แน่ใจ', 'ขอดูก่อน', 'เดี๋ยวแจ้ง'],
    'negation': ['ไม่', 'ไม่ได้'],
}


def read_frontmatter(path):
    try:
        t = open(path, encoding='utf-8').read()
        if t.startswith('---'):
            return yaml.safe_load(t.split('---', 2)[1]) or {}
    except Exception:
        pass
    return {}


def load_config():
    cfg = dict(DEFAULT_SENT)
    fm = read_frontmatter(os.path.join(VAULT, 'Config', 'คำ sentiment.md'))
    for k in DEFAULT_SENT:
        if isinstance(fm.get(k), list) and fm[k]:
            cfg[k] = [str(x) for x in fm[k] if str(x).strip()]
    topics = {}
    tdir = os.path.join(VAULT, 'Topics')
    if os.path.isdir(tdir):
        for fn in sorted(os.listdir(tdir)):
            if fn.endswith('.md'):
                kw = read_frontmatter(os.path.join(tdir, fn)).get('keywords')
                if isinstance(kw, list) and kw:
                    topics[fn[:-3]] = [str(x).lower() for x in kw if str(x).strip()]
    if not topics:
        topics = {t: [k.lower() for k in kws] for t, kws in DEFAULT_TOPICS.items()}
    return cfg, topics


def score_text(t, cfg):
    t = t.lower()
    s = 0.0
    neg_words = [n.lower() for n in cfg['negation']]

    def negated(idx):
        pre = t[max(0, idx - 5):idx]
        return any(n in pre for n in neg_words)

    for k in cfg['positive']:
        i = t.find(k.lower())
        if i >= 0:
            s += -1 if negated(i) else 1
    for k in cfg['negative']:
        kl = k.lower()
        i = t.find(kl)
        if i >= 0:
            s += 0.5 if (negated(i) and not kl.startswith('ไม่')) else -1
    for k in cfg['hesitant']:
        if k.lower() in t:
            s -= 0.5
    return max(-1.0, min(1.0, s))


_MASK = [(re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+'), '[อีเมล]'), (re.compile(r'\d[\d\s-]{7,}\d'), '[ตัวเลข]')]


def quote(t, n=160):
    t = norm(t)
    for rx, rep in _MASK:
        t = rx.sub(rep, t)
    t = t.lstrip('>#-').strip()
    return (t[:n] + '…') if len(t) > n else t


# ---------------------------------------------------------------- FB chats → notes
class Msg(object):
    __slots__ = ('seq', 'time', 'side', 'kind', 'text')

    def __init__(self, seq, time_, side, kind, text):
        self.seq, self.time, self.side, self.kind, self.text = seq, time_, side, kind, text


def parse_time(s, year):
    m = re.match(r'(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?', str(s or '').strip())
    if not m:
        return None
    d, mo, h, mi, se = m.groups()
    try:
        return datetime(year, int(mo), int(d), int(h), int(mi), int(se or 0), tzinfo=BKK)
    except ValueError:
        return None


def load_fb_month(sid, mkey):
    year = int(mkey[:4])
    T = tabs_of(sid)
    if 'สรุปรายแชท' not in T:
        raise ToolError('ไม่พบแท็บ สรุปรายแชท')
    _, summ = read_table(sid, 'สรุปรายแชท', T, 'เดือน', cols=[
        'Thread ID', 'กลุ่ม', 'ป้าย Meta', 'แอดมินพิมพ์เองครั้งแรก', 'ทีมที่ตอบ', 'ได้รับราคา', 'ลูกค้าแจ้งจ่าย',
        'หมวด (เกณฑ์ admin-hub)'], chunk=1500)
    threads = defaultdict(list)
    mtabs = [t for t in T if t.startswith('ข้อความ')]
    for tab in mtabs:                       # อ่านไม่ครบทุกแท็บ → ยกเลิกเดือนนี้ทั้งเดือน (ไม่สร้างโน้ตจากข้อมูลครึ่ง ๆ กลาง ๆ)
        header, rows = read_table(sid, tab, T, 'เดือน', cols=['Thread ID', 'ลำดับ', 'เวลา', 'ฝ่าย', 'ประเภท', 'ข้อความ'],
                                  heavy=('ข้อความ',), chunk=3000, heavy_chunk=800)
        for r in rows:
            tid = str(r.get('Thread ID') or '').strip()
            if not tid:
                continue
            try:
                seq = int(float(str(r.get('ลำดับ') or '0')))
            except ValueError:
                seq = 0
            threads[tid].append(Msg(seq, parse_time(r.get('เวลา'), year), str(r.get('ฝ่าย') or '').strip(),
                                    str(r.get('ประเภท') or '').strip(), str(r.get('ข้อความ') or '')))
    for v in threads.values():
        v.sort(key=lambda m: m.seq)
    log('FB %s: สรุปรายแชท %d ห้อง · มีข้อความ %d ห้อง (%d แท็บ)' % (mkey, len(summ), len(threads), len(mtabs)))
    return summ, threads


def build_matchers(ads):
    eq, rx, labels = defaultdict(set), [], set()
    for a in ads.values():
        if not a.get('welcome'):
            continue
        for t in a['welcome']['texts']:
            if '{{' in t:
                parts = re.split(r'\{\{[^}]*\}\}', t)
                rx.append((re.compile('^' + '.+?'.join(re.escape(p) for p in parts) + '$'), t, a['id']))
            else:
                eq[t].add(a['id'])
        labels.update(a['labels'])
    rxd = defaultdict(set)
    for c, t, aid in rx:
        rxd[(c.pattern, t)].add(aid)
    rx_list = [(re.compile(p), t, ids) for (p, t), ids in rxd.items()]
    return eq, rx_list, labels


def match_touch(msgs, i, ads, eq, rx_list, daily, channel='FB'):
    W, cands = None, set()
    for j in range(max(0, i - 3), min(len(msgs), i + 4)):
        m = msgs[j]
        if j == i or m.side != 'ธุรกิจ':
            continue
        t = norm(m.text)
        if t in eq:
            W, cands = t, set(eq[t])
            break
        for c, key, ids in rx_list:
            if c.match(t):
                W, cands = key, set(ids)
                break
        if W:
            break
    if not W:
        return None, 'ad-unknown', 0
    want = 'INSTAGRAM' if channel == 'IG' else 'MESSENGER'
    c1 = {a for a in cands if want in ads[a]['dest']} or cands
    Q = None
    for j in range(max(0, i - 2), min(len(msgs), i + 5)):
        if msgs[j].side == 'ลูกค้า':
            q = norm(msgs[j].text)
            if any(q in ads[a]['labels'] for a in c1):
                Q = q
                break
    if Q:
        c1 = {a for a in c1 if Q in ads[a]['labels']} or c1
    t0 = msgs[i].time
    if t0 is not None:
        d = t0.astimezone(LA).date().isoformat()
        c2 = {a for a in c1 if daily.get((d, a), 0) > 0}
        if not c2:
            c2 = {a for a in c1 if ads[a]['first'] and ads[a]['last'] and ads[a]['first'] <= d <= ads[a]['last']}
        c1 = c2 or c1
    else:
        d = ''
    best = max(c1, key=lambda a: (daily.get((d, a), 0), ads[a]['chats']))
    if len(c1) == 1:
        kind = 'exact'
    elif len({ads[a]['cid'] for a in c1}) == 1:
        kind = 'campaign'
    else:
        kind = 'welcome'
    return best, kind, len(c1)


def analyse_threads(mkey, summ, threads, ads, eq, rx_list, labels, daily, cfg, topics):
    res = {}
    for row in summ:
        tid = str(row.get('Thread ID') or '').strip()
        if not tid:
            continue
        msgs = threads.get(tid, [])
        touches = [i for i, m in enumerate(msgs) if m.side == 'ธุรกิจ' and norm(m.text).endswith('ตอบกลับโฆษณา')]
        ad, kind, ncand = None, None, 0
        for i in touches:
            a, k, n = match_touch(msgs, i, ads, eq, rx_list, daily)
            if ad is None or (a and kind == 'ad-unknown'):
                ad, kind, ncand = a, k, n
        real = [m for m in msgs if m.kind != 'ระบบ Meta']
        if touches:
            source = 'ads'
        elif real and real[0].side == 'ลูกค้า':
            source = 'organic'
        elif real:
            source = 'admin_followup'
        else:
            source = 'unknown'
        cust = [m for m in msgs if m.side == 'ลูกค้า']
        texts = [m.text for m in cust if norm(m.text) and not norm(m.text).startswith('[')
                 and norm(m.text) not in labels]
        scores = [score_text(t, cfg) for t in texts]
        k = min(3, max(1, len(scores) // 2))          # ข้อความน้อย: ต้น = ข้อความแรก ท้าย = ข้อความสุดท้าย
        s_start = round(statistics.mean(scores[:k]), 2) if scores else None
        s_end = round(statistics.mean(scores[-k:]), 2) if scores else None
        low = ' '.join(texts).lower()
        tps = [t for t, kws in topics.items() if any(k in low for k in kws)]
        group = str(row.get('กลุ่ม') or '').strip()
        stage = group.split(' ')[0] if group else ''
        cat = str(row.get('หมวด (เกณฑ์ admin-hub)') or '').strip()
        closed = stage == 'S5' or cat.startswith('ปิดการขาย')
        first_t = next((m.time for m in msgs if m.time), None)
        res[tid] = dict(
            tid=tid, month=mkey, source=source, ad=ad, match=kind if touches else None, ncand=ncand,
            touches=len(touches), stage=stage, closed=closed, lead=stage in ('S2', 'S3', 'S4', 'S5'),
            price=str(row.get('ได้รับราคา') or '').strip() == 'Y', paid=str(row.get('ลูกค้าแจ้งจ่าย') or '').strip() == 'Y',
            label=str(row.get('ป้าย Meta') or '').strip(), cat=cat, team=str(row.get('ทีมที่ตอบ') or '').strip(),
            first_reply=str(row.get('แอดมินพิมพ์เองครั้งแรก') or '').strip(), cust_n=len(cust),
            s_start=s_start, s_end=s_end, s_delta=(round(s_end - s_start, 2) if scores else None), topics=tps,
            q_first=quote(texts[0]) if texts else '', q_last=quote(texts[-1]) if len(texts) > 1 else '',
            first_at=first_t.strftime('%Y-%m-%d %H:%M') if first_t else '')
    return res


def avg(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 2) if xs else None


def pct(a, b):
    return round(100.0 * a / b, 1) if b else None


def month_chat_stats(res):
    by_src = defaultdict(lambda: dict(chats=0, leads=0, closed=0, s_start=[], s_end=[]))
    by_ad = defaultdict(lambda: dict(chats=0, leads=0, closed=0, s_end=[], topics=Counter(), exact=0))
    match = Counter()
    for r in res.values():
        s = by_src[r['source']]
        s['chats'] += 1
        s['leads'] += r['lead']
        s['closed'] += r['closed'] and r['lead']
        s['s_start'].append(r['s_start'])
        s['s_end'].append(r['s_end'])
        if r['source'] == 'ads':
            match[r['match'] or 'ad-unknown'] += 1
        if r['ad']:
            a = by_ad[r['ad']]
            a['chats'] += 1
            a['leads'] += r['lead']
            a['closed'] += r['closed'] and r['lead']
            a['s_end'].append(r['s_end'])
            a['topics'].update(r['topics'])
            a['exact'] += r['match'] == 'exact'
    src = {k: dict(chats=v['chats'], leads=v['leads'], closed=v['closed'], s_start=avg(v['s_start']), s_end=avg(v['s_end']))
           for k, v in by_src.items()}
    ad = {k: dict(chats=v['chats'], leads=v['leads'], closed=v['closed'], s_end=avg(v['s_end']),
                  topics=dict(v['topics']), exact=v['exact']) for k, v in by_ad.items()}
    return dict(by_source=src, by_ad=ad, match=dict(match), threads=len(res))


SRC_TH = {'ads': 'โฆษณา', 'organic': 'ทักเอง (ไม่ใช่โฆษณา)', 'admin_followup': 'แอดมินตามเอง', 'unknown': 'ไม่ทราบ'}


def write_chat_notes(mkey, res, ads, camps):
    y, mo = int(mkey[:4]), int(mkey[5:7])
    n = 0
    for r in res.values():
        if r['stage'] not in NOTE_STAGES:
            continue
        a = ads.get(r['ad']) if r['ad'] else None
        fm = dict(type='chat', channel='FB', thread_id=r['tid'], month=mkey, source=r['source'],
                  ad=('[[%s]]' % a['title']) if a else None,
                  campaign=('[[%s]]' % camps[a['cid']]['title']) if a and a['cid'] in camps else None,
                  match=r['match'], ad_candidates=r['ncand'] or None, ad_touches=r['touches'] or None,
                  stage=r['stage'], closed=r['closed'], price_sent=r['price'], customer_paid=r['paid'],
                  meta_label=r['label'] or None, category=r['cat'] or None, customer_msgs=r['cust_n'],
                  sent_start=r['s_start'], sent_end=r['s_end'], sent_delta=r['s_delta'],
                  topics=['[[%s]]' % t for t in r['topics']], first_human_reply=r['first_reply'] or None,
                  team=r['team'] or None, first_at=r['first_at'] or None)
        body = ['# แชท %s' % r['tid'], '',
                'FB %s %d · ที่มา: %s · ขั้น %s%s' % (TH_ABBR[mo], y, SRC_TH.get(r['source'], r['source']), r['stage'],
                                                   ' · ปิดการขายแล้ว' if r['closed'] else '')]
        if a:
            body += ['', 'โฆษณา: [[%s]] (จับคู่แบบ %s)' % (a['title'], r['match'])]
        if r['q_first']:
            body += ['', '## ข้อความแรกของลูกค้า', '> ' + r['q_first']]
        if r['q_last']:
            body += ['', '## ข้อความสุดท้ายของลูกค้า', '> ' + r['q_last']]
        day = (r['first_at'] or '')[8:10] or '00'          # แบ่งโฟลเดอร์ตามวันที่ทักครั้งแรก (โฟลเดอร์ละไม่เกิน ~150 ไฟล์)
        put('Chats/FB/%s/%s/%s.md' % (mkey, day, safe(r['tid'], 60)), front(fm) + '\n' + '\n'.join(body))
        n += 1
    return n


# ---------------------------------------------------------------- สถิติแชทสะสม (แยกไฟล์เล็กรายเดือน)
# Composio ส่งคำตอบกลับได้ราว 10k token → ไฟล์ state ต้องเล็ก: .vault/stats/<เดือน>/main.json + ads-NN.json (โฆษณาละไม่เกิน 25 ตัว)
STATE_DIR = '.vault/stats'
AD_SHARD = 25
BAD_STATE_MONTHS = set()          # เดือนที่อ่านไฟล์ state ไม่ครบ → ไม่เขียนทับ/ไม่ลบไฟล์ของเดือนนั้น (ถ้ารอบนี้ไม่ได้ประมวลผลใหม่)


def load_state():
    months = {}
    for p in PREFETCH_FAILED:
        m = re.match(r'^%s/(\d{4}-\d{2})/' % re.escape(STATE_DIR), p)
        if m:
            BAD_STATE_MONTHS.add(m.group(1))
    base = os.path.join(VAULT, *STATE_DIR.split('/'))
    if os.path.isdir(base):
        for m in sorted(os.listdir(base)):
            d = os.path.join(base, m)
            if not (re.match(r'^\d{4}-\d{2}$', m) and os.path.isdir(d)):
                continue
            st = {'by_ad': {}}
            for fn in sorted(os.listdir(d)):
                try:
                    part = json.load(open(os.path.join(d, fn), encoding='utf-8'))
                except Exception:
                    BAD_STATE_MONTHS.add(m)
                    continue
                if fn == 'main.json':
                    st.update({k: v for k, v in part.items() if k != 'by_ad'})
                else:
                    st['by_ad'].update(part)
            months[m] = st
    if BAD_STATE_MONTHS:
        warn('สถิติแชทสะสมอ่านไม่ครบ %d เดือน (%s) — คงไฟล์เดิมของเดือนนั้นไว้' % (
            len(BAD_STATE_MONTHS), ', '.join(sorted(BAD_STATE_MONTHS))))
    return {'months': months}


def save_state(state):
    for m, st in sorted(state['months'].items()):
        if m in BAD_STATE_MONTHS:
            continue
        main_part = {k: v for k, v in st.items() if k != 'by_ad'}
        put('%s/%s/main.json' % (STATE_DIR, m), json.dumps(main_part, ensure_ascii=False, sort_keys=True, separators=(',', ':')))
        ads = sorted((st.get('by_ad') or {}).items())
        for i in range(0, len(ads), AD_SHARD):
            part = {}
            for aid, v in ads[i:i + AD_SHARD]:
                v = dict(v)
                v['topics'] = dict(Counter(v.get('topics') or {}).most_common(5))
                part[aid] = v
            put('%s/%s/ads-%02d.json' % (STATE_DIR, m, i // AD_SHARD + 1),
                json.dumps(part, ensure_ascii=False, sort_keys=True, separators=(',', ':')))


# ---------------------------------------------------------------- notes: ads / campaigns / months
def ad_chat_totals(state):
    tot = defaultdict(lambda: dict(chats=0, leads=0, closed=0, s_end=[], topics=Counter(), exact=0))
    for m, st in state.get('months', {}).items():
        for aid, v in (st.get('by_ad') or {}).items():
            t = tot[aid]
            t['chats'] += v['chats']; t['leads'] += v['leads']; t['closed'] += v['closed']; t['exact'] += v.get('exact', 0)
            if v.get('s_end') is not None:
                t['s_end'].extend([v['s_end']] * max(1, v['chats']))
            t['topics'].update(v.get('topics') or {})
    return tot


def write_ads(camps, ads, wg, am, cm, last3, chat_tot):
    per = '%s ถึง %s' % (last3[0], last3[-1]) if last3 else ''
    for a in ads.values():
        if a['spend'] <= 0 and a['id'] not in chat_tot:
            continue
        s3, c3, b3 = sum3(am.get(a['id'], {}), last3)
        ct = chat_tot.get(a['id'])
        c = camps.get(a['cid'])
        fm = dict(type='ad', ad_id=a['id'], aliases=['AD-' + a['id']], ad_name=a['name'],
                  campaign='[[%s]]' % c['title'] if c else None, adset=a['adset'] or None,
                  welcome='[[%s]]' % a['welcome']['title'] if a.get('welcome') else None,
                  destination=a['dest'] or None, status=a['status'] or None, area=a['area'],
                  course=c['course'] if c else None, created=a['created'] or None,
                  spend=round(a['spend']), chats_meta=a['chats'], leads_meta=a['leads'], purchases_meta=a['buys'],
                  cost_per_chat=round(a['spend'] / a['chats']) if a['chats'] else None,
                  cost_per_purchase=round(a['spend'] / a['buys']) if a['buys'] else None,
                  chat_to_purchase_pct=pct(a['buys'], a['chats']),
                  spend_3m=round(s3) or None, chats_3m=c3 or None, purchases_3m=b3 or None,
                  cost_per_purchase_3m=round(s3 / b3) if b3 else None,
                  chats_matched=ct['chats'] if ct else None, leads_matched=ct['leads'] if ct else None,
                  closed_matched=ct['closed'] if ct else None,
                  close_pct_matched=pct(ct['closed'], ct['leads']) if ct else None,
                  sent_end_avg=avg(ct['s_end']) if ct else None,
                  top_topics=['[[%s]]' % t for t, _ in ct['topics'].most_common(3)] if ct else None,
                  quality=a['quality'] or None)
        body = ['# ' + a['title'], '',
                '- แคมเปญ: %s' % ('[[%s]]' % c['title'] if c else '-'),
                '- ชุดโฆษณา: %s' % (a['adset'] or '-'),
                '- ข้อความต้อนรับ: %s' % ('[[%s]]' % a['welcome']['title'] if a.get('welcome') else '-'),
                '- ชื่อใน Meta: "%s"' % a['name']]
        if a['preview']:
            body.append('- [ดูตัวอย่างโฆษณา](%s)' % a['preview'])
        body += ['', '| ช่วง | ใช้จ่าย | เริ่มแชท | ปิด (Meta) | บาท/การปิด |', '|---|---|---|---|---|',
                 '| ทั้งหมดในชีต | %s | %s | %s | %s |' % (fmt(a['spend']), fmt(a['chats']), fmt(a['buys']),
                                                       fmt(a['spend'] / a['buys']) if a['buys'] else '-'),
                 '| %s | %s | %s | %s | %s |' % (per or '3 เดือนล่าสุด', fmt(s3), fmt(c3), fmt(b3), fmt(s3 / b3) if b3 else '-')]
        if ct:
            body += ['', 'จาก chat log: จับคู่ได้ %d แชท (ตรงตัว %d) · ลีด %d · ปิด %d · อารมณ์ท้ายเฉลี่ย %s' % (
                ct['chats'], ct['exact'], ct['leads'], ct['closed'], avg(ct['s_end']))]
        if a['headline'] or a['text']:
            body += ['', '## ข้อความโฆษณา']
            if a['headline']:
                body.append('**%s**' % norm(a['headline']))
            if a['text']:
                body += ['', '> ' + norm(a['text'])[:600]]
        body += ['', '## แชทที่จับคู่ได้', '```dataview',
                 'TABLE WITHOUT ID file.link AS "แชท", month AS "เดือน", stage AS "ขั้น", closed AS "ปิด", match AS "จับคู่", sent_start AS "อารมณ์ต้น", sent_end AS "อารมณ์ท้าย", topics AS "เรื่องที่ถาม"',
                 'FROM "Chats"', 'WHERE ad = this.file.link', 'SORT first_at DESC', '```']
        put('Ads/Ads/%s/%s.md' % (c['title'] if c else 'ไม่ทราบแคมเปญ', a['title']), front(fm) + '\n' + '\n'.join(body))

    for c in camps.values():
        if c['spend'] <= 0 and not any(x in chat_tot for x in c['ads']):
            continue
        s3, c3, b3 = sum3(cm.get(c['id'], {}), last3)
        mt = [chat_tot[x] for x in c['ads'] if x in chat_tot]
        fm = dict(type='campaign', campaign_id=c['id'], aliases=['CP-' + c['id']], campaign_name=c['name'],
                  objective=c['objective'] or None, status=c['status'] or None, platform=c['platform'],
                  area=c['area'], course=c['course'], start=c['start'] or None, end=c['end'] or None,
                  spend=round(c['spend']), chats_meta=c['chats'], leads_meta=c['leads'], purchases_meta=c['buys'],
                  cost_per_chat=round(c['spend'] / c['chats']) if c['chats'] else None,
                  cost_per_purchase=round(c['spend'] / c['buys']) if c['buys'] else None,
                  chat_to_purchase_pct=pct(c['buys'], c['chats']), cpm=c['cpm'] or None,
                  spend_3m=round(s3) or None, chats_3m=c3 or None, purchases_3m=b3 or None,
                  cost_per_purchase_3m=round(s3 / b3) if b3 else None,
                  chats_matched=sum(t['chats'] for t in mt) or None,
                  closed_matched=sum(t['closed'] for t in mt) or None, ads_count=len(c['ads']))
        body = ['# ' + c['title'], '',
                'พื้นที่: [[%s]] · คอร์ส: [[%s]] · ช่องทาง: [[%s]]' % (c['area'], c['course'], c['platform']), '',
                '| ช่วง | ใช้จ่าย | เริ่มแชท | ลีด | ปิด (Meta) | บาท/แชท | บาท/การปิด |', '|---|---|---|---|---|---|---|',
                '| ทั้งหมดในชีต | %s | %s | %s | %s | %s | %s |' % (
                    fmt(c['spend']), fmt(c['chats']), fmt(c['leads']), fmt(c['buys']),
                    fmt(c['spend'] / c['chats']) if c['chats'] else '-', fmt(c['spend'] / c['buys']) if c['buys'] else '-'),
                '| %s | %s | %s | - | %s | %s | %s |' % (per or '3 เดือนล่าสุด', fmt(s3), fmt(c3), fmt(b3),
                                                       fmt(s3 / c3) if c3 else '-', fmt(s3 / b3) if b3 else '-'),
                '', '## โฆษณาในแคมเปญนี้', '```dataview',
                'TABLE WITHOUT ID file.link AS "โฆษณา", spend AS "ใช้จ่าย", chats_meta AS "แชท", purchases_meta AS "ปิด", cost_per_purchase AS "บาท/การปิด", cost_per_purchase_3m AS "บาท/การปิด 3 เดือน", chats_matched AS "แชทที่จับคู่", sent_end_avg AS "อารมณ์ท้าย"',
                'FROM "Ads/Ads"', 'WHERE campaign = this.file.link', 'SORT spend DESC', '```']
        put('Ads/Campaigns/%s.md' % c['title'], front(fm) + '\n' + '\n'.join(body))

    for k, g in wg.items():
        gads = [ads[x] for x in g['ads']]
        fm = dict(type='welcome', code=g['code'], ads_count=len(gads), spend=round(sum(x['spend'] for x in gads)),
                  chats_meta=sum(x['chats'] for x in gads), purchases_meta=sum(x['buys'] for x in gads))
        body = ['# ' + g['title'], ''] + ['> ' + t for t in g['texts']] + [
            '', 'ใช้ใน %d โฆษณา — ถ้าหลายโฆษณาใช้ข้อความเดียวกัน แชทจะจับคู่ได้แค่ระดับแคมเปญ/กลุ่มข้อความ (ดู [[03 วิธีเชื่อมข้อมูล]])' % len(gads),
            '', '```dataview',
            'TABLE WITHOUT ID file.link AS "โฆษณา", campaign AS "แคมเปญ", chats_meta AS "แชท", purchases_meta AS "ปิด", cost_per_purchase AS "บาท/การปิด"',
            'FROM "Ads/Ads"', 'WHERE welcome = this.file.link', 'SORT chats_meta DESC', '```']
        put('Ads/Welcome/%s.md' % g['title'], front(fm) + '\n' + '\n'.join(body))

    hubs = {('area', c['area']) for c in camps.values()} | {('course', c['course']) for c in camps.values()} | \
           {('platform', c['platform']) for c in camps.values()}
    for prop, name in sorted(hubs):
        put('Ads/กลุ่ม/%s.md' % safe(name), front(dict(type='hub', group=prop)) + '\n' + '\n'.join([
            '# ' + name, '', 'โน้ตศูนย์กลาง — แคมเปญที่ลิงก์มาหาโน้ตนี้จะเกาะกลุ่มกันใน Graph', '', '```dataview',
            'TABLE WITHOUT ID file.link AS "แคมเปญ", spend AS "ใช้จ่าย", purchases_meta AS "ปิด", cost_per_purchase AS "บาท/การปิด", cost_per_purchase_3m AS "บาท/การปิด 3 เดือน"',
            'FROM "Ads/Campaigns"', 'WHERE %s = "%s"' % (prop, name), 'SORT spend DESC', '```']))


CONTENT_JSON = '.vault/content/monthly.json'      # เขียนโดยงาน obsidian-content (tools/content/pull.py) ทุกวันจันทร์
CPF = [('FB', 'fb'), ('IG', 'ig'), ('TikTok', 'tiktok'), ('YouTube', 'youtube')]


def load_content():
    """สรุปคอนเทนต์รายเดือน FB/IG/TikTok/YouTube + ค่าแอด TikTok / Google Ads รายเดือน · ไม่มี/อ่านไม่ได้ → {}"""
    fp = os.path.join(VAULT, *CONTENT_JSON.split('/'))
    try:
        if os.path.exists(fp):                                       # โหมด git (clone อยู่แล้ว)
            return json.load(open(fp, encoding='utf-8'))
        if MODE != 'api':
            return {}
        # ไฟล์ใหญ่เกินคำตอบ Composio (~10k token) → อ่านรายชื่อโฟลเดอร์ (เล็ก) แล้วโหลดจาก download_url
        d = gh('GITHUB_GET_REPOSITORY_CONTENT', {'path': CONTENT_JSON.rsplit('/', 1)[0], 'ref': BRANCH})
        lst = d.get('content') if isinstance(d, dict) else d
        url = next((x.get('download_url') for x in (lst if isinstance(lst, list) else [])
                    if isinstance(x, dict) and x.get('name') == CONTENT_JSON.rsplit('/', 1)[1]), None)
        if not url:
            return {}
        import requests
        r = requests.get(url, timeout=120)
        if r.status_code != 200:
            raise ToolError('HTTP %d' % r.status_code)
        return r.json()
    except Exception as e:
        warn('อ่าน %s ไม่ได้ (%s) — โน้ตรายเดือนรอบนี้ไม่มีส่วนคอนเทนต์' % (CONTENT_JSON, type(e).__name__))
        return {}


def content_section(m, content):
    """ส่วน "คอนเทนต์ที่ลงเดือนนี้" ในโน้ต Monthly · ลิงก์ไปโน้ตโพสต์ใน Content/"""
    cm = (content.get('months') or {}).get(m) or {}
    sp = content.get('ad_spend') or {}
    out = []
    bits = []
    for pf, lab in (('TikTok', 'TikTok Ads'), ('YouTube', 'Google Ads แอดวิดีโอ YouTube')):
        v = (sp.get(pf) or {}).get(m)
        if v:
            bits.append('**%s** ใช้จ่าย %s บาท · ยอดดูจากแอด %s' % (lab, fmt(v.get('spend')), fmt(v.get('views'))))
    if bits:
        out += [''] + [' · '.join(bits)]
    if not cm:
        return out
    out += ['', '## คอนเทนต์ที่ลงเดือนนี้', '',
            '| ช่องทาง | โพสต์ | ทำแอด | ยอดดูรวม | ยอดดูมัธยฐาน (ไม่ทำแอด) | ออร์แกนิกยอดดูสูงสุด |', '|---|---:|---:|---:|---:|---|']
    for pf, _ in CPF:
        c = cm.get(pf)
        if not c:
            continue
        top = ' · '.join('[[%s\\|%s]] %s' % (t['note'], t.get('title') or t.get('format'), fmt(t.get('views'))) for t in (c.get('top') or [])[:2])
        out.append('| %s | %s | %s | %s | %s | %s |' % (
            pf, fmt(c.get('posts')), '-' if c.get('ads') is None else fmt(c.get('ads')), fmt(c.get('views')),
            fmt(c.get('views_organic_median')), top or '-'))
    stale = content.get('stale') or {}
    out += ['', '_ตัวเลขคอนเทนต์สะสมถึง %s (อัปเดตทุกวันจันทร์ — งาน obsidian-content) · "ยอดดูรวม" รวมยอดจากแอด · ดูทั้งหมดที่ [[สรุปคอนเทนต์]]%s_' % (
        content.get('pulled') or '-', (' · ⚠️ ' + ' · '.join('%s ใช้ข้อมูล %s' % kv for kv in sorted(stale.items()))) if stale else '')]
    return out


def write_months(M, fbov, line, ig, state, content=None):
    content = content or {}
    acct = {str(r.get('เดือน (เริ่ม)'))[:7]: r for r in M['acct']}
    months = sorted(set(acct) | set(fbov) | set(state.get('months', {})) | set(content.get('months') or {}))
    for m in months:
        y, mo = int(m[:4]), int(m[5:7])
        a = acct.get(m) or {}
        s, c, b = num(a.get('Spend (ยอดใช้จ่าย บาท)')), num(a.get('เริ่มแชท (7 วัน)')), num(a.get('การซื้อ'))
        f = fbov.get(m) or {}
        st = (state.get('months') or {}).get(m) or {}
        bs = st.get('by_source') or {}

        def src(k, f2):
            return (bs.get(k) or {}).get(f2)

        fm = dict(type='month', month=m,
                  meta_spend=round(s) or None, meta_chats=c or None, meta_leads=num(a.get('ลีด')) or None,
                  meta_purchases=b or None, meta_cost_per_chat=round(s / c, 1) if c else None,
                  meta_cost_per_purchase=round(s / b) if b else None, meta_cpm=num(a.get('CPM (บาท/1,000 ครั้ง)')) or None,
                  fb_chats=f.get('chats'), fb_closed=f.get('closed'),
                  fb_ad_lead_close_pct=pct(f.get('ad_close', 0), f.get('ad_leads', 0)),
                  fb_nonad_lead_close_pct=pct(f.get('nonad_close', 0), f.get('nonad_leads', 0)),
                  fb_new_from_ad=f.get('new_ad'), fb_new_organic=f.get('new_organic'), fb_new_comment=f.get('new_comment'),
                  fb_returning=f.get('returning'), fb_admin_followup=f.get('admin_follow'),
                  line_rooms=(line.get(m) or {}).get('rooms'), line_closed_slip=(line.get(m) or {}).get('closed'),
                  ig_chats=(ig.get(m) or {}).get('chats'), ig_closed=(ig.get(m) or {}).get('closed'),
                  notes_chats=st.get('threads'),
                  chats_ads=src('ads', 'chats'), chats_organic=src('organic', 'chats'), chats_admin=src('admin_followup', 'chats'),
                  close_pct_ads=pct(src('ads', 'closed') or 0, src('ads', 'leads') or 0),
                  close_pct_organic=pct(src('organic', 'closed') or 0, src('organic', 'leads') or 0),
                  close_pct_admin=pct(src('admin_followup', 'closed') or 0, src('admin_followup', 'leads') or 0),
                  sent_end_ads=src('ads', 's_end'), sent_end_organic=src('organic', 's_end'),
                  sent_end_admin=src('admin_followup', 's_end'))
        cm = (content.get('months') or {}).get(m) or {}
        csp = content.get('ad_spend') or {}
        for pf, k in CPF:
            fm['%s_posts' % k] = (cm.get(pf) or {}).get('posts')
            fm['%s_post_views' % k] = (cm.get(pf) or {}).get('views')
        fm['tiktok_ad_spend'] = ((csp.get('TikTok') or {}).get(m) or {}).get('spend')
        fm['youtube_ad_spend'] = ((csp.get('YouTube') or {}).get(m) or {}).get('spend')
        body = ['# เดือน %s %d' % (TH_ABBR[mo], y), '']
        if s:
            body.append('**Meta Ads** ใช้จ่าย %s บาท · เริ่มแชท %s · บาท/แชท %s · ปิด (ป้าย Meta) %s · บาท/การปิด %s' % (
                fmt(s), fmt(c), fmt(s / c, 1) if c else '-', fmt(b), fmt(s / b) if b else '-'))
        if f:
            body += ['', '**FB chat log** แชท %s · ปิดได้ %s · ลีดจากโฆษณาปิด %s%% · ลีดอื่นปิด %s%%' % (
                fmt(f.get('chats')), fmt(f.get('closed')), pct(f.get('ad_close', 0), f.get('ad_leads', 0)),
                pct(f.get('nonad_close', 0), f.get('nonad_leads', 0)))]
        if bs:
            body += ['', '## โฆษณา vs ไม่ใช่โฆษณา (คำนวณจากข้อความรายห้อง)', '',
                     '| ที่มา | แชท | ลีด | ปิด | ปิด/ลีด | อารมณ์ต้น | อารมณ์ท้าย |', '|---|---|---|---|---|---|---|']
            for k in ('ads', 'organic', 'admin_followup', 'unknown'):
                v = bs.get(k)
                if v:
                    body.append('| %s | %s | %s | %s | %s%% | %s | %s |' % (
                        SRC_TH[k], v['chats'], v['leads'], v['closed'], pct(v['closed'], v['leads']), v['s_start'], v['s_end']))
            mt = st.get('match') or {}
            if mt:
                tot = sum(mt.values())
                body += ['', 'จับคู่แชทโฆษณากับตัวโฆษณา: ' + ' · '.join(
                    '%s %d (%s%%)' % (k, v, pct(v, tot)) for k, v in sorted(mt.items(), key=lambda x: (-x[1], x[0])))]
        body += content_section(m, content)
        body += ['', '## โน้ตของฉันเดือนนี้', '- (จดสิ่งที่เกิดขึ้น เช่น เปลี่ยนครีเอทีฟ เปิดคอร์สใหม่ ช่วงสอบ)']
        put('Monthly/%s.md' % m, front(fm) + '\n' + '\n'.join(body))



# ---------------------------------------------------------------- ที่มาของข้อมูล (ลิงก์ชีต) + ไฟล์ตั้งต้น
SOURCES = {}


def sheet_link(title, sid):
    return '- [%s](https://docs.google.com/spreadsheets/d/%s/edit)' % (title, sid)


def write_sources(fb_files):
    fb = sorted(fb_files.items())
    seen, fb_links = set(), []
    for m, sid in reversed(fb):
        if sid not in seen:
            seen.add(sid)
            fb_links.append(sheet_link('FB Chat Log — %s %s' % (TH_ABBR[int(m[5:7])], m[:4]), sid))
    notes = {
        'FB chat log': ('แยกไฟล์รายเดือน ในโฟลเดอร์ Data Chat FB', fb_links, [
            'แท็บ **สรุปรายแชท**: 1 แถว = 1 แชท · คีย์ `Thread ID` (t_…) · กลุ่ม S0–S5, มาจากโฆษณา, ป้าย Meta, ได้รับราคา, ลูกค้าแจ้งจ่าย, หมวด',
            'แท็บ **ข้อความ part 1–3**: 1 แถว = 1 ข้อความ · เวลาไทย · ฝ่าย ลูกค้า/ธุรกิจ · ประเภท ลูกค้า/แอดมินพิมพ์เอง/สำเร็จรูป/ระบบ Meta',
            'แท็บ **สรุปภาพรวม**: ตัวเลขรวมเดือน รวมที่มาของแชท',
            'คอลัมน์ "มาจากโฆษณา" ในชีตจับแค่คำ "BIOPALM ติวเตอร์วิชาชีวะ" — vault นี้จับคู่ใหม่ด้วยข้อความต้อนรับทุกแบบ (ดู [[03 วิธีเชื่อมข้อมูล]])',
            'ระบบเขียนทับชีตทุกเช้า ห้ามพิมพ์โน้ตในชีต']),
        'IG chat log': ('ไฟล์เดียวทั้งปี ในโฟลเดอร์ Data Chat IG', [sheet_link(*x) for x in SOURCES.get('ig', [])], [
            'แท็บ **สรุปรายแชท ทุกเดือน** + **ข้อความดิบ (เดือน)** · ยังไม่ได้จับคู่กับโฆษณา (ขั้น 3 ในแผน)']),
        'LINE chat log': ('ไฟล์เดียวทั้งปี ในโฟลเดอร์ Data Chat Line', [sheet_link(*x) for x in SOURCES.get('line', [])], [
            'แท็บ **สรุปรายแชท (ทุกเดือน)** คีย์ `LINE user id` · **โน้ตลงทะเบียน (เดือน)** รหัสคอร์ส G + ยอดชำระ']),
        'Meta Ads': ('ไฟล์เดียว ทุกระดับ', [sheet_link(*x) for x in SOURCES.get('meta', [])], [
            'คีย์ `Campaign ID` → `Ad set ID` → `Ad ID` (ไม่เปลี่ยนแม้เปลี่ยนชื่อ)',
            'แท็บที่ใช้: แคมเปญ, โฆษณาและครีเอทีฟ, แคมเปญรายเดือน, โฆษณารายเดือน, โฆษณารายวัน, ข้อความต้อนรับแชทของโฆษณา, บัญชีโฆษณา',
            '"การซื้อ" = ป้ายที่ทีมติดในกล่องข้อความ Meta · วันที่เป็นเวลา Los Angeles']),
    }
    for name, (desc, links, bullets) in notes.items():
        put('Sources/%s.md' % name, front(dict(type='source')) + '\n# แหล่งข้อมูล: %s\n%s\n\n%s\n\n%s' % (
            name, desc, '\n'.join(links) or '- (ไม่พบไฟล์)', '\n'.join('- ' + b for b in bullets)))


DEFAULT_TOPICS = {
    'ราคา': ['ราคา', 'ค่าเรียน', 'เท่าไร', 'เท่าไหร่', 'โปร', 'ส่วนลด', 'แพง'],
    'ตารางเรียน': ['ตาราง', 'กี่โมง', 'วันไหน', 'เริ่มเรียน', 'เรียนวัน'],
    'รูปแบบเรียน': ['ออนไลน์', 'online', 'onsite', 'ออนไซต์', 'เทป', 'ย้อนหลัง', 'ที่สถาบัน'],
    'ระดับชั้น': ['ม.1', 'ม.2', 'ม.3', 'ม.4', 'ม.5', 'ม.6', 'ป.6', 'ม. 1', 'ม. 2', 'ม. 3'],
    'การชำระเงิน': ['โอน', 'ผ่อน', 'บัตร', 'สลิป', 'ชำระ', 'จ่ายเงิน', 'วิธีจ่าย'],
    'สนามสอบ': ['mwit', 'kvis', 'สอวน', 'เตรียมอุดม', 'กำเนิดวิทย์', 'สอบเข้า'],
    'ลังเล-ขอคิดก่อน': ['ขอคิดก่อน', 'ขอปรึกษา', 'ผู้ปกครอง', 'ไว้ก่อน', 'ยังไม่แน่ใจ', 'ขอดูก่อน'],
}


def seed_files():
    out = {}
    cfg = dict(type='config')
    cfg.update({k: v for k, v in DEFAULT_SENT.items()})
    out['Config/คำ sentiment.md'] = front(cfg) + '\n' + '\n'.join([
        '# คำที่ใช้วัดอารมณ์ลูกค้า (แก้ได้)', '',
        '- ต่อข้อความลูกค้า: เจอคำ positive +1 · negative −1 · hesitant −0.5 · มีคำใน negation นำหน้า ("ไม่แพง") กลับเครื่องหมาย · รวมแล้วอยู่ในช่วง −1 ถึง 1',
        '- อารมณ์ต้น = เฉลี่ยข้อความแรก ๆ (สูงสุด 3) · อารมณ์ท้าย = เฉลี่ยข้อความท้าย ๆ · เปลี่ยนไป = ท้าย − ต้น',
        '- ไม่นับ: ปุ่มที่ลูกค้ากด รูป/ไฟล์ ข้อความสำเร็จรูป ข้อความแอดมิน', '',
        'แก้คำในกล่อง properties ด้านบน แล้วกด Ctrl/Cmd+P → Git: Commit-and-sync — รอบเช้าถัดไประบบใช้คำชุดใหม่'])
    for t, kws in DEFAULT_TOPICS.items():
        out['Topics/%s.md' % t] = front(dict(type='topic', keywords=kws)) + '\n' + '\n'.join([
            '# เรื่องที่ลูกค้าถาม: ' + t, '',
            'คำที่ใช้จับอยู่ใน properties `keywords` ด้านบน (แก้ได้ แล้ว Commit-and-sync)', '',
            '## แชทที่พูดถึงเรื่องนี้', '```dataview',
            'TABLE WITHOUT ID file.link AS "แชท", month AS "เดือน", source AS "ที่มา", ad AS "โฆษณา", closed AS "ปิด", sent_delta AS "อารมณ์เปลี่ยน"',
            'FROM "Chats"', 'WHERE contains(topics, this.file.link)', 'SORT first_at DESC', 'LIMIT 100', '```', '',
            '## ปิดได้กี่ราย เมื่อลูกค้าถามเรื่องนี้ แยกตามที่มา', '```dataview',
            'TABLE WITHOUT ID key AS "ที่มา", length(rows) AS "แชท", length(filter(rows, (r) => r.closed)) AS "ปิดได้"',
            'FROM "Chats"', 'WHERE contains(topics, this.file.link)', 'GROUP BY source', '```'])
    out['Templates/บันทึกการทดลอง.md'] = '---\ntype: experiment\ndate: "{{date}}"\nad:\nhypothesis:\nresult:\n---\n# ทดลอง: \n\n- สมมติฐาน: \n- เปลี่ยนอะไร: \n- วัดผลด้วย: บาท/การปิด 3 เดือน, ปิด% จาก log, อารมณ์ท้าย\n- ผล: \n'
    out['Bases/จัดอันดับโฆษณา.base'] = '\n'.join([
        'filters:', '  and:', '    - file.inFolder("Ads/Ads")', 'formulas:', '  chats_per_close: chats_meta / purchases_meta',
        'properties:', '  formula.chats_per_close:', '    displayName: แชทต่อ 1 การปิด', 'views:', '  - type: table',
        '    name: บาทต่อการปิด 3 เดือน (น้อย = ดี)', '    order:', '      - file.name', '      - campaign', '      - welcome',
        '      - spend_3m', '      - chats_3m', '      - purchases_3m', '      - cost_per_purchase_3m', '      - chats_matched',
        '      - sent_end_avg', '      - formula.chats_per_close', '    sort:', '      - property: cost_per_purchase_3m',
        '        direction: ASC', ''])
    out['Bases/แคมเปญ.base'] = '\n'.join([
        'filters:', '  and:', '    - file.inFolder("Ads/Campaigns")', 'views:', '  - type: table', '    name: แคมเปญทั้งหมด',
        '    order:', '      - file.name', '      - area', '      - platform', '      - course', '      - spend', '      - purchases_meta',
        '      - cost_per_purchase', '      - spend_3m', '      - cost_per_purchase_3m', '      - chats_matched', '    sort:',
        '      - property: spend', '        direction: DESC', ''])
    out['บันทึกของฉัน/อ่านก่อน.md'] = '# บันทึกของฉัน\nโฟลเดอร์นี้ระบบอัตโนมัติไม่แตะ จดอะไรก็ได้ แล้วพิมพ์ `[[` เพื่อลิงก์ไปหาแคมเปญ/โฆษณา/เดือน/แชท\n'
    return out


# ---------------------------------------------------------------- GitHub (Composio) — โหมด api
def gh(slug, args):
    a = dict(args)
    a.update(owner=OWNER, repo=REPO)
    return call(slug, a)


def api_tree():
    """รายชื่อไฟล์ทั้งหมดใน vault + blob sha · ลองแบบ recursive ก่อน ถ้าคำตอบใหญ่เกิน (Composio ส่งกลับได้ราว 10k token)
    ไล่ทีละโฟลเดอร์ · โฟลเดอร์ที่รายชื่อยาวเกินจนอ่านไม่ได้ → คืนใน unknown (เขียนทับทุกไฟล์ในนั้น และไม่ลบไฟล์ในนั้น)"""
    try:
        d = gh('GITHUB_GET_A_TREE', {'tree_sha': BRANCH, 'recursive': True})
        if isinstance(d.get('tree'), list) and not d.get('truncated'):
            return {e['path']: e['sha'] for e in d['tree'] if e.get('type') == 'blob' and e.get('path')}, []
    except ToolError as e:
        if 'TOO_LARGE' not in str(e):
            raise
    out, unknown = {}, []

    def walk(item):
        sha, prefix = item
        try:
            d = gh('GITHUB_GET_A_TREE', {'tree_sha': sha, 'recursive': False})
        except ToolError as e:
            if 'TOO_LARGE' in str(e) and prefix:
                unknown.append(prefix)
                return []
            raise
        subs = []
        for e in d.get('tree') or []:
            pth = prefix + str(e.get('path') or '')
            if e.get('type') == 'blob':
                out[pth] = e.get('sha')
            elif e.get('type') == 'tree':
                subs.append((e.get('sha'), pth + '/'))
        return subs

    frontier = [(BRANCH, '')]
    with ThreadPoolExecutor(4) as ex:
        while frontier:
            frontier = [x for subs in ex.map(walk, frontier) for x in subs]
    return out, sorted(unknown)


def api_read(path):
    d = gh('GITHUB_GET_REPOSITORY_CONTENT', {'path': path, 'ref': BRANCH})
    c = d.get('content')
    enc = 'base64'
    if isinstance(c, dict):
        enc = c.get('encoding') or enc
        c = c.get('content')
    if not isinstance(c, str):
        return None
    if enc == 'base64':
        return base64.b64decode(c.replace('\n', '')).decode('utf-8')
    return c


PREFETCH_FAILED = set()


def api_prefetch(tree):
    """ดึงไฟล์ที่ผู้ใช้แก้ได้ (Config, Topics) + สถิติแชทสะสม ลงโฟลเดอร์ชั่วคราว ให้โค้ดส่วนอื่นอ่านเหมือนโหมด git"""
    want = [p for p in tree if p == 'Config/คำ sentiment.md' or (p.startswith('Topics/') and p.endswith('.md'))
            or (p.startswith(STATE_DIR + '/') and p.endswith('.json'))]
    for p in want:
        try:
            t = api_read(p)
        except ToolError as e:
            PREFETCH_FAILED.add(p)
            warn('อ่าน %s จาก vault ไม่ได้ (%s)' % (p, str(e)[:60]))
            continue
        if t is None:
            continue
        fp = os.path.join(VAULT, p)
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with open(fp, 'w', encoding='utf-8') as fh:
            fh.write(t)
    log('vault: ไฟล์เดิม %d · ดึง config/state %d ไฟล์' % (len(tree), len(want)))


def blob_sha(text):
    b = text.encode('utf-8')
    return hashlib.sha1(b'blob %d\0' % len(b) + b).hexdigest()


def is_generated(path, processed, keep_from):
    if path in ('05 สถานะระบบ.md', '.vault/chat_stats.json'):        # chat_stats.json = รูปแบบเดิม (ไฟล์เดียว ใหญ่เกินอ่านกลับ)
        return True
    m = re.match(r'^%s/(\d{4}-\d{2})/' % re.escape(STATE_DIR), path)
    if m:
        return m.group(1) not in BAD_STATE_MONTHS
    if path.startswith(('Ads/', 'Monthly/', 'Sources/')):
        return True
    m = re.match(r'^Chats/FB/(\d{4}-\d{2})/', path)
    if m:
        return m.group(1) in processed or (keep_from is not None and m.group(1) < keep_from)
    return False


def api_commit(tree, unknown, processed, keep_from):
    """unknown = โฟลเดอร์ที่อ่านรายชื่อไม่ได้: ไฟล์ในนั้นไม่มีใน tree จึงถูกเขียนทับทุกไฟล์ และไม่มีการลบ"""
    up = [(p, t) for p, t in sorted(FILES.items()) if tree.get(p) != blob_sha(t)]
    dels = sorted(p for p in tree if p not in FILES and is_generated(p, processed, keep_from))
    for pre in ('Ads/', 'Monthly/'):                 # กันพลาด: ถ้ารอบนี้สร้างได้น้อยกว่าครึ่งของของเดิม ไม่ลบโฟลเดอร์นั้น
        old = sum(1 for p in tree if p.startswith(pre))
        new = sum(1 for p in FILES if p.startswith(pre))
        if old >= 20 and new < old / 2:
            dels = [p for p in dels if not p.startswith(pre)]
            warn('โน้ตใน %s รอบนี้น้อยผิดปกติ (%d จากเดิม %d) — ไม่ลบไฟล์เก่าในโฟลเดอร์นี้' % (pre, new, old))
    log('commit: เปลี่ยน %d ไฟล์ · ลบ %d ไฟล์' % (len(up), len(dels)))
    if DRY_RUN or not (up or dels):
        return 0
    batches, cur, size = [], [], 0
    for p, t in up:
        n = len(t.encode('utf-8'))
        if cur and (len(cur) >= 150 or size + n > 700000):
            batches.append(cur)
            cur, size = [], 0
        cur.append((p, t))
        size += n
    if cur:
        batches.append(cur)
    del_batches = [dels[i:i + 300] for i in range(0, len(dels), 300)]
    jobs = [(b, []) for b in batches] + [([], d) for d in del_batches]
    stamp = datetime.now(BKK).strftime('%Y-%m-%d %H:%M')
    done = 0
    for i, (b, d) in enumerate(jobs, 1):
        args = {'branch': BRANCH, 'message': 'vault: อัปเดตอัตโนมัติ %s (%d/%d)' % (stamp, i, len(jobs))}
        if b:
            args['upserts'] = [{'path': p, 'content': t, 'encoding': 'utf-8'} for p, t in b]
        if d:
            args['deletes'] = d
        for attempt in range(4):
            try:
                gh('GITHUB_COMMIT_MULTIPLE_FILES', args)
                done += len(b) + len(d)
                break
            except ToolError as e:
                if 'TOO_LARGE' in str(e):
                    # commit สำเร็จแล้ว (Composio ตอบ successful) แค่คำตอบรายชื่อไฟล์ยาวเกินจะส่งกลับ — ห้ามส่งซ้ำ
                    done += len(b) + len(d)
                    break
                if attempt == 3:
                    raise
                log('  commit ส่วน %d ไม่ผ่าน ลองใหม่ (%s)' % (i, type(e).__name__))
                time.sleep(15 * (attempt + 1))
        time.sleep(2)
    log('commit เสร็จ %d ส่วน (%d ไฟล์)' % (len(jobs), done))
    return done

# ---------------------------------------------------------------- main
def months_to_process(files):
    env = (os.environ.get('FB_MONTHS') or '').strip()
    if env:
        return [m.strip() for m in env.split(',') if re.match(r'^\d{4}-\d{2}$', m.strip())]
    cur = NOW.strftime('%Y-%m')
    out = [cur]
    if NOW.day <= 3:
        out.insert(0, (NOW.replace(day=1) - timedelta(days=1)).strftime('%Y-%m'))
    return [m for m in out if m in files]


def clean_generated(months):
    """ลบโฟลเดอร์ที่ระบบสร้างใหม่ทั้งหมด (Ads, Monthly) + โน้ตแชทเดือนที่เก่ากว่า KEEP_CHAT_MONTHS
    โน้ตแชทของเดือนที่จะประมวลผล ลบทีหลังเมื่ออ่านชีตเดือนนั้นสำเร็จแล้วเท่านั้น"""
    for d in ('Ads', 'Monthly'):
        shutil.rmtree(os.path.join(VAULT, d), ignore_errors=True)
    base = os.path.join(VAULT, 'Chats', 'FB')
    if os.path.isdir(base) and months:
        y, m = int(max(months)[:4]), int(max(months)[5:7])
        for _ in range(KEEP_CHAT_MONTHS - 1):
            y, m = (y, m - 1) if m > 1 else (y - 1, 12)
        keep_from = '%04d-%02d' % (y, m)
        for d in os.listdir(base):
            if re.match(r'^\d{4}-\d{2}$', d) and d < keep_from:
                shutil.rmtree(os.path.join(base, d), ignore_errors=True)
    sample = os.path.join(base, '2026-10', 'ตัวอย่างแชท (สมมติ).md')
    if os.path.exists(sample):
        os.remove(sample)


def main():
    t0 = time.time()
    if not os.path.isdir(VAULT):
        raise SystemExit('ไม่พบโฟลเดอร์ vault: ' + VAULT)
    tree, unknown = None, []
    if MODE == 'api':
        tree, unknown = api_tree()
        if unknown:
            log('vault: โฟลเดอร์ที่รายชื่อยาวเกินอ่าน %d โฟลเดอร์ → เขียนทับทั้งโฟลเดอร์' % len(unknown))
        api_prefetch(tree)
    log('โหมด: %s%s' % (MODE, ' (dry run)' if DRY_RUN else ''))
    state = load_state()
    cfg, topics = load_config()
    log('config: คำบวก %d · คำลบ %d · ลังเล %d · หัวข้อ %d' % (len(cfg['positive']), len(cfg['negative']),
                                                            len(cfg['hesitant']), len(topics)))
    M = load_meta()
    camps, ads, wg = build_ads_model(M)
    am, cm, _, last3 = monthly_ad_stats(M)
    STATUS['steps'].append('Meta: แคมเปญ %d · โฆษณา %d · กลุ่มข้อความต้อนรับ %d' % (len(camps), len(ads), len(wg)))

    files = find_fb_files()
    fbov = load_fb_overviews(files)
    line, ig = load_line_ig(NOW.year)
    log('FB ไฟล์ %d เดือน · สรุปภาพรวม %d เดือน · LINE %d · IG %d' % (len(files), len(fbov), len(line), len(ig)))

    eq, rx_list, labels = build_matchers(ads)
    processed = []
    notes_total = 0
    months = months_to_process(files)
    keep_from = None
    if months:
        y, m = int(max(months)[:4]), int(max(months)[5:7])
        for _ in range(KEEP_CHAT_MONTHS - 1):
            y, m = (y, m - 1) if m > 1 else (y - 1, 12)
        keep_from = '%04d-%02d' % (y, m)
    if MODE == 'git':
        clean_generated(months)
    for mkey in months:
        if mkey not in files:
            warn('ไม่พบไฟล์ FB Chat Log เดือน %s' % mkey)
            continue
        try:
            summ, threads = load_fb_month(files[mkey], mkey)
        except ToolError as e:
            warn('ประมวลผลแชท FB %s ไม่สำเร็จ — โน้ตเดือนนี้คงของเดิมไว้ (%s)' % (mkey, str(e)[:80]))
            continue
        if MODE == 'git':
            shutil.rmtree(os.path.join(VAULT, 'Chats', 'FB', mkey), ignore_errors=True)
        res = analyse_threads(mkey, summ, threads, ads, eq, rx_list, labels, M['daily'], cfg, topics)
        st = month_chat_stats(res)
        state['months'][mkey] = st
        BAD_STATE_MONTHS.discard(mkey)            # เดือนนี้คำนวณใหม่ครบแล้ว เขียนทับได้
        n = write_chat_notes(mkey, res, ads, camps)
        notes_total += n
        processed.append(mkey)
        mt = st['match']
        STATUS['steps'].append('FB %s: %d ห้อง · โน้ตลีด %d · แชทโฆษณา %d (ตรงตัว %d · แคมเปญ %d · กลุ่มข้อความ %d · ไม่รู้ตัวโฆษณา %d)' % (
            mkey, st['threads'], n, sum(mt.values()), mt.get('exact', 0), mt.get('campaign', 0), mt.get('welcome', 0),
            mt.get('ad-unknown', 0)))
        log(STATUS['steps'][-1])

    chat_tot = ad_chat_totals(state)
    write_ads(camps, ads, wg, am, cm, last3, chat_tot)
    content = load_content()
    if content:
        STATUS['steps'].append('คอนเทนต์รายเดือน (FB/IG/TikTok/YouTube) จากงาน obsidian-content รอบ %s · %d เดือน' % (
            content.get('pulled') or '-', len(content.get('months') or {})))
    write_months(M, fbov, line, ig, state, content)
    write_sources(files)
    for rel, text in seed_files().items():
        if MODE == 'api':
            exists = rel in tree or any(rel.startswith(u) for u in unknown)
        else:
            exists = os.path.exists(os.path.join(VAULT, rel))
        if not exists:
            put(rel, text)

    STATUS['finished'] = datetime.now(BKK).strftime('%Y-%m-%d %H:%M')
    lines = ['# สถานะระบบ', '', 'อัปเดตอัตโนมัติโดย GitHub Actions (admin-hub → obsidian-vault) — ไฟล์นี้ระบบเขียนทับทุกรอบ', '',
             '- เริ่ม: %s · เสร็จ: %s (%.0f วินาที)' % (STATUS['started'], STATUS['finished'], time.time() - t0),
             '- เดือนแชทที่ประมวลผลรอบนี้: %s' % (', '.join(processed) or '-'),
             '- ช่วง 3 เดือนล่าสุดของ Meta: %s' % (', '.join(last3) or '-'),
             '- คำขอไป Composio %d · ลดขนาดช่วงอ่าน %d · พักรอโควตา Google %d · ลองใหม่ %d' % (
                 STATS['calls'], STATS['shrink'], STATS['quota_waits'], STATS['retries']),
             '- โฟลเดอร์ใน vault ที่รายชื่อยาวเกินอ่าน (เขียนทับทั้งโฟลเดอร์ ไม่ลบไฟล์เก่า): %s' % (', '.join(unknown) or '-'), '']
    lines += ['- ' + s for s in STATUS['steps']]
    if STATUS['warnings']:
        lines += ['', '## คำเตือน'] + ['- ' + w for w in STATUS['warnings']]
    put('05 สถานะระบบ.md', front(dict(type='status', updated=STATUS['finished'])) + '\n' + '\n'.join(lines))
    save_state(state)

    if MODE == 'git':
        for rel, text in FILES.items():
            p = os.path.join(VAULT, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w', encoding='utf-8') as fh:
                fh.write(text)
    else:
        api_commit(tree, unknown, set(processed), keep_from)
    kinds = Counter(rel.split('/')[0] if '/' in rel else 'root' for rel in FILES)
    log('เขียนไฟล์ %d (%s) · โน้ตแชท %d · %.0f วินาที' % (
        len(FILES), ', '.join('%s %d' % kv for kv in sorted(kinds.items())), notes_total, time.time() - t0))
    if STATUS['warnings']:
        log('คำเตือน %d รายการ (ดู 05 สถานะระบบ.md ใน vault)' % len(STATUS['warnings']))


if __name__ == '__main__':
    try:
        main()
    finally:
        log('คำขอ %d · ลดขนาดช่วงอ่าน %d · พักรอโควตา %d · ลองใหม่ %d' % (
            STATS['calls'], STATS['shrink'], STATS['quota_waits'], STATS['retries']))

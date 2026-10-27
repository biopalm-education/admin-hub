# -*- coding: utf-8 -*-
"""Insight แชท (Biopalm) — อ่านแชท FB / LINE / IG ทั้งปีจากข้อมูลแดชบอร์ด admin-hub (data/*.json ถอดด้วย secret ADMIN_SECRET
ของ repo เอง) + โน้ตลงทะเบียน LINE จากชีต แล้ววิเคราะห์ (ผปค/นักเรียน, scenario, ความเร็วตอบ,
ข้อความกับผลลัพธ์, bundle, คำถามที่พบบ่อย) แล้วเขียนผลสรุปลง vault private (.vault/insight/)

รันใน GitHub Actions (.github/workflows/obsidian-insight.yml) — repo admin-hub เป็น public:
  * ข้อมูลแชท: data/*.json ใน repo นี้ ถอดรหัสในเครื่อง runner ด้วย ADMIN_SECRET (secret เดิมของงาน refresh-dashboard)
  * โน้ตลงทะเบียน LINE: อ่านชีตอย่างเดียว ผ่าน Composio (tools/meta_ads/composio_shim.py ตัวเดิม · secret COMPOSIO_API_KEY เดิม)
  * เขียนเฉพาะ repo private biopalm-insight ผ่าน Composio GitHub (บัญชีเดียวกับ obsidian-vault)
  * log พิมพ์แค่ชื่อขั้น / สถานะ / จำนวน — ไม่พิมพ์ชื่อหรือข้อความลูกค้า ไม่พิมพ์ข้อความ error ดิบ ไม่อัปโหลด artifact
  * ข้อมูลดิบอยู่แค่ในเครื่อง runner ชั่วคราว (ลบเมื่อจบงาน)
"""
import os, sys, re, json, time, gzip, hashlib, shutil, subprocess, tempfile, traceback
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'meta_ads'))
from composio_shim import run_composio_tool

WORK = os.environ.get('INSIGHT_WORK') or tempfile.mkdtemp(prefix='insight-')
VAULT_REPO = os.environ.get('VAULT_REPO') or 'biopalm-education/biopalm-insight'
OWNER, REPO = VAULT_REPO.split('/')
YEAR = os.environ.get('INSIGHT_YEAR') or '2026'
DRY = (os.environ.get('DRY_RUN') or '').strip().lower() in ('1', 'true', 'yes')
TH_ABBR = ['', 'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']
QUOTA = re.compile(r'429|quota exceeded|rate.?limit|too many requests|resource.?exhausted', re.I)
LOG = []          # private log (goes to the vault only)
STAT = {'calls': 0, 'shrink': 0, 'quota_waits': 0}


def say(msg):
    """public log: counts / step names only"""
    print(msg, flush=True)
    LOG.append(msg)


class ToolError(Exception):
    pass


def call(slug, args):
    err = ''
    for attempt in range(8):
        res, err = run_composio_tool(slug, args)
        if not err:
            STAT['calls'] += 1
            return (res or {}).get('data') or {}
        err = str(err)
        if 'TOO_LARGE' in err or attempt == 7:
            break
        if QUOTA.search(err):
            STAT['quota_waits'] += 1
            time.sleep(40 + 20 * attempt)
            continue
        time.sleep(10 * (attempt + 1))
    raise ToolError('TOO_LARGE' if 'TOO_LARGE' in err else 'call failed')


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
    out = []
    for s in d.get('sheets') or []:
        p = s.get('properties') or {}
        g = p.get('gridProperties') or {}
        out.append((p.get('title'), int(g.get('rowCount') or 0), int(g.get('columnCount') or 26)))
    return out


def read_cols(sid, tab, first, last, a, z, chunk, cap):
    """rows first..last, columns a..z (1-based) — TOO_LARGE halves the window, 3 successes in a row grow it back"""
    out = []
    r, size, streak = first, chunk, 0
    q = tab.replace("'", "''")
    while r <= last:
        b = min(last, r + size - 1)
        try:
            part = batch_get(sid, ["'%s'!%s%d:%s%d" % (q, col_letter(a), r, col_letter(z), b)])[0]
        except ToolError as e:
            if 'TOO_LARGE' in str(e) and b > r:
                cap = min(cap, b - r)
                size, streak = max(1, (b - r + 1) // 2), 0
                STAT['shrink'] += 1
                continue
            raise
        n = b - r + 1
        part = list(part)[:n] + [[]] * (n - len(part))
        for row in part:
            out.append([(row[j] if j < len(row) else '') for j in range(z - a + 1)])
        r = b + 1
        streak += 1
        if streak >= 3 and size < cap:
            size, streak = min(cap, size * 3 // 2 + 1), 0
    return out


TEXT_COLS = ('ข้อความ', 'ข้อความโน้ต')


def read_tab(sid, tab, nrows, ncols):
    head = batch_get(sid, ["'%s'!A1:%s1" % (tab.replace("'", "''"), col_letter(max(1, ncols)))])[0]
    header = [str(h).strip() for h in (head[0] if head else [])]
    while header and not header[-1]:
        header.pop()
    nc = len(header)
    if nc == 0 or nrows < 2:
        return [header]
    text = [i + 1 for i, h in enumerate(header) if h in TEXT_COLS]
    light = [i for i in range(1, nc + 1) if i not in text]
    cols = {}
    runs = []                                    # contiguous runs of light columns
    for i in light:
        if runs and i == runs[-1][1] + 1:
            runs[-1][1] = i
        else:
            runs.append([i, i])
    for a, z in runs:
        block = read_cols(sid, tab, 2, nrows, a, z, 3000, 6000)
        for j in range(a, z + 1):
            cols[j] = [row[j - a] for row in block]
    for i in text:
        block = read_cols(sid, tab, 2, nrows, i, i, 800, 1600)
        cols[i] = [row[0] for row in block]
    n = nrows - 1
    rows = [header]
    for k in range(n):
        row = [str(cols[j][k]) if k < len(cols[j]) else '' for j in range(1, nc + 1)]
        if any(v.strip() for v in row):
            rows.append(row)
    return rows


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


def search(query):
    d = call('GOOGLESHEETS_SEARCH_SPREADSHEETS', {'query': query, 'search_type': 'name', 'max_results': 100})
    return [(s.get('name') or '', s.get('id'), s.get('modifiedTime') or '') for s in (d.get('spreadsheets') or [])]


def pick_sheets():
    fb = {}
    for name, sid, mod in search('Biopalm FB Chat Log'):
        if not name.startswith('Biopalm FB Chat Log'):
            continue
        for k in month_keys_from_title(name):
            if k.startswith(YEAR) and (k not in fb or mod > fb[k][1]):
                fb[k] = (sid, mod, name)
    sheets = {}
    for k, (sid, mod, name) in fb.items():
        key = 'fb-' + '_'.join(month_keys_from_title(name))
        sheets[key] = sid
    for prefix, key in (('Biopalm LINE Chat Log', 'line-' + YEAR), ('Biopalm IG Chat Log', 'ig-' + YEAR)):
        cand = [(mod, sid) for name, sid, mod in search(prefix) if name.strip() == '%s — %s' % (prefix, YEAR)]
        if cand:
            sheets[key] = max(cand)[1]
    return sheets


def wanted(key, tab):
    # แชทมาจากข้อมูลแดชบอร์ดแล้ว — จากชีตเอาแค่โน้ตลงทะเบียน LINE (รหัสคอร์ส G)
    return key.startswith('line') and tab.startswith('โน้ตลงทะเบียน')


def pull():
    raw = os.path.join(WORK, 'raw')
    os.makedirs(raw, exist_ok=True)
    sheets = pick_sheets()
    say('ชีตที่ใช้: FB %d ไฟล์ · LINE %d · IG %d' % (sum(1 for k in sheets if k.startswith('fb')),
                                                    sum(1 for k in sheets if k.startswith('line')),
                                                    sum(1 for k in sheets if k.startswith('ig'))))
    jobs = []
    for key, sid in sorted(sheets.items()):
        if not key.startswith('line'):
            continue
        for tab, nrows, ncols in tabs_of(sid):
            if wanted(key, tab):
                jobs.append((key, sid, tab, nrows, ncols))
    man = {}

    def one(job):
        key, sid, tab, nrows, ncols = job
        rows = read_tab(sid, tab, nrows, ncols)
        fn = '%s__%s.json.gz' % (key, hashlib.md5(tab.encode()).hexdigest()[:10])
        with gzip.open(os.path.join(raw, fn), 'wt', encoding='utf-8') as f:
            json.dump(rows, f, ensure_ascii=False)
        man[fn] = {'key': key, 'tab': tab, 'rows': len(rows)}
        return len(rows)

    with ThreadPoolExecutor(3) as ex:
        n = list(ex.map(one, jobs))
    json.dump(man, open(os.path.join(WORK, 'raw_manifest.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    say('อ่านชีตครบ %d แท็บ · %d แถว · คำขอ %d · ลดขนาดช่วง %d · พักรอโควตา %d' % (
        len(jobs), sum(n), STAT['calls'], STAT['shrink'], STAT['quota_waits']))


STEPS = ['mk_rules.py', 'build_db_hub.py', 'ex_cards.py', 'purchases.py', 'features.py', 'roles.py',
         'an1.py', 'an2.py', 'an3.py', 'summarize.py']
# masked chat samples for checking the rules by eye: only when asked (Run workflow -> samples), never on push
SAMPLES = os.environ.get('SAMPLES') == '1'
if SAMPLES:
    STEPS.append('samples.py')


def run_steps():
    for f in os.listdir(HERE):
        if f.endswith('.py') and f != 'run.py' or f == 'catalog.json':
            shutil.copy(os.path.join(HERE, f), WORK)
    for f in ('stage_rules.py', 'sample_links.py'):
        shutil.copy(os.path.join(ROOT, f), WORK)
    env = dict(os.environ, REPO_ROOT=ROOT, PYTHONIOENCODING='utf-8')
    for s in STEPS:
        t0 = time.time()
        p = subprocess.run([sys.executable, s], cwd=WORK, env=env, capture_output=True, text=True)
        LOG.append('---- %s rc=%d\n%s' % (s, p.returncode, (p.stdout or '')[-6000:]))
        if p.returncode != 0:
            # public log: only the exception class and the failing line of OUR script — never the message
            last = [l for l in (p.stderr or '').splitlines() if l.strip()]
            exc = last[-1].split(':')[0] if last else '?'
            where = [l for l in (p.stderr or '').splitlines() if 'File "' in l and s in l]
            line = re.search(r'line (\d+)', where[-1]).group(1) if where else '?'
            LOG.append('STDERR tail:\n' + '\n'.join(last[-30:]))
            say('ขั้น %s ล้มเหลว (%s ที่บรรทัด %s) หลัง %.0f วินาที' % (s, exc, line, time.time() - t0))
            return False
        say('ขั้น %s เสร็จ (%.0f วินาที)' % (s, time.time() - t0))
    return True


def commit(files, message):
    if DRY:
        say('DRY_RUN: ไม่ commit (%d ไฟล์)' % len(files))
        return
    args = {'owner': OWNER, 'repo': REPO, 'branch': 'main', 'message': message,
            'upserts': [{'path': p, 'content': t, 'encoding': 'utf-8'} for p, t in files.items()]}
    for attempt in range(4):
        try:
            call('GITHUB_COMMIT_MULTIPLE_FILES', args)
            say('commit ลง vault แล้ว %d ไฟล์' % len(files))
            return
        except ToolError as e:
            if 'TOO_LARGE' in str(e):
                say('commit ลง vault แล้ว %d ไฟล์ (คำตอบยาว)' % len(files))
                return
            if attempt == 3:
                raise
            time.sleep(15 * (attempt + 1))


def main():
    t0 = time.time()
    stamp = time.strftime('%Y-%m-%d %H:%M', time.gmtime(time.time() + 7 * 3600))
    ok = False
    try:
        try:
            pull()
        except Exception as e:                 # notes are optional (validation only)
            say('อ่านโน้ตลงทะเบียน LINE จากชีตไม่ได้ (%s) — ข้ามขั้นตรวจเทียบโน้ต' % type(e).__name__)
        ok = run_steps()
    except Exception as e:
        tb = traceback.extract_tb(e.__traceback__)
        where = next((('%s:%d' % (os.path.basename(f.filename), f.lineno)) for f in reversed(tb) if HERE in f.filename), '?')
        say('ล้มเหลว: %s ที่ %s' % (type(e).__name__, where))
        LOG.append(traceback.format_exc()[-4000:])
    files = {'.vault/insight/run_log.txt': 'รอบ %s · %s · %.0f วินาที\n\n' % (stamp, 'สำเร็จ' if ok else 'ไม่สำเร็จ', time.time() - t0) + '\n'.join(LOG)}
    for name in ('summary.json', 'samples.json') if SAMPLES else ('summary.json',):
        p = os.path.join(WORK, name)
        if ok and os.path.exists(p):
            files['.vault/insight/' + name] = open(p, encoding='utf-8').read()
    try:
        commit(files, 'insight: ผลวิเคราะห์แชท %s' % stamp)
    finally:
        shutil.rmtree(WORK, ignore_errors=True)
    if not ok:
        sys.exit(1)


if __name__ == '__main__':
    main()

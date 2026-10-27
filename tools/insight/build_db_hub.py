# -*- coding: utf-8 -*-
"""Build chat.db from the admin-hub dashboard data (data/*.json, decrypted with the repo secret ADMIN_SECRET).

Why: the dashboard data already holds every FB / IG / LINE message of the year with the corrected sender roles
(Meta source tags, fix_roles.py), and reading it takes seconds — reading the same rows from Google Sheets through
Composio MCP takes hours because each response is capped. LINE registration notes (G codes) are not in the
dashboard data, so those still come from the LINE sheet (raw/ from run.py, optional).
Never prints customer data. Output schema is the same as build_db.py (msg / linenote) plus role2 = role.
"""
import os, re, json, gzip, base64, hashlib, sqlite3, datetime as dt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = os.environ.get('REPO_ROOT', '.')
SECRET = (os.environ.get('ADMIN_SECRET') or '').strip()
if ':' not in SECRET:
    raise SystemExit('ADMIN_SECRET missing')
man = json.load(open(os.path.join(ROOT, 'manifest.json'), encoding='utf-8'))
key = hashlib.pbkdf2_hmac('sha256', SECRET.encode(), base64.b64decode(man['kdf']['s']), man['kdf']['n'], 32)
gcm = AESGCM(key)


def unseal(blob):
    raw = gcm.decrypt(base64.b64decode(blob['i']), base64.b64decode(blob['c']), None)
    if blob.get('z') == 'gzip':
        raw = gzip.decompress(raw)
    return json.loads(raw.decode('utf-8'))


unseal(man['check'])                       # wrong secret -> fails here
T0 = dt.datetime(2026, 1, 1)
YEAR = int(os.environ.get('INSIGHT_YEAR') or 2026)
PHONE = re.compile(r'(?<!\d)(?:\+?66|0)\d{1,2}[\s-]?\d{3}[\s-]?\d{3,4}(?!\d)')
EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+')
ACC = re.compile(r'166\s*-?\s*3\s*-?\s*63464\s*-?\s*6')


def nm_parts(n):
    n = str(n or '').strip()
    if not n or n in ('ผู้ใช้ Facebook',):
        return []
    return sorted(set([n] + [p for p in re.split(r'\s+', n) if len(p) >= 3]), key=len, reverse=True)


def mask(t, names):
    t = str(t or '').replace('\x01', '〔ชื่อ〕')
    t = ACC.sub('〔บัญชีBioPalm〕', t)
    t = EMAIL.sub('〔อีเมล〕', t)
    t = PHONE.sub('〔เบอร์〕', t)
    for n in names:
        if n and len(n) >= 3:
            t = t.replace(n, '〔ชื่อ〕')
    return t


def base(y, m):
    return int((dt.datetime(y, m, 1) - T0).total_seconds() // 60)


def txf(d):
    return lambda x: d[x] if isinstance(x, int) and 0 <= x < len(d) else (x if isinstance(x, str) else '')


DB = 'chat.db'
if os.path.exists(DB):
    os.remove(DB)
con = sqlite3.connect(DB)
cur = con.cursor()
cur.executescript('''
CREATE TABLE msg(ch TEXT, tid TEXT, mo INT, seq INT, t INT, role TEXT, lab TEXT, admin TEXT, txt TEXT, role2 TEXT);
CREATE TABLE linenote(tid TEXT, mo INT, t INT, author TEXT, gcodes TEXT, typ TEXT, tag TEXT, txt TEXT);
''')
files = man['files']
SEQ = {}


def nxt(k):
    SEQ[k] = SEQ.get(k, 0) + 1
    return SEQ[k]


FBROLE = {0: 'C', 1: 'H', 2: 'B', 3: 'S'}
fbm = sorted(k for k in files if re.match(r'^fb-%d-\d\d$' % YEAR, k))
for name in fbm:
    y, m = int(name[3:7]), int(name[8:10])
    obj = unseal(json.load(open(os.path.join(ROOT, files[name].lstrip('./')), encoding='utf-8')))
    tx = txf(obj.get('dict') or [])
    b = base(y, m)
    rows = []
    for c in obj.get('chats') or []:
        tid = 't_' + str(c[19])
        names = nm_parts(c[0])
        for msg in c[18]:
            role = FBROLE.get(msg[1], 'S')
            rows.append(('FB', tid, m, nxt(('FB', tid)), b + int(msg[0]), role, '', '', mask(tx(msg[2]), names), role))
    cur.executemany('INSERT INTO msg VALUES (?,?,?,?,?,?,?,?,?,?)', rows)
    con.commit()
    print('FB', name, 'chats', len(obj.get('chats') or []), 'msgs', len(rows), flush=True)
    del obj, rows

if 'ig-all' in files:
    ig = unseal(json.load(open(os.path.join(ROOT, files['ig-all'].lstrip('./')), encoding='utf-8')))
    tx = txf(ig.get('dict') or [])
    IGROLE = {0: 'C', 1: 'H', 2: 'B', 3: 'B'}
    n = 0
    for mo in sorted(ig.get('months') or {}):
        if not mo.startswith(str(YEAR)):
            continue
        y, m = int(mo[:4]), int(mo[5:7])
        b = base(y, m)
        rows = []
        for c in (ig['months'][mo].get('leads') or []):
            tid = 'ig_' + str(c[19])
            names = nm_parts(c[0])
            for msg in c[18]:
                role = IGROLE.get(msg[1], 'B')
                rows.append(('IG', tid, m, nxt(('IG', tid)), b + int(msg[0]), role, '', '', mask(tx(msg[2]), names), role))
        cur.executemany('INSERT INTO msg VALUES (?,?,?,?,?,?,?,?,?,?)', rows)
        n += len(rows)
    con.commit()
    print('IG msgs', n, flush=True)
    del ig

lnm = sorted(k for k in files if re.match(r'^line-%d-\d\d$' % YEAR, k))
for name in lnm:
    y, m = int(name[5:9]), int(name[10:12])
    obj = unseal(json.load(open(os.path.join(ROOT, files[name].lstrip('./')), encoding='utf-8')))
    tx = txf(obj.get('dict') or [])
    rows = []
    for r in obj.get('rooms') or []:
        tid = str(r.get('id'))
        names = nm_parts(r.get('n'))
        for e in r.get('tr') or []:
            ts, w, x = e[0], e[1], e[2]
            try:
                d = dt.datetime.strptime('%d-%s' % (y, ts), '%Y-%m-%d %H:%M')
            except ValueError:
                continue
            t = int((d - T0).total_seconds() // 60)
            role = 'C' if w == 'C' else ('B' if w == 'B' else 'H')
            rows.append(('LINE', tid, m, nxt(('LINE', tid)), t, role, '', '' if role != 'H' else str(w), mask(tx(x), names), role))
    cur.executemany('INSERT INTO msg VALUES (?,?,?,?,?,?,?,?,?,?)', rows)
    con.commit()
    print('LINE', name, 'rooms', len(obj.get('rooms') or []), 'msgs', len(rows), flush=True)
    del obj, rows

# LINE registration notes (from the sheet, pulled by run.py) — optional
MON = {'ม.ค.': 1, 'ก.พ.': 2, 'มี.ค.': 3, 'เม.ย.': 4, 'พ.ค.': 5, 'มิ.ย.': 6, 'ก.ค.': 7, 'ส.ค.': 8, 'ก.ย.': 9, 'ต.ค.': 10, 'พ.ย.': 11, 'ธ.ค.': 12}
nn = 0
if os.path.exists('raw_manifest.json'):
    rm = json.load(open('raw_manifest.json', encoding='utf-8'))
    for fn, meta in rm.items():
        if not meta['tab'].startswith('โน้ตลงทะเบียน'):
            continue
        mo = MON.get(meta['tab'].split(' ')[1], 0)
        rows = json.load(gzip.open(os.path.join('raw', fn), 'rt', encoding='utf-8'))
        for r in rows[1:]:
            r = list(r) + [''] * (10 - len(r))
            try:
                t = int((dt.datetime.strptime(r[3] + ' ' + r[4], '%Y-%m-%d %H:%M') - T0).total_seconds() // 60)
            except Exception:
                t = None
            cur.execute('INSERT INTO linenote VALUES (?,?,?,?,?,?,?,?)', (r[1], mo, t, r[5], r[6], r[7], r[8], mask(r[9], nm_parts(r[0]))))
            nn += 1
    con.commit()
print('LINE notes', nn, flush=True)
cur.execute('CREATE INDEX i1 ON msg(ch,tid,t,seq)')
con.commit()
for q in ['SELECT ch,COUNT(*),COUNT(DISTINCT tid) FROM msg GROUP BY ch', "SELECT ch,role,COUNT(*) FROM msg GROUP BY ch,role"]:
    print(q, cur.execute(q).fetchall(), flush=True)
print('DONE', flush=True)

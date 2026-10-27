# -*- coding: utf-8 -*-
import json, gzip, os, re, sqlite3, datetime as dt, hashlib, sys
RAW='raw'; DB='chat.db'
man=json.load(open('raw_manifest.json'))
MON={'ม.ค.':1,'ก.พ.':2,'มี.ค.':3,'เม.ย.':4,'พ.ค.':5,'มิ.ย.':6,'ก.ค.':7,'ส.ค.':8,'ก.ย.':9,'ต.ค.':10,'พ.ย.':11,'ธ.ค.':12}
T0=dt.datetime(2026,1,1)
def mins(d): return int((d-T0).total_seconds()//60)
PHONE=re.compile(r'(?<!\d)(?:\+?66|0)\d{1,2}[\s-]?\d{3}[\s-]?\d{3,4}(?!\d)')
EMAIL=re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+')
ACC=re.compile(r'166\s*-?\s*3\s*-?\s*63464\s*-?\s*6')
def mask(t, names):
    t=str(t or '')
    t=ACC.sub('〔บัญชีBioPalm〕',t)
    t=EMAIL.sub('〔อีเมล〕',t); t=PHONE.sub('〔เบอร์〕',t)
    for n in names:
        if n and len(n)>=3: t=t.replace(n,'〔ชื่อ〕')
    return t
def nm_parts(n):
    n=str(n or '').strip()
    if not n or n in ('ผู้ใช้ Facebook',): return []
    parts=[n]+[p for p in re.split(r'\s+',n) if len(p)>=3]
    return sorted(set(parts),key=len,reverse=True)
def h(s): return hashlib.sha1(str(s).encode()).hexdigest()[:12]
if os.path.exists(DB): os.remove(DB)
con=sqlite3.connect(DB); cur=con.cursor()
cur.executescript('''
CREATE TABLE msg(ch TEXT, tid TEXT, mo INT, seq INT, t INT, role TEXT, lab TEXT, admin TEXT, txt TEXT);
CREATE TABLE fbsum(tid TEXT, mo INT, grp TEXT, from_ad TEXT, meta TEXT, day INT, hour INT, first_typed TEXT, stuck TEXT, team TEXT, price TEXT, pay TEXT, cat TEXT);
CREATE TABLE linesum(tid TEXT, mo INT, status TEXT, tags TEXT, owner TEXT, admins TEXT, nc INT, na INT, nb INT, first TEXT, note TEXT);
CREATE TABLE linenote(tid TEXT, mo INT, t INT, author TEXT, gcodes TEXT, typ TEXT, tag TEXT, txt TEXT);
CREATE TABLE igsum(tid TEXT, mo INT, grp TEXT, reason TEXT, cat TEXT);
''')
def load(fn): return json.load(gzip.open(os.path.join(RAW,fn),'rt',encoding='utf-8'))
names_fb={}
for fn,m in man.items():
    if m['key'].startswith('fb') and m['tab']=='สรุปรายแชท':
        rows=load(fn); hd=rows[0]; ix={k:i for i,k in enumerate(hd)}
        g=lambda r,k: (r[ix[k]] if k in ix and ix[k]<len(r) else '')
        for r in rows[1:]:
            if not r: continue
            tid=g(r,'Thread ID'); mo=MON.get(g(r,'เดือน'),0)
            names_fb[tid]=nm_parts(g(r,'ชื่อลูกค้า (FB)'))
            cur.execute('INSERT INTO fbsum VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',(tid,mo,g(r,'กลุ่ม'),g(r,'มาจากโฆษณา'),g(r,'ป้าย Meta'),
                int(g(r,'วันที่') or 0) if str(g(r,'วันที่')).isdigit() else 0, int(g(r,'ชม.') or 0) if str(g(r,'ชม.')).isdigit() else 0,
                g(r,'แอดมินพิมพ์เองครั้งแรก'),g(r,'ค้างไม่ตอบ'),g(r,'ทีมที่ตอบ'),g(r,'ได้รับราคา'),g(r,'ลูกค้าแจ้งจ่าย'),g(r,'หมวด (เกณฑ์ admin-hub)')))
con.commit(); print('fbsum ok', flush=True)
FBROLE={'ลูกค้า':'C','แอดมินพิมพ์เอง':'H','สำเร็จรูป':'B','ระบบ Meta':'S'}
for fn,m in sorted(man.items(), key=lambda x:x[1]['key']):
    if m['key'].startswith('fb') and m['tab'].startswith('ข้อความ'):
        rows=load(fn); batch=[]
        for r in rows[1:]:
            if not r or len(r)<9: r=(r or [])+['']*(9-len(r or []))
            mo=MON.get(r[0],0); tid=r[1]
            if not tid: continue
            mm=re.match(r'(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?',str(r[5]))
            t=mins(dt.datetime(2026,int(mm.group(2)),int(mm.group(1)),int(mm.group(3)),int(mm.group(4)))) if mm else None
            nm=names_fb.get(tid) or nm_parts(r[2])
            batch.append(('FB',tid,mo,int(float(r[4] or 0)),t,FBROLE.get(r[7],'?'),r[7],'',mask(r[8],nm)))
        cur.executemany('INSERT INTO msg VALUES (?,?,?,?,?,?,?,?,?)',batch); con.commit(); del rows,batch
        print('fb',m['key'],m['tab'],flush=True)
names_line={}
for fn,m in man.items():
    if m['key']=='line-2026' and m['tab'].startswith('สรุปรายแชท'):
        rows=load(fn); hd=rows[0]; ix={k:i for i,k in enumerate(hd)}
        g=lambda r,k: (r[ix[k]] if k in ix and ix[k]<len(r) else '')
        for r in rows[1:]:
            if not r: continue
            tid=g(r,'LINE user id'); mo=MON.get(str(g(r,'เดือน')).split(' ')[0],0)
            names_line[tid]=nm_parts(g(r,'ชื่อลูกค้า'))
            def iv(x):
                try: return int(float(x))
                except: return 0
            cur.execute('INSERT INTO linesum VALUES (?,?,?,?,?,?,?,?,?,?,?)',(tid,mo,g(r,'สถานะลีด'),g(r,'แท็กทั้งหมด'),g(r,'แอดมินที่ดูแล'),g(r,'แอดมินที่ตอบจริง'),
                iv(g(r,'ข้อความลูกค้า')),iv(g(r,'ข้อความแอดมิน')),iv(g(r,'ข้อความบอท')),g(r,'เริ่มคุย'),g(r,'หมายเหตุ')))
con.commit(); print('linesum ok',flush=True)
LROLE={'ลูกค้า':'C','แอดมิน':'H','บอท':'B'}
for fn,m in man.items():
    if m['key']=='line-2026' and m['tab'].startswith('ข้อความ'):
        mo=MON.get(m['tab'].split(' ')[1],0); rows=load(fn); batch=[]; seq={}
        for r in rows[1:]:
            if not r: continue
            r=r+['']*(8-len(r)); tid=r[1]
            if not tid: continue
            try: t=mins(dt.datetime.strptime(r[2]+' '+r[3],'%Y-%m-%d %H:%M'))
            except Exception: t=None
            seq[tid]=seq.get(tid,0)+1
            nm=names_line.get(tid) or nm_parts(r[0])
            batch.append(('LINE',tid,mo,seq[tid],t,LROLE.get(r[4],'?'),r[4],r[5],mask(r[6],nm)))
        cur.executemany('INSERT INTO msg VALUES (?,?,?,?,?,?,?,?,?)',batch); con.commit(); del rows,batch
        print('line',m['tab'],flush=True)
    if m['key']=='line-2026' and m['tab'].startswith('โน้ตลงทะเบียน'):
        mo=MON.get(m['tab'].split(' ')[1],0); rows=load(fn)
        for r in rows[1:]:
            if not r: continue
            r=r+['']*(10-len(r))
            try: t=mins(dt.datetime.strptime(r[3]+' '+r[4],'%Y-%m-%d %H:%M'))
            except Exception: t=None
            nm=names_line.get(r[1]) or nm_parts(r[0])
            cur.execute('INSERT INTO linenote VALUES (?,?,?,?,?,?,?,?)',(r[1],mo,t,r[5],r[6],r[7],r[8],mask(r[9],nm)))
        con.commit()
IGROLE={'ลูกค้า':'C','แอดมิน(พิมพ์เอง)':'H','ข้อความสำเร็จรูป':'B','บรอดแคสต์':'B'}
for fn,m in man.items():
    if m['key']=='ig-2026' and m['tab'].startswith('สรุปรายแชท'):
        rows=load(fn); hd=rows[0]; ix={k:i for i,k in enumerate(hd)}
        g=lambda r,k: (r[ix[k]] if k in ix and ix[k]<len(r) else '')
        for r in rows[1:]:
            if not r: continue
            cur.execute('INSERT INTO igsum VALUES (?,?,?,?,?)',(h(g(r,'IG Account')),MON.get(g(r,'เดือน'),0),g(r,'กลุ่ม'),g(r,'สาเหตุ'),g(r,'หมวด (เกณฑ์ admin-hub)')))
    if m['key']=='ig-2026' and m['tab'].startswith('ข้อความดิบ'):
        mm0=re.search(r'\((\S+)\s',m['tab']); mo=MON.get(mm0.group(1),0) if mm0 else 0
        rows=load(fn); hd=rows[0]; ix={k:i for i,k in enumerate(hd)}
        g=lambda r,k: (r[ix[k]] if k in ix and ix[k]<len(r) else '')
        batch=[]
        for r in rows[1:]:
            if not r: continue
            mm=re.match(r'(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})',str(g(r,'เวลา')))
            t=mins(dt.datetime(2026,int(mm.group(2)),int(mm.group(1)),int(mm.group(3)),int(mm.group(4)))) if mm else None
            acc=g(r,'IG Account'); txt=g(r,'ข้อความ')
            if acc and len(acc)>=3: txt=str(txt).replace(acc,'〔ชื่อ〕')
            try: sq=int(float(g(r,'ลำดับ') or 0))
            except: sq=0
            batch.append(('IG',g(r,'Thread ID') or h(acc),mo,sq,t,IGROLE.get(g(r,'ผู้ส่ง'),'?'),g(r,'ผู้ส่ง'),'',mask(txt,[]) + (' [ไฟล์แนบ]' if g(r,'ไฟล์แนบ') and not txt else '')))
        cur.executemany('INSERT INTO msg VALUES (?,?,?,?,?,?,?,?,?)',batch); con.commit()
        print('ig',m['tab'],len(batch),flush=True)
cur.execute('CREATE INDEX i1 ON msg(ch,tid,t,seq)'); con.commit()
for q in ['SELECT ch,COUNT(*),COUNT(DISTINCT tid) FROM msg GROUP BY ch','SELECT COUNT(*) FROM fbsum','SELECT COUNT(*) FROM linesum','SELECT COUNT(*) FROM linenote','SELECT COUNT(*) FROM igsum','SELECT COUNT(*) FROM msg WHERE t IS NULL']:
    print(q, cur.execute(q).fetchall(), flush=True)
print('DONE',flush=True)

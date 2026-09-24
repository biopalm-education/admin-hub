# -*- coding: utf-8 -*-
"""admin-hub auto refresh — Facebook + Instagram, one or more months.

RUN INSIDE THE COMPOSIO WORKBENCH (needs run_composio_tool for Instagram):
    exec(open('/tmp/ahb/tools/auto/refresh.py').read())
    run_refresh(['2026-09'])          # daily: current month
    run_refresh(['2026-08','2026-09'])  # weekly: previous + current

What it does, per month: walks the Page /conversations list back to the 1st,
re-fetches every thread touched since then, rebuilds that month's columns with
the SAME rules as tools/month-pull (never edit them - cross-month numbers depend
on it), merges into src/, runs build_v4.py and pushes with deploy.sh.

LINE is NOT included: its history can only be read from a logged-in
chat.line.biz session, so it stays a manual monthly job.
"""
import os, re, json, time, glob, base64, threading, subprocess, collections
import datetime as dt, statistics as stt
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import requests

REPO='/tmp/ahb'; WORK='/tmp/bp'; SLUG='biopalm-education/admin-hub'
PAGE='691470034208676'; IGPAGE='17841463207664263'; V='v21.0'
BASE=f'https://graph.facebook.com/{V}'
TH=dt.timezone(dt.timedelta(hours=7))
MSHORT={1:'ม.ค.',2:'ก.พ.',3:'มี.ค.',4:'เม.ย.',5:'พ.ค.',6:'มิ.ย.',7:'ก.ค.',8:'ส.ค.',9:'ก.ย.',10:'ต.ค.',11:'พ.ย.',12:'ธ.ค.'}
MLABEL={1:'มกราคม',2:'กุมภาพันธ์',3:'มีนาคม',4:'เมษายน',5:'พฤษภาคม',6:'มิถุนายน',7:'กรกฎาคม',8:'สิงหาคม',9:'กันยายน',10:'ตุลาคม',11:'พฤศจิกายน',12:'ธันวาคม'}

# ---------- shared rules (do not edit) ----------
META=re.compile(r'^ตั้งระยะข้อมูลลูกค้าเป็น')
FB_PRICE=re.compile(r'บาท|ค่าเรียน'); FB_CLOSE=re.compile(r'ขออนุญาตสรุปรายละเอียด|ธนาคารกสิกรไทย')
FB_GIVE=re.compile(r'Giveaway|แจกฟรี|ขอชีท|ชีทเซลล')
FB_INTEREST=re.compile(r'สนใจ|คอร์ส|เรียน|ราคา|ตาราง|รายละเอียด|ม\.[1-6]|ม\.ต้น|ม\.ปลาย|สอวน|สสวท')
FB_GRADEQ=re.compile(r'ระดับชั้นใด|ชั้นเรียนใด|เรียนอยู่ชั้น|อยู่ระดับชั้น|เรียนอยู่ระดับ|ปัจจุบันเรียนอยู่')
FB_PAY=re.compile(r'ส่งการชำระเงินจำนวน|สลิป|โอนแล้ว|โอนเงิน|ชำระ|จ่ายแล้ว|หลักฐาน')
LBL={'S0':'S0 ไม่มีข้อความลูกค้า','S1':'S1 ทักแต่ไม่ถามคอร์ส','S2':'S2 สนใจคอร์ส','S3':'S3 ได้รับราคาแล้ว',
     'S4':'S4 ขอสมัคร/ถามวิธีจ่าย','S5':'S5 ปิดการขาย','G':'G มารับของแถม'}
# Instagram (reconstructed 18 Sep 2026, back-tested on ม.ค.-ส.ค.: 7 of 1,046 chats differ)
IG_SLIP=re.compile(r'ตรวจสอบสลิปสำเร็จ')
IG_GRD=re.compile(r'ม\.ต้น|ม\.ปลาย|ม\.?\s?[1-6]|ป\.?\s?[1-6]')
IG_GRADEQ=re.compile(r'ระดับชั้น|ชั้นเรียนใด|เรียนอยู่ชั้น')
IG_PAY=re.compile(r'จ่าย|ชำระ|โอน')
IG_ASKC=re.compile(r'สนใจ|คอร์ส|ราคา|ตาราง|รายละเอียด|สมัคร|สอวน|สสวท|[Mm]odule|ติว|[Mm][Ww][Ii][Tt]')
IG_GWC=re.compile(r'[Gg]iveaway|แจกฟรี|ขอชีท|ชีท|ของแถม')
IG_GW=re.compile(r'ร่วมกิจกรรม|[Gg]iveaway|รีวิว')
# sender rule (Sep 22 2026, fix_roles.py): FB uses Meta's source tag; IG reuses how the same text behaves on FB
WEBBOT=re.compile(r'สถานะ\s*[:：]\s*ตรวจสอบสลิป|เราช่วยติวชีวะ|ยินดีให้คำปรึกษา|ติวชีวะ A-Level กับพี่|เพิ่งติดตามเพจ|ตอบกลับโฆษณา|กำหนดการสนทนา|transfer request|responding to a user comment|ตอบกลับความคิดเห็น')
ATT_FB=('[รูป/ไฟล์แนบ]',)

def bounds(mo):
    y,m=int(mo[:4]),int(mo[5:7])
    a=dt.datetime(y,m,1,tzinfo=TH); b=dt.datetime(y+(m==12),(m%12)+1,1,tzinfo=TH)
    return a.astimezone(dt.timezone.utc), b.astimezone(dt.timezone.utc)
def pdt(s): return dt.datetime.strptime(s,'%Y-%m-%dT%H:%M:%S%z')
def fmt(x):
    if x is None: return '—'
    x=int(x)
    if x<60: return '%d วิ'%x
    if x<3600: return '%d นาที'%round(x/60)
    if x<86400: return '%.1f ชม.'%(x/3600)
    return '%d วัน'%round(x/86400)

def log(*a):
    print(dt.datetime.now(TH).strftime('%H:%M:%S'),*a,flush=True)

# ---------- repo ----------
def prepare_repo():
    tok=open('/tmp/gh_token.txt').read().strip(); sec=open('/tmp/admin_secret.txt').read().strip()
    subprocess.run(['bash','-lc',f'rm -rf {REPO} && git clone -q --depth 1 https://github.com/{SLUG}.git {REPO}'],check=True)
    open(f'{REPO}/gh_token.txt','w').write(tok); open(f'{REPO}/secret.txt','w').write(sec)
    r=subprocess.run(['bash','-lc',f'cd {REPO} && python3 unpack.py'],capture_output=True,text=True)
    if 'OK' not in r.stdout: raise RuntimeError('unpack failed: '+r.stdout[-400:]+r.stderr[-400:])
    log('repo ready')

# ---------- Facebook ----------
def fb_token():
    res,err=run_composio_tool('FACEBOOK_GET_USER_PAGES',{})
    if err: raise RuntimeError('FB token: %s'%str(err)[:200])
    return res['data']['data'][0]['access_token']

def _get(url,params=None,tries=5):
    for i in range(tries):
        try:
            r=requests.get(url,params=params,timeout=90)
            if r.status_code==200: return r.json()
            j=r.json() if 'json' in r.headers.get('content-type','') else {}
            if (j.get('error') or {}).get('code') in (4,17,32,613,1,2) or r.status_code>=500:
                time.sleep(10*(i+1)); continue
            return None
        except Exception: time.sleep(5*(i+1))
    return None

def fb_pull(mo,tok):
    A0,A1=bounds(mo); cand=[]; after=None; n=0
    while True:
        p={'fields':'id,updated_time,message_count','limit':100,'access_token':tok}
        if after: p['after']=after
        j=_get(f'{BASE}/{PAGE}/conversations',p)
        if j is None: raise RuntimeError('FB walk failed at %d'%n)
        d=j.get('data',[])
        if not d: break
        n+=len(d)
        for c in d:
            if pdt(c['updated_time'])>=A0: cand.append(c['id'])
        after=(j.get('paging') or {}).get('cursors',{}).get('after')
        if pdt(d[-1]['updated_time'])<A0 or not after: break
    cand=list(dict.fromkeys(cand)); log('FB',mo,'walked',n,'candidates',len(cand))
    out=[]; lock=threading.Lock()
    F='created_time,from,to,message,tags,attachments{mime_type}'
    def work(cid):
        j=_get(f'{BASE}/{cid}',{'fields':f'participants,messages.limit(100){{{F}}}','access_token':tok})
        if j is None: return
        nm=''
        for q in ((j.get('participants') or {}).get('data') or []):
            if str(q.get('id'))!=PAGE: nm=q.get('name') or ''
        m=j.get('messages') or {}; msgs=m.get('data',[]); nx=(m.get('paging') or {}).get('next'); g=0
        while nx and g<40:
            if msgs and pdt(msgs[-1]['created_time'])<A0: break
            j2=_get(nx)
            if not j2 or not j2.get('data'): break
            msgs+=j2['data']; nx=(j2.get('paging') or {}).get('next'); g+=1
        keep=[{'t':x['created_time'],'f':(x.get('from') or {}).get('id'),'fn':(x.get('from') or {}).get('name'),
               'to':[y.get('name') for y in ((x.get('to') or {}).get('data') or [])],'m':x.get('message') or '',
               'a':1 if ((x.get('attachments') or {}).get('data')) else 0,
               's':next((q['name'][7:] for q in ((x.get('tags') or {}).get('data') or []) if q['name'].startswith('source:')),'')}
              for x in msgs if A0<=pdt(x['created_time'])<A1]
        rec={'id':cid,'nm':nm,'msgs':keep,'pre':bool(msgs and pdt(msgs[-1]['created_time'])<A0)}
        with lock: out.append(rec)
    with ThreadPoolExecutor(10) as ex: list(ex.map(work,cand))
    log('FB',mo,'fetched',len(out))
    return out

def fb_columns(mo,recs):
    short=MSHORT[int(mo[5:7])]
    RECS=[r for r in recs if r.get('msgs')]
    bz=Counter()
    for r in RECS:
        for m in r['msgs']:
            if str(m.get('f'))==PAGE:
                tx=(m.get('m') or '').strip() or ('[รูป/ไฟล์แนบ]' if m.get('a') else '')
                if not META.match(tx): bz[tx]+=1
    CANNED={t for t,c in bz.items() if c>=5 and len(t)>12}
    def mtype(m):
        if m['side']=='ลูกค้า': return 'ลูกค้า'
        if META.match(m['tx']): return 'ระบบ Meta'
        if m['tx']=='' or m['tx'] in CANNED: return 'สำเร็จรูป'
        return 'แอดมินพิมพ์เอง'
    sumrows=[]; extra={}; msgrows=[]
    for r in RECS:
        tid=r['id']; name=r.get('nm') or ''
        out=[]
        for m in sorted(r['msgs'],key=lambda x:x['t']):
            tx=(m.get('m') or '').strip() or ('[รูป/ไฟล์แนบ]' if m.get('a') else '')
            side='ธุรกิจ' if str(m.get('f'))==PAGE else 'ลูกค้า'
            out.append({'t':pdt(m['t']).astimezone(TH),'side':side,'tx':tx,'s':m.get('s') or '',
                        'to':[x for x in (m.get('to') or []) if x],'fn':m.get('fn') or ''})
        if not name:
            for m in out:
                if m['side']=='ธุรกิจ':
                    for n2 in m['to']:
                        if n2 and n2!='BioPalm': name=n2; break
                elif m['fn']: name=m['fn']
                if name: break
        # Sep 22 2026: who sent it comes from Meta's own tag (see fix_roles.py) — mobile = a person;
        # web / private_reply = automation unless it is a one-off text sent 2+ min after the customer
        def mtype2(i):
            m=out[i]; t0=mtype(m)
            if m['side']!='ธุรกิจ' or t0=='ระบบ Meta' or not m['s']: return t0
            if m['s']=='mobile': return 'แอดมินพิมพ์เอง'
            if t0=='แอดมินพิมพ์เอง' and m['tx'] not in ATT_FB and not WEBBOT.search(m['tx']):
                lc=next((out[j]['t'] for j in range(i-1,-1,-1) if out[j]['side']=='ลูกค้า'),None)
                if lc is not None and (m['t']-lc).total_seconds()>=120: return t0
            return 'สำเร็จรูป'
        types=[mtype2(i) for i in range(len(out))]
        conv=[(m,t) for m,t in zip(out,types) if t!='ระบบ Meta']
        biz=[m['tx'] for m,t in zip(out,types) if m['side']=='ธุรกิจ' and t!='ระบบ Meta']
        cus=[m['tx'] for m in out if m['side']=='ลูกค้า']
        metat=[m['tx'] for m,t in zip(out,types) if t=='ระบบ Meta']
        if any('สร้างคอนเวอร์ชั่น' in t for t in metat) or any(FB_CLOSE.search(t) for t in biz): stg='S5'
        elif not cus: stg='S0'
        elif any('ค่าเรียน' in t for t in biz): stg='S4'
        elif any('บาท' in t for t in biz): stg='S3'
        elif any(FB_GIVE.search(t) for t in cus): stg='G'
        elif any(FB_INTEREST.search(t) for t in cus): stg='S2'
        else: stg='S1'
        hasqual=any('มีคุณสมบัติ' in t for t in metat)
        tag='ปิดการขาย' if stg=='S5' else ('มีคุณสมบัติ' if hasqual else '')
        ad='Y' if any('BIOPALM ติวเตอร์วิชาชีวะ' in m['tx'] for m in out) else ''
        first=conv[0][0]['t'] if conv else (out[0]['t'] if out else None)
        sides=[m['side'] for m,t in conv]
        alt=sum(1 for i in range(1,len(sides)) if sides[i]!=sides[i-1])
        fc=next((m for m,t in conv if m['side']=='ลูกค้า'),None)
        fh0=next((m for m,t in conv if t=='แอดมินพิมพ์เอง'),None)
        firstv='—' if fh0 is None else ('0 วิ' if fc is None else fmt(max(0,(fh0['t']-fc['t']).total_seconds())))
        gaps=[(conv[i][0]['t']-conv[i-1][0]['t']).total_seconds() for i in range(1,len(conv))]
        maxw=fmt(max(gaps)) if gaps else '0 วิ'
        stuck='Y' if conv and conv[-1][0]['side']=='ลูกค้า' else ''
        hum=[m['tx'] for m,t in zip(out,types) if t=='แอดมินพิมพ์เอง']
        tm=set()
        for t in hum:
            if 'ครับ' in t or 'คับ' in t: tm.add('A')
            if 'ค่ะ' in t or 'คะ' in t: tm.add('B')
        team=''.join(sorted(tm)) or '-'
        price='Y' if any(FB_PRICE.search(t) for t in biz) else ''
        pay='Y' if any(FB_PAY.search(t) for t in cus) else ''
        gq=sum(1 for t in biz if FB_GRADEQ.search(t)); gq=gq if gq>=2 else ''
        ftv=fav=None
        if fc is not None:
            i0=[i for i,(m,t) in enumerate(conv) if m is fc][0]
            for m,t in conv[i0+1:]:
                if ftv is None and t=='แอดมินพิมพ์เอง': ftv=(m['t']-fc['t']).total_seconds()
                if fav is None and m['side']=='ธุรกิจ': fav=(m['t']-fc['t']).total_seconds()
        txtall=' '.join(m['tx'] for m in out)
        adsrc='ad' if ('BIOPALM ติวเตอร์วิชาชีวะ' in txtall or 'ตอบกลับโฆษณา' in txtall) else (
              'comment' if ('ตอบกลับความคิดเห็น' in txtall or 'responding to a user comment' in txtall) else 'organic')
        sumrows.append([short,tid,name,LBL[stg],ad,tag,('%02d'%first.day) if first else '',(str(first.hour) if first else ''),
            len(conv),sum(1 for m,t in conv if m['side']=='ลูกค้า'),
            sum(1 for m,t in conv if t=='แอดมินพิมพ์เอง'),sum(1 for m,t in conv if t=='สำเร็จรูป'),
            alt,firstv,maxw,stuck,team,price,pay,gq])
        extra[tid]={'ft':ftv,'fa':fav,'qual':hasqual,'stage':stg,'new':(not r.get('pre')),
                    'adsrc':adsrc,'firstside':(conv[0][0]['side'] if conv else 'ธุรกิจ')}
        for i,(m,t) in enumerate(zip(out,types),1):
            msgrows.append([short,tid,name,stg,i,m['t'].strftime('%d/%m %H:%M:%S'),m['side'],t,m['tx']])
    sumrows.sort(key=lambda r:(r[6],r[7].zfill(2),r[1]))
    mix=Counter()
    for r in sumrows:
        e=extra[r[1]]
        if e['new']: mix[{'ad':'na','comment':'nc','organic':'no'}[e['adsrc']]]+=1
        elif e['firstside']=='ลูกค้า': mix['rb']+=1
        else: mix['fr' if int(r[9] or 0)>0 else 'fs']+=1
    return sumrows,extra,msgrows,dict(mix)

def fb_month_files(mo,S,EX,M,mix):
    y,m=int(mo[:4]),int(mo[5:7]); maxd=(dt.date(y+(m==12),(m%12)+1,1)-dt.timedelta(days=1)).day
    ROLE={'ลูกค้า':0,'แอดมินพิมพ์เอง':1,'สำเร็จรูป':2,'ระบบ Meta':3}
    G=lambda r:str(r[3])[:2].strip()
    def sec(s):
        s=str(s).strip()
        if s in ('','—','-'): return -1
        mm=re.match(r'^([\d.,]+)\s*(วิ|นาที|ชม\.|วัน)$',s)
        if not mm: return -1
        return int(float(mm.group(1).replace(',',''))*{'วิ':1,'นาที':60,'ชม.':3600,'วัน':86400}[mm.group(2)])
    msgs=collections.defaultdict(list)
    for r in M: msgs[r[1]].append(r)
    D={}; DL=[]
    def idx(t):
        if t not in D: D[t]=len(DL); DL.append(t)
        return D[t]
    chats=[]
    for r in S:
        tid=r[1]; nm=r[2]; stg=G(r); d=int(r[6] or 1); h=int(r[7] or 0)
        dow=dt.date(y,m,min(max(d,1),maxd)).weekday(); ms=[]
        for mm in sorted(msgs.get(tid,[]),key=lambda x:int(x[4])):
            ts=mm[5]; dd=int(ts[0:2]); hh=int(ts[6:8]); mi=int(ts[9:11]); tx=mm[8]
            if nm and nm in tx: tx=tx.replace(nm,'\x01')
            ms.append([(dd-1)*1440+hh*60+mi,ROLE.get(mm[7],3),idx(tx)])
        chats.append([nm,stg,'',d,h,dow,int(r[9]),int(r[10]),int(r[11]),int(r[12]),
            sec(r[13]),sec(r[14]),1 if r[15]=='Y' else 0,r[16] or '-',
            int(r[19]) if str(r[19]) not in ('','0') else 0,
            1 if r[17]=='Y' else 0,1 if r[18]=='Y' else 0,1 if stg=='S5' else 0,
            ms,tid[2:] if tid.startswith('t_') else tid,
            1 if r[4]=='Y' else 0,1 if r[5]=='มีคุณสมบัติ' else 0])
    leads=[r for r in S if G(r) in ('S2','S3','S4','S5')]
    def q(a,p): return a[min(len(a)-1,int(len(a)*p))] if a else 0
    ft=sorted(EX[r[1]]['ft'] for r in leads if EX[r[1]]['ft'] is not None)
    fa=sorted(EX[r[1]]['fa'] for r in leads if EX[r[1]]['fa'] is not None)
    perh=collections.defaultdict(list); cnth=Counter()
    for r in leads:
        h=int(r[7] or 0); cnth[h]+=1
        v=EX[r[1]]['ft']
        if v is not None: perh[h].append(v)
    dow=[0]*7
    for r in leads: dow[dt.date(y,m,min(max(int(r[6] or 1),1),maxd)).weekday()]+=1
    days=sorted({str(r[6]).zfill(2) for r in S})
    daily=[[d,sum(1 for r in S if str(r[6]).zfill(2)==d),sum(1 for r in leads if str(r[6]).zfill(2)==d),
            sum(1 for r in S if str(r[6]).zfill(2)==d and G(r)=='S5')] for d in days]
    reasons=Counter()
    for r in leads:
        if G(r)=='S5': continue
        if int(r[10] or 0)==0: reasons['R06']+=1
        elif r[15]=='Y': reasons['R05']+=1
        elif r[17]=='Y': reasons['R01']+=1
        else: reasons['R08']+=1
    agg={'threads':len(S),'msgs':sum(int(r[8]) for r in S),'leads':len(leads),
     'gw':sum(1 for r in S if G(r)=='G'),'other':sum(1 for r in S if G(r) in ('S0','S1')),
     'stages':dict(Counter(G(r) for r in S)),'closed':sum(1 for r in S if G(r)=='S5'),
     'qual':sum(1 for r in leads if EX[r[1]]['qual']),'fromAd':sum(1 for r in S if r[4]=='Y'),
     'adLeads':sum(1 for r in leads if r[4]=='Y'),'adClosed':sum(1 for r in leads if r[4]=='Y' and G(r)=='S5'),
     'noAdLeads':sum(1 for r in leads if r[4]!='Y'),'noAdClosed':sum(1 for r in leads if r[4]!='Y' and G(r)=='S5'),
     'price':sum(1 for r in leads if r[17]=='Y'),'pay':sum(1 for r in leads if r[18]=='Y'),
     'notyped':sum(1 for r in leads if int(r[10] or 0)==0),'gotHuman':sum(1 for r in leads if int(r[10] or 0)>0),
     'noreply':0,'unans':sum(1 for r in leads if r[15]=='Y'),'ask2':sum(1 for r in leads if str(r[19]) not in ('','0')),
     'turnsMed':int(stt.median([int(r[12] or 0) for r in leads])) if leads else 0,
     'turnsMean':round(stt.mean([int(r[12] or 0) for r in leads]),1) if leads else 0,
     'ftMed':int(q(ft,.5)),'ftP75':int(q(ft,.75)),'ftP90':int(q(ft,.9)),
     'faMed':int(stt.median(fa)) if fa else 0,
     'mc':round(stt.mean([int(r[9]) for r in leads]),1) if leads else 0,
     'mh':round(stt.mean([int(r[10]) for r in leads]),1) if leads else 0,
     'ma':round(stt.mean([int(r[11]) for r in leads]),1) if leads else 0,
     'dow':dow,'who':dict(Counter(str(r[16]) for r in leads)),
     'reasons':sorted(reasons.items(),key=lambda x:-x[1]),
     'hours':[[h,cnth[h],(round(stt.median(perh[h])/60,1) if perh[h] else None),len(perh[h])] for h in range(24)],
     'daily':daily,'mix':mix}
    return {'dict':DL,'chats':chats},agg

# ---------- Instagram ----------
def ig_pull(mo):
    A0,A1=bounds(mo); cut=A0.strftime('%Y-%m-%dT%H:%M:%S+0000')
    convs=[]; after=None
    while True:
        a={'limit':50,'fields':'id,updated_time,participants'}
        if after: a['after']=after
        res=err=None
        for _ in range(3):
            res,err=run_composio_tool('INSTAGRAM_LIST_ALL_CONVERSATIONS',a)
            if not err: break
            time.sleep(5)
        if err: raise RuntimeError('IG walk: %s'%str(err)[:200])
        d=res['data']; b=d.get('data',[])
        convs+=b; after=((d.get('paging') or {}).get('cursors') or {}).get('after')
        if not b or not after or min(x['updated_time'] for x in b)<cut: break
    seen=set(); cand=[]
    for c in convs:
        if c['updated_time']>=cut and c['id'] not in seen: seen.add(c['id']); cand.append(c)
    log('IG',mo,'walked',len(convs),'candidates',len(cand))
    MS={}; lock=threading.Lock()
    def work(c):
        cid=c['id']; out=[]; after=None
        for _ in range(60):
            a={'conversation_id':cid,'limit':100,'fields':'id,from,to,message,created_time,attachments,is_unsupported,story,shares,reactions'}
            if after: a['after']=after
            res=err=None
            for _t in range(3):
                res,err=run_composio_tool('INSTAGRAM_LIST_ALL_MESSAGES',a)
                if not err: break
                time.sleep(3)
            if err: return
            d=res['data']; b=d.get('data',[]) if isinstance(d.get('data'),list) else []
            out+=b; after=((d.get('paging') or {}).get('cursors') or {}).get('after')
            if not b or not after or min(x['created_time'] for x in b)<cut: break
        with lock: MS[cid]=out
    with ThreadPoolExecutor(6) as ex: list(ex.map(work,cand))
    log('IG',mo,'fetched',len(MS))
    return cand,MS

def ig_build(mo,convs,MS,IG):
    D8=IG['dict']; DI={t:i for i,t in enumerate(D8)}
    def di(t):
        if t not in DI: DI[t]=len(D8); D8.append(t)
        return DI[t]
    def th(s): return dt.datetime.strptime(s,'%Y-%m-%dT%H:%M:%S%z').astimezone(TH)
    txf=lambda i: D8[i] if isinstance(i,int) else i
    chs=[]
    for c in convs:
        ms=sorted([m for m in MS.get(c['id'],[]) if th(m['created_time']).strftime('%Y-%m')==mo],key=lambda m:m['created_time'])
        if not ms: continue
        parts=(c.get('participants') or {}).get('data',[])
        cust=next((p for p in parts if str(p.get('id'))!=IGPAGE and p.get('username')!='biopalmmm'),{})
        ev=[]
        for m in ms:
            me=(m.get('from') or {}).get('username')=='biopalmmm' or str((m.get('from') or {}).get('id'))==IGPAGE
            t=(m.get('message') or '').strip()
            if not t: t='[ไฟล์แนบ]' if m.get('attachments') else ('[ตอบกลับสตอรี่]' if m.get('story') else ('[แชร์โพสต์]' if m.get('shares') else '[ข้อความที่ IG ไม่รองรับ]'))
            ev.append({'t':th(m['created_time']),'me':me,'tx':t})
        chs.append({'id':c['id'],'name':cust.get('username') or '','ev':ev})
    dc=Counter()
    for x in chs:
        for t in set(e['tx'] for e in x['ev'] if e['me'] and not e['tx'].startswith('[')): dc[t]+=1
    hist=Counter()
    for m2,d in IG['months'].items():
        if m2==mo: continue
        for c in d['leads']:
            for t in set(txf(m[2]) for m in c[18] if m[1] in (1,2,3)): hist[t]+=1
    rep=lambda t: dc[t]+hist[t]
    def roles(x):
        out=[]
        for i,e in enumerate(x['ev']):
            if not e['me']: out.append(0); continue
            t=e['tx']
            if t.startswith('['):
                nb=[j for j in (i-1,i+1) if 0<=j<len(x['ev']) and x['ev'][j]['me'] and not x['ev'][j]['tx'].startswith('[') and abs((x['ev'][j]['t']-e['t']).total_seconds())<=180]
                if nb:
                    tt=x['ev'][nb[0]]['tx']; out.append(3 if IG_GW.search(tt) and rep(tt)>=5 else (2 if rep(tt)>=3 and len(tt)>12 else 1))
                else: out.append(2)
                continue
            if IG_GW.search(t) and rep(t)>=5: out.append(3)
            elif rep(t)>=3 and len(t)>12: out.append(2)
            else: out.append(1)
        return fix_ig(x['ev'],out)
    try: CLS=json.load(open(f'{REPO}/src/agg.json',encoding='utf-8')).get('txtclass') or {}
    except Exception: CLS={}
    def fix_ig(ev,rr):
        # Sep 22 2026 (fix_roles.py): a saved-reply text is an admin reply if Facebook shows the same
        # text sent from mobile; unknown texts: 2+ min after the customer's last message = admin
        new=list(rr); lc=None
        for i,e in enumerate(ev):
            if rr[i]==0: lc=e['t']; continue
            if rr[i]==3 or e['tx'].startswith('['): continue
            k=e['tx'][:30]
            if k in CLS: new[i]=1 if CLS[k] else 2
            elif rr[i]==2: new[i]=1 if (lc is not None and (e['t']-lc).total_seconds()>=120) else 2
        for i,e in enumerate(ev):
            if rr[i] in (1,2) and e['tx'].startswith('['):
                nb=[j for j in range(len(ev)) if rr[j] in (1,2) and not ev[j]['tx'].startswith('[') and abs((ev[j]['t']-e['t']).total_seconds())<=180]
                if nb: new[i]=new[min(nb,key=lambda j:abs(j-i))]
        return new
    rows=[]; fa=[]
    for x in chs:
        rr=roles(x); ev=[dict(e,r=r) for e,r in zip(x['ev'],rr)]
        cu=[e for e in ev if e['r']==0]; ty=[e for e in ev if e['r']==1]
        first=(cu or ev)[0]['t']
        ctext=' '.join(e['tx'] for e in cu if not e['tx'].startswith('['))
        ptext=' '.join(e['tx'] for e in ev if e['r'])
        turns=sum(1 for a,b in zip(ev,ev[1:]) if (a['r']==0)!=(b['r']==0))
        ft=-1
        if cu:
            c0=cu[0]['t']; a=next((e for e in ev if e['r']==1 and e['t']>=c0),None)
            if a: ft=int((a['t']-c0).total_seconds())
            a2=next((e for e in ev if e['r'] and e['t']>=c0),None)
            if a2: fa.append(int((a2['t']-c0).total_seconds()))
        mw=None
        for i,e in enumerate(ev):
            if e['r']==0 and (i+1<len(ev) and ev[i+1]['r']): mw=max(mw or 0,int((ev[i+1]['t']-e['t']).total_seconds()))
        if mw is not None: mw=(mw//60)*60
        li=max([i for i,e in enumerate(ev) if e['r']==0],default=None)
        unans=1 if li is not None and not any(e['r']==1 for e in ev[li+1:]) else 0
        tt=' '.join(e['tx'] for e in ty); hA=re.search(r'ครับ|คับ',tt); hB=re.search(r'ค่ะ|คะ',tt)
        team='AB' if hA and hB else ('A' if hA else ('B' if hB else ''))
        ask2=sum(1 for e in ev if e['r'] and IG_GRADEQ.search(e['tx']))
        price=1 if re.search(r'บาท|ค่าเรียน',ptext) else 0
        pay=1 if IG_PAY.search(ctext) else 0
        won=1 if any(IG_SLIP.search(e['tx']) for e in ev) else 0
        gwsig=any(e['r']==3 for e in ev) or bool(IG_GWC.search(ctext))
        if won: stg='S5'
        elif not cu: stg='S0'
        elif gwsig and not IG_ASKC.search(ctext): stg='G'
        elif price: stg='S3'
        elif IG_ASKC.search(ctext) or IG_GRD.search(ctext): stg='S2'
        else: stg='S1'
        rz='' if stg=='S5' else ('R06' if not ty else ('R05' if unans else ('R01' if price else 'R08')))
        g=IG_GRD.search(ctext)
        msgs=[[(e['t'].day-1)*1440+e['t'].hour*60+e['t'].minute,e['r'],di(e['tx'])] for e in ev]
        rows.append([x['name'],stg,rz,'%02d'%first.day,first.hour,first.weekday(),len(cu),len(ty),
            sum(1 for e in ev if e['r']==2),turns,ft,mw,unans,team,ask2,price,pay,won,msgs,x['id'],0,0,0,'',
            g.group(0) if g else '',[rz] if rz else [],'organic',None,None,stg,won,0,'slip' if won else '',0,
            None,None,None,None,None,None,None])
    LD=[r for r in rows if r[1] in ('S2','S3','S5')]
    def q(a,p): return a[min(len(a)-1,int(len(a)*p))] if a else 0
    ftl=sorted(r[10] for r in LD if r[10]>=0)
    cnth=Counter(r[4] for r in LD); perh=collections.defaultdict(list)
    for r in LD:
        if r[10]>=0: perh[r[4]].append(r[10])
    mix=Counter()
    for r in rows: mix['nu' if (r[18] and r[18][0][1]==0) else 'fr']+=1
    agg={'qual':0,'fromAd':0,'adLeads':0,'adClosed':0,'noAdLeads':len(LD),
         'noAdClosed':sum(r[17] for r in LD),'faMed':int(stt.median(fa)) if fa else 0,'noreply':0,
         'mix':dict(mix),'v':3,
         'threads':len(rows),'msgs':sum(len(r[18]) for r in rows),'leads':len(LD),
         'gw':sum(r[1]=='G' for r in rows),'other':sum(r[1] in ('S0','S1') for r in rows),
         'stages':dict(Counter(r[1] for r in rows)),'closed':sum(r[17] for r in rows),
         'price':sum(r[15] for r in LD),'pay':sum(r[16] for r in LD),
         'notyped':sum(1 for r in LD if r[7]==0),'gotHuman':sum(1 for r in LD if r[7]>0),
         'unans':sum(r[12] for r in LD),'ask2':sum(1 for r in LD if r[14]>=2),
         'turnsMed':int(stt.median([r[9] for r in LD])) if LD else 0,
         'turnsMean':round(stt.mean([r[9] for r in LD]),1) if LD else 0,
         'ftMed':int(q(ftl,.5)),'ftP75':int(q(ftl,.75)),'ftP90':int(q(ftl,.9)),
         'mc':round(stt.mean([r[6] for r in LD]),1) if LD else 0,
         'mh':round(stt.mean([r[7] for r in LD]),1) if LD else 0,
         'ma':round(stt.mean([r[8] for r in LD]),1) if LD else 0,
         'dow':[sum(1 for r in LD if r[5]==d) for d in range(7)],
         'who':dict(Counter(r[13] or '-' for r in LD)),
         'reasons':sorted(Counter(r[2] for r in LD if r[2]).items(),key=lambda x:-x[1]),
         'hours':[[h,cnth[h],(round(stt.median(perh[h])/60,1) if perh[h] else None),len(perh[h])] for h in range(24)],
         'daily':[[d,sum(1 for r in rows if r[3]==d),sum(1 for r in LD if r[3]==d)] for d in sorted({r[3] for r in rows})],
         'full':True}
    return rows,agg,D8

# ---------- driver ----------
def run_refresh(months, push=True):
    prepare_repo()
    tok=fb_token()
    AGG=json.load(open(f'{REPO}/src/agg.json',encoding='utf-8'))
    IG=json.load(open(f'{REPO}/src/ig_all.json',encoding='utf-8'))
    done=[]
    for mo in months:
        recs=fb_pull(mo,tok)
        S,EX,M,mix=fb_columns(mo,recs)
        f,agg=fb_month_files(mo,S,EX,M,mix)
        json.dump(f,open(f'{REPO}/src/fb_{mo}.json','w',encoding='utf-8'),separators=(',',':'),ensure_ascii=False)
        AGG['fb'][mo]=agg
        log('FB',mo,'chats',agg['threads'],'leads',agg['leads'],'closed',agg['closed'])
        convs,MS=ig_pull(mo)
        rows,iagg,D8=ig_build(mo,convs,MS,IG)
        IG['dict']=D8; IG['months'][mo]={'agg':iagg,'leads':rows}
        AGG['ig'][mo]=iagg
        log('IG',mo,'chats',iagg['threads'],'leads',iagg['leads'],'closed',iagg['closed'])
        for k in ('mkeys','fbkeys','igfull'):
            if mo not in AGG[k]: AGG[k]=sorted(set(AGG[k])|{mo})
        AGG['mlabel'][mo]='%s %s'%(MLABEL[int(mo[5:7])],mo[:4]); AGG['mshort'][mo]=MSHORT[int(mo[5:7])]
        done.append(mo)
    json.dump(IG,open(f'{REPO}/src/ig_all.json','w',encoding='utf-8'),separators=(',',':'),ensure_ascii=False)
    json.dump(AGG,open(f'{REPO}/src/agg.json','w',encoding='utf-8'),separators=(',',':'),ensure_ascii=False)
    # stitch.py: an admin reply that lands in the NEXT month (within 7 days) still counts for this month
    r=subprocess.run(['bash','-lc',f'cd {REPO} && python3 stitch.py 2>&1|tail -2'],capture_output=True,text=True)
    log('stitch',r.stdout.strip()[-200:])
    r=subprocess.run(['bash','-lc',f'cd {REPO} && python3 build_v4.py 2>&1|tail -3'],capture_output=True,text=True)
    log('build_v4',r.stdout.strip()[-300:])
    # build_v5 re-applies the strict "ทักมาแล้วหาย" split (14 + 30 day); post_v5_speed restores the
    # reply-speed tables that build_v5 drops. Skipping these reverted the live 14-day view every morning.
    # build_fu rebuilds the FB/IG "ตามแชท Auto reply" list and appends today's counts to its history.
    # tools/fb_links/cov.py recounts agg.fblinkcov (rooms with a direct Inbox link per month) for the FB note.
    for step in ('build_v5.py','post_v5_speed.py','build_fu.py','tools/fb_links/cov.py'):
        r=subprocess.run(['bash','-lc',f'cd {REPO} && python3 {step} 2>&1|tail -3'],capture_output=True,text=True)
        log(step,r.stdout.strip()[-300:])
        if r.returncode!=0 or 'Traceback' in r.stdout: raise RuntimeError(step+' failed: '+r.stdout[-400:])
    if not push: return done
    msg='อัปเดตอัตโนมัติ %s (%s)'%(dt.datetime.now(TH).strftime('%d/%m %H:%M'),', '.join(done))
    r=subprocess.run(['bash','-lc',f'cd {REPO} && sh deploy.sh "{msg}" 2>&1|tail -3'],capture_output=True,text=True)
    log('deploy',r.stdout.strip()[-300:])
    if 'pushed' not in r.stdout and 'ไม่มีอะไรเปลี่ยน' not in r.stdout:
        raise RuntimeError('deploy failed: '+r.stdout[-400:])
    return done

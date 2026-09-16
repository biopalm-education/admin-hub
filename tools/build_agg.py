
# -*- coding: utf-8 -*-
import json, re, collections, statistics as st
from datetime import date
S=json.load(open("/home/user/w/june_sum.json"))
M=json.load(open("/home/user/w/june_msgs.json"))
EX=json.load(open("/home/user/w/june_extra.json"))
Y,MO=2026,6
def sec(s):
    s=str(s).strip()
    if s in ('','—','-'): return -1
    m=re.match(r'^([\d.,]+)\s*(วิ|นาที|ชม\.|วัน)$',s)
    if not m: return -1
    return int(float(m.group(1).replace(',',''))*{'วิ':1,'นาที':60,'ชม.':3600,'วัน':86400}[m.group(2)])
G=lambda r:str(r[3])[:2].strip()
ROLE={'ลูกค้า':0,'แอดมินพิมพ์เอง':1,'สำเร็จรูป':2,'ระบบ Meta':3}
msgs=collections.defaultdict(list)
for r in M: msgs[r[1]].append(r)
D={}; DL=[]
def idx(t):
    if t not in D: D[t]=len(DL); DL.append(t)
    return D[t]
chats=[]
for r in S:
    tid=r[1]; nm=r[2]; stg=G(r)
    d=int(r[6] or 1); h=int(r[7] or 0)
    dow=date(Y,MO,min(max(d,1),30)).weekday()
    ms=[]
    for m in sorted(msgs.get(tid,[]), key=lambda x:int(x[4])):
        tsx=m[5]; dd=int(tsx[0:2]); hh=int(tsx[6:8]); mi=int(tsx[9:11])
        tx=m[8]
        if nm and nm in tx: tx=tx.replace(nm,'\x01')
        ms.append([(dd-1)*1440+hh*60+mi, ROLE.get(m[7],3), idx(tx)])
    chats.append([nm,stg,'',d,h,dow,int(r[9]),int(r[10]),int(r[11]),int(r[12]),
        sec(r[13]),sec(r[14]), 1 if r[15]=='Y' else 0, r[16] or '-',
        int(r[19]) if str(r[19]) not in ('','0') else 0,
        1 if r[17]=='Y' else 0, 1 if r[18]=='Y' else 0, 1 if stg=='S5' else 0,
        ms, tid[2:] if tid.startswith('t_') else tid,
        1 if r[4]=='Y' else 0, 1 if r[5]=='มีคุณสมบัติ' else 0])
payload={'dict':DL,'chats':chats}
json.dump(payload, open("/home/user/w/src/fb_2026-06.json","w"), ensure_ascii=False, separators=(',',':'))
# ---------- aggregate ----------
leads=[r for r in S if G(r) in ('S2','S3','S4','S5')]
def q(a,p): return a[min(len(a)-1,int(len(a)*p))] if a else 0
ft=sorted(EX[r[1]]["ft"] for r in leads if EX[r[1]]["ft"] is not None)
fa=sorted(EX[r[1]]["fa"] for r in leads if EX[r[1]]["fa"] is not None)
perh=collections.defaultdict(list); cnth=collections.Counter()
for r in leads:
    h=int(r[7] or 0); cnth[h]+=1
    v=EX[r[1]]["ft"]
    if v is not None: perh[h].append(v)
dow=[0]*7
for r in leads: dow[date(Y,MO,min(max(int(r[6] or 1),1),30)).weekday()]+=1
days=sorted({str(r[6]).zfill(2) for r in S})
daily=[[d,
        sum(1 for r in S if str(r[6]).zfill(2)==d),
        sum(1 for r in leads if str(r[6]).zfill(2)==d),
        sum(1 for r in S if str(r[6]).zfill(2)==d and G(r)=='S5')] for d in days]
reasons=collections.Counter()
for r in leads:
    if G(r)=='S5': continue
    if int(r[10] or 0)==0: reasons['R06']+=1
    elif r[15]=='Y': reasons['R05']+=1
    elif r[17]=='Y': reasons['R01']+=1
    else: reasons['R08']+=1
agg={
 'threads':len(S),'msgs':sum(int(r[8]) for r in S),'leads':len(leads),
 'gw':sum(1 for r in S if G(r)=='G'),'other':sum(1 for r in S if G(r) in ('S0','S1')),
 'stages':dict(collections.Counter(G(r) for r in S)),
 'closed':sum(1 for r in S if G(r)=='S5'),
 'qual':sum(1 for r in leads if EX[r[1]]["qual"]),
 'fromAd':sum(1 for r in S if r[4]=='Y'),
 'adLeads':sum(1 for r in leads if r[4]=='Y'),
 'adClosed':sum(1 for r in leads if r[4]=='Y' and G(r)=='S5'),
 'noAdLeads':sum(1 for r in leads if r[4]!='Y'),
 'noAdClosed':sum(1 for r in leads if r[4]!='Y' and G(r)=='S5'),
 'price':sum(1 for r in leads if r[17]=='Y'),
 'pay':sum(1 for r in leads if r[18]=='Y'),
 'notyped':sum(1 for r in leads if int(r[10] or 0)==0),
 'gotHuman':sum(1 for r in leads if int(r[10] or 0)>0),
 'noreply':0,
 'unans':sum(1 for r in leads if r[15]=='Y'),
 'ask2':sum(1 for r in leads if str(r[19]) not in ('','0')),
 'turnsMed':int(st.median([int(r[12] or 0) for r in leads])) if leads else 0,
 'turnsMean':round(st.mean([int(r[12] or 0) for r in leads]),1) if leads else 0,
 'ftMed':int(q(ft,.5)),'ftP75':int(q(ft,.75)),'ftP90':int(q(ft,.9)),
 'faMed':int(st.median(fa)) if fa else 0,
 'mc':round(st.mean([int(r[9]) for r in leads]),1) if leads else 0,
 'mh':round(st.mean([int(r[10]) for r in leads]),1) if leads else 0,
 'ma':round(st.mean([int(r[11]) for r in leads]),1) if leads else 0,
 'dow':dow,
 'who':dict(collections.Counter(str(r[16]) for r in leads)),
 'reasons':sorted(reasons.items(), key=lambda x:-x[1]),
 'hours':[[h,cnth[h],(round(st.median(perh[h])/60,1) if perh[h] else None),len(perh[h])] for h in range(24)],
 'daily':daily,
}
json.dump(agg, open("/home/user/w/june_agg.json","w"), ensure_ascii=False)
print(json.dumps({k:v for k,v in agg.items() if k not in ('hours','daily','dow')}, ensure_ascii=False)[:1200])
print("dict",len(DL),"chats",len(chats))

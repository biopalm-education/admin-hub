# -*- coding: utf-8 -*-
import sqlite3, json, collections, statistics as st, datetime as dt, re
con=sqlite3.connect('chat.db'); c=con.cursor()
roles=json.load(open('roles.json'))
T0=dt.datetime(2026,1,1)
def mo(t): return (T0+dt.timedelta(minutes=t)).strftime('%Y-%m') if t is not None else None
def dtm(t): return T0+dt.timedelta(minutes=t)
cols=[d[1] for d in c.execute('PRAGMA table_info(th)')]
TH=[dict(zip(cols,r)) for r in c.execute('SELECT * FROM th')]
for r in TH:
    r['role']=roles.get(r['ch']+'|'+r['tid'],'unknown')
    r['islead']=int(bool(r['lead'] or r['paid'] or r['card_t'] is not None))
def scen(r):
    if r['paid']: return 'S6'
    if r['ongoing']: return 'S0'
    if r['n_creal']==0: return 'S1'
    if r['n_h']==0: return 'S2'
    if r['card_t'] is not None: return 'S5'
    if r['price_t'] is not None: return 'S4'
    return 'S3'
for r in TH: r['scen']=scen(r)
R={}
R['overview']={ch:dict(threads=sum(1 for r in TH if r['ch']==ch), leads=sum(r['islead'] for r in TH if r['ch']==ch),
    paid=sum(r['paid'] for r in TH if r['ch']==ch), typed=sum(1 for r in TH if r['ch']==ch and r['n_creal']>0)) for ch in ('FB','IG','LINE')}
sc=collections.Counter(); scm=collections.Counter()
for r in TH:
    if not r['islead']: continue
    sc[(r['ch'],r['scen'])]+=1
    m=mo(r['first_real_t'] if r['first_real_t'] is not None else r['first_t'])
    scm[(r['ch'],m,r['scen'])]+=1
R['scen']={'%s|%s'%k:v for k,v in sc.items()}
R['scen_month']={'%s|%s|%s'%k:v for k,v in scm.items()}
rp=collections.Counter()
for r in TH:
    if r['islead']: rp[(r['ch'],r['role'],r['paid'])]+=1
R['role_paid']={'%s|%s|%d'%k:v for k,v in rp.items()}
rs=collections.Counter((r['ch'],r['role'],r['scen']) for r in TH if r['islead'])
R['role_scen']={'%s|%s|%s'%k:v for k,v in rs.items()}
lm=collections.Counter(); wh=collections.Counter(); whp=collections.Counter()
for r in TH:
    if not r['islead']: continue
    t=r['first_real_t'] if r['first_real_t'] is not None else r['first_t']
    d=dtm(t); lm[(r['ch'],d.strftime('%Y-%m'))]+=1
    wh[(r['ch'],d.weekday(),d.hour)]+=1
    if r['paid']: whp[(r['ch'],d.weekday(),d.hour)]+=1
R['lead_month']={'%s|%s'%k:v for k,v in lm.items()}
R['wd_hour']={'%s|%d|%d'%k:v for k,v in wh.items()}
R['wd_hour_paid']={'%s|%d|%d'%k:v for k,v in whp.items()}
pm=collections.Counter((r['ch'],mo(r['paid_t'])) for r in TH if r['paid'])
R['paid_month']={'%s|%s'%k:v for k,v in pm.items()}
def med(xs):
    xs=sorted(x for x in xs if x is not None and x>=0)
    return (xs[len(xs)//2], xs[int(len(xs)*.25)], xs[min(len(xs)-1,int(len(xs)*.75))], len(xs)) if xs else None
tim={}
for ch in ('FB','LINE'):
    P=[r for r in TH if r['ch']==ch and r['paid'] and r['first_real_t'] is not None]
    tim[ch]=dict(first_to_pay=med([r['paid_t']-r['first_real_t'] for r in P]),
                 first_to_price=med([r['price_t']-r['first_real_t'] for r in P if r['price_t'] is not None and r['price_t']>=r['first_real_t']]),
                 price_to_card=med([r['card_t']-r['price_t'] for r in P if r['card_t'] is not None and r['price_t'] is not None and r['card_t']>=r['price_t']]),
                 card_to_pay=med([r['paid_t']-r['card_t'] for r in P if r['card_t'] is not None and r['paid_t']>=r['card_t']]),
                 first_human=med([r['first_h_after'] for r in P]))
R['stage_times']=tim
def bk(x):
    if x is None: return '6 ไม่มีคนตอบ'
    if x<=5: return '1 ≤5 นาที'
    if x<=15: return '2 5–15 นาที'
    if x<=60: return '3 15–60 นาที'
    if x<=180: return '4 1–3 ชม.'
    return '5 >3 ชม.'
fr=collections.Counter()
for r in TH:
    if r['islead'] and r['n_creal']>0 and not r['ongoing']:
        fr[(r['ch'],bk(r['first_h_after']),r['paid'])]+=1
R['firstreply_paid']={'%s|%s|%d'%k:v for k,v in fr.items()}
sb=collections.Counter()
for r in TH:
    if r['islead'] and r['scen'] in ('S3','S4','S5'):
        n=r['n_creal']; k=str(n) if n<=4 else '5+'
        sb[(r['ch'],r['scen'],k,'ลูกค้าเงียบ' if r['ended_by'] in ('H','B') else 'แอดมินยังไม่ตอบ')]+=1
R['stuck']={'|'.join(k):v for k,v in sb.items()}
# scenario A (only the bot ever answered) vs B (a person answered), finished leads only
bo=collections.Counter()
for r in TH:
    if r['islead'] and not r['ongoing']:
        bo[(r['ch'],'บอทอย่างเดียว' if r['n_h']==0 else 'มีคนตอบ','พิมพ์เอง' if r['n_creal']>0 else 'กดปุ่มอย่างเดียว',r['paid'])]+=1
R['botonly']={'%s|%s|%s|%d'%k:v for k,v in bo.items()}
ep=collections.Counter((r['ch'],r['entry'],r['paid']) for r in TH if r['islead'])
R['entry_paid']={'%s|%s|%d'%k:v for k,v in ep.items()}
json.dump(R,open('res1.json','w'),ensure_ascii=False)
json.dump([{k:r[k] for k in ('ch','tid','role','scen','islead','paid','paid_t','first_real_t','first_t','n_creal','n_h','entry','fams','price_t','card_t','sample_t','first_h_after','ongoing','ended_by','last_ours_txt')} for r in TH],open('th.json','w'),ensure_ascii=False)
print(json.dumps(R['overview'],ensure_ascii=False)); print(sorted(sc.items()))

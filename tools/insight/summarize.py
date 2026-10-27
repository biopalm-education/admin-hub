# -*- coding: utf-8 -*-
# Compact everything the vault notes need into summary.json (aggregates only)
import json, collections, sqlite3, re, datetime as dt
R1=json.load(open('res1.json')); R2=json.load(open('res2.json')); R3=json.load(open('res3.json'))
S={}
S['overview']=R1['overview']; S['scen']=R1['scen']; S['stage_times']=R1['stage_times']
S['role_paid']=R1['role_paid']; S['role_scen']=R1['role_scen']; S['entry_paid']=R1['entry_paid']
S['firstreply_paid']=R1['firstreply_paid']; S['stuck']=R1['stuck']
S['lead_month']=R1['lead_month']; S['paid_month']=R1['paid_month']
# scenario by month FB/LINE
S['scen_month']={k:v for k,v in R1['scen_month'].items() if k.split('|')[0] in ('FB','LINE')}
# weekday / hour totals per channel (leads) and paid
wd=collections.Counter(); hr=collections.Counter(); wdp=collections.Counter(); hrp=collections.Counter(); cell=collections.Counter()
for k,v in R1['wd_hour'].items():
    ch,w,h=k.split('|'); wd[(ch,w)]+=v; hr[(ch,h)]+=v; cell[(ch,w,h)]+=v
for k,v in R1['wd_hour_paid'].items():
    ch,w,h=k.split('|'); wdp[(ch,w)]+=v; hrp[(ch,h)]+=v
S['wd']={'%s|%s'%k:v for k,v in wd.items()}; S['hr']={'%s|%s'%k:v for k,v in hr.items()}
S['wdp']={'%s|%s'%k:v for k,v in wdp.items()}; S['hrp']={'%s|%s'%k:v for k,v in hrp.items()}
S['top_cells']={ch:sorted([(int(w),int(h),v) for (c,w,h),v in cell.items() if c==ch],key=lambda x:-x[2])[:8] for ch in ('FB','LINE','IG')}
# per-turn waits by hour
wh=collections.defaultdict(collections.Counter)
for k,v in R2['waits_hour'].items():
    ch,h,b=k.split('|'); wh[(ch,int(h))][b]+=v
S['waits_hour']={'%s|%d'%k:dict(v) for k,v in wh.items()}
S['price_src']=R2['price_src']
# templates
T=[]
for ch,key,n,rep,roles in R2['templates']:
    h=roles.get('H',0); b=roles.get('B',0)
    T.append(dict(ch=ch,key=key,n=n,rate=round(rep/n,3),role='คน' if h>=b else 'บอท'))
def pick(ch,role,low=True,k=12,minn=60):
    xs=[t for t in T if t['ch']==ch and t['role']==role and t['n']>=minn]
    xs.sort(key=lambda t:(t['rate'] if low else -t['rate']))
    return xs[:k]
S['tmpl']={'FB_H_low':pick('FB','คน',True),'FB_H_high':pick('FB','คน',False),'FB_B_low':pick('FB','บอท',True,8),
           'LINE_H_low':pick('LINE','คน',True,10),'LINE_H_high':pick('LINE','คน',False,10)}
base=collections.defaultdict(lambda:[0,0])
for t in T:
    base[(t['ch'],t['role'])][0]+=t['n']; base[(t['ch'],t['role'])][1]+=t['n']*t['rate']
S['tmpl_base']={'%s|%s'%k:round(v[1]/v[0],3) for k,v in base.items() if v[0]}
S['last_before_silence']=R2['last_before_silence'][:30]; S['last_total']=R2['last_total']
S['fast']=R2['fast']; S['fast_n']=R2['fast_n']
S['bundle_feat']=R2['bundle_feat']; S['bundle_n']=R2['bundle_n']
S['rec']=R2['rec']; S['rec_q']=R2['rec_q']
S['prob']=R2['prob']   # raw customer snippets (prob_ex / neg_ex) stay out: they can carry names typed by customers
S['botonly']=R1['botonly']
S['lastA']=R2['lastA'][:30]; S['lastA_total']=R2['lastA_total']
S['neg']=R2['neg']; S['neg_prev']=R2['neg_prev']
S['faq_intent']=R3['faq_intent']; S['faq_intent_ex']=R3['faq_intent_ex']
S['other_first']={ch:[e for e in v if e[1]>=3][:30] for ch,v in R3['other_first'].items()}
S['tmpl']['LINE_B_low']=pick('LINE','บอท',True,8)
for k in ('n_threads_typed','int5','int10','int_first','int_paid','prod','prod_partners','prod_month','prod_days','kinds','kinds_month','combos','archetypes','disc_by_kind','kind_n'):
    S[k]=R3[k]
S['faq_top']={ch:R3['faq_top'][ch][:30] for ch in R3['faq_top']}
# validation: LINE card G-codes vs registration notes (+/- 14 days of the slip)
P=json.load(open('purchases.json'))
con=sqlite3.connect('chat.db'); c=con.cursor()
notes=collections.defaultdict(list)
for tid,t,g in c.execute("SELECT tid,t,gcodes FROM linenote WHERE gcodes<>''"):
    notes[tid].append((t,set(re.findall(r'G\d{3}',g))))
agree=part=none=tot=0
for p in P['paid']:
    if p['ch']!='LINE' or not p['items']: continue
    codes={c2 for it in p['items'] for c2 in it['codes']}
    if not codes: continue
    st=p['slips'][0][0]
    ns=set()
    for t,g in notes.get(p['tid'],[]):
        if t is not None and abs(t-st)<=14*1440: ns|=g
    if not ns: none+=1; continue
    tot+=1
    if codes==ns: agree+=1
    elif codes&ns: part+=1
S['val_line_notes']=dict(compared=tot,exact=agree,partial=part,no_note=none)
amt_ok=sum(1 for p in P['paid'] if p['items'] and p['total'] and abs(p['paid_amt']-p['total'])<=1)
S['val_amount']=dict(match=amt_ok,of=sum(1 for p in P['paid'] if p['items']))
S['purch_counts']=dict(with_card=sum(1 for p in P['paid'] if p['items']),orphan=sum(1 for p in P['paid'] if not p['items']),unpaid_cards=len(P['unpaid']),
                       revised_card_in_window=sum(1 for p in P['paid'] if p['items'] and p.get('n_hdr',0)>=2))
S['roles_count']=dict(collections.Counter(v for v in json.load(open('roles.json')).values()))
json.dump(S,open('summary.json','w'),ensure_ascii=False,separators=(',',':'))
print('summary bytes',len(json.dumps(S,ensure_ascii=False)))

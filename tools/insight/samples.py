# -*- coding: utf-8 -*-
# Small masked samples for checking the rules by eye (written to the PRIVATE vault only, never printed)
import json, random, sqlite3, collections
from products import card_start
random.seed(2026)
con=sqlite3.connect('chat.db'); c=con.cursor()
TH=json.load(open('th.json')); roles=json.load(open('roles.json'))
P=json.load(open('purchases.json'))
cards={(x[0],x[1],x[2]):x[3] for x in json.load(open('cards.json'))}
def body(p):
    t=cards.get((p['ch'],p['tid'],p['t']),'').replace('\\n','\n'); k=card_start(t)
    t=t[k:] if k>=0 else t
    q=t.find('โอนชำระ')
    return (t[:q] if q>0 else t)[:900]
def kind(p):
    fams={(i['fam'],i['tape']) for i in p['items']}
    return 'หลายคน' if p['n_students']>=2 else ('หลายคอร์ส' if len(fams)>=2 else 'คอร์สเดียว')
paid=[p for p in P['paid'] if p['items']]
S={}
multi=[p for p in paid if kind(p)=='หลายคอร์ส']
S['multi']=[dict(ch=p['ch'],items=[(i['fam'],i['tape'],i['codes']) for i in p['items']],total=p['total'],paid=p['paid_amt'],disc=p['disc'],body=body(p)) for p in random.sample(multi,min(15,len(multi)))]
single=[p for p in paid if kind(p)=='คอร์สเดียว']
S['single']=[dict(ch=p['ch'],items=[(i['fam'],i['tape'],i['codes']) for i in p['items']],total=p['total'],paid=p['paid_amt'],body=body(p)) for p in random.sample(single,min(8,len(single)))]
mis=[p for p in paid if p['total'] and abs(p['paid_amt']-p['total'])>1]
S['mismatch']=[dict(ch=p['ch'],total=p['total'],paid=p['paid_amt'],nslip=len(p['slips']),body=body(p)) for p in random.sample(mis,min(10,len(mis)))]
def tail(ch,tid,n=8):
    rows=c.execute("SELECT role2,txt FROM msg WHERE ch=? AND tid=? ORDER BY t DESC,seq DESC LIMIT ?",(ch,tid,n)).fetchall()
    return [(r,x[:140]) for r,x in reversed(rows)]
def head(ch,tid,n=8):
    rows=c.execute("SELECT role2,txt FROM msg WHERE ch=? AND tid=? ORDER BY t,seq LIMIT ?",(ch,tid,n)).fetchall()
    return [(r,x[:140]) for r,x in rows]
by=collections.defaultdict(list)
for r in TH:
    if r['islead'] and r['ch']=='FB': by[r['scen']].append(r)
S['scen']={k:[dict(head=head('FB',r['tid'],6),tail=tail('FB',r['tid'],6),n_creal=r['n_creal'],n_h=r['n_h']) for r in random.sample(v,min(5,len(v)))] for k,v in by.items()}
fm={}
for l in open('firstmsgs.jsonl'):
    ch,tid,entry,pd,msgs=json.loads(l)
    if ch=='FB': fm[tid]=msgs
byr=collections.defaultdict(list)
for k,v in roles.items():
    ch,tid=k.split('|',1)
    if ch=='FB' and fm.get(tid): byr[v].append(tid)
S['roles']={k:[[m[:90] for m in fm[t][:6]] for t in random.sample(v,min(25,len(v)))] for k,v in byr.items()}
json.dump(S,open('samples.json','w'),ensure_ascii=False)
print('samples ok',{k:len(v) for k,v in S.items()})

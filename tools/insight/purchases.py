import json, collections, re, sqlite3
from products import parse_card
cards=json.load(open('cards.json'))
SLIP=re.compile(r'ตรวจสอบสลิปสำเร็จ|ชื่อผู้รับ\s*[:：]\s*(บจก\.?\s*ไบโอปาล์ม|BIOPALM)',re.I)
REF=re.compile(r'เลขอ้างอิง\s*[:：]\s*(\S+)'); AMT=re.compile(r'ยอดเงิน\s*[:：]\s*([\d,]+)')
con=sqlite3.connect('chat.db'); c=con.cursor()
bythread=collections.defaultdict(list)
for ch,tid,t,txt in cards: bythread[(ch,tid)].append((t,txt))
slips=collections.defaultdict(list); seen=set()
for ch,tid,t,txt in c.execute("SELECT ch,tid,t,txt FROM msg WHERE txt LIKE '%ตรวจสอบสลิป%' OR txt LIKE '%ชื่อผู้รับ%' ORDER BY ch,tid,t"):
    if not SLIP.search(txt): continue
    r=REF.search(txt); key=(ch, r.group(1) if r else tid+str(t))
    if key in seen: continue
    seen.add(key); a=AMT.search(txt)
    slips[(ch,tid)].append((t, int(a.group(1).replace(',','')) if a else 0))
P=[]; unpaid=[]
for k in set(bythread)|set(slips):
    cs=sorted(bythread.get(k,[])); ss=sorted(slips.get(k,[]))
    used=collections.defaultdict(list); orphan=[]
    for st,amt in ss:
        prev=[x for x in cs if x[0]<=st and st-x[0]<=30*1440]
        if prev: used[prev[-1][0]].append((st,amt))
        else: orphan.append((st,amt))
    for t,txt in cs:
        p=parse_card(txt)
        if t in used:
            p.update(ch=k[0],tid=k[1],t=t,slips=used[t],paid_amt=sum(a for _,a in used[t])); P.append(p)
        else:
            p.update(ch=k[0],tid=k[1],t=t); unpaid.append(p)
    for st,amt in orphan: P.append(dict(ch=k[0],tid=k[1],t=st,slips=[(st,amt)],paid_amt=amt,items=[],total=None,n_students=1,disc=[],mode='',orphan=True))
json.dump({'paid':P,'unpaid':unpaid},open('purchases.json','w'),ensure_ascii=False)
withcard=[p for p in P if p['items']]
print('slip events',sum(len(v) for v in slips.values()),'purchases with card',len(withcard),'slip without card (30d)',sum(1 for p in P if not p['items']))
print('by channel',collections.Counter((p['ch'],bool(p['items'])) for p in P))
print('unpaid cards (no slip linked)',len(unpaid))
paid_threads={(p['ch'],p['tid']) for p in withcard}
print('unpaid cards in threads that later paid another card',sum(1 for u in unpaid if (u['ch'],u['tid']) in paid_threads))
ok=sum(1 for p in withcard if p['total'] and abs(p['paid_amt']-p['total'])<=1)
print('amount match',ok,'/',len(withcard))
def kind(p):
    fams={(i['fam'],i['tape']) for i in p['items']}
    if p['n_students']>=2: return 'หลายคน'
    if len(fams)>=2: return 'หลายคอร์ส'
    return 'คอร์สเดียว'
print('purchase kind',collections.Counter(kind(p) for p in withcard))

import sqlite3, collections, re, json
from stage_rules import summary_marks, SLIPTXT, WIN
con=sqlite3.connect('chat.db')
cards=[]
for ch in ('FB','LINE','IG'):
    cur=con.cursor(); cur.execute("SELECT tid,t,role2,txt FROM msg WHERE ch=? ORDER BY tid,t,seq",(ch,))
    buf=[]; last=None
    def flush(th):
        ms=[(t, r in ('H','B'), x) for (_,t,r,x) in th]
        for k in summary_marks(ms):
            t_end=th[k][1]
            parts=[x for (_,t,r,x) in th if r in ('H','B') and t_end-WIN<=t<=t_end and not SLIPTXT.search(x)]
            cards.append((ch,th[0][0],t_end,'\n'.join(parts)))
    for row in cur:
        if last is not None and row[0]!=last:
            flush(buf); buf=[]
        buf.append(row); last=row[0]
    if buf: flush(buf)
print('cards',collections.Counter(x[0] for x in cards))
json.dump(cards,open('cards.json','w'),ensure_ascii=False)

import sqlite3, collections, re
exec(open('webbot.txt').read())
ATT=('[รูป/ไฟล์แนบ]','[ไฟล์แนบ]','[รูปภาพ]','[สติกเกอร์]','[ข้อความที่ IG ไม่รองรับ]',' [ไฟล์แนบ]')
con=sqlite3.connect('chat.db'); c=con.cursor()
try: c.execute('ALTER TABLE msg ADD COLUMN role2 TEXT')
except Exception: pass
c.execute("UPDATE msg SET role2=role")
TXT=collections.defaultdict(lambda:[0,0])
for role,txt in c.execute("SELECT role,txt FROM msg WHERE ch='FB' AND mo>=9 AND role IN ('H','B')"):
    k=txt.strip()[:30]
    if k in ATT or len(k)<8: continue
    TXT[k][0 if role=='H' else 1]+=1
cls={}
for k,(hm,bw) in TXT.items():
    n=hm+bw
    if n>=5:
        if hm>=0.9*n: cls[k]='H'
        elif bw>=0.9*n: cls[k]='B'
print('classes',len(cls),'H',sum(1 for v in cls.values() if v=='H'))
stat=collections.Counter()
def fix(ch, cond):
    rows=c.execute("SELECT rowid,tid,t,role,txt FROM msg WHERE ch=? AND "+cond+" ORDER BY tid,t,seq",(ch,)).fetchall()
    upd=[]; i=0
    while i<len(rows):
        j=i
        while j<len(rows) and rows[j][1]==rows[i][1]: j+=1
        th=rows[i:j]; new=[None]*len(th); lc=None
        for a,(rid,tid,t,role,txt) in enumerate(th):
            if role=='C': lc=t; continue
            if role not in ('H','B'): continue
            s=txt.strip()
            if s in ATT or s.endswith('[ไฟล์แนบ]') and len(s)<12: continue
            k=s[:30]
            if WEBBOT.search(s): new[a]='B'; stat['webbot']+=1
            elif k in cls: new[a]=cls[k]; stat['byText']+=1
            elif role=='H': new[a]='H'; stat['typed']+=1
            else: new[a]='H' if (lc is not None and t-lc>=2) else 'B'; stat['byTime']+=1
        for a,(rid,tid,t,role,txt) in enumerate(th):
            if role in ('H','B') and new[a] is None:
                nb=[b for b in range(len(th)) if new[b] is not None and abs(th[b][2]-t)<=3]
                new[a]=new[min(nb,key=lambda b:abs(b-a))] if nb else role; stat['att']+=1
        for a,(rid,tid,t,role,txt) in enumerate(th):
            if new[a] and new[a]!=role: upd.append((new[a],rid)); stat['%s>%s'%(role,new[a])]+=1
        i=j
    c.executemany('UPDATE msg SET role2=? WHERE rowid=?',upd); con.commit()
fix('FB','mo<=8'); print('FB',dict(stat)); stat.clear()
fix('IG','1=1'); print('IG',dict(stat))
print('FB H share by month after', [(mo, round(h/(h+b),3)) for mo,h,b in c.execute("SELECT mo,SUM(role2='H'),SUM(role2='B') FROM msg WHERE ch='FB' GROUP BY mo")])

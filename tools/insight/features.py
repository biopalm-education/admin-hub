# -*- coding: utf-8 -*-
import sqlite3, re, json, collections, statistics as st, datetime
from rules_pay import BTN, LOW, NOISE, PRICE, BILL, DECLINE, TOLINE, SYS
from rules_v4 import BTN4, GRADE, ASK, SUPPORT, TOPIC
from stage_rules import summary_marks, sample_at
from products import family
B=set(BTN)|set(BTN4)|{'เมนูหลัก','▶ กดปุ่ม','เชื่อมต่อบัญชีธนาคารของคุณเพื่อตรวจสอบความถูกต้องของสลิป','Connect your bank account to validate slips.'}
ATTX=re.compile(r'^\s*(\[[^\]]*\]\s*)+$|^\s*$|^〔(เบอร์|อีเมล)〕$')
SYSX=re.compile(r'ส่งการชำระเงิน|ตอบกลับโฆษณา$|ตอบกลับความคิดเห็น|responding to a user comment|replied to a post|ได้ตอบกลับโพสต์|Facebook สร้างแชทนี้|transfer request|You received a message')
SLIP=re.compile(r'ตรวจสอบสลิปสำเร็จ|ชื่อผู้รับ\s*[:：]\s*(บจก\.?\s*ไบโอปาล์ม|BIOPALM)',re.I)
_T0=datetime.datetime(2026,1,1)
END={'FB':int((datetime.datetime(2026,10,27)-_T0).total_seconds()//60),'IG':int((datetime.datetime(2026,10,27)-_T0).total_seconds()//60),
     'LINE':int((datetime.datetime(2026,10,21)-_T0).total_seconds()//60)}
def real(txt):
    t=txt.strip()
    if t in B or t in NOISE or ATTX.match(t) or SYSX.search(t): return False
    if LOW.match(t): return False
    return True
def ours(r): return r in ('H','B')
con=sqlite3.connect('chat.db'); c=con.cursor()
c.execute('DROP TABLE IF EXISTS th')
c.execute('''CREATE TABLE th(ch TEXT, tid TEXT, first_t INT, last_t INT, n INT, n_c INT, n_creal INT, n_h INT, n_b INT,
 entry TEXT, lead INT, paid INT, paid_t INT, n_slip INT, price_t INT, sample_t INT, card_t INT, first_real_t INT, first_h_after INT,
 ended_by TEXT, ongoing INT, real_before_silence INT, h_before_silence INT, last_ours_txt TEXT, waits TEXT, fams TEXT, decline INT, toline INT, months TEXT)''')
FIRST=open('firstmsgs.jsonl','w')
def flush(ch,tid,th):
    n=len(th); rs=[z[2] for z in th]
    cust=[(z[1],z[3]) for z in th if z[2]=='C']
    creal=[(t,x) for t,x in cust if real(x)]
    txts=' '.join(z[3] for z in th[:6])
    if ch in ('FB','IG'):
        if 'ตอบกลับโฆษณา' in txts or 'BIOPALM ติวเตอร์วิชาชีวะ' in txts: entry='ad'
        elif re.search(r'ตอบกลับความคิดเห็น|responding to a user comment|replied to a post|ได้ตอบกลับโพสต์',txts): entry='comment'
        else:
            fr=next((z[2] for z in th if z[2] in ('C','H','B') and not SYSX.search(z[3])),'C')
            entry='organic' if fr=='C' else 'admin_first'
    else:
        fr=next((z[2] for z in th if z[2] in ('C','H','B')),'C')
        entry='line_in' if fr=='C' else 'admin_first'
    call=' '.join(x for _,x in cust)
    lead=int(bool(any(x.strip() in B and re.search(r'สนใจ|คอร์ส|รายละเอียด|ตาราง|ค่าเรียน|สมัคร|โปร|ราคา',x) for _,x in cust) or ASK.search(call) or (GRADE.search(call) and TOPIC.search(call))))
    slips=[z[1] for z in th if SLIP.search(z[3])]
    ms=[(z[1], ours(z[2]), z[3]) for z in th]
    cards=summary_marks(ms)
    price=[z[1] for z in th if ours(z[2]) and (PRICE.search(z[3]) or BILL.search(z[3])) and not SLIP.search(z[3])]
    samp=[z[1] for z in th if ours(z[2]) and sample_at(z[1],z[3])]
    fr_t=creal[0][0] if creal else None
    fh=next((z[1] for z in th if z[2]=='H' and fr_t is not None and z[1]>=fr_t),None)
    waits=[]; i=0; seq=[(z[1],z[2],z[3]) for z in th if z[2] in ('C','H','B')]
    while i<len(seq):
        t,r,x=seq[i]
        if r=='C' and real(x):
            j=i+1
            while j<len(seq) and seq[j][1]!='H': j+=1
            waits.append(int(seq[j][0]-t) if j<len(seq) else -1)
            k=i+1
            while k<len(seq) and seq[k][1]=='C': k+=1
            i=k
        else: i+=1
    conv=[(t,r,x) for t,r,x in seq if not (r=='C' and not real(x))]
    ended=conv[-1][1] if conv else ''
    lastt=th[-1][1]; ongoing=int(END[ch]-lastt<7*1440)
    lo=next((x for t,r,x in reversed(conv) if r in ('H','B')),'')
    hb=sum(1 for t,r,x in conv if r=='H')
    fams=sorted({family(x) for t,x in creal}-{'OTHER'})
    dec=int(any(DECLINE.search(x) for _,x in creal)); tol=int(any(TOLINE.search(z[3]) for z in th if ours(z[2])))
    c.execute('INSERT INTO th VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(ch,tid,th[0][1],lastt,n,len(cust),len(creal),rs.count('H'),rs.count('B'),
        entry,lead,int(bool(slips)),(slips[0] if slips else None),len(slips),(price[0] if price else None),(samp[0] if samp else None),
        (ms[cards[0]][0] if cards else None),fr_t,(fh-fr_t if fh is not None and fr_t is not None else None),ended,ongoing,len(creal),hb,lo[:300],
        json.dumps(waits),json.dumps(fams,ensure_ascii=False),dec,tol,json.dumps(sorted({z[4] for z in th}))))
    FIRST.write(json.dumps([ch,tid,entry,int(bool(slips)),[x for _,x in creal[:10]]],ensure_ascii=False)+'\n')
if __name__=='__main__':
    for ch in ('FB','IG','LINE'):
        cur=con.cursor()
        rows=cur.execute("SELECT tid,t,role2,txt,mo FROM msg WHERE ch=? ORDER BY tid,t,seq",(ch,))
        buf=[]; last=None
        for row in rows:
            if last is not None and row[0]!=last:
                flush(ch,last,buf); buf=[]
            buf.append(row); last=row[0]
        if buf: flush(ch,last,buf)
        con.commit(); print(ch,'done',flush=True)
    FIRST.close()
    print(c.execute("SELECT ch,COUNT(*),SUM(lead),SUM(paid),SUM(n_creal>0),SUM(n_h>0) FROM th GROUP BY ch").fetchall())
    print(c.execute("SELECT ch,entry,COUNT(*),SUM(paid) FROM th GROUP BY ch,entry").fetchall())

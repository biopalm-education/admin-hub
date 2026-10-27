# -*- coding: utf-8 -*-
# Part 2 (memory-light): per-turn waits, price source, template reply rates, last message before silence,
# fast-close features, bundle features, recommendation answers, problem keywords
import sqlite3, json, collections, re, datetime as dt, bisect, gc
src=open('features.py').read().split("con=sqlite3.connect('chat.db')")[0]; ns={}; exec(src,ns); real=ns['real']
from rules_pay import PRICE, BILL
from products import family
T0=dt.datetime(2026,1,1)
TH={(r['ch'],r['tid']):r for r in json.load(open('th.json'))}
P=json.load(open('purchases.json'))
purch=collections.defaultdict(list)
for p in P['paid']:
    if p['items']: purch[(p['ch'],p['tid'])].append(p)
del P; gc.collect()
SLIP=re.compile(r'ตรวจสอบสลิปสำเร็จ|ชื่อผู้รับ',re.I)
def tkey(x):
    s=str(x).replace('\\n',' ').replace('\n',' ')
    s=re.sub(r'〔[^〕]*〕','',s); s=re.sub(r'https?://\S+','<ลิงก์>',s); s=re.sub(r'\d+','#',s)
    s=re.sub(r'[^A-Za-zก-๙#<> ]','',s); s=re.sub(r'\s+',' ',s).strip()
    return s[:60]
ATT=re.compile(r'^\s*(\[[^\]]*\]\s*)+$')
PROMO=re.compile(r'สมัคร\s*[2-9]\s*คอร์ส|[2-9]\s*คอร์ส\s*(?:ขึ้นไป|ลด)|ลด\s*\d+\s*%|ลงคู่|เรียนต่อเนื่อง|ต่อเนื่อง|ครบ\s*4|ทั้ง\s*4|Module\s*1\s*[-–]\s*4|แพ็ก|แพค|เซ็ต|เซต|โปรโมชั่น|โปร\b|ราคาพิเศษ')
SCARCE=re.compile(r'ที่นั่ง|ใกล้เต็ม|เต็มแล้ว|เหลือ\s*\d+\s*ที่|ปิดรับ|รอบสุดท้าย|วันสุดท้าย|หมดเขต|early\s*bird',re.I)
OLDSTU=re.compile(r'นักเรียนเก่า')
TRIAL=re.compile(r'ทดลองเรียน|ตัวอย่าง|คลิปตัวอย่าง')
SCHED=re.compile(r'ตารางเรียน|📌|เริ่ม\s*\d+|วัน(?:จันทร์|อังคาร|พุธ|พฤหัส|ศุกร์|เสาร์|อาทิตย์)')
REC=re.compile(r'คอร์สไหนดี|ควรเรียน|ควรลง|ลงอะไรดี|เรียนอะไรดี|เริ่มจาก|เริ่มที่ไหน|เริ่มเรียน(?:ตัว)?ไหน|แนะนำ(?:คอร์ส|หน่อย|ไหม|มั้ย|ด้วย)|เหมาะกับ|ตัวไหนดี|อันไหนดี|ช่วยแนะนำ|คอร์สไหนเหมาะ|ลงคอร์สไหน|เรียนคอร์สไหน')
APP=[('ถามระดับชั้น/เป้าหมายก่อน',re.compile(r'ระดับชั้น|เรียนอยู่ชั้น|ชั้นไหน|ชั้นอะไร|ม\.อะไร|เป้าหมาย|สอบเข้าที่|สนามสอบ|สอบที่ไหน|พื้นฐาน(?:ของน้อง)?(?:เป็น|ประมาณ)|เคยเรียน')),
     ('แนะนำเริ่มจาก Module/ปรับพื้นฐาน',re.compile(r'Module\s*1|โมดูล\s*1|ปรับพื้นฐาน|เริ่มจาก|เริ่มที่|ปูพื้น')),
     ('แนะนำคอร์สสนามสอบ',re.compile(r'สอวน|IJSO|MWIT|KVIS|เตรียมอุดม|\bTU\b|A-?Level|TCAS|สอบเข้า',re.I)),
     ('ส่งแผนการเรียน/ตาราง/รูป',re.compile(r'แผนการเรียน|ตาราง|^\s*\[รูป')),
     ('ส่งตัวอย่าง/ทดลองเรียน',TRIAL)]
PROB=[('ราคา/ขอส่วนลด',re.compile(r'แพง|ลดได้|ลดหน่อย|ลดให้|ส่วนลด|ผ่อน|ถูกกว่า|ลดราคา')),
      ('เวลาไม่ตรง/ไม่ว่าง/เต็ม',re.compile(r'ไม่ว่าง|เวลาไม่ตรง|ไม่สะดวก|ชนกับ|เวลาชน|ติดเรียน|ติดสอบ|เรียนไม่ทัน|ไม่ทันแล้ว|เต็มแล้ว')),
      # "ไว้ก่อน" alone also hits "ลงคอร์สไว้ก่อนสอบ" -> only explicit put-off phrases
      ('ลังเล/ขอคิดก่อน',re.compile(r'ขอคิด|ขอปรึกษา|ปรึกษา(?:ก่อน|ลูก|น้อง|พ่อ|แม่|ที่บ้าน|กับ|คุณ)|ขอดูก่อน|ยังไม่แน่ใจ|(?:เดี๋ยว|เด๋ว|เดะ)\s*(?:แจ้ง|ทัก|บอก|ตัดสินใจ|ปรึกษา|ถาม|สอบถาม|คุย)|ถาม(?:น้อง|ลูก)ก่อน|ขอถาม(?:น้อง|ลูก)|ขอคุยกับ(?:น้อง|ลูก|ผู้เรียน|ที่บ้าน)')),
      # "อยู่ไหมคะ" alone also hits "ยังว่างอยู่ไหมคะ" -> only nudges aimed at the admin
      ('ทวงคำตอบ/รอนาน',re.compile(r'ยังไม่ได้คำตอบ|รอนาน|ทำไมไม่ตอบ|ไม่ตอบเลย|ไม่มีคนตอบ|ช่วยตอบ|ตอบด้วย|(?:มีใคร|มีคน|แอดมิน)อยู่ไหม|^\s*แอดมิน(?:คะ|ครับ|ค่ะ)?\s*$|^\s*(?:ฮัลโหล|hello)\s*$',re.I)),
      ('เข้าเรียน/ลิงก์/เอกสาร มีปัญหา',re.compile(r'เข้าไม่ได้|ไม่ได้รับ(?:ลิ้ง|ลิงก์|ลิงค์|อีเมล|เมล)|รหัสผ่าน|เปิดไม่ได้|ดูไม่ได้|เอกสาร(?:ไม่|ยัง)|ไฟล์(?:ไม่|ยัง)|ย้อนหลังไม่')),
      ('การโอน/สลิป/ใบเสร็จ',re.compile(r'โอนไม่ได้|โอนผิด|สลิป(?:ไม่|ผิด|ยัง)|ใบเสร็จ|ใบกำกับ|บัตรเครดิต|ผ่อนชำระ|คืนเงิน')),
      # "ลาเรียน" is inside "เวลาเรียน" -> lookbehind
      ('ขอเลื่อน/ลา/เปลี่ยนกลุ่ม',re.compile(r'ขอเลื่อน|เลื่อน(?:เรียน|วัน|คลาส|กลุ่ม|รอบ|ไป(?:วัน|รอบ|กลุ่ม|เรียน))|(?<!เว)ลาเรียน|ขอลา(?!ย)|เปลี่ยนกลุ่ม|ย้ายกลุ่ม|ขาดเรียน'))]
# a hit that is really something else (e.g. "โอนแล้วเดี๋ยวแจ้ง" is not hesitation)
PROB_SKIP={'ลังเล/ขอคิดก่อน':re.compile(r'โอน|สลิป|จอง')}
# customer reactions that say our last message did not land
NEG=[('ไม่สนใจ/ให้หยุดส่ง',re.compile(r'ไม่สนใจ(?:แล้ว)?(?:ค่ะ|ครับ|คะ|นะคะ|นะครับ)?\s*$|ไม่ต้อง(?:ส่ง|ทัก|ตาม)(?:มา|ข้อความ|แล้ว)|หยุดส่ง|เลิกส่ง|สแปม|spam',re.I)),
     ('ตอบไม่ตรง/ต้องถามซ้ำ',re.compile(r'ตอบไม่ตรง|ไม่ตรงคำถาม|ไม่ได้ถาม(?:เรื่อง|อันนี้|แบบนี้|ว่า)|ที่ถาม(?:คือ|ไปคือ|ไปว่า)|(?:เคย)?(?:สอบ)?ถามไปแล้ว|ไม่ตอบคำถาม|ยังไม่ได้ตอบ|ช่วยตอบคำถาม')),
     ('อยากคุยกับคน/ไม่อยากคุยกับบอท',re.compile(r'คุยกับ(?:คน|แอดมิน|เจ้าหน้าที่|พนักงาน)|ขอคุยกับ(?:คน|แอดมิน|เจ้าหน้าที่)|แอดมินตัวจริง|เป็นบอท|ใช่บอท|บอทตอบ|ข้อความอัตโนมัติ|ระบบอัตโนมัติ|ตอบอัตโนมัติ')),
     ('ไม่เข้าใจ/งง/ยาวไป',re.compile(r'ยาวไป|อ่านไม่ไหว|^\s*(?:แม่|ผม|หนู|ดิฉัน|เรา)?\s*(?:ยัง)?ไม่เข้าใจ(?:ค่ะ|ครับ|คะ|เลย|อ่ะ|นะคะ)?\s*$|^\s*งง+|งง+(?:เลย|มาก|ค่ะ|ครับ)|ดู(?:แผ่น|รูป|ตาราง)?(?:นี้|นี่)?(?:แล้ว|ละ)?งง'))]
CARDISH=re.compile(r'รหัสคอร์ส|สรุปรายละเอียด|ยอดชำระ|คงเหลือชำระ|โอนชำระ|〔บัญชีBioPalm〕|ชื่อบัญชี')
END={'FB':int((dt.datetime(2026,10,27)-T0).total_seconds()//60),'IG':int((dt.datetime(2026,10,27)-T0).total_seconds()//60),'LINE':int((dt.datetime(2026,10,21)-T0).total_seconds()//60)}
con=sqlite3.connect('chat.db')
waits=collections.Counter(); tn=collections.Counter(); tr=collections.Counter(); lastk=collections.Counter(); lastk_all=0
fastf=collections.defaultdict(collections.Counter); fastn=collections.Counter()
bund=collections.defaultdict(collections.Counter); bundn=collections.Counter()
rec=collections.defaultdict(lambda:[0,0]); recq=collections.Counter()
prob=collections.defaultdict(lambda:[0,0]); probex=collections.defaultdict(list)
pricesrc=collections.Counter()
lastA=collections.Counter(); lastA_all=collections.Counter()
neg=collections.defaultdict(lambda:[0,0]); negex=collections.defaultdict(list); negprev=collections.defaultdict(collections.Counter)
def process(ch,th):
    global lastk_all
    tid=th[0][0]; T=TH.get((ch,tid))
    if not T or not T['islead']: return
    cr=[(t,x) for _,t,r,x in th if r=='C' and real(x)]; crt=[t for t,_ in cr]
    def replied(t,win=1440):
        k=bisect.bisect_right(crt,t)
        return k<len(crt) and crt[k]-t<=win
    seq=[(t,r,x) for _,t,r,x in th]
    k=0
    while k<len(seq):
        t,r,x=seq[k]
        if r=='C' and real(x):
            q=k+1
            while q<len(seq) and seq[q][1]!='H': q+=1
            w=seq[q][0]-t if q<len(seq) else None
            if not (w is None and END[ch]-t<2*1440):
                h=(T0+dt.timedelta(minutes=t)).hour
                b='ไม่มีคนตอบ' if w is None else ('≤15' if w<=15 else ('15–60' if w<=60 else ('1–3ชม' if w<=180 else '>3ชม')))
                waits[(ch,h,b)]+=1
            while k<len(seq) and seq[k][1]=='C': k+=1
        else: k+=1
    pr=next((r for _,t,r,x in th if r in ('H','B') and (PRICE.search(x) or BILL.search(x)) and not SLIP.search(x)),None)
    if pr: pricesrc[(ch,pr,T['scen'])]+=1
    if not T['ongoing']:
        for _,t,r,x in th:
            if r in ('H','B') and not ATT.match(x) and len(x.strip())>=8 and not SLIP.search(x):
                key=tkey(x)
                if len(key)<6: continue
                tn[(ch,key,r)]+=1
                if replied(t): tr[(ch,key,r)]+=1
        if T['scen'] in ('S3','S4','S5') and T['ended_by'] in ('H','B'):
            lo=next((x for _,t,r,x in reversed(th) if r in ('H','B') and not ATT.match(x) and len(x.strip())>=8),None)
            if lo: lastk[(ch,tkey(lo))]+=1; lastk_all+=1
        # scenario A: only the bot ever answered and the customer did not buy
        if not T['paid'] and T['n_h']==0:
            lo=next((x for _,t,r,x in reversed(th) if r=='B' and not ATT.match(x) and len(x.strip())>=8),None)
            if lo: lastA[(ch,tkey(lo))]+=1; lastA_all[ch]+=1
    if T['paid'] and T['first_real_t'] is not None:
        d=(T['paid_t']-T['first_real_t'])/1440
        g='≤1 วัน' if d<=1 else ('1–7 วัน' if d<=7 else '>7 วัน')
        pre=[(t,r,x) for _,t,r,x in th if t<=T['paid_t']]
        # leave out the payment card itself (it always has a schedule and often a discount line)
        ours=[x for t,r,x in pre if r in ('H','B') and not CARDISH.search(x)]; hum=[x for t,r,x in pre if r=='H']
        f=fastf[(ch,g)]; fastn[(ch,g)]+=1
        f['ส่งตัวอย่าง/ทดลองเรียน']+=int((T['sample_t'] is not None and T['sample_t']<=T['paid_t']) or any(TRIAL.search(x) for x in ours))
        f['บอกโปร/ส่วนลด']+=int(any(PROMO.search(x) for x in ours))
        f['ราคานักเรียนเก่า']+=int(any(OLDSTU.search(x) for x in ours))
        f['บอกที่นั่ง/หมดเขต']+=int(any(SCARCE.search(x) for x in ours))
        f['ส่งตาราง/กลุ่มเรียน']+=int(any(SCHED.search(x) for x in ours))
        f['คนตอบครั้งแรก ≤5 นาที']+=int(T['first_h_after'] is not None and T['first_h_after']<=5)
        f['แอดมินพิมพ์ ≥10 ข้อความ']+=int(len(hum)>=10)
        f['ลูกค้าเป็นผู้ปกครอง']+=int(T['role']=='parent'); f['ลูกค้าเป็นนักเรียน']+=int(T['role']=='student')
    for p in purch.get((ch,tid),[]):
        fams={(it['fam'],it['tape']) for it in p['items']}
        kind='หลายคน' if p['n_students']>=2 else ('หลายคอร์ส' if len(fams)>=2 else 'คอร์สเดียว')
        pre=[(t,r,x) for _,t,r,x in th if t<p['t']]
        ours=[x for t,r,x in pre if r in ('H','B') and not CARDISH.search(x)]
        cf=set()
        for t,r,x in pre:
            if r=='C' and real(x): cf|={family(x)}-{'OTHER'}
        b=bund[(ch,kind)]; bundn[(ch,kind)]+=1
        b['แอดมินเสนอโปร/ลงหลายคอร์สก่อนสรุปยอด']+=int(any(PROMO.search(x) for x in ours))
        b['ลูกค้าพูดถึง ≥2 คอร์สเอง']+=int(len(cf)>=2)
        b['ราคานักเรียนเก่า']+=int('นักเรียนเก่า' in p.get('disc',[]))
        b['มีเทปในใบสรุป']+=int(any(it['tape'] for it in p['items']))
        b['ส่งตัวอย่างก่อนสรุปยอด']+=int(T['sample_t'] is not None and T['sample_t']<p['t'])
        b['ผู้ปกครอง']+=int(T['role']=='parent'); b['นักเรียน']+=int(T['role']=='student')
    for t,x in cr:
        if REC.search(x) or x.strip()=='ช่วยแนะนำคอร์สเรียน':
            isbtn=x.strip()=='ช่วยแนะนำคอร์สเรียน'
            recq[(ch,'ปุ่ม' if isbtn else 'พิมพ์เอง')]+=1
            hr=next((y for _,tt,r,y in th if r=='H' and tt>=t and tt-t<=1440),None)
            ap=[a for a,rx in APP if hr and rx.search(hr)] or (['ไม่มีคนตอบใน 24 ชม.'] if hr is None else ['ตอบแบบอื่น'])
            for a in ap:
                z=rec[(ch,a)]; z[0]+=1; z[1]+=T['paid']
            break
    for lab,rx in PROB:
        sk=PROB_SKIP.get(lab)
        hit=next((x for t,x in cr if rx.search(x) and not (sk and sk.search(x))),None)
        if hit:
            z=prob[(ch,lab)]; z[0]+=1; z[1]+=T['paid']
            if len(probex[(ch,lab)])<40: probex[(ch,lab)].append(hit[:90])
    for lab,rx in NEG:
        j=next((j for j,(t,r,x) in enumerate(seq) if r=='C' and real(x) and rx.search(x)),None)
        if j is None: continue
        z=neg[(ch,lab)]; z[0]+=1; z[1]+=T['paid']
        if len(negex[(ch,lab)])<40: negex[(ch,lab)].append(seq[j][2][:90])
        pv=next(((r,x) for t,r,x in reversed(seq[:j]) if r in ('H','B') and not ATT.match(x) and len(x.strip())>=8),None)
        if pv: negprev[(ch,lab)][('คน' if pv[0]=='H' else 'บอท')+' · '+tkey(pv[1])]+=1
for ch in ('FB','LINE','IG'):
    cur=con.cursor(); cur.execute("SELECT tid,t,role2,txt FROM msg WHERE ch=? ORDER BY tid,t,seq",(ch,))
    buf=[]; last=None
    for row in cur:
        if last is not None and row[0]!=last:
            process(ch,buf); buf=[]
        buf.append(row); last=row[0]
    if buf: process(ch,buf)
    # prune rare templates per channel to keep memory low
    for k in [k for k,v in tn.items() if k[0]==ch and v<10]:
        tn.pop(k,None); tr.pop(k,None)
    gc.collect(); print(ch,'ok',len(tn),flush=True)
R={}
R['waits_hour']={'%s|%d|%s'%k:v for k,v in waits.items()}
R['price_src']={'%s|%s|%s'%k:v for k,v in pricesrc.items()}
agg=collections.defaultdict(lambda:[0,0,collections.Counter()])
for (ch,key,r),n in tn.items():
    a=agg[(ch,key)]; a[0]+=n; a[1]+=tr.get((ch,key,r),0); a[2][r]+=n
R['templates']=[(k[0],k[1],v[0],v[1],dict(v[2])) for k,v in agg.items() if v[0]>=40]
R['last_before_silence']=[(k[0],k[1],v) for k,v in lastk.most_common(80)]; R['last_total']=lastk_all
R['fast']={'%s|%s'%k:dict(v) for k,v in fastf.items()}; R['fast_n']={'%s|%s'%k:v for k,v in fastn.items()}
R['bundle_feat']={'%s|%s'%k:dict(v) for k,v in bund.items()}; R['bundle_n']={'%s|%s'%k:v for k,v in bundn.items()}
R['rec']={'%s|%s'%k:[v[0],v[1]] for k,v in rec.items()}; R['rec_q']={'%s|%s'%k:v for k,v in recq.items()}
R['prob']={'%s|%s'%k:v for k,v in prob.items()}; R['prob_ex']={'%s|%s'%k:v for k,v in probex.items()}
R['lastA']=[(k[0],k[1],v) for k,v in lastA.most_common(60)]; R['lastA_total']=dict(lastA_all)
R['neg']={'%s|%s'%k:v for k,v in neg.items()}; R['neg_ex']={'%s|%s'%k:v for k,v in negex.items()}
R['neg_prev']={'%s|%s'%k:v.most_common(8) for k,v in negprev.items()}
json.dump(R,open('res2.json','w'),ensure_ascii=False)
print('templates>=40',len(R['templates']),'last-before-silence total',lastk_all)

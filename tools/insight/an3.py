# -*- coding: utf-8 -*-
import json, collections, re, datetime as dt, statistics as st
from products import FAMNAME, GROUP, family
T0=dt.datetime(2026,1,1)
TH={(r['ch'],r['tid']):r for r in json.load(open('th.json'))}
INT=[('แจ้ง/ถามระดับชั้น',re.compile(r'^\s*(?:ม|ป)\.?\s?[1-6]|(?:^|[^ก-๙]|น้อง|ชั้น|สนใจ|ลูก|หนู|คอร์ส|ของ)(?:ม|ป)\s?\.?\s?[1-6](?!\d)|มัธยม(?:ศึกษา)?(?:ปีที่)?\s?[1-6]|ม\.?\s?(?:ต้น|ปลาย)|(?:ขึ้น|อยู่|เรียน)\s*(?:ชั้น\s*)?(?:ม|ป)\.?\s?[1-6]|ม\.ต้น|ม\.ปลาย|มอ\s?[1-6]|year\s?\d|grade\s?\d|ซิ่ว',re.I)),
     ('ราคา/ค่าเรียน',re.compile(r'ราคา|เท่าไ|ค่าเรียน|กี่บาท|ค่าใช้จ่าย|คชจ|ค่าคอร์ส|ค่าบริการ')),
     ('ตารางเรียน/วันเวลา/รอบ',re.compile(r'ตาราง|วันไหน|กี่โมง|เวลาเรียน|เริ่มเรียน|เริ่มวัน|เปิดรอบ|รอบไหน|รอบหน้า|กลุ่มไหน|เรียนวัน|ปิดเทอม|เสาร์|อาทิตย์|ช่วงไหน|กี่ครั้ง|กี่ชั่วโมง|ระยะเวลา')),
     ('รูปแบบเรียน (สด/ออนไลน์/เทป/สถานที่)',re.compile(r'เรียนแบบไหน|เรียนยังไง|เรียนอย่างไร|สอนแบบไหน|เรียนผ่าน|ออนไลน์|online|onsite|ออนไซต์|เรียนสด|สอนสด|เทป|ย้อนหลัง|rerun|zoom|meet|ที่ไหน|สถานที่|สาขา|เรียนที่|ตัวต่อตัว|ส่วนตัว',re.I)),
     ('รายละเอียด/เนื้อหาคอร์ส',re.compile(r'มีอะไรบ้าง|ให้บริการอะไร|มีแบบไหน|มีคอร์สไหน|รายละเอียด|เนื้อหา|เรียนอะไร|สอนอะไร|หัวข้อ|มีคอร์สอะไร|คอร์สอะไรบ้าง|มีคอร์ส|เอกสาร|ชีท|หนังสือ')),
     ('ขอคำแนะนำคอร์ส',re.compile(r'แนะนำ|ควรเรียน|ควรลง|ไหนดี|อะไรดี|เหมาะ|เริ่มจาก|เริ่มที่')),
     ('เป้าหมายสอบ (สอวน./IJSO/สอบเข้า/A-Level)',re.compile(r'สอวน|IJSO|MWIT|KVIS|มหิดล|กำเนิดวิทย์|เตรียมอุดม|\bTU\b|สอบเข้า|วมว|จภ|จุฬาภรณ์|A-?Level|TCAS|กสพท|แพทย์|หมอ|สสวท',re.I)),
     ('พื้นฐาน/ตามทันไหม',re.compile(r'พื้นฐาน|ไม่เคยเรียน|ตามทัน|ยากไหม|ยากมั้ย|เรียนไม่ทัน|อ่อน|ไม่เก่ง|ปูพื้น')),
     ('โปร/ส่วนลด',re.compile(r'โปร|ส่วนลด|ลดไหม|ลดได้|ลดราคา|early|ราคาพิเศษ',re.I)),
     ('วิธีสมัคร/จอง/ชำระเงิน',re.compile(r'สมัคร|ลงทะเบียน|จอง|โอน|ชำระ|(?<!ค่าใช้)จ่าย|ผ่อน|บัตร')),
     ('ตัวอย่าง/ทดลองเรียน/รีวิว',re.compile(r'ตัวอย่าง|ทดลอง|คลิป|รีวิว|ผลงาน')),
     ('เรื่องนักเรียนปัจจุบัน (ลิงก์/เลื่อน/เอกสาร)',re.compile(r'ลิ้ง|ลิงก์|ลิงค์|เข้าไม่ได้|รหัสผ่าน|ขาดเรียน|(?<!เว)ลาเรียน|เลื่อน|การบ้าน|ใบเสร็จ|ไม่ได้รับ')),
     ('ทักทาย/สนใจ (ยังไม่ระบุ)',re.compile(r'^(?:สนใจ|สอบถาม|สวัสดี|ขอข้อมูล|ขอรายละเอียด)\S{0,6}$'))]
GREET=re.compile(r'^(?:รบกวน)?(?:สนใจ|สอบถาม|สวัสดี|ขอข้อมูล|ขอรายละเอียด)(?:คอร์สเรียน|คอร์ส|เรียน|คอร์สนี้|อันนี้|ข้อมูล|รายละเอียด|เพิ่มเติม)?$')
PART=re.compile(r'[\s\.\?!~,]+|ค่ะ|คะ|ครับ|คับ|ค่า|นะ|จ้า|จ้ะ|ka|krub|[😊🙏❤️👍🥰💕🏻]')
NAMED={'M1','M2','M3','M4','M1A','M2A','M3A','M4A','M5A','AL1','AL2','AL3','AL4','WRAP1','WRAP2','ALD','LAB'}
def intents(x):
    out=[lab for lab,rx in INT if rx.search(x) and lab!='ทักทาย/สนใจ (ยังไม่ระบุ)']
    if family(x) in NAMED: out.append('ระบุ Module/คอร์สที่สนใจ')
    if not out and GREET.match(PART.sub('',x.lower())): out=['ทักทาย/สนใจ (ยังไม่ระบุ)']
    return out or ['อื่น ๆ']
R={}
it5=collections.Counter(); it10=collections.Counter(); itm=collections.Counter(); nthr=collections.Counter(); itpaid=collections.Counter()
first1=collections.Counter()
def norm(x):
    s=re.sub(r'〔[^〕]*〕','',x); s=re.sub(r'(?:ค่ะ|คะ|ครับ|คับ|ค่า|คร้าบ|นะ|จ้า|จ้ะ|ka|krub)+\s*$','',s.strip())
    s=re.sub(r'[\s\.\?!,~😊🙏❤️👍🥰💕🏻]+',' ',s).strip().lower()
    return s
faq=collections.Counter(); faqq=collections.Counter()
fqi=collections.Counter(); fqex=collections.defaultdict(collections.Counter); oth=collections.Counter()
QW=re.compile(r'ไหม|มั้ย|มั๊ย|ไหน|อะไร|เท่าไ|ยังไง|อย่างไร|กี่|หรือเปล่า|หรือป่าว|ได้ไหม|\?|ไหร')
for l in open('firstmsgs.jsonl'):
    ch,tid,entry,paid,msgs=json.loads(l)
    T=TH.get((ch,tid))
    if not T or not T['islead'] or not msgs: continue
    nthr[ch]+=1
    s5=set(); s10=set(); sq=set()
    for k,x in enumerate(msgs[:10]):
        ii=intents(x)
        for lab in ii:
            itm[(ch,lab)]+=1
            s10.add(lab)
            if k<5: s5.add(lab)
        n=norm(x)
        if 2<=len(n)<=60:
            faq[(ch,n)]+=1
            if QW.search(x): faqq[(ch,n)]+=1
        if QW.search(x):                      # a question: count each topic once per chat
            for lab in ii:
                if lab not in sq: fqi[(ch,lab)]+=1; sq.add(lab)
                if 2<=len(n)<=60: fqex[(ch,lab)][n]+=1
    for lab in intents(msgs[0]): first1[(ch,lab)]+=1
    if intents(msgs[0])==['อื่น ๆ']:
        n=norm(msgs[0])
        if 2<=len(n)<=60: oth[(ch,n)]+=1
    for lab in s5: it5[(ch,lab)]+=1
    for lab in s10: it10[(ch,lab)]+=1; itpaid[(ch,lab)]+=paid
R['n_threads_typed']=dict(nthr)
R['int5']={'%s|%s'%k:v for k,v in it5.items()}; R['int10']={'%s|%s'%k:v for k,v in it10.items()}
R['int_first']={'%s|%s'%k:v for k,v in first1.items()}; R['int_msgs']={'%s|%s'%k:v for k,v in itm.items()}
R['int_paid']={'%s|%s'%k:v for k,v in itpaid.items()}
R['faq_top']={ch:[(k[1],v) for k,v in faqq.most_common(6000) if k[0]==ch][:40] for ch in ('FB','LINE','IG')}
R['faq_any_top']={ch:[(k[1],v) for k,v in faq.most_common(6000) if k[0]==ch][:40] for ch in ('FB','LINE','IG')}
R['faq_intent']={'%s|%s'%k:v for k,v in fqi.items()}
R['faq_intent_ex']={'%s|%s'%k:[e for e in v.most_common(8) if e[1]>=3] for k,v in fqex.items()}
R['other_first']={ch:[(k[1],v) for k,v in oth.most_common(3000) if k[0]==ch][:40] for ch in ('FB','LINE')}
P=json.load(open('purchases.json'))
paid=[p for p in P['paid'] if p['items']]
def kind(p):
    fams={(i['fam'],i['tape']) for i in p['items']}
    return 'หลายคน' if p['n_students']>=2 else ('หลายคอร์ส' if len(fams)>=2 else 'คอร์สเดียว')
prod=collections.defaultdict(lambda:collections.Counter()); partners=collections.defaultdict(collections.Counter); pm=collections.Counter(); days=collections.defaultdict(list)
for p in paid:
    k=kind(p); fs=sorted({i['fam'] for i in p['items']})
    m=(T0+dt.timedelta(minutes=p['slips'][0][0])).strftime('%Y-%m')
    T=TH.get((p['ch'],p['tid']))
    for f in fs:
        c=prod[f]; c['n']+=1; c[k]+=1; c['ch_'+p['ch']]+=1
        c['tape']+=int(any(i['tape'] for i in p['items'] if i['fam']==f)); c['live']+=int(any(not i['tape'] for i in p['items'] if i['fam']==f))
        c['oldstu']+=int('นักเรียนเก่า' in p['disc']); c['disc2']+=int('สมัคร 2 คอร์สขึ้นไป' in p['disc'] or 'ลด %' in p['disc'])
        if T: c['role_'+T['role']]+=1; c['sample']+=int(T['sample_t'] is not None and T['sample_t']<p['t'])
        pm[(f,m)]+=1
        for g in fs:
            if g!=f: partners[f][g]+=1
        if T and T['first_real_t'] is not None and p['slips'][0][0]>=T['first_real_t']: days[f].append((p['slips'][0][0]-T['first_real_t'])/1440)
R['prod']={f:dict(v) for f,v in prod.items()}
R['prod_partners']={f:v.most_common(4) for f,v in partners.items()}
R['prod_month']={'%s|%s'%k:v for k,v in pm.items()}
R['prod_days']={f:(round(st.median(v),1),len(v)) for f,v in days.items() if v}
R['kinds']={'%s|%s'%k:v for k,v in collections.Counter((p['ch'],kind(p)) for p in paid).items()}
R['kinds_month']={'%s|%s'%k:v for k,v in collections.Counter(((T0+dt.timedelta(minutes=p['slips'][0][0])).strftime('%Y-%m'),kind(p)) for p in paid).items()}
combo=collections.Counter()
for p in paid:
    if kind(p)=='หลายคอร์ส':
        combo[' + '.join(sorted({FAMNAME[i['fam']]+(' [เทป]' if i['tape'] else '') for i in p['items']}))]+=1
R['combos']=combo.most_common(40)
def arche(p):
    fs={i['fam'] for i in p['items']}; gs={GROUP[f] for f in fs}
    tape={i['tape'] for i in p['items']}
    if len(gs)==1:
        g=next(iter(gs))
        a='Module/เล่มต่อเนื่องในสายเดียวกัน' if ('Module' in g or 'A-Level Bio' in g or 'Wrap' in g) else ('สนามสอบเข้า ม.4 หลายคอร์ส' if g=='สอบเข้า ม.4' else 'สายเดียวกัน')
    else:
        a='ข้ามสาย (เช่น Module + สนามสอบ)'
    if tape=={True,False}: a+=' · สด+เทป'
    elif tape=={True}: a+=' · เทปทั้งหมด'
    return a
R['archetypes']=collections.Counter(arche(p) for p in paid if kind(p)=='หลายคอร์ส').most_common()
R['disc_by_kind']={'%s|%s'%k:v for k,v in collections.Counter((kind(p),d) for p in paid for d in p['disc']).items()}
R['kind_n']=dict(collections.Counter(kind(p) for p in paid))
json.dump(R,open('res3.json','w'),ensure_ascii=False)
print('ok', R['kinds'], R['archetypes'][:8])

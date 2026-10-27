# -*- coding: utf-8 -*-
import re, json
CAT=json.load(open('catalog.json',encoding='utf-8'))
FAMNAME={'M1':'Module 1 (ม.ต้น)','M2':'Module 2 (ม.ต้น)','M3':'Module 3 (ม.ต้น)','M4':'Module 4 (ม.ต้น)',
 'M1A':'Module 1 adv (ม.4 เทอม 1)','M2A':'Module 2 adv (ม.4 เทอม 2)','M3A':'Module 3 adv (ม.5 เทอม 1)','M4A':'Module 4 adv (ม.5 เทอม 2)','M5A':'Module 5 adv',
 'AL1':'A-Level Bio 1 (สสวท ม.4 เทอม 1)','AL2':'A-Level Bio 2 (สสวท ม.4 เทอม 2)','AL3':'A-Level Bio 3 (สสวท ม.5 เทอม 1)','AL4':'A-Level Bio 4 (สสวท ม.5 เทอม 2)',
 'ENT':'สรุปเนื้อหาสอบเข้า ม.4','MWIT':'ตะลุยโจทย์ MWIT/KVIS','TU':'ตะลุยโจทย์เตรียมอุดม TU','IJSO':'IJSO','SOWN':'สอวน. ชีวะ',
 'WRAP1':'Wrap up 1','WRAP2':'Wrap up 2','ALD':'ตะลุยโจทย์ A-Level/TCAS','LAB':'LAB X BIOPALM','PW':'กลุ่ม ภว.','OTHER':'อื่น ๆ'}
GROUP={'M1':'ม.ต้น Module','M2':'ม.ต้น Module','M3':'ม.ต้น Module','M4':'ม.ต้น Module',
 'M1A':'ม.ปลาย Module adv','M2A':'ม.ปลาย Module adv','M3A':'ม.ปลาย Module adv','M4A':'ม.ปลาย Module adv','M5A':'ม.ปลาย Module adv',
 'AL1':'ม.ปลาย A-Level Bio (สสวท)','AL2':'ม.ปลาย A-Level Bio (สสวท)','AL3':'ม.ปลาย A-Level Bio (สสวท)','AL4':'ม.ปลาย A-Level Bio (สสวท)',
 'ENT':'สอบเข้า ม.4','MWIT':'สอบเข้า ม.4','TU':'สอบเข้า ม.4','IJSO':'แข่งขัน IJSO','SOWN':'แข่งขัน สอวน.',
 'WRAP1':'ม.ปลาย Wrap up','WRAP2':'ม.ปลาย Wrap up','ALD':'ม.ปลาย ตะลุยโจทย์ A-Level','LAB':'LAB','PW':'กลุ่ม ภว.','OTHER':'อื่น ๆ'}
TERM={('4','1'):'1',('4','2'):'2',('5','1'):'3',('5','2'):'4'}
def family(name, level=''):
    n=str(name or '')
    if re.search(r'ภว',n): return 'PW'
    if re.search(r'LAB|แลป|แล็บ|แลบ',n,re.I): return 'LAB'
    if re.search(r'สอวน',n): return 'SOWN'
    if re.search(r'IJSO',n,re.I): return 'IJSO'
    m=re.search(r'wrap\s*-?\s*up\s*([12])',n,re.I)
    if m: return 'WRAP'+m.group(1)
    m=re.search(r'A-?\s?level\s*Bio\s*([1-4])',n,re.I)
    if m: return 'AL'+m.group(1)
    if re.search(r'สสวท',n):
        m=re.search(r'ม\.?\s?([45])\s*เทอม\s*([12])',n)
        if m and (m.group(1),m.group(2)) in TERM: return 'AL'+TERM[(m.group(1),m.group(2))]
    m=re.search(r'(?:Module|โมดูล|M)\s*([1-5])\s*(?:adv|advance|แอดวานซ์|Adv)',n,re.I)
    if m: return 'M%sA'%m.group(1)
    if re.search(r'ตะลุยโจทย์.*(A-?\s?Level|TCAS|มหาวิทยาลัย|70\s*\+)|โค้ง\s*A-?\s?Level|TCAS',n,re.I): return 'ALD'
    if re.search(r'สรุปเนื้อหา.*สอบเข้า|สอบเข้า\s*ม\.?\s?4.*สรุป',n) and not re.search(r'ตะลุย',n): return 'ENT'
    if re.search(r'MWIT|KVIS|มหิดล|กำเนิดวิทย์',n,re.I): return 'MWIT'
    if re.search(r'\bTU\b|TU\s?\d|เตรียมอุดม',n): return 'TU'
    if re.search(r'สอบเข้า\s*ม\.?\s?4',n): return 'ENT'
    m=re.search(r'(?:Module|โมดูล)\s*([1-5])',n,re.I)
    if m:
        k=m.group(1)
        if 'ปลาย' in str(level) or re.search(r'ม\.?\s?[456]\s*เทอม',n): return 'M%sA'%k
        return 'M'+k
    return 'OTHER'
def fam_of_code(g):
    e=CAT.get(g)
    return family(e[0],e[1]) if e else None
GC=re.compile(r'G\s?-?\s?(\d{3})')
def card_heads(t):
    """Positions of card headers that are followed by course lines (a 30-min window can hold a first and a revised card)."""
    ks=[m.start() for m in re.finditer('สรุปรายละเอียด',t)]
    out=[]
    for j,q in enumerate(ks):
        end=ks[j+1] if j+1<len(ks) else len(t)
        if 'รหัสคอร์ส' in t[q:end]: out.append(q)
    return ks,out
def card_start(t):
    ks,full=card_heads(t)
    if full: return full[-1]          # the latest complete card = what the customer was asked to pay
    return ks[0] if ks else -1
def parse_card(text):
    t=str(text).replace('\\n','\n')
    k=card_start(t)
    n_hdr=len(card_heads(t)[1])
    body=t[k:] if k>=0 else t
    nstu=re.search(r'สำหรับนักเรียน\s*(\d+)\s*ท่าน',body)
    blocks=re.split(r'(?=รหัสคอร์ส)',body)
    items=[]
    for b in blocks:
        if not b.startswith('รหัสคอร์ส'): continue
        codes=['G'+x for x in GC.findall(b.split('\n')[0]+' '+b[:40])]
        nm=re.search(r'คอร์ส(?:ที่ลงทะเบียน)?\s*[:：]?\s*([^\n]+)',b[len('รหัสคอร์ส'):])
        name=nm.group(1).strip() if nm else ''
        sched=bool(re.search(r'วัน(?:จันทร์|อังคาร|พุธ|พฤหัส|ศุกร์|เสาร์|อาทิตย์)|ทุกวัน|เวลา\s*\d|\d{1,2}[.:]\d{2}\s*[-–]\s*\d{1,2}[.:]\d{2}|📌',b))
        tape=('G000' in codes) or (bool(re.search(r'เทป|ย้อนหลัง|RERUN',b,re.I)) and not sched)
        fam=family(name)
        if fam=='OTHER':
            for g in codes:
                f=fam_of_code(g)
                if f: fam=f; break
        if fam=='OTHER': fam=family(b[:200])
        items.append(dict(codes=codes,name=name[:60],fam=fam,tape=tape))
    if not items:
        fams=[]
        for line in body.split('\n'):
            f=family(line)
            if f!='OTHER' and f not in fams: fams.append(f)
        items=[dict(codes=['G'+x for x in GC.findall(body)][:1],name='',fam=f,tape=bool(re.search(r'เทป|ย้อนหลัง',body))) for f in fams]
    cut=len(body)
    for mk in ('โอนชำระ','ธนาคาร','〔บัญชีBioPalm〕'):
        q=body.find(mk)
        if q>=0: cut=min(cut,q)
    pre=body[:cut]
    MONEY=re.compile(r'(?:(?:ยอดชำระ|ชำระ|ค่าเรียน|ราคา|เหลือ|รวม|=|ลด\S*)\s*[:：]?\s*)(\d{1,3},\d{3}|\d{4,5})|(\d{1,3},\d{3}|\d{3,5})(?:\.\d+)?\s*(?:บาท|฿|\.-)')
    amts=[]
    for m in MONEY.finditer(pre):
        v=int((m.group(1) or m.group(2)).replace(',',''))
        if 2560<=v<=2575 and not m.group(2): continue
        amts.append(v)
    tot=amts[-1] if amts else None
    disc=[]
    for lab,rx in [('นักเรียนเก่า',r'นักเรียนเก่า'),('early bird',r'early\s*bird'),('ลด %',r'ลด\s*\d+\s*%'),('สมัคร 2 คอร์สขึ้นไป',r'สมัคร\s*[2-9]\s*คอร์ส|[2-9]\s*คอร์ส\s*ขึ้นไป|ลงคู่'),
                   ('ราคาพิเศษ/โปร',r'ราคาพิเศษ|โปรโมชั่น|โปร\s'),('ส่วนลดอื่น',r'ส่วนลด|ลดเหลือ|ลดพิเศษ')]:
        if re.search(rx,body,re.I): disc.append(lab)
    mode='online' if re.search(r'online|ออนไลน์',body,re.I) else ('onsite' if re.search(r'onsite|ออนไซต์|MBK|สยาม',body,re.I) else '')
    return dict(n_students=int(nstu.group(1)) if nstu else 1, items=items, total=tot, amounts=amts, disc=disc, mode=mode, n_hdr=n_hdr)

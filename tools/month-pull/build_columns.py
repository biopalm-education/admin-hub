# -*- coding: utf-8 -*-
import json, re, collections
from datetime import datetime, timezone, timedelta
TH=timezone(timedelta(hours=7)); PAGE="691470034208676"
MONTH="มี.ค."; Y,MO,MAXD=2026,3,31
SRC="/tmp/mar_threads.jsonl"
def dt(s): return datetime.strptime(s,"%Y-%m-%dT%H:%M:%S%z").astimezone(TH)
META=re.compile(r'^ตั้งระยะข้อมูลลูกค้าเป็น')
RECS=[]; bizcount=collections.Counter()
for line in open(SRC):
    line=line.strip()
    if not line: continue
    try: r=json.loads(line)
    except Exception: continue
    if not r.get("msgs"): continue
    RECS.append(r)
    for m in r["msgs"]:
        if str(m.get("f"))==PAGE:
            tx=(m.get("m") or "").strip() or ("[รูป/ไฟล์แนบ]" if m.get("a") else "")
            if not META.match(tx): bizcount[tx]+=1
print("threads with Mar msgs",len(RECS),flush=True)
CANNED={t for t,c in bizcount.items() if c>=5 and len(t)>12}
del bizcount
print("canned",len(CANNED),flush=True)
def mtype(m):
    if m["side"]=='ลูกค้า': return 'ลูกค้า'
    if META.match(m["tx"]): return 'ระบบ Meta'
    if m["tx"]=="" or m["tx"] in CANNED: return 'สำเร็จรูป'
    return 'แอดมินพิมพ์เอง'
PRICE=re.compile(r'บาท|ค่าเรียน'); CLOSE=re.compile(r'ขออนุญาตสรุปรายละเอียด|ธนาคารกสิกรไทย')
GIVE=re.compile(r'Giveaway|แจกฟรี|ขอชีท|ชีทเซลล')
INTEREST=re.compile(r'สนใจ|คอร์ส|เรียน|ราคา|ตาราง|รายละเอียด|ม\.[1-6]|ม\.ต้น|ม\.ปลาย|สอวน|สสวท')
GRADE=re.compile(r'ระดับชั้นใด|ชั้นเรียนใด|เรียนอยู่ชั้น|อยู่ระดับชั้น|เรียนอยู่ระดับ|ปัจจุบันเรียนอยู่')
PAYRE=re.compile(r'ส่งการชำระเงินจำนวน|สลิป|โอนแล้ว|โอนเงิน|ชำระ|จ่ายแล้ว|หลักฐาน')
LBL={'S0':'S0 ไม่มีข้อความลูกค้า','S1':'S1 ทักแต่ไม่ถามคอร์ส','S2':'S2 สนใจคอร์ส','S3':'S3 ได้รับราคาแล้ว',
     'S4':'S4 ขอสมัคร/ถามวิธีจ่าย','S5':'S5 ปิดการขาย','G':'G มารับของแถม'}
def fmt(x):
    if x is None: return '—'
    x=int(x)
    if x<60: return "%d วิ"%x
    if x<3600: return "%d นาที"%round(x/60)
    if x<86400: return "%.1f ชม."%(x/3600)
    return "%d วัน"%round(x/86400)
sumrows=[]; extra={}; MF=open("/tmp/mar_msgs.jsonl","w")
for r in RECS:
    tid=r["id"]; name=r.get("nm") or ""
    out=[]
    for m in sorted(r["msgs"], key=lambda x:x["t"]):
        tx=(m.get("m") or "").strip() or ("[รูป/ไฟล์แนบ]" if m.get("a") else "")
        side='ธุรกิจ' if str(m.get("f"))==PAGE else 'ลูกค้า'
        out.append({"t":dt(m["t"]),"side":side,"tx":tx,"to":[x for x in (m.get("to") or []) if x],"fn":m.get("fn") or ""})
    if not name:
        for m in out:
            if m["side"]=='ธุรกิจ':
                for n2 in m["to"]:
                    if n2 and n2!="BioPalm": name=n2; break
            elif m["fn"]: name=m["fn"]
            if name: break
    types=[mtype(m) for m in out]
    conv=[(m,t) for m,t in zip(out,types) if t!='ระบบ Meta']
    biz=[m["tx"] for m,t in zip(out,types) if m["side"]=='ธุรกิจ' and t!='ระบบ Meta']
    cus=[m["tx"] for m in out if m["side"]=='ลูกค้า']
    metat=[m["tx"] for m,t in zip(out,types) if t=='ระบบ Meta']
    if any('สร้างคอนเวอร์ชั่น' in t for t in metat) or any(CLOSE.search(t) for t in biz): stg='S5'
    elif not cus: stg='S0'
    elif any('ค่าเรียน' in t for t in biz): stg='S4'
    elif any('บาท' in t for t in biz): stg='S3'
    elif any(GIVE.search(t) for t in cus): stg='G'
    elif any(INTEREST.search(t) for t in cus): stg='S2'
    else: stg='S1'
    hasqual=any('มีคุณสมบัติ' in t for t in metat)
    tag='ปิดการขาย' if stg=='S5' else ('มีคุณสมบัติ' if hasqual else '')
    ad='Y' if any('BIOPALM ติวเตอร์วิชาชีวะ' in m["tx"] for m in out) else ''
    first=conv[0][0]["t"] if conv else (out[0]["t"] if out else None)
    sides=[m["side"] for m,t in conv]
    alt=sum(1 for i in range(1,len(sides)) if sides[i]!=sides[i-1])
    fc=next((m for m,t in conv if m["side"]=='ลูกค้า'),None)
    fh0=next((m for m,t in conv if t=='แอดมินพิมพ์เอง'),None)
    if fh0 is None: firstv='—'
    elif fc is None: firstv='0 วิ'
    else: firstv=fmt(max(0,(fh0["t"]-fc["t"]).total_seconds()))
    gaps=[(conv[i][0]["t"]-conv[i-1][0]["t"]).total_seconds() for i in range(1,len(conv))]
    maxw=fmt(max(gaps)) if gaps else '0 วิ'
    stuck='Y' if conv and conv[-1][0]["side"]=='ลูกค้า' else ''
    hum=[m["tx"] for m,t in zip(out,types) if t=='แอดมินพิมพ์เอง']
    tm=set()
    for t in hum:
        if 'ครับ' in t or 'คับ' in t: tm.add('A')
        if 'ค่ะ' in t or 'คะ' in t: tm.add('B')
    team=''.join(sorted(tm)) or '-'
    price='Y' if any(PRICE.search(t) for t in biz) else ''
    pay='Y' if any(PAYRE.search(t) for t in cus) else ''
    gq=sum(1 for t in biz if GRADE.search(t)); gq=gq if gq>=2 else ''
    ftv=None; fav=None
    if fc is not None:
        i0=[i for i,(m,t) in enumerate(conv) if m is fc][0]
        for m,t in conv[i0+1:]:
            if ftv is None and t=='แอดมินพิมพ์เอง': ftv=(m["t"]-fc["t"]).total_seconds()
            if fav is None and m["side"]=='ธุรกิจ': fav=(m["t"]-fc["t"]).total_seconds()
    txtall=" ".join(m["tx"] for m in out)
    if 'BIOPALM ติวเตอร์วิชาชีวะ' in txtall or 'ตอบกลับโฆษณา' in txtall: adsrc='ad'
    elif 'ตอบกลับความคิดเห็น' in txtall or 'responding to a user comment' in txtall: adsrc='comment'
    else: adsrc='organic'
    sumrows.append([MONTH,tid,name,LBL[stg],ad,tag,("%02d"%first.day) if first else '',(str(first.hour) if first else ''),
        len(conv),sum(1 for m,t in conv if m["side"]=='ลูกค้า'),
        sum(1 for m,t in conv if t=='แอดมินพิมพ์เอง'),sum(1 for m,t in conv if t=='สำเร็จรูป'),
        alt,firstv,maxw,stuck,team,price,pay,gq])
    extra[tid]={"ft":ftv,"fa":fav,"qual":hasqual,"stage":stg,"new":(not r.get("pre")),
                "adsrc":adsrc,"firstside":(conv[0][0]["side"] if conv else 'ธุรกิจ')}
    for i,(m,t) in enumerate(zip(out,types),1):
        MF.write(json.dumps([MONTH,tid,name,stg,i,m["t"].strftime("%d/%m %H:%M:%S"),m["side"],t,m["tx"]],ensure_ascii=False)+"\n")
MF.close()
sumrows.sort(key=lambda r:(r[6],r[7].zfill(2),r[1]))
json.dump(sumrows,open("/tmp/mar_sum.json","w"),ensure_ascii=False)
json.dump(extra,open("/tmp/mar_extra.json","w"),ensure_ascii=False)
print("chats",len(sumrows))
print(collections.Counter(r[3][:2].strip() for r in sumrows))
mix=collections.Counter()
for r in sumrows:
    e=extra[r[1]]
    if e["new"]: mix[{'ad':'na','comment':'nc','organic':'no'}[e["adsrc"]]]+=1
    elif e["firstside"]=='ลูกค้า': mix['rb']+=1
    else: mix['fr' if int(r[9] or 0)>0 else 'fs']+=1
json.dump(dict(mix),open("/tmp/mar_mix.json","w"),ensure_ascii=False)
print("mix",dict(mix))

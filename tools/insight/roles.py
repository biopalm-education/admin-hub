import sqlite3, re, collections, random, json
src=open('features.py').read().split("con=sqlite3.connect('chat.db')")[0]
ns={}; exec(src,ns); real=ns['real']
PC=re.compile(r'ลูก(?!ค้า|ศิษย์|เล่น|ๆ|ทีม|ค่ะ$)|ผู้ปกครอง(?!หนู|ผม)|หลาน|(?:ให้|ของ|พา|ส่ง|ถาม|ปรึกษา)น้อง|มี\s*[2-9]\s*คน|น้อง\s*(?:อยาก|พึ่ง|เพิ่ง|เรียน|อยู่|สอบ|จะ|ชื่อ|สนใจ|ต้องการ|เคย|ยัง|อายุ|ม\.|เขา|เค้า|ชอบ|ไม่|ได้|ก็|เป็น|มี|ต้อง|ขึ้น|กำลัง)|แม่(?:น้อง|เอง)|พ่อ(?:น้อง|เอง)')
PS=re.compile(r'หนู(?!ๆ|น้อย)|(?<!ลูก)(?<!ครับ)ผม(?:เรียน|อยู่|อยาก|สนใจ|จะ|เป็น|ต้องการ|ยัง|เคย|ไม่|ชอบ|มี)|ตัวเอง|เราเรียน|เราอยู่|เรียนเอง|เด็กซิ่ว|ซิ่ว|[Dd]ek\s?\d\d|ผมเป็นเด็ก|เป็นนักเรียน|(?:ผู้ปกครอง|แม่|พ่อ)(?:หนู|ผม)')
STRONG_S=re.compile(r'ไม่ใช่(?:คุณ)?(?:แม่|พ่อ|ผู้ปกครอง)|ผมเป็นเด็ก|หนูเป็นนักเรียน|ผมเป็นนักเรียน|เป็นคนเรียนเอง|(?:ผู้ปกครอง|แม่|พ่อ)(?:หนู|ผม)|หนูเรียนอยู่|ผมเรียนอยู่|คุณ(?:แม่|พ่อ)(?:จะ|โอน|ให้|บอก|สมัคร|ถาม|อนุญาต)')
STRONG_P=re.compile(r'ลูก(?:สาว|ชาย|ผม|ฉัน|เรา|ดิฉัน|คนโต|คนเล็ก)|เป็น(?:คุณ)?แม่|เป็นผู้ปกครอง|ให้ลูก')
PA=re.compile(r'คุณแม่|คุณพ่อ|ผู้ปกครอง')
con=sqlite3.connect('chat.db'); c=con.cursor()
freq=collections.Counter(x.strip()[:60] for (x,) in c.execute("SELECT txt FROM msg WHERE role2='H' AND (txt LIKE '%คุณแม่%' OR txt LIKE '%คุณพ่อ%' OR txt LIKE '%ผู้ปกครอง%')"))
TPL={k for k,v in freq.items() if v>=3}
print('templated admin parent-address texts',len(TPL))
res={}
def decide(f):
    if f['ss'] and not f['sp']: return 'student'
    if f['sp'] and not f['ss']: return 'parent'
    if f['ss'] and f['sp']: return 'unclear'
    if f['pc'] and not f['ps']: return 'parent'
    if f['ps'] and not f['pc']: return 'student' if not f['pa'] else 'unclear'
    if f['pc'] and f['ps']: return 'unclear'
    if f['pa']: return 'parent'
    return 'unknown'
cur=None; f=None
for ch,tid,r,x in c.execute("SELECT ch,tid,role2,txt FROM msg WHERE role2 IN ('C','H') ORDER BY ch,tid,t"):
    if (ch,tid)!=cur:
        if cur: res[cur]=decide(f)
        cur=(ch,tid); f={'pc':0,'ps':0,'pa':0,'sp':0,'ss':0}
    if r=='C' and real(x):
        if PC.search(x): f['pc']=1
        if PS.search(x): f['ps']=1
        if STRONG_P.search(x): f['sp']=1
        if STRONG_S.search(x): f['ss']=1
    elif r=='H' and x.strip()[:60] not in TPL:
        if PA.search(x): f['pa']=1
res[cur]=decide(f)
json.dump({'%s|%s'%k:v for k,v in res.items()},open('roles.json','w'),ensure_ascii=False)
cnt=collections.Counter((k[0],v) for k,v in res.items())
for ch in ('FB','IG','LINE'):
    tot=sum(v for (a,b),v in cnt.items() if a==ch)
    print(ch,{b:'%d (%.1f%%)'%(v,100*v/tot) for (a,b),v in cnt.items() if a==ch})

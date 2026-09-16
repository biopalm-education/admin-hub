import requests, json, os, time, threading
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
TOK=open("/mnt/files/bp/fbtok.txt").read().strip(); V="v21.0"
BASE=f"https://graph.facebook.com/{V}"
A0=datetime(2026,2,28,17,0,tzinfo=timezone.utc); A1=datetime(2026,3,31,17,0,tzinfo=timezone.utc)
OUT="/tmp/mar_threads.jsonl"
def dt(s): return datetime.strptime(s,"%Y-%m-%dT%H:%M:%S%z")
meta={}
for l in open("/mnt/files/bp/mar/index.jsonl"):
    r=json.loads(l); meta[r["id"]]={"u":r["u"],"nm":r["nm"]}
cand=json.load(open("/mnt/files/bp/mar/cand.json"))
done=set()
if os.path.exists(OUT):
    for l in open(OUT):
        try: done.add(json.loads(l)["id"])
        except Exception: pass
todo=[c for c in cand if c not in done]
print("todo",len(todo),flush=True)
lock=threading.Lock(); f=open(OUT,"a"); n=[0]
FIELDS="created_time,from,to,message,tags,attachments{mime_type}"
def get(url,params=None):
    for i in range(5):
        try:
            r=requests.get(url,params=params,timeout=90)
            if r.status_code==200: return r.json()
            j=r.json() if 'json' in r.headers.get('content-type','') else {}
            if (j.get('error') or {}).get('code') in (4,17,32,613,1,2) or r.status_code>=500:
                time.sleep(10*(i+1)); continue
            return None
        except Exception: time.sleep(5*(i+1))
    return None
def work(cid):
    j=get(f"{BASE}/{cid}",{"fields":f"messages.limit(100){{{FIELDS}}}","access_token":TOK})
    if j is None: return
    m=j.get("messages") or {}; msgs=m.get("data",[])
    nx=(m.get("paging") or {}).get("next"); g=0
    while nx and g<40:
        if msgs and dt(msgs[-1]["created_time"])<A0: break
        j2=get(nx)
        if not j2: break
        msgs+=j2.get("data",[]); nx=(j2.get("paging") or {}).get("next"); g+=1
        if not j2.get("data"): break
    keep=[]
    for m2 in msgs:
        t=dt(m2["created_time"])
        if A0<=t<A1:
            keep.append({"t":m2["created_time"],"f":(m2.get("from") or {}).get("id"),
                         "fn":(m2.get("from") or {}).get("name"),
                         "to":[x.get("name") for x in ((m2.get("to") or {}).get("data") or [])],
                         "m":m2.get("message") or "",
                         "a":1 if ((m2.get("attachments") or {}).get("data")) else 0})
    mm=meta.get(cid,{})
    rec={"id":cid,"u":mm.get("u"),"nm":mm.get("nm"),"msgs":keep,
         "pre":bool(msgs and dt(msgs[-1]["created_time"])<A0)}
    with lock:
        f.write(json.dumps(rec,ensure_ascii=False)+"\n"); n[0]+=1
        if n[0]%500==0: f.flush(); print("done",n[0],flush=True)
with ThreadPoolExecutor(10) as ex: list(ex.map(work,todo))
f.close(); print("MARPULL FINISHED",flush=True)

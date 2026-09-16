import requests, json, os, time, threading
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
TOK=open("/mnt/files/bp/fbtok.txt").read().strip(); V="v21.0"
BASE=f"https://graph.facebook.com/{V}"
J0=datetime(2026,5,31,17,0,tzinfo=timezone.utc); J1=datetime(2026,6,30,17,0,tzinfo=timezone.utc)
OUT="/mnt/files/bp/june/threads"; os.makedirs(OUT,exist_ok=True)
def dt(s): return datetime.strptime(s,"%Y-%m-%dT%H:%M:%S%z")
meta={}
for l in open("/home/user/w/index.jsonl"):
    r=json.loads(l); meta[r["id"]]={"u":r["u"],"nm":r["nm"],"mc":r.get("mc")}
cand=json.load(open("/home/user/w/cand.json"))
have=set(os.listdir(OUT))
todo=[c for c in cand if (c+".json") not in have]
print("todo",len(todo),flush=True)
lock=threading.Lock(); done=[0]
FIELDS="created_time,from,to,message,tags,attachments{mime_type}"
def get(url, params=None):
    for i in range(6):
        try:
            r=requests.get(url,params=params,timeout=120)
            if r.status_code==200: return r.json()
            j=r.json() if 'json' in r.headers.get('content-type','') else {}
            if (j.get('error') or {}).get('code') in (4,17,32,613,1,2) or r.status_code>=500:
                time.sleep(12*(i+1)); continue
            return None
        except Exception: time.sleep(6*(i+1))
    return None
def work(cid):
    j=get(f"{BASE}/{cid}",{"fields":f"messages.limit(100){{{FIELDS}}}","access_token":TOK})
    if j is None: return
    m=j.get("messages") or {}; msgs=m.get("data",[])
    nx=(m.get("paging") or {}).get("next"); guard=0
    while nx and guard<40:
        if msgs and dt(msgs[-1]["created_time"])<J0: break
        j2=get(nx)
        if not j2: break
        msgs+=j2.get("data",[]); nx=(j2.get("paging") or {}).get("next"); guard+=1
    keep=[]
    for m2 in msgs:
        t=dt(m2["created_time"])
        if J0<=t<J1:
            keep.append({"t":m2["created_time"],"f":(m2.get("from") or {}).get("id"),
                         "fn":(m2.get("from") or {}).get("name"),
                         "to":[x.get("name") for x in ((m2.get("to") or {}).get("data") or [])],
                         "m":m2.get("message") or "",
                         "a":1 if ((m2.get("attachments") or {}).get("data")) else 0})
    mm=meta.get(cid,{})
    json.dump({"id":cid,"u":mm.get("u"),"nm":mm.get("nm"),"msgs":keep},
              open(f"{OUT}/{cid}.json","w"), ensure_ascii=False)
    with lock:
        done[0]+=1
        if done[0]%250==0: print("done",done[0],flush=True)
with ThreadPoolExecutor(8) as ex: list(ex.map(work,todo))
print("PASS2 FINISHED",flush=True)

import json, glob, gc
from datetime import datetime, timezone
J0=datetime(2026,5,31,17,0,tzinfo=timezone.utc); J1=datetime(2026,6,30,17,0,tzinfo=timezone.utc)
def dt(s): return datetime.strptime(s,"%Y-%m-%dT%H:%M:%S%z")
out=open("/home/user/w/index.jsonl","w")
cand=[]
n=0
for p in sorted(glob.glob("/mnt/files/bp/june/raw/p*.json")):
    data=json.load(open(p))
    for c in data:
        ms=(c.get("messages") or {}).get("data") or []
        ts=[dt(m["created_time"]) for m in ms]
        nm=""
        for q in ((c.get("participants") or {}).get("data") or []):
            if str(q.get("id"))!="691470034208676": nm=q.get("name") or ""
        jun=sum(1 for t in ts if J0<=t<J1)
        rec={"id":c["id"],"u":c.get("updated_time"),"mc":c.get("message_count"),"nm":nm,
             "lo":ts and min(ts).isoformat() or None,"k":len(ms),"jun":jun}
        out.write(json.dumps(rec,ensure_ascii=False)+"\n")
        if jun>0 or not ts or min(ts)>=J0: cand.append(c["id"])
        n+=1
    del data; gc.collect()
out.close()
json.dump(cand, open("/home/user/w/cand.json","w"))
print("convs",n,"cand",len(cand),flush=True)

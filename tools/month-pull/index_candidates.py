import json, glob, gc
from datetime import datetime, timezone
A0=datetime(2026,2,28,17,0,tzinfo=timezone.utc); A1=datetime(2026,3,31,17,0,tzinfo=timezone.utc)
def dt(s): return datetime.strptime(s,"%Y-%m-%dT%H:%M:%S%z")
out=open("/mnt/files/bp/mar/index.jsonl","w"); cand=[]; n=0; seen=set()
for p in sorted(glob.glob("/mnt/files/bp/mar/raw/p*.json")):
    for c in json.load(open(p)):
        if c["id"] in seen: continue
        seen.add(c["id"])
        ms=(c.get("messages") or {}).get("data") or []
        ts=[dt(m["created_time"]) for m in ms]
        nm=""
        for q in ((c.get("participants") or {}).get("data") or []):
            if str(q.get("id"))!="691470034208676": nm=q.get("name") or ""
        hit=sum(1 for t in ts if A0<=t<A1)
        k=len(ms); mc=c.get("message_count")
        more=(k>=40) or (mc and mc>k)
        out.write(json.dumps({"id":c["id"],"u":c.get("updated_time"),"mc":mc,"nm":nm},ensure_ascii=False)+"\n"); n+=1
        if hit>0: cand.append(c["id"])
        elif (not ts or min(ts)>=A0) and more: cand.append(c["id"])
    gc.collect()
lean=0
for p in sorted(glob.glob("/mnt/files/bp/mar/raw2/q*.json")):
    for c in json.load(open(p)):
        if c["id"] in seen: continue
        seen.add(c["id"]); n+=1; lean+=1
        out.write(json.dumps({"id":c["id"],"u":c.get("updated_time"),"mc":c.get("message_count"),"nm":""},ensure_ascii=False)+"\n")
        if dt(c["updated_time"])>=A0: cand.append(c["id"])
    gc.collect()
out.close()
json.dump(cand, open("/mnt/files/bp/mar/cand.json","w"))
print("convs",n,"lean",lean,"cand",len(cand),flush=True)

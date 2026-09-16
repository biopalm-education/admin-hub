import requests, json, os, time
from datetime import datetime, timezone
TOK = open("/mnt/files/bp/fbtok.txt").read().strip()
PAGE="691470034208676"; V="v21.0"
BASE=f"https://graph.facebook.com/{V}"
OUT="/mnt/files/bp/mar/raw2"
START=datetime(2026,2,28,17,0,0,tzinfo=timezone.utc)
FIELDS="id,updated_time,message_count"
def get(url, params=None, tries=6):
    for i in range(tries):
        try:
            r=requests.get(url, params=params, timeout=60)
            if r.status_code==200: return r.json()
            j=r.json() if r.headers.get('content-type','').startswith('application/json') else {}
            if (j.get('error') or {}).get('code') in (4,17,32,613,1,2) or r.status_code>=500:
                time.sleep(10*(i+1)); continue
            print("HTTP",r.status_code,r.text[:200],flush=True); return None
        except Exception as ex:
            print("EX",str(ex)[:120],flush=True); time.sleep(5*(i+1))
    return None
state_f="/mnt/files/bp/mar/state2.json"
if os.path.exists(state_f): st=json.load(open(state_f))
else:
    h=json.load(open("/mnt/files/bp/mar/state_heavy.json"))
    st={"page":0,"after":h["after"],"done":False,"n":0}
url=f"{BASE}/{PAGE}/conversations"
while not st["done"]:
    params={"fields":FIELDS,"limit":100,"access_token":TOK,"after":st["after"]}
    j=get(url, params)
    if j is None:
        print("ABORT at page",st["page"],flush=True); break
    data=j.get("data",[])
    if not data:
        st["done"]=True; break
    json.dump(data, open(f"{OUT}/q{st['page']:05d}.json","w"), ensure_ascii=False)
    st["n"]+=len(data); st["page"]+=1
    last=data[-1]["updated_time"]
    lastdt=datetime.strptime(last,"%Y-%m-%dT%H:%M:%S%z")
    st["after"]=(j.get("paging") or {}).get("cursors",{}).get("after")
    json.dump(st, open(state_f,"w"))
    print(st["page"], st["n"], last, flush=True)
    if lastdt < START or not st["after"]:
        st["done"]=True; break
json.dump(st, open(state_f,"w"))
print("STATE", st["page"], st["n"], st["done"], flush=True)

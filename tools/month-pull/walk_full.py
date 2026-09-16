import requests, json, os, time
from datetime import datetime, timezone
TOK = open("/mnt/files/bp/fbtok.txt").read().strip()
PAGE="691470034208676"; V="v21.0"
BASE=f"https://graph.facebook.com/{V}"
OUT="/mnt/files/bp/mar/raw"
START=datetime(2026,2,28,17,0,0,tzinfo=timezone.utc)   # 1 Mar 2026 00:00 +07
FIELDS="id,updated_time,message_count,participants,messages.limit(40){created_time,from,to,message,tags,attachments{mime_type}}"
def get(url, params=None, tries=6):
    for i in range(tries):
        try:
            r=requests.get(url, params=params, timeout=120)
            if r.status_code==200: return r.json()
            j=r.json() if r.headers.get('content-type','').startswith('application/json') else {}
            code=(j.get('error') or {}).get('code')
            if code in (4,17,32,613,1,2) or r.status_code>=500:
                time.sleep(15*(i+1)); continue
            print("HTTP",r.status_code,r.text[:300],flush=True); return None
        except Exception as ex:
            print("EX",ex,flush=True); time.sleep(8*(i+1))
    return None
state_f="/mnt/files/bp/mar/state.json"
st=json.load(open(state_f)) if os.path.exists(state_f) else {"page":0,"after":None,"done":False,"n":0}
url=f"{BASE}/{PAGE}/conversations"
while not st["done"]:
    params={"fields":FIELDS,"limit":50,"access_token":TOK}
    if st["after"]: params["after"]=st["after"]
    j=get(url, params)
    if j is None:
        print("ABORT at page",st["page"],flush=True); break
    data=j.get("data",[])
    if not data:
        st["done"]=True; break
    json.dump(data, open(f"{OUT}/p{st['page']:05d}.json","w"), ensure_ascii=False)
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

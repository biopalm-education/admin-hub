import os, json
from concurrent.futures import ThreadPoolExecutor
SRC="/mnt/files/bp/june/threads"
files=[os.path.join(SRC,f) for f in os.listdir(SRC)]
def rd(p):
    try: return open(p,'rb').read()
    except Exception: return None
out=open("/home/user/w/threads.jsonl","wb"); n=0
with ThreadPoolExecutor(32) as ex:
    for b in ex.map(rd, files):
        if b: out.write(b.strip()+b"\n"); n+=1
out.close(); print("collected",n,flush=True)

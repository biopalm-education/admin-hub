
import json, os, math
from concurrent.futures import ThreadPoolExecutor
SID = open('/mnt/files/bp/mar/sid.txt').read().strip()
CKPT = '/mnt/files/bp/mar/push_ckpt.json'
def colletter(n):
    s=""
    while n:
        n,r=divmod(n-1,26); s=chr(65+r)+s
    return s
def clean(row,width):
    out=[]
    for v in row[:width]:
        if v is None: out.append("")
        elif isinstance(v,bool): out.append(v)
        elif isinstance(v,(int,float)): out.append(v)
        else: out.append(str(v)[:45000])
    out += [""]*(width-len(out))
    return out
def load_ckpt():
    return json.load(open(CKPT)) if os.path.exists(CKPT) else {}
def push(tab, rows, width, batch=1000, workers=4):
    rows=[clean(r,width) for r in rows]
    ck=load_ckpt(); done=set(ck.get(tab,[]))
    nb=math.ceil(len(rows)/batch)
    jobs=[i for i in range(nb) if i not in done]
    last=colletter(width)
    def run(i):
        chunk=rows[i*batch:(i+1)*batch]; r0=2+i*batch
        rng="'%s'!A%d:%s%d"%(tab,r0,last,r0+len(chunk)-1)
        res,err=run_composio_tool(tool_slug='GOOGLESHEETS_VALUES_UPDATE', arguments={
            'spreadsheet_id':SID,'range':rng,'value_input_option':'RAW','values':chunk,'auto_expand_sheet':True})
        return i,(not err),(str(err)[:150] if err else "")
    ok,bad=[],[]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i,good,msg in ex.map(run,jobs):
            (ok if good else bad).append((i,msg))
    ck=load_ckpt(); ck[tab]=sorted(set(ck.get(tab,[]))|{i for i,_ in ok}); json.dump(ck,open(CKPT,'w'))
    return {"tab":tab,"batches":nb,"done_now":len(ok),"failed":bad[:3],"remaining":nb-len(ck[tab])}

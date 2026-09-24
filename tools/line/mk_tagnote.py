# -*- coding: utf-8 -*-
"""agg['tagnote'] from the yearly LINE sheet: rooms per month split by tag x note.
tag = any tag (status != ไม่ติดแท็ก); note = >=1 note created on/before month end (cumulative).
Usage: python3 mk_tagnote.py sheet.json src/agg.json"""
import json,sys,collections
MS=['ม.ค.','ก.พ.','มี.ค.','เม.ย.','พ.ค.','มิ.ย.','ก.ค.','ส.ค.','ก.ย.','ต.ค.','พ.ย.','ธ.ค.']
def main(sp,ap):
    D=json.load(open(sp)); S=D['S']; N=D['N']
    MK={m:'%02d'%(i+1) for i,m in enumerate(MS)}
    notes=collections.defaultdict(list)
    for m,rows in N.items():
        for r in rows[1:]:
            r=r+['']*(10-len(r)); notes[r[1]].append(r[3])
    rooms=collections.defaultdict(dict)
    for r in S[1:]:
        r=r+['']*(7-len(r)); p=r[0].split()
        if len(p)<2 or p[0] not in MK: continue
        rooms[p[1]+'-'+MK[p[0]]][r[2]]=r
    out={}
    for k in sorted(rooms):
        end=k+'-31'; c=collections.Counter(); tx=collections.Counter(); L={'xx':[],'xN':[]}
        for cid,r in rooms[k].items():
            t=r[4]!='ไม่ติดแท็ก'; n=any(d and d<=end for d in notes.get(cid,[]))
            g=('T' if t else 'x')+('N' if n else 'x'); c[g]+=1
            if g=='Tx': tx[r[4]]+=1
            if g in L: L[g].append([r[1],cid,r[6]])
        out[k]=dict(rooms=len(rooms[k]),TN=c['TN'],Tx=c['Tx'],xx=c['xx'],xN=c['xN'],txs=dict(tx),
                    notes=sum(1 for v in notes.values() for d in v if d[:7]==k),lists=L)
        assert c['TN']+c['Tx']+c['xx']+c['xN']==len(rooms[k])
    A=json.load(open(ap)); A['tagnote']=dict(months=out,src='Biopalm LINE Chat Log — 2026')
    json.dump(A,open(ap,'w'),ensure_ascii=False,separators=(',',':'))
    for k,v in out.items(): print(k,v['rooms'],v['TN'],v['Tx'],v['xx'],v['xN'],v['notes'])
if __name__=='__main__': main(sys.argv[1],sys.argv[2])

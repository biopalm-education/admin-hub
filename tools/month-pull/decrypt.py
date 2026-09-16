import os,sys,json,gzip,base64,hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
REPO=sys.argv[1]
USER,PWD=open('secret.txt',encoding='utf-8').read().strip().split(':',1)
man=json.load(open(REPO+'/manifest.json'))
salt=base64.b64decode(man['kdf']['s']); it=man['kdf']['n']
key=hashlib.pbkdf2_hmac('sha256',(USER+':'+PWD).encode(),salt,it,32); g=AESGCM(key)
def op(b):
    d=g.decrypt(base64.b64decode(b['i']),base64.b64decode(b['c']),None)
    if b.get('z')=='gzip': d=gzip.decompress(d)
    return json.loads(d.decode('utf-8'))
print('probe',op(man['check']))
os.makedirs('src',exist_ok=True)
name={'agg':'src/agg.json','ig-all':'src/ig_all.json'}
for n,p in man['files'].items():
    o=op(json.load(open(REPO+'/'+p.lstrip('./'))))
    out=name.get(n,'src/'+n.replace('fb-','fb_')+'.json')
    json.dump(o,open(out,'w'),separators=(',',':'),ensure_ascii=False)
    print(out,os.path.getsize(out))

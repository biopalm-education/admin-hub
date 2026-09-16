# -*- coding: utf-8 -*-
"""Build the publishable site: encrypt every data file under one derived key.

  src/agg.json          -> pages/data/agg.json        (always loaded, ~small)
  src/ig_all.json       -> pages/data/ig-all.json     (loaded when you open Instagram)
  src/fb_<month>.json   -> pages/data/fb-<month>.json (loaded when you open that FB month)
  app.html              -> <out>/index.html          (code only, no data)
  <out>/manifest.json   -> salt + iterations + password probe + file list

Adding a month = drop a new src/fb_YYYY-MM.json in, refresh src/agg.json, run this.
The app shell never has to change.
"""
import os, re, sys, json, gzip, base64, hashlib, glob, datetime
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

OUT = sys.argv[1] if len(sys.argv) > 1 else 'pages'
ITER = 250000
USER, PWD = open('secret.txt', encoding='utf-8').read().strip().split(':', 1)

os.makedirs(OUT + '/data', exist_ok=True)
salt = os.urandom(16)
key = hashlib.pbkdf2_hmac('sha256', (USER + ':' + PWD).encode(), salt, ITER, 32)
gcm = AESGCM(key)

def seal(obj, compress=True):
    raw = json.dumps(obj, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    body = gzip.compress(raw, 9) if compress else raw
    iv = os.urandom(12)
    return {'i': base64.b64encode(iv).decode(), 'z': 'gzip' if compress else 'none',
            'c': base64.b64encode(gcm.encrypt(iv, body, None)).decode()}, len(raw)

files, report = {}, []
def emit(name, src):
    blob, raw = seal(json.load(open(src, encoding='utf-8')))
    out = OUT + '/data/%s.json' % name
    json.dump(blob, open(out, 'w'), separators=(',', ':'))
    files[name] = './data/%s.json' % name
    report.append((name, raw, os.path.getsize(out)))

emit('agg', 'src/agg.json')
emit('ig-all', 'src/ig_all.json')
for p in sorted(glob.glob('src/fb_*.json')):
    emit('fb-' + re.search(r'fb_(.+)\.json$', p).group(1), p)
for p in sorted(glob.glob('src/line_*.json')):
    emit('line-' + re.search(r'line_(.+)\.json$', p).group(1), p)

check, _ = seal({'ok': 1}, compress=False)
manifest = {'v': 1, 'kdf': {'s': base64.b64encode(salt).decode(), 'n': ITER},
            'check': check, 'files': files,
            'built': datetime.datetime.now().astimezone().isoformat(timespec='minutes')}
json.dump(manifest, open(OUT + '/manifest.json', 'w'), separators=(',', ':'))

open(OUT + '/index.html', 'w', encoding='utf-8').write(open('app.html', encoding='utf-8').read())
open(OUT + '/.nojekyll', 'w').write('')

print('%-16s %12s %12s' % ('file', 'raw', 'published'))
for n, raw, enc in report:
    print('%-16s %12s %12s' % (n, format(raw, ','), format(enc, ',')))
print('%-16s %12s %12s' % ('index.html', '', format(os.path.getsize(OUT + '/index.html'), ',')))
print('%-16s %12s %12s' % ('manifest.json', '', format(os.path.getsize(OUT + '/manifest.json'), ',')))

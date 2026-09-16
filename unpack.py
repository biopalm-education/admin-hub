# -*- coding: utf-8 -*-
"""Decrypt the published data/*.json back into src/ so build.py can rebuild.

Run from the folder that holds manifest.json, data/ and secret.txt.
"""
import os, json, gzip, base64, hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

USER, PWD = open('secret.txt', encoding='utf-8').read().strip().split(':', 1)
man = json.load(open('manifest.json', encoding='utf-8'))
salt = base64.b64decode(man['kdf']['s'])
key = hashlib.pbkdf2_hmac('sha256', (USER + ':' + PWD).encode(), salt, man['kdf']['n'], 32)
gcm = AESGCM(key)

def unseal(blob):
    raw = gcm.decrypt(base64.b64decode(blob['i']), base64.b64decode(blob['c']), None)
    if blob.get('z') == 'gzip':
        raw = gzip.decompress(raw)
    return json.loads(raw.decode('utf-8'))

# fail fast on a wrong password
unseal(man['check'])
os.makedirs('src', exist_ok=True)

NAME = {'agg': 'src/agg.json', 'ig-all': 'src/ig_all.json'}
for name, path in man['files'].items():
    blob = json.load(open(path.lstrip('./'), encoding='utf-8'))
    obj = unseal(blob)
    out = NAME.get(name) or 'src/' + name.replace('-', '_', 1) + '.json'
    json.dump(obj, open(out, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    print('%-22s -> %s  (%s bytes)' % (name, out, format(os.path.getsize(out), ',')))
print('OK — src/ rebuilt')

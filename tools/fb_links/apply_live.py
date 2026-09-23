# -*- coding: utf-8 -*-
"""Put the FB deep links on the LIVE page without a full build.py rebuild.

build.py would re-seal every data file under a fresh salt; the only thing that
actually changed is agg['fbuid'], so this re-seals just data/agg.json under the
manifest's existing salt.  Smallest possible diff — nothing else on the live page moves.
Run after unpack.py + link_fb.py.
"""
import json, gzip, base64, hashlib, os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
USER, PWD = open(ROOT + '/secret.txt', encoding='utf-8').read().strip().split(':', 1)
man = json.load(open(ROOT + '/manifest.json', encoding='utf-8'))
salt = base64.b64decode(man['kdf']['s'])
gcm = AESGCM(hashlib.pbkdf2_hmac('sha256', (USER + ':' + PWD).encode(), salt, man['kdf']['n'], 32))

def unseal(b):
    raw = gcm.decrypt(base64.b64decode(b['i']), base64.b64decode(b['c']), None)
    return json.loads((gzip.decompress(raw) if b.get('z') == 'gzip' else raw).decode('utf-8'))

def seal(obj):
    raw = gzip.compress(json.dumps(obj, separators=(',', ':'), ensure_ascii=False).encode('utf-8'), 9)
    iv = os.urandom(12)
    return {'i': base64.b64encode(iv).decode(), 'z': 'gzip',
            'c': base64.b64encode(gcm.encrypt(iv, raw, None)).decode()}

path = ROOT + '/' + man['files']['agg'].lstrip('./')
live = unseal(json.load(open(path, encoding='utf-8')))
before = len(live.get('fbuid', {}))
merged = dict(live.get('fbuid', {}))
merged.update(json.load(open(ROOT + '/src/agg.json', encoding='utf-8')).get('fbuid', {}))
live['fbuid'] = merged
json.dump(seal(live), open(path, 'w'), separators=(',', ':'))
assert len(unseal(json.load(open(path, encoding='utf-8')))['fbuid']) == len(merged)   # read straight back
print('live fbuid: %d -> %d  (+%d)  · re-read OK' % (before, len(merged), len(merged) - before))

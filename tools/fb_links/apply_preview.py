# -*- coding: utf-8 -*-
"""Put the new FB deep links into admin-hub/preview/ WITHOUT rebuilding it.

preview/ holds a whole bundle of UI work that is still waiting for พี่ปาล์ม's "deploy",
and its index.html was built from an app.html that is not in the repo — so a full
build.py run against preview/ would wipe that work.  Instead this re-seals ONLY
preview/data/agg.json, under preview/manifest.json's own salt, with fbuid merged.
"""
import json, gzip, base64, hashlib, os, sys
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PREV = ROOT + '/preview'
USER, PWD = open(ROOT + '/secret.txt', encoding='utf-8').read().strip().split(':', 1)
man = json.load(open(PREV + '/manifest.json', encoding='utf-8'))
salt = base64.b64decode(man['kdf']['s'])
gcm = AESGCM(hashlib.pbkdf2_hmac('sha256', (USER + ':' + PWD).encode(), salt, man['kdf']['n'], 32))

def unseal(b):
    raw = gcm.decrypt(base64.b64decode(b['i']), base64.b64decode(b['c']), None)
    if b.get('z') == 'gzip':
        raw = gzip.decompress(raw)
    return json.loads(raw.decode('utf-8'))

def seal(obj):
    raw = gzip.compress(json.dumps(obj, separators=(',', ':'), ensure_ascii=False).encode('utf-8'), 9)
    iv = os.urandom(12)
    return {'i': base64.b64encode(iv).decode(), 'z': 'gzip',
            'c': base64.b64encode(gcm.encrypt(iv, raw, None)).decode()}

path = PREV + '/' + man['files']['agg'].lstrip('./')
agg = unseal(json.load(open(path, encoding='utf-8')))
before = len(agg.get('fbuid', {}))

live = json.load(open(ROOT + '/src/agg.json', encoding='utf-8'))
merged = dict(agg.get('fbuid', {}))
merged.update(live.get('fbuid', {}))          # add, never drop
agg['fbuid'] = merged
json.dump(seal(agg), open(path, 'w'), separators=(',', ':'))
print('preview fbuid: %d -> %d  (+%d)' % (before, len(merged), len(merged) - before))

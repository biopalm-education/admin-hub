# -*- coding: utf-8 -*-
"""ขึ้นรายการ "ติดแท็ก / ใส่โน้ต ให้ครบ" (agg['tnfu']) โดยไม่ต้อง build.py ทั้งชุด

build.py สุ่ม salt ใหม่และเข้ารหัสทุกไฟล์ใหม่หมด แต่รอบรีเฟรชแท็ก/โน้ตเปลี่ยนแค่ agg['tnfu']
ไฟล์นี้จึงเข้ารหัสเฉพาะ data/agg.json ใหม่ ด้วย salt เดิมใน manifest — ไฟล์อื่นบนหน้าเว็บไม่ขยับเลย
รันหลัง unpack.py + tn_update.py จาก root ของ repo (ต้องมี secret.txt)
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
new = json.load(open(ROOT + '/src/agg.json', encoding='utf-8'))['tnfu']
before = (live.get('tnfu') or {}).get('stamp')
keys0 = set(live)
live['tnfu'] = new
json.dump(seal(live), open(path, 'w'), separators=(',', ':'))
back = unseal(json.load(open(path, encoding='utf-8')))            # อ่านกลับทันที
assert back['tnfu']['stamp'] == new['stamp'] and len(back['tnfu']['rooms']) == len(new['rooms'])
assert set(back) == keys0 | {'tnfu'}
print('live tnfu: %s → %s · ห้องค้าง %d · อ่านกลับผ่าน' % (before, new['stamp'], len(new['rooms'])))

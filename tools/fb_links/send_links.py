# -*- coding: utf-8 -*-
"""Send harvested FB thread links into the Apps Script "ลิงก์แชท FB" sheet tab.
Reads rows from a local JSON file: [[threadFBID, title, ts_ms], ...]
Token + /exec URL are read from local files and never printed."""
import json, hashlib, sys, urllib.request

ROOT = __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))))
agg = json.load(open(ROOT + '/src/agg.json'))
URL = agg['ovurl']
TOK = hashlib.sha256(('bp-ov|' + open(ROOT + '/secret.txt').read().strip()).encode()).hexdigest()

def send(rows, by='Claude (23 ก.ย. รอบ 11:00)', chunk=400):
    sent = 0
    for i in range(0, len(rows), chunk):
        part = rows[i:i+chunk]
        body = json.dumps({'t': TOK, 'act': 'links', 'by': by, 'rows': part}).encode()
        req = urllib.request.Request(URL, data=body, headers={'Content-Type': 'text/plain'})
        r = urllib.request.urlopen(req, timeout=120).read().decode()[:200]
        sent += len(part)
        print('chunk %d-%d -> %s' % (i, i+len(part), r))
    return sent

def fetch():
    r = urllib.request.urlopen('%s?t=%s&act=links' % (URL, TOK), timeout=120).read().decode()
    return json.loads(r)

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'send':
        rows = json.load(open(sys.argv[2]))
        print('rows:', len(rows), '-> sent', send(rows))
    elif cmd == 'fetch':
        d = fetch()
        json.dump(d, open(ROOT + '/links_sheet.json', 'w'), ensure_ascii=False)
        print('links in sheet:', len(d.get('links', [])))

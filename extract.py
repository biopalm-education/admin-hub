# -*- coding: utf-8 -*-
"""One-off: pull the data blobs out of the old monolithic hub_publish.html into src/.

After the first run you never need this again — src/ is the source of truth and
new months are added as new src/fb_YYYY-MM.json files.
"""
import re, json, os, sys

path = sys.argv[1] if len(sys.argv) > 1 else 'hub_publish.html'
S = open(path, encoding='utf-8').read()
os.makedirs('src', exist_ok=True)

def grab(name, js=False):
    m = re.search(r'^const %s=(.*?);?\s*$' % name, S, re.M)
    assert m, 'not found: ' + name
    raw = m.group(1).rstrip().rstrip(';')
    return json.loads(raw.replace("'", '"') if js else raw)

DATA   = grab('DATA')
FBAGG  = grab('FBAGG')
FBDATA = grab('FBDATA')
agg = {'ig': {k: v['agg'] for k, v in DATA['months'].items()},
       'fb': {'2026-07': FBAGG},
       'igt': grab('IGT'),
       'mkeys': grab('MKEYS', True), 'fbkeys': grab('FBKEYS', True),
       'mlabel': grab('MLABEL', True), 'mshort': grab('MSHORT', True)}

def w(p, o):
    json.dump(o, open(p, 'w'), separators=(',', ':'), ensure_ascii=False)
    print('%-24s %s bytes' % (p, format(os.path.getsize(p), ',')))

w('src/agg.json', agg)
w('src/ig_all.json', DATA)
w('src/fb_2026-07.json', FBDATA)

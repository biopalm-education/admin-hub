# -*- coding: utf-8 -*-
"""Rename a LINE admin's display name in the decrypted data (src/) — no re-pull needed.  (26 พ.ย. 2026)

LINE gives every admin a fixed bizId; tools/line/convert.py (OWN) maps it to the name shown on the dashboard.
When a name changes (an emoji name gets its real name, or a provisional label gets confirmed), update OWN in
convert.py AND run this once, so months already in src/ follow the new name too.

  python3 tools/line/rename_admin.py src '🚲=NR' '🌙=Miew'

Touches only fields that hold an ADMIN name (never customer names or message text):
  src/line_*.json   rooms[*].tr[*][1] (sender) · rooms[*].ad[*] · rooms[*].ow
  src/agg.json      line.*.admins / adminScore · v4|v4w30.line.*.adm · adm.line.*.sby / sbypaid / fa keys
                    notes.months.* fields owner / by / adm · tnfu.rooms[*][2]
followup.json / ba.json are rebuilt from these by build_fu.py / build_week.py — run the usual chain afterwards:
  build_v4.py -> build_v5.py -> post_v5_speed.py -> build_fu.py -> build_adm.py -> build_stage.py -> build_week.py -> build.py
Prints counts only.
"""
import sys, os, json, glob, collections

SRC = sys.argv[1]
MAP = dict(a.split('=', 1) for a in sys.argv[2:])
if not MAP: sys.exit('usage: rename_admin.py src OLD=NEW [...]')
C = collections.Counter()
rn = lambda x, tag: (C.update([tag]) or MAP[x]) if isinstance(x, str) and x in MAP else x

def save(obj, p):
    tmp = p + '.rn-tmp'
    json.dump(obj, open(tmp, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    os.replace(tmp, p)

for p in sorted(glob.glob(os.path.join(SRC, 'line_*.json'))):
    f = json.load(open(p, encoding='utf-8')); n0 = sum(C.values())
    for r in f['rooms']:
        for m in r.get('tr', []):
            if len(m) > 1: m[1] = rn(m[1], 'line.tr')
        if isinstance(r.get('ad'), list): r['ad'] = [rn(x, 'line.ad') for x in r['ad']]
        if 'ow' in r: r['ow'] = rn(r['ow'], 'line.ow')
    if sum(C.values()) > n0: save(f, p)

p = os.path.join(SRC, 'agg.json'); A = json.load(open(p, encoding='utf-8'))
for o in (A.get('line') or {}).values():
    for k in ('admins', 'adminScore'):
        for x in o.get(k) or []: x[0] = rn(x[0], 'agg.line.' + k)
for top in ('v4', 'v4w30'):
    for o in ((A.get(top) or {}).get('line') or {}).values():
        for x in (o or {}).get('adm') or []: x[0] = rn(x[0], top + '.adm')
for o in ((A.get('adm') or {}).get('line') or {}).values():
    for k in ('sby', 'sbypaid', 'fa'):          # fa = {ชื่อ: [ตอบคนแรก, ภายใน 15 นาที]} (build_adm.py · 26 พ.ย. 2026)
        d = o.get(k)
        if isinstance(d, dict):
            new = {}
            for n, v in d.items():
                n2 = rn(n, 'adm.' + k)
                if isinstance(v, list):
                    old = new.get(n2) or [0] * len(v); new[n2] = [a + b for a, b in zip(old, v)]
                else:
                    new[n2] = new.get(n2, 0) + v
            o[k] = new

def walk_notes(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ('owner', 'by', 'adm') and isinstance(v, str): o[k] = rn(v, 'notes.' + k)
            else: walk_notes(v)
    elif isinstance(o, list):
        for v in o: walk_notes(v)
walk_notes((A.get('notes') or {}).get('months') or {})
for r in (A.get('tnfu') or {}).get('rooms') or []:
    if len(r) > 2: r[2] = rn(r[2], 'tnfu.owner')
save(A, p)
print('rename', MAP, dict(C))

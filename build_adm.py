# -*- coding: utf-8 -*-
"""Admin-team metrics (admin-hub, Sep 30 2026) -> src/agg.json["adm"][channel][month]

The admin view no longer looks at course interest / ads. It measures the team on every chat a
customer started, whatever it was about (course, existing student, other topics):

  n    chats where the customer sent at least one message (stage != X), Giveaway excluded
       (the bot hands out the freebie, nobody is expected to reply)
  ans  of those, chats where a human admin replied after the customer's first message
       (same first-reply rule as build_v4: FB/IG role 1 · LINE named admin; saved replies an admin
       clicks count, bots and auto replies never do; a reply landing next month within 7 days counts)
  W    closed sales in the month (verified slip, one count per เลขอ้างอิง — build_v4's stage W)
  sp   reply-speed tables in build_v4's exact shape (b · s · bins · hr), over the same n chats,
       so the page can reuse its speed tables unchanged

Answer quality on the page = W / ans.
Needs no network and never touches fb_pull / ig_pull output: it only reads src/ after build_v5.py
and post_v5_speed.py have stamped the stage (FB/IG c[37], LINE r['sg']) and first reply (c[40], r['fr']).

Pipeline: ... build_v5.py -> post_v5_speed.py -> build_fu.py -> build_adm.py -> build.py
"""
import os, json, glob
os.chdir(os.path.dirname(os.path.abspath(__file__)))
SRC = open('build_v4.py', encoding='utf-8').read()
ns = {'__name__': 'v4helpers'}
exec(SRC[:SRC.index("\nv4 = {'fb'")], ns)                                   # definitions only
exec(SRC[SRC.index('def sp_bucket'):SRC.index("agg = load('src/agg.json')", SRC.index('def sp_bucket'))], ns)
load, tx_of, sysmsg, sp_blank, sp_add = ns['load'], ns['tx_of'], ns['sysmsg'], ns['sp_blank'], ns['sp_add']

SKIP = ('X', 'G')          # X = customer never wrote · G = Giveaway


def blank():
    return {'n': 0, 'ans': 0, 'W': 0, 'sp': sp_blank()}


def add(o, st, fr, mod):
    if st == 'W':
        o['W'] += 1
    if st in SKIP or st is None:
        return
    o['n'] += 1
    if fr is not None and fr >= 0:
        o['ans'] += 1
    if mod is not None:
        sp_add(o['sp'], fr, mod, st == 'W')


def fb_like(rows, tx):
    o = blank()
    for c in rows:
        st = c[37] if len(c) > 37 else None
        fr = c[40] if len(c) > 40 else None
        c0 = next((m[0] for m in c[18] if m[1] == 0 and not sysmsg(tx(m[2]))), None)
        add(o, st, fr, None if c0 is None else c0 % 1440)
    return o


agg = load('src/agg.json')
out = {'fb': {}, 'ig': {}, 'line': {}}
for p in sorted(glob.glob('src/fb_*.json')):
    f = load(p)
    out['fb'][p[-12:-5]] = fb_like(f['chats'], tx_of(f['dict']))
    del f
ig = load('src/ig_all.json')
if ig:
    tx = tx_of(ig['dict'])
    for mo, d in sorted(ig['months'].items()):
        out['ig'][mo] = fb_like(d['leads'], tx)
    del ig
for p in sorted(glob.glob('src/line_*.json')):
    f = load(p); o = blank()
    for r in f['rooms']:
        t = next((m[0] for m in r['tr'] if m[1] == 'C'), None)
        mod = None
        if t:
            try:
                hh, mm = t.split(' ')[1].split(':'); mod = int(hh) * 60 + int(mm)
            except Exception:
                mod = None
        add(o, r.get('sg'), r.get('fr'), mod)
    out['line'][p[-12:-5]] = o
    del f

agg['adm'] = out
tmp = 'src/agg.json.adm-tmp'      # write aside then swap, so a failure never leaves agg.json half written
json.dump(agg, open(tmp, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
os.replace(tmp, 'src/agg.json')
for ch in out:
    for mo in sorted(out[ch])[-2:]:
        o = out[ch][mo]
        print('adm', ch, mo, 'n', o['n'], 'ans', o['ans'], 'W', o['W'], 'b', [x[0] for x in o['sp']['b']])

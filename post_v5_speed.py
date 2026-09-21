# -*- coding: utf-8 -*-
"""Recompute the reply-speed tables (sp) AFTER build_v5.py.

build_v5.py rewrites agg['v4'] (14-day) and agg['v4w30'] (30-day) from scratch, which
drops the 'sp' tables build_v4.py produced, and leaves the "ความเร็วตอบแชท" section empty.
This reuses build_v4's own sp helpers and fills sp for BOTH windows, each from its own
per-chat status field: 14 days -> FB/IG c[37], LINE r['sg'] · 30 days -> c[41], r['sg30'].

Pipeline:  unpack.py -> build_v4.py -> build_v5.py -> post_v5_speed.py -> build.py
"""
import os, re, json, glob
os.chdir(os.path.dirname(os.path.abspath(__file__)))
SRC = open('build_v4.py', encoding='utf-8').read()
ns = {'__name__': 'v4helpers'}
exec(SRC[:SRC.index("\nv4 = {'fb'")], ns)                                   # definitions only
exec(SRC[SRC.index('def sp_bucket'):SRC.index("agg = load('src/agg.json')", SRC.index('def sp_bucket'))], ns)
load, tx_of, sysmsg, sp_blank, sp_add = ns['load'], ns['tx_of'], ns['sysmsg'], ns['sp_blank'], ns['sp_add']
agg = load('src/agg.json')
WIN = {'v4': (37, 'sg'), 'v4w30': (41, 'sg30')}
FUN = ('V', 'T', 'Q', 'W')
for p in sorted(glob.glob('src/fb_*.json')):
    mo = p[-12:-5]; f = load(p); tx = tx_of(f['dict'])
    for key, (ci, _) in WIN.items():
        o = sp_blank()
        for c in f['chats']:
            st = c[ci] if len(c) > ci else None
            if st not in FUN: continue
            c0 = next((m[0] for m in c[18] if m[1] == 0 and not sysmsg(tx(m[2]))), None)
            if c0 is not None: sp_add(o, c[40], c0 % 1440, st == 'W')
        if mo in agg[key]['fb']: agg[key]['fb'][mo]['sp'] = o
ig = load('src/ig_all.json'); tx = tx_of(ig['dict'])
for mo, d in ig['months'].items():
    for key, (ci, _) in WIN.items():
        o = sp_blank()
        for c in d['leads']:
            st = c[ci] if len(c) > ci else None
            if st not in FUN: continue
            c0 = next((m[0] for m in c[18] if m[1] == 0 and not sysmsg(tx(m[2]))), None)
            if c0 is not None: sp_add(o, c[40], c0 % 1440, st == 'W')
        if mo in agg[key]['ig']: agg[key]['ig'][mo]['sp'] = o
for p in sorted(glob.glob('src/line_*.json')):
    mo = p[-12:-5]; f = load(p)
    for key, (_, fld) in WIN.items():
        o = sp_blank()
        for r in f['rooms']:
            st = r.get(fld)
            if st not in FUN: continue
            t = next((m[0] for m in r['tr'] if m[1] == 'C'), None)
            if t:
                hh, mm = t.split(' ')[1].split(':'); sp_add(o, r.get('fr'), int(hh) * 60 + int(mm), st == 'W')
        if mo in agg[key]['line']: agg[key]['line'][mo]['sp'] = o
json.dump(agg, open('src/agg.json', 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
for key in WIN:
    print(key, {ch: {mo: sum(x[0] for x in agg[key][ch][mo]['sp']['b']) for mo in sorted(agg[key][ch])[-2:]} for ch in ('fb', 'ig', 'line')})

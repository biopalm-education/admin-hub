# -*- coding: utf-8 -*-
"""app.html -> page with the weekly before / after Follow up section (9 ต.ค. 2026).

  python3 tools/followup_week/patch_app.py app.html preview/index.html     # preview (reads ../data like every preview)
  python3 tools/followup_week/patch_app.py app.html app.html               # when it is approved for the live page

Every replacement must match exactly once, otherwise nothing is written. Idempotent: an already patched file is left as is.
Data: build_week.py -> src/followup.json key "wk" (the daily run builds it; the page falls back to the old
"แชทค้างไปไหน" box when the key is missing).
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
src, dst = sys.argv[1], sys.argv[2]
h = open(src, encoding='utf-8').read()
if 'function wkTop(' in h:
    print('already patched'); open(dst, 'w', encoding='utf-8').write(h); sys.exit(0)
JS = open(os.path.join(HERE, 'wk.js'), encoding='utf-8').read()
CSS = open(os.path.join(HERE, 'wk.css'), encoding='utf-8').read()


def once(old, new):
    global h
    n = h.count(old)
    if n != 1: raise SystemExit('patch_app: expected 1 match, found %d for: %s' % (n, old[:80]))
    h = h.replace(old, new)


once('</style>', CSS + '\n</style>')
once('async function renderFU(){', JS + '\nasync function renderFU(){')
# overview above the list switcher (both pages) · the weekly box replaces the old "แชทค้างไปไหน" box when data exists
once("const cards=fuModeBar()+`<div class=\"fucards\">`+", "const cards=wkTop()+fuModeBar()+`<div class=\"fucards\">`+")
once("const cards=fuModeBar()+`<div class=\"fucards c3\">`+", "const cards=wkTop()+fuModeBar()+`<div class=\"fucards c3\">`+")
once('</div>${fuFlow()}${fuStatus()}', "</div>${wkOn()?wkBox('ar'):fuFlow()}${fuStatus()}")
once("el.innerHTML=cards+`<div class=\"fugrid\"><div>${wtable}</div><div>${want}</div></div>`+list+hist+help;",
     "el.innerHTML=cards+`<div class=\"fugrid\"><div>${wtable}</div><div>${want}</div></div>`+list+hist+help;wkBind(el);")
once("el.innerHTML=cards+flow+(NPM?statNP:stat)+note+", "el.innerHTML=cards+(wkOn()?wkBox(PU_KEY):flow)+(NPM?statNP:stat)+note+")
once("+list+(NPM?'':hist);", "+list+(NPM?'':hist);wkBind(el);")
# the morning run is no longer at 05:00 (GitHub Actions since 29 ก.ย.; on the page around 09:00–10:00)
once('(รายวัน 05:00 ดึงเดือนปัจจุบัน · จันทร์ 04:00 ดึงเดือนก่อนหน้าซ้ำ)',
     '(ทุกเช้า ขึ้นหน้าเว็บราว 09:00–10:00 น. ดึงเดือนปัจจุบัน · วันจันทร์และวันที่ 1 ดึงเดือนก่อนหน้าซ้ำด้วย)')
n = h.count('รอบ 05:00')
h = h.replace('รอยืนยันรอบ 05:00', 'รอยืนยันรอบอัปเดตเช้า').replace('รอบ 05:00', 'รอบอัปเดตเช้า')
left = h.count('05:00')
if left: raise SystemExit('patch_app: %d "05:00" left unreplaced' % left)
open(dst, 'w', encoding='utf-8').write(h)
print('patched -> %s (%d "รอบ 05:00" labels reworded)' % (dst, n))

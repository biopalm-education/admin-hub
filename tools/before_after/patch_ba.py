# -*- coding: utf-8 -*-
"""app.html -> + the "Tracking" page (เดิมชื่อ Before / After · ขึ้นหน้าจริง 21 ต.ค. 2026).

  python3 tools/before_after/patch_ba.py app.html app.html && cp app.html index.html     # the live page (done 21 ต.ค. 2026)
  Follow up page stays as it is. tools/followup_week/patch_app.py (weekly tables in Follow up) is optional and not live:
  it skips a page that already has wk.js, so run it before this script if you ever want those tables in a preview.

Every replacement must match the expected number of times, otherwise nothing is written. Idempotent: a patched file is left as is.
ba.js reuses labels from tools/followup_week/wk.js: when the page has no wk.js yet, its definitions are added (not used by Follow up).
Data: build_week.py -> src/ba.json (daily Follow up timeline since 1 ม.ค. + notice texts) -> build.py emits data/ba.json.
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
src, dst = sys.argv[1], sys.argv[2]
h = open(src, encoding='utf-8').read()
if 'function renderBA(' in h:
    print('already patched'); open(dst, 'w', encoding='utf-8').write(h); sys.exit(0)
JS = open(os.path.join(HERE, 'ba.js'), encoding='utf-8').read()
CSS = open(os.path.join(HERE, 'ba.css'), encoding='utf-8').read()
WK = os.path.join(os.path.dirname(HERE), 'followup_week')


def rep(old, new, n=1):
    global h
    c = h.count(old)
    if c != n: raise SystemExit('patch_ba: expected %d match(es), found %d for: %s' % (n, c, old[:80]))
    h = h.replace(old, new)


# ba.js reuses labels from tools/followup_week/wk.js (+ wk.css). Without patch_app.py (the live page, 21 ต.ค. 2026) only
# the definitions go in: the Follow up page itself stays exactly as it is.
if 'function wkTop(' not in h:
    rep('</style>', open(os.path.join(WK, 'wk.css'), encoding='utf-8').read() + '\n</style>')
    rep('async function renderFU(){', open(os.path.join(WK, 'wk.js'), encoding='utf-8').read() + '\nasync function renderFU(){')
# the old weekly LINE report box (only shown when patch_app.py put the weekly tables in) — the Monday / Friday texts live on Tracking
rep("const rep=FU.wk.report&&FU.wk.report.msgs?FU.wk.report.msgs.join('\\n\\n'):'';", "const rep='';")
rep('</style>', CSS + '\n</style>')
rep('async function renderFU(){', JS + '\nasync function renderFU(){')
# the page button (works on ทุกช่องทาง and on each channel) + its section; the button opens the category popup every time
rep('<button data-v="raw" aria-pressed="false">ข้อมูลดิบ</button>',
    '<button data-v="ba" aria-pressed="false">Tracking</button>\n   <button data-v="raw" aria-pressed="false">ข้อมูลดิบ</button>')
rep("if(b.dataset.v==='fu')FU_ASK=true;", "if(b.dataset.v==='fu')FU_ASK=true;if(b.dataset.v==='ba')BA_ASK=true;")
rep('<section id="s-fu" hidden>',
    '<section id="s-ba" class="ovs baov" hidden><div class="shead"><h2>Tracking · ความคืบหน้าการเคลียร์แชท</h2>'
    '<span class="lab" id="bascope"></span></div><div id="ba"></div></section>\n <section id="s-fu" hidden>')
rep("const fu=VIEW==='fu'; $('#s-fu').hidden=!fu; const mc=$('#mctl'); if(mc)mc.hidden=fu;",
    "const fu=VIEW==='fu', ba=VIEW==='ba'; $('#s-fu').hidden=!fu; {const sb=$('#s-ba');if(sb)sb.hidden=!ba;} const mc=$('#mctl'); if(mc)mc.hidden=fu||ba;\n"
    " if(!ba){const bp=document.getElementById('bbpk');if(bp)bp.remove();}\n"
    " if(ba){['s-v4k','s-v4m','s-v4f','s-v4n','s-v4s','s-v4q','s-v4a','s-raw'].forEach(id=>{const e=document.getElementById(id);if(e)e.hidden=true;});"
    "{const n=document.getElementById('ovnav');if(n)n.hidden=true;}renderBA();return;}")
# a link ending in #ba (the LINE notice) opens this page straight away
rep("refresh();\n}\n\n/* ---- lead tier",
    "if(/^#ba\\b/.test(location.hash)){VIEW='ba';$('#vseg').querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',String(x.dataset.v===VIEW)));}\n"
    "refresh();\n}\n\n/* ---- lead tier")
open(dst, 'w', encoding='utf-8').write(h)
print('patched -> %s (Tracking page)' % dst)

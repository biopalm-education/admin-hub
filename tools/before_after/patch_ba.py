# -*- coding: utf-8 -*-
"""page with the Follow up weekly box (tools/followup_week) -> + the "Before / After" page (v2, 21 ต.ค. 2026).

  python3 tools/followup_week/patch_app.py app.html /tmp/p1.html && python3 tools/before_after/patch_ba.py /tmp/p1.html preview/index.html
  Re-run both whenever app.html, tools/followup_week or tools/before_after change, so the preview keeps up.
  When approved for the live page: run both patches with app.html as input and output.

Every replacement must match the expected number of times, otherwise nothing is written. Idempotent: a patched file is left as is.
Needs wk.js (followup_week) in the page: ba.js reuses its labels, and falls back to its weekly box until ba.json exists.
Data: build_week.py -> src/ba.json (daily Follow up timeline since 1 ม.ค.) -> build.py emits data/ba.json.
Follow up page: the 5-row weekly table and the weekly box give way to one progress card for the category on screen.
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
src, dst = sys.argv[1], sys.argv[2]
h = open(src, encoding='utf-8').read()
if 'function renderBA(' in h:
    print('already patched'); open(dst, 'w', encoding='utf-8').write(h); sys.exit(0)
if 'function wkTop(' not in h:
    raise SystemExit('patch_ba: run tools/followup_week/patch_app.py first (ba.js needs wk.js)')
JS = open(os.path.join(HERE, 'ba.js'), encoding='utf-8').read()
CSS = open(os.path.join(HERE, 'ba.css'), encoding='utf-8').read()


def rep(old, new, n=1):
    global h
    c = h.count(old)
    if c != n: raise SystemExit('patch_ba: expected %d match(es), found %d for: %s' % (n, c, old[:80]))
    h = h.replace(old, new)


# Follow up page (before ba.js goes in, so its own text cannot match): progress card instead of the weekly tables
rep('wkTop()+fuModeBar()', 'baFuTop()+fuModeBar()', 2)
rep("wkOn()?wkBox('ar'):fuFlow()", "wkOn()?baFuBox('ar'):fuFlow()")
rep('wkOn()?wkBox(PU_KEY):flow', 'wkOn()?baFuBox(PU_KEY):flow')
rep('</style>', CSS + '\n</style>')
rep('async function renderFU(){', JS + '\nasync function renderFU(){')
# the page button (works on ทุกช่องทาง and on each channel) + its section; the button opens the category popup every time
rep('<button data-v="raw" aria-pressed="false">ข้อมูลดิบ</button>',
    '<button data-v="ba" aria-pressed="false">Before / After</button>\n   <button data-v="raw" aria-pressed="false">ข้อมูลดิบ</button>')
rep("if(b.dataset.v==='fu')FU_ASK=true;", "if(b.dataset.v==='fu')FU_ASK=true;if(b.dataset.v==='ba')BA_ASK=true;")
rep('<section id="s-fu" hidden>',
    '<section id="s-ba" class="ovs baov" hidden><div class="shead"><h2>Before / After · ความคืบหน้าการเคลียร์แชท</h2>'
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
print('patched -> %s (Before / After v2 + Follow up progress card)' % dst)

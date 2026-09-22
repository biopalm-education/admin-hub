# mk_line.py rewrites agg.line[month] from scratch; keep the legacy keys some months still carry (v / unansQ / adminScore)
import json, sys
old = json.load(open(sys.argv[1], encoding='utf-8'))['line']; a = json.load(open('src/agg.json', encoding='utf-8'))
for m, v in old.items():
    for k in ('v', 'unansQ', 'adminScore'):
        if k in v and m in a['line'] and k not in a['line'][m]: a['line'][m][k] = v[k]
json.dump(a, open('src/agg.json', 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)

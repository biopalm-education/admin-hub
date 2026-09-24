# -*- coding: utf-8 -*-
"""agg['tagnote'] — ห้องแชท LINE OA รายเดือน แยกตาม แท็ก x โน้ต

tag  = ห้องมีแท็กสถานะอะไรก็ได้ (สถานะลีด != 'ไม่ติดแท็ก')  -> จากชีทรายปี
note = ห้องมีโน้ตอย่างน้อย 1 ใบ ที่สร้างภายในสิ้นเดือนนั้น (สะสมข้ามเดือน/ข้ามปี)

วันที่โน้ตต้องอ่านจาก bundle ดิบ ไม่ใช่จากชีท เพราะชีท "Biopalm LINE Chat Log — 2026"
เก็บเฉพาะโน้ตที่เขียนในปี 2026 — โน้ตปี 2025 (1,345 ใบ / 879 ห้อง) หายไปทั้งหมด
ถ้าใช้ชีทเป็นแหล่งวันที่ ม.ค. 2026 จะเหลือห้องที่ "มีโน้ต" ใบเดียว ซึ่งผิด

ใช้:  python3 mk_tagnote.py sheet.json src/agg.json line_*.json.gz [...]
bundle ที่ต้องมีให้ครบทุกห้องที่อยู่ในชีท (สคริปต์เช็กให้ ถ้าขาดจะหยุด)
"""
import json, sys, gzip, collections, datetime

TZ = datetime.timezone(datetime.timedelta(hours=7))   # เวลาไทย เท่ากับที่ชีทใช้
MS = ['ม.ค.','ก.พ.','มี.ค.','เม.ย.','พ.ค.','มิ.ย.','ก.ค.','ส.ค.','ก.ย.','ต.ค.','พ.ย.','ธ.ค.']


def read_bundles(paths):
    """-> (notes: cid -> set(YYYY-MM-DD), fetched: set(cid))"""
    notes = collections.defaultdict(set)
    fetched = set()
    for p in paths:
        op = gzip.open if p.endswith('.gz') else open
        D = json.load(op(p, 'rt', encoding='utf-8'))
        fetched |= set(D.get('info', {})) | set(D.get('notes', {}))
        for cid, L in D.get('notes', {}).items():
            for n in L:
                notes[cid].add(datetime.datetime.fromtimestamp(n[2] / 1000, TZ).strftime('%Y-%m-%d'))
        del D
    return notes, fetched


def main(sheet_path, agg_path, bundles):
    D = json.load(open(sheet_path, encoding='utf-8'))
    S = D['S']
    MK = {m: '%02d' % (i + 1) for i, m in enumerate(MS)}
    notes, fetched = read_bundles(bundles)

    rooms = collections.defaultdict(dict)
    for r in S[1:]:
        r = r + [''] * (7 - len(r))
        p = r[0].split()
        if len(p) < 2 or p[0] not in MK:
            continue
        rooms[p[1] + '-' + MK[p[0]]][r[2]] = r

    everyone = set().union(*rooms.values())
    missing = everyone - fetched
    if missing:
        raise SystemExit('โน้ตยังไม่ครบ %d ห้อง — ต้องดึงโน้ตห้องพวกนี้ก่อน เช่น %s'
                         % (len(missing), sorted(missing)[:3]))

    out = {}
    for k in sorted(rooms):
        end = k + '-31'
        # รายชื่อห้องรายเดือนไม่เก็บแล้ว (24 ก.ย. 2026) — งานไล่เก็บย้ายไปหน้า Follow up ซึ่งใช้ agg['tnfu']
        c = collections.Counter(); tx = collections.Counter()
        for cid, r in rooms[k].items():
            t = r[4] != 'ไม่ติดแท็ก'
            n = any(d <= end for d in notes.get(cid, ()))
            g = ('T' if t else 'x') + ('N' if n else 'x')
            c[g] += 1
            if g == 'Tx':
                tx[r[4]] += 1
        assert c['TN'] + c['Tx'] + c['xx'] + c['xN'] == len(rooms[k])
        out[k] = dict(rooms=len(rooms[k]), TN=c['TN'], Tx=c['Tx'], xx=c['xx'], xN=c['xN'],
                      txs=dict(tx), lo=False,
                      notes=sum(1 for v in notes.values() for d in v if d[:7] == k))

    A = json.load(open(agg_path, encoding='utf-8'))
    A['tagnote'] = dict(months=out, src='Biopalm LINE Chat Log — 2026 + โน้ตดิบจาก LINE OA')
    json.dump(A, open(agg_path, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    for k, v in out.items():
        print(k, v['rooms'], v['TN'], v['Tx'], v['xx'], v['xN'], v['notes'])


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3:])

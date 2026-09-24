# -*- coding: utf-8 -*-
"""agg['tnfu'] — รายการงาน "ติดแท็ก / ใส่โน้ต ให้ครบ" ของช่องทาง LINE OA

ต่างจาก agg['tagnote'] (ตารางรายเดือน ย้อนหลัง) ตรงที่อันนี้คือ **สถานะล่าสุด**
ของทุกห้องที่มีแชทในปี 2026 ว่าตอนนี้ห้องไหนยังขาดแท็กหรือขาดโน้ต เพื่อให้แอดมินไล่เก็บ

แหล่งข้อมูล — ทั้งสองอย่างอ่านจาก bundle ดิบ ไม่ใช่จากชีท:
  แท็กปัจจุบัน  info[cid] = [ชื่อ, [tagId...], ts]   bundle ที่ดึงทีหลังทับของเก่า
  โน้ตทั้งหมด   notes[cid] = [[ผู้เขียน, noteId, สร้าง(ms), แก้ไข(ms), ข้อความ]...]
ชีทใช้แค่ชื่อลูกค้า / แอดมินที่ดูแล / เดือนที่คุยล่าสุด

3 กลุ่มที่ต้องทำ (ห้องหนึ่งอยู่ได้กลุ่มเดียว)
  xx  ไม่มีทั้งแท็กและโน้ต
  Tx  มีแท็กสถานะ แต่ไม่มีโน้ต   (สำคัญสุด = แท็ก "Q-สมัครแล้ว")
  xN  มีโน้ต แต่ไม่ได้ติดแท็กสถานะ (อ่านโน้ตแล้วไปติดแท็กให้ถูก)

ใช้:  python3 mk_tnfu.py sheet.json src/agg.json line_*.json.gz [...]
      เรียงไฟล์ bundle จากเก่าไปใหม่ — ไฟล์ท้ายสุดถือเป็นแท็กล่าสุด
"""
import json, sys, gzip, re, collections, datetime

TZ = datetime.timezone(datetime.timedelta(hours=7))
MS = ['ม.ค.','ก.พ.','มี.ค.','เม.ย.','พ.ค.','มิ.ย.','ก.ค.','ส.ค.','ก.ย.','ต.ค.','พ.ย.','ธ.ค.']

# แท็กทั้งหมดของ OA Biopalm (ตรวจแล้วตรงกับชีท 3,811/3,855 ห้อง ที่เหลือคือแท็กที่เพิ่งติดหลังชีทถูกดึง)
TAGS = {
    'agmizo66nlddeql7vu5nu3ivai': 'Q-สมัครแล้ว',
    'agh6cwvpsg4pwtlq75zlptukai': 'Q-ยังไม่สมัคร',
    'aglwd5uhmy7serziqodvuy5wai': 'Q-ถามกับระบบ',
    'agmeobfxgl3al2256ucsmcooai': 'แก๊งค์---รวมอ่านเงียบ',
    'agmmvivqh7yjkaxfbkv5kmdfai': 'แก๊งค์--รวมตอบกลับ',
    'aglwoifbzyfklszijzxo62c3ai': 'คอร์สเนื้อหา ม.ต้น',
    'aglwoilotzbgv47q2fxidbudai': 'คอร์สเนื้อหา ม.ปลาย',
    'agko5io6w5ghmdhz5m4hg22uai': 'คอร์สสอบเข้า ม.4',
    'agko5ii7gu5qj63kxff76no5ai': 'คอร์ส สอวน.',
    'aglwoio4f75cmlafspg6vjkuai': 'คอร์ส A-Level',
    'agko5ijoxjpchguvvo22uvzzai': 'คอร์ส IJSO',
    'agnngfs6snhl3o7briy7zvlgai': 'คอร์ส LAB',
}
STATUS = ('Q-สมัครแล้ว', 'Q-ยังไม่สมัคร', 'Q-ถามกับระบบ')   # แท็กสถานะลีด = ตัวที่นับว่า "ติดแท็ก"
# แท็ก "แก๊งค์" เป็นกลุ่มไว้ส่งข้อความ ไม่ใช่สถานะลูกค้า — ไม่เอามาแสดงในรายการงานนี้
SKIP_TAGS = ('แก๊งค์---รวมอ่านเงียบ', 'แก๊งค์--รวมตอบกลับ')
NOTE_MAX = 260


def clean(t):
    t = re.sub(r'\s+', ' ', (t or '')).strip()
    return t[:NOTE_MAX] + '…' if len(t) > NOTE_MAX else t


def read_bundles(paths):
    info, notes, stamp = {}, collections.defaultdict(dict), ''
    for p in paths:
        op = gzip.open if p.endswith('.gz') else open
        D = json.load(op(p, 'rt', encoding='utf-8'))
        info.update(D.get('info', {}))                       # ไฟล์ที่มาทีหลังทับ = แท็กล่าสุด
        for cid, L in D.get('notes', {}).items():
            for n in L:
                notes[cid][n[1]] = (datetime.datetime.fromtimestamp(n[2] / 1000, TZ).strftime('%Y-%m-%d'),
                                    clean(n[4]))
        stamp = max(stamp, (D.get('meta') or {}).get('pulled', ''))
        del D
    unknown = {t for v in info.values() for t in (v[1] or [])} - set(TAGS)
    if unknown:
        raise SystemExit('เจอแท็กที่ยังไม่รู้จัก %s — เพิ่มลง TAGS ใน mk_tnfu.py ก่อน' % sorted(unknown))
    return info, notes, stamp


def main(sheet_path, agg_path, bundles):
    S = json.load(open(sheet_path, encoding='utf-8'))['S']
    MK = {m: '%02d' % (i + 1) for i, m in enumerate(MS)}
    info, notes, stamp = read_bundles(bundles)

    rows = collections.defaultdict(dict)
    for r in S[1:]:
        r = r + [''] * (7 - len(r))
        p = r[0].split()
        if len(p) < 2 or p[0] not in MK:
            continue
        rows[r[2]][p[1] + '-' + MK[p[0]]] = r

    missing = set(rows) - set(info)
    if missing:
        raise SystemExit('ไม่มีข้อมูลแท็กล่าสุดของ %d ห้อง — ต้องดึง LINE ใหม่ เช่น %s'
                         % (len(missing), sorted(missing)[:3]))

    out, g = [], collections.Counter()
    for cid in sorted(rows):
        mm = rows[cid]; last = max(mm); r = mm[last]
        tags = sorted({TAGS[t] for t in (info[cid][1] or [])} - set(SKIP_TAGS))
        has_tag = any(t in STATUS for t in tags)
        mine = sorted(notes.get(cid, {}).values(), reverse=True)     # ใหม่สุดก่อน
        grp = ('T' if has_tag else 'x') + ('N' if mine else 'x')
        g[grp] += 1
        if grp == 'TN':
            continue                                                # ครบแล้ว ไม่ต้องตาม
        nd, nt = (mine[0] if grp == 'xN' else ('', ''))
        out.append([cid, r[1], r[6], last, tags, grp, nd, nt])

    A = json.load(open(agg_path, encoding='utf-8'))
    A['tnfu'] = dict(stamp=stamp[:16].replace('T', ' '), rooms=out, tot=len(rows),
                     done=g['TN'], status=list(STATUS))
    json.dump(A, open(agg_path, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('ห้องทั้งหมด %d · ครบแล้ว %d · ต้องทำ %d (xx %d · Tx %d · xN %d)'
          % (len(rows), g['TN'], len(out), g['xx'], g['Tx'], g['xN']))
    print('แท็กล่าสุด ณ', stamp)
    q = collections.Counter(t for x in out if x[5] == 'Tx' for t in x[4] if t in STATUS)
    print('Tx แยกตามแท็กสถานะ:', dict(q))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3:])

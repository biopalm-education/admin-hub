# -*- coding: utf-8 -*-
"""อัปเดตตาราง "แชทที่ติดแท็ก / ติดโน้ต" รายเดือน (agg['tagnote']) จากไฟล์ดิบ LINE — ไม่ต้องใช้ชีท

ทำไมต้องมีไฟล์นี้ (25 พ.ย. 2026): mk_tagnote.py ต้องใช้ชีทรายปี + ไฟล์ดิบครบทุกห้องของทั้งปี จึงรันได้ครั้งเดียว
(24 ก.ย.) แล้วไม่มีรอบไหนเรียกอีก ตารางค้างที่ ม.ค.–ก.ย. (ก.ย. ข้อมูลถึง 22 ก.ย.) · ไฟล์นี้อัปเดตเฉพาะเดือนที่มีไฟล์ดิบ
แบบรายเดือน (bundle['month']) ในรอบนี้ เดือนอื่นคงของเดิม

นิยามเหมือน mk_tagnote.py ทุกอย่าง:
  ห้อง  = ห้องที่มีข้อความในเดือนนั้น  -> src/line_YYYY-MM.json (หลัง unpack.py / mk_line.py)
  แท็ก  = มีแท็กสถานะ (Q-สมัครแล้ว / Q-ยังไม่สมัคร / Q-ถามกับระบบ) -> แท็กล่าสุดจาก bundle['tagall'] ที่ใหม่สุด
          (ไม่มีใน tagall = แท็กของห้องใน src/line_YYYY-MM.json)
  โน้ต  = มีโน้ตอย่างน้อย 1 ใบ ที่สร้างภายในสิ้นเดือนนั้น -> โน้ตดิบใน bundle (notes / xnotes) ของห้องที่เช็กแล้ว
ห้องที่ไม่มีไฟล์ดิบเช็กโน้ตเลย ใช้สถานะจาก agg.tnfu แทน (นับใน report เป็น fb) · ถ้าเกิน 5% ของเดือน = ไม่อัปเดตเดือนนั้น
เดือนที่ยังไม่จบตอนดึง เก็บ asof (วันที่ดึง) ไว้ให้หน้าเว็บขึ้นว่า "ข้อมูลถึง …"
ไฟล์ดิบที่เก่ากว่ารอบที่อยู่ในตาราง (walk) จะไม่ทับของใหม่

ใช้:  python3 tools/line/tn_month.py src <ไฟล์ดิบ...> [--dry]
พิมพ์แต่ตัวเลข ไม่มีชื่อลูกค้า (log ของ Actions เป็นสาธารณะ)
"""
import json, sys, gzip, os, collections, datetime, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
TZ = datetime.timezone(datetime.timedelta(hours=7))
UTC = datetime.timezone.utc
FB_MAX = 0.05


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + '.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


T = _load('mk_tnfu')        # TAGS (id -> ชื่อ), STATUS


def st_of(tags):            # เหมือน convert.st_of — ค่าเดียวกับคอลัมน์ "สถานะลีด" ในชีท
    return ('สมัครแล้ว' if 'Q-สมัครแล้ว' in tags else 'ยังไม่สมัคร' if 'Q-ยังไม่สมัคร' in tags
            else 'ถามกับระบบ' if 'Q-ถามกับระบบ' in tags else 'ไม่ติดแท็ก')


def walk_of(D):
    m = D.get('meta') or {}
    return m.get('walkAt') or m.get('pulled') or ''


def thai_day(iso):
    return datetime.datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(TZ).strftime('%Y-%m-%d')


def read(paths):
    """-> months {mo: (walk, to_ms)}, tagall ล่าสุด, notes {cid: [createdAt ms...]}, checked set"""
    B = []
    for p in paths:
        D = json.load(gzip.open(p, 'rt', encoding='utf-8') if p.endswith('.gz') else open(p, encoding='utf-8'))
        nb = collections.defaultdict(list)
        for key in ('notes', 'xnotes'):
            for cid, L in (D.get(key) or {}).items():
                nb[cid].extend(n[2] for n in L)
        chk = set(D.get('checked') or []) or (set(D.get('info') or {}) | set(nb))
        B.append(dict(walk=walk_of(D), month=D.get('month') if D.get('mode', 'month') == 'month' else None,
                      to=D.get('to'), tagall=D.get('tagall') or {}, nb=dict(nb), chk=chk))
        del D
    B.sort(key=lambda b: b['walk'])                     # เก่า → ใหม่: ไฟล์ใหม่ทับไฟล์เก่า
    months, TA, NOTES, CHK = {}, {}, {}, set()
    for b in B:
        if b['month'] and b['walk'] and b['walk'] >= months.get(b['month'], ('',))[0]:
            months[b['month']] = (b['walk'], b['to'])
        TA.update(b['tagall'])
        for cid in b['chk']:
            NOTES[cid] = b['nb'].get(cid, [])
        CHK |= b['chk']
    return months, TA, NOTES, CHK


def main(src, paths, dry=False):
    aggp = os.path.join(src, 'agg.json')
    A = json.load(open(aggp, encoding='utf-8'))
    months, TA, NOTES, CHK = read(paths)
    if not months:
        print('tagnote: ไม่มีไฟล์ดิบแบบรายเดือน — คงตารางเดิม'); return {}
    TN = A.get('tagnote') or dict(months={}, src='')
    F = A.get('tnfu') or {}
    fgrp = {r[0]: r[5] for r in F.get('rooms', [])}
    rep = {}
    for mo in sorted(months):
        walk, to_ms = months[mo]
        old = TN['months'].get(mo) or {}
        if old.get('walk') and old['walk'] >= walk:
            rep[mo] = 'ข้าม (ตารางมีรอบที่ใหม่กว่าแล้ว)'; continue
        p = os.path.join(src, 'line_%s.json' % mo)
        if not os.path.exists(p):
            rep[mo] = 'ข้าม (ไม่มี src/line_%s.json)' % mo; continue
        rooms = json.load(open(p, encoding='utf-8'))['rooms']
        end_ms = to_ms if to_ms else None               # ขอบบนของเดือน (เวลาไทย, ไม่รวม)
        if end_ms is None:
            y, m = int(mo[:4]), int(mo[5:])
            nxt = datetime.datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=TZ)
            end_ms = nxt.timestamp() * 1000
        c, tx, fb = collections.Counter(), collections.Counter(), 0
        for r in rooms:
            cid = r['id']
            ta = TA.get(cid)
            tags = {T.TAGS.get(t, t) for t in (ta[1] or [])} if ta else set(r.get('tg') or [])
            st = st_of(tags)
            if cid in CHK:
                n = any(t < end_ms for t in NOTES.get(cid, []))
            else:
                fb += 1
                n = fgrp.get(cid, 'TN') in ('TN', 'xN')
            g = ('T' if st != 'ไม่ติดแท็ก' else 'x') + ('N' if n else 'x')
            c[g] += 1
            if g == 'Tx':
                tx[st] += 1
        if rooms and fb / len(rooms) > FB_MAX:
            rep[mo] = 'ข้าม (ไม่มีโน้ตดิบ %d/%d ห้อง)' % (fb, len(rooms)); continue
        start = datetime.datetime(int(mo[:4]), int(mo[5:]), 1, tzinfo=TZ).timestamp() * 1000
        nn = sum(1 for cid in CHK for t in NOTES.get(cid, []) if start <= t < end_ms)   # โน้ตที่สร้างในเดือน
        asof = thai_day(walk)
        full = walk and datetime.datetime.fromisoformat(walk.replace('Z', '+00:00')).timestamp() * 1000 >= end_ms
        row = dict(rooms=len(rooms), TN=c['TN'], Tx=c['Tx'], xx=c['xx'], xN=c['xN'], txs=dict(tx), lo=False,
                   notes=nn, walk=walk)
        if not full:
            row['asof'] = asof
        assert row['TN'] + row['Tx'] + row['xx'] + row['xN'] == row['rooms']
        TN['months'][mo] = row
        rep[mo] = dict(rooms=row['rooms'], TN=row['TN'], Tx=row['Tx'], xx=row['xx'], xN=row['xN'],
                       notes=nn, fb=fb, asof=row.get('asof', 'ครบเดือน'))
    if not dry:
        TN['src'] = 'Biopalm LINE Chat Log — 2026 + โน้ตดิบจาก LINE OA · ก.ย. 2026 เป็นต้นไปจากไฟล์ดิบ LINE (tn_month.py)'
        A['tagnote'] = TN
        json.dump(A, open(aggp, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('tagnote:', json.dumps(rep, ensure_ascii=False))
    return rep


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if x != '--dry']
    main(a[0], a[1:], dry='--dry' in sys.argv)

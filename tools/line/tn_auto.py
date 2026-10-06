# -*- coding: utf-8 -*-
"""รอบอัปเดตอัตโนมัติ (GitHub Actions): อัปเดตรายการ "ติดแท็ก / ใส่โน้ต ให้ครบ" จากไฟล์ดิบ LINE บน Drive

refresh.py ดาวน์โหลดไฟล์ line_*_raw.json.gz ล่าสุดจาก Drive มาไว้ในโฟลเดอร์หนึ่ง แล้วเรียกไฟล์นี้
ใช้เฉพาะไฟล์ที่ดึงหลังรอบที่อยู่ในแดชบอร์ด (เทียบเวลา walkAt/pulled กับ agg.tnfu) เรียงเก่า → ใหม่
ไม่มีไฟล์ใหม่ = ไม่ทำอะไร · พิมพ์แต่ตัวเลข ไม่มีชื่อลูกค้า (log ของ Actions เป็นสาธารณะ)

ใช้:  python3 tools/line/tn_auto.py src <ไฟล์ดิบ...>
"""
import json, sys, gzip, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tn_update as U   # noqa: E402


def pulled_at(p):
    try:
        D = json.load(gzip.open(p, 'rt', encoding='utf-8') if p.endswith('.gz') else open(p, encoding='utf-8'))
    except Exception:
        return None
    m = D.get('meta') or {}
    t = m.get('walkAt') or m.get('pulled')
    ok = isinstance(D.get('tagall'), dict) or isinstance(D.get('info'), dict)
    del D
    return U.iso_utc(t) if (t and ok) else None


def main(src, files):
    A = json.load(open(os.path.join(src, 'agg.json'), encoding='utf-8'))
    if not A.get('tnfu'):
        print('tnfu: ยังไม่มีรายการในแดชบอร์ด — ข้าม'); return
    st = U.old_stamp(A['tnfu'])
    del A
    pick = sorted((t, p) for p in files for t in [pulled_at(p)] if t and t > st)
    if not pick:
        print('tnfu: ไม่มีไฟล์ LINE ใหม่กว่ารอบเดิม (%s) — คงรายการเดิม' % U.thai(st).strftime('%Y-%m-%d %H:%M'))
        return
    rep = U.main(src, [p for _, p in pick], verbose=False)
    g = rep['groups']
    print('tnfu: อัปเดตจาก %d ไฟล์ · ณ %s · ห้องปีนี้ %d · ค้าง %s → %s (ไม่มีทั้งคู่ %d · มีแท็กไม่มีโน้ต %d · มีโน้ตไม่มีแท็ก %d)'
          ' · แท็กสด %d/%d · เช็กโน้ต %d · ห้องใหม่ยังไม่เช็ก %d · ห้องรอบเดิม %s/%s'
          % (len(pick), rep['new_stamp'], rep['tot'], rep['todo_old'], rep['todo'], g.get('xx', 0), g.get('Tx', 0),
             g.get('xN', 0), rep['tags_fresh'], rep['tot'], rep['notes_checked'], rep['new_unchecked'],
             rep['uni_old_rebuilt'], rep['tot_old']))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])

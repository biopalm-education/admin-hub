# -*- coding: utf-8 -*-
"""ลิงก์ตรงห้องแชท Instagram สำหรับทุกห้อง (เพิ่ม 1 ต.ค. 2026)

เดิม agg['igt'] (ชื่อบัญชี IG → เลขห้องใน Business Suite) ทำมือครั้งเดียว รอบอัปเดตทุกเช้าไม่เคยเติม
แชท IG ใหม่จึงไม่มีลิงก์ ปุ่มเลยเปิด Inbox เฉย ๆ และ Meta เปิดแชทล่าสุดให้แทน

รหัสห้องจาก Graph API (แถว[19]) ถอดเป็นเลขห้องได้ตรง ๆ:
  ตัด escape ของ Meta (ZA→Z, ZB→+, ZC→/, ZD→=) แล้ว base64 → "ig_dm:<เลขห้อง>"
  (ตรวจกับแชทจริง 1 ต.ค. 2026 · ลิงก์ = selected_item_id=<เลขห้อง>&thread_type=IG_MESSAGE)
สคริปต์นี้เติม igt ให้ทุกห้องที่ถอดได้ ไม่ลบของเดิม — รันจาก repo root หลัง unpack / ดึงข้อมูล
"""
import json, os, re, base64

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def thread_no(cid):
    s = str(cid or '')
    if not s.startswith('aWdf'):
        return None
    out, i = [], 0
    while i < len(s):
        if s[i] == 'Z' and i + 1 < len(s) and s[i + 1] in 'ABCD':
            out.append({'A': 'Z', 'B': '+', 'C': '/', 'D': '='}[s[i + 1]]); i += 2
        else:
            out.append(s[i]); i += 1
    b = ''.join(out)
    b += '=' * (-len(b) % 4)
    try:
        t = base64.b64decode(b).decode('ascii')
    except Exception:
        return None
    m = re.fullmatch(r'ig_dm:(\d{6,})', t)
    return m.group(1) if m else None


def main():
    AP = os.path.join(ROOT, 'src', 'agg.json')
    agg = json.load(open(AP, encoding='utf-8'))
    ig = json.load(open(os.path.join(ROOT, 'src', 'ig_all.json'), encoding='utf-8'))
    igt = dict(agg.get('igt') or {})
    before = len(igt)
    rows = linked = added = changed = undecodable = 0
    for mo, d in (ig.get('months') or {}).items():
        for r in d.get('leads') or []:
            rows += 1
            name = r[0] if r else ''
            n = thread_no(r[19]) if len(r) > 19 else None
            if not n:
                undecodable += 1
                if name in igt:
                    linked += 1
                continue
            if not name:
                continue
            if name not in igt:
                added += 1
            elif str(igt[name]) != n:
                changed += 1
            igt[name] = n
            linked += 1
    print('IG แชท %d แถว · มีลิงก์ %d · igt %d → %d (เพิ่ม %d · แก้ %d) · ถอดรหัสไม่ได้ %d'
          % (rows, linked, before, len(igt), added, changed, undecodable))
    if igt != (agg.get('igt') or {}):
        agg['igt'] = igt
        json.dump(agg, open(AP, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)


if __name__ == '__main__':
    main()

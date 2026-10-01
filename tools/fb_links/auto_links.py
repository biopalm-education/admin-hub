# -*- coding: utf-8 -*-
"""ใส่ลิงก์ตรงห้องแชท Facebook อัตโนมัติจากไฟล์ fb_threads ที่ผู้ใช้อัปขึ้น Drive (เพิ่ม 1 ต.ค. 2026)

refresh.py ดาวน์โหลดไฟล์ชื่อ fb_threads*.json ที่แก้ไขภายใน 21 วันล่าสุดจาก Drive มาไว้ใน FBT_DIR
(ค่าเริ่ม /tmp/fb_threads_in) แล้วรันสคริปต์นี้ทุกเช้าหลังดึงข้อมูล — รันซ้ำกี่รอบก็ได้ผลเหมือนเดิม
เพราะใส่เฉพาะห้องที่ยังไม่มีลิงก์ และไม่ใช้รหัสบัญชีที่ผูกกับห้องอื่นแล้ว

ไฟล์ fb_threads = {"rows": [[threadFBID, title, timestamp_ms, threadType, threadID], ...]}
เก็บจากรายการแชทใน Business Suite ด้วย harvest_list.js · มีชื่อลูกค้า ห้าม commit เข้า repo

เกณฑ์ (ต่อยอดจาก match_month.py / match_timeonly.py ที่ใช้ขึ้นหน้าจริงเมื่อ 24 ก.ย.)
  A  ชื่อที่ห้องเคยใช้ (normalize) ตรงกับชื่อใน Inbox และนาทีล่าสุดใน Inbox ตรงกับนาทีของข้อความใด
     ข้อความหนึ่งของห้องนั้นในข้อมูลเรา และมีผู้สมัครเดียว
     — ใช้ได้แม้ไฟล์เก่ากว่าข้อมูลหลายวัน (ห้องที่คุยต่อหลังเก็บรายการ เวลาใน Inbox ยังตรงกับข้อความเดิม)
  B  ชื่อไม่ซ้ำทั้งสองฝั่ง และเวลาใน Inbox ใหม่กว่าข้อความล่าสุดทั้งหมดในข้อมูลเรา (= T2 เดิม)
  C  นาทีล่าสุดใน Inbox ตรงกับข้อความล่าสุดของห้องพอดี และมีห้อง Inbox ที่ยังไม่ถูกใช้ห้องเดียว
     ในนาทีนั้น (= T3 เดิม · ทดสอบย้อนหลังผิดได้ไม่เกินราว 1 ใน 500)
ตรวจลิงก์เดิม: ถ้าห้อง Inbox ของรหัสที่ผูกไว้ ไม่ตรงกับห้องเดิมเลย (เวลาใน Inbox เก่ากว่าข้อความล่าสุด
  ของห้องเดิมและไม่ตรงกับข้อความใดของห้องเดิม) แต่ตรงกับอีกห้องหนึ่งตามเกณฑ์ A เพียงห้องเดียว
  → ย้ายรหัสไปห้องที่ถูก และห้องเดิมกลับไปรอจับคู่ใหม่
repo นี้ public: log พิมพ์แค่จำนวน ไม่พิมพ์ชื่อหรือรหัส
"""
import json, glob, os, sys, importlib.util
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
spec = importlib.util.spec_from_file_location('mm', os.path.join(HERE, 'match_month.py'))
mm = importlib.util.module_from_spec(spec); spec.loader.exec_module(mm)


def load_threads(paths):
    """รวมหลายไฟล์: รหัสเดียวกันใช้แถวที่เวลาใหม่สุด"""
    best = {}
    for p in paths:
        try:
            rows = json.load(open(p, encoding='utf-8')).get('rows') or []
        except Exception as e:
            print('ข้ามไฟล์ที่อ่านไม่ได้: %s' % type(e).__name__)
            continue
        for x in rows:
            if not x or not x[0]:
                continue
            fid, ts = str(x[0]), int(x[2] or 0)
            if fid not in best or ts > best[fid][2]:
                best[fid] = (fid, mm.norm(x[1]), ts)
    return [(fid, n, ts // 60000 - mm.EPOCH_MIN) for fid, n, ts in best.values()]


def room_index(months):
    names, mins, last = defaultdict(set), defaultdict(set), {}
    gmax = 0
    for k, chats in months.items():
        b = mm.month_base(k)
        for r in chats:
            g = r[19]
            if r[0]:
                names[g].add(mm.norm(r[0]))
            for x in (r[18] or ()):
                t = b + x[0]
                mins[g].add(t)
                if t > last.get(g, -1):
                    last[g] = t
                gmax = max(gmax, t)
    return names, mins, last, gmax


def run(paths, write=True):
    inbox = load_threads(paths)
    if not inbox:
        print('ไม่มีไฟล์ fb_threads ให้ใช้ — ข้าม')
        return 0
    AP = os.path.join(ROOT, 'src', 'agg.json')
    agg = json.load(open(AP, encoding='utf-8'))
    fb = dict(agg.get('fbuid') or {})
    os.chdir(ROOT)
    months = mm.load_months()
    names, mins, last, gmax = room_index(months)

    by_name = defaultdict(list)
    for x in inbox:
        by_name[x[1]].append(x)
    by_fid = {x[0]: x for x in inbox}
    gids_by_name = defaultdict(set)
    for g, ns in names.items():
        for n in ns:
            gids_by_name[n].add(g)

    def cand_a(g):
        return {x[0] for n in names[g] for x in by_name.get(n, ()) if x[2] in mins[g]}

    # 1) ตรวจลิงก์เดิมกับไฟล์ล่าสุด
    ok = bad = moved = 0
    owner = {v: g for g, v in fb.items()}
    for g, fid in list(fb.items()):
        x = by_fid.get(fid)
        if not x or g not in last:
            continue
        if x[2] in mins[g] or x[2] >= last[g]:
            ok += 1
            continue
        bad += 1
        # ห้องอื่นที่ชื่อ + นาทีตรงกับห้อง Inbox นี้
        others = [h for h in gids_by_name.get(x[1], ()) if h != g and x[2] in mins[h]]
        if len(others) == 1 and others[0] not in fb:
            h = others[0]
            del fb[g]
            fb[h] = fid
            owner[fid] = h
            moved += 1
    print('ตรวจลิงก์เดิมที่อยู่ในไฟล์: ตรง %d · ไม่ตรง %d · ย้ายไปห้องที่ถูก %d' % (ok, bad, moved))

    # 2) ห้องที่ยังไม่มีลิงก์
    used = set(fb.values())
    todo = [g for g in last if g not in fb]
    newA, newB, newC = {}, {}, {}
    for g in todo:
        c = cand_a(g) - used
        if len(c) == 1:
            newA[g] = c.pop()
    taken = used | set(newA.values())
    for g in todo:
        if g in newA:
            continue
        hits = [x for n in names[g] for x in by_name.get(n, ())]
        ns = [n for n in names[g] if n in by_name]
        if len(hits) != 1 or len(ns) != 1 or len(gids_by_name[ns[0]]) != 1:
            continue
        x = hits[0]
        if x[2] > gmax and x[0] not in taken:
            newB[g] = x[0]
    taken |= set(newB.values())
    bymin = defaultdict(list)
    for x in inbox:
        if x[0] not in taken:
            bymin[x[2]].append(x[0])
    for g in todo:
        if g in newA or g in newB:
            continue
        c = bymin.get(last[g], [])
        if len(c) == 1:
            newC[g] = c[0]
    cnt = Counter(list(newA.values()) + list(newB.values()) + list(newC.values()))
    add = {}
    for d in (newA, newB, newC):
        for g, v in d.items():
            if cnt[v] == 1 and v not in used:
                add[g] = v
    fb.update(add)
    assert len(set(fb.values())) == len(fb), 'รหัสบัญชีซ้ำ — ไม่เขียน'
    nA = sum(1 for g in add if g in newA)
    nB = sum(1 for g in add if g in newB)
    nC = len(add) - nA - nB
    print('ห้อง Inbox ในไฟล์ %d · ลิงก์ใหม่ %d (A ชื่อ+เวลา %d · B ชื่อไม่ซ้ำ %d · C เวลาอย่างเดียว %d) · fbuid %d → %d'
          % (len(inbox), len(add), nA, nB, nC, len(agg.get('fbuid') or {}), len(fb)))
    if write and (add or moved):
        agg['fbuid'] = fb
        json.dump(agg, open(AP, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    return len(add)


if __name__ == '__main__':
    d = os.environ.get('FBT_DIR') or '/tmp/fb_threads_in'
    ps = sys.argv[1:] or sorted(glob.glob(os.path.join(d, '*.json')))
    ps = [p for p in ps if not p.startswith('--')]
    run(ps, write='--dry' not in sys.argv)

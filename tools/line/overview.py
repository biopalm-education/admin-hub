# -*- coding: utf-8 -*-
"""Rebuild the "สรุปภาพรวม (รายเดือน)" tab for every LINE month in agg.json.
Registration numbers (from notes) are not in agg: they are read back from the current tab and only the months
passed in `regs` ({'2026-09': {...reg_of...}}) are replaced. Run in the Composio workbench:
    exec(open('tools/line/overview.py').read()); rebuild_overview(run_composio_tool, SID, agg, {'2026-09': S['reg']}, pulled_note)"""
OVTAB = 'สรุปภาพรวม (รายเดือน)'
THM = {'01': 'ม.ค.', '02': 'ก.พ.', '03': 'มี.ค.', '04': 'เม.ย.', '05': 'พ.ค.', '06': 'มิ.ย.', '07': 'ก.ค.', '08': 'ส.ค.', '09': 'ก.ย.', '10': 'ต.ค.', '11': 'พ.ย.', '12': 'ธ.ค.'}
REGROWS = {'ห้องที่มีโน้ตลงทะเบียน (รหัส G)': 'rooms', '— ลงคอร์สเรียนสด': 'live', '— ซื้อเทปย้อนหลัง (G000)': 'tape', 'จำนวนการลงทะเบียน (ห้อง × คอร์ส)': 'regs'}

def rebuild_overview(run, sid, agg, regs, source_line, partial=None):
    r, e = run(tool_slug='GOOGLESHEETS_BATCH_GET', arguments={'spreadsheet_id': sid, 'ranges': ["'%s'!A1:Z200" % OVTAB], 'valueRenderOption': 'UNFORMATTED_VALUE'})
    old = r['data']['valueRanges'][0].get('values', [])
    MS = sorted(agg['line'].keys()); LB = ['%s %s' % (THM[m[5:]], m[:4]) for m in MS]
    hdr = next(row for row in old if row and row[0] == 'ยอดสมัครจริง')
    col = {h: i for i, h in enumerate(hdr)}
    note = {row[0]: row[-1] for row in old if row and len(row) > 3 and isinstance(row[-1], str) and len(row[-1]) > 12}
    R = {m: {} for m in MS}
    for row in old:
        if row and row[0] in REGROWS:
            for m, l in zip(MS, LB):
                if l in col and col[l] < len(row) and row[col[l]] != '': R[m][REGROWS[row[0]]] = row[col[l]]
    for m, v in regs.items(): R[m] = v
    L = agg['line']; W = {m: agg['v4']['line'].get(m, {}).get('W', '') for m in MS}
    fmt = lambda s: '—' if s is None else ('%d วิ' % round(s) if round(s) < 60 else '%d นาที' % round(s / 60))
    sg = lambda x: ('+%d' % x) if x > 0 else str(x)
    pc = lambda a, b: '%.1f%%' % (100 * a / b) if b else '—'
    short = [l.split()[0] for l in LB]
    H = lambda t: [t] + LB + ['เปลี่ยนแปลง %s→%s' % (short[0], short[-1]), 'หมายเหตุ']
    def mrow(label, vals, numeric=True, nt=None):
        ch = sg(vals[-1] - vals[0]) if numeric and all(isinstance(v, int) for v in (vals[0], vals[-1])) else ''
        return [label] + vals + [ch, note.get(label, '') if nt is None else nt]
    g = [['สรุปภาพรวมรายเดือน — LINE OA'], [source_line], []]
    g.append(H('ตัวชี้วัด'))
    g.append(mrow('ห้องแชท', [L[m]['threads'] for m in MS], nt=note.get('ห้องแชท', '').split(' · ⏳')[0] + ((' · ⏳ ' + partial) if partial else '')))
    g.append(mrow('ข้อความทั้งหมด', [L[m]['msgs'] for m in MS]))
    g.append(mrow('— ลูกค้าพิมพ์/กดปุ่ม', [L[m]['cust'] for m in MS]))
    g.append(mrow('— แอดมินตัวจริงพิมพ์', [L[m]['adm'] for m in MS]))
    g.append(mrow('— บอทตอบอัตโนมัติ', [L[m]['bot'] for m in MS]))
    g.append(mrow('ตอบครั้งแรกจริง (มัธยฐาน)', [fmt(L[m]['first_med']) for m in MS], False))
    g.append(mrow('ตอบครั้งแรกจริง (ช้าสุด 10%)', [fmt(L[m]['first_p90']) for m in MS], False))
    g.append(mrow('ตอบเร็วสุดต่อห้อง (มัธยฐาน)', [fmt(L[m].get('fast_med')) for m in MS], False))
    g.append(mrow('ตอบเร็วสุดต่อห้อง (ช้าสุด 10%)', [fmt(L[m].get('fast_p90')) for m in MS], False))
    g.append(mrow('ไม่เคยได้คุยกับแอดมิน', [L[m]['notyped'] for m in MS], nt=' · '.join('%s %s' % (s, pc(L[m]['notyped'], L[m]['threads'])) for s, m in zip(short, MS))))
    g.append(mrow('ทักมาแล้วหาย', [L[m]['unans'] for m in MS], nt=' · '.join('%s %s' % (s, pc(L[m]['unans'], L[m]['threads'])) for s, m in zip(short, MS))))
    g.append([]); g.append(H('ยอดสมัครจริง'))
    for lbl, k in REGROWS.items(): g.append(mrow(lbl, [R[m].get(k, '') for m in MS]))
    g.append(mrow('ปิดการขาย (สลิปตรวจสำเร็จ)', [W[m] for m in MS]))
    g.append([]); g.append(H('สถานะจากแท็กของทีม'))
    g.append(mrow('Q-สมัครแล้ว', [L[m]['won'] for m in MS], nt='⚠ แท็กติดที่ตัวห้อง ไม่ผูกกับเดือน — เทียบกับห้องที่มีโน้ตลงทะเบียน: ' + ' · '.join('%s %s vs %s' % (s, L[m]['won'], R[m].get('rooms', '—')) for s, m in zip(short, MS))))
    g.append(mrow('Q-ยังไม่สมัคร', [L[m]['open'] for m in MS])); g.append(mrow('Q-ถามกับระบบ', [L[m]['sysonly'] for m in MS]))
    g.append(mrow('ไม่ติดแท็ก', [L[m]['notag'] for m in MS]))
    g.append([])
    adm = []
    for m in MS:
        for a, _, _ in L[m]['admins']:
            if a not in adm: adm.append(a)
    ad = {m: {a: (x, y) for a, x, y in L[m]['admins']} for m in MS}
    g.append(['แอดมิน'] + ['ห้อง ' + s for s in short] + ['ข้อความ ' + s for s in short])
    for a in adm: g.append([a] + [ad[m].get(a, (0, 0))[0] for m in MS] + [ad[m].get(a, (0, 0))[1] for m in MS])
    g.append([])
    tg = {m: dict(L[m]['tags']) for m in MS}; tags = sorted({t for m in MS for t in tg[m]}, key=lambda t: -sum(tg[m].get(t, 0) for m in MS))
    g.append(['แท็กคอร์ส/สถานะ'] + ['ห้อง ' + s for s in short])
    for t in tags: g.append([t] + [tg[m].get(t, 0) for m in MS])
    g.append([])
    hr = {m: dict((h, n) for h, n in L[m]['hours']) for m in MS}
    g.append(['ชั่วโมง (เวลาไทย)'] + ['ข้อความลูกค้า ' + s for s in short])
    for h in range(24): g.append(['%02d:00' % h] + [hr[m].get(h, 0) for m in MS])
    Wd = max(max(len(r) for r in g), max((len(r) for r in old), default=0))
    n = max(len(g), len(old))
    grid = [r + [''] * (Wd - len(r)) for r in g] + [[''] * Wd for _ in range(n - len(g))]
    colL = lambda i: ('' if i < 26 else chr(64 + i // 26)) + chr(65 + i % 26)
    r, e = run(tool_slug='GOOGLESHEETS_VALUES_UPDATE', arguments={'spreadsheet_id': sid, 'range': "'%s'!A1:%s%d" % (OVTAB, colL(Wd - 1), n), 'value_input_option': 'RAW', 'values': grid, 'auto_expand_sheet': True})
    if e: raise Exception(e)
    print('overview rebuilt', len(MS), 'months', r['data'].get('updatedRange'))
    return R

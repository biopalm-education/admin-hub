# -*- coding: utf-8 -*-
"""Write one month into the yearly sheet "Biopalm LINE Chat Log — 2026". REPLACES that month if it is already there
(summary rows with that month label are deleted, the month's message/notes tabs are dropped and recreated).
Run inside the Composio workbench (needs run_composio_tool):
    exec(open('tools/line/sheet_month.py').read()); write_month(run_composio_tool, SID, json.load(open('out/sheet_2026-09.json')))"""
import json, time, threading, calendar
from concurrent.futures import ThreadPoolExecutor
SUMTAB = 'สรุปรายแชท (ทุกเดือน)'
MH = ['ชื่อลูกค้า', 'LINE user id', 'วันที่', 'เวลา', 'ผู้ส่ง', 'ชื่อแอดมิน', 'ข้อความ', 'สถานะห้อง']
NH = ['ชื่อลูกค้า', 'LINE user id', 'ลิงก์เข้าห้องแชท', 'วันที่สร้างโน้ต', 'เวลา', 'ผู้เขียนโน้ต', 'รหัสคอร์ส (G)', 'ประเภท', 'สถานะลีด (แท็ก)', 'ข้อความโน้ต']

def _tabs(run, sid):
    r, e = run(tool_slug='GOOGLESHEETS_GET_SPREADSHEET_INFO', arguments={'spreadsheet_id': sid})
    return {s['properties']['title']: s['properties'] for s in r['data']['sheets']}

def _get(run, sid, rng):
    r, e = run(tool_slug='GOOGLESHEETS_BATCH_GET', arguments={'spreadsheet_id': sid, 'ranges': [rng], 'valueRenderOption': 'UNFORMATTED_VALUE'})
    if e: raise Exception(e)
    return r['data']['valueRanges'][0].get('values', [])

def write_month(run, sid, S, threads=4):
    mo, lab = S['month'], S['label']; th = lab.split()[0]; last = calendar.monthrange(int(mo[:4]), int(mo[5:]))[1]
    names = {'1': 'ข้อความ %s 1-10' % th, '2': 'ข้อความ %s 11-20' % th, '3': 'ข้อความ %s 21-%d' % (th, last)}
    ntab = 'โน้ตลงทะเบียน %s' % th
    tabs = _tabs(run, sid)
    # 1) drop + recreate the month's own tabs
    for t in list(names.values()) + [ntab]:
        if t in tabs:
            r, e = run(tool_slug='GOOGLESHEETS_DELETE_SHEET', arguments={'spreadsheetId': sid, 'sheetId': tabs[t]['sheetId']})
            if e: raise Exception('delete %s: %s' % (t, e))
    for k, t in names.items():
        run(tool_slug='GOOGLESHEETS_ADD_SHEET', arguments={'spreadsheet_id': sid, 'title': t, 'force_unique': False,
            'properties': {'gridProperties': {'rowCount': max(2, len(S['msg'][k]) + 1), 'columnCount': 8, 'frozenRowCount': 1}}})
    run(tool_slug='GOOGLESHEETS_ADD_SHEET', arguments={'spreadsheet_id': sid, 'title': ntab, 'force_unique': False,
        'properties': {'gridProperties': {'rowCount': max(2, len(S['notes']) + 1), 'columnCount': 10, 'frozenRowCount': 1}}})
    # 2) delete old summary rows of this month (bottom-up, contiguous blocks)
    colA = _get(run, sid, "'%s'!A1:A20000" % SUMTAB)
    idx = [i for i, r in enumerate(colA) if r and r[0] == lab]
    blocks = []
    for i in idx:
        if blocks and blocks[-1][1] == i: blocks[-1][1] = i + 1
        else: blocks.append([i, i + 1])
    sumid = _tabs(run, sid)[SUMTAB]['sheetId']
    for a, b in reversed(blocks):
        r, e = run(tool_slug='GOOGLESHEETS_DELETE_DIMENSION', arguments={'spreadsheet_id': sid, 'delete_dimension_request': {
            'range': {'sheet_id': sumid, 'dimension': 'ROWS', 'start_index': a, 'end_index': b}}})
        if e: raise Exception('delete rows: %s' % e)
    start = len(colA) - len(idx) + 1
    # 3) write
    jobs = []
    def add(tab, row0, rows, ncol):
        L = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'[ncol - 1]
        for i in range(0, len(rows), 800):
            ch = [[('' if c is None else c) for c in list(r) + [''] * (ncol - len(r))] for r in rows[i:i + 800]]
            jobs.append(("'%s'!A%d:%s%d" % (tab, row0 + i, L, row0 + i + len(ch) - 1), ch))
    add(SUMTAB, start, S['sum'], 17)
    for k, t in names.items(): add(t, 1, [MH] + S['msg'][k], 8)
    add(ntab, 1, [NH] + S['notes'], 10)
    lock, fails = threading.Lock(), []
    def w(j):
        rng, vals = j
        for a in range(4):
            r, e = run(tool_slug='GOOGLESHEETS_VALUES_UPDATE', arguments={'spreadsheet_id': sid, 'range': rng, 'value_input_option': 'RAW', 'values': vals, 'auto_expand_sheet': True})
            if not e and r.get('data', {}).get('updatedRows'): return
            time.sleep(8)
        with lock: fails.append(rng)
    with ThreadPoolExecutor(threads) as ex: list(ex.map(w, jobs))
    if fails: raise Exception('write failed: %s' % fails[:3])
    # 4) verify
    colA = _get(run, sid, "'%s'!A1:A20000" % SUMTAB)
    got = dict(sum=sum(1 for r in colA if r and r[0] == lab),
               msgs=sum(len(_get(run, sid, "'%s'!B2:B40000" % t)) for t in names.values()),
               notes=len(_get(run, sid, "'%s'!B2:B5000" % ntab)))
    want = dict(sum=len(S['sum']), msgs=sum(len(v) for v in S['msg'].values()), notes=len(S['notes']))
    print('sheet', mo, 'written', got, 'expected', want, 'OK' if got == want else 'MISMATCH')
    return got == want

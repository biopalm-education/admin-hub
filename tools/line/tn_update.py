# -*- coding: utf-8 -*-
"""อัปเดต agg['tnfu'] (Follow up · ติดแท็ก / ใส่โน้ต ให้ครบ) ต่อจากของเดิม — ไม่ต้องใช้ไฟล์ดิบเก่า

ทำไมต้องมีไฟล์นี้: mk_tnfu.py สร้างรายการจากศูนย์ ต้องมีไฟล์ดิบครบทุกเดือนของปี ซึ่งลบทิ้งหลังแต่ละรอบ
รายการจึงค้างอยู่ที่รอบแรก (22 ก.ย. 2026) ไฟล์นี้อัปเดตจากรอบล่าสุดอย่างเดียว:

  แท็ก   อ่านใหม่ทุกห้อง จาก bundle['tagall'] (puller.js เก็บแท็กของทุกห้องตอนไล่รายชื่อ ไม่เพิ่ม request)
  โน้ต   ห้องที่ bundle เช็กโน้ตแล้ว (bundle['checked']) ใช้ของใหม่ · ห้องที่ไม่ได้เช็ก ใช้สถานะเดิมใน agg.tnfu
  ห้อง   ทุกห้องที่มีแชทในปีนี้ จาก src/line_YYYY-*.json (หลัง unpack.py) ไม่ต้องใช้ชีท

ห้องที่ไม่ได้เช็กโน้ตรอบนี้ และไม่อยู่ในรายการเดิม:
  ถ้ามีแชทก่อนรอบเดิม = ตอนนั้นครบแล้ว (TN) → ถือว่ายังมีโน้ต
  ถ้าเพิ่งเริ่มคุยหลังรอบเดิม = ไม่รู้ → ถือว่ายังไม่มีโน้ต (ขึ้นในรายการไว้ก่อน ดีกว่าหลุดหาย) และนับใน report

ใช้:
  python3 tools/line/tn_update.py --todo src [out.json]
        → รหัสห้อง (prefix) ที่ยังค้าง ไม่มีโน้ต (xx / Tx) + วันที่รอบเดิม สำหรับ LINEPULL.start({notesFor, from})
  python3 tools/line/tn_update.py src line_*.json.gz [...] [--dry]
        → เขียน src/agg.json['tnfu'] ใหม่ (เรียงไฟล์เก่า → ใหม่) · --dry = รายงานอย่างเดียว ไม่เขียน
"""
import json, sys, gzip, glob, os, collections, datetime, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + '.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


T = _load('mk_tnfu')        # TAGS, STATUS, SKIP_TAGS, clean
C = _load('convert')        # OWN (assignedBizId → ชื่อแอดมิน)
TZ = datetime.timezone(datetime.timedelta(hours=7))
UTC = datetime.timezone.utc


def thai(dt): return dt.astimezone(TZ)
def iso_utc(s): return datetime.datetime.fromisoformat(s.replace('Z', '+00:00')).astimezone(UTC)


def old_stamp(old):
    """เวลารอบเดิมแบบ datetime — mk_tnfu.py เขียน stamp เป็นเวลา UTC (ตัดจาก toISOString) ไม่มีโซน"""
    if old.get('stampUtc'):
        return iso_utc(old['stampUtc'])
    return datetime.datetime.strptime(old['stamp'], '%Y-%m-%d %H:%M').replace(tzinfo=UTC)


def universe(src):
    files = sorted(glob.glob(os.path.join(src, 'line_*.json')))
    year = max(os.path.basename(p)[5:9] for p in files)
    U = {}
    for p in files:
        mo = os.path.basename(p)[5:12]
        if mo[:4] != year:
            continue
        for r in json.load(open(p, encoding='utf-8'))['rooms']:
            u = U.get(r['id'])
            U[r['id']] = dict(name=r.get('n') or '', own=r.get('ow') or '', mo=mo, tg=r.get('tg') or [],
                              first=u['first'] if u else mo, f=u['f'] if u else (r.get('f') or ''))
    return U, year


def existed_at(u, st):
    """ห้องนี้มีแชทแล้วก่อนเวลา st ไหม (ดูจากข้อความแรกของห้องในปี)"""
    t = thai(st); smon = t.strftime('%Y-%m')
    if u['first'] != smon:
        return u['first'] < smon
    return bool(u['f']) and u['f'] <= t.strftime('%m-%d %H:%M')


def read_bundles(paths):
    TA, NOTES, CHK, walk, info_only = {}, {}, set(), '', 0
    for p in paths:
        D = json.load(gzip.open(p, 'rt', encoding='utf-8') if p.endswith('.gz') else open(p, encoding='utf-8'))
        ta = D.get('tagall')
        if ta:
            TA.update(ta)
        else:                                   # ไฟล์จากตัวดึงรุ่นเก่า: มีแท็กเฉพาะห้องที่คุยในเดือนนั้น
            for cid, v in (D.get('info') or {}).items():
                TA[cid] = [v[0], v[1], 0, v[2] if len(v) > 2 else 0, None]
            info_only += 1
        nb = collections.defaultdict(list)
        for key in ('notes', 'xnotes'):
            for cid, L in (D.get(key) or {}).items():
                nb[cid].extend(L)
        chk = set(D.get('checked') or []) or (set(D.get('info') or {}) | set(nb))
        for cid in chk:                         # เช็กในไฟล์ที่ใหม่กว่า = แทนของเดิมทั้งหมด (โน้ตที่ลบไปก็หาย)
            NOTES[cid] = {n[0]: n for n in nb.get(cid, [])}
        CHK |= chk
        m = D.get('meta') or {}
        walk = max(walk, m.get('walkAt') or m.get('pulled') or '')
        del D
    return TA, NOTES, CHK, walk, info_only


def todo(src, outp=None):
    A = json.load(open(os.path.join(src, 'agg.json'), encoding='utf-8'))
    old = A.get('tnfu') or {}
    U, _ = universe(src)
    ids = sorted(r[0] for r in old.get('rooms', []) if r[5] in ('xx', 'Tx'))
    pl = 6
    while len({i[:pl] for i in U}) < len(U):    # prefix สั้นสุดที่ยังไม่ชนกันในห้องของปีนี้
        pl += 1
    since = (thai(old_stamp(old)) - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    res = dict(since=since, pl=pl, n=len(ids), notesFor=sorted({i[:pl] for i in ids}))
    if outp:
        json.dump(res, open(outp, 'w', encoding='utf-8'), separators=(',', ':'))
    print('รอบเดิม %s · ห้องที่ต้องเช็กโน้ต %d (xx+Tx) · prefix %d ตัว · from:%s'
          % (old.get('stamp'), len(ids), pl, since))
    return res


def main(src, paths, dry=False, verbose=True):
    aggp = os.path.join(src, 'agg.json')
    A = json.load(open(aggp, encoding='utf-8'))
    old = A.get('tnfu')
    if not old:
        raise SystemExit('ยังไม่มี agg.tnfu — สร้างครั้งแรกด้วย mk_tnfu.py')
    st0 = old_stamp(old)
    U, year = universe(src)
    TA, NOTES, CHK, walk, info_only = read_bundles(paths)
    unknown = {t for v in TA.values() for t in (v[1] or [])} - set(T.TAGS)
    if unknown:
        raise SystemExit('เจอแท็กที่ยังไม่รู้จัก %s — เพิ่มลง TAGS ใน mk_tnfu.py ก่อน' % sorted(unknown))
    if not walk:
        raise SystemExit('ไฟล์ดิบไม่มีเวลาที่ดึง (meta.walkAt / meta.pulled)')
    st1 = iso_utc(walk)
    if st1 <= st0:
        raise SystemExit('ไฟล์ดิบเก่ากว่ารอบที่อยู่ในแดชบอร์ด (%s ≤ %s)' % (thai(st1), thai(st0)))
    ms0 = st0.timestamp() * 1000

    prev = {r[0]: r for r in old['rooms']}
    old_uni = {cid for cid, u in U.items() if existed_at(u, st0)}
    out, g = [], collections.Counter()
    trans = collections.Counter()               # (กลุ่มเดิม, กลุ่มใหม่)
    fb_tag = unk_note = 0
    bump = collections.Counter()                # ทดสอบว่า LINE ขยับ updatedAt เมื่อเขียนโน้ต / เปลี่ยนแท็กไหม
    for cid in sorted(U):
        u, p = U[cid], prev.get(cid)
        ta = TA.get(cid)
        if ta:
            tags = {T.TAGS[t] for t in (ta[1] or [])}
            own = C.OWN.get(ta[4]) if len(ta) > 4 and ta[4] else None
        else:
            tags, own = set(p[4] if p else u['tg']), None
            fb_tag += 1
        tags = sorted(tags - set(T.SKIP_TAGS))
        has_tag = any(t in T.STATUS for t in tags)
        nd = nt = ''
        if cid in CHK:
            ns = sorted(NOTES.get(cid, {}).values(), key=lambda n: n[2], reverse=True)
            has_note = bool(ns)
            if ns:
                nd = thai(datetime.datetime.fromtimestamp(ns[0][2] / 1000, UTC)).strftime('%Y-%m-%d')
                nt = T.clean(ns[0][4])
                if ns[0][2] > ms0 and ta and ta[3]:
                    bump['note_new'] += 1
                    bump['note_new_act_after'] += ta[3] >= ns[0][2]
        elif p:
            has_note = p[5] == 'xN'
            nd, nt = p[6], p[7]
        elif cid in old_uni:
            has_note = True                     # อยู่ในรอบเดิมแต่ไม่อยู่ในรายการ = ตอนนั้นครบแล้ว
        else:
            has_note = False
            unk_note += 1
        if p and ta and ta[2] and set(p[4]) != set(tags):
            bump['tag_changed'] += 1
            bump['tag_changed_upd_after'] += ta[2] >= ms0
        grp = ('T' if has_tag else 'x') + ('N' if has_note else 'x')
        g[grp] += 1
        old_g = p[5] if p else ('TN' if cid in old_uni else 'new')
        trans[(old_g, grp)] += 1
        if grp == 'TN':
            continue
        if grp != 'xN':
            nd = nt = ''
        out.append([cid, u['name'] or (ta[0] if ta else ''), own or u['own'], u['mo'], tags, grp, nd, nt])

    rep = dict(old_stamp=thai(st0).strftime('%Y-%m-%d %H:%M'), new_stamp=thai(st1).strftime('%Y-%m-%d %H:%M'),
               year=year, tot_old=old.get('tot'), uni_old_rebuilt=len(old_uni), tot=len(U),
               todo_old=len(old['rooms']), todo=len(out), groups=dict(g),
               old_groups=dict(collections.Counter(r[5] for r in old['rooms'])),
               trans={'%s→%s' % k: v for k, v in sorted(trans.items())},
               tags_fresh=len(U) - fb_tag, tags_fallback=fb_tag, notes_checked=len(CHK & set(U)),
               new_unchecked=unk_note, old_format_bundles=info_only, bump=dict(bump),
               dropped=len(set(prev) - set(U)))
    if verbose:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
    if not dry:
        A['tnfu'] = dict(stamp=rep['new_stamp'], stampUtc=st1.isoformat().replace('+00:00', 'Z'), rooms=out,
                         tot=len(U), done=g['TN'], status=list(T.STATUS))
        json.dump(A, open(aggp, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
        if verbose:
            print('เขียน agg.tnfu แล้ว · ณ', rep['new_stamp'])
    return rep


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if x != '--dry']
    if a and a[0] == '--todo':
        todo(a[1], a[2] if len(a) > 2 else None)
    else:
        main(a[0], a[1:], dry='--dry' in sys.argv)

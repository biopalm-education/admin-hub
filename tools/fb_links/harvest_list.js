// เก็บรหัสห้องแชท FB ทั้งเดือนจากรายการใน Business Suite (วิธีใหม่ 24 ก.ย. 2026 — ใช้ได้จริง 10,024 ห้องในรอบเดียว)
// วางใน javascript_tool ที่แท็บ https://business.facebook.com/latest/inbox/messenger?asset_id=691470034208676&business_id=310165158296126&mailbox_id=691470034208676
//
// ทำไมรอบก่อน ๆ ได้แค่ 74 / 8 ห้อง: ไม่ได้โดน Facebook จำกัด — การเลื่อนหน้าจอ (scrollTop) ไม่ทำให้รายการสั่งโหลดเพิ่ม
// รายการแชทมาทาง websocket (gateway.facebook.com/ws/realtime) ไม่ใช่ GraphQL/HTTP
// วิธีที่ใช้ได้: เรียก props.onRequestMoreRows() ของ component BizInboxThreadListLayout ตรง ๆ แล้วอ่าน props.threadList
// (ไม่ต้องพึ่ง DOM เลย ห้องที่ไม่ได้ render ก็อ่านได้) — บางช่วง canLoadMoreRows=false สักครู่ระหว่างรอ sync แล้วจะกลับมาเอง
//
// ใช้: 1) รันไฟล์นี้  2) BGSTART('2026-06-30T17:00:00Z')  (= 1 ก.ค. 00:00 เวลาไทย, หยุดเองเมื่อห้องเก่าสุดเก่ากว่านี้)
//      3) เช็ก BGSTAT() เป็นระยะ  4) BGEXPORT('fb_threads_2026-07.json') -> ไฟล์ลง Downloads -> ผู้ใช้ลากขึ้น Drive
// ห้ามพึ่ง localStorage (Facebook ล้างคีย์แปลกปลอม) · ห้าม fiber walk แบบ recursive · ความเร็วตั้งไว้ 2.5 วิ/ครั้ง (ผู้ใช้กังวลเรื่องโดนจำกัด)
window.TL = window.TL || {};
window.hScroller = function () {
  if (window.HSC && document.contains(window.HSC)) return window.HSC;
  const info = el => { const k = Object.keys(el).find(k => k.startsWith('__reactFiber')); if (!k) return null; let f = el[k];
    for (let i = 0; i < 25 && f; i++) { const p = f.memoizedProps; if (p && p.thread && p.thread.threadFBID) return 1; f = f.return; } return null; };
  const scs = [...document.querySelectorAll('div')].filter(e => { const cs = getComputedStyle(e);
    return (cs.overflowY === 'auto' || cs.overflowY === 'scroll') && e.scrollHeight > e.clientHeight + 50; });
  let best = null, bd = 1e9;
  for (const sc of scs) { const kids = sc.querySelectorAll('div'); if (kids.length > 4000) continue;
    let hit = 0; for (let i = 0; i < kids.length && hit < 2; i++) { if (info(kids[i])) hit++; }
    if (hit >= 2 && kids.length < bd) { best = sc; bd = kids.length; } }
  window.HSC = best; return best; };
window.listProps = function () {            // scroller -> 7 fibers up = BizInboxThreadListLayout (มี threadList/onRequestMoreRows)
  const sc = hScroller(); const k = Object.keys(sc).find(k => k.startsWith('__reactFiber')); let f = sc[k];
  for (let i = 0; i < 12 && f; i++) { const p = f.memoizedProps; if (p && p.threadList && p.onRequestMoreRows) return p; f = f.return; }
  return null; };
window.absorb = function () { const q = listProps();
  for (const t of q.threadList) if (t && t.threadFBID) TL[t.threadFBID] = [t.title, t.timestamp, t.threadType, t.threadID];
  return q; };
window.BGSTART = function (stopIso, delay) {
  window.BG = { on: true, calls: 0, err: null, delay: delay || 2500, stopAt: Date.parse(stopIso) };
  (async () => { try { while (BG.on) { const q = absorb(); let mn = Infinity;
      for (const v of Object.values(TL)) if (v[1] < mn) mn = v[1];
      BG.oldest = mn; BG.n = Object.keys(TL).length; BG.can = q.canLoadMoreRows;
      if (mn < BG.stopAt) { BG.on = false; BG.done = true; break; }
      if (!q.isLoadingMoreRows) { q.onRequestMoreRows(); BG.calls++; }
      await new Promise(r => setTimeout(r, BG.delay)); } } catch (e) { BG.err = String(e); BG.on = false; } })();
  return 'started'; };
window.BGSTAT = () => ({ on: BG.on, done: BG.done, err: BG.err, n: BG.n, calls: BG.calls,
  oldest: new Date(BG.oldest + 7 * 3600e3).toISOString().slice(0, 16) + ' (ไทย)' });
window.BGEXPORT = function (name) {
  const rows = Object.entries(TL).map(([id, v]) => [id, v[0], v[1], v[2], v[3]]);
  const obj = { generated: new Date().toISOString(), page: '691470034208676', count: rows.length,
    cols: ['threadFBID', 'title', 'timestamp_ms', 'threadType', 'threadID'], rows };
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(obj)], { type: 'application/json' }));
  a.download = name; document.body.appendChild(a); a.click(); a.remove(); return rows.length; };

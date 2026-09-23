// วางใน javascript_tool (แท็บ https://business.facebook.com/latest/inbox/messenger?asset_id=691470034208676)
// 1) รันครั้งแรกเพื่อประกาศฟังก์ชัน  2) เรียก await hRun2(27000) ซ้ำ ๆ (แต่ละครั้ง < 30 วิ)
// 3) ดึงผลออกมาด้วย JSON.stringify(Object.entries(H).map(([id,v])=>[id,v[0],v[1]]))
//    แล้วส่งเข้าชีตจาก workbench ด้วย tools/fb_links/send_links.py — ไม่ต้องเอา token เข้าหน้าเว็บอีกแล้ว
// ห้ามพึ่ง localStorage (Facebook ล้างคีย์แปลกปลอมทิ้ง) · ห้ามเขียน fiber walk แบบ recursive (เบราว์เซอร์ค้าง)
//
// 23 ก.ย. 2026: Facebook เอา role="row" ออกจากแถวรายการแชทแล้ว โค้ดเดิมจึงได้ 0 ห้อง
// ตอนนี้หากล่องเลื่อนด้วยการมองหา React fiber ของ thread แทน (ไม่พึ่ง role/class ที่เปลี่ยนบ่อย)
window.H = window.H || {};
window.hInfo = function (el) {           // bounded fiber walk (ห้าม recursive)
  const k = Object.keys(el).find(k => k.startsWith('__reactFiber')); if (!k) return null;
  let f = el[k];
  for (let i = 0; i < 25 && f; i++) { const p = f.memoizedProps;
    if (p && p.thread && p.thread.threadFBID) { const t = p.thread; return [t.threadFBID, t.title, t.timestamp, t.threadType]; }
    f = f.return; }
  return null; };
window.hScroller = function () {         // กล่องเลื่อนที่ "เล็กที่สุดที่ยังมีแถวแชทอยู่ข้างใน"
  if (window.HSC && document.contains(window.HSC)) return window.HSC;
  const scs = [...document.querySelectorAll('div')].filter(e => { const cs = getComputedStyle(e);
    return (cs.overflowY === 'auto' || cs.overflowY === 'scroll') && e.scrollHeight > e.clientHeight + 50; });
  let best = null, bd = 1e9;
  for (const sc of scs) { const kids = sc.querySelectorAll('div'); if (kids.length > 4000) continue;
    let hit = 0; for (let i = 0; i < kids.length && hit < 2; i++) { if (hInfo(kids[i])) hit++; }
    if (hit >= 2 && kids.length < bd) { best = sc; bd = kids.length; } }
  window.HSC = best; return best; };
window.hGrab = function () { const sc = hScroller(); if (!sc) return 0; let n = 0;
  for (const d of sc.querySelectorAll('div')) { const x = hInfo(d);
    if (x && x[0] && x[3] === 'FB_MESSAGE') { if (!H[x[0]]) n++; H[x[0]] = [x[1], x[2]]; } }
  return n; };
window.hStat = function () { let mn = Infinity, mx = -Infinity;
  for (const v of Object.values(H)) { if (v[1] && v[1] < mn) mn = v[1]; if (v[1] && v[1] > mx) mx = v[1]; }
  return { n: Object.keys(H).length, oldest: isFinite(mn) ? new Date(mn).toISOString() : null,
           newest: isFinite(mx) ? new Date(mx).toISOString() : null }; };
// เลื่อนช้า ๆ ทีละ 420px · พอถึงก้นรายการให้รอโหลด แล้วถอยขึ้นไปเก็บแถวที่เพิ่งโหลด
// (ห้ามกระโดด scrollTop = scrollHeight รวดเดียวตลอด — แถวที่ข้ามไปจะไม่ mount และหายไปเงียบ ๆ)
window.hRun2 = async function (ms) { const sc = hScroller(); if (!sc) return { err: 'no scroller' };
  const t0 = Date.now(); let steps = 0, waits = 0, grew = 0, stalled = 0;
  while (Date.now() - t0 < ms - 3000) { hGrab();
    if (sc.scrollTop + sc.clientHeight >= sc.scrollHeight - 60) {
      const sh0 = sc.scrollHeight; sc.scrollTop = sc.scrollHeight;
      await new Promise(r => setTimeout(r, 2200)); waits++;
      if (sc.scrollHeight > sh0) { grew++; stalled = 0; sc.scrollTop = Math.max(0, sh0 - sc.clientHeight - 150); }
      else { stalled++; if (stalled >= 5) break; }
    } else { sc.scrollTop += 420; steps++; await new Promise(r => setTimeout(r, 800)); } }
  hGrab(); const s = hStat(); s.steps = steps; s.waits = waits; s.grew = grew; s.stalled = stalled;
  s.sh = sc.scrollHeight; return s; };

// วางใน javascript_tool (แท็บ https://business.facebook.com/latest/inbox/messenger?asset_id=691470034208676)
// 1) รันครั้งแรกเพื่อประกาศฟังก์ชัน  2) เรียก await hRun(25000) ซ้ำ ๆ (แต่ละครั้ง < 30 วิ)  3) hFlush() ส่งเข้าชีต
// ต้องตั้ง window.OVURL และ window.OVTOK ก่อน (ค่าจาก agg.ovurl และ token) — อย่า commit ค่าจริงลง repo
window.H = window.H || {}; window.HSENT = window.HSENT || {};
window.hInfo = function (el) {           // bounded fiber walk (ห้าม recursive)
  const k = Object.keys(el).find(k => k.startsWith('__reactFiber')); if (!k) return null;
  let f = el[k];
  for (let i = 0; i < 25 && f; i++) { const p = f.memoizedProps;
    if (p && p.thread && p.thread.threadFBID) { const t = p.thread; return [t.threadFBID, t.title, t.timestamp, t.threadType]; }
    f = f.return; }
  return null; };
window.hScroller = function () { let e = document.querySelector('[role="row"]');
  while (e && e !== document.body) { const cs = getComputedStyle(e);
    if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll') && e.scrollHeight > e.clientHeight + 50) return e; e = e.parentElement; }
  return null; };
window.hGrab = function () { for (const r of document.querySelectorAll('[role="row"]')) { const x = hInfo(r);
  if (x && x[3] === 'FB_MESSAGE') H[x[0]] = [x[1], x[2]]; } };
window.hFlush = function () {            // ส่งเฉพาะห้องที่ยังไม่เคยส่ง ผ่าน form POST (fetch โดน CSP)
  const rows = Object.entries(H).filter(([id]) => !HSENT[id]).map(([id, v]) => [id, v[0], v[1]]);
  if (!rows.length) return 0;
  const n = 'bpx' + Date.now(); const ifr = document.createElement('iframe'); ifr.name = n; ifr.style.display = 'none'; document.body.appendChild(ifr);
  const f = document.createElement('form'); f.method = 'POST'; f.action = OVURL; f.target = n;
  const i = document.createElement('input'); i.type = 'hidden'; i.name = 'p';
  i.value = JSON.stringify({ t: OVTOK, act: 'links', by: 'Claude', rows }); f.appendChild(i); document.body.appendChild(f); f.submit();
  setTimeout(() => { f.remove(); ifr.remove(); }, 15000);
  for (const r of rows) HSENT[r[0]] = 1; return rows.length; };
window.hRun = async function (ms) { const sc = hScroller(); const t0 = Date.now(); let steps = 0, stuck = 0;
  while (Date.now() - t0 < ms) { hGrab(); const before = sc.scrollTop; sc.scrollTop += 450; steps++;
    await new Promise(r => setTimeout(r, 900));
    if (sc.scrollTop === before) { stuck++; await new Promise(r => setTimeout(r, 2500)); if (stuck > 8) break; } else stuck = 0; }
  hGrab(); const unsent = Object.keys(H).filter(id => !HSENT[id]).length; const sent = unsent >= 150 ? hFlush() : 0;
  let mn = Infinity; for (const v of Object.values(H)) if (v[1] && v[1] < mn) mn = v[1];
  return { n: Object.keys(H).length, sent, steps, stuck, oldest: new Date(mn).toISOString() }; };

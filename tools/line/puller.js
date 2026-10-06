// LINE OA puller — paste into the browser pane on https://chat.line.biz (logged in as Biopalm admin).
// Usage (month round):  await LINEPULL.start({from:'2026-09-01', to:'2026-10-01', db:'lp_2026_09_20261005', notesFor:[...]})
//                        dates = Thai-time month bounds, to = exclusive · notesFor = optional room-id prefixes from
//                        `python3 tools/line/tn_update.py --todo src` (rooms still on the tag/note list — notes only)
// Usage (tag/note only): await LINEPULL.start({mode:'tn', from:'<วันที่ของรอบแท็ก/โน้ตก่อน YYYY-MM-DD>', db:'lp_tn_20261006', notesFor:[...]})
//                        no messages at all: walks the list (tags of EVERY room) + notes of the listed rooms and of
//                        every room active since `from`
//        LINEPULL.status()   ·  LINEPULL.stop()   ·  await LINEPULL.bundle()  -> downloads line_<label>_raw.json.gz
// Every run also keeps the current tags of EVERY 1:1 room seen while walking the list (bundle.tagall), so the
// "ติดแท็ก / ใส่โน้ต ให้ครบ" list can be refreshed for old rooms that had no chat this month.
// Only touches bot U38b62d24ef14a84a048cd6633fc15d21. GET only, strictly serial, jitter 1.2–3.0s,
// 20–45s break every 170–250 requests, 90–150s break every 900, 60s back-off on 429/5xx, stops on 401/403.
(() => {
const BOT='U38b62d24ef14a84a048cd6633fc15d21';
const th=d=>{const [y,m,dd]=d.split('-').map(Number); return Date.UTC(y,m-1,dd)-7*3600e3;};
const sleep=ms=>new Promise(r=>setTimeout(r,ms)); const rnd=(a,b)=>a+Math.random()*(b-a);
const L=window.LINEPULL={running:false,st:{req:0,phase:'idle',cands:0,done:0,rows:0,notes:0,notesRooms:0,pages:0,tagall:0,xcands:0,errors:[],r429:0},log:[]};
let db, sinceBreak=0,nextBreak=170,sinceLong=0;
const STORES=['meta','rows','notes','xnotes'];
const open=n=>new Promise((res,rej)=>{const q=indexedDB.open(n,2); q.onupgradeneeded=()=>{const d=q.result; STORES.forEach(s=>{if(!d.objectStoreNames.contains(s)) d.createObjectStore(s)})}; q.onsuccess=()=>res(q.result); q.onerror=()=>rej(q.error)});
const put=(s,k,v)=>new Promise((res,rej)=>{const t=db.transaction(s,'readwrite'); t.objectStore(s).put(v,k); t.oncomplete=()=>res(); t.onerror=()=>rej(t.error)});
const get=(s,k)=>new Promise(res=>{const q=db.transaction(s).objectStore(s).get(k); q.onsuccess=()=>res(q.result);});
const all=s=>new Promise(res=>{const o={}; const q=db.transaction(s).objectStore(s).openCursor(); q.onsuccess=e=>{const c=e.target.result; if(c){o[c.key]=c.value;c.continue();} else res(o);};});
const log=m=>{L.log.push(new Date().toLocaleTimeString('th-TH')+' '+m); if(L.log.length>40)L.log.shift();};
async function req(url){ if(L.stopFlag) throw new Error('STOPPED');
  await sleep(rnd(1200,3000));
  if(sinceBreak>=nextBreak){const w=rnd(20000,45000); log('break '+Math.round(w/1000)+'s'); await sleep(w); sinceBreak=0; nextBreak=Math.floor(rnd(170,250));}
  if(sinceLong>=900){const w=rnd(90000,150000); log('long break'); await sleep(w); sinceLong=0;}
  for(let a=0;a<4;a++){ let r; try{ r=await fetch(url,{credentials:'include'}); }catch(e){ r={status:0}; }
    L.st.req++; sinceBreak++; sinceLong++;
    if(r.status===200){ try{ return JSON.parse(await r.text()); }catch(e){ L.st.errors.push('badjson'); await sleep(10000); continue; } }
    if(r.status===401||r.status===403){ L.st.errors.push(String(r.status)); throw new Error('AUTH '+r.status); }
    if(r.status===404) return null;
    if(r.status===429) L.st.r429++; L.st.errors.push(String(r.status)); await sleep(60000); }
  throw new Error('FAILED '+url.slice(-60)); }
const mapEv=e=>{const m=e.message||{}; const t=e.type; const tx=m.type==='text'?(m.text||''):(m.altText||'');
  if(t==='message') return [e.timestamp,'c',null,m.type||'',tx]; if(t==='messageSent') return [e.timestamp,'a',e.bizId||null,m.type||'',tx];
  if(t==='postback') return [e.timestamp,'p',null,'postback','']; if(t==='follow') return [e.timestamp,'f',null,'follow','']; if(t==='unfollow') return [e.timestamp,'u',null,'unfollow','']; return null;};
async function run(){ L.running=true; L.stopFlag=false; const {FROM,TO,MODE,PFX,PL}=L;
 try{
  // 1) walk the WHOLE chat list: LINE sorts by updatedAt, which can lag real activity, so never stop early.
  //    Every 1:1 room's current tags go into tagall (no extra requests — they come with the list).
  //    cand.x=1 → room is here only because it is on the tag/note list (notesFor): notes only, no messages.
  let cands=await get('meta','cands');
  if(!(await get('meta','listdone'))){ L.st.phase='walk'; cands=cands||[]; const seen=new Set(cands.map(c=>c.id)); let cur=await get('meta','listcur')||null;
    const TA=(await get('meta','tagall'))||{};
    while(true){ const j=await req(`/api/v2/bots/${BOT}/chats?folderType=ALL&tagIds=&autoTagIds=&limit=25&prioritizePinnedChat=true`+(cur?`&next=${encodeURIComponent(cur)}`:'')); const list=(j&&j.list)||[]; L.st.pages++;
      for(const c of list){ if(c.chatType==='GROUP') continue; const act=Math.max(c.lastTalkedAt||0,c.lastReceivedAt||0,c.lastSentAt||0,c.updatedAt||0);
        TA[c.chatId]=[(c.profile&&c.profile.name)||'',c.tagIds||[],c.updatedAt||0,act,c.assignedBizId||null];
        const inWin=act>=FROM, onList=PL>0&&PFX.has(c.chatId.slice(0,PL));
        if((inWin||onList)&&!seen.has(c.chatId)){ seen.add(c.chatId); cands.push({id:c.chatId,nm:(c.profile&&c.profile.name)||'',ct:c.chatType||'USER',tg:c.tagIds||[],at:c.autoTagIds||[],as:c.assignedBizId||null,lt:c.lastTalkedAt||c.updatedAt||0,act,x:inWin?0:1}); } }
      L.st.cands=cands.length; L.st.tagall=Object.keys(TA).length; cur=j&&j.next;
      await put('meta','cands',cands); await put('meta','tagall',TA); await put('meta','listcur',cur||''); if(!cur) break; }
    await put('meta','walkAt',new Date().toISOString()); await put('meta','listdone',true); log('walk done '+cands.length+' · tags '+Object.keys(TA).length); }
  L.cands=cands; L.st.cands=cands.length; L.st.xcands=cands.filter(c=>c.x).length; L.st.phase='pull';
  // 2) per room: messages back to FROM (month mode, rooms in the window), then ALL notes of the room
  const done=new Set(await get('meta','done')||[]);
  for(const c of cands){ if(done.has(c.id)) continue;
    if(MODE!=='tn'&&!c.x){ let back=null,oldest=Infinity,full=false,pages=0; const ev=[];
      while(true){ const j=await req(`/api/v3/bots/${BOT}/chats/${c.id}/messages`+(back?`?backward=${encodeURIComponent(back)}`:'')); pages++; const list=(j&&j.list)||[];
        for(const e of list){ if(e.timestamp<oldest) oldest=e.timestamp; if(e.timestamp>=FROM&&e.timestamp<TO){ const x=mapEv(e); if(x) ev.push(x);} }
        back=j&&j.backward; if(!back||!list.length){full=true;break;} if(oldest<FROM) break; }
      if(ev.length){ ev.sort((a,b)=>a[0]-b[0]); await put('rows',c.id,{...c,pages,oldest,full,ev}); L.st.rows++; } }
    const nj=await req(`/api/v1/bots/${BOT}/chats/${c.id}/notes?limit=100&withTotal=true`); const nl=(nj&&nj.list)||[];
    // notes of list-only rooms go to xnotes, so month registration counts (line_month.py reads `notes`) stay as before
    if(nl.length){ await put(c.x?'xnotes':'notes',c.id,nl.map(n=>[n.noteId,n.userBizId||null,n.createdAt,n.updatedAt,n.body||''])); L.st.notesRooms++; L.st.notes+=nl.length; }
    done.add(c.id); L.st.done=done.size; await put('meta','done',[...done]); }
  L.st.phase='finished'; log('finished');
 }catch(e){ L.st.phase='stopped: '+e.message; log('stop '+e.message); }
 L.running=false; }
L.start=async(o)=>{ if(L.running) return 'already running';
  L.MODE=o.mode==='tn'?'tn':'month'; L.FROM=th(o.from); L.TO=o.to?th(o.to):Date.now()+864e5;
  const nf=(o.notesFor||[]).map(String).filter(Boolean); L.PL=nf.length?Math.min(...nf.map(s=>s.length)):0; L.PFX=new Set(nf.map(s=>s.slice(0,L.PL)));
  L.label=L.MODE==='tn'?'tn_'+new Date(Date.now()+7*3600e3).toISOString().slice(0,10):o.from.slice(0,7);
  db=await open(o.db||('lp_'+L.label.replace(/-/g,'_')));
  if(L.wd) clearInterval(L.wd); L.restarts=0; L.wd=setInterval(()=>{const p=L.st.phase||''; if(!L.running&&p.startsWith('stopped')&&!/AUTH|STOPPED/.test(p)&&L.restarts<20){L.restarts++; run();}},90000);
  run(); return 'started '+L.MODE+' · notesFor '+L.PFX.size; };
L.stop=()=>{L.stopFlag=true; if(L.wd) clearInterval(L.wd); return 'stopping';};
L.status=()=>({...L.st,errors:L.st.errors.slice(-3),running:L.running,log:L.log.slice(-3),now:new Date().toLocaleTimeString('th-TH')});
L.bundle=async()=>{ const rows=Object.values(await all('rows')); const notes=await all('notes'); const xnotes=await all('xnotes'); const info={};
  (L.cands||[]).filter(c=>!c.x).forEach(c=>info[c.id]=[c.nm,c.tg,c.lt]);
  const tagall=(await get('meta','tagall'))||{}, walkAt=(await get('meta','walkAt'))||null, checked=(await get('meta','done'))||[];
  const b={month:L.MODE==='tn'?null:L.label, mode:L.MODE, from:L.FROM, to:L.TO, bot:BOT, raw:rows, notes, xnotes, info, tagall, checked,
    meta:{pulled:new Date().toISOString(), walkAt, notesFor:L.PFX?L.PFX.size:0, ...L.st}};
  const gz=await new Response(new Blob([JSON.stringify(b)]).stream().pipeThrough(new CompressionStream('gzip'))).blob();
  const a=document.createElement('a'); a.href=URL.createObjectURL(gz); a.download='line_'+L.label+'_raw.json.gz'; document.body.appendChild(a); a.click(); a.remove();
  return {mode:L.MODE, rooms:rows.length, notesRooms:Object.keys(notes).length+Object.keys(xnotes).length, checked:checked.length, tagall:Object.keys(tagall).length, kb:Math.round(gz.size/1024)}; };
})();

// LINE OA puller — paste into the browser pane on https://chat.line.biz (logged in as Biopalm admin).
// Usage: await LINEPULL.start({from:'2026-09-01', to:'2026-10-01', db:'lp_2026_09'})  (dates = Thai-time month bounds, to = exclusive)
//        LINEPULL.status()   ·  LINEPULL.stop()   ·  await LINEPULL.bundle()  -> downloads line_<from>_bundle.json.gz
// Only touches bot U38b62d24ef14a84a048cd6633fc15d21. GET only, strictly serial, jitter 1.2–3.0s,
// 20–45s break every 170–250 requests, 90–150s break every 900, 60s back-off on 429/5xx, stops on 401/403.
(() => {
const BOT='U38b62d24ef14a84a048cd6633fc15d21';
const th=d=>{const [y,m,dd]=d.split('-').map(Number); return Date.UTC(y,m-1,dd)-7*3600e3;};
const sleep=ms=>new Promise(r=>setTimeout(r,ms)); const rnd=(a,b)=>a+Math.random()*(b-a);
const L=window.LINEPULL={running:false,st:{req:0,phase:'idle',cands:0,done:0,rows:0,notes:0,notesRooms:0,pages:0,errors:[],r429:0},log:[]};
let db, sinceBreak=0,nextBreak=170,sinceLong=0;
const open=n=>new Promise((res,rej)=>{const q=indexedDB.open(n,1); q.onupgradeneeded=()=>{const d=q.result; ['meta','rows','notes'].forEach(s=>{if(!d.objectStoreNames.contains(s)) d.createObjectStore(s)})}; q.onsuccess=()=>res(q.result); q.onerror=()=>rej(q.error)});
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
async function run(){ L.running=true; L.stopFlag=false; const {FROM,TO}=L;
 try{
  // 1) walk the WHOLE chat list: LINE sorts by updatedAt, which can lag real activity, so never stop early
  let cands=await get('meta','cands');
  if(!(await get('meta','listdone'))){ L.st.phase='walk'; cands=cands||[]; const seen=new Set(cands.map(c=>c.id)); let cur=await get('meta','listcur')||null;
    while(true){ const j=await req(`/api/v2/bots/${BOT}/chats?folderType=ALL&tagIds=&autoTagIds=&limit=25&prioritizePinnedChat=true`+(cur?`&next=${encodeURIComponent(cur)}`:'')); const list=(j&&j.list)||[]; L.st.pages++;
      for(const c of list){ const act=Math.max(c.lastTalkedAt||0,c.lastReceivedAt||0,c.lastSentAt||0,c.updatedAt||0);
        if(act>=FROM&&!seen.has(c.chatId)&&c.chatType!=='GROUP'){ seen.add(c.chatId); cands.push({id:c.chatId,nm:(c.profile&&c.profile.name)||'',ct:c.chatType||'USER',tg:c.tagIds||[],at:c.autoTagIds||[],as:c.assignedBizId||null,lt:c.lastTalkedAt||c.updatedAt||0,act}); } }
      L.st.cands=cands.length; cur=j&&j.next; await put('meta','cands',cands); await put('meta','listcur',cur||''); if(!cur) break; }
    await put('meta','listdone',true); log('walk done '+cands.length); }
  L.cands=cands; L.st.cands=cands.length; L.st.phase='pull';
  // 2) per room: messages back to FROM, then ALL notes of the room (notes carry createdAt, split by month later)
  const done=new Set(await get('meta','done')||[]);
  for(const c of cands){ if(done.has(c.id)) continue; let back=null,oldest=Infinity,full=false,pages=0; const ev=[];
    while(true){ const j=await req(`/api/v3/bots/${BOT}/chats/${c.id}/messages`+(back?`?backward=${encodeURIComponent(back)}`:'')); pages++; const list=(j&&j.list)||[];
      for(const e of list){ if(e.timestamp<oldest) oldest=e.timestamp; if(e.timestamp>=FROM&&e.timestamp<TO){ const x=mapEv(e); if(x) ev.push(x);} }
      back=j&&j.backward; if(!back||!list.length){full=true;break;} if(oldest<FROM) break; }
    if(ev.length){ ev.sort((a,b)=>a[0]-b[0]); await put('rows',c.id,{...c,pages,oldest,full,ev}); L.st.rows++; }
    const nj=await req(`/api/v1/bots/${BOT}/chats/${c.id}/notes?limit=100&withTotal=true`); const nl=(nj&&nj.list)||[];
    if(nl.length){ await put('notes',c.id,nl.map(n=>[n.noteId,n.userBizId||null,n.createdAt,n.updatedAt,n.body||''])); L.st.notesRooms++; L.st.notes+=nl.length; }
    done.add(c.id); L.st.done=done.size; await put('meta','done',[...done]); }
  L.st.phase='finished'; log('finished');
 }catch(e){ L.st.phase='stopped: '+e.message; log('stop '+e.message); }
 L.running=false; }
L.start=async(o)=>{ if(L.running) return 'already running'; L.FROM=th(o.from); L.TO=th(o.to); L.label=o.from.slice(0,7); db=await open(o.db||('lp_'+o.from.slice(0,7).replace('-','_')));
  if(L.wd) clearInterval(L.wd); L.restarts=0; L.wd=setInterval(()=>{const p=L.st.phase||''; if(!L.running&&p.startsWith('stopped')&&!/AUTH|STOPPED/.test(p)&&L.restarts<20){L.restarts++; run();}},90000);
  run(); return 'started'; };
L.stop=()=>{L.stopFlag=true; if(L.wd) clearInterval(L.wd); return 'stopping';};
L.status=()=>({...L.st,errors:L.st.errors.slice(-3),running:L.running,log:L.log.slice(-3),now:new Date().toLocaleTimeString('th-TH')});
L.bundle=async()=>{ const rows=Object.values(await all('rows')); const notes=await all('notes'); const info={}; (L.cands||[]).forEach(c=>info[c.id]=[c.nm,c.tg,c.lt]);
  const b={month:L.label, from:L.FROM, to:L.TO, bot:BOT, raw:rows, notes, info, meta:{pulled:new Date().toISOString(), ...L.st}};
  const gz=await new Response(new Blob([JSON.stringify(b)]).stream().pipeThrough(new CompressionStream('gzip'))).blob();
  const a=document.createElement('a'); a.href=URL.createObjectURL(gz); a.download='line_'+L.label+'_raw.json.gz'; document.body.appendChild(a); a.click(); a.remove();
  return {rooms:rows.length, notesRooms:Object.keys(notes).length, kb:Math.round(gz.size/1024)}; };
})();

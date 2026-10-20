/* ---------- Before / After (preview 20 ต.ค. 2026) — data: build_week.py -> FU.wk (weeks; v2 adds months) ----------
   One page for all channels or one channel: how many chats were waiting on the 5 Follow up lists at the start of a
   week / month (before), what admins did with them, and how many were still waiting at the end (after).
   Rows, buckets and "แอดมินจัดการ" are the weekly box's (wk.js: wkBucket / wkCount) — this page adds channels together,
   months, the trend, and the source list (every chat behind every number). Needs wk.js in the same page. */
let BA_P=(()=>{try{return localStorage.getItem('bp_ba_p')==='m'?'m':'w';}catch(e){return 'w';}})();
let BA_K='', BA_L='', BA_B='', BA_C='', BA_Q='', BA_AGE='', BA_PG=0, BA_TL='', BA_C1=null, BA_C2=null;
const BA_CH=['fb','ig','line'], BA_CHN={fb:'Facebook',ig:'Instagram',line:'LINE OA'}, BA_CHI={fb:'🔵',ig:'🟣',line:'🟢'};
const BA_CHC={fb:'var(--fb)',ig:'var(--ig)',line:'var(--ln)'};
const BA_BK=['done','act','cus','none','skip','aged'];
const BA_BN={S:'ค้างต้นช่วง',N:'เข้าใหม่ระหว่างช่วง',E:'ค้างปลายช่วง',done:'✅ เคลียร์แล้ว',act:'✋ ตอบ/ตามแล้ว',cus:'💬 ลูกค้าทักกลับ รอตอบ',none:'⏳ ยังไม่มีใครแตะ',skip:'ระบบคัดออก',aged:'หมดอายุ (เกิน 90 วัน)'};
const BA_BS={done:'เคลียร์แล้ว',act:'ตอบ/ตามแล้ว',cus:'ลูกค้าทักกลับ รอตอบ',none:'ยังไม่มีใครแตะ',skip:'ระบบคัดออก',aged:'หมดอายุ'};
const BA_ORD={cus:0,none:1,act:2,done:3,skip:4,aged:5};
const BA_PS=50;
function baOn(){return !!(FU&&FU.wk&&FU.wk.rows&&FU.wk.weeks);}
function baChs(){return (CH==='all'?BA_CH:[CH]).filter(c=>((FU.wk.weeks||{})[c]||[]).length);}
const baPK=()=>BA_P==='m'?'months':'weeks', baRK=()=>BA_P==='m'?'mrows':'rows';
function baHasM(){return !!(FU.wk.months&&BA_CH.some(c=>(FU.wk.months[c]||[]).length));}
function baHasAge(){for(const c of BA_CH){const R=(FU.wk.rows||{})[c];if(!R)continue;for(const l in R)for(const w of R[l])if(w.length)return w[0].length>6;}return false;}
/* periods of every channel in scope, by start. A period before a channel's first one is dropped (LINE's weeks start a
   week earlier than Facebook's when its data stops mid-week — a LINE-only week would look like a crash in the totals);
   a period after a channel's data stops is kept and says so. */
function baPeriods(){const m={},src=FU.wk[baPK()]||{},chs=baChs(),first={};
 for(const c of chs){const W=src[c]||[];if(W.length)first[c]=W[0][0];W.forEach((w,i)=>{(m[w[0]]=m[w[0]]||{k:w[0],per:{}}).per[c]={i,w};});}
 return Object.keys(m).sort().filter(k=>chs.every(c=>m[k].per[c]||!first[c]||k>first[c])).map(k=>m[k]);}
const baMiss=p=>baChs().filter(c=>!p.per[c]);
const baFull=p=>Object.keys(p.per).some(c=>p.per[c].w[2]);
function baEndOf(p){let e='';for(const c in p.per)if(p.per[c].w[1]>e)e=p.per[c].w[1];return e;}
function baCur(p){return !baFull(p)&&(Date.now()-wkT(p.k).getTime())<(BA_P==='w'?7:31)*864e5;}
function baLab(p){if(BA_P==='w')return wkLab([p.k,baEndOf(p),baFull(p)?1:0]);const d=wkT(p.k);return FU_TH_M[d.getMonth()]+' '+d.getFullYear();}
function baPre(p){return baFull(p)?'':(baCur(p)?(BA_P==='w'?'สัปดาห์นี้ · ':'เดือนนี้ · '):'ข้อมูลไม่ครบ · ');}
function baLong(p){const e=baEndOf(p);return baPre(p)+(BA_P==='w'?'สัปดาห์ '+baLab(p):baLab(p))+(baFull(p)?'':' (ถึง '+fuDay(e)+' '+e.slice(11,16)+' น.)');}
function baSel(P){if(!P.length)return null;let p=P.find(x=>x.k===BA_K);if(p)return p;
 for(let i=P.length-1;i>=0;i--)if(baFull(P[i])){p=P[i];break;}p=p||P[P.length-1];BA_K=p.k;return p;}
const baPrev=(P,p)=>{const i=P.indexOf(p);return i>0?P[i-1]:null;};
const BA_U=()=>BA_P==='w'?'สัปดาห์':'เดือน';
/* a button pressed after the build, while the chat was listed in the period -> act (as wkLiveMan, for any channel) */
function baLive(ch,tid,w){const L=wkOvIndex()[ch+'|'+tid];if(!L)return null;const built=wkT(FU.wk.built||'2000-01-01 00:00'),s=wkT(w[0]),e=w[2]?wkT(w[1]):new Date(8.64e15);
 for(let i=L.length-1;i>=0;i--){const x=L[i],at=new Date(x[6]);if(isNaN(at)||at<=built||at<=s||at>e)continue;if(x[3]==='skip')return {by:x[5]||'',why:x[4]||''};return null;}return null;}
function baRows(ch,lst,i){const w=((FU.wk[baPK()]||{})[ch]||[])[i],R=((((FU.wk[baRK()]||{})[ch]||{})[lst])||[])[i]||[],ids=FU.wk.ids[ch]||[];
 const out=[];for(const r of R){const id=ids[r[0]]||['','',''];
  const o={ch,lst,tid:id[0],name:id[1],owner:id[2],fl:r[1],out:r[2],sub:r[3],who:(r[4]||[]).slice(),man:r[5]||'',age:r.length>6?r[6]:null};
  if(!o.man&&w){const lm=baLive(ch,o.tid,w);if(lm){o.man='act';o.live=1;if(lm.by&&!o.who.includes(lm.by))o.who.push(lm.by);}}
  if(BA_AGE&&o.age!=null&&o.age>=0&&(BA_AGE==='y'?o.age>=30:o.age<30))continue;
  o.b=wkBucket(o);out.push(o);}
 return out;}
/* every row of one period, per list per channel (cached: the page re-renders on every click) */
function baGet(p){const key=[CH,BA_P,BA_AGE,p.k,OVROWS.length,FU.wk.built].join('|');if(BA_C1&&BA_C1.key===key)return BA_C1.v;
 const v={by:{},all:[]};for(const L of WK_L){v.by[L[0]]={};for(const c in p.per){const rs=baRows(c,L[0],p.per[c].i);v.by[L[0]][c]=rs;for(const o of rs)v.all.push(o);}}
 /* a chat that left one list as "done" and entered another list in the same period = moved a step, not a new chat */
 const dn={};for(const o of v.all)if(o.b==='done'){const k=o.ch+'|'+o.tid;(dn[k]=dn[k]||new Set()).add(o.lst);}
 v.mv=0;for(const o of v.all){if(!(o.fl&8))continue;const s=dn[o.ch+'|'+o.tid];if(s&&[...s].some(l=>l!==o.lst))v.mv++;}
 BA_C1={key,v};return v;}
function baTrend(P){const key=[CH,BA_P,BA_AGE,OVROWS.length,FU.wk.built,P.length].join('|');if(BA_C2&&BA_C2.key===key)return BA_C2.v;
 const v=P.map(p=>{const t={},all=[];for(const L of WK_L){const rs=[];for(const c in p.per)for(const o of baRows(c,L[0],p.per[c].i)){rs.push(o);all.push(o);}t[L[0]]=wkCount(rs);}
  t.all=wkCount(all);return t;});
 BA_C2={key,v};return v;}
const BA_SHORT={ar:'บอทตอบ ไม่มีแอดมินตอบ',sp:'ยังไม่แนบตัวอย่าง',np:'แนบตัวอย่างแล้ว ยังไม่สรุปจ่าย',pay:'แนบตัวอย่าง+สรุปจ่ายแล้ว ยังไม่โอน',pz:'สรุปจ่ายแล้ว (ไม่แนบตัวอย่าง) ยังไม่โอน'};
const BA_TINY={ar:'บอทตอบ',sp:'ยังไม่แนบตัวอย่าง',np:'ยังไม่สรุปจ่าย',pay:'ยังไม่โอน · แนบตัวอย่าง',pz:'ยังไม่โอน · ไม่แนบตัวอย่าง'};
const baSum=rows=>wkCount(rows);
function baD(c,big){const d=c.E-c.S;const cls=d<0?'badown':(d>0?'baup':'baeq');return `<span class="bad0 ${cls}">${d===0?'= เท่าเดิม':(d<0?'▼ '+nf(-d):'▲ '+nf(d))}${big&&c.S&&d?' ('+(d<0?'−':'+')+Math.round(Math.abs(d)*100/c.S)+'%)':''}</span>`;}
const baPk=p=>p==null?'':(p>=60?'ok':(p>=30?'warnc':'bad'));
const baPctTxt=c=>c.pct==null?'—':c.pct+'%';
function baCell(v,lst,b,ch,cls){return `<td class="n${cls?' '+cls:''}">${v?`<button type="button" class="bacell" data-ba="src|${lst}|${b}|${ch||''}" title="ดูรายชื่อแชท">${nf(v)}</button>`:'<span class="mut">0</span>'}</td>`;}
function baRowHTML(lab,c,lst,ch,tot){return `<tr${tot?' class="batot"':''}><td><button type="button" class="balab" data-ba="src|${lst}||${ch||''}" title="ดูรายชื่อแชท">${lab}</button>${wkMini(c)}</td>${baCell(c.S,lst,'S',ch)}${baCell(c.N,lst,'N',ch,'cx mut')}${baCell(c.done,lst,'done',ch,'cx ok')}${baCell(c.act,lst,'act',ch,'cx act')}${baCell(c.cus,lst,'cus',ch,'cx warnc')}${baCell(c.none,lst,'none',ch,'cx bad')}${baCell(c.skip+c.aged,lst,'out',ch,'cx mut')}
 <td class="n">${c.E?`<button type="button" class="bacell" data-ba="src|${lst}|E|${ch||''}"><b>${nf(c.E)}</b></button>`:'<b>0</b>'} ${baD(c)}</td><td class="n">${c.pct==null?'<span class="mut">—</span>':'<b class="'+baPk(c.pct)+'">'+c.pct+'%</b>'}</td>
 <td class="cx"><button type="button" class="basrcb" data-ba="src|${lst}||${ch||''}" aria-pressed="${BA_L===lst&&!BA_B&&BA_C===(ch||'')}">ดู source</button></td></tr>`;}
const BA_TH=`<th>ค้างต้นช่วง</th><th class="cx">เข้าใหม่</th><th class="cx">✅ เคลียร์แล้ว</th><th class="cx">✋ ตอบ/ตามแล้ว</th><th class="cx">💬 ลูกค้าทักกลับ</th><th class="cx">⏳ ยังไม่มีใครแตะ</th><th class="cx">คัดออก · หมดอายุ</th><th>ค้างปลายช่วง</th><th>แอดมินจัดการ</th><th class="cx"></th>`;
const baName=l=>{const L=baLN(l);return `${L[1]} <span class="bafull">${esc(L[2])}</span><span class="batiny">${esc(BA_TINY[l]||L[2])}</span>`;};
/* ---------- auto reading ---------- */
function baRead(p,P,V){const T=baSum(V.all),out=[],u=BA_U();
 if(!T.S&&!T.N)return ['ไม่มีแชทค้างในหมวด Follow up ช่วงนี้'];
 const d=T.E-T.S;
 if(d<0)out.push(`<b>ค้างลดลง ${nf(-d)} แชท</b> (${nf(T.S)} → ${nf(T.E)}) — ${u}นี้แอดมินจัดการ (${nf(T.done+T.act)}) ได้มากกว่าแชทที่เข้ามาใหม่ (${nf(T.N)})`);
 else if(d>0)out.push(`<b style="color:var(--risk)">ค้างเพิ่มขึ้น ${nf(d)} แชท</b> (${nf(T.S)} → ${nf(T.E)}) — แชทที่เข้ารายการใหม่ (${nf(T.N)}) มากกว่าที่แอดมินจัดการได้ (${nf(T.done+T.act)})`);
 else out.push(`ค้างเท่าเดิม ${nf(T.E)} แชท — จัดการได้พอ ๆ กับที่เข้ามาใหม่`);
 const pp=baPrev(P,p);if(pp){const Vp=baGet(pp),Tp=baSum(Vp.all);if(T.pct!=null&&Tp.pct!=null){const dd=T.pct-Tp.pct;
  out.push(`แอดมินจัดการ <b>${T.pct}%</b> ของงานที่ต้องทำ · ${baLab(pp)} ${Tp.pct}% ${dd===0?'(เท่าเดิม)':(dd>0?'<span class="badown">▲ '+dd+' จุด</span>':'<span class="baup">▼ '+(-dd)+' จุด</span>')}`);}}
 else if(T.pct!=null)out.push(`แอดมินจัดการ <b>${T.pct}%</b> ของงานที่ต้องทำ (${nf(T.done+T.act)} จาก ${nf(T.need)} แชท)`);
 if(T.cus)out.push(`💬 <b>ลูกค้าทักกลับแล้วยังไม่มีแอดมินตอบ ${nf(T.cus)} แชท</b> — ตอบกลุ่มนี้ก่อน <button type="button" class="chip" data-ba="src|all|cus|">ดูรายชื่อ</button>`);
 if(T.none){const per=WK_L.map(L=>[L,baSum([].concat(...Object.values(V.by[L[0]]))).none]).sort((a,b)=>b[1]-a[1]);
  const old=V.all.filter(o=>o.b==='none'&&o.age!=null&&o.age>=30).length,hasA=V.all.some(o=>o.age!=null&&o.age>=0);
  out.push(`⏳ ไม่มีใครแตะเลย <b>${nf(T.none)} แชท</b> (${Math.round(T.none*100/Math.max(1,T.need))}% ของงาน) — มากสุดในหมวด ${per[0][0][1]} ${esc(per[0][0][2])} (${nf(per[0][1])})${hasA&&old?' · ในนี้ '+nf(old)+' แชทค้างมา 30 วันขึ้นไปแล้ว':''}`);}
 const cats=WK_L.map(L=>[L,baSum([].concat(...Object.values(V.by[L[0]])))]).filter(x=>x[1].need>=10&&x[1].pct!=null).sort((a,b)=>b[1].pct-a[1].pct);
 if(cats.length>1)out.push(`หมวดที่จัดการได้มากสุด ${cats[0][0][1]} ${cats[0][1].pct}% · น้อยสุด ${cats[cats.length-1][0][1]} <b>${cats[cats.length-1][1].pct}%</b> (${esc(cats[cats.length-1][0][2])})`);
 if(CH==='all'){const cs=Object.keys(p.per).map(c=>[c,baSum(V.all.filter(o=>o.ch===c))]).filter(x=>x[1].need);
  if(cs.length>1){const a=cs.slice().sort((x,y)=>y[1].none-x[1].none)[0];out.push(`ช่องทางที่ยังไม่มีใครแตะมากสุด ${BA_CHI[a[0]]} ${BA_CHN[a[0]]} ${nf(a[1].none)} แชท · จัดการ ${baPctTxt(a[1])}`);}}
 if(V.mv)out.push(`<span class="nsm">เข้าใหม่ ${nf(T.N)} รวมแชทที่แอดมินดันขึ้นขั้นถัดไปในช่วงเดียวกัน ${nf(V.mv)} แชท (เช่น ตอบแล้ว → ไปอยู่ “ยังไม่แนบตัวอย่าง”)</span>`);
 return out;}
function baDataNote(p){const n=[],chs=baChs();
 for(const c of chs){const e=(FU.wk.end||{})[c];if(!p.per[c]){n.push(`<b>${BA_CHN[c]} ไม่อยู่ในตัวเลขนี้</b> — ข้อมูลถึง ${e?fuDay(e):'—'}`);continue;}
  const w=p.per[c].w;if(!w[2]&&baFull(p))n.push(`${BA_CHN[c]} นับถึง ${fuDay(w[1])} ${w[1].slice(11,16)} น. (ยังไม่ครบ${BA_U()})`);}
 return n;}
/* ---------- trend: before (start) -> after (end) per period, a dumbbell per row ---------- */
function baDumb(P,p){const TR=baTrend(P),key=BA_TL||'all',rows=P.map((x,i)=>[x,TR[i][key]]).reverse();
 const mx=Math.max(1,...rows.map(r=>Math.max(r[1].S,r[1].E)));
 const lists=`<div class="balists" role="group" aria-label="เลือกหมวดของกราฟ"><button type="button" class="chip" data-ba="tl|" aria-pressed="${!BA_TL}">ทุกหมวด</button>${WK_L.map(L=>`<button type="button" class="chip" data-ba="tl|${L[0]}" aria-pressed="${BA_TL===L[0]}" title="${esc(L[2])}">${L[1]} ${esc(BA_TINY[L[0]])}</button>`).join('')}</div>`;
 const body=rows.map(([x,c])=>{const a=c.S*100/mx,b=c.E*100/mx,l=Math.min(a,b),w=Math.abs(a-b);
  const tip=`${baLab(x)}: ต้นช่วง ${nf(c.S)} → ปลายช่วง ${nf(c.E)} · เข้าใหม่ ${nf(c.N)} · แอดมินจัดการ ${baPctTxt(c)}`;
  return `<div class="r${x===p?' on':''}" data-ba="k|${x.k}" tabindex="0" role="button" aria-pressed="${x===p}" title="${esc(tip)}"><div class="pl">${baLab(x)}${baFull(x)?'':`<small>${baCur(x)?'ยังไม่จบ':'ข้อมูลไม่ครบ'}</small>`}${CH==='all'&&baMiss(x).length?`<small>ไม่รวม ${baMiss(x).map(c=>BA_CHN[c]).join(' · ')}</small>`:''}</div>
   <div class="tk" aria-hidden="true"><i class="ln" style="left:${l}%;width:${w}%"></i><i class="d0" style="left:${a}%"></i><i class="d1" style="left:${b}%"></i></div>
   <div class="tx"><b>${nf(c.S)}</b> → <b>${nf(c.E)}</b> ${baD(c)} · จัดการ <b class="${baPk(c.pct)}">${baPctTxt(c)}</b></div></div>`;}).join('');
 return lists+`<div class="badbk"><span><i style="background:#7FC0CF"></i>ต้น${BA_U()} (ก่อน)</span><span><i style="background:var(--leaf)"></i>ปลาย${BA_U()} (หลัง)</span><span>เส้นสั้น = ค้างพอ ๆ เดิม · จุดเข้มอยู่ซ้าย = ค้างลดลง · กดแถวเพื่อดู${BA_U()}นั้น</span></div><div class="badb">${body}</div>`;}
/* ---------- source: every chat behind a number ---------- */
function baSrcRows(V){let L=BA_L==='all'?V.all:[].concat(...Object.values(V.by[BA_L]||{}));
 if(BA_C)L=L.filter(o=>o.ch===BA_C);
 return L;}
function baFilt(L){const q=BA_Q.trim().toLowerCase();
 return L.filter(o=>{if(BA_B){if(BA_B==='S'&&!(o.fl&1))return false;if(BA_B==='N'&&!(o.fl&8))return false;if(BA_B==='E'&&!((o.fl&2)&&!o.man))return false;
   if(BA_B==='out'&&o.b!=='skip'&&o.b!=='aged')return false;if(BA_ORD[BA_B]!=null&&o.b!==BA_B)return false;}
  if(q&&!(String(o.name).toLowerCase().includes(q)||o.who.join(' ').toLowerCase().includes(q)||String(o.owner||'').toLowerCase().includes(q)))return false;return true;})
  .sort((a,b)=>(BA_ORD[a.b]-BA_ORD[b.b])||((a.age==null?1e9:a.age)-(b.age==null?1e9:b.age)));}
const baLN=l=>(WK_L.find(L=>L[0]===l)||['','',''] );
function baOutTxt(o){return o.out?(WK_OUT[o.out]||o.out):(o.man?(o.live?'กดปุ่มแล้ว (หลังรอบอัปเดต)':'กดปุ่มในหน้าเว็บแล้ว'):((o.fl&4)?'แอดมินพิมพ์ในแชทแล้ว ยังอยู่ขั้นนี้':'ยังค้าง ไม่มีใครแตะ'));}
function baStartTxt(o){return (o.fl&1?'ค้างอยู่แล้ว':'เข้าใหม่')+(o.age!=null&&o.age>=0?' · รอมา '+nf(o.age)+' วัน':'');}
function baBtn(o){const s=CH;CH=o.ch;try{return fuBtn({tid:o.tid,name:o.name});}finally{CH=s;}}
function baLink(o){const s=CH;CH=o.ch;try{return fuLink({tid:o.tid,name:o.name})||'';}finally{CH=s;}}
function baSrcList(V){const L=baFilt(baSrcRows(V)),n=L.length,pg=Math.min(BA_PG,Math.max(0,Math.ceil(n/BA_PS)-1)),part=L.slice(pg*BA_PS,pg*BA_PS+BA_PS);
 const SN=l=>WK_SUBN[l]||{};
 const rows=part.map(o=>`<tr><td class="nm"><i class="bacd" style="background:${BA_CHC[o.ch]}" title="${BA_CHN[o.ch]}"></i>${o.ch==='ig'?'@':''}${esc(o.name||'(ไม่มีชื่อ)')}${o.ch==='line'&&o.owner?'<div class="nsm">ผู้ดูแลห้อง '+esc(o.owner)+'</div>':''}</td>
  <td class="wr cx2">${baLN(o.lst)[1]} ${esc(SN(o.lst)[o.sub]||'')}</td><td class="wr">${esc(baStartTxt(o))}</td>
  <td class="wr"><span class="bab ${o.b}">${BA_BS[o.b]}</span>${o.b==='none'?'':'<div>'+esc(baOutTxt(o))+'</div>'}</td><td class="wr cx2">${o.who.length?esc(o.who.join(', ')):'<span class="mut">—</span>'}</td><td>${baBtn(o)}</td></tr>`).join('');
 const pages=Math.ceil(n/BA_PS);
 const pager=pages>1?`<button type="button" class="chip" data-ba="pg|${pg-1}"${pg?'':' disabled'}>‹ ก่อนหน้า</button><span class="nsm">หน้า ${pg+1}/${pages}</span><button type="button" class="chip" data-ba="pg|${pg+1}"${pg+1<pages?'':' disabled'}>ถัดไป ›</button>`:'';
 return `<div class="nsm" style="margin:4px 0 6px"><b>${nf(n)}</b> แชท${n>BA_PS?' · แสดงทีละ '+BA_PS:''} · เรียงงานที่ต้องทำก่อน (ลูกค้าทักกลับ → ไม่มีใครแตะ → ตอบ/ตามแล้ว → เคลียร์แล้ว) · ในกลุ่มเดียวกันแชทที่รอมาน้อยกว่าอยู่บน</div>
  ${n?`<div class="tw"><table class="wkt"><thead><tr><th>ลูกค้า</th><th class="cx2">หมวด · กลุ่ม</th><th>ต้นช่วง</th><th>ปลายช่วง</th><th class="cx2">ใครจัดการ</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`:'<div class="empty">ไม่มีแชทตามตัวกรองนี้</div>'}
  <div class="pg">${pager}<button type="button" class="dlbtn" data-ba="csv" style="margin-left:auto">⤓ ดาวน์โหลด CSV · ${nf(n)} แชท</button></div>`;}
function baSrc(p,V){if(!BA_L)return '';
 const base=baSrcRows(V),c0=baSum(base);
 const bchip=(k,v)=>`<button type="button" class="chip" data-ba="b|${k}" aria-pressed="${BA_B===k}">${BA_BN[k]||'คัดออก · หมดอายุ'} <b>${nf(v)}</b></button>`;
 const bchips=`<button type="button" class="chip" data-ba="b|" aria-pressed="${!BA_B}">ทุกสถานะ <b>${nf(base.length)}</b></button>`+[['S',c0.S],['N',c0.N],['done',c0.done],['act',c0.act],['cus',c0.cus],['none',c0.none],['out',c0.skip+c0.aged],['E',c0.E]].filter(x=>x[1]).map(x=>bchip(x[0],x[1])).join('');
 const lchips=`<button type="button" class="chip" data-ba="l|all" aria-pressed="${BA_L==='all'}">ทุกหมวด</button>`+WK_L.map(L=>`<button type="button" class="chip" data-ba="l|${L[0]}" aria-pressed="${BA_L===L[0]}" title="${esc(L[2])}">${L[1]} ${esc(L[2])}</button>`).join('');
 const cchips=CH==='all'?`<div class="fl"><span class="lab">ช่องทาง</span><button type="button" class="chip" data-ba="c|" aria-pressed="${!BA_C}">ทุกช่องทาง</button>${Object.keys(p.per).map(c=>`<button type="button" class="chip" data-ba="c|${c}" aria-pressed="${BA_C===c}">${BA_CHI[c]} ${BA_CHN[c]}</button>`).join('')}</div>`:'';
 const ttl=(BA_L==='all'?'ทุกหมวด':baLN(BA_L)[1]+' '+baLN(BA_L)[2])+(BA_C?' · '+BA_CHN[BA_C]:(CH==='all'?' · ทุกช่องทาง':' · '+BA_CHN[CH]));
 return `<div class="basrc" id="basrc"><div class="hd"><b>Source · ${esc(ttl)}</b><span class="nsm">${esc(baLong(p))}</span><button type="button" class="x" data-ba="close">ปิด ✕</button></div>
  <div class="fl"><span class="lab">หมวด</span>${lchips}</div>${cchips}<div class="fl"><span class="lab">สถานะ</span>${bchips}</div>
  <div class="fl"><input type="search" id="baq" placeholder="ค้นชื่อลูกค้า หรือชื่อแอดมิน" value="${esc(BA_Q)}" aria-label="ค้นในรายชื่อ"></div>
  <div id="basrcl">${baSrcList(V)}</div></div>`;}
function baCSV(p,V){const L=baFilt(baSrcRows(V)),SN=l=>WK_SUBN[l]||{};
 const out=[['ช่วงเวลา','ช่องทาง','หมวด','กลุ่ม','ชื่อลูกค้า','ต้นช่วง','รอมาแล้ว (วัน) ตอนเข้ารายการ','สถานะปลายช่วง','รายละเอียด','ยังค้างปลายช่วง','ใครจัดการ','ผู้ดูแลห้อง (LINE)','ลิงก์ห้องแชท']];
 for(const o of L)out.push([baLong(p),BA_CHN[o.ch],baLN(o.lst)[2],SN(o.lst)[o.sub]||o.sub||'',o.name,o.fl&1?'ค้างอยู่แล้ว':'เข้าใหม่',o.age!=null&&o.age>=0?o.age:'',BA_BS[o.b],baOutTxt(o),(o.fl&2)&&!o.man?'Y':'',o.who.join(', '),o.owner||'',baLink(o)]);
 downloadCSV('before-after-'+(CH==='all'?'ทุกช่องทาง':BA_CHN[CH].replace(/\s+/g,''))+'-'+(BA_P==='w'?'สัปดาห์':'เดือน')+'-'+p.k.slice(0,10)+(BA_L&&BA_L!=='all'?'-'+BA_L:'')+(BA_B?'-'+BA_B:'')+'.csv',out);}
/* ---------- LINE group notice (preview of the weekly message) ---------- */
function baLine(nm,c){return `${nm}: ${nf(c.S)}${c.N?'(+'+nf(c.N)+')':''} → ✅${nf(c.done)} ✋${nf(c.act)} 💬${nf(c.cus)} ⏳${nf(c.none)} → ${nf(c.E)} ${c.E===c.S?'เท่าเดิม':(c.E<c.S?'▼'+nf(c.S-c.E):'▲'+nf(c.E-c.S))}${c.pct!=null?' · จัดการ '+c.pct+'%':''}`;}
function baNotice(p,V){const T=baSum(V.all),d=wkT(p.k),y=d.getFullYear(),miss=baChs().filter(c=>!p.per[c]).map(c=>BA_CHN[c]);
 const L=[`📊 สรุปแอดมินเคลียร์แชท Follow up · ${BA_P==='w'?'สัปดาห์ '+baLab(p)+' '+y:baLab(p)}${CH==='all'?'':' · '+BA_CHN[CH]}${baFull(p)?'':' (ยังไม่จบ)'}`,
  `ต้น${BA_U()}ค้าง ${nf(T.S)} → ปลาย${BA_U()} ${nf(T.E)} (${T.E===T.S?'เท่าเดิม':(T.E<T.S?'▼'+nf(T.S-T.E):'▲'+nf(T.E-T.S))})`,
  `แอดมินจัดการ ${nf(T.done+T.act)} แชท (✅ เคลียร์ ${nf(T.done)} · ✋ ตอบ/ตาม ${nf(T.act)})${T.pct!=null?' = '+T.pct+'% ของงาน':''}`,
  `💬 ลูกค้าทักกลับรอตอบ ${nf(T.cus)} · ⏳ ยังไม่มีใครแตะ ${nf(T.none)}`,'','แยกหมวด'];
 for(const W of WK_L){const c=baSum([].concat(...Object.values(V.by[W[0]])));if(c.S||c.N)L.push(baLine(W[1]+' '+BA_SHORT[W[0]],c));}
 if(CH==='all'){L.push('','แยกช่องทาง');for(const c of Object.keys(p.per))L.push(baLine(BA_CHI[c]+' '+BA_CHN[c],baSum(V.all.filter(o=>o.ch===c))));}
 if(miss.length)L.push('(ยังไม่รวม '+miss.join(' · ')+' — ข้อมูลยังไม่ถึง'+BA_U()+'นี้)');
 const who={};for(const o of V.all){if(o.b!=='done'&&o.b!=='act')continue;for(const n of o.who)who[n]=(who[n]||0)+1;}
 const ws=Object.keys(who).sort((a,b)=>who[b]-who[a]);if(ws.length)L.push('','👤 ใครจัดการ: '+ws.map(n=>n+' '+nf(who[n])).join(' · '));
 L.push('','อ่าน: ค้างต้น(+เข้าใหม่) → ✅เคลียร์แล้ว ✋ตอบ/ตามแล้ว 💬ลูกค้าทักกลับรอตอบ ⏳ยังไม่มีใครแตะ → ค้างปลาย','ดูรายชื่อแชท (หน้า Before / After): https://biopalm-education.github.io/admin-hub/#ba');
 return L.join('\n');}
/* ---------- page ---------- */
function renderBA(){
 const el=$('#ba'),sc=$('#bascope');if(!el)return;
 if(!FU&&!FU_ERR){el.innerHTML='<div class="empty">กำลังโหลดข้อมูล Follow up…</div>';admFU().then(()=>{if(VIEW==='ba')renderBA();});return;}
 if(!FU){el.innerHTML='<div class="empty">โหลดข้อมูลไม่สำเร็จ ('+esc(FU_ERR)+')</div>';return;}
 if(!baOn()){el.innerHTML='<div class="empty">ยังไม่มีข้อมูลรายสัปดาห์ในชุดข้อมูลนี้ — จะขึ้นหลังรอบอัปเดตเช้า</div>';return;}
 if(BA_P==='m'&&!baHasM()){sc.textContent=CHN[CH];
  el.innerHTML=baCtl([],null)+'<div class="empty">ตัวเลขรายเดือนจะขึ้นหลังรอบอัปเดตเช้ารอบถัดไป (ระบบเพิ่งเพิ่มการนับรายเดือน 20 ต.ค. 2026) — ระหว่างนี้ดูรายสัปดาห์ได้เลย</div>';baBind(el);return;}
 const P=baPeriods();
 if(!P.length){sc.textContent=CHN[CH];el.innerHTML=baCtl(P,null)+'<div class="empty">ช่องทางนี้ยังไม่มีข้อมูลในช่วงที่นับ</div>';baBind(el);return;}
 const p=baSel(P);if(CH!=='all'||(BA_C&&!p.per[BA_C]))BA_C='';
 const V=baGet(p),T=baSum(V.all),u=BA_U();
 sc.textContent=CHN[CH]+' · '+baLong(p);
 const fullS=wkT(p.k),endS=baEndOf(p),endD=wkT(endS);if(baFull(p))endD.setMinutes(endD.getMinutes()-1);
 const dTxt=d=>d.getDate()+' '+FU_TH_M[d.getMonth()];
 const notes=baDataNote(p);
 /* hero */
 const hero=`<div class="bahero">
  <div class="bak before"><button type="button" class="bago" data-ba="src|all|S|"><span class="lab">ก่อน · ต้น${u} (${dTxt(fullS)} 00:00)</span><div class="v">${nf(T.S)}<small>แชทค้าง</small></div></button>
   <span class="s">+ เข้ารายการระหว่าง${u} <b>${nf(T.N)}</b>${V.mv?' (ในนี้ '+nf(V.mv)+' ขยับมาจากหมวดก่อนหน้า)':''}</span></div>
  <div class="baarr" aria-hidden="true">→</div>
  <div class="bak mid"><span class="lab">แอดมินจัดการระหว่าง${u}</span><div class="v">${nf(T.done+T.act)}<small>แชท</small></div>
   <span class="s">✅ เคลียร์แล้ว <b>${nf(T.done)}</b> · ✋ ตอบ/ตามแล้ว <b>${nf(T.act)}</b></span>
   <span class="bapct ${baPk(T.pct)}">${T.pct==null?'—':T.pct+'% ของงานที่ต้องทำ ('+nf(T.need)+')'}</span></div>
  <div class="baarr" aria-hidden="true">→</div>
  <div class="bak after"><button type="button" class="bago" data-ba="src|all|E|"><span class="lab">หลัง · ${baFull(p)?'ปลาย'+u+' ('+dTxt(endD)+' 24:00)':'ล่าสุด ('+dTxt(wkT(endS))+' '+endS.slice(11,16)+' น.)'}</span><div class="v">${nf(T.E)}<small>แชทค้าง</small></div></button>
   <span class="s">${baD(T,true)} จากต้น${u}</span></div></div>
  <div class="wkbar" role="img" aria-label="${BA_BK.map(b=>BA_BN[b]+' '+T[b]).join(' · ')}">${BA_BK.map(b=>T[b]?`<i class="${b}" style="width:${Math.round(T[b]/Math.max(1,T.S+T.N)*1000)/10}%"></i>`:'').join('')}</div>
  <div class="balegend">${BA_BK.filter(b=>T[b]).map(b=>`<button type="button" class="chip wkb-${b}" data-ba="src|all|${b}|"><b>${nf(T[b])}</b> ${BA_BN[b]}</button>`).join('')}</div>`;
 /* tables */
 const t1rows=WK_L.map(L=>baRowHTML(baName(L[0]),baSum([].concat(...Object.values(V.by[L[0]]))),L[0],'')).join('')+baRowHTML('<b>รวม 5 หมวด</b>',T,'all','',true);
 const t1=`<h3 class="bah3">แยกหมวด <span class="nsm">กดชื่อหมวดหรือตัวเลขเพื่อดูรายชื่อแชท (source)</span></h3><div class="tw"><table class="wkt batab"><thead><tr><th>หมวด<span class="bafull"> · ${esc(baLong(p))}</span></th>${BA_TH}</tr></thead><tbody>${t1rows}</tbody></table></div>`;
 let t2='';
 if(CH==='all'){const chs=Object.keys(p.per);
  const cell=(rows,lst,ch)=>{const c=baSum(rows);return `<td class="n">${c.S||c.N?`<button type="button" class="bacell" data-ba="src|${lst}||${ch}"><span class="mx">${nf(c.S)} → <b>${nf(c.E)}</b> ${baD(c)}</span><span class="mx2">จัดการ ${baPctTxt(c)} · ⏳ ${nf(c.none)}</span></button>`:'<span class="mut">—</span>'}</td>`;};
  const mrow=(lab,lst,get)=>`<tr${lst==='all'?' class="batot"':''}><td>${lab}</td>${chs.map(c=>cell(get(c),lst,c)).join('')}${cell(get(''),lst,'')}</tr>`;
  const rows=WK_L.map(L=>mrow(baName(L[0]),L[0],c=>c?(V.by[L[0]][c]||[]):[].concat(...Object.values(V.by[L[0]])))).join('')+mrow('<b>รวม 5 หมวด</b>','all',c=>c?V.all.filter(o=>o.ch===c):V.all);
  t2=`<h3 class="bah3">หมวด × ช่องทาง <span class="nsm">ต้น${u} → ปลาย${u} · กดช่องเพื่อดูรายชื่อ</span></h3><div class="tw"><table class="wkt bamx"><thead><tr><th>หมวด</th>${chs.map(c=>`<th>${BA_CHI[c]} ${BA_CHN[c]}${p.per[c].w[2]||!baFull(p)?'':' *'}</th>`).join('')}<th>รวม</th></tr></thead><tbody>${rows}</tbody></table></div>`+
   (notes.length?`<p class="banote">* ${notes.join(' · ')}</p>`:'');}
 /* who handled */
 const who={};for(const o of V.all){if(o.b!=='done'&&o.b!=='act')continue;for(const n of o.who)who[n]=(who[n]||0)+1;}
 const ws=Object.keys(who).sort((a,b)=>who[b]-who[a]);
 const whoBox=`<h3 class="bah3">ใครจัดการ <span class="nsm">${CH==='line'?'ชื่อแอดมินที่ LINE บอก + ชื่อที่เลือกตอนกดปุ่ม':(CH==='all'?'LINE บอกชื่อทุกข้อความ · Facebook / Instagram นับได้เฉพาะชื่อที่เลือกตอนกดปุ่มในหน้าเว็บ (Meta ไม่บอกชื่อแอดมิน)':'Meta ไม่บอกชื่อแอดมิน — นับจากชื่อที่เลือกตอนกดปุ่มในหน้าเว็บ')}</span></h3>
  <div class="bawho">${ws.length?ws.map(n=>`<span class="badge">${esc(n)} ${nf(who[n])}</span>`).join(' '):'<span class="nsm">— ยังไม่มีชื่อในช่วงนี้</span>'}</div>`;
 const notice=baNotice(p,V);
 el.innerHTML=baCtl(P,p)+
  (notes.length&&CH==='all'?`<div class="bawarn">${notes.join(' · ')}</div>`:'')+
  hero+`<div class="baread"><ul>${baRead(p,P,V).map(x=>'<li>'+x+'</li>').join('')}</ul></div>`+
  t1+t2+baSrc(p,V)+
  `<h3 class="bah3">ย้อนหลังราย${u} <span class="nsm">ต้น${u} → ปลาย${u} ของทุก${u}ที่มีข้อมูล</span></h3>${baDumb(P,p)}`+
  whoBox+
  `<details class="fhelp" style="margin-top:18px"><summary>ข้อความแจ้งเตือนเข้า LINE กลุ่ม (ตัวอย่างจาก${u}ที่เลือก)</summary><pre class="wkrep" id="banotice">${esc(notice)}</pre><button type="button" class="chip" data-ba="copy">คัดลอกข้อความ</button> <span class="nsm">ขั้นต่อไป: ให้ระบบส่งข้อความนี้เข้า LINE กลุ่มเองทุกเช้าวันจันทร์ (สัปดาห์ที่จบแล้ว)</span></details>`+
  baHelp();
 baBind(el);}
function baCtl(P,p){const hasAge=baHasAge();
 const per=P.slice().reverse().map(x=>`<button type="button" class="chip${baFull(x)?'':' part'}" data-ba="k|${x.k}" aria-pressed="${x===p}">${baPre(x)}${baLab(x)}</button>`).join('');
 return `<div class="bactl"><div class="ctl"><span class="lab">ดูเป็น</span><div class="seg" role="group" aria-label="รายสัปดาห์หรือรายเดือน"><button type="button" data-ba="p|w" aria-pressed="${BA_P==='w'}">รายสัปดาห์</button><button type="button" data-ba="p|m" aria-pressed="${BA_P==='m'}">รายเดือน</button></div></div>
  ${hasAge?`<div class="ctl"><span class="lab">อายุแชท</span><div class="seg" role="group" aria-label="อายุแชทตอนเข้ารายการ"><button type="button" data-ba="age|" aria-pressed="${!BA_AGE}">ทั้งหมด</button><button type="button" data-ba="age|y" aria-pressed="${BA_AGE==='y'}">ไม่เกิน 29 วัน</button><button type="button" data-ba="age|o" aria-pressed="${BA_AGE==='o'}">30 วันขึ้นไป</button></div>${BA_AGE?'<span class="nsm">นับตามอายุตอนแชทเข้ารายการในช่วงนั้น</span>':''}</div>`:''}
  ${P.length?`<div class="ctl" style="flex-basis:100%"><span class="lab">${BA_U()}</span><div class="baper" role="group" aria-label="เลือกช่วงเวลา">${per}</div></div>`:''}</div>`;}
function baHelp(){return `<details class="fhelp" style="margin-top:10px"><summary>นับอย่างไร</summary><dl>
 <dt>หมวด</dt><dd>5 หมวดเดียวกับหน้า Follow up: 🤖 บอทตอบ ไม่มีแอดมินตอบ (ค้าง 7 วันขึ้นไป) · 🎬 แอดมินตอบแล้วแต่ยังไม่แนบตัวอย่าง · 🗨️ แนบตัวอย่างแล้วยังไม่สรุปจ่าย · 💸 แนบตัวอย่าง + สรุปจ่ายแล้ว ลูกค้ายังไม่โอน · 🧾 สรุปจ่ายแล้ว (ไม่แนบตัวอย่าง) ยังไม่โอน — 4 หมวดหลังนับแชทที่รอ 1–89 วัน</dd>
 <dt>ก่อน · ค้างต้นช่วง</dt><dd>ระบบอ่านแชทจริงย้อนหลังทีละวัน (ตัดที่เที่ยงคืน) ด้วยกฎเดียวกับรายการ Follow up · ค้างต้นสัปดาห์ = อยู่ในรายการตอนเที่ยงคืนวันจันทร์ · ค้างต้นเดือน = เที่ยงคืนวันที่ 1</dd>
 <dt>เข้าใหม่</dt><dd>เข้ารายการระหว่างช่วง — ทั้งแชทใหม่ และแชทที่แอดมินดันขึ้นขั้นถัดไป (เช่น ตอบแล้ว → ไปอยู่หมวด “ยังไม่แนบตัวอย่าง”) แชทเดียวจึงนับได้มากกว่า 1 หมวดในช่วงเดียวกัน</dd>
 <dt>✅ เคลียร์แล้ว</dt><dd>ขยับไปขั้นถัดไปหรือจบ: แอดมินตอบ · ส่งตัวอย่าง · ส่งสรุปยอด · ลูกค้าโอนแล้ว · ลูกค้าปิดท้ายเอง</dd>
 <dt>✋ ตอบ/ตามแล้ว</dt><dd>แอดมิน (คน ไม่ใช่บอท) พิมพ์ในแชทระหว่างที่อยู่ในรายการ แต่ยังอยู่ขั้นเดิม เช่น ทักตาม ตอบคำถามใหม่ ส่งสรุปยอดรอบใหม่ · หรือกดปุ่ม ✓ ตอบแล้ว / ✓ ตามแล้ว / ไม่ต้องตาม ในหน้า Follow up</dd>
 <dt>💬 ลูกค้าทักกลับ รอตอบ</dt><dd>ลูกค้าส่งข้อความใหม่แล้วยังไม่มีแอดมินตอบ — งานยังอยู่ที่แอดมิน ไม่นับเป็นเคลียร์</dd>
 <dt>⏳ ยังไม่มีใครแตะ</dt><dd>อยู่ในรายการถึงปลายช่วงโดยไม่มีแอดมินพิมพ์ในแชทเลย</dd>
 <dt>คัดออก · หมดอายุ</dt><dd>ลูกค้าปฏิเสธ/นักเรียนเดิม/ย้ายไปคุย LINE (ระบบคัดเอง) · รอเกิน 90 วัน — ไม่นับในตัวหาร</dd>
 <dt>หลัง · ค้างปลายช่วง</dt><dd>ยังอยู่ในรายการตอนจบช่วง (ไม่นับแชทที่กดย้ายเอง) · สัปดาห์/เดือนที่ยังไม่จบ = ณ ข้อมูลล่าสุด</dd>
 <dt>แอดมินจัดการ</dt><dd>(✅ + ✋) ÷ (ค้างต้นช่วง + เข้าใหม่ − คัดออก − หมดอายุ) · เขียว 60% ขึ้นไป · เหลือง 30–59% · แดง ต่ำกว่า 30%</dd>
 <dt>อายุแชท</dt><dd>จำนวนวันที่รอมาแล้วตอนเข้ารายการในช่วงนั้น (บอทตอบ: นับจากข้อความล่าสุดของลูกค้า · หมวดอื่น: นับจากแอดมินตอบ/ส่งสรุปยอด) · “30 วันขึ้นไป” = กองเก่า แยกดูได้ว่างานใหม่ถูกเคลียร์ทันไหม</dd>
 <dt>อัปเดตเมื่อไร</dt><dd>Facebook + Instagram ทุกเช้า (ขึ้นเว็บราว 09:00–10:00 น.) · LINE OA ตามรอบที่ดึงข้อมูล LINE — สัปดาห์หลังวันที่ดึงล่าสุดจะยังไม่รวม LINE · ปุ่มที่กดในหน้า Follow up นับทันที${FU.wk.built?' · ชุดนี้คำนวณเมื่อ '+fuDay(FU.wk.built)+' '+FU.wk.built.slice(11,16)+' น.':''}</dd></dl></details>`;}
function baBind(el){
 const act=t=>{const a=(t.dataset.ba||'').split('|'),k=a[0];
  if(k==='p'){if(BA_P===a[1])return;BA_P=a[1];BA_K='';BA_PG=0;try{localStorage.setItem('bp_ba_p',BA_P);}catch(e){}renderBA();return;}
  if(k==='k'){BA_K=a[1];BA_PG=0;renderBA();return;}
  if(k==='age'){BA_AGE=a[1];BA_PG=0;renderBA();return;}
  if(k==='tl'){BA_TL=a[1];renderBA();return;}
  if(k==='src'){BA_L=a[1]||'all';BA_B=a[2]||'';BA_C=a[3]||'';BA_PG=0;BA_Q='';renderBA();const s=document.getElementById('basrc');if(s&&s.scrollIntoView)s.scrollIntoView({behavior:'smooth',block:'start'});return;}
  if(k==='l'){BA_L=a[1];BA_PG=0;renderBA();return;}
  if(k==='b'){BA_B=a[1];BA_PG=0;renderBA();return;}
  if(k==='c'){BA_C=a[1];BA_PG=0;renderBA();return;}
  if(k==='pg'){BA_PG=Math.max(0,+a[1]||0);baSrcOnly();const s=document.getElementById('basrc');if(s&&s.scrollIntoView)s.scrollIntoView({block:'start'});return;}
  if(k==='close'){BA_L='';BA_B='';BA_C='';BA_Q='';renderBA();return;}
  if(k==='csv'){const P=baPeriods(),p=baSel(P);if(p)baCSV(p,baGet(p));return;}
  if(k==='copy'){const t2=(el.querySelector('#banotice')||{}).textContent||'';toast(copyText(t2)?'คัดลอกข้อความแล้ว':'คัดลอกไม่สำเร็จ');return;}};
 el.onclick=e=>{const t=e.target.closest('[data-ba]');if(!t||!el.contains(t)||t.disabled)return;e.preventDefault();act(t);};
 el.onkeydown=e=>{if(e.key!=='Enter'&&e.key!==' ')return;const t=e.target.closest('div[data-ba]');if(!t)return;e.preventDefault();act(t);};
 const q=el.querySelector('#baq');if(q){let h=null;q.addEventListener('input',()=>{clearTimeout(h);h=setTimeout(()=>{BA_Q=q.value;BA_PG=0;baSrcOnly();},200);});}}
function baSrcOnly(){const P=baPeriods(),p=baSel(P),box=document.getElementById('basrcl');if(!p||!box)return;box.innerHTML=baSrcList(baGet(p));}

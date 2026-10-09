/* ---------- Follow up · weekly before / after (preview 9 ต.ค. 2026) — data: build_week.py -> FU.wk ----------
   Every chat that was on a list during a Monday–Sunday week is one row: on the list at the start, entered during
   the week, where it stood at the end, and whether a person on our side wrote while it was listed.
   Buttons pressed after the data was built (OVROWS) are merged here so the current week moves at once. */
let WK_WI=null, WK_SEL='', WK_SUB='';
const WK_L=[['ar','🤖','บอทตอบ - ไม่มีแอดมินตอบ'],['sp','🎬','แอดมินตอบแล้ว แต่ยังไม่แนบตัวอย่าง'],['np','🗨️','แนบตัวอย่างแล้ว แต่ยังไม่ได้สรุปจ่าย'],
 ['pay','💸','แนบตัวอย่าง + สรุปจ่ายแล้ว แต่ลูกค้ายังไม่โอน'],['pz','🧾','ส่งสรุปจ่ายแล้ว (ไม่แนบตัวอย่าง) ยังไม่โอน']];
const WK_B=[['done','✅ เคลียร์แล้ว','ขยับไปขั้นถัดไปหรือจบแล้ว'],['act','✋ ตอบ/ตามแล้ว','แอดมินพิมพ์ในแชทหรือกดปุ่มแล้ว แต่ยังอยู่ขั้นนี้'],
 ['cus','💬 ลูกค้าทักกลับ รอตอบ','ลูกค้าส่งข้อความใหม่ ยังไม่มีแอดมินตอบ'],['none','⏳ ยังไม่มีใครแตะ','ไม่มีแอดมินพิมพ์ในแชทเลยตลอดสัปดาห์'],
 ['skip','ระบบคัดออก','ลูกค้าปฏิเสธ/ไม่ใช่ลูกค้า (ระบบคัดเอง)'],['aged','หมดอายุ','เกิน 90 วัน']];
const WK_DONE={ar:'แอดมินตอบแล้ว · โอนแล้ว · ลูกค้าปิดท้ายเอง',sp:'ส่งตัวอย่าง · ส่งสรุปยอด · โอนแล้ว',np:'ส่งสรุปยอด · โอนแล้ว',pay:'ลูกค้าโอนแล้ว (สลิปผ่าน)',pz:'ลูกค้าโอนแล้ว (สลิปผ่าน)'};
const WK_OUT={ans:'แอดมินตอบแล้ว',smp:'ส่งตัวอย่างแล้ว',sum:'ส่งสรุปยอดแล้ว',paid:'โอนแล้ว',close:'ลูกค้าปิดท้ายเอง',fu:'ทักตามแล้ว รอลูกค้าตอบ',
 reans:'ตอบคำถามใหม่แล้ว (ยังไม่ขยับขั้น)',requote:'ส่งสรุปยอดรอบใหม่',move:'แนบตัวอย่างเพิ่ม → ย้ายหมวด',cus:'ลูกค้าทักกลับ ยังไม่มีคนตอบ',x:'ระบบคัดออก',aged:'เกิน 90 วัน'};
const WK_SUBN={ar:{nA:'ไม่เคยมีแอดมินคุย · ถามจริง',nB:'ไม่เคยมีแอดมินคุย · กดปุ่มสนใจ',pA:'เคยคุยแล้ว · ถามรอบใหม่',pB:'เคยคุยแล้ว · กดปุ่มรอบใหม่'},
 sp:{A:'บอกชั้น/คอร์สแล้ว',B:'ถามเรื่องคอร์สทั่วไป'},np:{A:'บอกชั้น/คอร์สแล้ว',B:'ถามเรื่องคอร์สทั่วไป'},
 pay:{R:'ลูกค้าถามค้าง',A:'สรุปยอดแล้ว ลูกค้าเงียบ',B:'คุยต่อแล้วเงียบ',C:'ได้ราคาแล้วเงียบ'}};
WK_SUBN.pz=WK_SUBN.pay;
const WK_DONEK=['ans','smp','sum','paid','close'], WK_ACTK=['fu','reans','requote','move'];
function wkOn(){return !!(FU&&FU.wk&&FU.wk.rows&&FU.wk.rows[CH]&&(FU.wk.weeks[CH]||[]).length);}
function wkWeeks(){return (FU.wk.weeks||{})[CH]||[];}
function wkIdx(){const n=wkWeeks().length;if(WK_WI==null||WK_WI>=n||WK_WI<0)WK_WI=n-1;return WK_WI;}
function wkT(s){return new Date(s.slice(0,10)+'T'+(s.slice(11,16)||'00:00')+':00');}
function wkLab(w){const a=wkT(w[0]),b=wkT(w[1]);if(w[2]||(b.getHours()===0&&b.getMinutes()===0))b.setDate(b.getDate()-1);
 return (a.getMonth()===b.getMonth()?a.getDate():a.getDate()+' '+FU_TH_M[a.getMonth()])+'–'+b.getDate()+' '+FU_TH_M[b.getMonth()];}
let WK_OVI=null, WK_OVN=-1;
function wkOvIndex(){if(WK_OVI&&WK_OVN===OVROWS.length)return WK_OVI;const m={};
 for(const x of OVROWS){const k=x[0]+'|'+x[1];(m[k]=m[k]||[]).push(x);}WK_OVI=m;WK_OVN=OVROWS.length;return m;}
/* a button pressed after the build, while the chat was listed this week -> act (both "ตอบ/ตามแล้ว" and "ไม่ต้องตาม") */
function wkLiveMan(tid,w){const L=wkOvIndex()[CH+'|'+tid];if(!L)return null;const built=wkT(FU.wk.built||'2000-01-01 00:00'),s=wkT(w[0]),e=w[2]?wkT(w[1]):new Date(8.64e15);
 for(let i=L.length-1;i>=0;i--){const x=L[i],at=new Date(x[6]);if(isNaN(at)||at<=built||at<=s||at>e)continue;
  if(x[3]==='skip')return {by:x[5]||'',why:x[4]||''};return null;}return null;}
function wkRows(lst,wi){const R=(((FU.wk.rows[CH]||{})[lst])||[])[wi]||[], ids=FU.wk.ids[CH]||[], w=wkWeeks()[wi];
 const out=[];for(const r of R){const id=ids[r[0]]||['','',''];const o={tid:id[0],name:id[1],owner:id[2],fl:r[1],out:r[2],sub:r[3],who:(r[4]||[]).slice(),man:r[5]||''};
  if(!o.man&&w){const lm=wkLiveMan(o.tid,w);if(lm){o.man='act';o.live=1;if(lm.by&&!o.who.includes(lm.by))o.who.push(lm.by);}}
  if(FU_O&&CH==='line'&&o.owner!==FU_O)continue;out.push(o);}
 return out;}
function wkBucket(o){if(WK_DONEK.includes(o.out))return 'done';if(WK_ACTK.includes(o.out)||o.man)return 'act';if((o.fl&4)&&!o.out)return 'act';
 if(o.out==='aged')return 'aged';if(o.out==='x')return 'skip';return o.out==='cus'?'cus':'none';}
function wkCount(rows){const c={S:0,N:0,done:0,act:0,cus:0,none:0,skip:0,aged:0,E:0};
 for(const o of rows){c.S+=o.fl&1?1:0;c.N+=o.fl&8?1:0;c[wkBucket(o)]++;if((o.fl&2)&&!o.man)c.E++;}
 c.need=c.S+c.N-c.skip-c.aged;c.pct=c.need?Math.round((c.done+c.act)/c.need*100):null;return c;}
function wkDelta(c){const d=c.E-c.S;return d===0?'<span class="fud0">เท่าเดิม</span>':(d<0?'<span class="fudok">▼ '+nf(-d)+'</span>':'<span class="fudbad">▲ '+nf(d)+'</span>');}
function wkPct(c){if(c.pct==null)return '<span class="mut">—</span>';const k=c.pct>=60?'ok':(c.pct>=30?'warnc':'bad');return '<b class="'+k+'">'+c.pct+'%</b>';}
function wkCells(c){return `<td class="n">${nf(c.S)}</td><td class="n mut cx">${c.N?'+'+nf(c.N):'·'}</td><td class="n ok cx">${nf(c.done)}</td><td class="n act cx">${nf(c.act)}</td><td class="n warnc cx">${nf(c.cus)}</td><td class="n bad cx">${nf(c.none)}</td><td class="n mut cx">${nf(c.skip+c.aged)}</td><td class="n"><b>${nf(c.E)}</b> ${wkDelta(c)}</td><td class="n">${wkPct(c)}</td>`;}
/* phone: the middle columns fold into one line under the row name */
function wkMini(c){return `<div class="wkmini">${c.N?'+'+nf(c.N)+' ใหม่ · ':''}<span class="ok">✅${nf(c.done)}</span> <span class="act">✋${nf(c.act)}</span> <span class="warnc">💬${nf(c.cus)}</span> <span class="bad">⏳${nf(c.none)}</span></div>`;}
function wkRow(lab,c,attr,on){return `<tr${attr?' class="go'+(on?' on':'')+'" '+attr+' tabindex="0"':''}><td>${lab}${wkMini(c)}</td>${wkCells(c)}</tr>`;}
const WK_TH=`<th>ค้างต้นสัปดาห์</th><th class="cx">เข้าใหม่</th><th class="cx">✅ เคลียร์แล้ว</th><th class="cx">✋ ตอบ/ตามแล้ว</th><th class="cx">💬 ลูกค้าทักกลับ</th><th class="cx">⏳ ยังไม่มีใครแตะ</th><th class="cx">ระบบคัดออก · หมดอายุ</th><th>ค้างปลายสัปดาห์</th><th>แอดมินจัดการ</th>`;
/* a week that is not over in the data: "this week" while it really is this week, otherwise the data simply stops there (LINE) */
function wkCur(x){return !x[2]&&(Date.now()-wkT(x[0]).getTime())<7*864e5;}
function wkPre(x){return x[2]?'':(wkCur(x)?'สัปดาห์นี้ · ':'ข้อมูลถึงกลางสัปดาห์ · ');}
function wkWeekChips(){const W=wkWeeks(),wi=wkIdx();
 return `<div class="wkweeks" role="group" aria-label="เลือกสัปดาห์">`+W.map((x,i)=>`<button type="button" class="chip${x[2]?'':' part'}" data-wkw="${i}" aria-pressed="${i===wi}">${wkPre(x)}${wkLab(x)}</button>`).reverse().join('')+`</div>`;}
function wkEndNote(){const e=(FU.wk.end||{})[CH]||'';const w=wkWeeks()[wkIdx()];
 return (e?'ข้อมูลถึง '+fuDay(e)+' '+e.slice(11,16)+' น.':'')+(w&&wkCur(w)?' · สัปดาห์นี้ยังไม่จบ ตัวเลขขยับได้ทุกเช้า':(w&&!w[2]?' · สัปดาห์นี้มีข้อมูลไม่ครบ 7 วัน':''))+(CH==='line'?' · LINE ยังไม่อัปเดตรายวัน — สัปดาห์หลังวันที่ดึงล่าสุดจะยังไม่มีข้อมูล':'');}
function wkTop(){
 if(!wkOn())return '';
 const wi=wkIdx(), w=wkWeeks()[wi]; if(!w)return '';
 const chn=CH==='ig'?'Instagram':(CH==='line'?'LINE OA':'Facebook');
 const rows=WK_L.map(L=>wkRow(L[1]+' '+L[2],wkCount(wkRows(L[0],wi)),'data-wkl="'+L[0]+'"',FU_MODE===L[0])).join('');
 const rep=FU.wk.report&&FU.wk.report.msgs?FU.wk.report.msgs.join('\n\n'):'';
 return `<section class="wk wktop" aria-label="สรุป Follow up รายสัปดาห์">
  <div class="wkhd"><b>สรุปรายสัปดาห์ · ${chn}</b><span class="nsm">ต้นสัปดาห์ค้างเท่าไร → แอดมินจัดการไปเท่าไร → ปลายสัปดาห์เหลือเท่าไร · กดแถวเพื่อเปิดหมวดนั้น</span></div>
  ${wkWeekChips()}
  <div class="tw"><table class="wkt"><thead><tr><th>หมวด · สัปดาห์ ${wkLab(w)}</th>${WK_TH}</tr></thead><tbody>${rows}</tbody></table></div>
  <p class="nsm wknote">${wkEndNote()} · <b>แอดมินจัดการ</b> = (เคลียร์แล้ว + ตอบ/ตามแล้ว) ÷ (ค้างต้นสัปดาห์ + เข้าใหม่ − ระบบคัดออก − หมดอายุ)</p>
  <details class="fhelp"><summary>นับอย่างไร</summary><dl>
   <dt>ค้างต้นสัปดาห์ · เข้าใหม่</dt><dd>อ่านแชทจริงย้อนหลังทีละวัน (เที่ยงคืน) ด้วยกฎเดียวกับรายการ Follow up แต่ละหมวด · ค้างต้นสัปดาห์ = อยู่ในรายการตอนเที่ยงคืนวันจันทร์ · เข้าใหม่ = เข้ารายการระหว่างสัปดาห์</dd>
   <dt>✅ เคลียร์แล้ว</dt><dd>แชทขยับไปขั้นถัดไปหรือจบ · บอทตอบ: ${WK_DONE.ar} · ยังไม่แนบตัวอย่าง: ${WK_DONE.sp} · ยังไม่สรุปจ่าย: ${WK_DONE.np} · ยังไม่โอน: ${WK_DONE.pay}</dd>
   <dt>✋ ตอบ/ตามแล้ว</dt><dd>แอดมิน (คนกดส่ง ไม่ใช่บอท) พิมพ์ในแชทระหว่างที่แชทอยู่ในรายการ เช่น ทักตาม ตอบคำถามใหม่ ส่งสรุปยอดรอบใหม่ — แต่แชทยังอยู่ขั้นเดิม · หรือกดปุ่ม ✓ ตอบแล้ว / ✓ ตามแล้ว / ย้ายไป “ไม่ต้องตาม” ในหน้านี้ (นับทันทีที่กด)</dd>
   <dt>💬 ลูกค้าทักกลับ รอตอบ</dt><dd>ลูกค้าส่งข้อความใหม่แล้วยังไม่มีแอดมินตอบ — งานอยู่ที่แอดมิน <b>ไม่นับเป็นเคลียร์</b> (ของเดิมนับเป็นเคลียร์ได้)</dd>
   <dt>⏳ ยังไม่มีใครแตะ</dt><dd>อยู่ในรายการตลอดถึงปลายสัปดาห์ และไม่มีแอดมินพิมพ์ในแชทเลย</dd>
   <dt>ระบบคัดออก · หมดอายุ</dt><dd>ลูกค้าปฏิเสธ/ถามเรื่องนักเรียนเดิม/ชวนไปคุย LINE แล้ว (ระบบคัดเอง) · เกิน 90 วัน — ไม่นับในตัวหาร</dd>
   <dt>ตัวเลขอัปเดตเมื่อไร</dt><dd>Facebook + Instagram ทุกเช้า (ขึ้นเว็บราว 09:00–10:00 น.) ระบบอ่านทุกแชทที่มีความเคลื่อนไหวใหม่ แล้วจัดหมวดใหม่ทั้งห้องอัตโนมัติ · ปุ่มที่กดในหน้านี้นับทันที · LINE OA ตามรอบที่ดึงข้อมูล LINE</dd></dl></details>
  ${rep?`<details class="fhelp"><summary>ข้อความรายงานเข้า LINE กลุ่ม (ตัวอย่าง · สัปดาห์ล่าสุดที่จบแล้ว)</summary><pre class="wkrep" id="wkrep">${esc(rep)}</pre><button type="button" class="chip" id="wkcopy">คัดลอกข้อความ</button></details>`:''}
 </section>`;}
function wkBox(lst){
 if(!wkOn())return '';
 const wi=wkIdx(), W=wkWeeks(), w=W[wi]; if(!w)return '';
 const rows=wkRows(lst,wi), c=wkCount(rows), tot=Math.max(1,c.S+c.N);
 const bar=WK_B.map(b=>c[b[0]]?`<i class="${b[0]}" style="width:${Math.round(c[b[0]]/tot*1000)/10}%"></i>`:'').join('');
 const chips=WK_B.filter(b=>c[b[0]]).map(b=>`<button type="button" class="chip wkb-${b[0]}" data-wkb="${b[0]}" aria-pressed="${WK_SEL===b[0]}" title="${esc(b[2])}"><b>${nf(c[b[0]])}</b> ${b[1]}</button>`).join('');
 /* sub-groups (and LINE room owners) */
 const SN=WK_SUBN[lst]||{}, subs={};for(const o of rows)(subs[o.sub]=subs[o.sub]||[]).push(o);
 const subRows=Object.keys(SN).filter(k=>subs[k]).map(k=>wkRow(esc(SN[k]),wkCount(subs[k]),'data-wks="'+k+'"',WK_SUB===k)).join('');
 let ownRows='';
 if(CH==='line'&&!FU_O){const ow={};for(const o of rows)(ow[o.owner||'-']=ow[o.owner||'-']||[]).push(o);
  ownRows=Object.keys(ow).sort((a,b)=>ow[b].length-ow[a].length).map(k=>wkRow('ผู้ดูแลห้อง '+esc(k),wkCount(ow[k]))).join('');}
 /* who handled them: LINE names every sender, Facebook / Instagram only the name picked on a button */
 const who={};for(const o of rows){const b=wkBucket(o);if(b!=='done'&&b!=='act')continue;for(const n of o.who)who[n]=(who[n]||0)+1;}
 const whoS=Object.keys(who).sort((a,b)=>who[b]-who[a]);
 const whoBox=`<div class="wkwho"><span class="nsm">ใครจัดการ ${CH==='line'?'(ชื่อแอดมินที่ LINE บอก + ปุ่มที่กด)':'(Meta ไม่บอกชื่อแอดมิน — นับจากชื่อที่เลือกตอนกดปุ่มในหน้านี้)'}:</span> ${whoS.length?whoS.map(n=>`<span class="badge">${esc(n)} ${nf(who[n])}</span>`).join(' '):'<span class="nsm">—</span>'}</div>`;
 /* trend: every week of this list */
 const trend=W.map((x,i)=>wkRow(wkPre(x)+wkLab(x),wkCount(wkRows(lst,i)),'data-wkw="'+i+'"',i===wi)).reverse().join('');
 /* names for the chosen bucket / sub-group */
 let names='';
 if(WK_SEL||WK_SUB){const L=rows.filter(o=>(!WK_SEL||wkBucket(o)===WK_SEL)&&(!WK_SUB||o.sub===WK_SUB));
  const lab=[WK_SEL?(WK_B.find(b=>b[0]===WK_SEL)||[])[1]:'',WK_SUB?SN[WK_SUB]:''].filter(Boolean).join(' · ');
  names=`<div class="flnames"><div class="fuhd"><b>${esc(lab)}</b> <span class="nsm">${nf(L.length)} แชท${L.length>300?' · แสดง 300 แชทแรก':''}</span> <button type="button" class="chip" data-wkclr="1" aria-pressed="true">ล้างตัวกรอง ✕</button></div>`+
   L.slice(0,300).map(o=>`<div class="flrow"><span>${CH==='ig'?'@':''}${esc(o.name||'(ไม่มีชื่อ)')} <span class="nsm">· ${esc(o.out?(WK_OUT[o.out]||o.out):(o.man?(o.live?'กดปุ่มแล้ว (วันนี้)':'กดปุ่มแล้ว'):((o.fl&4)?'แอดมินพิมพ์ในแชทแล้ว ยังค้างขั้นนี้':'ยังค้าง')))}${o.who.length?' · '+esc(o.who.join(', ')):''}${o.fl&8?' · เข้าใหม่':''}</span></span>${fuBtn({tid:o.tid,name:o.name})}</div>`).join('')+`</div>`;}
 return `<div class="wk wkbox"><div class="wkhd"><b>หมวดนี้ · สัปดาห์ ${wkLab(w)}${w[2]?'':(wkCur(w)?' (ยังไม่จบ)':' (ข้อมูลไม่ครบสัปดาห์)')}</b><span class="nsm">${wkEndNote()}</span></div>
  ${wkWeekChips()}
  <div class="wkkpi"><div class="k1"><span class="lab">ค้างต้นสัปดาห์</span><b>${nf(c.S)}</b>${c.N?` <span class="nsm">+ เข้าใหม่ ${nf(c.N)}</span>`:''}</div>
   <div class="k1"><span class="lab">ค้างปลายสัปดาห์</span><b>${nf(c.E)}</b> ${wkDelta(c)}</div>
   <div class="k1"><span class="lab">แอดมินจัดการ</span><b>${c.pct==null?'—':c.pct+'%'}</b> <span class="nsm">${nf(c.done+c.act)} จาก ${nf(c.need)} แชท</span></div></div>
  <div class="wkbar" role="img" aria-label="${WK_B.map(b=>b[1]+' '+c[b[0]]).join(' · ')}">${bar}</div>
  <div class="wkchips">${chips||'<span class="nsm">ไม่มีแชทในหมวดนี้สัปดาห์นี้ 🎉</span>'}</div>
  ${names}
  ${subRows||ownRows?`<div class="tw"><table class="wkt"><thead><tr><th>แยกตามกลุ่ม</th>${WK_TH}</tr></thead><tbody>${subRows}${ownRows}</tbody></table></div>`:''}
  ${whoBox}
  <details class="fhelp" style="margin-top:10px"><summary>ย้อนหลังรายสัปดาห์ (หมวดนี้)</summary><div class="tw"><table class="wkt"><thead><tr><th>สัปดาห์</th>${WK_TH}</tr></thead><tbody>${trend}</tbody></table></div></details>
 </div>`;}
function wkRe(){if(FU_MODE==='ar')renderFU();else if(FU_MODE==='tn')renderTN();else renderPay();}
function wkBind(el){if(!wkOn())return;
 const key=(n,f)=>{n.addEventListener('click',f);n.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();f();}});};
 el.querySelectorAll('[data-wkw]').forEach(b=>key(b,()=>{WK_WI=+b.dataset.wkw;WK_SEL='';WK_SUB='';wkRe();}));
 el.querySelectorAll('[data-wkb]').forEach(b=>key(b,()=>{WK_SEL=WK_SEL===b.dataset.wkb?'':b.dataset.wkb;wkRe();}));
 el.querySelectorAll('[data-wks]').forEach(b=>key(b,()=>{WK_SUB=WK_SUB===b.dataset.wks?'':b.dataset.wks;wkRe();}));
 el.querySelectorAll('[data-wkclr]').forEach(b=>key(b,()=>{WK_SEL='';WK_SUB='';wkRe();}));
 el.querySelectorAll('[data-wkl]').forEach(b=>key(b,()=>{const m=b.dataset.wkl;WK_SEL='';WK_SUB='';
  if(m!==FU_MODE){FU_MODE=m;try{localStorage.setItem('bp_fu_mode',m);}catch(e){}FU_PAGE=0;PU_PAGE=0;PU_G='all';PU_B='1';PU_T='';PU_W='';PU_Q='';PU_FLK='';}
  wkRe();const t=document.querySelector('.wkbox');if(t&&t.scrollIntoView)t.scrollIntoView({behavior:'smooth',block:'start'});}));
 const cp=el.querySelector('#wkcopy');if(cp)cp.addEventListener('click',()=>{const t=(el.querySelector('#wkrep')||{}).textContent||'';
  try{navigator.clipboard.writeText(t).then(()=>toast('คัดลอกแล้ว'),()=>toast('คัดลอกไม่สำเร็จ'));}catch(e){toast('คัดลอกไม่สำเร็จ');}});}

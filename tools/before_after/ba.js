/* ---------- Tracking (เดิมชื่อ Before / After) v2 (preview 21 ต.ค. 2026) — data: build_week.py -> ba.json (daily timeline since ม.ค.) ----------
   Any range (a week, a month, or dates picked on the calendar) is counted from the daily timeline: a chat is "before"
   when it is on the list at 00:00 of the first day, "after" when it still is at 24:00 of the last day (or the data end),
   and in between we know whether an admin wrote in it, pressed a button, or the chat moved on. Same rules and numbers as
   the weekly rows (checked: every week, list and channel equal wk.sum). One category at a time (popup + dropdown),
   a status that says whether the team is clearing more / faster than the period before, and the source list.
   Needs wk.js (WK_OUT, WK_SUBN, wkRe) in the same page. */
let BA=null, BA_ERR='', BA_LP=null, BA_ASK=true, BA_CC=new Map();
let BA_CAT=(()=>{try{return localStorage.getItem('bp_ba_cat')||'';}catch(e){return '';}})();
let BA_M=(()=>{try{const v=localStorage.getItem('bp_ba_m');return v==='m'||v==='c'?v:'w';}catch(e){return 'w';}})();
let BA_A='', BA_B='', BA_SRC=false, BA_SB='', BA_SC='', BA_SQ='', BA_PG=0, BA_CAL=null;
const BA_CH=['fb','ig','line'], BA_CHN={fb:'Facebook',ig:'Instagram',line:'LINE OA'}, BA_CHI={fb:'🔵',ig:'🟣',line:'🟢'};
const BA_CHC={fb:'var(--fb)',ig:'var(--ig)',line:'var(--ln)'};
const BA_LS=['ar','sp','np','pay','pz'];
const BA_LN={ar:['🤖','บอทตอบ ไม่มีแอดมินตอบ','บอทตอบ','ลูกค้าได้แต่ข้อความอัตโนมัติ ค้าง 7 วันขึ้นไป'],
 sp:['🎬','แอดมินตอบแล้ว แต่ยังไม่แนบตัวอย่าง','ยังไม่แนบตัวอย่าง','ตอบแล้ว ยังไม่ได้ส่งคลิป/ฟอร์มทดลองเรียน'],
 np:['🗨️','แนบตัวอย่างแล้ว แต่ยังไม่สรุปจ่าย','ยังไม่สรุปจ่าย','ส่งตัวอย่างแล้ว ยังไม่ได้ส่งใบสรุปยอด'],
 pay:['💸','แนบตัวอย่าง + สรุปจ่ายแล้ว ลูกค้ายังไม่โอน','ยังไม่โอน · แนบตัวอย่าง','ได้ใบสรุปยอดแล้ว ยังไม่มีสลิป'],
 pz:['🧾','สรุปจ่ายแล้ว (ไม่แนบตัวอย่าง) ยังไม่โอน','ยังไม่โอน · ไม่แนบตัวอย่าง','นักเรียนเก่า/สมัครต่อ ได้ใบสรุปยอดแล้ว ยังไม่มีสลิป'],
 all:['📊','ภาพรวมทุกหมวด','ทุกหมวด','5 หมวดรวมกัน + เทียบทีละหมวด']};
const BA_FROM={sp:'2026-08-19',np:'2026-08-19',pay:'2026-08-19'};   /* stage_rules.SAMPLE_FROM: ทีมเริ่มนับ "แนบตัวอย่าง" วันนี้ */
const BA_DONE=['ans','smp','sum','paid','close'], BA_ACT=['fu','reans','requote','move'];
const BA_BK=['done','act','cus','none','skip','aged'];
const BA_BN={S:'ค้างต้นช่วง',N:'เข้าใหม่ระหว่างช่วง',E:'ค้างปลายช่วง',done:'✅ เคลียร์แล้ว',act:'✋ ตอบ/ตามแล้ว',cus:'💬 ลูกค้าทักกลับ รอตอบ',none:'⏳ ยังไม่มีใครแตะ',skip:'ระบบคัดออก',aged:'หมดอายุ (เกิน 90 วัน)',out:'คัดออก · หมดอายุ'};
const BA_BS={done:'เคลียร์แล้ว',act:'ตอบ/ตามแล้ว',cus:'ลูกค้าทักกลับ รอตอบ',none:'ยังไม่มีใครแตะ',skip:'ระบบคัดออก',aged:'หมดอายุ'};
const BA_ORD={cus:0,none:1,act:2,done:3,skip:4,aged:5};
const BA_TH_MF=['มกราคม','กุมภาพันธ์','มีนาคม','เมษายน','พฤษภาคม','มิถุนายน','กรกฎาคม','สิงหาคม','กันยายน','ตุลาคม','พฤศจิกายน','ธันวาคม'];
const BA_PS=50;
/* ---------- data ---------- */
function baLoad(){if(BA||BA_ERR)return Promise.resolve();
 if(!BA_LP)BA_LP=(async()=>{try{if(!MAN||!MAN.files||!MAN.files.ba)throw new Error('nodata');const d=await getFile('ba');baPrep(d);BA=d;}catch(e){BA_ERR=String(e.message||e);}})();
 return BA_LP;}
function baPrep(d){d.t0=Date.UTC(+d.d0.slice(0,4),+d.d0.slice(5,7)-1,+d.d0.slice(8,10));
 const b=d.built||'2000-01-01 00:00';d.builtMs=Date.UTC(+b.slice(0,4),+b.slice(5,7)-1,+b.slice(8,10),+b.slice(11,13)||0,+b.slice(14,16)||0);
 for(const c in d.ch){const C=d.ch[c];C.c=c;C.endK=C.n-1;C.lastDay=C.endK-1;C.it={};
  for(const l of BA_LS)C.it[l]=((C.L||{})[l]||[]).map(f=>{const ks=[],cs=[];for(let j=1;j<f.length;j+=2){ks.push(f[j]);cs.push(f[j+1]);}return {i:f[0],ks,cs};});
  C.L=null;}}
const baYmd=k=>{const t=new Date(BA.t0+k*864e5);return t.getUTCFullYear()+'-'+String(t.getUTCMonth()+1).padStart(2,'0')+'-'+String(t.getUTCDate()).padStart(2,'0');};
const baK=ymd=>Math.round((Date.UTC(+ymd.slice(0,4),+ymd.slice(5,7)-1,+ymd.slice(8,10))-BA.t0)/864e5);
const baDt=k=>new Date(BA.t0+k*864e5);
const baDM=k=>{const t=baDt(k);return t.getUTCDate()+' '+FU_TH_M[t.getUTCMonth()];};
function baChs(){return (CH==='all'?BA_CH:[CH]).filter(c=>BA&&BA.ch[c]);}
function baMaxDay(){let m=-1;for(const c of baChs())m=Math.max(m,BA.ch[c].lastDay);return m;}
function baEndTxt(c){const e=BA.ch[c].end;return fuDay(e)+' '+e.slice(11,16)+' น.';}
/* ---------- periods ---------- */
function baWeeks(){const out=[],last=baMaxDay();if(last<0)return out;const dow=baDt(0).getUTCDay(),m0=(8-dow)%7;
 for(let k=m0;k<=last;k+=7)out.push({a:baYmd(k),b:baYmd(k+6)});return out;}
function baMonths(){const out=[],last=baMaxDay();if(last<0)return out;const s=baDt(0),e=baDt(last);
 for(let y=s.getUTCFullYear(),m=s.getUTCMonth();y<e.getUTCFullYear()||(y===e.getUTCFullYear()&&m<=e.getUTCMonth());m++){if(m>11){m=0;y++;}
  const a=Math.round((Date.UTC(y,m,1)-BA.t0)/864e5),b=Math.round((Date.UTC(y,m+1,1)-BA.t0)/864e5)-1;out.push({a:baYmd(Math.max(0,a)),b:baYmd(b)});}
 return out;}
function baSel(){const last=baMaxDay();
 if(BA_A&&BA_B&&baK(BA_A)<=last&&baK(BA_A)>=0)return {a:BA_A,b:BA_B};
 let s;if(BA_M==='w'){const W=baWeeks();s=W[W.length-1];for(let i=W.length-1;i>=0;i--)if(baK(W[i].b)<=last){s=W[i];break;}}
 else if(BA_M==='m'){const M=baMonths();s=M[M.length-1];}
 else s={a:baYmd(Math.max(0,last-13)),b:baYmd(last)};
 if(s){BA_A=s.a;BA_B=s.b;}return s||null;}
function baLab(s,mode){const md=mode||BA_M,ka=baK(s.a),kb=baK(s.b),A=baDt(ka),last=baMaxDay();
 if(md==='m')return FU_TH_M[A.getUTCMonth()]+' '+A.getUTCFullYear()+(kb>last?' (ถึง '+baDM(last)+')':'');
 const e=Math.min(kb,last),E=baDt(e),y=E.getUTCFullYear();
 if(md==='c')return baDM(ka)+' – '+baDM(e)+' '+y;
 return (A.getUTCMonth()===E.getUTCMonth()?A.getUTCDate():baDM(ka))+'–'+E.getUTCDate()+' '+FU_TH_M[E.getUTCMonth()]+' '+y+(kb>last?' (ยังไม่จบ)':'');}
const baUnit=()=>BA_M==='w'?'สัปดาห์':(BA_M==='m'?'เดือน':'ช่วง');
function baPrevSel(s){const ka=baK(s.a),kb=baK(s.b),span=Math.min(kb,baMaxDay())-ka;
 if(BA_M==='m'){const d=baDt(ka),pa=Math.round((Date.UTC(d.getUTCFullYear(),d.getUTCMonth()-1,1)-BA.t0)/864e5);if(pa<0)return null;
  const pl=ka-pa;if(kb<=baMaxDay())return {a:baYmd(pa),b:baYmd(ka-1)};   /* a whole month vs the whole month before; the running month vs the same days */
  return {a:baYmd(pa),b:baYmd(pa+Math.min(span,pl-1))};}
 const L=BA_M==='w'?7:(kb-ka+1),pa=ka-L;return pa<0?null:{a:baYmd(pa),b:baYmd(pa+span)};}
function baPrevLab(p){if(!p)return '';return BA_M==='w'?'สัปดาห์ก่อน':(BA_M==='m'?'เดือนก่อน':'ช่วงก่อนหน้า');}
function baTrendSels(s){if(BA_M==='w'){const W=baWeeks(),i=W.findIndex(w=>w.a===s.a);return W.slice(Math.max(0,i-11),i+1);}
 if(BA_M==='m'){const M=baMonths(),i=M.findIndex(m=>m.a===s.a);return M.slice(0,i+1);}
 const W=baWeeks(),ka=baK(s.a),kb=baK(s.b);return W.filter(w=>baK(w.b)>=ka&&baK(w.a)<=kb).slice(-26);}
/* ---------- range engine ---------- */
function baBS(ks,k){let lo=0,hi=ks.length-1,r=-1;while(lo<=hi){const m=(lo+hi)>>1;if(ks[m]<=k){r=m;lo=m+1;}else hi=m-1;}return r;}
function baMan(mp,ke,kb){if(!mp)return null;for(let j=mp.length-1;j>=0;j--){const x=mp[j];if(x[0]>kb)continue;if(x[1]==='u')return null;if(x[0]>ke)return x;return (x[3]!==-1&&x[3]<=kb)?null:'drop';}return null;}
let BA_LV=null, BA_LVN=-1;
function baLiveIdx(){if(BA_LV&&BA_LVN===OVROWS.length)return BA_LV;const m={};
 for(const x of OVROWS){const ms=Date.parse(x[6]);if(isNaN(ms))continue;const th=ms+7*36e5;if(th<=BA.builtMs)continue;
  (m[x[0]+'|'+x[1]]=m[x[0]+'|'+x[1]]||[]).push({k:Math.ceil((th-BA.t0)/864e5),st:x[3],by:x[5]||''});}
 BA_LV=m;BA_LVN=OVROWS.length;return m;}
function baBucket(o){if(BA_DONE.includes(o.out))return 'done';if(BA_ACT.includes(o.out)||o.man)return 'act';if((o.fl&4)&&!o.out)return 'act';
 if(o.out==='aged')return 'aged';if(o.out==='x')return 'skip';return o.out==='cus'?'cus':'none';}
function baEval(C,l,ka,kb,out){const ids=C.ids,aw=C.aw,mp=C.mp,LV=baLiveIdx();
 for(const it of C.it[l]){const ks=it.ks,cs=it.cs;if(ks[0]>kb)continue;
  const j=baBS(ks,ka),c0=j>=0?cs[j]:null;let ke=-1;
  if(c0&&c0[0]==='+')ke=ka;else for(let q=j+1;q<ks.length&&ks[q]<=kb;q++)if(cs[q][0]==='+'){ke=ks[q];break;}
  if(ke<0)continue;
  const m=baMan(mp[it.i],ke,kb);if(m==='drop')continue;
  const cb=cs[baBS(ks,kb)],on1=cb[0]==='+',on0=ke===ka,who=[];let adm=false,touch=-1,man=m?m[1]:'',live=0;
  const W=aw[it.i];if(W)for(const w of W){if(w[0]>ke&&w[0]<=kb){adm=true;if(touch<0)touch=w[0];for(let z=1;z<w.length;z++){const n=C.nm[w[z]];if(n&&!who.includes(n))who.push(n);}}}
  if(m){if(m[2]>=0){const n=C.nm[m[2]];if(n&&!who.includes(n))who.push(n);}if(touch<0||m[0]<touch)touch=m[0];}
  else{const lv=LV[C.c+'|'+ids[it.i][0]];if(lv)for(let z=lv.length-1;z>=0;z--){const x=lv[z];if(x.k<=ke||x.k>kb)continue;if(x.st==='skip'){man='a';live=1;if(x.by&&!who.includes(x.by))who.push(x.by);if(touch<0||x.k<touch)touch=x.k;}break;}}
  const ce=cs[baBS(ks,ke)],at=ce.indexOf('@');
  const o={ch:C.c,lst:l,i:it.i,tid:ids[it.i][0],name:ids[it.i][1],owner:ids[it.i][2],fl:(on0?1:8)|(on1?2:0)|(adm?4:0),out:on1?'':cb,
   sub:ce.slice(1,at),who,man,live,age:Math.max(0,Math.floor(ke-parseFloat(ce.slice(at+1)))),touch:touch>=0?touch-ke:-1};
  o.b=baBucket(o);out.push(o);}}
function baRange(s,cat){if(!s)return null;const key=[CH,s.a,s.b,cat,OVROWS.length].join('|');if(BA_CC.has(key))return BA_CC.get(key);
 const v={rows:[],chs:{},miss:[],part:[]};
 for(const c of baChs()){const C=BA.ch[c],ka=Math.max(0,baK(s.a)),kf=baK(s.b)+1;if(ka>=C.endK||kf<=0){v.miss.push(c);continue;}
  const kb=Math.min(kf,C.endK);v.chs[c]={ka,kb};if(kf>C.endK)v.part.push(c);
  for(const l of (cat==='all'?BA_LS:[cat]))baEval(C,l,ka,kb,v.rows);}
 v.c=baCount(v.rows);if(BA_CC.size>600)BA_CC.clear();BA_CC.set(key,v);return v;}
function baMed(a){if(!a.length)return null;const s=a.slice().sort((x,y)=>x-y),m=s.length>>1;return s.length%2?s[m]:(s[m-1]+s[m])/2;}
function baCount(rows){const c={S:0,N:0,done:0,act:0,cus:0,none:0,skip:0,aged:0,E:0,tN:0,tT:0},td=[];
 for(const o of rows){if(o.fl&1)c.S++;if(o.fl&8){c.N++;c.tN++;if(o.touch>=0){c.tT++;td.push(o.touch);}}c[o.b]++;if((o.fl&2)&&!o.man)c.E++;}
 c.need=c.S+c.N-c.skip-c.aged;c.h=c.done+c.act;c.pct=c.need?Math.round(c.h*100/c.need):null;
 c.med=td.length>=3?baMed(td):null;c.tPct=c.tN?Math.round(c.tT*100/c.tN):null;return c;}
/* ---------- status: is the team doing better than the period before? ---------- */
const baDays=v=>v==null?'—':(v<=1?'ภายใน 1 วัน':'~'+(Math.round(v*10)/10)+' วัน');
function baStatus(c,p){const it=[];
 let s1=0;if(c.pct!=null&&p&&p.pct!=null&&c.need>=5&&p.need>=5){const d=c.pct-p.pct;s1=d>=5?1:(d<=-5?-1:0);}
 it.push({s:s1,lab:'เคลียร์ได้ดีขึ้นไหม',v:c.pct==null?'—':c.pct+'%',
  d:c.pct!=null&&p&&p.pct!=null?(c.pct===p.pct?'เท่าเดิม':(c.pct>p.pct?'▲ '+(c.pct-p.pct)+' จุด':'▼ '+(p.pct-c.pct)+' จุด'))+' (เดิม '+p.pct+'%)':'',
  sub:'จัดการ '+nf(c.h)+' จาก '+nf(c.need)+' แชท'});
 const dd=c.E-c.S;let s2=0;if(c.S+c.N>=5)s2=dd<0?1:(dd>Math.max(2,c.S*0.05)?-1:0);
 it.push({s:s2,lab:'แชทค้างลดลงไหม',v:nf(c.S)+' → '+nf(c.E),d:dd===0?'เท่าเดิม':(dd<0?'▼ ลดลง '+nf(-dd):'▲ เพิ่มขึ้น '+nf(dd)),sub:'เข้าใหม่ระหว่าง'+baUnit()+' '+nf(c.N)+' แชท',own:1});
 let s3=0;if(c.med!=null&&p&&p.med!=null){const d=c.med-p.med;s3=d<=-0.5?1:(d>=0.5?-1:0);}
 it.push({s:s3,lab:'ตอบเร็วขึ้นไหม',v:baDays(c.med),d:c.med!=null&&p&&p.med!=null?(s3>0?'⚡ เร็วขึ้น':(s3<0?'ช้าลง':'พอ ๆ เดิม'))+' (เดิม '+baDays(p.med)+')':'',
  sub:c.tN?'แชทเข้าใหม่ '+nf(c.tN)+' · แอดมินแตะแล้ว '+c.tPct+'%':'ไม่มีแชทเข้าใหม่ในช่วงนี้'});
 if(!p)return {sc:0,cls:'flat',e:'📍',t:'ช่วงแรกที่มีข้อมูล',it};   /* nothing before it to compare with */
 const sc=s1+s2+s3,B=sc>=2?['great','🎉','ดีขึ้นชัดเจน']:(sc===1?['good','👍','ดีขึ้น']:(sc===0?['flat','➖','ทรงตัว']:['push','💪','ต้องเร่งอีกนิด']));
 return {sc,cls:B[0],e:B[1],t:B[2],it};}
const baTC=s=>s>0?'up':(s<0?'dn':'eq');
const baTI=s=>s>0?'✓ ดีขึ้น':(s<0?'! ต้องเร่ง':'– ทรงตัว');
function baHead(c,p,st,u){if(!c.S&&!c.N)return 'ไม่มีแชทในหมวดนี้ช่วงนี้ 🎉';
 const g=st.it,pos=[],pl=BA_M==='m'?'เดือนก่อน':(BA_M==='c'?'ช่วงก่อนหน้า':'สัปดาห์ก่อน');
 if(g[0].s>0)pos.push(u+'แอดมินจัดการได้ '+c.pct+'% ของงาน ดีขึ้นจาก'+pl+' '+(c.pct-p.pct)+' จุด');
 if(g[1].s>0)pos.push('กองแชทค้างลดลง '+nf(c.S-c.E)+' แชท');
 if(g[2].s>0)pos.push('แตะแชทใหม่เร็วขึ้น ('+baDays(c.med)+' จากเดิม '+baDays(p.med)+')');
 if(p&&c.h>p.h&&c.h>=5)pos.push('จัดการไป '+nf(c.h)+' แชท มากกว่า'+pl+' '+nf(c.h-p.h)+' แชท');
 if(pos.length)return pos.slice(0,2).join(' · ')+(st.sc>=2?' — เยี่ยมมาก ทีมทำได้ดีขึ้นจริง ๆ 🎉':' — ทำต่อแบบนี้เลย 💪');
 if(c.h)return 'จัดการไปแล้ว '+nf(c.h)+' แชท'+(c.cus?' — เริ่มจาก 💬 ลูกค้าทักกลับ '+nf(c.cus)+' แชทก่อน จะเห็นผลเร็วที่สุด':(c.none?' — ยังมี ⏳ '+nf(c.none)+' แชทที่ยังไม่มีใครแตะ ลองไล่จากแชทใหม่สุดก่อน':''));
 return c.none?'ยังไม่มีใครแตะ '+nf(c.none)+' แชท — เริ่มจากแชทใหม่สุดก่อน ลูกค้ายังสนใจอยู่':'';}
function baRecords(all,i){const out=[],cur=all[i];if(!cur||cur.pre)return out;const pts=all.filter(x=>!x.pre),n=pts.length;if(n<6)return out;const o=pts.filter(x=>x!==cur),u=BA_M==='m'?'เดือน':'สัปดาห์';
 if(cur.pct!=null&&o.every(x=>x.pct==null||cur.pct>x.pct))out.push('🏆 จัดการได้ดีที่สุดในรอบ '+n+' '+u);
 if(cur.h>0&&o.every(x=>cur.h>x.h))out.push('🏅 จัดการได้มากที่สุดในรอบ '+n+' '+u);
 if(cur.med!=null&&o.every(x=>x.med==null||cur.med<x.med))out.push('⚡ แตะแชทใหม่เร็วที่สุดในรอบ '+n+' '+u);
 if(o.every(x=>cur.E<x.E))out.push('📉 แชทค้างน้อยที่สุดในรอบ '+n+' '+u);
 return out;}
/* ---------- charts: small multiples (one measure each, no second axis) ---------- */
function baTrendData(s,cat){const f=BA_FROM[cat]?baK(BA_FROM[cat]):-1;   /* before the category existed = no data (not 0) */
 return baTrendSels(s).map(x=>{if(baK(x.b)<f)return {s:x,pct:null,E:null,h:0,med:null,need:0,miss:[],part:[],pre:1};
  const r=baRange(x,cat),c=r.c;return {s:x,pct:c.pct,E:c.E,h:c.h,med:c.med,need:c.need,miss:r.miss,part:r.part};});}
function baVerdict(pts,f,lowGood,fmt){const v=pts.map(f).filter(x=>x!=null);if(v.length<3)return '';
 const h=Math.min(4,Math.floor(v.length/2)),a=v.slice(-h),b=v.slice(-2*h,-h),av=x=>x.reduce((p,q)=>p+q,0)/x.length,A=av(a),Bv=av(b);
 const better=lowGood?A<Bv*0.95:A>Bv*1.05,worse=lowGood?A>Bv*1.05:A<Bv*0.95,u=BA_M==='m'?'เดือน':'สัปดาห์';
 return `<span class="${better?'up':(worse?'dn':'eq')}">${better?'↗ ดีขึ้น':(worse?'↘ แย่ลง':'→ ทรงตัว')}</span> เฉลี่ย ${h} ${u}ล่าสุด ${fmt(A)} · ก่อนหน้า ${fmt(Bv)}`;}
const baFpct=x=>x.pct, baFE=x=>x.E, baFmed=x=>x.med;
function baPLab(x){const k=baK(x.s.a);return BA_M==='m'?FU_TH_M[baDt(k).getUTCMonth()]:baDM(k);}
function baChart(pts,cur,title,f,fmt,max,lowGood,note,own){const mx=max||Math.max(1,...pts.map(x=>f(x)||0));
 const cols=pts.map((x,i)=>{const v=f(x),on=x.s.a===cur.a,h=v==null?0:Math.max(2,v*100/mx);
  const tip=baLab(x.s,BA_M==='m'?'m':'w')+': '+(v==null?(x.pre?'หมวดนี้เริ่มนับ 19 ส.ค. 2026':'ไม่มีข้อมูล'):fmt(v))+(x.miss.length?' · ไม่รวม '+x.miss.map(c=>BA_CHN[c]).join(', '):'');
  return `<button type="button" class="col${on?' on':''}${v==null?' nil':''}" data-bb="k|${x.s.a}|${x.s.b}" data-tip="${esc(tip)}" aria-label="${esc(tip)}"><span class="lb">${on||i===pts.length-1?(v==null?'':fmt(v)):''}</span><i style="height:${h}%"></i></button>`;}).join('');
 const step=Math.max(1,Math.ceil(pts.length/6));
 const n1=pts.length-1,xs=pts.map((x,i)=>`<span>${(i%step===0&&n1-i>=Math.max(2,step))||i===n1?baPLab(x):''}</span>`).join('');
 const cv=own||pts.find(x=>x.s.a===cur.a);   /* custom range: its own number, the bars are the weeks inside it */
 return `<div class="bbc"><div class="bbch"><b>${title}</b><span class="v">${cv&&f(cv)!=null?fmt(f(cv)):'—'}</span></div><div class="bbcp" style="--n:${pts.length}">${cols}</div><div class="bbcx" style="--n:${pts.length}">${xs}</div><div class="bbcv">${baVerdict(pts,f,lowGood,fmt)}</div>${note?'<div class="bbcn">'+note+'</div>':''}</div>`;}
/* ---------- source: every chat behind a number ---------- */
function baSrcRows(v){let L=v.rows;if(BA_SC)L=L.filter(o=>o.ch===BA_SC);return L;}
function baFilt(L){const q=BA_SQ.trim().toLowerCase();
 return L.filter(o=>{if(BA_SB){if(BA_SB==='S'&&!(o.fl&1))return false;if(BA_SB==='N'&&!(o.fl&8))return false;if(BA_SB==='E'&&!((o.fl&2)&&!o.man))return false;
   if(BA_SB==='out'&&o.b!=='skip'&&o.b!=='aged')return false;if(BA_ORD[BA_SB]!=null&&o.b!==BA_SB)return false;}
  if(q&&!(String(o.name).toLowerCase().includes(q)||o.who.join(' ').toLowerCase().includes(q)||String(o.owner||'').toLowerCase().includes(q)))return false;return true;})
  .sort((a,b)=>(BA_ORD[a.b]-BA_ORD[b.b])||(a.age-b.age));}
function baOutTxt(o){return o.out?(WK_OUT[o.out]||o.out):(o.man?(o.live?'กดปุ่มแล้ว (หลังรอบอัปเดต)':'กดปุ่มในหน้าเว็บแล้ว'):((o.fl&4)?'แอดมินพิมพ์ในแชทแล้ว ยังอยู่ขั้นนี้':'ยังค้าง ไม่มีใครแตะ'));}
function baBtn(o){const s=CH;CH=o.ch;try{return fuBtn({tid:o.tid,name:o.name});}finally{CH=s;}}
function baLink(o){const s=CH;CH=o.ch;try{return fuLink({tid:o.tid,name:o.name})||'';}finally{CH=s;}}
function baSrcList(v){const L=baFilt(baSrcRows(v)),n=L.length,pages=Math.ceil(n/BA_PS),pg=Math.min(BA_PG,Math.max(0,pages-1)),part=L.slice(pg*BA_PS,pg*BA_PS+BA_PS),SN=l=>WK_SUBN[l]||{};
 const rows=part.map(o=>`<tr><td class="nm"><i class="bbdot" style="background:${BA_CHC[o.ch]}" title="${BA_CHN[o.ch]}"></i>${o.ch==='ig'?'@':''}${esc(o.name||'(ไม่มีชื่อ)')}${o.ch==='line'&&o.owner?'<div class="nsm">ผู้ดูแลห้อง '+esc(o.owner)+'</div>':''}</td>
  <td class="wr cx2">${BA_LN[o.lst][0]} ${esc(SN(o.lst)[o.sub]||'')}</td><td class="wr">${o.fl&1?'ค้างอยู่แล้ว':'เข้าใหม่'} · รอมา ${nf(o.age)} วัน</td>
  <td class="wr"><span class="bbb ${o.b}">${BA_BS[o.b]}</span>${o.b==='none'?'':'<div>'+esc(baOutTxt(o))+(o.touch>0?' · แตะหลังเข้ารายการ '+o.touch+' วัน':'')+'</div>'}</td>
  <td class="wr cx2">${o.who.length?esc(o.who.join(', ')):'<span class="mut">—</span>'}</td><td>${baBtn(o)}</td></tr>`).join('');
 const pager=pages>1?`<button type="button" class="chip" data-bb="pg|${pg-1}"${pg?'':' disabled'}>‹ ก่อนหน้า</button><span class="nsm">หน้า ${pg+1}/${pages}</span><button type="button" class="chip" data-bb="pg|${pg+1}"${pg+1<pages?'':' disabled'}>ถัดไป ›</button>`:'';
 return `<div class="nsm" style="margin:6px 0"><b>${nf(n)}</b> แชท · เรียงงานที่ต้องทำก่อน (ลูกค้าทักกลับ → ยังไม่มีใครแตะ → ตอบ/ตามแล้ว → เคลียร์แล้ว) แชทที่รอมาน้อยกว่าอยู่บน</div>
  ${n?`<div class="tw"><table class="wkt bbsrct"><thead><tr><th>ลูกค้า</th><th class="cx2">หมวด · กลุ่ม</th><th>ต้นช่วง</th><th>ปลายช่วง</th><th class="cx2">ใครจัดการ</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`:'<div class="empty">ไม่มีแชทตามตัวกรองนี้</div>'}
  <div class="bbpg">${pager}<button type="button" class="dlbtn" data-bb="csv" style="margin-left:auto">⤓ ดาวน์โหลด CSV · ${nf(n)} แชท</button></div>`;}
function baSrc(s,v){if(!BA_SRC)return `<div class="bbsrcbar"><button type="button" class="bbsrcopen" data-bb="src|">📋 ดูรายชื่อแชท (source) · ${nf(v.rows.length)} แชท</button><span class="nsm">หรือกดตัวเลขในกล่อง ก่อน → หลัง</span></div>`;
 const c=baCount(baSrcRows(v)),ch=(k,lab,n)=>n?`<button type="button" class="chip" data-bb="sb|${k}" aria-pressed="${BA_SB===k}">${lab} <b>${nf(n)}</b></button>`:'';
 const bch=`<button type="button" class="chip" data-bb="sb|" aria-pressed="${!BA_SB}">ทุกสถานะ <b>${nf(baSrcRows(v).length)}</b></button>`+ch('S',BA_BN.S,c.S)+ch('N',BA_BN.N,c.N)+ch('done',BA_BN.done,c.done)+ch('act',BA_BN.act,c.act)+ch('cus',BA_BN.cus,c.cus)+ch('none',BA_BN.none,c.none)+ch('out',BA_BN.out,c.skip+c.aged)+ch('E',BA_BN.E,c.E);
 const cch=CH==='all'?`<div class="fl"><span class="lab">ช่องทาง</span><button type="button" class="chip" data-bb="sc|" aria-pressed="${!BA_SC}">ทุกช่องทาง</button>${Object.keys(v.chs).map(x=>`<button type="button" class="chip" data-bb="sc|${x}" aria-pressed="${BA_SC===x}">${BA_CHI[x]} ${BA_CHN[x]}</button>`).join('')}</div>`:'';
 return `<div class="bbsrc" id="bbsrc"><div class="hd"><b>📋 รายชื่อแชท · ${BA_LN[BA_CAT][0]} ${esc(BA_LN[BA_CAT][2])}</b><span class="nsm">${esc(baLab(s))}${CH==='all'?' · ทุกช่องทาง':' · '+BA_CHN[CH]} · เปลี่ยนช่วงเวลาได้ที่แถบด้านบน</span><button type="button" class="x" data-bb="srcx">ปิด ✕</button></div>
  ${cch}<div class="fl"><span class="lab">สถานะ</span>${bch}</div>
  <div class="fl"><input type="search" id="bbq" placeholder="ค้นชื่อลูกค้า หรือชื่อแอดมิน" value="${esc(BA_SQ)}" aria-label="ค้นในรายชื่อ"></div><div id="bbsrcl">${baSrcList(v)}</div></div>`;}
function baCSV(s,v){const L=baFilt(baSrcRows(v)),SN=l=>WK_SUBN[l]||{};
 const out=[['ช่วงเวลา','ช่องทาง','หมวด','กลุ่ม','ชื่อลูกค้า','ต้นช่วง','รอมาแล้ว (วัน) ตอนเข้ารายการ','สถานะปลายช่วง','รายละเอียด','วันจนแอดมินแตะ','ยังค้างปลายช่วง','ใครจัดการ','ผู้ดูแลห้อง (LINE)','ลิงก์ห้องแชท']];
 for(const o of L)out.push([baLab(s),BA_CHN[o.ch],BA_LN[o.lst][1],SN(o.lst)[o.sub]||o.sub||'',o.name,o.fl&1?'ค้างอยู่แล้ว':'เข้าใหม่',o.age,BA_BS[o.b],baOutTxt(o),o.touch>=0?o.touch:'',(o.fl&2)&&!o.man?'Y':'',o.who.join(', '),o.owner||'',baLink(o)]);
 downloadCSV('before-after-'+BA_CAT+'-'+(CH==='all'?'ทุกช่องทาง':BA_CHN[CH].replace(/\s+/g,''))+'-'+s.a+'_'+s.b+(BA_SB?'-'+BA_SB:'')+'.csv',out);}
/* ---------- controls: category popup, period dropdowns, calendar ---------- */
function baCatPicker(){const old=document.getElementById('bbpk');if(old)old.remove();const s=baSel(),p=baPrevSel(s);
 const opt=k=>{const c=baRange(s,k).c,st=baStatus(c,p?baRange(p,k).c:null),L=BA_LN[k];
  return `<button type="button" class="fupko" data-bbpk="${k}" aria-current="${BA_CAT===k}"><span class="ic" aria-hidden="true">${L[0]}</span><span class="t">${esc(L[1])}</span><span class="s"><span class="bbbadge ${st.cls}">${st.e} ${st.t}</span> <span class="ds">${esc(L[3])}</span></span><span class="n">${nf(c.E)}<small>ค้างปลาย${baUnit()}</small></span></button>`;};
 const bg=document.createElement('div');bg.className='fupk-bg';bg.id='bbpk';
 bg.innerHTML=`<div class="fupk" role="dialog" aria-modal="true" aria-labelledby="bbpkh"><h3 id="bbpkh">จะดูความคืบหน้าหมวดไหน?</h3><p class="sub">${esc(baLab(s))}${CH==='all'?' · ทุกช่องทาง':' · '+BA_CHN[CH]} — เปลี่ยนหมวดได้ทุกเมื่อจากปุ่ม “หมวด” ด้านบน</p>${['all'].concat(BA_LS).map(opt).join('')}<div class="foot"><span>ป้าย = เทียบกับ${baPrevLab(1)}</span><button type="button" class="fupkx" data-bbpkx="1">ปิด</button></div></div>`;
 document.body.appendChild(bg);
 const close=()=>{bg.remove();document.removeEventListener('keydown',kd);};const kd=e=>{if(e.key==='Escape')close();};
 document.addEventListener('keydown',kd);bg.addEventListener('click',e=>{if(e.target===bg)close();});
 bg.querySelector('[data-bbpkx]').addEventListener('click',close);
 bg.querySelectorAll('[data-bbpk]').forEach(b=>b.addEventListener('click',()=>{BA_CAT=b.dataset.bbpk;try{localStorage.setItem('bp_ba_cat',BA_CAT);}catch(e){}BA_SRC=false;BA_SB='';BA_SC='';BA_PG=0;close();renderBA();}));
 const f=bg.querySelector('.fupko[aria-current="true"]')||bg.querySelector('.fupko');if(f&&f.focus)f.focus();}
function baCal(){const C=BA_CAL;if(!C)return '';const last=baMaxDay(),y=+C.m.slice(0,4),mo=+C.m.slice(5,7)-1;
 const k1=Math.round((Date.UTC(y,mo,1)-BA.t0)/864e5),nd=new Date(Date.UTC(y,mo+1,0)).getUTCDate(),lead=(baDt(k1).getUTCDay()+6)%7;
 const ka=C.a?baK(C.a):null,kb=C.b?baK(C.b):ka;let cells='';for(let i=0;i<lead;i++)cells+='<span></span>';
 for(let d=1;d<=nd;d++){const k=k1+d-1,dis=k<0||k>last,inr=ka!=null&&k>=Math.min(ka,kb)&&k<=Math.max(ka,kb),edge=k===ka||k===kb;
  cells+=`<button type="button" class="d${inr?' in':''}${edge?' edge':''}"${dis?' disabled':''} data-bb="cald|${baYmd(k)}">${d}</button>`;}
 const pre=[['7','7 วันล่าสุด'],['14','14 วันล่าสุด'],['30','30 วันล่าสุด'],['tm','เดือนนี้'],['lm','เดือนที่แล้ว'],['ytd','ตั้งแต่ต้นปี']].map(x=>`<button type="button" class="chip" data-bb="calp|${x[0]}">${x[1]}</button>`).join('');
 return `<div class="bbpop" id="bbcal" role="dialog" aria-label="เลือกช่วงวันที่"><div class="pre">${pre}</div>
  <div class="calh"><button type="button" data-bb="calm|-1"${k1>0?'':' disabled'} aria-label="เดือนก่อน">‹</button><b>${BA_TH_MF[mo]} ${y}</b><button type="button" data-bb="calm|1"${k1+nd<=last?'':' disabled'} aria-label="เดือนถัดไป">›</button></div>
  <div class="calg"><span class="w">จ</span><span class="w">อ</span><span class="w">พ</span><span class="w">พฤ</span><span class="w">ศ</span><span class="w">ส</span><span class="w">อา</span>${cells}</div>
  <div class="calf"><span class="nsm">${C.a?'เลือก: '+baDM(Math.min(ka,kb))+(kb!==ka?' – '+baDM(Math.max(ka,kb)):'')+(C.b?'':' · กดวันสุดท้าย'):'กดวันแรก แล้วกดวันสุดท้าย'}</span><button type="button" class="chip" data-bb="calx">ยกเลิก</button><button type="button" class="bbok" data-bb="calok"${C.a?'':' disabled'}>ใช้ช่วงนี้</button></div></div>`;}
function baBar(s){const L=BA_LN[BA_CAT];let pick='';
 if(BA_M==='w'){const W=baWeeks().slice().reverse(),last=baMaxDay();pick=`<select class="bbselw" data-bbsel="w" aria-label="เลือกสัปดาห์">${W.map(w=>`<option value="${w.a}|${w.b}"${w.a===s.a?' selected':''}>${esc((baK(w.b)>last?'สัปดาห์นี้ · ':'')+baLab(w,'w'))}</option>`).join('')}</select>`;}
 else if(BA_M==='m'){const M=baMonths().slice().reverse();pick=`<select class="bbselw" data-bbsel="m" aria-label="เลือกเดือน">${M.map(m=>`<option value="${m.a}|${m.b}"${m.a===s.a?' selected':''}>${esc(baLab(m,'m'))}</option>`).join('')}</select>`;}
 else pick=`<div class="bbcalw"><button type="button" class="bbcalb" data-bb="cal" aria-expanded="${!!BA_CAL}">📅 ${esc(baLab(s,'c'))} ▾</button>${baCal()}</div>`;
 return `<div class="bbbar"><button type="button" class="bbcatb" data-bb="pick" aria-haspopup="dialog"><span class="lab">หมวด</span><span class="cv">${L[0]} ${esc(L[2])}</span><span aria-hidden="true">▾</span></button>
  <div class="bbper"><div class="seg" role="group" aria-label="ช่วงเวลา"><button type="button" data-bb="m|w" aria-pressed="${BA_M==='w'}">รายสัปดาห์</button><button type="button" data-bb="m|m" aria-pressed="${BA_M==='m'}">รายเดือน</button><button type="button" data-bb="m|c" aria-pressed="${BA_M==='c'}">กำหนดเอง</button></div>${pick}</div></div>`;}
/* ---------- page ---------- */
function baNotes(s,v){const n=[];
 for(const c of v.miss)n.push(`${BA_CHN[c]} ยังไม่มีข้อมูลช่วงนี้ (ข้อมูลถึง ${baEndTxt(c)}) — ไม่รวมในตัวเลข`);
 for(const c of v.part)if(BA.ch[c].lastDay<baMaxDay())n.push(`${BA_CHN[c]} นับถึง ${baEndTxt(c)} (ข้อมูลช่องทางนี้อัปเดตช้ากว่า)`);
 for(const l of (BA_CAT==='all'?BA_LS:[BA_CAT]))if(BA_FROM[l]&&baK(s.a)<baK(BA_FROM[l]))n.push(`${BA_LN[l][0]} ${BA_LN[l][2]} เริ่มนับ 19 ส.ค. 2026 (วันที่ทีมเริ่มนับ “แนบตัวอย่าง”) — ก่อนหน้านั้นหมวดนี้ยังไม่มีแชท`);
 if((BA_CAT==='pz'||BA_CAT==='all')&&baK(s.a)<baK('2026-08-19'))n.push('🧾 ก่อน 19 ส.ค. หมวดนี้รวมแชทที่ได้ตัวอย่างชุดเก่าด้วย (ระบบเริ่มแยกตัวอย่างวันที่ 19 ส.ค.)');
 return n;}
function baHero(c,u){const tot=Math.max(1,c.S+c.N);
 return `<div class="bbflow"><button type="button" class="bbfk" data-bb="srcb|S"><span class="lab">ก่อน · ค้างต้น${u}</span><b>${nf(c.S)}</b><span class="s">+ เข้าใหม่ ${nf(c.N)}</span></button><span class="arr" aria-hidden="true">→</span>
  <button type="button" class="bbfk mid" data-bb="srcb|"><span class="lab">แอดมินจัดการ</span><b>${nf(c.h)}</b><span class="s">✅ ${nf(c.done)} · ✋ ${nf(c.act)}</span></button><span class="arr" aria-hidden="true">→</span>
  <button type="button" class="bbfk end" data-bb="srcb|E"><span class="lab">หลัง · ค้างปลาย${u}</span><b>${nf(c.E)}</b><span class="s">${c.E===c.S?'เท่าเดิม':(c.E<c.S?'▼ '+nf(c.S-c.E):'▲ '+nf(c.E-c.S))}</span></button></div>
  <div class="wkbar" role="img" aria-label="${BA_BK.map(b=>BA_BN[b]+' '+c[b]).join(' · ')}">${BA_BK.map(b=>c[b]?`<i class="${b}" style="width:${Math.round(c[b]/tot*1000)/10}%"></i>`:'').join('')}</div>
  <div class="bblegend">${BA_BK.filter(b=>c[b]).map(b=>`<button type="button" class="chip wkb-${b}" data-bb="srcb|${b}"><b>${nf(c[b])}</b> ${BA_BN[b]}</button>`).join('')}</div>`;}
function baCatsGrid(s,p){return `<div class="bbcats">${BA_LS.map(l=>{const c=baRange(s,l).c,st=baStatus(c,p?baRange(p,l).c:null),tr=baTrendData(s,l).slice(-8);
  const sp=tr.map(x=>`<i class="${x.s.a===s.a?'on':''}" style="height:${x.pct==null?3:Math.max(5,x.pct)}%"></i>`).join('');
  return `<button type="button" class="bbcat ${st.cls}" data-bb="cat|${l}"><span class="h"><span class="ic">${BA_LN[l][0]}</span><span class="t">${esc(BA_LN[l][2])}</span></span>
   <span class="bbbadge ${st.cls}">${st.e} ${st.t}</span><span class="n">${nf(c.S)} → <b>${nf(c.E)}</b></span><span class="p">จัดการ ${c.pct==null?'—':c.pct+'%'} · แตะใหม่ ${baDays(c.med)}</span><span class="spk" aria-hidden="true">${sp}</span></button>`;}).join('')}</div>`;}
function baChTable(v){if(CH!=='all')return '';const rows=Object.keys(v.chs).map(ch=>{const c=baCount(v.rows.filter(o=>o.ch===ch));
  return `<tr><td>${BA_CHI[ch]} ${BA_CHN[ch]}${v.part.includes(ch)?' <span class="nsm">ถึง '+baEndTxt(ch)+'</span>':''}</td><td class="n">${nf(c.S)}</td><td class="n">${nf(c.N)}</td><td class="n ok">${nf(c.done)}</td><td class="n act">${nf(c.act)}</td><td class="n warnc">${nf(c.cus)}</td><td class="n bad">${nf(c.none)}</td><td class="n"><b>${nf(c.E)}</b></td><td class="n">${c.pct==null?'—':c.pct+'%'}</td><td class="n">${baDays(c.med)}</td></tr>`;}).join('');
 return `<details class="fhelp bbdet"><summary>ตัวเลขแยกช่องทาง</summary><div class="tw" style="margin-top:8px"><table class="wkt bbtab"><thead><tr><th>ช่องทาง</th><th>ค้างต้นช่วง</th><th>เข้าใหม่</th><th>✅</th><th>✋</th><th>💬</th><th>⏳</th><th>ค้างปลายช่วง</th><th>จัดการ</th><th>แตะใหม่</th></tr></thead><tbody>${rows}</tbody></table></div></details>`;}
let BA_NK=(()=>{const d=new Date().getDay();return d>=1&&d<=4?'mon':'fri';})(), BA_NOPEN=false;
function baNoticeBox(){const N=BA&&BA.notice,hd='<summary>ข้อความแจ้งเตือนเข้า LINE กลุ่ม · จันทร์ / ศุกร์</summary>';
 if(!N||!N.mon)return `<details class="fhelp bbdet">${hd}<p class="nsm">ตัวอย่างข้อความจะขึ้นหลังรอบอัปเดตเช้า</p></details>`;
 const D=N[BA_NK]||N.mon,M=D.msgs||{};
 const tabs=[['mon','จันทร์ · สรุปสัปดาห์ก่อน',N.mon],['fri','ศุกร์ · ความคืบหน้าสัปดาห์นี้',N.fri]].filter(x=>x[2]).map(x=>`<button type="button" class="chip" data-bb="nk|${x[0]}" aria-pressed="${BA_NK===x[0]}">${x[1]} <b>${esc(x[2].lab)}</b></button>`).join('');
 const boxes=BA_CH.filter(c=>M[c]).map(c=>`<div class="bbnt"><div class="h"><b>${BA_CHI[c]} ${BA_CHN[c]}</b><button type="button" class="chip" data-bb="ncopy|${c}">คัดลอก</button></div><pre class="wkrep">${esc(M[c])}</pre></div>`).join('');
 return `<details class="fhelp bbdet"${BA_NOPEN?' open':''} id="bbntd">${hd}<p class="nsm" style="margin:6px 0">แยก Facebook / Instagram / LINE OA เป็น 3 ข้อความ · ส่งอัตโนมัติทุกวันจันทร์และศุกร์หลังรอบอัปเดตเช้า (เมื่อตั้งค่าบอท LINE แล้ว) · ตัวอย่างนี้คำนวณเมื่อ ${esc(fuDay(N.built)+' '+String(N.built).slice(11,16))} น.</p><div class="fl" style="display:flex;flex-wrap:wrap;gap:6px;margin:6px 0">${tabs}</div><div class="bbnts">${boxes}</div></details>`;}
function baHelp(){return `<details class="fhelp bbdet"><summary>นับอย่างไร</summary><dl>
 <dt>หมวด</dt><dd>5 หมวดเดียวกับหน้า Follow up · 🤖 บอทตอบ = ลูกค้าได้แต่ข้อความอัตโนมัติ ค้าง 7 วันขึ้นไป · อีก 4 หมวด = แชทที่รอ 1–89 วัน · 🎬🗨️💸 เริ่มนับ 19 ส.ค. 2026 ตามกติกาทีม (นับ “แนบตัวอย่าง” ตั้งแต่วันนั้น)</dd>
 <dt>ก่อน · หลัง</dt><dd>ระบบอ่านแชทจริงทุกห้องย้อนหลังทีละวัน (ตัดที่เที่ยงคืน) ตั้งแต่ 1 ม.ค. 2026 ด้วยกฎเดียวกับรายการ Follow up · ก่อน = อยู่ในรายการตอน 00:00 ของวันแรก · หลัง = ยังอยู่ตอน 24:00 ของวันสุดท้าย (หรือเวลาข้อมูลล่าสุด)</dd>
 <dt>✅ เคลียร์แล้ว · ✋ ตอบ/ตามแล้ว</dt><dd>✅ ขยับไปขั้นถัดไปหรือจบ (แอดมินตอบ · ส่งตัวอย่าง · ส่งสรุปยอด · โอนแล้ว · ลูกค้าปิดท้ายเอง) · ✋ แอดมิน (คน ไม่ใช่บอท) พิมพ์ในแชทหรือกดปุ่มในหน้า Follow up แต่ยังอยู่ขั้นเดิม</dd>
 <dt>💬 · ⏳</dt><dd>💬 ลูกค้าทักกลับแล้วยังไม่มีแอดมินตอบ (ไม่นับเป็นเคลียร์) · ⏳ อยู่ในรายการถึงปลายช่วงโดยไม่มีแอดมินพิมพ์เลย</dd>
 <dt>เคลียร์ได้ดีขึ้นไหม</dt><dd>แอดมินจัดการ = (✅ + ✋) ÷ (ค้างต้นช่วง + เข้าใหม่ − คัดออก − หมดอายุ) · เทียบกับช่วงก่อนหน้าที่ยาวเท่ากัน · ต่างกัน 5 จุดขึ้นไปจึงนับว่าดีขึ้น/แย่ลง</dd>
 <dt>แชทค้างลดลงไหม</dt><dd>ค้างปลายช่วงเทียบกับค้างต้นช่วง — ลดลง = แอดมินจัดการได้มากกว่าแชทที่เข้ามาใหม่</dd>
 <dt>ตอบเร็วขึ้นไหม</dt><dd>แชทที่เข้ารายการระหว่างช่วง แอดมินเข้าไปแตะ (พิมพ์ในแชทหรือกดปุ่ม) หลังเข้ารายการกี่วัน · ค่ากลางของแชทที่แตะแล้ว · เร็วขึ้น/ช้าลงครึ่งวันขึ้นไปจึงนับ</dd>
 <dt>ป้ายสถานะ</dt><dd>นับ 3 ข้อด้านบน: ดีขึ้น +1 · แย่ลง −1 → รวม 2–3 = 🎉 ดีขึ้นชัดเจน · 1 = 👍 ดีขึ้น · 0 = ➖ ทรงตัว · ติดลบ = 💪 ต้องเร่งอีกนิด</dd>
 <dt>อัปเดต</dt><dd>Facebook + Instagram ทุกเช้า (ขึ้นเว็บราว 09:00–10:00 น.) · LINE OA ตามรอบที่ดึงข้อมูล LINE · ปุ่มที่กดในหน้า Follow up หลังรอบอัปเดตนับทันที${BA&&BA.built?' · ชุดนี้คำนวณเมื่อ '+fuDay(BA.built)+' '+BA.built.slice(11,16)+' น.':''}</dd></dl></details>`;}
function renderBA(){
 const el=$('#ba'),sc=$('#bascope');if(!el)return;
 if((!FU&&!FU_ERR)||(!BA&&!BA_ERR)){el.innerHTML='<div class="empty">กำลังโหลดข้อมูล…</div>';Promise.all([admFU(),baLoad()]).then(()=>{if(VIEW==='ba')renderBA();});return;}
 if(!BA){el.innerHTML=`<div class="empty">${BA_ERR==='nodata'?'ข้อมูลรายวันชุดใหม่ (ตั้งแต่ ม.ค.) จะขึ้นหลังรอบอัปเดตเช้ารอบถัดไป':'โหลดข้อมูลไม่สำเร็จ ('+esc(BA_ERR)+')'}</div>`;return;}
 if(!baChs().length){el.innerHTML='<div class="empty">ช่องทางนี้ยังไม่มีข้อมูล</div>';return;}
 if(!BA_LN[BA_CAT])BA_CAT='all';
 const s=baSel();if(!s){el.innerHTML='<div class="empty">ยังไม่มีข้อมูลในช่วงที่นับ</div>';return;}
 const p=baPrevSel(s),v=baRange(s,BA_CAT),pv=p?baRange(p,BA_CAT):null,c=v.c,pc=pv?pv.c:null,u=baUnit();
 if(BA_SC&&!v.chs[BA_SC])BA_SC='';
 const st=baStatus(c,pc),pts=baTrendData(s,BA_CAT),ci=pts.findIndex(x=>x.s.a===s.a),rec=baRecords(pts,ci),notes=baNotes(s,v);
 sc.textContent=CHN[CH]+' · '+BA_LN[BA_CAT][2]+' · '+baLab(s);
 const tiles=st.it.map(x=>`<div class="bbt ${p?baTC(x.s):'eq'}"><span class="lab">${x.lab}</span><b>${x.v}</b><span class="d">${p||x.own?(x.d||''):''}</span>${p&&x.d?`<span class="tag">${baTI(x.s)}</span>`:''}<span class="s">${esc(x.sub)}</span></div>`).join('');
 const status=`<section class="bbst ${st.cls}" aria-label="สถานะ"><div class="bbsth"><span class="bbbadge big ${st.cls}">${st.e} ${st.t}</span><span class="vs">${p?'เทียบกับ'+baPrevLab(p)+' ('+esc(baLab(p,BA_M==='m'?'c':BA_M))+')':'ยังไม่มีช่วงก่อนหน้าให้เทียบ'}</span></div>
  <p class="bbhl">${esc(baHead(c,pc,st,u==='ช่วง'?'ช่วงนี้':u+'นี้'))}</p><div class="bbtiles">${tiles}</div>${rec.length?`<div class="bbrec">${rec.map(x=>`<span>${x}</span>`).join('')}</div>`:''}</section>`;
 const tn=BA_M==='m'?'เดือน':'สัปดาห์',own=BA_M==='c'?{pct:c.pct,E:c.E,med:c.med}:null;
 const charts=`<h3 class="bbh3">แนวโน้มราย${tn} <span class="nsm">${BA_M==='c'?'สัปดาห์ที่อยู่ในช่วงที่เลือก':(BA_M==='m'?'ตั้งแต่ ม.ค.':'12 สัปดาห์ล่าสุด')} · แท่งเข้ม = ช่วงที่เลือก · กดแท่งเพื่อดู${tn}นั้น</span></h3><div class="bbcharts">
  ${baChart(pts,s,'แอดมินจัดการ (% ของงาน)',baFpct,x=>Math.round(x)+'%',100,false,'',own)}
  ${baChart(pts,s,'แชทค้าง ณ ปลาย'+tn,baFE,x=>nf(Math.round(x)),0,true,'',own)}
  ${baChart(pts,s,'แตะแชทใหม่ภายใน (วัน)',baFmed,x=>(Math.round(x*10)/10)+' วัน',0,true,'ค่ากลางของแชทเข้าใหม่ · แท่งเตี้ย = เร็ว',own)}</div>`;
 el.innerHTML=baBar(s)+(notes.length?`<div class="bbwarn">${notes.map(esc).join('<br>')}</div>`:'')+status+
  `<h3 class="bbh3">ก่อน → หลัง <span class="nsm">${esc(baLab(s))} · กดตัวเลขเพื่อดูรายชื่อแชท</span></h3>`+baHero(c,u)+
  (BA_CAT==='all'?`<h3 class="bbh3">แยกหมวด <span class="nsm">กดการ์ดเพื่อดูหมวดนั้น · แท่งเล็ก = % จัดการ 8 ${tn}ล่าสุด</span></h3>${baCatsGrid(s,p)}`:'')+
  charts+baSrc(s,v)+baChTable(v)+
  baNoticeBox()+baHelp();
 baBind(el);
 if(BA_ASK){BA_ASK=false;baCatPicker();}}
function baGo(){BA_PG=0;BA_SB='';renderBA();}
function baTip(t){let tip=document.getElementById('bbtip');if(!t){if(tip)tip.hidden=true;return;}
 if(!tip){tip=document.createElement('div');tip.id='bbtip';tip.className='bbtip';document.body.appendChild(tip);}
 tip.textContent=t.dataset.tip;tip.hidden=false;const r=t.getBoundingClientRect();
 tip.style.left=Math.max(8,Math.min(window.innerWidth-tip.offsetWidth-8,r.left+r.width/2-tip.offsetWidth/2))+'px';tip.style.top=(r.top+window.scrollY-tip.offsetHeight-6)+'px';}
function baBind(el){
 const act=t=>{const a=(t.dataset.bb||'').split('|'),k=a[0];
  if(k==='pick'){baCatPicker();return;}
  if(k==='cat'){BA_CAT=a[1];try{localStorage.setItem('bp_ba_cat',BA_CAT);}catch(e){}BA_SRC=false;baGo();try{window.scrollTo({top:Math.max(0,el.getBoundingClientRect().top+window.scrollY-120),behavior:'smooth'});}catch(e){}return;}
  if(k==='m'){if(BA_M===a[1])return;const cur=baSel();BA_M=a[1];try{localStorage.setItem('bp_ba_m',BA_M);}catch(e){}BA_A='';BA_B='';BA_CAL=null;
   if(BA_M==='c'&&cur){BA_A=cur.a;BA_B=baYmd(Math.min(baK(cur.b),baMaxDay()));}baGo();return;}
  if(k==='k'){BA_A=a[1];BA_B=a[2];BA_CAL=null;baGo();return;}
  if(k==='cal'){if(BA_CAL)BA_CAL=null;else{const s=baSel();BA_CAL={m:(s?s.b:baYmd(baMaxDay())).slice(0,7),a:s?s.a:null,b:s?s.b:null};}renderBA();return;}
  if(k==='calm'){const y=+BA_CAL.m.slice(0,4),m=+BA_CAL.m.slice(5,7)-1+(+a[1]),d=new Date(Date.UTC(y,m,1));BA_CAL.m=d.getUTCFullYear()+'-'+String(d.getUTCMonth()+1).padStart(2,'0');renderBA();return;}
  if(k==='cald'){const d=a[1];if(!BA_CAL.a||BA_CAL.b){BA_CAL.a=d;BA_CAL.b=null;}else if(d<BA_CAL.a){BA_CAL.b=BA_CAL.a;BA_CAL.a=d;}else BA_CAL.b=d;renderBA();return;}
  if(k==='calp'){const last=baMaxDay(),L=baDt(last);let ka,kb=last;
   if(a[1]==='tm')ka=Math.round((Date.UTC(L.getUTCFullYear(),L.getUTCMonth(),1)-BA.t0)/864e5);
   else if(a[1]==='lm'){ka=Math.round((Date.UTC(L.getUTCFullYear(),L.getUTCMonth()-1,1)-BA.t0)/864e5);kb=Math.round((Date.UTC(L.getUTCFullYear(),L.getUTCMonth(),1)-BA.t0)/864e5)-1;}
   else if(a[1]==='ytd')ka=0;else ka=last-(+a[1])+1;
   BA_A=baYmd(Math.max(0,ka));BA_B=baYmd(kb);BA_CAL=null;baGo();return;}
  if(k==='calok'){if(!BA_CAL.a)return;BA_A=BA_CAL.a;BA_B=BA_CAL.b||BA_CAL.a;BA_CAL=null;baGo();return;}
  if(k==='calx'){BA_CAL=null;renderBA();return;}
  if(k==='src'){BA_SRC=true;BA_SB='';BA_PG=0;renderBA();baScrollSrc();return;}
  if(k==='srcb'){BA_SRC=true;BA_SB=a[1]||'';BA_PG=0;BA_SQ='';renderBA();baScrollSrc();return;}
  if(k==='srcx'){BA_SRC=false;BA_SB='';BA_SC='';BA_SQ='';renderBA();return;}
  if(k==='sb'){BA_SB=a[1];BA_PG=0;renderBA();return;}
  if(k==='sc'){BA_SC=a[1];BA_PG=0;renderBA();return;}
  if(k==='pg'){BA_PG=Math.max(0,+a[1]||0);baSrcOnly();baScrollSrc();return;}
  if(k==='csv'){const s=baSel();if(s)baCSV(s,baRange(s,BA_CAT));return;}
  if(k==='nk'){BA_NK=a[1];BA_NOPEN=true;const d=el.querySelector('#bbntd');if(d)d.outerHTML=baNoticeBox();return;}
  if(k==='ncopy'){const N=BA.notice||{},t2=((N[BA_NK]||{}).msgs||{})[a[1]]||'';toast(t2&&copyText(t2)?'คัดลอกข้อความ '+BA_CHN[a[1]]+' แล้ว':'คัดลอกไม่สำเร็จ');return;}};
 el.onclick=e=>{const t=e.target.closest('[data-bb]');if(!t||!el.contains(t)||t.disabled)return;e.preventDefault();baTip(null);act(t);};
 el.onchange=e=>{const t=e.target.closest('[data-bbsel]');if(!t)return;const [a,b]=t.value.split('|');BA_A=a;BA_B=b;baGo();};
 el.onmouseover=e=>baTip(e.target.closest('[data-tip]'));
 el.onmouseleave=()=>baTip(null);
 const q=el.querySelector('#bbq');if(q){let h=null;q.addEventListener('input',()=>{clearTimeout(h);h=setTimeout(()=>{BA_SQ=q.value;BA_PG=0;baSrcOnly();},200);});}}
function baScrollSrc(){const s=document.getElementById('bbsrc');if(s&&s.scrollIntoView)s.scrollIntoView({behavior:'smooth',block:'start'});}
function baSrcOnly(){const s=baSel(),box=document.getElementById('bbsrcl');if(!s||!box)return;box.innerHTML=baSrcList(baRange(s,BA_CAT));}

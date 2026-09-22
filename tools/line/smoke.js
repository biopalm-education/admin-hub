// jsdom smoke test of the BUILT site in pages/: signs in, loops LINE / all / FB x every month, fails on JS errors or undefined/NaN.
// node tools/line/smoke.js pages secret.txt   (needs: npm i jsdom@24)
const fs=require('fs'),path=require('path');const {JSDOM,VirtualConsole}=require('jsdom');
const ROOT=process.argv[2]||'pages'; const [U,P]=fs.readFileSync(process.argv[3]||'secret.txt','utf8').trim().split(':');
const errs=[]; const vc=new VirtualConsole(); vc.on('jsdomError',e=>errs.push(String(e.message||e).slice(0,200)));
const dom=new JSDOM(fs.readFileSync(path.join(ROOT,'index.html'),'utf8'),{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,url:'https://x/admin-hub/',beforeParse(w){
 Object.defineProperty(w,'crypto',{value:require('crypto').webcrypto});
 w.TextEncoder=TextEncoder; w.TextDecoder=TextDecoder; w.DecompressionStream=DecompressionStream; w.Blob=Blob; w.Response=Response;
 w.fetch=async(u)=>{u=String(u).replace(/^https?:\/\/x\/admin-hub\//,'').replace(/^\.\//,'').split('?')[0]; return new Response(fs.readFileSync(path.join(ROOT,u)),{status:200});};
 w.scrollTo=()=>{}; w.matchMedia=()=>({matches:false,addEventListener(){},addListener(){}}); }});
const w=dom.window,d=w.document; const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{ await sleep(500); d.querySelector('#gu').value=U; d.querySelector('#gp').value=P; d.querySelector('#gb').click();
 for(let i=0;i<60&&!w.eval('typeof AGG!=="undefined"&&AGG');i++) await sleep(500);
 const bad=[]; let n=0;
 for(const ch of ['line','all','fb']){ d.querySelector(`button[data-ch="${ch}"]`).click(); await sleep(800); const sel=d.querySelector('#msel');
  for(const v of [...sel.options].map(o=>o.value)){ sel.value=v; sel.dispatchEvent(new w.Event('change',{bubbles:true})); await sleep(ch==='line'?1500:400); n++;
   const cl=d.body.cloneNode(true); cl.querySelectorAll('script,style,template').forEach(e=>e.remove()); const m=cl.textContent.match(/.{0,40}(undefined|NaN).{0,40}/); if(m) bad.push([ch,v,m[0]]); } }
 console.log(JSON.stringify({combos:n,bad,errs:errs.slice(0,5)})); process.exit(bad.length||errs.length?1:0); })();

"""workbench HTML 템플릿 — 서버가 데이터(payload)를 주입하는 순수 렌더러.

_inspector_html.py 관례: 템플릿은 이 모듈, 데이터 주입(__WB__ 등 치환)은 서버.
워크벤치 페이지의 다이얼/퍼널/픽 JS 는 scratchpad_workbench.py v0.1 (2026-07-22,
단일-클립 탭 뷰) 이식 — **의미론(pass/funnel/score/picks·DEF)은 파이썬
workbench.compute_picks / DEFAULT_CFG 와 문자 그대로 동일해야 한다**(로드 시
셀프테스트가 이 짝을 감시). v0.1 대비 서버판 변경: data.js → const WB 인라인 ·
GT 클릭 = POST /api/gt 즉시 저장(로드 시 서버 GT 복원, export 는 백업용) ·
썸네일 src 절대경로(/thumbs/...).
"""

# ── 워크벤치 뷰 (/wb?clips=a,b) — __WB__·__GT0__·__CORPUS__ 치환 ─────────────
WORKBENCH_PAGE = r"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><title>likeness sampling workbench</title>
<style>
body{background:#161616;color:#ddd;font:13px/1.45 system-ui,sans-serif;margin:0}
#top{position:sticky;top:0;background:#1d1d1d;border-bottom:1px solid #333;padding:8px 14px;z-index:9}
#selftest{font-weight:600}
.ok{color:#7c6} .bad{color:#e66}
#panel{position:fixed;left:0;top:78px;bottom:0;width:270px;overflow:auto;background:#1b1b1b;
  border-right:1px solid #333;padding:10px 14px;box-sizing:border-box}
#main{margin-left:270px;padding:10px 16px}
.grp{margin:10px 0 4px;color:#9ad;font-weight:600;font-size:12px;text-transform:uppercase}
.dial{margin:6px 0}
.dial label{display:flex;justify-content:space-between;font-size:12px;color:#bbb}
.dial.mod label{color:#fc6}
.dial.mod label::after{content:" •"}
.dial input[type=range]{width:100%}
#tabs{display:flex;gap:6px;flex-wrap:wrap;margin:4px 0 10px}
.tab{padding:4px 10px;border:1px solid #444;border-radius:4px;cursor:pointer;font-size:12px;color:#aaa}
.tab.cur{background:#28343f;color:#dfeaf5;border-color:#6a92b8}
.tab .b{color:#9a8} .tab .g{color:#cb8}
.funnel{margin:6px 0 10px;max-width:560px}
.fr{display:flex;align-items:center;gap:8px;font-size:11px;color:#9a8;margin:1px 0}
.fr .lbl{width:44px;text-align:right;color:#8b9}
.fr .bar{height:9px;background:#3f6b52;border-radius:2px}
.fr.last .bar{background:#6fae7c}
.fr .cnt{color:#bcb}
.rowlbl{color:#89b;font-size:11px;margin-top:12px}
.strip{display:flex;gap:6px;flex-wrap:wrap;margin:4px 0}
.cell{position:relative;cursor:pointer}
.strip.sm .cell,.strip.sm .cell img,.strip.sm .cell .noimg{width:112px}
.strip.sm .cell img,.strip.sm .cell .noimg{height:112px}
.strip.big .cell,.strip.big .cell img,.strip.big .cell .noimg{width:224px}
.strip.big .cell img,.strip.big .cell .noimg{height:224px}
.cell img{display:block;border:2px solid #444;box-sizing:border-box;transition:transform .07s}
.strip.sm .cell:hover img{transform:scale(2);position:relative;z-index:8;border-color:#9cf}
.strip.big .cell:hover img{transform:scale(1.4);position:relative;z-index:8;border-color:#9cf}
.cell .noimg{border:2px dashed #444;box-sizing:border-box;display:flex;align-items:center;
  justify-content:center;color:#666;font-size:10px}
.cell .cap{font-size:10px;color:#aaa;line-height:1.25;margin-top:1px}
.cell.pos img,.cell.pos .noimg{border-color:#5c5}
.cell.neg img,.cell.neg .noimg{border-color:#e55}
.cell .flag{position:absolute;top:2px;right:2px;font-size:12px;color:#fff;text-shadow:0 0 3px #000}
.pickA img{outline:2px solid #7ac} .pickB img{outline:2px dashed #ca7}
.diff img{outline-color:#f80 !important}
button{background:#2a2a2a;color:#ddd;border:1px solid #555;border-radius:3px;
  padding:3px 10px;margin-right:6px;cursor:pointer}
button:hover{background:#383838}
a{color:#8ab}
.gtscore{color:#cb8;font-size:12px;margin-left:12px}
.gterr{color:#e66;font-size:12px;margin-left:12px}
.note{color:#777;font-size:11px}
</style></head><body>
<div id="top">
 <a href="/">≡ 목록</a>
 <span id="selftest">selftest…</span>
 <button onclick="snapshotB()">현재 설정 → B 저장</button>
 <button onclick="clearB()">B 지우기</button>
 <button onclick="resetA()">A 기본값(v7.2)</button>
 <button onclick="exportGT()">GT export (.jsonl)</button>
 <input type="file" id="gtfile" style="display:none" onchange="importGT(this)">
 <button onclick="document.getElementById('gtfile').click()">GT import</button>
 <span class="gtscore" id="gtscore"></span><span class="gterr" id="gterr"></span>
 <div class="note">클릭=GT 깃발(없음→긍정→부정, 서버 즉시 저장 → fixtures/eval) · 호버=확대 · ←→=클립 전환 · 주황 외곽=A/B 불일치 픽</div>
</div>
<div id="panel"></div><div id="main"></div>
<script>
const WB=__WB__;
const GT0=__GT0__;
const CORPUS=__CORPUS__;
const DIALS=[
 ["1단 · 품질 스크린 (결정경계)"],
 ["sym_max","보이는-정면 sym <",0.3,2.0,0.05],
 ["dev_max","|yaw dev| <",5,45,1],
 ["pu_min","눈동자 pupil >=",0,0.8,0.01],
 ["cs_min","정체성 cs pct >=",0,90,5],
 ["mv_min","입-가시 mv pct >=",0,90,5],
 ["lt_min","조도·생동 lt pct >=",0,90,5],
 ["ex_max","표정 ex <= (상한)",0.2,1.0,0.05],
 ["2단 · 대표성 랭킹 (깃발)"],
 ["w_expr","w 무표정",0,0.6,0.05],
 ["w_pu","w 눈동자",0,0.6,0.05],
 ["w_q3","w 품질3축",0,0.6,0.05],
 ["w_vis2","w 판독성·입",0,0.6,0.05],
 ["w_light","w 조도·생동",0,0.6,0.05],
 ["시간 다양성"],
 ["gap_min","픽 간 최소 프레임 gap",0,60,2],
];
const DEF={sym_max:0.6,dev_max:15,pu_min:0.4,cs_min:0,mv_min:0,lt_min:0,ex_max:1.0,gap_min:12,
           w_expr:0.30,w_pu:0.15,w_q3:0.20,w_vis2:0.15,w_light:0.20};
let A={...DEF}, Bcfg=null, GT={}, cur=0, sortMode="time";
for(const o of GT0){if((o.role||"center")=="center"&&(o.flag=="pos"||o.flag=="neg")
 &&o.corpus==CORPUS)GT[o.clip+":"+o.frame]=o.flag;}

function pass(r,c){return r.sy<c.sym_max&&Math.abs(r.dv)<c.dev_max&&r.pu>=c.pu_min
 &&(r.cs==null||r.cs>=c.cs_min)&&(r.mv==null||r.mv>=c.mv_min)&&(r.lt==null||r.lt>=c.lt_min)
 &&r.ex<=c.ex_max;}
function funnel(rows,c){
 const s1=rows.filter(r=>r.sy<c.sym_max&&Math.abs(r.dv)<c.dev_max);
 const s2=s1.filter(r=>r.pu>=c.pu_min);
 const s3=s2.filter(r=>r.cs==null||r.cs>=c.cs_min);
 const s4=s3.filter(r=>r.mv==null||r.mv>=c.mv_min);
 const s5=s4.filter(r=>r.lt==null||r.lt>=c.lt_min);
 const s6=s5.filter(r=>r.ex<=c.ex_max);
 return [rows.length,s1.length,s2.length,s3.length,s4.length,s5.length,s6.length];}
function score(r,c){return c.w_expr*r.r[0]+c.w_pu*r.r[1]+c.w_q3*r.r[2]+c.w_vis2*r.r[3]+c.w_light*r.r[4];}
function picks(rows,c){
 const sv=rows.filter(r=>pass(r,c));
 sv.forEach(r=>r._s=score(r,c));
 sv.sort((a,b)=>b._s-a._s);
 const got=[];
 for(const r of sv){if(got.every(o=>Math.abs(r.f-o.f)>=c.gap_min))got.push(r);if(got.length==3)break;}
 return got.map(r=>r.f);}

function cellHTML(clip,r,cls){
 const k=clip+":"+r.f, fl=GT[k]||"";
 const img=r.th?`<img src="/${r.th}">`:`<div class="noimg">f${r.f}<br>(no thumb)</div>`;
 const cap=`f${r.f} ex${r.ex} pu${r.pu}<br>cs${r.cs==null?"--":r.cs} mv${r.mv==null?"--":r.mv} lt${r.lt==null?"--":r.lt}`;
 const mark=fl=="pos"?"O":fl=="neg"?"X":"";
 return `<div class="cell ${fl} ${cls||""}" onclick="cyc('${clip}',${r.f})">${img}
   <span class="flag">${mark}</span><div class="cap">${cap}</div></div>`;}

function funnelHTML(fn){
 const names=["전체","정면","눈동자","cs","입","빛","표정"];
 const mx=Math.max(fn[0],1);
 return `<div class="funnel">`+fn.map((v,i)=>
  `<div class="fr${i==6?" last":""}"><span class="lbl">${names[i]}</span>
   <span class="bar" style="width:${Math.max(2,Math.round(280*v/mx))}px"></span>
   <span class="cnt">${v}</span></div>`).join("")+
  (fn[6]<3?`<div class="fr"><span class="lbl"></span><span style="color:#e66">⚠ 풀&lt;3</span></div>`:``)+`</div>`;}

function render(){
 // 셀프테스트 + 탭 배지는 전 클립 계산 (표시만 단일 클립)
 let st_ok=true,st_msg=[],gtP=0,gtN=0,gtPB=0,gtNB=0;
 const isDef=JSON.stringify(A)==JSON.stringify(DEF);
 const meta=WB.clips.map(C=>{
  const pA=picks(C.rows,A), fn=funnel(C.rows,A);
  const pB=Bcfg?picks(C.rows,Bcfg):null;
  if(isDef){const same=JSON.stringify(pA.slice().sort((a,b)=>a-b))==JSON.stringify(C.selftest.slice().sort((a,b)=>a-b));
   if(!same){st_ok=false;st_msg.push(C.clip);}}
  pA.forEach(f=>{const g=GT[C.clip+":"+f];if(g=="pos")gtP++;if(g=="neg")gtN++;});
  if(pB)pB.forEach(f=>{const g=GT[C.clip+":"+f];if(g=="pos")gtPB++;if(g=="neg")gtNB++;});
  let p=0,ng=0;for(const k in GT){if(k.startsWith(C.clip+":")){GT[k]=="pos"?p++:ng++;}}
  return {pA,pB,fn,p,ng};});

 const tabs=WB.clips.map((C,i)=>
  `<span class="tab${i==cur?" cur":""}" onclick="cur=${i};render()">${C.clip}
   <span class="b">${meta[i].fn[6]}</span>${meta[i].p+meta[i].ng?`<span class="g"> +${meta[i].p}/−${meta[i].ng}</span>`:""}</span>`).join("");

 const C=WB.clips[cur], m=meta[cur];
 const byf={};C.rows.forEach(r=>byf[r.f]=r);
 const setA=new Set(m.pA), setB=m.pB?new Set(m.pB):null;
 let h=`<div id="tabs">${tabs}</div><b>${C.clip}</b> t${C.tid} <span class="note">n=${C.n} · 풀 정렬:</span>
  <button onclick="sortMode=sortMode=='time'?'score':'time';render()">${sortMode=='time'?'시간순':'점수순'}</button>`;
 h+=funnelHTML(m.fn);
 h+=`<div class="rowlbl">CURRENT (생산 likeness.json)</div><div class="strip sm">`+
   C.cur.map(f=>byf[f]?cellHTML(C.clip,byf[f],""):"").join("")+`</div>`;
 h+=`<div class="rowlbl">A 픽</div><div class="strip big">`+
   m.pA.map(f=>cellHTML(C.clip,byf[f],"pickA"+(setB&&!setB.has(f)?" diff":""))).join("")+`</div>`;
 if(m.pB)h+=`<div class="rowlbl">B 픽</div><div class="strip big">`+
   m.pB.map(f=>cellHTML(C.clip,byf[f],"pickB"+(!setA.has(f)?" diff":""))).join("")+`</div>`;
 const sv=C.rows.filter(r=>pass(r,A));
 sv.forEach(r=>r._s=score(r,A));
 const ordered=sortMode=="time"?sv.slice().sort((a,b)=>a.f-b.f):sv.slice().sort((a,b)=>b._s-a._s);
 const show=ordered.filter(r=>r.th).slice(0,96);
 h+=`<div class="rowlbl">생존 풀 (A, ${sv.length}행 중 썸네일 ${show.length} 표시 · ${sortMode=='time'?'시간순':'점수순'})</div>
  <div class="strip sm">`+show.map(r=>cellHTML(C.clip,r,"")).join("")+`</div>`;
 document.getElementById("main").innerHTML=h;

 const st=document.getElementById("selftest");
 if(isDef){st.textContent=st_ok?"selftest OK — JS ≡ python (기본 설정)":"selftest FAIL: "+st_msg.join(",");
  st.className=st_ok?"ok":"bad";}
 else{st.textContent="탐색 중 (기본 설정 아님 — selftest는 기본값에서만)";st.className="";}
 const tot=Object.keys(GT).length;
 document.getElementById("gtscore").textContent=
  tot?`GT ${tot}개 · A: +${gtP}/−${gtN}`+(Bcfg?` · B: +${gtPB}/−${gtNB}`:""):"";
 for(const d of DIALS){if(d.length==1)continue;const k=d[0];
  const el=document.getElementById("d_"+k);
  if(el)el.className="dial"+(A[k]!=DEF[k]?" mod":"");}
}
function postGT(row){
 return fetch("/api/gt",{method:"POST",headers:{"Content-Type":"application/json"},
   body:JSON.stringify(row)})
  .then(r=>{document.getElementById("gterr").textContent=r.ok?"":"GT 저장 실패 "+r.status;})
  .catch(e=>{document.getElementById("gterr").textContent="GT 저장 실패: "+e;});}
function cyc(clip,f){const k=clip+":"+f;GT[k]=GT[k]=="pos"?"neg":GT[k]=="neg"?undefined:"pos";
 if(!GT[k])delete GT[k];
 postGT({clip:clip,frame:f,role:"center",flag:GT[k]||null,corpus:CORPUS});
 render();}
function snapshotB(){Bcfg={...A};render();}
function clearB(){Bcfg=null;render();}
function resetA(){A={...DEF};buildPanel();render();}
function exportGT(){
 const lines=Object.entries(GT).map(([k,v])=>{const i=k.indexOf(":");
  return JSON.stringify({schema:"momentscan.workbench-gt/v0",clip:k.slice(0,i),frame:+k.slice(i+1),
    role:"center",flag:v,corpus:CORPUS,ts:new Date().toISOString()});});
 const blob=new Blob([lines.join("\n")+"\n"],{type:"application/jsonl"});
 const a=document.createElement("a");a.href=URL.createObjectURL(blob);
 a.download="workbench_gt.jsonl";a.click();}
function importGT(inp){const fr=new FileReader();fr.onload=async()=>{
 for(const l of fr.result.split("\n").filter(x=>x.trim())){
  try{const o=JSON.parse(l);
   if(o.flag&&o.clip!=null&&o.frame!=null){
    await postGT({clip:o.clip,frame:+o.frame,role:o.role||"center",flag:o.flag,
                  corpus:o.corpus||CORPUS,ts:o.ts});
    if((o.corpus||CORPUS)==CORPUS&&(o.role||"center")=="center")GT[o.clip+":"+o.frame]=o.flag;}
  }catch(e){}}
 render();};
 fr.readAsText(inp.files[0]);}
function buildPanel(){
 const p=document.getElementById("panel");let h="";
 for(const d of DIALS){
  if(d.length==1){h+=`<div class="grp">${d[0]}</div>`;continue;}
  const [k,lbl,mn,mx,stp]=d;
  h+=`<div class="dial" id="d_${k}"><label>${lbl}<span id="v_${k}">${A[k]}</span></label>
   <input type="range" min="${mn}" max="${mx}" step="${stp}" value="${A[k]}"
    oninput="A['${k}']=+this.value;document.getElementById('v_${k}').textContent=this.value;render()"></div>`;}
 h+=`<div class="note" style="margin-top:12px">주황 라벨 • = 기본값에서 움직인 다이얼</div>`;
 p.innerHTML=h;}
document.addEventListener("keydown",e=>{
 if(e.target.tagName=="INPUT")return;
 if(e.key=="ArrowRight"){cur=(cur+1)%WB.clips.length;render();}
 if(e.key=="ArrowLeft"){cur=(cur+WB.clips.length-1)%WB.clips.length;render();}});
buildPanel();render();
</script></body></html>
"""

# ── 클립 목록 + 등록 (/) — __DATA__ 치환 ─────────────────────────────────────
INDEX_PAGE = r"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><title>momentscan workbench — clips</title>
<style>
body{background:#161616;color:#ddd;font:13px/1.5 system-ui,sans-serif;margin:0;padding:16px 22px}
h1{font-size:16px;margin:0 0 2px} .note{color:#777;font-size:11px}
table{border-collapse:collapse;margin:10px 0}
td,th{border-bottom:1px solid #2c2c2c;padding:4px 12px 4px 0;text-align:left;font-size:13px}
th{color:#9ad;font-size:11px;text-transform:uppercase}
a{color:#8ab} .cached{color:#7c6} .uncached{color:#987}
button{background:#2a2a2a;color:#ddd;border:1px solid #555;border-radius:3px;
  padding:4px 12px;margin-right:6px;cursor:pointer}
button:hover{background:#383838}
input[type=text]{background:#111;color:#ddd;border:1px solid #444;border-radius:3px;padding:4px 6px}
#reg{margin:14px 0;padding:10px 12px;background:#1b1b1b;border:1px solid #2c2c2c;border-radius:4px;max-width:760px}
#reg .row{margin:4px 0}
#jobs{margin:6px 0} .job{font-size:12px;color:#a9c}
.err{color:#e66}
</style></head><body>
<script>const DATA=__DATA__;</script>
<h1>momentscan workbench</h1>
<div class="note">코퍼스 = <b id="corpus"></b> · GT 홈 = <span id="gtpath"></span> (<span id="gtn"></span>행)
 · 첫 열람은 클립당 수십 초(detect.mp4 디코드 → 캐시), 이후 즉시</div>

<div id="reg">
 <b>비디오 등록</b> <span class="note">— 로컬 경로 → perception 기판 잡(likeness 클로저), 완주 후 목록에 등장</span>
 <div class="row">소스 경로 <input type="text" id="src" size="58" placeholder="/path/to/video.mp4"></div>
 <div class="row">clip_id <input type="text" id="cid" size="24" placeholder="비우면 파일명">
  <button onclick="register()">등록</button> <span id="regmsg" class="note"></span></div>
 <div id="jobs"></div>
</div>

<div>
 <button onclick="openSel()">선택 클립 워크벤치 열기</button>
 <span class="note">(체크 후 — 열람 순간 미캐시 클립은 빌드)</span>
</div>
<table id="tbl"><tr><th></th><th>clip</th><th>frame_table 캐시</th><th></th></tr></table>

<script>
document.getElementById("corpus").textContent=DATA.corpus;
document.getElementById("gtpath").textContent=DATA.gt_path;
document.getElementById("gtn").textContent=DATA.gt_count;
const tbl=document.getElementById("tbl");
for(const c of DATA.clips){
 const tr=document.createElement("tr");
 tr.innerHTML=`<td><input type="checkbox" value="${c.clip}"></td><td><b>${c.clip}</b></td>
  <td class="${c.cached?"cached":"uncached"}">${c.cached?"✓ 캐시됨":"− 미빌드"}</td>
  <td><a href="/wb?clips=${c.clip}">열기</a></td>`;
 tbl.appendChild(tr);
}
function openSel(){
 const sel=[...document.querySelectorAll('#tbl input:checked')].map(x=>x.value);
 if(!sel.length){alert("클립을 선택하세요");return;}
 location.href="/wb?clips="+sel.join(",");}
async function register(){
 const src=document.getElementById("src").value.trim();
 const cid=document.getElementById("cid").value.trim();
 const msg=document.getElementById("regmsg");
 if(!src){msg.textContent="소스 경로를 입력하세요";return;}
 msg.textContent="등록 중…";
 try{
  const r=await fetch("/api/register",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify(cid?{source_path:src,clip_id:cid}:{source_path:src})});
  const j=await r.json();
  msg.textContent=r.ok?`접수: ${j.clip_id} (${j.status||"done"})`:`실패: ${j.error||r.status}`;
  msg.className=r.ok?"note":"err";
 }catch(e){msg.textContent="실패: "+e;msg.className="err";}
 pollJobs();}
async function pollJobs(){
 try{
  const j=await(await fetch("/api/jobs")).json();
  const el=document.getElementById("jobs");
  el.innerHTML=j.jobs.length?j.jobs.map(x=>
   `<div class="job">${x.clip_id} — ${x.status}${x.error?` <span class="err">${x.error}</span>`:""}</div>`).join(""):"";
  if(j.jobs.some(x=>x.status=="queued"||x.status=="running"))setTimeout(pollJobs,3000);
  else if(j.jobs.some(x=>x.status=="done")&&!document.__reloaded){
   document.__reloaded=1;location.reload();}
 }catch(e){}}
pollJobs();
</script></body></html>
"""

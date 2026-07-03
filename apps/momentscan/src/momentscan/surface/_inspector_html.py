# Self-contained inspect/clip.html template. __DATA__ → the per-clip JSON.
# Boxes are drawn on a canvas overlay from stash data (toggleable); the crop
# preview is cut from the main <video> (pristine when --source was given).
_TUBELET_INSPECT_HTML = r"""<!doctype html><html><head><meta charset=utf-8>
<title>tubelet inspect</title><style>
 body{background:#161616;color:#ddd;font:13px system-ui,sans-serif;margin:0;padding:10px}
 #top{display:flex;gap:12px;align-items:flex-start}
 #vwrap{position:relative} video{width:600px;display:block;background:#000;border:1px solid #333}
 #ov{position:absolute;left:0;top:0;pointer-events:none}
 #readout{font:12px ui-monospace,monospace;min-width:260px;line-height:1.5} #readout b{color:#9fe}
 canvas#c{display:block;margin-top:8px;border:1px solid #2a2a2a;cursor:crosshair}
 .hint{color:#888;font-size:11px;margin:4px 0} .tab{display:inline-block;padding:3px 10px;margin:2px;border:1px solid #444;border-radius:4px;cursor:pointer}
 .tab.on{background:#2c4;color:#000;font-weight:bold} label{margin-right:10px;font-size:12px;cursor:pointer}
 #prev{border:1px solid #555;background:#000}
 #outputs{margin:8px 0;display:flex;gap:6px;flex-wrap:wrap;align-items:flex-start}
 #outputs img{height:118px;border:1px solid #444;display:block} #outputs .o{text-align:center;cursor:pointer}
</style></head><body>
<div id=tabs></div>
<div id=toggles class=hint>
 <label><input type=checkbox id=tDet checked> det/track box</label>
 <label><input type=checkbox id=tPort checked> portrait box</label>
 <label><input type=checkbox id=tOthers> 다른 subject 박스</label>
 <label><input type=checkbox id=tMesh> <span style="color:#9e9">landmark mesh</span></label>
 <label><input type=checkbox id=tGdetail> <span style="color:#9a9">게이트 상세 사다리 (L2)</span></label>
 <label><input type=checkbox id=tROI checked> <span style="color:#9c9">제품 ROI (공간 관심영역)</span></label>
 <span style="margin-left:6px">tab: <b style="color:#5b8fd6">▍</b>likeness <b style="color:#d6a04b">▍</b>portrait <b style="color:#5bbf7a">▍</b>highlight</span>
 <span id=srcnote></span></div>
<div id=top>
 <div id=vwrap><video id=v controls preload=auto></video><canvas id=ov></canvas></div>
 <div><div id=hdr></div><div class=hint>탭=subject · 캔버스 클릭=점프 · ←/→ 프레임 · 스페이스 재생</div><div id=readout></div></div>
 <div><div class=hint>portrait box 프리뷰 (4:5 · 무왜곡)</div><canvas id=prev width=176 height=220></canvas></div>
 <div><div class=hint>canonical frame (pose-removed · CANONICAL_FRAME)</div><canvas id=canon width=170 height=210 style="background:#000;border:1px solid #555"></canvas></div>
</div>
<div id=outputs></div>
<canvas id=c></canvas>
<script>
const DATA=__DATA__;
const v=document.getElementById('v'),cv=document.getElementById('c'),ctx=cv.getContext('2d');
const ov=document.getElementById('ov'),octx=ov.getContext('2d'),ro=document.getElementById('readout'),hdr=document.getElementById('hdr');
const prev=document.getElementById('prev'),pctx=prev.getContext('2d');
const tDet=document.getElementById('tDet'),tPort=document.getElementById('tPort'),tOthers=document.getElementById('tOthers');
const tMesh=document.getElementById('tMesh');
const tGdetail=document.getElementById('tGdetail');   // L2 상세 사다리 토글 (기본 접힘)
const tROI=document.getElementById('tROI');           // 제품별 공간 관심영역(ROI) 중첩 박스
const MESHE=DATA.mesh_edges||[];                    // face feature outlines (thin)
const MNOSE=DATA.mesh_nose||[];                     // nose outline — drawn THICKER (representative pts)
const MRIDGE=DATA.mesh_ridge||[];                   // nose centre ridge — soft (dashed, dim)
const MREGION=DATA.mesh_region||[];                 // 연삼각 (soft-triangle) regions — translucent fill
const canon=document.getElementById('canon'),cnx=canon.getContext('2d');
v.src=DATA.main;
const CROPS=DATA.crops||{};                       // clean crop track per subject (data-retention)
const cropv=document.createElement('video');cropv.muted=true;cropv.preload='auto';
function setCropSrc(){const f=CROPS[DATA.subjects[cur].sid];if(f&&!cropv.src.endsWith(f.split('/').pop()))cropv.src=f;}
cropv.addEventListener('seeked',()=>{const e=eIdx(cur,DISP);if(e>=0&&CROPS[DATA.subjects[cur].sid]){try{pctx.drawImage(cropv,0,0,prev.width,prev.height);}catch(err){}}});
const pv=DATA.crop_provenance,O=DATA.obs||{};
document.getElementById('srcnote').textContent=
 (Object.keys(CROPS).length?'· preview=clean crop track'
   :(DATA.clean?'· main=clean source':'· main=detect.mp4 (박스 구워짐 — fallback)'))
 +(pv&&pv.processed_at?' · crop@'+pv.processed_at.slice(0,10):'')
 +(O.ran!=null?` · run ${O.ran}✓/${O.skipped}skip/${O.failed}✗`+(O.elapsed_ms!=null?` ${O.elapsed_ms}ms`:''):'')
 +(O.traces&&O.traces.length?' · channels←'+O.traces.join('+'):'')
 +(O.issues&&O.issues.length?' · ⚠ '+O.issues.map(x=>x.stage+(x.reason?'('+x.reason+')':'')).join(' '):'')
 +(O.stale&&O.stale.length?' · ⚠ STALE: '+O.stale.join(',')+' (source changed since — re-run)':'')
 +(O.source?' · src '+O.source.split('/').pop():'');
const fps=DATA.fps,fmin=DATA.fmin,fmax=DATA.fmax;
// gate verdict → color, and the served-view set — both GENERATED from gates.py
// (DATA.gate_colors / gate_served), so the inspector can never disagree with the
// engine's verdict vocabulary. admit/quarter/side served; reject:* / no_view not.
const GCOL=DATA.gate_colors||{};
const GPASS=Object.fromEntries((DATA.gate_served||[]).map(r=>[r,1]));
const SCOL=['#5ac85a','#3ca0e6','#e6a050','#c85ac8','#50c8c8','#c8c850'];
const FCOL=['#e05050','#50b0e0','#80d060','#d0a040','#b070d0','#50c0b0','#d06090','#9090d0'];
const PASPECT=0.8,FACEH=0.62,EYE=0.42;
function pbox(b){const fh=b[3]-b[1],cx=(b[0]+b[2])/2,H=fh/FACEH,Wd=H*PASPECT,eyeY=b[1]+EYE*fh,top=eyeY-EYE*H;return[cx-Wd/2,top,cx+Wd/2,top+H];}
let cur=0,DISP=fmin;
const fset=DATA.subjects.map(s=>{const m=new Map();s.frames.forEach((f,i)=>m.set(f,i));return m;});
function eIdx(ci,f){const m=fset[ci].get(f);return m==null?-1:m;}
const W=Math.min(1700,Math.max(700,(fmax-fmin)*2));
const LEFT=92,GATE_V=18,FRAG=16,COPRES=Math.max(14,DATA.subjects.length*9),LANE=46,PAD=6,TOP=4;
// GATE ladder — each persisted sub-gate rung as its own pass/fail strip, grouped by the
// THREE execution STAGES (gates.py ① VALIDITY / ② POLICY / ③ ROUTING). col[2] = stage.
// ① VALIDITY is the SHARED verdict — likeness · highlight · portrait ALL read `valid`;
// ② POLICY + ③ ROUTING are portrait-ONLY (its query-proximity gate + view routing).
// kind: 'rej' green pass / red BLOCK · 'key' = the shared `valid` keystone (brighter) ·
// 'route' = view-color when it applies, dim otherwise. This is the per-product differential.
const GLAD=[
 ['face_present','face','①','rej'],['sharp_ok','sharp','①','rej'],['exposure_ok','expos','①','rej'],
 ['id_ok','id·core','①','rej'],['id_valid','id·self','①','rej'],['valid','VALID','①','key'],
 ['eyes_ok','eyes','②','rej'],['expr_ok','expr','②','rej'],['query_ok','query','②','key'],
 ['admit','admit','③','route'],['quarter_ok','quart','③','route'],['side_ok','side','③','route']];
// which products consume each stage (left-margin tag) + the stage's accent color.
const GCONSUME={'①':'L·H·P','②':'P','③':'P'},GSTAGECOL={'①':'#7ab0ea','②':'#d6a04b','③':'#5fbf7a'};
const GROW=7,GGAP=1,GATE=GATE_V+3+(GLAD.length+3)*(GROW+GGAP);  // +3 = the ①②③ stage-header rows
const GATE_COLLAPSED=15;  // 계층화: L2 상세 사다리 접힘 → 얇은 on-demand 스트립 (기본). L0 요약이 항상-표시분.
// GATE OPEN/CLOSED summary — the intuitive per-product view (above the detailed ladder):
// when is each product's gate OPEN (collecting/serving) vs CLOSED, over the FULL clip range.
// The TARGET-presence gate is the existence precondition (subject detected + tubelet); an
// absent frame is CLOSED for everyone. The POSE gate then differs per product: likeness needs
// the STRICT frontal core · portrait any served VIEW (frontal/quarter/side) · highlight only
// validity. So likeness's open windows are a SUBSET of portrait's = the per-product difference, visible.
const GOPEN=[['__target__','TARGET','#6a9a6a'],['likeness','likeness·front','#7ab0ea'],
 ['portrait','portrait·view','#d6a04b'],['highlight','highlight·WHEN','#5fbf7a']];
const GOROW=12,GATEOPEN_H=11+GOPEN.length*GOROW+2;
let _gateStrip=null;   // 접힌 GATE 스트립의 캔버스 y-band → 클릭하면 펼침 (drawGate가 매 draw마다 갱신)
function xo(f){return LEFT+Math.round((f-fmin)/Math.max(1,fmax-fmin)*(W-1));}
function nIdx(s,f){let b=0,bd=1e9;s.frames.forEach((ff,j)=>{let d=Math.abs(ff-f);if(d<bd){bd=d;b=j;}});return b;}
function sizeOv(){ov.width=DATA.vw;ov.height=DATA.vh;ov.style.width=v.clientWidth+'px';ov.style.height=v.clientHeight+'px';}
// frame N spans [N/fps,(N+1)/fps): read with floor, SEEK to mid-frame (N+0.5)/fps
// so the browser lands firmly inside frame N (currentTime=N/fps can fall to N-1).
function frameOf(t){return Math.floor(t*fps+1e-4);}
function seekFrame(N){v.currentTime=(Math.max(fmin,Math.min(fmax,N))+0.5)/fps;}
function setDisp(f){DISP=Math.max(fmin,Math.min(fmax,f));draw();}
function groups(s){return[...new Set(s.channels.map(c=>c.group))];}
// why a subject has 0 extracted portraits — read from portrait_meta (the run already
// recorded crop_track/n_admit), NOT a guess. explains THIS run instead of "run portrait".
function portraitWhy(pm){
 if(!pm) return 'portrait stage not run';
 if(pm.crop_track===false) return 'crop track missing — source/crops expired (data-retention)';
 if(pm.n_admit!=null&&pm.min_admit!=null&&pm.n_admit<pm.min_admit) return 'n_admit '+pm.n_admit+' < '+pm.min_admit+' — gate rejected too many frames';
 if(pm.rep_ok===false) return 'crop extraction failed for the picked frames';
 return 'no rep selected';
}
function renderOutputs(){
 const out=document.getElementById('outputs');out.innerHTML='';const s=DATA.subjects[cur];const ps=s.portraits||[];
 const h=document.createElement('div');h.style.cssText='width:100%;color:#d6a04b;font-weight:bold;font:12px monospace';
 h.textContent='EXTRACTED PORTRAITS · subject '+s.sid+' ('+ps.length+')'+(ps.length?'':' — none: '+portraitWhy(s.portrait_meta));out.appendChild(h);
 ps.forEach(p=>{const d=document.createElement('div');d.className='o';
  const img=document.createElement('img');img.src=p.file;img.onerror=()=>{img.style.opacity=0.25;};
  const c=document.createElement('div');c.style.cssText='font:11px monospace;color:#bbb';c.textContent=p.label+' f'+p.frame;
  d.appendChild(img);d.appendChild(c);d.onclick=()=>{seekFrame(p.frame);};out.appendChild(d);});
}
function tabs(){const t=document.getElementById('tabs');t.innerHTML='';
 DATA.subjects.forEach((s,i)=>{const d=document.createElement('span');d.className='tab'+(i==cur?' on':'');
  d.textContent=`subject ${s.sid} [${s.role}] n=${s.frames.length}`;d.style.borderColor=SCOL[i%6];
  d.onclick=()=>{cur=i;setCropSrc();tabs();draw();};t.appendChild(d);});
 const s=DATA.subjects[cur];hdr.innerHTML=`<b>${DATA.clip}</b> · subject <b>${s.sid}</b> [${s.role}] · n=${s.frames.length} · fragments=${new Set(s.raw).size} · seams=${s.seams.length} · coherence=${s.coherence==null?'—':s.coherence}`;
 renderOutputs();}
function drawOverlay(f){
 octx.clearRect(0,0,ov.width,ov.height);octx.lineWidth=2.5;
 DATA.subjects.forEach((s,si)=>{const e=eIdx(si,f);if(e<0)return;const active=si===cur;
  if(!active&&!tOthers.checked)return;const b=s.bbox[e];
  if(tDet.checked){octx.strokeStyle=SCOL[si%6];octx.globalAlpha=active?1:0.4;octx.setLineDash([7,5]);
   octx.strokeRect(b[0],b[1],b[2]-b[0],b[3]-b[1]);octx.setLineDash([]);octx.globalAlpha=1;}
  if(active&&tPort.checked){const p=pbox(b);octx.strokeStyle='#22ddee';octx.lineWidth=2;
   octx.strokeRect(p[0],p[1],p[2]-p[0],p[3]-p[1]);octx.fillStyle='#22ddee';octx.font='14px monospace';octx.fillText('portrait',p[0]+3,p[1]+15);octx.lineWidth=2.5;}
  if(active&&tROI.checked){
   // spatial REGION OF INTEREST per product — each looks at a DIFFERENT region: likeness the
   // tight FACE (→ pose-removed canonical space, see the mini-view), portrait the 4:5 framed
   // VIEW, highlight the RIDER + SCENE (wide). Nested = the widening spatial scope.
   octx.setLineDash([]);octx.font='13px monospace';
   const roiBox=(x0,y0,x1,y1,col,lab)=>{octx.strokeStyle=col;octx.lineWidth=2;
     octx.strokeRect(x0,y0,x1-x0,y1-y0);octx.fillStyle=col;octx.fillText(lab,x0+3,y0-4);};
   const cx=(b[0]+b[2])/2,cy=(b[1]+b[3])/2,w=b[2]-b[0],h=b[3]-b[1];
   roiBox(cx-w*1.7,cy-h*1.5,cx+w*1.7,cy+h*2.3,'#5fbf7a','highlight · rider+scene');   // outermost (always: WHEN receptive field)
   // portrait ROI only when THIS frame is admitted (portrait attends per-frame; inactive → no box)
   const padm=s.gate_open&&s.gate_open.portrait&&s.gate_open.portrait[e];
   if(padm){const p=pbox(b);roiBox(p[0],p[1],p[2],p[3],'#d6a04b','portrait · 4:5 (admit)');}   // mid
   roiBox(b[0],b[1],b[2],b[3],'#7ab0ea','likeness · face→canonical');                 // innermost (always: global cohort target)
   octx.lineWidth=2.5;
  }});
 drawMeshObs(DATA.subjects[cur],f);
 drawPreview(eIdx(cur,f));
 drawCanon(DATA.subjects[cur],f);
}
function drawPreview(e){
 pctx.fillStyle='#000';pctx.fillRect(0,0,prev.width,prev.height);
 if(e<0)return;
 const cropFile=CROPS[DATA.subjects[cur].sid];
 // clean main (--source) → crop straight from the main video: SAME element, SAME
 // DISP frame as the bbox overlay → perfectly synced. The crop track (separate,
 // async-seeking video) is only for an annotated main (post-window, no source).
 if(!DATA.clean && cropFile){
   const t=(e+0.5)/fps;
   if(Math.abs(cropv.currentTime-t)>0.4/fps){cropv.currentTime=t;return;}  // seeked handler redraws
   try{pctx.drawImage(cropv,0,0,prev.width,prev.height);}catch(err){}
 }else{
   const p=pbox(DATA.subjects[cur].bbox[e]);
   try{pctx.drawImage(v,p[0],p[1],p[2]-p[0],p[3]-p[1],0,0,prev.width,prev.height);}catch(err){}
 }
}
// CASCADE stages — the timeline's primary axis is ①FEATURE ②GATE ③PRODUCT, the
// SAME boundary the run-watch execution banners print, so "where in the pipeline /
// where did it break" reads identically in the log and here. This is the
// "one DAG, three node kinds" model: producers (signals) → gate (threshold) →
// heads (products). A lane's PRODUCT affinity (which head it feeds) survives as a
// thin left-edge color tab (LANE_PRODUCT); the per-frame readout (right) stays
// product-grouped, because a verdict is inherently per-output.
const SECTIONS=[
 {name:'① FEATURE · signals measured  (producer nodes)', color:'#6f7b86',
  lanes:['FRAG','identity','pose','expression','lighting','occlusion','CO-PRES','emotion','scene']},
 {name:'② GATE · open / closed per product  (likeness = ① validity+frontal · portrait = ② query-proximity · highlight = WHEN segment)', color:'#b06a3a',
  lanes:['GATES','GATE']},
 {name:'③ PRODUCT · served outputs  (heads)', color:'#4a8f6a',
  lanes:['PICKS','SEGS']},
];
// product affinity per lane — which head this signal primarily feeds. Drawn as a
// left-edge tab so the cascade regroup doesn't lose the signal→product mapping.
// likeness=blue, portrait=amber, highlight=green (== the readout section colors).
const LANE_PRODUCT={FRAG:'#5b8fd6',identity:'#5b8fd6',
 pose:'#d6a04b',expression:'#d6a04b',lighting:'#d6a04b',occlusion:'#d6a04b',
 'CO-PRES':'#5bbf7a',emotion:'#5bbf7a',scene:'#5bbf7a',
 PICKS:'#d6a04b',SEGS:'#5bbf7a'};
const SECT_H=16;
// output-kind dispatch (analyzer ③): cat→strip · timeline→line lane · sel→markers
const LANE_KIND={GATES:'cat',GATE:'cat',FRAG:'cat','CO-PRES':'cat',PICKS:'sel',SEGS:'sel'};
function laneKind(n){return LANE_KIND[n]||'timeline';}
function laneH(name){if(name==='GATES')return GATEOPEN_H;if(name==='GATE')return tGdetail.checked?GATE:GATE_COLLAPSED;if(name==='FRAG')return FRAG;if(name==='CO-PRES')return COPRES;
 if(name==='PICKS'||name==='SEGS')return 12;
 return groups(DATA.subjects[cur]).includes(name)?LANE:0;}
// 닫힘색 = 닫은 단계: 검정=존재X(TARGET) · 암적=invalid①(공유) · 암청=포즈②(likeness 비정면) ·
// 암황=뷰③(portrait no-view). → 펼치지 않아도 "왜 닫혔나"의 단계가 L0 요약에서 바로 읽힘.
function drawGateOpen(s,y){const cw=Math.max(1,W/(fmax-fmin+1));
 ctx.fillStyle='#ccc';ctx.fillText('OPEN/CLOSED',4,y+9);
 ctx.font='9px monospace';let lx=LEFT;                                          // 닫힘색 범례 (헤더 줄)
 for(const[cc,tt] of [['#141414','존재X'],['#3a2222','invalid①'],['#243a55','포즈②'],['#4a3a1a','뷰③']]){
  ctx.fillStyle=cc;ctx.fillRect(lx,y+1,10,8);ctx.strokeStyle='#555';ctx.strokeRect(lx+0.5,y+1.5,9,7);
  ctx.fillStyle='#999';ctx.fillText(tt,lx+13,y+9);lx+=13+ctx.measureText(tt).width+11;}
 const fset=new Set(s.frames),idx=new Map(s.frames.map((f,i)=>[f,i])),go=s.gate_open||{},L=s.gate_ladder||{};
 const CLOSEDHUE={likeness:'#243a55',portrait:'#4a3a1a'};                        // valid이나 제품게이트 실패: 포즈②/뷰③
 let yy=y+11;
 for(const[key,lbl,col] of GOPEN){
  ctx.fillStyle=col;ctx.fillText(lbl,4,yy+9);
  for(let f=fmin;f<=fmax;f++){const x=xo(f);let c;const j=idx.get(f);const arr=go[key];
   if(!fset.has(f)) c='#141414';                                  // absent (no tubelet) = TARGET(존재) 게이트 CLOSED
   else if(key==='__target__') c=col;                            // subject present
   else if(arr&&arr[j]) c=col;                                   // OPEN = product color
   else if(key==='highlight') c='#1e2a22';                       // highlight CLOSED = no WHEN fired (neutral, NOT invalid — a segment can even hold invalid frames)
   else if((L.valid||[])[j]===false) c='#3a2222';               // CLOSED by ① invalid (공유) = 암적
   else if(arr) c=CLOSEDHUE[key]||'#3a2222';                     // CLOSED by 제품 게이트 (valid이나 ②/③) = 암청/암황
   else c='#3a2222';                                             // gate_open 데이터 없음(퇴화 클립) = 암적
   ctx.fillStyle=c;ctx.fillRect(x,yy,cw+1,GOROW-2);}
  yy+=GOROW;}
 ctx.font='11px monospace';}
function drawGate(s,y){const cw=Math.max(1,W/(fmax-fmin+1));
 if(!tGdetail.checked){                                          // 계층화: L2 접힘 → 얇은 on-demand 스트립
  _gateStrip=[y,y+GATE_COLLAPSED];
  ctx.fillStyle='#1c1c1c';ctx.fillRect(LEFT,y,W,GATE_COLLAPSED);
  ctx.fillStyle='#8a8a8a';ctx.font='10px monospace';
  ctx.fillText('▸ 상세 게이트 사다리 (①②③ 서브게이트) — 클릭하거나 상단 체크박스로 펼침',LEFT+6,y+11);
  ctx.font='11px monospace';return;}
 _gateStrip=null;                                               // 펼침 상태 — 클릭영역 없음
 ctx.fillStyle='#bbb';ctx.fillText('detail',4,y+12);
 s.frames.forEach((f,i)=>{ctx.fillStyle=GCOL[s.gate[i]]||'#444';ctx.fillRect(xo(f),y,cw+1,GATE_V);});  // routed verdict
 const L=s.gate_ladder||{};let yy=y+GATE_V+3;ctx.font='9px monospace';let pst=null;                   // sub-gate ladder
 for(const[key,lbl,tier,kind] of GLAD){const arr=L[key]||[];
  if(tier!==pst){  // stage boundary → accent header naming WHICH products consume this stage
   const sc=GSTAGECOL[tier]||'#888';ctx.fillStyle=sc;ctx.fillText(tier+' '+(tier==='①'?'VALIDITY':tier==='②'?'POLICY':'ROUTING')+' → '+GCONSUME[tier],4,yy+GROW);
   const lx=xo(fmin);ctx.fillStyle=sc;ctx.globalAlpha=0.25;ctx.fillRect(LEFT,yy,W,GROW);ctx.globalAlpha=1;  // faint stage band
   yy+=GROW+GGAP;pst=tier;}
  ctx.fillStyle=kind==='key'?(GSTAGECOL[tier]||'#aaa'):'#777';ctx.fillText('   '+lbl,4,yy+GROW);
  s.frames.forEach((f,i)=>{const val=arr[i];
   ctx.fillStyle = val==null?'#2a2a2a'
     : kind==='key' ? (val?'#46e05a':'#e03b3b')                                         // the SHARED `valid` keystone (bright)
     : kind==='rej' ? (val?'#2f6f3f':'#c04040')                                         // pass / BLOCK
     : val ? (key==='side_ok'?'#22ddee':key==='quarter_ok'?'#7ed957':'#5ac85a') : '#242424';  // route / dim
   ctx.fillRect(xo(f),yy,cw+1,GROW);});
  yy+=GROW+GGAP;}
 ctx.font='11px monospace';}
function drawFrag(s,y){const cw=Math.max(1,W/(fmax-fmin+1));ctx.fillStyle='#bbb';ctx.fillText('FRAG',4,y+12);const tr=[...new Set(s.raw)];
 s.frames.forEach((f,i)=>{ctx.fillStyle=FCOL[tr.indexOf(s.raw[i])%FCOL.length];ctx.fillRect(xo(f),y,cw+1,FRAG);});
 s.seams.forEach(se=>{const x=xo(se.frame);ctx.strokeStyle='#fff';ctx.beginPath();ctx.moveTo(x,y-1);ctx.lineTo(x,y+FRAG+1);ctx.stroke();
  ctx.fillStyle=se.cos!=null&&se.cos<0.5?'#f55':'#9f9';ctx.fillText((se.cos==null?'?':se.cos),x+1,y+FRAG-3);});}
function drawCopres(s,y){const cw=Math.max(1,W/(fmax-fmin+1));ctx.fillStyle='#bbb';ctx.fillText('CO-PRES',4,y+10);
 DATA.subjects.forEach((ss,si)=>{const yy=y+si*9;ctx.fillStyle=SCOL[si%6];ss.frames.forEach(f=>ctx.fillRect(xo(f),yy,cw+1,7));});}
function drawGroup(s,g,y){ctx.fillStyle='#222';ctx.fillRect(LEFT,y,W,LANE);ctx.fillStyle='#bbb';ctx.fillText(g,4,y+13);
 let lx=4;for(const c of s.channels.filter(c=>c.group===g)){const col=`rgb(${c.color})`;
  ctx.fillStyle=col;ctx.fillText(c.name,lx,y+LANE-4);lx+=Math.max(54,c.name.length*7);
  ctx.strokeStyle=col;ctx.beginPath();let st=false;
  for(let i=0;i<s.frames.length;i++){const val=c.vals[i];if(val==null){st=false;continue;}
   const t=(val-c.lo)/(c.hi-c.lo+1e-9),yy=y+LANE-3-Math.max(0,Math.min(1,t))*(LANE-6);
   if(!st){ctx.moveTo(xo(s.frames[i]),yy);st=true;}else ctx.lineTo(xo(s.frames[i]),yy);}ctx.stroke();}}
function drawPicks(s,which,y){
 ctx.fillStyle='#bbb';ctx.fillText(which==='portrait'?'PICKS':'SEGS',4,y+10);
 const p=s.picks||{};
 if(which==='portrait'){(p.portrait||[]).forEach((f,i)=>{const x=xo(f);ctx.fillStyle=i===0?'#5fef5f':'#3a8';
   ctx.beginPath();ctx.moveTo(x-3,y);ctx.lineTo(x+3,y);ctx.lineTo(x,y+8);ctx.closePath();ctx.fill();});}
 else{(p.highlight||[]).forEach(seg=>{const xs=xo(seg[0]),xe=xo(seg[1]);
   ctx.fillStyle='rgba(230,140,40,0.55)';ctx.fillRect(xs,y,Math.max(2,xe-xs),11);});}}
// kind-dispatched lane renderer: categorical strips are bespoke; timeline → the
// generic line lane (any new timeline analyzer renders for free); selection → marks.
function drawLane(s,name,y){const k=laneKind(name);
 if(k==='cat'){if(name==='GATES')drawGateOpen(s,y);else if(name==='GATE')drawGate(s,y);else if(name==='FRAG')drawFrag(s,y);else drawCopres(s,y);}
 else if(k==='sel')drawPicks(s,name==='PICKS'?'portrait':'highlight',y);
 else drawGroup(s,name,y);}
// landmark wireframe — nearest embedded mesh frame to f (subjects carry a
// DOWNSAMPLED mesh; snap within a few frames). obs = full-frame px (drawn on the
// video overlay = per-frame fit), canon = pose-removed in the DECLARED frame.
function meshAt(s,f){const m=s.mesh;if(!m)return -1;let b=-1,bd=13;
 for(let i=0;i<m.f.length;i++){const d=Math.abs(m.f[i]-f);if(d<bd){bd=d;b=i;}}return b;}
function strokeEdges(c,pts,edges){c.beginPath();for(const e of edges){c.moveTo(pts[e[0]*2],pts[e[0]*2+1]);c.lineTo(pts[e[1]*2],pts[e[1]*2+1]);}c.stroke();}
function fillPoly(c,pts,poly,style){if(!poly||poly.length<3)return;c.fillStyle=style;c.beginPath();c.moveTo(pts[poly[0]*2],pts[poly[0]*2+1]);for(let k=1;k<poly.length;k++)c.lineTo(pts[poly[k]*2],pts[poly[k]*2+1]);c.closePath();c.fill();}
function drawMeshObs(s,f){if(!tMesh.checked)return;const i=meshAt(s,f);if(i<0)return;const o=s.mesh.obs[i];
 octx.globalAlpha=1;octx.setLineDash([]);
 for(const p of MREGION)fillPoly(octx,o,p,'rgba(255,190,70,0.25)');                                // 연삼각 region fill
 octx.strokeStyle='rgba(120,230,140,0.7)';octx.lineWidth=1;strokeEdges(octx,o,MESHE);              // face (thin)
 octx.strokeStyle='rgba(120,230,140,0.7)';octx.lineWidth=1;strokeEdges(octx,o,MNOSE);              // nose base (thin)
 octx.strokeStyle='rgba(120,230,140,0.45)';octx.lineWidth=1;octx.setLineDash([2,2]);strokeEdges(octx,o,MRIDGE);  // ridge
 octx.setLineDash([]);octx.lineWidth=1;}
function drawCanon(s,f){cnx.fillStyle='#000';cnx.fillRect(0,0,canon.width,canon.height);
 const i=tMesh.checked?meshAt(s,f):-1;
 if(i<0){cnx.fillStyle='#666';cnx.font='11px monospace';cnx.fillText(tMesh.checked?'no landmark fit':'(toggle landmark mesh)',8,24);return;}
 const c=s.mesh.canon[i];cnx.setLineDash([]);
 for(const p of MREGION)fillPoly(cnx,c,p,'rgba(255,190,70,0.3)');                      // 연삼각 region fill
 cnx.strokeStyle='#9e9';cnx.lineWidth=1;strokeEdges(cnx,c,MESHE);                      // face (thin)
 cnx.strokeStyle='#9e9';cnx.lineWidth=1;strokeEdges(cnx,c,MNOSE);                      // nose base (thin)
 cnx.strokeStyle='rgba(150,230,150,0.5)';cnx.lineWidth=1;cnx.setLineDash([2,2]);strokeEdges(cnx,c,MRIDGE);  // ridge
 cnx.setLineDash([]);cnx.lineWidth=1;
 cnx.fillStyle='#7a7';cnx.font='10px monospace';cnx.fillText('mesh f'+s.mesh.f[i],4,canon.height-5);}
function draw(){
 const s=DATA.subjects[cur];
 let H=TOP;for(const sec of SECTIONS){H+=SECT_H;for(const ln of sec.lanes){const h=laneH(ln);if(h)H+=h+PAD;}H+=4;}
 cv.width=LEFT+W+10;cv.height=H+6;
 ctx.fillStyle='#161616';ctx.fillRect(0,0,cv.width,cv.height);ctx.font='11px monospace';
 let y=TOP;
 for(const sec of SECTIONS){
  ctx.fillStyle=sec.color;ctx.fillRect(0,y,cv.width,SECT_H-2);
  ctx.fillStyle='#111';ctx.font='bold 11px monospace';ctx.fillText(sec.name,6,y+12);ctx.font='11px monospace';
  y+=SECT_H;
  for(const ln of sec.lanes){const h=laneH(ln);if(!h)continue;
   const pc=LANE_PRODUCT[ln];if(pc){ctx.fillStyle=pc;ctx.fillRect(0,y,3,h);}  // product-affinity tab
   drawLane(s,ln,y);y+=h+PAD;}
  y+=4;
 }
 const f=DISP,x=xo(f);ctx.strokeStyle='#fff';ctx.beginPath();ctx.moveTo(x,TOP);ctx.lineTo(x,cv.height-4);ctx.stroke();
 sizeOv();drawOverlay(f);
 // ── decision-first readout (A): per product section, verdict + evidence ──
 const ex=eIdx(cur,f),i=ex>=0?ex:nIdx(s,f);
 const val=n=>{const c=s.channels.find(c=>c.name===n);return c?c.vals[i]:null;};
 const nf=(x,d=2)=>x==null?'—':(+x).toFixed(d);
 const sec=(t,c)=>`<div style="color:${c};font-weight:bold;margin-top:7px">${t}</div>`;
 const chip=(t,c)=>` <span style="color:${c}">${t}</span>`;
 let html=`<div style="color:#fff">frame <b>${f}</b></div>`;
 const SEL=s.select||{}, QRY=SEL.query||{};   // ③ SELECT reasoning + the QUERY criterion per product
 const sbar=(t,c)=>`<br><span style="color:${c||'#9ac'}">▸ SELECT</span> ${t}`;
 // each product = its own bordered, tinted BOX (accent = product color) with a 기준(criterion)
 // subtitle = what it was selected AGAINST (portrait query / highlight expectation).
 let _open=false;
 // ── TEMPORAL SCOPE bar — each product answers over a DIFFERENT time span: likeness converges
 // over the WHOLE clip, highlight over SEGMENTS, portrait per FRAME. The bar (over the full clip
 // range) + the white current-frame marker make that span visible, so the readout stops reading
 // as if all three were per-frame.
 const pct=fr=>((fr-fmin)/Math.max(1,fmax-fmin)*100);
 const RFHALF=Math.max(1,Math.round((SEL.rf_win_s||2)*fps/2));   // ½ WHEN receptive field, in frames
 // scopebar: static extent (kind) + an OPTIONAL moving receptive-field window (rfWin, frames)
 // centred on the current frame f — highlight's ~2s WHEN input span exists at EVERY frame and
 // MOVES with the playhead, distinct from the delivered segments drawn beneath it.
 const scopebar=(kind,items,c,label,rfWin)=>{
   let seg='';
   if(kind==='clip')seg=`<div style="position:absolute;left:0;width:100%;height:100%;background:${c};opacity:.4;border-radius:2px"></div>`;
   else if(kind==='cohort'){   // the SELECTED, aggregated set over ALL time (playhead-independent):
     const vf=(items&&items[0])||[],cf=(items&&items[1])||[];   // valid pool (dim) → selected core (bright)
     seg=vf.map(fr=>`<div style="position:absolute;left:${pct(fr)}%;top:0;width:1.5px;height:100%;background:${c};opacity:.28"></div>`).join('')
       +cf.map(fr=>`<div style="position:absolute;left:${pct(fr)}%;top:0;width:1.5px;height:100%;background:${c}"></div>`).join('');}
   else if(kind==='segments')seg=(items||[]).map(g=>`<div style="position:absolute;left:${pct(g[0])}%;width:${Math.max(0.8,pct(g[1])-pct(g[0]))}%;height:100%;background:${c};border-radius:2px"></div>`).join('');
   else seg=(items||[]).map((fr,i)=>`<div style="position:absolute;left:${pct(fr)}%;top:0;width:${i===0?3:2}px;height:100%;background:${i===0?c:c+'99'}"></div>`).join('');
   const rf=(rfWin>0)?`<div style="position:absolute;left:${pct(f-rfWin)}%;width:${Math.max(1,pct(f+rfWin)-pct(f-rfWin))}%;height:100%;background:${c};opacity:.3;border:1px dashed ${c};box-sizing:border-box;border-radius:2px"></div>`:'';
   return `<div style="display:flex;align-items:center;gap:5px;margin:2px 0 3px"><span style="color:#8a8a8a;font-size:10px;white-space:nowrap">${label}</span>`
     +`<div style="position:relative;flex:1;height:7px;background:#1c1c1c;border-radius:2px">${seg}${rf}`
     +`<div style="position:absolute;left:${pct(f)}%;top:-1px;width:1px;height:9px;background:#fff"></div></div></div>`;
 };
 const box=(c,title,crit,scope)=>{const pre=_open?'</div>':'';_open=true;
   return pre+`<div style="border-left:3px solid ${c};background:${c}14;padding:4px 8px 6px;margin-top:7px;border-radius:4px">`
     +`<div style="color:${c};font-weight:bold">${title}</div>`
     +(scope||'')
     +(crit?`<div style="color:#9a9;font-size:11px;margin:1px 0 3px">기준: ${crit}</div>`:'');};
 // LIKENESS — who (visit-invariant)
 // likeness attention = the SELECTED, aggregated set over ALL time (NOT the current frame).
 // lkValid = ACTUAL geometry consumption (valid∩landmarks) — valid alone OVERSTATES:
 // no-landmark frames can't enter the distribution reading (drawing them as attention
 // exaggerated the test_0 early-occlusion "contamination" that measurement refuted).
 const GLk=s.gate_ladder||{};
 const lkValid=s.frames.filter((fr,i)=>(GLk.valid||[])[i]&&((GLk.have_bs||[])[i]!==false));
 const lkCore=s.frames.filter((fr,i)=>((s.gate_open||{}).likeness||[])[i]);
 html+=box('#7ab0ea','LIKENESS · who · 전 시간 선택·집계','정면 정체성 코어 (query 없음 — 정체성은 사실) · gate ① valid∩landmarks(실소비) + STRICT frontal',scopebar('cohort',[lkValid,lkCore],'#7ab0ea','선택·집계'));
 html+=`role ${s.role} · coherence ${nf(s.coherence)}`;
 // likeness CONVERGES to clean_ref: face_id (identity centroid) is built from the STRICT
 // FRONTAL core; the broader `valid` set feeds only its variation (geometry / hair / fashion).
 const Lk=s.gate_ladder||{};const lv=ex>=0&&Lk.valid?Lk.valid[ex]:null;
 const lkO=ex>=0?((s.gate_open||{}).likeness||[])[ex]:null;
 if(ex>=0)html+='<br>① valid: '+(lv===true?chip('✓','#5e5'):lv===false?chip('✗ excluded','#f66'):'—')
   +' · face_id core: '+(lkO===true?chip('✓ frontal — collected','#5e5'):chip('✗ non-frontal — variation only','#888'));
 html+=`<br><span style="color:#8a9">attention:</span> 시간 전역에서 게이트 통과 프레임을 선택·집계 (재생 위치와 무관) · 선택 `+chip(lkCore.length,'#7ab0ea')+`/실소비 ${lkValid.length}`+(lkO===true?chip(' · N도 포함','#5e5'):lkO===false?'<span style="color:#666"> · N 미포함</span>':'');
 if(s.fashion)html+=`<br>fashion: ${s.fashion}`;
 // ③ how the identity was READ: cohort size · reliability(split-half drift, lower=better) ·
 // what the face varies with (top PC axis) · whether an ArcFace centroid was formed.
 const lkR=SEL.likeness;
 if(lkR)html+=sbar(`n_obs ${lkR.n_obs} · 신뢰도 drift ${nf(lkR.drift)} · 주변화축 ${lkR.top_axis?chip(lkR.top_axis[0]+' '+lkR.top_axis[1],'#7ab0ea'):'—'} · face_id ${lkR.face_id?chip('✓','#5e5'):chip('✗','#888')}`);
 const ns=s.seams.filter(se=>Math.abs(se.frame-f)<=8)[0];
 if(ns)html+=`<br>seam@${ns.frame} ${ns.from}→${ns.to} cos=${ns.cos}${ns.cos!=null&&ns.cos<0.5?chip('suspect','#f66'):''}`;
 // PORTRAIT — verdict this frame
 html+=box('#d6a04b','PORTRAIT · f'+f+' · 프레임 단위',QRY.portrait,scopebar('frames',s.picks.portrait,'#d6a04b','프레임'));
 if(ex<0){html+=`<span style="color:#888">(subject absent — ~f${s.frames[i]})</span>`;}
 else{
   // GATE = the engine's real verdict (gate_trace.reason), not a re-decision.
   // admit/quarter/side are served views; reject:* / no_view are not.
   const g=s.gate[ex];
   // portrait is the FULL-cascade consumer: ① validity → ② policy (eyes/expr/pose-cone) → ③ routing.
   html+='GATE ①②③: '+(GPASS[g]?chip('✓ '+g.toUpperCase(),'#5e5'):g==='—'?chip('— (run portrait)','#888'):chip('✗ '+g,GCOL[g]||'#f66'));
   // which sub-gates FAILED at this exact frame (the blockers) and which view(s)
   // it routed to — read from the same gate_ladder the GATE band draws.
   const Lp=s.gate_ladder||{};
   const failed=GLAD.filter(([k,,,kd])=>kd==='rej'&&Lp[k]&&Lp[k][ex]===false).map(([,l])=>l);
   if(failed.length)html+=' '+chip('blocked: '+failed.join(','),'#f66');
   const routes=GLAD.filter(([k,,,kd])=>kd==='route'&&Lp[k]&&Lp[k][ex]===true).map(([,l])=>l);
   if(routes.length)html+=' '+chip('route: '+routes.join('/'),'#7ec8e6');
   const pp=s.picks.portrait||[];
   html+=`<br><span style="color:#a97">attention:</span> 점 {N} (프레임 독립 · 시간맥락 0) · 현재 N `+(GPASS[g]?chip('admit — 후보','#5e5'):chip('inactive — 미admit','#888'));
   html+='<br>pick: '+(pp[0]===f?chip('● rep','#5fef5f'):pp.slice(1).includes(f)?chip('○ alt','#3a8'):'—');
   // ③ WHY the rep won: objective = front·sharp·WARM(query proximity). n_admit = candidate pool.
   const pR=SEL.portrait;
   if(pR&&pR.rep){const t=pR.rep.terms||{};
     html+=sbar(`rep f${pR.rep.frame_idx} · obj ${nf(pR.rep.objective)} = front ${nf(t.front)} · sharp ${nf(t.sharp)} · `
       +chip('warm '+nf(t.warm),'#d6a04b')+`(qd ${t.query_dist==null?'—':nf(t.query_dist)}) · admit ${pR.n_admit}/${pR.n_total}`,'#d6a04b');}
   const yaw=val('yaw'),pit=val('pitch'),rol=val('roll'),bl=val('blink'),y6=val('yaw6d'),p6=val('pit6d'),r6=val('rol6d');
   const bad=(t,b)=>`<span style="color:${b?'#f66':'#bbb'}">${t}</span>`;
   const view=(s.setviews||{})[f];
   // the verdict above is now authoritative (no drift), so the set view just names
   // which bin served this frame — no contradiction to flag.
   if(view)html+='<br>set view: '+chip('◆ '+view,view==='side'?'#22ddee':'#d6a04b');
   if(yaw==null && y6!=null){
     // MediaPipe blank (profile) — the 6DRepNet triplet is the evidence that admitted
     // this side view; show it where the mp pose triplet would otherwise be empty.
     html+='<br>'+chip(`6d y${nf(y6,0)} p${nf(p6,0)} r${nf(r6,0)}° · profile (MediaPipe NaN)`,'#d6a04b')+' · blur '+nf(val('blur'),0);
   }else{
     // both backends live → per-axis Δ = the ALIGNMENT check at the playhead (all
     // three axes adapter-aligned 2026-07-02; a persistently large signed Δ would
     // mean convention drift, not noise).
     const d6=(y6!=null&&p6!=null&&r6!=null)?` <span style="color:#888">·6dΔ y${nf(y6-yaw,0)} p${nf(p6-pit,0)} r${nf(r6-rol,0)}</span>`:'';
     html+='<br>'+bad('yaw'+nf(yaw,0),Math.abs(yaw)>=20)+' '+bad('pit'+nf(pit,0),Math.abs(pit)>=20)+' '+bad('rol'+nf(rol,0),Math.abs(rol)>=20)
        +d6
        +' · '+bad('blink '+nf(bl),bl>=0.45)+' · blur '+nf(val('blur'),0);
   }
 }
 // HIGHLIGHT — in a picked segment?
 html+=box('#5fbf7a','HIGHLIGHT · f'+f+' · 구간 분석',QRY.highlight||'generic WHEN = max(impact·rarity·scene·valence⁺)',scopebar('segments',(s.picks.highlight||[]).map(g=>[g[0],g[1]]),'#5fbf7a','구간',RFHALF));
 // highlight's SWITCH = WHEN (action impact/rarity/scene) → delivered segment. seg carries
 // [start,end,score,peak,resolved]; score = the WHEN peak strength, peak = the WHEN-peak frame.
 const seg=(s.picks.highlight||[]).find(g=>f>=g[0]&&f<=g[1]);
 html+='WHEN: '+(seg?chip(`● segment [${seg[0]}–${seg[1]}] · score ${seg[2]}${seg[4]===false?' unres':''}`,'#e88c28')+(seg[3]===f?chip('◆ WHEN peak','#5fef5f'):''):chip('— no WHEN here','#888'));
 html+=`<br><span style="color:#8a9">attention:</span> 이동창 [f${Math.max(fmin,f-RFHALF)}–f${Math.min(fmax,f+RFHALF)}] ≈${nf(2*RFHALF/fps,1)}s (WHEN 입력 · 매 프레임 존재) · 전달 세그먼트 `+(seg?chip('안','#5e5'):chip('밖 (receptive field만 활성)','#888'));
 // ③ WHY this window fired: WHEN = max(impact, rarity, scene, valence⁺) — which twin carried it.
 const hR=(SEL.highlight||[]).find(g=>f>=g.lo&&f<=g.hi);
 if(hR&&hR.drivers)html+=sbar(`WHEN driver ${chip(hR.driver,'#e88c28')} = impact ${nf(hR.drivers.impact)} · rarity ${nf(hR.drivers.rarity)} · scene ${nf(hR.drivers.scene)} · val ${nf(hR.drivers.valence)}`,'#5fbf7a');
 // generated NL description of THIS moment + its LLM-judge match to the authored attraction
 // expectation (the language-space, context-conditioned criterion — highlight_lang stage).
 const lg=SEL.lang||{}, lc=(lg.by_frame||{})[f];
 if(lc)html+=sbar(`LANG <span style="color:#cfc;font-style:italic">"${lc.desc}"</span>`,'#9c9')
   +`<br>&nbsp;&nbsp;&nbsp;&nbsp;match ${chip(nf(lc.lang),'#e88c28')} (위 기준 대비) · scene ${lc.scene||'—'}`;
 // ① VALIDITY gates WHICH (face state), NOT WHEN (action): an invalid frame can sit in a
 // segment (WHEN fires on the action) but can never be its rep (WHICH zeroed).
 const hv=ex>=0&&(s.gate_ladder||{}).valid?s.gate_ladder.valid[ex]:null;
 if(ex>=0)html+='<br>WHICH (rep, ① valid): '+(hv===true?chip('✓ eligible','#5e5'):hv===false?chip('✗ WHICH=0 (still counts toward WHEN)','#f66'):'—');
 // EMOTION — the directed HSEmotion reading (sign = direction, NOT degree), read
 // person-relative against this rider's own baseline (bright/low FOR THEM).
 const vv=val('valence'), b=s.emo_base||{};
 if(vv!=null){
   const dir = vv>0.1?'+ positive':vv<-0.1?'− negative':'~ neutral';
   const dcol = vv>0.1?'#5e5':vv<-0.1?'#f66':'#bbb';
   let rel='';
   if(b.p50!=null) rel = (b.p90!=null&&vv>=b.p90)?'bright FOR THEM'
                       : (b.p10!=null&&vv<=b.p10)?'low FOR THEM':'mid for them';
   html+=`<br>valence ${nf(vv)} ${chip(dir,dcol)} · em_conf ${nf(val('em_conf'))}`
       + (b.p50!=null?`<br><span style="color:#9c9">self center ${nf(b.p50)} (p10 ${nf(b.p10)}…p90 ${nf(b.p90)}) → ${rel}</span>`:'');
   if(b.style_low)html+=`<br><span style="color:#888">expresses: high=${(b.style_high||[]).join('/')} · low=${(b.style_low||[]).join('/')}</span>`;
 }
 if(val('cos_cust')!=null)html+=`<br>cos_cust ${nf(val('cos_cust'))} · cos_bg ${nf(val('cos_bg'))}`;
 if(_open)html+='</div>';        // close the last product box
 ro.innerHTML=html;
}
if('requestVideoFrameCallback' in HTMLVideoElement.prototype){
 // primary: rVFC gives the PRESENTED frame's mediaTime → box matches the visible
 // frame (and the preview, which samples the live video).
 const onF=(now,meta)=>{setDisp(frameOf(meta.mediaTime));v.requestVideoFrameCallback(onF);};v.requestVideoFrameCallback(onF);
}else{
 // fallback: a 60Hz rAF loop while playing tracks currentTime tightly. (`timeupdate`
 // fires only ~4×/s — way too coarse for a frame-accurate overlay at 6 fps.)
 let raf=0;const loop=()=>{setDisp(frameOf(v.currentTime));raf=requestAnimationFrame(loop);};
 v.addEventListener('play',()=>{if(!raf)loop();});
 v.addEventListener('pause',()=>{cancelAnimationFrame(raf);raf=0;setDisp(frameOf(v.currentTime));});
}
v.addEventListener('seeked',()=>setDisp(frameOf(v.currentTime)));
v.addEventListener('loadeddata',()=>{sizeOv();setCropSrc();tabs();setDisp(frameOf(v.currentTime));});
window.addEventListener('resize',()=>{sizeOv();draw();});
[tDet,tPort,tOthers,tMesh,tGdetail,tROI].forEach(t=>t.addEventListener('change',draw));
cv.addEventListener('click',e=>{const r=cv.getBoundingClientRect();const cy=e.clientY-r.top;
 if(_gateStrip&&cy>=_gateStrip[0]&&cy<=_gateStrip[1]){tGdetail.checked=true;draw();return;}  // 접힌 스트립 클릭 = 펼침
 seekFrame(Math.round(fmin+(e.clientX-r.left-LEFT)/W*(fmax-fmin)));});
document.addEventListener('keydown',e=>{if(e.key==='ArrowLeft'){seekFrame(frameOf(v.currentTime)-1);e.preventDefault();}
 if(e.key==='ArrowRight'){seekFrame(frameOf(v.currentTime)+1);e.preventDefault();} if(e.key===' '){v.paused?v.play():v.pause();e.preventDefault();}});
</script></body></html>"""

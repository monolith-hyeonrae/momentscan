"""tubelet inspect — INTERACTIVE (browser), v1.

One page per CLIP. Scrub the video ↔ synced cursor on signal lanes, raw values at
cursor (verify signal-vs-face). Plus:
  • STITCH 검증 — FRAGMENTS lane (raw track_id colors) + seam ticks + cross-seam
    ArcFace cosine (the re-id's own evidence: low = suspect merge).
  • MULTI-SUBJECT — subject tabs, active-subject bbox drawn over the video
    (which face in a crowd), CO-PRESENCE strip (who is present per frame).

Run: python tubelet_inspect_html.py <clip_id>   then open the printed .html
"""
from __future__ import annotations
import sys, json, subprocess, os
import numpy as np, polars as pl, cv2

ROOT = "/home/hyeonrae/repo/monolith/momentscan"
CLIP = sys.argv[1] if len(sys.argv) > 1 else "cap_1"
D = f"{ROOT}/output/l2/{CLIP}"
OUT = f"{D}/inspect"; os.makedirs(OUT, exist_ok=True)
FPS = 6

h264 = f"{OUT}/detect_h264.mp4"
if not os.path.exists(h264):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{D}/detect.mp4",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-x264-params", "keyint=1",
                    "-an", h264], check=True)
    print("transcoded ->", h264)

# CLEAN source (detect.mp4 has the tracker box burned in → bad for the crop preview).
# original decoded at fps=6 is frame-aligned with detect.mp4 (verified: equal frame count).
SRC = next((c for c in [os.path.expanduser(f"~/Videos/reaction_test/{CLIP}.mp4"),
                        os.path.expanduser(f"~/Videos/reaction_test/{CLIP}.mov")] if os.path.exists(c)), None)
clean_mp4 = f"{OUT}/clean_h264.mp4"
if SRC and not os.path.exists(clean_mp4):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", SRC, "-vf", "fps=6",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-x264-params", "keyint=1",
                    "-an", clean_mp4], check=True)
    print("clean source ->", clean_mp4)
CLEAN_SRC = "clean_h264.mp4" if os.path.exists(clean_mp4) else ""

tub = pl.read_parquet(f"{D}/tubelets.parquet").sort(["track_id", "frame_idx"])
det = pl.read_parquet(f"{D}/detections.parquet").sort(["subject_id", "frame_idx"])
det_emb = np.array(det["embedding"].to_list(), float)
det_idx = {(r["subject_id"], r["frame_idx"]): i for i, r in enumerate(det.iter_rows(named=True))}
det_trk = {(r["subject_id"], r["frame_idx"]): r["track_id"] for r in det.iter_rows(named=True)}
lm = pl.read_parquet(f"{D}/landmarks.parquet").sort("frame_idx")
lm_bs = {(r["track_id"], r["frame_idx"]): np.array(r["blendshapes"], float)
         for r in lm.iter_rows(named=True) if r["blendshapes"] is not None}
lm_tf = {(r["track_id"], r["frame_idx"]): np.array(r["transform"], float).reshape(4, 4)
         for r in lm.iter_rows(named=True) if r["transform"] is not None}
try:
    sc = pl.read_parquet(f"{D}/scene.parquet").sort("frame_idx")
    sc_map = {r["frame_idx"]: r for r in sc.iter_rows(named=True)} if "customer_embedding" in sc.columns else {}
except Exception:
    sc_map = {}
cap = cv2.VideoCapture(f"{D}/detect.mp4")
VW, VH = int(cap.get(3)), int(cap.get(4))


def euler(M):
    R = M[:3, :3]
    return (float(np.degrees(np.arctan2(-R[2, 0], np.hypot(R[0, 0], R[1, 0])))),
            float(np.degrees(np.arctan2(R[2, 1], R[2, 2]))),
            float(np.degrees(np.arctan2(R[1, 0], R[0, 0]))))


def build(sid):
    df = tub.filter(pl.col("track_id") == sid).sort("frame_idx")
    fx = df["frame_idx"].to_numpy()
    bbox = np.array(df["bbox"].to_list(), float)
    role = df["rider_role"][0]
    emb = np.array(df["embedding"].to_list(), float)
    detsc = df["det_score"].to_numpy().astype(float)
    en = emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9)
    c = en.mean(0); c /= np.linalg.norm(c) + 1e-9
    iddev = 1 - en @ c
    N = len(fx)

    # raw track per frame (pre-stitch fragment) + seams + cross-seam ArcFace cos
    raw = [det_trk.get((sid, int(f)), -1) for f in fx]
    seams = []
    for k in range(1, N):
        if raw[k] != raw[k - 1] and raw[k] >= 0 and raw[k - 1] >= 0:
            ia, ib = det_idx.get((sid, int(fx[k - 1]))), det_idx.get((sid, int(fx[k])))
            cos = None
            if ia is not None and ib is not None:
                a, b = det_emb[ia], det_emb[ib]
                cos = round(float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9)), 3)
            seams.append({"frame": int(fx[k]), "cos": cos, "from": int(raw[k - 1]), "to": int(raw[k]),
                          "gap": int(fx[k] - fx[k - 1])})

    yaw = np.full(N, np.nan); pit = yaw.copy(); rol = yaw.copy()
    blink = yaw.copy(); smile = yaw.copy(); jaw = yaw.copy(); exprm = yaw.copy()
    bl = [lm_bs.get((sid, int(f))) for f in fx]
    haveb = [b for b in bl if b is not None]
    bmed = np.median(haveb, axis=0) if haveb else np.zeros(52)
    for k, f in enumerate(fx):
        b = lm_bs.get((sid, int(f))); M = lm_tf.get((sid, int(f)))
        if M is not None: yaw[k], pit[k], rol[k] = euler(M)
        if b is not None:
            blink[k] = max(b[9], b[10]); smile[k] = max(b[42], b[43]); jaw[k] = b[25]
            exprm[k] = float(np.linalg.norm(b - bmed))

    bright = np.full(N, np.nan); harsh = bright.copy(); blur = bright.copy()
    for k, f in enumerate(fx):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(f)); ok, img = cap.read()
        if not ok: continue
        x1, y1, x2, y2 = bbox[k].astype(int); x1, y1 = max(0, x1), max(0, y1)
        cr = img[y1:y2, x1:x2]
        if cr.size == 0: continue
        g = cv2.cvtColor(cr, cv2.COLOR_BGR2GRAY).astype(float)
        bright[k] = g.mean()
        harsh[k] = float(np.median(np.abs(cv2.Laplacian(cv2.GaussianBlur(g, (0, 0), 2), cv2.CV_64F))))
        blur[k] = float(cv2.Laplacian(g, cv2.CV_64F).var())

    blur_t = float(np.nanpercentile(blur, 30)) if np.isfinite(blur).any() else 0
    gate = []
    for k in range(N):
        r = "pass"
        if blur[k] < blur_t: r = "blur"
        if jaw[k] >= 0.5: r = "jaw"
        if abs(yaw[k]) >= 20 or abs(pit[k]) >= 20 or abs(rol[k]) >= 20: r = "pose"
        if blink[k] >= 0.45: r = "eyes"
        gate.append(r)

    cu = np.full(N, np.nan); bg = cu.copy()
    for k, f in enumerate(fx):
        r = sc_map.get(int(f))
        if r and r.get("customer_embedding") is not None:
            cl = np.array(r["embedding"], float); c1 = np.array(r["customer_embedding"], float); c2 = np.array(r["bg_embedding"], float)
            cu[k] = float(cl @ c1 / (np.linalg.norm(cl) * np.linalg.norm(c1) + 1e-9))
            bg[k] = float(cl @ c2 / (np.linalg.norm(cl) * np.linalg.norm(c2) + 1e-9))

    def ch(name, group, vals, color, lo=None, hi=None):
        v = np.asarray(vals, float)
        fin = v[np.isfinite(v)]
        lo = (float(fin.min()) if len(fin) else 0) if lo is None else lo
        hi = (float(fin.max()) if len(fin) else 1) if hi is None else hi
        return {"name": name, "group": group, "color": color,
                "vals": [None if not np.isfinite(x) else round(float(x), 4) for x in v], "lo": lo, "hi": hi}

    channels = [
        ch("self_dev", "identity", iddev, [90, 220, 220]), ch("det", "identity", detsc, [150, 150, 150], 0, 1),
        ch("yaw", "pose", yaw, [90, 200, 90], -60, 60), ch("pitch", "pose", pit, [80, 170, 255], -45, 45),
        ch("roll", "pose", rol, [220, 160, 80], -45, 45),
        ch("blink", "expression", blink, [255, 140, 70], 0, 1), ch("smile", "expression", smile, [110, 230, 130], 0, 1),
        ch("jaw", "expression", jaw, [200, 130, 90], 0, 1), ch("expr_mag", "expression", exprm, [200, 130, 230]),
        ch("bright", "lighting", bright, [120, 220, 220], 0, 255), ch("harsh", "lighting", harsh, [90, 150, 240]),
        ch("blur", "lighting", blur, [150, 150, 150]),
    ]
    if sc_map:
        channels += [ch("cos_cust", "scene", cu, [110, 200, 110], 0, 1), ch("cos_bg", "scene", bg, [150, 150, 150], 0, 1)]

    return {"sid": int(sid), "role": role, "frames": [int(f) for f in fx],
            "bbox": [[round(float(x), 1) for x in b] for b in bbox],
            "gate": gate, "channels": channels, "raw": [int(t) for t in raw], "seams": seams}


# main + aux first, then the rest; keep only subjects with enough detections
counts = tub.group_by("track_id").len().sort("len", descending=True)
sids = [r["track_id"] for r in counts.iter_rows(named=True) if r["len"] >= 20]
subjects = [build(s) for s in sids]
clip_data = {"clip": CLIP, "fps": FPS, "vw": VW, "vh": VH,
             "fmin": int(min(min(s["frames"]) for s in subjects)),
             "fmax": int(max(max(s["frames"]) for s in subjects)),
             "subjects": subjects}

HTML = r"""<!doctype html><html><head><meta charset=utf-8><title>inspect {clip}</title><style>
 body{{background:#161616;color:#ddd;font:13px system-ui,sans-serif;margin:0;padding:10px}}
 #top{{display:flex;gap:12px;align-items:flex-start}}
 #vwrap{{position:relative;width:600px}} video{{width:600px;display:block;background:#000;border:1px solid #333}}
 #ov{{position:absolute;left:0;top:0;pointer-events:none}}
 #readout{{font:12px ui-monospace,monospace;white-space:pre;min-width:240px}} #readout b{{color:#9fe}}
 canvas#c{{display:block;margin-top:8px;border:1px solid #2a2a2a;cursor:crosshair}}
 .hint{{color:#888;font-size:11px;margin:4px 0}} .tab{{display:inline-block;padding:3px 10px;margin:2px;border:1px solid #444;border-radius:4px;cursor:pointer}}
 .tab.on{{background:#2c4;color:#000;font-weight:bold}}
</style></head><body>
<div id=tabs></div>
<div id=top>
 <div id=vwrap><video id=v src="detect_h264.mp4" controls preload=auto></video><canvas id=ov></canvas></div>
 <div><div id=hdr></div><div class=hint>탭=subject 전환 · 캔버스 클릭=점프 · ←/→ 프레임 · 스페이스 재생</div><div id=readout></div></div>
 <div><div class=hint>portrait box 프리뷰 (4:5 · 무왜곡 · 최종 crop)</div><canvas id=prev width=176 height=220 style="border:1px solid #555;background:#000"></canvas></div>
</div>
<canvas id=c></canvas>
<video id=clean src="{clean_src}" muted preload=auto style="display:none"></video>
<script>
const DATA={data};
const v=document.getElementById('v'),cv=document.getElementById('c'),ctx=cv.getContext('2d');
const ov=document.getElementById('ov'),octx=ov.getContext('2d'),ro=document.getElementById('readout'),hdr=document.getElementById('hdr');
const prev=document.getElementById('prev'),pctx=prev.getContext('2d');
const clean=document.getElementById('clean'),hasClean=!!clean.getAttribute('src');
const PASPECT=0.8,FACEH=0.62,EYE=0.42;   // portrait box: w/h, face frac of height, eye height frac (preset)
function pbox(b){{const fh=b[3]-b[1],cx=(b[0]+b[2])/2,H=fh/FACEH,Wd=H*PASPECT,eyeY=b[1]+EYE*fh,top=eyeY-EYE*H,left=cx-Wd/2;return [left,top,left+Wd,top+H];}}
const fps=DATA.fps,fmin=DATA.fmin,fmax=DATA.fmax;
const GCOL={{pass:'#5ac85a',eyes:'#3c82d2',pose:'#e68c28',jaw:'#aa5ac8',blur:'#828282'}};
const SCOL=['#5ac85a','#3ca0e6','#e6a050','#c85ac8','#50c8c8','#c8c850'];   // subject colors
const FCOL=['#e05050','#50b0e0','#80d060','#d0a040','#b070d0','#50c0b0','#d06090','#9090d0']; // fragment(track) colors
let cur=0;  // active subject index
const W=Math.min(1700,Math.max(700,(fmax-fmin)*2));
const LEFT=92,GATE=18,FRAG=16,COPRES=Math.max(14,DATA.subjects.length*9),LANE=46,PAD=6,TOP=4;
function xo(f){{return LEFT+Math.round((f-fmin)/Math.max(1,fmax-fmin)*(W-1));}}
let DISP=fmin;
const fset=DATA.subjects.map(s=>{{const m=new Map();s.frames.forEach((f,i)=>m.set(f,i));return m;}});
function exactIdx(ci,f){{const m=fset[ci].get(f);return m==null?-1:m;}}
function sizeOverlay(){{ov.width=DATA.vw;ov.height=DATA.vh;ov.style.width=v.clientWidth+'px';ov.style.height=v.clientHeight+'px';}}
function setDisp(f){{DISP=Math.max(fmin,Math.min(fmax,f));if(hasClean&&v.paused)clean.currentTime=DISP/fps;draw();}}
function tabs(){{
 const t=document.getElementById('tabs');t.innerHTML='';
 DATA.subjects.forEach((s,i)=>{{const d=document.createElement('span');d.className='tab'+(i==cur?' on':'');
  d.textContent=`subject ${{s.sid}} [${{s.role}}] n=${{s.frames.length}}`;d.style.borderColor=SCOL[i%6];
  d.onclick=()=>{{cur=i;tabs();draw();}};t.appendChild(d);}});
 const s=DATA.subjects[cur];hdr.innerHTML=`<b>${{DATA.clip}}</b> · subject <b>${{s.sid}}</b> [${{s.role}}] · n=${{s.frames.length}} · fragments=${{new Set(s.raw).size}} · seams=${{s.seams.length}}`;
}}
function groupsOf(s){{return [...new Set(s.channels.map(c=>c.group))];}}
function setH(){{const s=DATA.subjects[cur];cv.width=LEFT+W+10;cv.height=TOP+GATE+PAD+FRAG+PAD+COPRES+PAD+groupsOf(s).length*(LANE+PAD)+8;}}
function nearestIdx(s,f){{let b=0,bd=1e9;s.frames.forEach((ff,j)=>{{let d=Math.abs(ff-f);if(d<bd){{bd=d;b=j;}}}});return b;}}
function draw(){{
 const s=DATA.subjects[cur];setH();ctx.fillStyle='#161616';ctx.fillRect(0,0,cv.width,cv.height);
 ctx.font='11px monospace';let y=TOP;const cw=Math.max(1,W/(fmax-fmin+1));
 // GATE
 ctx.fillStyle='#bbb';ctx.fillText('GATE',4,y+13);
 s.frames.forEach((f,i)=>{{ctx.fillStyle=GCOL[s.gate[i]]||'#444';ctx.fillRect(xo(f),y,cw+1,GATE);}});y+=GATE+PAD;
 // FRAGMENTS + seams
 ctx.fillStyle='#bbb';ctx.fillText('FRAG',4,y+12);
 const tracks=[...new Set(s.raw)];
 s.frames.forEach((f,i)=>{{ctx.fillStyle=FCOL[tracks.indexOf(s.raw[i])%FCOL.length];ctx.fillRect(xo(f),y,cw+1,FRAG);}});
 s.seams.forEach(se=>{{const x=xo(se.frame);ctx.strokeStyle='#fff';ctx.beginPath();ctx.moveTo(x,y-1);ctx.lineTo(x,y+FRAG+1);ctx.stroke();
   ctx.fillStyle=se.cos!=null&&se.cos<0.5?'#f55':'#9f9';ctx.fillText((se.cos==null?'?':se.cos),x+1,y+FRAG-3);}});y+=FRAG+PAD;
 // CO-PRESENCE (all subjects)
 ctx.fillStyle='#bbb';ctx.fillText('CO-PRES',4,y+10);
 DATA.subjects.forEach((ss,si)=>{{const yy=y+si*9;const fs=new Set(ss.frames);
   ctx.fillStyle=SCOL[si%6];ss.frames.forEach(f=>ctx.fillRect(xo(f),yy,cw+1,7));}});y+=COPRES+PAD;
 // channel lanes
 for(const g of groupsOf(s)){{ctx.fillStyle='#222';ctx.fillRect(LEFT,y,W,LANE);ctx.fillStyle='#bbb';ctx.fillText(g,4,y+13);
   let lx=4;for(const c of s.channels.filter(c=>c.group===g)){{const col=`rgb(${{c.color}})`;
     ctx.fillStyle=col;ctx.fillText(c.name,lx,y+LANE-4);lx+=Math.max(54,c.name.length*7);
     ctx.strokeStyle=col;ctx.beginPath();let st=false;
     for(let i=0;i<s.frames.length;i++){{const val=c.vals[i];if(val==null){{st=false;continue;}}
       const t=(val-c.lo)/(c.hi-c.lo+1e-9),yy=y+LANE-3-Math.max(0,Math.min(1,t))*(LANE-6);
       if(!st){{ctx.moveTo(xo(s.frames[i]),yy);st=true;}}else ctx.lineTo(xo(s.frames[i]),yy);}}ctx.stroke();}}y+=LANE+PAD;}}
 // cursor
 const f=DISP,x=xo(f);ctx.strokeStyle='#fff';ctx.beginPath();ctx.moveTo(x,TOP);ctx.lineTo(x,cv.height-6);ctx.stroke();
 // bbox overlay — EXACT frame only, native coords (no scale error), dashed = our marker; hide when subject absent
 const ex=exactIdx(cur,f),i=ex>=0?ex:nearestIdx(s,f);
 octx.clearRect(0,0,ov.width,ov.height);
 if(ex>=0){{const b=s.bbox[ex];octx.strokeStyle=SCOL[cur%6];octx.lineWidth=2.5;octx.setLineDash([7,5]);
   octx.strokeRect(b[0],b[1],b[2]-b[0],b[3]-b[1]);octx.setLineDash([]);
   const p=pbox(b);octx.strokeStyle='#22ddee';octx.lineWidth=2;octx.strokeRect(p[0],p[1],p[2]-p[0],p[3]-p[1]);
   octx.fillStyle='#22ddee';octx.font='14px monospace';octx.fillText('portrait',p[0]+3,p[1]+15);octx.font='11px monospace';
   pctx.fillStyle='#000';pctx.fillRect(0,0,prev.width,prev.height);
   const srcEl=(hasClean&&clean.readyState>=2)?clean:v;   // clean source = no burned-in tracker box
   try{{pctx.drawImage(srcEl,p[0],p[1],p[2]-p[0],p[3]-p[1],0,0,prev.width,prev.height);}}catch(e){{}}
 }}else{{pctx.clearRect(0,0,prev.width,prev.height);}}
 // readout
 let txt=`frame ${{f}}   ${{ex>=0?'gate='+s.gate[ex]:'(absent ~f'+s.frames[i]+')'}}   raw_track=${{ex>=0?s.raw[ex]:'-'}}\n`;
 const ns=s.seams.filter(se=>Math.abs(se.frame-f)<=8)[0];if(ns)txt+=`seam@${{ns.frame}} ${{ns.from}}→${{ns.to}} cos=${{ns.cos}} gap=${{ns.gap}}f\n`;
 for(const g of groupsOf(s)){{txt+=`[${{g}}]\n`;for(const c of s.channels.filter(c=>c.group===g)){{txt+=`  ${{c.name.padEnd(9)}} ${{c.vals[i]==null?'—':c.vals[i]}}\n`;}}}}
 ro.innerHTML=txt.replace(/frame \d+/,m=>`<b>${{m}}</b>`);
}}
if('requestVideoFrameCallback' in HTMLVideoElement.prototype){{const onF=(now,meta)=>{{setDisp(Math.round(meta.mediaTime*fps));v.requestVideoFrameCallback(onF);}};v.requestVideoFrameCallback(onF);}}
else{{v.addEventListener('timeupdate',()=>setDisp(Math.round(v.currentTime*fps)));}}
v.addEventListener('seeked',()=>setDisp(Math.round(v.currentTime*fps)));
v.addEventListener('loadeddata',()=>{{sizeOverlay();tabs();setDisp(Math.round(v.currentTime*fps));}});
window.addEventListener('resize',()=>{{sizeOverlay();draw();}});
if(hasClean){{v.addEventListener('play',()=>clean.play());v.addEventListener('pause',()=>{{clean.pause();clean.currentTime=v.currentTime;}});clean.addEventListener('seeked',draw);}}
cv.addEventListener('click',e=>{{const r=cv.getBoundingClientRect();v.currentTime=Math.max(0,(fmin+(e.clientX-r.left-LEFT)/W*(fmax-fmin))/fps);}});
document.addEventListener('keydown',e=>{{if(e.key==='ArrowLeft'){{v.currentTime=Math.max(0,v.currentTime-1/fps);e.preventDefault();}}
 if(e.key==='ArrowRight'){{v.currentTime+=1/fps;e.preventDefault();}} if(e.key===' '){{v.paused?v.play():v.pause();e.preventDefault();}}}});
tabs();draw();
</script></body></html>"""

p = f"{OUT}/clip.html"
with open(p, "w") as fh:
    fh.write(HTML.format(clip=CLIP, clean_src=CLEAN_SRC, data=json.dumps(clip_data, separators=(",", ":"))))
print(f"clip {CLIP}: {len(subjects)} subjects -> {p}")
for s in subjects:
    print(f"  subject {s['sid']} [{s['role']}] n={len(s['frames'])} fragments={len(set(s['raw']))} seams={len(s['seams'])}")

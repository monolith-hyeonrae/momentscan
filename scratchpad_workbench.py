"""샘플링 워크벤치 v0 (2026-07-21, 원장 ⑫) — user 도구 3종 발상의 통합 계기.

층 구성:
  데이터층  = frame_table: 클립·트랙의 전 신호를 와이드 행으로 (오늘 프로브 4종이
              반복한 조인의 단일홈; stash 읽기-전용 파생, 영속화 없음=이중-진실 방지)
  인터랙션층 = HTML 다이얼 시뮬레이터: 1단 품질 스크린(floor — 결정경계를 좁힘, 퍼널
              표시) / 2단 대표성 랭킹(가중 — 우선순위 깃발). 측정=영속이라 JS 실시간.
  축적층    = 클릭 GT: 프레임 pos/neg 깃발 → export(.jsonl) → fixtures/eval/ (user 확정
              홈). 수용-집합 원형(P2)의 likeness-샘플링 적용, 프레임-수준=정책-강건.

드리프트 방어: JS 사다리는 만들지 않는다 — 명시 floor(사다리는 생산 상세). 로드 시
셀프테스트 = JS가 기본 설정으로 뽑은 픽 ≡ 파이썬이 같은(반올림된) 데이터로 뽑은 픽.
봉인 전 최종 확인은 항상 파이썬 카드(v7 계기) 재실행으로.
스코프 v0 = center 픽만 (hair 빈은 v1). 표시 썸네일은 표본화(수치는 전 행 기준).
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import polars as pl

sys.path.insert(0, "apps/momentscan/src")
from momentscan.infra.store.stash import read_landmarks, read_features, read_tubelets
from momentscan.perception.readings.geometry import canonicalize
from momentscan.preset import resolve

from momentscan_features_specialist45d.registry import INDEX
from momentscan_features_specialist45d.specialists import BLENDSHAPE_ORDER

from scratchpad_likeness_sat import skin_sv

RACE = resolve("race981")
FRONTAL_DEG = RACE.camera.frontal_deg
CLIPS = ("test_3", "test_12", "dual_2", "test_4", "test_0", "international_1")
THUMB = 112

# 기본 설정 = v7.2 등가(단일-floor 의미론) — JS DEF와 문자 그대로 동일해야 함
DEFAULT_CFG = {"sym_max": 0.6, "dev_max": 15.0, "pu_min": 0.4, "cs_min": 0.0,
               "mv_min": 0.0, "lt_min": 0.0, "ex_max": 1.0, "gap_min": 12,
               "w_expr": 0.30, "w_pu": 0.15, "w_q3": 0.20, "w_vis2": 0.15, "w_light": 0.20}


def face_signals(P):
    def d2(a, b):
        return np.linalg.norm(P[:, a, :2] - P[:, b, :2], axis=1)
    r_iris = (d2(469, 471) + d2(470, 472)) / 2 + 1e-9
    l_iris = (d2(474, 476) + d2(475, 477)) / 2 + 1e-9
    pupil = (d2(159, 145) / r_iris + d2(386, 374) / l_iris) / 2
    dr = np.abs(P[:, 1, 0] - P[:, 234, 0]) + 1e-9
    dl = np.abs(P[:, 454, 0] - P[:, 1, 0]) + 1e-9
    return pupil, np.abs(np.log(dr / dl))


def pct_rank(x):
    out = np.full(len(x), np.nan)
    fin = np.isfinite(x)
    if fin.sum():
        v = x[fin]
        out[fin] = np.array([float(np.mean(v <= xi)) * 100 for xi in x[fin]])
    return out


def rank01(x, flip=False):
    r = np.argsort(np.argsort(np.nan_to_num(x, nan=(np.inf if flip else -np.inf))))
    r = r / max(len(x) - 1, 1)
    return 1 - r if flip else r


def frame_table(clip_id: str, out_root: Path):
    """클립 main rider의 전 신호 와이드 테이블 (+썸네일용 컨텍스트)."""
    rec = json.load(open(out_root / clip_id / "likeness.json"))
    tid, rider = next((int(t), r) for t, r in rec["riders"].items() if r.get("role") == "main")
    lm = read_landmarks(out_root, clip_id).filter(pl.col("track_id") == tid).sort("frame_idx")
    gt = pl.read_parquet(out_root / clip_id / "gate_trace.parquet").filter(pl.col("track_id") == tid)
    valid = set(gt.filter(pl.col("valid"))["frame_idx"].to_list())
    keep = lm["frame_idx"].is_in(list(valid))
    if int(keep.sum()) >= 10:
        lm = lm.filter(keep)
    fx = lm["frame_idx"].to_numpy()
    n = len(fx)
    P = np.array(lm["landmarks"].to_list(), dtype=np.float64).reshape(n, 478, 3)
    T = np.array(lm["transform"].to_list(), dtype=np.float64).reshape(n, 4, 4)
    cb = np.array(lm["crop_box"].to_list(), dtype=np.float64)
    canonicalize(P, T, cb)

    feats = read_features(out_root, clip_id, "A").filter(pl.col("track_id") == tid).sort("frame_idx")
    pos = {f: i for i, f in enumerate(feats["frame_idx"].to_numpy())}
    M = np.array(feats["feature"].to_list(), dtype=np.float64)
    sel = np.array([pos[f] for f in fx])
    yaw = M[sel, INDEX["head_yaw_dev"]]
    blur = M[sel, INDEX["face_blur"]]

    pq = pl.read_parquet(out_root / clip_id / "parse.parquet").filter(pl.col("track_id") == tid)
    g = lambda col: (dict(zip(pq["frame_idx"].to_list(), pq[col].to_list())) if col in pq.columns else {})
    micro_of, mv_of, lum_of, hi_of = g("face_micro"), g("mouth_vis"), g("skin_lum"), g("skin_clip_hi")
    micro = np.array([micro_of.get(int(f), np.nan) for f in fx], float)
    mv = np.array([mv_of.get(int(f), np.nan) for f in fx], float)
    lum = np.array([lum_of.get(int(f), np.nan) for f in fx], float)
    chi = np.array([hi_of.get(int(f), np.nan) for f in fx], float)
    lum_eff = lum * (1.0 - np.nan_to_num(chi, nan=0.0))

    det = pl.read_parquet(out_root / clip_id / "detections.parquet").filter(pl.col("track_id") == tid)
    erows = [(int(f), np.asarray(e, float)) for f, e in
             zip(det["frame_idx"].to_list(), det["embedding"].to_list()) if e is not None]
    cs = np.full(n, np.nan)
    nrm = np.full(n, np.nan)
    if len(erows) >= 10:
        dfr = np.array([f for f, _ in erows])
        dE = np.stack([e for _, e in erows])
        dn = np.linalg.norm(dE, axis=1)
        Eh = dE / dn[:, None]
        c0 = np.median(Eh, axis=0)
        c0 /= np.linalg.norm(c0)
        cs_of = dict(zip(dfr.tolist(), (Eh @ c0).tolist()))
        nm_of = dict(zip(dfr.tolist(), dn.tolist()))
        cs = np.array([cs_of.get(int(f), np.nan) for f in fx])
        nrm = np.array([nm_of.get(int(f), np.nan) for f in fx])

    tb = read_tubelets(out_root, clip_id).filter(pl.col("track_id") == tid)
    ph = dict(zip(tb["frame_idx"].to_list(), tb["scene_phase"].to_list()))
    board = np.array([ph.get(int(f)) == "boarding" for f in fx])

    B = np.array(lm["blendshapes"].to_list(), dtype=np.float64)
    ecols = [i for i, nm_ in enumerate(BLENDSHAPE_ORDER)
             if nm_ != "_neutral" and not nm_.startswith("eyeLook")]
    expr = B[:, ecols].max(axis=1)
    pupil, sym = face_signals(P)
    return dict(tid=tid, rider=rider, fx=fx, cb=cb, P=P, yaw=yaw, blur=blur, micro=micro,
                mv=mv, lum_eff=lum_eff, cs=cs, nrm=nrm, board=board, expr=expr,
                pupil=pupil, sym=sym)


def compute_picks(rows, cfg):
    """JS 시뮬레이터와 문자 그대로 동일한 의미론 (반올림된 shipped 값 위에서)."""
    surv = [r for r in rows
            if r["sy"] < cfg["sym_max"] and abs(r["dv"]) < cfg["dev_max"]
            and r["pu"] >= cfg["pu_min"]
            and (r["cs"] is None or r["cs"] >= cfg["cs_min"])
            and (r["mv"] is None or r["mv"] >= cfg["mv_min"])
            and (r["lt"] is None or r["lt"] >= cfg["lt_min"])
            and r["ex"] <= cfg["ex_max"]]
    for r in surv:
        r["_s"] = (cfg["w_expr"] * r["r"][0] + cfg["w_pu"] * r["r"][1]
                   + cfg["w_q3"] * r["r"][2] + cfg["w_vis2"] * r["r"][3]
                   + cfg["w_light"] * r["r"][4])
    surv.sort(key=lambda r: -r["_s"])
    got = []
    for r in surv:
        if all(abs(r["f"] - o["f"]) >= cfg["gap_min"] for o in got):
            got.append(r)
        if len(got) == 3:
            break
    return [r["f"] for r in got]


def build_clip(clip_id, out_root, wb_dir):
    t = frame_table(clip_id, out_root)
    fx, cb, P = t["fx"], t["cb"], t["P"]
    n = len(fx)

    # chroma + 썸네일: 한 번의 순차 디코드
    dev = t["yaw"] - FRONTAL_DEG
    thumbable = (t["sym"] < 1.3) & (t["pupil"] >= 0.25) & (np.abs(dev) < 25)
    tidx = np.where(thumbable)[0]
    if len(tidx) > 120:
        tidx = tidx[np.unique(np.linspace(0, len(tidx) - 1, 120).astype(int))]
    cur = [f for f in t["rider"]["samples"]["center_nearest"]]
    tset = set(int(fx[i]) for i in tidx) | set(int(c) for c in cur if c in set(fx.tolist()))
    row_of = {int(f): i for i, f in enumerate(fx)}
    chroma = np.full(n, np.nan)
    tdir = wb_dir / "thumbs" / clip_id
    tdir.mkdir(parents=True, exist_ok=True)
    thumb_ok = set()
    cap = cv2.VideoCapture(str(out_root / clip_id / "detect.mp4"))
    fidx = 0
    while True:
        ok, frm = cap.read()
        if not ok:
            break
        i = row_of.get(fidx)
        if i is not None:
            cbv = cb[i]
            pts = np.stack([cbv[0] + P[i, :, 0] * (cbv[2] - cbv[0]),
                            cbv[1] + P[i, :, 1] * (cbv[3] - cbv[1])], 1)
            r = skin_sv(frm, pts, cbv)
            if r is not None:
                chroma[i] = r[3]
            if fidx in tset:
                x1, y1, x2, y2 = (int(v) for v in cbv)
                if x2 - x1 > 1 and y2 - y1 > 1:
                    tile = cv2.resize(frm[max(0, y1):y2, max(0, x1):x2], (THUMB, THUMB))
                    cv2.imwrite(str(tdir / f"f{fidx:05d}.jpg"), tile,
                                [cv2.IMWRITE_JPEG_QUALITY, 82])
                    thumb_ok.add(fidx)
        fidx += 1
    cap.release()

    micro_pct, sharp_pct = pct_rank(t["micro"]), pct_rank(t["blur"])
    norm_pct, cs_pct, mv_pct = pct_rank(t["nrm"]), pct_rank(t["cs"]), pct_rank(t["mv"])
    light_pct = np.nanmean(np.vstack([pct_rank(t["lum_eff"]), pct_rank(chroma)]), axis=0)
    q3 = np.nanmean(np.vstack([sharp_pct, micro_pct, norm_pct]), axis=0)
    vis2 = np.nanmean(np.vstack([cs_pct, mv_pct]), axis=0)
    R = np.stack([rank01(t["expr"], flip=True), rank01(t["pupil"]), rank01(q3),
                  rank01(vis2), rank01(light_pct)], axis=1)

    def num(v, nd=2):
        return None if not np.isfinite(v) else round(float(v), nd)

    rows = []
    for i in range(n):
        rows.append({"f": int(fx[i]), "b": int(t["board"][i]),
                     "sy": round(float(t["sym"][i]), 3) if np.isfinite(t["sym"][i]) else 9.9,
                     "dv": round(float(dev[i]), 1) if np.isfinite(dev[i]) else 99.0,
                     "pu": round(float(t["pupil"][i]), 3) if np.isfinite(t["pupil"][i]) else 0.0,
                     "ex": round(float(t["expr"][i]), 3) if np.isfinite(t["expr"][i]) else 1.0,
                     "cs": num(cs_pct[i], 1), "mv": num(mv_pct[i], 1), "lt": num(light_pct[i], 1),
                     "r": [round(float(v), 4) for v in R[i]],
                     "th": (f"thumbs/{clip_id}/f{int(fx[i]):05d}.jpg" if int(fx[i]) in thumb_ok else None)})
    selftest = compute_picks([dict(r) for r in rows], DEFAULT_CFG)
    return {"clip": clip_id, "tid": t["tid"], "n": n, "cur": cur, "selftest": selftest,
            "rows": rows}


HTML = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><title>likeness sampling workbench v0</title>
<style>
body{background:#161616;color:#ddd;font:13px/1.45 system-ui,sans-serif;margin:0}
#top{position:sticky;top:0;background:#1d1d1d;border-bottom:1px solid #333;padding:8px 14px;z-index:9}
#selftest{font-weight:600}
.ok{color:#7c6} .bad{color:#e66}
#panel{position:fixed;left:0;top:52px;bottom:0;width:270px;overflow:auto;background:#1b1b1b;
  border-right:1px solid #333;padding:10px 14px;box-sizing:border-box}
#main{margin-left:270px;padding:10px 16px}
.grp{margin:10px 0 4px;color:#9ad;font-weight:600;font-size:12px;text-transform:uppercase}
.dial{margin:6px 0}
.dial label{display:flex;justify-content:space-between;font-size:12px;color:#bbb}
.dial input[type=range]{width:100%}
.clip{margin:26px 0;border-top:1px solid #2c2c2c;padding-top:10px}
.funnel{color:#9a8;font-size:12px;margin:4px 0}
.rowlbl{color:#89b;font-size:11px;margin-top:8px}
.strip{display:flex;gap:6px;flex-wrap:wrap;margin:4px 0}
.cell{width:112px;position:relative}
.cell img{width:112px;height:112px;display:block;border:2px solid #444;box-sizing:border-box}
.cell .noimg{width:112px;height:112px;border:2px dashed #444;box-sizing:border-box;
  display:flex;align-items:center;justify-content:center;color:#666;font-size:10px}
.cell .cap{font-size:10px;color:#aaa;line-height:1.25;margin-top:1px}
.cell.pos img,.cell.pos .noimg{border-color:#5c5}
.cell.neg img,.cell.neg .noimg{border-color:#e55}
.cell .flag{position:absolute;top:2px;right:2px;font-size:12px}
.pickA img{outline:2px solid #7ac} .pickB img{outline:2px dashed #ca7}
button{background:#2a2a2a;color:#ddd;border:1px solid #555;border-radius:3px;
  padding:3px 10px;margin-right:6px;cursor:pointer}
button:hover{background:#383838}
.gtscore{color:#cb8;font-size:12px;margin-left:12px}
.note{color:#777;font-size:11px}
</style></head><body>
<div id="top">
 <span id="selftest">selftest…</span>
 <button onclick="snapshotB()">현재 설정 → B 저장</button>
 <button onclick="clearB()">B 지우기</button>
 <button onclick="resetA()">A 기본값(v7.2)</button>
 <button onclick="exportGT()">GT export (.jsonl)</button>
 <input type="file" id="gtfile" style="display:none" onchange="importGT(this)">
 <button onclick="document.getElementById('gtfile').click()">GT import</button>
 <span class="gtscore" id="gtscore"></span>
 <div class="note">클릭=GT 깃발 순환(없음→긍정→부정) · 저장 홈=fixtures/eval/ · 수치=전 행 기준, 썸네일=표본(없으면 점선칸)</div>
</div>
<div id="panel"></div><div id="main"></div>
<script src="data.js"></script>
<script>
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
let A={...DEF}, Bcfg=null, GT={};   // GT["clip:f"]="pos"|"neg"

function pass(r,c){return r.sy<c.sym_max&&Math.abs(r.dv)<c.dev_max&&r.pu>=c.pu_min
 &&(r.cs==null||r.cs>=c.cs_min)&&(r.mv==null||r.mv>=c.mv_min)&&(r.lt==null||r.lt>=c.lt_min)
 &&r.ex<=c.ex_max;}
function funnel(rows,c){
 const s0=rows.length;
 const s1=rows.filter(r=>r.sy<c.sym_max&&Math.abs(r.dv)<c.dev_max);
 const s2=s1.filter(r=>r.pu>=c.pu_min);
 const s3=s2.filter(r=>r.cs==null||r.cs>=c.cs_min);
 const s4=s3.filter(r=>r.mv==null||r.mv>=c.mv_min);
 const s5=s4.filter(r=>r.lt==null||r.lt>=c.lt_min);
 const s6=s5.filter(r=>r.ex<=c.ex_max);
 return [s0,s1.length,s2.length,s3.length,s4.length,s5.length,s6.length];}
function picks(rows,c){
 const sv=rows.filter(r=>pass(r,c));
 sv.forEach(r=>r._s=c.w_expr*r.r[0]+c.w_pu*r.r[1]+c.w_q3*r.r[2]+c.w_vis2*r.r[3]+c.w_light*r.r[4]);
 sv.sort((a,b)=>b._s-a._s);
 const got=[];
 for(const r of sv){if(got.every(o=>Math.abs(r.f-o.f)>=c.gap_min))got.push(r);if(got.length==3)break;}
 return got.map(r=>r.f);}

function cellHTML(clip,r,cls){
 const k=clip+":"+r.f, fl=GT[k]||"";
 const img=r.th?`<img src="${r.th}">`:`<div class="noimg">f${r.f}<br>(no thumb)</div>`;
 const cap=`f${r.f} ex${r.ex} pu${r.pu}<br>cs${r.cs==null?"--":r.cs} mv${r.mv==null?"--":r.mv} lt${r.lt==null?"--":r.lt}`;
 const mark=fl=="pos"?"O":fl=="neg"?"X":"";
 return `<div class="cell ${fl} ${cls||""}" onclick="cyc('${clip}',${r.f})">${img}
   <span class="flag">${mark}</span><div class="cap">${cap}</div></div>`;}

function render(){
 const m=document.getElementById("main");let h="";let st_ok=true,st_msg=[];
 let gtP=0,gtN=0,gtPB=0,gtNB=0;
 for(const C of WB.clips){
  const byf={};C.rows.forEach(r=>byf[r.f]=r);
  const pA=picks(C.rows,A), fn=funnel(C.rows,A);
  const pB=Bcfg?picks(C.rows,Bcfg):null;
  const same=JSON.stringify(pA.slice().sort((a,b)=>a-b))==JSON.stringify(C.selftest.slice().sort((a,b)=>a-b));
  const isDef=JSON.stringify(A)==JSON.stringify(DEF);
  if(isDef&&!same){st_ok=false;st_msg.push(C.clip);}
  pA.forEach(f=>{const g=GT[C.clip+":"+f];if(g=="pos")gtP++;if(g=="neg")gtN++;});
  if(pB)pB.forEach(f=>{const g=GT[C.clip+":"+f];if(g=="pos")gtPB++;if(g=="neg")gtNB++;});
  h+=`<div class="clip"><b>${C.clip}</b> t${C.tid} <span class="note">n=${C.n}</span>
   <div class="funnel">퍼널 A: ${fn[0]} → 정면 ${fn[1]} → 눈 ${fn[2]} → cs ${fn[3]} → 입 ${fn[4]} → 빛 ${fn[5]} → 표정 ${fn[6]}${fn[6]<3?' ⚠ 풀<3':''}</div>`;
  h+=`<div class="rowlbl">CURRENT (생산 likeness.json)</div><div class="strip">`+
    C.cur.map(f=>byf[f]?cellHTML(C.clip,byf[f],""):"").join("")+`</div>`;
  h+=`<div class="rowlbl">A 픽</div><div class="strip">`+
    pA.map(f=>cellHTML(C.clip,byf[f],"pickA")).join("")+`</div>`;
  if(pB)h+=`<div class="rowlbl">B 픽</div><div class="strip">`+
    pB.map(f=>cellHTML(C.clip,byf[f],"pickB")).join("")+`</div>`;
  const sv=C.rows.filter(r=>pass(r,A));
  const show=sv.filter(r=>r.th).slice(0,60);
  h+=`<div class="rowlbl">생존 풀 (A, ${sv.length}행 중 썸네일 ${show.length} 표시)</div><div class="strip">`+
    show.map(r=>cellHTML(C.clip,r,"")).join("")+`</div></div>`;
 }
 m.innerHTML=h;
 const st=document.getElementById("selftest");
 if(JSON.stringify(A)==JSON.stringify(DEF)){
  st.textContent=st_ok?"selftest OK — JS ≡ python (기본 설정)":"selftest FAIL: "+st_msg.join(",");
  st.className=st_ok?"ok":"bad";
 }else{st.textContent="탐색 중 (기본 설정 아님 — selftest는 기본값에서만)";st.className="";}
 const gs=document.getElementById("gtscore");
 const tot=Object.keys(GT).length;
 gs.textContent=tot?`GT ${tot}개 · A: +${gtP}/−${gtN}`+(Bcfg?` · B: +${gtPB}/−${gtNB}`:""):"";
}
function cyc(clip,f){const k=clip+":"+f;GT[k]=GT[k]=="pos"?"neg":GT[k]=="neg"?undefined:"pos";
 if(!GT[k])delete GT[k];render();}
function snapshotB(){Bcfg={...A};render();}
function clearB(){Bcfg=null;render();}
function resetA(){A={...DEF};buildPanel();render();}
function exportGT(){
 const lines=Object.entries(GT).map(([k,v])=>{const [c,f]=k.split(":");
  return JSON.stringify({schema:"momentscan.workbench-gt/v0",clip:c,frame:+f,role:"center",
    flag:v,corpus:"output/l2",ts:new Date().toISOString()});});
 const blob=new Blob([lines.join("\\n")+"\\n"],{type:"application/jsonl"});
 const a=document.createElement("a");a.href=URL.createObjectURL(blob);
 a.download="workbench_gt.jsonl";a.click();}
function importGT(inp){const fr=new FileReader();fr.onload=()=>{
 fr.result.split("\\n").filter(x=>x.trim()).forEach(l=>{try{const o=JSON.parse(l);
  if(o.flag)GT[o.clip+":"+o.frame]=o.flag;}catch(e){}});render();};
 fr.readAsText(inp.files[0]);}
function buildPanel(){
 const p=document.getElementById("panel");let h="";
 for(const d of DIALS){
  if(d.length==1){h+=`<div class="grp">${d[0]}</div>`;continue;}
  const [k,lbl,mn,mx,stp]=d;
  h+=`<div class="dial"><label>${lbl}<span id="v_${k}">${A[k]}</span></label>
   <input type="range" min="${mn}" max="${mx}" step="${stp}" value="${A[k]}"
    oninput="A['${k}']=+this.value;document.getElementById('v_${k}').textContent=this.value;render()"></div>`;}
 p.innerHTML=h;}
buildPanel();render();
</script></body></html>
"""

if __name__ == "__main__":
    out_root = Path("output/l2")
    dst = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("workbench_out")
    wb = dst / "workbench"
    wb.mkdir(parents=True, exist_ok=True)
    clips = []
    for clip in CLIPS:
        try:
            clips.append(build_clip(clip, out_root, wb))
            print(f"{clip}: rows={clips[-1]['n']} selftest={clips[-1]['selftest']}")
        except Exception as e:
            print(f"{clip}: FAIL {type(e).__name__}: {e}")
    (wb / "data.js").write_text("const WB=" + json.dumps({"clips": clips}, ensure_ascii=False)
                                + ";", encoding="utf-8")
    (wb / "workbench.html").write_text(HTML, encoding="utf-8")
    print("workbench:", wb / "workbench.html")

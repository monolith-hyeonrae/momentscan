"""샘플링 워크벤치 v0.2 (2026-07-22) — 원장 ⑫ 계기. v0 대비 UI 개정(user 피드백
"여러 비디오 동시 표시 = 과복잡" → v0.1 / "다이얼에 따라 타임라인 어디가 선택·
걸러지는지 보이게" → v0.2):
  v0.1: 단일-클립 탭 뷰(←→ 키보드 전환·탭에 GT/생존 배지) · 썸네일 224px(픽=원치수,
  풀=112 축소+호버 2× 확대) · 퍼널 막대 · 풀 정렬 토글(시간순/점수순 — 랭커 취향
  노출) · A/B diff 하이라이트(주황 외곽) · 변경-다이얼 하이라이트.
  v0.2: **비디오 타임라인 스트립** — 프레임 틱 색 = 생존(초록) / 그 프레임을 먹은
  첫 스크린 색(정면·눈·cs·입·빛·표정 6색, 퍼널 막대와 동일 팔레트) · boarding 배경
  밴드 · A(파랑)/B(호박 점선) 픽 마커 · GT 점 · 호버=썸네일+수치 미리보기 · 클릭=GT
  깃발(어디서든 클릭=GT 일관).

층 구성(v0과 동일): frame_table(조인 단일홈, stash 읽기-전용 파생) + HTML 다이얼
시뮬레이터(1단 품질 스크린=floor/퍼널 · 2단 대표성 랭킹=가중) + 클릭 GT(pos/neg →
export → fixtures/eval/, 스키마 momentscan.workbench-gt/v0).
드리프트 방어: 명시-floor 의미론(사다리는 생산 상세) + 로드 시 셀프테스트(JS가 기본
설정으로 뽑은 픽 ≡ 파이썬 동일-데이터 픽). 봉인 전 최종 확인=파이썬 카드 재실행.
스코프 v0.x = center 픽만(hair 빈은 v1). 표시 썸네일은 표본화(수치는 전 행 기준).
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
THUMB = 224     # 저장 원치수 — 픽 행은 원치수, 풀은 112 축소 표시+호버 확대

# 기본 설정 = v7.2 등가(단일-floor 의미론) — JS DEF와 문자 그대로 동일해야 함
# pt_max=99 = pitch 스크린 off(신설 다이얼, 클립-중앙값 상대 |pc| — 기본 off라 셀프테스트 불변)
DEFAULT_CFG = {"sym_max": 0.6, "dev_max": 15.0, "pt_max": 99.0, "pu_min": 0.4, "cs_min": 0.0,
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
    pitch = M[sel, INDEX["head_pitch"]]
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
    return dict(tid=tid, rider=rider, fx=fx, cb=cb, P=P, yaw=yaw, pitch=pitch, blur=blur,
                micro=micro, mv=mv, lum_eff=lum_eff, cs=cs, nrm=nrm, board=board, expr=expr,
                pupil=pupil, sym=sym)


def compute_picks(rows, cfg):
    """JS 시뮬레이터와 문자 그대로 동일한 의미론 (반올림된 shipped 값 위에서)."""
    surv = [r for r in rows
            if r["sy"] < cfg["sym_max"] and abs(r["dv"]) < cfg["dev_max"]
            and abs(r["pc"]) < cfg["pt_max"]
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

    pt = t["pitch"]
    pt_med = float(np.nanmedian(pt)) if np.isfinite(pt).any() else 0.0
    rows = []
    for i in range(n):
        rows.append({"f": int(fx[i]), "b": int(t["board"][i]),
                     "pt": round(float(pt[i]), 1) if np.isfinite(pt[i]) else None,
                     # pc = 클립-중앙값 상대 pitch(스크린용) — 결측=0(통과), 절대 비교 금지 원칙
                     "pc": round(float(pt[i] - pt_med), 1) if np.isfinite(pt[i]) else 0.0,
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
<html lang="ko"><head><meta charset="utf-8"><title>likeness sampling workbench v0.1</title>
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
#tl{position:relative;margin:8px 0 2px;max-width:1004px}
#tl canvas{display:block;background:#101010;border:1px solid #333;cursor:crosshair}
#tlTip{position:absolute;display:none;background:#222;border:1px solid #555;padding:4px;
  z-index:20;pointer-events:none;font-size:10px;color:#ccc;line-height:1.3}
#tlTip img{width:112px;height:112px;display:block;border:1px solid #444;margin-bottom:2px}
.legend{font-size:10px;color:#999;margin:2px 0 10px}
.legend span{display:inline-block;margin-right:11px}
.legend i{display:inline-block;width:9px;height:9px;margin-right:3px;vertical-align:-1px}
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
 <div class="note">클릭=GT 깃발(없음→긍정→부정) · <b>Shift+클릭=포즈 그라운딩</b>(그 프레임이 통과하는 경계로 sym/yaw 세팅) · 호버=확대 · ←→=클립 전환 · 주황 외곽=A/B 불일치 픽 · 저장 홈=fixtures/eval/</div>
</div>
<div id="panel"></div><div id="main"></div>
<script src="data.js"></script>
<script>
const DIALS=[
 ["1단 · 품질 스크린 (결정경계)"],
 ["sym_max","보이는-정면 sym <",0.3,2.0,0.05],
 ["dev_max","|yaw dev| <",5,45,1],
 ["pt_max","|pitch dev| < (클립상대·99=off)",3,99,1],
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
const DEF={sym_max:0.6,dev_max:15,pt_max:99,pu_min:0.4,cs_min:0,mv_min:0,lt_min:0,ex_max:1.0,gap_min:12,
           w_expr:0.30,w_pu:0.15,w_q3:0.20,w_vis2:0.15,w_light:0.20};
let A={...DEF}, Bcfg=null, GT={}, cur=0, sortMode="time", poseOpen=false;
const STAGES=["정면","pitch","눈동자","cs","입","빛","표정"];
const SCOL=["#c98a4a","#7fa85c","#d95555","#b070d0","#55aacc","#d8c455","#e08aa8"];
const SURV="#69d069";

function firstFail(r,c){
 if(!(r.sy<c.sym_max&&Math.abs(r.dv)<c.dev_max))return 0;
 if(!(Math.abs(r.pc)<c.pt_max))return 1;
 if(!(r.pu>=c.pu_min))return 2;
 if(!(r.cs==null||r.cs>=c.cs_min))return 3;
 if(!(r.mv==null||r.mv>=c.mv_min))return 4;
 if(!(r.lt==null||r.lt>=c.lt_min))return 5;
 if(!(r.ex<=c.ex_max))return 6;
 return -1;}
function pass(r,c){return firstFail(r,c)<0;}
function funnel(rows,c){
 const s1=rows.filter(r=>r.sy<c.sym_max&&Math.abs(r.dv)<c.dev_max);
 const s1p=s1.filter(r=>Math.abs(r.pc)<c.pt_max);
 const s2=s1p.filter(r=>r.pu>=c.pu_min);
 const s3=s2.filter(r=>r.cs==null||r.cs>=c.cs_min);
 const s4=s3.filter(r=>r.mv==null||r.mv>=c.mv_min);
 const s5=s4.filter(r=>r.lt==null||r.lt>=c.lt_min);
 const s6=s5.filter(r=>r.ex<=c.ex_max);
 return [rows.length,s1.length,s1p.length,s2.length,s3.length,s4.length,s5.length,s6.length];}
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
 const img=r.th?`<img src="${r.th}">`:`<div class="noimg">f${r.f}<br>(no thumb)</div>`;
 const cap=`f${r.f} ex${r.ex} pu${r.pu}<br>cs${r.cs==null?"--":r.cs} mv${r.mv==null?"--":r.mv} lt${r.lt==null?"--":r.lt}`;
 const mark=fl=="pos"?"O":fl=="neg"?"X":"";
 return `<div class="cell ${fl} ${cls||""}" onclick="cyc(event,'${clip}',${r.f})">${img}
   <span class="flag">${mark}</span><div class="cap">${cap}</div></div>`;}

function funnelHTML(fn){
 const names=["전체",...STAGES];
 const cols=["#666",...SCOL.slice(0,STAGES.length-1),SURV];  // 마지막 행=최종 생존(초록)
 const mx=Math.max(fn[0],1), last=fn.length-1;
 return `<div class="funnel">`+fn.map((v,i)=>
  `<div class="fr${i==last?" last":""}"><span class="lbl">${names[i]}</span>
   <span class="bar" style="width:${Math.max(2,Math.round(280*v/mx))}px;background:${cols[i]}"></span>
   <span class="cnt">${v}</span></div>`).join("")+
  (fn[last]<3?`<div class="fr"><span class="lbl"></span><span style="color:#e66">⚠ 풀&lt;3</span></div>`:``)+`</div>`;}

function legendHTML(){
 return `<div class="legend"><span><i style="background:${SURV}"></i>생존</span>`+
  STAGES.map((s,i)=>`<span><i style="background:${SCOL[i]}"></i>${s}에 걸러짐</span>`).join("")+
  `<span><i style="background:rgba(80,170,180,.5)"></i>boarding</span>
   <span><i style="background:#7ac"></i>A 픽</span><span><i style="border:1px dashed #ca7;width:7px;height:7px"></i>B 픽</span>
   <span style="color:#4e4">●</span><span style="color:#e44;margin-left:-8px">●</span> <span>GT ±</span>
   · 호버=미리보기 · 클릭=GT 깃발</div>`;}

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
  return {pA,pB,fn,p,ng,alive:fn[fn.length-1]};});

 const tabs=WB.clips.map((C,i)=>
  `<span class="tab${i==cur?" cur":""}" onclick="cur=${i};render()">${C.clip}
   <span class="b">${meta[i].alive}</span>${meta[i].p+meta[i].ng?`<span class="g"> +${meta[i].p}/−${meta[i].ng}</span>`:""}</span>`).join("");

 const C=WB.clips[cur], m=meta[cur];
 const byf={};C.rows.forEach(r=>byf[r.f]=r);
 const setA=new Set(m.pA), setB=m.pB?new Set(m.pB):null;
 let h=`<div id="tabs">${tabs}</div><b>${C.clip}</b> t${C.tid} <span class="note">n=${C.n} · 풀 정렬:</span>
  <button onclick="sortMode=sortMode=='time'?'score':'time';render()">${sortMode=='time'?'시간순':'점수순'}</button>
  <button onclick="poseOpen=!poseOpen;render()">포즈 눈금 ${poseOpen?'닫기':'보기'}</button>`;
 h+=funnelHTML(m.fn);
 h+=`<div id="tl"><canvas id="tlc" width="1000" height="44"></canvas><div id="tlTip"></div></div>`+legendHTML();
 if(poseOpen){
  const wt=C.rows.filter(r=>r.th);
  const samp=a=>{if(a.length<=8)return a;const o=[];for(let i=0;i<8;i++)o.push(a[Math.round(i*(a.length-1)/7)]);return [...new Set(o)];};
  const byDev=samp(wt.slice().sort((a,b)=>Math.abs(a.dv)-Math.abs(b.dv)));
  const bySy=samp(wt.slice().sort((a,b)=>a.sy-b.sy));
  const pose=r=>{const ff=firstFail(r,A);const dim=(ff===0||ff===1)?"opacity:.35":"";
   return `<div class="cell" style="${dim}" onclick="groundPose('${C.clip}',${r.f})"><img src="${r.th}">
    <div class="cap">|dv|${Math.abs(r.dv).toFixed(0)} sy${r.sy}<br>pt${r.pt==null?"--":r.pt} pc${r.pc}</div></div>`;};
  h+=`<div class="rowlbl">포즈 눈금 — yaw 사다리 (타일 클릭 = 이 포즈까지 허용으로 그라운딩 · 흐림 = 현재 포즈 스크린에 걸러짐)</div>
   <div class="strip sm">`+byDev.map(pose).join("")+`</div>
   <div class="rowlbl">포즈 눈금 — sym 사다리</div><div class="strip sm">`+bySy.map(pose).join("")+`</div>`;
 }
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
 drawTimeline(C,m);

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
function drawTimeline(C,m){
 const cv=document.getElementById("tlc");
 if(!cv)return;
 const ctx=cv.getContext("2d"), W=cv.width, H=cv.height;
 ctx.clearRect(0,0,W,H);
 const fmin=C.rows[0].f, fmax=Math.max(C.rows[C.rows.length-1].f, fmin+1);
 const X=f=>4+(f-fmin)/(fmax-fmin)*(W-8);
 ctx.fillStyle="rgba(80,170,180,0.22)";                      // boarding 밴드
 for(const r of C.rows) if(r.b) ctx.fillRect(X(r.f)-1,0,2.2,H);
 for(const r of C.rows){                                     // 프레임 틱
  const ff=firstFail(r,A);
  ctx.fillStyle=ff<0?SURV:SCOL[ff];
  if(ff<0) ctx.fillRect(X(r.f),12,1.7,H-14);
  else     ctx.fillRect(X(r.f),20,1.4,H-22);
 }
 ctx.fillStyle="#7ac";                                       // A 픽
 for(const f of m.pA) ctx.fillRect(X(f)-1.5,9,3,H-9);
 if(m.pB){ctx.strokeStyle="#ca7";ctx.setLineDash([3,2]);     // B 픽
  for(const f of m.pB) ctx.strokeRect(X(f)-2.5,9,5,H-10);
  ctx.setLineDash([]);}
 for(const r of C.rows){                                     // GT 점
  const g=GT[C.clip+":"+r.f];
  if(!g)continue;
  ctx.fillStyle=g=="pos"?"#4e4":"#e44";
  ctx.beginPath();ctx.arc(X(r.f),4.5,2.6,0,7);ctx.fill();
 }
 const tip=document.getElementById("tlTip");
 const nearest=x=>{const fe=fmin+(x-4)/(W-8)*(fmax-fmin);
  let bi=0,bd=1e9;
  for(let i=0;i<C.rows.length;i++){const d=Math.abs(C.rows[i].f-fe);if(d<bd){bd=d;bi=i;}}
  return C.rows[bi];};
 cv.onmousemove=e=>{
  const rect=cv.getBoundingClientRect(), x=e.clientX-rect.left;
  const r=nearest(x), ff=firstFail(r,A);
  const st=ff<0?`<span style="color:${SURV}">생존</span>`:`<span style="color:${SCOL[ff]}">${STAGES[ff]}에 걸러짐</span>`;
  const g=GT[C.clip+":"+r.f], gs=g?` · GT:${g=="pos"?"＋":"−"}`:"";
  tip.innerHTML=(r.th?`<img src="${r.th}">`:"")+
   `f${r.f} ${st}${gs}<br>ex${r.ex} pu${r.pu} sy${r.sy} dv${r.dv}<br>pt${r.pt==null?"--":r.pt}(Δ${r.pc}) cs${r.cs==null?"--":r.cs} mv${r.mv==null?"--":r.mv} lt${r.lt==null?"--":r.lt}`;
  tip.style.display="block";
  tip.style.left=Math.min(x+14,W-140)+"px";
  tip.style.top="46px";
 };
 cv.onmouseleave=()=>{tip.style.display="none";};
 cv.onclick=e=>{
  const rect=cv.getBoundingClientRect();
  cyc(e,C.clip,nearest(e.clientX-rect.left).f);
 };
}
function cyc(e,clip,f){
 if(e&&e.shiftKey){groundPose(clip,f);return;}
 const k=clip+":"+f;GT[k]=GT[k]=="pos"?"neg":GT[k]=="neg"?undefined:"pos";
 if(!GT[k])delete GT[k];render();}
function groundPose(clip,f){
 // 예시-그라운딩: 이 프레임이 포즈 스크린을 통과하는 최소 경계로 세팅 (쿼리 바이 예시)
 const C=WB.clips.find(c=>c.clip==clip);
 const r=C&&C.rows.find(r=>r.f==f);
 if(!r)return;
 A.sym_max=Math.min(2.0,Math.round((Math.floor(r.sy/0.05)+1)*5)/100);
 A.dev_max=Math.min(45,Math.floor(Math.abs(r.dv))+1);
 if(A.pt_max<99)A.pt_max=Math.max(A.pt_max,Math.min(99,Math.floor(Math.abs(r.pc))+1));
 buildPanel();render();}
function snapshotB(){Bcfg={...A};render();}
function clearB(){Bcfg=null;render();}
function resetA(){A={...DEF};buildPanel();render();}
function exportGT(){
 const lines=Object.entries(GT).map(([k,v])=>{const i=k.indexOf(":");
  return JSON.stringify({schema:"momentscan.workbench-gt/v0",clip:k.slice(0,i),frame:+k.slice(i+1),
    role:"center",flag:v,corpus:"output/l2",ts:new Date().toISOString()});});
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

if __name__ == "__main__":
    out_root = Path("output/l2")
    dst = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("workbench_out")
    wb = dst
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

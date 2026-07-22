"""workbench — likeness 표본 샘플링 연구 콘솔의 데이터층 (원장 ⑫ 승격).

참조 구현 = scratchpad_workbench.py v0.9 (2026-07-22, main 7573af8) 을 값-동일하게
승격한 것. 다이얼 의미론(상태별 스크린/밴드 + 상태 가중 랭킹)과 셀프테스트 픽은
v0.x 와 문자 그대로 같아야 한다 — 검증 좌표: test_3=[29,511,352] ·
dual_2=[34,1052,6] · test_4=[570,408,286].

v0.6 공평 우주: 측정 행 썸네일 표본화를 제거(전 행 저장)하고, 선택받지 못한 프레임의
존재를 유령 우주(ghost/absent/vf)로 페이로드에 실어 타임라인 유령 레인·풀 그리드가
비디오 전체를 정직하게 비춘다 — 유령 종류: inv(측정됐으나 valid 밖)·det(검출만,
랜드마크 없음)·frag(동일 subject 타 트랙)·무검출(absent 구간).

v0.7 상태 5그룹 재편(user 정식화: 포즈/표정·얼굴/빛/영상/왜곡 — 원장 ⑪ 봉인 좌표계):
다이얼 패널·퍼널·타임라인이 그룹 단위. 빛-심층 축 신설 — dp=입체감(|face_light_lr|+
|tb| 방향성, relight '입체감 floor' 예약석)·hh=거칠기(face_light_harsh)·sp=선명
(face_blur pct, 영상 그룹), 전부 기본 off.

v0.8 빛 판별력 계수 lf(⑪-e v3): 흐린 날=저분산 클립에서 풀-상대 랭크가 과대발언 —
lf=robust (p90−p10)/p50 정규화(test_4급≈1.0, /0.8 cap 1.0), 페이로드 선적.
적용은 JS ATT 토글(w_light×lf, 기본 off=셀프테스트 불변)에서만.

v0.9 상태-쿼리 구조(user: "각 상태를 판별하고 종합하는 수준 높은 스크리닝"):
1단=상태별 스크린/밴드(포즈=밴드가 곧 쿼리·표정도 ex_min~ex_max 밴드) · 2단=상태
점수 4종 종합(state_scores: 표정·얼굴=(2무표정+눈동자)/3 · 빛=조도생동 · 영상=
(선명+micro)/2 · 왜곡=(cs+입가시+norm)/3) — 가중이 신호가 아닌 상태 단위
(w_face/w_light/w_image/w_distort). rank01 은 8축 개별 선적(r). 점수 기준 재정의 =
v7.2 등가 브리지 종료(⑪ 후보 정책의 진화; 가드=JS≡python 셀프테스트 유지).

층 구성 (원장 ⑫ — user 도구 3종의 세 층):
  frame_table    클립 main rider 의 전 신호 와이드 행 — 프로브 4종이 반복한 조인의
                 단일홈 (+유령 우주 컨텍스트: lm_all_cb·det_bbox·frag_bbox).
                 stash 읽기-전용 파생, stash 로 영속화하지 않는다(이중-진실 방지).
  build_clip_data  frame_table + chroma/썸네일 디코드(전 행 + 유령 표본) + 랭크 합성
                 → 워크벤치 페이로드(+ghost/absent/vf). 캐시 = <wb_dir>/cache/<clip>.json
                 (mtime-기반 무효화). 캐시는 stash 아티팩트가 아니라 계기 파생물 —
                 freshness 등재 대상이 아니다.
  compute_picks  다이얼 설정 → 픽. 서버가 기본 설정으로 계산해 페이로드에 동봉
                 (selftest) → JS 가 같은 의미론으로 대조한다(드리프트 방어).
  GT I/O         클릭 깃발의 영구 홈 = fixtures/eval/workbench_gt.jsonl
                 (스키마 momentscan.workbench-gt/v0, 같은 clip:frame:role 은 나중이 이김).

chroma 이음매: skin_chroma 는 parse 가 아직 보존하지 않아 detect.mp4 순차 디코드로
산출한다(_skin_chroma — 생산 parse._quality 동형 soft skin 마스크). lk-sampling2 가
parse 에 skin_chroma 컬럼을 착지시키면 이 디코드를 parse 읽기로 교체한다.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

import numpy as np
import polars as pl

from momentscan.infra.store.stash import (
    appearance_path,
    clip_dir,
    read_features,
    read_landmarks,
    read_tubelets,
)

from momentscan.perception.readings.face_signals import pupil_visibility, visual_frontality

# ── 상수 (v0.x 와 문자 그대로 동일해야 하는 것들) ────────────────────────────
THUMB = 224                       # 저장 원치수 px — 픽 행은 원치수, 풀은 112 축소 표시
GHOST_THUMB_MAX = 60              # 유령 종류별 썸네일 상한 (v0.6 — 측정 행은 전량 저장)
CACHE_VERSION = 4                 # 의미론 변경 시 올린다 → 전 캐시 무효화 (4=v0.7~v0.9: rank 8축·dp/hh/sp·lf)

# 기본 설정 — _workbench_html.js 의 DEF 와 문자 그대로 동일해야 한다
# (로드 시 셀프테스트가 이 짝을 감시).
# v0.9 상태-쿼리 구조: 1단=상태별 스크린/밴드(포즈는 밴드=쿼리, 점수 없음) ·
#   2단=상태 점수 종합(w_face·w_light·w_image·w_distort — 상태-내 구성은 고정 평균,
#   세부 sub-가중은 v0.9.x). 점수 기준 재정의 = v7.2 등가 브리지 종료(⑪ 후보 정책의 진화).
# ex 밴드(ex_min~ex_max): 표정 상태도 쿼리 가능(portrait 웃음-구간 등). 기본 ex_min=0.
# pt_max=99 = pitch 스크린 off(v0.3 신설 다이얼, 클립-중앙값 상대 |pc| — 기본 off 라 셀프테스트 불변)
# yaw = 부호-있는 밴드(v0.5, portrait 쿼리 대비: [60,90] 같은 측면 구간 선택 가능) —
#   기본 (−15,15) = 구 |dev|<15 와 동치(셀프테스트 불변). 수렴=밴드의 특수형.
DEFAULT_CFG = {"sym_max": 0.6, "dev_lo": -15.0, "dev_hi": 15.0, "pt_max": 99.0, "pu_min": 0.4,
               "cs_min": 0.0, "mv_min": 0.0, "lt_min": 0.0, "ex_min": 0.0, "ex_max": 1.0,
               "gap_min": 12, "dp_min": 0.0, "hh_max": 100.0, "sp_min": 0.0,
               "w_face": 0.45, "w_light": 0.20, "w_image": 0.15, "w_distort": 0.20}


def state_scores(r: list[float]) -> tuple[float, float, float, float]:
    """상태 점수 4종 — r = [re,rp,rs,rm,rn,rc,rv,rl] (rank01 8축).
    표정·얼굴=(2·무표정+눈동자)/3 · 빛=조도생동 · 영상=(선명+micro)/2 ·
    왜곡=(cs+입가시+norm)/3 (q3 분해 판정: norm→왜곡)."""
    re_, rp_, rs_, rm_, rn_, rc_, rv_, rl_ = r
    return ((2 * re_ + rp_) / 3, rl_, (rs_ + rm_) / 2, (rc_ + rv_ + rn_) / 3)

GT_SCHEMA = "momentscan.workbench-gt/v0"

# build_clip_data 캐시를 무효화하는 소스 아티팩트 (클립 디렉토리 상대).
_SOURCES = ("likeness.json", "landmarks.parquet", "gate_trace.parquet",
            "features/A.parquet", "parse.parquet", "detections.parquet",
            "tubelets.parquet", "detect.mp4")

# 생산 parse._quality 동형 soft skin 마스크 (scratchpad_likeness_sat.skin_sv 승계).
_SKIN_ANCHORS = (9, 107, 336, 151, 67, 297, 50, 280, 205, 425, 116, 345, 123, 352,
                 152, 175, 200, 6, 197, 195)
_SIG_FRAC = 0.16
_L_OUTER, _R_OUTER = 33, 263


def workbench_dir(out_root: Path) -> Path:
    """워크벤치 자체 디렉토리 — 캐시·썸네일의 홈 (stash 클립 디렉토리와 형제)."""
    return Path(out_root) / "workbench"


# ── 랭크 헬퍼 (v0 값-동일) ────────────────────────────────────────────────────
def pct_rank(x: np.ndarray) -> np.ndarray:
    """유한값 대상 백분위(%). NaN 은 NaN 유지 — 풀-내 상대만(절대 floor 금지 교훈)."""
    out = np.full(len(x), np.nan)
    fin = np.isfinite(x)
    if fin.sum():
        v = x[fin]
        out[fin] = np.array([float(np.mean(v <= xi)) * 100 for xi in x[fin]])
    return out


def rank01(x: np.ndarray, flip: bool = False) -> np.ndarray:
    """0..1 순위 (동률=입력 순서, NaN 은 최하위). flip=작을수록 좋음."""
    r = np.argsort(np.argsort(np.nan_to_num(x, nan=(np.inf if flip else -np.inf))))
    r = r / max(len(x) - 1, 1)
    return 1 - r if flip else r


# ── frame_table: stash 조인의 단일홈 ─────────────────────────────────────────
def frame_table(clip_id: str, out_root: Path) -> dict:
    """클립 main rider 의 전 신호 와이드 테이블 (+유령 우주 컨텍스트, v0.6).

    조인: landmarks(유효 게이트 프레임) × features/A(yaw·blur) × parse(micro·
    mouth_vis·skin_lum·clip_hi) × detections(raw embedding → cs·norm) ×
    tubelets(scene_phase) × blendshapes(expr). 전부 읽기-전용.
    유령 우주: lm_all_cb(valid-필터 전 전체 lm crop_box)·det_bbox(이 트랙 검출 bbox)·
    frag_bbox(동일 subject·타 track_id 파편 bbox) — build_clip_data 가 차집합으로 종류 분류."""
    # 랭킹 상수는 preset 소유 (C9 자리) — v0 과 동일하게 race981 의 정면 좌표를 쓴다.
    from momentscan.preset import resolve
    frontal_deg = resolve("race981").camera.frontal_deg

    from momentscan_features_specialist45d.registry import INDEX
    from momentscan_features_specialist45d.specialists import BLENDSHAPE_ORDER

    out_root = Path(out_root)
    rec = json.loads(appearance_path(out_root, clip_id).read_text(encoding="utf-8"))
    tid, rider = next((int(t), r) for t, r in rec["riders"].items() if r.get("role") == "main")
    lmr = read_landmarks(out_root, clip_id).filter(pl.col("track_id") == tid).sort("frame_idx")
    # 유령 우주 재료: 무효(valid-필터로 빠질 lm 행)의 crop_box — 전량 보존 후 필터
    lm_all_cb = {int(f): tuple(float(v) for v in b)
                 for f, b in zip(lmr["frame_idx"].to_list(), lmr["crop_box"].to_list())}
    gt = pl.read_parquet(clip_dir(out_root, clip_id) / "gate_trace.parquet") \
           .filter(pl.col("track_id") == tid)
    valid = set(gt.filter(pl.col("valid"))["frame_idx"].to_list())
    lm = lmr
    keep = lm["frame_idx"].is_in(list(valid))
    if int(keep.sum()) >= 10:
        lm = lm.filter(keep)
    fx = lm["frame_idx"].to_numpy()
    n = len(fx)
    # P = raw crop-정규화 랜드마크 그대로 — pupil/sym 공식(face_signals)의 선언 입력이자
    # 썸네일 crop 투영의 0..1 좌표. (v0 의 canonicalize 호출은 반환값을 버리는 순수
    # 함수 호출 = 무영향 잔재라 승계하지 않는다.)
    P = np.array(lm["landmarks"].to_list(), dtype=np.float64).reshape(n, 478, 3)
    cb = np.array(lm["crop_box"].to_list(), dtype=np.float64)

    feats = read_features(out_root, clip_id, "A").filter(pl.col("track_id") == tid).sort("frame_idx")
    pos = {f: i for i, f in enumerate(feats["frame_idx"].to_numpy())}
    M = np.array(feats["feature"].to_list(), dtype=np.float64)
    sel = np.array([pos[f] for f in fx])
    yaw = M[sel, INDEX["head_yaw_dev"]]
    pitch = M[sel, INDEX["head_pitch"]]
    blur = M[sel, INDEX["face_blur"]]
    # v0.7 빛-심층(얼굴면 광학, relight '입체감 floor' 예약석): 방향성·거칠기
    light_lr = M[sel, INDEX["face_light_lr"]]
    light_tb = M[sel, INDEX["face_light_tb"]]
    light_hh = M[sel, INDEX["face_light_harsh"]]

    pq = pl.read_parquet(clip_dir(out_root, clip_id) / "parse.parquet") \
           .filter(pl.col("track_id") == tid)

    def g(col: str) -> dict:
        return dict(zip(pq["frame_idx"].to_list(), pq[col].to_list())) if col in pq.columns else {}

    micro_of, mv_of, lum_of, hi_of = g("face_micro"), g("mouth_vis"), g("skin_lum"), g("skin_clip_hi")
    micro = np.array([micro_of.get(int(f), np.nan) for f in fx], float)
    mv = np.array([mv_of.get(int(f), np.nan) for f in fx], float)
    lum = np.array([lum_of.get(int(f), np.nan) for f in fx], float)
    chi = np.array([hi_of.get(int(f), np.nan) for f in fx], float)
    lum_eff = lum * (1.0 - np.nan_to_num(chi, nan=0.0))    # 원장 ⑪-e: 백화 페널티

    det_all = pl.read_parquet(clip_dir(out_root, clip_id) / "detections.parquet")
    det = det_all.filter(pl.col("track_id") == tid)
    # 유령 우주 재료: 이 트랙의 검출 bbox(랜드마크 유무 무관) + 동일-subject 타-트랙 파편
    det_bbox = {int(f): tuple(float(v) for v in b)
                for f, b in zip(det["frame_idx"].to_list(), det["bbox"].to_list()) if b is not None}
    frag_bbox = {}
    if "subject_id" in det_all.columns:
        sids = det["subject_id"].drop_nulls().unique().to_list()
        if sids:
            fr = det_all.filter(pl.col("subject_id").is_in(sids) & (pl.col("track_id") != tid))
            frag_bbox = {int(f): tuple(float(v) for v in b)
                         for f, b in zip(fr["frame_idx"].to_list(), fr["bbox"].to_list())
                         if b is not None}
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
    pupil = pupil_visibility(P)
    sym = visual_frontality(P)
    return dict(tid=tid, rider=rider, fx=fx, cb=cb, P=P, yaw=yaw, pitch=pitch, blur=blur,
                micro=micro, mv=mv, lum_eff=lum_eff, cs=cs, nrm=nrm, board=board, expr=expr,
                pupil=pupil, sym=sym, frontal_deg=frontal_deg,
                lm_all_cb=lm_all_cb, det_bbox=det_bbox, frag_bbox=frag_bbox,
                light_lr=light_lr, light_tb=light_tb, light_hh=light_hh)


# ── 픽 의미론 (JS 시뮬레이터와 문자 그대로 동일 — 반올림된 shipped 값 위에서) ──
def compute_picks(rows: list[dict], cfg: dict) -> list[int]:
    """1단 상태별 스크린/밴드 → 2단 상태 가중 랭킹(state_scores) → 시간 gap 3픽."""
    surv = [r for r in rows
            if r["sy"] < cfg["sym_max"] and cfg["dev_lo"] < r["dv"] < cfg["dev_hi"]
            and abs(r["pc"]) < cfg["pt_max"]
            and r["pu"] >= cfg["pu_min"]
            and (r["cs"] is None or r["cs"] >= cfg["cs_min"])
            and (r["mv"] is None or r["mv"] >= cfg["mv_min"])
            and (r["lt"] is None or r["lt"] >= cfg["lt_min"])
            and (r["dp"] is None or r["dp"] >= cfg["dp_min"])
            and (r["hh"] is None or r["hh"] <= cfg["hh_max"])
            and (r["sp"] is None or r["sp"] >= cfg["sp_min"])
            and cfg["ex_min"] <= r["ex"] <= cfg["ex_max"]]
    for r in surv:
        sf, sl, si, sd = state_scores(r["r"])
        r["_s"] = (cfg["w_face"] * sf + cfg["w_light"] * sl
                   + cfg["w_image"] * si + cfg["w_distort"] * sd)
    surv.sort(key=lambda r: -r["_s"])
    got = []
    for r in surv:
        if all(abs(r["f"] - o["f"]) >= cfg["gap_min"] for o in got):
            got.append(r)
        if len(got) == 3:
            break
    return [r["f"] for r in got]


# ── chroma (parse 미보존분 — 이음매 주석은 모듈 독스트링) ─────────────────────
def _skin_chroma(frame: np.ndarray, pts: np.ndarray, cb: np.ndarray) -> float | None:
    """생산 parse._quality 동형 soft point-Gaussian skin 가중의 절대 chroma 평균.

    원장 ⑪-e v2: 지각 생동감의 자 = max(BGR)−min(BGR) (HSV-S 는 밝기 반비례로 기각).
    풀-내 상대 랭크로만 쓴다 — 절대 비교 금지."""
    import cv2
    from mediapipe.tasks.python.vision.face_landmarker import (
        FaceLandmarksConnections as _FLC,
    )
    oval = sorted({i for c in _FLC.FACE_LANDMARKS_FACE_OVAL for i in (c.start, c.end)})

    H, W = frame.shape[:2]
    x1, y1 = max(0, int(cb[0])), max(0, int(cb[1]))
    x2, y2 = min(W, int(cb[2])), min(H, int(cb[3]))
    if x2 - x1 < 8 or y2 - y1 < 8:
        return None
    sub = frame[y1:y2, x1:x2].astype(np.float32)
    C = sub.max(axis=2) - sub.min(axis=2)
    p = pts - np.array([x1, y1], np.float64)
    h, w = C.shape
    hull = cv2.convexHull(np.clip(p[oval], [0, 0], [w - 1, h - 1]).astype(np.int32))
    facemask = np.zeros((h, w), np.uint8)
    cv2.fillConvexPoly(facemask, hull, 1)
    iod = np.linalg.norm(p[_L_OUTER] - p[_R_OUTER]) + 1e-6
    sig = _SIG_FRAC * iod
    yy, xx = np.mgrid[0:h, 0:w]
    wgt = np.zeros((h, w), np.float32)
    for a in _SKIN_ANCHORS:
        ax, ay = p[a]
        wgt += np.exp(-((xx - ax) ** 2 + (yy - ay) ** 2) / (2.0 * sig * sig))
    wgt = wgt * facemask
    wf = wgt.ravel()
    m = wf > 1e-3
    if m.sum() < 50:
        return None
    wm = wf[m]
    return float((C.ravel()[m] * wm).sum() / wm.sum())


# ── 페이로드 빌드 + 캐시 ──────────────────────────────────────────────────────
def _source_paths(out_root: Path, clip_id: str) -> list[Path]:
    return [clip_dir(out_root, clip_id) / rel for rel in _SOURCES]


def cache_path(out_root: Path, clip_id: str) -> Path:
    return workbench_dir(out_root) / "cache" / f"{clip_id}.json"


def _cache_fresh(cache: Path, out_root: Path, clip_id: str) -> bool:
    """캐시 신선 ⟺ 존재 ∧ 버전 일치 ∧ 모든 소스 아티팩트 mtime ≤ 캐시 mtime."""
    if not cache.exists():
        return False
    try:
        if json.loads(cache.read_text(encoding="utf-8")).get("cache_version") != CACHE_VERSION:
            return False
    except (ValueError, OSError):
        return False
    cm = cache.stat().st_mtime
    srcs = [p for p in _source_paths(out_root, clip_id) if p.exists()]
    return bool(srcs) and all(p.stat().st_mtime <= cm for p in srcs)


def build_clip_data(clip_id: str, out_root: Path, *, force: bool = False) -> dict:
    """워크벤치 클립 페이로드 {clip,tid,n,vf,cur,lf,selftest,rows,ghost,absent} — 캐시-우선.

    빌드 = frame_table + detect.mp4 한 번의 순차 디코드(chroma 전 행 + 썸네일 전 행 +
    유령 표본) + 랭크 합성 + 파이썬 셀프테스트 픽 + 유령 우주(ghost/absent/vf).
    썸네일은 <wb_dir>/thumbs/<clip>/ 에 파일로."""
    import cv2

    out_root = Path(out_root)
    cp = cache_path(out_root, clip_id)
    if not force and _cache_fresh(cp, out_root, clip_id):
        return json.loads(cp.read_text(encoding="utf-8"))

    t = frame_table(clip_id, out_root)
    fx, cb, P = t["fx"], t["cb"], t["P"]
    n = len(fx)

    # chroma + 썸네일(v0.6: 전 행 = 공평 우주) + 유령 썸네일: 한 번의 순차 디코드
    dev = t["yaw"] - t["frontal_deg"]
    cur = list(t["rider"]["samples"]["center_nearest"])
    row_of = {int(f): i for i, f in enumerate(fx)}
    fxset = set(row_of)
    # 유령 우주: inv=측정됐으나 valid 밖 · det=검출만(랜드마크 없음) · frag=동일-subject 타 트랙
    inv_f = sorted(set(t["lm_all_cb"]) - fxset)
    det_f = sorted(set(t["det_bbox"]) - set(t["lm_all_cb"]))
    frag_f = sorted(set(t["frag_bbox"]) - set(t["det_bbox"]) - set(t["lm_all_cb"]))
    ghost_kind = {**{f: "inv" for f in inv_f}, **{f: "det" for f in det_f},
                  **{f: "frag" for f in frag_f}}
    ghost_thumb = set()
    for kfs in (inv_f, det_f, frag_f):                          # 종류별 썸네일 ≤60 표본
        if len(kfs) > GHOST_THUMB_MAX:
            ghost_thumb |= {kfs[i] for i in
                            np.unique(np.linspace(0, len(kfs) - 1, GHOST_THUMB_MAX).astype(int))}
        else:
            ghost_thumb |= set(kfs)

    def _sq(b, W0, H0, pad=1.3):
        x1, y1, x2, y2 = b
        cx, cy, s = (x1 + x2) / 2, (y1 + y2) / 2, max(x2 - x1, y2 - y1) * pad / 2
        return max(0, int(cx - s)), max(0, int(cy - s)), min(W0, int(cx + s)), min(H0, int(cy + s))

    chroma = np.full(n, np.nan)
    tdir = workbench_dir(out_root) / "thumbs" / clip_id
    tdir.mkdir(parents=True, exist_ok=True)
    thumb_ok = set()
    cap = cv2.VideoCapture(str(clip_dir(out_root, clip_id) / "detect.mp4"))
    vf = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fidx = 0
    while True:
        ok, frm = cap.read()
        if not ok:
            break
        H0, W0 = frm.shape[:2]
        i = row_of.get(fidx)
        box = None
        if i is not None:
            cbv = cb[i]
            pts = np.stack([cbv[0] + P[i, :, 0] * (cbv[2] - cbv[0]),
                            cbv[1] + P[i, :, 1] * (cbv[3] - cbv[1])], 1)
            r = _skin_chroma(frm, pts, cbv)
            if r is not None:
                chroma[i] = r
            box = tuple(cbv)
        elif fidx in ghost_thumb:
            k = ghost_kind[fidx]
            box = (t["lm_all_cb"].get(fidx) if k == "inv"
                   else _sq(t["det_bbox"].get(fidx) or t["frag_bbox"].get(fidx), W0, H0))
        if box is not None:
            x1, y1, x2, y2 = (int(v) for v in box)
            if x2 - x1 > 1 and y2 - y1 > 1:
                tile = cv2.resize(frm[max(0, y1):y2, max(0, x1):x2], (THUMB, THUMB))
                cv2.imwrite(str(tdir / f"f{fidx:05d}.jpg"), tile,
                            [cv2.IMWRITE_JPEG_QUALITY, 82])
                thumb_ok.add(fidx)
        fidx += 1
    cap.release()
    vf = max(vf, fidx)
    covered = fxset | set(ghost_kind)
    absent = []
    _st = None
    for f in range(vf):
        if f not in covered:
            if _st is None:
                _st = f
        elif _st is not None:
            absent.append([_st, f - 1])
            _st = None
    if _st is not None:
        absent.append([_st, vf - 1])
    ghost = [{"f": f, "k": k,
              "th": (f"thumbs/{clip_id}/f{f:05d}.jpg" if f in thumb_ok else None)}
             for f, k in sorted(ghost_kind.items())]

    micro_pct, sharp_pct = pct_rank(t["micro"]), pct_rank(t["blur"])
    norm_pct, cs_pct, mv_pct = pct_rank(t["nrm"]), pct_rank(t["cs"]), pct_rank(t["mv"])
    light_pct = np.nanmean(np.vstack([pct_rank(t["lum_eff"]), pct_rank(chroma)]), axis=0)
    # v0.7 빛-심층·영상: 입체감=|lr|+|tb|(방향성 총량, flat→저값)·거칠기 harsh·선명
    dp_pct = pct_rank(np.abs(t["light_lr"]) + np.abs(t["light_tb"]))
    hh_pct = pct_rank(t["light_hh"])

    # v0.8 빛 판별력 계수(⑪-e v3): 흐린 날=저분산 → 랭크 과대발언 감쇠용.
    # robust (p90−p10)/p50, test_4급 동적범위(≈0.8)를 1.0으로 정규화.
    def _spread(v):
        fin = v[np.isfinite(v)]
        if len(fin) < 10:
            return 0.0
        p10, p50, p90 = np.percentile(fin, [10, 50, 90])
        return float((p90 - p10) / (abs(p50) + 1e-6))
    lf = round(min(1.0, 0.5 * (_spread(t["lum_eff"]) + _spread(chroma)) / 0.8), 2)
    # v0.9 상태-쿼리: 축별 rank01 8종 — [무표정, 눈동자, 선명, micro, norm, cs, 입가시, 빛]
    R = np.stack([rank01(t["expr"], flip=True), rank01(t["pupil"]),
                  rank01(sharp_pct), rank01(micro_pct), rank01(norm_pct),
                  rank01(cs_pct), rank01(mv_pct), rank01(light_pct)], axis=1)

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
                     "dp": num(dp_pct[i], 1), "hh": num(hh_pct[i], 1), "sp": num(sharp_pct[i], 1),
                     "r": [round(float(v), 4) for v in R[i]],
                     "th": (f"thumbs/{clip_id}/f{int(fx[i]):05d}.jpg"
                            if int(fx[i]) in thumb_ok else None)})
    selftest = compute_picks([dict(r) for r in rows], DEFAULT_CFG)
    payload = {"clip": clip_id, "tid": t["tid"], "n": n, "vf": vf, "cur": cur, "lf": lf,
               "selftest": selftest, "rows": rows, "ghost": ghost, "absent": absent,
               "cache_version": CACHE_VERSION,
               "built_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    _atomic_write(cp, json.dumps(payload, ensure_ascii=False))
    return payload


# ── 클립 목록 ─────────────────────────────────────────────────────────────────
def list_clips(out_root: Path) -> list[dict]:
    """코퍼스 루트 스캔 — likeness.json 보유 = 워크벤치 가능 클립."""
    out_root = Path(out_root)
    clips = []
    for lk in sorted(out_root.glob("*/likeness.json")):
        clip_id = lk.parent.name
        clips.append({
            "clip": clip_id,
            "likeness_mtime": int(lk.stat().st_mtime),
            "cached": _cache_fresh(cache_path(out_root, clip_id), out_root, clip_id),
        })
    return clips


# ── GT I/O — fixtures/eval/workbench_gt.jsonl (스키마 v0, additive만) ────────
def gt_default_path() -> Path:
    """레포 체크아웃의 fixtures/eval/workbench_gt.jsonl (openapi 정본 탐색과 동형)."""
    for up in Path(__file__).resolve().parents:
        if (up / "fixtures" / "eval").is_dir():
            return up / "fixtures" / "eval" / "workbench_gt.jsonl"
    # 레포 밖 설치 등 — cwd 기준 폴백 (연구 콘솔은 레포 체크아웃이 정상 배치)
    return Path("fixtures/eval/workbench_gt.jsonl")


def _gt_key(row: dict) -> tuple:
    return (row.get("clip"), row.get("frame"), row.get("role", "center"))


def read_gt(path: Path) -> list[dict]:
    """파일의 판정 rows — 같은 clip:frame:role 은 나중 행이 이김(병합)."""
    if not Path(path).exists():
        return []
    merged: dict[tuple, dict] = {}
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        if row.get("flag") in ("pos", "neg"):
            merged[_gt_key(row)] = row
    return list(merged.values())


def apply_gt(path: Path, row: dict) -> list[dict]:
    """판정 하나 병합-쓰기(원자적). flag=None → 그 깃발 제거(무의견 복귀).

    스키마 도장·ts 는 서버가 찍는다 — 프런트가 무엇을 보내든 파일은 v0 스키마."""
    path = Path(path)
    flag = row.get("flag")
    if flag not in ("pos", "neg", None):
        raise ValueError(f"flag must be pos|neg|null, got {flag!r}")
    clean = {"schema": GT_SCHEMA, "clip": str(row["clip"]), "frame": int(row["frame"]),
             "role": str(row.get("role") or "center"), "flag": flag,
             "corpus": str(row.get("corpus") or ""),
             "ts": row.get("ts") or time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    rows = read_gt(path)
    rows = [r for r in rows if _gt_key(r) != _gt_key(clean)]
    if flag is not None:
        rows.append(clean)
    text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    _atomic_write(path, text)
    return rows


def _atomic_write(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise

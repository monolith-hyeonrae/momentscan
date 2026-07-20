"""likeness — 방문-스코프 외형 ID = 분포 읽기 (구명 appearance, 2026-06-15 개명).

The machine consumer needs MEASUREMENTS, not a JPEG. Per rider track the
landmark observation stream (landmarks.parquet) is canonicalized — un-rotate
each frame by its facial_transformation_matrix, scale-normalize — and the
product is read from the DISTRIBUTION:

    robust center   = the person's mean face geometry (the measurement itself)
    PCA axes        = personal variation; axes labelled by correlating PC
                      scores with the AU/emotion/pose dims we already extract
    eigenvalues     = stability — small residual = expression-free confidence
    frames          = SAMPLES only (center-nearest for a canonical image,
                      pose-binned for hair multi-view), not the deliverable

Eval is label-free (E005 lesson: hand pose priors fight human preference —
here none is needed): split-half reproducibility (does the center converge to
the same place from the clip's two halves?) against inter-person distance
(other rider in the same clip). The same numbers are computed WITHOUT
un-rotation as a control, so "canonicalization helps" is measured, not assumed.
"""

from __future__ import annotations

import json
import logging
import time

import numpy as np
import polars as pl

from momentscan.infra.contracts import validate_likeness
from momentscan.infra.store.stash import (
    read_detections,
    read_fashion,
    read_features,
    read_gate_trace,
    read_landmarks,
    read_parse,
    read_tubelets,
    write_appearance,
)

from momentscan.perception.readings.face_signals import (
    eye_openness,
    pupil_visibility,
    visual_frontality,
)
from momentscan.perception.readings.geometry import canonicalize, norm468, template
from momentscan.perception.readings.pose import CAMERA_FRONTAL_DEG

from momentscan.preset import RACE981

log = logging.getLogger("momentscan.appearance")


def _gate_cohorts(out_root, clip_id: str) -> dict[int, dict[str, set[int]]] | None:
    """The gate cohorts likeness consumes from portrait's gate_trace, per track_id:
      'valid'   — the shared ① VALIDITY verdict (a real, unoccluded face of THIS person).
      'frontal' — the policy-FREE clean-frontal cohort, read from the persisted
                  frontal_clean column (computed ONCE in gates._derive: pose_class==
                  frontal & have_bs) = EXACTLY the cohort clean_ref reduces over.
    likeness has two polarities (see clean-ref-polarity): its IDENTITY CORE (face_id
    centroid, canonical geometry) CONVERGES to clean_ref → built from `frontal` frames
    (ArcFace embeddings of profiles/angles are noisier — frontal gives a far cleaner
    identity centroid: test_0 coherence 0.747→0.900). Its appearance VARIATION (hair
    multi-view, fashion) wants pose spread → stays on `valid`. None → no gate_trace →
    caller keeps its prior all-frames behaviour (graceful degrade, never a hard fail)."""
    gt = read_gate_trace(out_root, clip_id)
    if gt is None or "valid" not in gt.columns:
        return None
    have_fc = "frontal_clean" in gt.columns   # pre-column traces → empty cohort (stale; freshness flags)
    out: dict[int, dict[str, set[int]]] = {}
    for r in gt.iter_rows(named=True):
        tid, fi = int(r["track_id"]), int(r["frame_idx"])
        d = out.setdefault(tid, {"valid": set(), "frontal": set()})
        if r.get("valid"):
            d["valid"].add(fi)
        if have_fc and r.get("frontal_clean"):
            d["frontal"].add(fi)
    return out

N_LM = 478
# empirical frontal (E002) — single home: pose.CAMERA_FRONTAL_DEG (imported above)
BIN_EDGE_DEG = RACE981.camera.bin_edge_deg   # |yaw − frontal| < edge → frontal bin (preset: race981.camera.bin_edge_deg)

# ⑧ 정준 기하(center·neutral) frontal 제한의 폴백 문턱 (user 2026-07-20, 원장 ⑧).
# face_id 센트로이드 전례와 **같은 성질** = "clean-frontal 이 이만큼 없으면 valid 전폭으로
# 폴백(측면 위주 트랙 기아 방지)". 별도 preset 필드를 신설하지 않고 그 값을 재사용한다 —
# 둘 다 '프레임 제한 집계를 신뢰할 최소 정면 프레임 수'라는 한 노브이고, 시설이 재보정하면
# 함께 움직이는 게 옳다(ARCHITECTURE §⑪ 단일-사용 홈 신설 금지). 정의부 1줄 재바인딩 =
# 이 파일의 기존 과도기 문법(f_eyewear 등과 동일, G5 종착=인자·G8 감시).
_CENTER_MIN_FRONTAL = RACE981.likeness.face_id_min_frontal

# ── ⑨ 표본 선발 정책 (2026-07-20 user 진단 카드 왕복 봉인, 원장 ⑨) ──────────────
# 정면(sym∧yaw) → 눈동자(pupil) → 무표정 사다리 + 점수순 + 시간 간격 그리디. 이 값들은
# preset 이 아니다: 시설/카메라 보정이 아니라 "무엇이 좋은 표본인가"의 연구 정책이다
# (ARCHITECTURE §⑤ X — 코드지 값이 아님). sym/pupil 은 무차원 비율이라 카메라 무관,
# yaw dev 는 이미 CAMERA_FRONTAL_DEG(preset)를 뺀 상대각 — 카메라 기하는 preset 이 쥐고
# 선발 알고리즘 구조는 여기 산다. 값 유래는 각 상수 주석.
_SYM_LADDER = ((0.6, 15.0), (0.9, 20.0), (1.3, 999.0))   # (sym |log비| 상한, |yaw dev| deg 상한)
#   동시 만족 = 상호 환각 방어. 완화 3단: 엄격 정면 → 준정면 → 사실상 무제한(3장 확보 폴백).
_PUPIL_LADDER = (0.4, 0.3)          # 눈동자-가시비 floor 완화 2단. floor 직무 = 감김 배제이지
#   개구 최대화가 아님 — user f510 판정(0.43 온전-차분=훌륭·0.5는 과함)으로 0.5→0.4 재보정(f510).
_GAP_LADDER_S = (2.0, 1.0, 0.0)     # 표본 간 최소 시간 간격 [초] 완화 3단(시간 다양성).
#   프레임 변환 = 초 × 런 fps (결합 명시; 원 진단은 fps6 에서 12→6→0 프레임).
_SCORE_W_CALM = 0.40                # 점수 가중 — 무표정 순위 (calm-first, 원장 ⑨ 하이브리드)
_SCORE_W_PUPIL = 0.25               # 점수 가중 — 눈동자-가시 순위
_SCORE_W_Q3 = 0.35                  # 점수 가중 — 자유 품질 3축(선명·face_micro·embedding_norm) 순위
_EYE_OPEN_PCT_FLOOR = 40.0          # 헤어뷰 빈-내 눈뜸 EAR 백분위 floor (감은 눈 배제, 원장 ⑨)

# Classic anthropometric ratios on well-known mesh indices (scale-free —
# the measurement vocabulary; 황금비 is at most a reference POINT on these
# scales, never the basis).
_IDX = {"brow_top": 10, "chin": 152, "side_r": 234, "side_l": 454,
        "eye_r_out": 33, "eye_r_in": 133, "eye_l_in": 362, "eye_l_out": 263,
        "mouth_r": 61, "mouth_l": 291, "lip_top": 0, "lip_bot": 17,
        "nose_bridge": 168, "nose_base": 2}


def face_ratios(shape: np.ndarray) -> dict[str, float]:
    """Anthropometric ratios from a (≥468, 3) shape."""
    def d(a: str, b: str) -> float:
        return float(np.linalg.norm(shape[_IDX[a]] - shape[_IDX[b]]))
    eye_w = (d("eye_r_out", "eye_r_in") + d("eye_l_in", "eye_l_out")) / 2
    face_h, face_w = d("brow_top", "chin"), d("side_r", "side_l")
    return {
        "face_aspect": face_h / face_w,
        "eye_spacing": d("eye_r_in", "eye_l_in") / eye_w,   # 눈 사이 / 눈 폭
        "eye_face": eye_w / face_w,
        "nose_length": d("nose_bridge", "nose_base") / face_h,
        "lower_face": d("nose_base", "chin") / face_h,
        "mouth_width": d("mouth_r", "mouth_l") / face_w,
        "lip_fullness": d("lip_top", "lip_bot") / d("nose_base", "chin"),
    }


def _split_half_drift(shapes: np.ndarray) -> float:
    """RMS distance between the robust centers of the two clip halves —
    the label-free reproducibility metric."""
    h = len(shapes) // 2
    if h < 5:
        return float("nan")
    c1 = np.median(shapes[:h], axis=0)
    c2 = np.median(shapes[h:], axis=0)
    return float(np.sqrt(((c1 - c2) ** 2).sum(axis=1).mean()))


# ── ⑨ 표본 선발 헬퍼 (원장 ⑨ 진단 구현 이식) ─────────────────────────────────

def _pct_rank(x: np.ndarray) -> np.ndarray:
    """유한값의 백분위 순위 [0,100] — NaN 은 NaN 으로 보존(랭킹서 제외)."""
    out = np.full(len(x), np.nan)
    fin = np.isfinite(x)
    if fin.sum():
        v = x[fin]
        out[fin] = np.array([float(np.mean(v <= xi)) * 100 for xi in x[fin]])
    return out


def _rank01(x: np.ndarray, *, flip: bool = False) -> np.ndarray:
    """순위를 [0,1] 로 정규화. flip=True 면 작을수록 높은 점수(무표정 등);
    NaN 은 극값으로 대체돼 최하위로 밀린다."""
    r = np.argsort(np.argsort(np.nan_to_num(x, nan=(np.inf if flip else -np.inf))))
    r = r / max(len(x) - 1, 1)
    return 1 - r if flip else r


def _greedy_spaced(cand: list[int], fx: np.ndarray, gap_frames: list[int]) -> list[int]:
    """점수순 후보에서 시간 간격(프레임) 사다리를 완화하며 3장 그리디 선택.
    gap=0(사다리 끝)에서는 간격 제약이 없어 후보가 3 이상이면 항상 3장을 채운다."""
    got: list[int] = []
    for gap in gap_frames:
        got = []
        for i in cand:
            if all(abs(int(fx[i]) - int(fx[j])) >= gap for j in got):
                got.append(i)
            if len(got) == 3:
                break
        if len(got) == 3:
            break
    return got


def _pick3(score: np.ndarray, sym: np.ndarray, dev: np.ndarray, pupil: np.ndarray,
           fx: np.ndarray, phase_pools: list[np.ndarray], use_phase: bool,
           gap_frames: list[int]) -> tuple[list[int], str]:
    """정면(sym∧yaw) > pupil > phase 사다리 + 점수순 + 시간간격으로 대표 3장을 뽑는다.

    반환 (인덱스 3개, note). 안(엄격)에서 밖(완화)으로 내려가며 처음 3장을 채우는 rung
    에서 멈춘다 — boarding 선호(⑦)는 같은 (sym,pupil) rung 안의 최내곽 루프라, 정면·눈동자
    기준을 낮추면서까지 boarding 을 좇지 않는다. 어느 rung 도 3장을 못 채우면 점수 상위 3(FB)."""
    n = len(fx)
    for sym_max, dev_max in _SYM_LADDER:
        for pu_min in _PUPIL_LADDER:
            for pi, pool in enumerate(phase_pools):
                cand = [i for i in range(n) if pool[i] and sym[i] < sym_max
                        and abs(dev[i]) < dev_max and pupil[i] >= pu_min]
                if len(cand) < 3:
                    continue
                cand.sort(key=lambda i: -score[i])
                got = _greedy_spaced(cand, fx, gap_frames)
                if len(got) == 3:
                    ph_tag = "board" if (use_phase and pi == 0) else "all"
                    return got, f"{ph_tag} sym<{sym_max} pu>={pu_min}"
    return list(np.argsort(-score)[:3]), "FB:score-only"


def _track_face_micro(out_root, clip_id: str, track_id: int, fx: np.ndarray) -> np.ndarray:
    """parse.parquet 의 face_micro(skin-내부 Laplacian var, exposure-gate 예약분) → fx 정렬
    배열, 결측/미실행 NaN. DESCRIPTIVE 보존분을 SELECTION 랭킹에만 쓴다(게이트 아님, 원장 ⑨)."""
    pq = read_parse(out_root, clip_id)
    if pq is None:
        return np.full(len(fx), np.nan)
    pq = pq.filter(pl.col("track_id") == track_id)
    micro_of = dict(zip(pq["frame_idx"].to_list(), pq["face_micro"].to_list()))
    return np.array([micro_of.get(int(f), np.nan) for f in fx], dtype=np.float64)


def _track_embedding_norm(out_root, clip_id: str, track_id: int, fx: np.ndarray) -> np.ndarray:
    """detections.parquet buffalo_l 임베딩의 L2 norm(raw 저장) → fx 정렬, None/결측 NaN.
    face_id centroid(정규화)와 달리 정규화 전 크기 = 뭉개짐/차분정면의 품질 프록시(원장 ⑨ q3)."""
    det = read_detections(out_root, clip_id).filter(pl.col("track_id") == track_id)
    norm_of = {int(f): float(np.linalg.norm(np.asarray(e)))
               for f, e in zip(det["frame_idx"].to_list(), det["embedding"].to_list())
               if e is not None}
    return np.array([norm_of.get(int(f), np.nan) for f in fx], dtype=np.float64)


def _track_reading(out_root, clip_id: str, track_id: int,
                   cohorts: dict[int, dict[str, set[int]]] | None = None,
                   *, phase_pref: str = "", phase_min: int = 0, fps: int = 6) -> dict | None:
    lm = read_landmarks(out_root, clip_id).filter(
        pl.col("track_id") == track_id).sort("frame_idx")
    # ① VALIDITY: drop frames that are not a real, unoccluded face of THIS person before
    # the geometry distribution is built — a misdetect/occlusion frame would skew it.
    # Keep all if no gate_trace, or if filtering would leave too few frames (degrade).
    valid = cohorts.get(track_id, {}).get("valid") if cohorts else None
    if valid is not None:
        keep = lm["frame_idx"].is_in(list(valid))
        if int(keep.sum()) >= 10:
            lm = lm.filter(keep)
    if len(lm) < 10:
        return None
    fx = lm["frame_idx"].to_numpy()
    P = np.array(lm["landmarks"].to_list(), dtype=np.float64).reshape(len(fx), N_LM, 3)
    T = np.array(lm["transform"].to_list(), dtype=np.float64).reshape(len(fx), 4, 4)
    cb = np.array(lm["crop_box"].to_list(), dtype=np.float64)
    canon, raw = canonicalize(P, T, cb)

    # ⑧ (user 2026-07-20, 원장 ⑧): 보고되는 정준 기하(center·neutral)는 FRONTAL 코호트에서만
    # 추론한다 — 측면 얼굴의 직무는 hair 추론이지 shape 집계가 아니다. 이번 결정이 해소하는
    # 것은 "canonical center 를 정면에 제한"이라는 문서화된 열린 결정(center·neutral 뿐)이다.
    # 분포 읽기(PCA·축·blendshape 통계·split_half_drift)와 hair 멀티뷰 pose_bins 는 pose
    # spread 가 필요해 valid 전폭에 남는다. frontal < _CENTER_MIN_FRONTAL 이면 valid 전폭 폴백
    # (측면 위주 트랙 기아 방지) + 정직 열화 로그.
    frontal = cohorts.get(track_id, {}).get("frontal") if cohorts else None
    fmask = (np.array([int(f) in frontal for f in fx], dtype=bool)
             if frontal else np.zeros(len(fx), dtype=bool))
    use_frontal = int(fmask.sum()) >= _CENTER_MIN_FRONTAL
    if frontal is not None and not use_frontal:
        log.warning("likeness.degraded", extra={
            "clip_id": clip_id, "track_id": track_id, "lane": "center_frontal",
            "reason": f"frontal={int(fmask.sum())} < min={_CENTER_MIN_FRONTAL} → valid 전폭 폴백"})

    center = np.median(canon[fmask] if use_frontal else canon, axis=0)   # ⑧ 보고 중심 = 정면-전용
    # PCA(개인 변이 축)는 valid 전폭 분포 읽기 — 자기 평균(valid-all) 중심 잔차라, center 를
    # 정면 제한해도 잔차·축·resid_rms 는 byte-identical 로 남는다.
    center_all = np.median(canon, axis=0)
    flat = (canon - center_all).reshape(len(fx), -1)
    _, S, Vt = np.linalg.svd(flat / np.sqrt(len(fx)), full_matrices=False)
    var = S ** 2
    evr = (var / (var.sum() + 1e-18))[:5]
    scores = flat @ Vt[:3].T                 # per-frame PC scores (top 3)
    resid_rms = float(np.sqrt((flat ** 2).sum(axis=1).mean() / N_LM))

    # Label the axes with dims we already have (expression? residual pose?).
    axes = []
    try:
        from momentscan_features_specialist45d.registry import INDEX
        feats = read_features(out_root, clip_id, "A").filter(
            pl.col("track_id") == track_id).sort("frame_idx")
        ffx = feats["frame_idx"].to_numpy()
        M = np.array(feats["feature"].to_list(), dtype=np.float64)
        pos = {f: i for i, f in enumerate(ffx)}
        sel = np.array([pos[f] for f in fx])
        probes = {"em_happy": M[sel, INDEX["em_happy"]],
                  "au12_smile": M[sel, INDEX["au12_lip_corner"]],
                  "au25_lips": M[sel, INDEX["au25_lips_part"]],
                  "yaw": M[sel, INDEX["head_yaw_dev"]],
                  "pitch": M[sel, INDEX["head_pitch"]]}
        for k in range(3):
            corr = {}
            for name, x in probes.items():
                m = np.isfinite(x)
                if m.sum() > 10 and np.nanstd(x[m]) > 1e-9:
                    corr[name] = round(float(np.corrcoef(scores[m, k], x[m])[0, 1]), 3)
            top = sorted(corr.items(), key=lambda kv: -abs(kv[1]))[:2]
            axes.append({"pc": k + 1, "evr": round(float(evr[k]), 4), "top_corr": dict(top)})
        yaw_all = M[sel, INDEX["head_yaw_dev"]]
        blur_all = M[sel, INDEX["face_blur"]]
    except Exception:
        yaw_all = np.full(len(fx), np.nan)
        blur_all = np.full(len(fx), np.nan)

    # ── 평균 대비: canonical template offset + anthropometric ratios ─────────
    person = norm468(center)
    tmpl = template()
    off = np.sqrt(((person - tmpl) ** 2).sum(axis=1))
    pr, tr = face_ratios(person), face_ratios(tmpl)
    template_rec = {   # (record; a local named `template` would shadow geometry.template)
        "offset_rms": round(float(np.sqrt((off ** 2).mean())), 4),
        "ratios": {k: {"person": round(pr[k], 4), "template": round(tr[k], 4),
                       "diff_pct": round((pr[k] / tr[k] - 1) * 100, 1)} for k in pr},
    }

    # ── 보편 표정 기저 (blendshapes) ─────────────────────────────────────────
    blend = None
    neutral = None
    expr = np.zeros(len(fx))   # 표정계수(⑨ 무표정 선발용) — 기본 0, blendshape 있으면 채운다
    if "blendshapes" in lm.columns and lm["blendshapes"][0] is not None:
        from momentscan_features_specialist45d.specialists import BLENDSHAPE_ORDER
        B = np.array(lm["blendshapes"].to_list(), dtype=np.float64)
        expr_cols = [i for i, n in enumerate(BLENDSHAPE_ORDER)
                     if n != "_neutral" and not n.startswith("eyeLook")]
        expr = B[:, expr_cols].max(axis=1)
        calm = expr < 0.3
        calm_shift = None
        if calm.sum() >= 10:
            calm_center = np.median(canon[calm], axis=0)   # blendshape 통계 = valid 전폭(center_all)
            calm_shift = round(float(np.sqrt(((calm_center - center_all) ** 2)
                                             .sum(axis=1).mean())), 4)
        med = np.median(B, axis=0)
        p90 = np.percentile(B, 90, axis=0)
        top = np.argsort(-med)[:5]
        blend = {
            "n_calm": int(calm.sum()),
            "calm_ratio": round(float(calm.mean()), 3),
            "calm_center_shift": calm_shift,    # 표정 조건화가 중심을 얼마나 움직이나
            "median_top": {BLENDSHAPE_ORDER[i]: round(float(med[i]), 3) for i in top},
            # ARKit-호환 표정 시그니처 — Blender 아바타 shape key와 이름 1:1.
            "profile": {n: [round(float(med[i]), 3), round(float(p90[i]), 3)]
                        for i, n in enumerate(BLENDSHAPE_ORDER)},
        }

        # ── 무표정 보정: blendshape 회귀 (⑧: frontal 입력) ─────────────────────
        # 선형 blendshape 모델 shape ≈ neutral + Σ bs_k·basis_k 의 역적용:
        # ridge 회귀의 절편 = bs=0(완전 무표정)에서의 기하. calm 프레임이
        # 0.3~1.8%뿐이라(야외 squint) 프레임 선별 대신 회귀가 유일한 길.
        # bs=0은 관측 범위 밖 외삽 — split-half 재현성이 그 위험의 측정기.
        # ⑧: 회귀 입력도 center 와 같은 frontal 코호트(폴백 시 valid 전폭 = 이전 거동).
        nsel = np.where(fmask)[0] if use_frontal else np.arange(len(fx))
        Y = canon[nsel].reshape(len(nsel), -1)
        A = np.hstack([np.ones((len(nsel), 1)), B[nsel, 1:]])
        lam = 0.01 * len(nsel)

        def _fit_neutral(sl: slice) -> np.ndarray:
            Ah, Yh = A[sl], Y[sl]
            G = Ah.T @ Ah + lam * np.eye(A.shape[1])
            G[0, 0] -= lam                      # don't shrink the intercept
            return np.linalg.solve(G, Ah.T @ Yh)

        theta = _fit_neutral(slice(None))
        neutral_face = theta[0].reshape(N_LM, 3)
        resid_var = float((Y - A @ theta).var())
        var_exp = 1.0 - resid_var / float((Y - Y.mean(axis=0)).var())
        h = len(nsel) // 2
        n_drift = float("nan")
        if h >= 30:
            d1 = _fit_neutral(slice(0, h))[0].reshape(N_LM, 3)
            d2 = _fit_neutral(slice(h, None))[0].reshape(N_LM, 3)
            n_drift = float(np.sqrt(((d1 - d2) ** 2).sum(axis=1).mean()))
        npr = face_ratios(norm468(neutral_face))
        n_off = np.sqrt(((norm468(neutral_face) - tmpl) ** 2).sum(axis=1))
        neutral = {
            # expression-regressed canonical geometry — what downstream
            # adapters (e.g. appearance-engine face recipe) consume.
            "center": np.round(neutral_face, 5).reshape(-1).tolist(),
            "var_explained": round(var_exp, 3),
            "split_half_drift": round(n_drift, 4),
            "shift_from_center": round(float(np.sqrt(
                ((neutral_face - center) ** 2).sum(axis=1).mean())), 4),
            "offset_rms": round(float(np.sqrt((n_off ** 2).mean())), 4),
            "ratios": {k: {"person": round(npr[k], 4), "template": round(tr[k], 4),
                           "diff_pct": round((npr[k] / tr[k] - 1) * 100, 1)}
                       for k in npr},
        }

    # ── ⑨ 표본 선발 (2026-07-20 user 진단 카드 판정, 원장 ⑨) ─────────────────────
    # center_nearest = 정면(sym∧yaw)>눈동자(pupil)>무표정 사다리 + 점수순 + 시간간격으로
    # 뽑은 대표 3장 (구 "center-거리 최근접"을 대체 — 거리는 어두움·감김·측면을 안 걸렀다).
    # pose_bins = 헤어 멀티뷰, 빈-내 눈뜸 floor + 품질 Q argmax. ⑦ boarding 선호(원장 ⑦,
    # user 2026-07-14)는 사다리 최내곽/빈-내 소프트로 보존한다 — 3뷰·샘플 수 손실 없음,
    # 미달이면 전체 폴백 + 정직 열화 warning. phase_pref/phase_min/fps 는 인자다 — 이 함수는
    # preset·런 값을 모른다(G5). face_micro=parse DESCRIPTIVE, embedding_norm=detections raw
    # L2 — 둘 다 읽기 전용 품질 프록시(게이트 아님, 원장 ⑨ q3).
    board = np.zeros(len(fx), dtype=bool)
    use_phase = False
    if phase_pref:
        tb = read_tubelets(out_root, clip_id).filter(pl.col("track_id") == track_id)
        phase_of = dict(zip(tb["frame_idx"].to_list(), tb["scene_phase"].to_list()))
        board = np.array([phase_of.get(int(f)) == phase_pref for f in fx])
        use_phase = int(board.sum()) >= phase_min
        if not use_phase:
            log.warning("likeness.degraded", extra={
                "clip_id": clip_id, "track_id": track_id, "lane": "phase",
                "reason": f"{phase_pref}={int(board.sum())} < min={phase_min} → 전체 폴백"})

    pupil = pupil_visibility(P)
    sym = visual_frontality(P)
    dev = yaw_all - CAMERA_FRONTAL_DEG
    sharp_pct = _pct_rank(blur_all)
    micro_pct = _pct_rank(_track_face_micro(out_root, clip_id, track_id, fx))
    norm_pct = _pct_rank(_track_embedding_norm(out_root, clip_id, track_id, fx))
    q3 = np.nanmean(np.vstack([sharp_pct, micro_pct, norm_pct]), axis=0)   # 자유 품질 3축
    score = (_SCORE_W_CALM * _rank01(expr, flip=True)
             + _SCORE_W_PUPIL * _rank01(pupil)
             + _SCORE_W_Q3 * _rank01(q3))

    phase_pools = [board, np.ones(len(fx), bool)] if use_phase else [np.ones(len(fx), bool)]
    gap_frames = [int(round(s * fps)) for s in _GAP_LADDER_S]   # 초 × 런 fps → 프레임 간격
    picked, sel_note = _pick3(score, sym, dev, pupil, fx, phase_pools, use_phase, gap_frames)
    center_nearest = [int(fx[i]) for i in picked]

    # 헤어뷰 빈: 빈-내 눈뜸 floor(EAR pct ≥ floor) + 품질 Q argmax, floor 미충족 시 빈 폴백(FB).
    eye_pct = _pct_rank(eye_openness(canon))
    Q = np.nanmean(np.vstack([eye_pct, micro_pct, sharp_pct]), axis=0)
    bins: dict[str, int] = {}
    bins_fb: list[str] = []
    for name, mask in (("frontal", np.abs(dev) < BIN_EDGE_DEG),
                       ("left", dev <= -BIN_EDGE_DEG), ("right", dev >= BIN_EDGE_DEG)):
        m = mask & np.isfinite(blur_all)
        if not m.any():
            continue                                 # 관측 없는 뷰 = 정직한 결측(C11)
        mb = m & board
        pool = mb if (use_phase and mb.any()) else m   # 빈-내 boarding 선호, 없으면 그 빈의 ride
        pe = pool & (eye_pct >= _EYE_OPEN_PCT_FLOOR)
        if not pe.any():
            bins_fb.append(name)                     # 뜬 눈 없음 → 빈 전체로 폴백(정직 표기)
        pw = np.where(pe if pe.any() else pool)[0]
        bins[name] = int(fx[pw[np.argmax(np.nan_to_num(Q[pw], nan=-1.0))]])

    # samples.selection = 소형 provenance (C11 additive; 소비자 = 카드/감사). 과설계 금지.
    sel_prov = {"policy": "frontal-pupil-calm/v1", "center_nearest": sel_note}
    if bins_fb:
        sel_prov["pose_bins_fb"] = sorted(bins_fb)

    return {
        "n_obs": int(len(fx)),
        "split_half_drift": round(_split_half_drift(canon), 5),
        "split_half_drift_raw": round(_split_half_drift(raw), 5),  # no un-rotate control
        "resid_rms": round(resid_rms, 5),
        "evr_top5": [round(float(e), 4) for e in evr],
        "axes": axes,
        "template": template_rec,
        "neutral": neutral,
        "blendshapes": blend,
        "samples": {"center_nearest": center_nearest, "pose_bins": bins, "selection": sel_prov},
        "_center": center,                    # stripped before JSON; used for separation
    }


FACE_ID_MIN_FRONTAL = RACE981.likeness.face_id_min_frontal   # < this many clean-frontal frames → fall back to `valid` (preset)
FACE_ID_P05_FLOOR = RACE981.likeness.face_id_p05_floor        # coherence_p05 < 이 값 → 저품질 희석 (P1-② 감사; preset)


def _face_ids(out_root, clip_id: str,
              cohorts: dict[int, dict[str, set[int]]] | None = None) -> dict[int, dict]:
    """Visit-scoped identity embedding per subject — likeness is the
    layer that records what does NOT change over today's frames (오늘의 이
    사람: face, hair, wear, ... and the face_id itself). The ArcFace-style
    buffalo_l centroid is directly consumable by diffusion personalization
    (InstantID / IP-Adapter-FaceID conditioning), independent of face_recipe.

    The centroid is the IDENTITY CORE, so it CONVERGES to clean_ref: built from the
    FRONTAL cohort (pose_class==frontal & have_bs), NOT every valid frame. ArcFace
    embeddings of profiles/angles are noisy — frontal gives a far cleaner centroid
    (test_0 coherence 0.747→0.900). Per subject: frontal if ≥ FACE_ID_MIN_FRONTAL frames,
    else the broader `valid` set (don't starve a mostly-profile track). No gate_trace →
    all embeddings. (The misdetect/occlusion exclusion of the old valid-filter is kept:
    frontal ⊂ valid, and the valid fallback still drops invalid frames.)

    Embeddings come from TUBELETS (the subjectlet, C3) — not raw detections, whose
    raw-vs-subject id split forces re-litigating WHO here and whose bystander/ghost
    tracks were centroided for nothing (rider frame sets verified identical)."""
    try:
        df = read_tubelets(out_root, clip_id)
    except Exception:
        return {}
    keep: dict[int, set[int]] | None = None
    if cohorts is not None:
        keep = {sid: (d["frontal"] if len(d["frontal"]) >= FACE_ID_MIN_FRONTAL else d["valid"])
                for sid, d in cohorts.items()}
    by_sid: dict[int, list[np.ndarray]] = {}
    for r in df.iter_rows(named=True):
        if r["embedding"] is None:
            continue
        sid = int(r["track_id"])
        if keep is not None and sid in keep and int(r["frame_idx"]) not in keep[sid]:
            continue                                   # not a frontal-core (or valid-fallback) frame → skip
        v = np.asarray(r["embedding"], dtype=np.float32)
        n = float(np.linalg.norm(v))
        if n > 0:
            by_sid.setdefault(sid, []).append(v / n)
    out: dict[int, dict] = {}
    for sid, vecs in by_sid.items():
        mat = np.stack(vecs)
        c = mat.mean(axis=0)
        c /= np.linalg.norm(c)
        cos = mat @ c
        p05 = round(float(np.percentile(cos, 5)), 3)
        out[sid] = {
            "model": "buffalo_l",
            "n_emb": int(len(vecs)),
            "coherence_mean": round(float(cos.mean()), 3),
            "coherence_p05": p05,
            "low_confidence": bool(p05 < FACE_ID_P05_FLOOR),   # 소비자(MICA·diffusion) 주의 신호 — 게이트 아님
            "embedding": np.round(c, 6).tolist(),
        }
    return out


# fashion/accessory thresholds (parse.parquet) — preset policy (cap_1 보정), preset 으로
# 이주(race981.likeness.*). 정의부 1줄 재바인딩 = 과도기 문법(G5 종착=인자 전달).
_F_EYEWEAR = RACE981.likeness.f_eyewear
_F_SUN_LUM = RACE981.likeness.f_sun_lum
_F_MASK = RACE981.likeness.f_mask
_F_HAT = RACE981.likeness.f_hat
_F_WORN = RACE981.likeness.f_worn
_F_MIN_JUDGEABLE = RACE981.likeness.f_min_judgeable   # < this many clean-frontal → all-frames fallback
_F_FUSE_TAU = RACE981.likeness.f_fuse_tau             # typed covering 신뢰 ≥ → parse mask 불리언 기각
_HAIR_OBS_TAU = RACE981.likeness.hair_obs_tau         # hair/face 픽셀비 < → hair 관측불가(후드-업)


def _fashion_reading(out_root, clip_id: str,
                     cohorts: dict[int, dict[str, set[int]]] | None = None) -> dict[int, dict]:
    """Per-rider visit-scoped fashion reading — per-frame parse signals aggregated
    to a stable conclusion (worn = persistent), NOT a per-frame classification.
    Worn items (sunglasses/mask/hat) are part of "오늘 이 사람의 ID". Eyewear is
    split sunglasses vs clear by eye-region luminance. Mid-range fraction →
    'variable' (put on/off mid-ride = a state-change segment candidate). Empty if
    no parse.parquet.

    JUDGEABILITY: rows are conditioned on the clean-frontal cohort (frontal_clean)
    — SegFormer presence parsing is frontal-premised, so off-frontal "mouth
    invisible" is a POSE fact, not a worn mask (test_0 s2: false mask_frac 0.352 →
    0.000 under frontal-conditioning while the real mask wearer s18 stays 1.000).
    A mostly-profile track (< _F_MIN_JUDGEABLE frontal frames) falls back to all
    rows — the FACE_ID_MIN_FRONTAL pattern (don't starve; degrade to the old read)."""
    df = read_parse(out_root, clip_id)
    if df is None:
        return {}
    # FashionCLIP enrichment (typed accessory attrs) — complementary to the
    # geometric parse signal (each has failure modes: parse misses hoods, clip
    # misses clear glasses / over-predicts scarf). Both kept; fusion = preset.
    fc = {}
    ci = {}
    hair = {}
    fcj = read_fashion(out_root, clip_id)
    if fcj:
        fc = {s["subject_id"]: {k: s[k] for k in ("eyewear", "headwear", "covering") if k in s}
              for s in fcj.get("subjects", [])}
        # color identity (Cat W #86-89 포팅, P1-2b) — 방문-집계 의상 팔레트.
        # fashion 스테이지가 생산, likeness가 rider 최상위 필드로 배달.
        ci = {s["subject_id"]: s.get("color_identity") for s in fcj.get("subjects", [])}
        hair = {s["subject_id"]: s.get("hair") for s in fcj.get("subjects", [])}
    out: dict[int, dict] = {}
    for sid in df["track_id"].unique().to_list():
        d = df.filter(pl.col("track_id") == int(sid))
        frontal = cohorts.get(int(sid), {}).get("frontal") if cohorts else None
        if frontal is not None and len(frontal) >= _F_MIN_JUDGEABLE:
            dj = d.filter(pl.col("frame_idx").is_in(list(frontal)))
            if dj.height >= _F_MIN_JUDGEABLE:
                d = dj
        n = d.height
        eyewear = d["glasses_frac"].to_numpy() > _F_EYEWEAR
        sun = eyewear & (d["eye_lum_rel"].fill_null(1.0).to_numpy() < _F_SUN_LUM)
        mask = d["mouth_vis"].to_numpy() < _F_MASK
        hat = d["hat_frac"].to_numpy() > _F_HAT
        ew_f, sun_f, mask_f, hat_f = (round(float(x.mean()), 3) for x in (eyewear, sun, mask, hat))
        eyewear_type = "none" if ew_f < _F_WORN else ("sunglasses" if sun_f >= 0.4 else "clear")
        # 두-레인 융합 (P1-④ⓐ): parse의 mouth_vis는 occlusion-blind — "입이 안 보인다"
        # 만 안다. 고신뢰 typed covering이 가린 것의 이름(scarf 등)을 대면 그쪽이 이긴다
        # (dual_3 s0: 스카프를 턱까지 → parse mask 0.511 FP, covering scarf 0.915가 정답).
        # 역방향(parse False→mask True) 승격은 코퍼스 증거 없음 — 미적용.
        mask_worn = mask_f >= _F_WORN
        cov = (fc.get(int(sid)) or {}).get("covering") or {}
        mask_override = None
        if mask_worn and cov.get("winner") not in (None, "mask") and cov.get("conf", 0.0) >= _F_FUSE_TAU:
            mask_override = {"from": True, "by": "covering",
                             "winner": cov["winner"], "conf": cov["conf"]}
            mask_worn = False
        variable = [k for k, f in (("eyewear", ew_f), ("mask", mask_f), ("hat", hat_f)) if 0.3 < f < 0.7]
        if mask_override and "mask" in variable:
            variable.remove("mask")   # 중간 frac의 정체가 밝혀짐(스카프) — 착탈 해석 철회
        out[int(sid)] = {
            "eyewear": eyewear_type, "eyewear_frac": ew_f, "sunglasses_frac": sun_f,
            "mask": mask_worn, "mask_frac": mask_f, "mask_override": mask_override,
            "hat": hat_f >= _F_WORN, "hat_frac": hat_f, "n_obs": n,
            "variable": variable,
            "clip": fc.get(int(sid)),     # FashionCLIP typed winners (None if not run)
            "color_identity": ci.get(int(sid)),   # appearance_clip이 최상위로 승격
            "hair": hair.get(int(sid)),           # appearance_clip이 samples로 승격
        }
    return out


def appearance_clip(out_root, clip_id: str, *, fps: int = 6) -> dict:
    """Read the appearance distribution for every rider track; write
    likeness.json (center geometry + confidence + samples + fashion).
    fps = 런 프레임 레이트 (⑨ 표본 시간 간격 → 프레임 변환용, G5: 호출부가 전달)."""
    t0 = time.perf_counter()
    lm = read_landmarks(out_root, clip_id)
    riders: dict[str, dict] = {}
    centers: dict[int, np.ndarray] = {}
    roles = dict(zip(lm["track_id"], lm["rider_role"], strict=False))
    cohorts = _gate_cohorts(out_root, clip_id)  # {tid: {valid, frontal}} (None → all-frames fallback)
    face_ids = _face_ids(out_root, clip_id, cohorts)   # identity core → FRONTAL cohort
    fashion = _fashion_reading(out_root, clip_id, cohorts)   # judgeable = clean-frontal cohort
    drifts: dict[int, float] = {}
    for tid in sorted(set(lm["track_id"].to_list())):
        r = _track_reading(out_root, clip_id, tid, cohorts,
                           phase_pref=RACE981.likeness.hair_phase,
                           phase_min=RACE981.likeness.phase_min_frames,
                           fps=fps)   # G5: 호출부가 preset·런 값 전달
        if r is None:
            continue
        centers[tid] = r.pop("_center")
        drifts[tid] = r.get("split_half_drift")
        # 제품 스코프 (user 2026-07-07): likeness는 **주탑승자만** — aux는 얼굴이 작고
        # 상시 가림이라 측정 신뢰가 낮다 (P1-② 감사: aux들이 coherence·n_obs 최저).
        # 센터/drift는 전 트랙 계산 유지 — separation(사람-간÷drift) 자의 상대측 필요.
        if roles.get(tid) != "main":
            continue
        fa = fashion.get(tid)
        color_id = fa.pop("color_identity", None) if fa else None
        hair = fa.pop("hair", None) if fa else None
        if hair and hair.get("visible_frac") is not None:
            # hair_match 이음매의 결측 신호: 후드-업이면 pose_bins 크롭에 hair가 없다.
            hair["observable"] = hair["visible_frac"] >= _HAIR_OBS_TAU
        r["samples"]["hair"] = hair
        riders[str(tid)] = {"role": roles.get(tid), **r, "face_id": face_ids.get(tid),
                            "fashion": fa, "color_identity": color_id}

    # Inter-person separation vs intra-person drift — the label-free yardstick.
    separation = []
    tids = sorted(centers)
    for i, a in enumerate(tids):
        for b in tids[i + 1:]:
            d = float(np.sqrt(((centers[a] - centers[b]) ** 2).sum(axis=1).mean()))
            drift = float(np.nanmean([drifts.get(t) for t in (a, b)]))
            separation.append({"tracks": [a, b], "dist": round(d, 5),
                               "ratio_vs_drift": round(d / drift, 1) if drift else None})

    record = {
        "schema": "momentscan.likeness/v1",   # P1-③ 동결 (2026-07-07) — contracts.md C11
        "clip_id": clip_id,
        "riders": {k: {**v, "center": np.round(centers[int(k)], 5).reshape(-1).tolist()}
                   for k, v in riders.items()},
        "separation": separation,
        "elapsed_s": round(time.perf_counter() - t0, 3),
        "ok": bool(riders),
    }
    validate_likeness(record, clip_id=clip_id)   # C11 형태 검증 — write 직전 fail-fast (R6/L3)
    path = write_appearance(out_root, clip_id, record)
    shown = {**record, "riders": {k: {kk: vv for kk, vv in v.items() if kk != "center"}
                                  for k, v in record["riders"].items()},
             "appearance_path": str(path)}
    log.info("appearance.done", extra={k: v for k, v in shown.items() if k != "riders"})
    return shown

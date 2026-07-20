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
    read_fashion,
    read_features,
    read_gate_trace,
    read_landmarks,
    read_parse,
    read_tubelets,
    write_appearance,
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


def _track_reading(out_root, clip_id: str, track_id: int,
                   cohorts: dict[int, dict[str, set[int]]] | None = None) -> dict | None:
    lm = read_landmarks(out_root, clip_id).filter(
        pl.col("track_id") == track_id).sort("frame_idx")
    # ① VALIDITY: drop frames that are not a real, unoccluded face of THIS person before
    # the geometry distribution (center/PCA/neutral) is built — a misdetect/occlusion frame
    # would skew the canonical shape. (Geometry stays on the broad `valid` set, not the
    # frontal core: canonicalization un-rotates pose, and the hair multi-view pose_bins need
    # the spread; frontal-restricting the canonical center is a separate open decision.)
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

    center = np.median(canon, axis=0)
    flat = (canon - center).reshape(len(fx), -1)
    # PCA over the residuals — personal variation axes.
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
    if "blendshapes" in lm.columns and lm["blendshapes"][0] is not None:
        from momentscan_features_specialist45d.specialists import BLENDSHAPE_ORDER
        B = np.array(lm["blendshapes"].to_list(), dtype=np.float64)
        expr_cols = [i for i, n in enumerate(BLENDSHAPE_ORDER)
                     if n != "_neutral" and not n.startswith("eyeLook")]
        expr_level = B[:, expr_cols].max(axis=1)
        calm = expr_level < 0.3
        calm_shift = None
        if calm.sum() >= 10:
            calm_center = np.median(canon[calm], axis=0)
            calm_shift = round(float(np.sqrt(((calm_center - center) ** 2)
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

        # ── 무표정 보정: blendshape 회귀 ────────────────────────────────────
        # 선형 blendshape 모델 shape ≈ neutral + Σ bs_k·basis_k 의 역적용:
        # ridge 회귀의 절편 = bs=0(완전 무표정)에서의 기하. calm 프레임이
        # 0.3~1.8%뿐이라(야외 squint) 프레임 선별 대신 회귀가 유일한 길.
        # bs=0은 관측 범위 밖 외삽 — split-half 재현성이 그 위험의 측정기.
        Y = canon.reshape(len(fx), -1)
        A = np.hstack([np.ones((len(fx), 1)), B[:, 1:]])
        lam = 0.01 * len(fx)

        def _fit_neutral(sl: slice) -> np.ndarray:
            Ah, Yh = A[sl], Y[sl]
            G = Ah.T @ Ah + lam * np.eye(A.shape[1])
            G[0, 0] -= lam                      # don't shrink the intercept
            return np.linalg.solve(G, Ah.T @ Yh)

        theta = _fit_neutral(slice(None))
        neutral_face = theta[0].reshape(N_LM, 3)
        resid_var = float((Y - A @ theta).var())
        var_exp = 1.0 - resid_var / float((Y - Y.mean(axis=0)).var())
        h = len(fx) // 2
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

    # Samples FROM the distribution: center-nearest (canonical image) and
    # pose bins (hair multi-view) — sharpest frame within each bin.
    dist_c = np.sqrt(((canon - center) ** 2).sum(axis=2).mean(axis=1))
    center_nearest = [int(fx[i]) for i in np.argsort(dist_c)[:3]]
    bins: dict[str, int] = {}
    dev = yaw_all - CAMERA_FRONTAL_DEG
    for name, mask in (("frontal", np.abs(dev) < BIN_EDGE_DEG),
                       ("left", dev <= -BIN_EDGE_DEG), ("right", dev >= BIN_EDGE_DEG)):
        m = mask & np.isfinite(blur_all)
        if m.any():
            bins[name] = int(fx[np.where(m)[0][np.argmax(blur_all[m])]])

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
        "samples": {"center_nearest": center_nearest, "pose_bins": bins},
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


def appearance_clip(out_root, clip_id: str) -> dict:
    """Read the appearance distribution for every rider track; write
    likeness.json (center geometry + confidence + samples + fashion)."""
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
        r = _track_reading(out_root, clip_id, tid, cohorts)
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

"""select v2 (E003) — directed readings + Δ-contrast + phrase segments.

E002 proved that adding dims to an UNDIRECTED residual does not help
(0.456→0.441): magnitude without direction ranks a head-turn with a smile.
v2 makes the readings directional and temporal:

likeness (외형 측정용 — 옛 이름 "profile"은 폐기, 동결 168쌍 라벨
  데이터의 product:"profile" 문자열만 그대로 두고 evalharness가 alias로
  흡수한다) —
    frontal gate exp(−(yaw−12°)²/2σ²)   (12° = this camera's empirical frontal)
  × calm (em_neutral — suppressed expression measures better)
  × quality (sharpness, exposure, no clipping)   × boarding bonus (no wind)

highlight — 2026-07-03 졸업: 시간 제품 정책(합동 악구·방출)은 highlight.py가
  소유하고 highlight.json을 쓴다. 이 파일은 highlight의 프레임 채널
  (when/which/impact/rarity/scene/valence/arousal)을 frame_scores로 계산해
  줄 뿐이다. WHEN 채널 측정: max 0.662 > impact-only 0.632.

portrait (E008→E009a/b, 대표 사진) — aesthetic, NO pose prior (E005 lesson;
  앵글샷·사이드샷도 portrait): quality × eyes-open(blendshape) ×
  pleasant(smile bs ⊕ valence 블렌드) × em_conf × light(측면 방향광 lr 가산
  + DPR SH ambient 가산 — "얼굴이 밝게 받는가", 역광만 벌점; E009a에서 v0
  평탄광 prior 역전·harsh 제거, E009b에서 SH ambient 합류) ×
  representativeness(정준 center 거리, soft — unknown이면 무벌점).
  Two readings, one gate:
  ``portrait`` = top rank (대표 1장), ``portrait_set`` = quality-FLOOR-gated
  view coverage (frontal/left/right/side — 다양성 = 잘 나온 다양한 뷰).
  Its true eval = a NEW pairwise lane (taste); 동결 168쌍과 별도.

``frame_scores`` is THE scoring function — select_clip builds candidates from
it and eval --rescore re-derives pair preferences from it, so the 168 frozen
human winners measure every version of this file.

NB 이 파일은 제품이 아니라 **공유 채점 기판 + select 스테이지**다: 세 제품의
프레임 점수를 한 번에 계산(frame_scores)하고 likeness 후보를 기록한다.
제품 파일은 likeness.py / portrait.py / highlight.py.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import polars as pl

from momentscan.perception.readings.emotion import fused_valence
from momentscan.perception.readings.pose import CAMERA_FRONTAL_DEG
from momentscan.infra.store.stash import (
    append_candidate, candidates_path, read_features, read_gate_trace, read_tubelets, write_select,
)
from momentscan.infra.store.telemetry import CandidateLog

log = logging.getLogger("momentscan.select")

# empirical frontal for the off-axis camera (E002) — single home: pose.CAMERA_FRONTAL_DEG
FRONTAL_SIGMA = 20.0
WHICH_YAW_SIGMA = 30.0   # highlight tolerates more head-turn than likeness
BURN_IN_S = 3.0
TOP_K = 3
# 배달 창·방출(VAL_EMIT_FLOOR·AROUSAL_EMIT_TAU·CLIP_LEN_S·MAX_PHRASE_S)은
# highlight.py로 졸업 — 시간 제품 정책은 제품 파일이 소유한다.
RARITY_WIN_S = 2.0       # E010: state-window grain for the rarity reading
# E010: dims feeding the state vector (rarity + phrase kind descriptors) —
# emotion, pose, framing, lighting; per-track robust-z, NaN = per-dim median.
RARITY_FIELDS = (
    "em_happy", "em_neutral", "em_surprise", "em_angry",
    "em_contempt", "em_disgust", "em_fear", "em_sad",
    "head_yaw_dev", "head_pitch", "head_roll",
    "face_area_ratio", "face_center_distance", "face_blur", "face_exposure",
    *(f"lighting__sector_{i}" for i in range(9)),
    "face_light_lr", "face_light_tb", "face_light_harsh",
    *(f"face_sh_{i}" for i in range(9)),
)


def rolling_median(x: np.ndarray, win: int) -> np.ndarray:
    """NaN-tolerant rolling median — the WHEN-ridge smoother (kills 1-frame spikes).
    PUBLIC: the inspector's select-timeline subscribes to THIS (never re-implements),
    so the rendered ridge is byte-identical to the one the segments were cut from."""
    out = np.empty_like(x)
    h = win // 2
    for i in range(len(x)):
        w = x[max(0, i - h): i + h + 1]
        # all-NaN window → NaN, without numpy's RuntimeWarning (burn-in edges hit this)
        out[i] = np.nan if np.isnan(w).all() else np.nanmedian(w)
    return out


def when_from_channels(
    impact: np.ndarray, rarity: np.ndarray, scene: np.ndarray, valence: np.ndarray,
) -> tuple[np.ndarray, dict]:
    """Synthesize the highlight WHEN line from its four channels → (when, drivers).

    owner = highlight engine; resident in select.py until R16/17 — 물리 이전은
    energy 재편 트랙이 지불할 수 있다. WHEN 공식의 유일한 정본: 이 함수 밖에서
    공식(리터럴 포함)을 재정의하지 말 것.

    WHEN = max(강렬함 impact, 드묾 rarity, 장면변화 scene, 3·valence⁺) — anomaly
    쌍둥이 OR (recall 목표). 측정: 동결 68평결 0.676 (> E010 0.662 > E003 0.632).

    valence는 3·clip(valence,0,None)로 들어간다 (STEP 3): a quiet POSITIVE-valence
    moment is a highlight the impact/rarity/scene triggers MISS (the bright face just
    before a cheer = high valence + low motion). The trigger is ABSOLUTE-positive
    direction (genuinely valence>0), shared magnitude — NOT person-relative z⁺, which
    fired on "less frowny than this frown-rider's median" (a −0.19 face is still a
    frown, and its 6 s window is full of scowls — bad highlight). Scaled so a full
    laugh (+1) competes with a strong impact (z⁺~3). The truly-subtle case (a rider
    whose peak is only +0.2) stays weak here by design = open point #1 (population
    floor), not a cross-rider-inverting z.

    Element-wise over arrays or scalars. drivers = 각 채널의 WHEN 기여 (valence는
    이미 3배 스케일) — highlight의 피크 breakdown이 여기 구독한다(공식 re-scale 금지).
    """
    val_when = 3.0 * np.clip(valence, 0.0, None)
    when = np.fmax(np.fmax(np.fmax(impact, rarity), scene), val_when)
    drivers = {"impact": impact, "rarity": rarity, "scene": scene, "valence": val_when}

    return when, drivers


def _z(x: np.ndarray) -> np.ndarray:
    med = np.nanmedian(x)
    mad = np.nanmedian(np.abs(x - med)) * 1.4826 + 1e-9
    return (x - med) / mad


def _zp(x: np.ndarray) -> np.ndarray:
    return np.clip(_z(x), 0.0, None)


def _state_rarity(Xn: np.ndarray, *, win: int) -> np.ndarray:
    """E010 WHEN: state-distribution anomaly, person×visit conditioned.

    Window mean vectors over the normalized state matrix → mean distance to
    the k nearest other windows. No baseline constant (the rarity IS the
    score); time-order-free by construction — the transition-anomaly twin
    (Δ-impact) covers what this misses (repeated drops). arXiv 2403.09401
    Fig.1 observation; measured against the frozen pairs in E010.
    """
    r = np.full(len(Xn), np.nan)
    n = len(Xn) - win + 1
    if n < 20:
        return r
    W = np.stack([Xn[i:i + win].mean(axis=0) for i in range(n)])
    D = np.sqrt(((W[:, None, :] - W[None, :, :]) ** 2).sum(-1))
    np.fill_diagonal(D, np.inf)
    k = max(5, n // 10)
    r[win // 2: win // 2 + n] = np.sort(D, axis=1)[:, :k].mean(axis=1)
    return r


def _valid_mask(out_root, clip_id: str, track_id: int, fx: np.ndarray) -> np.ndarray:
    """Per-frame ① VALIDITY for one track, aligned to fx → 1.0 (valid) / 0.0 (invalid).
    Reads portrait's shared `valid` verdict from gate_trace (the SAME column likeness
    consumes) — validity declared once, consumed by all three. highlight gates WHICH
    (face state) on it; WHEN (action impact) stays ungated. No gate_trace → all-1.0."""
    gt = read_gate_trace(out_root, clip_id)
    if gt is None or "valid" not in gt.columns:
        return np.ones(len(fx), dtype=float)
    g = gt.filter(pl.col("track_id") == track_id)
    vset = {int(f) for f, v in zip(g["frame_idx"].to_list(), g["valid"].to_list()) if v}
    return np.array([1.0 if int(f) in vset else 0.0 for f in fx], dtype=float)


def frame_scores(out_root, clip_id: str, track_id: int, *, fps: int = 6) -> dict:
    """Per-frame v2 scores for one track: {'fx', 'likeness', 'highlight', ...}."""
    from momentscan_features_specialist45d.registry import INDEX

    feats = read_features(out_root, clip_id, "A").filter(pl.col("track_id") == track_id).sort("frame_idx")
    tubes = read_tubelets(out_root, clip_id).filter(pl.col("track_id") == track_id).sort("frame_idx")
    fx = feats["frame_idx"].to_numpy()
    M = np.array(feats["feature"].to_list(), dtype=np.float64)
    phase = dict(zip(tubes["frame_idx"], tubes["scene_phase"], strict=True))
    ts = dict(zip(tubes["frame_idx"], tubes["timestamp_ms"], strict=True))
    bbox = {r["frame_idx"]: r["bbox"] for r in tubes.iter_rows(named=True)}

    def col(name):
        return M[:, INDEX[name]]

    def col_opt(name):   # newer registry dims on an older parquet → NaN (graceful)
        i = INDEX[name]
        return M[:, i] if M.shape[1] > i else np.full(len(fx), np.nan)

    yaw, pitch = col("head_yaw_dev"), col("head_pitch")
    happy, surprise, neutral = col("em_happy"), col("em_surprise"), col("em_neutral")
    det = col("face_confidence")
    # Emotion-classifier confidence as a photo-usability signal (user insight):
    # an ambiguous softmax (no clear winner) usually means an ambiguous FACE —
    # mid-transition grimace, "굴욕사진" — bad for any photo product.
    # STEP 3: the SHARED emotion reading (silo dissolved — select no longer computes
    # its own valence/em_conf inline; one definition in emotion.fused_valence feeds
    # portrait + highlight + likeness). valence_signed is DIRECTED (em_happy − Σneg);
    # em_conf is the same nanmax-softmax 굴욕사진 gate as before.
    _emo = fused_valence(M, INDEX)
    valence_signed = _emo["valence_signed"]
    em_conf = np.nan_to_num(_emo["em_conf"], nan=0.5)
    sectors = np.stack([col(f"lighting__sector_{i}") for i in range(9)], axis=1)
    # E004 — the cheer-face signature (au25/26 mouth open + au5 wide eyes +
    # au1/2 raised brows), DISFA 0–5 → [0,1]; and total AU energy for calm.
    # LibreFace intensities run LOW on small outdoor faces (legacy experience
    # confirmed) — relative dynamics are real though, so normalize per track.
    def _norm01(x):
        lo, hi = np.nanmin(x), np.nanmax(x)
        return (x - lo) / (hi - lo + 1e-9)
    au_energy = _norm01(np.nanmean(np.stack([col(f) for f in (
        "au1_inner_brow", "au2_outer_brow", "au4_brow_lowerer", "au5_upper_lid",
        "au6_cheek_raiser", "au9_nose_wrinkler", "au12_lip_corner",
        "au15_lip_depressor", "au17_chin_raiser", "au20_lip_stretcher",
        "au25_lips_part", "au26_jaw_drop")]), axis=0))

    # ── WHEN: contrasts (Δ), z⁺-combined ────────────────────────────────
    def dgrad(x):
        g = np.abs(np.gradient(np.nan_to_num(x, nan=np.nanmedian(x))))
        return g
    d_expr = dgrad(happy) + dgrad(surprise)
    d_pose = dgrad(yaw) + dgrad(pitch)
    d_light = np.abs(np.gradient(np.nan_to_num(sectors, nan=0.0), axis=0)).max(axis=1)
    cx = np.array([(bbox[f][0] + bbox[f][2]) / 2 for f in fx])
    cy = np.array([(bbox[f][1] + bbox[f][3]) / 2 for f in fx])
    vel = np.hypot(np.gradient(cx), np.gradient(cy))
    impact = np.nanmean(np.stack([_zp(d_expr), _zp(d_pose), _zp(d_light), _zp(vel)]), axis=0)

    # E010: state vector + rarity — the density twin of the Δ-impact above.
    Xn = np.stack([col_opt(d) for d in RARITY_FIELDS], axis=1)
    for j in range(Xn.shape[1]):
        cmed = np.nanmedian(Xn[:, j])
        if not np.isfinite(cmed):
            Xn[:, j] = 0.0
            continue
        filled = np.where(np.isfinite(Xn[:, j]), Xn[:, j], cmed)
        mad = np.median(np.abs(filled - cmed)) + 1e-9
        Xn[:, j] = (filled - cmed) / mad
    rarity = _zp(_state_rarity(Xn, win=int(RARITY_WIN_S * fps)))

    # ── WHICH: directed face state ──────────────────────────────────────
    # valence is the SIGNED shared signal (computed above). The old
    # happy+surprise+cheer SUM is gone: it was unsigned (a frustrated face scored
    # ~neutral, not negative) and folded AU energy (arousal) into the valence axis.
    valence = valence_signed
    # E005 (select_timeline finding: side/occluded rep frames): visibility is
    # pose-GRADED, not binary — a measured 60° turn is no longer "fully
    # visible", and a missing mesh (usually a hard turn or occlusion) costs
    # more than the old 0.5.
    front = np.where(np.isfinite(yaw),
                     np.exp(-((yaw - CAMERA_FRONTAL_DEG) ** 2) / (2 * WHICH_YAW_SIGMA ** 2)),
                     0.25)
    visibility = np.nan_to_num(det, nan=0.0) * (0.3 + 0.7 * front)
    # WHICH directed by the SIGNED valence: a negative expression (frustration) now
    # scores low instead of floored-neutral — a negative moment is not picked as a rep.
    which = np.clip(0.5 + 0.5 * valence, 0.0, 1.0) * visibility * (0.4 + 0.6 * em_conf)
    # ① VALIDITY gate on WHICH (face state) — NOT on WHEN (action). A highlight's rep must
    # be a real, unoccluded face of THIS person: a misdetect/occluded frame zeroes WHICH so
    # it can be neither a rep (argmax WHICH) nor a highlight peak (WHEN×WHICH), while WHEN
    # still fires on the action so the moment is still found (the rep within it is valid).
    # Inherits ① validity, NOT ② portrait policy — a wild-expression valid frame keeps WHICH.
    which = which * _valid_mask(out_root, clip_id, track_id, fx)

    # E012: 장면 변화율 — DINO 임베딩의 시간 미분 = 강렬함의 장면 측.
    # 클립 수준 신호(라이더 무관); scene.parquet 없으면 NaN(무영향).
    scene = np.full(len(fx), np.nan)
    try:
        from momentscan.infra.store.stash import read_scene
        sdf = read_scene(out_root, clip_id).sort("frame_idx")
        E = np.array(sdf["embedding"].to_list(), dtype=np.float64)
        dE = np.linalg.norm(np.diff(E, axis=0), axis=1)
        dE = np.concatenate([[dE[0]], dE]) if len(dE) else dE
        smap = dict(zip(sdf["frame_idx"].to_list(), _zp(dE).tolist(), strict=True))
        scene = np.array([smap.get(int(f), np.nan) for f in fx])
    except Exception:
        pass

    is_ride = np.array([phase.get(f) == "ride" for f in fx])

    # WHEN 합성 + 채널별 driver 는 when_from_channels 가 소유한다 (공식·리터럴의
    # 유일한 정본). 여기·highlight.py 는 그 함수를 구독할 뿐 재정의하지 않는다.
    when, when_drivers = when_from_channels(impact, rarity, scene, valence_signed)

    # rank_sig = 세그먼트-자(E011/E012)의 WHEN — rarity 를 뺀다 (게이트형 판정:
    # "항상 웃는 사람" 미결, 세그먼트 랭킹에서 역방향), WHICH 로 게이트. valence
    # 기여는 정본 함수의 driver 를 경유 (3.0 리터럴 재정의 금지).
    rank_sig = np.fmax(np.fmax(impact, scene), when_drivers["valence"]) * which
    highlight = when * which
    ride_start = int(np.argmax(is_ride)) if is_ride.any() else len(fx)
    for arr in (when, rank_sig, highlight):
        arr[: ride_start + int(BURN_IN_S * fps)] = np.nan
        arr[~is_ride] = np.nan

    # ── likeness: frontal gate × calm × quality ───────────────────
    g = np.where(np.isfinite(yaw),
                 np.exp(-((yaw - CAMERA_FRONTAL_DEG) ** 2) / (2 * FRONTAL_SIGMA ** 2)), 0.05)
    # E005 NOTE: a pitch gate (exp around −10°, σ15) was tried here and
    # REJECTED by measurement (profile 0.593→0.556 on the frozen pairs) —
    # labelers accept the natural ride-posture pitch range more than the
    # gate did. Head-down picks (dual_3) need a different signal (eye
    # visibility / gaze), not a pitch prior.
    # E004: calm = neutral emotion AND low AU energy (표정 억제의 직접 측정).
    calm = np.nan_to_num(neutral, nan=0.5) * (1.0 - 0.5 * np.nan_to_num(au_energy, nan=0.0))
    blur, expo = col("face_blur"), col("face_exposure")
    pen = col("clipped_ratio") + col("crushed_ratio")
    q = (blur - np.nanmin(blur)) / (np.nanmax(blur) - np.nanmin(blur) + 1e-9) \
        - 2.0 * np.abs(expo - 0.45) - 3.0 * pen
    q01 = (q - np.nanmin(q)) / (np.nanmax(q) - np.nanmin(q) + 1e-9)
    likeness = g * (0.3 + 0.7 * calm) * (0.2 + 0.8 * q01) \
        * (0.4 + 0.6 * em_conf) * np.where(is_ride, 1.0, 1.15)

    # ── portrait (E008): 대표 사진 — 미학 v0, 포즈 prior 없음 ───────────────
    # E005 교훈 + 사용자 지시(앵글샷·사이드샷도 portrait): 포즈는 품질 축이
    # 아니라 스타일 축. 눈뜸(blendshape)·대표성(정준 center 거리)은 관측이
    # 없으면 중립 — 메시 없는 사이드샷에 벌점을 주지 않는다.
    blink = np.full(len(fx), np.nan)
    smile = np.full(len(fx), np.nan)
    d_center = np.full(len(fx), np.nan)
    try:
        from momentscan.perception.readings.geometry import canonicalize
        from momentscan.infra.store.stash import read_appearance, read_landmarks
        from momentscan_features_specialist45d.specialists import BLENDSHAPE_ORDER

        lmdf = read_landmarks(out_root, clip_id).filter(
            pl.col("track_id") == track_id).sort("frame_idx")
        if len(lmdf) and lmdf["blendshapes"][0] is not None:
            lfx = lmdf["frame_idx"].to_numpy()
            pos = {int(f): i for i, f in enumerate(fx)}
            B = np.array(lmdf["blendshapes"].to_list(), dtype=np.float64)
            bi = [BLENDSHAPE_ORDER.index("eyeBlinkLeft"),
                  BLENDSHAPE_ORDER.index("eyeBlinkRight")]
            bl = B[:, bi].mean(axis=1)
            si = [BLENDSHAPE_ORDER.index("mouthSmileLeft"),
                  BLENDSHAPE_ORDER.index("mouthSmileRight")]
            sm = B[:, si].mean(axis=1)
            ref = read_appearance(out_root, clip_id) or {}
            ctr = ((ref.get("riders") or {}).get(str(track_id)) or {}).get("center")
            dd = None
            if ctr is not None:
                P = np.array(lmdf["landmarks"].to_list(), dtype=np.float64).reshape(len(lfx), 478, 3)
                T = np.array(lmdf["transform"].to_list(), dtype=np.float64).reshape(len(lfx), 4, 4)
                cbx = np.array(lmdf["crop_box"].to_list(), dtype=np.float64)
                canon, _ = canonicalize(P, T, cbx)
                c = np.asarray(ctr, dtype=np.float64).reshape(478, 3)
                dd = np.sqrt(((canon - c) ** 2).sum(axis=2).mean(axis=1))
            for j, f in enumerate(lfx):
                i = pos.get(int(f))
                if i is not None:
                    blink[i] = bl[j]
                    smile[i] = sm[j]
                    if dd is not None:
                        d_center[i] = dd[j]
    except Exception:
        pass  # older stash without landmark track — portrait stays quality-led

    lr, tb = col_opt("face_light_lr"), col_opt("face_light_tb")
    harsh = col_opt("face_light_harsh")
    eyes = np.where(np.isfinite(blink), 1.0 - 0.6 * blink, 0.75)
    # E009a: 미소 = smile blendshape과 valence의 50:50 블렌드. 전량 교체는
    # ablation에서 기각 — smile 단일 신호는 vs-random 0.760이지만
    # rank-adjacent 0.579로 약함(진단 0.679는 쌍 유형 혼입). 블렌드가
    # 미세 랭킹 최고(0.600); 메시 없는 프레임은 valence만.
    _pv = _norm01(np.clip(np.nan_to_num(valence, nan=0.0), 0.0, None))  # pleasant = positive only
    _ps = _norm01(smile)
    pleasant = 0.5 + 0.5 * np.where(np.isfinite(_ps), 0.5 * _ps + 0.5 * _pv, _pv)
    rep = np.where(np.isfinite(d_center),
                   np.exp(-(d_center / (2.0 * (np.nanmedian(d_center) if
                            np.isfinite(d_center).any() else 1.0) + 1e-9)) ** 2), 1.0)
    # E009a: 조명 prior 역전 — 사람은 방향광(입체감) 선호. lr 단일 신호가
    # rank-adjacent 0.680으로 최강 미세 랭킹 축이라 완만한 가산으로; v0의
    # 평탄광 선호 벌점은 역방향이라 폐기. harsh는 미세 랭킹 0.520(동전)이라
    # 항 자체를 제거(가산도 벌점도 무영향 확인). 역광(tb) 벌점만 유지.
    light = (1.0 + 0.2 * _norm01(np.abs(np.nan_to_num(lr, nan=0.0)))) \
        * (1.0 - 0.25 * np.clip(np.abs(np.nan_to_num(tb, nan=0.0)) - 0.45, 0, 0.5) / 0.5)
    # E009b: DPR SH ambient 가산 — 사람이 좋아하는 1차 조명 신호는 "얼굴이
    # 충분히 밝게 받는가" (rank-adj 0.720, vs-random 0.714 — 유형 일관 유일
    # 신호). 픽셀 lr 가산과 상보적(ablation: 어느 쪽을 빼도 하락). 상광(z+)
    # 벌점·방향 강도는 ablation 기각 — cross에서만 강해 미세 랭킹을 해침.
    amb = col_opt("face_sh_0")
    light = light * (1.0 + 0.2 * _norm01(np.nan_to_num(amb, nan=0.0)))
    portrait = (0.2 + 0.8 * q01) * eyes * pleasant * (0.4 + 0.6 * em_conf) \
        * light * rep * np.nan_to_num(det, nan=0.0)

    return {"fx": fx, "ts": ts, "likeness": likeness, "highlight": highlight,
            "rarity": rarity, "when": when, "rank_sig": rank_sig, "scene": scene,
            "statevec": Xn, "valence": valence_signed, "arousal": _emo["arousal"],
            "impact": impact, "which": which, "is_ride": is_ride,
            "portrait": portrait, "yaw": yaw,
            # term breakdowns — the viz cards show WHY, not just the composite
            "impact_terms": {"d_expr": _zp(d_expr), "d_pose": _zp(d_pose),
                             "d_light": _zp(d_light), "vel": _zp(vel)},
            "portrait_terms": {"quality": 0.2 + 0.8 * q01, "eyes": eyes,
                               "smile": pleasant, "em_conf": 0.4 + 0.6 * em_conf,
                               "light": light, "rep": rep,
                               "det": np.nan_to_num(det, nan=0.0)}}


def select_clip(out_root, clip_id: str, *, feature_track: str = "A", fps: int = 6, top_k: int = TOP_K) -> dict:
    t0 = time.perf_counter()
    tubes = read_tubelets(out_root, clip_id)
    cpath = candidates_path(Path(out_root), clip_id)
    if cpath.exists():
        cpath.unlink()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    summary: dict = {"clip_id": clip_id, "riders": {}}
    for tid in sorted(tubes["track_id"].unique().to_list()):
        role = tubes.filter(pl.col("track_id") == tid)["rider_role"][0]
        s = frame_scores(out_root, clip_id, tid, fps=fps)
        fx, ts = s["fx"], s["ts"]

        # likeness candidates — min 2s separation (E001: adjacent dups → ties)
        order = np.argsort(-np.nan_to_num(s["likeness"], nan=-1e9))
        picks: list[int] = []
        for i in order:
            if len(picks) >= top_k:
                break
            if all(abs(int(fx[i]) - int(fx[p])) >= 2 * fps for p in picks):
                picks.append(i)
        prof = [{"frame_idx": int(fx[i]), "timestamp_ms": int(ts[int(fx[i])]),
                 "score": round(float(s["likeness"][i]), 4)} for i in picks]
        append_candidate(Path(out_root), clip_id, CandidateLog(
            clip_id=clip_id, track_id=tid, rider_role=role, product="likeness",
            track=feature_track, pick=prof[0], alternatives=prof[1:], timestamp=now,
            scores={"policy": 2.0}))

        # portrait moved out — the redefined product (synthetic-criterion gate
        # → projection → crop-track extraction) lives in portrait.py, keyed off
        # landmarks not frame_scores. highlight moved out too (highlight.py).
        summary["riders"][str(tid)] = {"role": role, "likeness_top": prof[0]}

    # highlight 합동 추출은 highlight.py로 졸업 (2026-07-03) — candidates.jsonl은
    # 이제 likeness 로그만 담는다 (한 파일 한 스테이지 소유).
    summary["candidates_path"] = str(cpath)
    summary["elapsed_s"] = round(time.perf_counter() - t0, 3)
    summary["ok"] = cpath.is_file()
    write_select(Path(out_root), clip_id, summary)   # the stage's own record + resume probe
    log.info("select.done", extra=summary)
    return summary

"""Emotion — the shared, person-relative emotion READING (STEP 0: the valence spine).

The portrait engine + gates were emotionally illiterate: they read MediaPipe's
geometric "smile" blendshape, which scores an open-mouth JOYFUL LAUGH as ~0.01
(it only measures closed-mouth lip-corner pull). The dedicated HSEmotion model
scores the SAME frames em_happy≈0.98. Rich emotion IS computed in features.parquet
(HSEmotion em_* + LibreFace au*) but was siloed to select.py (highlight) only.

This module is the ONE place that turns the multi-model emotion zoo into the
canonical per-frame reading every product will share. STEP 0 ships only the SPINE:

  fused_valence(M, INDEX) -> {valence_signed, em_conf, arousal}   (per frame)

Design (from the emotion-first-class-reading synthesis, data-verified on dual_3):
- ANCHOR on HSEmotion em_* (8 softmax probs, ALWAYS finite — survives the head-back
  squint where landmark/AU/MediaPipe signals go NaN). valence_signed is a fixed
  signed projection in em-space, so a laugh is +large and a freeze is -large;
  corr(valence_signed, em_happy)=0.982 on dual_3 (the signal that makes the laugh win).
- TRUST PRECEDENCE, never naive average: em_* sets the valence DIRECTION + magnitude;
  LibreFace au* contribute ONLY as arousal/agreement EVIDENCE where finite (per-channel
  NaN-skip), never into the valence direction (a joint em+au subspace was verified to
  rank grimaces over joy — corr(Mahalanobis, em_happy)=-0.34). MediaPipe geometric
  smile/jaw is demoted to nothing here — it is the literal source of the bug.
- DESCRIPTIVE only. valence_signed says what the face SHOWS; whether a moment is
  DESIRABLE is a context-conditioned policy over this reading (a tense face = engaged
  concentration vs frustration by ride phase/segment), decided downstream, not here.

STEP 0 proved the signal wire-free; the stage NOW persists the per-person baseline
(emotion.json, inspector-only so far) + the per-frame observability trace
(emotion_frame.parquet), and select.py/portrait consume fused_valence directly
(one definition). The identity-gate cohort fix and the full select-silo dissolve
remain STEP 2-3.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

# HSEmotion 8-category softmax. valence_signed = sum(POS) - sum(NEG); the UNSIGNED
# categories carry no valence sign. em_conf = the dominant category's probability.
# em_surprise is UNSIGNED (not positive): verified bivalent — across frames with
# surprise>0.2 the companion is happy 56% / fear 44%, so no fixed sign is correct,
# and em_conf cannot guard it (strong isolated surprise is high-confidence yet
# facially indistinguishable from a fear-gasp at a ride drop). It routes to arousal
# instead. fear stays in NEG, so genuine scary frames (surprise AND fear) still sign
# negative; only the unguarded pure-surprise hole closes.
EM_POS = ("em_happy",)
EM_NEG = ("em_sad", "em_angry", "em_fear", "em_disgust", "em_contempt")
EM_UNSIGNED = ("em_neutral", "em_surprise")
EM_ALL = (*EM_POS, *EM_UNSIGNED, *EM_NEG)

# LibreFace FACS action units (DISFA) — arousal/agreement EVIDENCE only, sometimes-NaN.
AU_FIELDS = (
    "au1_inner_brow", "au2_outer_brow", "au4_brow_lowerer", "au5_upper_lid",
    "au6_cheek_raiser", "au9_nose_wrinkler", "au12_lip_corner", "au15_lip_depressor",
    "au17_chin_raiser", "au20_lip_stretcher", "au25_lips_part", "au26_jaw_drop",
)


def fused_valence(M: np.ndarray, index: dict) -> dict:
    """Multi-model emotion → per-frame (valence_signed, em_conf, arousal).

    M: (N, D) feature matrix; index: name → column (registry INDEX). Returns numpy
    arrays of length N. valence_signed/em_conf are anchored on the always-finite
    em_* (so they are finite on every frame a face was detected); arousal falls back
    em-energy → wild_intensity → 0 with per-channel NaN-skip.
    """
    n = M.shape[0]

    def col(name):
        return M[:, index[name]] if name in index else np.full(n, np.nan)

    em = np.stack([col(e) for e in EM_ALL])           # (8, N) softmax probs
    em_finite = np.isfinite(em).any(axis=0)
    pos = np.nansum(np.stack([col(e) for e in EM_POS]), axis=0)
    neg = np.nansum(np.stack([col(e) for e in EM_NEG]), axis=0)
    valence_signed = np.where(em_finite, pos - neg, np.nan)   # [-1, 1]
    em_conf = np.where(em_finite, np.nanmax(em, axis=0), np.nan)  # dominant-category prob

    # arousal — the unsigned activation: max of AU energy / em_surprise / wild_intensity
    # where finite. em_surprise lands HERE (not in valence): it is high-arousal but
    # bivalent. Always finite (em_surprise is), so arousal never NaNs. (Open-mouth
    # high-energy cheers that HSEmotion mislabels surprise still register their energy.)
    au = np.stack([col(f) for f in AU_FIELDS])        # (12, N), sometimes NaN
    au_any = np.isfinite(au).any(axis=0)
    au_e = np.where(au_any, np.nanmean(np.where(np.isfinite(au), au, np.nan), axis=0), np.nan)
    cand = np.stack([au_e, col("em_surprise"), col("wild_intensity")])
    arousal = np.where(np.isfinite(cand).any(axis=0), np.nanmax(cand, axis=0), 0.0)

    return {"valence_signed": valence_signed, "em_conf": em_conf, "arousal": arousal}


def valence_timeline(out_root, clip_id: str, track_id: int | None = None):
    """Convenience loader: read features.parquet → per-frame valence reading. Returns
    (frame_idx[np], reading_dict, track_id[np])."""
    import polars as pl

    from momentscan.infra.store.stash import read_features
    from momentscan_features_specialist45d.registry import INDEX

    f = read_features(out_root, clip_id, "A")
    if track_id is not None:
        f = f.filter(pl.col("track_id") == track_id)
    f = f.sort(["track_id", "frame_idx"])
    M = np.array(f["feature"].to_list(), float)
    reading = fused_valence(M, INDEX)
    return f["frame_idx"].to_numpy(), reading, f["track_id"].to_numpy()


# the 8 HSEmotion categories (bare names) for the dominant-category style read —
# DERIVED from EM_ALL (single 8-category home; argmax maps back through the same
# tuple, so the order is self-consistent by construction).
EM8 = tuple(e.removeprefix("em_") for e in EM_ALL)
N_MIN = 30        # cold-start: need this many ride frames for a person-relative baseline
RANGE_EPS = 0.05  # ...and a non-degenerate valence spread


def compute_baseline(valence, em_conf, arousal, dom_em, is_ride) -> dict:
    """Per-person RIDE-conditioned emotion baseline — the 'do not trust the classifier
    100%' surface: a frame is bright/low FOR THIS PERSON relative to these quantiles,
    not by an absolute em_happy threshold. Conditioned on the ride phase (falls back
    to all frames if too few ride frames). Carries the person's expressive RANGE,
    a person-relative coverage histogram, and which emotion dominates their high vs
    low tails (the style that makes the resting-grumpy person ≠ the always-bright one)."""
    from collections import Counter

    v = np.asarray(valence, float)
    m = np.asarray(is_ride, bool) & np.isfinite(v)
    n_ride = int(m.sum())
    use = m if n_ride >= N_MIN else np.isfinite(v)   # cold-start fallback to all frames
    vv = v[use]
    if vv.size == 0:
        return {"em_baseline_ok": False, "n_ride": n_ride, "n_used": 0, "reason": "no finite valence"}
    a = np.asarray(arousal, float)[use]
    de = np.asarray(dom_em)[use]
    p10, p25, p50, p75, p90 = (round(float(x), 3) for x in np.percentile(vv, [10, 25, 50, 75, 90]))
    rng = round(p90 - p10, 3)
    a75 = float(np.nanpercentile(a, 75)) if np.isfinite(a).any() else 1.0
    # coverage is ABSOLUTE (genuinely positive/negative), NOT person-relative quartiles —
    # an extreme-frown rider's top quartile is still a frown, so "bright = top quartile"
    # would lie. Person-relativity lives in the percentiles above; coverage answers "is
    # this person EVER genuinely happy/upset" (the blend of the two is open point #1).
    cov = {"pos": int((vv > 0.2).sum()), "strong_pos": int((vv > 0.6).sum()),
           "neg": int((vv < -0.2).sum()), "strong_neg": int((vv < -0.6).sum()),
           "intense": int((a >= a75).sum())}
    # style = which emotion dominates the person's OWN high vs low tails (person-relative):
    # the resting-contempt rider reads style_low=contempt even when never truly upset.
    style_high = [c for c, _ in Counter(de[vv >= p75]).most_common(2)]
    style_low = [c for c, _ in Counter(de[vv <= p25]).most_common(2)]
    # cold-start gate: enough ride frames AND a non-degenerate spread, else the
    # person-relative reading is untrustworthy (downstream falls back / abstains).
    em_baseline_ok = bool(n_ride >= N_MIN and rng > RANGE_EPS)
    return {"p10": p10, "p25": p25, "p50": p50, "p75": p75, "p90": p90, "range": rng,
            "coverage": cov, "style_high": style_high, "style_low": style_low,
            "em_baseline_ok": em_baseline_ok, "ride_conditioned": bool(n_ride >= N_MIN),
            "n_ride": n_ride, "n_used": int(use.sum())}


def extract_emotion(out_root, clip_id: str, *, fps: int = 6) -> dict:
    """Stage runner → emotion.json: the per-person RIDE-conditioned valence baseline
    for every subject. Per-frame valence stays a pure function of features (derive via
    fused_valence / `reading`); only the aggregate baseline is persisted (measure-once,
    no redundant per-frame store, nothing to drift vs the function)."""
    import time

    import polars as pl

    from momentscan.infra.store.stash import (
        clip_dir, read_features, read_tubelets, write_emotion, write_emotion_frame,
    )
    from momentscan_features_specialist45d.registry import INDEX

    t0 = time.perf_counter()
    cdir = clip_dir(Path(out_root), clip_id)
    feats = read_features(out_root, clip_id, "A")
    if feats is None or len(feats) == 0:
        return {"clip_id": clip_id, "ok": False, "reason": "no features (run `features` first)"}
    tub = read_tubelets(out_root, clip_id)
    ride = {(r["track_id"], r["frame_idx"]): (r.get("scene_phase") == "ride")
            for r in tub.iter_rows(named=True)}
    emcols = [INDEX[f"em_{e}"] for e in EM8]

    summary = {"clip_id": clip_id, "ok": True, "riders": {}}
    frame_rows: list[dict] = []
    for sid in sorted(feats["track_id"].unique().to_list()):
        f = feats.filter(pl.col("track_id") == sid).sort("frame_idx")
        fx = f["frame_idx"].to_numpy()
        M = np.array(f["feature"].to_list(), float)
        r = fused_valence(M, INDEX)
        dom = [EM8[j] for j in np.argmax(M[:, emcols], axis=1)]
        is_ride = np.array([ride.get((sid, int(ff)), False) for ff in fx])
        summary["riders"][str(sid)] = {
            "n_frames": int(len(fx)),
            "baseline": compute_baseline(r["valence_signed"], r["em_conf"], r["arousal"], dom, is_ride),
        }
        # persist the per-frame series too (the inspector used to RE-COMPUTE this);
        # emotion.json keeps only the baseline. The reading stays a pure fn of features.
        for k in range(len(fx)):
            frame_rows.append({"track_id": int(sid), "frame_idx": int(fx[k]),
                               "valence": float(r["valence_signed"][k]), "em_conf": float(r["em_conf"][k]),
                               "arousal": float(r["arousal"][k])})
    write_emotion(out_root, clip_id, summary)
    if frame_rows:
        write_emotion_frame(out_root, clip_id, frame_rows)
    summary["emotion"] = str(cdir / "emotion.json")
    summary["ms"] = int((time.perf_counter() - t0) * 1000)
    return summary


def reading(out_root, clip_id: str, track_id: int):
    """Consumer entry point — the per-frame valence timeline (derived) PLUS the
    person baseline (from emotion.json) for one subject, so a product reads emotion
    in ONE call. Returns (frame_idx, reading_dict, baseline_dict). state_anomaly is
    derived here (|valence - p50|) — not persisted."""
    from momentscan.infra.store.stash import read_emotion

    fx, r, _ = valence_timeline(out_root, clip_id, track_id=track_id)
    em = read_emotion(out_root, clip_id) or {}
    base = (em.get("riders", {}).get(str(track_id), {}) or {}).get("baseline", {})
    p50 = base.get("p50", 0.0)
    r = dict(r)
    r["state_anomaly"] = np.abs(r["valence_signed"] - p50)
    return fx, r, base

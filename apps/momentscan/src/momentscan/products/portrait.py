"""Portrait selection — the redefined product (products.md "portrait"): a
synthetic admissibility criterion authored in canonical coords (blendshape +
pose), projected onto the real frames, then the actual picture extracted via the
clean crop track (the uniform container). It does NOT rank the aesthetic 0-axis:
the representative is chosen by an OBJECTIVE tiebreak among admissible survivors,
and the diversity set is view coverage — never an aesthetic score.

Method diverges from select.py's frame_scores (deprecated multiplicative model):
this reads landmarks.parquet (blendshape + pose) directly, so it runs WITHOUT the
67D features stage. Lighting (입체감 floor) is an optional gate when features exist.

  gate (default query)  eyes-open · frontal · mouth-ok · sharp
  rep 1장               objective tiebreak (frontality + sharpness + eye-open)
  diversity set         best-objective per view bin (frontal/left/right/side)
  extract               crop-track frame → portraits/*.png (the deliverable)

Layout: <out>/<clip>/portraits/{s{sid}_rep.png, s{sid}_set_{view}.png, portrait.json}
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import polars as pl

from momentscan import gates
from momentscan.domains import signals
from momentscan.domains.emotion import EM_ALL as EM, fused_valence
from momentscan.gates import BLINK_MAX
from momentscan.domains.pose import FRONTAL_DEG, POSE_MAX_DEG, SIDE_DEG, euler_from_transform, fuse_pose
from momentscan.stash import (
    append_candidate, candidates_path, clip_dir, read_candidates,
    read_features, read_headpose, read_landmarks, read_parse, read_tubelets,
    write_gate_trace, write_portrait,
)
from momentscan.telemetry import CandidateLog

log = logging.getLogger("momentscan.portrait")

# the 8 HSEmotion categories — single home emotion.EM_ALL (imported as EM above);
# both consumers are order-independent (em_conf by name, vel = Σ|Δsoftmax|).

# The admissibility GATES (Tier 0–3) now live in gates.py as a declared ladder;
# this engine builds the per-frame SIGNALS, calls gates.evaluate, then does the
# product work over the verdicts (rep tiebreak + diversity-set view bins + crop
# extraction). Constants imported above are the few thresholds this engine reuses
# in the objective tiebreak / view binning — BLINK_MAX from gates, pose thresholds
# (POSE_MAX_DEG, FRONTAL_DEG, SIDE_DEG) from pose.py: same single source as the
# gates/quantizer.
#
# occlusion (parse.parquet): eye region darker than skin → sunglasses (clear
# glasses ≈ skin); mouth region absent → mask. Preset policy, calibrated on cap_1.
EYE_LUM_MIN, MOUTH_VIS_MIN = 0.7, 0.01
# a portrait needs a minimum of genuinely-admissible evidence — an always-occluded
# subject should get NO portrait, not one from a few noise-leaked frames.
MIN_ADMIT = 5
ID_MIN_CENTROID = 10   # a subject needs ≥ this many admit frames for a trustworthy ArcFace
                       # centroid (the nearest-subject id_valid anchor); fewer → no rescue/rival


def _n01(x, lo, hi):
    return float(np.clip((x - lo) / (hi - lo + 1e-9), 0, 1))


def _emo_align(ed, fx):
    """Align a subject's emotion to its tubelet frames → (em_conf, vel). em_conf = HSEmotion
    dominant-category prob (the expr_ok gate + the obj anti-ambiguity tiebreak); vel = L1
    Δsoftmax between time-contiguous frames (obj anti-transition tiebreak). NaN where features
    are absent / frame-gap → gate passes, factor 1.0 = no penalty."""
    N = len(fx)
    em_conf = np.full(N, np.nan); vel = np.full(N, np.nan)
    if ed is None:
        return em_conf, vel
    posf = {int(f): i for i, f in enumerate(ed["fx"])}; pmo = ed["emo"]
    for k, f in enumerate(fx):
        i = posf.get(int(f))
        if i is None:
            continue
        em_conf[k] = ed["conf"][i]
        j = posf.get(int(fx[k - 1])) if k > 0 and fx[k] - fx[k - 1] == 1 else None
        if j is not None and np.isfinite(pmo[i]).all() and np.isfinite(pmo[j]).all():
            vel[k] = float(np.abs(pmo[i] - pmo[j]).sum())
    return em_conf, vel


def select_portrait(out_root, clip_id: str, *, fps: int = 6) -> dict:
    """Gate → survivors → rep + diversity set → extract crops. Returns summary."""
    t0 = time.perf_counter()
    cdir = clip_dir(Path(out_root), clip_id)
    tub = read_tubelets(out_root, clip_id).sort(["track_id", "frame_idx"])
    lm = read_landmarks(out_root, clip_id)
    lm_bs = {(r["track_id"], r["frame_idx"]): np.array(r["blendshapes"], float)
             for r in lm.iter_rows(named=True) if r["blendshapes"] is not None}
    lm_tf = {(r["track_id"], r["frame_idx"]): np.array(r["transform"], float).reshape(4, 4)
             for r in lm.iter_rows(named=True) if r["transform"] is not None}

    # crop track (clean container) — blur source + extraction. None → degrade.
    crops_dir = cdir / "crops"
    manifest = None
    if (crops_dir / "manifest.json").exists():
        manifest = json.loads((crops_dir / "manifest.json").read_text(encoding="utf-8"))
    crop_index = {s["subject_id"]: {f: i for i, f in enumerate(s["frames"])}
                  for s in (manifest["subjects"] if manifest else [])}

    # occlusion signal (parse.parquet) — optional; gate skips it if absent.
    occ = {}
    pq = read_parse(out_root, clip_id)
    if pq is not None:
        occ = {(r["track_id"], r["frame_idx"]): (r["eye_lum_rel"], r["mouth_vis"], r["eyes_vis"],
                                                 r.get("skin_entropy"), r.get("skin_frac"))
               for r in pq.iter_rows(named=True)}   # .get: tolerate parse.parquet predating skin_entropy

    # full-range pose (6DRepNet) — fills MediaPipe's profile NaN so SIDE faces get
    # a real yaw (adapter already sign-aligned). Optional; absent → frontal-only.
    hp = {}
    hq = read_headpose(out_root, clip_id)
    if hq is not None:
        hp = {(r["track_id"], r["frame_idx"]): (r["yaw"], r["pitch"], r["roll"])
              for r in hq.iter_rows(named=True)}

    # EMOTION for the rep-pick tiebreak (the SAME em_conf select.py uses, via fused_valence)
    # — ambiguous softmax (mid-transition / unposed) is down-ranked among admit frames; the
    # gate is untouched. read_features RAISES when the features stage didn't run (unlike
    # read_parse/headpose → None), so guard: no features → empty map → obj is byte-identical.
    emo_by_sid: dict = {}
    try:
        from momentscan_features_specialist45d.registry import INDEX
        ff = read_features(out_root, clip_id, "A")
        emi = [INDEX[e] for e in EM]
        for s in ff["track_id"].unique().to_list():
            fs = ff.filter(pl.col("track_id") == s).sort("frame_idx")
            Ms = np.array(fs["feature"].to_list(), float)
            emo_by_sid[int(s)] = {"fx": fs["frame_idx"].to_numpy(),
                                  "conf": fused_valence(Ms, INDEX)["em_conf"],
                                  "emo": Ms[:, emi]}
    except Exception:
        emo_by_sid = {}   # no features stage → obj == front+sharp+eyes (unchanged)

    pdir = cdir / "portraits"
    pdir.mkdir(parents=True, exist_ok=True)
    for old in pdir.glob("*.png"):
        old.unlink()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # idempotent: drop our own products from candidates.jsonl, then re-append
    # (select.py clears the file for likeness/highlight; we own portrait*).
    cpath = candidates_path(Path(out_root), clip_id)
    if cpath.exists():
        kept = [c for c in read_candidates(Path(out_root), clip_id)
                if c.get("product") not in ("portrait", "portrait_set")]
        with cpath.open("w", encoding="utf-8") as fh:
            for c in kept:
                fh.write(json.dumps(c, ensure_ascii=False) + "\n")

    def crop_reader(sid):
        f = crops_dir / f"s{sid}.mp4"
        return cv2.VideoCapture(str(f)) if (manifest and f.exists()) else None

    def crop_frame(cap, sid, frame_idx):
        idx = crop_index.get(sid, {}).get(frame_idx)
        if cap is None or idx is None:
            return None
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, img = cap.read()
        return img if ok else None

    summary = {"clip_id": clip_id, "ok": True, "riders": {}}
    all_portraits = []
    trace_rows = []   # gate_trace.parquet — every per-frame gate verdict as data

    # PASS 1 — assemble each subject's per-frame signals and the PROVISIONAL admit cohort
    # with cos_self/cos_other = NaN. id_valid then ≡ id_ok (the cos rescue floors all fail),
    # and admit = frontal_pose & valid reads valid via have_bs (frontal ⟹ have_bs), so the
    # admit set is FINAL here — independent of the cos signals it will go on to seed. Those
    # admit frames are the clean cohort each subject's ArcFace centroid is built from.
    ctxs = []
    for sid in sorted(tub["track_id"].unique().to_list()):
        df = tub.filter(pl.col("track_id") == sid).sort("frame_idx")
        fx = df["frame_idx"].to_numpy()
        role = df["rider_role"][0]
        ts = {r["frame_idx"]: r["timestamp_ms"] for r in df.iter_rows(named=True)}
        emb = np.array(df["embedding"].to_list(), float)   # ArcFace — occlusion guard
        cap = crop_reader(sid)

        N = len(fx)
        blink = np.full(N, np.nan); jaw = blink.copy(); smile = blink.copy()
        yaw = blink.copy(); pit = blink.copy(); rol = blink.copy(); blur = blink.copy()
        yaw6 = blink.copy(); pit6 = blink.copy(); rol6 = blink.copy()
        for k, f in enumerate(fx):
            b = lm_bs.get((sid, int(f))); M = lm_tf.get((sid, int(f)))
            if b is not None:
                blink[k] = signals.blink(b); jaw[k] = signals.jaw(b); smile[k] = signals.smile(b)
            if M is not None:
                yaw[k], pit[k], rol[k] = euler_from_transform(M)
            h = hp.get((sid, int(f)))
            if h is not None:
                yaw6[k], pit6[k], rol6[k] = h
            img = crop_frame(cap, sid, int(f))
            if img is not None:
                blur[k] = signals.crop_blur(img)

        # fused pose + 6D-rescue mask — single home pose.fuse_pose (MediaPipe
        # where it fit, 6DRepNet where it didn't).
        yaw_f, pit_f, rol_f, pose_6d = fuse_pose(yaw, pit, rol, yaw6, pit6, rol6)

        # FASHION items from parse — sunglasses (dark eye region) / mask (no
        # mouth). These are worn items: part of the person that day, NOT an
        # occlusion to reject. They stay admissible (recorded on likeness); the
        # only effect on the gate is to skip the eyes-open check under sunglasses
        # (the eyes can't be seen). Accidental occlusion (hand/hair) is a separate
        # signal — not yet wired (TODO).
        sunglasses = np.zeros(N, bool); masked = np.zeros(N, bool)
        face_present = np.ones(N, bool)   # parse found SOME facial structure (eyes|mouth>0)
        skin_entropy = np.full(N, np.nan); skin_frac = np.full(N, np.nan)   # exposure-gate signals
        if occ:
            for k, f in enumerate(fx):
                v = occ.get((sid, int(f)))
                if v is None:
                    continue
                eye_rel, mouth_vis, eyes_vis, s_ent, s_frac = v
                if eye_rel is not None and eye_rel < EYE_LUM_MIN:
                    sunglasses[k] = True
                if mouth_vis is not None and mouth_vis < MOUTH_VIS_MIN:
                    masked[k] = True
                face_present[k] = bool((eyes_vis or 0) > 0 or (mouth_vis or 0) > 0)
                if s_ent is not None:
                    skin_entropy[k] = s_ent
                if s_frac is not None:
                    skin_frac[k] = s_frac

        # SIGNALS → GATES. The admissibility decision is the declared ladder in
        # gates.py (T0 validity · T1 quality · T2 routing · T3 query); this engine
        # only assembles the per-frame signals and reads back the verdicts — no gate
        # logic lives here anymore. iddev is a measurement (the gate's `clean_ref`
        # Reference summarises it); sunglasses/masked/face_present came from parse.
        iddev = signals.identity_deviation(emb)
        em_conf, vel = _emo_align(emo_by_sid.get(int(sid)), fx)   # em_conf gates expr_ok (PASS 1)
        _nan = np.full(N, np.nan)
        sig = {"fx": fx, "blink": blink, "smile": smile, "jaw": jaw, "blur": blur, "iddev": iddev,
               "yaw_f": yaw_f, "pit_f": pit_f, "rol_f": rol_f, "pose_6d": pose_6d,
               "mp_yaw_raw": yaw, "sixd_yaw_raw": yaw6,   # raw backends → gates' pose_class
               "cos_self": _nan, "cos_other": _nan.copy(),   # filled in PASS 2 (cross-subject)
               "em_conf": em_conf,                           # → expr_ok (coherent-expression gate)
               "sunglasses": sunglasses, "masked": masked, "face_present": face_present,
               "skin_entropy": skin_entropy, "skin_frac": skin_frac}
        admit1 = gates.evaluate(sig)["admit"]
        ctxs.append({"sid": sid, "fx": fx, "role": role, "ts": ts, "emb": emb, "cap": cap,
                     "N": N, "blink": blink, "yaw": yaw, "yaw_f": yaw_f, "pit_f": pit_f,
                     "rol_f": rol_f, "blur": blur, "pose_6d": pose_6d,
                     "sig": sig, "admit1": admit1, "em_conf": em_conf, "vel": vel})

    # CENTROIDS — each subject's clean ArcFace anchor = L2-normalised mean of its admit-frame
    # (L2-normalised) embeddings. < ID_MIN_CENTROID admits → no centroid (no rescue, no rival).
    cents = {}
    for c in ctxs:
        a = c["admit1"]
        if int(a.sum()) >= ID_MIN_CENTROID:
            e = c["emb"][a]
            e = e / (np.linalg.norm(e, axis=1, keepdims=True) + 1e-9)
            m = e.mean(0); cents[c["sid"]] = m / (np.linalg.norm(m) + 1e-9)

    # PASS 2 — cos_self / cos_other → final gate verdicts (id_valid re-admits peak/profile
    # frames id_ok over-filtered) → portrait selection. evaluate() is pure/cheap; re-running
    # it keeps the admit cohort gate-owned rather than re-deriving the decision here.
    for c in ctxs:
        sid, fx, role, ts = c["sid"], c["fx"], c["role"], c["ts"]
        emb, cap, N = c["emb"], c["cap"], c["N"]
        blink, yaw, yaw_f = c["blink"], c["yaw"], c["yaw_f"]
        pit_f, rol_f, blur = c["pit_f"], c["rol_f"], c["blur"]
        pose_6d, sig = c["pose_6d"], c["sig"]   # raw sunglasses/masked ride in sig; verdicts come judged from gv
        em_conf, vel = c["em_conf"], c["vel"]   # computed in PASS 1 (em_conf also gates expr_ok)
        en = emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9)
        own = cents.get(sid)
        cos_self = en @ own if own is not None else np.full(N, np.nan)
        others = [v for s2, v in cents.items() if s2 != sid]
        cos_other = np.max([en @ v for v in others], axis=0) if others else np.full(N, np.nan)
        sig["cos_self"], sig["cos_other"] = cos_self, cos_other
        gv = gates.evaluate(sig)
        admit, quarter_ok, side_ok = gv["admit"], gv["quarter_ok"], gv["side_ok"]
        n_admit = int(admit.sum())
        # judgeability-derived verdicts (gv, not the raw parse booleans) — off-frontal
        # frames abstain, so a profile ride no longer reads as "wore a mask".
        fashion = {"sunglasses": round(float(gv["sunglasses"].mean()), 3) if N else 0.0,
                   "mask": round(float(gv["masked"].mean()), 3) if N else 0.0}
        # gate_trace.parquet rows — the gate's own self-record (the inspector renders
        # it instead of re-deciding). Schema owned by gates.py; written after the loop.
        trace_rows += gates.trace_rows(sid, fx, sig, gv)

        # 제품 스코프 (user 2026-07-07): portrait은 **주탑승자만** — aux는 얼굴이 작고
        # 상시 가림이라 측정 신뢰가 낮다 (P1-② 감사 실증: aux들이 coherence 최저).
        # 게이트 판정·trace는 전원 유지 — 공유 validity를 likeness가 소비하고, aux
        # 센트로이드는 상대귀속(cos_other)의 rival로 필요 (스테이지 의존 ≠ 제품 노출).
        if role != "main":
            continue

        # em_conf (PASS 1) now ALSO gates expr_ok (reject:ambiguous); here it stays the soft
        # anti-ambiguity tiebreak that RANKS the survivors (gate removes the muddled extreme,
        # tiebreak prefers the clearest among the rest — exactly the blink gate+term split).
        # objective tiebreak (NOT the aesthetic 0-axis): frontality + sharpness + eye-open,
        # softly de-rated for emotion ambiguity/instability (tiebreak only — high floors keep
        # it from overriding geometry or smuggling the 0-axis; NaN → 1.0 = exact no-op).
        sharp_hi = float(np.nanmax(blur)) if np.isfinite(blur).any() else 1.0
        # anti-AMBIGUITY tiebreak only — em_conf is a happy/recognizability detector, NOT an
        # energy meter (corr(em_conf,arousal)≈−0.1; it ranks a wild scream below a subtle smile).
        # Do NOT reuse it as expression energy (that's AU-energy/arousal, a HIGHLIGHT axis).
        def conf_fac(e):   # em_conf 1→1.0, .6→1.0(sat), .5→.95, 0→.7 ; floored so calm-neutral survives
            return 1.0 if not np.isfinite(e) else float(np.clip(0.7 + 0.5 * e, 0.0, 1.0))
        def stab_fac(v):   # anti-transition: vel 0→1.0, 1→.7, floor .5
            return 1.0 if not np.isfinite(v) else float(np.clip(1.0 - 0.3 * v, 0.5, 1.0))
        # ③ query-proximity ranking key — per-frame distance of the expression from the
        # authored warm-PFP query (the SAME metric the ② gate thresholds). The rep + each
        # view bin pick the CLOSEST-to-query (warmest) survivor; obj is the geometric
        # tiebreak. No blendshape (profiles) → inf → the side bin falls back to obj.
        qd = gates.query_dist(sig.__getitem__)   # THE ② metric — single home (dim 추가 자동 상속)
        qd = np.where(np.isfinite(qd), qd, np.inf)
        def _obj_terms(k):
            # within-view ranking = geometry (frontality + sharpness) + ③ query WARMTH,
            # balanced so a warm-but-soft frame can't beat a sharp one (sharp term holds) and a
            # sharp frame closer to the warm query wins over a neutral one. `warm` = proximity to
            # the authored query (subsumes eyes-open: blink IS a query dim); profiles have no
            # blendshape (qd=inf) → fall back to the eyes-open term (front≈const, sharpness decides).
            ang = abs(yaw_f[k]) + abs(np.nan_to_num(pit_f[k])) + abs(np.nan_to_num(rol_f[k]))
            front = 1.0 - _n01(ang, 0, 3 * POSE_MAX_DEG)
            sharp = _n01(np.nan_to_num(blur[k], nan=0.0), 0, sharp_hi)
            warm = (1.0 - _n01(qd[k], 0.0, gates.QUERY_DIST_MAX)) if np.isfinite(qd[k]) \
                else 1.0 - _n01(np.nan_to_num(blink[k], nan=0.0), 0, BLINK_MAX)
            return front, sharp, warm

        def _obj_breakdown(k):
            """The rep-selection reasoning made observable: which term carried the objective."""
            front, sharp, warm = _obj_terms(k)
            return {"front": round(float(front), 3), "sharp": round(float(sharp), 3),
                    "warm": round(float(warm), 3),
                    "query_dist": round(float(qd[k]), 3) if np.isfinite(qd[k]) else None,
                    "conf": round(conf_fac(em_conf[k]), 3), "stab": round(stab_fac(vel[k]), 3)}

        def obj(k):
            front, sharp, warm = _obj_terms(k)
            return round((front + sharp + warm) * conf_fac(em_conf[k]) * stab_fac(vel[k]), 4)

        # min-admit guard: too few admissible frames → no portrait (an always-
        # occluded subject must not get one from noise-leaked frames).
        surv = [int(k) for k in np.where(admit)[0]] if n_admit >= MIN_ADMIT else []
        rep_pick = None; alts = []
        if surv:
            surv.sort(key=obj, reverse=True)   # ③ obj now folds in query warmth (front + sharp + warm)
            sep = 2 * fps
            chosen = []
            for k in surv:
                if all(abs(int(fx[k]) - int(fx[c])) >= sep for c in chosen):
                    chosen.append(k)
                if len(chosen) >= 5:
                    break
            def entry(k):
                return {"frame_idx": int(fx[k]), "timestamp_ms": int(ts[int(fx[k])]),
                        "objective": obj(k), "yaw": round(float(yaw[k]), 1),
                        "terms": _obj_breakdown(k)}
            rep_pick, alts = entry(chosen[0]), [entry(k) for k in chosen[1:]]

        # diversity set — view coverage over the FULL fused-pose range (best
        # objective per bin). The profile bin holds genuine side faces (real
        # 6DRepNet yaw, not "MediaPipe gave up") and populates independently of the
        # frontal rep, so a profile-only subject still gets a side portrait — this
        # is what makes side faces queryable as portraits.
        members = []
        bins = (("frontal", admit & (np.abs(yaw_f) < FRONTAL_DEG)),
                ("left",  quarter_ok & (yaw_f <= -FRONTAL_DEG) & (yaw_f > -SIDE_DEG)),
                ("right", quarter_ok & (yaw_f >= FRONTAL_DEG) & (yaw_f < SIDE_DEG)),
                ("side",  side_ok))
        for view, mask in bins:
            cand = list(np.where(mask)[0])
            if cand:
                k = max(cand, key=obj)   # ③ obj folds in query warmth (per-view warmest+sharpest)
                members.append({"frame_idx": int(fx[k]), "timestamp_ms": int(ts[int(fx[k])]),
                                "objective": obj(int(k)), "view": view,
                                "yaw": round(float(yaw_f[k]), 1),
                                "pose_src": "6d" if pose_6d[k] else "mp",
                                "terms": _obj_breakdown(int(k))})

        # extract actual portraits from the crop track (the deliverable)
        extracted = []
        def save(tag, frame_idx):
            img = crop_frame(cap, sid, frame_idx)
            if img is None:
                return None
            p = pdir / f"s{sid}_{tag}.png"
            cv2.imwrite(str(p), img)
            extracted.append(p.name)
            return p.name
        rep_file = save("rep", rep_pick["frame_idx"]) if rep_pick else None
        for m in members:
            m["file"] = save(f"set_{m['view']}", m["frame_idx"])
        if cap is not None:
            cap.release()

        # telemetry (shared CandidateLog contract; product distinguishes)
        if rep_pick:
            append_candidate(Path(out_root), clip_id, CandidateLog(
                clip_id=clip_id, track_id=sid, rider_role=role, product="portrait",
                track="gate", pick=rep_pick, alternatives=alts, timestamp=now,
                scores={"n_admit": float(n_admit), "n_total": float(N)}))
        if members:
            append_candidate(Path(out_root), clip_id, CandidateLog(
                clip_id=clip_id, track_id=sid, rider_role=role, product="portrait_set",
                track="gate", pick=members[0], alternatives=members[1:], timestamp=now,
                scores={"n_views": float(len(members))}))

        summary["riders"][str(sid)] = {
            "role": role, "n_total": N, "n_admit": n_admit,
            "n_side": int(side_ok.sum()), "n_pose_6d": int(pose_6d.sum()),
            "fashion": fashion,
            "rep": rep_pick, "rep_file": rep_file,
            "views": [m["view"] for m in members], "extracted": extracted,
            "set": [{"view": m["view"], "frame_idx": m["frame_idx"], "file": m.get("file")}
                    for m in members],
            "crop_track": manifest is not None, "parse": bool(occ), "headpose": bool(hp),
        }
        all_portraits.extend(extracted)

    write_portrait(out_root, clip_id, summary)
    if trace_rows:
        write_gate_trace(out_root, clip_id, trace_rows)
    summary["portraits_dir"] = str(pdir)
    summary["n_portraits"] = len(all_portraits)
    summary["ms"] = int((time.perf_counter() - t0) * 1000)
    log.info("portrait.done", extra={"clip_id": clip_id, "n_portraits": len(all_portraits),
                                     "crop_track": manifest is not None})
    return summary

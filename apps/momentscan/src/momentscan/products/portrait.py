"""Portrait selection — the redefined product (products.md "portrait"): a
synthetic admissibility criterion authored in canonical coords (blendshape +
pose), projected onto the real frames, then the actual picture extracted via the
clean crop track (the uniform container). It does NOT rank the aesthetic 0-axis:
the representative is chosen by an OBJECTIVE tiebreak among admissible survivors,
and the diversity set is view coverage — never an aesthetic score.

This engine is a pure READER of gate_trace.parquet (R10): the admissibility
decision is the gates STAGE's ladder (gates.evaluate), and portrait consumes the
per-frame verdicts + signals it recorded. No gate logic / signal assembly / ArcFace
centroid lives here — only the product work (rep tiebreak, diversity bins, extraction).

  gate (default query)  admit / quarter / side verdicts read from gate_trace
  rep 1장               objective tiebreak (frontality + sharpness + query warmth)
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

from momentscan.perception.gates import BLINK_MAX, QUERY_DIST_MAX
from momentscan.perception.readings.pose import FRONTAL_DEG, POSE_MAX_DEG, SIDE_DEG
from momentscan.infra.store.stash import (
    append_candidate, candidates_path, clip_dir, headpose_path, parse_path,
    read_candidates, read_gate_trace, read_tubelets, write_portrait,
)
from momentscan.infra.store.telemetry import CandidateLog

log = logging.getLogger("momentscan.portrait")

# The admissibility GATES (T0–T3) are the gates STAGE's ladder (gates.evaluate →
# gate_trace.parquet, R10). This engine is now a pure READER of that trace: it pulls the
# per-frame verdicts + signals (admit/quarter_ok/side_ok · yaw_f/blur/blink/em_conf/em_vel/
# query_dist/mp_yaw_raw/pose_src · sunglasses_v/masked_v) and does ONLY the PRODUCT work over
# them — rep tiebreak + diversity-set view bins + crop extraction. No gate logic, no signal
# assembly, no ArcFace centroids live here anymore (all in gates.run_gates). Constants reused:
# BLINK_MAX + QUERY_DIST_MAX (the ③ warm-ranking fallback + band, from gates), pose thresholds
# (POSE_MAX_DEG/FRONTAL_DEG/SIDE_DEG from pose.py — the gate/quantizer home).
# a portrait needs a minimum of genuinely-admissible evidence — an always-occluded
# subject should get NO portrait, not one from a few noise-leaked frames.
MIN_ADMIT = 5


def _n01(x, lo, hi):
    return float(np.clip((x - lo) / (hi - lo + 1e-9), 0, 1))


def _reset_own_candidates(out_root, clip_id: str) -> None:
    """Idempotent: drop portrait/portrait_set rows from candidates.jsonl so a re-run does not
    duplicate them (select.py clears the file for likeness/highlight; portrait owns portrait*)."""
    cpath = candidates_path(Path(out_root), clip_id)
    if not cpath.exists():
        return
    kept = [c for c in read_candidates(Path(out_root), clip_id)
            if c.get("product") not in ("portrait", "portrait_set")]
    with cpath.open("w", encoding="utf-8") as fh:
        for c in kept:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")


def _objective_fns(yaw_f, pit_f, rol_f, blur, qd, blink, em_conf, vel, sharp_hi):
    """Build one subject's objective tiebreak (NOT the aesthetic 0-axis): frontality +
    sharpness + ③ query WARMTH, softly de-rated for emotion ambiguity (conf) / instability
    (stab); NaN → 1.0 = exact no-op. Returns (obj, breakdown) closures keyed by frame index k.
    em_conf is a happy/recognizability detector, NOT an energy meter (corr(em_conf,arousal)≈−0.1)
    — do NOT reuse it as expression energy (that is a HIGHLIGHT axis)."""
    def conf_fac(e):   # em_conf 1→1.0, .6→1.0(sat), .5→.95, 0→.7 ; floored so calm-neutral survives
        return 1.0 if not np.isfinite(e) else float(np.clip(0.7 + 0.5 * e, 0.0, 1.0))

    def stab_fac(v):   # anti-transition: em_vel 0→1.0, 1→.7, floor .5
        return 1.0 if not np.isfinite(v) else float(np.clip(1.0 - 0.3 * v, 0.5, 1.0))

    def terms(k):
        # within-view ranking = geometry (frontality + sharpness) + ③ query WARMTH, balanced so
        # a warm-but-soft frame can't beat a sharp one and a sharp frame closer to the warm query
        # wins over a neutral one. `warm` = proximity to the authored query (subsumes eyes-open:
        # blink IS a query dim); profiles have no blendshape (qd=inf) → fall back to eyes-open.
        ang = abs(yaw_f[k]) + abs(np.nan_to_num(pit_f[k])) + abs(np.nan_to_num(rol_f[k]))
        front = 1.0 - _n01(ang, 0, 3 * POSE_MAX_DEG)
        sharp = _n01(np.nan_to_num(blur[k], nan=0.0), 0, sharp_hi)
        warm = (1.0 - _n01(qd[k], 0.0, QUERY_DIST_MAX)) if np.isfinite(qd[k]) \
            else 1.0 - _n01(np.nan_to_num(blink[k], nan=0.0), 0, BLINK_MAX)
        return front, sharp, warm

    def obj(k):
        front, sharp, warm = terms(k)
        return round((front + sharp + warm) * conf_fac(em_conf[k]) * stab_fac(vel[k]), 4)

    def breakdown(k):
        """The rep-selection reasoning made observable: which term carried the objective."""
        front, sharp, warm = terms(k)
        return {"front": round(float(front), 3), "sharp": round(float(sharp), 3),
                "warm": round(float(warm), 3),
                "query_dist": round(float(qd[k]), 3) if np.isfinite(qd[k]) else None,
                "conf": round(conf_fac(em_conf[k]), 3), "stab": round(stab_fac(vel[k]), 3)}

    return obj, breakdown


def select_portrait(out_root, clip_id: str, *, fps: int = 6) -> dict:
    """Read gate_trace → rep + diversity set → extract crops. Returns summary.
    Pure reader of gate_trace.parquet (produced by the gates stage): no gate logic here."""
    t0 = time.perf_counter()
    cdir = clip_dir(Path(out_root), clip_id)
    tub = read_tubelets(out_root, clip_id).sort(["track_id", "frame_idx"])
    gt = read_gate_trace(out_root, clip_id)
    if gt is None:
        raise ValueError(
            f"portrait needs gate_trace.parquet (the gates stage must run first) — none for clip {clip_id!r}")

    # crop track (clean container) — the extraction source. None → no crops extracted.
    crops_dir = cdir / "crops"
    manifest = None
    if (crops_dir / "manifest.json").exists():
        manifest = json.loads((crops_dir / "manifest.json").read_text(encoding="utf-8"))
    crop_index = {s["subject_id"]: {f: i for i, f in enumerate(s["frames"])}
                  for s in (manifest["subjects"] if manifest else [])}

    # optional-input PRESENCE — recorded on the summary (the inspector's portrait_meta shows
    # it). The gates stage consumed parse/headpose; portrait only REPORTS whether they were
    # available (path existence — a realistic parse/headpose parquet always carries rows).
    parse_present = parse_path(Path(out_root), clip_id).exists()
    headpose_present = headpose_path(Path(out_root), clip_id).exists()

    pdir = cdir / "portraits"
    pdir.mkdir(parents=True, exist_ok=True)
    for old in pdir.glob("*.png"):
        old.unlink()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _reset_own_candidates(out_root, clip_id)

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

    # 제품 스코프 (user 2026-07-07): portrait은 **주탑승자만** — aux는 얼굴이 작고 상시
    # 가림이라 측정 신뢰가 낮다 (P1-② 감사 실증). 게이트 판정·trace는 gates 스테이지가
    # 전원 유지 (공유 validity를 likeness가 소비, aux 센트로이드는 cos_other rival) — 여기선
    # main만 방출하므로 non-main은 일찍 건너뛴다.
    for sid in sorted(tub["track_id"].unique().to_list()):
        df = tub.filter(pl.col("track_id") == sid).sort("frame_idx")
        role = df["rider_role"][0]
        if role != "main":
            continue

        ts = {r["frame_idx"]: r["timestamp_ms"] for r in df.iter_rows(named=True)}

        # per-frame GATE VERDICTS + SIGNALS read straight from the trace (frame_idx order
        # matches tubelets — both sorted). These ARE the values the gate assembled from the
        # producers; reading them back keeps portrait.json byte-identical while the
        # admissibility decision stays gate-owned (R10).
        g = gt.filter(pl.col("track_id") == sid).sort("frame_idx")
        fx = g["frame_idx"].to_numpy()
        N = len(fx)
        admit = g["admit"].to_numpy()
        quarter_ok = g["quarter_ok"].to_numpy()
        side_ok = g["side_ok"].to_numpy()
        yaw_f = g["yaw_f"].to_numpy()
        pit_f = g["pit_f"].to_numpy()
        rol_f = g["rol_f"].to_numpy()
        blur = g["blur"].to_numpy()
        blink = g["blink"].to_numpy()
        em_conf = g["em_conf"].to_numpy()
        vel = g["em_vel"].to_numpy()
        mp_yaw = g["mp_yaw_raw"].to_numpy()   # raw MediaPipe yaw → the rep's reported yaw
        pose_src = g["pose_src"].to_list()    # "6d" | "mp" per frame (diversity provenance)
        sunglasses_v = g["sunglasses_v"].to_numpy()
        masked_v = g["masked_v"].to_numpy()
        qd = g["query_dist"].to_numpy()
        qd = np.where(np.isfinite(qd), qd, np.inf)   # profiles → inf → warm falls back to eyes-open
        n_admit = int(admit.sum())

        # judged worn-item fractions (off-frontal frames abstained in the gate) — averaged here.
        fashion = {"sunglasses": round(float(sunglasses_v.mean()), 3) if N else 0.0,
                   "mask": round(float(masked_v.mean()), 3) if N else 0.0}

        # objective tiebreak (NOT the aesthetic 0-axis) — single home _objective_fns.
        sharp_hi = float(np.nanmax(blur)) if np.isfinite(blur).any() else 1.0
        obj, _obj_breakdown = _objective_fns(yaw_f, pit_f, rol_f, blur, qd, blink, em_conf, vel, sharp_hi)

        # min-admit guard: too few admissible frames → no portrait (an always-
        # occluded subject must not get one from noise-leaked frames).
        surv = [int(k) for k in np.where(admit)[0]] if n_admit >= MIN_ADMIT else []
        rep_pick = None
        alts = []
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
                        "objective": obj(k), "yaw": round(float(mp_yaw[k]), 1),
                        "terms": _obj_breakdown(k)}
            rep_pick, alts = entry(chosen[0]), [entry(k) for k in chosen[1:]]

        # diversity set — view coverage over the FULL fused-pose range (best objective per bin).
        # The profile bin holds genuine side faces (real 6DRepNet yaw, not "MediaPipe gave up")
        # and populates independently of the frontal rep, so a profile-only subject still gets a
        # side portrait — this is what makes side faces queryable as portraits.
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
                                "pose_src": pose_src[k],
                                "terms": _obj_breakdown(int(k))})

        # extract actual portraits from the crop track (the deliverable)
        cap = crop_reader(sid)
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
            "n_side": int(side_ok.sum()), "n_pose_6d": int(sum(s == "6d" for s in pose_src)),
            "fashion": fashion,
            "rep": rep_pick, "rep_file": rep_file,
            "views": [m["view"] for m in members], "extracted": extracted,
            "set": [{"view": m["view"], "frame_idx": m["frame_idx"], "file": m.get("file")}
                    for m in members],
            "crop_track": manifest is not None, "parse": parse_present, "headpose": headpose_present,
        }
        all_portraits.extend(extracted)

    write_portrait(out_root, clip_id, summary)
    summary["portraits_dir"] = str(pdir)
    summary["n_portraits"] = len(all_portraits)
    summary["ms"] = int((time.perf_counter() - t0) * 1000)
    log.info("portrait.done", extra={"clip_id": clip_id, "n_portraits": len(all_portraits),
                                     "crop_track": manifest is not None})
    return summary

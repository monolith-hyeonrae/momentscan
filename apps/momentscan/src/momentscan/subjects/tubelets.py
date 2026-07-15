"""Step 0 synthesis — detections + attribution + scene-phase → tubelets.parquet.

A *tubelet* is one rider's spatio-temporal tube through the clip: one row per
(rider, frame), with every anchor already resolved — ``track_id`` (the stitched
subject), ``rider_role`` (depth vote — NOT face size; children break size
heuristics), ``scene_phase``. It is Step 0's final artifact and the boundary
contract: feature extractors (Track A/B) read tubelets ONLY, never raw
detections. Ghosts and bystanders are gone here; downstream never re-litigates
who is who.

scene-phase (the one genuinely-new Step 0 piece, phase2-plan §A): the kart
sits still while boarding and moves on the ride, so global motion (mean abs
frame difference, downscaled gray) splits the clip. The threshold is derived
from the clip itself (1-D 2-means on the smoothed motion signal) — no magic
constant to drift across cameras/seasons. Tracks that never reach the ride
phase (boarding staff) are dropped, with a log trail.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import cv2
import numpy as np
import polars as pl

from visualbus import FileSource
from visualbus.structured_log import log_context
from visualbus.timestamp import ns_to_seconds

from momentscan.store.stash import read_attribution, read_detections, write_tubelets

log = logging.getLogger("momentscan.tubelets")

SMOOTH_S = 2.0        # motion smoothing window (seconds)
SUSTAIN_S = 1.0       # ride must hold above threshold this long
FLAT_RATIO = 0.6      # low-cluster ≥ this × high-cluster → no boarding detected


def scene_phases(video_path: str | Path, *, fps: int | None = None) -> tuple[dict[int, str], dict[int, int], dict]:
    """One decode pass → (frame_id→phase, frame_id→timestamp_ms, info).

    Motion is computed on 160px-wide grayscale; the boarding/ride boundary is
    the first sustained crossing of a threshold placed between the two motion
    clusters of THIS clip.
    """
    src = FileSource(video_path, fps=fps)
    out_fps = float(fps) if fps else (src.profile.fps or 30.0)
    motion: dict[int, float] = {}
    ts_ms: dict[int, int] = {}
    prev = None
    try:
        for frame in src:
            ts_ms[frame.frame_id] = int(round(ns_to_seconds(frame.t_ns) * 1000))
            h, w = frame.data.shape[:2]
            scale = 160 / w
            g = cv2.cvtColor(
                cv2.resize(frame.data, (160, max(2, int(h * scale)))), cv2.COLOR_BGR2GRAY
            ).astype(np.int16)
            if prev is not None:
                motion[frame.frame_id] = float(np.mean(np.abs(g - prev)))
            prev = g
    finally:
        src.close()

    ids = sorted(motion)
    if not ids:
        return {}, ts_ms, {"boundary_frame": None, "note": "no frames"}

    win = max(1, int(SMOOTH_S * out_fps))
    vals = np.array([motion[i] for i in ids], dtype=np.float64)
    smooth = np.convolve(vals, np.ones(win) / win, mode="same")

    # 1-D 2-means: a self-calibrated still/moving split.
    c0, c1 = float(smooth.min()), float(smooth.max())
    for _ in range(20):
        assign = np.abs(smooth - c0) <= np.abs(smooth - c1)
        if assign.all() or (~assign).all():
            break
        c0, c1 = float(smooth[assign].mean()), float(smooth[~assign].mean())
    if c0 > c1:
        c0, c1 = c1, c0

    info: dict = {"motion_low": round(c0, 2), "motion_high": round(c1, 2)}
    if c1 <= 0 or c0 >= FLAT_RATIO * c1:
        # No still prefix distinguishable — the clip starts already riding.
        info.update({"boundary_frame": None, "note": "no boarding phase detected"})
        return {fid: "ride" for fid in ts_ms}, ts_ms, info

    theta = (c0 + c1) / 2.0
    sustain = max(1, int(SUSTAIN_S * out_fps))
    boundary = None
    above = 0
    for k, v in enumerate(smooth):
        above = above + 1 if v >= theta else 0
        if above >= sustain:
            boundary = ids[k - sustain + 1]
            break
    info["boundary_frame"] = boundary
    if boundary is None:   # never moved — treat all as boarding
        info["note"] = "no ride phase detected"
        return {fid: "boarding" for fid in ts_ms}, ts_ms, info
    return {fid: ("boarding" if fid < boundary else "ride") for fid in ts_ms}, ts_ms, info


def synthesize_tubelets(
    video_path: str | Path,
    out_root: str | Path,
    *,
    fps: int | None = None,
) -> dict:
    """Join detections + attribution + scene-phase into tubelets.parquet."""
    video_path = Path(video_path).expanduser().resolve()
    clip_id = video_path.stem

    with log_context(clip_id=clip_id):
        t0 = time.perf_counter()
        df = read_detections(out_root, clip_id)
        att = read_attribution(out_root, clip_id)
        if not att or not att.get("roles"):
            # a subject QUERY that honestly found nobody carries its reason — surface
            # it instead of the misleading "run attribute first" (attribution exists).
            why = (att or {}).get("reason") or "run `momentscan attribute` first"
            raise FileNotFoundError(f"no subjects constituted for {clip_id} — {why}")
        roles = {int(k): v for k, v in att["roles"].items()}
        depth_by_frame: dict[int, dict] = {s["frame_idx"]: s["depth"] for s in att.get("samples") or []}

        phases, ts_ms, phase_info = scene_phases(video_path, fps=fps)

        rows: list[dict] = []
        dropped_subjects: list[int] = []
        for sid, role in roles.items():
            sub = df.filter(pl.col("subject_id") == sid)
            in_ride = any(phases.get(f) == "ride" for f in sub["frame_idx"].to_list())
            if not in_ride:
                dropped_subjects.append(sid)   # never reached the ride → boarding staff etc.
                continue
            for r in sub.iter_rows(named=True):
                f = r["frame_idx"]
                rows.append({
                    "clip_id": clip_id,
                    "track_id": sid,                       # stitched anchor (data-contract key)
                    "rider_role": role,
                    "frame_idx": f,
                    "timestamp_ms": ts_ms.get(f, int(round(f / (fps or 30) * 1000))),
                    "bbox": r["bbox"],
                    "det_score": r["score"],
                    "depth": (depth_by_frame.get(f) or {}).get(str(sid)),
                    "scene_phase": phases.get(f, "ride"),
                    "embedding": r["embedding"],
                    # Self-contained decode recipe — extractors re-read the
                    # source (cheap) instead of us stashing ~2.5k crops/clip.
                    "crop_ref": f"video:{video_path}?fps={fps or 'native'}&frame={f}",
                })
        n_dropped_rows = int(df.height) - len(rows)

        path = write_tubelets(out_root, clip_id, rows) if rows else None
        result = {
            "clip_id": clip_id,
            "n_tubelet_rows": len(rows),
            "riders": {str(s): roles[s] for s in roles if s not in dropped_subjects},
            "dropped_subjects": dropped_subjects,
            "n_dropped_rows": n_dropped_rows,
            **{f"phase_{k}": v for k, v in phase_info.items()},
            "n_boarding": sum(1 for r in rows if r["scene_phase"] == "boarding"),
            "n_ride": sum(1 for r in rows if r["scene_phase"] == "ride"),
            "tubelets_path": str(path) if path else None,
            "elapsed_s": round(time.perf_counter() - t0, 3),
            "ok": path is not None and Path(path).is_file(),
        }
        log.log(logging.INFO if result["ok"] else logging.WARNING, "tubelets.done", extra=result)
        return result

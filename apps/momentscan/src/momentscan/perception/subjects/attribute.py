"""step0b — rider attribution by depth vote, with whole-clip validity evidence.

Decides ``rider_role`` (main = front seat / auxiliary = back seat) per subject.
The decision is made ONCE per clip — seats do not change mid-ride — but the
EVIDENCE is dense and doubles as a track-swap sensor:

  - depth is sampled on frames where both rider candidates co-occur (stride),
    using the substrate ``DepthEstimator`` (Depth-Anything-V2-Small, bbox =
    absolute xyxy). Face SIZE never participates — a child main rider + adult
    auxiliary inverts any size heuristic; depth measures the seat geometry.
  - per-sample depth ordering → majority vote → roles; ``margin`` = how
    decisive the vote was.
  - **flip segments**: sustained runs where the ordering inverts. A single
    noisy sample is ignored; ``flip_run`` consecutive minority samples mark a
    segment — the signature of a mid-clip track/identity swap.
  - ``valid`` = decisive margin AND no flip segment. An invalid attribution is
    still recorded (with all evidence), but downstream Profile accumulation
    must skip the clip — a poisoned baseline costs more than a missing one.

Runs as its own process (CLI stage over the stash + video), keeping the torch
stack out of the warm onnx daemon. Deps via the ``step0b`` extra.

NOTE: decode fps must match the fps the detect stage ran with — frame_idx
alignment depends on it. (Goes away once scan-level meta lands in the stash.)
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import polars as pl
from visualbus import FileSource
from visualbus.structured_log import log_context

from momentscan.infra.store.stash import read_detections, write_attribution

log = logging.getLogger("momentscan.attribute")

MIN_PERSISTENCE = 0.10   # candidate must appear in ≥10% of the clip's detection frames
DEFAULT_STRIDE = 5       # sample every Nth co-occurrence frame
MARGIN_VALID = 0.7       # vote margin below this → attribution not trusted
FLIP_RUN = 3             # ≥N consecutive minority samples = a flip segment


def rider_candidates(df: pl.DataFrame, *, min_persistence: float = MIN_PERSISTENCE) -> list[int]:
    """Persistent subjects, longest first. Ghost/bystander blips fall out here."""
    n_frames = df["frame_idx"].n_unique()
    per = df.group_by("subject_id").agg(pl.col("frame_idx").n_unique().alias("n"))
    keep = per.filter(pl.col("n") >= max(1, int(min_persistence * n_frames)))
    return keep.sort("n", descending=True)["subject_id"].to_list()


def tally(samples: list[dict], a: int, b: int, *, flip_run: int = FLIP_RUN) -> dict:
    """Vote + whole-clip consistency from per-sample depth orderings.

    Pure function — testable without a depth model. ``samples`` are
    time-ordered ``{"frame_idx": int, "closer": subject_id}`` records.
    """
    votes = {a: 0, b: 0}
    for s in samples:
        votes[s["closer"]] += 1
    total = votes[a] + votes[b]
    if total == 0:
        return {"roles": None, "votes": votes, "margin": None, "flip_segments": [], "valid": False}
    main = a if votes[a] >= votes[b] else b
    aux = b if main == a else a
    margin = abs(votes[a] - votes[b]) / total

    # Sustained minority runs = the ordering inverted for a stretch of the
    # clip. That is what a mid-clip identity swap looks like from depth.
    flip_segments: list[dict] = []
    run: list[dict] = []
    for s in samples:
        if s["closer"] != main:
            run.append(s)
        else:
            if len(run) >= flip_run:
                flip_segments.append(
                    {"start_frame": run[0]["frame_idx"], "end_frame": run[-1]["frame_idx"], "n_samples": len(run)}
                )
            run = []
    if len(run) >= flip_run:
        flip_segments.append(
            {"start_frame": run[0]["frame_idx"], "end_frame": run[-1]["frame_idx"], "n_samples": len(run)}
        )

    return {
        "roles": {str(main): "main", str(aux): "auxiliary"},
        "votes": {str(k): v for k, v in votes.items()},
        "margin": round(margin, 3),
        "flip_segments": flip_segments,
        "valid": margin >= MARGIN_VALID and not flip_segments,
    }


def attribute_clip(
    video_path: str | Path,
    out_root: str | Path,
    *,
    fps: int | None = None,
    stride: int = DEFAULT_STRIDE,
) -> dict:
    """Attribute rider roles for one already-detected clip. Writes attribution.json."""
    video_path = Path(video_path)
    clip_id = video_path.stem

    with log_context(clip_id=clip_id):
        t0 = time.perf_counter()
        df = read_detections(out_root, clip_id)
        candidates = rider_candidates(df)
        record: dict = {
            "clip_id": clip_id,
            "method": "depth-vote",
            "candidates": candidates,
            "stride": stride,
        }

        if not candidates:
            record.update({"ride_type": "NONE", "roles": {}, "valid": False, "samples": []})
        elif len(candidates) == 1:
            # No second rider → no boundary to confuse. Vacuously valid; no depth cost.
            record.update({
                "ride_type": "SOLO",
                "roles": {str(candidates[0]): "main"},
                "margin": None, "votes": None, "flip_segments": [],
                "valid": True, "samples": [],
            })
        else:
            if len(candidates) > 2:
                log.warning("attribution.candidates", extra={"n": len(candidates), "note": "top-2 only"})
            a, b = candidates[0], candidates[1]
            record["ride_type"] = "DUO"

            pair = df.filter(pl.col("subject_id").is_in([a, b]))
            by_frame: dict[int, dict[int, list[float]]] = {}
            for r in pair.iter_rows(named=True):
                by_frame.setdefault(r["frame_idx"], {})[r["subject_id"]] = r["bbox"]
            co_frames = sorted(f for f, m in by_frame.items() if len(m) == 2)
            wanted = set(co_frames[::stride])

            from visualpath.plugins.depth import DepthEstimator  # torch — step0b extra
            est = DepthEstimator()
            samples: list[dict] = []
            src = FileSource(video_path, fps=fps)
            try:
                for frame in src:
                    if frame.frame_id not in wanted:
                        continue
                    depth = est.estimate_depth(frame.data)
                    if depth is None:
                        break
                    h, w = depth.shape[:2]

                    def _mean(bb):
                        x1, y1 = max(0, int(bb[0])), max(0, int(bb[1]))
                        x2, y2 = min(w, int(bb[2])), min(h, int(bb[3]))
                        return float(depth[y1:y2, x1:x2].mean()) if x2 > x1 and y2 > y1 else None
                    da, db_ = _mean(by_frame[frame.frame_id][a]), _mean(by_frame[frame.frame_id][b])
                    if da is None or db_ is None:
                        continue
                    samples.append({
                        "frame_idx": frame.frame_id,
                        "depth": {str(a): round(da, 2), str(b): round(db_, 2)},
                        "closer": a if da > db_ else b,   # higher = nearer (Depth-Anything)
                    })
            finally:
                src.close()

            record.update(tally(samples, a, b))
            record["n_co_frames"] = len(co_frames)
            record["samples"] = samples

        path = write_attribution(out_root, clip_id, record)
        record["elapsed_s"] = round(time.perf_counter() - t0, 3)
        log.log(
            logging.INFO if record["valid"] else logging.WARNING,
            "attribution.done",
            extra={k: record.get(k) for k in
                   ("ride_type", "roles", "margin", "votes", "flip_segments", "valid", "elapsed_s")},
        )
        record["attribution_path"] = str(path)
        return record

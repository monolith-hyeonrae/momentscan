"""Step 0 synthesis — detections + attribution + scene-phase → tubelets.parquet.

A *tubelet* is one rider's spatio-temporal tube through the clip: one row per
(rider, frame), with every anchor already resolved — ``track_id`` (the stitched
subject), ``rider_role`` (depth vote — NOT face size; children break size
heuristics), ``scene_phase``. It is Step 0's final artifact and the boundary
contract: feature extractors (Track A/B) read tubelets ONLY, never raw
detections. Ghosts and bystanders are gone here; downstream never re-litigates
who is who.

scene-phase: 시간 분할 로직(전역 모션 2-means)은 `perception/extraction/phase.py`
로 분리됐다(접수 #11) — tubelets 는 그 frame→phase 맵을 소비해 `scene_phase` 컬럼에
도장하고, ride 에 끝내 도달 못한 트랙(boarding staff)을 로그와 함께 드롭한다.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import polars as pl
from visualbus.structured_log import log_context

from momentscan.infra.store.stash import read_attribution, read_detections, write_tubelets

from momentscan.perception.extraction.phase import scene_phases  # 시간 분할(#11 분리) — 구독

log = logging.getLogger("momentscan.tubelets")


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

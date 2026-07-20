"""Crop track persistence (data-retention) — materialize each subject tubelet
as a CLEAN, fixed-ratio, distortion-free crop video, while the source is still
live (it is only guaranteed ~1 week). The full source is NOT retained; after it
expires every pixel-dependent step (likeness · portrait · relight · inspector
preview) runs off these crop tracks instead.

A crop track is the tubelet "snake" made of pixels: per present frame, the
portrait box (4:5, face = FACEH of height) expanded by a margin, letterboxed
into a fixed canvas (no distortion), encoded H.264 (frame-accurate). Sidecar
manifest maps crop-frame i → original frame_idx and records source provenance
(path · fingerprint · processed time) so within-window re-access works and
post-window is an honest "expired" state, never a crash.

Layout: <out>/<clip>/crops/s{subject}.mp4  +  <out>/<clip>/crops/manifest.json
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2

from momentscan.infra.media import h264_writer, letterbox, transcode_h264
from momentscan.infra.store.stash import clip_dir, read_tubelets

log = logging.getLogger("momentscan.crops")

# portrait box geometry (matches the inspector's pbox): canvas aspect == box aspect.
PASPECT, FACEH, EYE = 0.8, 0.62, 0.42
CANVAS_H = 560
CANVAS_W = int(round(CANVAS_H * PASPECT))   # 448
MARGIN = 1.4                                # reframing headroom around the portrait box


def portrait_box(bbox: list[float], *, margin: float = MARGIN) -> tuple[int, int, int, int]:
    """face bbox → portrait box (4:5, face=FACEH of height), expanded by margin."""
    x1, y1, x2, y2 = bbox
    fh = y2 - y1
    cx = (x1 + x2) / 2
    H = fh / FACEH * margin
    Wd = H * PASPECT
    eye_y = y1 + EYE * fh
    cy = eye_y - EYE * (fh / FACEH) + (fh / FACEH) / 2     # box center y (margin-invariant)
    return (int(round(cx - Wd / 2)), int(round(cy - H / 2)),
            int(round(cx + Wd / 2)), int(round(cy + H / 2)))


# cutting/encoding = media.py (letterbox · h264_writer · transcode_h264); this
# module keeps only the ROI GEOMETRY (portrait_box) + the retention orchestration.


def _fingerprint(src: Path) -> dict:
    st = src.stat()
    return {"path": str(src), "size": st.st_size, "mtime": int(st.st_mtime)}


def extract_crops(video_path: str | Path, out_root: str | Path, clip_id: str,
                  *, fps: int = 6, margin: float = MARGIN) -> dict:
    """Persist a clean crop track per subject from the live source. Returns a
    summary; writes crops/s{sid}.mp4 + crops/manifest.json under the clip dir."""
    src = Path(video_path)
    if not src.exists():
        return {"clip_id": clip_id, "ok": False, "reason": f"source not found: {src}"}
    cdir = clip_dir(Path(out_root), clip_id)
    if not (cdir / "tubelets.parquet").exists():
        return {"clip_id": clip_id, "ok": False, "reason": f"no tubelets at {cdir}"}
    crops_dir = cdir / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)

    with log_ctx(clip_id):
        tub = read_tubelets(out_root, clip_id).sort(["track_id", "frame_idx"])
        # per-subject: frame_idx → bbox, in frame order
        subs: dict[int, dict] = {}
        for r in tub.iter_rows(named=True):
            s = subs.setdefault(r["track_id"], {"role": r["rider_role"], "fb": {}})
            s["fb"][int(r["frame_idx"])] = r["bbox"]
        subs = {sid: s for sid, s in subs.items() if len(s["fb"]) >= 20}
        if not subs:
            return {"clip_id": clip_id, "ok": False, "reason": "no subjects with >=20 frames"}

        # transcode source → temp clean@fps (frame-aligned 0..N-1), read once, then DELETE.
        tmp_clean = crops_dir / "_clean_tmp.mp4"
        transcode_h264(src, tmp_clean, fps=fps)

        writers = {sid: h264_writer(crops_dir / f"s{sid}.mp4", fps, (CANVAS_W, CANVAS_H))
                   for sid in subs}
        order = {sid: [] for sid in subs}      # crop-frame i → original frame_idx
        cap = cv2.VideoCapture(str(tmp_clean))
        f = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            for sid, s in subs.items():
                bbox = s["fb"].get(f)
                if bbox is None:
                    continue
                tile = letterbox(frame, portrait_box(bbox, margin=margin), (CANVAS_W, CANVAS_H))
                writers[sid].stdin.write(tile.tobytes())
                order[sid].append(f)
            f += 1
        cap.release()
        for w in writers.values():
            w.stdin.close(); w.wait()
        tmp_clean.unlink(missing_ok=True)      # full source NOT retained

        manifest = {
            "clip_id": clip_id, "fps": fps, "canvas": [CANVAS_W, CANVAS_H], "margin": margin,
            "source": _fingerprint(src),
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "subjects": [{"subject_id": int(sid), "role": subs[sid]["role"],
                          "n_frames": len(order[sid]), "frames": order[sid],
                          "file": f"s{sid}.mp4"} for sid in subs],
        }
        (crops_dir / "manifest.json").write_text(json.dumps(manifest, separators=(",", ":")), encoding="utf-8")

        result = {"clip_id": clip_id, "ok": True, "crops_dir": str(crops_dir),
                  "n_subjects": len(subs),
                  "subjects": [{"subject_id": int(sid), "n_frames": len(order[sid])} for sid in subs],
                  "source_retained": False}
        log.info("crops.done", extra={"clip_id": clip_id, "n_subjects": len(subs)})
        return result


class log_ctx:
    """Lightweight context — keeps a clip_id field on log records if visualbus's
    structured logger is present; a no-op fallback otherwise."""
    def __init__(self, clip_id: str):
        self.clip_id = clip_id
        self._cm = None

    def __enter__(self):
        try:
            from visualbus.structured_log import log_context
            self._cm = log_context(clip_id=self.clip_id)
            return self._cm.__enter__()
        except Exception:
            return self

    def __exit__(self, *a):
        if self._cm is not None:
            return self._cm.__exit__(*a)
        return False

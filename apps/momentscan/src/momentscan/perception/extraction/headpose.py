"""Full-range head pose (6DRepNet) — the profile-capable pose backend.

The MediaPipe `pose` unit (pose.euler_from_transform) is precise near frontal
but emits NaN on strong profiles (no FaceMesh fit) — correct, but it means SIDE
faces can't be pose-queried. 6DRepNet (300W-LP, full-range, ONNX) fills that gap:
it returns a valid yaw at 75–90° where MediaPipe is silent.

This is a SECOND pose backend, not a replacement. The canonical pose stays
registry-owned with an adapter + provenance (headpose-backend decision):
  - MediaPipe is kept where it fits (frontal, precise).
  - 6DRepNet is consumed where MediaPipe is NaN (profiles).
  - adapter: 6DRepNet euler is a full MIRROR of MediaPipe's frame — ALL THREE
    axes sign-flipped to the MediaPipe convention (validated per-axis sign-corr
    over MediaPipe-covered frames: yaw −0.97, pitch −0.695, roll −0.629 raw →
    all positive after the flip, 6/6 clips consistent).

substrate "extract once": runs on the clean crop track (source expires; crops
persist) like parse/fashion. Needs crops first.

Layout: <out>/<clip>/headpose.parquet  (track_id, frame_idx, yaw, pitch, roll)
        all axes sign-aligned to MediaPipe; full-range (no NaN on profiles).
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import cv2
import numpy as np

from momentscan.infra.store.stash import clip_dir, write_headpose

log = logging.getLogger("momentscan.headpose")

DEFAULT_ONNX = Path.home() / ".insightface" / "models" / "6drepnet" / "sixdrepnet.onnx"
MODEL = "6DRepNet (300W-LP, full-range)"
BATCH = 16

_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)


def _euler_deg(R: np.ndarray) -> tuple[float, float, float]:
    """rotation matrix → (pitch, yaw, roll) degrees (6DRepNet convention)."""
    sy = np.hypot(R[0, 0], R[1, 0])
    return (float(np.degrees(np.arctan2(R[2, 1], R[2, 2]))),   # pitch
            float(np.degrees(np.arctan2(-R[2, 0], sy))),       # yaw
            float(np.degrees(np.arctan2(R[1, 0], R[0, 0]))))   # roll


def extract_headpose(out_root, clip_id: str, *, fps: int = 6,
                     onnx: str | Path = DEFAULT_ONNX) -> dict:
    """Run 6DRepNet over each subject's crop track → headpose.parquet."""
    import onnxruntime as ort

    t0 = time.perf_counter()
    cdir = clip_dir(Path(out_root), clip_id)
    crops_dir = cdir / "crops"
    man_path = crops_dir / "manifest.json"
    if not man_path.exists():
        return {"clip_id": clip_id, "ok": False, "reason": "no crop track (run `crops` first)"}
    if not Path(onnx).exists():
        return {"clip_id": clip_id, "ok": False, "reason": f"6DRepNet onnx missing: {onnx}"}
    manifest = json.loads(man_path.read_text(encoding="utf-8"))

    sess = ort.InferenceSession(str(onnx), providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
    inp = sess.get_inputs()[0].name

    def pose_batch(imgs: list[np.ndarray]) -> list[tuple[float, float, float]]:
        """RGB crops → list of (yaw, pitch, roll), ALL THREE axes sign-aligned to the
        MediaPipe euler convention (pose.euler_from_transform = the definitional home).

        6DRepNet's raw euler frame is a full MIRROR of MediaPipe's — the same
        image↔camera axis relation geometry.CANONICAL_FRAME declares as (1,-1,-1).
        Measured over MP-covered frames (6 clips, n=6558): raw-vs-MP corr yaw −0.97 ·
        pitch −0.695 · roll −0.629, sign-consistent 6/6 clips per axis; flipping all
        three turns every corr positive with ~0 median offset. Until 2026-07-02 only
        yaw was flipped — the fused pit_f/rol_f mixed conventions per frame source
        (harmless to the |·| cone gates, a landmine for any SIGNED consumer)."""
        x = np.stack([(cv2.resize(im, (224, 224)).astype(np.float32) / 255.0 - _MEAN) / _STD
                      for im in imgs]).transpose(0, 3, 1, 2)        # (B,3,224,224) RGB
        Rs = sess.run(None, {inp: x})[0]                            # (B,3,3)
        out = []
        for R in Rs:
            pit, yaw, rol = _euler_deg(R)
            out.append((-yaw, -pit, -rol))   # adapter: full mirror → MediaPipe convention
        return out

    rows: list[dict] = []
    for s in manifest["subjects"]:
        sid, frames = int(s["subject_id"]), s["frames"]
        ntot = len(frames)
        cap = cv2.VideoCapture(str(crops_dir / s["file"]))
        buf, fidx, ci = [], [], 0
        while True:
            ok, img = cap.read()
            if not ok:
                break
            buf.append(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            fidx.append(frames[ci]); ci += 1
            if len(buf) == BATCH:
                rows += _flush(buf, fidx, sid, pose_batch)
                buf, fidx = [], []
                if ci <= BATCH or ci % 50 < BATCH:  # run-watch heartbeat (early + frequent)
                    print(f"  · headpose sid{sid} {ci}/{ntot}f", flush=True)
        if buf:
            rows += _flush(buf, fidx, sid, pose_batch)
        cap.release()

    p = write_headpose(out_root, clip_id, rows)
    result = {"clip_id": clip_id, "ok": True, "headpose": str(p),
              "n_frames": len(rows), "ms": int((time.perf_counter() - t0) * 1000)}
    log.info("headpose.done", extra={"clip_id": clip_id, "n_frames": len(rows)})
    return result


def _flush(imgs, fidx, sid, pose_batch):
    poses = pose_batch(imgs)
    return [{"track_id": sid, "frame_idx": int(f),
             "yaw": round(y, 2), "pitch": round(p, 2), "roll": round(r, 2)}
            for f, (y, p, r) in zip(fidx, poses)]

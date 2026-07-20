"""Track A extractor v0 — tubelets → 46D time series → features/A.parquet.

One decode pass; per tubelet row, fills the 12 pixel/bbox-derived dims
(detection 4 + face-quality 5 + frame-quality 3). All specialist-model dims
(AU, emotion, pose, seg, composites) stay NaN until their plugins/models land —
the vector shape never changes when they do (jepa-poc A4).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import cv2
import numpy as np

from momentscan.infra.store.stash import read_tubelets, write_features, write_landmarks
from visualbus import FileSource
from visualbus.structured_log import log_context

from momentscan_features_specialist45d.registry import DIM, FILLABLE, INDEX

log = logging.getLogger("momentscan.features.specialist45d")


def _gray_stats(gray: np.ndarray) -> tuple[float, float, float, float, float]:
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    mean = float(gray.mean()) / 255.0
    std = float(gray.std()) / 255.0
    clipped = float((gray >= 250).mean())
    crushed = float((gray <= 5).mean())
    return blur, mean, std, clipped, crushed


def extract_clip(video_path: str | Path, out_root: str | Path, *, fps: int | None = None) -> dict:
    video_path = Path(video_path).expanduser().resolve()
    clip_id = video_path.stem

    with log_context(clip_id=clip_id):
        t0 = time.perf_counter()
        tl = read_tubelets(out_root, clip_id)
        by_frame: dict[int, list[dict]] = {}
        for r in tl.iter_rows(named=True):
            by_frame.setdefault(r["frame_idx"], []).append(r)

        from momentscan_features_specialist45d.dpr import LightingEstimator
        from momentscan_features_specialist45d.specialists import (
            AUEstimator, EmotionEstimator, PoseEstimator,
        )
        pose_est = PoseEstimator()
        emo_est = EmotionEstimator()
        au_est = AUEstimator()
        light_est = LightingEstimator()

        rows: list[dict] = []
        lm_rows: list[dict] = []
        src = FileSource(video_path, fps=fps)
        _seen = 0
        try:
            for frame in src:
                _seen += 1
                if _seen == 1 or _seen % 50 == 0:  # run-watch heartbeat (early + frequent)
                    print(f"  · features {_seen}f", flush=True)
                tube_rows = by_frame.get(frame.frame_id)
                if not tube_rows:
                    continue
                img = frame.data
                fh, fw = img.shape[:2]
                fgray = cv2.cvtColor(cv2.resize(img, (320, max(2, int(fh * 320 / fw)))),
                                     cv2.COLOR_BGR2GRAY)
                f_blur, f_bright, f_contrast, _, _ = _gray_stats(fgray)
                # E003: 9-sector brightness map (3×3 grid means, [0,1]) —
                # Δ over time = lighting transients (sun sweep, tunnel).
                gh, gw = fgray.shape
                sectors = [float(fgray[r * gh // 3:(r + 1) * gh // 3,
                                       c * gw // 3:(c + 1) * gw // 3].mean()) / 255.0
                           for r in range(3) for c in range(3)]

                for r in tube_rows:
                    v = np.full(DIM, np.nan, dtype=np.float32)
                    x1, y1, x2, y2 = (int(max(0, r["bbox"][0])), int(max(0, r["bbox"][1])),
                                      int(min(fw, r["bbox"][2])), int(min(fh, r["bbox"][3])))
                    bw, bh = x2 - x1, y2 - y1
                    if bw > 1 and bh > 1:
                        cgray = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
                        c_blur, c_exp, c_con, c_clip, c_crush = _gray_stats(cgray)
                        # E008: face light structure (portrait lighting v0).
                        sm = cv2.GaussianBlur(
                            cv2.resize(cgray, (32, 32)).astype(np.float32), (5, 5), 0)
                        lh, rh = sm[:, :16].mean(), sm[:, 16:].mean()
                        th, bh_ = sm[:16, :].mean(), sm[16:, :].mean()
                        gx = np.abs(np.gradient(sm, axis=1)) + np.abs(np.gradient(sm, axis=0))
                        v[INDEX["face_light_lr"]] = (lh - rh) / (lh + rh + 1e-6)
                        v[INDEX["face_light_tb"]] = (th - bh_) / (th + bh_ + 1e-6)
                        v[INDEX["face_light_harsh"]] = float(np.median(gx)) / 255.0
                        v[INDEX["face_blur"]] = c_blur
                        v[INDEX["face_exposure"]] = c_exp
                        v[INDEX["face_contrast"]] = c_con
                        v[INDEX["clipped_ratio"]] = c_clip
                        v[INDEX["crushed_ratio"]] = c_crush
                        cx, cy = (x1 + x2) / 2 / fw, (y1 + y2) / 2 / fh
                        v[INDEX["face_confidence"]] = r["det_score"]
                        v[INDEX["face_area_ratio"]] = (bw * bh) / (fw * fh)
                        v[INDEX["face_center_distance"]] = float(np.hypot(cx - 0.5, cy - 0.5))
                        v[INDEX["face_aspect_ratio"]] = bw / bh
                        # E002: pose on a padded crop (context helps the mesh);
                        # no mesh on side faces → NaN stays (correct weak prior).
                        px, py = int(bw * 0.25), int(bh * 0.25)
                        cb = (max(0, x1 - px), max(0, y1 - py),
                              min(fw, x2 + px), min(fh, y2 + py))
                        pose = pose_est(img[cb[1]:cb[3], cb[0]:cb[2]])
                        if pose is not None:
                            from momentscan_features_specialist45d.specialists import BLENDSHAPE_ORDER
                            if pose_est.blendshape_names not in (None, BLENDSHAPE_ORDER):
                                raise RuntimeError(
                                    f"blendshape order drifted from contract: {pose_est.blendshape_names}")
                            v[INDEX["head_yaw_dev"]] = pose["pose"][0]
                            v[INDEX["head_pitch"]] = pose["pose"][1]
                            v[INDEX["head_roll"]] = pose["pose"][2]
                            # Raw landmark observation → its own stash track;
                            # appearance reads geometry from the DISTRIBUTION.
                            lm_rows.append({
                                "clip_id": clip_id,
                                "track_id": r["track_id"],
                                "rider_role": r["rider_role"],
                                "frame_idx": frame.frame_id,
                                "landmarks": pose["landmarks"].reshape(-1).tolist(),
                                "transform": pose["transform"].reshape(-1).tolist(),
                                "crop_box": [float(c) for c in cb],
                                "blendshapes": pose["blendshapes"].tolist(),
                            })
                        # E009b: DPR SH on the same padded crop (context helps
                        # the lighting net like it helps the mesh).
                        sh = light_est(img[cb[1]:cb[3], cb[0]:cb[2]])
                        if sh is not None:
                            for k in range(9):
                                v[INDEX[f"face_sh_{k}"]] = sh[k]
                        emo = emo_est(img[y1:y2, x1:x2])
                        if emo is not None:
                            for k, val in emo.items():
                                v[INDEX[k]] = val
                        # E004: DISFA 0–5. Legacy-faithful 10% padded crop —
                        # tight crops depress intensities (mouth/chin clipped).
                        ax, ay = int(max(bw, bh) * 0.1), int(max(bw, bh) * 0.1)
                        au = au_est(img[max(0, y1 - ay):min(fh, y2 + ay),
                                        max(0, x1 - ax):min(fw, x2 + ax)])
                        if au is not None:
                            for k, val in au.items():
                                v[INDEX[k]] = val
                    v[INDEX["blur_score"]] = f_blur
                    v[INDEX["brightness"]] = f_bright
                    v[INDEX["contrast"]] = f_contrast
                    for si, sv in enumerate(sectors):
                        v[INDEX[f"lighting__sector_{si}"]] = sv
                    rows.append({
                        "clip_id": clip_id,
                        "track_id": r["track_id"],
                        "rider_role": r["rider_role"],
                        "frame_idx": frame.frame_id,
                        "feature_space": "specialist45d",
                        "feature": v.tolist(),
                    })
        finally:
            src.close()
            pose_est.close()   # explicit mediapipe teardown (silences the exit-time __del__ TypeError)

        path = write_features(out_root, clip_id, "A", rows) if rows else None
        lm_path = write_landmarks(out_root, clip_id, lm_rows) if lm_rows else None
        n_filled = len(FILLABLE)
        result = {
            "clip_id": clip_id, "feature_space": "specialist45d", "dim": DIM,
            "n_rows": len(rows), "n_dims_filled": n_filled, "n_dims_nan": DIM - n_filled,
            "n_landmark_rows": len(lm_rows),
            "features_path": str(path) if path else None,
            "landmarks_path": str(lm_path) if lm_path else None,
            "elapsed_s": round(time.perf_counter() - t0, 3),
            "ok": path is not None and Path(path).is_file(),
        }
        log.log(logging.INFO if result["ok"] else logging.WARNING, "features.done", extra=result)
        return result

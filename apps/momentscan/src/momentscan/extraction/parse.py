"""Face-surface readings on the clean crop track → parse.parquet.

TWO concerns share this stage today:

  (1) QUALITY (the gate substrate) — exposure/sharpness over the FACE SURFACE,
      measured on a soft point-Gaussian region built from the MediaPipe-478
      landmarks (model-free, geometrically excludes background/hair/hood). The
      weight concentrates on the most-reliable flat skin (cheek apples, forehead
      band, chin, nose-bridge), so the statistics reflect the cleanest skin and
      are robust to landmark jitter (no hard polygon edge). Produces skin_lum /
      skin_clip_* / skin_contrast / skin_entropy / face_micro / eye_lum_rel.

  (2) OCCLUSION / FASHION presence — sunglasses/mask/hat/cloth, still parsed by a
      frozen SegFormer (jonathandinu/face-parsing). DEFERRED: this is migrating to
      FashionCLIP (fashion.py) + the landmark eye region; once that lands, the
      SegFormer block below is deleted and the stage becomes pure-landmark.
      Until then SegFormer runs ONLY for eyes_vis/mouth_vis/glasses_frac/hat_frac/
      cloth_frac/skin_frac — the quality columns no longer come from it.

substrate "extract once": parse.parquet is computed on the crop track and consumed
by the portrait gate (and later likeness/highlight). Needs crops + landmarks first.

Layout: <out>/<clip>/parse.parquet
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import cv2
import numpy as np

from momentscan.subjects.crops import portrait_box
from momentscan.stash import clip_dir, read_landmarks, read_tubelets, write_parse

log = logging.getLogger("momentscan.parse")

MODEL = "jonathandinu/face-parsing"
# CelebAMask-HQ classes (SegFormer — fashion/occlusion only now)
SKIN, NOSE, EYE_G, L_EYE, R_EYE, L_BROW, R_BROW = 1, 2, 3, 4, 5, 6, 7
MOUTH, U_LIP, L_LIP, HAIR, HAT, CLOTH = 10, 11, 12, 13, 14, 18
FACE_CLASSES = (SKIN, NOSE, EYE_G, L_EYE, R_EYE, L_BROW, R_BROW, MOUTH, U_LIP, L_LIP)
BATCH = 4   # SegFormer mit-b5 @ 512² — keep small for 8 GB GPUs

# ── landmark quality region (soft point-Gaussian over mid-skin anchors) ──────────
# Mid-skin anchor landmark indices — forehead band, cheek apples, chin, nose-bridge
# (nose-bridge kept so the T-zone, where sun-washout blows first, is sampled).
_SKIN_ANCHORS = (9, 107, 336, 151, 67, 297, 50, 280, 205, 425, 116, 345, 123, 352,
                 152, 175, 200, 6, 197, 195)
_SIG_FRAC = 0.16        # gaussian sigma = fraction of inter-ocular distance (scale-invariant)
_L_OUTER, _R_OUTER = 33, 263   # eye outer corners — inter-ocular scale reference
_MESH = None            # cached (oval_idx, eye_idx) from mediapipe, or (None, None)


def _oval_idx():
    """Cached MediaPipe face-oval contour index set, or None if unavailable."""
    global _MESH
    if _MESH is None:
        try:
            from mediapipe.tasks.python.vision.face_landmarker import (
                FaceLandmarksConnections as FLC,
            )
            _MESH = sorted({i for c in FLC.FACE_LANDMARKS_FACE_OVAL for i in (c.start, c.end)})
        except Exception:
            _MESH = ()
    return _MESH or None


def _crop_pixels(lm_row, det_bbox, w, h):
    """MediaPipe-478 landmarks (normalized within crop_box) → crop-track pixels.
    landmark→original: cb[0]+nx*(cb[2]-cb[0]); original→crop: portrait_box(det_bbox)→(w,h)."""
    P = np.asarray(lm_row["landmarks"], np.float64).reshape(478, 3)
    cb = np.asarray(lm_row["crop_box"], np.float64)
    ox = cb[0] + P[:, 0] * (cb[2] - cb[0])
    oy = cb[1] + P[:, 1] * (cb[3] - cb[1])
    bx1, by1, bx2, by2 = portrait_box(list(np.asarray(det_bbox, float)))
    crx = (ox - bx1) / (bx2 - bx1) * w
    cry = (oy - by1) / (by2 - by1) * h
    return np.stack([crx, cry], 1)


def _quality(g, pts, oval_idx):
    """Weighted face-surface readings over a soft point-Gaussian skin region.
    g = crop grayscale (float32). pts = (478,2) crop pixels. Returns a dict of
    quality signals, or all-None if the region is too small (→ unjudgeable).
    eye_lum_rel (sunglasses) is NOT here — it stays a SegFormer occlusion signal
    (deferred) so its calibration is unchanged."""
    h, w = g.shape
    hull = cv2.convexHull(pts[oval_idx].astype(np.int32))
    facemask = np.zeros((h, w), np.uint8)
    cv2.fillConvexPoly(facemask, hull, 1)
    iod = np.linalg.norm(pts[_L_OUTER] - pts[_R_OUTER]) + 1e-6
    sig = _SIG_FRAC * iod
    yy, xx = np.mgrid[0:h, 0:w]
    wgt = np.zeros((h, w), np.float32)
    for a in _SKIN_ANCHORS:
        ax, ay = pts[a]
        wgt += np.exp(-((xx - ax) ** 2 + (yy - ay) ** 2) / (2.0 * sig * sig))
    wgt = (wgt * facemask).astype(np.float32)
    wf = wgt.ravel(); vf = g.ravel(); m = wf > 1e-3
    if m.sum() < 50:
        return None
    wm, vm = wf[m], vf[m]
    sw = wm.sum()
    mean = float((vm * wm).sum() / sw)
    var = float(((vm - mean) ** 2 * wm).sum() / sw)
    hgt, _ = np.histogram(vm, bins=256, range=(0.0, 256.0), weights=wm)
    p = hgt[hgt > 0] / hgt.sum()
    entropy = float(-(p * np.log2(p)).sum())
    # face_micro = weighted Laplacian variance = facial-detail RESOLVABILITY.
    # DESCRIPTIVE (camera/resolution/face-size confounded — NOT a gate); used only
    # for per-subject SELECTION ranking (the crispest capture).
    lap = cv2.Laplacian(g, cv2.CV_32F, ksize=3).ravel()[m]
    lap_mean = float((lap * wm).sum() / sw)
    face_micro = float(((lap - lap_mean) ** 2 * wm).sum() / sw)
    return {
        "skin_lum": round(mean, 2),
        "skin_clip_hi": round(float((wm[vm >= 250]).sum() / sw), 4),
        "skin_clip_lo": round(float((wm[vm <= 6]).sum() / sw), 4),
        "skin_contrast": round(float(np.sqrt(var) / (mean + 1e-6)), 4),
        "skin_entropy": round(entropy, 4),
        "face_micro": round(face_micro, 2),
    }


_Q_NULL = {"skin_lum": None, "skin_clip_hi": None, "skin_clip_lo": None,
           "skin_contrast": None, "skin_entropy": None, "face_micro": None}


def extract_parse(out_root, clip_id: str, *, fps: int = 6) -> dict:
    """Landmark-region quality + SegFormer occlusion over each subject's crop track."""
    import torch
    from transformers import SegformerForSemanticSegmentation

    t0 = time.perf_counter()
    cdir = clip_dir(Path(out_root), clip_id)
    crops_dir = cdir / "crops"
    man_path = crops_dir / "manifest.json"
    if not man_path.exists():
        return {"clip_id": clip_id, "ok": False, "reason": "no crop track (run `crops` first)"}
    manifest = json.loads(man_path.read_text(encoding="utf-8"))

    oval_idx = _oval_idx()
    lm = read_landmarks(out_root, clip_id)
    # bbox from TUBELETS (the subjectlet, subject-keyed) — NOT raw detections.
    # detections.track_id is the raw pre-stitch tracker id; keying on it silently
    # lost every stitched-fragment frame (test_0 s2: 522/933 frames = 100% null
    # quality — the exact fault class the C3 boundary contract names). tubelets
    # carries the same bbox values (verified identical) under the subject id.
    tub = read_tubelets(out_root, clip_id)
    LM = {(r["track_id"], r["frame_idx"]): r for r in lm.iter_rows(named=True)} if lm is not None else {}
    DB = {(r["track_id"], r["frame_idx"]): r["bbox"]
          for r in tub.iter_rows(named=True)} if tub is not None else {}

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SegformerForSemanticSegmentation.from_pretrained(MODEL).to(device).eval()

    def seg_fashion(masks: np.ndarray, grays: np.ndarray) -> list[dict]:
        """SegFormer OCCLUSION/FASHION presence ONLY (quality now comes from landmarks).
        eye_lum_rel (sunglasses, opaque/dark over eyes = eye-region luminance / skin
        luminance) stays here with its original SegFormer calibration — unchanged.
        DEFERRED → FashionCLIP; this whole block is deleted when fashion migrates."""
        out = []
        for m, g in zip(masks, grays):
            denom = float(np.isin(m, FACE_CLASSES).sum()) + 1e-6
            eyes = float((m == L_EYE).sum() + (m == R_EYE).sum())
            mouth = float((m == MOUTH).sum() + (m == U_LIP).sum() + (m == L_LIP).sum())
            eye_region = np.isin(m, (EYE_G, L_EYE, R_EYE))
            skin = (m == SKIN)
            eye_lum = float(g[eye_region].mean()) if eye_region.any() else np.nan
            seg_skin_lum = float(g[skin].mean()) if skin.any() else np.nan
            rel = (round(eye_lum / (seg_skin_lum + 1e-6), 4)
                   if np.isfinite(eye_lum) and np.isfinite(seg_skin_lum) else None)
            out.append({
                "eyes_vis": round(eyes / denom, 4),
                "mouth_vis": round(mouth / denom, 4),
                "glasses_frac": round(float((m == EYE_G).sum()) / denom, 4),
                "eye_lum_rel": rel,
                "hat_frac": round(float((m == HAT).sum()) / float(m.size), 4),
                "cloth_frac": round(float((m == CLOTH).sum()) / float(m.size), 4),
                "skin_frac": round(float((m == SKIN).sum()) / denom, 4),
            })
        return out

    def lm_quality(grays: np.ndarray, sid: int, fidx: list[int]) -> list[dict]:
        """landmark soft-Gaussian quality per frame (None where no fit / region too small)."""
        out = []
        for g, fi in zip(grays, fidx):
            row = LM.get((sid, fi)); bb = DB.get((sid, fi))
            q = None
            if row is not None and bb is not None and oval_idx is not None:
                pts = _crop_pixels(row, bb, g.shape[1], g.shape[0])
                q = _quality(g, pts, oval_idx)
            out.append(q if q is not None else dict(_Q_NULL))
        return out

    rows: list[dict] = []
    for s in manifest["subjects"]:
        sid, frames = int(s["subject_id"]), s["frames"]
        ntot = len(frames)
        cap = cv2.VideoCapture(str(crops_dir / s["file"]))
        buf, fidx = [], []
        ci = 0
        while True:
            ok, img = cap.read()
            if not ok:
                break
            buf.append(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            fidx.append(frames[ci]); ci += 1
            if len(buf) == BATCH:
                rows += _run_batch(buf, fidx, sid, model, device, seg_fashion, lm_quality)
                buf, fidx = [], []
                if ci <= BATCH or ci % 50 < BATCH:   # run-watch heartbeat (early + frequent)
                    print(f"  · parse {clip_id} sid{sid} {ci}/{ntot}f", flush=True)
        if buf:
            rows += _run_batch(buf, fidx, sid, model, device, seg_fashion, lm_quality)
        cap.release()

    p = write_parse(out_root, clip_id, rows)
    result = {"clip_id": clip_id, "ok": True, "parse": str(p),
              "n_frames": len(rows), "ms": int((time.perf_counter() - t0) * 1000)}
    log.info("parse.done", extra={"clip_id": clip_id, "n_frames": len(rows)})
    return result


_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)


def _run_batch(imgs, fidx, sid, model, device, seg_fashion, lm_quality):
    import torch
    h0, w0 = imgs[0].shape[:2]
    batch = np.stack([(cv2.resize(im, (512, 512)).astype(np.float32) / 255.0 - _MEAN) / _STD
                      for im in imgs])                       # (B,512,512,3) RGB
    t = torch.from_numpy(batch).permute(0, 3, 1, 2).to(device)
    with torch.no_grad():
        logits = model(pixel_values=t).logits               # (B, C, h, w)
    up = torch.nn.functional.interpolate(logits, size=(h0, w0), mode="bilinear", align_corners=False)
    masks = up.argmax(1).cpu().numpy()
    grays = np.stack([cv2.cvtColor(im, cv2.COLOR_RGB2GRAY) for im in imgs]).astype(np.float32)
    fashion = seg_fashion(masks, grays)
    quality = lm_quality(grays, sid, fidx)
    return [{"track_id": sid, "frame_idx": int(f), **fa, **q}
            for f, fa, q in zip(fidx, fashion, quality)]

"""E012/E013 — scene embedding stream (DINOv2 per processed frame).

The highlight 장면 축's observation substrate: per processed frame, a
clip-level embedding of the FULL FRAME (CLS) AND a BACKGROUND embedding
(patch tokens NOT overlapping any rider bbox, pooled). DINOv2 lane per
dino-lane-decision: semantic-spatial structure, NOT identity/expression.

E013c (customer/situation split, user direction): per frame, cluster the
DINOv3 patches (유사 맥락 그룹핑) → the cluster(s) the face bbox lands in =
CUSTOMER region (face+body grouped); the rest = BACKGROUND (situation). Two
dynamic contexts to correlate: customer_embedding (고객 맥락) vs bg_embedding
(상황 맥락). CLS kept as the full-frame baseline. Staged: simple region-split
first, add ego-motion (common-mode) handling only if the correlation buries.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import cv2
import numpy as np

from momentscan.infra.store.stash import read_tubelets, write_scene
from visualbus import FileSource
from visualbus.structured_log import log_context

log = logging.getLogger("momentscan.features.scene")

# E013b: DINOv3 ViT-B/16 (HF transformers, gated) at 512px → 32×32=1024 patches
# — 4× finer than the DINOv2-S/14 @ 224 grid (16×16), fixing the coarse
# face-vs-everything separation E013 viz exposed. ImageNet norm (== v2).
MODEL_NAME = "dinov3_vitb16"
MODEL_HF = "facebook/dinov3-vitb16-pretrain-lvd1689m"
INPUT_RES = 512
_PATCH = 16
_GRID = INPUT_RES // _PATCH      # 32×32 = 1024 patch tokens
_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class SceneEmbedder:
    """DINOv3 ViT-B/16 on the full frame (512×512) → (CLS, patch tokens),
    both L2-normed. Token layout [CLS, reg×4, patches]; patches are the last
    _GRID² (32×32). CLS = global scene; patches = grid for fg/bg pooling."""

    def __init__(self) -> None:
        import torch
        from transformers import AutoModel

        self._torch = torch
        self._model = AutoModel.from_pretrained(MODEL_HF)
        self._model.eval()
        self._dev = "cuda" if torch.cuda.is_available() else "cpu"
        self._model.to(self._dev)
        self._npatch = _GRID * _GRID

    def __call__(self, frame_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        rgb = cv2.cvtColor(cv2.resize(frame_bgr, (INPUT_RES, INPUT_RES)), cv2.COLOR_BGR2RGB)
        x = (rgb.astype(np.float32) / 255.0 - _IMAGENET_MEAN) / _IMAGENET_STD
        t = self._torch.from_numpy(x.transpose(2, 0, 1))[None].to(self._dev)
        with self._torch.no_grad():
            lhs = self._model(t).last_hidden_state[0]        # [1+reg+patch, 768]
        cls = lhs[0].cpu().numpy().astype(np.float32)
        patches = lhs[-self._npatch:].cpu().numpy().astype(np.float32)  # [1024, 768]
        cls = cls / (np.linalg.norm(cls) + 1e-9)
        return cls, patches


_KCLUST = 6      # KMeans groups for customer-region segmentation (E013c)


def _customer_mask(patches: np.ndarray, bboxes: list, fw: int, fh: int) -> np.ndarray:
    """Customer region via DINOv3 patch clustering (유사 맥락 그룹핑) — the
    cluster(s) the face bbox lands in = the rider (face + body grouped, since
    a dark-clothed rider clusters away from the bright scene). Returns a
    per-patch bool mask (True = customer). If no rider bbox → all False.
    """
    from sklearn.cluster import KMeans

    n = _GRID * _GRID
    face = np.zeros(n, dtype=bool)
    sx, sy = _GRID / max(fw, 1), _GRID / max(fh, 1)
    for x1, y1, x2, y2 in bboxes:
        for r in range(max(0, int(y1*sy)), min(_GRID, int(np.ceil(y2*sy)))):
            for c in range(max(0, int(x1*sx)), min(_GRID, int(np.ceil(x2*sx)))):
                face[r * _GRID + c] = True
    if not face.any():
        return np.zeros(n, dtype=bool)
    lab = KMeans(_KCLUST, n_init=1, max_iter=20, random_state=0).fit_predict(patches)
    face_clusters = set(lab[face].tolist())
    return np.isin(lab, list(face_clusters))


def _pool(patches: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """L2-normed mean of the masked patches (full pool if mask empty)."""
    keep = patches[mask] if mask.any() else patches
    v = keep.mean(axis=0)
    return v / (np.linalg.norm(v) + 1e-9)


def extract_scene(video_path: str | Path, out_root: str | Path, *,
                  fps: int | None = None) -> dict:
    video_path = Path(video_path).expanduser().resolve()
    clip_id = video_path.stem
    with log_context(clip_id=clip_id):
        t0 = time.perf_counter()
        # rider bboxes per frame (background = frame minus these)
        bbox_by_frame: dict[int, list] = {}
        try:
            tl = read_tubelets(out_root, clip_id)
            for r in tl.iter_rows(named=True):
                bbox_by_frame.setdefault(r["frame_idx"], []).append(r["bbox"])
        except Exception:
            pass  # no tubelets → bg = full frame (graceful)

        emb = SceneEmbedder()
        rows: list[dict] = []
        src = FileSource(video_path, fps=fps)
        try:
            for frame in src:
                cls, patches = emb(frame.data)
                fh, fw = frame.data.shape[:2]
                cust = _customer_mask(patches, bbox_by_frame.get(frame.frame_id, []), fw, fh)
                rows.append({"clip_id": clip_id, "frame_idx": frame.frame_id,
                             "embedding": cls.tolist(),                 # full frame (CLS)
                             "customer_embedding": _pool(patches, cust).tolist(),
                             "bg_embedding": _pool(patches, ~cust).tolist(),
                             "model": MODEL_NAME})
                if len(rows) == 1 or len(rows) % 50 == 0:   # run-watch heartbeat (early + frequent)
                    print(f"  · scene {len(rows)}f", flush=True)
        finally:
            src.close()
        path = write_scene(out_root, clip_id, rows) if rows else None
        result = {"clip_id": clip_id, "model": MODEL_NAME, "n_frames": len(rows),
                  "scene_path": str(path) if path else None,
                  "elapsed_s": round(time.perf_counter() - t0, 3),
                  "ok": path is not None}
        log.log(logging.INFO if result["ok"] else logging.WARNING, "scene.done", extra=result)
        return result

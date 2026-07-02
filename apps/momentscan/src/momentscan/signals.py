"""Unit analyzers — one canonical home per primitive signal so selection
(portrait.py), the inspector (viz.py) and future consumers share the SAME
computation, never a drifting re-implementation. Each is a pure function over an
ALREADY-EXTRACTED stream (MediaPipe blendshapes/transform · ArcFace embeddings ·
the crop track); the model that produced the stream lives upstream. This is the
"한 분석기 = 한 정준 함수" layer under the S2 substrate.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

# MediaPipe ARKit-52 blendshape indices — the canonical contract.
BS_BLINK = (9, 10)     # eyeBlink L/R
BS_SMILE = (42, 43)    # mouthSmile L/R
BS_JAW = 25            # jawOpen


# euler_from_transform moved to pose.py (2026-07-02) — the pose DOMAIN home
# (euler readout · MP⊕6D fusion · view quantizer · thresholds live together there).


def blink(bs) -> float:
    return float(max(bs[BS_BLINK[0]], bs[BS_BLINK[1]]))


def smile(bs) -> float:
    return float(max(bs[BS_SMILE[0]], bs[BS_SMILE[1]]))


def jaw(bs) -> float:
    return float(bs[BS_JAW])


def expr_magnitude(bs, baseline) -> float:
    """Distance of a blendshape vector from the person's neutral baseline."""
    return float(np.linalg.norm(np.asarray(bs, float) - np.asarray(baseline, float)))


def crop_blur(img) -> float:
    """Laplacian-variance sharpness of a crop (BGR or gray)."""
    g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(g, cv2.CV_64F).var())


def crop_lighting(img) -> tuple[float, float]:
    """(brightness, harshness) of a crop — mean luminance, and median gradient
    magnitude on a smoothed gray (shadow hardness)."""
    g = (img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)).astype(float)
    harsh = float(np.median(np.abs(cv2.Laplacian(cv2.GaussianBlur(g, (0, 0), 2), cv2.CV_64F))))
    return float(g.mean()), harsh


def identity_deviation(emb) -> np.ndarray:
    """Per-frame ArcFace self-relative deviation = 1 - cos(frame, person-centroid).
    emb: (N, D) → (N,). High = far from this person's own centre."""
    en = np.asarray(emb, float)
    en = en / (np.linalg.norm(en, axis=1, keepdims=True) + 1e-9)
    c = en.mean(0)
    c /= (np.linalg.norm(c) + 1e-9)
    return 1.0 - en @ c


# ── face-geometry primitives — moved from appearance.py / select.py so
# appearance, portrait and the inspector share ONE canonicalization (never a
# drifting re-impl). _template caches the MediaPipe canonical face model.
CANONICAL_OBJ = Path.home() / ".cache" / "visualstack" / "mediapipe" / "canonical_face_model.obj"
_TEMPLATE: np.ndarray | None = None


@dataclass(frozen=True)
class CanonicalFrame:
    """The ONE DECLARED definition of momentscan's face-landmark canonical frame —
    the pose-removed, normalized coordinate system every consumer (appearance,
    portrait, select, inspector, eval) shares via the functions below (verified
    SINGLE home: signals.py — no re-impl across the tree). Externalized from the
    implicit math so the frame's origin / axes / scale / reference are DECLARED +
    provenanced, not reverse-engineered. Declares WHAT IS today (the functions READ
    it → behaviour byte-identical); the two OPEN conventions (centroid origin vs a
    fixed anatomical anchor, 478 vs 468 basis) are NAMED as unification candidates,
    to be settled under split-half eval (STEP 2), never silently. Pose ANGLES stay
    registry-owned (POSE_FIELDS) — this frame references that convention, never
    redefines it."""
    name: str
    reference: Path           # canonical reference shape (MediaPipe face model)
    origin: str               # how translation is removed
    axis_flip: tuple          # (x,y,z) sign flip: image space → camera/canonical space
    handedness: str           # resulting hand of the axes
    scale: str                # scale convention (unitless rms vs metric)
    basis_full: int           # vert count for the distribution/PCA frame (incl. iris)
    basis_mesh: int           # vert count for template/ratio comparison (excl. iris)
    pose_convention: str      # where the euler-angle convention is OWNED (not here)


CANONICAL_FRAME = CanonicalFrame(
    name="mediapipe-canonical-v1",
    reference=CANONICAL_OBJ,
    origin="centroid",              # mean (per-frame) / median (person center) — no fixed anchor
    axis_flip=(1.0, -1.0, -1.0),    # π about x: flip y AND z (image y-down/z-in → camera y-up/z-out)
    handedness="right",             # +x right, +y up, +z toward camera
    scale="rms-unit",               # each shape RMS-normalized to unit radius — UNITLESS (no metric length)
    basis_full=478,                 # incl. iris — _canonicalize (distribution/PCA)
    basis_mesh=468,                 # excl. iris — _norm468 (template / anthropometric ratios)
    pose_convention="registry:POSE_FIELDS (deg, 0=frontal, signed yaw)",
)

# the flip must be a PROPER rotation (det +1), not a reflection — flipping y ALONE
# is a reflection that scrambles the un-rotation (measured: PC1↔yaw −0.996 → +0.09).
# This guard freezes that hard-won lesson at import.
assert round(float(np.prod(CANONICAL_FRAME.axis_flip)), 6) == 1.0, \
    "CANONICAL_FRAME.axis_flip must be a proper rotation (det +1), not a reflection"


def frame_provenance() -> dict:
    """Provenance of the declared frame's reference shape — content identity, not
    just a path (the .obj is an external dep; freshness tracks its mtime, this adds
    a content hash + vert count so a swapped/edited model is visible)."""
    import hashlib
    r = CANONICAL_FRAME.reference
    if not r.exists():
        return {"name": CANONICAL_FRAME.name, "reference": str(r), "present": False}
    raw = r.read_bytes()
    nv = sum(1 for ln in raw.decode("utf-8", "ignore").splitlines() if ln.startswith("v "))
    return {"name": CANONICAL_FRAME.name, "reference": str(r), "present": True,
            "sha256": hashlib.sha256(raw).hexdigest()[:12], "n_verts": nv}


def _norm468(x: np.ndarray) -> np.ndarray:
    """Center + RMS scale over the mesh verts (iris excluded, CANONICAL_FRAME.basis_mesh)
    — the shared normalization for person-vs-template comparison."""
    n = CANONICAL_FRAME.basis_mesh
    x = x[:n] - x[:n].mean(axis=0)
    return x / (np.sqrt((x ** 2).sum(axis=1).mean()) + 1e-9)


def _template() -> np.ndarray:
    global _TEMPLATE
    if _TEMPLATE is None:
        verts = [[float(x) for x in ln.split()[1:4]]
                 for ln in CANONICAL_OBJ.read_text().splitlines() if ln.startswith("v ")]
        _TEMPLATE = _norm468(np.array(verts, dtype=np.float64))
    return _TEMPLATE


def _canonicalize(P: np.ndarray, T: np.ndarray, cb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Crop-normalized landmarks → canonical shapes. Returns (canon, raw),
    both (N, 478, 3) centered + scale-normalized; `raw` skips the un-rotation
    (the control condition for measuring what canonicalization buys)."""
    cw = (cb[:, 2] - cb[:, 0])[:, None]
    ch = (cb[:, 3] - cb[:, 1])[:, None]
    pts = P.copy()
    pts[:, :, 0] *= cw
    pts[:, :, 1] *= ch
    pts[:, :, 2] *= cw                       # mediapipe z is scaled like x
    # image space (y-down, z-in) → matrix's camera space via the DECLARED
    # CANONICAL_FRAME axis flip (π about x = flip y AND z). Flipping y alone is a
    # reflection that scrambles the un-rotation (PC1↔yaw −0.996 → +0.09, drift
    # 0.079 → 0.019); the contract's det=+1 guard freezes that at import.
    pts *= np.asarray(CANONICAL_FRAME.axis_flip, dtype=pts.dtype)
    pts -= pts.mean(axis=1, keepdims=True)

    def _scale_norm(x: np.ndarray) -> np.ndarray:
        s = np.sqrt((x ** 2).sum(axis=2).mean(axis=1))[:, None, None]
        return x / (s + 1e-9)

    R = T[:, :3, :3]                         # canonical → camera rotation
    canon = np.einsum("nji,nkj->nki", R, pts)  # R.T applied per frame
    return _scale_norm(canon), _scale_norm(pts)


def _rolling_median(x: np.ndarray, win: int) -> np.ndarray:
    out = np.empty_like(x)
    h = win // 2
    for i in range(len(x)):
        out[i] = np.nanmedian(x[max(0, i - h): i + h + 1])
    return out

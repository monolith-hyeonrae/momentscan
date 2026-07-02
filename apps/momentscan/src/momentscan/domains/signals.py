"""Unit analyzers — one canonical home per primitive signal so selection
(portrait.py), the inspector (viz.py) and future consumers share the SAME
computation, never a drifting re-implementation. Each is a pure function over an
ALREADY-EXTRACTED stream (MediaPipe blendshapes/transform · ArcFace embeddings ·
the crop track); the model that produced the stream lives upstream. This is the
"한 분석기 = 한 정준 함수" layer under the S2 substrate.
"""
from __future__ import annotations

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


# face-geometry (CanonicalFrame contract · canonicalize/norm468/template) moved to
# geometry.py (2026-07-02) — its own domain (contract + external .obj dep + STEP2
# open conventions). rolling_median moved to products/select.py (its WHEN-smoothing
# home; the inspector subscribes from there).

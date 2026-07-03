"""Pose domain — the single home for head-pose policy between backends and consumers.

Two L1 backends produce raw pose; they are adapters and stay OUT of this module:
  landmarks stage   MediaPipe facial-transformation matrix — frontal-precise,
                    NaN on strong profiles (correct silence: no FaceMesh fit)
  headpose.py       6DRepNet ONNX — full-range profile backend, yaw sign-aligned
                    to MediaPipe's convention (adapter, validated corr ≈ −0.97)

This module owns everything BETWEEN those backends and the consumers: the euler
readout, the MP⊕6D fusion, the {frontal,angle,side} view quantizer, and the pose
thresholds. A pose change lands once here and every consumer inherits it —
portrait's signal assembly, the gate ladder (frontal_pose · side routing),
likeness cohort bins (appearance), select's frontal preference, the inspector.

Experiment discipline (no runtime versioning — git + eval ARE the versions):
write a fuse_pose_v2 beside fuse_pose, flip the single call site, prove with
replay-check (neutrality) or the frozen eval pairs (logic delta), keep or delete.
"""
from __future__ import annotations

import numpy as np

# ── pose thresholds (the two same-name "frontal" facts now carry distinct names) ──
POSE_MAX_DEG = 20.0   # frontal_pose gate band: |yaw|,|pitch|,|roll| all under this
FRONTAL_DEG = 15.0    # frontal | three-quarter view-bin boundary (routing). The
                      # engine's diversity-set frontal/left/right SPLIT (by sign
                      # of yaw_f) is presentation routing done over admit/quarter_ok;
                      # the ladder routes only to admit/quarter/side.
SIDE_DEG = 50.0       # three-quarter | profile boundary (|yaw| ≥ → side)
CORROB_DEG = 30.0     # MP must independently read ≥ this (sign-matched) to confirm a
                      # 6D≥SIDE as a real profile — excludes 6D hood/glare false-highs,
                      # which sit at |mp|<CORROB. Below admit's max |mp| guarantee, so
                      # the SIDE promote can never touch an admitted frontal.
CAMERA_FRONTAL_DEG = 12.0   # E002: this camera's EMPIRICAL frontal (off-axis mount) —
                            # an OFFSET (where true frontal actually sits), not a bin
                            # boundary. Formerly duplicated as appearance.FRONTAL_DEG
                            # and select.EMP_FRONTAL_DEG under a name colliding with
                            # the 15° routing boundary above; distinct fact, kept apart.


def euler_from_transform(M) -> tuple[float, float, float]:
    """MediaPipe facial-transformation matrix (4x4) → (yaw, pitch, roll) degrees;
    0 = frontal (registry pose convention).

    THE euler convention's definitional home: every pose backend must be adapted
    to agree with THIS function's output (semantic axis names stay owned by
    registry:POSE_FIELDS). Adapter validation = per-axis sign-correlation on
    frames both backends cover (headpose.py: 6DRepNet raw euler is a full MIRROR
    — all three axes flip; the same image↔camera axis relation as
    geometry.CANONICAL_FRAME's (1,-1,-1))."""
    R = np.asarray(M, float).reshape(4, 4)[:3, :3]
    return (float(np.degrees(np.arctan2(-R[2, 0], np.hypot(R[0, 0], R[1, 0])))),
            float(np.degrees(np.arctan2(R[2, 1], R[2, 2]))),
            float(np.degrees(np.arctan2(R[1, 0], R[0, 0]))))


def fuse_pose(yaw, pit, rol, yaw6, pit6, rol6):
    """Fused scalar pose: MediaPipe where it fit (precise), 6DRepNet where it
    didn't (profiles). Returns (yaw_f, pit_f, rol_f, pose_6d); pose_6d marks the
    frames the profile backend rescued.

    ⚠ Known blind spot (next logic work lands HERE): fusion trusts finiteness
    only — a 6D reading on an occluded face can be confidently wrong (test_0
    early frames: hand-on-head profile, 175/185 6D-fallback with iddev>0.4)."""
    mp_ok = np.isfinite(yaw)
    yaw_f = np.where(mp_ok, yaw, yaw6)
    pit_f = np.where(mp_ok, pit, pit6)
    rol_f = np.where(mp_ok, rol, rol6)
    pose_6d = ~mp_ok & np.isfinite(yaw6)
    return yaw_f, pit_f, rol_f, pose_6d


def pose_class(mp_yaw, sixd_yaw):
    """View quantizer: MP + 6D yaw → {"frontal","angle","side"} per frame.

    The single-scalar yaw_f cut mislabels real profiles MediaPipe under-reads (it
    compresses |yaw| toward frontal as the face turns) while a lone 6D≥SIDE on a
    near-frontal face is a hood/glare false-high. So SIDE needs TWO-signal consent:
    6D≥SIDE_DEG AND (MP dropped out = true profile, OR MP corroborates a strong turn
    |mp|≥CORROB_DEG with matching sign). FRONTAL needs a live MP under FRONTAL_DEG (the
    permissive bin is withheld unless MP confirms it); everything ambiguous — 6D-only
    mild angles, sign conflicts, MP-high/6D-low — lands in ANGLE. Geometry only; have_bs
    stays a separate admit/quarter precondition downstream."""
    mp = np.asarray(mp_yaw, float)
    sd = np.asarray(sixd_yaw, float)
    mp_nan = ~np.isfinite(mp)
    side = (np.isfinite(sd) & (np.abs(sd) >= SIDE_DEG)
            & (mp_nan | ((np.abs(mp) >= CORROB_DEG) & (np.sign(mp) == np.sign(sd)))))
    frontal = (~mp_nan) & (np.abs(mp) < FRONTAL_DEG)
    out = np.full(np.shape(mp), "angle", dtype=object)
    out[frontal] = "frontal"
    out[side] = "side"     # SIDE last: two-signal consent overrides the frontal default
    return out

"""The 45D signal registry — ported as a CONTRACT from legacy visualbind
(`portrait981/libs/visualbind/signals.py`), field names preserved verbatim so
legacy intuition and any future label tooling carry over.

Fill state (2026-06): emotion 8 + pose 3 + detection 4 + face-quality 5 +
frame-quality 3 = 23 dims fillable from today's visualstack specialists; AU 12
and segmentation 4 stay NaN until their plugins land; legacy composites 3 +
CLIP-mood 4 are NaN (deferred — derived/dynamic). Missing dims are NaN, never
a dropped row (jepa-poc A4) — the robust centroid down-weights them, and the
schema never migrates when a new specialist arrives.
"""

from __future__ import annotations

AU_FIELDS = (
    "au1_inner_brow", "au2_outer_brow", "au4_brow_lowerer", "au5_upper_lid",
    "au6_cheek_raiser", "au9_nose_wrinkler", "au12_lip_corner", "au15_lip_depressor",
    "au17_chin_raiser", "au20_lip_stretcher", "au25_lips_part", "au26_jaw_drop",
)                                                                      # 12 — NaN (no AU plugin yet)
EMOTION_FIELDS = (
    "em_happy", "em_neutral", "em_surprise", "em_angry",
    "em_contempt", "em_disgust", "em_fear", "em_sad",
)                                                                      # 8 — face-expression plugin
POSE_FIELDS = ("head_yaw_dev", "head_pitch", "head_roll")              # 3 — head-pose plugin
DETECTION_FIELDS = (
    "face_confidence", "face_area_ratio", "face_center_distance", "face_aspect_ratio",
)                                                                      # 4 — from tubelet bbox/score
FACE_QUALITY_FIELDS = (
    "face_blur", "face_exposure", "face_contrast", "clipped_ratio", "crushed_ratio",
)                                                                      # 5 — computed on the crop
FRAME_QUALITY_FIELDS = ("blur_score", "brightness", "contrast")        # 3 — computed on the frame
SEGMENTATION_FIELDS = ("seg_face", "seg_eye", "seg_mouth", "seg_hair")  # 4 — NaN (no parse plugin yet)
COMPOSITE_FIELDS = ("duchenne_smile", "wild_intensity", "chill_score")  # 3 — NaN (derived, deferred)
CLIP_MOOD_FIELDS = (
    "clip_warm_smile", "clip_cool_gaze", "clip_playful_face", "clip_wild_energy",
)                                                                      # 4 — NaN (dynamic, deferred)
# E003: lighting restored (legacy 65D had 20D lighting; the 45D cut dropped it).
# 9-sector frame brightness — Δ over time catches lighting transients ("태양
# 스침"). DPR SH coefficients join later (E004+, dpr_v1.t7 preserved).
LIGHTING_FIELDS = tuple(f"lighting__sector_{i}" for i in range(9))     # 9 — frame-level
# E008: FACE-level light structure (portrait의 조명 v0 — 얼굴 크롭 픽셀 산수;
# DPR SH가 모델 기반 후속):
#   face_light_lr     (L−R)/(L+R) half-luminance, signed [−1,1] — 측광 균형
#   face_light_tb     (T−B)/(T+B) — 상/하광 균형 (역광·언더라이트)
#   face_light_harsh  median |gradient| on smoothed crop — 그림자 경도
FACE_LIGHT_FIELDS = ("face_light_lr", "face_light_tb", "face_light_harsh")  # 3 — crop-level
# E009b: DPR SH 9-coeff (dpr_v1.t7, the model-based successor face_light v0
# announced). RAW coefficients stored — direction/strength are READINGS.
# DPR image-frame convention: sh_0=ambient, sh_1=Y(depth), sh_2=Z(image-top+),
# sh_3=X(image-right+), sh_4..8=2nd order.
FACE_SH_FIELDS = tuple(f"face_sh_{i}" for i in range(9))               # 9 — crop-level (DPR)

FIELDS: tuple[str, ...] = (
    AU_FIELDS + EMOTION_FIELDS + POSE_FIELDS + DETECTION_FIELDS
    + FACE_QUALITY_FIELDS + FRAME_QUALITY_FIELDS + SEGMENTATION_FIELDS
    + COMPOSITE_FIELDS + CLIP_MOOD_FIELDS + LIGHTING_FIELDS
    + FACE_LIGHT_FIELDS    # appended LAST — existing indices stay stable
    + FACE_SH_FIELDS       # E009b — appended LAST again, same rule
)
# NOTE: legacy's own docstring said "45D" but its code-level registry holds 46
# fields (detection has 4, not 3 — face_aspect_ratio). We inherit the CODE as
# the contract (+9 lighting E003, +3 face-light E008); "specialist45d" stays
# as the brand name.
DIM = len(FIELDS)
assert DIM == 67, DIM

INDEX: dict[str, int] = {name: i for i, name in enumerate(FIELDS)}

# Dims fillable (E002): bbox/pixel 12 + pose 3 (MediaPipe canonical: degrees,
# 0=frontal, yaw SIGNED for view-binning — legacy name "yaw_dev" kept, semantics
# documented here) + emotion 8 (HSEmotion onnx). AU/seg/composites/clip still NaN.
FILLABLE: frozenset[str] = frozenset(
    DETECTION_FIELDS + FACE_QUALITY_FIELDS + FRAME_QUALITY_FIELDS
    + POSE_FIELDS + EMOTION_FIELDS + LIGHTING_FIELDS + AU_FIELDS   # E004
    + FACE_LIGHT_FIELDS                                            # E008
    + FACE_SH_FIELDS                                               # E009b
)

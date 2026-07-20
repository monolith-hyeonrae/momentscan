"""Cat G — 37축 얼굴 기하 공식 (랜드마크 → 축 값).

출처: appearance-engine `component2/geometry.py` 흡수 (2026-07-20, absorption-plan
§1 A2). appearance-engine 삭제 전 그 레포에서 momentscan 으로 옮긴 측정 수학.

**비밀 2종 분리 (change-forecast ③·absorption-plan A2)**: 이 모듈은 *공식*만
소유한다 — 랜드마크 인덱스 토폴로지 + 비율/각도 산식(측정 기판 비밀). 축 ID·
한글 라벨·캘리 range 는 도메인 정책 비밀이라 여기 두지 않는다(그 절반은
`products/recipe_axes.py`). 합격 시험: 이 파일에 '정책'(라벨·range·게인)이 없고,
`recipe_axes.py` 에 '수학'(랜드마크 산식)이 없으면 분리가 지켜진 것.

계약: `face_axes(points)` — MediaPipe Face Mesh 468/478 정점, **이미지 픽셀 규약**
(y-down, 원점 좌상단)의 (K, 2|3) 배열을 받아 37개 이름-값을 낸다. 모든 비율은
interocular / face_W / face_H 정규화라 스케일 무차원. 값은 자연 float(반올림·
직렬화는 소비자=recipe 스테이지 몫). 축퇴(interocular≈0) 시 빈 dict — 소비자가
전 축을 unfilled 로 정직 보고(절대 조용히 0 채우지 않음).

Reference indices (MediaPipe Face Mesh, viewer's perspective):
    MediaPipe "left" = subject's left = viewer's RIGHT in mirrored frontal view.
    Right eye (lower idx):  outer 33,  inner 133, top 159, bottom 145
    Left  eye (higher idx): outer 263, inner 362, top 386, bottom 374
    Mouth: right corner 61, left corner 291, top 13, bottom 14
    Face contour: chin tip 152, forehead 10, right cheek 234, left cheek 454
    Jaw: right lower 172, left lower 397 · Nose: tip 1, bridge 6, alae 49/279
"""

from __future__ import annotations

import math

import numpy as np

# 분모 degeneracy 가드 (0으로 나눗셈 방지) — 수치 안전값, 정책 아님.
_EPS = 1e-6
# 축퇴 랜드마크 감지 floor: 눈-안쪽 간 거리가 이보다 작으면 좌표가 무너진 것.
_INTEROCULAR_MIN = 1e-3

# G37 mouth_corner_class 경계 (도) — G22(mouth_corner_angle_deg)의 3-class 사상.
# 공식-내재 분류 경계(축 정의 자체가 "low<-3°, mid -3~+5°, high>+5°"), 캘리 range
# 아님. 출처=appearance-engine attribute_axis_schema §6.2 G37.
_MOUTH_CORNER_LOW_DEG = -3.0
_MOUTH_CORNER_HIGH_DEG = 5.0

# MediaPipe Face Mesh 표준 인덱스 (측정 토폴로지 = 공식의 일부).
IDX: dict[str, int | list[int]] = {
    # Eyes
    "right_eye_outer": 33,
    "right_eye_inner": 133,
    "right_eye_top": 159,
    "right_eye_bottom": 145,
    "left_eye_outer": 263,
    "left_eye_inner": 362,
    "left_eye_top": 386,
    "left_eye_bottom": 374,
    # Mouth
    "mouth_right_corner": 61,
    "mouth_left_corner": 291,
    "mouth_top": 13,
    "mouth_bottom": 14,
    "upper_lip_top": 0,
    "lower_lip_bottom": 17,
    # Face contour
    "chin_tip": 152,
    "forehead_top": 10,
    "right_cheek": 234,
    "left_cheek": 454,
    "right_jaw_lower": 172,
    "left_jaw_lower": 397,
    # Nose
    "nose_tip": 1,
    "nose_bridge": 6,
    "nose_alae_right": 49,
    "nose_alae_left": 279,
    "nose_base_center": 2,          # under-nose center
    # Cheek/zygomatic for cheekbone width
    "right_zygomatic": 117,
    "left_zygomatic": 346,
    # Brows (10 points each, ordered top-outer → top-inner → bottom-inner → bottom-outer)
    "right_brow": [70, 63, 105, 66, 107, 55, 65, 52, 53, 46],
    "left_brow": [300, 293, 334, 296, 336, 285, 295, 282, 283, 276],
    # Symmetry pair samples — canonically defined points (avoid pairs unreliable
    # in a stub-canonical face).
    "_sym_pairs": [
        (33, 263),    # eye outers
        (133, 362),   # eye inners
        (159, 386),   # eye tops
        (145, 374),   # eye bottoms
        (61, 291),    # mouth corners
        (172, 397),   # jaw lowers
        (234, 454),   # cheeks
    ],
}

# 축 이름 순서 (G01…G37) — recipe_axes.py 의 axis_id 사상과 위치가 정합해야 한다
# (같은 순서로 zip). 라벨/range 가 아니라 이 모듈이 내는 키의 정본 순서라 여기 산다.
AXIS_NAMES: tuple[str, ...] = (
    "face_width_height_ratio",          # G01
    "jaw_face_width_ratio",             # G02
    "chin_angle_deg",                   # G03
    "cheekbone_face_width_ratio",       # G04
    "forehead_face_height_ratio",       # G05
    "eye_width_ratio_L",                # G06
    "eye_width_ratio_R",                # G07
    "eye_height_ratio_L",               # G08
    "eye_height_ratio_R",               # G09
    "eye_aspect_L",                     # G10
    "eye_aspect_R",                     # G11
    "inter_eye_face_width_ratio",       # G12
    "eye_tilt_L_deg",                   # G13
    "eye_tilt_R_deg",                   # G14
    "nose_width_ratio",                 # G15
    "nose_length_ratio",                # G16
    "nose_bridge_length_ratio",         # G17
    "nose_tip_angle_deg",               # G18
    "upper_lip_thickness_ratio",        # G19
    "lower_lip_thickness_ratio",        # G20
    "mouth_width_ratio",                # G21
    "mouth_corner_angle_deg",           # G22
    "philtrum_length_ratio",            # G23
    "face_thirds_balance",              # G24
    "face_symmetry_score",              # G25
    "brow_length_ratio_L",              # G26
    "brow_length_ratio_R",              # G27
    "brow_thickness_ratio_L",           # G28
    "brow_thickness_ratio_R",           # G29
    "brow_arch_height_L",               # G30
    "brow_arch_height_R",               # G31
    "brow_slope_L_deg",                 # G32
    "brow_slope_R_deg",                 # G33
    "brow_eye_distance_ratio",          # G34
    "inter_brow_distance_ratio",        # G35
    "chin_length_ratio",                # G36
    "mouth_corner_class",               # G37
)


def _dist(p1: np.ndarray, p2: np.ndarray) -> float:
    return float(np.linalg.norm(p1[:2] - p2[:2]))


def _corner_tilt_deg(outer: np.ndarray, inner: np.ndarray) -> float:
    """Tilt of a corner line, L/R symmetric (uses |dx| so both sides share sign).
    Positive = outer higher than inner (uplifted: cat-eye, smile)."""
    dx = abs(outer[0] - inner[0])
    dy = inner[1] - outer[1]                        # +y down in image → flip
    return math.degrees(math.atan2(dy, dx)) if dx > _EPS else 0.0


def _angle_at(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Angle at vertex b formed by segments b→a and b→c, in degrees [0, 180]."""
    va = a[:2] - b[:2]
    vc = c[:2] - b[:2]
    na = float(np.linalg.norm(va))
    nc = float(np.linalg.norm(vc))
    if na < _EPS or nc < _EPS:
        return 0.0
    cos_t = float(np.clip(np.dot(va, vc) / (na * nc), -1.0, 1.0))
    return math.degrees(math.acos(cos_t))


def _brow_endpoints_by_center(brow_pts: np.ndarray, center_x: float) -> tuple[np.ndarray, np.ndarray]:
    """Inner (closer to face-center x) and outer (farther) brow endpoints.
    Pose-invariant: works regardless of which side L/R is in image coords."""
    dists = np.abs(brow_pts[:, 0] - center_x)
    inner_idx = int(np.argmin(dists))
    outer_idx = int(np.argmax(dists))
    return brow_pts[inner_idx], brow_pts[outer_idx]


def _point_line_distance(p: np.ndarray, line_a: np.ndarray, line_b: np.ndarray) -> float:
    """Perpendicular distance from p to the line through (a, b). 2D."""
    ab = line_b[:2] - line_a[:2]
    ap = p[:2] - line_a[:2]
    cross = float(abs(ab[0] * ap[1] - ab[1] * ap[0]))
    ab_len = float(np.linalg.norm(ab))
    return cross / (ab_len + _EPS)


def _arch_height(brow_pts: np.ndarray, inner: np.ndarray, outer: np.ndarray, length: float) -> float:
    """Topmost brow point's perpendicular distance to the inner-outer line, /length."""
    if length < _EPS:
        return 0.0
    topmost = brow_pts[int(np.argmin(brow_pts[:, 1]))]      # min y = highest in image
    return _point_line_distance(topmost, inner, outer) / length


def face_axes(points: np.ndarray) -> dict[str, str | float]:
    """MediaPipe landmarks (image-pixel coords, y-down) → 37 Cat-G axis values.

    Returns {name: value} keyed by AXIS_NAMES (G37 is a categorical str). Empty
    dict on degenerate landmarks (interocular ≈ 0) — the caller reports every axis
    as unfilled rather than emit a bogus recipe."""
    pts = points

    # ── reference scales ─────────────────────────────────────────────────────
    right_inner = pts[IDX["right_eye_inner"]]
    left_inner = pts[IDX["left_eye_inner"]]
    interocular = _dist(right_inner, left_inner)
    if interocular < _INTEROCULAR_MIN:
        return {}

    face_width = _dist(pts[IDX["right_cheek"]], pts[IDX["left_cheek"]])
    face_height = _dist(pts[IDX["forehead_top"]], pts[IDX["chin_tip"]])
    jaw_width = _dist(pts[IDX["right_jaw_lower"]], pts[IDX["left_jaw_lower"]])
    cheekbone_width = _dist(pts[IDX["right_zygomatic"]], pts[IDX["left_zygomatic"]])

    attrs: dict[str, str | float] = {}

    # ── face shape (G01–G05) ─────────────────────────────────────────────────
    attrs["face_width_height_ratio"] = face_width / max(face_height, _EPS)
    attrs["jaw_face_width_ratio"] = jaw_width / max(face_width, _EPS)
    attrs["chin_angle_deg"] = _angle_at(
        pts[IDX["right_jaw_lower"]], pts[IDX["chin_tip"]], pts[IDX["left_jaw_lower"]])
    attrs["cheekbone_face_width_ratio"] = cheekbone_width / max(face_width, _EPS)
    eye_mid_y = float((pts[IDX["right_eye_top"]][1] + pts[IDX["left_eye_top"]][1]) / 2.0)
    forehead_h = max(eye_mid_y - float(pts[IDX["forehead_top"]][1]), 0.0)
    attrs["forehead_face_height_ratio"] = forehead_h / max(face_height, _EPS)

    # ── eyes (G06–G14) ───────────────────────────────────────────────────────
    L_outer, L_inner = pts[IDX["left_eye_outer"]], pts[IDX["left_eye_inner"]]
    L_top, L_bottom = pts[IDX["left_eye_top"]], pts[IDX["left_eye_bottom"]]
    R_outer, R_inner = pts[IDX["right_eye_outer"]], pts[IDX["right_eye_inner"]]
    R_top, R_bottom = pts[IDX["right_eye_top"]], pts[IDX["right_eye_bottom"]]
    L_w, L_h = _dist(L_outer, L_inner), _dist(L_top, L_bottom)
    R_w, R_h = _dist(R_outer, R_inner), _dist(R_top, R_bottom)

    attrs["eye_width_ratio_L"] = L_w / max(face_width, _EPS)
    attrs["eye_width_ratio_R"] = R_w / max(face_width, _EPS)
    attrs["eye_height_ratio_L"] = L_h / max(L_w, _EPS)
    attrs["eye_height_ratio_R"] = R_h / max(R_w, _EPS)
    attrs["eye_aspect_L"] = attrs["eye_height_ratio_L"]      # spec axis #10 = #8 (호환용)
    attrs["eye_aspect_R"] = attrs["eye_height_ratio_R"]
    L_center = (L_outer[:2] + L_inner[:2]) / 2.0
    R_center = (R_outer[:2] + R_inner[:2]) / 2.0
    center_to_center = float(np.linalg.norm(L_center - R_center))
    attrs["inter_eye_face_width_ratio"] = center_to_center / max(face_width, _EPS)
    attrs["eye_tilt_L_deg"] = _corner_tilt_deg(L_outer, L_inner)
    attrs["eye_tilt_R_deg"] = _corner_tilt_deg(R_outer, R_inner)

    # ── nose (G15–G18) ───────────────────────────────────────────────────────
    nose_alae_r = pts[IDX["nose_alae_right"]]
    nose_alae_l = pts[IDX["nose_alae_left"]]
    nose_tip = pts[IDX["nose_tip"]]
    nose_bridge = pts[IDX["nose_bridge"]]
    attrs["nose_width_ratio"] = _dist(nose_alae_r, nose_alae_l) / max(face_width, _EPS)
    attrs["nose_length_ratio"] = _dist(nose_bridge, nose_tip) / max(face_height, _EPS)
    alae_mid = (nose_alae_r + nose_alae_l) / 2.0
    attrs["nose_bridge_length_ratio"] = _dist(nose_bridge, alae_mid) / max(face_height, _EPS)
    attrs["nose_tip_angle_deg"] = _angle_at(nose_alae_r, nose_tip, nose_alae_l)

    # ── mouth + lips (G19–G23) ───────────────────────────────────────────────
    M_right_corner = pts[IDX["mouth_right_corner"]]
    M_left_corner = pts[IDX["mouth_left_corner"]]
    M_top = pts[IDX["mouth_top"]]
    M_bottom = pts[IDX["mouth_bottom"]]
    upper_lip_top = pts[IDX["upper_lip_top"]]
    lower_lip_bottom = pts[IDX["lower_lip_bottom"]]
    mouth_width = _dist(M_right_corner, M_left_corner)
    attrs["upper_lip_thickness_ratio"] = _dist(upper_lip_top, M_top) / max(face_height, _EPS)
    attrs["lower_lip_thickness_ratio"] = _dist(M_bottom, lower_lip_bottom) / max(face_height, _EPS)
    attrs["mouth_width_ratio"] = mouth_width / max(face_width, _EPS)

    # G22 — corner height vs the mouth CENTERLINE (mid-y of top/bottom). Corner-corner
    # midpoint is degenerate (all corners on that line by definition → always 0).
    mouth_centerline_y = float((M_top[1] + M_bottom[1]) / 2.0)

    def _tilt_vs_centerline(corner: np.ndarray) -> float:
        dy = mouth_centerline_y - corner[1]                 # +y down → flip; +above centerline (smile)
        # interocular*0.1 = stable non-zero baseline for atan2 (corner shares its own x).
        return math.degrees(math.atan2(dy, interocular * 0.1))

    tilt_l = _tilt_vs_centerline(M_left_corner)
    tilt_r = _tilt_vs_centerline(M_right_corner)
    attrs["mouth_corner_angle_deg"] = (tilt_l + tilt_r) / 2.0
    nose_base = pts[IDX["nose_base_center"]]
    attrs["philtrum_length_ratio"] = _dist(nose_base, upper_lip_top) / max(face_height, _EPS)

    # ── face-thirds balance (G24) ────────────────────────────────────────────
    forehead_y = float(pts[IDX["forehead_top"]][1])
    nose_base_y = float(nose_base[1])
    chin_y = float(pts[IDX["chin_tip"]][1])
    thirds = np.array([
        max(eye_mid_y - forehead_y, 0.0),
        max(nose_base_y - eye_mid_y, 0.0),
        max(chin_y - nose_base_y, 0.0),
    ])
    thirds_sum = thirds.sum()
    if thirds_sum > _EPS:
        normed = thirds / thirds_sum
        attrs["face_thirds_balance"] = float(1.0 - 1.5 * np.max(np.abs(normed - 1.0 / 3.0)))
    else:
        attrs["face_thirds_balance"] = 0.0

    # ── face symmetry (G25) — L/R pair midpoints vs the nose-tip centerline ──
    centerline_x = float(nose_tip[0])
    deviations = []
    for ri, li in IDX["_sym_pairs"]:
        r_pt, l_pt = pts[ri], pts[li]
        midpoint_x = (r_pt[0] + l_pt[0]) / 2.0
        pair_width = abs(l_pt[0] - r_pt[0])
        if pair_width > _EPS:
            deviations.append(abs(midpoint_x - centerline_x) / pair_width)
    if deviations:
        attrs["face_symmetry_score"] = float(1.0 - min(np.mean(deviations) * 2, 1.0))
    else:
        attrs["face_symmetry_score"] = 1.0

    # ── brow geometry (G26–G35) ──────────────────────────────────────────────
    R_brow_pts = pts[IDX["right_brow"], :2]
    L_brow_pts = pts[IDX["left_brow"], :2]
    R_brow_inner, R_brow_outer = _brow_endpoints_by_center(R_brow_pts, centerline_x)
    L_brow_inner, L_brow_outer = _brow_endpoints_by_center(L_brow_pts, centerline_x)

    R_brow_len = _dist(R_brow_inner, R_brow_outer)
    L_brow_len = _dist(L_brow_inner, L_brow_outer)
    attrs["brow_length_ratio_R"] = R_brow_len / interocular
    attrs["brow_length_ratio_L"] = L_brow_len / interocular

    attrs["brow_thickness_ratio_R"] = float(R_brow_pts[:, 1].max() - R_brow_pts[:, 1].min()) / interocular
    attrs["brow_thickness_ratio_L"] = float(L_brow_pts[:, 1].max() - L_brow_pts[:, 1].min()) / interocular

    attrs["brow_arch_height_R"] = _arch_height(R_brow_pts, R_brow_inner, R_brow_outer, R_brow_len)
    attrs["brow_arch_height_L"] = _arch_height(L_brow_pts, L_brow_inner, L_brow_outer, L_brow_len)

    # slope: outer relative to inner (+ = lifted tail, − = drooping)
    attrs["brow_slope_R_deg"] = _corner_tilt_deg(R_brow_outer, R_brow_inner)
    attrs["brow_slope_L_deg"] = _corner_tilt_deg(L_brow_outer, L_brow_inner)

    R_brow_bottom_y = float(R_brow_pts[:, 1].max())
    L_brow_bottom_y = float(L_brow_pts[:, 1].max())
    R_eye_top_y = float(pts[IDX["right_eye_top"]][1])
    L_eye_top_y = float(pts[IDX["left_eye_top"]][1])
    brow_eye_avg = (max(R_eye_top_y - R_brow_bottom_y, 0.0)
                    + max(L_eye_top_y - L_brow_bottom_y, 0.0)) / 2.0
    attrs["brow_eye_distance_ratio"] = brow_eye_avg / max(face_height, _EPS)

    attrs["inter_brow_distance_ratio"] = abs(L_brow_inner[0] - R_brow_inner[0]) / max(face_width, _EPS)

    # ── chin length (G36) + mouth-corner class (G37) ─────────────────────────
    mouth_center_y = float((M_top[1] + M_bottom[1]) / 2.0)
    attrs["chin_length_ratio"] = max(chin_y - mouth_center_y, 0.0) / max(face_height, _EPS)

    mca = attrs["mouth_corner_angle_deg"]
    if mca < _MOUTH_CORNER_LOW_DEG:
        attrs["mouth_corner_class"] = "low"
    elif mca > _MOUTH_CORNER_HIGH_DEG:
        attrs["mouth_corner_class"] = "high"
    else:
        attrs["mouth_corner_class"] = "mid"

    return attrs

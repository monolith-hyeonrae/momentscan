"""C7 정준 프레임 계약의 속성 테스트 (hypothesis).

canonicalize의 계약(domains/geometry.py): 반환 canon은 (N,478,3), per-frame
centroid≈0 · RMS≈1, 그리고 **un-rotation 불변성** — 같은 형상을 임의의 강체
변환(회전 R + 평행이동 t)으로 관측해도 T가 그 R을 들고 있으면 canon은 동일.
이 불변성이 "canonicalization이 사주는 것"의 정의다 (likeness center의 전제).
"""
import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from momentscan.domains.geometry import CANONICAL_FRAME, canonicalize

FLIP = np.asarray(CANONICAL_FRAME.axis_flip, dtype=np.float64)

# 고정 기저 형상 — 시드 고정, 중심화 (테스트 결정성)
_BASE = np.random.default_rng(0).standard_normal((478, 3))
_BASE -= _BASE.mean(axis=0)
_EXPECTED = _BASE / np.sqrt((_BASE ** 2).sum(axis=1).mean())


def _rot(ax: float, ay: float, az: float) -> np.ndarray:
    cx, sx, cy, sy, cz, sz = np.cos(ax), np.sin(ax), np.cos(ay), np.sin(ay), np.cos(az), np.sin(az)
    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return rx @ ry @ rz


def test_axis_flip_is_proper_rotation():
    """reflection 버그 동결 가드의 재확인 (det=+1)."""
    assert float(np.prod(FLIP)) == 1.0


angle = st.floats(-1.2, 1.2, allow_nan=False, allow_infinity=False)
shift = st.floats(-5.0, 5.0, allow_nan=False, allow_infinity=False)


@settings(max_examples=50, deadline=None)
@given(ax=angle, ay=angle, az=angle, tx=shift, ty=shift, tz=shift)
def test_unrotation_invariance(ax, ay, az, tx, ty, tz):
    R = _rot(ax, ay, az)
    # 관측 구성: camera 좌표 = R @ base + t → 입력 P는 axis_flip의 역(±1 대각,
    # 자기 자신)과 단위 crop box로 되돌린 것.
    cam = _BASE @ R.T + np.array([tx, ty, tz])
    P = (cam * FLIP)[None]
    T = np.eye(4)[None].copy()
    T[0, :3, :3] = R
    cb = np.array([[0.0, 0.0, 1.0, 1.0]])

    canon, _raw = canonicalize(P, T, cb)

    assert canon.shape == (1, 478, 3)
    assert np.isfinite(canon).all()
    # centroid ≈ 0 (평행이동 t가 소거됨)
    assert np.allclose(canon[0].mean(axis=0), 0.0, atol=1e-9)
    # RMS ≈ 1
    assert abs(np.sqrt((canon[0] ** 2).sum(axis=1).mean()) - 1.0) < 1e-6
    # 불변성: 어떤 (R, t)로 관측했든 같은 canon
    assert np.allclose(canon[0], _EXPECTED, atol=1e-7)

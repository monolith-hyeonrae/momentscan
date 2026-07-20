"""face_signals — 표본 선발용 얼굴 기하 측정 (측정 공식, 정책 없음).

출처: 2026-07-20 user 진단 카드 왕복(원장 ⑨) — 6클립 진단 카드로 봉인한 표본 선발
정책이 소비하는 세 측정. readings 계층 계약대로 이 모듈은 **어떻게 재는가**의 공식만
소유하고 값(문턱·가중·사다리)은 갖지 않는다 — 정책은 소비자 products/likeness.py 에
산다("이 값을 바꾸면 세 제품이 함께 바뀌나"에 대한 답: pupil/sym 공식은 측정,
문턱은 선발 정책).

실증된 함정 (진단 카드 왕복에서 관측 — 두 신호가 서로를 지켜야 하는 이유):
- pupil: 홍채 랜드마크(469~477)는 **측면에서 붕괴**한다 → pupil 은 정면이 선행
  게이트일 때만 신뢰할 수 있다(측면 프레임의 pupil 값은 쓰레기). ∴ 소비자는
  정면 통과 뒤에서만 pupil floor 를 적용한다.
- sym(visual_frontality): yaw 추정치가 오분류하는 극단 케이스(f716/f16)를 sym 이
  정확히 뒤집는 것이 카드에서 실증됐으나, **극단 yaw 에서는 sym 도 환각**한다 →
  sym 과 |yaw dev| 를 **동시에** 만족시켜 상호 방어한다(원장 ⑨ 사다리의 이중 정면).
"""
from __future__ import annotations

import numpy as np

# MediaPipe FaceMesh iris-refine(478점) 랜드마크 인덱스 — 좌표계 무관 순수 인덱스.
_IRIS_R = ((469, 471), (470, 472))   # 우안 홍채 지름 (수평·수직 쌍, 평균)
_IRIS_L = ((474, 476), (475, 477))   # 좌안 홍채 지름
_LID_R = (159, 145)                  # 우안 상·하 눈꺼풀 (개구)
_LID_L = (386, 374)                  # 좌안 상·하 눈꺼풀
_EYE_R = (33, 133)                   # 우안 눈꼬리 양끝 (EAR 눈 폭 앵커)
_EYE_L = (362, 263)                  # 좌안 눈꼬리 양끝
_NOSE_TIP = 1
_CHEEK_R = 234
_CHEEK_L = 454
_EPS = 1e-9                          # 0-나눗셈 방어


def pupil_visibility(P: np.ndarray) -> np.ndarray:
    """눈꺼풀 개구 ÷ 홍채 지름, 양안 평균 — "눈동자가 보일 만큼 떴는가"의 절대량.

    입력 P = (N, 478, 3) raw crop-정규화 랜드마크. 반환 (N,). 비율이라 스케일 불변.
    ⚠홍채가 측면에서 무너지므로 정면 게이트 뒤에서만 신뢰(모듈 독스트링)."""
    def _d(a: int, b: int) -> np.ndarray:
        return np.linalg.norm(P[:, a, :2] - P[:, b, :2], axis=1)

    r_iris = (_d(*_IRIS_R[0]) + _d(*_IRIS_R[1])) / 2 + _EPS
    l_iris = (_d(*_IRIS_L[0]) + _d(*_IRIS_L[1])) / 2 + _EPS
    return (_d(*_LID_R) / r_iris + _d(*_LID_L) / l_iris) / 2


def visual_frontality(P: np.ndarray) -> np.ndarray:
    """코끝 기준 좌우 뺨 x-거리의 |log 비| — 0=완전 정면, 클수록 측면(sym).

    입력 P = (N, 478, 3) raw crop-정규화 랜드마크. 반환 (N,). yaw 추정과 독립한
    시각적 정면도(yaw 오분류를 뒤집는 프로브 실증)이나 극단 yaw 에선 환각하므로
    yaw 와 동시 만족이 필요하다(모듈 독스트링)."""
    dr = np.abs(P[:, _NOSE_TIP, 0] - P[:, _CHEEK_R, 0]) + _EPS
    dl = np.abs(P[:, _CHEEK_L, 0] - P[:, _NOSE_TIP, 0]) + _EPS
    return np.abs(np.log(dr / dl))


def eye_openness(canon: np.ndarray) -> np.ndarray:
    """EAR (눈꺼풀 개구 ÷ 눈 폭), 양안 평균 — 정준 좌표 입력, 헤어뷰 빈 눈뜸 floor용.

    입력 canon = (N, 478, 3) 정준(un-rotate·scale-norm) 랜드마크. 반환 (N,). pupil 과
    달리 홍채가 아닌 눈꼬리 폭 기준이라 측면에서 덜 취약 — 빈-내 상대 랭킹으로만 쓴다."""
    ear_r = (np.linalg.norm(canon[:, _LID_R[0]] - canon[:, _LID_R[1]], axis=1)
             / (np.linalg.norm(canon[:, _EYE_R[0]] - canon[:, _EYE_R[1]], axis=1) + _EPS))
    ear_l = (np.linalg.norm(canon[:, _LID_L[0]] - canon[:, _LID_L[1]], axis=1)
             / (np.linalg.norm(canon[:, _EYE_L[0]] - canon[:, _EYE_L[1]], axis=1) + _EPS))
    return (ear_r + ear_l) / 2

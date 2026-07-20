"""Preset 스키마 — 시설/카메라/기구 의존 값의 그룹 구조 (C9 · G6).

그룹 블록(camera/phase/likeness/portrait/highlight/delivery)은 contracts.md C9 예약
필드와 1:1. 1차 이주(track/likeness-preset)는 camera·likeness 만 채운다 — 나머지 블록은
예약(다음 이주가 지불): phase(⑦ 조건화)·portrait(쿼리 저작)·highlight(energy 재편)·
delivery(방출 규격). subject_rule·role_delivery 는 Optional 예약.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class CameraPreset:
    """이 카메라의 지오메트리 보정 — 시설/마운트마다 재보정."""
    frontal_deg: float       # 경험적 정면 yaw (off-axis 마운트, E002)
    bin_edge_deg: float      # |yaw−frontal| < 이 값 → frontal 빈 (frontal_deg 와 짝)


@dataclass(frozen=True, kw_only=True)
class LikenessPreset:
    """likeness 판정 임계 — cap_1 코퍼스 보정 계열."""
    f_eyewear: float         # glasses_frac > → 안경 프레임
    f_sun_lum: float         # 안경 중 eye_lum_rel < → 선글라스
    f_mask: float            # mouth_vis < → 마스크 프레임
    f_hat: float             # hat_frac > → 모자 프레임
    f_worn: float            # 프레임 비율 ≥ → 지속 착용(worn) 결론
    f_min_judgeable: int     # < clean-frontal 행 → 전체 행 폴백(측면 위주 트랙)
    f_fuse_tau: float        # typed covering 신뢰 ≥ → parse mask 불리언 기각(두-레인 융합)
    hair_obs_tau: float      # hair/face 픽셀비 중앙값 < → hair 관측불가(후드-업)
    face_id_min_frontal: int # < clean-frontal → face_id 센트로이드 valid 폴백
    face_id_p05_floor: float # coherence_p05 < → low_confidence 플래그(주의 신호, 게이트 아님)


@dataclass(frozen=True, kw_only=True)
class PhasePreset:
    """예약 — phase 모델·좌석 규칙·기대 문장 (⑦ 조건화 이주가 채운다)."""


@dataclass(frozen=True, kw_only=True)
class PortraitPreset:
    """예약 — PORTRAIT_QUERY/W·QUERY_DIST_MAX (쿼리 저작 이주가 채운다)."""


@dataclass(frozen=True, kw_only=True)
class HighlightPreset:
    """예약 — EXPECTATIONS·SCENE_PROMPTS·방출 노브 (energy 재편이 채운다)."""


@dataclass(frozen=True, kw_only=True)
class DeliveryPreset:
    """예약 — 릴 템플릿·방출 규격 (delivery 이주가 채운다)."""


@dataclass(frozen=True, kw_only=True)
class Preset:
    """한 시설/카메라/기구의 정책 값 묶음. 값 근거 = 각 인스턴스(예: race981.py) 주석."""
    name: str
    camera: CameraPreset
    phase: PhasePreset
    likeness: LikenessPreset
    portrait: PortraitPreset
    highlight: HighlightPreset
    delivery: DeliveryPreset
    subject_rule: str | None = None      # C9 예약 — 좌석 규칙 이름
    role_delivery: dict | None = None    # C9 예약 — 역할별 방출 정책

"""race981 — 첫 preset 인스턴스 (이 시설/카메라의 보정값).

값 근거는 각 필드 주석 (code-style §2 3요소: 이름 + 단위 + 근거). 이주 출처 =
preset-inventory.md O 항목 · 원 정의부 주석. 값-불변 이주(track/likeness-preset 1차) —
숫자는 원 상수에서 1비트도 바뀌지 않았다(test_preset.py 특성화 핀이 동결).
"""
from momentscan.preset.schema import (
    CameraPreset,
    DeliveryPreset,
    HighlightPreset,
    LikenessPreset,
    PhasePreset,
    PortraitPreset,
    Preset,
)

RACE981 = Preset(
    name="race981",
    camera=CameraPreset(
        frontal_deg=12.0,          # E002: off-axis 마운트의 경험적 정면 (시설/카메라마다 재보정)
        bin_edge_deg=15.0,         # frontal 빈 경계 (frontal_deg 와 짝; 카메라 지오메트리 의존)
    ),
    likeness=LikenessPreset(
        f_eyewear=0.03,            # glasses_frac > → 안경 (cap_1 보정)
        f_sun_lum=0.7,             # 안경 중 eye_lum_rel < → 선글라스 (cap_1; 조명 의존)
        f_mask=0.01,               # mouth_vis < → 마스크 (cap_1)
        f_hat=0.05,                # hat_frac > → 모자 (cap_1)
        f_worn=0.5,                # 프레임 비율 ≥ → 지속 착용 (탑승 패턴 의존)
        f_min_judgeable=10,        # < clean-frontal 행 → 전체 행 폴백 (측면 위주 트랙)
        f_fuse_tau=0.75,           # typed covering 신뢰 ≥ → parse mask 기각 (dual_3; FashionCLIP 스케일)
        hair_obs_tau=0.1,          # hair/face 픽셀비 < → hair 관측불가 (후드-업; 크롭 스케일 의존)
        face_id_min_frontal=10,    # < clean-frontal → face_id 센트로이드 valid 폴백 (기아 방지)
        face_id_p05_floor=0.5,     # coherence_p05 < → low_confidence (P1-② 감사 보정)
        hair_phase="boarding",     # ⑦(user 2026-07-14): 활강 이전 얼굴이 덜 일그러지고 헤어 안 망가짐
        phase_min_frames=8,        # ≈1.3s@6fps — 대표 뷰(pose_bins/hair)를 담을 최소 boarding 관측;
                                   # 미달=전체 폴백(정직 열화). 보수적 제안값 — user 델타 검토로 조정 대기
    ),
    phase=PhasePreset(),
    portrait=PortraitPreset(),
    highlight=HighlightPreset(),
    delivery=DeliveryPreset(),
)

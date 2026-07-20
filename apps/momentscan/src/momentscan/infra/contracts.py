"""Wire 계약의 형태 검증 (R6·G9·축 L) — egress 경계를 우리 쪽에서 지킨다.

L3 헛점 폐쇄: 계약 위반이 소비자(회사·gen) 측에서 발견되지 않고, 산출 지점에서
지참물과 함께 시끄럽게 죽는다(fail-fast, code-style §3). 검증 대상은 경계를 넘는 두
산출물뿐 — LikenessV1(C11 · likeness.json) · ResultV1(C1 · result.json).

**PresetV1 은 없다** (G9): preset 은 경계를 안 넘는다. C1 이 나르는 것은 domain_profile
이름 문자열뿐이고, preset 값 자체는 프로세스 내부에 머문다(도메인-내부 스키마와 wire
계약을 한 파일에 두면 p981-contracts 분리 시 도로 갈라낼 이중 이동의 씨앗 — 심사1 ⑤).

**검증 철학 = C11 버전 규율의 집행**: 계약된 필드의 실존+형태는 STRICT, 몰튼 내부(미지
하위 필드)는 통과(msgspec 기본 = unknown field 무시). 그래서 additive 연구 변경은 v1 을
안 깨고, 계약 필드의 누락/형태 변경만 raise 한다. 의미/형태 변경 = v2 (어댑터 동시 이행).
"""
from __future__ import annotations

import msgspec


class ContractViolation(ValueError):
    """egress 산출물이 wire 계약(LikenessV1/ResultV1)의 형태를 위반 — 생산 지점에서 raise."""


# ── C11: likeness.json (face_recipe 어댑터 입력 계약) ─────────────────────────
class FaceIdV1(msgspec.Struct):
    """diffusion 개인화 경로(InstantID류) — buffalo_l ArcFace 임베딩."""
    model: str
    n_emb: int
    coherence_mean: float
    coherence_p05: float
    low_confidence: bool          # P1-④ additive; p05<0.5 = 저품질 희석 주의(게이트 아님)
    embedding: list[float]        # 512-D (buffalo_l)


class RiderV1(msgspec.Struct):
    """한 주탑승자의 외형 ID (C11 필수 필드 = 계약면; 몰튼 내부 하위 필드는 통과)."""
    role: str
    n_obs: int
    split_half_drift: float
    split_half_drift_raw: float   # 대조군
    resid_rms: float
    evr_top5: list[float]
    axes: list                    # 이름 붙은 개인 변이축 (내부 형태 몰튼)
    template: dict                # 정준 기하 부속
    neutral: dict
    blendshapes: dict
    face_id: FaceIdV1
    fashion: dict                 # 불리언 레인 + clip 타입 레인 + mask_override
    color_identity: dict | None   # C11: nullable — null = 관측부족(정직)
    samples: dict                 # center_nearest · pose_bins · hair|null
    center: list[float]           # 정준 좌표 (실측 478×3 = 1434; C11 표기 468×3 과 불일치 — 실측 채택)


class LikenessV1(msgspec.Struct):
    """likeness.json v1 (동결 2026-07-07 · C11). riders = 주탑승자만 (스코프 P1-②)."""
    schema: str
    clip_id: str
    riders: dict[str, RiderV1]
    separation: list              # [{tracks, dist, ratio_vs_drift}] — 진단 자(소비자 아님이나 필수)


# ── C1: result.json (Job/Result 계약의 Result 절반) ──────────────────────────
class ResultV1(msgspec.Struct):
    """result.json v1 (service RESULT_SCHEMA) — 회사 대면 Result 계약."""
    schema: str
    clip_id: str
    ok: bool
    failure: str | None
    node: str
    report_url: str
    output_prefix: str
    outputs: dict                 # {product: [경로,...]}
    products_open: list[str]
    products_requested: list[str]
    n_ran: int
    n_skipped: int
    elapsed_s: float
    finished_at_iso: str


def validate_likeness(record: dict, *, clip_id: str = "") -> None:
    """likeness.json 레코드를 C11/LikenessV1 형태로 검증 — 위반 시 ContractViolation raise.
    write 직전 호출: 위반이 face_recipe 소비자 측이 아니라 여기서 죽게(L3 폐쇄)."""
    try:
        msgspec.convert(record, LikenessV1)
    except msgspec.ValidationError as e:
        raise ContractViolation(f"likeness.json (C11/LikenessV1) 위반 clip={clip_id!r}: {e}") from e


def validate_result(record: dict, *, clip_id: str = "") -> None:
    """result.json 레코드를 C1/ResultV1 형태로 검증 — 위반 시 ContractViolation raise.
    Result 작성 직후 호출: 깨진 Result 가 배송/영속되기 전에 우리 쪽에서 죽게."""
    try:
        msgspec.convert(record, ResultV1)
    except msgspec.ValidationError as e:
        raise ContractViolation(f"result.json (C1/ResultV1) 위반 clip={clip_id!r}: {e}") from e

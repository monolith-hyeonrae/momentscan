"""preset — 시설/카메라/기구 의존 값의 단일 홈 (C9 실체화 · 축 B 의 은닉처).

**파이썬 모듈, toml/yaml 아님** (blueprint Q1): freshness 가 transitive import 클로저의
mtime 을 보므로 파이썬 모듈은 값 수정 → 소비 스테이지만 자동 stale (세밀). toml 은
import 클로저 밖이라 `_external_deps` 수동 등록 + 전체-stale 보수 결합이 강제된다
(L1/test_3 = stale 오신뢰 사고 재발 경로). provenance 주석·blame 사슬도 파이썬이라야 산다.

**종착 형태 = "함수는 preset 을 모른다" (G5)**: 스테이지·게이트 함수는 preset 을
임포트하지 않는다 — 값을 **인자로 받는다**. 신설 상수는 태어날 때부터 인자 전달
(`pose_class(…, bands=preset.camera.bands)` 식). 과도기에만 정의부 1줄 재바인딩을 허용
(`_F_EYEWEAR = RACE981.likeness.f_eyewear` — T4 재수출 전례)하고, AST authority 테스트
(G8)가 이주된 상수의 리터럴 재정의를 감시한다. **런타임 스위칭·러너 threading 은 안
만든다** — 두 번째 시설이 지불한다 (C9 원문: 시설 1개인 오늘의 선지불 배관 금지).

로딩 경로: Job.domain_profile("race981" 기본) → run_pipeline 인자(additive) → 초입 1회
`resolve()`(미지 이름=raise) → job.json 기록 → 소비 러너 명시 kwargs.
"""
from momentscan.preset.race981 import RACE981
from momentscan.preset.schema import (
    CameraPreset,
    DeliveryPreset,
    HighlightPreset,
    LikenessPreset,
    PhasePreset,
    PortraitPreset,
    Preset,
)

__all__ = [
    "RACE981", "Preset", "CameraPreset", "LikenessPreset", "PhasePreset",
    "PortraitPreset", "HighlightPreset", "DeliveryPreset", "resolve", "DEFAULT",
]

DEFAULT = "race981"
_PRESETS: dict[str, Preset] = {p.name: p for p in (RACE981,)}


def resolve(name: str) -> Preset:
    """domain_profile 이름 → Preset 인스턴스. 미지 이름 = raise (지참물 = 이름 + 알려진 목록).
    초입 1회 호출 (로딩 경로) — 미지 profile 이 조용히 기본값으로 새지 않게 fail-fast."""
    try:
        return _PRESETS[name]
    except KeyError:
        raise ValueError(f"미지 domain_profile: {name!r} (알려진: {sorted(_PRESETS)})") from None

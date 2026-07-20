"""recipe_preview 특성화 — 13 shape key 투영이 구 appearance-engine 어댑터의 수학을
재현하는지 봉인 + 렌더 선택-의존 경계의 정직한 실패.

투영(순수 수학)은 blender 불요 — 여기서 전량 검증한다. 렌더(blender subprocess)는
바이너리 부재 시 조용히 열화하지 않고 RuntimeError(CLI 가 exit 2 로 번역)하는지만
검증한다(실제 렌더는 통합 실증으로 분리 — 세션-한도 방어).

골든 = fixtures/preview_golden/shape_keys.json. 입력 = fixtures/recipe_golden/expected/
의 frozen recipe.json(구 어댑터 실행 물증). 둘 다 봉인본이라 appearance-engine 삭제
후에도 성립(구 코드 import 없음).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from momentscan.products.recipe_axes import CALIB_TABLES

from momentscan.surface.recipe_preview import (
    _LR_ASYMMETRY_THRESHOLD,
    DEFAULT_GAIN,
    PROPOSED_SHAPE_KEY_MAP,
    SHAPE_KEY_MAP,
    Variant,
    _aggregate_normed,
    project_shape_keys,
    render_recipe_montage,
    select_hair,
)

_FIX = Path(__file__).parent / "fixtures"
_RECIPES = _FIX / "recipe_golden" / "expected"
_GOLDEN = json.loads((_FIX / "preview_golden" / "shape_keys.json").read_text(encoding="utf-8"))

# 비트-동일 포팅(실측 편차 0.0)이라 여유롭게 잡아도 O(0.01~1) 포팅 버그는 잡힌다.
_ATOL = 1e-6


def _recipe(image_id: str) -> dict:
    return json.loads((_RECIPES / f"{image_id}.recipe.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("image_id", sorted(_GOLDEN))
def test_shape_keys_match_golden(image_id):
    got = project_shape_keys(_recipe(image_id), gain=1.0)
    exp = _GOLDEN[image_id]

    assert set(got) == set(exp), f"{image_id}: shape key set differs"
    for sk, ev in exp.items():
        assert abs(got[sk] - ev) <= _ATOL, f"{image_id}/{sk}: {got[sk]} !~ {ev}"


@pytest.mark.parametrize("image_id", sorted(_GOLDEN))
def test_values_in_unit_interval(image_id):
    for sk, v in project_shape_keys(_recipe(image_id), gain=2.2).items():
        assert 0.0 <= v <= 1.0, f"{image_id}/{sk} out of [0,1]: {v}"


@pytest.mark.parametrize("image_id", sorted(_GOLDEN))
def test_gain_never_decreases(image_id):
    """gain≥1 은 (neutral=0 기준) clamped-multiply 라 어떤 키도 줄지 않는다."""
    recipe = _recipe(image_id)
    g1 = project_shape_keys(recipe, gain=1.0)
    g2 = project_shape_keys(recipe, gain=2.2)
    for sk in g1:
        assert g2[sk] >= g1[sk] - 1e-12, f"{image_id}/{sk}: gain 2.2 < gain 1.0"


def test_lr_asymmetry_guard_drops_far_side():
    """L/R 쌍 간극이 임계를 넘으면 0.5 에서 먼 쪽을 버린다(랜드마크 노이즈 가드)."""
    near, far = 0.55, 0.55 + _LR_ASYMMETRY_THRESHOLD + 0.05     # far 가 0.5 에서 더 멀다
    assert _aggregate_normed([near, far]) == near
    # 간극이 임계 이하면 평균.
    assert _aggregate_normed([0.4, 0.6]) == pytest.approx(0.5)


def test_lr_guard_fires_in_corpus():
    """코퍼스 실데이터에서 가드가 실제로 발화(골든이 가드 경로를 포함하는 증거).
    dual_2_t1 Eye_Size 는 두 눈 크기 비대칭이 커 가드가 평균 대신 한 쪽을 택한다."""
    recipe = _recipe("dual_2_t1")
    entries = {}
    for axes in recipe["categories"].values():
        entries.update(axes)
    from momentscan.surface.recipe_preview import _normalize
    l = _normalize(float(entries["G06"]["value"]), *entries["G06"]["range"])
    r = _normalize(float(entries["G07"]["value"]), *entries["G07"]["range"])
    assert abs(l - r) > _LR_ASYMMETRY_THRESHOLD                 # 가드 발화 조건
    got = project_shape_keys(recipe, gain=1.0)["Eye_Size"]
    assert got in (l, r) and got != pytest.approx((l + r) / 2)  # 평균 아님 = 한 쪽 택함


def test_calib_override_race981_matches_baked_and_legacy_saturates():
    """--ab calib 배선 봉인(원장 ① — L-B 판정 후 세계). 기본 캘리 = race981 이므로
    ranges=race981 이 recipe.json 에 구워진 range 와 비트-동일(= calib 몽타주의
    race981 열이 현 파이프 산출과 일치). legacy override 는 posed-편향 창이라
    Eyebrow_Thickness 를 하단 포화(≈0)시킨다 — 전환 근거의 단위-수준 증거."""
    legacy = CALIB_TABLES["legacy-sample1"]
    race981 = CALIB_TABLES["race981-20260720"]

    # race981-explicit == baked-in(ranges=None) — 전 골든에서 비트-동일.
    for image_id in sorted(_GOLDEN):
        r = _recipe(image_id)
        baked = project_shape_keys(r, gain=1.0)
        rc = project_shape_keys(r, gain=1.0, ranges=race981)
        assert set(baked) == set(rc)
        for sk in baked:
            assert abs(baked[sk] - rc[sk]) <= _ATOL, f"{image_id}/{sk}"

    # legacy override: 테이블 교체가 실제로 투영을 바꾸고, posed-편향 포화를 재현.
    r = _recipe("test_3_t0")
    leg = project_shape_keys(r, ranges=legacy)
    rc = project_shape_keys(r, ranges=race981)
    assert all(0.0 <= v <= 1.0 for v in rc.values())
    assert rc != leg
    # Eyebrow_Thickness: legacy 하단 포화(≈0) ↔ race981 창 안(전환 근거).
    assert leg["Eyebrow_Thickness"] < 0.05
    assert 0.1 < rc["Eyebrow_Thickness"] < 0.95


def test_select_hair_none_when_h_unfilled():
    """현 momentscan recipe 는 Cat H 를 방출하지 않는다 → hair 선택 None 폴백."""
    chosen, ranked = select_hair(_recipe("test_3_t0"))
    assert chosen is None
    assert ranked == []


def test_render_raises_when_blender_absent(monkeypatch, tmp_path):
    """blender 바이너리 부재 시 조용히 빈-렌더로 열화하지 않고 RuntimeError(설치 힌트)."""
    monkeypatch.setattr("momentscan.surface.recipe_preview.shutil.which", lambda _n: None)
    # blend 존재 여부보다 먼저 걸리도록 실제 recipe 가 있는 임시 stash 를 만든다.
    clip = tmp_path / "test_3"
    (clip / "recipe").mkdir(parents=True)
    (clip / "recipe" / "test_3_t0.recipe.json").write_text(
        json.dumps(_recipe("test_3_t0")), encoding="utf-8")
    # 존재하는 blend 를 흉내(경로 검사 통과) — which=None 이 먼저 걸려야 함.
    fake_blend = tmp_path / "rig.blend"
    fake_blend.write_bytes(b"stub")

    with pytest.raises(RuntimeError, match="blender"):
        render_recipe_montage(tmp_path, ["test_3"],
                              variants=[Variant(title="×1", slug="g1", gain=1.0)],
                              preview_out=tmp_path / "out", blend=fake_blend)


# ── 확장 키셋 (원장 ⑩ · track lk-keyset) ─────────────────────────────────────

_EXPECTED_PROPOSED_AXES = frozenset({
    "G01", "G02", "G03", "G04", "G05",           # 얼굴형 5축
    "G08", "G09", "G10", "G11",                   # 눈 개방형태 (2키 풀링)
    "G15", "G16", "G18",                          # 코 3축
    "G30", "G31", "G34",                          # 눈썹 (아치 풀링 · 눈썹-눈 거리)
})


def test_key_tiers_disjoint_and_cover_expected_axes():
    """2계층 맵은 겹치지 않고, 제안 계층은 원장 ⑩ 미표현 축 중 몰프-저작 가능한 15축을
    정확히 커버한다. 제외 3축(G24·G25 파생품질·G37 범주형)은 어느 계층에도 없다."""
    assert not (set(SHAPE_KEY_MAP) & set(PROPOSED_SHAPE_KEY_MAP)), "계층 간 키 충돌"

    proposed_axes = {a for ids in PROPOSED_SHAPE_KEY_MAP.values() for a in ids}
    assert proposed_axes == _EXPECTED_PROPOSED_AXES

    all_axes = {a for ids in {**SHAPE_KEY_MAP, **PROPOSED_SHAPE_KEY_MAP}.values() for a in ids}
    assert not ({"G24", "G25", "G37"} & all_axes), "제외 축이 매핑됨"


@pytest.mark.parametrize("image_id", sorted(_GOLDEN))
def test_include_proposed_adds_exactly_proposed_keys(image_id):
    """include_proposed=True 는 rig 13키에 제안 키만 이어 붙인다(집합 = rig ∪ 제안)."""
    rig = project_shape_keys(_recipe(image_id), gain=1.0)
    both = project_shape_keys(_recipe(image_id), gain=1.0, include_proposed=True)
    assert set(rig) == set(SHAPE_KEY_MAP)
    assert set(both) == set(SHAPE_KEY_MAP) | set(PROPOSED_SHAPE_KEY_MAP)


@pytest.mark.parametrize("image_id", sorted(_GOLDEN))
@pytest.mark.parametrize("gain", [1.0, 2.2])
def test_rig_keys_bit_identical_with_or_without_proposed(image_id, gain):
    """확장을 켜도 rig 13키 값은 비트-동일(맵을 잇기만 함) — 골든 무영향의 근거."""
    rig = project_shape_keys(_recipe(image_id), gain=gain)
    both = project_shape_keys(_recipe(image_id), gain=gain, include_proposed=True)
    for sk in rig:
        assert both[sk] == rig[sk], f"{image_id}/{sk}: rig 값이 확장으로 바뀜"


@pytest.mark.parametrize("image_id", sorted(_GOLDEN))
@pytest.mark.parametrize("gain", [1.0, 2.2])
def test_proposed_values_in_unit_interval(image_id, gain):
    both = project_shape_keys(_recipe(image_id), gain=gain, include_proposed=True)
    for sk in PROPOSED_SHAPE_KEY_MAP:
        if sk in both:                                       # 소스 축이 recipe 에 있을 때만 산출
            assert 0.0 <= both[sk] <= 1.0, f"{image_id}/{sk} out of [0,1]: {both[sk]}"


def test_function_default_gain_is_unit_identity():
    """정책 기본(DEFAULT_GAIN)과 분리 — 순수 함수 gain 기본은 1.0(골든 봉인 항등)."""
    r = _recipe("test_3_t0")
    assert project_shape_keys(r) == project_shape_keys(r, gain=1.0)


def test_default_gain_pinned_2_2():
    """L-B ③ 판정 핀: 정책 기본 gain = 2.2."""
    assert DEFAULT_GAIN == 2.2


def test_cli_gain_default_wired_to_default_gain():
    """CLI `--gain` 기본이 DEFAULT_GAIN(=2.2)에 배선됐다(단일-변형·--ab calib 기본)."""
    import argparse

    from momentscan.infra.cli import surfaces

    parser = argparse.ArgumentParser()
    common = argparse.ArgumentParser(add_help=False)
    surfaces.register(parser.add_subparsers(), common)
    args = parser.parse_args(["viz-recipe", "test_3"])
    assert args.gain == DEFAULT_GAIN == 2.2

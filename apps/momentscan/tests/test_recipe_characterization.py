"""recipe 스테이지 특성화 골든 — 신 포팅(face_axes + recipe)이 구 appearance-engine
어댑터의 실행 물증(recipe.json)을 재현하는지 봉인한다.

골든 = appearance-engine `output/recipes_momentscan/` 의 recipe.json (구 어댑터의 유일한
실행 물증). 입력 = 그 골든을 만든 rider 를 담은 likeness.json — **함께 고정(vendored)**.
코퍼스 재독 금지: output/l2 의 likeness 는 이후 변했다(방문마다 재집계). fixtures/ 밑의
frozen 사본만 읽는다.

**선별본(21→14)**: 골든 21건 중 14건만 특성화한다. 21건은 main+auxiliary rider 를
모두 담던 시절 산출이나, 현 likeness 파이프라인은 **main rider 만** 방출한다(P1-② 스코프,
2026-07-07). 제외 7건 = aux rider 6 (재현 불가 — 파이프가 더 이상 안 냄) + test_4 main 1
(코퍼스 재집계로 n_obs 696→346 변화, 원 입력 소실). 14건은 provenance(role·split_half_
drift·var_explained)가 골든과 비트-동일 = 골든을 만든 그 rider 그대로. 상세=README.md.

수치=tolerance(float32 경로 + 5-decimal 직렬화 노이즈, 실측 최대 ~1.5e-5), 구조=exact.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from momentscan.products.recipe import recipe_clip

_FIX = Path(__file__).parent / "fixtures" / "recipe_golden"
_EXPECTED = _FIX / "expected"
_INPUTS = _FIX / "inputs"

# 수치 축 허용오차: |a−b| ≤ ATOL + RTOL·|b|. 실측 최대 편차 ~1.5e-5 ≪ 이 값,
# 포팅 버그(잘못된 인덱스/부호 → O(0.01~10) 이동)는 여전히 잡힌다.
_ATOL = 1e-3
_RTOL = 1e-3

# source provenance 중 홈-불변 하위필드(경로·어댑터명은 홈마다 다르니 제외).
_PROV_KEYS = ("geometry", "rider_role", "n_obs", "split_half_drift", "neutral_var_explained")


def _clip_of(image_id: str) -> str:
    """image_id → clip_id (마지막 _t{rider} 제거). clip 이름의 밑줄은 보존."""
    clip, sep, _tid = image_id.rpartition("_t")
    assert sep, f"unexpected image_id (no _t): {image_id!r}"
    return clip


def _golden_pairs() -> list[tuple[str, str]]:
    """(clip_id, image_id) — expected/ 의 골든에서 파생."""
    return sorted((_clip_of(p.name[: -len(".recipe.json")]), p.name[: -len(".recipe.json")])
                  for p in _EXPECTED.glob("*.recipe.json"))


def _run_recipe(clip_id: str, tmp: Path) -> dict[str, dict]:
    """frozen likeness.json 을 임시 stash 에 놓고 recipe 스테이지를 돌린 뒤 image_id→recipe."""
    (tmp / clip_id).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_INPUTS / f"{clip_id}.likeness.json", tmp / clip_id / "likeness.json")
    from momentscan.infra.store.stash import read_recipes
    recipe_clip(tmp, clip_id)
    return read_recipes(tmp, clip_id) or {}


def _num_close(a, b) -> bool:
    return abs(float(a) - float(b)) <= _ATOL + _RTOL * abs(float(b))


def _assert_axis(got: dict, exp: dict, where: str) -> None:
    # 메타(라벨/타입/척도/설명/range)는 exact, 값만 tolerance.
    for k in ("korean", "name", "type", "time_scale", "range", "description"):
        assert got.get(k) == exp.get(k), f"{where}.{k}: {got.get(k)!r} != {exp.get(k)!r}"
    gv, ev = got["value"], exp["value"]
    if isinstance(ev, (str, bool)) or isinstance(gv, (str, bool)):
        assert gv == ev, f"{where}.value(cat): {gv!r} != {ev!r}"
    else:
        assert _num_close(gv, ev), f"{where}.value: {gv} !~ {ev}"


@pytest.mark.parametrize("clip_id,image_id", _golden_pairs())
def test_recipe_matches_golden(clip_id, image_id, tmp_path):
    produced = _run_recipe(clip_id, tmp_path)
    assert image_id in produced, f"recipe not produced for {image_id} (got {sorted(produced)})"
    got = produced[image_id]
    exp = json.loads((_EXPECTED / f"{image_id}.recipe.json").read_text(encoding="utf-8"))

    # ── structure (exact) ────────────────────────────────────────────────────
    assert got["image_id"] == exp["image_id"]
    assert got["n_axes"] == exp["n_axes"]
    assert got["registry_version"] == exp["registry_version"]

    # categories: 같은 카테고리·같은 axis_id 집합, 엔트리별 메타 exact + 값 tolerance.
    assert set(got["categories"]) == set(exp["categories"]), "category names differ"
    for cat in exp["categories"]:
        g_axes, e_axes = got["categories"][cat], exp["categories"][cat]
        assert set(g_axes) == set(e_axes), f"{cat}: axis_id set differs"
        for aid in e_axes:
            _assert_axis(g_axes[aid], e_axes[aid], f"{image_id}/{cat}/{aid}")

    # unfilled 보고 동일 (완료기준 ①): 카테고리별 ID 목록 일치(순서 무관).
    assert set(got["unfilled"]) == set(exp["unfilled"]), "unfilled category names differ"
    for cat, ids in exp["unfilled"].items():
        assert sorted(got["unfilled"][cat]) == sorted(ids), f"unfilled[{cat}] differs"

    # provenance 안정 하위필드 (홈-불변) — 골든을 만든 그 rider 임을 재확인.
    for k in _PROV_KEYS:
        assert got["source"][k] == exp["source"][k], \
            f"source.{k}: {got['source'][k]!r} != {exp['source'][k]!r}"


def test_recipe_additively_carries_likeness_fields(tmp_path):
    """원장 ④ 동승: recipe 의 additive 'likeness' 블록이 입력 rider 의
    face_id·fashion·color_identity·samples 를 그대로 나른다(소비 이음매). 이 블록은
    골든에 없는 additive 확장이라 특성화(categories/unfilled)와 무관하게 별도 검증."""
    clip_id, image_id = "dual_2", "dual_2_t1"
    produced = _run_recipe(clip_id, tmp_path)
    rec = produced[image_id]
    src = json.loads((_INPUTS / f"{clip_id}.likeness.json").read_text(encoding="utf-8"))
    tid = image_id.rpartition("_t")[2]
    rider = src["riders"][tid]

    assert "likeness" in rec, "additive 'likeness' 패스스루 블록 부재"
    for field in ("face_id", "fashion", "color_identity", "samples"):
        assert rec["likeness"][field] == rider.get(field), f"likeness.{field} 패스스루 불일치"
    # 패스스루는 categories/unfilled 를 건드리지 않는다(criterion ① 무영향 재확인).
    assert set(rec["categories"]) == {"Face Geometry"}
    assert "Face Geometry" not in rec["unfilled"]

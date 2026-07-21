"""recipe_preview 의 blend 를 freshness 가 external dep 로 추적하는지 봉인.

프리뷰는 디자이너 blend(모듈 상수 `_DEFAULT_BLEND`)에 의존한다 — 파이썬 소스가
아니라 런타임에 여는 에셋이라, import 클로저만으로는 blend 교체(D0 이관·리그 갱신)를
'알고리즘 변경'으로 인지하지 못한다. `_external_deps` 에 등재해 blend mtime 이 프리뷰
mtime 보다 새로우면 stale 로 뜨게 한다(ONNX 가중치·canonical.obj 전례와 동일 규율).
"""

from __future__ import annotations

import os
from pathlib import Path

from momentscan.infra.pipeline import freshness

_MOD = "momentscan.surface.recipe_preview"


def test_blend_is_registered_external_dep():
    """실제 _DEFAULT_BLEND 가 프리뷰 모듈의 external dep 로 등재돼 있다."""
    from momentscan.surface.recipe_preview import _DEFAULT_BLEND

    freshness._external_deps.cache_clear()
    deps = freshness._external_deps().get(_MOD, ())
    assert Path(_DEFAULT_BLEND) in deps, f"blend 미등재: {deps}"


def test_canonical_obj_in_preview_closure_via_geometry():
    """측정-메쉬 병치(--ab mesh)가 canonical obj 토폴로지를 읽는다 — 경로 단일홈
    (geometry.CANONICAL_OBJ)의 lazy import 로 geometry 가 프리뷰 클로저에 들어오고,
    obj 는 geometry 의 external dep 로 이미 등재 → 프리뷰 신선도에 잡힌다.
    (_DEFAULT_BLEND 처럼 이중 등재할 필요가 없다는 설계 판단의 봉인.)"""
    from momentscan.perception.readings.geometry import CANONICAL_OBJ

    geo = "momentscan.perception.readings.geometry"
    assert geo in freshness._closure_modules(_MOD), "geometry 가 프리뷰 클로저 밖"
    freshness._external_deps.cache_clear()
    assert Path(CANONICAL_OBJ) in freshness._external_deps().get(geo, ()), "obj 미등재"


def test_blend_mtime_drives_preview_staleness(tmp_path, monkeypatch):
    """blend mtime 이 프리뷰보다 새로우면 stale. Downloads 를 만지지 않도록 stand-in
    blend 로 mtime 만 조작해 blend 엣지를 격리 실증한다."""
    stand_in = tmp_path / "rig.blend"
    stand_in.write_bytes(b"stub")
    monkeypatch.setattr(freshness, "_external_deps", lambda: {_MOD: (stand_in,)})

    art = tmp_path / "montage.png"
    art.write_bytes(b"png")

    # 프리뷰가 모든 소스(+blend)보다 새로우면 fresh.
    newest = freshness.source_mtime(_MOD) + 100
    os.utime(art, (newest, newest))
    assert freshness.is_stale(art, _MOD) is False

    # blend 를 미래로 bump(=리그 갱신) → 프리뷰가 blend 보다 오래됨 → stale.
    os.utime(stand_in, (newest + 1000, newest + 1000))
    assert freshness.is_stale(art, _MOD) is True

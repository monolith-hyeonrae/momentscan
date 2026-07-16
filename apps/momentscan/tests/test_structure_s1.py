"""struct-s1 핀 — 선언 가드(D1 assert 확장)·R12 tier·manifest (2026-07-15 구조 감사).

fail-fast 원칙(code-style §3): 선언이 어긋나면 import에서 지참물과 함께 죽는다 —
이 핀들은 그 가드 자체가 살아 있음을 고정한다."""
from pathlib import Path

from momentscan.pipeline import freshness
from momentscan.pipeline import registry


def test_stage_module_paths_all_resolve():
    """D1: STAGE_MODULE의 dotted-path가 하나라도 해석 불가면 freshness가 무증상
    실명한다(_origin→None→is_stale 항상 False) — 전 경로 실존을 핀."""
    dangling = {s: m for s, m in freshness.STAGE_MODULE.items()
                if freshness._origin(m) is None}
    assert not dangling, f"해석 불가 모듈 경로: {dangling}"


def test_every_analyzer_has_valid_tier():
    for a in registry.ANALYZERS:
        assert a.tier in registry.TIERS, (a.name, a.tier)


def test_tier_honesty_pins():
    """D5 정직화: select는 engine이지만 공유 채점 기판 = substrate.
    제품 엔진 3종만 product."""
    assert registry.get("select").tier == "substrate"
    for name in ("portrait", "likeness", "highlight"):
        assert registry.get(name).tier == "product", name
    for name in ("detect", "landmarks", "tubelets", "features", "emotion"):
        assert registry.get(name).tier == "substrate", name


def test_artifact_tiers_cover_shared_traces():
    for art in ("gate_trace.parquet", "candidates.jsonl", "detections.parquet",
                "likeness.json", "detect.mp4", "run.json"):
        assert art in registry.ARTIFACT_TIERS, art


def test_classify_clip_files(tmp_path):
    (tmp_path / "likeness.json").write_text("{}")
    (tmp_path / "run.json").write_text("{}")
    (tmp_path / "detect.mp4").write_bytes(b"")
    (tmp_path / "crops").mkdir()
    (tmp_path / "mystery.bin").write_bytes(b"")
    got = registry.classify_clip_files(tmp_path)
    assert got["likeness.json"] == "product"
    assert got["run.json"] == "ops"
    assert got["detect.mp4"] == "surface"
    assert got["crops/"] == "substrate"
    assert got["mystery.bin"] == "unclassified"       # 미지 항목 = 정직한 미분류


def test_manifest_writer(tmp_path):
    from momentscan.store.stash import write_manifest
    p = write_manifest(tmp_path, "clipX", {"schema": "momentscan.manifest/v0",
                                           "tiers": {"likeness.json": "product"}})
    import json
    rec = json.loads(Path(p).read_text())
    assert rec["schema"] == "momentscan.manifest/v0"
    assert rec["tiers"]["likeness.json"] == "product"


def test_infra_exclusion_covers_store_package():
    """T4 가드: store/(IO 배관)는 스테이지 임포트 클로저에서 제외 — 제외가 깨지면
    stash 한 줄 수정이 전 산출물을 stale로 만든다(감사 지뢰: INFRA parts[1] 매칭).
    crops는 store.stash와 extraction.media를 둘 다 임포트하는 실측 표본."""
    closure = freshness._closure_modules("momentscan.subjects.crops")
    assert not any(m.startswith("momentscan.store") for m in closure), closure
    assert "momentscan.extraction.media" in closure       # 픽셀 규약은 추적 유지

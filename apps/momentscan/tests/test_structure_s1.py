"""struct-s1 핀 — 선언 가드(D1 assert 확장)·R12 tier·manifest (2026-07-15 구조 감사).

fail-fast 원칙(code-style §3): 선언이 어긋나면 import에서 지참물과 함께 죽는다 —
이 핀들은 그 가드 자체가 살아 있음을 고정한다."""
from pathlib import Path

from momentscan.infra.pipeline import freshness, registry


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
    from momentscan.infra.store.stash import write_manifest
    p = write_manifest(tmp_path, "clipX", {"schema": "momentscan.manifest/v0",
                                           "tiers": {"likeness.json": "product"}})
    import json
    rec = json.loads(Path(p).read_text())
    assert rec["schema"] == "momentscan.manifest/v0"
    assert rec["tiers"]["likeness.json"] == "product"


def test_infra_exclusion_covers_store_package():
    """T4 가드: infra/store/(IO 배관)는 스테이지 임포트 클로저에서 제외 — 제외가
    깨지면 stash 한 줄 수정이 전 산출물을 stale로 만든다(A″ 지뢰: INFRA 접두 매칭이
    infra.store 만 집고 infra.media/pipeline 은 남겨야 한다).
    crops는 infra.store.stash와 infra.media를 둘 다 임포트하는 실측 표본."""
    closure = freshness._closure_modules("momentscan.perception.subjects.crops")
    assert not any(m.startswith("momentscan.infra.store") for m in closure), closure
    assert "momentscan.infra.media" in closure       # 픽셀 규약은 추적 유지


def test_classify_corpus_clip_no_unclassified():
    """G3: 코퍼스 클립(test_3)의 top-level 산출물이 전부 tier 를 갖는다 — unclassified =
    무소유 잔재(EXTRA_ARTIFACT_TIERS 등재 누락). 코퍼스 없으면 skip."""
    import pytest
    clip = Path(__file__).resolve().parents[3] / "output" / "l2" / "test_3"
    if not clip.is_dir():
        pytest.skip("corpus clip output/l2/test_3 absent")
    unclassified = [k for k, v in registry.classify_clip_files(clip).items() if v == "unclassified"]
    assert not unclassified, f"무소유 산출물(EXTRA_ARTIFACT_TIERS 등재 필요): {unclassified}"


def test_docs_cite_live_source_paths():
    """G4: docs 가 인용하는 apps/momentscan/src/... 경로는 실존해야 한다 — 이동(T6/T7)
    후 죽은 경로 인용 방지(선언=주소; 주소가 거짓말하면 문서가 침식, D6). 계획/레거시
    경로는 이 패턴 밖으로 표기(§ contracts.py 미구축 · portrait981 레거시)."""
    import re
    root = Path(__file__).resolve().parents[3]
    pat = re.compile(r"apps/momentscan/src/momentscan/[A-Za-z0-9_/]+\.py")
    dead: list[str] = []
    for md in (root / "docs").rglob("*.md"):
        for m in pat.findall(md.read_text(encoding="utf-8")):
            if not (root / m).is_file():
                dead.append(f"{md.relative_to(root)}: {m}")
    assert not dead, "docs 가 죽은 소스 경로 인용:\n  " + "\n  ".join(sorted(set(dead)))

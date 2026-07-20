"""R5 artifact-edge freshness — 순수 함수 + 선언-파생 간선 해석 테스트."""
from momentscan.infra.pipeline.runner import RUNNERS, _upstream_probes
from momentscan.infra.pipeline.freshness import artifact_stale


def test_artifact_stale_pure_cases():
    assert artifact_stale(100.0, []) is False              # 상류 없음 → fresh
    assert artifact_stale(100.0, [50.0, 99.0]) is False    # 전부 과거 → fresh
    assert artifact_stale(100.0, [50.0, 100.5]) is True    # 하나라도 미래 → stale
    assert artifact_stale(100.0, [100.0]) is False         # 동일 mtime = eps 안 → fresh


def test_upstream_probes_resolve_from_declarations():
    # likeness: fashion/parse/landmarks + gates (공유 valid 소비 — R10 이후 gate_trace;
    # R11 수리로 portrait 헛간선 제거, 실제 read = gate_trace.parquet)
    lk = set(_upstream_probes("likeness"))
    assert {"fashion.json", "parse.parquet", "landmarks.parquet",
            "gate_trace.parquet"} <= lk
    assert "portraits/portrait.json" not in lk
    # detect(비-RUNNER 상류)는 선언 artifact로 해석
    assert "detections.parquet" in _upstream_probes("attribute")
    # sibling-write 가드: select 간선은 공유 candidates.jsonl이 아니라 자기 probe
    assert "select.json" in _upstream_probes("highlight")
    assert "candidates.jsonl" not in _upstream_probes("highlight")


def test_upstream_probes_only_runner_or_ingest_artifacts():
    """해석 결과는 전부 실제 probe/선언 파일 — 디렉토리·inline 없음."""
    for name in RUNNERS:
        for p in _upstream_probes(name):
            assert p != "inline" and not p.endswith("/")


def test_unknown_name_empty():
    assert _upstream_probes("nope") == ()

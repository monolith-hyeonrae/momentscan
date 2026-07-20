"""R6·G9 — wire 계약(infra/contracts.py) 형태 검증 핀.

L3 헛점 폐쇄의 가드: egress 산출물이 계약 형태를 벗어나면 생산 지점에서 raise 한다.
코퍼스 전수 decode(현재 산출물이 v1 계약을 실제로 만족) + 인위 위반이 raise 하는지."""
import copy
import json
from pathlib import Path

import msgspec
import pytest

from momentscan.infra.contracts import (
    ContractViolation,
    LikenessV1,
    ResultV1,
    validate_likeness,
    validate_result,
)

_ROOT = Path(__file__).resolve().parents[3]
_CORPUS = _ROOT / "output" / "l2"


def _likeness_clips():
    return sorted(_CORPUS.glob("*/likeness.json")) if _CORPUS.is_dir() else []


def test_corpus_likeness_all_decode():
    """G9 가드: 코퍼스 15클립 likeness.json 이 전부 C11/LikenessV1 로 decode 된다 —
    현재 산출물이 계약을 실제로 만족함의 실측. 코퍼스 없으면 skip."""
    clips = _likeness_clips()
    if not clips:
        pytest.skip("corpus output/l2/*/likeness.json absent")
    bad = []
    for p in clips:
        try:
            msgspec.json.decode(p.read_bytes(), type=LikenessV1)
        except msgspec.ValidationError as e:
            bad.append(f"{p.parent.name}: {e}")
    assert not bad, "likeness.json 계약 위반:\n  " + "\n  ".join(bad)


def _sample_likeness() -> dict:
    clips = _likeness_clips()
    if not clips:
        pytest.skip("corpus absent")
    return json.loads(clips[0].read_text())


def test_likeness_missing_top_field_raises():
    rec = _sample_likeness()
    del rec["clip_id"]
    with pytest.raises(ContractViolation) as ei:
        validate_likeness(rec, clip_id="synthetic")
    assert "clip_id" in str(ei.value)          # 지참물 = 위반 필드


def test_likeness_missing_rider_field_raises():
    rec = _sample_likeness()
    tid = next(iter(rec["riders"]))
    del rec["riders"][tid]["center"]           # C11 필수 rider 필드
    with pytest.raises(ContractViolation):
        validate_likeness(rec, clip_id="synthetic")


def test_likeness_wrong_type_raises():
    rec = _sample_likeness()
    tid = next(iter(rec["riders"]))
    rec["riders"][tid]["n_obs"] = "many"       # int → str 위반
    with pytest.raises(ContractViolation):
        validate_likeness(rec, clip_id="synthetic")


_VALID_RESULT = {
    "schema": "momentscan.result/v1", "clip_id": "c", "ok": True, "failure": None,
    "node": "10.0.0.1:18080", "report_url": "http://10.0.0.1:18080/reports/c/",
    "output_prefix": "output/l2/c", "outputs": {"likeness": ["output/l2/c/likeness.json"]},
    "products_open": ["likeness"], "products_requested": ["likeness"],
    "n_ran": 0, "n_skipped": 13, "elapsed_s": 0.1, "finished_at_iso": "2026-07-20T00:00:00+00:00",
}


def test_result_valid_passes():
    validate_result(copy.deepcopy(_VALID_RESULT), clip_id="c")   # no raise


def test_result_missing_field_raises():
    rec = copy.deepcopy(_VALID_RESULT)
    del rec["report_url"]
    with pytest.raises(ContractViolation) as ei:
        validate_result(rec, clip_id="c")
    assert "report_url" in str(ei.value)


def test_result_wrong_type_raises():
    rec = copy.deepcopy(_VALID_RESULT)
    rec["n_ran"] = "zero"
    with pytest.raises(ContractViolation):
        validate_result(rec, clip_id="c")

"""R2 특성화 테스트 — R0(2026-07-08) 기준값 고정.

기준값 출처 = refactor-exec-plan.md §5 R0-4 (2026-07-07 세션 실측).
코퍼스(output/l2)가 없는 환경에서는 전체 skip — 행동 고정은 코퍼스 보유 노드의 몫.
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
L2 = ROOT / "output" / "l2"

pytestmark = pytest.mark.skipif(
    not (L2 / "test_3" / "likeness.json").exists(), reason="corpus not present"
)


def _likeness(clip: str) -> dict:
    return json.loads((L2 / clip / "likeness.json").read_text(encoding="utf-8"))


def test_test3_schema_and_rider_scope():
    lk = _likeness("test_3")
    assert lk["schema"] == "momentscan.likeness/v1"
    assert set(lk["riders"]) == {"0"}              # main-only 방출 (2026-07-07 스코프)
    r = lk["riders"]["0"]
    assert r["role"] == "main"
    assert r["n_obs"] == 648


def test_test3_face_id_honesty_fields():
    fid = _likeness("test_3")["riders"]["0"]["face_id"]
    assert fid["coherence_p05"] == pytest.approx(0.752, abs=1e-3)
    assert fid["low_confidence"] is False          # P1-④ⓑ: main 전원 floor 위


def test_test3_fashion_fused_verdict():
    fa = _likeness("test_3")["riders"]["0"]["fashion"]
    assert fa["mask"] is False
    assert fa["mask_override"] is None             # 비발화 클립은 명시적 None


def test_test3_samples_hair():
    hair = _likeness("test_3")["riders"]["0"]["samples"]["hair"]
    assert hair["n_frames"] == 12
    assert hair["observable"] is True
    assert hair["visible_frac"] == pytest.approx(0.881, abs=1e-3)


def test_test3_samples_selection_policy():
    """⑨ 표본 선발 정책 provenance (원장 ⑨, track/lk-sampling). 코퍼스가 신정책으로
    갱신되면 활성화 — 구 코퍼스(selection 필드 부재)에서는 skip 한다(공유 코퍼스 스윕은
    머지 후가 지불: CLAUDE.md 트랙-스코프). 로직 자체의 회귀 그물은 test_face_signals.py."""
    smp = _likeness("test_3")["riders"]["0"]["samples"]
    sel = smp.get("selection")
    if sel is None:
        pytest.skip("corpus predates ⑨ (samples.selection 부재) — 머지 후 스윕이 채운다")
    assert sel["policy"] == "frontal-pupil-calm/v1"
    assert len(smp["center_nearest"]) == 3 and all(isinstance(f, int) for f in smp["center_nearest"])
    assert set(smp["pose_bins"]) <= {"frontal", "left", "right"}


def test_test3_color_identity_palette():
    ci = _likeness("test_3")["riders"]["0"]["color_identity"]
    assert ci["primary"]["hex"] == "#140e11"


def test_test3_separation_shape():
    sep = _likeness("test_3")["separation"]
    assert isinstance(sep, list)
    for row in sep:
        assert {"tracks", "dist", "ratio_vs_drift"} <= set(row)


def test_dual3_scarf_override_fired():
    """P1-④ⓐ 두-레인 융합의 유일한 라이브 발화 — scarf가 parse FP를 기각."""
    fa = _likeness("dual_3")["riders"]["0"]["fashion"]
    assert fa["mask"] is False
    assert fa["mask_override"]["winner"] == "scarf"


def test_mask2_true_wearer_preserved():
    """융합이 진짜 착용자를 죽이지 않는다."""
    assert _likeness("mask_2")["riders"]["0"]["fashion"]["mask"] is True


def test_test12_hair_unobservable():
    """세그 측정 frac 0.0 (⚠user 교정: 오검출 의심 — 값은 고정하되 의미는 조사 중)."""
    hair = _likeness("test_12")["riders"]["0"]["samples"]["hair"]
    assert hair["observable"] is False


def test_run_json_stage_names():
    rj = json.loads((L2 / "test_3" / "run.json").read_text(encoding="utf-8"))
    names = {s["name"] if isinstance(s, dict) else s for s in rj["stages"]}
    assert {"fashion", "parse", "likeness", "portrait", "highlight"} <= names

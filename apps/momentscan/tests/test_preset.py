"""G7·G8 — preset(C9) 값 동결 + 이주 상수의 단일홈 강제.

G7 = race981 값 전수 특성화 핀(1차 이주값 전부; import-time assert 보다 강한 동결 장치,
msgspec 없이 성립). G8 = AST authority — 이주된 상수명이 preset/ 밖에서 숫자 리터럴로
재정의되면 실패(R15 문법 재사용; "단일홈이라는 주장을 주장이 아니라 검사로")."""
import ast
from pathlib import Path

import pytest

from momentscan.perception.readings import pose
from momentscan.preset import DEFAULT, RACE981, Preset, resolve
from momentscan.products import likeness

_SRC = Path(__file__).resolve().parents[1] / "src" / "momentscan"


# ── G7: race981 값 전수 특성화 (1차 이주값 동결) ──────────────────────────────
def test_race981_camera_values():
    assert RACE981.camera.frontal_deg == 12.0
    assert RACE981.camera.bin_edge_deg == 15.0


def test_race981_likeness_values():
    lk = RACE981.likeness
    assert lk.f_eyewear == 0.03
    assert lk.f_sun_lum == 0.7
    assert lk.f_mask == 0.01
    assert lk.f_hat == 0.05
    assert lk.f_worn == 0.5
    assert lk.f_min_judgeable == 10
    assert lk.f_fuse_tau == 0.75
    assert lk.hair_obs_tau == 0.1
    assert lk.face_id_min_frontal == 10
    assert lk.face_id_p05_floor == 0.5


def test_preset_frozen_and_default():
    assert DEFAULT == "race981"
    assert isinstance(RACE981, Preset)
    with pytest.raises(Exception):        # frozen dataclass — 대입 불가
        RACE981.camera.frontal_deg = 99.0


def test_resolve_unknown_raises():
    assert resolve("race981") is RACE981
    with pytest.raises(ValueError) as ei:
        resolve("nope")
    assert "nope" in str(ei.value)        # 지참물 = 이름


# ── 값-불변: 소비처 재바인딩이 preset 을 정확히 경유한다 (드리프트 0) ──────────
def test_consumers_rebind_to_preset():
    assert pose.CAMERA_FRONTAL_DEG == RACE981.camera.frontal_deg
    assert likeness.BIN_EDGE_DEG == RACE981.camera.bin_edge_deg
    assert likeness.FACE_ID_MIN_FRONTAL == RACE981.likeness.face_id_min_frontal
    assert likeness.FACE_ID_P05_FLOOR == RACE981.likeness.face_id_p05_floor
    assert likeness._F_EYEWEAR == RACE981.likeness.f_eyewear
    assert likeness._F_SUN_LUM == RACE981.likeness.f_sun_lum
    assert likeness._F_MASK == RACE981.likeness.f_mask
    assert likeness._F_HAT == RACE981.likeness.f_hat
    assert likeness._F_WORN == RACE981.likeness.f_worn
    assert likeness._F_MIN_JUDGEABLE == RACE981.likeness.f_min_judgeable
    assert likeness._F_FUSE_TAU == RACE981.likeness.f_fuse_tau
    assert likeness._HAIR_OBS_TAU == RACE981.likeness.hair_obs_tau


# ── G8: AST authority — 이주 상수는 preset/ 밖에서 리터럴로 재정의 금지 ────────
_MIGRATED = {
    "CAMERA_FRONTAL_DEG", "BIN_EDGE_DEG", "FACE_ID_MIN_FRONTAL", "FACE_ID_P05_FLOOR",
    "_F_EYEWEAR", "_F_SUN_LUM", "_F_MASK", "_F_HAT", "_F_WORN",
    "_F_MIN_JUDGEABLE", "_F_FUSE_TAU", "_HAIR_OBS_TAU",
}


def _is_number(node) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return _is_number(node.operand)      # 음수 리터럴 (-12.0)
    return False


def test_migrated_constants_not_redefined_as_literals():
    offenders: list[str] = []
    for py in _SRC.rglob("*.py"):
        if "preset" in py.relative_to(_SRC).parts:   # preset/ 는 값의 정본 — 제외
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            # target/value 를 병렬 검사 (스칼라 + 튜플 언패킹 literal 둘 다)
            for tgt in node.targets:
                names = tgt.elts if isinstance(tgt, ast.Tuple) else [tgt]
                vals = node.value.elts if isinstance(node.value, ast.Tuple) else [node.value]
                pairs = zip(names, vals) if len(names) == len(vals) else [(n, node.value) for n in names]
                for n, v in pairs:
                    if isinstance(n, ast.Name) and n.id in _MIGRATED and _is_number(v):
                        offenders.append(f"{py.relative_to(_SRC)}:{n.lineno} {n.id} = <literal>")
    assert not offenders, "이주 상수의 리터럴 재정의(단일홈=preset/ 밖):\n  " + "\n  ".join(offenders)

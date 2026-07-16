"""R9 — ruff 검사만, baseline 비율제 (code-style.md enforcement).

baseline(2026-07-16 갱신, struct-s2가 75→58로 감소) = 58건 (E702 48 · C901 7 · E701 7 · F401 5 · F541 4 ·
E402 2 · E741 1 · F841 1 — F821 1건은 실버그로 즉시 수리: inspector read_scene
임포트 누락). 소급 리포맷 금지 — 이 테스트는 **신규 위반**만 막는다:
카운트가 baseline을 넘으면 실패, 줄이는 것은 언제나 환영(줄면 baseline도 갱신)."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BASELINE = 58

SRC = Path(__file__).resolve().parents[1] / "src" / "momentscan"


def test_ruff_violations_do_not_grow():
    if shutil.which("ruff") is None and subprocess.run(
            [sys.executable, "-m", "ruff", "--version"], capture_output=True).returncode != 0:
        pytest.skip("ruff not installed")
    r = subprocess.run([sys.executable, "-m", "ruff", "check", str(SRC)],
                       capture_output=True, text=True)
    n = sum(1 for line in r.stdout.splitlines() if line.startswith("Found "))
    # "Found N errors." 파싱 — 없으면 0건 통과
    import re
    m = re.search(r"Found (\d+) error", r.stdout)
    count = int(m.group(1)) if m else 0
    assert count <= BASELINE, (
        f"ruff 위반 {count}건 > baseline {BASELINE} — 신규 위반을 고치거나, "
        f"의도된 예외면 pyproject [tool.ruff]에 근거와 함께 반영하라")

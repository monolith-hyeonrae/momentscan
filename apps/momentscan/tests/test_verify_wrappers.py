"""기존 verify CLI를 pytest 그물에 편입 — L2(enforcement 절반) 수리의 최소 단위.

replay는 코퍼스·시간이 필요해 제외(수동/R0 절차); registry·api는 수 초라 상시.
"""
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BIN = ROOT / ".venv" / "bin" / "momentscan"

pytestmark = pytest.mark.skipif(not BIN.exists(), reason="venv CLI not present")


def test_verify_registry_clean():
    r = subprocess.run([str(BIN), "verify", "registry"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr


def test_verify_api_contract():
    r = subprocess.run([str(BIN), "verify", "api"], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr

"""CLI 관문 — 실체는 infra/cli/ 패키지 (구조 감사 접수 #5, 2026-07-15 분할; A″에서 infra/ 편입)."""
from momentscan.infra.cli import main

if __name__ == "__main__":
    raise SystemExit(main())

"""momentscan — three products (likeness · portrait · highlight) over one shared
signal substrate, criterion-source switched: the criterion's source (subject →
author → context) picks its space (biometric → geometric → semantic). See
docs/products.md (definitions) and docs/criterion-source.md (the lens).

The package layout mirrors the architecture — A″ grouping (2026-07-16/17): each
top directory answers one FAMILY of question. infra/ (돌게 하는 기계·졸업석:
cli·serve·pipeline·store·media) · perception/ (픽셀→믿을 수 있는 읽기:
subjects·extraction·readings·gates) · products/ (세 가치 질문의 답 + 공유 채점
기판 select + evals) · surface/ (렌더) · verify/ (자기신뢰). The layout contract,
the direction table, membership tests, isolation ladder and graduation rules live
in ARCHITECTURE.md (repo root) — the single truth this docstring only points to.
"""

from momentscan.infra.store.ports import FeatureSource, TrackFeatures, Tubelet
from momentscan.infra.store.telemetry import CandidateLog

__all__ = ["FeatureSource", "Tubelet", "TrackFeatures", "CandidateLog"]

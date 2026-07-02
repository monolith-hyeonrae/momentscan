"""momentscan — three products (likeness · portrait · highlight) over one shared
signal substrate, criterion-source switched: the criterion's source (subject →
author → context) picks its space (biometric → geometric → semantic). See
docs/products.md (definitions) and docs/criterion-source.md (the lens).

The package layout mirrors the architecture — each directory answers one
question (extraction=signals · subjects=what they attach to · domains=how
measurements are interpreted · gates=verdicts · products=deliverables ·
surface=rendering · verify=self-trust). The layout contract, membership tests,
isolation ladder and graduation rules live in ARCHITECTURE.md (repo root) —
the single truth this docstring only points to.
"""

from momentscan.ports import FeatureSource, TrackFeatures, Tubelet
from momentscan.telemetry import CandidateLog

__all__ = ["FeatureSource", "Tubelet", "TrackFeatures", "CandidateLog"]

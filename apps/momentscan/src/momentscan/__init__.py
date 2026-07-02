"""momentscan — three products (likeness · portrait · highlight) over one shared
signal substrate, criterion-source switched: the criterion's source (subject →
author → context) picks its space (biometric → geometric → semantic). See
docs/products.md (definitions) and docs/criterion-source.md (the lens).

The package layout mirrors the architecture (2026-07-02 restructure):
  stages/   L0-L1 extraction (every DAG node; heavy model backends live in the
            isolated ``plugins/`` workspace packages behind the FeatureSource port)
  domains/  L2 signal-domain policy (fusion · quantizers · thresholds)
  gates.py  L3 the declared gate ladder → gate_trace
  products/ L4 engines · surface/ frontend · verify/ replay-freshness-eval
  stash.py  the storage port every stage hands off through

(The dormant Track B / vjepa package under plugins/ is the reserved seam of the
original two-track FeatureSource design — jepa-poc.md, deferred research.)
"""

from momentscan.features import FeatureSource, TrackFeatures, Tubelet
from momentscan.telemetry import CandidateLog

__all__ = ["FeatureSource", "Tubelet", "TrackFeatures", "CandidateLog"]

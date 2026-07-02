"""Track B FeatureSource — frozen V-JEPA 2 embeddings per track tubelet.

Isolated package / venv: torch / V-JEPA stack (conflicts with Track A's
onnx / mediapipe; may run on RunPod A100). **Frozen backbone only — NO custom
pretraining** (jepa-poc.md §3). Implements ``momentscan.FeatureSource``: reads
tubelets from stash, extracts time-indexed embeddings, writes ``TrackFeatures``
back to stash — the same downstream path as Track A.

Wiring lands in Phase 4.
"""

from __future__ import annotations

from momentscan import TrackFeatures, Tubelet


class VJEPAFeatures:
    """Implements momentscan.FeatureSource (Phase 4)."""

    name = "vjepa"
    feature_space = "vjepa"
    dim = -1  # set from the loaded checkpoint

    def extract(self, tubelet: Tubelet) -> TrackFeatures:
        raise NotImplementedError("Phase 4")

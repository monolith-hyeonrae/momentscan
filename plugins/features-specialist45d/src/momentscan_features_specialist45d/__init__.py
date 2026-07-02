"""Track A FeatureSource — specialist ensemble -> 45D signal vector per track frame.

Isolated package / venv: onnx / mediapipe / insightface stack (conflicts with
Track B's torch). Implements ``momentscan.FeatureSource``. Reads tubelets from
stash, runs the visualpath specialist plugins (face-detect / expression /
landmarks / head-pose) + visualbind to assemble the 45D vector, writes
``TrackFeatures`` back to stash. Missing signals stay NaN (Appendix A4).

Wiring lands in Phase 3.
"""

from __future__ import annotations

from momentscan import TrackFeatures, Tubelet


class Specialist45D:
    """Implements momentscan.FeatureSource (Phase 3)."""

    name = "specialist45d"
    feature_space = "specialist45d"
    dim = 45

    def extract(self, tubelet: Tubelet) -> TrackFeatures:
        raise NotImplementedError("Phase 3")

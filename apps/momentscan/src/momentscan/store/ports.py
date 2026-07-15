"""FeatureSource — the ONE component that differs between Track A and Track B.

Track A feeds the shared ``Distribution`` a 45D specialist-signal vector per
track frame; Track B feeds V-JEPA embeddings. Everything downstream
(Distribution, readings, eval harness) is identical — that identity is exactly
what makes the A-vs-B comparison fair (jepa-poc.md §2, Appendix A0).

A FeatureSource lives in its own isolated package / venv because the two stacks
conflict (onnx/mediapipe vs torch). It runs as a *decoupled stage*: reads
tubelets from stash, writes per-track features back to stash (the offline L1/L2
decoupling), so one track's heavy venv never has to coexist with the other's.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np


@dataclass(frozen=True)
class Tubelet:
    """One person's track within one clip — the Step 0 output unit.

    The atomic downstream unit is ``(clip_id, track_id, rider_role)``
    (jepa-poc.md §6 Step 0). ``frame_indices`` are the ordered, time-indexed
    source-frame indices for this track; gaps (occlusion) are allowed and
    expected. Crops are carried out-of-band (stash paths), not inline.
    """

    clip_id: str
    track_id: int
    rider_role: str            # "main" | "auxiliary" (depth-primary; Appendix A2)
    frame_indices: np.ndarray  # (T,) int


@dataclass(frozen=True)
class TrackFeatures:
    """Per-track, time-indexed feature matrix in one feature space.

    ``features`` rows may be partial: a missing signal is ``NaN``, not a
    dropped row — the Distribution's robust centroid down-weights it
    (Appendix A4; this is why there is no occlusion detector and no n=0 bug).
    """

    clip_id: str
    track_id: int
    rider_role: str
    feature_space: str         # "specialist45d" | "vjepa"
    frame_indices: np.ndarray  # (T,)
    features: np.ndarray       # (T, D) float; missing -> NaN


@runtime_checkable
class FeatureSource(Protocol):
    """A track-specific feature extractor. Implemented in an isolated package."""

    name: str
    feature_space: str
    dim: int

    def extract(self, tubelet: Tubelet) -> TrackFeatures: ...

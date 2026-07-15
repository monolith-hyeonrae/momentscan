"""Candidate-log — a telemetry-ready record per served candidate (jepa-poc.md §8).

There is no sales/feedback loop yet, but we log now so the self-improvement loop
attaches later with **no schema migration**. When the product later offers
buy / choose / skip, this log becomes the free, label-free reward signal that
closes the loop.

The timestamp is caller-supplied (ISO8601) so the record is pure data and
trivially testable — the library never reads the clock itself.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class CandidateLog:
    """One served candidate (a Profile pick or a Highlight segment) for one rider."""

    clip_id: str
    track_id: int
    rider_role: str                      # "main" | "auxiliary"
    product: str                         # "likeness" | "highlight" | "portrait" | "portrait_set"
    track: str                           # "A" | "B" — which FeatureSource produced it
    pick: dict[str, Any]                 # chosen candidate (frame id, or segment span)
    timestamp: str                       # ISO8601, stamped by the caller
    alternatives: list[dict[str, Any]] = field(default_factory=list)  # ranked runners-up
    scores: dict[str, float] = field(default_factory=dict)            # scores behind the pick

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

"""momentscan core — track-agnostic selection + eval over a swappable FeatureSource.

Reoriented 2026-06-08 onto the JEPA PoC (see ../../docs/jepa-poc.md): this repo
is the Track A / Track B *selection + eval* site. Heavy, mutually-conflicting
feature extractors live in isolated packages under ``plugins/``; this core stays
light and shared so the two tracks run the same Distribution, readings, and eval
harness — directly comparable.
"""

from momentscan.features import FeatureSource, TrackFeatures, Tubelet
from momentscan.telemetry import CandidateLog

__all__ = ["FeatureSource", "Tubelet", "TrackFeatures", "CandidateLog"]

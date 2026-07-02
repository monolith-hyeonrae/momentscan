"""scene stage — thin adapter over the isolated specialist45d DINO backend.

Stage NODE here (``ls stages/`` = the full DAG vocabulary); the model BACKEND
(DINO CLS frame-grain scene stream, E012) lives in
``plugins/features-specialist45d`` alongside the 46-dim extractor — see
stages/features.py for why the split exists (dependency seam · FeatureSource
port · service-worker boundary; not an architecture layer).
"""
from __future__ import annotations


def extract_scene(path, out_root, *, fps: int = 6) -> dict:
    """video → scene.parquet (clip-level, rider-free scene embeddings). Raises
    ImportError when the specialist45d package is not installed."""
    from momentscan_features_specialist45d.scene import extract_scene as _extract

    return _extract(path, out_root, fps=fps)

"""features stage — thin adapter over the isolated specialist45d extractor.

The stage NODE lives here so ``ls extraction/`` shows the full DAG vocabulary; the
model BACKEND (HSEmotion em_* · LibreFace AU · DPR-SH · the 46-dim registry
contract) lives in ``plugins/features-specialist45d`` — an isolated workspace
package, the same relation as the visualstack plugins behind detect/landmarks.
The isolation is a dependency seam (heavy model stacks), the FeatureSource swap
port (Track B / vjepa reserved), and a future service-worker boundary — NOT an
architecture layer: both sides are L1 extraction.
"""
from __future__ import annotations


def extract_features(path, out_root, *, fps: int = 6) -> dict:
    """tubelets → features/<track>.parquet (46-dim per-frame). Raises ImportError
    when the specialist45d package is not installed (CLI turns that into a hint)."""
    from momentscan_features_specialist45d.extractor import extract_clip

    return extract_clip(path, out_root, fps=fps)

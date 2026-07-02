"""3b — per-(clip, track) Distribution over the active feature subspace.

``SignalStatistics.update`` skips any NaN-containing vector (weak-prior), so a
46D matrix with 34 all-NaN dims would skip every row. The fit therefore selects
the ACTIVE dims (those with any data) and fits the subspace — when new
specialist dims arrive, the subspace widens with zero code change here.

Phase-conditioned by contract ([[phase-conditioned-readings]]): the Highlight
baseline is the person's RIDE norm; mixing still/moving regimes inflates Σ.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import polars as pl

from visualbind import SignalStatistics

from momentscan.stash import read_features, read_tubelets


@dataclass
class TrackDistribution:
    clip_id: str
    track_id: int
    rider_role: str
    phase: str
    active_dims: np.ndarray      # indices into the 46D registry
    stats: SignalStatistics      # fitted on the active subspace
    n_rows: int
    n_skipped: int               # rows with NaN inside the active subspace

    def center(self) -> np.ndarray:
        return self.stats.mean

    def mahalanobis(self, vec46: np.ndarray) -> float:
        return float(self.stats.mahalanobis(vec46[self.active_dims]))


def fit_track(out_root, clip_id: str, track_id: int, *, phase: str = "ride") -> TrackDistribution:
    feats = read_features(out_root, clip_id, "A").filter(pl.col("track_id") == track_id)
    tubes = read_tubelets(out_root, clip_id).filter(pl.col("track_id") == track_id)
    phase_by_frame = dict(zip(tubes["frame_idx"], tubes["scene_phase"], strict=True))
    keep = [phase_by_frame.get(f) == phase for f in feats["frame_idx"].to_list()]
    m = np.array(feats.filter(pl.Series(keep))["feature"].to_list(), dtype=np.float64)
    role = tubes["rider_role"][0]

    active = np.where(~np.isnan(m).all(axis=0))[0]
    sub = m[:, active]
    stats = SignalStatistics(dim=len(active))
    skipped = 0
    for row in sub:
        if np.isnan(row).any():
            skipped += 1
            continue
        stats.update(row)
    return TrackDistribution(clip_id, track_id, role, phase, active, stats,
                             n_rows=int(stats.n), n_skipped=skipped)

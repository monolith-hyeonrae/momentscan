"""Tests for SignalStatisticsCollector — buffering + commit + dump."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from visualbus import BBox, Detection, Frame
from visualbind import Normalizer

from momentscan_worker.statistics_collector import SignalStatisticsCollector


# ── helpers ──────────────────────────────────────────────────────────


def _normalizer() -> Normalizer:
    """Policy matching the current momentscan/policies/signal_ranges.json:
    both MediaPipe and 6DRepNet head-pose columns + the two common signals."""
    return Normalizer(
        {
            "expression__smile":         {"kind": "linear",   "min": 0.0, "max": 1.0},
            "face__detection_score":     {"kind": "linear",   "min": 0.0, "max": 1.0},
            "mediapipe__frontality":     {"kind": "linear",   "min": 0.0, "max": 1.0},
            "mediapipe__yaw_deg":        {"kind": "circular", "period_deg": 360.0},
            "mediapipe__pitch_deg":      {"kind": "circular", "period_deg": 360.0},
            "mediapipe__roll_deg":       {"kind": "circular", "period_deg": 360.0},
            "head_pose__frontality":     {"kind": "linear",   "min": 0.0, "max": 1.0},
            "head_pose__yaw_deg":        {"kind": "circular", "period_deg": 360.0},
            "head_pose__pitch_deg":      {"kind": "circular", "period_deg": 360.0},
            "head_pose__roll_deg":       {"kind": "circular", "period_deg": 360.0},
        }
    )


def _det(frame_id: int, det_id: int, *, track_id: int | None = 0, score: float = 0.9) -> Detection:
    return Detection(
        bbox=BBox(0.0, 0.0, 100.0, 100.0),
        score=score,
        frame_id=frame_id,
        detection_id=det_id,
        track_id=track_id,
    )


def _flush_after(collector: SignalStatisticsCollector, frame_id: int) -> None:
    """Simulate frame_id+1's frame/* arrival → commits frame_id's buffer."""
    next_frame = Frame.from_array(
        data=np.zeros((4, 4, 3), dtype=np.uint8),
        frame_id=frame_id + 1,
        t_ns=0,
    )
    collector.on_frame("frame/test", next_frame, bus=None)


def _push_full_frame(
    collector: SignalStatisticsCollector,
    *,
    frame_id: int,
    det_id: int = 0,
    track_id: int = 0,
    smile: float = 0.5,
    yaw: float = 0.0,
    pitch: float = 0.0,
    roll: float = 0.0,
    frontality: float = 1.0,
    det_score: float = 0.9,
) -> None:
    """Drive one full frame's worth of topics in deterministic order.

    Both head-pose sources (MediaPipe + 6DRepNet) get the same synthetic
    yaw/pitch/roll/frontality so all 10 raw columns are populated and the
    vector update fires.
    """
    collector.on_smile(
        "signal/expression__smile",
        {"frame_id": frame_id, "values": {det_id: smile}},
        bus=None,
    )
    pose_payload = {
        "frame_id": frame_id,
        "values": {
            det_id: {
                "frontality": frontality,
                "yaw_deg": yaw,
                "pitch_deg": pitch,
                "roll_deg": roll,
            },
        },
    }
    collector.on_mediapipe_pose("signal/face__frontality", pose_payload, bus=None)
    collector.on_head_pose_6drepnet("signal/face__head_pose", pose_payload, bus=None)
    collector.on_tracked(
        "signal/face__tracked",
        [_det(frame_id, det_id, track_id=track_id, score=det_score)],
        bus=None,
    )
    # Commit: the next frame's arrival is the signal that this frame's
    # plugin chain has finished (synchronous bus dispatch).
    _flush_after(collector, frame_id)


# ── construction / metadata ─────────────────────────────────────────


class TestConstruction:
    def test_initial_state(self) -> None:
        c = SignalStatisticsCollector(_normalizer())
        assert c.n_subjects == 0
        info = c.info()
        # 4 linear + 6 circular (×2 sin/cos) = 4 + 12 = 16
        assert info["dim"] == 16
        assert info["n_subjects"] == 0
        assert info["buffered_frames"] == 0

    def test_dim_matches_normalizer(self) -> None:
        c = SignalStatisticsCollector(_normalizer())
        assert c._dim == _normalizer().dim


# ── commit on tracked-detection arrival ──────────────────────────────


class TestCommit:
    def test_full_frame_creates_subject(self) -> None:
        c = SignalStatisticsCollector(_normalizer())
        _push_full_frame(c, frame_id=0, track_id=7)
        assert c.n_subjects == 1
        stats = c.statistics_for(7)
        assert stats is not None
        assert stats.n == 1

    def test_multiple_frames_accumulate(self) -> None:
        c = SignalStatisticsCollector(_normalizer())
        for fid in range(50):
            _push_full_frame(c, frame_id=fid, track_id=1, smile=0.4 + 0.001 * fid)
        assert c.n_subjects == 1
        stats = c.statistics_for(1)
        assert stats.n == 50
        # Eigendecomp must have updated K dynamically — at least 1 axis.
        assert stats.top_k_for_variance() >= 1

    def test_untracked_detection_is_skipped(self) -> None:
        c = SignalStatisticsCollector(_normalizer())
        # frontality + smile in buffer, but tracked arrives with track_id=None.
        c.on_smile(
            "signal/expression__smile",
            {"frame_id": 0, "values": {0: 0.5}},
            bus=None,
        )
        c.on_tracked(
            "signal/face__tracked",
            [_det(0, 0, track_id=None)],
            bus=None,
        )
        _flush_after(c, 0)
        assert c.n_subjects == 0

    def test_two_subjects_kept_separate(self) -> None:
        c = SignalStatisticsCollector(_normalizer())
        # Subject 1 stable smile near 0.2, subject 2 near 0.8.
        pose_zero = {"frontality": 1.0, "yaw_deg": 0, "pitch_deg": 0, "roll_deg": 0}
        for fid in range(20):
            c.on_smile(
                "signal/expression__smile",
                {"frame_id": fid, "values": {0: 0.2, 1: 0.8}},
                bus=None,
            )
            both_subjects_pose = {
                "frame_id": fid,
                "values": {0: pose_zero, 1: pose_zero},
            }
            c.on_mediapipe_pose("signal/face__frontality", both_subjects_pose, bus=None)
            c.on_head_pose_6drepnet("signal/face__head_pose", both_subjects_pose, bus=None)
            c.on_tracked(
                "signal/face__tracked",
                [_det(fid, 0, track_id=100), _det(fid, 1, track_id=200)],
                bus=None,
            )
            _flush_after(c, fid)
        assert c.n_subjects == 2
        # mean of smile (vector slot 0) reflects the per-subject input.
        mean_100 = c.statistics_for(100).mean
        mean_200 = c.statistics_for(200).mean
        # Linear [0,1] → [-1,1] so 0.2 → -0.6, 0.8 → +0.6.
        assert mean_100[0] == pytest.approx(-0.6, abs=1e-9)
        assert mean_200[0] == pytest.approx(0.6, abs=1e-9)

    def test_missing_smile_is_nan_and_skips_update(self) -> None:
        # If a topic the policy expects is absent for the frame, the
        # vector contains NaN and SignalStatistics.update() skips it.
        c = SignalStatisticsCollector(_normalizer())
        pose_payload = {
            "frame_id": 0,
            "values": {0: {"frontality": 1.0, "yaw_deg": 0, "pitch_deg": 0, "roll_deg": 0}},
        }
        c.on_mediapipe_pose("signal/face__frontality", pose_payload, bus=None)
        c.on_head_pose_6drepnet("signal/face__head_pose", pose_payload, bus=None)
        c.on_tracked(
            "signal/face__tracked",
            [_det(0, 0, track_id=42)],
            bus=None,
        )
        _flush_after(c, 0)
        # Subject created but n=0 (vector had NaN in expression__smile).
        assert c.n_subjects == 1
        assert c.statistics_for(42).n == 0

    def test_missing_one_pose_source_skips_update(self) -> None:
        # MediaPipe arrives but 6DRepNet doesn't (or vice versa) → head_pose__
        # columns NaN → vector NaN → skip. Documents the current "all-or-
        # nothing" semantics (task #26 to revisit).
        c = SignalStatisticsCollector(_normalizer())
        c.on_smile(
            "signal/expression__smile",
            {"frame_id": 0, "values": {0: 0.5}},
            bus=None,
        )
        c.on_mediapipe_pose(
            "signal/face__frontality",
            {
                "frame_id": 0,
                "values": {0: {"frontality": 1.0, "yaw_deg": 0, "pitch_deg": 0, "roll_deg": 0}},
            },
            bus=None,
        )
        # Note: on_head_pose_6drepnet *not* called for this frame.
        c.on_tracked(
            "signal/face__tracked",
            [_det(0, 0, track_id=99)],
            bus=None,
        )
        _flush_after(c, 0)
        assert c.n_subjects == 1
        assert c.statistics_for(99).n == 0


# ── buffer GC ────────────────────────────────────────────────────────


class TestBufferGC:
    def test_buffer_flushed_on_frame_event(self) -> None:
        c = SignalStatisticsCollector(_normalizer(), max_buffered_frames=3)
        # 100 frames of partial smile signal with no frame/* commit trigger
        # — buffer grows freely.
        for fid in range(100):
            c.on_smile(
                "signal/expression__smile",
                {"frame_id": fid, "values": {0: 0.5}},
                bus=None,
            )
        assert len(c._buffer) == 100  # commit hasn't fired yet
        # A late frame/* event commits everything < 200 (no track_id → no
        # subjects created), then the buffer is empty.
        _flush_after(c, 199)
        assert len(c._buffer) == 0
        assert c.n_subjects == 0


# ── parquet dump ─────────────────────────────────────────────────────


class TestDump:
    def test_empty_dump_writes_nothing(self, tmp_path: Path) -> None:
        c = SignalStatisticsCollector(_normalizer())
        out = tmp_path / "statistics.parquet"
        n = c.dump(out)
        assert n == 0
        assert not out.exists()

    def test_dump_one_subject(self, tmp_path: Path) -> None:
        c = SignalStatisticsCollector(_normalizer())
        for fid in range(40):
            _push_full_frame(c, frame_id=fid, track_id=7, smile=0.5 + 0.01 * fid)
        out = tmp_path / "statistics.parquet"
        n = c.dump(out)
        assert n == 1
        assert out.exists()
        df = pl.read_parquet(out)
        assert df.shape == (1, 7)  # subject_id, n, K, mean, eigvals, z, vec_cols
        row = df.row(0, named=True)
        assert row["subject_id"] == "7"
        assert row["n"] == 40
        assert len(row["mean"]) == 16
        assert len(row["eigenvalues"]) == 16
        assert len(row["sliding_z_latest"]) == 16
        assert row["vector_columns"][0] == "expression__smile"

    def test_teardown_dumps_when_output_path_set(self, tmp_path: Path) -> None:
        out = tmp_path / "statistics.parquet"
        c = SignalStatisticsCollector(_normalizer(), output_path=out)
        for fid in range(10):
            _push_full_frame(c, frame_id=fid, track_id=3)
        c.teardown()
        assert out.exists()
        df = pl.read_parquet(out)
        assert df.height == 1

    def test_teardown_noop_without_output_path(self, tmp_path: Path) -> None:
        c = SignalStatisticsCollector(_normalizer())  # output_path=None
        for fid in range(10):
            _push_full_frame(c, frame_id=fid, track_id=3)
        c.teardown()  # should not raise


# ── sliding window ──────────────────────────────────────────────────


class TestSlidingWindow:
    def test_z_score_visible_on_outlier(self) -> None:
        c = SignalStatisticsCollector(_normalizer(), sliding_window=10)
        for fid in range(9):
            _push_full_frame(c, frame_id=fid, track_id=1, smile=0.5)
        # Hard outlier — smile maxed.
        _push_full_frame(c, frame_id=9, track_id=1, smile=1.0)
        stats = c.statistics_for(1)
        z = stats.z_score_sliding()
        # First slot is expression__smile — must be a positive z score.
        assert z[0] > 1.0
        # Last slots (yaw/pitch/roll sin/cos) constant → z=0 by convention.
        assert all(abs(x) < 1e-9 or math.isnan(x) for x in z[3:])

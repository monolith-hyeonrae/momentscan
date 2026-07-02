"""SignalStatisticsCollector — per-subject visualbind accumulator on the bus.

Sink-only visualpath Module. Subscribes to the raw signal topics this
domain knows about, buffers per-``frame_id``, and commits per-subject
``Normalizer.transform`` → :meth:`SignalStatistics.update` when the
*next* frame arrives — by which point every plugin handler for the
previous frame has finished (the bus dispatches synchronously, DFS-
style, so all signal/* emissions for frame N complete before frame N+1
publishes).

A naïve "commit on signal/face__tracked arrival" doesn't work because
IoUTracker emits ``signal/face__tracked`` *inside* its
``on_detection`` handler, before face-landmarks / head-pose / face-
expression have run for the same frame — the buffer is empty at that
moment. Watching ``frame/*`` instead defers commit to the boundary
*after* a full chain.

Topic adapters are coded inline (a small ``if-elif`` table — see
``on_*_pose`` / ``on_tracked``). Each plugin's payload shape is its
own decision: adding a new plugin means a new adapter method here.
The *which-column-goes-where* policy stays in the JSON under
``momentscan/policies/`` and reaches us only via the injected
:class:`visualbind.Normalizer`.

Subject id mapping: ``subject_id = Detection.track_id`` for now. A
later face-cluster pass replaces this without touching the update path.

On :meth:`teardown` (or explicit :meth:`dump`), per-subject statistics
are written to a flat parquet — one row per subject with list columns
for the vector-valued state (mean / eigenvalues / sliding z).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, ClassVar

import polars as pl

from visualbus import Detection, Frame, VisualBus
from visualbind import Normalizer, SignalStatistics


_log = logging.getLogger("momentscan.statistics_collector")


class SignalStatisticsCollector:
    """Per-subject signal_statistics accumulator + parquet dumper."""

    name: ClassVar[str] = "signal_statistics_collector"
    version: ClassVar[str] = "0.0.0"
    license: ClassVar[str] = "TBD"
    description: ClassVar[str] = (
        "Buffers raw signal topics per frame_id, commits per-subject "
        "SignalStatistics updates on the next frame's arrival (after all "
        "plugin handlers have run), dumps statistics.parquet on teardown."
    )
    requires_gpu: ClassVar[bool] = False
    gpu_memory_mb: ClassVar[int] = 0

    inputs: ClassVar[dict[str, str]] = {
        "frame/*": "on_frame",                           # commit trigger
        "signal/face__tracked": "on_tracked",            # track_id + det.score
        "signal/expression__smile": "on_smile",
        "signal/face__frontality": "on_mediapipe_pose",  # MediaPipe head-pose
        "signal/face__head_pose": "on_head_pose_6drepnet",  # 6DRepNet
    }
    outputs: ClassVar[list[str]] = []  # sink-only

    def __init__(
        self,
        normalizer: Normalizer,
        *,
        sliding_window: int = 30,
        variance_target: float = 0.95,
        output_path: Path | None = None,
        max_buffered_frames: int = 4,
    ) -> None:
        self._normalizer = normalizer
        self._sliding_window = int(sliding_window)
        self._variance_target = float(variance_target)
        self._output_path = (
            Path(output_path).expanduser() if output_path is not None else None
        )
        self._dim = normalizer.dim
        self._max_buffered_frames = int(max_buffered_frames)

        # Per-frame buffer:
        # {frame_id: {"dets":   {det_id: {col_name: value}},
        #              "tracks": {det_id: track_id}}}
        self._buffer: dict[int, dict[str, dict]] = {}
        # Per-subject SignalStatistics (subject_id == track_id for now).
        self._stats: dict[int, SignalStatistics] = {}
        # Last frame_id we've *seen on the frame/* channel*; this is the
        # one we commit when the *next* frame arrives.
        self._last_committed: int = -1

    # ── lifecycle ────────────────────────────────────────────────────

    def info(self) -> dict[str, Any]:
        return {
            "dim": self._dim,
            "vector_columns": list(self._normalizer.vector_columns),
            "sliding_window": self._sliding_window,
            "variance_target": self._variance_target,
            "n_subjects": len(self._stats),
            "buffered_frames": len(self._buffer),
            "output_path": str(self._output_path) if self._output_path else None,
        }

    def teardown(self) -> None:
        # Commit any frames still pending — the source has stopped so no
        # frame/* event will trigger their commit.
        for fid in sorted(self._buffer):
            self._commit_frame(fid)
        self._buffer.clear()
        if self._output_path is not None:
            self.dump(self._output_path)

    # ── inspection ───────────────────────────────────────────────────

    @property
    def n_subjects(self) -> int:
        return len(self._stats)

    def statistics_for(self, subject_id: int) -> SignalStatistics | None:
        return self._stats.get(subject_id)

    # ── handlers ─────────────────────────────────────────────────────

    def on_frame(self, topic: str, frame: Frame, bus: VisualBus) -> None:
        """Commit-trigger handler. By the time frame N+1's frame/* arrives,
        every plugin handler for frame N (chain of synchronous publish
        calls) has finished — buffers are complete."""
        # Commit every buffered frame strictly older than the incoming
        # frame_id. Usually just one (the previous frame).
        stale = [fid for fid in self._buffer if fid < frame.frame_id]
        for fid in sorted(stale):
            self._commit_frame(fid)
        # Cap the buffer in case something went pathological (frame_id
        # going backward, or a frame skipped without prior emit).
        if len(self._buffer) > self._max_buffered_frames:
            cutoff = frame.frame_id - self._max_buffered_frames
            for fid in [f for f in self._buffer if f < cutoff]:
                self._buffer.pop(fid, None)

    def on_smile(self, topic: str, payload: dict, bus: VisualBus) -> None:
        buf = self._dets_buf(payload["frame_id"])
        for det_id, score in payload.get("values", {}).items():
            buf.setdefault(int(det_id), {})["expression__smile"] = float(score)

    def on_mediapipe_pose(self, topic: str, payload: dict, bus: VisualBus) -> None:
        """signal/face__frontality (MediaPipe) → mediapipe__ columns."""
        buf = self._dets_buf(payload["frame_id"])
        for det_id, values in payload.get("values", {}).items():
            det_buf = buf.setdefault(int(det_id), {})
            det_buf["mediapipe__frontality"] = _maybe_float(values.get("frontality"))
            det_buf["mediapipe__yaw_deg"] = _maybe_float(values.get("yaw_deg"))
            det_buf["mediapipe__pitch_deg"] = _maybe_float(values.get("pitch_deg"))
            det_buf["mediapipe__roll_deg"] = _maybe_float(values.get("roll_deg"))

    def on_head_pose_6drepnet(self, topic: str, payload: dict, bus: VisualBus) -> None:
        """signal/face__head_pose (6DRepNet) → head_pose__ columns."""
        buf = self._dets_buf(payload["frame_id"])
        for det_id, values in payload.get("values", {}).items():
            det_buf = buf.setdefault(int(det_id), {})
            det_buf["head_pose__frontality"] = _maybe_float(values.get("frontality"))
            det_buf["head_pose__yaw_deg"] = _maybe_float(values.get("yaw_deg"))
            det_buf["head_pose__pitch_deg"] = _maybe_float(values.get("pitch_deg"))
            det_buf["head_pose__roll_deg"] = _maybe_float(values.get("roll_deg"))

    def on_tracked(
        self, topic: str, detections: list[Detection], bus: VisualBus,
    ) -> None:
        """signal/face__tracked — record track_id and detection score per det_id.
        No commit happens here; commit is on the *next* frame/*."""
        if not detections:
            return
        frame_id = detections[0].frame_id
        slot = self._buffer.setdefault(
            frame_id, {"dets": {}, "tracks": {}},
        )
        tracks = slot["tracks"]
        dets = slot["dets"]
        for det in detections:
            track_id = det.track_id
            if track_id is None:
                continue
            tracks[det.detection_id] = int(track_id)
            dets.setdefault(det.detection_id, {})["face__detection_score"] = float(det.score)

    # ── dump ─────────────────────────────────────────────────────────

    def dump(self, path: Path) -> int:
        """Write per-subject summary to parquet. Returns row count."""
        if not self._stats:
            _log.info("no subjects accumulated — skipping parquet dump")
            return 0

        vector_cols = list(self._normalizer.vector_columns)
        rows: list[dict[str, Any]] = []
        for subject_id, stats in self._stats.items():
            evals, _ = stats.eigendecomp()
            rows.append(
                {
                    "subject_id": str(subject_id),
                    "n": int(stats.n),
                    "K_dynamic": int(stats.top_k_for_variance()),
                    "mean": stats.mean.tolist(),
                    "eigenvalues": evals.tolist(),
                    "sliding_z_latest": stats.z_score_sliding().tolist(),
                }
            )
        df = pl.DataFrame(rows)
        df = df.with_columns(pl.lit(vector_cols).alias("vector_columns"))
        path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(path)
        _log.info(
            "statistics.parquet written: subjects=%d, dim=%d, path=%s",
            len(rows), self._dim, path,
        )
        return len(rows)

    # ── internal ─────────────────────────────────────────────────────

    def _dets_buf(self, frame_id: int) -> dict[int, dict[str, float]]:
        slot = self._buffer.setdefault(frame_id, {"dets": {}, "tracks": {}})
        return slot["dets"]

    def _commit_frame(self, frame_id: int) -> None:
        slot = self._buffer.pop(frame_id, None)
        if slot is None:
            return
        tracks: dict[int, int] = slot["tracks"]
        dets: dict[int, dict[str, float]] = slot["dets"]
        for det_id, track_id in tracks.items():
            col_dict = dets.get(det_id, {})
            vector = self._normalizer.transform(col_dict)
            stats = self._stats.get(track_id)
            if stats is None:
                stats = SignalStatistics(
                    dim=self._dim,
                    sliding_window=self._sliding_window,
                    variance_target=self._variance_target,
                )
                self._stats[track_id] = stats
            stats.update(vector)
        self._last_committed = frame_id


def _maybe_float(v: Any) -> float:
    """Coerce to float; None / non-numeric → NaN (weak-prior)."""
    if v is None:
        return float("nan")
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")

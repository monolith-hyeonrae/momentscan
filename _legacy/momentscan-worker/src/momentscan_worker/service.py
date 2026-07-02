"""The actual processing harness — one job = one VisualBus + Pipeline + stash.

The worker doesn't try to be a daemon. The orchestrator (RQ /
Celery / Postgres-as-queue / a plain ``multiprocessing.Pool``) is
responsible for parallelism, retry, and queueing. A single process
of momentscan-worker picks up *one* video, processes it through the
visualstack pipeline, writes parquet (and any clip output), and
returns a small ``JobResult`` summary.

Patterns demonstrated here:

  - Standard 4-channel observability surface (JSON logs to stderr,
    Prometheus on /metrics, UDS control plane, optional streaming
    subscribe for debug) — same shape as every other visualstack
    service.
  - Per-job context (``log_context(job_id=...)``) flowing into every
    log line.
  - Policy-driven setup (``policies/signal_ranges.json`` etc. injected
    via :class:`momentscan_worker.policies.Policies`) — domain
    vocabulary lives in the caller, not in visualstack / visualbind.
  - Analyzer chain → composer → stash action wiring through the
    Pipeline. The face-landmarks plugin is wired conditionally — if
    its MediaPipe model file is missing the worker logs and continues
    without it (weak-prior).
  - Per-subject :class:`SignalStatisticsCollector` (sink-only module)
    accumulates the unified signal vector and dumps
    ``<stash>/statistics.parquet`` on teardown. Wired only when
    ``policies_dir`` is supplied.

Selector → 3-artifact (highlight / diversity / standard) generation is
not in place yet (redesign-2026-05 §3, §8). It needs the remaining
appearance / shape / category statistics implementations on the
visualbind side first.
"""

from __future__ import annotations

import logging
import os
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path

from visualbus import (
    ControlServer,
    FileSource,
    PrometheusExporter,
    VisualBus,
    log_context,
    setup_json_logging,
)
from visualpath.core import Pipeline
from visualpath.plugins.face_detect import FaceDetect, IoUTracker
from visualpath.plugins.face_expression import FaceExpression, SmilingCloseup
from visualpath.stash import ParquetStashAction

from momentscan_worker.policies import Policies, load_policies
from momentscan_worker.statistics_collector import SignalStatisticsCollector

_log = logging.getLogger("momentscan.worker")


# ── job / result types ──────────────────────────────────────────────────


@dataclass(frozen=True)
class Job:
    """One unit of work — minimal schema for now; evolve with the orchestrator."""

    id: str
    file_path: Path
    output_dir: Path

    @property
    def stash_dir(self) -> Path:
        return self.output_dir / self.id / "stash"


@dataclass
class JobResult:
    job_id: str
    ok: bool
    duration_seconds: float = 0.0
    partitions_written: int = 0
    error: str | None = None
    extra: dict = field(default_factory=dict)


# ── pipeline ────────────────────────────────────────────────────────────


def build_pipeline(
    *,
    detect_model_root: Path,
    landmarks_model_root: Path | None,
    landmarks_model_filename: str = "face_landmarker.task",
    head_pose_model_root: Path | None = None,
    head_pose_model_filename: str = "sixdrepnet.onnx",
) -> Pipeline:
    """Modules this worker assembles for every job.

    The face-landmarks plugin is wired in conditionally. If
    ``landmarks_model_root`` is None, or the MediaPipe model file
    isn't present at that root, the plugin is skipped and downstream
    consumers see ``signal/face__frontality`` as silent (weak-prior;
    nothing breaks).

    Pipeline assembly is intentionally explicit — no plugin-discovery
    magic — so a glance at this function answers "what is momentscan
    analyzing today?".
    """
    modules = [
        FaceDetect(model_root=str(detect_model_root), emit_render_hints=False),
        IoUTracker(),
        FaceExpression(),
        SmilingCloseup(rise_threshold=0.55, min_face_height_px=120),
    ]
    if landmarks_model_root is not None:
        try:
            from visualpath.plugins.face_landmarks import FaceLandmarks
            fl = FaceLandmarks(
                model_root=str(landmarks_model_root),
                model_filename=landmarks_model_filename,
                emit_render_hints=False,
            )
            # Inline so the parent worker process sees the landmarks signal
            # (no subprocess IPC). Production worker is single-process per job.
            fl.isolation = "inline"  # type: ignore[misc]
            modules.insert(2, fl)
            _log.info(
                "face-landmarks enabled (model_root=%s)", landmarks_model_root,
            )
        except FileNotFoundError as exc:
            _log.warning(
                "face-landmarks skipped (model missing): %s — mediapipe__ signals silent",
                exc,
            )
        except Exception:  # noqa: BLE001 — weak-prior
            _log.exception(
                "face-landmarks failed to initialize — continuing without it",
            )
    if head_pose_model_root is not None:
        try:
            from visualpath.plugins.head_pose import HeadPose
            modules.append(
                HeadPose(
                    model_root=str(head_pose_model_root),
                    model_filename=head_pose_model_filename,
                    emit_render_hints=False,
                )
            )
            _log.info(
                "head-pose enabled (model_root=%s)", head_pose_model_root,
            )
        except FileNotFoundError as exc:
            _log.warning(
                "head-pose skipped (model missing): %s — head_pose__ signals silent",
                exc,
            )
        except Exception:  # noqa: BLE001 — weak-prior
            _log.exception(
                "head-pose failed to initialize — continuing without it",
            )
    return Pipeline(modules=modules)


# ── service entry ───────────────────────────────────────────────────────


def run_job(
    job: Job,
    *,
    detect_model_root: Path,
    landmarks_model_root: Path | None = None,
    landmarks_model_filename: str = "face_landmarker.task",
    head_pose_model_root: Path | None = None,
    head_pose_model_filename: str = "sixdrepnet.onnx",
    policies_dir: Path | None = None,
    with_control_plane: bool = False,
    with_metrics: bool = False,
    metrics_port: int = 9100,
) -> JobResult:
    """Process one job; return a small result summary.

    ``with_control_plane`` / ``with_metrics`` are off by default because
    a job-queue worker that processes one file and exits doesn't
    benefit from them. Turn them on when you want to debug a long
    job from outside, or when the worker is a long-running daemon
    that processes a queue inside one process. See ``docs/applications.md``
    in visualstack for the deployment matrix.

    ``policies_dir`` points at the momentscan domain policies. When
    supplied, the policies are loaded *before* pipeline assembly so a
    malformed file fails the job fast rather than mid-stream. When
    omitted, the worker still runs (current legacy mode) but skips the
    policy-driven setup; future selectors will require it.
    """
    constants = {
        "service": "momentscan",
        "worker_id": os.environ.get("WORKER_ID", "w-local"),
        "hostname": socket.gethostname(),
    }
    setup_json_logging(level="INFO", constants=constants)

    job.stash_dir.mkdir(parents=True, exist_ok=True)
    started_at = time.perf_counter()

    policies: Policies | None = None
    if policies_dir is not None:
        try:
            policies = load_policies(policies_dir)
            _log.info(
                "policies loaded",
                extra={
                    "policies_dir": str(policies_dir),
                    "vector_dim": policies.vector_dim,
                    "vector_columns": list(policies.normalizer.vector_columns),
                },
            )
        except Exception:  # noqa: BLE001
            _log.exception("policies load failed — aborting job")
            return JobResult(
                job_id=job.id,
                ok=False,
                duration_seconds=time.perf_counter() - started_at,
                error=f"policies load failed: {policies_dir}",
            )

    bus = VisualBus()
    metrics = control = None

    if with_metrics:
        metrics = PrometheusExporter(port=metrics_port, const_labels=constants)
        metrics.attach(bus)
        metrics.start_http()
    if with_control_plane:
        control = ControlServer(bus)
        control.start()

    pipeline = build_pipeline(
        detect_model_root=detect_model_root,
        landmarks_model_root=landmarks_model_root,
        landmarks_model_filename=landmarks_model_filename,
        head_pose_model_root=head_pose_model_root,
        head_pose_model_filename=head_pose_model_filename,
    )

    collector: SignalStatisticsCollector | None = None
    if policies is not None:
        ss = policies.statistics_config.get("signal_statistics", {})
        collector = SignalStatisticsCollector(
            normalizer=policies.normalizer,
            sliding_window=int(ss.get("sliding_window", 30)),
            variance_target=float(ss.get("variance_target", 0.95)),
            output_path=job.stash_dir / "statistics.parquet",
        )
        pipeline.modules.append(collector)

    try:
        pipeline.attach_to(bus)

        stash = ParquetStashAction(
            output_dir=job.stash_dir,
            topics={
                "signal/face__tracked": "detections",
                "signal/expression__smile": "augment",
            },
        )
        stash.attach(bus)

        with log_context(job_id=job.id, file_path=str(job.file_path)):
            _log.info("job start")
            bus.attach_source(FileSource(str(job.file_path)), name="job")
            bus.run_until_done()
            duration = time.perf_counter() - started_at
            _log.info("job done", extra={"duration_s": duration,
                                          "partitions_written": stash.partitions_written})

        return JobResult(
            job_id=job.id,
            ok=True,
            duration_seconds=duration,
            partitions_written=stash.partitions_written,
            extra={
                "policies_vector_dim": policies.vector_dim if policies else None,
                "n_subjects": collector.n_subjects if collector else None,
            },
        )
    except Exception as exc:
        _log.exception("job failed")
        return JobResult(
            job_id=job.id,
            ok=False,
            duration_seconds=time.perf_counter() - started_at,
            error=f"{type(exc).__name__}: {exc}",
        )
    finally:
        # Pipeline.detach() iterates modules and calls teardown() — but we
        # also call collector.teardown() directly so the parquet dump
        # happens even on the failure path before detach unwinds anything.
        if collector is not None:
            try:
                collector.teardown()
            except Exception:
                _log.exception("statistics collector teardown failed")
        try:
            pipeline.detach()
        except Exception:
            _log.exception("pipeline detach failed")
        if control is not None:
            control.stop()
        if metrics is not None:
            metrics.stop_http()

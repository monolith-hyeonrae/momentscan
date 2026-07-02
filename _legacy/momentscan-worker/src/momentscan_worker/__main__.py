"""CLI entry: ``momentscan-worker <video> [--output-dir DIR] [...]``.

Designed to be invoked by an orchestrator (RQ / Celery / etc.) per
job, but also usable directly for local testing.

Output structure::

    <output_dir>/<job_id>/stash/<partition_id>/detections.parquet
                                /<partition_id>/...
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from momentscan_worker.service import Job, run_job


# When momentscan is checked out as a sibling repo, the policies live at
# ``<repo-root>/policies/``. We resolve it from this module's path so an
# editable install keeps working without an explicit --policies-dir.
# Production deployments should pass --policies-dir explicitly.
_DEFAULT_POLICIES = Path(__file__).resolve().parents[4] / "policies"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="momentscan-worker",
        description="Process one video through the momentscan pipeline.",
    )
    p.add_argument("video", type=Path, help="path to input video file")
    p.add_argument(
        "--job-id",
        default=None,
        help="job identifier (default: auto-generated uuid4 short).",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./output"),
        help="where to write per-job stash output (default: ./output).",
    )
    p.add_argument(
        "--detect-model-root",
        type=Path,
        default=Path.home() / ".cache" / "visualstack" / "insightface",
        help="InsightFace model root (looks for models/buffalo_l/ inside).",
    )
    p.add_argument(
        "--landmarks-model-root",
        type=Path,
        default=Path.home() / ".cache" / "visualstack" / "mediapipe",
        help=(
            "MediaPipe FaceLandmarker model root. "
            "Plugin is silently skipped if the file is missing."
        ),
    )
    p.add_argument(
        "--landmarks-model-filename",
        default="face_landmarker.task",
        help=(
            "MediaPipe Tasks bundle basename inside --landmarks-model-root. "
            "Default 'face_landmarker.task' (no-blendshapes variant — "
            "smaller, same mesh + transformation_matrixes output)."
        ),
    )
    p.add_argument(
        "--no-landmarks",
        action="store_true",
        help="disable the face-landmarks plugin even if the model is present.",
    )
    p.add_argument(
        "--head-pose-model-root",
        type=Path,
        default=Path.home() / ".portrait981" / "models" / "6drepnet",
        help=(
            "6DRepNet ONNX model root. Plugin is silently skipped if missing."
        ),
    )
    p.add_argument(
        "--head-pose-model-filename",
        default="sixdrepnet.onnx",
        help="6DRepNet ONNX basename.",
    )
    p.add_argument(
        "--no-head-pose",
        action="store_true",
        help="disable the head-pose plugin even if the model is present.",
    )
    p.add_argument(
        "--policies-dir",
        type=Path,
        default=_DEFAULT_POLICIES if _DEFAULT_POLICIES.is_dir() else None,
        help=(
            "momentscan domain policies directory containing "
            "signal_ranges.json + statistics_config.json + selector_policy.json. "
            "Omit to skip policy-driven setup (legacy mode)."
        ),
    )
    p.add_argument(
        "--metrics",
        action="store_true",
        help="expose Prometheus metrics on --metrics-port (default off).",
    )
    p.add_argument("--metrics-port", type=int, default=9100)
    p.add_argument(
        "--control",
        action="store_true",
        help="expose UDS control plane (default off; useful for long jobs).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    job = Job(
        id=args.job_id or uuid.uuid4().hex[:12],
        file_path=args.video.expanduser().resolve(),
        output_dir=args.output_dir.expanduser().resolve(),
    )
    if not job.file_path.exists():
        print(f"error: input video not found: {job.file_path}", file=sys.stderr)
        return 2

    landmarks_root: Path | None = (
        None if args.no_landmarks else args.landmarks_model_root.expanduser()
    )
    head_pose_root: Path | None = (
        None if args.no_head_pose else args.head_pose_model_root.expanduser()
    )
    policies_dir: Path | None = (
        args.policies_dir.expanduser() if args.policies_dir is not None else None
    )

    result = run_job(
        job,
        detect_model_root=args.detect_model_root.expanduser(),
        landmarks_model_root=landmarks_root,
        landmarks_model_filename=args.landmarks_model_filename,
        head_pose_model_root=head_pose_root,
        head_pose_model_filename=args.head_pose_model_filename,
        policies_dir=policies_dir,
        with_control_plane=args.control,
        with_metrics=args.metrics,
        metrics_port=args.metrics_port,
    )
    # Result line on stdout — orchestrators parse this; logs are on stderr (JSON).
    print(json.dumps({
        "job_id": result.job_id,
        "ok": result.ok,
        "duration_seconds": round(result.duration_seconds, 3),
        "partitions_written": result.partitions_written,
        "error": result.error,
        "stash_dir": str(job.stash_dir),
        "policies_vector_dim": result.extra.get("policies_vector_dim"),
        "n_subjects": result.extra.get("n_subjects"),
    }))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

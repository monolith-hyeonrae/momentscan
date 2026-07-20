"""Layer 0 — ingest spine + observability (NO analysis yet).

The foundation the whole pipeline stands on: prove the original video decodes,
that frames flow in order, and that every step leaves a structured log AND a
visible trace — *before* any analysis module runs. This is the spine; analysis
is flesh added on top.

Each analysis module added later contributes, uniformly:
  - one structured log event,
  - one draw hint on the trace,
  - one stash column.

No bus, no models here: a clip is iterated directly off ``FileSource`` (which
is itself an iterator of decoded frames). The bus enters only when frames must
fan out to multiple analysis consumers — that is the bus's reason to exist, and
it stays out of the foundation.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
from visualbus import DrawText, FileSource, apply_hint
from visualbus.structured_log import log_context
from visualbus.timestamp import ns_to_seconds

log = logging.getLogger("momentscan.ingest")

VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".m4v"}
_PROGRESS_EVERY = 100  # frames between progress logs


@dataclass(frozen=True)
class IngestResult:
    clip_id: str
    frames_read: int
    frames_written: int
    native_fps: float | None
    width: int
    height: int
    duration_s: float | None
    elapsed_s: float
    trace_path: str | None
    ok: bool


def _draw_hud(img, *, clip_id: str, frame_id: int, t_ns: int) -> None:
    """The Layer-0 overlay: just enough to *see* that ingest is real —
    which clip, which frame, what timestamp. Later layers draw over this."""
    lines = [clip_id, f"frame {frame_id}   t={ns_to_seconds(t_ns):6.2f}s"]
    for i, text in enumerate(lines):
        apply_hint(
            img,
            DrawText(
                text=text, x=12, y=30 + i * 28, frame_id=frame_id,
                color=(0, 255, 0), font_scale=0.7, thickness=2,
            ),
        )


def ingest_clip(
    video_path: str | Path,
    out_root: str | Path,
    *,
    fps: int | None = None,
    trace: bool = True,
) -> IngestResult:
    """Decode one clip end to end, logging and (optionally) tracing the flow.

    Returns an :class:`IngestResult`; never raises on a decode fault — it logs
    ``clip.error`` and returns ``ok=False`` so a batch keeps moving.
    """
    video_path = Path(video_path)
    clip_id = video_path.stem
    out_dir = Path(out_root) / clip_id
    out_dir.mkdir(parents=True, exist_ok=True)

    with log_context(clip_id=clip_id):
        t0 = time.perf_counter()
        src = FileSource(video_path, fps=fps)
        prof = src.profile
        dur_s = ns_to_seconds(prof.duration_ns) if prof.duration_ns else None
        log.info(
            "clip.open",
            extra={
                "codec": prof.codec, "width": prof.width, "height": prof.height,
                "native_fps": prof.fps, "duration_s": dur_s, "target_fps": fps,
            },
        )

        writer = None
        trace_path: Path | None = None
        frames_read = frames_written = 0
        last_logged = 0
        ok = True
        try:
            for frame in src:
                frames_read += 1
                if trace:
                    if writer is None:
                        trace_path = out_dir / "ingest.mp4"
                        out_fps = float(fps) if fps else (prof.fps or 30.0)
                        writer = cv2.VideoWriter(
                            str(trace_path),
                            cv2.VideoWriter_fourcc(*"mp4v"),
                            out_fps,
                            (frame.width, frame.height),
                        )
                    img = frame.data.copy()
                    _draw_hud(img, clip_id=clip_id, frame_id=frame.frame_id, t_ns=frame.t_ns)
                    writer.write(img)
                    frames_written += 1
                if frames_read - last_logged >= _PROGRESS_EVERY:
                    last_logged = frames_read
                    log.info("clip.progress", extra={"frames_read": frames_read})
        except Exception as exc:  # decode fault — log and end this clip, keep batch alive
            ok = False
            log.exception("clip.error", extra={"frames_read": frames_read, "error": str(exc)})
        finally:
            if writer is not None:
                writer.release()
            src.close()

        result = IngestResult(
            clip_id=clip_id,
            frames_read=frames_read,
            frames_written=frames_written,
            native_fps=prof.fps,
            width=prof.width,
            height=prof.height,
            duration_s=dur_s,
            elapsed_s=round(time.perf_counter() - t0, 3),
            trace_path=str(trace_path) if trace_path else None,
            ok=ok,
        )
        log.info("clip.done", extra=asdict(result))
        return result


def iter_videos(path: str | Path) -> list[Path]:
    """A single clip, or every video directly under a directory (sorted)."""
    path = Path(path)
    if path.is_dir():
        return sorted(p for p in path.iterdir() if p.suffix.lower() in VIDEO_SUFFIXES)
    return [path]


def ingest_paths(
    path: str | Path,
    out_root: str | Path,
    *,
    fps: int | None = None,
    trace: bool = True,
) -> list[IngestResult]:
    """Batch entry point: process clips strictly in sequence (the L0 spine).

    Sequential on purpose — parallelism is a worker-pool concern layered on top
    later, not something the foundation should bake in.
    """
    videos = iter_videos(path)
    log.info("batch.start", extra={"n_clips": len(videos), "root": str(path)})
    results: list[IngestResult] = []
    for i, video in enumerate(videos):
        log.info("batch.clip", extra={"i": i, "n": len(videos), "path": str(video)})
        results.append(ingest_clip(video, out_root, fps=fps, trace=trace))
    log.info(
        "batch.done",
        extra={
            "n_clips": len(videos),
            "ok": sum(r.ok for r in results),
            "frames": sum(r.frames_read for r in results),
        },
    )
    return results

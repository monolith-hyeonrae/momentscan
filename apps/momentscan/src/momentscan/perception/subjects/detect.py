"""Layers 1+2 — face detect + IoU track, warm-resident, on the bus.

Analysis flesh on the L0 spine. It demonstrates the things that matter
operationally:

  - **warm**: the buffalo_l model loads ONCE (``warm_init``) and every clip
    reuses it. Loading per clip would dwarf the ~seconds of actual work.
    Warm reuse requires per-clip ``reset()`` of stream state (det/track id
    counters, open tracks) — otherwise ids leak across clip boundaries.
  - **bus**: ``FaceDetect`` and ``IoUTracker`` are bus modules; one frame
    stream fans out to detect → track → (trace, stash).
  - **anchor staging** (Step 0a, first half): ``track_id`` is the temporal
    anchor that later layers stitch into ``subject_id`` (re-id) and attribute
    to ``rider_role`` (depth vote, step0b). Per the rider-attribution rule:
    face SIZE never decides role — it is only a quality signal downstream.

Uniform growth, layer 2 adds: one log dimension (``clip.done`` gains
``n_tracks`` + per-track health), one draw (track-labelled boxes ``#tid``),
one stash column (``track_id`` in ``detections.parquet``).

Unit-input observability: the job timeline (job.accept → clip.done) shows what
went in and out; ``_ProcessTrace`` records what happened in between — per-frame
module latency / faces / errors → ``process_trace.jsonl``, rendered to
``process_timeline.png`` (viz.render_process_timeline) after every job.
"""

from __future__ import annotations

import contextlib
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from visualbus import DrawText, FileSource, VideoFileSink, VisualBus
from visualbus.structured_log import log_context
from visualpath.core import Pipeline
from visualpath.plugins.face_detect import FaceDetect, IoUTracker

from momentscan.infra.store.stash import write_detections, write_process_trace, write_stitch

from momentscan.perception.subjects.stitch import stitch_tracks, track_purity

log = logging.getLogger("momentscan.detect")

DEFAULT_MODEL_ROOT = Path.home() / ".insightface"  # <root>/models/buffalo_l/


@dataclass
class WarmDetect:
    """Resident detect+track state — built once, reused by every ``process_clip``."""
    bus: VisualBus
    pipeline: Pipeline
    detect: FaceDetect
    tracker: IoUTracker


def warm_init(*, model_root: str | Path = DEFAULT_MODEL_ROOT, min_score: float = 0.5) -> WarmDetect:
    """COLD path — load the model and wire it onto a bus. Call once at startup."""
    t0 = time.perf_counter()
    log.info("warm.init.start", extra={"model_root": str(model_root)})
    bus = VisualBus()
    detect = FaceDetect(
        str(model_root),
        emit_embeddings=True,      # buffalo_l recognition vector → re-id later
        emit_render_hints=False,   # tracker draws instead — labelled with #track_id
        min_score=min_score,
    )
    tracker = IoUTracker(emit_render_hints=True)
    pipeline = Pipeline([detect, tracker])
    pipeline.attach_to(bus)        # modules subscribe BEFORE any per-clip sink
    log.info("warm.ready", extra={"load_s": round(time.perf_counter() - t0, 3)})
    return WarmDetect(bus=bus, pipeline=pipeline, detect=detect, tracker=tracker)


class _DetectionCollector:
    """Accumulates ``signal/face__tracked`` payloads into stash rows."""

    def __init__(self, clip_id: str) -> None:
        self.clip_id = clip_id
        self.rows: list[dict] = []

    def on_detection(self, topic: str, payload) -> None:
        for det in payload or ():
            emb = det.embedding
            self.rows.append({
                "clip_id": self.clip_id,
                "frame_idx": det.frame_id,
                "det_id": det.detection_id,
                "track_id": det.track_id,
                "bbox": [det.bbox.x1, det.bbox.y1, det.bbox.x2, det.bbox.y2],
                "score": det.score,
                "embedding": emb.tolist() if emb is not None else None,
            })


class _ProcessTrace:
    """Per-frame processing record — HOW this unit input moved through the bus.

    The job timeline (job.accept → clip.open → clip.done) says what went in and
    out; this says what happened in between, per frame: each module's latency
    (from the pipeline's free ``signal/telemetry__*``), faces found, errors.

    Correlation trick: the bus publishes synchronously, so the warm modules
    (subscribed first) run — and emit their telemetry — BEFORE the ``frame/*``
    fanout reaches this collector's ``on_frame``. Pending events therefore
    belong to exactly the frame that triggered them, and ``on_frame`` flushes
    them into that frame's row. Subscribed after the sink, so ``t_rel_ms``
    marks "frame fully processed, including encode".
    """

    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.n_errors = 0
        self._t0 = time.perf_counter()
        self._modules: dict[str, float] = {}
        self._faces = 0
        self._errors: list[dict] = []

    def on_telemetry(self, topic: str, payload) -> None:
        if isinstance(payload, dict):
            m = str(payload.get("module") or topic.rsplit("__", 1)[-1])
            self._modules[m] = self._modules.get(m, 0.0) + float(payload.get("duration_ns", 0)) / 1e6

    def on_error(self, topic: str, payload) -> None:
        if isinstance(payload, dict):
            self._errors.append({
                "module": payload.get("module"),
                "error_type": payload.get("error_type"),
                "message": payload.get("message"),
            })

    def on_tracked(self, topic: str, payload) -> None:
        self._faces += len(payload or ())

    def on_frame(self, topic: str, frame) -> None:
        row = {
            "frame_idx": frame.frame_id,
            "t_rel_ms": round((time.perf_counter() - self._t0) * 1000, 2),
            "n_faces": self._faces,
            "modules": {k: round(v, 3) for k, v in self._modules.items()},
        }
        if self._errors:
            row["errors"] = self._errors
            self.n_errors += len(self._errors)
        self.rows.append(row)
        self._modules, self._faces, self._errors = {}, 0, []

    def summary(self) -> dict:
        """Per-module p50/p95/max ms + whole-frame cycle stats, for clip.done."""
        if not self.rows:
            return {}
        import numpy as np
        out: dict[str, dict] = {}
        names = {m for r in self.rows for m in r["modules"]}
        for m in sorted(names):
            v = np.array([r["modules"].get(m, 0.0) for r in self.rows])
            out[m] = {"p50_ms": round(float(np.percentile(v, 50)), 2),
                      "p95_ms": round(float(np.percentile(v, 95)), 2),
                      "max_ms": round(float(v.max()), 2)}
        t = np.array([r["t_rel_ms"] for r in self.rows])
        dt = np.diff(t, prepend=0.0)
        out["frame_cycle"] = {"p50_ms": round(float(np.percentile(dt, 50)), 2),
                              "p95_ms": round(float(np.percentile(dt, 95)), 2),
                              "max_ms": round(float(dt.max()), 2)}
        return out


def _track_health(rows: list[dict]) -> dict:
    """Track health, derived from the stash rows (README: first-class scan meta).

    Per track: ``length`` (frames observed), ``gap_frames`` (frames missed
    inside the track's first→last span). Many short tracks or gappy tracks =
    the temporal anchor is fragmenting — exactly what re-id stitching (next
    layer) must repair, so it is measured BEFORE that layer exists.
    """
    frames_by_track: dict[int, set[int]] = {}
    for r in rows:
        frames_by_track.setdefault(r["track_id"], set()).add(r["frame_idx"])
    tracks = []
    for tid in sorted(frames_by_track):
        seen = frames_by_track[tid]
        span = max(seen) - min(seen) + 1
        tracks.append({
            "track_id": tid,
            "length": len(seen),
            "gap_frames": span - len(seen),
        })
    return {"n_tracks": len(tracks), "tracks": tracks}


def process_clip(
    warm: WarmDetect,
    video_path: str | Path,
    out_root: str | Path,
    *,
    fps: int | None = None,
    clip_id: str | None = None,
) -> dict:
    """HOT path — run one clip through the warm detector. NOT re-entrant on a
    single ``warm`` (the bus pump is single-threaded); the daemon serializes.

    clip_id 기본값 = 파일명 stem (CLI/데몬 관례). 서비스 잡은 clip_id가 파일명과
    다를 수 있어(회사 workflowId 등) 명시 전달한다 — 안 갈라지면 하류가 전멸한다
    (2026-07-15 wf777 리허설 실증)."""
    video_path = Path(video_path)
    clip_id = clip_id or video_path.stem
    out_dir = Path(out_root) / clip_id
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "detect.mp4"

    with log_context(clip_id=clip_id):
        t0 = time.perf_counter()
        # Warm reuse ≠ state reuse: ids are clip-scoped, and the previous
        # clip's open tracks must never IoU-match this clip's first frame.
        warm.detect.reset()
        warm.tracker.reset()
        src = FileSource(video_path, fps=fps)
        prof = src.profile
        out_fps = float(fps) if fps else (prof.fps or 30.0)
        log.info(
            "clip.open",
            extra={"codec": prof.codec, "width": prof.width, "height": prof.height,
                   "native_fps": prof.fps, "target_fps": fps},
        )

        sink = VideoFileSink(str(trace_path), fps=out_fps)
        collector = _DetectionCollector(clip_id)
        ptrace = _ProcessTrace()

        # Frame-number HUD: subscribed BEFORE the sink attaches, so the hint is
        # published before the sink draws each frame.
        def _hud(topic, frame):
            warm.bus.publish_signal("signal/render_hint__hud", [DrawText(
                text=f"{clip_id}  f={frame.frame_id}", x=12, y=26,
                frame_id=frame.frame_id, color=(235, 235, 235), font_scale=0.55,
            )])
        hud_handle = warm.bus.subscribe("frame/*", _hud)
        handles = sink.attach(warm.bus)
        handles.append(hud_handle)
        handles.append(warm.bus.subscribe("signal/face__tracked", collector.on_detection))
        # Process trace: telemetry/error/face events buffer, on_frame flushes —
        # on_frame is subscribed AFTER the sink so t_rel_ms includes the encode.
        handles.append(warm.bus.subscribe("signal/telemetry__*", ptrace.on_telemetry))
        handles.append(warm.bus.subscribe("trigger/module_error__*", ptrace.on_error))
        handles.append(warm.bus.subscribe("signal/face__tracked", ptrace.on_tracked))
        handles.append(warm.bus.subscribe("frame/*", ptrace.on_frame))
        name = warm.bus.attach_source(src)
        try:
            warm.bus.run_until_done()
        finally:
            # run_until_done auto-retires an exhausted source, so detach is
            # best-effort (it may already be gone). Each cleanup is guarded so
            # one failure can't skip the others (esp. sink.close finalizing mp4).
            for h in handles:
                with contextlib.suppress(Exception):
                    warm.bus.unsubscribe(h)
            with contextlib.suppress(KeyError):
                warm.bus.detach_source(name)
            sink.close()
            src.close()

        # Re-id stitch BEFORE the write — rows gain subject_id, so the stash
        # carries the stitched anchor and the raw track_id provenance together.
        if collector.rows:
            stitch = stitch_tracks(collector.rows)
            purity = track_purity(collector.rows)
            write_stitch(out_root, clip_id, {**stitch, "purity": purity})
        else:
            stitch = {"n_subjects": 0, "subjects": [], "stitches": []}
            purity = []
        det_path = write_detections(out_root, clip_id, collector.rows) if collector.rows else None
        frames_with_face = len({r["frame_idx"] for r in collector.rows})

        # Unit-input observability: persist the per-frame trace and render the
        # processing timeline from it. Render failure must not fail the job —
        # the trace (the data) is the artifact of record, the png is a view.
        ptrace_path = write_process_trace(out_root, clip_id, ptrace.rows) if ptrace.rows else None
        timeline_path = None
        if ptrace_path is not None:
            try:
                from momentscan.surface.cards import render_process_timeline
                timeline_path = render_process_timeline(out_root, clip_id).get("timeline_path")
            except Exception:
                log.exception("process_timeline render failed")

        # Artifact integrity — verified against the DISK, not against what the
        # code believes it wrote. A partial failure (trace written, parquet
        # missing — the exact bug class we hit once) must surface per-artifact
        # instead of drowning in an aggregate "done". None = not expected
        # (a clip with zero detections legitimately has no parquet).
        artifacts = {
            "trace": trace_path.is_file() and sink.n_written > 0,
            "detections": (det_path is not None and det_path.is_file()) if collector.rows else None,
            "process_trace": (ptrace_path is not None and ptrace_path.is_file()) if ptrace.rows else None,
        }
        ok = all(v is not False for v in artifacts.values())
        health = _track_health(collector.rows)
        result = {
            "clip_id": clip_id,
            "frames_written": sink.n_written,
            "n_detections": len(collector.rows),
            "frames_with_face": frames_with_face,
            **health,
            **stitch,
            "elapsed_s": round(time.perf_counter() - t0, 3),
            "module_ms": ptrace.summary(),
            "n_module_errors": ptrace.n_errors,
            "purity_suspects": sum(len(p["suspect_runs"]) for p in purity),
            "trace_path": str(trace_path),
            "detections_path": str(det_path) if det_path else None,
            "process_trace_path": str(ptrace_path) if ptrace_path else None,
            "timeline_path": timeline_path,
            "artifacts": artifacts,
            "ok": ok,
        }
        log.log(logging.INFO if ok else logging.WARNING, "clip.done", extra=result)
        return result

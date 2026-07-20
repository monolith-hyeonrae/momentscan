"""run 가족 — 파이프라인 구동 동사: ingest(Layer 0 spine) · run(one-command full pipeline)."""

from __future__ import annotations

import argparse
from pathlib import Path


def _cmd_ingest(args: argparse.Namespace) -> int:
    from momentscan.perception.extraction.ingest import ingest_paths

    results = ingest_paths(args.path, args.out, fps=args.fps, trace=not args.no_trace)
    return 0 if all(r.ok for r in results) else 1


def _cmd_run(args: argparse.Namespace) -> int:
    import contextlib
    import io
    import logging
    import os
    import time as _time
    import warnings

    # QUIET BY DEFAULT — the first-15-minutes log is the product's face. Everything
    # useful still lands in run.json / the structured logs; this only silences the
    # third-party chatter on the happy path (model-load progress bars, provider
    # dumps, mediapipe init spew, deprecation warnings from vendored call sites).
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    os.environ.setdefault("TQDM_DISABLE", "1")          # transformers weight-load bars
    os.environ.setdefault("GLOG_minloglevel", "2")      # mediapipe/absl I/W lines
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")  # TFLite XNNPACK info line
    warnings.filterwarnings("ignore", category=FutureWarning)   # skimage via insightface
    # accepted residue: ~8 absl C++ init lines from mediapipe (pre-InitializeLog);
    # suppressing those needs fd-level stderr redirection — more invasive than the noise.

    from momentscan.infra.pipeline.runner import run_pipeline
    from momentscan.infra.store.stash import detections_path

    # ONE-COMMAND happy path: `run <video-or-clip>` — a video PATH as clip_id means
    # source=itself; when detections are missing and a source is known, run detect
    # INLINE (one-shot warm_init, no daemon needed) before the stage runner. The
    # daemon stays the operator path (warm, many clips); this is the first-15-minutes path.
    logging.disable(logging.INFO)   # cascade banners + stage lines ARE the digestible log
    p = Path(args.clip_id).expanduser()
    if p.suffix.lower() in (".mp4", ".mov", ".mkv", ".avi") and p.exists():
        args.source, args.clip_id = str(p), p.stem
    if args.source and not detections_path(args.out, args.clip_id).exists():
        from momentscan.perception.subjects.detect import process_clip, warm_init
        try:
            import onnxruntime as _ort
            _ort.set_default_logger_severity(3)
        except Exception:
            pass
        _t0 = _time.perf_counter()
        with contextlib.redirect_stdout(io.StringIO()):   # insightface provider dumps
            warm = warm_init()
        r = process_clip(warm, args.source, args.out, fps=args.fps)
        print(f"═══ ⓪ DETECT (inline warm — no daemon for a one-shot) ═══\n"
              f"  detect      ✓ {int((_time.perf_counter() - _t0) * 1000):>6d}ms  "
              f"n_frames={r.get('frames_written', '?')} · subjects={r.get('n_subjects', '?')}")
    result = run_pipeline(args.out, args.clip_id, source=args.source, fps=args.fps,
                          force=args.force, only=args.only, products=args.product,
                          subject_query=args.subject)
    ran = sorted(result["ran"], key=lambda x: x.get("ms") or 0, reverse=True)
    total_s = sum((x.get("ms") or 0) for x in result["ran"]) / 1000.0
    print(f"\n── {args.clip_id}: {len(result['ran'])} ran · {len(result['skipped'])} skipped · "
          f"{len(result['failed'])} failed · {total_s:.0f}s ──")
    if ran:                                  # where the time went — caching hid this
        print("  slowest: " + " · ".join(f"{x['name']} {(x.get('ms') or 0)/1000:.1f}s" for x in ran[:3]))
    for f in result["failed"]:
        print(f"  ✗ {f['name']}: {f.get('error') or f.get('reason')}")
    # RESULT-first exit: one file to open (deliverables + inspector link).
    if not result["failed"]:
        from momentscan.surface.report import render_report
        rep = render_report(args.out, args.clip_id)
        print(f"  ▶ report: {rep['report']}")
    return 0 if not result["failed"] else 1


def register(sub, common: argparse.ArgumentParser) -> None:
    pi = sub.add_parser("ingest", parents=[common], help="Layer 0 — decode + log + trace a clip or directory")
    pi.add_argument("path", help="video file, or a directory of clips (batch)")
    pi.add_argument("--out", default="output", help="output root (default ./output)")
    pi.add_argument("--fps", type=int, default=None, help="target fps downsample (default: native)")
    pi.add_argument("--no-trace", action="store_true", help="skip the trace.mp4, log only")
    pi.set_defaults(func=_cmd_ingest)

    prun = sub.add_parser("run", parents=[common],
                          help="video/clip → full pipeline → report (one-command; inline detect when needed)")
    prun.add_argument("clip_id", help="clip id in the stash, OR a video path (runs detect inline)")
    prun.add_argument("--source", default=None, help="original video (needed for source-based stages)")
    prun.add_argument("--out", default="output", help="stash root")
    prun.add_argument("--fps", type=int, default=6, help="fps the pipeline ran with")
    prun.add_argument("--force", action="store_true", help="re-run even if artifacts exist")
    prun.add_argument("--only", nargs="*", default=None, help="run only these stages")
    prun.add_argument("--product", nargs="*", default=None,
                      help="run only the closure(s) needed for these products "
                           "(likeness/portrait/highlight); mutually exclusive with --only (R11)")
    prun.add_argument("--subject", default=None,
                      help="subject query (C2): 'seat' (default rule) or 'face:<photo>' — "
                           "constitute the run around THIS person. Re-querying a processed "
                           "clip needs --force (or a fresh --out)")
    prun.set_defaults(func=_cmd_run)

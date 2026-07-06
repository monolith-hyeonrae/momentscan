"""momentscan CLI — pipeline driver and daemon operator surface.

Stages, decoupled via stash (the offline L1/L2 split, jepa-poc.md):

    ingest     clip(s)         -> trace + logs       (Layer 0 — spine)   [wired]
    step0      clip            -> tubelets                      (Phase 2)
    features   tubelets        -> per-track features  [--track A|B]  (Phase 2 / 4)
    select     features        -> Profile / Highlight + candidate-log (Phase 3)
    eval       candidate-logs  -> metrics vs seed eval          (Phase 3)

Layer 0 (``ingest``) is the foundation: it proves the video decodes, frames
flow in order, and the flow is logged + visible — before any analysis. Later
stages are wired in their phase.

Daemon operation — server and client share ``DEFAULT_SOCKET``
(``~/.cache/momentscan/daemon.sock``), so they rendezvous with zero flags:

    momentscan serve                  # warm daemon (loads the model once)
    momentscan process <clip>         # trigger one clip through the warm daemon
    momentscan status                 # is it up? what has it published?
    momentscan shutdown

momentscan owns this vocabulary; visualbus only lends the wire mechanism
(``visualbus.control.call``). Cross-app fleet view stays generic:
``python -m visualbus.control ls``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from visualbus.structured_log import setup_logging


def _cmd_ingest(args: argparse.Namespace) -> int:
    from momentscan.ingest import ingest_paths

    results = ingest_paths(args.path, args.out, fps=args.fps, trace=not args.no_trace)
    return 0 if all(r.ok for r in results) else 1


def _cmd_serve(args: argparse.Namespace) -> int:
    from momentscan.daemon import DEFAULT_SOCKET, serve
    from momentscan.extraction.detect import DEFAULT_MODEL_ROOT

    return serve(
        socket_path=args.socket or DEFAULT_SOCKET,
        out_root=args.out,
        fps=args.fps,
        model_root=args.model_root or DEFAULT_MODEL_ROOT,
    )


def _cmd_api_check(args: argparse.Namespace) -> int:
    from momentscan.verify.apicheck import run_apicheck

    return run_apicheck()


def _cmd_serve_http(args: argparse.Namespace) -> int:
    from momentscan.service import serve_http

    serve_http(
        args.out,
        port=args.port,
        fps=args.fps,
        open_products=tuple(args.products.split(",")) if args.products else ("likeness",),
        eureka_url=args.eureka,
        advertise_host=args.advertise_host,
        app_name=args.app_name,
    )
    return 0


# ── daemon client verbs — momentscan's own operator surface ──────────────────
# Thin wrappers over visualbus.control.call (the borrowed wire mechanism); the
# vocabulary, validation and defaults here are momentscan's.


def _call_daemon(args: argparse.Namespace, cmd: str, *, timeout: float | None = 5.0, **kw):
    from visualbus.control import call

    from momentscan.daemon import DEFAULT_SOCKET

    sock = Path(args.socket).expanduser() if args.socket else DEFAULT_SOCKET
    try:
        return call(sock, cmd, timeout=timeout, **kw)
    except (FileNotFoundError, ConnectionRefusedError):
        print(
            f"momentscan: no daemon at {sock} — start one with 'momentscan serve'",
            file=sys.stderr,
        )
        raise SystemExit(2) from None


def _cmd_process(args: argparse.Namespace) -> int:
    path = Path(args.path).expanduser().resolve()
    if not path.is_file():
        print(f"momentscan: no such clip: {path}", file=sys.stderr)
        return 2
    req = {"path": str(path)}
    if args.fps is not None:
        req["fps"] = args.fps
    # A clip takes ~seconds-to-minutes through the warm detector; wait it out.
    result = _call_daemon(args, "process", timeout=None, **req)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


def _cmd_status(args: argparse.Namespace) -> int:
    pong = _call_daemon(args, "ping")
    stats = _call_daemon(args, "stats")
    print(json.dumps({**pong, **stats}, indent=2, ensure_ascii=False))
    return 0


def _cmd_shutdown(args: argparse.Namespace) -> int:
    result = _call_daemon(args, "shutdown")
    print(json.dumps(result, ensure_ascii=False))
    return 0


def _cmd_appearance(args: argparse.Namespace) -> int:
    from momentscan.products.likeness import appearance_clip
    from momentscan.surface.cards import render_appearance_card

    result = appearance_clip(args.out, args.clip_id)
    if result["ok"]:
        result["card"] = render_appearance_card(args.out, args.clip_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def _cmd_label(args: argparse.Namespace) -> int:
    from momentscan.surface.label_server import serve_labels

    serve_labels(args.out, port=args.port, lane=args.lane)
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    from momentscan.verify.evalharness import make_template, score

    from momentscan.verify.evalharness import score_pairs

    if args.template:
        result = make_template(args.out, args.template)
    elif args.rescore:
        from momentscan.verify.evalharness import rescore_pairs
        result = rescore_pairs(args.out)
    elif (Path(args.out) / "eval" / "pair_verdicts.jsonl").exists():
        result = score_pairs(args.out)     # pairwise = the eval of record
        if (Path(args.out) / "eval" / "pair_verdicts_portrait.jsonl").exists():
            result["portrait_lane"] = score_pairs(
                args.out, verdicts_name="pair_verdicts_portrait.jsonl")
        if (Path(args.out) / "eval" / "pair_verdicts_segment.jsonl").exists():
            result["segment_lane"] = score_pairs(
                args.out, verdicts_name="pair_verdicts_segment.jsonl")
    else:
        clips = args.clips or sorted(
            p.parent.name for p in Path(args.out).glob("*/candidates.jsonl"))
        result = score(args.out, clips)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def _cmd_select(args: argparse.Namespace) -> int:
    from momentscan.products.select import select_clip
    from momentscan.surface.cards import render_portrait_card, render_select_timeline

    result = select_clip(args.out, args.clip_id, fps=args.fps)
    if result["ok"]:
        result["select_timeline"] = render_select_timeline(args.out, args.clip_id, fps=args.fps)
        result["portrait_card"] = render_portrait_card(args.out, args.clip_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def _cmd_highlight(args: argparse.Namespace) -> int:
    from momentscan.products.highlight import highlight_clip
    from momentscan.surface.cards import render_highlight_clips

    result = highlight_clip(args.out, args.clip_id, fps=args.fps)
    if result["ok"]:
        result["highlight_clips"] = render_highlight_clips(args.out, args.clip_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def _cmd_features(args: argparse.Namespace) -> int:
    from momentscan.extraction.features import extract_features

    try:
        result = extract_features(args.path, args.out, fps=args.fps)
    except ImportError as exc:
        print(f"momentscan: features stage needs the specialist45d package: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def _cmd_scene(args: argparse.Namespace) -> int:
    from momentscan.extraction.scene import extract_scene

    try:
        result = extract_scene(args.path, args.out, fps=args.fps)
    except ImportError as exc:
        print(f"momentscan: scene stage needs the specialist45d package: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def _cmd_tubelets(args: argparse.Namespace) -> int:
    from momentscan.subjects.tubelets import synthesize_tubelets

    result = synthesize_tubelets(args.path, args.out, fps=args.fps)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


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

    from momentscan.pipeline import run_pipeline
    from momentscan.stash import detections_path

    # ONE-COMMAND happy path: `run <video-or-clip>` — a video PATH as clip_id means
    # source=itself; when detections are missing and a source is known, run detect
    # INLINE (one-shot warm_init, no daemon needed) before the stage runner. The
    # daemon stays the operator path (warm, many clips); this is the first-15-minutes path.
    logging.disable(logging.INFO)   # cascade banners + stage lines ARE the digestible log
    p = Path(args.clip_id).expanduser()
    if p.suffix.lower() in (".mp4", ".mov", ".mkv", ".avi") and p.exists():
        args.source, args.clip_id = str(p), p.stem
    if args.source and not detections_path(args.out, args.clip_id).exists():
        from momentscan.extraction.detect import process_clip, warm_init
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
                          force=args.force, only=args.only, subject_query=args.subject)
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


def _cmd_doctor(args: argparse.Namespace) -> int:
    from momentscan.verify.doctor import render_text
    return render_text()


def _cmd_report(args: argparse.Namespace) -> int:
    from momentscan.surface.report import render_report
    result = render_report(args.out, args.clip_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def _cmd_analyzers(args: argparse.Namespace) -> int:
    from momentscan.analyzers import ANALYZERS, topo_order

    if args.json:
        from dataclasses import asdict
        print(json.dumps([asdict(a) for a in ANALYZERS], ensure_ascii=False, indent=2))
        return 0
    order = {a.name: i for i, a in enumerate(topo_order())}
    by_kind: dict[str, list] = {}
    for a in ANALYZERS:
        by_kind.setdefault(a.kind, []).append(a)
    for kind in ("stage", "unit", "engine"):
        print(f"\n── {kind} ──")
        for a in sorted(by_kind.get(kind, []), key=lambda a: order[a.name]):
            dep = (" ← " + ", ".join(a.depends)) if a.depends else ""
            print(f"  {a.name:<13} [{a.output_kind:<11}] {a.model}")
            print(f"  {'':<13}  → {a.artifact}{dep}")
    print("\n── run order (DAG) ──\n  " + " → ".join(a.name for a in topo_order()))
    return 0


def _cmd_products(args: argparse.Namespace) -> int:
    from momentscan import analyzers as A

    if args.json:
        from dataclasses import asdict
        print(json.dumps([asdict(p) for p in A.PRODUCTS], ensure_ascii=False, indent=2))
        return 0
    print("\n── products (vertical read-map · what each deliverable reads across the horizontal pipeline) ──")
    for p in A.PRODUCTS:
        print(f"\n{p.name:<11} [{p.state:<6}] {p.operation}")
        print(f"  {p.definition}")
        print(f"  emitted by : {', '.join(p.emitted_by)}")
        print("  reads      :")
        for stage, keys in p.reads:
            art = A.get(stage).artifact
            ks = ", ".join(keys) if keys else "—"
            print(f"    {stage:<13}{art:<22} ← {ks}")
        print(f"  outputs    : {', '.join(p.outputs)}")
        if p.note:
            print(f"  note       : {p.note}")
    print("\n  (producer view: `momentscan analyzers` · frozen = own module earned, molten = kept consolidated on purpose)")
    return 0


def _cmd_cascade(args: argparse.Namespace) -> int:
    """The data lineage stated plainly: INPUT → ①FEATURE/②GATE (intermediate, stash)
    → ③PRODUCT (FINAL, egress). DERIVED from ANALYZERS (.artifact) + PRODUCTS (.egress),
    so it cannot drift from what actually runs. Same ①②③ as the run-watch banners."""
    from momentscan import analyzers as A
    from momentscan.analyzers import topo_order

    stages = [a for a in topo_order() if a.kind == "stage"]
    if args.json:
        # the machine view = the Storage port contract: what to fetch (input), what
        # is scratch (intermediate), what to upload (final/egress).
        print(json.dumps({
            "input": {"source": "video → frames", "weights": sorted({a.model for a in stages})},
            "intermediate": {a.name: a.artifact for a in stages} | {"gate": "gate_trace.parquet"},
            "final": {p.name: list(p.egress) for p in A.PRODUCTS},
        }, ensure_ascii=False, indent=2))
        return 0

    print("\n── cascade · data lineage  (INPUT → INTERMEDIATE → FINAL) ──")
    print("\nINPUT   (crosses the service boundary inward · S3-in / Job)")
    print(f"  {'source video':<13} → frames           (FileSource, decode @ fps)")
    print(f"  {'frozen weights':<13}   per-stage models   (see `momentscan analyzers`; tracked by freshness)")

    print("\n① FEATURE EXTRACTION   (intermediate — stays in the stash)")
    for a in stages:
        print(f"  {a.name:<12} → {a.artifact:<22} ({a.model})")

    print("\n② GATE   (intermediate — the decision trace)")
    print(f"  {'portrait':<12} → {'gate_trace.parquet':<22} (gates.evaluate ladder · T0 valid · T1 sharp · T2 view)")

    print("\n③ PRODUCT   (FINAL — crosses the boundary outward · S3-out / Result)")
    for p in A.PRODUCTS:
        fin = ", ".join(p.egress) if p.egress else "(none wired)"
        inter = [o for o in p.outputs if o not in p.egress]
        flag = "" if p.egress else "   ⚠ no clean deliverable yet"
        print(f"  {p.name:<12} → {fin}{flag}")
        if inter:
            print(f"  {'':<12}   (intermediate: {', '.join(inter)})")
    print("\n  producer detail → `momentscan analyzers`   ·   vertical read-map → `momentscan products`")
    return 0


def _cmd_frame(args: argparse.Namespace) -> int:
    """The canonical-frame contract stated plainly — origin/axes/scale/basis/reference
    + provenance. The coordinate analogue of gates.py / `momentscan products`: ONE
    declared frame every consumer (appearance/portrait/select/inspector/eval) reads
    via signals.py (verified single home)."""
    from momentscan.domains.geometry import CANONICAL_FRAME as F
    from momentscan.domains.geometry import frame_provenance

    pv = frame_provenance()
    if args.json:
        from dataclasses import asdict
        d = asdict(F)
        d["reference"] = str(F.reference)
        d["provenance"] = pv
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return 0
    ref = pv["reference"] + ("  [sha %s · %d verts · present]" % (pv["sha256"], pv["n_verts"])
                             if pv.get("present") else "  [MISSING]")
    flip = tuple(int(s) for s in F.axis_flip)
    print(f"\n── canonical frame  ({F.name}) ──")
    print(f"  reference : {ref}")
    print(f"  origin    : {F.origin}   (translation removed; no fixed anatomical anchor)")
    print(f"  axes      : flip (x,y,z)={flip} = π about x → {F.handedness}-handed (+x right, +y up, +z toward camera)")
    print(f"              guard: det(flip)=+1, a proper rotation (y-only would be a reflection)")
    print(f"  scale     : {F.scale}   (UNITLESS — no metric length)")
    print(f"  basis     : distribution/PCA = {F.basis_full} verts (incl. iris)  ·  template/ratios = {F.basis_mesh} (excl. iris)")
    print(f"              ⚠ two bases coexist — unify candidate (settle under split-half eval · STEP 2)")
    print(f"  pose      : {F.pose_convention} — referenced, not redefined")
    print(f"  consumers : geometry.canonicalize / norm468 / template · pose.euler_from_transform  (verified single home)")
    return 0


def _cmd_graph(args: argparse.Namespace) -> int:
    from momentscan.verify import graph

    if args.json:
        from dataclasses import asdict
        print(json.dumps({"nodes": [asdict(n) for n in graph.nodes()], "edges": graph.edges()},
                         ensure_ascii=False, indent=2))
        return 0
    print(graph.render_text())
    return 0


def _cmd_replay_check(args: argparse.Namespace) -> int:
    from momentscan.verify.replay import replay_check

    clips = [args.clip_id] if args.clip_id else ["cap_1"]
    print("\n── replay-check (re-run CPU stages on frozen inputs → diff vs refs; ignore volatile + float tol) ──")
    print("  (a FAIL = the on-disk ref is not reproduced; refresh a stale ref by re-running the pipeline)")
    n_fail = 0
    for c in clips:
        ok, report = replay_check(args.out, c, fps=args.fps)
        if ok:
            print(f"  ✓ {c}: behaviour reproduced")
        else:
            n_fail += 1
            print(f"  ✗ {c}:")
            for art, diffs in report.items():
                print(f"      {art}: {len(diffs)} diff(s)")
                for d in diffs[:4]:
                    print(f"        {d}")
    print(f"\n  {n_fail} clip(s) drifted")
    return 1 if n_fail else 0


def _cmd_check(args: argparse.Namespace) -> int:
    from momentscan import analyzers as A, gates
    from momentscan.pipeline import RUNNERS, UPSTREAM_OF_RUNNER

    problems = A.registry_drift(RUNNERS.keys(), UPSTREAM_OF_RUNNER) + gates.gate_drift()
    errs = [m for sev, m in problems if sev == "error"]
    warns = [m for sev, m in problems if sev == "warn"]
    print("\n── registry check (STEPS ⇄ ANALYZERS ⇄ PRODUCTS) ──")
    for m in errs:
        print(f"  ✗ {m}")
    for m in warns:
        print(f"  ⚠ {m}")
    if not errs and not warns:
        print("  ✓ consistent")
    print(f"\n  {len(errs)} error(s), {len(warns)} warning(s)")
    return 1 if errs else 0


def _cmd_fashion(args: argparse.Namespace) -> int:
    try:
        from momentscan.extraction.fashion import extract_fashion
    except ImportError as exc:
        print(f"momentscan: fashion stage needs torch/transformers: {exc}", file=sys.stderr)
        return 2
    result = extract_fashion(args.out, args.clip_id, fps=args.fps)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def _cmd_headpose(args: argparse.Namespace) -> int:
    try:
        from momentscan.extraction.headpose import extract_headpose
    except ImportError as exc:
        print(f"momentscan: headpose stage needs onnxruntime: {exc}", file=sys.stderr)
        return 2
    result = extract_headpose(args.out, args.clip_id, fps=args.fps)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def _cmd_emotion(args: argparse.Namespace) -> int:
    from momentscan.domains.emotion import extract_emotion
    result = extract_emotion(args.out, args.clip_id, fps=args.fps)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def _cmd_parse(args: argparse.Namespace) -> int:
    try:
        from momentscan.extraction.parse import extract_parse
    except ImportError as exc:
        print(f"momentscan: parse stage needs torch/transformers: {exc}", file=sys.stderr)
        return 2
    result = extract_parse(args.out, args.clip_id, fps=args.fps)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def _cmd_portrait(args: argparse.Namespace) -> int:
    from momentscan.products.portrait import select_portrait

    result = select_portrait(args.out, args.clip_id, fps=args.fps)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def _cmd_highlight_lang(args: argparse.Namespace) -> int:
    try:
        from momentscan.products.highlight_lang import score_highlight_lang
    except ImportError as exc:
        print(f"momentscan: highlight-lang needs torch/transformers/opencv: {exc}", file=sys.stderr)
        return 2
    result = score_highlight_lang(args.out, args.clip_id, expectation=args.expectation, fps=args.fps)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def _cmd_crops(args: argparse.Namespace) -> int:
    from momentscan.subjects.crops import extract_crops

    result = extract_crops(args.source, args.out, args.clip_id, fps=args.fps)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def _cmd_inspect(args: argparse.Namespace) -> int:
    from momentscan.surface.inspector import render_tubelet_inspect

    result = render_tubelet_inspect(args.out, args.clip_id, fps=args.fps,
                                    video_path=args.source)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def _cmd_viz(args: argparse.Namespace) -> int:
    from momentscan.stash import candidates_path, process_trace_path
    from momentscan.surface.cards import (
        render_attribution, render_highlight_clips, render_identity_strip,
        render_portrait_card, render_process_timeline, render_select_timeline,
    )

    result = render_attribution(args.path, args.out, fps=args.fps)
    clip_id = Path(args.path).stem
    if process_trace_path(Path(args.out), clip_id).exists():
        result["process_timeline"] = render_process_timeline(args.out, clip_id)
    result["identity_strip"] = render_identity_strip(args.path, args.out, fps=args.fps)
    if candidates_path(Path(args.out), clip_id).exists():
        result["select_timeline"] = render_select_timeline(args.out, clip_id, fps=args.fps)
        result["portrait_card"] = render_portrait_card(args.out, clip_id)
        result["highlight_clips"] = render_highlight_clips(
            args.out, clip_id, video_path=args.path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _cmd_attribute(args: argparse.Namespace) -> int:
    try:
        from momentscan.subjects.attribute import attribute_clip
    except ImportError as exc:
        print(
            f"momentscan: attribute stage needs the step0b extra (torch/depth): {exc}\n"
            "install with: uv sync --extra step0b",
            file=sys.stderr,
        )
        return 2
    result = attribute_clip(args.path, args.out, fps=args.fps, stride=args.stride)
    shown = {k: v for k, v in result.items() if k != "samples"}
    shown["n_samples"] = len(result.get("samples") or [])
    print(json.dumps(shown, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


def main(argv: list[str] | None = None) -> int:
    # Logging options live on a shared parent so they're accepted both before
    # AND after the subcommand (`momentscan serve --log-format human`). The
    # parent's defaults are SUPPRESS so a subcommand parse can't clobber a
    # value given before the subcommand; real defaults sit on the top parser.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--log-level", default=argparse.SUPPRESS, help="log level (default INFO)")
    common.add_argument(
        "--log-format", default=argparse.SUPPRESS, choices=("auto", "json", "human"),
        help="auto = human on a TTY, JSON when redirected (default auto)",
    )

    p = argparse.ArgumentParser(prog="momentscan", description="momentscan pipeline")
    p.add_argument("--log-level", default="INFO", help=argparse.SUPPRESS)
    p.add_argument("--log-format", default="auto", choices=("auto", "json", "human"), help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="stage", required=True)

    pi = sub.add_parser("ingest", parents=[common], help="Layer 0 — decode + log + trace a clip or directory")
    pi.add_argument("path", help="video file, or a directory of clips (batch)")
    pi.add_argument("--out", default="output", help="output root (default ./output)")
    pi.add_argument("--fps", type=int, default=None, help="target fps downsample (default: native)")
    pi.add_argument("--no-trace", action="store_true", help="skip the trace.mp4, log only")
    pi.set_defaults(func=_cmd_ingest)

    ps = sub.add_parser("serve", parents=[common], help="daemon — warm detect + control plane (UDS)")
    ps.add_argument("--socket", default=None, help="control socket path (default ~/.cache/momentscan/daemon.sock)")
    ps.add_argument("--out", default="output", help="output root (default ./output)")
    ps.add_argument("--fps", type=int, default=None, help="default target fps for jobs (overridable per request)")
    ps.add_argument("--model-root", default=None, help="insightface model root (default ~/.insightface)")
    ps.set_defaults(func=_cmd_serve)

    psh = sub.add_parser("serve-http", parents=[common],
                         help="외부 HTTP 면 — C1 Job/Result 서버 (알파 배포; POST /jobs)")
    psh.add_argument("--port", type=int, default=8080)
    psh.add_argument("--out", default="output", help="stash root")
    psh.add_argument("--fps", type=int, default=6, help="Job.fps 생략 시 기본값")
    psh.add_argument("--products", default="likeness",
                     help="열린 제품 (단계 배포 스위치, 쉼표구분; 기본 likeness)")
    psh.add_argument("--eureka", default=None,
                     help="Eureka 서버 URL (예: http://eureka.corp:8761/eureka) — 주면 등록")
    psh.add_argument("--advertise-host", default=None,
                     help="Eureka에 광고할 host/IP (기본: 자동 감지)")
    psh.add_argument("--app-name", default="momentscan", help="Eureka 앱 이름")
    psh.set_defaults(func=_cmd_serve_http)

    pac = sub.add_parser("api-check", parents=[common],
                         help="REST API 계약 테스트 — 인프로세스 서버 vs docs/api/openapi.yaml")
    pac.set_defaults(func=_cmd_api_check)

    pp = sub.add_parser("process", parents=[common], help="trigger one clip through the running warm daemon")
    pp.add_argument("path", help="video file to analyze")
    pp.add_argument("--fps", type=int, default=None, help="target fps for this job")
    pp.add_argument("--socket", default=None, help="daemon socket (default ~/.cache/momentscan/daemon.sock)")
    pp.set_defaults(func=_cmd_process)

    pst = sub.add_parser("status", parents=[common], help="ping the daemon + bus stats")
    pst.add_argument("--socket", default=None, help="daemon socket (default ~/.cache/momentscan/daemon.sock)")
    pst.set_defaults(func=_cmd_status)

    psh = sub.add_parser("shutdown", parents=[common], help="stop the running daemon")
    psh.add_argument("--socket", default=None, help="daemon socket (default ~/.cache/momentscan/daemon.sock)")
    psh.set_defaults(func=_cmd_shutdown)

    pa = sub.add_parser("attribute", parents=[common],
                        help="step0b — rider roles by depth vote (needs `uv sync --extra step0b`)")
    pa.add_argument("path", help="video file (must already be processed → detections.parquet)")
    pa.add_argument("--out", default="output", help="stash root used by the detect stage")
    pa.add_argument("--fps", type=int, default=None, help="MUST match the fps the detect stage used")
    pa.add_argument("--stride", type=int, default=5, help="sample every Nth co-occurrence frame")
    pa.set_defaults(func=_cmd_attribute)

    pt = sub.add_parser("tubelets", parents=[common],
                        help="Step 0 synthesis — detections+attribution+scene-phase → tubelets.parquet")
    pt.add_argument("path", help="video file (already processed + attributed)")
    pt.add_argument("--out", default="output", help="stash root")
    pt.add_argument("--fps", type=int, default=None, help="MUST match the fps the detect stage used")
    pt.set_defaults(func=_cmd_tubelets)

    pv = sub.add_parser("viz", parents=[common],
                        help="render attribution_trace.mp4 + contact_sheet.jpg from the stash")
    pv.add_argument("path", help="video file (already processed + attributed)")
    pv.add_argument("--out", default="output", help="stash root")
    pv.add_argument("--fps", type=int, default=None, help="MUST match the fps the detect stage used")
    pv.set_defaults(func=_cmd_viz)

    psc = sub.add_parser("scene", parents=[common],
                         help="E012 — frame-grain scene embeddings (DINOv2 CLS) -> scene.parquet")
    psc.add_argument("path", help="video file")
    psc.add_argument("--out", default="output", help="stash root")
    psc.add_argument("--fps", type=int, default=None, help="MUST match the fps the detect stage used")
    psc.set_defaults(func=_cmd_scene)

    pf = sub.add_parser("features", parents=[common],
                        help="Track A extractor — tubelets → features/A.parquet (specialist45d)")
    pf.add_argument("path", help="video file (tubelets must exist)")
    pf.add_argument("--out", default="output", help="stash root")
    pf.add_argument("--fps", type=int, default=None, help="MUST match the fps the detect stage used")
    pf.set_defaults(func=_cmd_features)

    psel = sub.add_parser("select", parents=[common],
                          help="3c — 공유 채점 기판 + likeness 후보 → candidates.jsonl")
    psel.add_argument("clip_id", help="clip id (stash dir name)")
    psel.add_argument("--out", default="output", help="stash root")
    psel.add_argument("--fps", type=int, default=6, help="fps the pipeline ran with")
    psel.set_defaults(func=_cmd_select)

    phl = sub.add_parser("highlight", parents=[common],
                         help="3d — 합동 WHEN 악구 → highlight.json + highlights/*.mp4")
    phl.add_argument("clip_id", help="clip id (stash dir name)")
    phl.add_argument("--out", default="output", help="stash root")
    phl.add_argument("--fps", type=int, default=6, help="fps the pipeline ran with")
    phl.set_defaults(func=_cmd_highlight)

    prun = sub.add_parser("run", parents=[common],
                          help="video/clip → full pipeline → report (one-command; inline detect when needed)")
    prun.add_argument("clip_id", help="clip id in the stash, OR a video path (runs detect inline)")
    prun.add_argument("--source", default=None, help="original video (needed for source-based stages)")
    prun.add_argument("--out", default="output", help="stash root")
    prun.add_argument("--fps", type=int, default=6, help="fps the pipeline ran with")
    prun.add_argument("--force", action="store_true", help="re-run even if artifacts exist")
    prun.add_argument("--only", nargs="*", default=None, help="run only these stages")
    prun.add_argument("--subject", default=None,
                      help="subject query (C2): 'seat' (default rule) or 'face:<photo>' — "
                           "constitute the run around THIS person. Re-querying a processed "
                           "clip needs --force (or a fresh --out)")
    prun.set_defaults(func=_cmd_run)

    pdoc = sub.add_parser("doctor", parents=[common],
                          help="check external deps (models·binaries·stacks) — checker, not fetcher")
    pdoc.set_defaults(func=_cmd_doctor)

    prep = sub.add_parser("report", parents=[common],
                          help="render <clip>/index.html — the result-consumer front door")
    prep.add_argument("clip_id", help="clip id (stash dir name)")
    prep.add_argument("--out", default="output", help="stash root")
    prep.set_defaults(func=_cmd_report)

    pan = sub.add_parser("analyzers", parents=[common],
                         help="introspect the analyzer registry (producers · output-kinds · DAG order)")
    pan.add_argument("--json", action="store_true", help="emit the full catalog as JSON")
    pan.set_defaults(func=_cmd_analyzers)

    ppr = sub.add_parser("products", parents=[common],
                         help="the product read-map (vertical: what each deliverable reads across stages)")
    ppr.add_argument("--json", action="store_true", help="emit the product map as JSON")
    ppr.set_defaults(func=_cmd_products)

    pcas = sub.add_parser("cascade", parents=[common],
                          help="data lineage stated plainly: INPUT → ①FEATURE/②GATE (stash) → ③PRODUCT (egress)")
    pcas.add_argument("--json", action="store_true", help="emit lineage as JSON (the Storage-port fetch/scratch/upload contract)")
    pcas.set_defaults(func=_cmd_cascade)

    pfr = sub.add_parser("frame", parents=[common],
                         help="the canonical-frame contract (origin/axes/scale/basis/reference + provenance)")
    pfr.add_argument("--json", action="store_true", help="emit the frame contract + provenance as JSON")
    pfr.set_defaults(func=_cmd_frame)

    pck = sub.add_parser("check", parents=[common],
                         help="reconcile the registry (STEPS ⇄ ANALYZERS ⇄ PRODUCTS) — exits nonzero on drift")
    pck.set_defaults(func=_cmd_check)

    pgr = sub.add_parser("graph", parents=[common],
                         help="the ONE declared graph: frame ingest → stages → units → engines → gates → products")
    pgr.add_argument("--json", action="store_true", help="emit nodes + edges as JSON")
    pgr.set_defaults(func=_cmd_graph)

    prp = sub.add_parser("replay-check", parents=[common],
                         help="re-run CPU stages on a clip's frozen inputs → diff vs on-disk refs (dynamic regression guard)")
    prp.add_argument("clip_id", nargs="?", help="clip id (default fixtures: cap_1, dual_3)")
    prp.add_argument("--out", default="output", help="stash root")
    prp.add_argument("--fps", type=int, default=6, help="fps the pipeline ran with")
    prp.set_defaults(func=_cmd_replay_check)

    pfa = sub.add_parser("fashion", parents=[common],
                         help="FashionCLIP enrichment on crop track → fashion.json (typed accessory attrs)")
    pfa.add_argument("clip_id", help="clip id (stash dir name; crop track must exist)")
    pfa.add_argument("--out", default="output", help="stash root")
    pfa.add_argument("--fps", type=int, default=6, help="fps the pipeline ran with")
    pfa.set_defaults(func=_cmd_fashion)

    php = sub.add_parser("headpose", parents=[common],
                         help="6DRepNet full-range head pose on crop track → headpose.parquet (profile-capable)")
    php.add_argument("clip_id", help="clip id (stash dir name; crop track must exist)")
    php.add_argument("--out", default="output", help="stash root")
    php.add_argument("--fps", type=int, default=6, help="fps the pipeline ran with")
    php.set_defaults(func=_cmd_headpose)

    pem = sub.add_parser("emotion", parents=[common],
                         help="HSEmotion+LibreFace fusion → emotion.json (per-person RIDE valence baseline)")
    pem.add_argument("clip_id", help="clip id (stash dir name; features + tubelets must exist)")
    pem.add_argument("--out", default="output", help="stash root")
    pem.add_argument("--fps", type=int, default=6, help="fps the pipeline ran with")
    pem.set_defaults(func=_cmd_emotion)

    ppr = sub.add_parser("parse", parents=[common],
                         help="face parsing on crop track → parse.parquet (occlusion signal for portrait gate)")
    ppr.add_argument("clip_id", help="clip id (stash dir name; crop track must exist)")
    ppr.add_argument("--out", default="output", help="stash root")
    ppr.add_argument("--fps", type=int, default=6, help="fps the pipeline ran with")
    ppr.set_defaults(func=_cmd_parse)

    ppt = sub.add_parser("portrait", parents=[common],
                         help="portrait selection — synthetic-criterion gate → projection → crop-track extraction")
    ppt.add_argument("clip_id", help="clip id (stash dir name; landmarks.parquet must exist)")
    ppt.add_argument("--out", default="output", help="stash root")
    ppt.add_argument("--fps", type=int, default=6, help="fps the pipeline ran with (MUST match)")
    ppt.set_defaults(func=_cmd_portrait)

    phl = sub.add_parser("highlight-lang", parents=[common],
                         help="context-conditioned highlight WHEN — signal+scene→sentence→LLM-judge vs attraction expectation")
    phl.add_argument("clip_id", help="clip id (stash dir name; detections/gate_trace + source window must exist)")
    phl.add_argument("--out", default="output", help="stash root")
    phl.add_argument("--fps", type=int, default=6, help="fps the pipeline ran with")
    phl.add_argument("--expectation", default="default", help="named attraction expectation (highlight_lang.EXPECTATIONS)")
    phl.set_defaults(func=_cmd_highlight_lang)

    pcr = sub.add_parser("crops", parents=[common],
                         help="persist clean per-subject crop tracks while source is live (data-retention)")
    pcr.add_argument("clip_id", help="clip id (stash dir name; tubelets.parquet must exist)")
    pcr.add_argument("--source", required=True, help="live original video (NOT retained after extraction)")
    pcr.add_argument("--out", default="output", help="stash root")
    pcr.add_argument("--fps", type=int, default=6, help="fps the pipeline ran with (MUST match)")
    pcr.set_defaults(func=_cmd_crops)

    pins = sub.add_parser("inspect", parents=[common],
                          help="interactive per-clip tubelet inspector → inspect/clip.html")
    pins.add_argument("clip_id", help="clip id (stash dir name)")
    pins.add_argument("--out", default="output", help="stash root")
    pins.add_argument("--fps", type=int, default=6, help="fps the pipeline ran with (MUST match)")
    pins.add_argument("--source", default=None,
                      help="original video → clean main + crop preview (else detect.mp4 fallback)")
    pins.set_defaults(func=_cmd_inspect)

    pap = sub.add_parser("appearance", parents=[common],
                         help="외형 레퍼런스 — landmark distribution reading → likeness.json")
    pap.add_argument("clip_id", help="clip id (stash dir name; landmarks.parquet must exist)")
    pap.add_argument("--out", default="output", help="stash root")
    pap.set_defaults(func=_cmd_appearance)

    pl_ = sub.add_parser("label", parents=[common],
                         help="labeling dashboard — sequential verdict UI over eval templates")
    pl_.add_argument("--out", default="output", help="stash root")
    pl_.add_argument("--port", type=int, default=8901)
    pl_.add_argument("--lane", default="default",
                     choices=("default", "portrait", "segment"),
                     help="labeling lane — each lane keeps its own pairs/verdicts files"
                          " (frozen default lane untouched); segment = E010 clip-vs-clip")
    pl_.set_defaults(func=_cmd_label)

    pe = sub.add_parser("eval", parents=[common],
                        help="3d — score candidates vs eval/labels.jsonl, or --template <clip> to bootstrap labeling")
    pe.add_argument("--out", default="output", help="stash root")
    pe.add_argument("--template", default=None, metavar="CLIP_ID",
                    help="generate review sheet + label template for one clip")
    pe.add_argument("--rescore", action="store_true",
                    help="re-derive system preference from CURRENT features/policy vs frozen human winners")
    pe.add_argument("clips", nargs="*", help="clip ids to score (default: all with candidates)")
    pe.set_defaults(func=_cmd_eval)

    args = p.parse_args(argv)
    setup_logging(level=args.log_level, fmt=args.log_format, constants={"service": "momentscan"})
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

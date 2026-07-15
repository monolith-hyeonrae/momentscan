"""surfaces 가족 — 결과 표면/렌더: report · inspect · viz · label · highlight-lang."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _cmd_report(args: argparse.Namespace) -> int:
    from momentscan.surface.report import render_report
    result = render_report(args.out, args.clip_id)
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


def _cmd_inspect(args: argparse.Namespace) -> int:
    from momentscan.surface.inspector import render_tubelet_inspect

    result = render_tubelet_inspect(args.out, args.clip_id, fps=args.fps,
                                    video_path=args.source)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def _cmd_viz(args: argparse.Namespace) -> int:
    """렌더 애그리게이터 — 제품/스테이지별 렌더 커맨드를 하나로 흡수 (CLI 정리 2026-07-06).
    인자 = 비디오 경로(소스-기반 렌더 포함) 또는 clip_id(stash-순수 렌더만:
    타임라인·카드·highlight mp4[detect.mp4 폴백])."""
    from momentscan.store.stash import candidates_path, process_trace_path
    from momentscan.surface.cards import (
        render_appearance_card, render_attribution, render_highlight_clips,
        render_identity_strip, render_portrait_card, render_process_timeline,
        render_select_timeline,
    )

    p = Path(args.path).expanduser()
    result: dict = {}
    if p.is_file():                                     # 비디오 경로 — 소스-기반 렌더 포함
        clip_id = p.stem
        result = render_attribution(str(p), args.out, fps=args.fps)
        if process_trace_path(Path(args.out), clip_id).exists():
            result["process_timeline"] = render_process_timeline(args.out, clip_id)
        result["identity_strip"] = render_identity_strip(str(p), args.out, fps=args.fps)
        video = str(p)
    else:                                               # clip_id — stash-순수 렌더
        clip_id, video = args.path, None
        result["clip_id"] = clip_id
    if candidates_path(Path(args.out), clip_id).exists():
        result["select_timeline"] = render_select_timeline(args.out, clip_id, fps=args.fps or 6)
        result["portrait_card"] = render_portrait_card(args.out, clip_id)
        result["appearance_card"] = render_appearance_card(args.out, clip_id)
        result["highlight_clips"] = render_highlight_clips(args.out, clip_id, video_path=video)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _cmd_label(args: argparse.Namespace) -> int:
    from momentscan.evals.label_server import serve_labels

    serve_labels(args.out, port=args.port, lane=args.lane)
    return 0


def register(sub, common: argparse.ArgumentParser) -> None:
    pv = sub.add_parser("viz", parents=[common],
                        help="렌더 애그리게이터 — 비디오경로(소스 렌더 포함) 또는 clip_id(타임라인·카드·highlight mp4)")
    pv.add_argument("path", help="비디오 경로 또는 clip_id (stash-순수 렌더)")
    pv.add_argument("--out", default="output", help="stash root")
    pv.add_argument("--fps", type=int, default=None, help="MUST match the fps the detect stage used")
    pv.set_defaults(func=_cmd_viz)

    prep = sub.add_parser("report", parents=[common],
                          help="render <clip>/index.html — the result-consumer front door")
    prep.add_argument("clip_id", help="clip id (stash dir name)")
    prep.add_argument("--out", default="output", help="stash root")
    prep.set_defaults(func=_cmd_report)

    phl = sub.add_parser("highlight-lang", parents=[common],
                         help="context-conditioned highlight WHEN — signal+scene→sentence→LLM-judge vs attraction expectation")
    phl.add_argument("clip_id", help="clip id (stash dir name; detections/gate_trace + source window must exist)")
    phl.add_argument("--out", default="output", help="stash root")
    phl.add_argument("--fps", type=int, default=6, help="fps the pipeline ran with")
    phl.add_argument("--expectation", default="default", help="named attraction expectation (highlight_lang.EXPECTATIONS)")
    phl.set_defaults(func=_cmd_highlight_lang)

    pins = sub.add_parser("inspect", parents=[common],
                          help="interactive per-clip tubelet inspector → inspect/clip.html")
    pins.add_argument("clip_id", help="clip id (stash dir name)")
    pins.add_argument("--out", default="output", help="stash root")
    pins.add_argument("--fps", type=int, default=6, help="fps the pipeline ran with (MUST match)")
    pins.add_argument("--source", default=None,
                      help="original video → clean main + crop preview (else detect.mp4 fallback)")
    pins.set_defaults(func=_cmd_inspect)

    pl_ = sub.add_parser("label", parents=[common],
                         help="labeling dashboard — sequential verdict UI over eval templates")
    pl_.add_argument("--out", default="output", help="stash root")
    pl_.add_argument("--port", type=int, default=8901)
    pl_.add_argument("--lane", default="default",
                     choices=("default", "portrait", "segment"),
                     help="labeling lane — each lane keeps its own pairs/verdicts files"
                          " (frozen default lane untouched); segment = E010 clip-vs-clip")
    pl_.set_defaults(func=_cmd_label)

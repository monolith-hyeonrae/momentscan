"""verify 가족 — 검증 하니스: doctor(의존) · registry(선언정합) · api(계약) · replay(수치회귀) · eval(라벨채점)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _cmd_doctor(args: argparse.Namespace) -> int:
    from momentscan.verify.doctor import render_text
    return render_text()


def _cmd_check(args: argparse.Namespace) -> int:
    from momentscan import gates
    from momentscan.engine import analyzers as A
    from momentscan.engine.pipeline import RUNNERS, UPSTREAM_OF_RUNNER

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


def _cmd_api_check(args: argparse.Namespace) -> int:
    from momentscan.verify.apicheck import run_apicheck

    return run_apicheck()


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


def _cmd_eval(args: argparse.Namespace) -> int:
    from momentscan.evals.harness import make_template, score

    from momentscan.evals.harness import score_pairs

    if args.template:
        result = make_template(args.out, args.template)
    elif args.rescore:
        from momentscan.evals.harness import rescore_pairs
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


def register(sub, common: argparse.ArgumentParser) -> None:
    # ── verify 그룹 — 검증 하니스 (doctor·registry[구 check]·api·replay·eval) ──
    pvf = sub.add_parser("verify", parents=[common],
                         help="검증 — doctor(의존) · registry(선언정합) · api(계약) · replay(수치회귀) · eval(라벨채점)")
    vsub = pvf.add_subparsers(dest="verify_cmd", required=True,
                              metavar="{doctor,registry,api,replay,eval}")
    pdoc = vsub.add_parser("doctor", parents=[common],
                          help="check external deps (models·binaries·stacks) — checker, not fetcher")
    pdoc.set_defaults(func=_cmd_doctor)

    pck = vsub.add_parser("registry", parents=[common],
                         help="reconcile the registry (STEPS ⇄ ANALYZERS ⇄ PRODUCTS) — exits nonzero on drift")
    pck.set_defaults(func=_cmd_check)

    pac = vsub.add_parser("api", parents=[common],
                         help="REST API 계약 테스트 — 인프로세스 서버 vs docs/api/openapi.yaml")
    pac.set_defaults(func=_cmd_api_check)

    prp = vsub.add_parser("replay", parents=[common],
                         help="re-run CPU stages on a clip's frozen inputs → diff vs on-disk refs (dynamic regression guard)")
    prp.add_argument("clip_id", nargs="?", help="clip id (default fixtures: cap_1, dual_3)")
    prp.add_argument("--out", default="output", help="stash root")
    prp.add_argument("--fps", type=int, default=6, help="fps the pipeline ran with")
    prp.set_defaults(func=_cmd_replay_check)

    pe = vsub.add_parser("eval", parents=[common],
                        help="3d — score candidates vs eval/labels.jsonl, or --template <clip> to bootstrap labeling")
    pe.add_argument("--out", default="output", help="stash root")
    pe.add_argument("--template", default=None, metavar="CLIP_ID",
                    help="generate review sheet + label template for one clip")
    pe.add_argument("--rescore", action="store_true",
                    help="re-derive system preference from CURRENT features/policy vs frozen human winners")
    pe.add_argument("clips", nargs="*", help="clip ids to score (default: all with candidates)")
    pe.set_defaults(func=_cmd_eval)

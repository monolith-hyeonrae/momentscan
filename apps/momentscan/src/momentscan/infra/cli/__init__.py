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

    momentscan server start           # 외부 HTTP 면 (C1 실행기 — 배포 단위)
    momentscan server start --daemon  # UDS 웜 데몬 (연구/운영자)
    momentscan server status          # 두 면 다 점검
    momentscan server stop [--port|--daemon]

momentscan owns this vocabulary; visualbus only lends the wire mechanism
(``visualbus.control.call``). Cross-app fleet view stays generic:
``python -m visualbus.control ls``.

The verb families live one module each (구조 감사 접수 #5, 2026-07-15 분할):
run · server · verify · maps · surfaces. ``main`` here is assembly-only —
each family owns its handlers + parser defs behind ``register(sub, common)``.
"""

from __future__ import annotations

import argparse

from visualbus.structured_log import setup_logging

from . import maps, run, server, surfaces, verify


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

    # 가족별 파서 조립 — 각 모듈이 자기 동사군의 핸들러+파서를 소유 (register).
    run.register(sub, common)
    server.register(sub, common)
    verify.register(sub, common)
    maps.register(sub, common)
    surfaces.register(sub, common)

    args = p.parse_args(argv)
    setup_logging(level=args.log_level, fmt=args.log_format, constants={"service": "momentscan"})
    return args.func(args)

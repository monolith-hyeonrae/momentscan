"""server 가족 — 서버 수명주기 + 데몬 클라이언트: start(HTTP|--daemon UDS) · stop · status · process."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from visualbus.structured_log import setup_logging


def _cmd_serve(args: argparse.Namespace) -> int:
    """한 동사, 두 면: 기본 = 외부 HTTP 면(C1 실행기 — 배포·관측 단위),
    --daemon = UDS 웜 detect 제어면(연구/운영자 도구)."""
    if args.daemon:
        from momentscan.infra.serve.daemon import DEFAULT_SOCKET, serve

        from momentscan.perception.subjects.detect import DEFAULT_MODEL_ROOT

        return serve(
            socket_path=args.socket or DEFAULT_SOCKET,
            out_root=args.out,
            fps=args.fps or None,
            model_root=args.model_root or DEFAULT_MODEL_ROOT,
        )

    from momentscan.infra.serve.service import node_identity, serve_http

    # 서버의 로그는 기본으로 파일(~/logs/momentscan-{port}.log, JSON)에 떨어진다 —
    # 관측 레인(promtail→Loki)의 수집 지점이 파일이라, 셸 리다이렉트를 잊으면
    # 노드가 조용히 관측 불능이 되는 함정을 제거. `--log-file -` = stderr.
    stream = None
    log_path = args.log_file
    if log_path != "-":
        p = Path(log_path).expanduser() if log_path else (
            Path.home() / "logs" / f"momentscan-{args.port}.log")
        p.parent.mkdir(parents=True, exist_ok=True)
        stream = p.open("a", encoding="utf-8")
        print(f"logs → {p}")
    # 모든 로그 라인 본문에 node를 도장 — promtail이 이 필드를 라벨로 승격해
    # Loki에서 노드별 구분/집계가 된다 (멀티노드 운용의 "어느 서버?" 답).
    setup_logging(level=args.log_level, fmt=args.log_format, stream=stream,
                  constants={"service": "momentscan",
                             "node": node_identity(args.advertise_host, args.port)})
    serve_http(
        args.out,
        port=args.port,
        fps=args.fps or 6,
        open_products=tuple(args.products.split(",")) if args.products else ("likeness",),
        eureka_url=args.eureka,
        advertise_host=args.advertise_host,
        app_name=args.app_name,
        control_url=args.control_url,
        s3_bucket=args.s3_bucket,
    )
    return 0


# ── daemon client verbs — momentscan's own operator surface ──────────────────
# Thin wrappers over visualbus.control.call (the borrowed wire mechanism); the
# vocabulary, validation and defaults here are momentscan's.


def _call_daemon(args: argparse.Namespace, cmd: str, *, timeout: float | None = 5.0, **kw):
    from visualbus.control import call

    from momentscan.infra.serve.daemon import DEFAULT_SOCKET

    sock = Path(args.socket).expanduser() if args.socket else DEFAULT_SOCKET
    try:
        return call(sock, cmd, timeout=timeout, **kw)
    except (FileNotFoundError, ConnectionRefusedError):
        print(
            f"momentscan: no daemon at {sock} — start one with 'momentscan server start --daemon'",
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
    """운영자 표면: 이 머신에서 momentscan의 두 서버 면이 무엇이 돌고 있나 —
    serve(HTTP, 배포·관측 단위) + serve --daemon(UDS 웜, 연구/운영자)."""
    import urllib.request

    from visualbus.control import call

    from momentscan.infra.serve.daemon import DEFAULT_SOCKET

    ok_any = False
    sock = Path(args.socket).expanduser() if args.socket else DEFAULT_SOCKET
    print("── daemon (UDS 웜 제어면) ──")
    try:
        pong = call(sock, "ping", timeout=5.0)
        stats = call(sock, "stats", timeout=5.0)
        ok_any = True
        print(f"  ✓ {sock}")
        print(f"    {json.dumps({**pong, **stats}, ensure_ascii=False)}")
    except (FileNotFoundError, ConnectionRefusedError):
        print(f"  ✗ 없음 ({sock}) — `momentscan server start --daemon`으로 기동")

    print("── serve (외부 HTTP 면 · C1 실행기 · 관측 단위) ──")
    recs = sorted((Path.home() / ".cache" / "momentscan").glob("http-*.json"))
    if not recs:
        print("  ✗ 없음 — `momentscan server start`로 기동")
    for rp in recs:
        rec = json.loads(rp.read_text(encoding="utf-8"))
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{rec['port']}/health", timeout=3) as r:
                h = json.loads(r.read().decode("utf-8"))
            ok_any = True
            g = h.get("gpu") or {}
            gpu = (f" · gpu {g['self_mb']}/{g['used_mb']}/{g['total_mb']}MB(자기/사용/총)"
                   if g else "")
            print(f"  ✓ {h.get('node')} · {h.get('status')} · queue {h.get('queue')}"
                  f" · running {h.get('running') or '—'} · done {h.get('done')}"
                  f" · failed {h.get('failed')} · open {h.get('open_products')}"
                  f" · out {rec.get('out_root')}{gpu}")
        except Exception:
            print(f"  ⚠ {rec.get('node', rp.stem)} — 기록은 있으나 /health 무응답"
                  f" (죽은 프로세스면 정리: rm {rp})")
    return 0 if ok_any else 2


def _cmd_shutdown(args: argparse.Namespace) -> int:
    """한 동사, 두 면: --daemon = UDS 데몬 종료 · --port N = 그 HTTP 노드 종료 ·
    무인자 = 살아있는 것이 하나뿐이면 그것을 (모호하면 목록만)."""
    if args.daemon:
        result = _call_daemon(args, "shutdown")
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if not args.port:
        # 모호성 검사: HTTP 레코드 수 + 데몬 sock 존재
        from momentscan.infra.serve.daemon import DEFAULT_SOCKET
        recs = sorted((Path.home() / ".cache" / "momentscan").glob("http-*.json"))
        sock = Path(args.socket).expanduser() if args.socket else DEFAULT_SOCKET
        alive = [f"--port {json.loads(r.read_text(encoding='utf-8'))['port']}" for r in recs] \
            + (["--daemon"] if sock.exists() else [])
        if len(alive) != 1:
            print("무엇을 종료할지 지정 필요:" if alive else "종료할 서버 없음 (status로 확인)")
            for a in alive:
                print(f"  momentscan server stop {a}")
            return 2
        if alive[0] == "--daemon":
            result = _call_daemon(args, "shutdown")
            print(json.dumps(result, ensure_ascii=False))
            return 0
        args.port = int(alive[0].split()[-1])
    return _shutdown_http(args.port)


def _shutdown_http(port: int) -> int:
    """serve의 HTTP 면 우아한 종료 — 런타임 레코드로 pid를 찾아 SIGTERM
    (finally 정리: 유레카 즉시 해지 + 레코드 삭제). 원격 shutdown 엔드포인트는
    일부러 없다 — 네트워크에서 끌 수 있는 서비스는 footgun."""
    import os
    import signal
    import time as _time

    rp = Path.home() / ".cache" / "momentscan" / f"http-{port}.json"
    if not rp.exists():
        print(f"포트 {port}의 런타임 레코드 없음 — 이미 꺼져 있거나 kill -9 잔재는 status로 확인")
        return 2
    rec = json.loads(rp.read_text(encoding="utf-8"))
    pid = rec.get("pid")
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        rp.unlink(missing_ok=True)
        print(f"프로세스 {pid} 이미 없음 — 죽은 레코드 정리함")
        return 0
    for _ in range(50):                                  # 우아한 종료 대기 (최대 ~10s)
        if not rp.exists():
            print(f"✓ {rec.get('node')} 종료 (유레카 해지·레코드 삭제 완료)")
            return 0
        _time.sleep(0.2)
    print(f"⚠ {rec.get('node')} 종료 신호는 보냈으나 레코드가 남아 있음 — 잡 처리 중이면 대기, 아니면 status 확인")
    return 1


def register(sub, common: argparse.ArgumentParser) -> None:
    # ── server 그룹 — 한 대상(서버)의 수명주기 동사는 서브커맨드로 (CLI 정리 2단) ──
    psv = sub.add_parser("server", parents=[common],
                         help="서버 수명주기 — start [--daemon] · stop · status · process")
    ssub = psv.add_subparsers(dest="server_cmd", required=True, metavar="{start,stop,status,process}")

    ps = ssub.add_parser("start", parents=[common],
                         help="기동 — 기본: 외부 HTTP 면(C1 실행기) · --daemon: UDS 웜 detect 제어면")
    ps.add_argument("--daemon", action="store_true", help="UDS 웜 데몬 모드 (연구/운영자)")
    ps.add_argument("--port", type=int, default=8080, help="HTTP 포트")
    ps.add_argument("--out", default="output", help="stash root")
    ps.add_argument("--fps", type=int, default=None, help="분석 fps (HTTP 기본 6)")
    ps.add_argument("--products", default="likeness",
                    help="열린 제품 (단계 배포 스위치, 쉼표구분)")
    ps.add_argument("--eureka", default=None,
                    help="Eureka 서버 URL (예: http://eureka:8761/eureka) — 주면 등록")
    ps.add_argument("--advertise-host", default=None, help="광고할 host/IP (기본 자동 감지)")
    ps.add_argument("--app-name", default="momentscan", help="Eureka 앱 이름")
    ps.add_argument("--control-url", default=None,
                    help="회사 control 베이스 URL — 주면 디스패치 방언 수신(/video/process/*)"
                         "+완료 콜백(company.py)이 열림")
    ps.add_argument("--s3-bucket", default=None,
                    help="상대 S3 key 소스의 해석 버킷 (로컬 경로 소스는 버킷 불요)")
    ps.add_argument("--log-file", default=None,
                    help="로그 파일 (기본 ~/logs/momentscan-{port}.log · '-'=stderr)")
    ps.add_argument("--socket", default=None, help="[--daemon] control socket path")
    ps.add_argument("--model-root", default=None, help="[--daemon] insightface model root")
    ps.set_defaults(func=_cmd_serve)

    psh = ssub.add_parser("stop", parents=[common],
                          help="종료 — --port N: HTTP 노드 · --daemon: UDS 데몬 · 무인자: 하나뿐이면 그것")
    psh.add_argument("--port", type=int, default=None, help="종료할 HTTP 노드 포트")
    psh.add_argument("--daemon", action="store_true", help="UDS 데몬 종료")
    psh.add_argument("--socket", default=None, help="daemon socket (default ~/.cache/momentscan/daemon.sock)")
    psh.set_defaults(func=_cmd_shutdown)

    pst = ssub.add_parser("status", parents=[common],
                          help="두 서버 면 점검 — HTTP 노드(레코드→/health 프로브) + UDS 데몬")
    pst.add_argument("--socket", default=None, help="daemon socket (default ~/.cache/momentscan/daemon.sock)")
    pst.set_defaults(func=_cmd_status)

    pp = ssub.add_parser("process", parents=[common], help="웜 데몬으로 클립 하나 처리 (데몬 클라이언트)")
    pp.add_argument("path", help="video file to analyze")
    pp.add_argument("--fps", type=int, default=None, help="target fps for this job")
    pp.add_argument("--socket", default=None, help="daemon socket (default ~/.cache/momentscan/daemon.sock)")
    pp.set_defaults(func=_cmd_process)

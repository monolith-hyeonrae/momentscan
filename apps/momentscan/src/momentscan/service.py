"""service — 외부 HTTP 면: C1 Job/Result 계약의 서버 실행기 (알파 배포).

daemon.py(UDS, warm 제어면 — 운영자용)와 별개의 **외부 경계**: 회사 게이트웨이/
서비스가 Eureka에서 이 앱을 이름으로 찾아 HTTP로 처리를 요청한다 (contracts.md C1 v1).

  POST /jobs        Job JSON → 202 {clip_id, status, output_prefix, poll}
                    (완료된 clip_id 재요청 = 200 + 기존 Result, 재계산 없음 = 멱등)
  GET  /jobs/{id}   상태 조회 — queued | running | done | failed (+Result)
  GET  /health      {"status":"UP", …}   (Eureka healthCheckUrl · ops)
  GET  /info        앱 메타               (Eureka statusPageUrl)

설계 결정:
- **transport-agnostic 본체**: 처리의 실체는 `JobRunner.submit(job dict)` →
  result dict. HTTP는 그 어댑터일 뿐이라, Kafka consumer가 와도 같은 함수를 문다.
- **단일 워커 직렬화**: GPU 7.6GB 한 장 — 잡은 FIFO 큐로 한 번에 하나.
  warm detect는 워커에 캐시(첫 잡만 모델 로드).
- **멱등 = 파이프라인 resumability 재활용**: 같은 clip_id → 같은 stash 경로,
  존재하는 산출물은 stage-probe로 skip. result.json 있으면 그 경로들 즉시 반환.
- **egress = 선언에서 파생**: 어떤 파일이 밖으로 나가는가는 analyzers.PRODUCTS
  의 egress 선언 ∩ 열린 제품(단계 배포 스위치) — 코드에 목록 중복 없음.
- 입력 video: 로컬 경로 · file:// · s3:// (s3는 boto3 lazy import — 로컬 알파는
  boto3 없이 동작). 출력: output_uri 생략=stash 경로 반환 / 로컬 dir=복사 /
  s3://prefix=업로드, 항상 **저장 경로를 Result로 반환**.
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from momentscan.analyzers import PRODUCTS
from momentscan.stash import clip_dir, detections_path, read_result, write_job, write_result

log = logging.getLogger("momentscan.service")

APP_NAME = "momentscan"
RESULT_SCHEMA = "momentscan.result/v1"
ALL_PRODUCTS = tuple(p.name for p in PRODUCTS)
EGRESS = {p.name: p.egress for p in PRODUCTS}          # 제품 → 반출 파일 (선언이 단일 권위)


# ── 소스 반입 / 결과 반출 (S3 | 로컬) ─────────────────────────────────────────
def _s3():
    import boto3                                        # lazy — 로컬 알파는 불필요
    return boto3.client("s3")


def _split_s3(uri: str) -> tuple[str, str]:
    u = urllib.parse.urlparse(uri)
    return u.netloc, u.path.lstrip("/")


def fetch_source(source_uri: str, cache_dir: Path) -> Path:
    """비디오 주소 → 로컬 경로. s3://는 캐시로 내려받고, 로컬/file://는 그대로."""
    if source_uri.startswith("s3://"):
        bucket, key = _split_s3(source_uri)
        dst = cache_dir / Path(key).name
        if not dst.exists():
            cache_dir.mkdir(parents=True, exist_ok=True)
            t0 = time.perf_counter()
            _s3().download_file(bucket, key, str(dst))
            log.info("service.fetch", extra={"uri": source_uri,
                                             "bytes": dst.stat().st_size,
                                             "s": round(time.perf_counter() - t0, 1)})
        return dst
    p = Path(source_uri.removeprefix("file://")).expanduser()
    if not p.is_file():
        raise FileNotFoundError(f"source not found: {source_uri}")
    return p


def collect_egress(cdir: Path, products: tuple[str, ...]) -> dict[str, list[Path]]:
    """열린 제품의 반출 파일을 선언(PRODUCTS.egress)에서 수집. 항상 +provenance."""
    out: dict[str, list[Path]] = {}
    for prod in products:
        found = [f for pat in EGRESS[prod] for f in sorted(cdir.glob(pat)) if f.is_file()]
        if found:
            out[prod] = found
    if (cdir / "provenance.json").is_file():
        out["provenance"] = [cdir / "provenance.json"]
    return out


def deliver(cdir: Path, clip_id: str, files: dict[str, list[Path]],
            output_uri: str | None) -> tuple[str, dict[str, list[str]]]:
    """반출 파일을 output_uri로 옮기고 (실제 저장 prefix, 제품→경로들)을 반환."""
    if not output_uri:                                  # 생략 = stash가 곧 저장소
        return str(cdir), {k: [str(p) for p in v] for k, v in files.items()}
    outputs: dict[str, list[str]] = {}
    if output_uri.startswith("s3://"):
        bucket, prefix = _split_s3(output_uri.rstrip("/"))
        s3 = _s3()
        for k, paths in files.items():
            outputs[k] = []
            for p in paths:
                key = f"{prefix}/{clip_id}/{p.relative_to(cdir)}"
                s3.upload_file(str(p), bucket, key)
                outputs[k].append(f"s3://{bucket}/{key}")
        return f"s3://{bucket}/{prefix}/{clip_id}", outputs
    root = Path(output_uri).expanduser() / clip_id      # 로컬 dir 지정 = 복사
    for k, paths in files.items():
        outputs[k] = []
        for p in paths:
            dst = root / p.relative_to(cdir)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
            outputs[k].append(str(dst))
    return str(root), outputs


# ── Job 실행기 (transport-agnostic 본체) ─────────────────────────────────────
class JobRunner:
    """FIFO 단일 워커: Job 수리 → (detect →) run_pipeline → egress 반출 → Result."""

    def __init__(self, out_root: str, *, fps_default: int = 6,
                 open_products: tuple[str, ...] = ("likeness",), node: str = "local"):
        self.out_root = out_root
        self.fps_default = fps_default
        # 노드 정체성 ("host:port") — 멀티노드 운용에서 "어느 서버가 이 잡을
        # 처리했나"의 답. Result·/health·/info·모든 로그 라인(constants)에 도장.
        self.node = node
        self.open_products = tuple(p for p in open_products if p in ALL_PRODUCTS)
        self.jobs: dict[str, dict] = {}                 # clip_id → {status, job, result, error}
        self._q: list[str] = []
        self._cv = threading.Condition()
        self._warm = None                               # detect 모델 캐시 (첫 잡만 로드)
        self.started_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
        threading.Thread(target=self._work, name="job-worker", daemon=True).start()

    # 수리(accept): 검증 + 멱등 단락 + 큐잉. HTTP/Kafka 어느 쪽이든 이 함수를 문다.
    def submit(self, job: dict) -> tuple[int, dict]:
        src = job.get("source_uri")
        clip_id = job.get("clip_id") or (Path(str(src)).stem if src else None)
        if not clip_id:
            return 400, {"error": "clip_id or source_uri required"}
        bad = [p for p in job.get("products") or [] if p not in ALL_PRODUCTS]
        if bad:
            return 400, {"error": f"unknown products {bad} (known: {list(ALL_PRODUCTS)})"}
        job = {**job, "clip_id": clip_id}

        prior = read_result(Path(self.out_root), clip_id)
        with self._cv:
            st = self.jobs.get(clip_id)
            if st and st["status"] in ("queued", "running"):
                return 202, self._ticket(clip_id, st["status"])
            if prior and prior.get("ok") and not (st and st["status"] == "failed"):
                # 멱등: 완료 기록 존재 → 재계산 없이 저장 경로 반환 (Kafka 재전송 안전)
                self.jobs[clip_id] = {"status": "done", "job": job, "result": prior}
                log.info("service.job.idempotent", extra={"clip_id": clip_id})
                return 200, prior
            self.jobs[clip_id] = {"status": "queued", "job": job,
                                  "queued_iso": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            self._q.append(clip_id)
            self._cv.notify()
        log.info("service.job.accepted", extra={"clip_id": clip_id, "queue": len(self._q)})
        return 202, self._ticket(clip_id, "queued")

    def status(self, clip_id: str) -> tuple[int, dict]:
        st = self.jobs.get(clip_id)
        if st is None:
            prior = read_result(Path(self.out_root), clip_id)   # 재시작 후에도 done 조회 가능
            if prior:
                return 200, prior
            return 404, {"error": f"unknown job {clip_id}"}
        if st["status"] == "done":
            return 200, st["result"]
        if st["status"] == "failed":
            return 200, {"clip_id": clip_id, "ok": False, "status": "failed", "failure": st.get("error")}
        return 200, self._ticket(clip_id, st["status"])

    def _ticket(self, clip_id: str, status: str) -> dict:
        return {"clip_id": clip_id, "status": status,
                "output_prefix": str(clip_dir(Path(self.out_root), clip_id)),
                "poll": f"/jobs/{clip_id}",
                "queue_depth": len(self._q)}

    # ── 워커 ────────────────────────────────────────────────────────────────
    def _work(self) -> None:
        while True:
            with self._cv:
                while not self._q:
                    self._cv.wait()
                clip_id = self._q.pop(0)
                st = self.jobs[clip_id]
                st["status"] = "running"
            try:
                st["result"] = self._run(st["job"])
                st["status"] = "done"
            except Exception as e:
                log.exception("service.job.failed", extra={"clip_id": clip_id})
                st["error"] = {"stage": "service", "error": str(e)}
                st["status"] = "failed"

    def _run(self, job: dict) -> dict:
        from momentscan.pipeline import run_pipeline

        t0 = time.perf_counter()
        clip_id = job["clip_id"]
        out = self.out_root
        fps = int(job.get("fps") or self.fps_default)
        requested = tuple(job.get("products") or self.open_products)
        effective = tuple(p for p in requested if p in self.open_products)  # 단계 배포 스위치

        # C1 Job 실체화 — attribute의 subject_query 디스패치가 이 레코드를 읽는다.
        write_job(Path(out), clip_id, {k: job.get(k) for k in
                  ("clip_id", "source_uri", "output_uri", "fps", "subject_query",
                   "domain_profile", "products")} | {"fps": fps, "accepted_at_iso":
                  datetime.now(timezone.utc).isoformat(timespec="seconds")})

        source = None
        if job.get("source_uri"):
            source = fetch_source(str(job["source_uri"]), clip_dir(Path(out), clip_id) / "source_cache")
        if not detections_path(out, clip_id).exists():
            if source is None:
                raise FileNotFoundError(f"no detections for {clip_id} and no source_uri to run detect")
            if self._warm is None:
                from momentscan.extraction.detect import warm_init
                self._warm = warm_init()
            from momentscan.extraction.detect import process_clip
            process_clip(self._warm, str(source), out, fps=fps)

        run = run_pipeline(out, clip_id, source=str(source) if source else None, fps=fps)
        if run["failed"]:
            raise RuntimeError(f"stages failed: {[f['name'] for f in run['failed']]}")

        if "highlight" in effective:                    # mp4 렌더는 파이프 밖 (CLI와 동일)
            from momentscan.surface.cards import render_highlight_clips
            render_highlight_clips(out, clip_id, video_path=source)

        cdir = clip_dir(Path(out), clip_id)
        prefix, outputs = deliver(cdir, clip_id, collect_egress(cdir, effective),
                                  job.get("output_uri"))
        result = {
            "schema": RESULT_SCHEMA,
            "clip_id": clip_id, "ok": True, "failure": None,
            "node": self.node,
            "output_prefix": prefix, "outputs": outputs,
            "products_open": list(self.open_products), "products_requested": list(requested),
            "n_ran": len(run["ran"]), "n_skipped": len(run["skipped"]),
            "elapsed_s": round(time.perf_counter() - t0, 1),
            "finished_at_iso": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        write_result(Path(out), clip_id, result)        # 멱등 단락 + 재시작-후 조회의 근거
        log.info("service.job.done", extra={k: result[k] for k in
                                            ("clip_id", "output_prefix", "elapsed_s")})
        return result

    def health(self) -> dict:
        running = [c for c, s in self.jobs.items() if s["status"] == "running"]
        return {"status": "UP", "app": APP_NAME,        # "UP" = Spring health 관례
                "node": self.node,
                "queue": len(self._q), "running": running[0] if running else None,
                "done": sum(1 for s in self.jobs.values() if s["status"] == "done"),
                "failed": sum(1 for s in self.jobs.values() if s["status"] == "failed"),
                "open_products": list(self.open_products), "since": self.started_iso}


# ── HTTP 어댑터 ──────────────────────────────────────────────────────────────
def build_server(runner: JobRunner, *, port: int = 8080, bind: str = "0.0.0.0",
                 app_name: str = APP_NAME) -> ThreadingHTTPServer:
    """HTTP 면을 조립만 하고 돌리지는 않는다 — apicheck가 임시 포트(0)로 물어
    계약을 검증하는 지점. serve_http = 이것 + Eureka + serve_forever."""

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: dict, headers: dict | None = None) -> None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:                       # noqa: N802 (stdlib 계약)
            path = urllib.parse.urlparse(self.path).path.rstrip("/")
            if path == "/health":
                self._send(200, runner.health())
            elif path in ("", "/info"):
                self._send(200, {"app": app_name, "contract": "momentscan C1 v1",
                                 "result_schema": RESULT_SCHEMA, "node": runner.node,
                                 "open_products": list(runner.open_products),
                                 "endpoints": ["POST /jobs", "GET /jobs/{clip_id}",
                                               "GET /health", "GET /info"]})
            elif path.startswith("/jobs/"):
                self._send(*runner.status(path.removeprefix("/jobs/")))
            else:
                self._send(404, {"error": f"no route {path}"})

        def do_POST(self) -> None:                      # noqa: N802
            if urllib.parse.urlparse(self.path).path.rstrip("/") != "/jobs":
                self._send(404, {"error": "POST /jobs only"})
                return
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0)
                                  or b"{}")
            except (ValueError, TypeError) as e:
                self._send(400, {"error": f"bad json: {e}"})
                return
            code, payload = runner.submit(body)
            loc = {"Location": payload["poll"]} if code == 202 and "poll" in payload else None
            self._send(code, payload, loc)

        def log_message(self, fmt, *args):              # stdlib의 stderr 스팸 → 구조화 로그
            log.debug("service.http", extra={"line": fmt % args})

    server = ThreadingHTTPServer((bind, port), Handler)
    server.daemon_threads = True
    return server


HEALTH_LOG_S = 30      # 큐 깊이 같은 게이지를 Loki에서도 읽게 하는 주기 스냅샷
                       # (Zabbix가 /health를 폴링하는 것과 같은 내용의 로그판)


def node_identity(advertise_host: str | None, port: int) -> str:
    """"host:port" — 이 프로세스의 노드 정체성 (Eureka 광고 주소와 같은 근거).
    CLI가 로그 constants에, serve_http가 Result/health에 같은 값을 도장 찍는다."""
    from momentscan.eureka import _local_ip
    return f"{advertise_host or _local_ip()}:{port}"


def serve_http(out_root: str, *, port: int = 8080, fps: int = 6,
               open_products: tuple[str, ...] = ("likeness",),
               eureka_url: str | None = None, advertise_host: str | None = None,
               app_name: str = APP_NAME) -> None:
    node = node_identity(advertise_host, port)
    runner = JobRunner(out_root, fps_default=fps, open_products=open_products, node=node)
    server = build_server(runner, port=port, app_name=app_name)

    def _health_beat() -> None:
        while True:
            time.sleep(HEALTH_LOG_S)
            log.info("service.health", extra=runner.health())

    threading.Thread(target=_health_beat, name="health-log", daemon=True).start()

    eureka = None
    if eureka_url:                                      # 등록은 서버가 실제로 열린 뒤
        from momentscan.eureka import EurekaClient
        eureka = EurekaClient(eureka_url, app_name, port=port, host=advertise_host)
        eureka.start()

    log.info("service.ready", extra={"port": port, "out_root": out_root,
                                     "open_products": list(open_products),
                                     "eureka": eureka.instance_id if eureka else None})
    print(f"momentscan service :{port} · out={out_root} · open={list(open_products)}"
          + (f" · eureka={eureka.instance_id}" if eureka else ""))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if eureka:
            eureka.stop()                               # 정상 종료 = 즉시 해지 (축출 대기 없음)
        server.server_close()

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
- **egress = 선언에서 파생**: 어떤 파일이 밖으로 나가는가는 registry.PRODUCTS
  의 egress 선언 ∩ 열린 제품(단계 배포 스위치) — 코드에 목록 중복 없음.
- 입력 video: 로컬 경로 · file:// · s3:// (s3는 boto3 lazy import — 로컬 알파는
  boto3 없이 동작). 출력: output_uri 생략=stash 경로 반환 / 로컬 dir=복사 /
  s3://prefix=업로드, 항상 **저장 경로를 Result로 반환**.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from momentscan.pipeline.registry import PRODUCTS
from momentscan.store.stash import clip_dir, detections_path, read_result, write_job, write_result

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


def _openapi_path() -> Path | None:
    """docs/api/openapi.yaml (계약 정본) 탐색 — 레포 체크아웃 배포(알파 모드) 기준.
    contract-first: FastAPI처럼 코드에서 스펙을 생성하는 게 아니라, 손으로 쓴 스펙에
    api-check가 코드를 고정한다. /docs·/openapi.yaml은 그 정본의 서빙일 뿐."""
    for up in Path(__file__).resolve().parents:
        p = up / "docs" / "api" / "openapi.yaml"
        if p.is_file():
            return p
    return None


_DOCS_HTML = """<!doctype html><meta charset="utf-8"><title>momentscan API</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
<div id="ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>SwaggerUIBundle({url: "/openapi.yaml", dom_id: "#ui"});</script>
<noscript>JS 불가 환경 — 스펙 원문: <a href="/openapi.yaml">/openapi.yaml</a></noscript>"""


_GPU_CACHE: dict = {"t": 0.0, "snap": None}


def _gpu_snapshot() -> dict | None:
    """"누가 GPU를 얼만큼" — nvidia-smi 스냅샷 (5s 캐시, 첫 GPU 기준).
    self_mb=이 노드 프로세스의 점유(pid 매칭) · used_mb=장치 전체(타 프로세스 포함)
    · total_mb=용량. GPU/드라이버 없는 노드 → None (정직). /health(Zabbix 레인)와
    30s health beat(Loki 레인 → 대시보드 GPU 패널)에 실린다."""
    import subprocess
    now = time.monotonic()
    if now - _GPU_CACHE["t"] < 5.0:
        return _GPU_CACHE["snap"]
    try:
        dev = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5)
        total, used = (int(x) for x in dev.stdout.strip().splitlines()[0].split(","))
        procs = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5)
        me = os.getpid()
        self_mb = sum(int(m.strip()) for ln in procs.stdout.strip().splitlines() if ln.strip()
                      for p, m in [ln.split(",")] if int(p.strip()) == me)
        snap = {"total_mb": total, "used_mb": used, "self_mb": self_mb}
    except Exception:
        snap = None
    _GPU_CACHE.update(t=now, snap=snap)
    return snap


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
        log.info("service.job.accepted", extra={"clip_id": clip_id,
                                                "source_uri": job.get("source_uri"),
                                                "queue": len(self._q)})
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
            # 수명주기 표면: 어느 노드가(node=로그 상수) 어떤 비디오를(source_uri)
            # 언제 시작했나 — 대시보드 잡 테이블의 행이 되는 이벤트들.
            log.info("service.job.started", extra={"clip_id": clip_id,
                                                   "source_uri": st["job"].get("source_uri")})
            try:
                st["result"] = self._run(st["job"])
                st["status"] = "done"
            except Exception as e:
                log.exception("service.job.failed", extra={
                    "clip_id": clip_id, "source_uri": st["job"].get("source_uri")})
                st["error"] = {"stage": "service", "error": str(e)}
                st["status"] = "failed"
            cb = st["job"].get("_on_complete")          # 어댑터 완료 훅 (회사 콜백 등)
            if cb:
                try:
                    cb(st)
                except Exception:
                    log.exception("service.job.on_complete", extra={"clip_id": clip_id})

    def _run(self, job: dict) -> dict:
        from momentscan.pipeline.runner import run_pipeline

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
            # 파이프라인 관례(클립=파일명 stem)와 잡 clip_id의 정합화 — 단일 지점.
            # needs_source 스테이지들(attribute/tubelets/scene/…)은 소스 파일명에서
            # 클립을 파생하므로, 이름이 갈라지면 산출물이 남의 클립 디렉토리로
            # 흩어진다 (wf777 리허설 실증). 원본 URI는 job.json이 보존한다.
            if source.stem != clip_id:
                alias = clip_dir(Path(out), clip_id) / "source_cache" / f"{clip_id}{source.suffix}"
                alias.parent.mkdir(parents=True, exist_ok=True)
                if not alias.exists():
                    # 심링크 금지 — 일부 스테이지가 경로를 resolve()해 원본 이름으로
                    # 되돌아간다 (wf777 3차 리허설: tubelets/scene이 test_2로 회귀).
                    # 하드링크(동일 FS 무비용) → 복사 폴백.
                    try:
                        os.link(source, alias)
                    except OSError:
                        shutil.copy2(source, alias)
                source = alias
        if not detections_path(out, clip_id).exists():
            if source is None:
                raise FileNotFoundError(f"no detections for {clip_id} and no source_uri to run detect")
            if self._warm is None:
                from momentscan.subjects.detect import warm_init
                self._warm = warm_init()
            from momentscan.subjects.detect import process_clip
            # clip_id 명시 필수 — 파일명-파생에 맡기면 잡 clip_id와 갈라져
            # 하류 전멸 (wf777 리허설 실증: detect가 test_2/로 쓰고 잡은 wf777-*)
            process_clip(self._warm, str(source), out, fps=fps, clip_id=clip_id)

        # R11: restrict the run to the effective products' closure (run only what will be
        # served). Empty effective (all requested products closed) → None = full pipeline (fallback).
        run = run_pipeline(out, clip_id, source=str(source) if source else None, fps=fps,
                           products=list(effective) or None)
        if run["failed"]:
            raise RuntimeError(f"stages failed: {[f['name'] for f in run['failed']]}")

        if "highlight" in effective:                    # mp4 렌더는 파이프 밖 (CLI와 동일)
            from momentscan.surface.cards import render_highlight_clips
            render_highlight_clips(out, clip_id, video_path=source)

        try:                                            # 사람용 리포트 — /reports 드릴다운의 목적지.
            from momentscan.surface.report import render_report
            render_report(out, clip_id)                 # inspect는 무겁고 연구자 온디맨드 — 여기선 안 렌더
        except Exception as e:
            log.warning("service.report.skip", extra={"clip_id": clip_id, "error": str(e)})

        cdir = clip_dir(Path(out), clip_id)
        prefix, outputs = deliver(cdir, clip_id, collect_egress(cdir, effective),
                                  job.get("output_uri"))
        result = {
            "schema": RESULT_SCHEMA,
            "clip_id": clip_id, "ok": True, "failure": None,
            "node": self.node,
            "report_url": f"http://{self.node}/reports/{clip_id}/",   # 플릿→클립 드릴다운 좌표
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
                "node": self.node, "gpu": _gpu_snapshot(),
                "queue": len(self._q), "running": running[0] if running else None,
                "done": sum(1 for s in self.jobs.values() if s["status"] == "done"),
                "failed": sum(1 for s in self.jobs.values() if s["status"] == "failed"),
                "open_products": list(self.open_products), "since": self.started_iso}


# ── HTTP 어댑터 ──────────────────────────────────────────────────────────────
def build_server(runner: JobRunner, *, port: int = 8080, bind: str = "0.0.0.0",
                 app_name: str = APP_NAME, shim=None) -> ThreadingHTTPServer:
    """HTTP 면을 조립만 하고 돌리지는 않는다 — apicheck가 임시 포트(0)로 물어
    계약을 검증하는 지점. serve_http = 이것 + Eureka + serve_forever.
    shim(company.CompanyShim)이 있으면 회사 디스패치 방언 라우트를 함께 연다."""

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

        def _send_file(self, p: Path, ctype: str | None = None) -> None:
            import mimetypes
            data = p.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype or
                             mimetypes.guess_type(p.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_html(self, html_text: str) -> None:
            data = html_text.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _reports(self, path: str) -> None:
            """/reports/{clip_id}[/{relpath}] — 클립 리포트·inspect의 읽기-전용 정적 서빙.
            플릿(Grafana)에서 clip_id·node를 보고 이 노드의 "왜"로 들어오는 문."""
            parts = [urllib.parse.unquote(s) for s in path.split("/") if s][1:]   # drop "reports"
            if not parts:
                self._send(404, {"error": "GET /reports/{clip_id}/"})
                return
            clip_id, rel = parts[0], parts[1:]
            root = clip_dir(Path(runner.out_root), clip_id).resolve()
            if any(s in (".", "..") for s in parts) or not root.is_dir() \
                    or not root.is_relative_to(Path(runner.out_root).resolve()):
                self._send(404, {"error": "unknown clip"})
                return
            if not rel and not urllib.parse.urlparse(self.path).path.endswith("/"):
                # 상대 자산(portrait_card.png·inspect/…)이 풀리려면 트레일링 슬래시 필수
                self._send(301, {"see": f"/reports/{clip_id}/"},
                           {"Location": f"/reports/{clip_id}/"})
                return
            target = (root.joinpath(*rel) if rel else root / "index.html").resolve()
            if not target.is_relative_to(root) or not target.is_file():
                self._send(404, {"error": f"no such file under {clip_id}"})
                return
            self._send_file(target)

        def do_GET(self) -> None:                       # noqa: N802 (stdlib 계약)
            path = urllib.parse.urlparse(self.path).path.rstrip("/")
            if path.startswith("/reports/") or path == "/reports":
                self._reports(path)
                return
            if path == "/health":
                self._send(200, runner.health())
            elif path == "/docs":                       # Swagger UI (unpkg CDN) — 스펙은 로컬 정본
                self._send_html(_DOCS_HTML)
            elif path == "/openapi.yaml":
                spec = _openapi_path()
                if spec:
                    self._send_file(spec, "application/yaml; charset=utf-8")
                else:
                    self._send(404, {"error": "openapi.yaml not found (repo checkout 배포 기준)"})
            elif path in ("", "/info"):
                self._send(200, {"app": app_name, "contract": "momentscan C1 v1",
                                 "result_schema": RESULT_SCHEMA, "node": runner.node,
                                 "open_products": list(runner.open_products),
                                 "endpoints": ["POST /jobs", "GET /jobs/{clip_id}",
                                               "GET /health", "GET /info", "GET /docs",
                                               "GET /openapi.yaml", "GET /reports/{clip_id}/"]})
            elif path.startswith("/jobs/"):
                self._send(*runner.status(path.removeprefix("/jobs/")))
            else:
                self._send(404, {"error": f"no route {path}"})

        def do_POST(self) -> None:                      # noqa: N802
            path = urllib.parse.urlparse(self.path).path
            while "//" in path:                         # Feign target(base "…/") + "/경로" 관용
                path = path.replace("//", "/")
            path = path.rstrip("/")
            if not (path == "/jobs" or (shim and path.startswith("/video/process/"))):
                self._send(404, {"error": "POST /jobs only"
                                          + (" (+/video/process/{mediaType})" if shim else "")})
                return
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0)
                                  or b"{}")
            except (ValueError, TypeError) as e:
                self._send(400, {"error": f"bad json: {e}"})
                return
            if path != "/jobs":                         # 회사 디스패치 방언 (company.py)
                self._send(*shim.handle_process(path.removeprefix("/video/process/"), body))
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
    from momentscan.serve.eureka import _local_ip
    return f"{advertise_host or _local_ip()}:{port}"


def serve_http(out_root: str, *, port: int = 8080, fps: int = 6,
               open_products: tuple[str, ...] = ("likeness",),
               eureka_url: str | None = None, advertise_host: str | None = None,
               app_name: str = APP_NAME,
               control_url: str | None = None, s3_bucket: str | None = None) -> None:
    node = node_identity(advertise_host, port)
    runner = JobRunner(out_root, fps_default=fps, open_products=open_products, node=node)

    # 회사 Eureka·control 콜백 공용 JWT (2026-07-15 실측: 등록도 콜백도 인증 필수).
    # 자격은 env로만 — ps/CLI-인자 노출 방지, 회사 패턴과 동일.
    tp = None
    tok_uri = os.environ.get("EUREKA_TOKEN_URI", "")
    cid = os.environ.get("EUREKA_CLIENT_ID", "")
    sec = os.environ.get("EUREKA_CLIENT_SECRET", "")
    if tok_uri and cid and sec:
        from momentscan.serve.eureka import TokenProvider
        tp = TokenProvider(tok_uri, cid, sec,
                           scope=os.environ.get("EUREKA_TOKEN_SCOPE", "api.write api.read"))
        log.info("eureka.auth", extra={"token_uri": tok_uri})

    shim = None
    if control_url:                                     # 회사 디스패치 방언 어댑터 (company.py)
        from momentscan.serve.company import CompanyShim
        shim = CompanyShim(runner, control_url, s3_bucket=s3_bucket, token_provider=tp)
        log.info("company.shim", extra={"control_url": control_url, "s3_bucket": s3_bucket})

    server = build_server(runner, port=port, app_name=app_name, shim=shim)

    def _health_beat() -> None:
        while True:
            time.sleep(HEALTH_LOG_S)
            log.info("service.health", extra=runner.health())

    threading.Thread(target=_health_beat, name="health-log", daemon=True).start()

    eureka = None
    if eureka_url:                                      # 등록은 서버가 실제로 열린 뒤
        from momentscan.serve.eureka import EurekaClient
        eureka = EurekaClient(eureka_url, app_name, port=port, host=advertise_host,
                              token_provider=tp)
        eureka.start()

    # 런타임 레코드 — 데몬의 daemon.sock 관례와 나란한 로컬 발견 지점:
    # `momentscan status`가 이 파일로 "이 머신에 어떤 HTTP 면이 떠 있나"를 안다.
    runtime = Path.home() / ".cache" / "momentscan" / f"http-{port}.json"
    runtime.parent.mkdir(parents=True, exist_ok=True)
    runtime.write_text(json.dumps({
        "node": node, "port": port, "pid": os.getpid(), "out_root": str(out_root),
        "open_products": list(open_products), "started_iso": runner.started_iso,
    }, ensure_ascii=False), encoding="utf-8")

    # SIGTERM도 Ctrl-C와 같은 우아한 경로로 — systemd stop·`momentscan shutdown`·kill 전부
    # finally 정리(유레카 즉시 해지·런타임 레코드 삭제)를 타야 한다. 시그널 핸들러는
    # 메인 스레드에서 실행되므로 KeyboardInterrupt를 올리면 serve_forever가 빠져나온다.
    import signal

    def _term(signum, frame):                           # noqa: ARG001
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _term)

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
        runtime.unlink(missing_ok=True)                 # kill -9 잔재는 status가 ⚠로 표시
        log.info("service.stopped", extra={"port": port, "done":
                 sum(1 for s in runner.jobs.values() if s["status"] == "done")})

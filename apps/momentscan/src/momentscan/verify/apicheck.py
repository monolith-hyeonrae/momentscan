"""apicheck — REST API 계약 테스트 (`momentscan verify api`).

docs/api/openapi.yaml에 공유한 계약이 실제 서버 동작과 일치하는지 반복 검증한다.
Eureka·GPU·실비디오 전부 불필요: 인프로세스 서버(임시 포트) + 가짜 파이프라인 —
`run_pipeline` 하나만 패치하고 접수/큐/워커/egress/배송/멱등/HTTP는 **실코드**를
그대로 태운다. doctor(의존)·check(선언 정합)·replay-check(수치)와 나란한
검증 동사: 이것은 **외곽 계약**의 회귀 게이트.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

RESULT_KEYS = {"schema", "clip_id", "ok", "failure", "node", "report_url",
               "output_prefix", "outputs",
               "products_open", "products_requested", "n_ran", "n_skipped",
               "elapsed_s", "finished_at_iso"}
TICKET_KEYS = {"clip_id", "status", "output_prefix", "poll", "queue_depth"}


def _req(method: str, url: str, body: dict | None = None):
    """→ (code, json, headers) — 4xx도 본문을 읽는다 (에러 형태도 계약이다)."""
    req = urllib.request.Request(url, method=method,
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode()), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}"), dict(e.headers)


def run_apicheck(*, keep: bool = False) -> int:
    """전 계약 항목을 검증하고 0(통과)/1(실패)을 반환. 실패는 첫 항목에서 멈춤."""
    import momentscan.engine.pipeline as pipeline
    from momentscan.serve.service import JobRunner, build_server
    from momentscan.store.stash import clip_dir

    tmp = Path(tempfile.mkdtemp(prefix="momentscan-apicheck-"))
    fake_runs: list[str] = []

    def _stage(clip_id: str) -> None:
        """가짜 stash: detect 완료 + likeness 산출물이 이미 있는 클립."""
        cdir = clip_dir(tmp, clip_id)
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "detections.parquet").write_bytes(b"")          # detect-불필요 프로브
        (cdir / "likeness.json").write_text('{"riders":{}}', encoding="utf-8")
        (cdir / "provenance.json").write_text('{"clip_id":"%s"}' % clip_id, encoding="utf-8")

    real_run_pipeline = pipeline.run_pipeline
    pipeline.run_pipeline = lambda *a, **k: (fake_runs.append(a[1]) or   # noqa: ARG005
                                             {"ran": [], "skipped": [], "failed": []})
    passed = 0

    def ok(name: str, cond: bool, detail: str = "") -> None:
        nonlocal passed
        if not cond:
            raise AssertionError(f"{name}  {detail}")
        passed += 1
        print(f"  ✓ {name}")

    try:
        runner = JobRunner(str(tmp), open_products=("likeness",))
        server = build_server(runner, port=0, bind="127.0.0.1")
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_address[1]}"

        # ── 메타 면 ─────────────────────────────────────────────────────
        c, b, _ = _req("GET", f"{base}/info")
        ok("GET /info → 200 + 계약 필드", c == 200 and b["contract"] == "momentscan C1 v1"
           and b["open_products"] == ["likeness"] and "endpoints" in b, str(b))
        c, b, _ = _req("GET", f"{base}/health")
        ok("GET /health → status UP + 큐 지표 + node + gpu(nullable)", c == 200
           and b["status"] == "UP" and isinstance(b["queue"], int) and b["node"]
           and "gpu" in b, str(b))

        # ── API 자기서술 면 (/docs · /openapi.yaml) ──────────────────────
        raw = urllib.request.urlopen(f"{base}/openapi.yaml", timeout=10)
        ok("GET /openapi.yaml → 계약 정본 서빙", raw.status == 200
           and b"openapi: 3" in raw.read(), "")
        raw = urllib.request.urlopen(f"{base}/docs", timeout=10)
        ok("GET /docs → Swagger UI 페이지", raw.status == 200
           and b"swagger-ui" in raw.read(), "")

        # ── 검증 오류 형태 (에러도 계약) ─────────────────────────────────
        c, b, _ = _req("POST", f"{base}/jobs", {})
        ok("POST 빈 Job → 400 {error}", c == 400 and "error" in b, str(b))
        c, b, _ = _req("POST", f"{base}/jobs", {"clip_id": "x", "products": ["nope"]})
        ok("POST 미지 product → 400 + 알려진 목록", c == 400 and "nope" in b["error"], str(b))
        c, b, _ = _req("GET", f"{base}/jobs/ghost")
        ok("GET 미지 job → 404", c == 404 and "error" in b, str(b))
        c, b, _ = _req("GET", f"{base}/nope")
        ok("미지 라우트 → 404", c == 404, str(b))

        # ── 접수 → 완료 수명주기 ────────────────────────────────────────
        _stage("t1")
        c, b, h = _req("POST", f"{base}/jobs", {"clip_id": "t1", "products": ["likeness"]})
        ok("POST → 202 티켓 형태 + Location", c == 202 and set(b) == TICKET_KEYS
           and h.get("Location") == "/jobs/t1", f"{b} {h.get('Location')}")
        for _ in range(100):                             # 가짜 런은 수 ms — 짧은 폴링
            c, b, _ = _req("GET", f"{base}/jobs/t1")
            if not (c == 200 and b.get("status") in ("queued", "running")):
                break
            time.sleep(0.05)
        ok("완료 → Result 스키마 v1 전 필드", c == 200 and b.get("ok") is True
           and set(b) == RESULT_KEYS and b["schema"] == "momentscan.result/v1", str(set(b)))
        ok("outputs = 열린 제품만 + 실경로", set(b["outputs"]) == {"likeness", "provenance"}
           and all(Path(u).is_file() for us in b["outputs"].values() for u in us), str(b["outputs"]))

        # ── 멱등 ───────────────────────────────────────────────────────
        n_before = len(fake_runs)
        c, b, _ = _req("POST", f"{base}/jobs", {"clip_id": "t1"})
        ok("재요청 → 200 기존 Result·재계산 0", c == 200 and b["ok"] is True
           and len(fake_runs) == n_before, f"runs {len(fake_runs)}≠{n_before}")

        # ── 재시작 내구성 (result.json이 상태의 근거) ────────────────────
        runner2 = JobRunner(str(tmp), open_products=("likeness",))
        code_body = runner2.status("t1")
        ok("프로세스 재시작 후 조회 → result.json에서 복원",
           code_body[0] == 200 and code_body[1]["ok"] is True, str(code_body[0]))

        # ── /reports 정적 서빙 (플릿→클립 드릴다운의 문) ──────────────────
        (clip_dir(tmp, "t1") / "index.html").write_text("<h1>t1 report</h1>", encoding="utf-8")
        (clip_dir(tmp, "t1") / "inspect").mkdir(exist_ok=True)
        (clip_dir(tmp, "t1") / "inspect" / "clip.html").write_text("<h1>inspect</h1>", encoding="utf-8")
        raw = urllib.request.urlopen(f"{base}/reports/t1", timeout=10)   # 301 → urllib이 /로 따라감
        ok("GET /reports/{clip} → 301 → 리포트 HTML", raw.status == 200
           and "text/html" in raw.headers["Content-Type"] and b"t1 report" in raw.read(), "")
        sub = urllib.request.urlopen(f"{base}/reports/t1/inspect/clip.html", timeout=10)
        ok("하위 자산(inspect/clip.html) 서빙", sub.status == 200 and b"inspect" in sub.read(), "")
        import http.client                               # urllib은 ..를 클라이언트에서 정규화 → 원시 요청
        conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
        conn.request("GET", "/reports/t1/../../../etc/passwd")
        ok("경로 탈출 차단 (…/..) → 404", conn.getresponse().status == 404, "")
        conn.request("GET", "/reports/../secret")
        ok("clip_id='..' 차단 → 404", conn.getresponse().status == 404, "")
        conn.close()

        # ── output_uri 로컬 배송 + 단계 배포 스위치 ──────────────────────
        _stage("t2")
        dest = tmp / "delivery"
        c, b, _ = _req("POST", f"{base}/jobs",
                       {"clip_id": "t2", "output_uri": str(dest),
                        "products": ["likeness", "portrait"]})   # portrait는 닫혀 있음
        for _ in range(100):
            c, b, _ = _req("GET", f"{base}/jobs/t2")
            if not (c == 200 and b.get("status") in ("queued", "running")):
                break
            time.sleep(0.05)
        ok("output_uri 배송 → prefix 하위 실파일", b["output_prefix"].startswith(str(dest))
           and all(Path(u).is_file() for us in b["outputs"].values() for u in us), str(b["outputs"]))
        ok("닫힌 제품(portrait) 요청 → outputs에서 제외·요청은 기록",
           "portrait" not in b["outputs"] and b["products_requested"] == ["likeness", "portrait"]
           and b["products_open"] == ["likeness"], str(b["outputs"]))

        server.shutdown()
        print(f"\napi-check: {passed}/{passed} 통과 — 계약(docs/api/openapi.yaml)과 서버 일치")
        return 0
    except AssertionError as e:
        print(f"\n  ✗ FAIL: {e}")
        return 1
    finally:
        pipeline.run_pipeline = real_run_pipeline
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)

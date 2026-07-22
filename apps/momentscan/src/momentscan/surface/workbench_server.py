"""workbench server — 샘플링 연구 콘솔의 HTTP 면 (`momentscan workbench`).

C1 외부 면(infra/serve/service.py — docs/api/openapi.yaml 이 고정하는 회사 대면
계약)에 얹지 않고 label_server 선례의 **경량 로컬 앱**으로 신설한 이유: 워크벤치는
stash 내부 스키마(몰튼 비밀)를 직접 읽는 연구 표면이라, 계약면에 실으면 내부
스키마가 외곽 계약에 성급히 동결된다. 비디오 등록만은 C1 실행기의
transport-agnostic 본체(JobRunner.submit — 같은 멱등/큐/파이프라인 기계)를 그대로
문다: HTTP 는 어댑터일 뿐이라는 service.py 의 설계 결정이 여기서 두 번째 문을 연다.

라우트:
  GET  /                 클립 목록 + 비디오 등록 폼 (likeness.json 보유 = 워크벤치 가능)
  GET  /wb?clips=a,b     워크벤치 뷰 — const WB 인라인 (payload 위 순수 렌더러 원칙)
  GET  /api/clips        목록 JSON
  GET  /api/clip/{id}    클립 페이로드 JSON (첫 호출 = detect.mp4 디코드 → 캐시)
  GET  /api/gt           GT rows (병합본)
  POST /api/gt           판정 1행 병합-쓰기 → fixtures/eval/workbench_gt.jsonl (원자적)
  POST /api/register     {source_path|source_uri, clip_id?, fps?} → likeness 클로저 잡
  GET  /api/jobs         등록 잡 상태 (queued|running|done|failed)
  GET  /thumbs/...       썸네일 정적 서빙 (<out>/workbench/thumbs)

포트: 기본 8902 — server(HTTP C1) 8080 · label 8901 과 분리. bind 는 로컬호스트
(연구 콘솔 — 네트워크 노출 면이 아니다).
"""

from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from momentscan.surface._workbench_html import INDEX_PAGE, WORKBENCH_PAGE
from momentscan.surface.workbench import (
    apply_gt,
    build_clip_data,
    gt_default_path,
    list_clips,
    read_gt,
    workbench_dir,
)

log = logging.getLogger("momentscan.workbench")

DEFAULT_PORT = 8902


class _WorkbenchHandler(BaseHTTPRequestHandler):
    # build_workbench_app 이 채우는 클래스 상태 (label_server 선례)
    out_root: Path
    gt_path: Path
    corpus: str
    runner = None                          # infra.serve.service.JobRunner | None
    _locks: dict[str, threading.Lock] = {}
    _locks_guard = threading.Lock()

    def log_message(self, fmt, *args):     # stderr 스팸 → 구조화 로그
        log.debug("workbench.http", extra={"line": fmt % args})

    # ── 응답 헬퍼 ─────────────────────────────────────────────────────────────
    def _send(self, code: int, body: dict) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, html_text: str) -> None:
        data = html_text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")   # 연구 페이지 — stale JS 캐시 금지
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _clip_payload(self, clip_id: str) -> dict:
        """클립 페이로드 — 클립별 락으로 동시 요청의 이중 디코드를 막는다."""
        with self._locks_guard:
            lock = self._locks.setdefault(clip_id, threading.Lock())
        with lock:
            return build_clip_data(clip_id, self.out_root)

    def _known(self, clip_id: str) -> bool:
        return bool(clip_id) and "/" not in clip_id and "\\" not in clip_id \
            and (Path(self.out_root) / clip_id / "likeness.json").is_file()

    # ── GET ───────────────────────────────────────────────────────────────────
    def do_GET(self) -> None:              # noqa: N802 (stdlib 계약)
        u = urlparse(self.path)
        path = u.path.rstrip("/") or "/"
        if path == "/":
            data = {"clips": list_clips(self.out_root), "corpus": self.corpus,
                    "gt_path": str(self.gt_path), "gt_count": len(read_gt(self.gt_path))}
            self._send_html(INDEX_PAGE.replace("__DATA__", json.dumps(data, ensure_ascii=False)))
        elif path == "/wb":
            q = parse_qs(u.query)
            want = [c for c in (q.get("clips", [""])[0]).split(",") if c]
            if not want:                   # 무인자 = 캐시된 클립 전부 (직행 링크 관용)
                want = [c["clip"] for c in list_clips(self.out_root) if c["cached"]]
            bad = [c for c in want if not self._known(c)]
            if bad or not want:
                self._send(404, {"error": f"unknown clips {bad or '(none)'} — GET / 목록에서 선택"})
                return
            wb = {"clips": [self._clip_payload(c) for c in want]}
            page = (WORKBENCH_PAGE
                    .replace("__WB__", json.dumps(wb, ensure_ascii=False))
                    .replace("__GT0__", json.dumps(read_gt(self.gt_path), ensure_ascii=False))
                    .replace("__CORPUS__", json.dumps(self.corpus, ensure_ascii=False)))
            self._send_html(page)
        elif path == "/api/clips":
            self._send(200, {"clips": list_clips(self.out_root), "corpus": self.corpus})
        elif path.startswith("/api/clip/"):
            clip_id = unquote(path.removeprefix("/api/clip/"))
            if not self._known(clip_id):
                self._send(404, {"error": f"unknown clip {clip_id!r}"})
                return
            self._send(200, self._clip_payload(clip_id))
        elif path == "/api/gt":
            self._send(200, {"rows": read_gt(self.gt_path), "path": str(self.gt_path)})
        elif path == "/api/jobs":
            self._send(200, {"jobs": self._jobs()})
        elif path.startswith("/thumbs/"):
            self._thumb(path)
        else:
            self._send(404, {"error": f"no route {path}"})

    def _jobs(self) -> list[dict]:
        if self.runner is None:
            return []
        out = []
        for clip_id, st in self.runner.jobs.items():
            row = {"clip_id": clip_id, "status": st["status"]}
            if st.get("error"):
                row["error"] = str(st["error"].get("error", st["error"]))
            out.append(row)
        return out

    def _thumb(self, path: str) -> None:
        root = (workbench_dir(self.out_root) / "thumbs").resolve()
        target = Path(str(root) + "/" + unquote(path.removeprefix("/thumbs/"))).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            self._send(404, {"error": "no such thumb"})
            return
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Cache-Control", "max-age=3600")   # 썸네일은 내용-안정 (f키 고정)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ── POST ──────────────────────────────────────────────────────────────────
    def do_POST(self) -> None:             # noqa: N802
        path = urlparse(self.path).path.rstrip("/")
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0)
                              or b"{}")
        except (ValueError, TypeError) as e:
            self._send(400, {"error": f"bad json: {e}"})
            return
        if path == "/api/gt":
            self._post_gt(body)
        elif path == "/api/register":
            self._post_register(body)
        else:
            self._send(404, {"error": "POST /api/gt | /api/register only"})

    def _post_gt(self, body: dict) -> None:
        if not isinstance(body.get("clip"), str) or not str(body.get("clip")).strip():
            self._send(400, {"error": "clip (str) required"})
            return
        try:
            frame = int(body.get("frame"))
        except (TypeError, ValueError):
            self._send(400, {"error": "frame (int) required"})
            return
        row = {"clip": body["clip"], "frame": frame, "role": body.get("role") or "center",
               "flag": body.get("flag"), "corpus": body.get("corpus") or self.corpus,
               "ts": body.get("ts")}
        try:
            rows = apply_gt(self.gt_path, row)
        except ValueError as e:
            self._send(400, {"error": str(e)})
            return
        log.info("workbench.gt", extra={k: row[k] for k in ("clip", "frame", "role", "flag")})
        self._send(200, {"ok": True, "n": len(rows)})

    def _post_register(self, body: dict) -> None:
        """비디오 등록 → C1 실행기 본체(JobRunner.submit). 로컬 경로만 — S3 는 범위 밖
        (s3:// 소스가 필요하면 C1 면 `momentscan server start` 로)."""
        if self.runner is None:
            self._send(503, {"error": "job runner disabled (--no-jobs)"})
            return
        src = body.get("source_path") or body.get("source_uri")
        if not src or str(src).startswith("s3://"):
            self._send(400, {"error": "source_path (local path) required — s3:// 는 C1 면으로"})
            return
        p = Path(str(src).removeprefix("file://")).expanduser()
        if not p.is_file():
            self._send(400, {"error": f"source not found: {src}"})
            return
        job = {"clip_id": body.get("clip_id") or p.stem, "source_uri": str(p),
               "products": ["likeness"]}
        if body.get("fps"):
            job["fps"] = int(body["fps"])
        code, payload = self.runner.submit(job)
        self._send(code, payload)


def build_workbench_app(out_root: str | Path, *, gt_path: str | Path | None = None,
                        runner=None, corpus: str | None = None) -> type[_WorkbenchHandler]:
    """핸들러 조립만 (서버는 안 돌림) — 테스트가 임시 포트로 물어보는 지점."""
    cls = type("WorkbenchHandler", (_WorkbenchHandler,), {})
    cls.out_root = Path(out_root)
    cls.gt_path = Path(gt_path) if gt_path else gt_default_path()
    # corpus 라벨 = GT 행의 frame_idx 기준 좌표 — CLI 가 받은 --out 문자열 그대로가
    # 기본 (레포 루트 상대 관례: 메인 코퍼스 = "output/l2", v0 export 와 일치).
    cls.corpus = corpus if corpus is not None else str(out_root)
    cls.runner = runner
    cls._locks = {}
    return cls


def serve_workbench(out_root: str | Path, *, port: int = DEFAULT_PORT,
                    gt_path: str | Path | None = None, jobs: bool = True) -> None:
    root = Path(out_root)
    runner = None
    if jobs:
        from momentscan.infra.serve.service import JobRunner  # lazy — C1 실행기 본체 재사용
        runner = JobRunner(str(root), open_products=("likeness",),
                           node=f"workbench:{port}")
    handler = build_workbench_app(root, gt_path=gt_path, runner=runner,
                                  corpus=str(out_root))
    n = len(list_clips(root))
    print(f"sampling workbench → http://localhost:{port}  (클립 {n}개 · corpus={out_root})")
    print(f"  GT 홈 = {handler.gt_path}")
    if n == 0:
        print(f"  ⚠️  likeness.json 보유 클립이 없습니다 — --out 경로를 확인하세요 (지금: {root.resolve()})")
    ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()

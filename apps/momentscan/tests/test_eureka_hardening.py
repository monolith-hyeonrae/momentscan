"""Eureka 강건성 — 부팅 등록 실패 생존 + service-available-status 메타데이터.

배경: 부팅 시 Eureka가 안 닿으면(연결 거부) 이전 구현은 URLError로 프로세스가
죽어 K8s 크래시루프가 됐다(2026-08-04 로컬 실증). 수리 = 호출 실패를 _call에서
코드 0으로 정규화, 회복은 heartbeat 루프(404 재등록)가 맡는다.
메타데이터 규약 = 회사 워커(video-process EurekaMetaService)와 동일:
키 "service-available-status", 값 = 진행 중 작업 수.
"""
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from momentscan.infra.serve.eureka import EurekaClient


class _FakeEureka(BaseHTTPRequestHandler):
    seen: list = []            # (method, path)
    last_register: bytes = b""
    registered = False

    def _respond(self, code):
        self.send_response(code)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        type(self).seen.append(("POST", self.path))
        n = int(self.headers.get("Content-Length") or 0)
        type(self).last_register = self.rfile.read(n)
        type(self).registered = True
        self._respond(204)

    def do_PUT(self):
        type(self).seen.append(("PUT", self.path))
        if "/metadata" in self.path:
            self._respond(200)
        else:                              # heartbeat — 미등록이면 404 (실서버 규약)
            self._respond(200 if type(self).registered else 404)

    def do_DELETE(self):
        type(self).seen.append(("DELETE", self.path))
        self._respond(200)

    def log_message(self, *a):             # 테스트 출력 오염 방지
        pass


@pytest.fixture()
def fake_eureka():
    _FakeEureka.seen = []
    _FakeEureka.last_register = b""
    _FakeEureka.registered = False
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _FakeEureka)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/eureka"
    srv.shutdown()


def test_boot_survives_eureka_down():
    # 127.0.0.1:9 (discard) — 연결 거부가 즉시 나는 닫힌 포트
    c = EurekaClient("http://127.0.0.1:9/eureka", "ms-test", port=18099)
    c.start()                              # 이전 구현은 여기서 URLError로 사망
    assert c._thread is not None and c._thread.is_alive()
    c.stop()                               # 해지도 예외 없이


def test_heartbeat_reregisters_after_loss(fake_eureka):
    c = EurekaClient(fake_eureka, "ms-test", port=18099)
    # 등록이 사라진 상태(서버 재시작/축출/부팅 실패)에서 heartbeat 한 번이면 복구
    assert _FakeEureka.registered is False
    c.heartbeat()                          # PUT 404 → 재등록 POST
    assert _FakeEureka.registered is True
    assert ("POST", "/eureka/apps/MS-TEST") in _FakeEureka.seen


def test_register_payload_carries_available_status(fake_eureka):
    c = EurekaClient(fake_eureka, "ms-test", port=18099)
    assert c.register() is True
    assert b'"service-available-status": "0"' in _FakeEureka.last_register


def test_set_available_status_puts_metadata(fake_eureka):
    c = EurekaClient(fake_eureka, "ms-test", port=18099)
    c.register()
    c.set_available_status(1)
    paths = [p for (m, p) in _FakeEureka.seen if m == "PUT" and "/metadata" in p]
    assert paths and paths[-1].endswith("/metadata?service-available-status=1")


def test_service_notifies_inflight_around_job(tmp_path, monkeypatch):
    from momentscan.infra.serve.service import JobRunner
    s = JobRunner(str(tmp_path))
    calls: list = []
    s.on_inflight = calls.append
    monkeypatch.setattr(s, "_run", lambda job: {"ok": True, "clip_id": job["clip_id"]})
    threading.Thread(target=s._work, daemon=True).start()
    s.submit({"clip_id": "t1", "source_uri": "/x.mp4"})
    for _ in range(100):                   # 완료 대기 (최대 ~5s)
        if s.jobs.get("t1", {}).get("status") == "done":
            break
        import time
        time.sleep(0.05)
    assert s.jobs["t1"]["status"] == "done"
    assert calls == [1, 0]                 # 시작=1, 종료=0

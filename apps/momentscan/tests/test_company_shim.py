"""회사 디스패치 방언 어댑터 (company.py) — 2026-07-15 실코드 판독 계약의 고정.

수락=OK 즉시(비동기 처리)·포화=10002·무소스=수락 후 정직 VIDEO_ERROR 콜백,
소스 해석=로컬 우선→등록 버킷 key, 완료 콜백=성공/실패 모두, Feign 이중-슬래시 라우트.
run_pipeline만 패치하고 수리/큐/워커/콜백 훅은 실코드 (apicheck 관례)."""
import http.client
import json
from pathlib import Path
import threading

import pytest

import momentscan.engine.pipeline as pipeline
from momentscan.serve.company import BUSY, GROUP, OK, CompanyShim, resolve_source
from momentscan.serve.service import JobRunner, build_server
from momentscan.store.stash import clip_dir, write_result


def test_resolve_source_rules():
    b = "dev-981park-media-cju"
    assert resolve_source("s3://b/k.mp4", b) == "s3://b/k.mp4"          # 완전 URI 그대로
    assert resolve_source("/data/v.mp4", b) == "/data/v.mp4"            # 로컬 절대경로 그대로
    assert resolve_source("file:///d/v.mp4", None) == "file:///d/v.mp4"
    assert resolve_source("edit/2026/wf1.mp4", b) == f"s3://{b}/edit/2026/wf1.mp4"
    assert resolve_source("edit/2026/wf1.mp4", None) is None            # 버킷 미등록 = 정직 None
    assert resolve_source(None, b) is None
    assert resolve_source("", b) is None


def _dto(wf: int, source: str | None):
    param = None
    if source is not None:
        param = {"workflowId": wf, "processId": 42, "isTest": True, "subType": None,
                 "source": {"requestS3Video": source}}
    return {"workflowId": wf, "mediaType": "MOMENT_SCAN", "group": GROUP,
            "createdDateTime": 1752555555000, "parameter": param}


@pytest.fixture()
def harness(tmp_path, monkeypatch):
    """실 JobRunner + 가짜 파이프라인 + 콜백 캡처 shim."""
    monkeypatch.setattr(pipeline, "run_pipeline",
                        lambda *a, **k: {"ran": [], "skipped": [], "failed": []})
    runner = JobRunner(str(tmp_path), open_products=("likeness",))
    shim = CompanyShim(runner, "http://control.test", s3_bucket=None)
    sent: list[tuple[str, dict]] = []
    fired = threading.Event()

    def capture(url, body):
        sent.append((url, body))
        fired.set()
        return 200

    shim._post = capture
    return runner, shim, sent, fired, tmp_path


def test_accept_then_success_callback(harness):
    runner, shim, sent, fired, tmp = harness
    src = tmp / "wf7.mp4"
    src.write_bytes(b"\x00")
    clip_dir(tmp, "wf7-moment_scan").mkdir(parents=True, exist_ok=True)
    (clip_dir(tmp, "wf7-moment_scan") / "detections.parquet").write_bytes(b"")

    code, body = shim.handle_process("MOMENT_SCAN", _dto(7, str(src)))
    assert (code, body) == (200, OK)                    # 동기 응답 = 수락뿐
    assert fired.wait(15), "완료 콜백 미발화"
    url, cb = sent[0]
    assert url == "http://control.test/process/moment-scan/7"
    assert cb["status"] == "VIDEO_SUCCESS" and cb["errorMessage"] is None
    assert cb["workflowId"] == 7 and cb["videoProcessSeq"] == 42
    assert cb["group"] == GROUP and cb["mediaType"] == "MOMENT_SCAN"
    assert cb["resultPath"]["resultS3Video"]            # 임시 매핑 = output_prefix


def test_busy_returns_10002(harness):
    runner, shim, sent, fired, tmp = harness
    runner.jobs["occupied"] = {"status": "running", "job": {}}
    code, body = shim.handle_process("MOMENT_SCAN", _dto(8, "/nope.mp4"))
    assert (code, body) == (200, BUSY)
    assert not sent                                     # 포화는 콜백 없음 — control이 재시도


def test_null_parameter_honest_error_callback(harness):
    """control 테스트 트리거는 parameter=null로 큐잉 — 수락 후 VIDEO_ERROR 완주가
    control 큐를 비우는 유일한 경로 (회사 워커는 이때 침묵 → 회수 루프에 잔류)."""
    runner, shim, sent, fired, tmp = harness
    code, body = shim.handle_process("MOMENT_SCAN", _dto(9, None))
    assert (code, body) == (200, OK)
    assert fired.wait(10)
    url, cb = sent[0]
    assert url.endswith("/process/moment-scan/9")
    assert cb["status"] == "VIDEO_ERROR" and "no resolvable source" in cb["errorMessage"]
    assert cb["resultPath"] is None


def test_pipeline_failure_error_callback(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "run_pipeline",
                        lambda *a, **k: {"ran": [], "skipped": [],
                                         "failed": [{"name": "gates", "error": "boom"}]})
    runner = JobRunner(str(tmp_path), open_products=("likeness",))
    shim = CompanyShim(runner, "http://control.test")
    sent, fired = [], threading.Event()
    shim._post = lambda url, body: (sent.append((url, body)), fired.set(), 200)[-1]

    src = tmp_path / "wf5.mp4"
    src.write_bytes(b"\x00")
    clip_dir(tmp_path, "wf5-moment_scan").mkdir(parents=True, exist_ok=True)
    (clip_dir(tmp_path, "wf5-moment_scan") / "detections.parquet").write_bytes(b"")

    assert shim.handle_process("MOMENT_SCAN", _dto(5, str(src)))[1] == OK
    assert fired.wait(15)
    cb = sent[0][1]
    assert cb["status"] == "VIDEO_ERROR" and "gates" in cb["errorMessage"]


def test_idempotent_immediate_callback(harness):
    """이미 완료된 잡의 재디스패치(control 재할당/재시작) = 재계산 없이 즉시 성공 콜백."""
    runner, shim, sent, fired, tmp = harness
    write_result(tmp, "wf6-moment_scan",
                 {"ok": True, "clip_id": "wf6-moment_scan", "output_prefix": "/done/here"})
    code, body = shim.handle_process("MOMENT_SCAN", _dto(6, "/ignored.mp4"))
    assert (code, body) == (200, OK)
    assert fired.wait(10)
    cb = sent[0][1]
    assert cb["status"] == "VIDEO_SUCCESS"
    assert cb["resultPath"]["resultS3Video"] == "/done/here"


def test_detect_receives_job_clip_id(tmp_path, monkeypatch):
    """clip_id ≠ 파일명 stem인 잡(회사 workflowId 등)에서 detect가 잡의 clip_id로
    산출물을 써야 한다 — 파일명-파생에 맡기면 하류 전멸 (wf777 리허설 실증)."""
    import sys
    import types

    monkeypatch.setattr(pipeline, "run_pipeline",
                        lambda *a, **k: {"ran": [], "skipped": [], "failed": []})
    seen = {}

    def fake_process_clip(warm, video_path, out_root, *, fps=None, clip_id=None):
        seen["clip_id"] = clip_id
        d = clip_dir(Path(out_root), clip_id)
        d.mkdir(parents=True, exist_ok=True)
        (d / "detections.parquet").write_bytes(b"")
        return {}

    stub = types.SimpleNamespace(warm_init=lambda: object(), process_clip=fake_process_clip)
    monkeypatch.setitem(sys.modules, "momentscan.extraction.detect", stub)

    src = tmp_path / "some_video_name.mp4"              # stem ≠ clip_id
    src.write_bytes(b"\x00")
    runner = JobRunner(str(tmp_path), open_products=("likeness",))
    code, _ = runner.submit({"clip_id": "wf99-moment_scan", "source_uri": str(src)})
    assert code == 202
    deadline = threading.Event()
    for _ in range(100):
        if runner.jobs["wf99-moment_scan"]["status"] in ("done", "failed"):
            break
        deadline.wait(0.1)
    assert runner.jobs["wf99-moment_scan"]["status"] == "done"
    assert seen["clip_id"] == "wf99-moment_scan"


def test_source_alias_matches_clip_id(tmp_path, monkeypatch):
    """needs_source 스테이지들은 파일명 stem에서 클립을 파생한다 — 서비스는
    잡 clip_id 이름의 별칭으로 소스를 넘겨 전 스테이지 정합을 한 지점에서 보장."""
    captured = {}

    def fake_run_pipeline(out, clip_id, *, source=None, **k):
        captured["source"] = source
        return {"ran": [], "skipped": [], "failed": []}

    monkeypatch.setattr(pipeline, "run_pipeline", fake_run_pipeline)
    src = tmp_path / "camera_export_0042.mp4"           # stem ≠ clip_id
    src.write_bytes(b"\x00")
    clip_dir(tmp_path, "wf3-moment_scan").mkdir(parents=True, exist_ok=True)
    (clip_dir(tmp_path, "wf3-moment_scan") / "detections.parquet").write_bytes(b"")

    runner = JobRunner(str(tmp_path), open_products=("likeness",))
    runner.submit({"clip_id": "wf3-moment_scan", "source_uri": str(src)})
    for _ in range(100):
        if runner.jobs["wf3-moment_scan"]["status"] in ("done", "failed"):
            break
        threading.Event().wait(0.1)
    assert runner.jobs["wf3-moment_scan"]["status"] == "done"
    alias = Path(captured["source"])
    assert alias.stem == "wf3-moment_scan"              # 파생-이름 = 잡 clip_id
    assert not alias.is_symlink()                       # resolve() 스테이지에도 안전해야
    assert alias.resolve().stem == "wf3-moment_scan"    # (tubelets/scene 회귀 재발 방지)
    assert alias.read_bytes() == src.read_bytes()       # 실체는 원본과 동일


def test_http_route_and_feign_double_slash(harness):
    """빌드된 서버가 /video/process/{mediaType}를 열고, Feign의 base-URL 트레일링
    슬래시 관용(//video/…)도 같은 라우트로 수렴하는지. shim 미장착 서버는 404."""
    runner, shim, sent, fired, tmp = harness
    server = build_server(runner, port=0, bind="127.0.0.1", shim=shim)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    try:
        for path in ("/video/process/MOMENT_SCAN", "//video/process/MOMENT_SCAN"):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("POST", path, body=json.dumps(_dto(11, None)),
                         headers={"Content-Type": "application/json"})
            r = conn.getresponse()
            assert r.status == 200 and json.loads(r.read())["code"] == "00000", path
            conn.close()

        bare = build_server(JobRunner(str(tmp), open_products=("likeness",)),
                            port=0, bind="127.0.0.1")
        threading.Thread(target=bare.serve_forever, daemon=True).start()
        conn = http.client.HTTPConnection("127.0.0.1", bare.server_address[1], timeout=5)
        conn.request("POST", "/video/process/MOMENT_SCAN", body="{}")
        assert conn.getresponse().status == 404         # shim 미장착 = 정직한 부재
        bare.shutdown()
    finally:
        server.shutdown()

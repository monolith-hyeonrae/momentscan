"""provenance.json — 출력물의 출생 기록 (write-once).

source_uri=실제 연 파일(source_cache 사본일 수 있음) / source_origin=잡이 준 원
URI(S3 키 — 캐시 소멸 후에도 남는 추적선) / source_sha256=처리한 바이트의 지문
(전송수단-독립 신원). 스테이지 실행과 무관하게 run 시작 시 기록된다.
"""
import hashlib
import json

from momentscan.infra.pipeline.runner import run_pipeline
from momentscan.infra.store.stash import provenance_path

_BYTES = b"fake-video-bytes"


def _rec(out_root, clip_id):
    return json.loads(provenance_path(str(out_root), clip_id).read_text())


def test_records_origin_and_content_hash(tmp_path):
    src = tmp_path / "source_cache" / "wfX.mp4"
    src.parent.mkdir()
    src.write_bytes(_BYTES)
    run_pipeline(str(tmp_path), "wfX", source=str(src),
                 source_origin="s3://bkt/video/original/D3/2026/08/03/x.mp4",
                 only={"attribute"}, watch=False)
    rec = _rec(tmp_path, "wfX")
    assert rec["source_origin"] == "s3://bkt/video/original/D3/2026/08/03/x.mp4"
    assert rec["source_uri"] == str(src)               # 실제 연 파일은 별도 보존
    assert rec["source_sha256"] == hashlib.sha256(_BYTES).hexdigest()
    assert rec["source_bytes"] == len(_BYTES)


def test_origin_defaults_to_source_and_write_once(tmp_path):
    src = tmp_path / "clip.mp4"
    src.write_bytes(_BYTES)
    run_pipeline(str(tmp_path), "clip", source=str(src), only={"attribute"}, watch=False)
    assert _rec(tmp_path, "clip")["source_origin"] == str(src)  # CLI 로컬 경로 = 그대로 원본
    # write-once: 재실행이 다른 origin을 줘도 첫 기록이 진실로 남는다
    run_pipeline(str(tmp_path), "clip", source=str(src),
                 source_origin="s3://late/other.mp4", only={"attribute"}, watch=False)
    assert _rec(tmp_path, "clip")["source_origin"] == str(src)

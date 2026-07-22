"""workbench 표면 봉인 (track/lk-workbench, 원장 ⑫ 승격).

코퍼스-불필요: GT 병합 I/O(나중-이김·제거·원자성) · compute_picks 의미론(명시-floor
스크린·가중 랭킹·gap) · JS DEF ≡ python DEFAULT_CFG 상수 짝 · 캐시 신선도 ·
서버 라우트(GT 라운드트립 + 재기동 복원 · 등록 배선).
코퍼스-보유 노드: 셀프테스트 픽 고정 (v0 검증 좌표 — 워크벤치 캐시가 있으면 활성).
"""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from momentscan.surface import workbench as wb
from momentscan.surface._workbench_html import WORKBENCH_PAGE
from momentscan.surface.workbench_server import build_workbench_app

ROOT = Path(__file__).resolve().parents[3]
L2 = ROOT / "output" / "l2"


# ── GT I/O ────────────────────────────────────────────────────────────────────
def test_apply_gt_merge_later_wins(tmp_path):
    p = tmp_path / "gt.jsonl"
    wb.apply_gt(p, {"clip": "c1", "frame": 10, "flag": "pos", "corpus": "out"})
    wb.apply_gt(p, {"clip": "c1", "frame": 20, "flag": "pos", "corpus": "out"})
    rows = wb.apply_gt(p, {"clip": "c1", "frame": 10, "flag": "neg", "corpus": "out"})
    assert {(r["frame"], r["flag"]) for r in rows} == {(10, "neg"), (20, "pos")}
    # 파일 자체도 병합본 (한 키 한 행) + 스키마 도장
    lines = [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    assert all(r["schema"] == wb.GT_SCHEMA for r in lines)


def test_apply_gt_flag_removal_and_validation(tmp_path):
    p = tmp_path / "gt.jsonl"
    wb.apply_gt(p, {"clip": "c1", "frame": 10, "flag": "pos", "corpus": "out"})
    rows = wb.apply_gt(p, {"clip": "c1", "frame": 10, "flag": None, "corpus": "out"})
    assert rows == [] and p.read_text(encoding="utf-8") == ""
    with pytest.raises(ValueError):
        wb.apply_gt(p, {"clip": "c1", "frame": 10, "flag": "maybe"})


def test_apply_gt_role_is_key_axis(tmp_path):
    """role 다르면 다른 깃발 (v1 hair 빈 role 추가를 위한 additive 축)."""
    p = tmp_path / "gt.jsonl"
    wb.apply_gt(p, {"clip": "c1", "frame": 10, "role": "center", "flag": "pos"})
    rows = wb.apply_gt(p, {"clip": "c1", "frame": 10, "role": "hair_left", "flag": "neg"})
    assert {(r["role"], r["flag"]) for r in rows} == {("center", "pos"), ("hair_left", "neg")}


def test_read_gt_merges_duplicate_lines_later_wins(tmp_path):
    """append 병합 파일(수동 이어붙임 백업)도 읽기에서 나중-이김."""
    p = tmp_path / "gt.jsonl"
    p.write_text(
        json.dumps({"clip": "c1", "frame": 5, "role": "center", "flag": "pos"}) + "\n"
        + "not json\n"
        + json.dumps({"clip": "c1", "frame": 5, "role": "center", "flag": "neg"}) + "\n",
        encoding="utf-8")
    rows = wb.read_gt(p)
    assert len(rows) == 1 and rows[0]["flag"] == "neg"


# ── compute_picks 의미론 (상태별 스크린/밴드 + 상태 가중 + gap) ──────────────
def _row(f, *, sy=0.1, dv=0.0, pc=0.0, pu=0.9, ex=0.1, cs=50.0, mv=50.0, lt=50.0,
         dp=50.0, hh=50.0, sp=50.0, r=None):
    return {"f": f, "sy": sy, "dv": dv, "pc": pc, "pu": pu, "ex": ex,
            "cs": cs, "mv": mv, "lt": lt, "dp": dp, "hh": hh, "sp": sp,
            "r": r or [0.5] * 8}


def test_picks_explicit_floor_screen():
    rows = [
        _row(0),                       # 통과
        _row(1, sy=0.7),               # sym floor 탈락
        _row(2, dv=20.0),              # yaw 밴드 상한(dev_hi=15) 탈락
        _row(3, pu=0.1),               # pupil floor 탈락
        _row(4, ex=0.99, r=[1] * 8),   # ex_max=1.0 이하라 통과 + 최고점
        _row(5, cs=None, mv=None, lt=None, dp=None, hh=None, sp=None),  # 측정 부재(None) = 스크린 통과
        _row(6, pc=120.0),             # 극단 pitch 도 기본(99=off 상한 미만만 통과)에 걸림
        _row(7, dv=-20.0),             # yaw 밴드 하한(dev_lo=−15) 탈락 (v0.5 부호-있는 밴드)
    ]
    got = wb.compute_picks([dict(r) for r in rows], dict(wb.DEFAULT_CFG, gap_min=1))
    assert not {1, 2, 3, 6, 7} & set(got)
    assert got[0] == 4                 # 상태 가중합 최대가 1순위
    assert set(got) <= {0, 4, 5}


def test_picks_state_screens_v07_v09():
    """v0.7 빛-심층(dp/hh)·영상(sp) 스크린 + v0.9 표정 ex_min 밴드 하한 — 기본은 전부 off."""
    rows = [
        _row(0, dp=5.0, hh=95.0, sp=5.0, ex=0.05),      # 기본 설정에선 통과
        _row(30, dp=80.0, hh=10.0, sp=80.0, ex=0.5),
    ]
    assert set(wb.compute_picks([dict(r) for r in rows], wb.DEFAULT_CFG)) == {0, 30}
    tight = dict(wb.DEFAULT_CFG, dp_min=20.0, hh_max=50.0, sp_min=20.0, ex_min=0.1)
    assert wb.compute_picks([dict(r) for r in rows], tight) == [30]   # f0 은 네 스크린 전부에 걸림


def test_picks_yaw_band_side_query():
    """v0.5: 밴드를 측면 구간으로 옮기면 측면 프레임 선택 (portrait 쿼리 대비)."""
    rows = [_row(0, dv=0.0), _row(30, dv=70.0)]
    side = dict(wb.DEFAULT_CFG, dev_lo=60.0, dev_hi=90.0)
    assert wb.compute_picks([dict(r) for r in rows], side) == [30]


def test_picks_pitch_dial_default_off():
    """pt_max 기본 99 = 실질 off (|pc|<99 통과) · 조이면 스크린 (v0.3, 결측 pc=0=통과)."""
    rows = [_row(0, pc=0.0, r=[0.1] * 8), _row(30, pc=20.0, r=[1.0] * 8)]
    got_def = wb.compute_picks([dict(r) for r in rows], wb.DEFAULT_CFG)
    assert got_def[0] == 30            # 기본 = pitch 무영향, 점수 우선
    tight = dict(wb.DEFAULT_CFG, pt_max=10.0)
    got_tight = wb.compute_picks([dict(r) for r in rows], tight)
    assert got_tight == [0]            # |pc|=20 스크린 탈락


def test_picks_gap_min_time_diversity():
    rows = [_row(f, r=[1 - f * 0.001] * 8) for f in range(6)]   # f0 최고점, 인접 연속
    got = wb.compute_picks([dict(r) for r in rows], dict(wb.DEFAULT_CFG, gap_min=3))
    assert got[0] == 0
    assert all(abs(a - b) >= 3 for i, a in enumerate(got) for b in got[:i])


def test_state_scores_composition():
    """v0.9: 상태 4종 = 얼굴(2·무표정+눈동자)/3 · 빛=rl · 영상(선명+micro)/2 · 왜곡(cs+입+norm)/3."""
    r = [0.9, 0.6, 0.4, 0.8, 0.3, 0.5, 0.7, 1.0]   # [re,rp,rs,rm,rn,rc,rv,rl]
    sf, sl, si, sd = wb.state_scores(r)
    assert sf == pytest.approx((2 * 0.9 + 0.6) / 3)
    assert sl == pytest.approx(1.0)
    assert si == pytest.approx((0.4 + 0.8) / 2)
    assert sd == pytest.approx((0.5 + 0.7 + 0.3) / 3)


def test_picks_state_weights_reorder():
    """v0.9: 가중은 신호가 아닌 상태 단위 — 빛 상태만 가중하면 빛-우세 행이 1순위."""
    r_hi_face = _row(0, r=[1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])    # 얼굴 상태=1
    r_hi_light = _row(30, r=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0])  # 빛 상태=1
    only_light = dict(wb.DEFAULT_CFG, w_face=0.0, w_light=0.6, w_image=0.0, w_distort=0.0)
    got = wb.compute_picks([dict(r_hi_face), dict(r_hi_light)], only_light)
    assert got[0] == 30
    only_face = dict(wb.DEFAULT_CFG, w_face=0.6, w_light=0.0, w_image=0.0, w_distort=0.0)
    got = wb.compute_picks([dict(r_hi_face), dict(r_hi_light)], only_face)
    assert got[0] == 0


# ── JS ≡ python 상수 짝 (셀프테스트가 감시하는 계약의 정적 절반) ──────────────
def test_js_def_matches_python_default_cfg():
    m = re.search(r"const DEF=\{(.*?)\};", WORKBENCH_PAGE, re.S)
    assert m, "workbench 페이지에 const DEF 블록이 없다"
    js = dict(re.findall(r"(\w+):(-?[0-9.]+)", m.group(1)))   # dev_lo 음수 허용
    assert set(js) == set(wb.DEFAULT_CFG)
    for k, v in wb.DEFAULT_CFG.items():
        assert float(js[k]) == pytest.approx(float(v)), k


def test_workbench_page_has_selftest_and_gt_post():
    assert "selftest" in WORKBENCH_PAGE
    assert '"/api/gt"' in WORKBENCH_PAGE or "'/api/gt'" in WORKBENCH_PAGE


def test_workbench_page_has_ghost_lane_v06():
    """v0.6 공평 우주: 타임라인 축=0..vf · 유령 레인 3색 + 레이블 · 풀 필터 제거."""
    assert "const fmin=0" in WORKBENCH_PAGE               # 축=비디오 전체(0..vf)
    for hexcol in ("#a05244", "#5a78a0", "#8a70b0"):     # GCOL inv·det·frag
        assert hexcol in WORKBENCH_PAGE
    assert "GLBL" in WORKBENCH_PAGE                       # 유령 호버 레이블
    assert "ordered.slice(0,400)" in WORKBENCH_PAGE       # 풀 그리드 썸네일-필터 제거


def test_workbench_page_has_state_query_v07_v09():
    """v0.7~v0.9: 상태 5그룹(퍼널·타임라인 단위) · lf 표시+ATT 토글 · 상태-쿼리 미러."""
    assert 'const STAGES=["포즈","표정·얼굴","빛","영상","왜곡"]' in WORKBENCH_PAGE
    assert "function stateScores(rr)" in WORKBENCH_PAGE   # python state_scores 미러
    assert "빛 판별력 lf=" in WORKBENCH_PAGE               # v0.8 클립 헤더 표시
    assert "빛 분산-감쇠(시험)" in WORKBENCH_PAGE          # v0.8 ATT 체크박스
    assert "w_light*(lf==null?1:lf)" in WORKBENCH_PAGE    # ATT 감쇠 식
    for k in ("dp_min", "hh_max", "sp_min"):              # v0.7 빛-심층·영상 다이얼+분포 지도
        assert f"{k}:{{f:r=>" in WORKBENCH_PAGE
    assert 'band:["ex_min","ex_max"]' in WORKBENCH_PAGE   # v0.9 표정 밴드


# ── 캐시 신선도 (mtime + 버전) ────────────────────────────────────────────────
def _fake_corpus(tmp_path: Path, clip: str = "c1") -> Path:
    out = tmp_path / "out"
    d = out / clip
    (d / "features").mkdir(parents=True)
    for rel in wb._SOURCES:
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    return out


def test_cache_freshness_mtime_and_version(tmp_path):
    out = _fake_corpus(tmp_path)
    cp = wb.cache_path(out, "c1")
    cp.parent.mkdir(parents=True)
    cp.write_text(json.dumps({"cache_version": wb.CACHE_VERSION}), encoding="utf-8")
    future = time.time() + 60
    import os
    os.utime(cp, (future, future))                       # 캐시가 소스보다 최신
    assert wb._cache_fresh(cp, out, "c1")
    src = out / "c1" / "parse.parquet"
    os.utime(src, (future + 60, future + 60))            # 소스 재기록 → stale
    assert not wb._cache_fresh(cp, out, "c1")
    os.utime(cp, (future + 120, future + 120))           # 재빌드(캐시 갱신) → fresh
    assert wb._cache_fresh(cp, out, "c1")
    cp.write_text(json.dumps({"cache_version": wb.CACHE_VERSION + 1}), encoding="utf-8")
    os.utime(cp, (future + 120, future + 120))
    assert not wb._cache_fresh(cp, out, "c1")            # 버전 불일치 → stale


# ── 서버 라우트 (인프로세스, 임시 포트 — 코퍼스 불필요) ──────────────────────
class _StubRunner:
    def __init__(self):
        self.submitted = []
        self.jobs = {}

    def submit(self, job):
        self.submitted.append(job)
        self.jobs[job["clip_id"]] = {"status": "queued", "job": job}
        return 202, {"clip_id": job["clip_id"], "status": "queued"}


def _serve(handler) -> tuple[ThreadingHTTPServer, str]:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def _req(method: str, url: str, body: dict | None = None) -> tuple[int, dict | str]:
    req = urllib.request.Request(url, method=method,
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read().decode("utf-8")
            code = r.status
    except urllib.error.HTTPError as e:                  # 4xx 도 본문이 계약
        raw = e.read().decode("utf-8")
        code = e.code
    try:
        return code, json.loads(raw)
    except ValueError:
        return code, raw


def test_server_gt_roundtrip_and_restart_restore(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    gt = tmp_path / "gt.jsonl"
    srv, base = _serve(build_workbench_app(out, gt_path=gt))
    try:
        code, body = _req("POST", f"{base}/api/gt",
                          {"clip": "test_x", "frame": 7, "flag": "pos"})
        assert code == 200 and body["ok"] and body["n"] == 1
        code, body = _req("POST", f"{base}/api/gt",
                          {"clip": "test_x", "frame": 7, "flag": "neg"})
        assert code == 200 and body["n"] == 1            # 같은 키 병합 (나중-이김)
        code, body = _req("GET", f"{base}/api/gt")
        assert code == 200 and [r["flag"] for r in body["rows"]] == ["neg"]
        code, body = _req("POST", f"{base}/api/gt", {"clip": "", "frame": 1, "flag": "pos"})
        assert code == 400
        code, body = _req("POST", f"{base}/api/gt", {"clip": "c", "frame": "x", "flag": "pos"})
        assert code == 400
    finally:
        srv.shutdown()
    # 재기동 복원 — 같은 GT 파일을 무는 새 서버 인스턴스
    srv2, base2 = _serve(build_workbench_app(out, gt_path=gt))
    try:
        code, body = _req("GET", f"{base2}/api/gt")
        assert code == 200
        assert [(r["clip"], r["frame"], r["flag"]) for r in body["rows"]] \
            == [("test_x", 7, "neg")]
    finally:
        srv2.shutdown()


def test_server_index_clips_and_unknown_routes(tmp_path):
    out = tmp_path / "out"
    (out / "clip_a").mkdir(parents=True)
    (out / "clip_a" / "likeness.json").write_text("{}", encoding="utf-8")
    (out / "no_likeness").mkdir()
    srv, base = _serve(build_workbench_app(out, gt_path=tmp_path / "gt.jsonl"))
    try:
        code, html = _req("GET", f"{base}/")
        assert code == 200 and "momentscan workbench" in html
        code, body = _req("GET", f"{base}/api/clips")
        assert code == 200 and [c["clip"] for c in body["clips"]] == ["clip_a"]
        assert body["clips"][0]["cached"] is False       # 소스 불완전 → 미캐시
        code, _ = _req("GET", f"{base}/api/clip/../etc")
        assert code == 404
        code, _ = _req("GET", f"{base}/api/clip/nope")
        assert code == 404
        code, _ = _req("GET", f"{base}/thumbs/../../gt.jsonl")
        assert code == 404
        code, _ = _req("GET", f"{base}/no/such")
        assert code == 404
    finally:
        srv.shutdown()


def test_server_register_wiring(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    video = tmp_path / "reg_src.mp4"
    video.write_bytes(b"\x00")
    runner = _StubRunner()
    srv, base = _serve(build_workbench_app(out, gt_path=tmp_path / "gt.jsonl", runner=runner))
    try:
        code, body = _req("POST", f"{base}/api/register",
                          {"source_path": str(video), "clip_id": "wb_e2e"})
        assert code == 202 and body["clip_id"] == "wb_e2e"
        assert runner.submitted[0]["clip_id"] == "wb_e2e"
        assert runner.submitted[0]["products"] == ["likeness"]   # 기판 = likeness 클로저
        assert runner.submitted[0]["source_uri"] == str(video)
        code, body = _req("GET", f"{base}/api/jobs")
        assert code == 200 and body["jobs"] == [{"clip_id": "wb_e2e", "status": "queued"}]
        code, body = _req("POST", f"{base}/api/register", {"source_path": "/no/such.mp4"})
        assert code == 400
        code, body = _req("POST", f"{base}/api/register", {"source_path": "s3://b/k.mp4"})
        assert code == 400                               # S3 = 범위 밖 (C1 면으로)
    finally:
        srv.shutdown()


def test_server_register_disabled_without_runner(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    srv, base = _serve(build_workbench_app(out, gt_path=tmp_path / "gt.jsonl", runner=None))
    try:
        code, body = _req("POST", f"{base}/api/register", {"source_path": "/x.mp4"})
        assert code == 503
        code, body = _req("GET", f"{base}/api/jobs")
        assert code == 200 and body["jobs"] == []
    finally:
        srv.shutdown()


# ── 코퍼스-보유 노드: 셀프테스트 픽 고정 (v0.9 검증 좌표) ────────────────────
SELFTEST_REF = {"test_3": [29, 511, 352], "dual_2": [34, 1052, 6], "test_4": [570, 408, 286]}


@pytest.mark.parametrize("clip", sorted(SELFTEST_REF))
def test_selftest_picks_pinned_on_corpus(clip):
    """워크벤치 캐시(첫 열람이 채움)가 있으면 기본-설정 픽을 v0.9 좌표에 고정.
    코퍼스/캐시 부재·구버전 캐시 노드는 skip — 행동 고정은 현행 캐시 보유 노드의 몫."""
    if not (L2 / clip / "likeness.json").exists():
        pytest.skip("corpus not present")
    cp = wb.cache_path(L2, clip)
    if not cp.exists():
        pytest.skip("workbench cache not built — momentscan workbench 첫 열람이 채운다")
    payload = json.loads(cp.read_text(encoding="utf-8"))
    if payload.get("cache_version") != wb.CACHE_VERSION:
        pytest.skip("stale cache version — 다음 열람이 재빌드한다")
    assert payload["selftest"] == SELFTEST_REF[clip]
    assert payload["clip"] == clip

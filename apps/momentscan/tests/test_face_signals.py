"""⑨ 표본 선발 신호·사다리 단위 테스트 (track/lk-sampling, 원장 ⑨).

face_signals 공식(pupil/sym/EAR)과 selection 사다리(_pick3)를 **합성 입력**으로 고정한다
— 코퍼스 무관(구/신 output/l2 어디서도 green), 포팅 버그(잘못된 인덱스/부호)를 잡는 것이
직무다(recipe_golden 이 recipe 에 하는 것과 같은 자리). 실측 코퍼스 표본값의 재동결은
머지 후 공유 코퍼스 스윕이 지불한다(CLAUDE.md 트랙-스코프: 산출물은 브랜치를 안 탄다).
"""
import numpy as np
import pytest

from momentscan.perception.readings.face_signals import (
    eye_openness,
    pupil_visibility,
    visual_frontality,
)
from momentscan.products.likeness import _pct_rank, _pick3, _rank01


def _blank(n: int = 1) -> np.ndarray:
    return np.zeros((n, 478, 3), dtype=np.float64)


# ── 측정 공식 (알려진 기하 → 알려진 값) ──────────────────────────────────────

def test_visual_frontality_zero_when_symmetric():
    P = _blank()
    P[0, 1, 0] = 0.0       # 코끝 x 가 좌우 뺨 중앙
    P[0, 234, 0] = -1.0    # 우 뺨
    P[0, 454, 0] = 1.0     # 좌 뺨
    assert visual_frontality(P)[0] == pytest.approx(0.0, abs=1e-9)


def test_visual_frontality_grows_with_offset():
    P = _blank()
    P[0, 1, 0] = 0.5
    P[0, 234, 0] = -1.0
    P[0, 454, 0] = 1.0     # dr=1.5, dl=0.5 → |log 3|
    assert visual_frontality(P)[0] == pytest.approx(float(np.log(3.0)), abs=1e-6)


def test_pupil_visibility_lid_over_iris():
    P = _blank()
    P[0, 469], P[0, 471] = [0, 0, 0], [1, 0, 0]   # 우 홍채 지름 1
    P[0, 470], P[0, 472] = [0, 0, 0], [1, 0, 0]
    P[0, 159], P[0, 145] = [0, 0, 0], [0, 0.4, 0]  # 우 눈꺼풀 개구 0.4
    P[0, 474], P[0, 476] = [0, 0, 0], [1, 0, 0]   # 좌 거울
    P[0, 475], P[0, 477] = [0, 0, 0], [1, 0, 0]
    P[0, 386], P[0, 374] = [0, 0, 0], [0, 0.4, 0]
    assert pupil_visibility(P)[0] == pytest.approx(0.4, abs=1e-6)


def test_eye_openness_ear():
    C = _blank()
    C[0, 159], C[0, 145] = [0, 0, 0], [0, 0.4, 0]   # 우 눈꺼풀 개구 0.4
    C[0, 33], C[0, 133] = [0, 0, 0], [1, 0, 0]       # 우 눈 폭 1
    C[0, 386], C[0, 374] = [0, 0, 0], [0, 0.4, 0]
    C[0, 362], C[0, 263] = [0, 0, 0], [1, 0, 0]
    assert eye_openness(C)[0] == pytest.approx(0.4, abs=1e-6)


# ── 랭킹 유틸 ─────────────────────────────────────────────────────────────────

def test_pct_rank_basic():
    assert list(_pct_rank(np.array([1.0, 2.0, 3.0, 4.0]))) == [25.0, 50.0, 75.0, 100.0]


def test_pct_rank_nan_preserved():
    r = _pct_rank(np.array([1.0, np.nan, 3.0]))
    assert r[0] == 50.0 and np.isnan(r[1]) and r[2] == 100.0


def test_rank01_and_flip():
    assert list(_rank01(np.array([10.0, 20.0, 30.0]))) == [0.0, 0.5, 1.0]
    assert list(_rank01(np.array([10.0, 20.0, 30.0]), flip=True)) == [1.0, 0.5, 0.0]


# ── 선발 사다리 (_pick3) ─────────────────────────────────────────────────────

def _sig(n: int, sym: float, dev: float, pupil: float):
    return np.full(n, sym), np.full(n, dev), np.full(n, pupil)


def test_pick3_strict_rung_with_time_gap():
    fx = np.array([0, 6, 12, 18, 24, 30])
    score = np.array([6, 5, 4, 3, 2, 1], float)
    sym, dev, pupil = _sig(6, 0.1, 0.0, 0.5)          # 전부 정면·눈뜸·pupil 충족
    got, note = _pick3(score, sym, dev, pupil, fx, [np.ones(6, bool)], False, [12, 6, 0])
    assert note == "all sym<0.6 pu>=0.4"              # 최엄격 rung 에서 채워짐
    assert [int(fx[i]) for i in got] == [0, 12, 24]   # gap≥12 그리디 (점수순)


def test_pick3_boarding_preferred_within_rung():
    fx = np.array([0, 6, 12, 18, 24, 30])
    score = np.array([1, 2, 3, 4, 5, 6], float)       # ride 프레임 점수가 더 높음
    sym, dev, pupil = _sig(6, 0.1, 0.0, 0.5)
    board = np.array([True, True, True, False, False, False])
    got, note = _pick3(score, sym, dev, pupil, fx, [board, np.ones(6, bool)], True, [12, 6, 0])
    assert note == "board sym<0.6 pu>=0.4"            # ⑦: 같은 rung 안 boarding 우선
    assert {int(fx[i]) for i in got} == {0, 6, 12}    # 점수 높은 ride 를 좇지 않는다


def test_pick3_fallback_score_only():
    fx = np.array([0, 6, 12])
    score = np.array([1, 3, 2], float)
    sym, dev, pupil = _sig(3, 2.0, 0.0, 0.5)          # sym 2.0 > 최광 rung 1.3
    got, note = _pick3(score, sym, dev, pupil, fx, [np.ones(3, bool)], False, [12, 6, 0])
    assert note == "FB:score-only"
    assert [int(fx[i]) for i in got] == [6, 12, 0]    # 점수 내림차순

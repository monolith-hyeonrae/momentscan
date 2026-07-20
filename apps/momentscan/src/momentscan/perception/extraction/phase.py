"""Scene-phase — 클립을 시간으로 나누는 방법 (boarding vs ride).

비밀 = **클립의 시간 분할 방법.** 현재: 전역 모션(다운스케일 그레이 프레임차)의 1-D
2-means 단일 경계 — 카트는 boarding 중 정지, ride 중 이동. 임계는 클립 자체에서
유도하므로(자기보정) 카메라/계절 드리프트가 없다. **코스 프로파일(장면 DTW 정렬) 도입
시 이 함수가 교체점**이다 (축 E: 시설/기구 확장 — 어트랙션마다 phase 모델이 다르다).

인터페이스(문제 언어) = frame_id → phase 맵 (+ frame_id → timestamp_ms, info).
구현(2-means 단일경계)은 갈려도 이 계약은 언다.

소비자:
  subjects/tubelets.py     tubelets.parquet 에 `scene_phase` 컬럼으로 도장(생산자 1점)
  products/select.py·highlight.py   is_ride 조건부(ride-only 하이라이트 baseline·burn-in)
  products/likeness.py     boarding 대표-뷰 선호(⑦ — boarding 얼굴이 덜 일그러짐)

이동 출처: subjects/tubelets.py (접수 #11, 2026-07 — user: "장면 페이즈 구분은 파일을
정확히 분리, 하이라이트 장면-맥락 조건부에도 쓰인다"). SMOOTH_S/SUSTAIN_S/FLAT_RATIO 는
값-불변 동반 이동 (preset-inventory O 항목=축 E preset 후보이나 이 트랙은 이동만).
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from visualbus import FileSource
from visualbus.timestamp import ns_to_seconds

SMOOTH_S = 2.0        # motion smoothing window (seconds)
SUSTAIN_S = 1.0       # ride must hold above threshold this long
FLAT_RATIO = 0.6      # low-cluster ≥ this × high-cluster → no boarding detected


def scene_phases(video_path: str | Path, *, fps: int | None = None) -> tuple[dict[int, str], dict[int, int], dict]:
    """One decode pass → (frame_id→phase, frame_id→timestamp_ms, info).

    Motion is computed on 160px-wide grayscale; the boarding/ride boundary is
    the first sustained crossing of a threshold placed between the two motion
    clusters of THIS clip.
    """
    src = FileSource(video_path, fps=fps)
    out_fps = float(fps) if fps else (src.profile.fps or 30.0)
    motion: dict[int, float] = {}
    ts_ms: dict[int, int] = {}
    prev = None
    try:
        for frame in src:
            ts_ms[frame.frame_id] = int(round(ns_to_seconds(frame.t_ns) * 1000))
            h, w = frame.data.shape[:2]
            scale = 160 / w
            g = cv2.cvtColor(
                cv2.resize(frame.data, (160, max(2, int(h * scale)))), cv2.COLOR_BGR2GRAY
            ).astype(np.int16)
            if prev is not None:
                motion[frame.frame_id] = float(np.mean(np.abs(g - prev)))
            prev = g
    finally:
        src.close()

    ids = sorted(motion)
    if not ids:
        return {}, ts_ms, {"boundary_frame": None, "note": "no frames"}

    win = max(1, int(SMOOTH_S * out_fps))
    vals = np.array([motion[i] for i in ids], dtype=np.float64)
    smooth = np.convolve(vals, np.ones(win) / win, mode="same")

    # 1-D 2-means: a self-calibrated still/moving split.
    c0, c1 = float(smooth.min()), float(smooth.max())
    for _ in range(20):
        assign = np.abs(smooth - c0) <= np.abs(smooth - c1)
        if assign.all() or (~assign).all():
            break
        c0, c1 = float(smooth[assign].mean()), float(smooth[~assign].mean())
    if c0 > c1:
        c0, c1 = c1, c0

    info: dict = {"motion_low": round(c0, 2), "motion_high": round(c1, 2)}
    if c1 <= 0 or c0 >= FLAT_RATIO * c1:
        # No still prefix distinguishable — the clip starts already riding.
        info.update({"boundary_frame": None, "note": "no boarding phase detected"})
        return {fid: "ride" for fid in ts_ms}, ts_ms, info

    theta = (c0 + c1) / 2.0
    sustain = max(1, int(SUSTAIN_S * out_fps))
    boundary = None
    above = 0
    for k, v in enumerate(smooth):
        above = above + 1 if v >= theta else 0
        if above >= sustain:
            boundary = ids[k - sustain + 1]
            break
    info["boundary_frame"] = boundary
    if boundary is None:   # never moved — treat all as boarding
        info["note"] = "no ride phase detected"
        return {fid: "boarding" for fid in ts_ms}, ts_ms, info
    return {fid: ("boarding" if fid < boundary else "ride") for fid in ts_ms}, ts_ms, info

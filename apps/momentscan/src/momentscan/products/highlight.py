"""highlight — WHEN×WHICH, 어트랙션×고객 반응의 시간 세그먼트 제품.

2026-07-03 select.py에서 졸업 (파일 + 산출물 한 묶음): likeness/portrait처럼
제품이 자기 파일과 자기 산출물(highlight.json)을 가진다. candidates.jsonl은
select(채점 기판 스테이지)의 likeness 로그로 남고, highlight는 여기 없다 —
공유 가변 파일의 스테이지-횡단 소유가 두 번 버그를 냈다 (portrait unlink
레이스 · select 프로브 false-skip).

two-stage ([[highlight-two-stage-principle]], E010 = WHEN v2) —
  WHEN  = max(드묾, 강렬함, 장면변화) — anomaly 쌍둥이 OR (recall 목표):
        강렬함 impact(t) = mean z⁺(Δexpression, Δpose, Δlighting, velocity)
        드묾  rarity(t) = kNN distance between 2s state windows (no baseline
        constant; person×visit conditioned). 셋째 트리거 '적절함'(조건부
        일치)은 코스 프로파일 도착 시.
  WHICH valence(t)×visibility(t) picks the representative frame in the segment
  segments are PHRASE-shaped on the WHEN line ONLY (v1은 WHEN×WHICH 합성에서
  잘랐음 — 설계 모순): local peak → half-height arc (onset→resolution),
  one phrase = one segment, emission = kind-coverage greedy (feature distance,
  not time — same kind twice is the same highlight sold twice).

하이라이트는 라이드의 것이지 탑승자별이 아니다 (사용자, 2026-06-12; duo 교감
통찰과 일치): 모든 라이더의 frame_scores를 프레임 단위 OR(max)로 합쳐 한
타임라인에서 악구를 자르고, 클립당 한 세트만 배출한다 — 그 순간을 가장 잘 산
라이더가 WHEN을 들고, 가장 잘 찍힌 라이더가 WHICH를 든다.

프레임 채점(frame_scores)은 select.py의 공유 기판을 소비한다 — 동결 168쌍
라벨이 그 파일을 측정하고, 이 파일은 그 위의 시간 제품 정책만 소유한다.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np
import polars as pl

from momentscan.products.select import TOP_K, frame_scores, rolling_median
from momentscan.stash import read_tubelets, write_highlight

log = logging.getLogger("momentscan.highlight")

# E011: 배달 경계는 추정이 아니라 규격 — 고정 길이 창을 WHEN 피크에 앉힌다.
# 길이는 프리셋 소유 파라미터(릴 템플릿·어트랙션별 규격); 여기는 기본값.
# STEP3: 기본 길이 6→3s (Apple Live Photo = 셔터 ±1.5s, 대칭), 피크를 가운데
# (1/2). 이전 비대칭(리드 1/3·여운 2/3)은 감정 반응에서 피크 후 표정이
# baseline(찡그림)으로 식는 fade를 길게 담아 불리 — 대칭이 라이브포토와 맞다.
CLIP_LEN_S = 3.0
CLIP_LEAD_FRAC = 1 / 2   # 창 안에서 피크의 위치 (가운데 — 대칭 캡처)
VAL_EMIT_FLOOR = -0.1    # STEP 3: a highlight is a positive moment — do NOT emit a
                         # segment whose DELIVERY window is valence-negative (a frowning
                         # scene), even if motion/rarity made it a candidate. Better one
                         # genuine highlight than padding top-k with scowls.
# 2026-07-03: emission = 맥락적 정합성 — 창이 어느 타겟 축에서든 양성 증거를 내면
# 방출한다 (joy 축 = valence ≥ floor  OR  thrill/energy 축 = arousal ≥ τ). 절대
# 기준·사람-baseline 없음. valence 단독 floor는 극단 포즈에서 em_*가 웃음을
# 음수로 오판하면 그 사람의 최고 순간을 통째로 지웠다 (test_0 s2 head-back
# laugh: valence −0.28, arousal 86~98백분위 — 코퍼스 스윕이 τ를 앵커).
# τ=0.30: test_3 지속-찡그림 창 전부 wa≤0.086 (차단 유지), 현행-통과 창 p90=0.169,
# s2 웃음 최강 창 wa=0.362 (구제). 코퍼스 후보 179 차단 중 10만 구제 (보수).
AROUSAL_EMIT_TAU = 0.30
MAX_PHRASE_S = 12.0      # E010: 제품 제약 — 순간은 챕터가 아니다 (aux 평탄
                         # 신호의 반높이 확장이 36s까지 자라던 문제의 캡)


def _phrase_segments(s: dict, *, fps: int, top_k: int) -> list[dict]:
    """E010 phrase v2 — phrases on the WHEN line, emission by kind coverage.

    v1 flaws fixed by construction (docs/products.md highlight §):
    - boundaries come from WHEN only (two-stage restored — a face turning
      away no longer "resolves" an event);
    - no baseline constant: a phrase is a local arc — peak, expanded to its
      half-height (onset → peak → resolution);
    - one phrase = one segment (a `used` mask owns covered frames);
    - top-k is a KIND-coverage set: greedy by score, skipping phrases whose
      state descriptor sits too close to an already-picked one. Separation
      is feature distance, NOT time distance (two far-apart identical drops
      are duplicates; two adjacent different moments both count).
    """
    when, fx, ts = s["when"], s["fx"], s["ts"]
    hl, which, Xn = s["rank_sig"], s["which"], s["statevec"]
    valence = s.get("valence", np.zeros(len(fx)))
    arousal = s.get("arousal", np.zeros(len(fx)))
    if np.isfinite(when).sum() < 10:
        return []
    sm = rolling_median(when, 3)                        # kill 1-frame spikes

    peaks = [i for i in range(1, len(sm) - 1)
             if np.isfinite(sm[i]) and sm[i] >= sm[i - 1] and sm[i] >= sm[i + 1]]
    peaks.sort(key=lambda i: -sm[i])

    used = np.zeros(len(sm), dtype=bool)
    phrases: list[dict] = []
    for i in peaks:
        if used[i] or not np.isfinite(when[i]):
            continue
        half = sm[i] * 0.5
        # 확장은 시간 기준 (희소 트랙에서 인덱스 거리 ≠ 시간 거리 — cap_1
        # aux 36s 사례), 관측 공백 >2s는 악구를 끊는다 (안 보이던 구간을
        # 가로지르는 악구는 없다). 캡 = 피크 좌우 MAX_PHRASE_S/2.
        reach_ms, gap_ms = MAX_PHRASE_S / 2 * 1000, 2000

        def t_of(j: int) -> int:
            return int(ts[int(fx[j])])
        L = i
        while L > 0 and np.isfinite(sm[L - 1]) and sm[L - 1] > half and not used[L - 1] \
                and t_of(i) - t_of(L - 1) <= reach_ms and t_of(L) - t_of(L - 1) <= gap_ms:
            L -= 1
        R = i
        while R < len(sm) - 1 and np.isfinite(sm[R + 1]) and sm[R + 1] > half \
                and not used[R + 1] \
                and t_of(R + 1) - t_of(i) <= reach_ms and t_of(R + 1) - t_of(R) <= gap_ms:
            R += 1
        if R - L + 1 < 3:                                # an arc, not a blip
            continue
        used[L:R + 1] = True
        # resolved = 영상 끝에서 잘리지 않고 호가 닫혔는가. 감점하지 않는다
        # — 완결성은 세그먼트가 아니라 편집된 릴의 속성이고(클립들은 편집
        # 재료다, 사용자 2026-06-12), 잘린 관측일 수 있다는 신호로서만
        # 메타데이터에 남겨 편집 레이어가 판단하게 한다.
        resolved = R < len(sm) - 1 and np.isfinite(sm[min(R + 1, len(sm) - 1)])
        rep = L + int(np.nanargmax(which[L:R + 1]))      # WHICH picks inside
        score = float(np.nanmax(np.nan_to_num(hl[L:R + 1], nan=0.0)))
        phrases.append({"L": L, "R": R, "peak": i, "rep": rep, "score": score,
                        "resolved": resolved, "kind": Xn[L:R + 1].mean(axis=0)})

    # delivery window per phrase (E011 spec) — needed for overlap suppression
    for p in phrases:
        peak_ts = int(ts[int(fx[p["peak"]])])
        p["start_ms"] = max(0, peak_ts - int(CLIP_LEAD_FRAC * CLIP_LEN_S * 1000))
        p["end_ms"] = p["start_ms"] + int(CLIP_LEN_S * 1000)

    # kind-coverage emission — same kind twice = the same highlight sold twice;
    # window-overlap twice = the same SECONDS sold twice (합동 라인에서 두
    # 라이더의 인접 피크가 따로 악구가 되는 경우 — 그건 한 순간이다).
    phrases.sort(key=lambda p: -p["score"])
    tau = 0.0
    if len(phrases) > 1:
        K = np.stack([p["kind"] for p in phrases])
        D = np.sqrt(((K[:, None, :] - K[None, :, :]) ** 2).sum(-1))
        tau = 0.5 * float(np.median(D[np.triu_indices(len(phrases), 1)]))
    max_overlap_ms = 0.25 * CLIP_LEN_S * 1000
    picked: list[int] = []
    for pi, p in enumerate(phrases):
        if len(picked) >= top_k:
            break
        # 정합성 방출 — 창이 어느 타겟 축에서든 양성 증거를 내는가 (OR):
        # joy 축 = valence ≥ floor, thrill/energy 축 = arousal ≥ τ. valence 단독
        # veto는 극단 포즈의 웃음(em_* 오판, arousal은 발화)을 지웠다. 동역학만
        # 튀고 어느 축도 안 울리는 창(글리치·가림)은 여전히 차단 = anomaly 가드.
        in_w = [j for j in range(len(fx))
                if p["start_ms"] <= int(ts[int(fx[j])]) <= p["end_ms"]]
        wv = [valence[j] for j in in_w if np.isfinite(valence[j])]
        wa = [arousal[j] for j in in_w if np.isfinite(arousal[j])]
        joy = not (wv and float(np.mean(wv)) < VAL_EMIT_FLOOR)
        energy = bool(wa) and float(np.mean(wa)) >= AROUSAL_EMIT_TAU
        if not joy and not energy:
            continue
        if any(np.sqrt(((p["kind"] - phrases[q]["kind"]) ** 2).sum()) < tau
               for q in picked):
            continue
        if any(min(p["end_ms"], phrases[q]["end_ms"])
               - max(p["start_ms"], phrases[q]["start_ms"]) > max_overlap_ms
               for q in picked):
            continue
        picked.append(pi)

    segs = []
    for pi in picked:
        p = phrases[pi]
        # E011: delivery = fixed window anchored on the WHEN peak (detection
        # keeps the arc; the boundary is a product SPEC, not an estimate).
        # WHICH picks the rep frame inside what is actually DELIVERED.
        win = [j for j in range(len(fx))
               if p["start_ms"] <= int(ts[int(fx[j])]) <= p["end_ms"]
               and np.isfinite(which[j])]
        rep = max(win, key=lambda j: float(which[j])) if win else p["rep"]
        # WHEN driver breakdown at the peak — WHY this window fired (which anomaly twin /
        # scene-change / positive valence carried it). when = max(impact, rarity, scene, 3·val⁺).
        pk = p["peak"]
        drv = {"impact": float(np.nan_to_num(s["impact"][pk])),
               "rarity": float(np.nan_to_num(s["rarity"][pk])),
               "scene": float(np.nan_to_num(s["scene"][pk])),
               "valence": 3.0 * max(float(np.nan_to_num(s["valence"][pk])), 0.0)}
        segs.append({
            "peak_frame": int(fx[rep]),                  # the frame humans see/label
            "when_frame": int(fx[p["peak"]]),
            "start_ms": p["start_ms"],
            "end_ms": p["end_ms"],
            "resolved": bool(p["resolved"]),
            "score": round(p["score"], 3),
            "drivers": {k: round(v, 2) for k, v in drv.items()},   # observable: what carried WHEN
            "driver": max(drv, key=drv.get),
        })
    return segs


def _joint_scores(track_scores: dict[int, dict]) -> dict:
    """Merge per-track frame_scores into one clip-level dict for highlight.

    Frame-wise OR(max) over riders for when/rank_sig/which/highlight (a
    moment is a candidate if it is one for ANY rider; the best-captured
    rider carries WHICH); statevec = mean over riders present (kind
    descriptor). ts is global per frame, so dicts merge directly.
    """
    all_fx = sorted({int(f) for s in track_scores.values() for f in s["fx"]})
    pos = {tid: {int(f): i for i, f in enumerate(s["fx"])}
           for tid, s in track_scores.items()}
    n = len(all_fx)
    keys = ("when", "rank_sig", "which", "highlight", "valence", "arousal", "impact", "rarity", "scene")
    out: dict = {k: np.full(n, np.nan) for k in keys}
    d = next(iter(track_scores.values()))["statevec"].shape[1]
    sv_sum, sv_n = np.zeros((n, d)), np.zeros(n)
    for tid, s in track_scores.items():
        p = pos[tid]
        for j, f in enumerate(all_fx):
            i = p.get(f)
            if i is None:
                continue
            for k in keys:
                v = s[k][i]
                if np.isfinite(v):
                    out[k][j] = v if not np.isfinite(out[k][j]) else max(out[k][j], v)
            sv = s["statevec"][i]
            if np.isfinite(sv).all():
                sv_sum[j] += sv
                sv_n[j] += 1
    out["statevec"] = sv_sum / np.maximum(sv_n, 1)[:, None]
    out["fx"] = np.array(all_fx)
    ts: dict = {}
    for s in track_scores.values():
        ts.update(s["ts"])
    out["ts"] = ts
    return out


def highlight_clip(out_root, clip_id: str, *, fps: int = 6, top_k: int = TOP_K) -> dict:
    """합동 WHEN 악구 → highlight.json (제품의 authoritative 기록 + 스테이지 프로브)."""
    t0 = time.perf_counter()
    tubes = read_tubelets(out_root, clip_id)

    track_scores: dict[int, dict] = {}
    track_roles: dict[int, str] = {}
    for tid in sorted(tubes["track_id"].unique().to_list()):
        track_roles[tid] = tubes.filter(pl.col("track_id") == tid)["rider_role"][0]
        track_scores[tid] = frame_scores(out_root, clip_id, tid, fps=fps)

    segs: list[dict] = []
    main_tid = None
    if track_scores:
        joint = _joint_scores(track_scores)
        segs = _phrase_segments(joint, fps=fps, top_k=top_k)
        main_tid = next((t for t, r in track_roles.items() if r == "main"),
                        sorted(track_scores)[0])

    record = {
        "clip_id": clip_id,
        "n_segs": len(segs),
        "segs": segs,
        "main_track": main_tid,
        "riders_joined": len(track_scores),
        "params": {"top_k": top_k, "clip_len_s": CLIP_LEN_S,
                   "val_emit_floor": VAL_EMIT_FLOOR, "arousal_emit_tau": AROUSAL_EMIT_TAU},
        "elapsed_s": round(time.perf_counter() - t0, 3),
        "ok": True,
    }
    write_highlight(Path(out_root), clip_id, record)
    log.info("highlight.done", extra={k: record[k] for k in
                                      ("clip_id", "n_segs", "riders_joined", "elapsed_s")})
    return record

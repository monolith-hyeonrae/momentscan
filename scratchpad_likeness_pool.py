"""likeness 표본 신뢰 점검(2026-07-21) — 풀 판독 시트: "풀 오염 vs 픽 결함" 가름 재료.

user 판정: 선정 crop(center_nearest)이 부적절 — 카드 실측 결함 후보 = 시선(상/하방)
무스크린·pitch 무스크린·상대-무표정 한계·gap 붕괴(dual_2)·가림. 이 시트는:
  행1 CURRENT = 현행 픽 3장 (pu/sym/ex + 신규 gz[시선]·pitch 계기 병기)
  행2 ALT     = 동일 사다리 + 시선 하드 스크린(gz<0.35)을 걸었을 때의 픽 3장
  행3~ POOL   = frontal_clean 풀 전체(시간순, ≤40 다운샘플; 픽 강제 포함)
                빨강 테두리 = gz>0.4(시선 이탈) · 초록 = 현행 픽 · 파랑 = ALT 픽
gz = max(up, down, side), eyeLook* 블렌드셰입 쌍 평균 — 이미 측정된 신호, 스크린 미사용.
판정 질문: 풀에 "차분-정면-카메라시선" 프레임이 실재하는가(있으면 픽/스크린 결함,
없으면 소재 한계). 결정은 user 동행 — 이 시트는 재료다.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import polars as pl

sys.path.insert(0, "apps/momentscan/src")
from momentscan.infra.store.stash import read_landmarks, read_features, read_tubelets
from momentscan.perception.readings.geometry import canonicalize
from momentscan.preset import resolve

from momentscan_features_specialist45d.registry import INDEX
from momentscan_features_specialist45d.specialists import BLENDSHAPE_ORDER

RACE = resolve("race981")
FRONTAL_DEG = RACE.camera.frontal_deg
SYM_LADDER = ((0.6, 15.0), (0.9, 20.0), (1.3, 999.0))
PUPIL_LADDER = (0.4, 0.3)
GAP_LADDER = (12, 6, 0)
GZ_MAX = 0.35            # 시선 하드 스크린(ALT 행 전용, 제안 눈금 — 판정 재료)
GZ_FLAG = 0.40           # 풀 타일 빨강 표기
TILE, PTILE, LABEL = 128, 96, 64


def face_signals(P):
    def d2(a, b):
        return np.linalg.norm(P[:, a, :2] - P[:, b, :2], axis=1)
    r_iris = (d2(469, 471) + d2(470, 472)) / 2 + 1e-9
    l_iris = (d2(474, 476) + d2(475, 477)) / 2 + 1e-9
    pupil = (d2(159, 145) / r_iris + d2(386, 374) / l_iris) / 2
    dr = np.abs(P[:, 1, 0] - P[:, 234, 0]) + 1e-9
    dl = np.abs(P[:, 454, 0] - P[:, 1, 0]) + 1e-9
    return pupil, np.abs(np.log(dr / dl))


def pct_rank(x):
    out = np.full(len(x), np.nan)
    fin = np.isfinite(x)
    if fin.sum():
        v = x[fin]
        out[fin] = np.array([float(np.mean(v <= xi)) * 100 for xi in x[fin]])
    return out


def sheet(clip_id: str, out_root: Path, out_png: Path) -> dict:
    rec = json.load(open(out_root / clip_id / "likeness.json"))
    tid, rider = next((int(t), r) for t, r in rec["riders"].items() if r.get("role") == "main")

    lm = read_landmarks(out_root, clip_id).filter(pl.col("track_id") == tid).sort("frame_idx")
    gt = pl.read_parquet(out_root / clip_id / "gate_trace.parquet").filter(pl.col("track_id") == tid)
    valid = set(gt.filter(pl.col("valid"))["frame_idx"].to_list())
    frontal_gt = set(gt.filter(pl.col("frontal_clean"))["frame_idx"].to_list())
    keep = lm["frame_idx"].is_in(list(valid))
    if int(keep.sum()) >= 10:
        lm = lm.filter(keep)
    fx = lm["frame_idx"].to_numpy()
    n = len(fx)
    P = np.array(lm["landmarks"].to_list(), dtype=np.float64).reshape(n, 478, 3)
    T = np.array(lm["transform"].to_list(), dtype=np.float64).reshape(n, 4, 4)
    cb = np.array(lm["crop_box"].to_list(), dtype=np.float64)
    canonicalize(P, T, cb)          # (호출부 관례 유지 — 이 시트는 픽셀 판독이 본체)
    fmask = np.array([f in frontal_gt for f in fx])

    feats = read_features(out_root, clip_id, "A").filter(pl.col("track_id") == tid).sort("frame_idx")
    pos = {f: i for i, f in enumerate(feats["frame_idx"].to_numpy())}
    M = np.array(feats["feature"].to_list(), dtype=np.float64)
    sel = np.array([pos[f] for f in fx])
    yaw = M[sel, INDEX["head_yaw_dev"]]
    pitch = M[sel, INDEX["head_pitch"]]
    blur = M[sel, INDEX["face_blur"]]

    pq = pl.read_parquet(out_root / clip_id / "parse.parquet").filter(pl.col("track_id") == tid)
    micro_of = dict(zip(pq["frame_idx"].to_list(), pq["face_micro"].to_list()))
    micro = np.array([micro_of.get(int(f), float("nan")) for f in fx], dtype=np.float64)
    det = pl.read_parquet(out_root / clip_id / "detections.parquet").filter(pl.col("track_id") == tid)
    norm_of = {int(f): float(np.linalg.norm(np.asarray(e)))
               for f, e in zip(det["frame_idx"].to_list(), det["embedding"].to_list()) if e is not None}
    emb_norm = np.array([norm_of.get(int(f), np.nan) for f in fx])

    tb = read_tubelets(out_root, clip_id).filter(pl.col("track_id") == tid)
    phase_of = dict(zip(tb["frame_idx"].to_list(), tb["scene_phase"].to_list()))
    board = np.array([phase_of.get(int(f)) == "boarding" for f in fx])
    use_phase = int(board.sum()) >= RACE.likeness.phase_min_frames

    B = np.array(lm["blendshapes"].to_list(), dtype=np.float64)
    bs = {nm: i for i, nm in enumerate(BLENDSHAPE_ORDER)}
    up = (B[:, bs["eyeLookUpLeft"]] + B[:, bs["eyeLookUpRight"]]) / 2
    down = (B[:, bs["eyeLookDownLeft"]] + B[:, bs["eyeLookDownRight"]]) / 2
    side = np.maximum((B[:, bs["eyeLookOutLeft"]] + B[:, bs["eyeLookInRight"]]) / 2,
                      (B[:, bs["eyeLookInLeft"]] + B[:, bs["eyeLookOutRight"]]) / 2)
    gz = np.maximum(np.maximum(up, down), side)
    gdir = np.where(down >= np.maximum(up, side), "d", np.where(up >= side, "u", "s"))
    ecols = [i for i, nm in enumerate(BLENDSHAPE_ORDER)
             if nm != "_neutral" and not nm.startswith("eyeLook")]
    expr = B[:, ecols].max(axis=1)

    pupil, sym = face_signals(P)
    micro_pct, sharp_pct, norm_pct = pct_rank(micro), pct_rank(blur), pct_rank(emb_norm)

    def rank01(x, flip=False):
        r = np.argsort(np.argsort(np.nan_to_num(x, nan=(np.inf if flip else -np.inf))))
        r = r / max(len(x) - 1, 1)
        return 1 - r if flip else r

    q3 = np.nanmean(np.vstack([sharp_pct, micro_pct, norm_pct]), axis=0)
    score = (0.40 * rank01(expr, flip=True) + 0.25 * rank01(pupil) + 0.35 * rank01(q3))
    dev_all = yaw - FRONTAL_DEG
    phase_pools = [board, np.ones(n, bool)] if use_phase else [np.ones(n, bool)]

    def pick3(score_vec, pupil_floors, extra_ok):
        for sym_max, dev_max in SYM_LADDER:
            for pu_min in pupil_floors:
                for pi, ph in enumerate(phase_pools):
                    cand = [i for i in range(n) if ph[i] and sym[i] < sym_max
                            and abs(dev_all[i]) < dev_max and extra_ok[i]
                            and (pu_min is None or pupil[i] >= pu_min)]
                    if len(cand) < 3:
                        continue
                    cand.sort(key=lambda i: -score_vec[i])
                    for gap in GAP_LADDER:
                        got = []
                        for i in cand:
                            if all(abs(int(fx[i]) - int(fx[j])) >= gap for j in got):
                                got.append(i)
                            if len(got) == 3:
                                break
                        if len(got) == 3:
                            break
                    if len(got) == 3:
                        ph_tag = "board" if (use_phase and pi == 0) else "all"
                        return got, f"{ph_tag} sym<{sym_max} pu>={pu_min} gap>={gap}"
        return list(np.argsort(-score_vec)[:3]), "FB:score-only"

    idx_of = {int(f): i for i, f in enumerate(fx)}
    cur = [idx_of[f] for f in rider["samples"]["center_nearest"] if f in idx_of]
    alt, alt_note = pick3(score, PUPIL_LADDER, gz < GZ_MAX)

    # ── 풀 표시 집합: frontal_clean 시간순 ≤40 + 픽 강제 포함 ──
    pool_idx = list(np.where(fmask)[0])
    show = (list(np.array(pool_idx)[np.unique(np.linspace(0, len(pool_idx) - 1, 40).astype(int))])
            if len(pool_idx) > 40 else pool_idx)
    show = sorted(set(show) | set(cur) | set(alt), key=lambda i: fx[i])

    cols = 10
    pool_rows = int(np.ceil(len(show) / cols))
    row_h, prow_h = TILE + 46, PTILE + 34
    W = LABEL + cols * (PTILE + 6) + 16
    H = 30 + 2 * row_h + 14 + pool_rows * prow_h + 8
    img = np.full((H, W, 3), 22, dtype=np.uint8)

    def text(s, x, y, color=(225, 225, 225), sc=0.4):
        cv2.putText(img, s, (x, y), cv2.FONT_HERSHEY_SIMPLEX, sc, color, 1, cv2.LINE_AA)

    cap = cv2.VideoCapture(str(out_root / clip_id / "detect.mp4"))

    def tile(i, x, y, sz, border=None, th=2):
        x1, y1, x2, y2 = (int(v) for v in cb[i])
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(fx[i]))
        ok, frm = cap.read()
        if ok and x2 - x1 > 1 and y2 - y1 > 1:
            img[y:y + sz, x:x + sz] = cv2.resize(frm[y1:y2, x1:x2], (sz, sz))
        if border is not None:
            cv2.rectangle(img, (x - 1, y - 1), (x + sz, y + sz), border, th)

    gzc = int(((gz < GZ_MAX) & fmask & (pupil >= 0.4)).sum())
    gaps = sorted(int(fx[i]) for i in cur)
    min_gap = min((b - a for a, b in zip(gaps, gaps[1:])), default=0)
    text(f"{clip_id}  t{tid}  POOL SHEET (sample-trust probe)   n_valid={n} frontal_clean={int(fmask.sum())}"
         f"  gaze-clean(gz<{GZ_MAX} & pu>=.4)={gzc}   cur min-gap={min_gap}f   ALT[{alt_note}]",
         10, 18, sc=0.46)

    for r, (name, picks, col) in enumerate((("CURRENT", cur, (90, 220, 90)),
                                            ("ALT +gaze", alt, (235, 200, 70)))):
        y0 = 30 + r * row_h
        text(name, 6, y0 + TILE // 2, col, 0.42)
        for k, i in enumerate(picks):
            x0 = LABEL + k * (TILE + 10)
            tile(i, x0, y0, TILE, border=col)
            text(f"f{int(fx[i])} y{yaw[i]:+.0f} pt{pitch[i]:+.0f}", x0 + 2, y0 + TILE + 13, (200, 200, 200), 0.35)
            text(f"pu {pupil[i]:.2f} gz {gz[i]:.2f}{gdir[i]} ex {expr[i]:.2f}",
                 x0 + 2, y0 + TILE + 27, (170, 170, 170), 0.34)
        if r == 1:
            text("hard screen gz<0.35 on same ladder", LABEL + 3 * (TILE + 10) + 8, y0 + 14,
                 (235, 200, 70), 0.36)

    py0 = 30 + 2 * row_h + 14
    text(f"POOL frontal_clean ({len(show)} shown, time-ordered)  red=gz>{GZ_FLAG}(averted)"
         "  green=current  blue=alt", 6, py0 - 4, (180, 160, 220), 0.38)
    for j, i in enumerate(show):
        x0 = LABEL + (j % cols) * (PTILE + 6)
        y0 = py0 + (j // cols) * prow_h + 4
        border = ((90, 220, 90) if i in cur else (235, 200, 70) if i in alt
                  else (60, 60, 235) if gz[i] > GZ_FLAG else None)
        tile(i, x0, y0, PTILE, border=border, th=2)
        warn = (60, 60, 235) if gz[i] > GZ_FLAG else (160, 160, 160)
        text(f"f{int(fx[i])}", x0 + 1, y0 + PTILE + 12, (200, 200, 200), 0.32)
        text(f"g{gz[i]:.2f}{gdir[i]} e{expr[i]:.2f}", x0 + 1, y0 + PTILE + 25, warn, 0.32)

    cap.release()
    cv2.imwrite(str(out_png), img)
    fmt = lambda i: {"f": int(fx[i]), "pu": round(float(pupil[i]), 2), "gz": round(float(gz[i]), 2),
                     "dir": str(gdir[i]), "ex": round(float(expr[i]), 2)}
    return {"clip": clip_id, "n_frontal": int(fmask.sum()), "n_gaze_clean": gzc,
            "cur_min_gap": min_gap, "alt_note": alt_note,
            "cur": [fmt(i) for i in cur], "alt": [fmt(i) for i in alt]}


if __name__ == "__main__":
    out_root = Path("output/l2")
    dst = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    dst.mkdir(parents=True, exist_ok=True)
    for clip in ("test_3", "test_12", "dual_2", "test_4", "test_0", "international_1"):
        try:
            r = sheet(clip, out_root, dst / f"pool_{clip}.png")
            print(json.dumps(r, ensure_ascii=False))
        except Exception as e:
            print(f"{clip}: FAIL {type(e).__name__}: {e}")

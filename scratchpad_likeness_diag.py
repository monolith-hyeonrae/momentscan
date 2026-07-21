"""lk-sampling 체크포인트 A(v6) — 원장 ⑧⑨ 진단 카드 (변경 전, 판정 재료).

v6 (user 판정 3: 눈동자 보여야·게슴츠레/입꼬리 배제·측면 여전히 많음) — 구조 교정:
  **정면이 다른 모든 얼굴 신호의 선행 게이트다.**
  ① 보이는-정면 = 뺨 대칭비 sym(코끝 기준 좌우 뺨 x-거리 log비; yaw 추정치 아님 —
     yaw 오분류 케이스 f716/f16을 sym이 정확히 뒤집는 것 프로브 실증)
  ② 그 위에서 눈동자-가시비 pupil = 눈꺼풀 개구 ÷ 홍채 지름 (양안 평균, 절대량 —
     "눈동자가 보일 정도로 떴는가"; 측면에선 홍채 랜드마크가 무너져 정면 선행 필수)
  ③ 그 위에서 무표정 우선 = 표정계수 낮은 순 (정면 위에서만 신뢰 — v3 교란 회피)
  사다리: phase(boarding→전체) × sym(0.6→0.9→1.3) × pupil(0.5→0.4→0.3), FB 표기.
  점수 = 0.45 rank(pupil) + 0.25 rank(무표정) + 0.2 rank(선명) + 0.1 rank(밝기).

행1 = 현행 표본 · 행2 = 후보 v6(교체=초록) · 행3 = v6 풀 상위 8.
경고: 빨강 = pupil<0.4 · 주황 = sym>0.9. 헤어뷰(left/right)는 측면 전용 슬롯.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import polars as pl

sys.path.insert(0, "apps/momentscan/src")
from mediapipe.tasks.python.vision.face_landmarker import (
    FaceLandmarksConnections as _FLC,
)

from momentscan.infra.store.stash import read_landmarks, read_features, read_tubelets
from momentscan.perception.readings.geometry import canonicalize, norm468
from momentscan.preset import resolve

from momentscan_features_specialist45d.registry import INDEX

RACE = resolve("race981")
FRONTAL_DEG = RACE.camera.frontal_deg
EDGE_DEG = RACE.camera.bin_edge_deg
SYM_LADDER = ((0.6, 15.0), (0.9, 20.0), (1.3, 999.0))   # (sym, |yaw dev|) 동시 만족 — 상호 환각 방어(v6.2)
PUPIL_LADDER = (0.4, 0.3)         # floor 직무=감김 배제(user f510 판정: 0.43 온전-차분=훌륭, 0.5는 과함)
GAP_LADDER = (12, 6, 0)           # 시간 간격(프레임, fps6: 2s→1s→0)
TILE, PAD, LABEL = 128, 6, 96
EDGES = [(c.start, c.end) for c in (*_FLC.FACE_LANDMARKS_CONTOURS, *_FLC.FACE_LANDMARKS_NOSE)]


def face_signals(P: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(pupil, sym) — pupil=눈꺼풀 개구/홍채 지름(양안 평균) · sym=뺨 x-거리 log비."""
    def d2(a, b):
        return np.linalg.norm(P[:, a, :2] - P[:, b, :2], axis=1)

    r_iris = (d2(469, 471) + d2(470, 472)) / 2 + 1e-9
    l_iris = (d2(474, 476) + d2(475, 477)) / 2 + 1e-9
    pupil = (d2(159, 145) / r_iris + d2(386, 374) / l_iris) / 2

    dr = np.abs(P[:, 1, 0] - P[:, 234, 0]) + 1e-9
    dl = np.abs(P[:, 454, 0] - P[:, 1, 0]) + 1e-9
    sym = np.abs(np.log(dr / dl))
    return pupil, sym


def pct_rank(x: np.ndarray) -> np.ndarray:
    out = np.full(len(x), np.nan)
    fin = np.isfinite(x)
    if fin.sum():
        v = x[fin]
        out[fin] = np.array([float(np.mean(v <= xi)) * 100 for xi in x[fin]])
    return out


def wire(img, pts3, cx, cy, s, color, th=1):
    for a, b in EDGES:
        pa = (int(cx + pts3[a, 0] * s), int(cy - pts3[a, 1] * s))
        pb = (int(cx + pts3[b, 0] * s), int(cy - pts3[b, 1] * s))
        cv2.line(img, pa, pb, color, th, cv2.LINE_AA)


def hist_panel(img, x, y, w, h, values, title, vlines=(), markers=()):
    cv2.rectangle(img, (x, y), (x + w, y + h), (60, 60, 60), 1)
    v = values[np.isfinite(values)]
    cv2.putText(img, title, (x + 4, y + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (200, 200, 200), 1, cv2.LINE_AA)
    if len(v) < 5:
        return
    lo, hi = float(np.min(v)), float(np.max(v))
    if hi - lo < 1e-9:
        hi = lo + 1e-9
    cnt, _ = np.histogram(v, bins=40, range=(lo, hi))
    bw = (w - 12) / 40
    for i, c in enumerate(cnt):
        bh = int((h - 34) * c / max(cnt.max(), 1))
        x0 = int(x + 6 + i * bw)
        cv2.rectangle(img, (x0, y + h - 8 - bh), (int(x0 + bw - 1), y + h - 8), (110, 110, 110), -1)

    def to_x(val):
        return int(x + 6 + (val - lo) / (hi - lo) * (w - 12))

    for val, color, lbl in vlines:
        if lo <= val <= hi:
            vx = to_x(val)
            cv2.line(img, (vx, y + 22), (vx, y + h - 8), color, 1)
            if lbl:
                cv2.putText(img, lbl, (vx - 10, y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.32, color, 1, cv2.LINE_AA)
    for val, color in markers:
        if np.isfinite(val) and lo <= val <= hi:
            cv2.drawMarker(img, (to_x(val), y + h - 16), color, cv2.MARKER_TRIANGLE_UP, 8, 2)


def diagnose(clip_id: str, out_root: Path, out_png: Path) -> dict:
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
    canon, _raw = canonicalize(P, T, cb)
    center_valid = np.median(canon, axis=0)
    fmask = np.array([f in frontal_gt for f in fx])
    center_frontal = np.median(canon[fmask], axis=0) if fmask.sum() >= 10 else None
    shift = (float(np.sqrt(((center_frontal - center_valid) ** 2).sum(axis=1).mean()))
             if center_frontal is not None else float("nan"))

    feats = read_features(out_root, clip_id, "A").filter(pl.col("track_id") == tid).sort("frame_idx")
    pos = {f: i for i, f in enumerate(feats["frame_idx"].to_numpy())}
    M = np.array(feats["feature"].to_list(), dtype=np.float64)
    sel = np.array([pos[f] for f in fx])
    yaw = M[sel, INDEX["head_yaw_dev"]]
    blur = M[sel, INDEX["face_blur"]]

    pq = pl.read_parquet(out_root / clip_id / "parse.parquet").filter(pl.col("track_id") == tid)
    micro_of = dict(zip(pq["frame_idx"].to_list(), pq["face_micro"].to_list()))
    micro = np.array([micro_of.get(int(f), float("nan")) for f in fx], dtype=np.float64)

    tb = read_tubelets(out_root, clip_id).filter(pl.col("track_id") == tid)
    phase_of = dict(zip(tb["frame_idx"].to_list(), tb["scene_phase"].to_list()))
    board = np.array([phase_of.get(int(f)) == "boarding" for f in fx])
    use_phase = int(board.sum()) >= RACE.likeness.phase_min_frames

    expr = np.zeros(n)
    if "blendshapes" in lm.columns and lm["blendshapes"][0] is not None:
        from momentscan_features_specialist45d.specialists import BLENDSHAPE_ORDER
        B = np.array(lm["blendshapes"].to_list(), dtype=np.float64)
        ecols = [i for i, nm in enumerate(BLENDSHAPE_ORDER)
                 if nm != "_neutral" and not nm.startswith("eyeLook")]
        expr = B[:, ecols].max(axis=1)

    pupil, sym = face_signals(P)
    micro_pct, sharp_pct = pct_rank(micro), pct_rank(blur)

    det = pl.read_parquet(out_root / clip_id / "detections.parquet").filter(pl.col("track_id") == tid)
    norm_of = {int(f): float(np.linalg.norm(np.asarray(e)))
               for f, e in zip(det["frame_idx"].to_list(), det["embedding"].to_list()) if e is not None}
    emb_norm = np.array([norm_of.get(int(f), np.nan) for f in fx])
    emb_cov = float(np.isfinite(emb_norm).mean())
    norm_pct = pct_rank(emb_norm)

    cur_center = rider["samples"]["center_nearest"]
    cur_bins = rider["samples"]["pose_bins"]
    idx_of = {int(f): i for i, f in enumerate(fx)}

    # ── v6 c-슬롯: 정면(sym) → 눈동자(pupil) → 무표정 — 사다리 + 점수 + 간격 ──
    def rank01(x, flip=False):
        r = np.argsort(np.argsort(np.nan_to_num(x, nan=(np.inf if flip else -np.inf))))
        r = r / max(len(x) - 1, 1)
        return 1 - r if flip else r

    # 하이브리드(user 확정): 무표정 1축 + pupil floor 만족형 + 품질 3축(선명·밝기·
    # emb_norm, nan-skip 평균 — norm 은 뭉개짐/차분정면에서 보완력 실측, 단독 백본은
    # pupil 미흡수·커버리지 구멍으로 탈락).
    q3 = np.nanmean(np.vstack([sharp_pct, micro_pct, norm_pct]), axis=0)
    score = (0.40 * rank01(expr, flip=True) + 0.25 * rank01(pupil) + 0.35 * rank01(q3))

    dev_all = yaw - FRONTAL_DEG
    phase_pools = [board, np.ones(n, bool)] if use_phase else [np.ones(n, bool)]

    def pick3(score_vec, pupil_floors, extra_ok, tag):
        """사다리(정면>pupil>phase 선호) + 점수순 + 시간간격 그리디 — A/B 공용."""
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
                        return got, f"{ph_tag} sym<{sym_max} pu>={pu_min}"
        return list(np.argsort(-score_vec)[:3]), "FB:score-only"

    picked, note = pick3(score, PUPIL_LADDER, np.ones(n, bool), "A")
    new_center = [int(fx[i]) for i in picked]

    # (CAND C/MagFace 행 제거 — user 판정 2026-07-21: L-B 미채택 실험 행, 비교 무의미)
    pool_show = sorted([i for i in range(n) if sym[i] < 0.9 and abs(yaw[i] - FRONTAL_DEG) < 20 and pupil[i] >= 0.4],
                       key=lambda i: -score[i])[:8]

    # ── 헤어뷰 빈(v5 유지): 빈-내 눈뜸 floor + Q ──────────────────────────
    ear_r = np.linalg.norm(canon[:, 159] - canon[:, 145], axis=1) / (
        np.linalg.norm(canon[:, 33] - canon[:, 133], axis=1) + 1e-9)
    ear_l = np.linalg.norm(canon[:, 386] - canon[:, 374], axis=1) / (
        np.linalg.norm(canon[:, 362] - canon[:, 263], axis=1) + 1e-9)
    eye_pct = pct_rank((ear_r + ear_l) / 2)
    Q = np.nanmean(np.vstack([eye_pct, micro_pct, sharp_pct]), axis=0)
    dev = dev_all
    new_bins: dict[str, int] = {}
    bin_note: dict[str, str] = {}
    for name, mask in (("frontal", np.abs(dev) < EDGE_DEG),
                       ("left", dev <= -EDGE_DEG), ("right", dev >= EDGE_DEG)):
        m = mask & np.isfinite(blur)
        if not m.any():
            continue
        mb = m & board
        pool = mb if (use_phase and mb.any()) else m
        pe = pool & (eye_pct >= 40)
        bin_note[name] = "" if pe.any() else " FB"
        pw = np.where(pe if pe.any() else pool)[0]
        new_bins[name] = int(fx[pw[np.argmax(np.nan_to_num(Q[pw], nan=-1))]])

    # ── 캔버스 ──────────────────────────────────────────────────────────────
    n_slots = max(3 + len(cur_bins), 8)
    panel_w, panel_h = 330, 187
    rows_w = LABEL + n_slots * (TILE + PAD) + 18
    W = rows_w + 2 * (panel_w + 14) + 10
    row_h = TILE + 58
    H = max(30 + 3 * row_h + 8, 30 + 3 * (panel_h + 12))
    img = np.full((H, W, 3), 22, dtype=np.uint8)

    def text(s, x, y, color=(225, 225, 225), sc=0.42):
        cv2.putText(img, s, (x, y), cv2.FONT_HERSHEY_SIMPLEX, sc, color, 1, cv2.LINE_AA)

    text(f"{clip_id}  t{tid}  sampling diagnosis v6 (ledger 8/9, BEFORE change)   "
         f"n_valid={n} frontal_clean={int(fmask.sum())} phase={'boarding' if use_phase else 'off'}"
         f"   H[{note}]", 10, 18, sc=0.46)

    cap = cv2.VideoCapture(str(out_root / clip_id / "detect.mp4"))

    def draw_tile(f, x, y, slot_lbl, changed=False):
        i = idx_of.get(int(f))
        if i is None:
            return
        x1, y1, x2, y2 = (int(v) for v in cb[i])
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(fx[i]))
        ok, frm = cap.read()
        if ok and x2 - x1 > 1 and y2 - y1 > 1:
            img[y:y + TILE, x:x + TILE] = cv2.resize(frm[y1:y2, x1:x2], (TILE, TILE))
        col = None
        if np.isfinite(pupil[i]) and pupil[i] < 0.4:
            col = (60, 60, 235)                                # 빨강: 눈동자 안 보임
        elif np.isfinite(sym[i]) and sym[i] > 0.9:
            col = (40, 150, 245)                               # 주황: 정면 아님
        if col is not None:
            cv2.rectangle(img, (x, y), (x + TILE - 1, y + TILE - 1), col, 2)
        if changed:
            cv2.rectangle(img, (x - 2, y - 2), (x + TILE + 1, y + TILE + 1), (90, 220, 90), 2)
        ph = "B" if board[i] else "r"
        text(slot_lbl, x + 2, y + 12, (200, 200, 100), 0.36)
        text(f"f{int(f)} y{yaw[i]:+.0f} {ph}", x + 2, y + TILE + 13, (170, 170, 170), 0.35)
        text(f"pu {pupil[i]:.2f} sy {sym[i]:.1f} ex {expr[i]:.2f}", x + 2, y + TILE + 27,
             (170, 170, 170), 0.33)
        nm = f"nm{norm_pct[i]:.0f}%" if np.isfinite(norm_pct[i]) else "nm--"
        text(nm, x + 2, y + TILE + 41, (150, 150, 150), 0.33)

    yA, yB = 30, 30 + row_h
    yC = 30 + 2 * row_h
    text("CURRENT", 8, yA + TILE // 2, (120, 180, 240), 0.4)
    text("CAND H", 8, yB + TILE // 2, (120, 220, 120), 0.4)
    text("(hybrid)", 8, yB + TILE // 2 + 14, (120, 220, 120), 0.3)
    text("H POOL", 8, yC + TILE // 2, (180, 160, 220), 0.4)
    text("REPRESENTATIVE (frontal)", LABEL, 27, (200, 200, 100), 0.36)
    hv_x = LABEL + 4 * (TILE + PAD) + 18
    text("HAIR VIEWS (side by design)", hv_x, 27, (180, 160, 220), 0.36)
    slots = [("c1", 0), ("c2", 1), ("c3", 2)] + [(b, k + 3) for k, b in enumerate(cur_bins)]
    for name, k in slots:
        x = LABEL + k * (TILE + PAD) + (18 if k >= 4 else 0)
        if k < 3:
            if k < len(cur_center):
                draw_tile(cur_center[k], x, yA, name)
            if k < len(new_center):
                draw_tile(new_center[k], x, yB, name, changed=(new_center[k] not in cur_center))
        else:
            draw_tile(cur_bins[name], x, yA, name)
            if name in new_bins:
                draw_tile(new_bins[name], x, yB, name + bin_note.get(name, ""),
                          changed=(new_bins[name] != cur_bins[name]))
    for j, i in enumerate(pool_show):
        draw_tile(int(fx[i]), LABEL + j * (TILE + PAD), yC, f"p{j+1}")

    px0 = rows_w + 10
    smp_i = [idx_of[f] for f in (*cur_center, *cur_bins.values()) if f in idx_of]
    hist_panel(img, px0, 30, panel_w, panel_h, pupil,
               "pupil visibility = lid gap / iris dia  | floor .4",
               vlines=((0.4, (90, 200, 90), ".4"), (0.33, (60, 60, 235), ".33")),
               markers=[(pupil[i], (120, 180, 240)) for i in smp_i])
    hist_panel(img, px0, 30 + panel_h + 12, panel_w, panel_h, sym,
               "visual frontality sym=|log(cheekR/cheekL)| | .6/.9",
               vlines=((0.6, (90, 200, 90), ".6"), (0.9, (40, 150, 245), ".9")),
               markers=[(sym[i], (120, 180, 240)) for i in smp_i])
    px1 = px0 + panel_w + 14
    x, y, w, h = px1, 30, panel_w, panel_h
    cv2.rectangle(img, (x, y), (x + w, y + h), (60, 60, 60), 1)
    text("canon center: valid-all(yellow) vs frontal-only(green)", x + 4, y + 14, (200, 200, 200), 0.36)
    cy, s = y + h // 2 + 8, h * 0.36
    wire(img, norm468(center_valid), x + w // 2, cy, s, (60, 200, 230))
    if center_frontal is not None:
        wire(img, norm468(center_frontal), x + w // 2, cy, s, (90, 220, 90))
        text(f"shift RMS {shift:.4f}", x + 4, y + h - 8, (170, 170, 170), 0.38)
    hist_panel(img, px1, 30 + panel_h + 12, panel_w, panel_h, yaw - FRONTAL_DEG,
               f"yaw dev (bin edges +-{EDGE_DEG:.0f}) | canon {n} -> frontal {int(fmask.sum())}",
               vlines=((-EDGE_DEG, (90, 200, 90), ""), (EDGE_DEG, (90, 200, 90), "")),
               markers=[(yaw[i] - FRONTAL_DEG, (120, 180, 240)) for i in smp_i])

    cap.release()
    cv2.imwrite(str(out_png), img)
    fmt = lambda i: {"f": int(fx[i]), "pu": round(float(pupil[i]), 2),
                     "sy": round(float(sym[i]), 2), "ex": round(float(expr[i]), 2)}
    fmt2 = lambda i: {**fmt(i),
                      "nm": None if not np.isfinite(norm_pct[i]) else round(float(norm_pct[i]))}
    return {"clip": clip_id, "tid": tid, "H_note": note,
            "H": [fmt2(i) for i in picked]}


if __name__ == "__main__":
    out_root = Path("output/l2")
    dst = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    dst.mkdir(parents=True, exist_ok=True)
    rows = []
    for clip in ("test_3", "test_12", "dual_2", "test_4", "test_0", "international_1"):
        try:
            r = diagnose(clip, out_root, dst / f"diag_{clip}.png")
            rows.append(r)
            print(json.dumps(r, ensure_ascii=False))
        except Exception as e:
            print(f"{clip}: FAIL {type(e).__name__}: {e}")
    imgs = [cv2.imread(str(dst / f"diag_{r['clip']}.png")) for r in rows]
    if imgs:
        W = max(i.shape[1] for i in imgs)
        pads = [cv2.copyMakeBorder(i, 0, 8, 0, W - i.shape[1], cv2.BORDER_CONSTANT, value=(22, 22, 22))
                for i in imgs]
        cv2.imwrite(str(dst / "diag_montage.png"), cv2.vconcat(pads))
        print("montage:", dst / "diag_montage.png")

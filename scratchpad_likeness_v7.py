"""v7 후보 카드(2026-07-21) — 원장 ⑪ 사다리 A/B: CURRENT(봉인 v6.2) vs V7 후보.

V7 = ⑪ 판정의 구현 후보 (판정 재료 — 봉인은 user 동행):
  center: (a) phase 풀 제거(전체 valid) · gap 사다리 (12,6) — 0 붕괴 없음(다양성 floor)
          점수 = 0.30 무표정 + 0.15 pupil + 0.20 q3(선명·micro·norm)
                 + 0.15 vis2(cs=identity-legibility · mv=입-가시) — (c)(d)
                 + 0.20 light(⑪-e 직접 축: lum_eff=skin_lum×(1−clip_hi), 풀-내 상대
                   — boarding이 재던 조도 이점의 실측 대체; 절대 floor 금지=노출 교훈)
  bins:   (b) boarding 소프트 유지 + 눈뜸 floor pct40 + Q 6축(눈뜸·micro·선명
          + 빈-내 상대 cs · mv · light) — 측면의 cs 절대 비교 금지(포즈 교란).
행1 = CURRENT(likeness.json 표본) · 행2 = V7(교체=초록) · 행3 = V7 풀 상위 8.
패널: cos_self 분포 · mouth_vis 분포 · center 와이어(valid vs frontal) · yaw dev.
타일 라벨 셋째 줄 = cs/mv 백분위(풀-전역).
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
from momentscan_features_specialist45d.specialists import BLENDSHAPE_ORDER

RACE = resolve("race981")
FRONTAL_DEG = RACE.camera.frontal_deg
EDGE_DEG = RACE.camera.bin_edge_deg
SYM_LADDER = ((0.6, 15.0), (0.9, 20.0), (1.3, 999.0))
PUPIL_LADDER = (0.4, 0.3)
GAP_LADDER_V7 = (12, 6)          # ⑪-a: 0 없음 — 첫 1초 3연사 재발 방지
TILE, PAD, LABEL = 128, 6, 96
EDGES = [(c.start, c.end) for c in (*_FLC.FACE_LANDMARKS_CONTOURS, *_FLC.FACE_LANDMARKS_NOSE)]


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
    canon, _ = canonicalize(P, T, cb)
    center_valid = np.median(canon, axis=0)
    fmask = np.array([f in frontal_gt for f in fx])
    center_frontal = np.median(canon[fmask], axis=0) if fmask.sum() >= 10 else None

    feats = read_features(out_root, clip_id, "A").filter(pl.col("track_id") == tid).sort("frame_idx")
    pos = {f: i for i, f in enumerate(feats["frame_idx"].to_numpy())}
    M = np.array(feats["feature"].to_list(), dtype=np.float64)
    sel = np.array([pos[f] for f in fx])
    yaw = M[sel, INDEX["head_yaw_dev"]]
    blur = M[sel, INDEX["face_blur"]]

    pq = pl.read_parquet(out_root / clip_id / "parse.parquet").filter(pl.col("track_id") == tid)
    micro_of = dict(zip(pq["frame_idx"].to_list(), pq["face_micro"].to_list()))
    micro = np.array([micro_of.get(int(f), float("nan")) for f in fx], dtype=np.float64)
    mv_of = (dict(zip(pq["frame_idx"].to_list(), pq["mouth_vis"].to_list()))
             if "mouth_vis" in pq.columns else {})
    mv = np.array([mv_of.get(int(f), float("nan")) for f in fx], dtype=np.float64)
    lum_of = dict(zip(pq["frame_idx"].to_list(), pq["skin_lum"].to_list()))
    hi_of = dict(zip(pq["frame_idx"].to_list(), pq["skin_clip_hi"].to_list()))
    lum = np.array([lum_of.get(int(f), float("nan")) for f in fx], dtype=np.float64)
    chi = np.array([hi_of.get(int(f), float("nan")) for f in fx], dtype=np.float64)
    lum_eff = lum * (1.0 - np.nan_to_num(chi, nan=0.0))   # ⑪-e: 백화 픽셀만큼 조도 이득 삭감

    det = pl.read_parquet(out_root / clip_id / "detections.parquet")
    dmain = det.filter(pl.col("track_id") == tid)
    erows = [(int(f), np.asarray(e, float)) for f, e in
             zip(dmain["frame_idx"].to_list(), dmain["embedding"].to_list()) if e is not None]
    cs = np.full(n, np.nan)
    nrm_full = np.full(n, np.nan)
    if len(erows) >= 10:
        dfr = np.array([f for f, _ in erows])
        dE = np.stack([e for _, e in erows])
        dn = np.linalg.norm(dE, axis=1)
        Eh = dE / dn[:, None]
        c_self = np.median(Eh, axis=0)
        c_self /= np.linalg.norm(c_self)
        cos_of = dict(zip(dfr.tolist(), (Eh @ c_self).tolist()))
        nrm_of = dict(zip(dfr.tolist(), dn.tolist()))
        cs = np.array([cos_of.get(int(f), np.nan) for f in fx])
        nrm_full = np.array([nrm_of.get(int(f), np.nan) for f in fx])

    tb = read_tubelets(out_root, clip_id).filter(pl.col("track_id") == tid)
    phase_of = dict(zip(tb["frame_idx"].to_list(), tb["scene_phase"].to_list()))
    board = np.array([phase_of.get(int(f)) == "boarding" for f in fx])
    use_phase = int(board.sum()) >= RACE.likeness.phase_min_frames

    B = np.array(lm["blendshapes"].to_list(), dtype=np.float64)
    ecols = [i for i, nm in enumerate(BLENDSHAPE_ORDER)
             if nm != "_neutral" and not nm.startswith("eyeLook")]
    expr = B[:, ecols].max(axis=1)

    pupil, sym = face_signals(P)
    micro_pct, sharp_pct = pct_rank(micro), pct_rank(blur)
    norm_pct, cs_pct, mv_pct = pct_rank(nrm_full), pct_rank(cs), pct_rank(mv)
    light_pct = pct_rank(lum_eff)

    def rank01(x, flip=False):
        r = np.argsort(np.argsort(np.nan_to_num(x, nan=(np.inf if flip else -np.inf))))
        r = r / max(len(x) - 1, 1)
        return 1 - r if flip else r

    q3 = np.nanmean(np.vstack([sharp_pct, micro_pct, norm_pct]), axis=0)
    vis2 = np.nanmean(np.vstack([cs_pct, mv_pct]), axis=0)      # ⑪-c/d: 판독성+입-가시
    score = (0.30 * rank01(expr, flip=True) + 0.15 * rank01(pupil)
             + 0.20 * rank01(q3) + 0.15 * rank01(vis2) + 0.20 * rank01(lum_eff))
    dev_all = yaw - FRONTAL_DEG

    def pick3_v7(score_vec):
        """⑪-a: phase 풀 없음(전체) · gap (12,6)만 — 붕괴 없이 rung 완화로 넘어감."""
        for sym_max, dev_max in SYM_LADDER:
            for pu_min in PUPIL_LADDER:
                cand = [i for i in range(n) if sym[i] < sym_max
                        and abs(dev_all[i]) < dev_max and pupil[i] >= pu_min]
                if len(cand) < 3:
                    continue
                cand.sort(key=lambda i: -score_vec[i])
                for gap in GAP_LADDER_V7:
                    got = []
                    for i in cand:
                        if all(abs(int(fx[i]) - int(fx[j])) >= gap for j in got):
                            got.append(i)
                        if len(got) == 3:
                            break
                    if len(got) == 3:
                        return got, f"sym<{sym_max} pu>={pu_min} gap>={gap}"
        return list(np.argsort(-score_vec)[:3]), "FB:score-only"

    picked, note = pick3_v7(score)
    new_center = [int(fx[i]) for i in picked]
    cur_center = rider["samples"]["center_nearest"]
    cur_bins = rider["samples"]["pose_bins"]
    idx_of = {int(f): i for i, f in enumerate(fx)}

    # ── V7 헤어뷰 빈: boarding 소프트 유지 + 눈뜸 floor + Q 5축(빈-내 상대 cs/mv) ──
    ear_r = np.linalg.norm(canon[:, 159] - canon[:, 145], axis=1) / (
        np.linalg.norm(canon[:, 33] - canon[:, 133], axis=1) + 1e-9)
    ear_l = np.linalg.norm(canon[:, 386] - canon[:, 374], axis=1) / (
        np.linalg.norm(canon[:, 362] - canon[:, 263], axis=1) + 1e-9)
    eye_pct = pct_rank((ear_r + ear_l) / 2)
    new_bins: dict[str, int] = {}
    bin_note: dict[str, str] = {}
    for name, mask in (("frontal", np.abs(dev_all) < EDGE_DEG),
                       ("left", dev_all <= -EDGE_DEG), ("right", dev_all >= EDGE_DEG)):
        m = mask & np.isfinite(blur)
        if not m.any():
            continue
        mb = m & board
        pool = mb if (use_phase and mb.any()) else m
        pe = pool & (eye_pct >= 40)
        bin_note[name] = "" if pe.any() else " FB"
        pw = np.where(pe if pe.any() else pool)[0]
        cs_bin, mv_bin, lt_bin = pct_rank(cs[pw]), pct_rank(mv[pw]), pct_rank(lum_eff[pw])
        Q6 = np.nanmean(np.vstack([eye_pct[pw], micro_pct[pw], sharp_pct[pw], cs_bin, mv_bin, lt_bin]), axis=0)
        new_bins[name] = int(fx[pw[np.argmax(np.nan_to_num(Q6, nan=-1))]])

    # ── 캔버스 (diag 3행 구도 유지 — 판정 형식 연속성) ──────────────────────
    n_slots = max(3 + len(cur_bins), 8)
    panel_w, panel_h = 330, 187
    rows_w = LABEL + n_slots * (TILE + PAD) + 18
    W = rows_w + 2 * (panel_w + 14) + 10
    row_h = TILE + 58
    H = max(30 + 3 * row_h + 8, 30 + 3 * (panel_h + 12))
    img = np.full((H, W, 3), 22, dtype=np.uint8)

    def text(s, x, y, color=(225, 225, 225), sc=0.42):
        cv2.putText(img, s, (x, y), cv2.FONT_HERSHEY_SIMPLEX, sc, color, 1, cv2.LINE_AA)

    text(f"{clip_id}  t{tid}  V7.1 (ledger 11: no-phase center + gap>=6 + cs/mv + LIGHT axis)   "
         f"n_valid={n} frontal_clean={int(fmask.sum())} bins_phase={'board-soft' if use_phase else 'off'}"
         f"   V7.1[{note}]", 10, 18, sc=0.46)

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
            col = (60, 60, 235)
        elif np.isfinite(sym[i]) and sym[i] > 0.9:
            col = (40, 150, 245)
        if col is not None:
            cv2.rectangle(img, (x, y), (x + TILE - 1, y + TILE - 1), col, 2)
        if changed:
            cv2.rectangle(img, (x - 2, y - 2), (x + TILE + 1, y + TILE + 1), (90, 220, 90), 2)
        ph = "B" if board[i] else "r"
        text(slot_lbl, x + 2, y + 12, (200, 200, 100), 0.36)
        text(f"f{int(f)} y{yaw[i]:+.0f} {ph}", x + 2, y + TILE + 13, (170, 170, 170), 0.35)
        text(f"pu {pupil[i]:.2f} sy {sym[i]:.1f} ex {expr[i]:.2f}", x + 2, y + TILE + 27,
             (170, 170, 170), 0.33)
        css = f"cs{cs_pct[i]:.0f}" if np.isfinite(cs_pct[i]) else "cs--"
        mvs = f" mv{mv_pct[i]:.0f}" if np.isfinite(mv_pct[i]) else " mv--"
        lts = f" lt{light_pct[i]:.0f}" if np.isfinite(light_pct[i]) else " lt--"
        text(css + mvs + lts, x + 2, y + TILE + 41, (150, 150, 150), 0.33)

    yA, yB, yC = 30, 30 + row_h, 30 + 2 * row_h
    text("CURRENT", 8, yA + TILE // 2, (120, 180, 240), 0.4)
    text("V7", 8, yB + TILE // 2, (120, 220, 120), 0.4)
    text("(ledger 11)", 8, yB + TILE // 2 + 14, (120, 220, 120), 0.3)
    text("V7 POOL", 8, yC + TILE // 2, (180, 160, 220), 0.4)
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
    pool_show = sorted([i for i in range(n) if sym[i] < 0.9 and abs(dev_all[i]) < 20 and pupil[i] >= 0.4],
                       key=lambda i: -score[i])[:8]
    for j, i in enumerate(pool_show):
        draw_tile(int(fx[i]), LABEL + j * (TILE + PAD), yC, f"p{j+1}")

    px0 = rows_w + 10
    smp_i = [idx_of[f] for f in (*new_center, *new_bins.values()) if f in idx_of]
    hist_panel(img, px0, 30, panel_w, panel_h, cs,
               "identity legibility cos_self (11-c)  markers=V7 picks",
               markers=[(cs[i], (120, 220, 120)) for i in smp_i])
    hist_panel(img, px0, 30 + panel_h + 12, panel_w, panel_h, mv,
               "mouth_vis (11-d, soft pref)  markers=V7 picks",
               markers=[(mv[i], (120, 220, 120)) for i in smp_i])
    px1 = px0 + panel_w + 14
    x, y, w, h = px1, 30, panel_w, panel_h
    cv2.rectangle(img, (x, y), (x + w, y + h), (60, 60, 60), 1)
    text("canon center: valid-all(yellow) vs frontal-only(green)", x + 4, y + 14, (200, 200, 200), 0.36)
    cy, s = y + h // 2 + 8, h * 0.36
    wire(img, norm468(center_valid), x + w // 2, cy, s, (60, 200, 230))
    if center_frontal is not None:
        wire(img, norm468(center_frontal), x + w // 2, cy, s, (90, 220, 90))
    hist_panel(img, px1, 30 + panel_h + 12, panel_w, panel_h, lum_eff,
               "face light lum_eff=skin_lum x (1-clip_hi) (11-e)  markers=V7 picks",
               markers=[(lum_eff[i], (120, 220, 120)) for i in smp_i])

    cap.release()
    cv2.imwrite(str(out_png), img)
    gaps = sorted(new_center)
    fmt = lambda f: {"f": int(f)}
    return {"clip": clip_id, "tid": tid, "V7_note": note,
            "cur": cur_center, "v7": new_center,
            "v7_min_gap": min((b - a for a, b in zip(gaps, gaps[1:])), default=0),
            "center_changed": sorted(set(new_center) - set(cur_center)),
            "bins_cur": cur_bins, "bins_v7": new_bins,
            "bins_changed": {k: v for k, v in new_bins.items() if cur_bins.get(k) != v}}


if __name__ == "__main__":
    out_root = Path("output/l2")
    dst = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    dst.mkdir(parents=True, exist_ok=True)
    rows = []
    for clip in ("test_3", "test_12", "dual_2", "test_4", "test_0", "international_1"):
        try:
            r = diagnose(clip, out_root, dst / f"v7_{clip}.png")
            rows.append(r)
            print(json.dumps(r, ensure_ascii=False))
        except Exception as e:
            print(f"{clip}: FAIL {type(e).__name__}: {e}")
    imgs = [cv2.imread(str(dst / f"v7_{r['clip']}.png")) for r in rows]
    if imgs:
        W = max(i.shape[1] for i in imgs)
        pads = [cv2.copyMakeBorder(i, 0, 8, 0, W - i.shape[1], cv2.BORDER_CONSTANT, value=(22, 22, 22))
                for i in imgs]
        cv2.imwrite(str(dst / "v7_montage.png"), cv2.vconcat(pads))
        print("montage:", dst / "v7_montage.png")

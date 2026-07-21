"""얼굴면 조도 분석 카드(2026-07-21) — 원장 ⑪-e 실측: 표본 선별에 조도 축이 없다는
user 지적의 분석 재료. 클립별: skin_lum 타임라인(phase 색: boarding=청록·ride=회색,
CURRENT 픽=파랑▲·상단 rule=p10/50/90) + 조도 사다리 표본 타일(p5/p25/p50/p75/p95
+ clip_hi 최대 프레임) — "밝음 선호가 어디까지 안전한가"(백화 꼬리) 육안 판정용.
신호=parse 보존분: skin_lum(0~255, skin 마스크 휘도)·skin_clip_hi(백화 비율)·
skin_contrast·face_micro. 절대 비교 금지(클립 간 스케일 상이) — 풀-내 상대만.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import polars as pl

sys.path.insert(0, "apps/momentscan/src")
from momentscan.infra.store.stash import read_landmarks, read_tubelets

TILE = 112
PLOT_W, PLOT_H = 560, 150


def analyze(clip_id: str, out_root: Path) -> np.ndarray:
    rec = json.load(open(out_root / clip_id / "likeness.json"))
    tid, rider = next((int(t), r) for t, r in rec["riders"].items() if r.get("role") == "main")
    picks = set(rider["samples"]["center_nearest"])

    pq = pl.read_parquet(out_root / clip_id / "parse.parquet").filter(pl.col("track_id") == tid).sort("frame_idx")
    f = np.array(pq["frame_idx"].to_list())
    lum = np.array(pq["skin_lum"].to_list(), dtype=float)
    hi = np.array(pq["skin_clip_hi"].to_list(), dtype=float)
    ct = np.array(pq["skin_contrast"].to_list(), dtype=float)
    mc = np.array(pq["face_micro"].to_list(), dtype=float)
    tb = read_tubelets(out_root, clip_id).filter(pl.col("track_id") == tid)
    ph = dict(zip(tb["frame_idx"].to_list(), tb["scene_phase"].to_list()))
    board = np.array([ph.get(int(x)) == "boarding" for x in f])
    fin = np.isfinite(lum)

    lm = read_landmarks(out_root, clip_id).filter(pl.col("track_id") == tid)
    cb_of = {int(x): tuple(int(v) for v in b)
             for x, b in zip(lm["frame_idx"].to_list(), lm["crop_box"].to_list())}

    W = 10 + PLOT_W + 12 + 6 * (TILE + 6) + 10
    H = 26 + max(PLOT_H, TILE + 34) + 10
    img = np.full((H, W, 3), 22, np.uint8)

    def text(s, x, y, c=(220, 220, 220), sc=0.38):
        cv2.putText(img, s, (x, y), cv2.FONT_HERSHEY_SIMPLEX, sc, c, 1, cv2.LINE_AA)

    l = lum[fin]
    p10, p50, p90 = (float(np.percentile(l, p)) for p in (10, 50, 90))
    bl = lum[board & fin]
    rl = lum[~board & fin]
    bmed = float(np.median(bl)) if len(bl) else float("nan")
    rmed = float(np.median(rl)) if len(rl) else float("nan")
    text(f"{clip_id}  t{tid}  face illumination (skin_lum, 0-255)   p10/50/90 = {p10:.0f}/{p50:.0f}/{p90:.0f}   "
         f"boarding p50={bmed:.0f}(n={len(bl)}) vs ride p50={rmed:.0f}(n={len(rl)})   "
         f"clip_hi max={np.nanmax(hi):.2f}", 10, 16, (225, 225, 225), 0.42)

    # ── 타임라인 ──────────────────────────────────────────────
    x0, y0 = 10, 26
    cv2.rectangle(img, (x0, y0), (x0 + PLOT_W, y0 + PLOT_H), (60, 60, 60), 1)
    lo, hi_y = float(np.min(l)), float(np.max(l))
    if hi_y - lo < 1e-9:
        hi_y = lo + 1e-9
    fx_lo, fx_hi = float(f.min()), float(max(f.max(), 1))

    def to_xy(fr, v):
        return (int(x0 + 4 + (fr - fx_lo) / (fx_hi - fx_lo) * (PLOT_W - 8)),
                int(y0 + PLOT_H - 6 - (v - lo) / (hi_y - lo) * (PLOT_H - 12)))

    for pv, col in ((p10, (70, 70, 70)), (p50, (110, 110, 110)), (p90, (70, 70, 70))):
        _, yy = to_xy(fx_lo, pv)
        cv2.line(img, (x0 + 2, yy), (x0 + PLOT_W - 2, yy), col, 1)
    for i in range(len(f)):
        if not fin[i]:
            continue
        xx, yy = to_xy(float(f[i]), lum[i])
        col = (200, 190, 80) if board[i] else (130, 130, 130)
        cv2.circle(img, (xx, yy), 1, col, -1)
    for pk in picks:
        w = np.where(f == pk)[0]
        if len(w) and fin[w[0]]:
            xx, yy = to_xy(float(pk), lum[w[0]])
            cv2.drawMarker(img, (xx, yy), (240, 170, 60), cv2.MARKER_TRIANGLE_UP, 10, 2)
    text("cyan=boarding gray=ride  blue triangle=CURRENT center picks  rules=p10/50/90",
         x0 + 4, y0 + PLOT_H + 14, (150, 150, 150), 0.34)

    # ── 조도 사다리 표본 타일: p5/p25/p50/p75/p95 + clip_hi 최대 ──
    cap = cv2.VideoCapture(str(out_root / clip_id / "detect.mp4"))
    order = np.argsort(lum + np.where(fin, 0, np.inf))
    n_fin = int(fin.sum())
    idxs = [order[int(q * (n_fin - 1))] for q in (0.05, 0.25, 0.50, 0.75, 0.95)]
    labels = ["p5", "p25", "p50", "p75", "p95"]
    if np.nanmax(hi) > 0.02:
        idxs.append(int(np.nanargmax(hi)))
        labels.append("hiMAX")
    tx0 = x0 + PLOT_W + 12
    for k, (i, lb) in enumerate(zip(idxs, labels)):
        x = tx0 + k * (TILE + 6)
        y = 26
        fr = int(f[i])
        box = cb_of.get(fr)
        if box:
            x1, y1, x2, y2 = box
            cap.set(cv2.CAP_PROP_POS_FRAMES, fr)
            ok, frm = cap.read()
            if ok and x2 - x1 > 1 and y2 - y1 > 1:
                img[y:y + TILE, x:x + TILE] = cv2.resize(frm[y1:y2, x1:x2], (TILE, TILE))
        text(lb, x + 2, y + 12, (200, 200, 100), 0.36)
        text(f"f{fr} lum{lum[i]:.0f}", x + 1, y + TILE + 12, (200, 200, 200), 0.32)
        text(f"hi{hi[i]:.2f} ct{ct[i]:.0f} mc{mc[i]:.0f}", x + 1, y + TILE + 25, (160, 160, 160), 0.32)
    cap.release()
    return img


if __name__ == "__main__":
    out_root = Path("output/l2")
    dst = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    dst.mkdir(parents=True, exist_ok=True)
    cards = []
    for clip in ("test_3", "test_12", "dual_2", "test_4", "test_0", "international_1"):
        try:
            cards.append(analyze(clip, out_root))
        except Exception as e:
            print(f"{clip}: FAIL {type(e).__name__}: {e}")
    if cards:
        W = max(c.shape[1] for c in cards)
        pads = [cv2.copyMakeBorder(c, 0, 6, 0, W - c.shape[1], cv2.BORDER_CONSTANT, value=(22, 22, 22))
                for c in cards]
        out = dst / "light_montage.png"
        cv2.imwrite(str(out), cv2.vconcat(pads))
        print("montage:", out)

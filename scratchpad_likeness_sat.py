"""피부 채도(saturation) 분석 카드(2026-07-21) — user 발상: 같은 카메라·같은 사람이면
채도 차이가 "빛이 좋은 장면"을 가른다 (international_1 초반=색 생동 / test_12 백화=
채도 붕괴 예상 — skin_clip_hi(≥250)가 못 잡는 245-미만 포화의 대안 신호).

측정 = 생산 parse._quality와 동일 기법(20 mid-skin 앵커 soft point-Gaussian × 얼굴
타원 hull)을 detect.mp4 프레임에 적용. **v2 교정(같은 날)**: HSV S는 chroma/명도
비율이라 밝을수록 하락(실측 corr(S,V) −0.76~−0.90, user 생동 구간이 S 저값으로 반전)
→ 지각적 "생동감" = **절대 chroma = max(BGR)−min(BGR)** 채택. skin_chroma(가중 평균)·
chroma_std(가중 σ = 채도 contrast)·S·V 병기. 절대 비교 금지 — 풀-내 상대만.
카드: [lum(V) × chroma 2D 산점(백화=우하단·생동=우상단 서명, CURRENT 픽=파랑▲)
+ chroma 타임라인 + 표본 타일(ch p5/p50/p95·washMAX=고휘도-저채도·vivid=고휘도-고채도)].
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

from momentscan.infra.store.stash import read_landmarks, read_tubelets

_SKIN_ANCHORS = (9, 107, 336, 151, 67, 297, 50, 280, 205, 425, 116, 345, 123, 352,
                 152, 175, 200, 6, 197, 195)
_SIG_FRAC = 0.16
_L_OUTER, _R_OUTER = 33, 263
_OVAL = sorted({i for c in _FLC.FACE_LANDMARKS_FACE_OVAL for i in (c.start, c.end)})
TILE = 112
SC_W, SC_H = 300, 170
TL_W, TL_H = 300, 170


def skin_sv(frame, pts, cb):
    """생산 _quality 동형의 소프트 스킨 가중으로 (sat_mean, sat_std, v_mean)."""
    H, W = frame.shape[:2]
    x1, y1 = max(0, int(cb[0])), max(0, int(cb[1]))
    x2, y2 = min(W, int(cb[2])), min(H, int(cb[3]))
    if x2 - x1 < 8 or y2 - y1 < 8:
        return None
    sub = frame[y1:y2, x1:x2]
    hsv = cv2.cvtColor(sub, cv2.COLOR_BGR2HSV)
    S = hsv[..., 1].astype(np.float32)
    V = hsv[..., 2].astype(np.float32)
    bgr = sub.astype(np.float32)
    C = bgr.max(axis=2) - bgr.min(axis=2)          # 절대 chroma — 지각 생동감의 자
    p = pts - np.array([x1, y1], np.float64)
    h, w = S.shape
    hull = cv2.convexHull(np.clip(p[_OVAL], [0, 0], [w - 1, h - 1]).astype(np.int32))
    facemask = np.zeros((h, w), np.uint8)
    cv2.fillConvexPoly(facemask, hull, 1)
    iod = np.linalg.norm(p[_L_OUTER] - p[_R_OUTER]) + 1e-6
    sig = _SIG_FRAC * iod
    yy, xx = np.mgrid[0:h, 0:w]
    wgt = np.zeros((h, w), np.float32)
    for a in _SKIN_ANCHORS:
        ax, ay = p[a]
        wgt += np.exp(-((xx - ax) ** 2 + (yy - ay) ** 2) / (2.0 * sig * sig))
    wgt = wgt * facemask
    wf = wgt.ravel()
    m = wf > 1e-3
    if m.sum() < 50:
        return None
    wm = wf[m]
    sw = wm.sum()
    sv, vv, cv_ = S.ravel()[m], V.ravel()[m], C.ravel()[m]
    s_mean = float((sv * wm).sum() / sw)
    v_mean = float((vv * wm).sum() / sw)
    c_mean = float((cv_ * wm).sum() / sw)
    c_std = float(np.sqrt(((cv_ - c_mean) ** 2 * wm).sum() / sw))
    return s_mean, c_std, v_mean, c_mean


def analyze(clip_id: str, out_root: Path) -> tuple[np.ndarray, dict]:
    rec = json.load(open(out_root / clip_id / "likeness.json"))
    tid, rider = next((int(t), r) for t, r in rec["riders"].items() if r.get("role") == "main")
    picks = rider["samples"]["center_nearest"]

    lm = read_landmarks(out_root, clip_id).filter(pl.col("track_id") == tid).sort("frame_idx")
    fx = lm["frame_idx"].to_numpy()
    Pn = np.array(lm["landmarks"].to_list(), dtype=np.float64).reshape(len(fx), 478, 3)
    CB = np.array(lm["crop_box"].to_list(), dtype=np.float64)
    row_of = {int(f): i for i, f in enumerate(fx)}

    tb = read_tubelets(out_root, clip_id).filter(pl.col("track_id") == tid)
    ph = dict(zip(tb["frame_idx"].to_list(), tb["scene_phase"].to_list()))

    n = len(fx)
    sat = np.full(n, np.nan)     # 이하 sat 변수 = 절대 chroma(v2 교정), sraw = HSV-S 참고용
    sstd = np.full(n, np.nan)
    vmn = np.full(n, np.nan)
    sraw = np.full(n, np.nan)
    cap = cv2.VideoCapture(str(out_root / clip_id / "detect.mp4"))
    idx = 0
    while True:
        ok, frm = cap.read()
        if not ok:
            break
        i = row_of.get(idx)
        if i is not None:
            cb = CB[i]
            pts = np.stack([cb[0] + Pn[i, :, 0] * (cb[2] - cb[0]),
                            cb[1] + Pn[i, :, 1] * (cb[3] - cb[1])], 1)
            r = skin_sv(frm, pts, cb)
            if r is not None:
                sraw[i], sstd[i], vmn[i], sat[i] = r
        idx += 1
    cap.release()

    fin = np.isfinite(sat) & np.isfinite(vmn)
    board = np.array([ph.get(int(f)) == "boarding" for f in fx])
    s, v = sat[fin], vmn[fin]
    corr = float(np.corrcoef(v, s)[0, 1]) if fin.sum() > 10 else float("nan")
    hi_lum = vmn >= np.nanpercentile(vmn, 90)
    wash_sig = (float(np.nanmean(sat[hi_lum & fin])) - float(np.nanmean(s))) if fin.sum() > 10 else float("nan")
    early = fx < 60
    corr_sraw = (float(np.corrcoef(vmn[fin], sraw[fin])[0, 1]) if fin.sum() > 10 else float("nan"))
    stats = {"clip": clip_id, "chroma_p10": round(float(np.percentile(s, 10)), 1),
             "chroma_p50": round(float(np.percentile(s, 50)), 1),
             "chroma_p90": round(float(np.percentile(s, 90)), 1),
             "corr_chroma_lum": round(corr, 2), "corr_HSVS_lum": round(corr_sraw, 2),
             "top10pct_lum_chroma_delta": round(wash_sig, 1),
             "early60_chroma": round(float(np.nanmean(sat[early & fin])), 1) if (early & fin).any() else None,
             "picks_chroma_pct": [round(float(np.mean(s <= sat[row_of[p]])) * 100)
                                  if p in row_of and np.isfinite(sat[row_of[p]]) else None for p in picks]}

    # ── 카드 ──────────────────────────────────────────────────────
    W = 10 + SC_W + 12 + TL_W + 12 + 5 * (TILE + 6) + 10
    H = 26 + max(SC_H, TILE + 34) + 12
    img = np.full((H, W, 3), 22, np.uint8)

    def text(t, x, y, c=(220, 220, 220), sc=0.38):
        cv2.putText(img, t, (x, y), cv2.FONT_HERSHEY_SIMPLEX, sc, c, 1, cv2.LINE_AA)

    text(f"{clip_id}  t{tid}  skin CHROMA=max-min (production mask)   ch p10/50/90 = "
         f"{stats['chroma_p10']}/{stats['chroma_p50']}/{stats['chroma_p90']}   corr(ch,lumV)={corr:+.2f}"
         f" (HSV-S {corr_sraw:+.2f})   top-lum ch delta={wash_sig:+.1f}", 10, 16, (225, 225, 225), 0.42)

    # 2D 산점: x=lumV, y=sat
    x0, y0 = 10, 26
    cv2.rectangle(img, (x0, y0), (x0 + SC_W, y0 + SC_H), (60, 60, 60), 1)
    vlo, vhi = float(np.min(v)), float(max(np.max(v), np.min(v) + 1e-9))
    slo, shi = float(np.min(s)), float(max(np.max(s), np.min(s) + 1e-9))

    def sxy(vv_, ss_):
        return (int(x0 + 4 + (vv_ - vlo) / (vhi - vlo) * (SC_W - 8)),
                int(y0 + SC_H - 6 - (ss_ - slo) / (shi - slo) * (SC_H - 12)))

    fi = np.where(fin)[0]
    for i in fi:
        t01 = (fx[i] - fx.min()) / max(fx.max() - fx.min(), 1)
        col = (200, 190, 80) if board[i] else (int(90 + 110 * t01),) * 3
        cv2.circle(img, sxy(vmn[i], sat[i]), 1, col, -1)
    for p in picks:
        i = row_of.get(p)
        if i is not None and fin[i]:
            cv2.drawMarker(img, sxy(vmn[i], sat[i]), (240, 170, 60), cv2.MARKER_TRIANGLE_UP, 10, 2)
    text("x=lum(V)  y=chroma   cyan=boarding gray:dark->light=time  tri=CURRENT", x0 + 4, y0 + SC_H + 12,
         (150, 150, 150), 0.32)

    # sat 타임라인
    tx0 = x0 + SC_W + 12
    cv2.rectangle(img, (tx0, y0), (tx0 + TL_W, y0 + TL_H), (60, 60, 60), 1)
    flo, fhi2 = float(fx.min()), float(max(fx.max(), fx.min() + 1))
    for i in fi:
        xx = int(tx0 + 4 + (fx[i] - flo) / (fhi2 - flo) * (TL_W - 8))
        yy = int(y0 + TL_H - 6 - (sat[i] - slo) / (shi - slo) * (TL_H - 12))
        col = (200, 190, 80) if board[i] else (130, 130, 130)
        cv2.circle(img, (xx, yy), 1, col, -1)
    for p in picks:
        i = row_of.get(p)
        if i is not None and fin[i]:
            xx = int(tx0 + 4 + (fx[i] - flo) / (fhi2 - flo) * (TL_W - 8))
            yy = int(y0 + TL_H - 6 - (sat[i] - slo) / (shi - slo) * (TL_H - 12))
            cv2.drawMarker(img, (xx, yy), (240, 170, 60), cv2.MARKER_TRIANGLE_UP, 10, 2)
    text("chroma timeline", tx0 + 4, y0 + TL_H + 12, (150, 150, 150), 0.32)

    # 표본 타일: sat p5/p50/p95 + washMAX(고휘도-저채도) + vivid(고휘도-고채도)
    order = np.argsort(sat + np.where(fin, 0, np.inf))
    nf = int(fin.sum())
    tiles = [(order[int(0.05 * (nf - 1))], "chP5"), (order[int(0.5 * (nf - 1))], "chP50"),
             (order[int(0.95 * (nf - 1))], "chP95")]
    lowq = sat <= np.nanpercentile(sat, 25)
    if (lowq & fin).any():
        tiles.append((int(np.nanargmax(np.where(lowq & fin, vmn, -np.inf))), "washMAX"))
    vr = (pct := lambda a: np.argsort(np.argsort(np.nan_to_num(a, nan=-np.inf))) / max(n - 1, 1))
    vivid = pct(vmn) + pct(sat)
    tiles.append((int(np.nanargmax(np.where(fin, vivid, -np.inf))), "vivid"))
    cap = cv2.VideoCapture(str(out_root / clip_id / "detect.mp4"))
    bx0 = tx0 + TL_W + 12
    for k, (i, lb) in enumerate(tiles):
        x = bx0 + k * (TILE + 6)
        y = 26
        fr = int(fx[i])
        x1, y1, x2, y2 = (int(c) for c in CB[i])
        cap.set(cv2.CAP_PROP_POS_FRAMES, fr)
        ok, frm = cap.read()
        if ok and x2 - x1 > 1 and y2 - y1 > 1:
            img[y:y + TILE, x:x + TILE] = cv2.resize(frm[y1:y2, x1:x2], (TILE, TILE))
        text(lb, x + 2, y + 12, (200, 200, 100), 0.36)
        text(f"f{fr} ch{sat[i]:.0f} sd{sstd[i]:.0f}", x + 1, y + TILE + 12, (200, 200, 200), 0.32)
        text(f"V{vmn[i]:.0f} S{sraw[i]:.0f}", x + 1, y + TILE + 25, (160, 160, 160), 0.32)
    cap.release()
    return img, stats


if __name__ == "__main__":
    out_root = Path("output/l2")
    dst = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    dst.mkdir(parents=True, exist_ok=True)
    cards = []
    for clip in ("test_3", "test_12", "dual_2", "test_4", "test_0", "international_1"):
        try:
            card, st = analyze(clip, out_root)
            cards.append(card)
            print(json.dumps(st, ensure_ascii=False))
        except Exception as e:
            print(f"{clip}: FAIL {type(e).__name__}: {e}")
    if cards:
        W = max(c.shape[1] for c in cards)
        pads = [cv2.copyMakeBorder(c, 0, 6, 0, W - c.shape[1], cv2.BORDER_CONSTANT, value=(22, 22, 22))
                for c in cards]
        out = dst / "sat_montage.png"
        cv2.imwrite(str(out), cv2.vconcat(pads))
        print("montage:", out)

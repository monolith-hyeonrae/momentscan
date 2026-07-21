"""반가림 표본 프로브(2026-07-21) — user 질문: pose_bin 픽(예: dual_2 right f1205)의
얼굴 반가림이 face embedding(방향=cos_self·상대-귀속 margin)이나 norm(품질 프록시),
parse mouth_vis(마스크 프록시)에 신호차를 남기는가. 남기면 빈 Q(현재 눈뜸·micro·선명
3축, 가림-맹목)에 편입할 후보가 된다. 카드 = right 빈을 cos_self 오름차순/norm
오름차순으로 두 번 정렬 — 가림 프레임이 저값 쪽에 몰리면 신호 실재.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import polars as pl

sys.path.insert(0, "apps/momentscan/src")
from momentscan.infra.store.stash import read_landmarks, read_features, read_tubelets
from momentscan.preset import resolve

from momentscan_features_specialist45d.registry import INDEX

RACE = resolve("race981")
FRONTAL_DEG = RACE.camera.frontal_deg
EDGE = RACE.camera.bin_edge_deg
TILE = 96

clip = sys.argv[1] if len(sys.argv) > 1 else "dual_2"
dst = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
dst.mkdir(parents=True, exist_ok=True)
out_root = Path("output/l2")

rec = json.load(open(out_root / clip / "likeness.json"))
tid, rider = next((int(t), r) for t, r in rec["riders"].items() if r.get("role") == "main")
bins = rider["samples"]["pose_bins"]

det = pl.read_parquet(out_root / clip / "detections.parquet")
main = det.filter(pl.col("track_id") == tid)
rows = [(int(f), np.asarray(e, float)) for f, e in zip(main["frame_idx"].to_list(), main["embedding"].to_list())
        if e is not None]
df = np.array([f for f, _ in rows])
dE = np.stack([e for _, e in rows])
nrm = np.linalg.norm(dE, axis=1)
Eh = dE / nrm[:, None]
c_self = np.median(Eh, axis=0)
c_self /= np.linalg.norm(c_self)
cos_self = Eh @ c_self
others = []
for ot in det["track_id"].unique().to_list():
    if ot == tid:
        continue
    oe = [np.asarray(e, float) for e in det.filter(pl.col("track_id") == ot)["embedding"].to_list() if e is not None]
    if len(oe) >= 10:
        O = np.stack(oe)
        oc = np.median(O / np.linalg.norm(O, axis=1, keepdims=True), axis=0)
        others.append(oc / np.linalg.norm(oc))
cos_other = np.max(np.stack([Eh @ oc for oc in others]), axis=0) if others else np.full(len(df), np.nan)
margin = cos_self - cos_other

feats = read_features(out_root, clip, "A").filter(pl.col("track_id") == tid)
F = np.array(feats["feature"].to_list(), dtype=np.float64)
yaw_of = dict(zip(feats["frame_idx"].to_list(), F[:, INDEX["head_yaw_dev"]]))
dev = np.array([yaw_of.get(int(f), np.nan) for f in df]) - FRONTAL_DEG

pq = pl.read_parquet(out_root / clip / "parse.parquet").filter(pl.col("track_id") == tid)
print("parse cols:", pq.columns)
mv_of = (dict(zip(pq["frame_idx"].to_list(), pq["mouth_vis"].to_list()))
         if "mouth_vis" in pq.columns else {})
mv = np.array([mv_of.get(int(f), np.nan) for f in df])

tb = read_tubelets(out_root, clip).filter(pl.col("track_id") == tid).sort("frame_idx")
runs: list[list] = []
for f, p in zip(tb["frame_idx"].to_list(), tb["scene_phase"].to_list()):
    if runs and runs[-1][2] == p and f - runs[-1][1] <= 6:
        runs[-1][1] = f
    else:
        runs.append([f, f, p])
print("phase runs:", [(a, b, p) for a, b, p in runs])


def pctl(v, x):
    v = v[np.isfinite(v)]
    return float(np.mean(v <= x)) * 100 if len(v) else float("nan")


masks = {"frontal": np.abs(dev) < EDGE, "left": dev <= -EDGE, "right": dev >= EDGE}
for name, m in masks.items():
    pick = bins.get(name)
    if pick is None:
        continue
    where = np.where(df == pick)[0]
    line = f"{name}: n_emb={int(m.sum())} pick f{pick}"
    if len(where):
        i = int(where[0])
        mvs = f"{mv[i]:.2f}" if np.isfinite(mv[i]) else "--"
        line += (f" | norm {nrm[i]:.1f} (bin-pct {pctl(nrm[m], nrm[i]):.0f}%)"
                 f" | cos_self {cos_self[i]:.3f} (bin-pct {pctl(cos_self[m], cos_self[i]):.0f}%)"
                 f" | margin {margin[i]:.3f} (bin-pct {pctl(margin[m], margin[i]):.0f}%)"
                 f" | mouth_vis {mvs}")
    else:
        line += " | (pick frame has no embedding row)"
    print(line)
    for lbl, v in (("norm", nrm), ("cos_self", cos_self), ("margin", margin), ("mouth_vis", mv)):
        vv = v[m]
        vv = vv[np.isfinite(vv)]
        if len(vv):
            print(f"    {lbl:9s} p10 {np.percentile(vv, 10):.3f}  p50 {np.percentile(vv, 50):.3f}  "
                  f"p90 {np.percentile(vv, 90):.3f}")

r = masks["right"] & np.isfinite(cos_self) & np.isfinite(mv)
if r.sum() > 10:
    print(f"right-bin corr(cos_self, mouth_vis) = {np.corrcoef(cos_self[r], mv[r])[0, 1]:.3f}"
          f"   corr(norm, mouth_vis) = {np.corrcoef(nrm[r], mv[r])[0, 1]:.3f}   n={int(r.sum())}")

# ── 카드: right 빈 두 정렬(가림이 저값에 몰리는지 육안 판정) ──────────────────
lm = read_landmarks(out_root, clip).filter(pl.col("track_id") == tid).sort("frame_idx")
cb_of = {int(f): tuple(int(v) for v in b)
         for f, b in zip(lm["frame_idx"].to_list(), lm["crop_box"].to_list())}
ridx = np.where(masks["right"] & np.isfinite(cos_self))[0]
COLS, PER = 9, 18


def show_list(order):
    show = list(order[:PER])
    pick = bins.get("right")
    if pick is not None and len(order) > PER:
        pi = [k for k, i in enumerate(order) if df[i] == pick]
        if pi and pi[0] >= PER:
            show[-1] = order[pi[0]]
    return show


sections = [("sorted by cos_self asc (low = identity least legible)",
             show_list(ridx[np.argsort(cos_self[ridx])])),
            ("sorted by norm asc (low = weakest embedding magnitude)",
             show_list(ridx[np.argsort(nrm[ridx])]))]
sec_h = [26 + int(np.ceil(len(s) / COLS)) * (TILE + 34) for _, s in sections]
H = 26 + sum(sec_h) + 8
W = 10 + COLS * (TILE + 6) + 6
img = np.full((H, W, 3), 22, np.uint8)


def text(s, x, y, c=(220, 220, 220), sc=0.38):
    cv2.putText(img, s, (x, y), cv2.FONT_HERSHEY_SIMPLEX, sc, c, 1, cv2.LINE_AA)


cap = cv2.VideoCapture(str(out_root / clip / "detect.mp4"))
text(f"{clip}  t{tid}  RIGHT-bin embedding/occlusion probe   n={len(ridx)}   "
     f"pick=f{bins.get('right')} (green)", 8, 16, (225, 225, 225), 0.44)
y0 = 26
for (title, show), h in zip(sections, sec_h):
    text(title, 8, y0 + 12, (180, 160, 220), 0.4)
    for j, i in enumerate(show):
        x = 10 + (j % COLS) * (TILE + 6)
        y = y0 + 20 + (j // COLS) * (TILE + 34)
        f = int(df[i])
        box = cb_of.get(f)
        if box:
            x1, y1, x2, y2 = box
            cap.set(cv2.CAP_PROP_POS_FRAMES, f)
            ok, frm = cap.read()
            if ok and x2 - x1 > 1 and y2 - y1 > 1:
                img[y:y + TILE, x:x + TILE] = cv2.resize(frm[y1:y2, x1:x2], (TILE, TILE))
        if f == bins.get("right"):
            cv2.rectangle(img, (x - 1, y - 1), (x + TILE, y + TILE), (90, 220, 90), 2)
        text(f"f{f} cs{cos_self[i]:.2f}", x + 1, y + TILE + 12, (200, 200, 200), 0.32)
        mvs = f" mv{mv[i]:.1f}" if np.isfinite(mv[i]) else ""
        text(f"nm{nrm[i]:.0f} mg{margin[i]:.2f}" + mvs, x + 1, y + TILE + 25, (160, 160, 160), 0.32)
    y0 += h
cap.release()
out = dst / f"embprobe_{clip}_right.png"
cv2.imwrite(str(out), img)
print("card:", out)

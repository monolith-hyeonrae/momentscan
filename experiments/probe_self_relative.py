"""probe-0 (throwaway): does per-person self-relative deviation on the frozen
512D face channel carry EXPRESSION, or is it dominated by pose/size nuisance?

Tests the new-idea keystone ("frozen 위 per-person 자기-상대 선택") on existing
data, zero extraction. Decides the channel ladder: if face-channel deviation
tracks expression -> cheap channel suffices; if nuisance-dominated -> escalate.
"""
from __future__ import annotations
import sys
import numpy as np
import polars as pl
import cv2
from scipy.stats import spearmanr

CLIP = sys.argv[1] if len(sys.argv) > 1 else "251227002408570"
SUBJECT = int(sys.argv[2]) if len(sys.argv) > 2 else 0
ROOT = f"output/l2/{CLIP}"

# --- face channel: per-frame 512D, this subject only ---
det = pl.read_parquet(f"{ROOT}/detections.parquet").filter(pl.col("subject_id") == SUBJECT)
det = det.sort("frame_idx")
fidx = det["frame_idx"].to_numpy()
emb = np.array(det["embedding"].to_list(), dtype=np.float64)
bbox = np.array(det["bbox"].to_list(), dtype=np.float64)  # x1,y1,x2,y2

# self-relative deviation: baseline = unit-sphere centroid, dev = 1 - cos
embn = emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9)
baseline = embn.mean(0)
baseline /= np.linalg.norm(baseline) + 1e-9
dev = 1.0 - embn @ baseline  # higher = further from this person's own center

# --- nuisance proxies (face channel must NOT be ruled by these) ---
area = (bbox[:, 2] - bbox[:, 0]) * (bbox[:, 3] - bbox[:, 1])
xcen = (bbox[:, 0] + bbox[:, 2]) / 2.0

# --- expression signal (independent channel): blendshape delta magnitude ---
lm = pl.read_parquet(f"{ROOT}/landmarks.parquet").sort("frame_idx")
lm_map = {int(r["frame_idx"]): np.array(r["blendshapes"], dtype=np.float64)
          for r in lm.iter_rows(named=True) if r["blendshapes"] is not None}
have = np.array([f in lm_map for f in fidx])
bs = np.array([lm_map[f] for f in fidx[have]])
bs_base = np.median(bs, axis=0)
expr = np.linalg.norm(bs - bs_base, axis=1)  # expression magnitude vs neutral

# pose proxy from head transform (4x4) rotation -> yaw-ish
tf = {int(r["frame_idx"]): np.array(r["transform"], dtype=np.float64).reshape(4, 4)
      for r in lm.iter_rows(named=True) if r["transform"] is not None}
yaw = np.array([np.arctan2(-tf[f][2, 0], np.hypot(tf[f][0, 0], tf[f][1, 0]))
                if f in tf else np.nan for f in fidx])

# --- verdict: what does face-channel deviation correlate with? ---
def sp(a, b):
    m = np.isfinite(a) & np.isfinite(b)
    return spearmanr(a[m], b[m]).correlation

print(f"=== probe-0  clip={CLIP} subject={SUBJECT}  n={len(fidx)} (expr n={have.sum()}) ===")
print(f"  WANT  corr(face_dev, expression_mag) = {sp(dev[have], expr):+.3f}")
print(f"  NUIS  corr(face_dev, face_area)      = {sp(dev, area):+.3f}")
print(f"  NUIS  corr(face_dev, x_center)       = {sp(dev, xcen):+.3f}")
print(f"  NUIS  corr(face_dev, |yaw|)          = {sp(dev, np.abs(yaw)):+.3f}")

# --- montage: low-dev (should be neutral/clean) vs high-dev (should be peaks) ---
order = np.argsort(dev)
K = 6
picks = [("LOW dev", order[:K]), ("HIGH dev", order[-K:][::-1])]
cap = cv2.VideoCapture(f"{ROOT}/detect.mp4")
def frame(i):
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(fidx[i]))
    ok, img = cap.read()
    return img if ok else np.zeros((720, 1280, 3), np.uint8)
TH = 220
rows = []
for label, idxs in picks:
    cells = []
    for i in idxs:
        img = frame(i)
        h, w = img.shape[:2]
        img = cv2.resize(img, (int(TH * w / h), TH))
        txt = f"f{int(fidx[i])} d{dev[i]:.2f}"
        cv2.rectangle(img, (0, 0), (140, 22), (0, 0, 0), -1)
        cv2.putText(img, txt, (3, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        cells.append(img)
    W = max(c.shape[1] for c in cells)
    cells = [cv2.copyMakeBorder(c, 0, 0, 0, W - c.shape[1], cv2.BORDER_CONSTANT) for c in cells]
    strip = np.hstack(cells)
    bar = np.zeros((26, strip.shape[1], 3), np.uint8)
    cv2.putText(bar, label, (5, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    rows.append(np.vstack([bar, strip]))
out = f"experiments/probe0_{CLIP}_s{SUBJECT}.png"
cv2.imwrite(out, np.vstack(rows))
print(f"  montage -> {out}")

"""portrait gate prototype (throwaway): objective admissibility gate at
blendshape+pose level, then visualize the SELECTION so a human can judge it.

Gate (objective only — no aesthetic 0-axis):
  eyes open   max(eyeBlinkL, eyeBlinkR) < 0.45
  frontal     |yaw|,|pitch|,|roll| < 20 deg   (from MediaPipe head transform)
  mouth ok    jawOpen < 0.5  (no mid-speech/yawn)
  sharp       Laplacian-var(crop) > 30th pct  (relative)
Among survivors the tiebreak is OBJECTIVE (sharpest) — we do NOT rank the
unmeasurable aesthetic axis. Output = three-panel evidence viz.
"""
from __future__ import annotations
import numpy as np, polars as pl, cv2

CLIP = "251227002408570"
ROOT = f"output/l2/{CLIP}"
BLINK_T, POSE_T, JAW_T, BLUR_PCT = 0.45, 20.0, 0.5, 30

lm = pl.read_parquet(f"{ROOT}/landmarks.parquet").filter(pl.col("rider_role") == "main").sort("frame_idx")
fidx = lm["frame_idx"].to_numpy()
bs = np.array(lm["blendshapes"].to_list(), float)
cb = np.array(lm["crop_box"].to_list(), float).astype(int)
tf = np.array(lm["transform"].to_list(), float).reshape(-1, 4, 4)
R = tf[:, :3, :3]
yaw = np.degrees(np.arctan2(-R[:, 2, 0], np.hypot(R[:, 0, 0], R[:, 1, 0])))
pitch = np.degrees(np.arctan2(R[:, 2, 1], R[:, 2, 2]))
roll = np.degrees(np.arctan2(R[:, 1, 0], R[:, 0, 0]))
blink = np.maximum(bs[:, 9], bs[:, 10])
jaw = bs[:, 25]
smile = np.maximum(bs[:, 42], bs[:, 43])

# read crops + blur from the frame-aligned detect.mp4
cap = cv2.VideoCapture(f"{ROOT}/detect.mp4")
crops, blur = [], np.zeros(len(fidx))
for k, f in enumerate(fidx):
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(f))
    ok, img = cap.read()
    x1, y1, x2, y2 = cb[k]
    x1, y1 = max(0, x1), max(0, y1)
    crop = img[y1:y2, x1:x2] if ok else np.zeros((100, 100, 3), np.uint8)
    if crop.size == 0:
        crop = np.zeros((100, 100, 3), np.uint8)
    crops.append(crop)
    blur[k] = cv2.Laplacian(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
blur_t = np.percentile(blur, BLUR_PCT)

# per-criterion fail masks (first-failing reason for the timeline color)
fail = {
    "eyes":  blink >= BLINK_T,
    "pose":  (np.abs(yaw) >= POSE_T) | (np.abs(pitch) >= POSE_T) | (np.abs(roll) >= POSE_T),
    "jaw":   jaw >= JAW_T,
    "blur":  blur < blur_t,
}
passed = ~(fail["eyes"] | fail["pose"] | fail["jaw"] | fail["blur"])
order = ["eyes", "pose", "jaw", "blur"]
reason = np.full(len(fidx), "pass", dtype=object)
for r in order[::-1]:
    reason[fail[r]] = r
reason[passed] = "pass"

print(f"=== portrait gate  clip={CLIP}  n={len(fidx)} ===")
for r in order:
    print(f"  reject[{r:5}] = {int(fail[r].sum()):3}")
print(f"  SURVIVORS    = {int(passed.sum())}")
surv = np.where(passed)[0]
winner = surv[np.argmax(blur[surv])] if len(surv) else -1
if winner >= 0:
    print(f"  PICK (sharpest survivor) = frame {int(fidx[winner])}  "
          f"yaw{yaw[winner]:+.0f} pitch{pitch[winner]:+.0f} roll{roll[winner]:+.0f} "
          f"blink{blink[winner]:.2f} smile{smile[winner]:.2f} blur{blur[winner]:.0f}")

# ---------- visualization ----------
COL = {"pass": (90, 200, 90), "eyes": (200, 130, 60), "pose": (40, 140, 230),
       "jaw": (170, 90, 200), "blur": (130, 130, 130)}
def cell(k, border=None, tag=""):
    c = crops[k]; h, w = c.shape[:2]
    img = cv2.resize(c, (int(150 * w / h), 150))
    label = f"f{int(fidx[k])} {tag}"
    cv2.rectangle(img, (0, 0), (img.shape[1], 16), (0, 0, 0), -1)
    cv2.putText(img, label, (2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    if border:
        img = cv2.copyMakeBorder(img, 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=border)
    return img

def grid(idxs, tags, borders=None, ncol=8):
    borders = borders or [None] * len(idxs)
    cells = [cell(k, b, t) for k, t, b in zip(idxs, tags, borders)]
    H = max(c.shape[0] for c in cells); W = max(c.shape[1] for c in cells)
    cells = [cv2.copyMakeBorder(c, 0, H - c.shape[0], 0, W - c.shape[1], cv2.BORDER_CONSTANT) for c in cells]
    rows = [np.hstack(cells[i:i + ncol] + [np.zeros((H, W, 3), np.uint8)] * (ncol - len(cells[i:i + ncol])))
            for i in range(0, len(cells), ncol)]
    return np.vstack(rows) if rows else np.zeros((H, W * ncol, 3), np.uint8)

def banner(text, w, color=(255, 255, 255), h=26):
    b = np.full((h, w, 3), 25, np.uint8)
    cv2.putText(b, text, (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    return b

# Panel C: gate timeline (one column per frame, colored by reason)
TLH, cw = 40, 2
tl = np.zeros((TLH, len(fidx) * cw, 3), np.uint8)
for k in range(len(fidx)):
    tl[:, k * cw:(k + 1) * cw] = COL[reason[k]][::-1]  # BGR
legend = "  ".join(f"[{r}]" for r in ["pass"] + order)

# Panel A: survivors (sharpest-first), winner green-bordered
surv_sorted = surv[np.argsort(-blur[surv])]
tagsA = [f"b{blur[k]:.0f} y{yaw[k]:+.0f}" for k in surv_sorted]
bordersA = [(80, 230, 80) if k == winner else None for k in surv_sorted]
panelA = grid(surv_sorted[:24], tagsA[:24], bordersA[:24]) if len(surv) else banner("(no survivors)", 800)

# Panel B: rejected samples, a few per reason, labeled with reason
rej_idx, rej_tag, rej_bd = [], [], []
for r in order:
    ks = np.where((reason == r))[0]
    pick = ks[np.linspace(0, len(ks) - 1, min(4, len(ks))).astype(int)] if len(ks) else []
    for k in pick:
        rej_idx.append(k); rej_tag.append(r); rej_bd.append(COL[r][::-1])
panelB = grid(rej_idx, rej_tag, rej_bd) if rej_idx else banner("(nothing rejected)", 800)

W = max(tl.shape[1], panelA.shape[1], panelB.shape[1])
def pad(x): return cv2.copyMakeBorder(x, 0, 0, 0, W - x.shape[1], cv2.BORDER_CONSTANT)
out = np.vstack([
    banner(f"C. GATE TIMELINE (left=start)   {legend}", W),
    pad(tl),
    banner(f"A. SURVIVORS  ({len(surv)} of {len(fidx)})  sharpest-first, GREEN=pick", W, (120, 255, 120)),
    pad(panelA),
    banner("B. REJECTED (sampled per reason)  border=reason color", W, (120, 200, 255)),
    pad(panelB),
])
path = f"experiments/portrait_gate_{CLIP}.png"
cv2.imwrite(path, out)
print(f"  viz -> {path}  ({out.shape[1]}x{out.shape[0]})")

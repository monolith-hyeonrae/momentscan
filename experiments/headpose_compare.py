"""throwaway: compare 6DRepNet (full-range head pose, profile-capable) vs
MediaPipe (frontal-only, no output on strong profiles) — to decide whether a
full-range pose estimator lets SIDE faces be queried as portraits.

(1) agreement on frames MediaPipe covers (validation), (2) coverage on the
MediaPipe GAP (tubelet frame but no landmark = strong profile / occlusion),
(3) a montage of gap/profile frames labelled with 6DRepNet yaw to eyeball.
"""
from __future__ import annotations
import sys
import numpy as np, polars as pl, cv2, onnxruntime as ort
from momentscan import signals

ONNX = "/home/hyeonrae/.portrait981/models/6drepnet/sixdrepnet.onnx"
ROOT = "/home/hyeonrae/repo/monolith/momentscan"
MEAN = np.array([0.485, 0.456, 0.406], np.float32); STD = np.array([0.229, 0.224, 0.225], np.float32)
sess = ort.InferenceSession(ONNX, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])


def euler_deg(R):
    sy = np.hypot(R[0, 0], R[1, 0])
    return (float(np.degrees(np.arctan2(R[2, 1], R[2, 2]))),       # pitch
            float(np.degrees(np.arctan2(-R[2, 0], sy))),           # yaw
            float(np.degrees(np.arctan2(R[1, 0], R[0, 0]))))       # roll


def sixd(crop):
    x = cv2.resize(crop[:, :, ::-1], (224, 224)).astype(np.float32) / 255.0
    x = ((x - MEAN) / STD).transpose(2, 0, 1)[None]
    R = sess.run(None, {"input": x})[0][0]
    return euler_deg(R)


def run(clip, sid, vid):
    tub = pl.read_parquet(f"{ROOT}/output/l2/{clip}/tubelets.parquet").filter(pl.col("track_id") == sid).sort("frame_idx")
    fx = tub["frame_idx"].to_numpy(); bbox = np.array(tub["bbox"].to_list(), float)
    lm = pl.read_parquet(f"{ROOT}/output/l2/{clip}/landmarks.parquet").filter(pl.col("track_id") == sid)
    mp = {r["frame_idx"]: signals.euler_from_transform(np.array(r["transform"]))[0]
          for r in lm.iter_rows(named=True) if r["transform"] is not None}   # MediaPipe yaw
    cap = cv2.VideoCapture(vid)
    rows = []
    for k, f in enumerate(fx):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(f)); ok, img = cap.read()
        if not ok: continue
        x1, y1, x2, y2 = bbox[k].astype(int); m = int(0.15 * (y2 - y1))
        cr = img[max(0, y1 - m):y2 + m, max(0, x1 - m):x2 + m]
        if cr.size == 0: continue
        _, yaw6, _ = sixd(cr)
        rows.append((int(f), yaw6, mp.get(int(f), None), cr))
    cap.release()
    return rows


clip = sys.argv[1] if len(sys.argv) > 1 else "dual_2"
sid = int(sys.argv[2]) if len(sys.argv) > 2 else 1
vid = f"{ROOT}/output/l2/{clip}/inspect/clean_h264.mp4"
rows = run(clip, sid, vid)

both = [(r[1], r[2]) for r in rows if r[2] is not None]
gap = [r for r in rows if r[2] is None]
y6 = np.array([b[0] for b in both]); ymp = np.array([b[1] for b in both])
print(f"=== {clip} s{sid}: n={len(rows)}  MediaPipe-covered={len(both)}  gap={len(gap)} ===")
if len(both) > 5:
    print(f"  agreement (MediaPipe-covered frames): corr(6d_yaw, mp_yaw)={np.corrcoef(y6, ymp)[0,1]:+.3f}  mean|diff|={np.mean(np.abs(y6-ymp)):.1f}°")
if gap:
    g6 = np.array([r[1] for r in gap])
    print(f"  GAP frames 6d_yaw: |yaw| p50={np.percentile(np.abs(g6),50):.0f}° p90={np.percentile(np.abs(g6),90):.0f}°  (측면이면 큼)")

# montage: profile/gap frames with 6d yaw label
prof = sorted([r for r in rows if r[2] is None or abs(r[1]) >= 35], key=lambda r: -abs(r[1]))[:10]
if prof:
    tiles = []
    for f, yaw6, ymp_, cr in prof:
        t = cv2.resize(cr, (150, 150))
        cv2.rectangle(t, (0, 0), (150, 30), (0, 0, 0), -1)
        cv2.putText(t, f"f{f} 6d{yaw6:+.0f}", (3, 13), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1)
        cv2.putText(t, "mp:" + ("—" if ymp_ is None else f"{ymp_:+.0f}"), (3, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                    (120, 120, 255) if ymp_ is None else (120, 255, 120), 1)
        tiles.append(t)
    cv2.imwrite(f"{ROOT}/experiments/headpose_{clip}_s{sid}.png", np.hstack(tiles))
    print(f"  montage -> experiments/headpose_{clip}_s{sid}.png (측면/gap, 6d yaw vs mp)")

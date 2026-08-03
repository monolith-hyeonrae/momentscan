"""tubelet inspect v0 (prototype) — subject-addressable substrate inspector.

The decision-side views (render_select_timeline/portrait_card) already exist but
need features.parquet (the derived 67D stage). This reads the RAW observation
streams that a tubelet actually has — tubelets(spine: bbox·role·depth·ArcFace) +
landmarks(blendshape·pose) + scene(DINO) + detect.mp4 crops — and stacks every
channel frame-aligned under a filmstrip, per subject. Generalizes probe0 +
portrait_gate. Run: python tubelet_inspect.py <clip_id>
"""
from __future__ import annotations
import sys
import numpy as np, polars as pl, cv2

ROOT = "/home/hyeonrae/repo/monolith/momentscan"
CLIP = sys.argv[1] if len(sys.argv) > 1 else "251227002408570"
D = f"{ROOT}/output/l2/{CLIP}"
ROLE_COL = {"main": (90, 200, 90), "auxiliary": (60, 165, 255)}
GATE_COL = {"pass": (90, 200, 90), "eyes": (200, 130, 60), "pose": (40, 140, 230),
            "jaw": (170, 90, 200), "blur": (130, 130, 130)}

tub = pl.read_parquet(f"{D}/tubelets.parquet").sort(["track_id", "frame_idx"])
lm = pl.read_parquet(f"{D}/landmarks.parquet").sort("frame_idx")
lm_bs = {(r["track_id"], r["frame_idx"]): np.array(r["blendshapes"], float)
         for r in lm.iter_rows(named=True) if r["blendshapes"] is not None}
lm_tf = {(r["track_id"], r["frame_idx"]): np.array(r["transform"], float).reshape(4, 4)
         for r in lm.iter_rows(named=True) if r["transform"] is not None}
try:
    sc = pl.read_parquet(f"{D}/scene.parquet").sort("frame_idx")
    has_scene = "customer_embedding" in sc.columns
except Exception:
    has_scene = False
cap = cv2.VideoCapture(f"{D}/detect.mp4")


def euler(M):
    R = M[:3, :3]
    return (np.degrees(np.arctan2(-R[2, 0], np.hypot(R[0, 0], R[1, 0]))),
            np.degrees(np.arctan2(R[2, 1], R[2, 2])),
            np.degrees(np.arctan2(R[1, 0], R[0, 0])))


def n01(x):
    x = np.asarray(x, float); lo, hi = np.nanmin(x), np.nanmax(x)
    return (x - lo) / (hi - lo + 1e-9)


def build_subject(sid: int):
    df = tub.filter(pl.col("track_id") == sid).sort("frame_idx")
    fx = df["frame_idx"].to_numpy()
    bbox = np.array(df["bbox"].to_list(), float)
    role = df["rider_role"][0]
    phase = np.array(df["scene_phase"].to_list())
    emb = np.array(df["embedding"].to_list(), float)
    det = df["det_score"].to_numpy()
    depth = df["depth"].to_numpy() if "depth" in df.columns else np.full(len(fx), np.nan)

    # identity self-relative deviation (ArcFace)
    en = emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9)
    c = en.mean(0); c /= np.linalg.norm(c) + 1e-9
    iddev = 1 - en @ c

    # landmark-derived: pose + expression
    yaw = np.full(len(fx), np.nan); pit = yaw.copy(); rol = yaw.copy()
    blink = yaw.copy(); smile = yaw.copy(); jaw = yaw.copy(); exprm = yaw.copy()
    bs_all = [lm_bs.get((sid, f)) for f in fx]
    bs_med = np.median([b for b in bs_all if b is not None], axis=0)
    for k, f in enumerate(fx):
        b = lm_bs.get((sid, f)); M = lm_tf.get((sid, f))
        if M is not None: yaw[k], pit[k], rol[k] = euler(M)
        if b is not None:
            blink[k] = max(b[9], b[10]); smile[k] = max(b[42], b[43])
            jaw[k] = b[25]; exprm[k] = np.linalg.norm(b - bs_med)

    # crops -> filmstrip + lighting/blur
    bright = np.full(len(fx), np.nan); harsh = bright.copy(); blur = bright.copy()
    crops = {}
    for k, f in enumerate(fx):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(f)); ok, img = cap.read()
        if not ok: continue
        x1, y1, x2, y2 = bbox[k].astype(int); x1, y1 = max(0, x1), max(0, y1)
        cr = img[y1:y2, x1:x2]
        if cr.size == 0: continue
        g = cv2.cvtColor(cr, cv2.COLOR_BGR2GRAY).astype(float)
        bright[k] = g.mean()
        harsh[k] = np.median(np.abs(cv2.Laplacian(cv2.GaussianBlur(g, (0, 0), 2), cv2.CV_64F)))
        blur[k] = cv2.Laplacian(g, cv2.CV_64F).var()
        crops[f] = cr

    # gate reason (portrait_gate)
    blur_t = np.nanpercentile(blur, 30)
    reason = np.full(len(fx), "pass", dtype=object)
    for k in range(len(fx)):
        if blur[k] < blur_t: reason[k] = "blur"
        if jaw[k] >= 0.5: reason[k] = "jaw"
        if abs(yaw[k]) >= 20 or abs(pit[k]) >= 20 or abs(rol[k]) >= 20: reason[k] = "pose"
        if blink[k] >= 0.45: reason[k] = "eyes"

    # scene occupancy (optional)
    sc_cust = np.full(len(fx), np.nan); sc_bg = sc_cust.copy()
    if has_scene:
        m = {r["frame_idx"]: r for r in sc.iter_rows(named=True)}
        for k, f in enumerate(fx):
            r = m.get(int(f))
            if r and r.get("customer_embedding") is not None:
                cls = np.array(r["embedding"], float); cu = np.array(r["customer_embedding"], float); bg = np.array(r["bg_embedding"], float)
                sc_cust[k] = cls @ cu / (np.linalg.norm(cls) * np.linalg.norm(cu) + 1e-9)
                sc_bg[k] = cls @ bg / (np.linalg.norm(cls) * np.linalg.norm(bg) + 1e-9)

    return dict(sid=sid, fx=fx, bbox=bbox, role=role, phase=phase, crops=crops,
                lanes_cat=[("GATE", reason)],
                lanes_line=[
                    ("identity", [("self-dev", n01(iddev), (90, 220, 220)), ("det", n01(det), (120, 120, 120))]),
                    ("pose", [("yaw", n01(yaw), (90, 200, 90)), ("pitch", n01(pit), (60, 165, 255)), ("roll", n01(rol), (220, 160, 80))]),
                    ("expression", [("blink", blink, (200, 130, 60)), ("smile", n01(smile), (90, 220, 120)), ("expr|m|", n01(exprm), (180, 120, 220))]),
                    ("lighting", [("bright", n01(bright), (90, 220, 220)), ("harsh", n01(harsh), (80, 140, 230))]),
                ] + ([("scene", [("cos·cust", n01(sc_cust), (90, 200, 90)), ("cos·bg", n01(sc_bg), (120, 120, 120))])] if has_scene else []),
                depth=depth)


def render(s):
    fx = s["fx"]; n = len(fx); fmin, fmax = int(fx.min()), int(fx.max())
    left, right = 132, 14
    plot_w = min(1700, max(640, n * 2)); W = left + plot_w + right
    def xo(f): return left + int((f - fmin) / max(1, fmax - fmin) * (plot_w - 1))

    TS, TH = 84, 26          # filmstrip tile width-ish, header
    CAT_H, LINE_H, PAD = 22, 48, 6
    film_h = TS
    body_h = TH + film_h + PAD + len(s["lanes_cat"]) * (CAT_H + PAD) + len(s["lanes_line"]) * (LINE_H + PAD) + 24
    img = np.full((body_h, W, 3), 22, np.uint8)

    def text(t, x, y, sc=0.42, col=(220, 220, 220), th=1):
        cv2.putText(img, t, (x, y), cv2.FONT_HERSHEY_SIMPLEX, sc, col, th, cv2.LINE_AA)

    # header
    rc = ROLE_COL.get(s["role"], (160, 160, 160))
    text(f"{CLIP}  subject {s['sid']} [{s['role']}]  n={n}  frames {fmin}-{fmax}", 6, 17, 0.5, rc, 1)
    ph, cnt = np.unique(s["phase"], return_counts=True)
    text("phase: " + " ".join(f"{p}={c}" for p, c in zip(ph, cnt)), 6, 17, 0.42, (150, 150, 150)) if False else None
    y = TH

    # filmstrip — K tiles at their x positions
    K = min(18, n); idxs = np.linspace(0, n - 1, K).astype(int)
    for j in idxs:
        f = int(fx[j]); cr = s["crops"].get(f)
        x = min(xo(f), W - TS - 2)
        if cr is not None:
            h, w = cr.shape[:2]; t = cv2.resize(cr, (TS, int(TS * h / w)))[:film_h]
            t = t[:film_h] if t.shape[0] >= film_h else cv2.copyMakeBorder(t, 0, film_h - t.shape[0], 0, 0, cv2.BORDER_CONSTANT)
            img[y:y + film_h, x:x + TS] = t
            cv2.rectangle(img, (x, y), (x + TS, y + film_h), (60, 60, 60), 1)
            text(f"{f}", x + 2, y + 10, 0.34, (180, 255, 180))
    y += film_h + PAD

    # categorical lanes (gate)
    for name, reason in s["lanes_cat"]:
        text(name, 6, y + 15, 0.44, (220, 220, 220))
        for k in range(n):
            x = xo(int(fx[k])); col = GATE_COL.get(reason[k], (80, 80, 80))[::-1]
            cv2.rectangle(img, (x, y), (x + max(1, plot_w // n), y + CAT_H), col, -1)
        # legend
        lx = left + plot_w - 250
        for r, c in GATE_COL.items():
            cv2.rectangle(img, (lx, y + 4), (lx + 8, y + 12), c[::-1], -1); text(r, lx + 10, y + 12, 0.32, (200, 200, 200)); lx += 48
        y += CAT_H + PAD

    # line lanes
    for name, series in s["lanes_line"]:
        cv2.rectangle(img, (left, y), (left + plot_w, y + LINE_H), (30, 30, 30), -1)
        text(name, 6, y + 16, 0.44, (220, 220, 220))
        lx = 6
        for lab, sig, col in series:
            text(lab, lx, y + 34, 0.32, col[::-1]); lx += max(46, len(lab) * 7)
            pts = [(xo(int(fx[k])), y + LINE_H - 3 - int(np.clip(np.nan_to_num(sig[k]), 0, 1) * (LINE_H - 6)))
                   for k in range(n) if np.isfinite(sig[k])]
            for a, b in zip(pts, pts[1:]):
                cv2.line(img, a, b, col[::-1], 1, cv2.LINE_AA)
        y += LINE_H + PAD

    out = f"{ROOT}/experiments/tubelet_inspect_{CLIP}_s{s['sid']}.png"
    cv2.imwrite(out, img)
    return out


sids = tub.group_by("track_id").len().filter(pl.col("len") >= 30)["track_id"].to_list()
print(f"clip {CLIP}: subjects {sids}")
for sid in sids:
    s = build_subject(sid)
    print("  rendered", render(s), f"(role={s['role']})")

"""Sapiens2 외부-자 프로브 (2026-07-24) — 3단: prep(프로젝트 venv) → infer(전용 venv) → analyze(프로젝트 venv).

용법:  .venv/bin/python scratchpad_sapiens_probe.py prep
       <sapiens-venv>/bin/python scratchpad_sapiens_probe.py infer   # torch+transformers>=5.14+torchvision(cu130)
       .venv/bin/python scratchpad_sapiens_probe.py analyze
작업 디렉토리에 sap_in/(캔버스 PNG)·sap_meta.npz·sap_out/(맵 npy) 생성.
전용 venv 레시피: uv venv v && uv pip install --python v/bin/python torch torchvision \
  --index-url https://download.pytorch.org/whl/cu130 --extra-index-url https://pypi.org/simple \
  && uv pip install --python v/bin/python transformers pillow safetensors accelerate huggingface_hub
판정(원장 ⑪-e 2026-07-24): pointmap 5/5 주/보조 전후 정답 · el 중재=DPR 고평가 적발(mesh 편)
· 정면 3자 합의 7~19° · 역광=전원 약피팅(level floor 독트린 재확인).
"""
import sys
from pathlib import Path

MODE = sys.argv[1] if len(sys.argv) > 1 else "analyze"

if MODE == "prep":
    from pathlib import Path
    import numpy as np
    import cv2
    import polars as pl
    
    sys.path.insert(0, "/home/hyeonrae/repo/p981/momentscan")
    import scratchpad_workbench as wb  # noqa: E402
    from momentscan.surface.recipe_preview import _canonical_faces  # noqa: E402
    
    OUT = Path("/home/hyeonrae/repo/p981/momentscan/output/l2")
    SCR = Path.cwd()
    IN = SCR / "sap_in"
    IN.mkdir(exist_ok=True)
    TW, TH = 768, 1024
    
    faces = np.array(_canonical_faces(), int)
    adj = {}
    for tri in faces:
        for a in tri:
            adj.setdefault(int(a), set()).update(int(b) for b in tri if b != a)
    skin = set(wb.SKIN_ANCHORS)
    for a in list(skin):
        skin |= adj.get(a, set())
    SKIN_IDX = np.array(sorted(i for i in skin if i < 468), int)
    
    
    def vertex_normals(v):
        n = np.zeros_like(v)
        t0, t1, t2 = v[faces[:, 0]], v[faces[:, 1]], v[faces[:, 2]]
        fn = np.cross(t1 - t0, t2 - t0)
        for k in range(3):
            np.add.at(n, faces[:, k], fn)
        n /= (np.linalg.norm(n, axis=1, keepdims=True) + 1e-9)
        if np.nanmean(n[:, 2]) < 0:
            n = -n
        return n
    
    
    def letterbox(img, box):
        x1, y1, x2, y2 = (int(v) for v in box)
        x1, y1 = max(0, x1), max(0, y1)
        crop = img[y1:y2, x1:x2]
        ch_, cw_ = crop.shape[:2]
        sc = min(TW / cw_, TH / ch_)
        rw, rh = int(cw_ * sc), int(ch_ * sc)
        canvas = np.full((TH, TW, 3), 128, np.uint8)
        ox, oy = (TW - rw) // 2, (TH - rh) // 2
        canvas[oy:oy + rh, ox:ox + rw] = cv2.resize(crop, (rw, rh))
        return canvas, np.array([x1, y1, sc, ox, oy], float)
    
    
    TARGETS = {"international_1": [30, 52, 269, 657],
               "test_4": [532, 408, 379, 87, 118, 178, 658],
               "test_0": [377, 429]}
    meta = {"skin_idx": SKIN_IDX}
    for clip, fl in TARGETS.items():
        t = wb.frame_table(clip, OUT)
        row_of = {int(f): i for i, f in enumerate(t["fx"])}
        cap = cv2.VideoCapture(str(OUT / clip / "detect.mp4"))
        for f in fl:
            i = row_of.get(f)
            cap.set(cv2.CAP_PROP_POS_FRAMES, f)
            ok, frm = cap.read()
            if i is None or not ok:
                continue
            H0, W0 = frm.shape[:2]
            cbv = t["cb"][i]
            x1, y1, x2, y2 = cbv
            cx, cy, s = (x1 + x2) / 2, (y1 + y2) / 2, max(x2 - x1, y2 - y1)
            canvas, m5 = letterbox(frm, (cx - 1.2 * s, cy - 0.9 * s, cx + 1.2 * s, cy + 1.9 * s))
            key = f"n_{clip}_{f}"
            cv2.imwrite(str(IN / f"{key}.png"), canvas)
            P = t["P"][i]
            cw, ch = cbv[2] - cbv[0], cbv[3] - cbv[1]
            xy = np.stack([cbv[0] + P[:, 0] * cw, cbv[1] + P[:, 1] * ch], 1)
            I = np.full((len(SKIN_IDX), 3), np.nan)
            for k2, j in enumerate(SKIN_IDX):
                x, y = int(round(xy[j, 0])), int(round(xy[j, 1]))
                if 2 <= x < W0 - 2 and 2 <= y < H0 - 2:
                    I[k2] = frm[y - 2:y + 3, x - 2:x + 3].reshape(-1, 3).mean(0)[::-1]  # RGB
            v3 = np.stack([P[:468, 0] * cw, P[:468, 1] * ch, P[:468, 2] * cw], 1) * np.array([1., -1., -1.])
            sh = t["SH"][i]
            Ld = (np.array([sh[3], sh[2], -sh[1]]) if np.isfinite(sh).all() else np.full(3, np.nan))
            meta[key] = dict(m5=m5, xy=xy, I=I, Nm=vertex_normals(v3)[SKIN_IDX],
                             R3=t["R3"][i], Ldpr=Ld / (np.linalg.norm(Ld) + 1e-9))
        cap.release()
        print(clip, "준비 완료")
    
    det = pl.read_parquet(OUT / "dual_2/detections.parquet")
    cap = cv2.VideoCapture(str(OUT / "dual_2/detect.mp4"))
    for f in (0, 254, 505, 753, 1003):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, frm = cap.read()
        if not ok:
            continue
        H0, W0 = frm.shape[:2]
        canvas, m5 = letterbox(frm, (0, 0, W0, H0))
        key = f"p_dual_2_{f}"
        cv2.imwrite(str(IN / f"{key}.png"), canvas)
        sub = det.filter((pl.col("frame_idx") == f) & (pl.col("track_id").is_in([0, 1])))
        bb = {str(r["track_id"]): r["bbox"] for r in sub.to_dicts()}
        meta[key] = dict(m5=m5, bb0=np.array(bb.get("0", [np.nan] * 4)), bb1=np.array(bb.get("1", [np.nan] * 4)))
    cap.release()
    np.savez(SCR / "sap_meta.npz", **{f"{k}__{k2}": v for k, d in meta.items() if isinstance(d, dict) for k2, v in d.items()},
             skin_idx=SKIN_IDX)
    print("meta 저장:", len(meta) - 1, "프레임")

elif MODE == "infer":
    import numpy as np
    from PIL import Image
    import torch
    import transformers
    from transformers import AutoConfig, AutoImageProcessor
    
    SCR = Path.cwd()
    IN, OUTD = SCR / "sap_in", SCR / "sap_out"
    OUTD.mkdir(exist_ok=True)
    
    
    def load(repo):
        cfg = AutoConfig.from_pretrained(repo)
        cls = getattr(transformers, cfg.architectures[0])
        print(repo, "→", cfg.architectures[0])
        return (cls.from_pretrained(repo, dtype=torch.bfloat16).cuda().eval(),
                AutoImageProcessor.from_pretrained(repo))
    
    
    def run(model, proc, png):
        rgb = np.array(Image.open(png).convert("RGB"))
        inp = proc(images=rgb, do_resize=False, do_pad=False, return_tensors="pt")
        with torch.no_grad():
            out = model(pixel_values=inp["pixel_values"].to("cuda", torch.bfloat16))
        for k in out.keys():
            v = out[k]
            if torch.is_tensor(v) and v.dim() == 4 and v.shape[1] == 3:
                return v[0].float().cpu().numpy(), k
        raise RuntimeError(f"3ch 맵 없음: {[(k, tuple(out[k].shape)) for k in out.keys() if torch.is_tensor(out[k])]}")
    
    
    npngs = sorted(IN.glob("n_*.png"))
    model, proc = load("facebook/sapiens2-normal-0.4b")
    for p in npngs:
        m, key = run(model, proc, p)
        np.save(OUTD / (p.stem + ".npy"), m.astype(np.float16))
    print("normal 완료:", len(npngs), "· 출력 키:", key, "· 맵 shape:", m.shape)
    del model
    torch.cuda.empty_cache()
    
    ppngs = sorted(IN.glob("p_*.png"))
    model, proc = load("facebook/sapiens2-pointmap-0.4b")
    for p in ppngs:
        m, key = run(model, proc, p)
        np.save(OUTD / (p.stem + ".npy"), m.astype(np.float32))
    print("pointmap 완료:", len(ppngs), "· 출력 키:", key, "· 맵 shape:", m.shape,
          "· Z 범위:", np.percentile(m[2], [5, 50, 95]).round(2))

elif MODE == "analyze":
    import numpy as np
    
    SCR = Path.cwd()
    Z = np.load(SCR / "sap_meta.npz")
    SKIN_IDX = Z["skin_idx"]
    keys = sorted({k.rsplit("__", 1)[0] for k in Z.files if "__" in k})
    meta = {k: {k2.rsplit("__", 1)[1]: Z[k2] for k2 in Z.files if k2.startswith(k + "__")} for k in keys}
    
    
    def fit_light(I, N):
        keep = np.isfinite(I).all(axis=1)
        A_full = np.concatenate([np.ones((len(I), 1)), N], axis=1)
        th = None
        for _ in range(3):
            A, y = A_full[keep], I[keep]
            if len(y) < 12:
                return None
            th, *_ = np.linalg.lstsq(A, y, rcond=None)
            r = np.abs(A_full @ th - I).mean(axis=1)
            m_gray = th[1:, :].mean(axis=1)
            lit = (N @ (m_gray / (np.linalg.norm(m_gray) + 1e-9))) > -0.05
            cut = np.percentile(r[keep], 75)
            keep = keep & (r <= cut) & lit & np.isfinite(I).all(axis=1)
        a, m = th[0], th[1:].T
        mg = m.mean(axis=0)
        return a, m, mg / (np.linalg.norm(mg) + 1e-9), float(np.linalg.norm(mg) / max(a.mean(), 1e-3))
    
    
    def sample_map(mp, m5, xy, idxs):
        bx, by, sc, ox, oy = m5
        _, mh, mw = mp.shape
        out = np.zeros((len(idxs), mp.shape[0]))
        for k, j in enumerate(idxs):
            u = int(np.clip(round((ox + (xy[j, 0] - bx) * sc) * mw / 768), 0, mw - 1))
            v = int(np.clip(round((oy + (xy[j, 1] - by) * sc) * mh / 1024), 0, mh - 1))
            out[k] = mp[:, v, u]
        return out
    
    
    # 관례 교정 — 전역: 프레임별 스킨 평균 법선이 "얼굴 정면축의 카메라 표현" R3[:,2]와
    # 최대 정합하는 (fx,fy,fz) 부호 선택 (정면 한 프레임의 뺨 마진 0.02짜리 교정은 불량)
    cands = []
    for fx in (1, -1):
        for fy in (1, -1):
            for fz in (1, -1):
                cands.append(np.array([fx, fy, fz], float))
    scores = np.zeros(len(cands))
    for k in keys:
        if not k.startswith("n_"):
            continue
        d = meta[k]
        nm = np.load(SCR / f"sap_out/{k}.npy").astype(np.float32)
        mn = sample_map(nm, d["m5"], d["xy"], SKIN_IDX).mean(axis=0)
        mn /= (np.linalg.norm(mn) + 1e-9)
        pred = d["R3"][:, 2]
        for ci, c in enumerate(cands):
            scores[ci] += float((mn * c) @ pred)
    FLIP = cands[int(np.argmax(scores))]
    print(f"관례 교정(전역, {sum(1 for k in keys if k.startswith('n_'))}프레임): flip={FLIP}, 정합점수={scores.max():.2f} (차점 {sorted(scores)[-2]:.2f})")
    
    ang = lambda a, b: float(np.degrees(np.arccos(np.clip(a @ b, -1, 1))))
    azel = lambda R, l: (float(np.degrees(np.arctan2((R.T @ l)[0], (R.T @ l)[2]))),
                         float(np.degrees(np.arcsin(np.clip((R.T @ l)[1], -1, 1)))))
    print(f"\n{'frame':>22} | {'az sap/mesh/dpr':>18} | {'el sap/mesh/dpr':>16} | sap↔dpr sap↔mesh mesh↔dpr | ratio s/m")
    for k in keys:
        if not k.startswith("n_"):
            continue
        d = meta[k]
        nm = np.load(SCR / f"sap_out/{k}.npy").astype(np.float32)
        Ns = sample_map(nm, d["m5"], d["xy"], SKIN_IDX) * FLIP
        Ns /= (np.linalg.norm(Ns, axis=1, keepdims=True) + 1e-9)
        fs = fit_light(d["I"], Ns)
        fm = fit_light(d["I"], d["Nm"])
        if fs is None or fm is None:
            continue
        _, _, ls, rs = fs
        _, _, lm_, rm = fm
        R, Ld = d["R3"], d["Ldpr"]
        az_s, el_s = azel(R, ls)
        az_m, el_m = azel(R, lm_)
        dd = np.isfinite(Ld).all()
        az_d, el_d = azel(R, Ld) if dd else (np.nan, np.nan)
        print(f"{k[2:]:>22} | {az_s:>6.0f} {az_m:>5.0f} {az_d:>5.0f} | {el_s:>5.0f} {el_m:>5.0f} {el_d:>4.0f} |"
              f" {ang(ls, Ld) if dd else np.nan:>7.1f} {ang(ls, lm_):>8.1f} {ang(lm_, Ld) if dd else np.nan:>8.1f} | {rs:>4.2f} {rm:>4.2f}")
    
    print("\n--- pointmap 전후 판별 (dual_2: t1=main=하단 큰 박스) ---")
    for k in keys:
        if not k.startswith("p_"):
            continue
        d = meta[k]
        pm = np.load(SCR / f"sap_out/{k}.npy")
        bx, by, sc, ox, oy = d["m5"]
        _, mh, mw = pm.shape
        zs = {}
        for tid, bb in (("t0", d["bb0"]), ("t1", d["bb1"])):
            if not np.isfinite(bb).all():
                continue
            x1, y1, x2, y2 = bb
            cx1, cy1 = x1 + (x2 - x1) * .25, y1 + (y2 - y1) * .25
            cx2, cy2 = x2 - (x2 - x1) * .25, y2 - (y2 - y1) * .25
            u1 = int((ox + (cx1 - bx) * sc) * mw / 768); u2 = int((ox + (cx2 - bx) * sc) * mw / 768)
            v1 = int((oy + (cy1 - by) * sc) * mh / 1024); v2 = int((oy + (cy2 - by) * sc) * mh / 1024)
            zs[tid] = float(np.median(pm[2, v1:v2, u1:u2]))
        if len(zs) == 2:
            front = min(zs, key=zs.get)
            print(f"{k[2:]:>12}: Z t0={zs['t0']:.3f} t1={zs['t1']:.3f} → 앞={front} {'✓(main 앞)' if front == 't1' else '⚠(main이 뒤?)'}")

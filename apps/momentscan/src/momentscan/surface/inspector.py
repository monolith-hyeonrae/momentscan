"""Inspector — the coherent ONE-RUN window (interactive clip.html).

Split from viz.py (2026-07-02): assembles the persisted observability payloads
(gate_trace · emotion_frame · candidates · portrait.json · landmarks) into the
`const DATA` the _inspector_html.py frontend renders. Pure reader — any value it
shows exists on disk first (freshness flags stale runs).
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import cv2
import polars as pl

from momentscan import gates
from momentscan.domains import geometry, pose, signals
from momentscan.surface._inspector_html import _TUBELET_INSPECT_HTML
from momentscan.stash import (
    read_candidates, read_detections, read_gate_trace, read_headpose,
    read_landmarks, read_parse, read_portrait, read_stitch, read_tubelets,
)

log = logging.getLogger("momentscan.surface.inspector")

_MESH_TOPO = None


# the nose-bridge ridge (nasion→tip centre line). In a bare 2D wireframe this reads
# as a harsh stripe down the nose (MediaPipe's demo shows it as a 3D surface ridge,
# not a line) — so it is split OUT of the solid outline and drawn as a soft dashed
# ridge, while the lower-nose outline (tip / alae / base) stays a solid contour.
# nostril/ala BOTTOM only — the underside curve of the nose: ala (98/327) → nostril
# sill (97/326) → subnasale (2). Bridge side lines + angular wings dropped per
# request; the nose = this base curve + the dashed centre ridge, nothing else.
_NOSE_OUTLINE = [(98, 97), (97, 2), (2, 326), (326, 327)]
# the centre ridge (nasion→tip) — a soft dashed hint, not a hard stripe.
_NOSE_RIDGE = [(168, 6), (6, 197), (197, 195), (195, 5), (5, 4), (4, 1)]
# the lower-nose (연삼각) region — ONE polygon around the base boundary: tip(1) →
# ala R(98) → nostril sill R(97) → subnasale(2) → nostril sill L(326) → ala L(327).
# Drawn as a single translucent FILL.
_NOSE_REGION = [[1, 98, 97, 2, 326, 327]]


def _mesh_topology():
    """Face wireframe topology for the interactive overlay → (pts, face_edges,
    nose_edges, ridge_edges): face = MediaPipe feature contours (oval / eyes / brows
    / lips); nose = the representative nose outline (drawn THICKER); ridge = the soft
    dashed nose centre line. Remapped to a compact shared point set. Cached;
    (None,)*4 if mediapipe is unavailable (mesh viz degrades)."""
    global _MESH_TOPO
    if _MESH_TOPO is None:
        try:
            from mediapipe.tasks.python.vision.face_landmarker import (
                FaceLandmarksConnections as _FLC,
            )
            face = [(c.start, c.end) for c in _FLC.FACE_LANDMARKS_CONTOURS]
            pts = sorted({i for e in face + _NOSE_OUTLINE + _NOSE_RIDGE for i in e})
            remap = {p: k for k, p in enumerate(pts)}
            def rm(es):
                return [[remap[a], remap[b]] for a, b in es]
            region = [[remap[i] for i in poly] for poly in _NOSE_REGION]
            _MESH_TOPO = (pts, rm(face), rm(_NOSE_OUTLINE), rm(_NOSE_RIDGE), region)
        except Exception:
            _MESH_TOPO = (None, None, None, None, None)
    return _MESH_TOPO



def _transcode_h264(src, dst, *, fps=None):
    """detect.mp4 is mpeg4 (browsers can't play it) → H.264 all-intra, browser-
    aligned (zero_pts) + cached. Recipe single home: media.transcode_h264."""
    from momentscan.media import transcode_h264
    return transcode_h264(src, dst, fps=fps, zero_pts=True, cached=True)


def render_tubelet_inspect(out_root: str | Path, clip_id: str, *,
                           fps: int = 6, video_path: str | Path | None = None) -> dict:
    """Interactive per-clip inspector (inspect/clip.html) — the substrate-level
    debugging view. Scrub the video ↔ a synced cursor on the raw observation
    channels, with the value at the cursor as a readout, so signal-vs-face can
    be verified by eye. Subject tabs; stitch verification (fragment lane + seam
    ArcFace cosine — the re-id's own evidence); co-presence; an active-subject
    marker + a fixed-ratio PORTRAIT BOX with a distortion-free crop preview (the
    uniform-container / final-result preview).

    Pure function of the stash. Main scrub video = the original when given
    (pristine; all boxes drawn as toggleable overlays), else detect.mp4 (the
    tracker boxes are burned in — stash-pure fallback). Channels come from the
    raw streams (tubelets · landmarks · scene · video crops), NOT features.parquet,
    so it works before the 67D derived stage exists.
    """
    import json
    import numpy as np

    out_dir = Path(out_root) / clip_id
    # clip_id is an ALREADY-PROCESSED stash dir, not a video path — the inspector
    # is a pure read of the stash. Give a clear error (with what IS available)
    # instead of crashing on mkdir when the clip dir doesn't exist.
    detect_mp4 = out_dir / "detect.mp4"
    if not (out_dir / "tubelets.parquet").exists() or not detect_mp4.exists():
        have = sorted(p.parent.name for p in Path(out_root).glob("*/tubelets.parquet"))
        return {"clip_id": clip_id, "ok": False,
                "reason": f"no processed stash at {out_dir} (need tubelets.parquet + detect.mp4)",
                "available": have}

    inspect = out_dir / "inspect"
    inspect.mkdir(exist_ok=True)

    clean = None
    if video_path and Path(video_path).exists():
        clean = _transcode_h264(video_path, inspect / "clean_h264.mp4", fps=fps)
        main_name = clean.name
    else:
        _transcode_h264(detect_mp4, inspect / "detect_h264.mp4")
        main_name = "detect_h264.mp4"
    crop_src = str(clean) if clean else str(detect_mp4)   # lighting metrics off the cleanest image

    tub = read_tubelets(out_root, clip_id).sort(["track_id", "frame_idx"])
    det = read_detections(out_root, clip_id).sort(["subject_id", "frame_idx"])
    det_emb = np.array(det["embedding"].to_list(), float)
    det_idx = {(r["subject_id"], r["frame_idx"]): i for i, r in enumerate(det.iter_rows(named=True))}
    det_trk = {(r["subject_id"], r["frame_idx"]): r["track_id"] for r in det.iter_rows(named=True)}
    lm = read_landmarks(out_root, clip_id).sort("frame_idx")
    lm_bs = {(r["track_id"], r["frame_idx"]): np.array(r["blendshapes"], float)
             for r in lm.iter_rows(named=True) if r["blendshapes"] is not None}
    lm_tf = {(r["track_id"], r["frame_idx"]): np.array(r["transform"], float).reshape(4, 4)
             for r in lm.iter_rows(named=True) if r["transform"] is not None}
    try:
        scene = read_scene(out_root, clip_id).sort("frame_idx")
        sc_map = {r["frame_idx"]: r for r in scene.iter_rows(named=True)} if "customer_embedding" in scene.columns else {}
    except Exception:
        sc_map = {}
    stitch = read_stitch(out_root, clip_id) or {}
    coh = {s["subject_id"]: s.get("coherence") for s in stitch.get("subjects", [])}

    # occlusion signal (parse — region output-kind) + product picks (selection
    # output-kind): rendered generically by the inspector's kind dispatch (③).
    parse_map = {}
    _pq = read_parse(out_root, clip_id)
    if _pq is not None:
        for r in _pq.iter_rows(named=True):
            parse_map[(r["track_id"], r["frame_idx"])] = (r.get("eyes_vis"), r.get("mouth_vis"), r.get("eye_lum_rel"))
    # full-range pose (6DRepNet) — the profile-capable yaw that fills MediaPipe's
    # NaN gap; shown as its own channel so the profile fill (and the side portrait
    # it enables) is VISIBLE on the timeline, not just asserted in the output strip.
    hp_map = {}
    _hq = read_headpose(out_root, clip_id)
    if _hq is not None:
        for r in _hq.iter_rows(named=True):
            hp_map[(r["track_id"], r["frame_idx"])] = (r["yaw"], r["pitch"], r["roll"])

    def _hp6(sid, f, axis):
        v = hp_map.get((int(sid), int(f)))
        return v[axis] if v is not None else np.nan
    # gate verdict per frame — read from the portrait engine's gate_trace (the REAL
    # decision). The inspector MEASURES (the channels below) but must NOT re-decide:
    # the old inline re-gate here drifted from portrait.py (said "REJECT blur" on a
    # frame portrait served as a side view). Sourcing the verdict from the trace
    # makes the inspector structurally incapable of drifting. Absent → "—".
    gate_map, iddev_map, blink_map, jaw_map, ladder_map = {}, {}, {}, {}, {}
    # the per-frame SUB-GATE booleans — gate_trace already persists every ladder rung
    # (trace_rows), so the GATE band can show WHAT PASSED / WHAT BLOCKED per tier, not
    # just the final routed verdict. T0 id/face · T1 sharp · T3 eyes · T2 admit/quarter/
    # side. No schema change (all present in trace_rows) → no re-run, no staleness.
    # the ladder rungs the GATE band renders, grouped by the three execution STAGES
    # (gates.py VALIDITY_LADDER / POLICY_LADDER / ROUTING_LADDER) so the inspector shows
    # WHICH stage each product consumes: ① VALIDITY (valid) is shared by likeness +
    # highlight + portrait; ② POLICY + ③ ROUTING are portrait-only. `valid` is the shared
    # keystone likeness/highlight read; id_valid/expr_ok make the relative-id + coherent-
    # expression rungs visible. (frontal_pose is intermediate — its effect shows via admit.)
    LADDER_KEYS = ("face_present", "sharp_ok", "exposure_ok", "id_ok", "id_valid", "valid",
                   "have_bs",   # → likeness ACTUAL consumption = valid∩landmarks (not all of valid)
                   "eyes_ok", "expr_ok", "query_ok", "admit", "quarter_ok", "side_ok")
    _gt = read_gate_trace(out_root, clip_id)
    if _gt is not None:
        for r in _gt.iter_rows(named=True):
            _k = (r["track_id"], r["frame_idx"])
            gate_map[_k] = r["reason"]
            # read the persisted SIGNALS too, not just the verdict (gate_trace is
            # full-precision → these are byte-identical channel sources)
            iddev_map[_k] = r["iddev"]; blink_map[_k] = r["blink"]; jaw_map[_k] = r["jaw"]
            row = {kk: r.get(kk) for kk in LADDER_KEYS}
            # frontal = the policy-free clean-frontal cohort — read from the persisted
            # frontal_clean column (single home gates._derive; never re-derived here).
            row["frontal"] = bool(r.get("frontal_clean"))
            ladder_map[_k] = row
    cand_by_sub: dict[int, list] = {}
    for c in read_candidates(out_root, clip_id):
        cand_by_sub.setdefault(c["track_id"], []).append(c)
    # portrait OUTPUTS come from portrait.json (the authoritative deliverable record),
    # NOT candidates: portrait "moved out" of select (select.py), and select truncates
    # candidates.jsonl on each run, so portrait candidates are a racy/wiped source. the
    # json always reflects the PNGs actually extracted from the crop track.
    portrait_riders = (read_portrait(out_root, clip_id) or {}).get("riders", {})
    from momentscan.products.portrait import MIN_ADMIT          # threshold, for the "why empty" readout
    from momentscan.stash import read_appearance
    likeness_riders = (read_appearance(out_root, clip_id) or {}).get("riders", {})   # ③ likeness reading (how identity was read)
    # highlight-lang (optional stage): the generated NL description + its LLM-judge match to the
    # attraction expectation, per analyzed candidate frame. Absent if the stage was not run.
    import json as _json
    from momentscan.stash import clip_dir as _clip_dir
    _hlp = _clip_dir(Path(out_root), clip_id) / "highlight_lang.json"
    hl_lang = _json.loads(_hlp.read_text(encoding="utf-8")) if _hlp.exists() else None
    # the QUERY CRITERION each product was selected AGAINST (what we were looking for) —
    # portrait's authored expression query (gates preset), highlight's attraction expectation.
    from momentscan.gates import PORTRAIT_QUERY as _PQ, QUERY_DIST_MAX as _PTAU
    portrait_qlabel = (f"따뜻한 PFP · 눈뜸(blink≈{_PQ['blink']}) · 미소(smile≈{_PQ['smile']}) · "
                       f"입다뭄(jaw≈{_PQ['jaw']}) · 근접 τ≤{_PTAU}")

    cap = cv2.VideoCapture(crop_src)
    vw, vh = int(cap.get(3)), int(cap.get(4))

    def build(sid):
        df = tub.filter(pl.col("track_id") == sid).sort("frame_idx")
        fx = df["frame_idx"].to_numpy()
        bbox = np.array(df["bbox"].to_list(), float)
        role = df["rider_role"][0]
        emb = np.array(df["embedding"].to_list(), float)
        detsc = df["det_score"].to_numpy().astype(float)
        # iddev: READ the portrait engine's persisted value (gate_trace) instead of
        # re-deriving it — generalizes the gate_trace verdict-read to a SIGNAL-read.
        # Byte-identical (gate_trace stores iddev FULL precision; ch() rounds vals AND
        # auto-ranges lo/hi from the same raw values, so read == recompute). Fallback =
        # recompute for clips where portrait (gate_trace) has not run.
        if iddev_map:
            iddev = np.array([np.nan if (v := iddev_map.get((sid, int(f)))) is None else v for f in fx])
        else:
            iddev = signals.identity_deviation(emb)
        N = len(fx)

        raw = [det_trk.get((sid, int(f)), -1) for f in fx]
        seams = []
        for k in range(1, N):
            if raw[k] != raw[k - 1] and raw[k] >= 0 and raw[k - 1] >= 0:
                ia, ib = det_idx.get((sid, int(fx[k - 1]))), det_idx.get((sid, int(fx[k])))
                cos = None
                if ia is not None and ib is not None:
                    a, b = det_emb[ia], det_emb[ib]
                    cos = round(float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9)), 3)
                seams.append({"frame": int(fx[k]), "cos": cos, "from": int(raw[k - 1]),
                              "to": int(raw[k]), "gap": int(fx[k] - fx[k - 1])})

        yaw = np.full(N, np.nan); pit = yaw.copy(); rol = yaw.copy()
        blink = yaw.copy(); smile = yaw.copy(); jaw = yaw.copy(); exprm = yaw.copy()
        bl = [lm_bs.get((sid, int(f))) for f in fx]
        haveb = [b for b in bl if b is not None]
        bmed = np.median(haveb, axis=0) if haveb else np.zeros(52)
        for k, f in enumerate(fx):
            b = lm_bs.get((sid, int(f))); M = lm_tf.get((sid, int(f)))
            if M is not None:
                yaw[k], pit[k], rol[k] = pose.euler_from_transform(M)
            if b is not None:
                smile[k] = signals.smile(b); exprm[k] = signals.expr_magnitude(b, bmed)
                if not blink_map:
                    blink[k] = signals.blink(b)
                if not jaw_map:
                    jaw[k] = signals.jaw(b)

        # blink/jaw: READ the persisted gate_trace values (full precision) instead of
        # re-deriving — the same gate_trace-signal-read as iddev (fallback handled in-loop).
        if blink_map:
            blink = np.array([np.nan if (v := blink_map.get((sid, int(f)))) is None else v for f in fx])
        if jaw_map:
            jaw = np.array([np.nan if (v := jaw_map.get((sid, int(f)))) is None else v for f in fx])

        bright = np.full(N, np.nan); harsh = bright.copy(); blur = bright.copy()
        for k, f in enumerate(fx):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(f)); ok, img = cap.read()
            if not ok:
                continue
            x1, y1, x2, y2 = bbox[k].astype(int); x1, y1 = max(0, x1), max(0, y1)
            cr = img[y1:y2, x1:x2]
            if cr.size == 0:
                continue
            bright[k], harsh[k] = signals.crop_lighting(cr)
            blur[k] = signals.crop_blur(cr)

        # GATE verdict = the portrait engine's real per-frame reason from gate_trace
        # (admit / quarter / side / reject:identity / reject:occlusion / reject:blur
        # / no_view). NOT recomputed — see gate_map note above. "—" if portrait
        # hasn't run for this clip.
        gate = [gate_map.get((sid, int(f)), "—") for f in fx]
        # per-tier sub-gate pass/fail aligned to fx (None where the trace lacks the
        # frame, or portrait hasn't run) — the GATE band renders this as the ladder.
        gate_ladder = ({kk: [ladder_map.get((sid, int(f)), {}).get(kk) for f in fx]
                        for kk in LADDER_KEYS} if ladder_map else {})
        # per-product GATE OPEN/CLOSED — the intuitive "when does each product collect/serve"
        # summary. The pose gate differs per product: likeness needs the STRICT frontal core,
        # portrait any served VIEW (frontal/quarter/side), highlight only validity. (The TARGET-
        # presence gate — subject detected + tubelet this frame — is the existence precondition;
        # frames with no tubelet are absent from fx, so the HTML draws them CLOSED for everyone.)
        def _lv(f, k):
            return ladder_map.get((sid, int(f)), {}).get(k)
        # highlight's REAL switch = WHEN (action impact/rarity/scene, temporal) → its output is the
        # DELIVERED phrase segments. `valid` is a ~always-true WHICH-eligibility floor, so drawing it
        # as the switch reads inert; the segments (from candidates) ARE the WHEN discriminator.
        hl_segs = []
        for c in cand_by_sub.get(sid, []):
            if c["product"] == "highlight":
                for seg in [c["pick"]] + c.get("alternatives", []):
                    lo = int(seg.get("start_ms", 0) * fps / 1000)
                    hi = int(seg.get("end_ms", 0) * fps / 1000)
                    hl_segs.append({"lo": lo, "hi": hi, "score": round(float(seg.get("score", 0.0)), 2),
                                    "peak": int(seg.get("peak_frame", seg.get("when_frame", lo))),
                                    "resolved": bool(seg.get("resolved", True)),
                                    "driver": seg.get("driver"), "drivers": seg.get("drivers")})
        def _in_hl(f):
            return any(s["lo"] <= f <= s["hi"] for s in hl_segs)
        gate_open = ({
            "likeness":  [bool(_lv(f, "valid") and _lv(f, "frontal")) for f in fx],          # strict frontal core
            "portrait":  [bool(_lv(f, "admit") or _lv(f, "quarter_ok") or _lv(f, "side_ok")) for f in fx],  # any served view
            "highlight": [_in_hl(f) for f in fx],                                            # WHEN: in a delivered segment
        } if ladder_map else {})

        cu = np.full(N, np.nan); bg = cu.copy()
        for k, f in enumerate(fx):
            r = sc_map.get(int(f))
            if r and r.get("customer_embedding") is not None:
                cl = np.array(r["embedding"], float); c1 = np.array(r["customer_embedding"], float); c2 = np.array(r["bg_embedding"], float)
                cu[k] = float(cl @ c1 / (np.linalg.norm(cl) * np.linalg.norm(c1) + 1e-9))
                bg[k] = float(cl @ c2 / (np.linalg.norm(cl) * np.linalg.norm(c2) + 1e-9))

        def ch(name, group, vals, color, lo=None, hi=None):
            v = np.asarray(vals, float); fin = v[np.isfinite(v)]
            lo = (float(fin.min()) if len(fin) else 0.0) if lo is None else lo
            hi = (float(fin.max()) if len(fin) else 1.0) if hi is None else hi
            return {"name": name, "group": group, "color": color, "lo": lo, "hi": hi,
                    "vals": [None if not np.isfinite(x) else round(float(x), 4) for x in v]}

        channels = [
            ch("self_dev", "identity", iddev, [90, 220, 220]), ch("det", "identity", detsc, [150, 150, 150], 0, 1),
            ch("yaw", "pose", yaw, [90, 200, 90], -60, 60), ch("pitch", "pose", pit, [80, 170, 255], -45, 45),
            ch("roll", "pose", rol, [220, 160, 80], -45, 45),
            # 6DRepNet channels (magenta family) — overlay the pose lane: where both
            # backends exist the curve PAIRS should track with the SAME SIGN = the
            # visible proof of the 3-axis adapter alignment (2026-07-02: raw 6D was a
            # full mirror of MP euler; before, only yaw was flipped). Where MediaPipe
            # blanks on a profile, yaw6d continues to ±90 — the evidence behind a
            # side portrait. pit6d/rol6d share pitch/roll's scale for direct overlay.
            ch("yaw6d", "pose", [_hp6(sid, f, 0) for f in fx], [210, 130, 230], -90, 90),
            ch("pit6d", "pose", [_hp6(sid, f, 1) for f in fx], [160, 120, 255], -45, 45),
            ch("rol6d", "pose", [_hp6(sid, f, 2) for f in fx], [255, 120, 180], -45, 45),
            ch("blink", "expression", blink, [255, 140, 70], 0, 1), ch("smile", "expression", smile, [110, 230, 130], 0, 1),
            ch("jaw", "expression", jaw, [200, 130, 90], 0, 1), ch("expr_mag", "expression", exprm, [200, 130, 230]),
            ch("bright", "lighting", bright, [120, 220, 220], 0, 255), ch("harsh", "lighting", harsh, [90, 150, 240]),
            ch("blur", "lighting", blur, [150, 150, 150]),
        ]
        if sc_map:
            channels += [ch("cos_cust", "scene", cu, [110, 200, 110], 0, 1), ch("cos_bg", "scene", bg, [150, 150, 150], 0, 1)]
        if parse_map:
            pcols = np.array([parse_map.get((sid, int(f)), (np.nan, np.nan, np.nan)) for f in fx], float)
            channels += [ch("eyes_vis", "occlusion", pcols[:, 0], [110, 200, 110], 0, 0.05),
                         ch("mouth_vis", "occlusion", pcols[:, 1], [200, 130, 90], 0, 0.1),
                         ch("eye_lum", "occlusion", pcols[:, 2], [120, 180, 240], 0, 1.2)]

        # EMOTION (HSEmotion valence — the REAL directed reading the gates + highlight
        # now use). Shown next to the crude MediaPipe `expression` group so the contrast
        # is visible: smile≈0 on an open-mouth laugh while valence≈+1. The 0 line on the
        # valence lane is the sign boundary (negative below, positive above); the
        # person's baseline p50 is in the readout. Needs features + emotion.json.
        emo_base = {}
        try:
            from momentscan.stash import read_emotion, read_emotion_frame
            # OBSERVABILITY: the per-frame valence is now PERSISTED (emotion_frame.parquet),
            # so the inspector READS it instead of re-deriving — the gate_trace pattern on a
            # live channel. Byte-identical: the persisted floats are full-precision and ch()
            # rounds to 4dp at read-side (same place, same inputs → same bytes). baseline
            # still from emotion.json. Fallback = recompute for clips predating the trace.
            _emj = read_emotion(out_root, clip_id) or {}
            emo_base = (_emj.get("riders", {}).get(str(int(sid)), {}) or {}).get("baseline", {})
            ef = read_emotion_frame(out_root, clip_id)
            if ef is not None:
                ev, ec, ea = {}, {}, {}
                for _r in ef.iter_rows(named=True):
                    if _r["track_id"] == int(sid):
                        _f = int(_r["frame_idx"])
                        ev[_f] = _r["valence"]; ec[_f] = _r["em_conf"]; ea[_f] = _r["arousal"]
            else:
                from momentscan.domains.emotion import reading as _emo_reading
                efx, er, emo_base = _emo_reading(out_root, clip_id, int(sid))
                ev = {int(f): er["valence_signed"][i] for i, f in enumerate(efx)}
                ec = {int(f): er["em_conf"][i] for i, f in enumerate(efx)}
                ea = {int(f): er["arousal"][i] for i, f in enumerate(efx)}
            channels += [
                ch("valence", "emotion", [ev.get(int(f), np.nan) for f in fx], [90, 230, 130], -1, 1),
                ch("em_conf", "emotion", [ec.get(int(f), np.nan) for f in fx], [230, 200, 110], 0, 1),
                ch("arousal", "emotion", [ea.get(int(f), np.nan) for f in fx], [200, 130, 230], 0, 1)]
        except Exception:
            emo_base = {}

        # product picks (selection) + extracted portrait OUTPUTS (the deliverables)
        picks = {"portrait": [], "highlight": []}
        outputs = []
        setviews = {}                  # frame_idx → diversity-set view (frontal/left/right/side)
        # portrait deliverables: read from portrait.json (authoritative, race-immune).
        prj = portrait_riders.get(str(sid))
        if prj:
            rep = prj.get("rep") or {}
            if rep.get("frame_idx") is not None and prj.get("rep_file"):
                picks["portrait"] = [int(rep["frame_idx"])]
                outputs.append({"file": f"../portraits/{prj['rep_file']}", "label": "rep",
                                "frame": int(rep["frame_idx"])})
            sset = prj.get("set")
            if sset:                                   # current json: per-view frames present
                for m in sset:
                    if not m.get("file"):
                        continue
                    setviews[int(m["frame_idx"])] = m["view"]
                    outputs.append({"file": f"../portraits/{m['file']}", "label": m["view"],
                                    "frame": int(m["frame_idx"])})
            else:                                      # legacy json (pre-`set`): thumbnails only
                for view in prj.get("views", []):
                    fname = f"s{sid}_set_{view}.png"
                    if fname in prj.get("extracted", []):
                        outputs.append({"file": f"../portraits/{fname}", "label": view})
        # SEGS lane + readout consume the same hl_segs (WHEN output). [lo, hi] draw the bar;
        # [score, peak, resolved] let the readout surface WHEN (why this window fired).
        picks["highlight"] = [[s["lo"], s["hi"], s["score"], s["peak"], s["resolved"]] for s in hl_segs]

        # landmark wireframe — OBSERVED (full-frame px, for the video overlay = per-frame
        # fit) + CANONICAL (pose-removed, via geometry.canonicalize = the DECLARED frame,
        # single home). Points from landmarks.parquet; downsampled (≤~180 frames) to bound
        # the embedded HTML. canonical pre-scaled to the 170×210 mini-canvas (y flipped for
        # screen: CANONICAL_FRAME is +y up).
        mesh = None
        mpts, *_ = _mesh_topology()
        lm_sub = lm.filter(pl.col("track_id") == sid).sort("frame_idx") if mpts else None
        if mpts and lm_sub is not None and len(lm_sub) >= 10:
            mfx = lm_sub["frame_idx"].to_numpy()
            Pm = np.array(lm_sub["landmarks"].to_list(), float).reshape(len(mfx), 478, 3)
            Tm = np.array(lm_sub["transform"].to_list(), float).reshape(len(mfx), 4, 4)
            cbm = np.array(lm_sub["crop_box"].to_list(), float)
            canon_m, _ = geometry.canonicalize(Pm, Tm, cbm)
            cwm, chm = cbm[:, 2] - cbm[:, 0], cbm[:, 3] - cbm[:, 1]
            stride = max(1, len(mfx) // 180)
            mf, obs, can = [], [], []
            for i in range(0, len(mfx), stride):
                ox = (cbm[i, 0] + Pm[i, mpts, 0] * cwm[i]).round().astype(int)
                oy = (cbm[i, 1] + Pm[i, mpts, 1] * chm[i]).round().astype(int)
                sx = (canon_m[i, mpts, 0] * 45 + 85).round().astype(int)
                sy = (-canon_m[i, mpts, 1] * 45 + 105).round().astype(int)
                obs.append([int(v) for p in zip(ox, oy) for v in p])
                can.append([int(v) for p in zip(sx, sy) for v in p])
                mf.append(int(mfx[i]))
            mesh = {"f": mf, "obs": obs, "canon": can}

        # ── ③ SELECT reasoning — HOW each product's pick won (the ranking, not just where) ──
        # likeness = the identity READING (cohort size, reliability, what varies); portrait =
        # the rep's objective breakdown (front·sharp·warm=query proximity); highlight = each
        # segment's WHEN driver (impact/rarity/scene/valence — what carried the moment).
        lk = likeness_riders.get(str(sid)) or {}
        _ax = ((lk.get("axes") or [{}])[0].get("top_corr")) or {}
        _top = max(_ax.items(), key=lambda kv: abs(kv[1]))[0] if _ax else None
        sel = {
            "likeness": ({"n_obs": lk.get("n_obs"), "drift": lk.get("split_half_drift"),
                          "resid_rms": lk.get("resid_rms"), "evr1": (lk.get("evr_top5") or [None])[0],
                          "top_axis": ([_top, round(_ax[_top], 2)] if _top else None),
                          "face_id": lk.get("face_id") is not None} if lk else None),
            "portrait": ({"rep": (prj or {}).get("rep"), "n_admit": (prj or {}).get("n_admit"),
                          "n_total": (prj or {}).get("n_total"), "n_side": (prj or {}).get("n_side")}
                         if prj else None),
            "highlight": hl_segs,
        }
        # generated NL description + LLM-judge match per analyzed candidate frame (optional stage)
        _hll = hl_lang or {}
        _lf = ({int(c["frame"]): {"lang": c.get("lang_score"), "desc": c.get("description"),
                                  "scene": c.get("scene")}
                for c in _hll.get("candidates", [])} if _hll.get("track_id") == int(sid) else {})
        if _lf:
            sel["lang"] = {"expectation": _hll.get("expectation"), "by_frame": _lf}
        # the query CRITERION per product — what each was selected against (shown in the readout).
        sel["query"] = {"portrait": portrait_qlabel, "highlight": _hll.get("expectation_text")}
        # highlight's per-frame WHEN receptive field width (the rarity state-window; the moving
        # attention span that exists at EVERY ride frame, ≠ the intermittent delivered segment).
        from momentscan.products.select import RARITY_WIN_S as _RFW
        sel["rf_win_s"] = _RFW
        return {"sid": int(sid), "role": role, "coherence": coh.get(int(sid)),
                "frames": [int(f) for f in fx],
                "bbox": [[round(float(x), 1) for x in b] for b in bbox],
                "gate": gate, "gate_ladder": gate_ladder, "gate_open": gate_open, "mesh": mesh,
                "channels": channels, "raw": [int(t) for t in raw],
                "seams": seams, "picks": picks, "portraits": outputs, "select": sel,
                "setviews": {str(k): v for k, v in setviews.items()},
                # why a deliverable is empty: the portrait stage already recorded
                # crop_track/parse/n_admit in portrait.json — surface it (the inspector
                # explains 0 portraits instead of a generic "run portrait").
                "portrait_meta": ({"crop_track": prj.get("crop_track"), "parse": prj.get("parse"),
                                   "headpose": prj.get("headpose"), "n_admit": prj.get("n_admit"),
                                   "n_total": prj.get("n_total"), "min_admit": MIN_ADMIT,
                                   "rep_ok": bool(prj.get("rep_file"))} if prj else None),
                "emo_base": {k: emo_base.get(k) for k in
                             ("p10", "p50", "p90", "range", "coverage", "style_high",
                              "style_low", "em_baseline_ok") if k in emo_base}}

    counts = tub.group_by("track_id").len().sort("len", descending=True)
    sids = [r["track_id"] for r in counts.iter_rows(named=True) if r["len"] >= 20]
    if not sids:
        cap.release()
        return {"clip_id": clip_id, "ok": False, "reason": "no subjects with >=20 frames"}
    subjects = [build(s) for s in sids]
    cap.release()

    # fashion summary per subject (from likeness.json) — shown in the LIKENESS region.
    lk_path = out_dir / "likeness.json"
    if lk_path.exists():
        lk = json.loads(lk_path.read_text(encoding="utf-8")).get("riders", {})
        for s in subjects:
            fa = (lk.get(str(s["sid"])) or {}).get("fashion")
            if fa:
                bits = [fa["eyewear"]] if fa.get("eyewear") != "none" else []
                if fa.get("mask"): bits.append("mask")
                if fa.get("hat"): bits.append("hat")
                clip = fa.get("clip") or {}
                hw = (clip.get("headwear") or {}).get("winner")
                s["fashion"] = (", ".join(bits) or "none") + (f"  (clip headwear: {hw})" if hw else "")

    # clean crop tracks (data-retention): if present, the preview uses them →
    # permanently clean, no --source needed (works after the source expires).
    # crop-frame index == subject's frames index (both ascending, same present
    # frames), so JS needs only the file path. Provenance shown for honesty.
    crops = {}
    crop_provenance = None
    cm = inspect.parent / "crops" / "manifest.json"
    if cm.exists():
        man = json.loads(cm.read_text(encoding="utf-8"))
        crops = {s["subject_id"]: f"../crops/{s['file']}" for s in man.get("subjects", [])}
        crop_provenance = {"processed_at": man.get("processed_at"),
                           "source": (man.get("source") or {}).get("path")}

    # observability readout — the per-run trace (run.json) + provenance + which inspector
    # channels are now READ from a persisted trace (the session's observability seam,
    # made visible). Clip-level; rendered in the source-note bar.
    from momentscan.stash import clip_dir, read_emotion_frame, read_provenance, read_run
    _run = read_run(out_root, clip_id) or {}
    _prov = read_provenance(out_root, clip_id) or {}
    obs = {"ran": _run.get("n_ran"), "skipped": _run.get("n_skipped"), "failed": _run.get("n_failed"),
           "elapsed_ms": _run.get("elapsed_ms"), "at": (_run.get("started_at_iso") or "")[:19],
           "source": _prov.get("source_uri"),
           "traces": [t for t, ok in (("emotion_frame", read_emotion_frame(out_root, clip_id) is not None),
                                       ("gate_trace", bool(gate_map))) if ok]}
    # stages that explain a MISSING artifact: failed, or skipped for a real reason
    # (skipped/"exists" is normal — the artifact was already there, not an issue).
    obs["issues"] = [{"stage": s.get("name"), "reason": s.get("reason")}
                     for s in (_run.get("stages") or [])
                     if s.get("status") == "failed"
                     or (s.get("status") == "skipped" and s.get("reason") not in (None, "exists"))]
    # freshness: displayed artifacts that PREDATE their producing source — the
    # algorithm was edited but this clip was not re-run, so what's shown is the OLD
    # algorithm's result. Surfaced so the researcher never trusts a stale read.
    from momentscan.verify import freshness
    from momentscan.pipeline import RUNNERS as _RUNNERS
    _cd = clip_dir(out_root, clip_id)
    obs["stale"] = [st for st in _RUNNERS
                    if (_cd / _RUNNERS[st][0]).exists()
                    and freshness.is_stale(_cd / _RUNNERS[st][0], freshness.STAGE_MODULE[st])]

    data = {"clip": clip_id, "fps": fps, "vw": vw, "vh": vh, "main": main_name,
            "clean": bool(clean), "crops": {str(k): v for k, v in crops.items()},
            "crop_provenance": crop_provenance, "obs": obs,
            "fmin": int(min(min(s["frames"]) for s in subjects)),
            "fmax": int(max(max(s["frames"]) for s in subjects)),
            # gate lane vocabulary GENERATED from gates.py — the inspector cannot hold
            # a different gate verdict set than the engine ("—" = portrait not run).
            "gate_colors": {**gates.REASON_COLORS, "—": "#2c2c2c"},
            "gate_served": list(gates.SERVED),
            # landmark wireframe topology (shared by all subjects/frames): edges over a
            # compact point set; per-frame points live in subject.mesh.
            "mesh_edges": (_mt := _mesh_topology())[1] or [], "mesh_nose": _mt[2] or [],
            "mesh_ridge": _mt[3] or [], "mesh_region": _mt[4] or [],
            "mesh_n": len(_mt[0]) if _mt[0] else 0,
            "subjects": subjects}

    html = _TUBELET_INSPECT_HTML.replace("__DATA__", json.dumps(data, separators=(",", ":")))
    path = inspect / "clip.html"
    path.write_text(html, encoding="utf-8")
    result = {"clip_id": clip_id, "ok": True, "inspect": str(path),
              "n_subjects": len(subjects), "main": main_name,
              "clean_source": bool(clean)}
    log.info("viz.tubelet_inspect.done", extra=result)
    return result



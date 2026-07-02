"""Cards — per-product/process PNG·mp4 renderers over the stash (pure readers).

Split from viz.py (2026-07-02): attribution overlay · process timeline · identity
strip · select timeline · appearance(likeness)/portrait cards · highlight clips.
The interactive one-run window lives in surface/inspector.py.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import cv2
import polars as pl

from visualbus import BBox, DrawBBox, DrawText, FileSource, apply_hint
from visualbus.structured_log import log_context
from visualbus.timestamp import ns_to_seconds

from momentscan.stash import (
    read_attribution, read_candidates, read_detections, read_features,
    read_landmarks, read_process_trace, read_stitch, read_tubelets,
)

log = logging.getLogger("momentscan.surface.cards")

ROLE_COLORS = {"main": (0, 200, 0), "auxiliary": (0, 165, 255)}  # BGR
UNATTRIBUTED = (160, 160, 160)

# process-timeline palette (BGR) — modules get stable colors by name, then cycle.
MODULE_COLORS = {"face_detect": (90, 200, 90), "iou_tracker": (60, 170, 255)}
EXTRA_COLORS = ((200, 140, 80), (180, 90, 200), (90, 220, 220), (220, 220, 90))
SUBJECT_COLORS = ((90, 200, 90), (60, 170, 255), (220, 160, 80), (180, 90, 200),
                  (90, 220, 220), (130, 130, 240))


def render_attribution(
    video_path: str | Path,
    out_root: str | Path,
    *,
    fps: int | None = None,
    contact_sheet_n: int = 9,
) -> dict:
    """Render attribution_trace.mp4 + contact_sheet.jpg for one clip."""
    video_path = Path(video_path)
    clip_id = video_path.stem
    out_dir = Path(out_root) / clip_id

    with log_context(clip_id=clip_id):
        t0 = time.perf_counter()
        df = read_detections(out_root, clip_id)
        att = read_attribution(out_root, clip_id) or {}
        roles: dict[str, str] = att.get("roles") or {}
        samples = {s["frame_idx"]: s for s in att.get("samples") or []}
        sample_frames = sorted(samples)
        main_sid = next((int(k) for k, v in roles.items() if v == "main"), None)

        boxes_by_frame: dict[int, list[tuple[int, list[float]]]] = {}
        for r in df.iter_rows(named=True):
            boxes_by_frame.setdefault(r["frame_idx"], []).append((r["subject_id"], r["bbox"]))

        trace_path = out_dir / "attribution_trace.mp4"
        src = FileSource(video_path, fps=fps)
        prof = src.profile
        out_fps = float(fps) if fps else (prof.fps or 30.0)
        writer = None
        sheet_frames: list = []
        sheet_wanted = set(sample_frames[:: max(1, len(sample_frames) // contact_sheet_n)][:contact_sheet_n]) \
            if sample_frames else set()
        n_written = 0
        try:
            for frame in src:
                img = frame.data.copy()
                for sid, bb in boxes_by_frame.get(frame.frame_id, ()):
                    role = roles.get(str(sid))
                    label = f"{role.upper()[:4]} s{sid}" if role else f"s{sid}"
                    s = samples.get(frame.frame_id)
                    if s and str(sid) in s["depth"]:
                        label += f" d={s['depth'][str(sid)]:.0f}"
                    apply_hint(img, DrawBBox(
                        bbox=BBox(x1=bb[0], y1=bb[1], x2=bb[2], y2=bb[3]),
                        frame_id=frame.frame_id,
                        color=ROLE_COLORS.get(role, UNATTRIBUTED),
                        label=label, thickness=2,
                    ))
                _draw_consistency_strip(img, sample_frames, samples, main_sid, frame.frame_id)
                apply_hint(img, DrawText(
                    text=f"{clip_id}  {att.get('ride_type', '?')}  margin={att.get('margin')}"
                         f"  valid={att.get('valid')}",
                    x=12, y=28, frame_id=frame.frame_id, color=(235, 235, 235), font_scale=0.6,
                ))
                apply_hint(img, DrawText(
                    text=f"f={frame.frame_id}  t={ns_to_seconds(frame.t_ns):.2f}s",
                    x=12, y=52, frame_id=frame.frame_id, color=(180, 220, 180), font_scale=0.55,
                ))
                if writer is None:
                    h, w = img.shape[:2]
                    writer = cv2.VideoWriter(
                        str(trace_path), cv2.VideoWriter_fourcc(*"mp4v"), out_fps, (w, h))
                writer.write(img)
                n_written += 1
                if frame.frame_id in sheet_wanted:
                    sheet_frames.append(img.copy())
        finally:
            if writer is not None:
                writer.release()
            src.close()

        sheet_path = None
        if sheet_frames:
            sheet_path = out_dir / "contact_sheet.jpg"
            _write_contact_sheet(sheet_frames, sheet_path)

        result = {
            "clip_id": clip_id,
            "frames_written": n_written,
            "trace_path": str(trace_path),
            "contact_sheet": str(sheet_path) if sheet_path else None,
            "elapsed_s": round(time.perf_counter() - t0, 3),
        }
        log.info("viz.done", extra=result)
        return result


def render_process_timeline(out_root: str | Path, clip_id: str) -> dict:
    """Render process_timeline.png — HOW one unit input was processed.

    Pure function of the stash (process_trace.jsonl + detections.parquet).
    Three lanes over a shared frame axis:

      1. latency — per-frame cycle time (gray bars) with each module's compute
         stacked in color on top of it. Gray towering over color = the time
         went to decode/draw/encode, not the models; a color spike names the
         slow module. Red ticks above the lane mark module errors.
      2. faces  — detections per frame; empty columns are the no-face spans.
      3. tracks — gantt of track ids colored by stitched subject; in-span
         misses drawn red. Fragmentation (many short rows, red runs) is the
         picture of what re-id stitching had to repair. Stitch merges are
         drawn as white connectors between the joined rows (labelled with the
         merge cosine), and in-track identity-purity suspects (stitch.json)
         as magenta underlines — the IoU-swap risk made visible.

    If the clip has been carried through Step 0 (tubelets.parquet exists),
    later-stage conclusions are overlaid: each gantt row gains its rider_role
    (main/aux; tracks absent from tubelets are dimmed = dropped bystander),
    and the boarding→ride boundary is drawn as a vertical line plus a phase
    strip above the x-axis. The daemon-time render has none of this (those
    stages haven't run yet); re-render via ``momentscan viz`` after Step 0.
    """
    import numpy as np

    out_dir = Path(out_root) / clip_id
    rows = read_process_trace(out_root, clip_id)
    if not rows:
        return {"clip_id": clip_id, "ok": False, "reason": "no process_trace.jsonl"}

    fxs = [r["frame_idx"] for r in rows]
    f_min, f_max = min(fxs), max(fxs)
    n = len(rows)
    t_rel = np.array([r["t_rel_ms"] for r in rows], dtype=np.float64)
    cycle = np.diff(t_rel, prepend=0.0)
    mod_names = sorted({m for r in rows for m in r["modules"]})
    mod_ms = {m: np.array([r["modules"].get(m, 0.0) for r in rows]) for m in mod_names}
    faces = np.array([r.get("n_faces", 0) for r in rows])
    err_frames = [r["frame_idx"] for r in rows if r.get("errors")]

    tracks: list[tuple[int, int, set[int]]] = []   # (track_id, subject_id, frames)
    try:
        df = read_detections(out_root, clip_id)
        by_tid: dict[int, tuple[int, set[int]]] = {}
        for r in df.iter_rows(named=True):
            sid, seen = by_tid.setdefault(r["track_id"], (r["subject_id"], set()))
            seen.add(r["frame_idx"])
        tracks = sorted(((tid, sid, seen) for tid, (sid, seen) in by_tid.items()),
                        key=lambda x: min(x[2]))
    except Exception:
        pass  # zero-detection clip — gantt lane just stays empty

    # Stitch evidence (optional — older stashes predate stitch.json).
    stitch_rec = read_stitch(out_root, clip_id) or {}
    stitches = stitch_rec.get("stitches") or []
    purity_runs = {p["track_id"]: p["suspect_runs"]
                   for p in stitch_rec.get("purity") or [] if p["suspect_runs"]}

    # Step 0 overlay (optional): rider_role per track + scene_phase per frame.
    roles: dict[int, str] = {}
    phase_by_frame: dict[int, str] = {}
    try:
        for r in read_tubelets(out_root, clip_id).iter_rows(named=True):
            roles[r["track_id"]] = r["rider_role"]
            phase_by_frame[r["frame_idx"]] = r["scene_phase"]
    except Exception:
        pass  # not yet carried through Step 0 — render detect-stage view only
    ride_start = min((f for f, p in phase_by_frame.items() if p == "ride"), default=None)

    # ── geometry: shared x-mapping, lanes stacked under a header ─────────────
    left, right = (110 if roles else 76), 16
    plot_w = min(1760, max(600, n * 3))
    width = left + plot_w + right
    cw = max(1, plot_w // max(1, n))

    def x_of(f: int) -> int:
        return left + int((f - f_min) / max(1, f_max - f_min) * (plot_w - cw))

    lat_h, face_h, row_h = 130, 44, 13
    axis_h = 40 if phase_by_frame else 26   # extra row for the phase strip
    gantt_rows = tracks[:14]
    head_h, title_h = 46, 16
    height = (head_h + (title_h + lat_h + 8) + (title_h + face_h + 8)
              + (title_h + max(1, len(gantt_rows)) * row_h + 8) + axis_h)
    img = np.full((height, width, 3), 22, dtype=np.uint8)

    def text(s, x, y, color=(225, 225, 225), scale=0.42):
        cv2.putText(img, s, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)

    def color_of(m: str, i: int):
        return MODULE_COLORS.get(m, EXTRA_COLORS[i % len(EXTRA_COLORS)])

    # vertical frame gridlines — drawn first so lane content sits on top
    span = max(1, f_max - f_min)
    step = max(1, int(round(span / 8 / 10.0)) * 10)
    ticks = list(range(f_min, f_max + 1, step))
    for f in ticks:
        x = x_of(f)
        cv2.line(img, (x, head_h), (x, height - axis_h), (40, 40, 40), 1)
        text(f"f{f}", x - 8, height - 10, color=(140, 140, 140), scale=0.38)

    # header — the numeric summary the picture below explains
    text(f"{clip_id}  process timeline   {n} frames  f{f_min}..f{f_max}"
         f"   total {t_rel[-1] / 1000:.1f}s", 12, 20, scale=0.55)
    parts = [f"{m} p50 {np.percentile(v, 50):.0f}ms p95 {np.percentile(v, 95):.0f}ms"
             for m, v in mod_ms.items()]
    parts.append(f"cycle p50 {np.percentile(cycle, 50):.0f}ms p95 {np.percentile(cycle, 95):.0f}ms")
    parts.append(f"errors {len(err_frames)}")
    text("   ".join(parts), 12, 38, color=(170, 170, 170))

    y = head_h

    # ── lane 1: latency ──────────────────────────────────────────────────────
    text("latency  (gray = cycle, color = module, red = error)",
         left, y + 11, color=(170, 170, 170))
    for i, (m, _) in enumerate(mod_ms.items()):
        lx = left + 400 + i * 150
        cv2.rectangle(img, (lx, y + 4), (lx + 8, y + 12), color_of(m, i), -1)
        text(m, lx + 12, y + 11, color=(170, 170, 170))
    y += title_h
    y_base = y + lat_h
    ymax = max(float(np.percentile(cycle, 99)), 1.0)
    for frac in (0.5, 1.0):
        gy = y_base - int(lat_h * frac)
        cv2.line(img, (left, gy), (left + plot_w, gy), (45, 45, 45), 1)
        text(f"{ymax * frac:.0f}ms", 12, gy + 4, color=(120, 120, 120), scale=0.38)
    for i, r in enumerate(rows):
        x = x_of(r["frame_idx"])
        h = int(min(cycle[i] / ymax, 1.0) * lat_h)
        cv2.rectangle(img, (x, y_base - h), (x + cw - 1, y_base), (70, 70, 70), -1)
        stack = y_base
        for j, m in enumerate(mod_names):
            mh = int(min(mod_ms[m][i] / ymax, 1.0) * lat_h)
            if mh > 0:
                cv2.rectangle(img, (x, stack - mh), (x + cw - 1, stack), color_of(m, j), -1)
            stack -= mh
    for f in err_frames:
        x = x_of(f)
        cv2.rectangle(img, (x, y - 4), (x + max(cw, 2) - 1, y + 2), (0, 0, 230), -1)
    y = y_base + 8

    # ── lane 2: faces per frame ──────────────────────────────────────────────
    max_faces = int(faces.max()) if faces.size and faces.max() > 0 else 1
    text(f"faces / frame  (max {max_faces})", left, y + 11, color=(170, 170, 170))
    y += title_h
    y_base = y + face_h
    for i, r in enumerate(rows):
        if faces[i] <= 0:
            continue
        x = x_of(r["frame_idx"])
        h = int(faces[i] / max_faces * face_h)
        cv2.rectangle(img, (x, y_base - h), (x + cw - 1, y_base), (200, 190, 90), -1)
    y = y_base + 8

    # ── lane 3: track gantt ──────────────────────────────────────────────────
    extra = f"  (+{len(tracks) - len(gantt_rows)} more)" if len(tracks) > len(gantt_rows) else ""
    role_note = ", dim = dropped by Step 0" if roles else ""
    text(f"tracks  (color = subject, red = in-span miss, white link = stitch,"
         f" magenta = purity suspect{role_note}){extra}",
         left, y + 11, color=(170, 170, 170))
    y += title_h
    row_mid: dict[int, int] = {}
    first_seen: dict[int, int] = {}
    for tid, sid, seen in gantt_rows:
        mid = y + row_h // 2
        row_mid[tid], first_seen[tid] = mid, min(seen)
        c = SUBJECT_COLORS[sid % len(SUBJECT_COLORS)]
        label = f"t{tid}-s{sid}"
        if roles:
            # tubelets carry the stitched anchor id (= subject), so a merged
            # fragment inherits its subject's role rather than reading "drop".
            role = roles.get(tid, roles.get(sid))
            if role is None:                       # in detections, not in tubelets
                label += " drop"
                c = tuple(int(v * 0.4) for v in c)
            else:
                label += " " + {"main": "main", "auxiliary": "aux"}.get(role, role)
        text(label, 12, mid + 4, color=c, scale=0.38)
        cv2.line(img, (x_of(min(seen)), mid), (x_of(max(seen)) + cw - 1, mid), (60, 60, 60), 1)
        for f in range(min(seen), max(seen) + 1):
            x = x_of(f)
            if f in seen:
                cv2.rectangle(img, (x, mid - 4), (x + cw - 1, mid + 4), c, -1)
            else:
                cv2.rectangle(img, (x, mid - 2), (x + cw - 1, mid + 2), (0, 0, 200), -1)
        for run in purity_runs.get(tid, ()):       # in-track identity suspects
            cv2.rectangle(img, (x_of(run["start_frame"]), mid + 5),
                          (x_of(run["end_frame"]) + cw - 1, mid + 6), (200, 80, 220), -1)
        y += row_h

    # stitch links — vertical white connector at the junction (the later
    # track's first frame), labelled with the merge cosine.
    for m in stitches:
        a, b = m["tracks"]
        if a in row_mid and b in row_mid:
            xj = x_of(max(first_seen[a], first_seen[b]))
            y0, y1 = sorted((row_mid[a], row_mid[b]))
            cv2.line(img, (xj, y0), (xj, y1), (235, 235, 235), 1)
            cv2.circle(img, (xj, y0), 2, (235, 235, 235), -1)
            cv2.circle(img, (xj, y1), 2, (235, 235, 235), -1)
            text(f"{m['cos']:.2f}", xj + 4, (y0 + y1) // 2 + 4,
                 color=(235, 235, 235), scale=0.35)

    # ── Step 0 overlay: phase strip + boarding→ride boundary ─────────────────
    if phase_by_frame:
        sy = height - axis_h + 2
        for f, p in phase_by_frame.items():
            if f_min <= f <= f_max:
                x = x_of(f)
                c = (90, 200, 255) if p == "ride" else (150, 130, 70)
                cv2.rectangle(img, (x, sy), (x + cw - 1, sy + 5), c, -1)
        text("phase", 12, sy + 7, color=(140, 140, 140), scale=0.38)
    if ride_start is not None:
        x = x_of(ride_start)
        cv2.line(img, (x, head_h), (x, height - axis_h + 7), (90, 200, 255), 1)
        text(f"ride f{ride_start}", x + 4, height - axis_h + 9, color=(90, 200, 255), scale=0.38)

    timeline_path = out_dir / "process_timeline.png"
    cv2.imwrite(str(timeline_path), img)
    result = {"clip_id": clip_id, "timeline_path": str(timeline_path),
              "n_frames": n, "n_tracks": len(tracks), "n_errors": len(err_frames),
              "n_stitches": len(stitches),
              "purity_suspect_tracks": sorted(purity_runs),
              "step0_overlay": bool(roles), "ride_start": ride_start,
              "ok": True}
    log.info("viz.process_timeline.done", extra=result)
    return result


def render_identity_strip(
    video_path: str | Path,
    out_root: str | Path,
    *,
    fps: int | None = None,
    max_cols: int = 40,
    tile: int = 72,
) -> dict:
    """Render identity_strip.jpg — face crops per track along the time axis.

    The gantt proves boxes were CONNECTED; this shows WHO is inside them. One
    row per track (timeline order), one column per sampled time step, each
    cell the face crop at that moment. White connectors mark stitch junctions
    with their cosine. The eyeball test for both anchor failure modes:
      - did the stitch join the same person? (compare faces across the link)
      - did an IoU-continuous track swap person mid-span? (scan a row)
    """
    import numpy as np

    video_path = Path(video_path)
    clip_id = video_path.stem
    out_dir = Path(out_root) / clip_id

    with log_context(clip_id=clip_id):
        t0 = time.perf_counter()
        df = read_detections(out_root, clip_id)
        by_tid: dict[int, tuple[int, dict[int, list[float]]]] = {}
        for r in df.iter_rows(named=True):
            sid, boxes = by_tid.setdefault(r["track_id"], (r["subject_id"], {}))
            boxes[r["frame_idx"]] = r["bbox"]
        if not by_tid:
            return {"clip_id": clip_id, "ok": False, "reason": "no detections"}
        order = sorted(by_tid, key=lambda t: min(by_tid[t][1]))

        stitch_rec = read_stitch(out_root, clip_id) or {}
        roles: dict[int, str] = {}
        try:
            for r in read_tubelets(out_root, clip_id).iter_rows(named=True):
                roles[r["track_id"]] = r["rider_role"]
        except Exception:
            pass

        f_min = min(min(b) for _, b in by_tid.values())
        f_max = max(max(b) for _, b in by_tid.values())
        step = max(1, -(-(f_max - f_min + 1) // max_cols))   # ceil div
        cols = list(range(f_min, f_max + 1, step))

        # wanted[frame] = [(row_idx, col_idx, bbox)] — nearest observed frame
        # within half a step stands in for the column's center.
        wanted: dict[int, list[tuple[int, int, list[float]]]] = {}
        for ri, tid in enumerate(order):
            _, boxes = by_tid[tid]
            seen = sorted(boxes)
            for ci, fc in enumerate(cols):
                fsel = min(seen, key=lambda f: abs(f - fc))
                if abs(fsel - fc) <= step // 2:
                    wanted.setdefault(fsel, []).append((ri, ci, boxes[fsel]))

        label_w, pad, row_h = 110, 2, tile + 18
        width = label_w + len(cols) * (tile + pad) + 8
        height = 30 + len(order) * row_h + 22
        img = np.full((height, width, 3), 22, dtype=np.uint8)

        def text(s, x, y, color=(225, 225, 225), scale=0.42):
            cv2.putText(img, s, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)

        def cell_xy(ri: int, ci: int) -> tuple[int, int]:
            return label_w + ci * (tile + pad), 30 + ri * row_h

        src = FileSource(video_path, fps=fps)
        try:
            for frame in src:
                hits = wanted.get(frame.frame_id)
                if not hits:
                    continue
                fh, fw = frame.data.shape[:2]
                for ri, ci, bb in hits:
                    cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
                    side = max(bb[2] - bb[0], bb[3] - bb[1]) * 1.4
                    x1 = int(max(0, cx - side / 2)); y1 = int(max(0, cy - side / 2))
                    x2 = int(min(fw, cx + side / 2)); y2 = int(min(fh, cy + side / 2))
                    if x2 - x1 < 2 or y2 - y1 < 2:
                        continue
                    crop = cv2.resize(frame.data[y1:y2, x1:x2], (tile, tile))
                    x, y = cell_xy(ri, ci)
                    img[y:y + tile, x:x + tile] = crop
        finally:
            src.close()

        for ri, tid in enumerate(order):
            sid = by_tid[tid][0]
            c = SUBJECT_COLORS[sid % len(SUBJECT_COLORS)]
            label = f"t{tid}-s{sid}"
            if roles:
                role = roles.get(tid, roles.get(sid))
                label += " " + {"main": "main", "auxiliary": "aux"}.get(role, "drop")
            text(label, 8, 30 + ri * row_h + tile // 2, color=c, scale=0.42)

        # stitch junctions — white connector spanning the joined rows at the
        # later track's first column.
        row_of = {tid: ri for ri, tid in enumerate(order)}
        for m in stitch_rec.get("stitches") or []:
            a, b = m["tracks"]
            if a in row_of and b in row_of:
                fj = max(min(by_tid[a][1]), min(by_tid[b][1]))
                ci = min(range(len(cols)), key=lambda i: abs(cols[i] - fj))
                x = cell_xy(0, ci)[0] - pad
                ys = sorted((cell_xy(row_of[a], 0)[1], cell_xy(row_of[b], 0)[1]))
                cv2.line(img, (x, ys[0] + tile // 2), (x, ys[1] + tile // 2), (235, 235, 235), 2)
                text(f"stitch {m['cos']:.2f}", x + 4, ys[0] + tile // 2 - 6)

        for ci in range(0, len(cols), max(1, len(cols) // 10)):
            text(f"f{cols[ci]}", cell_xy(0, ci)[0], height - 8, color=(140, 140, 140), scale=0.38)
        text(f"{clip_id}  identity strip  (1 col = {step} frames)", 8, 18, scale=0.5)

        strip_path = out_dir / "identity_strip.jpg"
        cv2.imwrite(str(strip_path), img)
        result = {"clip_id": clip_id, "strip_path": str(strip_path),
                  "n_tracks": len(order), "n_cols": len(cols),
                  "elapsed_s": round(time.perf_counter() - t0, 3), "ok": True}
        log.info("viz.identity_strip.done", extra=result)
        return result


def render_select_timeline(out_root: str | Path, clip_id: str, *, fps: int = 6, tile: int = 56) -> dict:
    """Render select_timeline.png — WHY each pick, per rider track.

      highlight lane (E010) — the decision signal when×which as orange bars;
        the WHEN ridge (드묾⊕강렬함, what segmentation actually cuts on — no
        baseline constant) as a white line. Phrase segments shaded with
        rank+score+driver (unresolved dimmed), ▼ = WHEN peak, ● = WHICH rep.
        Component strip below: Δ components + the rarity line.
      likeness lane — 외형 측정 score bars + ranked picks.
      portrait lane (E008) — aesthetic bars (no pose prior) + ranked picks
        + diversity-set view letters (F/L/R/S).

    Signals come from select.frame_scores (THE scoring function); picks come
    from candidates.jsonl (what was actually served). If the two disagree the
    candidates are stale — and the picture shows it. Thumbnails are cut from
    detect.mp4 by tubelet bbox: pure function of the stash.
    """
    import numpy as np

    from momentscan.products.select import frame_scores
    from momentscan.products.select import rolling_median

    out_dir = Path(out_root) / clip_id
    cands = read_candidates(out_root, clip_id)
    if not cands:
        return {"clip_id": clip_id, "ok": False, "reason": "no candidates.jsonl"}
    tubes = read_tubelets(out_root, clip_id)
    by_tp: dict[tuple[int, str], dict] = {(c["track_id"], c["product"]): c for c in cands}
    tids = sorted({c["track_id"] for c in cands})

    scores: dict[int, dict] = {}
    roles: dict[int, str] = {}
    bboxes: dict[int, dict[int, list[float]]] = {}
    phase_by_frame: dict[int, str] = {}
    for r in tubes.iter_rows(named=True):
        bboxes.setdefault(r["track_id"], {})[r["frame_idx"]] = r["bbox"]
        roles[r["track_id"]] = r["rider_role"]
        phase_by_frame.setdefault(r["frame_idx"], r["scene_phase"])
    for tid in tids:
        scores[tid] = frame_scores(out_root, clip_id, tid, fps=fps)

    f_min = min(int(s["fx"].min()) for s in scores.values())
    f_max = max(int(s["fx"].max()) for s in scores.values())

    # ── geometry ─────────────────────────────────────────────────────────────
    left, right = 110, 16
    n = f_max - f_min + 1
    plot_w = min(1760, max(600, n * 3))
    width = left + plot_w + right
    cw = max(1, plot_w // max(1, n))

    def x_of(f: int) -> int:
        return left + int((f - f_min) / max(1, f_max - f_min) * (plot_w - cw))

    hl_h, pf_h, title_h, thumb_h = 110, 70, 16, tile + 8
    comp_h = 46                       # WHEN component strip under the hl lane
    sect_h = title_h + thumb_h + hl_h + comp_h + 18 + 2 * (title_h + thumb_h + pf_h + 16)
    head_h, axis_h = 30, 40
    height = head_h + len(tids) * sect_h + axis_h
    img = np.full((height, width, 3), 22, dtype=np.uint8)

    def text(s, x, y, color=(225, 225, 225), scale=0.42):
        cv2.putText(img, s, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)

    # gridlines + axis first, so lanes draw over them
    step = max(1, int(round((f_max - f_min) / 8 / 10.0)) * 10)
    for f in range(f_min, f_max + 1, step):
        cv2.line(img, (x_of(f), head_h), (x_of(f), height - axis_h), (40, 40, 40), 1)
        text(f"f{f}", x_of(f) - 8, height - 10, color=(140, 140, 140), scale=0.38)
    text(f"{clip_id}  select timeline   (signal = current frame_scores,"
         f" picks = candidates.jsonl)", 12, 19, scale=0.5)

    # phase strip (same colors as the process timeline)
    sy = height - axis_h + 2
    for f, p in phase_by_frame.items():
        if f_min <= f <= f_max:
            c = (90, 200, 255) if p == "ride" else (150, 130, 70)
            cv2.rectangle(img, (x_of(f), sy), (x_of(f) + cw - 1, sy + 5), c, -1)
    text("phase", 12, sy + 7, color=(140, 140, 140), scale=0.38)

    # thumbnail source — detect.mp4 random access
    cap = cv2.VideoCapture(str(out_dir / "detect.mp4"))

    def thumb(track_id: int, f: int):
        bb = bboxes.get(track_id, {}).get(f)
        if bb is None or not cap.isOpened():
            return None
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, frm = cap.read()
        if not ok:
            return None
        fh, fw = frm.shape[:2]
        cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
        side = max(bb[2] - bb[0], bb[3] - bb[1]) * 1.5
        x1, y1 = int(max(0, cx - side / 2)), int(max(0, cy - side / 2))
        x2, y2 = int(min(fw, cx + side / 2)), int(min(fh, cy + side / 2))
        if x2 - x1 < 2 or y2 - y1 < 2:
            return None
        return cv2.resize(frm[y1:y2, x1:x2], (tile, tile))

    def put_thumb(track_id: int, f: int, y0: int, rank: int, color):
        tm = thumb(track_id, f)
        x = min(max(x_of(f) - tile // 2, left), left + plot_w - tile)
        if tm is not None:
            img[y0:y0 + tile, x:x + tile] = tm
        cv2.rectangle(img, (x, y0), (x + tile, y0 + tile), color, 1)
        text(str(rank), x + 3, y0 + 13, color=color, scale=0.42)

    y = head_h
    for tid in tids:
        s = scores[tid]
        fx, ts = s["fx"], s["ts"]
        ts_arr = np.array([ts[int(f)] for f in fx])
        role = {"main": "main", "auxiliary": "aux"}.get(roles.get(tid, "?"), "?")

        def f_of_ms(ms: int) -> int:
            return int(fx[np.argmin(np.abs(ts_arr - ms))])

        # ── highlight lane ───────────────────────────────────────────────────
        text(f"t{tid} {role}  highlight, sqrt scale   (bars = when x which,"
             f" white = WHEN ridge [segments cut here, no baseline],"
             f" shade = phrase + driver %, v = WHEN peak, o = WHICH rep,"
             f" strip below = WHEN components incl. rarity)",
             left, y + 11, color=(170, 170, 170))
        y += title_h
        ty, y = y, y + thumb_h
        y_base = y + hl_h
        sig = s["highlight"]
        fin = np.isfinite(sig)
        if fin.any():
            ymax = float(np.nanmax(sig)) + 1e-9

            def y_amp(v: float) -> int:
                # sqrt scale — the signal is z⁺-peaky; linear crushes the
                # low-energy region this lane exists to show.
                return int(np.sqrt(min(v / ymax, 1.0)) * (hl_h - 14))
            hcand = by_tp.get((tid, "highlight"))
            segs = ([hcand["pick"], *hcand["alternatives"]] if hcand else [])
            iterms = s["impact_terms"]
            fpos = {int(f): i for i, f in enumerate(fx)}
            for rank, seg in enumerate(segs, start=1):    # shades under the bars
                xs, xe = x_of(f_of_ms(seg["start_ms"])), x_of(f_of_ms(seg["end_ms"])) + cw - 1
                shade = (52, 46, 30) if seg["resolved"] else (36, 34, 30)
                edge = (90, 200, 255) if seg["resolved"] else (110, 110, 110)
                cv2.rectangle(img, (xs, y - 2), (xe, y_base), shade, -1)
                cv2.rectangle(img, (xs, y - 2), (xe, y_base), edge, 1)
                note = "" if seg["resolved"] else " unres"
                drv = ""                                  # what MADE this phrase
                iw = fpos.get(seg["when_frame"])
                if iw is not None:
                    zv = {k: float(v[iw]) for k, v in iterms.items()
                          if np.isfinite(v[iw])}
                    if zv:
                        tot = sum(zv.values()) + 1e-9
                        kb = max(zv, key=zv.get)
                        drv = f" {kb.replace('d_', '')} {zv[kb] / tot:.0%}"
                text(f"#{rank} {seg['score']:.2f}{note}{drv}", xs + 3, y + 10,
                     color=edge, scale=0.38)
            for i, f in enumerate(fx):                    # fast energy bars
                if fin[i]:
                    cv2.rectangle(img, (x_of(int(f)), y_base - y_amp(sig[i])),
                                  (x_of(int(f)) + cw - 1, y_base), (60, 170, 255), -1)
            # E010: the WHEN ridge — the line segmentation actually cuts on
            # (smoothed, own scale). White so it reads against the orange bars.
            when = s["when"]
            wsm = rolling_median(when, 3)
            wmax = float(np.nanmax(wsm)) + 1e-9 if np.isfinite(wsm).any() else 1.0
            wpts = [(x_of(int(f)) + cw // 2,
                     y_base - int(np.sqrt(min(max(wsm[i], 0.0) / wmax, 1.0)) * (hl_h - 14)))
                    for i, f in enumerate(fx) if np.isfinite(wsm[i])]
            for a, b in zip(wpts, wpts[1:]):
                if b[0] - a[0] <= 3 * cw:
                    cv2.line(img, a, b, (235, 235, 235), 1)
            text("when", left + plot_w + 2, wpts[-1][1] + 4 if wpts else y_base,
                 color=(235, 235, 235), scale=0.35)
            for rank, seg in enumerate(segs, start=1):    # marks + thumbs on top
                xw = x_of(seg["when_frame"])
                cv2.drawMarker(img, (xw + cw // 2, y + 4), (235, 235, 235),
                               cv2.MARKER_TRIANGLE_DOWN, 7, 1)
                xr = x_of(seg["peak_frame"])
                cv2.circle(img, (xr + cw // 2, y + 4), 3, (200, 80, 220), -1)
                put_thumb(tid, seg["peak_frame"], ty, rank,
                          (90, 200, 255) if seg["resolved"] else (110, 110, 110))
        else:
            text("no ride signal (boarding-only / aux without ride span)",
                 left, y + hl_h // 2, color=(120, 120, 120), scale=0.42)
        # WHEN component strip — what made the energy (shared z⁺ scale);
        # E010 adds the rarity line (state anomaly) next to the Δ components.
        COMP_C = {"d_expr": (60, 220, 230), "d_pose": (230, 160, 80),
                  "d_light": (80, 230, 120), "vel": (160, 160, 160),
                  "rarity": (200, 120, 255)}
        cy0 = y_base + 6
        cv2.rectangle(img, (left, cy0), (left + plot_w, cy0 + comp_h), (28, 28, 28), -1)
        if fin.any():
            iterms = dict(s["impact_terms"])
            iterms["rarity"] = s["rarity"]
            cmax = max(float(np.nanmax(v)) for v in iterms.values()) + 1e-9
            for name, arr in iterms.items():
                pts = [(x_of(int(f)) + cw // 2,
                        cy0 + comp_h - 2 - int(min(arr[i] / cmax, 1.0) * (comp_h - 6)))
                       for i, f in enumerate(fx) if np.isfinite(arr[i]) and fin[i]]
                for a, b in zip(pts, pts[1:]):
                    if b[0] - a[0] <= 3 * cw:             # don't bridge NaN gaps
                        cv2.line(img, a, b, COMP_C[name], 1)
        for li, (name, c) in enumerate(COMP_C.items()):
            text(name.replace("d_", "D"), 12, cy0 + 8 + li * 9, color=c, scale=0.3)
        y = y_base + comp_h + 18

        # ── likeness lane (외형 측정 — 옛 이름 "profile" 폐기) ─────────
        text(f"t{tid} {role}  likeness   (bars = frontal x calm x quality,"
             f" numbered = picks)",
             left, y + 11, color=(170, 170, 170))
        y += title_h
        ty, y = y, y + thumb_h
        y_base = y + pf_h
        prof = s["likeness"]
        pmax = float(np.nanmax(prof)) + 1e-9 if np.isfinite(prof).any() else 1.0
        for i, f in enumerate(fx):
            if np.isfinite(prof[i]):
                h = int(min(prof[i] / pmax, 1.0) * (pf_h - 6))
                cv2.rectangle(img, (x_of(int(f)), y_base - h),
                              (x_of(int(f)) + cw - 1, y_base), (90, 200, 90), -1)
        pcand = by_tp.get((tid, "likeness"))
        picks = ([pcand["pick"], *pcand["alternatives"]] if pcand else [])
        for rank, p in enumerate(picks, start=1):
            f = p["frame_idx"]
            cv2.line(img, (x_of(f) + cw // 2, y), (x_of(f) + cw // 2, y_base), (235, 235, 235), 1)
            put_thumb(tid, f, ty, rank, (90, 200, 90))
        y = y_base + 16

        # ── portrait lane (E008) ─────────────────────────────────────────────
        text(f"t{tid} {role}  portrait   (bars = aesthetic v0 [no pose prior],"
             f" numbered = picks, F/L/R/S = diversity-set views)",
             left, y + 11, color=(170, 170, 170))
        y += title_h
        ty, y = y, y + thumb_h
        y_base = y + pf_h
        port = s.get("portrait")
        if port is not None and np.isfinite(port).any():
            pmax = float(np.nanmax(port)) + 1e-9
            for i, f in enumerate(fx):
                if np.isfinite(port[i]):
                    h = int(min(port[i] / pmax, 1.0) * (pf_h - 6))
                    cv2.rectangle(img, (x_of(int(f)), y_base - h),
                                  (x_of(int(f)) + cw - 1, y_base), (210, 130, 200), -1)
        cand = by_tp.get((tid, "portrait"))
        for rank, p in enumerate(([cand["pick"], *cand["alternatives"]] if cand else []), start=1):
            f = p["frame_idx"]
            cv2.line(img, (x_of(f) + cw // 2, y), (x_of(f) + cw // 2, y_base), (235, 235, 235), 1)
            put_thumb(tid, f, ty, rank, (210, 130, 200))
        scand = by_tp.get((tid, "portrait_set"))
        for m in ([scand["pick"], *scand["alternatives"]] if scand else []):
            x = x_of(m["frame_idx"])
            text(m["view"][0].upper(), x - 2, y_base + 13, color=(210, 130, 200), scale=0.42)
        y = y_base + 16

    cap.release()
    timeline_path = out_dir / "select_timeline.png"
    cv2.imwrite(str(timeline_path), img)
    result = {"clip_id": clip_id, "timeline_path": str(timeline_path),
              "n_tracks": len(tids), "ok": True}
    log.info("viz.select_timeline.done", extra=result)
    return result


def render_appearance_card(out_root: str | Path, clip_id: str, *,
                           n_cols: int = 8, tile: int = 110) -> dict:
    """Render appearance_card.png — visual proof (or refutation) of landmark
    canonicalization, per rider track. Columns sample the track's yaw
    spectrum (hard left → frontal → hard right):

      row 1  the face crop as observed (pose varies)
      row 2  landmarks scale-normed only — pose still inside the geometry
      row 3  canonicalized landmarks (green) over the track's MEDIAN face
             (gray underlay) — if normalization works, green sits on gray in
             every column regardless of pose; misalignment = pose leakage

    Right panels: median face with per-landmark deviation heat (blue=stable,
    red=variable) — which facial regions the distribution can trust — and the
    person's median face (green wire) over the MediaPipe canonical template
    (gray wire): the "평균 대비" picture behind template offset/ratios.
    """
    import numpy as np

    from momentscan.domains.geometry import canonicalize, norm468, template
    from momentscan_features_specialist45d.registry import INDEX

    from mediapipe.tasks.python.vision.face_landmarker import (
        FaceLandmarksConnections as _FLC,
    )
    edges = [(c.start, c.end) for c in
             (*_FLC.FACE_LANDMARKS_CONTOURS, *_FLC.FACE_LANDMARKS_NOSE)]

    out_dir = Path(out_root) / clip_id
    lm_all = read_landmarks(out_root, clip_id)
    feats_all = read_features(out_root, clip_id, "A")
    tids = sorted(set(lm_all["track_id"].to_list()))
    if not tids:
        return {"clip_id": clip_id, "ok": False, "reason": "no landmarks"}

    label_w, pad, heat_w = 92, 4, int(tile * 2.2)
    block_h = 18 + 3 * (tile + pad) + 18
    width = label_w + n_cols * (tile + pad) + 16 + 2 * (heat_w + 16)
    height = 26 + len(tids) * block_h
    img = np.full((height, width, 3), 22, dtype=np.uint8)

    def text(s, x, y, color=(225, 225, 225), scale=0.4):
        cv2.putText(img, s, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)

    def wire(pts3, cx, cy, s, color, thickness=1):
        for a, b in edges:
            if a < len(pts3) and b < len(pts3):
                pa = (int(cx + pts3[a, 0] * s), int(cy - pts3[a, 1] * s))
                pb = (int(cx + pts3[b, 0] * s), int(cy - pts3[b, 1] * s))
                cv2.line(img, pa, pb, color, thickness, cv2.LINE_AA)

    text(f"{clip_id}  appearance canonicalization card   "
         f"(row2 = as observed, row3 = canonicalized over track median[gray])", 10, 17, scale=0.5)

    cap = cv2.VideoCapture(str(out_dir / "detect.mp4"))
    y0 = 26
    for tid in tids:
        lm = lm_all.filter(pl.col("track_id") == tid).sort("frame_idx")
        if len(lm) < 10:
            continue
        fx = lm["frame_idx"].to_numpy()
        P = np.array(lm["landmarks"].to_list(), dtype=np.float64).reshape(len(fx), 478, 3)
        T = np.array(lm["transform"].to_list(), dtype=np.float64).reshape(len(fx), 4, 4)
        cb = np.array(lm["crop_box"].to_list(), dtype=np.float64)
        canon, raw = canonicalize(P, T, cb)
        med = np.median(canon, axis=0)
        dev = np.sqrt(((canon - med) ** 2).sum(axis=2)).mean(axis=0)   # per-landmark
        feats = feats_all.filter(pl.col("track_id") == tid).sort("frame_idx")
        pos = {f: i for i, f in enumerate(feats["frame_idx"].to_numpy())}
        M = np.array(feats["feature"].to_list(), dtype=np.float64)
        yaw = M[[pos[f] for f in fx], INDEX["head_yaw_dev"]]

        order = np.argsort(yaw)
        cols = [order[int(i * (len(order) - 1) / (n_cols - 1))] for i in range(n_cols)]
        role = lm["rider_role"][0]
        text(f"t{tid} {role}   n={len(fx)}", 10, y0 + 13, color=(90, 200, 90))
        rows_y = [y0 + 18, y0 + 18 + (tile + pad), y0 + 18 + 2 * (tile + pad)]
        for lbl, ry in zip(("crop", "observed", "canonical"), rows_y, strict=True):
            text(lbl, 10, ry + tile // 2 + 26, color=(150, 150, 150), scale=0.38)
        for ci, i in enumerate(cols):
            x0 = label_w + ci * (tile + pad)
            x1, y1_, x2, y2_ = (int(v) for v in cb[i])
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(fx[i]))
            ok, frm = cap.read()
            if ok and x2 - x1 > 1 and y2_ - y1_ > 1:
                img[rows_y[0]:rows_y[0] + tile, x0:x0 + tile] = cv2.resize(
                    frm[y1_:y2_, x1:x2], (tile, tile))
            text(f"f{fx[i]} y{yaw[i]:+.0f}", x0 + 2, rows_y[0] + tile + 12,
                 color=(160, 160, 160), scale=0.35)
            wcx = x0 + tile // 2
            ws = tile * 0.30
            wire(raw[i], wcx, rows_y[1] + tile // 2 - 4, ws, (90, 190, 230))
            wire(med, wcx, rows_y[2] + tile // 2 - 4, ws, (80, 80, 80))
            wire(canon[i], wcx, rows_y[2] + tile // 2 - 4, ws, (90, 220, 90))

        # heat panel — median face, per-landmark deviation
        hx = label_w + n_cols * (tile + pad) + 16
        t = np.clip(dev / (np.percentile(dev, 95) + 1e-9), 0, 1)
        s = heat_w * 0.32
        cx, cy = hx + heat_w // 2, rows_y[1] + tile // 2
        wire(med, cx, cy, s, (70, 70, 70))
        for k in range(478):
            px, py = int(cx + med[k, 0] * s), int(cy - med[k, 1] * s)
            c = (int(255 * (1 - t[k])), 60, int(255 * t[k]))   # blue stable → red variable
            cv2.circle(img, (px, py), 2, c, -1)
        text("deviation heat (blue=stable, red=var)",
             hx, rows_y[0] + 12, color=(150, 150, 150), scale=0.38)

        # template panel — person median (green) over canonical template (gray)
        tx = hx + heat_w + 16
        cx2 = tx + heat_w // 2
        person = norm468(med)
        tmpl = template()
        off_rms = float(np.sqrt((((person - tmpl) ** 2).sum(axis=1)).mean()))
        wire(tmpl, cx2, cy, s, (110, 110, 110))
        wire(person, cx2, cy, s, (90, 220, 90))
        text(f"vs canonical template (gray)   offset_rms {off_rms:.3f}",
             tx, rows_y[0] + 12, color=(150, 150, 150), scale=0.38)
        y0 += block_h
    cap.release()

    card_path = out_dir / "appearance_card.png"
    cv2.imwrite(str(card_path), img)
    result = {"clip_id": clip_id, "card_path": str(card_path), "n_tracks": len(tids), "ok": True}
    log.info("viz.appearance_card.done", extra=result)
    return result


def _draw_consistency_strip(img, sample_frames: list[int], samples: dict, main_sid, now: int) -> None:
    """Bottom strip: one tick per depth sample across the clip's co-occurrence
    span. Green = ordering agreed with the final role, red = inverted. A clean
    green band IS the picture of 'the main/aux boundary held for the whole
    clip'; red runs mark exactly where to scrub to."""
    if not sample_frames or main_sid is None:
        return
    h, w = img.shape[:2]
    y0, y1 = h - 22, h - 8
    cv2.rectangle(img, (0, y0 - 2), (w, h), (20, 20, 20), -1)
    f_min, f_max = sample_frames[0], sample_frames[-1]
    span = max(1, f_max - f_min)
    for f in sample_frames:
        x = int((f - f_min) / span * (w - 4)) + 2
        agreed = samples[f]["closer"] == main_sid
        cv2.rectangle(img, (x, y0), (x + 2, y1), (0, 200, 0) if agreed else (0, 0, 230), -1)
    # progress cursor
    if f_min <= now <= f_max:
        x = int((now - f_min) / span * (w - 4)) + 2
        cv2.rectangle(img, (x - 1, y0 - 4), (x + 2, y1 + 3), (235, 235, 235), 1)


def _write_contact_sheet(frames: list, path: Path, *, cols: int = 3, tile_w: int = 426) -> None:
    import numpy as np
    scale = tile_w / frames[0].shape[1]
    tiles = [cv2.resize(f, None, fx=scale, fy=scale) for f in frames]
    rows = []
    for i in range(0, len(tiles), cols):
        row = tiles[i:i + cols]
        while len(row) < cols:
            row.append(np.zeros_like(tiles[0]))
        rows.append(cv2.hconcat(row))
    cv2.imwrite(str(path), cv2.vconcat(rows))


def render_portrait_card(out_root: str | Path, clip_id: str, *, tile: int = 120) -> dict:
    """Render portrait_card.png — WHY each portrait pick, term by term.

    Per track: ranked picks + diversity-set members + two contrast frames
    (the track's worst and median finite-score ride frame). Under every
    thumbnail, one horizontal bar per scoring TERM (quality / eyes / smile /
    em_conf / light / rep / det), each scaled to that term's max over the
    whole track — so a short bar means "this frame lost points HERE", and
    ranking disagreements become attributable at a glance. Same stash-pure
    sources as select_timeline: frame_scores + candidates.jsonl + detect.mp4.
    """
    import numpy as np

    from momentscan.products.select import frame_scores

    out_dir = Path(out_root) / clip_id
    cands = read_candidates(out_root, clip_id)
    by_tp = {(c["track_id"], c["product"]): c for c in cands}
    tids = sorted({c["track_id"] for c in cands if c["product"] == "portrait"})
    if not tids:
        return {"clip_id": clip_id, "ok": False, "reason": "no portrait candidates"}
    tubes = read_tubelets(out_root, clip_id)
    bboxes: dict[int, dict[int, list[float]]] = {}
    roles: dict[int, str] = {}
    for r in tubes.iter_rows(named=True):
        bboxes.setdefault(r["track_id"], {})[r["frame_idx"]] = r["bbox"]
        roles[r["track_id"]] = r["rider_role"]

    TERMS = ("quality", "eyes", "smile", "em_conf", "light", "rep", "det")
    BAR_C = (210, 130, 200)         # portrait lane color
    bar_h, gap = 11, 3
    label_w, pad = 96, 10
    block_h = 22 + len(TERMS) * (bar_h + gap)        # score line + term bars
    sect_title = 24

    # column plan per track: (frame, tag) — ranked picks, set views, contrasts
    plans: dict[int, list[tuple[int, str]]] = {}
    scores: dict[int, dict] = {}
    for tid in tids:
        s = frame_scores(out_root, clip_id, tid)
        scores[tid] = s
        cols: list[tuple[int, str]] = []
        cand = by_tp.get((tid, "portrait"))
        for rank, p in enumerate([cand["pick"], *cand["alternatives"]], start=1):
            cols.append((p["frame_idx"], f"#{rank}"))
        seen = {f for f, _ in cols}
        scand = by_tp.get((tid, "portrait_set"))
        for m in ([scand["pick"], *scand["alternatives"]] if scand else []):
            if m["frame_idx"] not in seen:
                cols.append((m["frame_idx"], f"set:{m['view'][0].upper()}"))
                seen.add(m["frame_idx"])
        port, fx = s["portrait"], s["fx"]
        fin = np.where(np.isfinite(port))[0]
        if len(fin):
            order = fin[np.argsort(port[fin])]
            for i, tag in ((order[len(order) // 2], "median"), (order[0], "worst")):
                if int(fx[i]) not in seen:
                    cols.append((int(fx[i]), tag))
                    seen.add(int(fx[i]))
        plans[tid] = cols

    n_cols = max(len(c) for c in plans.values())
    width = label_w + n_cols * (tile + pad) + 16
    sect_h = sect_title + tile + block_h + 14
    height = 30 + len(tids) * sect_h + 8
    img = np.full((height, width, 3), 22, dtype=np.uint8)

    def text(s, x, y, color=(225, 225, 225), scale=0.42):
        cv2.putText(img, s, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)

    text(f"{clip_id}  portrait card   (bars = score terms, scaled to each"
         f" term's track max — short bar = where the frame lost)", 12, 19, scale=0.5)

    cap = cv2.VideoCapture(str(out_dir / "detect.mp4"))

    def thumb(track_id: int, f: int):
        bb = bboxes.get(track_id, {}).get(f)
        if bb is None or not cap.isOpened():
            return None
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, frm = cap.read()
        if not ok:
            return None
        fh, fw = frm.shape[:2]
        cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
        side = max(bb[2] - bb[0], bb[3] - bb[1]) * 1.6
        x1, y1 = int(max(0, cx - side / 2)), int(max(0, cy - side / 2))
        x2, y2 = int(min(fw, cx + side / 2)), int(min(fh, cy + side / 2))
        if x2 - x1 < 2 or y2 - y1 < 2:
            return None
        return cv2.resize(frm[y1:y2, x1:x2], (tile, tile))

    y = 30
    for tid in tids:
        s = scores[tid]
        fx, port, terms = s["fx"], s["portrait"], s["portrait_terms"]
        pos = {int(f): i for i, f in enumerate(fx)}
        # min–max per term over the track: full bar = track best, empty =
        # track worst — terms live in narrow bands, max-scaling hides them
        trange = {k: (float(np.nanmin(v)), float(np.nanmax(v)) - float(np.nanmin(v)) + 1e-9)
                  for k, v in terms.items()}
        role = {"main": "main", "auxiliary": "aux"}.get(roles.get(tid, "?"), "?")
        text(f"t{tid} {role}", 12, y + 14, color=(210, 130, 200), scale=0.5)
        for ti, name in enumerate(TERMS):                 # term row labels
            ly = y + sect_title + tile + 22 + ti * (bar_h + gap)
            text(name, 12, ly + bar_h - 2, color=(150, 150, 150), scale=0.36)
        for ci, (f, tag) in enumerate(plans[tid]):
            x = label_w + ci * (tile + pad)
            tm = thumb(tid, f)
            ty = y + sect_title
            if tm is not None:
                img[ty:ty + tile, x:x + tile] = tm
            edge = BAR_C if tag.startswith("#") else (110, 110, 110)
            cv2.rectangle(img, (x, ty), (x + tile, ty + tile), edge, 1)
            text(f"{tag} f{f}", x + 3, ty - 4, color=edge, scale=0.4)
            i = pos.get(f)
            if i is None:
                continue
            sc = port[i]
            text(f"score {sc:.3f}" if np.isfinite(sc) else "score nan",
                 x + 3, ty + tile + 14, color=(225, 225, 225), scale=0.38)
            for ti, name in enumerate(TERMS):
                v = terms[name][i]
                by = ty + tile + 22 + ti * (bar_h + gap)
                cv2.rectangle(img, (x, by), (x + tile, by + bar_h), (38, 38, 38), -1)
                if np.isfinite(v):
                    lo, span = trange[name]
                    w = int(min(max((v - lo) / span, 0.0), 1.0) * tile)
                    cv2.rectangle(img, (x, by), (x + w, by + bar_h), BAR_C, -1)
                    text(f"{v:.2f}", x + tile - 30, by + bar_h - 2,
                         color=(20, 20, 20) if w > tile - 34 else (130, 130, 130), scale=0.3)
                else:
                    text("nan", x + 4, by + bar_h - 2, color=(90, 90, 90), scale=0.3)
        y += sect_h

    cap.release()
    card_path = out_dir / "portrait_card.png"
    cv2.imwrite(str(card_path), img)
    result = {"clip_id": clip_id, "card_path": str(card_path),
              "n_tracks": len(tids), "ok": True}
    log.info("viz.portrait_card.done", extra=result)
    return result


def render_highlight_clips(out_root: str | Path, clip_id: str, *,
                           video_path: str | Path | None = None) -> dict:
    """Cut the served highlight segments into watchable mp4s — judgment
    evidence for the CLIP product (cards show frames; a span has to be felt).

    Per highlight track: one mp4 per segment (rank order in the name) plus a
    chronological reel of all segments concatenated (배열은 편집 레이어
    소관이지만, 시간순이 라이드 서사의 기본값이다). Source = the original
    video when given (native fps), else the stash's detect.mp4 (processing
    fps, correct duration) — stash-pure fallback.
    """
    out_dir = Path(out_root) / clip_id
    src = Path(video_path) if video_path else out_dir / "detect.mp4"
    cands = [c for c in read_candidates(out_root, clip_id) if c["product"] == "highlight"]
    if not cands or not src.exists():
        return {"clip_id": clip_id, "ok": False,
                "reason": "no highlight candidates" if cands == [] else f"no video at {src}"}
    hdir = out_dir / "highlights"
    hdir.mkdir(exist_ok=True)
    for old in hdir.glob("*.mp4"):                       # stale segments from prior policy
        old.unlink()

    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS) or 6.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def write_span(writer, start_ms: int, end_ms: int) -> int:
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0, start_ms))
        n = 0
        while cap.get(cv2.CAP_PROP_POS_MSEC) <= end_ms:
            ok, frame = cap.read()
            if not ok:
                break
            writer.write(frame)
            n += 1
        return n

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    written: list[str] = []
    for c in cands:
        tid = c["track_id"]
        segs = [c["pick"], *(c.get("alternatives") or [])]
        for rank, seg in enumerate(segs, start=1):
            p = hdir / f"t{tid}_rank{rank}.mp4"
            wr = cv2.VideoWriter(str(p), fourcc, fps, (w, h))
            n = write_span(wr, seg["start_ms"], seg["end_ms"])
            wr.release()
            if n:
                written.append(p.name)
            else:
                p.unlink(missing_ok=True)
        reel = hdir / f"t{tid}_reel.mp4"
        wr = cv2.VideoWriter(str(reel), fourcc, fps, (w, h))
        n = sum(write_span(wr, s["start_ms"], s["end_ms"])
                for s in sorted(segs, key=lambda s: s["start_ms"]))
        wr.release()
        if n:
            written.append(reel.name)
        else:
            reel.unlink(missing_ok=True)
    cap.release()

    result = {"clip_id": clip_id, "highlights_dir": str(hdir),
              "n_files": len(written), "files": written,
              "source": "original" if video_path else "detect.mp4", "ok": True}
    log.info("viz.highlight_clips.done", extra=result)
    return result



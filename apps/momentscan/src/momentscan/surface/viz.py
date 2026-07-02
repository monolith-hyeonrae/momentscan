"""Viz — a pure function of the stash (phase2 §B, first slice: attribution).

Reads ONLY stash artifacts (detections.parquet + attribution.json) and the
source video, and renders what the pipeline actually concluded — no parallel
analysis path that could drift from the real one. If it isn't in the stash,
it cannot appear in the picture.

Rendered per frame (visualbus grain — ``apply_hint`` + ``cv2.VideoWriter``):
  - bbox per subject, colored by attributed role (main=green, aux=orange),
    labelled ``MAIN s1`` / ``AUX s0``; depth value appended on sampled frames.
  - a bottom timeline strip: one tick per depth sample, green where the
    ordering agreed with the final role, red where it inverted — the
    whole-clip validity of the main/aux boundary, visible at a glance.
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

from momentscan import gates
from momentscan.domains import pose, signals
from momentscan.surface._inspector_html import _TUBELET_INSPECT_HTML
from momentscan.stash import (
    read_attribution, read_candidates, read_detections, read_features,
    read_gate_trace, read_headpose, read_landmarks, read_parse,
    read_portrait, read_process_trace, read_stitch, read_tubelets,
)

log = logging.getLogger("momentscan.viz")

ROLE_COLORS = {"main": (0, 200, 0), "auxiliary": (0, 165, 255)}  # BGR
UNATTRIBUTED = (160, 160, 160)

# process-timeline palette (BGR) — modules get stable colors by name, then cycle.
MODULE_COLORS = {"face_detect": (90, 200, 90), "iou_tracker": (60, 170, 255)}
EXTRA_COLORS = ((200, 140, 80), (180, 90, 200), (90, 220, 220), (220, 220, 90))
SUBJECT_COLORS = ((90, 200, 90), (60, 170, 255), (220, 160, 80), (180, 90, 200),
                  (90, 220, 220), (130, 130, 240))

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
    from momentscan.domains.signals import _rolling_median

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
            wsm = _rolling_median(when, 3)
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

    from momentscan.domains.signals import _canonicalize, _norm468, _template
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
        canon, raw = _canonicalize(P, T, cb)
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
        person = _norm468(med)
        tmpl = _template()
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


def _transcode_h264(src, dst, *, fps=None):
    """detect.mp4 is mpeg4 (browsers can't play it) → H.264 all-intra for
    frame-accurate seek. fps=N re-samples (clean source 30fps → 6fps, aligned
    with detect.mp4). Cached: skips if dst already exists."""
    import subprocess
    dst = Path(dst)
    if dst.exists():
        return dst
    # setpts=PTS-STARTPTS zeroes the first PTS — phone sources carry a start_time
    # offset (cap_1 ≈1.33s) that the browser's TIME-based seek honors but cv2's
    # FRAME-index extraction (bbox · crop track · thumbnails) ignores → a constant
    # frame offset. Resetting it aligns browser time with frame index.
    vf = ["-vf", (f"fps={fps}," if fps else "") + "setpts=PTS-STARTPTS"]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), *vf,
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-x264-params", "keyint=1",
                    "-an", "-reset_timestamps", "1", "-muxdelay", "0", "-muxpreload", "0",
                    str(dst)], check=True)
    return dst


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
            hp_map[(r["track_id"], r["frame_idx"])] = r["yaw"]
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
    hl_lang = _json.loads(_hlp.read_text()) if _hlp.exists() else None
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
            # 6DRepNet yaw (full range) — overlays the same axis as `yaw`: where
            # both exist they should track (adapter aligned); where MediaPipe blanks
            # on a profile, this continues to ±90, the visible evidence behind a side
            # portrait. (6d pitch/roll convention unvalidated → yaw only, honest.)
            ch("yaw6d", "pose", [hp_map.get((int(sid), int(f)), np.nan) for f in fx],
               [210, 130, 230], -90, 90),
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
        # fit) + CANONICAL (pose-removed, via signals._canonicalize = the DECLARED frame,
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
            canon_m, _ = signals._canonicalize(Pm, Tm, cbm)
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
        lk = json.loads(lk_path.read_text()).get("riders", {})
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
        man = json.loads(cm.read_text())
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
    path.write_text(html)
    result = {"clip_id": clip_id, "ok": True, "inspect": str(path),
              "n_subjects": len(subjects), "main": main_name,
              "clean_source": bool(clean)}
    log.info("viz.tubelet_inspect.done", extra=result)
    return result



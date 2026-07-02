# Phase 2 plan — Step 0 (port) + visualization

Step 0 is ~80% already written in portrait981's old momentscan; this is a **port +
vocabulary alignment**, not a rewrite.

> **Resolved 2026-06-08** ([`handoff-visualstack-depth-viz.md`](handoff-visualstack-depth-viz.md)):
> depth shipped as `visualpath.plugins.depth.DepthEstimator` — **bbox = absolute xyxy**
> (`visualbus.BBox`), not normalized xywh. The `vpx/viz` move was **scrapped**: visualstack
> is push-grain, so momentscan renders via `visualbus` hints (`apply_hint` + `cv2.VideoWriter`
> offline; `VideoFileSink` on-bus). `viz.py` is written fresh in the bus grain — NOT ported
> from portrait981, and it does not import the `Observation` model. Section B reflects this.

## A. Step 0 porting plan

### Port (keep the algorithm, drop the `vp.App` shell)

| old (portrait981) | → new | repo | note |
|---|---|---|---|
| `app/depth.py` `estimate_depth`, `compare_face_depth` | generic `depth` component | **visualstack** | Depth-Anything-V2-Small wrapper; domain-agnostic depth ops |
| `app/depth.py` `assign_driver` (sample DUO frames, vote nearer = driver) | `tubelets.py` attribution | momentscan | the voting = rider attribution; uses visualstack depth ops |
| `core.py` `_determine_ride_type_from` (top-20% stable max face count → SOLO/DUO/GROUP) | `tubelets.py` | momentscan | as-is |
| `core.py` `_assign_driver` + `PersonResult.seat` | `tubelets.py` | momentscan | **vocabulary: driver→`rider_role="main"`, passenger→"auxiliary"** |
| `personmemory` `MemoryBank.match` (cosine, EMA merge, tau) | re-id stitch | momentscan (port) | **in-memory only**; drop postgres/pgvector |
| visualstack `face-detect` `FaceDetect` + `IoUTracker` | as-is | visualstack | produces `track_id` |

### Drop (the shell the algorithms were wrapped in)

- `vp.App` lifecycle, `SimpleBackend`, warm executor, `bind_observations` — replaced by the offline stage.
- `JudgmentResult` / `_SlidingSmooth` / `_OnlineZScore` / `judge` — that is **Track A selection (Phase 3)**, not Step 0. Excluded here.
- `FrameResult` / `PersonResult` dataclasses — replaced by `Tubelet` + the `tubelets.parquet` rows.
- `depth.py` `_find_bbox` hack (digs bbox out of a signals dict) — the new tubelet has an explicit `bbox` column.

### New (the only genuinely-new piece)

- **scene-phase (boarding vs ride) + staff/bystander rejection.** Segment the clip
  by global motion / brightness; drop tracks that do not persist into the ride
  (descent) phase, and roadside detections. Old momentscan never rejected staff
  (it just counted persons), so this is new. Small.

### Two sub-stages (dependency isolation — they conflict)

```
step0a  detect + track + reid     onnx / insightface   per-frame      ─┐
        → tubelets.parquet (bbox, track_id, embedding, scene_phase)    │ same
step0b  depth attribution         torch / Depth-Anything  per-clip     ─┘ parquet
        → fills rider_role (main/auxiliary) by depth vote
```

Depth already runs "once per video on sampled frames" — so the onnx and torch
stacks never share a process. Both write `tubelets.parquet`; isolated venvs.

## B. Visualization plan

**Principle: `viz` is a pure function of the stash.** It is a separate, optional
stage that *reads* stash artifacts and renders — so what you see is a faithful
replay of what the pipeline actually did (no parallel code path that can drift).
Run it on demand, or with `--viz` after a run.

### Rendering surface (resolved to the bus grain)

| need | use | source |
|---|---|---|
| draw one mark on a BGR frame | `apply_hint(img, hint)` + `DrawBBox` / `DrawText` / `DrawKeypoint` | `visualbus` |
| offline compose (stashed tubelet → mp4) | `apply_hint` loop + `cv2.VideoWriter` (handoff pattern B) | `visualbus` + cv2 |
| on-bus annotated video | `VideoFileSink` (≈ old `VideoSaver`) | `visualbus` |
| per-frame HUD text panel | `DrawText` hints / a small HUD overlay object | momentscan (fresh) |
| clip report HTML (charts / thumbnails) | plain HTML strings | momentscan (port `report.py` *markup*, not its viz lib) |

`vpx/viz`, `render_marks`, the `Observation` model — **not used** (handoff §②). `BarMark` /
`AxisMark` enter as visualbus hint types via PR only if a second use appears.

### New viz stage (`momentscan/viz.py`)

Reads `tubelets` / `features` / `candidates` for a clip and renders:

1. **Processing-trace video** — *"what was the source, how was it processed"*:
   original frames + tubelet bboxes (`DrawBBox`, colored by `track_id`, labelled
   main/auxiliary via `DrawText`), a scene-phase band, depth-vote markers — composed
   with `apply_hint` + `cv2.VideoWriter` (pattern B). → `stash/{clip}/trace.mp4`
2. **Clip report (HTML)** — *"what came out"*: stage summary (n tracks detected,
   ride_type, driver, bystanders dropped), the Profile contact sheet + Highlight
   montage (from `candidates.jsonl`), and metrics (track purity, seed-eval
   precision). → `stash/{clip}/report.html`

### CLI

```
momentscan viz <clip_id>     # render trace.mp4 + report.html from stash
momentscan ... --viz         # auto-render after a pipeline run
```

Because every stage persists its artifact, the trace is systematic: each visual
element maps to a concrete stash column, so the picture can never claim more than
the pipeline produced.

## Order of work

1. visualstack-side ports: generic `depth` component + move `vpx/viz`. (visualstack session) — see [`handoff-visualstack-depth-viz.md`](handoff-visualstack-depth-viz.md)
2. momentscan `tubelets.py`: ride_type + depth-vote attribution + re-id stitch + scene-phase. (Phase 2)
3. momentscan `viz.py`: trace.mp4 + report.html from stash. (Phase 2)
4. First real run on `~/Videos/reaction_test` → tubelets + trace + report; eyeball track purity.

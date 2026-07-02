# momentscan — setup & layout

The domain intent (what momentscan analyzes and why) lives in
[`README.md`](README.md). This file documents the *repo's layout and
how to run things*. Both files matter; read this one when you want
to run code, the other when you want to understand the analysis.

## Reoriented (2026-06-08)

This repo is now the JEPA-PoC Track A/B **selection + eval** site
([`docs/jepa-poc.md`](docs/jepa-poc.md)). The previous single-process
``momentscan-worker`` is archived under ``_legacy/`` (preserved, not deleted).
The new structure is a flat shared core + two **isolated** FeatureSource
packages; the pipeline stages are skeletons, wired phase by phase (README 진행 상태).

## Repository layout

```
momentscan/
├── pyproject.toml                    uv workspace root; path-deps to visualstack
├── README.md                         domain design intent + Distribution contract
├── docs/jepa-poc.md                  north-star: PoC goal, two tracks, decisions
├── SETUP.md                          you are here — code layout
├── policies/                         domain policy JSON (reused)
├── _legacy/momentscan-worker/        archived pre-reorientation worker
├── apps/
│   └── momentscan/                   CORE (light, shared) — track-agnostic
│       └── src/momentscan/
│           ├── features.py           FeatureSource Protocol + Tubelet/TrackFeatures (contract)
│           ├── telemetry.py          CandidateLog schema (§8 contract)
│           ├── tubelets.py           Step 0: tracks + attribution         (Phase 2)
│           ├── select.py             center→Profile · residual→Highlight  (Phase 3)
│           ├── evalharness.py        shared eval harness                  (Phase 3)
│           └── __main__.py           CLI: step0 / features / select / eval
└── plugins/                          ISOLATED FeatureSource packages (own venvs)
    ├── features-specialist45d/       Track A — specialist 45D (onnx/mediapipe)
    └── features-vjepa/               Track B — V-JEPA (torch; optional `backbone` extra)
```

> The two `plugins/` packages are isolated *only* at the feature-extractor
> boundary, where deps conflict (onnx/mediapipe vs torch). Everything downstream
> is the shared core — that is what keeps Track A vs Track B directly comparable.
> The "Run a job" sections below describe the **archived** `_legacy` worker and
> will be re-wired per phase.

## Sibling layout

This repo expects to sit next to visualstack:

```
~/repo/...
├── visualstack/                 the OSS substrate
└── momentscan/                  this repo
```

Path dependencies in `pyproject.toml` resolve `../visualstack/...`.
If you place the repos differently, edit `[tool.uv.sources]` to point
at the right location.

## Install

```bash
uv sync           # one-shot, resolves visualstack via editable path deps
```

This installs every visualstack sub-package as an editable
dependency, so changes to visualstack source are picked up immediately
without re-syncing.

## Run a job (local)

```bash
# Process one video. Output goes to ./output/<job-id>/stash/...parquet.
uv run momentscan-worker /path/to/video.mp4

# With an explicit job id (matches whatever your orchestrator uses):
uv run momentscan-worker /path/to/video.mp4 --job-id abc123

# Long-running worker — expose Prometheus + UDS control for debugging:
uv run momentscan-worker /path/to/video.mp4 --metrics --control
```

The worker prints **one JSON line on stdout** (the orchestrator
parses this) and **structured JSON logs on stderr** (Loki / Promtail
collects these).

stdout result line:

```json
{"job_id":"abc123","ok":true,"duration_seconds":4.21,"partitions_written":12,
 "error":null,"stash_dir":"/.../output/abc123/stash"}
```

stderr log line (one per logging event):

```json
{"ts":"2026-05-14T...","level":"INFO","logger":"momentscan.worker",
 "msg":"job done","service":"momentscan","worker_id":"w-local","hostname":"...",
 "job_id":"abc123","file_path":"/path/to/video.mp4",
 "duration_s":4.21,"partitions_written":12}
```

## Where does output go

```
<output_dir>/<job_id>/
└── stash/
    ├── 0/detections.parquet
    ├── 1/detections.parquet
    └── ...
```

Each `detections.parquet` is one partition's flat rows (one row per
detection per frame, augmented with `expression__smile` per
detection). Read with polars / DuckDB / pandas:

```python
import polars as pl
df = pl.read_parquet("output/abc123/stash/0/detections.parquet")
```

Schema is the same as visualstack's stash output — see
[`visualstack/docs/applications.md`](../visualstack/docs/applications.md)
for the column conventions.

## Where does the pipeline live

[`apps/momentscan-worker/src/momentscan_worker/service.py`](apps/momentscan-worker/src/momentscan_worker/service.py)
— `build_pipeline()` lists exactly which modules a job runs.
Currently:

```python
Pipeline([
    FaceDetect(...),
    IoUTracker(),
    FaceExpression(),
    SmilingCloseup(...),
])
```

Domain-specific composers (a `MomentScanScorer` consuming face
detections + expression scores) go here as they're written, then
move to `plugins/` once they accumulate enough surface to be reused.

## Running a fleet (10 servers)

See [`visualstack/docs/applications.md`](../visualstack/docs/applications.md)
for the production deployment story — job queue (RQ / Celery /
Postgres-as-queue), systemd unit template, Prometheus scrape config,
Grafana dashboard variables.

## Useful adjacent tools

- `python -m visualbus.control stats --socket <path>` — query a running
  worker (when `--control` is on).
- `python -m visualbus.control subscribe 'patterns=["signal/*","trigger/*"]' | jq .`
  — live stream of every signal / trigger flowing through a worker.
- `curl localhost:9100/metrics | grep visualstack_` — scrape Prometheus
  metrics (when `--metrics` is on).

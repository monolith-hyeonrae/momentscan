# momentscan — setup & layout

The domain intent (what momentscan analyzes and why) lives in
[`README.md`](README.md). This file documents *how to run things*.
Layer map and boundary contracts: [`ARCHITECTURE.md`](ARCHITECTURE.md) ·
[`docs/contracts.md`](docs/contracts.md). Directory map: README §디렉토리 지도.

## Quickstart (first 15 minutes)

```bash
uv sync                                  # workspace + plugins + visualstack (editable)
uv run momentscan verify doctor          # external deps census — models·binaries·stacks
                                         #   (checker, not fetcher: gated weights say how to obtain)
uv run momentscan run /path/video.mp4    # ONE command: inline detect → full pipeline → report
# → output/<clip>/index.html             deliverables front door
# → output/<clip>/inspect/clip.html      the inspector — WHY each pick was made
```

History in one line: reoriented 2026-06-08 (JEPA-PoC Track A/B), migrated into
the p981 meta-repo 2026-07-07 — the trail lives in `docs/`.

## Sibling layout

This repo expects the visualstack substrate next door:

```
~/repo/p981/
├── visualstack/                 vision substrate (visualbus · visualpath · plugins)
└── momentscan/                  this repo
```

Path dependencies in `pyproject.toml` resolve `../visualstack/...` as editable —
changes to visualstack source are picked up without re-syncing. If you place the
repos differently, edit `[tool.uv.sources]`.

## Run

```bash
uv run momentscan run <clip> [--only <stage> ...] [--force] [--source <video>]
uv run momentscan server start [--port N] [--eureka URL] [--control-url URL] \
                               [--s3-bucket B] [--output-uri s3://…]   # HTTP worker face
uv run momentscan server status|stop
uv run momentscan verify registry|api|replay|eval    # declaration·contract·regression gates
uv run momentscan map|report|inspect|viz             # maps · result pages · inspector
```

- The server face (Eureka registration, company dispatch dialect, S3 in/out) is
  documented in [`docs/deploy-alpha.md`](docs/deploy-alpha.md); the container
  path (image + weights bundle + compose) in `deploy/docker/` and the DevOps
  launch contract in [`docs/deploy-handoff.md`](docs/deploy-handoff.md).
- Long-running local server: `setsid nohup … &` (session-teardown safe) — or the
  container, which is the deployment reference.

## Where output goes

`output/<clip>/` — stage artifacts (parquet·json), `index.html` (report),
`inspect/clip.html` (inspector). Only files declared as product egress
AND belonging to an open product (`--products`) are exported outward.

## Useful adjacent tools

- `python -m visualbus.control stats --socket <path>` — query a running daemon.
- `python -m visualbus.control subscribe 'patterns=["signal/*","trigger/*"]' | jq .`
  — live stream of signals/triggers through a worker.
- Observability (Grafana + Loki + promtail, local stack):
  [`docs/deploy-alpha.md`](docs/deploy-alpha.md) §5.

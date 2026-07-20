> ⚠ 이 문서의 최신성 주의 — 제품 산출물 스키마의 권위는 [`contracts.md`](contracts.md)
> (likeness.json = C11 동결). 이 문서는 stash 레이아웃/스테이지 분리 서술.

# Data contract (Phase 1)

The PoC instantiation of the storage model. Schemas are authoritative in
[`apps/momentscan/src/momentscan/infra/store/stash.py`](../apps/momentscan/src/momentscan/infra/store/stash.py)
(column maps) and [`ports.py`](../apps/momentscan/src/momentscan/infra/store/ports.py)
(`Tubelet` / `TrackFeatures`). This doc is the narrative + the `Distribution`
contract (which lives in visualstack and can't be enforced from here).

## Stages decoupled by stash

Three stages, each in its own process / venv, joined only by files. The clip id
keys everything; `(clip_id, track_id, rider_role)` threads through all of it.

```
clip ─Step0─▶ tubelets.parquet ─extractor─▶ features/{A,B}.parquet ─select─▶ candidates.jsonl ─eval─▶ metrics
```

```
stash/{clip_id}/
├── tubelets.parquet           one row per (track_id, frame); riders only (bystanders dropped)
├── features/A.parquet         Track A — specialist 45D  (one row per track_id,frame)
├── features/B.parquet         Track B — V-JEPA          (same layout, different feature_space)
└── candidates.jsonl           one CandidateLog per line
```

Why files, not one process: an extractor's heavy venv (onnx/mediapipe or torch)
never has to coexist with the other's, and Phase-3 selection re-runs cheaply over
stashed features without re-touching the GPU. This is the same decoupling that
removes the legacy bus-timing hack.

## Decided defaults (Phase 1)

- **tubelets grain** = flat, one row per track-frame, `rider_role` denormalized.
  (Tiny table; groupby `track_id` = a tubelet. No nested/2-table split for the PoC.)
- **feature storage** = parquet `list<float32>` per frame. One format for both
  tracks → directly comparable. (Not `.npz`; keeps it queryable in polars/duckdb.)
- **candidate-log** = `jsonl` (append-friendly, telemetry-shaped; §8).
- **missing signal** = `NaN` in the vector, never a dropped row.

## `Distribution` contract (visualstack-side; decided here)

The shared Layer-2 object — **one protocol, parametrized by feature space (`dim`)**.
Both tracks instantiate it; only `dim` (and the metric) differ.

```
Distribution(dim, *, robust=True)
  merge(other)        ⊕  — associative, has identity; incremental update is free.
  center() -> vec     ROBUST per-dim (trimmed mean / median), NOT plain Welford
                      mean. = identity reference (Profile) AND empirical frontal
                      for this off-axis camera (jepa-poc A3).
  distance(point)     deviation reading; the base for the Highlight residual.
```

Two hard requirements from this session (jepa-poc Appendix A4):

1. **NaN-tolerant per dim.** A partial vector updates the dims it has and skips
   only those dims — it must **never** drop the whole frame. (This is exactly the
   legacy `n=0` bug: "any-NaN-column ⇒ skip-frame" is forbidden.)
2. **Robust center.** Occluded / outlier frames are down-weighted by the
   trimmed-mean / median — so there is **no separate occlusion detector**.

**Metric.** Low-D (Track A, 45D): dynamic-95%-PCA whitened Mahalanobis — reuse
the existing `signal.py` path. High-D (Track B, V-JEPA): the PCA reduction keeps
Mahalanobis tractable; cosine-to-centroid is the fallback. **Exact high-D metric
deferred to Phase 4.**

## Highlight ≠ distance alone

`distance` is the *base*. `select.py` forms the **conditional residual**: subtract
a scene/nuisance model (global motion + brightness) from per-track embedding
change; peaks of the residual = highlight (jepa-poc §5). The Distribution provides
the deviation; the nuisance conditioning lives in `select.py`.

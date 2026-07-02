"""Pipeline runner — makes the analyzer registry LIVE. It sequences the stage/
engine analyzers in dependency order (`analyzers.topo_order`) and runs each,
SKIPPING any whose artifact already exists (resumable). The registry stops being
only a catalog and becomes the execution plan — add an analyzer + a STEP entry,
and it runs in the right place automatically.

`detect`/`landmarks` are upstream of this runner (warm-daemon / step0); it covers
everything after the stash's detections + landmarks exist.
"""
from __future__ import annotations

import datetime
import logging
import time
from pathlib import Path

from momentscan import analyzers
from momentscan.verify import freshness
from momentscan.stash import clip_dir, provenance_path, write_provenance, write_run

log = logging.getLogger("momentscan.pipeline")


def _attribute(out, clip, src, fps):
    from momentscan.stages.attribute import attribute_clip
    return attribute_clip(src, out, fps=fps)


def _tubelets(out, clip, src, fps):
    from momentscan.stages.tubelets import synthesize_tubelets
    return synthesize_tubelets(src, out, fps=fps)


def _scene(out, clip, src, fps):
    from momentscan.stages.scene import extract_scene
    return extract_scene(src, out, fps=fps)


def _features(out, clip, src, fps):
    from momentscan.stages.features import extract_features
    return extract_features(src, out, fps=fps)


def _crops(out, clip, src, fps):
    from momentscan.stages.crops import extract_crops
    return extract_crops(src, out, clip, fps=fps)


def _parse(out, clip, src, fps):
    from momentscan.stages.parse import extract_parse
    return extract_parse(out, clip, fps=fps)


def _fashion(out, clip, src, fps):
    from momentscan.stages.fashion import extract_fashion
    return extract_fashion(out, clip, fps=fps)


def _headpose(out, clip, src, fps):
    from momentscan.stages.headpose import extract_headpose
    return extract_headpose(out, clip, fps=fps)


def _emotion(out, clip, src, fps):
    from momentscan.domains.emotion import extract_emotion
    return extract_emotion(out, clip, fps=fps)


def _portrait(out, clip, src, fps):
    from momentscan.products.portrait import select_portrait
    return select_portrait(out, clip, fps=fps)


def _likeness(out, clip, src, fps):
    from momentscan.products.appearance import appearance_clip
    return appearance_clip(out, clip)


def _select(out, clip, src, fps):
    from momentscan.products.select import select_clip
    return select_clip(out, clip, fps=fps)


# detect/landmarks run UPSTREAM of this runner (warm-daemon / step0), so they are
# intentionally NOT in STEPS. Declared here (not left implicit in the `a.name in
# STEPS` filter) so `momentscan check` can tell an intentional exclusion from an
# analyzer someone forgot to wire — the latter would silently never run.
UPSTREAM_OF_RUNNER = ("detect", "landmarks")

# name → (existence-probe relpath, runner). The probe is the concrete file stat'd
# for resumability — a stash-LAYOUT fact distinct from the analyzer's logical
# `artifact` (a directory like "crops/" needs a sentinel; "features/A.parquet" a
# representative track). MEMBERSHIP + ORDER + needs_source now DERIVE from ANALYZERS
# (the single authority — see run_pipeline); RUNNERS carries only the irreducible
# code + probe path that cannot live in the import-light catalog.
RUNNERS = {
    "attribute": ("attribution.json", _attribute),
    "tubelets":  ("tubelets.parquet", _tubelets),
    "scene":     ("scene.parquet", _scene),
    "features":  ("features/A.parquet", _features),
    "crops":     ("crops/manifest.json", _crops),
    "parse":     ("parse.parquet", _parse),
    "fashion":   ("fashion.json", _fashion),
    "headpose6d": ("headpose.parquet", _headpose),
    "emotion":   ("emotion.json", _emotion),
    "portrait":  ("portraits/portrait.json", _portrait),
    "likeness":  ("likeness.json", _likeness),
    "select":    ("candidates.jsonl", _select),
}

# every runner must declare its source module, so freshness can detect a stale
# artifact (source edited after the artifact was written). Drift = loud at import.
assert set(freshness.STAGE_MODULE) == set(RUNNERS), (
    "freshness.STAGE_MODULE ⇄ RUNNERS drift: "
    f"{set(freshness.STAGE_MODULE) ^ set(RUNNERS)}")


def _stage_health(name: str, r) -> str:
    """One-line health for the watch-log — surfaces the ②GATE moment + a wing-tilt flag."""
    if not isinstance(r, dict):
        return ""
    if name == "portrait":                                   # gate ② + extraction ③
        riders = r.get("riders", {}) or {}
        adm = sum(int(v.get("n_admit", 0) or 0) for v in riders.values())
        tot = sum(int(v.get("n_total", 0) or 0) for v in riders.values())
        npng = sum(len(v.get("extracted", []) or []) for v in riders.values())
        tilt = "  ⚠ low-admit" if tot and adm / tot < 0.30 else ""
        return f"② gate admit {adm}/{tot} → ③ {npng} png{tilt}"
    for k in ("n_segs", "n_subjects", "n_frames", "n_candidates"):
        if k in r:
            return f"{k}={r[k]}"
    return ""


def run_pipeline(out_root, clip_id: str, *, source=None, fps: int = 6,
                 force: bool = False, only=None, watch: bool = True) -> dict:
    """Run post-detect stages in registry DAG order; skip existing artifacts."""
    cdir = clip_dir(Path(out_root), clip_id)
    _t_start, _started_unix = time.perf_counter(), round(time.time(), 3)
    _started_iso = datetime.datetime.now().isoformat(timespec="seconds")
    # provenance — what source produced these artifacts, when, with what fps. The
    # Storage port's audit/idempotency seam (source media expires; this is durable).
    # Per-clip only; nothing accumulates across visits. Written once, when a source
    # is supplied and not already recorded.
    if source and not provenance_path(out_root, clip_id).exists():
        rec = {"clip_id": clip_id, "source_uri": str(source), "fps": fps,
               "processed_at_unix": round(time.time(), 3),
               "processed_at_iso": datetime.datetime.now().isoformat(timespec="seconds")}
        _src = Path(source)
        if _src.exists():
            _st = _src.stat()
            rec["source_bytes"] = _st.st_size
            rec["source_mtime"] = round(_st.st_mtime, 3)
        write_provenance(out_root, clip_id, rec)
    # the run set DERIVES from ANALYZERS (the single authority): every stage/engine
    # analyzer except the frame-grain ingest (UPSTREAM_OF_RUNNER) runs, in DAG order.
    # No hand-kept membership list — a new analyzer with a RUNNERS entry runs
    # automatically; one without a runner is caught by `momentscan check`, never
    # silently dropped.
    order = [a for a in analyzers.topo_order()
             if a.kind in ("stage", "engine") and a.name not in UPSTREAM_OF_RUNNER]
    if only:
        order = [a for a in order if a.name in only]
    # CASCADE ORDER (the big-frame you watch run): all FEATURE-EXTRACTION (kind 'stage')
    # before PRODUCT engines (kind 'engine'), so execution AND the watch-log read as the
    # ①FEATURE → ③PRODUCT cascade — not the dependency-topo interleave (select used to run
    # mid-measurement). Dependency-safe: engines depend only on stages, which all run first.
    order = ([a for a in order if a.kind == "stage"]
             + [a for a in order if a.kind == "engine"])
    result = {"clip_id": clip_id, "ran": [], "skipped": [], "failed": []}
    phase = None
    for a in order:
        if watch and a.kind != phase:                     # crossed a cascade boundary
            phase = a.kind
            print("\n═══ " + ("① FEATURE EXTRACTION" if phase == "stage"
                              else "③ PRODUCT  (gate ② runs inside portrait)") + " ═══", flush=True)
        if a.name not in RUNNERS:
            result["skipped"].append({"name": a.name, "reason": "no runner (see momentscan check)"})
            if watch: print(f"  {a.name:11} — no runner", flush=True)
            continue
        probe, fn = RUNNERS[a.name]
        # resumable AND incremental: skip only if the artifact exists and is NEWER
        # than its source. A code edit (source mtime > artifact) re-runs the stage.
        stale = False
        if (cdir / probe).exists() and not force:
            if not freshness.is_stale(cdir / probe, freshness.STAGE_MODULE.get(a.name, "")):
                result["skipped"].append({"name": a.name, "reason": "exists"})
                if watch: print(f"  {a.name:11} · cached (fresh)", flush=True)
                continue
            stale = True
        if a.needs_source and not source:
            result["skipped"].append({"name": a.name, "reason": "needs --source"})
            if watch: print(f"  {a.name:11} · needs --source", flush=True)
            continue
        t0 = time.perf_counter()
        try:
            r = fn(out_root, clip_id, source, fps)
            ok = r.get("ok", True) if isinstance(r, dict) else True
            ms = int((time.perf_counter() - t0) * 1000)
            (result["ran"] if ok else result["failed"]).append(
                {"name": a.name, "ok": ok, "ms": ms,
                 "reason": ("stale: source changed" if (ok and stale)
                            else (None if ok else (r.get("reason") if isinstance(r, dict) else None)))})
            if watch:
                print(f"  {a.name:11} {'✓' if ok else '✗'} {ms:>6}ms  "
                      f"{_stage_health(a.name, r)}{'  (stale→reran)' if stale and ok else ''}", flush=True)
        except ImportError as e:
            result["skipped"].append({"name": a.name, "reason": f"dep missing: {e}"})
            if watch: print(f"  {a.name:11} · dep missing: {e}", flush=True)
        except Exception as e:  # noqa: BLE001 — record and continue; downstream will also report
            result["failed"].append({"name": a.name, "error": str(e)})
            if watch: print(f"  {a.name:11} ✗ ERROR: {e}", flush=True)
        log.info("pipeline.step", extra={"clip_id": clip_id, "step": a.name})
    log.info("pipeline.done", extra={"clip_id": clip_id, "ran": len(result["ran"]),
                                     "skipped": len(result["skipped"]), "failed": len(result["failed"])})
    # run.json — the per-clip RUN trace (what ran / how long / what failed): the
    # operational complement to provenance.json's run-identity. The per-stage record
    # already lives in `result`; persist it, folded to ONE DAG-ordered stages list
    # (each name a declared-graph node). Last-run-wins.
    _outcome: dict = {}
    for e in result["ran"]:
        _outcome[e["name"]] = {"name": e["name"], "status": "ran", "ms": e["ms"], "ok": e["ok"], "reason": e.get("reason")}
    for e in result["skipped"]:
        _outcome[e["name"]] = {"name": e["name"], "status": "skipped", "ms": None, "ok": None, "reason": e.get("reason")}
    for e in result["failed"]:
        _outcome[e["name"]] = {"name": e["name"], "status": "failed", "ms": e.get("ms"), "ok": False,
                               "reason": e.get("reason") or e.get("error")}
    write_run(out_root, clip_id, {
        "clip_id": clip_id, "fps": fps, "force": force, "only": sorted(only) if only else None,
        "started_at_unix": _started_unix, "started_at_iso": _started_iso,
        "elapsed_ms": int((time.perf_counter() - _t_start) * 1000),
        "stages": [_outcome[a.name] for a in order if a.name in _outcome],
        "n_ran": len(result["ran"]), "n_skipped": len(result["skipped"]), "n_failed": len(result["failed"]),
    })
    return result

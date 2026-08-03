"""Pipeline runner — makes the analyzer registry LIVE. It sequences the stage/
engine analyzers in dependency order (`registry.topo_order`) and runs each,
SKIPPING any whose artifact already exists (resumable). The registry stops being
only a catalog and becomes the execution plan — add an analyzer + a STEP entry,
and it runs in the right place automatically.

`detect`/`landmarks` are upstream of this runner (warm-daemon / step0); it covers
everything after the stash's detections + landmarks exist.
"""
from __future__ import annotations

import datetime
import hashlib
import logging
import time
from pathlib import Path

from momentscan.infra.pipeline import freshness, registry
from momentscan.infra.store.stash import clip_dir, provenance_path, write_manifest, write_provenance, write_run

log = logging.getLogger("momentscan.pipeline")


def _attribute(out, clip, src, fps):
    # SubjectQuery dispatch (contracts C2): the Job's query picks WHO this run is
    # about. seat_rule = the depth-vote default; reference_face = a photo. Every
    # strategy emits the SAME attribution.json shape → downstream unchanged (C3).
    from momentscan.infra.store.stash import read_job

    from momentscan.perception.subjects.query import parse_subject_query
    q = parse_subject_query(((read_job(out, clip) or {}).get("subject_query")))
    if q["strategy"] == "reference_face":
        from momentscan.perception.subjects.query import resolve_reference_face
        return resolve_reference_face(out, clip, q["params"]["ref"])
    from momentscan.perception.subjects.attribute import attribute_clip
    return attribute_clip(src, out, fps=fps)


def _tubelets(out, clip, src, fps):
    from momentscan.perception.subjects.tubelets import synthesize_tubelets
    return synthesize_tubelets(src, out, fps=fps)


def _scene(out, clip, src, fps):
    from momentscan.perception.extraction.scene import extract_scene
    return extract_scene(src, out, fps=fps)


def _features(out, clip, src, fps):
    from momentscan.perception.extraction.features import extract_features
    return extract_features(src, out, fps=fps)


def _crops(out, clip, src, fps):
    from momentscan.perception.subjects.crops import extract_crops
    return extract_crops(src, out, clip, fps=fps)


def _parse(out, clip, src, fps):
    from momentscan.perception.extraction.parse import extract_parse
    return extract_parse(out, clip, fps=fps)


def _fashion(out, clip, src, fps):
    from momentscan.perception.extraction.fashion import extract_fashion
    return extract_fashion(out, clip, fps=fps)


def _headpose(out, clip, src, fps):
    from momentscan.perception.extraction.headpose import extract_headpose
    return extract_headpose(out, clip, fps=fps)


def _emotion(out, clip, src, fps):
    from momentscan.perception.readings.emotion import extract_emotion
    return extract_emotion(out, clip, fps=fps)


def _gates(out, clip, src, fps):
    from momentscan.perception.gates import run_gates
    return run_gates(out, clip, fps=fps)


def _portrait(out, clip, src, fps):
    from momentscan.products.portrait import select_portrait
    return select_portrait(out, clip, fps=fps)


def _likeness(out, clip, src, fps):
    from momentscan.products.likeness import appearance_clip
    return appearance_clip(out, clip, fps=fps)


def _recipe(out, clip, src, fps):
    from momentscan.products.recipe import recipe_clip
    return recipe_clip(out, clip)


def _select(out, clip, src, fps):
    from momentscan.products.select import select_clip
    return select_clip(out, clip, fps=fps)


def _highlight(out, clip, src, fps):
    from momentscan.products.highlight import highlight_clip
    return highlight_clip(out, clip, fps=fps)


# detect/landmarks run UPSTREAM of this runner (warm-daemon / step0), so they are
# intentionally NOT in STEPS. Declared here (not left implicit in the `a.name in
# STEPS` filter) so `momentscan verify registry` can tell an intentional exclusion from an
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
    "gates":     ("gate_trace.parquet", _gates),   # R10: the decision layer is a STAGE (measurement), not a step inside portrait
    "portrait":  ("portraits/portrait.json", _portrait),
    "likeness":  ("likeness.json", _likeness),
    "recipe":    ("recipe/manifest.json", _recipe),   # per-rider recipe.json + manifest (probe); likeness.json → face recipe 사상
    "select":    ("select.json", _select),   # own artifact — candidates.jsonl is SHARED (portrait creates it first → false skip)
    "highlight": ("highlight.json", _highlight),   # 2026-07-03 졸업 — 제품 파일 + 자기 산출물
}


def _upstream_probes(name: str) -> tuple[str, ...]:
    """R5 artifact-edge: 직접 선언 상류(registry.depends)의 대표 산출물 경로.

    RUNNERS 상류 → 그 probe (공유 candidates.jsonl이 아니라 자기-산출물 —
    sibling-write 거짓-stale 가드) · UPSTREAM_OF_RUNNER(detect/landmarks) →
    선언 artifact · unit(inline)은 제외. **직접 간선만** — 연쇄는 한 런의
    topo 순서가 자연 전파한다(상류가 재실행되면 산출물이 새로워져 다음
    소비자가 같은 런에서 stale로 판정)."""
    try:
        a = registry.get(name)
    except KeyError:
        return ()
    out: list[str] = []
    for d in a.depends:
        if d in RUNNERS:
            out.append(RUNNERS[d][0])
        else:
            try:
                art = registry.get(d).artifact
            except KeyError:
                continue
            if art and art != "inline":
                out.append(art)
    return tuple(out)


# every runner must declare its source module, so freshness can detect a stale
# artifact (source edited after the artifact was written). Drift = loud at import.
assert set(freshness.STAGE_MODULE) == set(RUNNERS), (
    "freshness.STAGE_MODULE ⇄ RUNNERS drift: "
    f"{set(freshness.STAGE_MODULE) ^ set(RUNNERS)}")
# ...and every declared module path must RESOLVE. A dangling path (typo, file
# move) makes _origin()→None → source_mtime 0.0 → is_stale 항상 False — freshness가
# 에러 없이 실명하는 최악의 무증상 모드 (2026-07-15 구조 감사 D1). 이동/개명은
# 여기서 시끄럽게 죽는다.
_dangling = {s: m for s, m in freshness.STAGE_MODULE.items()
             if freshness._origin(m) is None}
assert not _dangling, f"freshness.STAGE_MODULE에 해석 불가 모듈 경로: {_dangling}"


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


def _scoped_order(order, only, products):
    """Restrict the DAG order to a stage set (`only`) or the union of the requested
    products' closures (`products`, R11 — registry.product_closure). No scope → unchanged."""
    if only:
        return [a for a in order if a.name in only]
    if not products:
        return order

    known = {p.name for p in registry.products()}
    bad = [p for p in products if p not in known]
    if bad:
        raise ValueError(f"run_pipeline: unknown products {bad} (known: {sorted(known)})")

    want = set().union(*(registry.product_closure(p) for p in products))
    return [a for a in order if a.name in want]


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_pipeline(out_root, clip_id: str, *, source=None, fps: int = 6,
                 force: bool = False, only=None, products=None, watch: bool = True,
                 subject_query: str | None = None,
                 source_origin: str | None = None) -> dict:
    """Run post-detect stages in registry DAG order; skip existing artifacts.

    `only` restricts to named stages; `products` restricts to the union of the named
    products' closures (registry.product_closure — R11). The two are mutually exclusive
    (fail-fast: a run is either stage-scoped or product-scoped, never both)."""
    if only and products:
        raise ValueError(
            f"run_pipeline: --only and --product are mutually exclusive "
            f"(only={sorted(only)}, products={sorted(products)})")
    cdir = clip_dir(Path(out_root), clip_id)
    if subject_query:   # the REQUEST record (C1 Job) — attribute dispatches on it
        from momentscan.infra.store.stash import write_job
        write_job(out_root, clip_id, {"clip_id": clip_id, "subject_query": subject_query,
                                      "fps": fps, "source": str(source) if source else None})
    _t_start, _started_unix = time.perf_counter(), round(time.time(), 3)
    _started_iso = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    # provenance — what source produced these artifacts, when, with what fps. The
    # Storage port's audit/idempotency seam (source media expires; this is durable).
    # Per-clip only; nothing accumulates across visits. Written once, when a source
    # is supplied and not already recorded. source_uri = the file actually opened
    # (may be a local source_cache copy); source_origin = the URI the job named
    # (e.g. the S3 key — survives cache eviction); source_sha256 = fingerprint of
    # the processed bytes (transport-independent identity).
    if source and not provenance_path(out_root, clip_id).exists():
        rec = {"clip_id": clip_id, "source_uri": str(source),
               "source_origin": str(source_origin) if source_origin else str(source),
               "fps": fps,
               "processed_at_unix": round(time.time(), 3),
               "processed_at_iso": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
        _src = Path(source)
        if _src.exists():
            _st = _src.stat()
            rec["source_bytes"] = _st.st_size
            rec["source_mtime"] = round(_st.st_mtime, 3)
            rec["source_sha256"] = _sha256(_src)
        write_provenance(out_root, clip_id, rec)
    # the run set DERIVES from ANALYZERS (the single authority): every stage/engine
    # analyzer except the frame-grain ingest (UPSTREAM_OF_RUNNER) runs, in DAG order.
    # No hand-kept membership list — a new analyzer with a RUNNERS entry runs
    # automatically; one without a runner is caught by `momentscan verify registry`, never
    # silently dropped.
    order = [a for a in registry.topo_order()
             if a.kind in ("stage", "engine") and a.name not in UPSTREAM_OF_RUNNER]
    order = _scoped_order(order, only, products)
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
            print("\n═══ " + ("① FEATURE EXTRACTION  (incl. ② the gates stage)" if phase == "stage"
                              else "③ PRODUCT  (reads the ② gate trace)") + " ═══", flush=True)
        if a.name not in RUNNERS:
            result["skipped"].append({"name": a.name, "reason": "no runner (see momentscan verify registry)"})
            if watch: print(f"  {a.name:11} — no runner", flush=True)
            continue
        probe, fn = RUNNERS[a.name]
        # resumable AND incremental: skip only if the artifact exists and is NEWER
        # than BOTH its source (code edit) and its direct upstream artifacts
        # (R5 artifact-edge — 상류 재기록이 하류를 stale시켜야 한다; 갭 3회 실증).
        stale = False
        stale_why = ""
        art = cdir / probe
        if art.exists() and not force:
            code_stale = freshness.is_stale(art, freshness.STAGE_MODULE.get(a.name, ""))
            up_mtimes = [p.stat().st_mtime
                         for p in (cdir / u for u in _upstream_probes(a.name)) if p.exists()]
            art_stale = freshness.artifact_stale(art.stat().st_mtime, up_mtimes)
            if not code_stale and not art_stale:
                result["skipped"].append({"name": a.name, "reason": "exists"})
                if watch: print(f"  {a.name:11} · cached (fresh)", flush=True)
                continue
            stale = True
            stale_why = ("source+upstream" if code_stale and art_stale
                         else "upstream artifact newer" if art_stale else "source changed")
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
                 "reason": (f"stale: {stale_why}" if (ok and stale)
                            else (None if ok else (r.get("reason") if isinstance(r, dict) else None)))})
            if watch:
                print(f"  {a.name:11} {'✓' if ok else '✗'} {ms:>6}ms  "
                      f"{_stage_health(a.name, r)}{f'  (stale→reran: {stale_why})' if stale and ok else ''}", flush=True)
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
        "products": sorted(products) if products else None,
        "started_at_unix": _started_unix, "started_at_iso": _started_iso,
        "elapsed_ms": int((time.perf_counter() - _t_start) * 1000),
        "stages": [_outcome[a.name] for a in order if a.name in _outcome],
        "n_ran": len(result["ran"]), "n_skipped": len(result["skipped"]), "n_failed": len(result["failed"]),
    })
    # R12 — 산출물 tier 지도. report·운영이 "이 파일은 무엇인가"를 선언으로 답한다.
    write_manifest(out_root, clip_id, {
        "schema": "momentscan.manifest/v0",
        "tiers": registry.classify_clip_files(cdir)})
    return result

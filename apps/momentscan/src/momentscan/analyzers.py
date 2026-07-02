"""Analyzer registry — the producer catalog under the S2 substrate.

`registry.py` lists the *output fields* of one stage (the 67D feature vector);
this lists the *producers*: every unit analyzer (a pure fn in signals.py over an
already-extracted stream) and every stage analyzer (a model → a stash artifact),
each declaring its model, inputs, output-kind, artifact, and upstream `depends`.

Borrows the legacy's good ideas (declared deps → a dependency DAG; declared
capabilities; a discoverable catalog) WITHOUT its entry-point-plugin machinery —
a static, readable declaration instead. One place answers "what analyzers exist,
what does each produce, in what order do they run, and how is each rendered."

OUTPUT_KINDS drive generic consumption (e.g. the inspector renders a `timeline`
as a line lane, a `categorical` as a colour strip — analyzer ③).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# how a producer's output is shaped — the contract consumers render/read against.
OUTPUT_KINDS = (
    "timeline",     # per-frame continuous scalar(s) over the tubelet
    "categorical",  # per-frame discrete class (gate reason, track fragment)
    "embedding",    # per-frame vector
    "region",       # per-frame region fractions (segmentation)
    "aggregate",    # one visit-invariant conclusion per subject
    "selection",    # a product output (picked frames / segments)
)


@dataclass(frozen=True)
class Analyzer:
    name: str
    kind: str                       # "unit" (signals.py fn) | "stage" (model→artifact) | "engine" (product)
    model: str                      # model / method behind it
    inputs: tuple[str, ...]         # streams / artifacts it reads
    output_kind: str                # one of OUTPUT_KINDS
    produces: tuple[str, ...]       # signal / field / file names it emits
    artifact: str                   # stash artifact, or "inline" for unit fns
    depends: tuple[str, ...] = ()   # upstream analyzer names (the DAG edges)
    note: str = ""
    needs_source: bool = False      # True = reads the raw video → run_pipeline must pass --source


ANALYZERS: tuple[Analyzer, ...] = (
    # ── stages: model → stash artifact ──────────────────────────────────────
    Analyzer("detect", "stage", "FaceDetect + IoUTracker (ArcFace emb)", ("frames",),
             "timeline", ("bbox", "embedding", "track_id", "subject_id"), "detections.parquet",
             (), "track_id online; subject_id = clip-end re-id stitch"),
    Analyzer("landmarks", "stage", "MediaPipe FaceMesh", ("frames", "detect"),
             "timeline", ("blendshapes", "transform", "crop_box"), "landmarks.parquet", ("detect",)),
    Analyzer("attribute", "stage", "depth (step0b)", ("detect",),
             "aggregate", ("rider_role", "depth"), "attribution.json", ("detect",),
             "main/aux = depth vote, not size", needs_source=True),
    Analyzer("tubelets", "stage", "synthesis", ("detect", "attribute"),
             "timeline", ("tubelets",), "tubelets.parquet", ("detect", "attribute"),
             "subject-keyed spatio-temporal volume", needs_source=True),
    Analyzer("scene", "stage", "DINOv3", ("frames", "tubelets"),
             "embedding", ("cls", "customer_embedding", "bg_embedding"), "scene.parquet", ("tubelets",),
             "node: extraction/scene.py → backend: plugins/features-specialist45d (isolated)", needs_source=True),
    Analyzer("features", "stage", "HSEmotion + LibreFace + MediaPipe + DPR-SH + pixel", ("tubelets",),
             "timeline", ("registry.py FIELDS (67D)",), "features.parquet", ("tubelets",),
             "node: extraction/features.py → backend: plugins/features-specialist45d (isolated)", needs_source=True),
    Analyzer("crops", "stage", "ffmpeg crop track (clean)", ("tubelets", "source"),
             "selection", ("crop track s{sid}.mp4", "manifest.json"), "crops/", ("tubelets",),
             "data-retention: source expires; crops persist", needs_source=True),
    Analyzer("parse", "stage", "landmark soft-Gaussian quality + SegFormer occlusion",
             ("crops", "landmarks", "detect"),
             "region", ("skin_entropy", "skin_lum", "face_micro", "eye_lum_rel",
                        "mouth_vis", "glasses_frac", "hat_frac", "cloth_frac"),
             "parse.parquet", ("crops", "landmarks", "detect"),
             "QUALITY=landmark Gaussian region; occlusion/fashion=SegFormer (deferred→FashionCLIP)"),
    Analyzer("fashion", "stage", "FashionCLIP (patrickjohncyh)", ("crops",),
             "aggregate", ("eyewear", "headwear", "covering"), "fashion.json", ("crops",),
             "typed accessory; complementary to parse"),
    Analyzer("headpose6d", "stage", "6DRepNet (300W-LP, full-range, ONNX)", ("crops",),
             "timeline", ("yaw", "pitch", "roll"), "headpose.parquet", ("crops",),
             "profile-capable; fills MediaPipe NaN; yaw sign-aligned (adapter)"),
    Analyzer("emotion", "stage", "HSEmotion+LibreFace fusion → person-relative valence",
             ("features", "tubelets"), "aggregate",
             ("valence_signed", "em_conf", "arousal", "per-person RIDE baseline"),
             "emotion.json", ("features", "tubelets"),
             "shared emotion reading; emotion.json = per-person baseline, emotion_frame.parquet = per-frame valence/em_conf/arousal (observability trace the inspector reads)"),

    # ── unit analyzers: pure fns in signals.py over a stream (inline);
    #    pose graduated to its own domain module pose.py (fusion+quantizer+thresholds) ──
    Analyzer("pose", "unit", "MediaPipe transform → euler", ("landmarks.transform",),
             "timeline", ("yaw", "pitch", "roll"), "inline", ("landmarks",),
             "frontal-precise; NaN on profiles → fused with headpose6d (pose.fuse_pose)"),
    Analyzer("expression", "unit", "MediaPipe blendshape", ("landmarks.blendshapes",),
             "timeline", ("blink", "smile", "jaw", "expr_magnitude"), "inline", ("landmarks",)),
    Analyzer("face_quality", "unit", "pixel (Laplacian)", ("crops",),
             "timeline", ("crop_blur", "crop_lighting (bright, harsh)"), "inline", ("crops",)),
    Analyzer("identity_dev", "unit", "ArcFace centroid cosine", ("detect.embedding",),
             "timeline", ("identity_deviation",), "inline", ("detect",),
             "self-relative; nuisance-entangled (probe-0)"),

    # ── engines: consume analyzers → product output ─────────────────────────
    Analyzer("portrait", "engine", "synthetic-criterion gate + crop-track extract",
             ("landmarks", "face_quality", "parse", "crops", "headpose6d"),
             "selection", ("portraits/*.png", "candidates(portrait)"), "portraits/",
             ("landmarks", "parse", "crops", "headpose6d"),
             "fashion admit; 0-axis not ranked; side via headpose6d fallback"),
    Analyzer("likeness", "engine", "landmark distribution + fashion reading", ("landmarks", "parse", "fashion"),
             "aggregate", ("likeness.json (center, axes, fashion)",), "likeness.json",
             ("landmarks", "parse", "fashion", "portrait"),
             "visit-invariant ID; depends portrait = consumes its shared ① `valid` verdict "
             "(face_id/geometry from valid frames). NB freshness is import-closure based, so a "
             "gates.py change re-runs portrait but NOT likeness — close via lift-assembly (call "
             "evaluate_validity) or an artifact-dep freshness rule; for now re-run engines together"),
    Analyzer("select", "engine", "frame_scores → candidates", ("features", "tubelets"),
             "selection", ("candidates(likeness, highlight)",), "candidates.jsonl", ("features", "portrait"),
             "depends portrait = highlight WHICH gated on the shared ① `valid` (same freshness caveat as likeness)"),
)

_BY_NAME = {a.name: a for a in ANALYZERS}


def get(name: str) -> Analyzer:
    return _BY_NAME[name]


def by_output_kind(kind: str) -> list[Analyzer]:
    return [a for a in ANALYZERS if a.output_kind == kind]


def topo_order() -> list[Analyzer]:
    """Kahn topological sort over `depends` — a valid run order for the DAG."""
    indeg = {a.name: sum(1 for d in a.depends if d in _BY_NAME) for a in ANALYZERS}
    ready = [a for a in ANALYZERS if indeg[a.name] == 0]
    order: list[Analyzer] = []
    while ready:
        a = ready.pop(0)
        order.append(a)
        for b in ANALYZERS:
            if a.name in b.depends:
                indeg[b.name] -= 1
                if indeg[b.name] == 0:
                    ready.append(b)
    return order


# ── the PRODUCT declaration map (the vertical view) ─────────────────────────
# ANALYZERS above is the PRODUCER catalog (horizontal: one entry per pipeline
# stage). The three deliverables are VERTICAL reads cutting across 4–9 stages,
# and a flat module bag has no place to make that smear visible — so a product's
# logic ends up scattered (likeness lives in BOTH appearance.py and select.py)
# or fused with a sibling (select.py emits likeness AND highlight). This map
# DECLARES each product's full read-chain WITHOUT moving any code: it names the
# stages/units a product reads and the keys it consumes, so `momentscan products`
# can draw the vertical the pipeline hides. Artifacts are NOT restated here — a
# read references an analyzer by NAME and the renderer resolves `.artifact` from
# the catalog, so this map cannot drift from the producer's real output path.
# `state` records whether a product's DEFINITION has frozen: a molten product is
# kept consolidated on purpose (splitting it freezes a boundary research is still
# moving), a frozen one has earned its own module (portrait already did). The map
# answers the feeling of scatter with LEGIBILITY, not premature consolidation.


@dataclass(frozen=True)
class Product:
    name: str                                       # the deliverable (likeness/portrait/highlight)
    definition: str                                 # one line: what it is
    operation: str                                  # integrate | select(static) | select(temporal)
    reads: tuple[tuple[str, tuple[str, ...]], ...]  # (analyzer name, keys) — the vertical read-chain
    emitted_by: tuple[str, ...]                     # engine analyzer name(s) that physically produce it
    outputs: tuple[str, ...]                         # artifacts / candidate products it lands
    state: str                                       # "frozen" (definition settled) | "molten" (still researched)
    note: str = ""
    egress: tuple[str, ...] = ()                     # the subset of `outputs` that CROSSES the service
                                                     # boundary OUTWARD (S3-out / the Result contract); the
                                                     # rest of `outputs` are intermediate traces. This makes
                                                     # INPUT/INTERMEDIATE/FINAL unambiguous (input=source,
                                                     # FINAL=egress, everything else in the stash=intermediate)
                                                     # AND doubles as the deliverable contract the service uploads.


PRODUCTS: tuple[Product, ...] = (
    Product(
        "likeness", "visit-invariant ID (오늘 이 사람) — distribution + exemplar picks", "integrate",
        (("landmarks", ("blendshapes", "transform")),
         ("detect", ("embedding",)),
         ("features", ("em_happy", "au12_lip_corner", "au25_lips_part", "head_yaw_dev", "head_pitch", "face_blur")),
         ("parse", ("glasses_frac", "hat_frac", "cloth_frac")),
         ("fashion", ("eyewear", "headwear", "covering")),
         ("tubelets", ())),
        ("likeness", "select"),
        ("likeness.json", "candidates.jsonl[likeness]"),
        "molten", "two homes: appearance.py=distribution reading, select.py=exemplar picks (distinct readings, rename pending — NOT a split to consolidate yet)",
        egress=("likeness.json",)),
    Product(
        "portrait", "query-extraction gate → clean crop-track pixels", "select(static)",
        (("tubelets", ("embedding",)),
         ("identity_dev", ("identity_deviation",)),
         ("landmarks", ("blendshapes", "transform")),
         ("expression", ("blink", "jaw")),
         ("pose", ("yaw", "pitch", "roll")),
         ("headpose6d", ("yaw", "pitch", "roll")),
         ("face_quality", ("crop_blur",)),
         ("parse", ("eye_lum_rel", "mouth_vis")),
         ("crops", ("crop track",))),
        ("portrait",),
        ("portraits/*.png", "portraits/portrait.json", "gate_trace.parquet", "candidates.jsonl[portrait,portrait_set]"),
        "frozen", "definition froze E008–E009, already its own module; gate verdicts via gates.evaluate → gate_trace; pose(frontal)+headpose6d(profile) fused",
        egress=("portraits/portrait.json", "portraits/*.png")),
    Product(
        "highlight", "WHEN×WHICH — attraction × customer reaction over a segment", "select(temporal)",
        (("features", ("em_* (→ fused_valence)", "head_yaw_dev", "face_blur")),
         ("scene", ("scene_change",)),
         ("tubelets", ("Δpose / motion",))),
        ("select",),
        ("candidates.jsonl[highlight]", "highlights/*.mp4"),
        "molten", "valence = emotion.fused_valence, a shared READING over features' em_* (NOT the emotion.json baseline — that is inspector-only / future portrait query); scene optional; shares select.py frame_scores with likeness picks (essential — leave fused); 3rd WHEN + gate STEP4+ pending",
        egress=("highlights/*.mp4",)),
)

_BY_PRODUCT = {p.name: p for p in PRODUCTS}

# Drift guard (runs at import, like gates.py's vocabulary asserts): the product
# map is a DECLARATION CHECKED against the producer catalog — every stage/unit a
# product claims to read, and every engine it is emitted by, must exist; emitters
# must actually be engines. A phantom reference (e.g. a renamed artifact) fails
# the import, so this map cannot silently diverge from ANALYZERS.
for _p in PRODUCTS:
    assert _p.state in ("frozen", "molten"), f"product {_p.name}: bad state {_p.state!r}"
    assert _p.operation in ("integrate", "select(static)", "select(temporal)"), \
        f"product {_p.name}: bad operation {_p.operation!r}"
    for _stage, _keys in _p.reads:
        assert _stage in _BY_NAME, f"product {_p.name} reads unknown analyzer {_stage!r}"
    for _eng in _p.emitted_by:
        assert _eng in _BY_NAME, f"product {_p.name} emitted_by unknown analyzer {_eng!r}"
        assert _BY_NAME[_eng].kind == "engine", \
            f"product {_p.name} emitter {_eng!r} is kind={_BY_NAME[_eng].kind!r}, not 'engine'"
    # egress (the Result contract) must be a SUBSET of declared outputs — it cannot
    # name a deliverable the product does not actually land.
    for _e in _p.egress:
        assert _e in _p.outputs, f"product {_p.name}: egress {_e!r} is not a declared output"


def products() -> tuple[Product, ...]:
    return PRODUCTS


def product(name: str) -> Product:
    return _BY_PRODUCT[name]


def _depends_closure() -> dict[str, set[str]]:
    """Transitive `depends` closure per analyzer (everyone that must run before it)."""
    closure: dict[str, set[str]] = {}

    def walk(name: str, seen: frozenset[str]) -> set[str]:
        if name in closure:
            return closure[name]
        acc: set[str] = set()
        for d in _BY_NAME[name].depends:
            if d in _BY_NAME and d not in seen:
                acc.add(d)
                acc |= walk(d, seen | {d})
        closure[name] = acc
        return acc

    for a in ANALYZERS:
        walk(a.name, frozenset({a.name}))
    return closure


def registry_drift(runner_names, upstream=()) -> list[tuple[str, str]]:
    """Reconcile the THREE declarations — ANALYZERS (producer catalog), the runner's
    RUNNERS table, and PRODUCTS (the read-map) — returning (severity, message)
    problems; [] = consistent. Pure: the RUNNERS key set is passed IN (pipeline
    imports analyzers, never the reverse), so the runner→catalog direction stays
    one-way. Membership + order now DERIVE from ANALYZERS, so this CHECKS that
    derivation: a runnable analyzer with no runner, or a runner for a non-analyzer,
    fails. `momentscan check` exits nonzero on any error — the guardrail that turns
    "the declaration that runs is the declaration that's drawn" from aspiration into
    something enforceable. See [[visualpath-dag-split]]."""
    problems: list[tuple[str, str]] = []
    runnable = {a.name for a in ANALYZERS if a.kind in ("stage", "engine")}
    runners = set(runner_names)
    up = set(upstream)
    known = set(_BY_NAME)

    # RUNNERS ⇄ ANALYZERS membership: the run set derives from ANALYZERS − UPSTREAM,
    # so every runnable analyzer must HAVE a runner and every runner must name a
    # runnable analyzer (the proven {detect,landmarks} silent-filter is now caught).
    for s in sorted(runners - runnable):
        problems.append(("error", f"RUNNER {s!r} is not a stage/engine analyzer in the catalog"))
    for a in sorted(runnable - runners - up):
        problems.append(("error", f"analyzer {a!r} is runnable but has no RUNNERS entry and is not UPSTREAM_OF_RUNNER — it would silently never run"))
    for u in sorted(up - known):
        problems.append(("error", f"UPSTREAM_OF_RUNNER {u!r} is not a known analyzer"))
    for u in sorted(up & runners):
        problems.append(("error", f"{u!r} is both upstream-of-runner and a RUNNER (contradiction)"))

    # every depends edge names a real analyzer (topo_order silently ignores unknowns)
    for a in ANALYZERS:
        for d in a.depends:
            if d not in known:
                problems.append(("error", f"analyzer {a.name!r} depends on unknown {d!r}"))
    if len(topo_order()) != len(ANALYZERS):
        problems.append(("error", "dependency cycle: topo_order() does not cover every analyzer"))

    # advisory: each product's STAGE reads should be covered by the (transitive)
    # depends closure of SOME emitter — else the run-order that makes the read work
    # is incidental, not guaranteed. (Optional/degrading reads legitimately trip this.)
    closure = _depends_closure()
    for p in PRODUCTS:
        covered: set[str] = set()
        for eng in p.emitted_by:
            covered |= closure.get(eng, set()) | {eng}
        need = {r for (r, _k) in p.reads if _BY_NAME[r].kind in ("stage", "engine")}
        for m in sorted(need - covered - up):
            problems.append(("warn", f"product {p.name!r} reads stage {m!r}, but no emitter {p.emitted_by} (transitively) depends on it — run-order incidental (ok only if that read is optional/degrades)"))
    return problems

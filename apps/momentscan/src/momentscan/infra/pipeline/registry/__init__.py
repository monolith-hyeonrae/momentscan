"""registry — the single declaration authority, split into legible submodules (접수 #7·#8).

  analyzers.py  producer catalog (horizontal: Analyzer + ANALYZERS + topo_order + closure)
  products.py   product read-map (vertical: Product + PRODUCTS)
  tiers.py      artifact tiers (TIERS + ARTIFACT_TIERS + classify_clip_files)

This __init__ RE-EXPORTS every public symbol so consumers import unchanged
(`from momentscan.infra.pipeline.registry import ANALYZERS`, `registry.PRODUCTS`).
It is also the ONLY place that imports BOTH analyzers and products, so every
CROSS-declaration drift guard lives HERE (like gates.py's vocabulary asserts, run
at import): tier validity (Analyzer.tier ⇄ TIERS), and the product↔producer edges
(reads/emitted_by must name real analyzers; emitters must be engines). A phantom
reference fails the import, so the map cannot silently diverge from the catalog.
"""
from __future__ import annotations

from momentscan.infra.pipeline.registry.analyzers import (
    ANALYZERS,
    OUTPUT_KINDS,
    Analyzer,
    _BY_NAME,
    _depends_closure,
    by_output_kind,
    get,
    topo_order,
)
from momentscan.infra.pipeline.registry.products import (
    PRODUCTS,
    Product,
    _BY_PRODUCT,
    product,
    products,
)
from momentscan.infra.pipeline.registry.tiers import (
    ARTIFACT_TIERS,
    EXTRA_ARTIFACT_TIERS,
    TIERS,
    classify_clip_files,
)

__all__ = [
    "ANALYZERS", "OUTPUT_KINDS", "Analyzer", "by_output_kind", "get", "topo_order",
    "PRODUCTS", "Product", "product", "products", "product_closure",
    "TIERS", "ARTIFACT_TIERS", "EXTRA_ARTIFACT_TIERS", "classify_clip_files",
    "registry_drift",
]

# ── cross-declaration drift guards (analyzers ⇄ tiers, products ⇄ analyzers) ──
# run at import — the declaration that runs is the declaration that's drawn.
for _a in ANALYZERS:                            # R12: 전 선언 tier 유효 — import에서 시끄럽게
    assert _a.tier in TIERS, f"analyzer {_a.name}: bad tier {_a.tier!r} (valid: {TIERS})"

for _p in PRODUCTS:
    for _stage, _keys in _p.reads:
        assert _stage in _BY_NAME, f"product {_p.name} reads unknown analyzer {_stage!r}"
    for _eng in _p.emitted_by:
        assert _eng in _BY_NAME, f"product {_p.name} emitted_by unknown analyzer {_eng!r}"
        assert _BY_NAME[_eng].kind == "engine", \
            f"product {_p.name} emitter {_eng!r} is kind={_BY_NAME[_eng].kind!r}, not 'engine'"


def product_closure(name: str) -> set[str]:
    """The analyzers that must run to produce product `name`: its emitter engine(s) +
    their transitive `depends` (R11). `run --product` restricts the run order to the
    union of these over the requested products. NB likeness is co-emitted by BOTH the
    `likeness` and `select` engines (Product.emitted_by), so its closure includes select
    and select's upstream — the run produces the product's FULL output set (likeness.json
    AND candidates.jsonl[likeness]), not only the egress artifact."""
    p = _BY_PRODUCT[name]
    closure = _depends_closure()
    need: set[str] = set()

    for eng in p.emitted_by:
        need.add(eng)
        need |= closure.get(eng, set())

    return need


def registry_drift(runner_names, upstream=()) -> list[tuple[str, str]]:
    """Reconcile the THREE declarations — ANALYZERS (producer catalog), the runner's
    RUNNERS table, and PRODUCTS (the read-map) — returning (severity, message)
    problems; [] = consistent. Pure: the RUNNERS key set is passed IN (pipeline
    imports analyzers, never the reverse), so the runner→catalog direction stays
    one-way. Membership + order now DERIVE from ANALYZERS, so this CHECKS that
    derivation: a runnable analyzer with no runner, or a runner for a non-analyzer,
    fails. `momentscan verify registry` exits nonzero on any error — the guardrail that turns
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

    # R12: 모든 stage/engine 산출물에 유효한 tier — import assert의 CLI판 (이중 안전망)
    for an in ANALYZERS:
        if an.tier not in TIERS:
            problems.append(("error", f"analyzer {an.name!r}: tier {an.tier!r} not in {TIERS}"))
    for art in ("gate_trace.parquet", "candidates.jsonl"):     # 공유 흔적도 지도에 있어야
        if art not in ARTIFACT_TIERS:
            problems.append(("error", f"shared artifact {art!r} missing from ARTIFACT_TIERS"))

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

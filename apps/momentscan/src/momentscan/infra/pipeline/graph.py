"""graph.py — the ONE declared graph (the legibility spine).

registry.py, gates.py, and the PRODUCTS map each declare a SLICE of the system;
to see "what runs in what order, reading what, producing what" you had to merge
2.5 representations in your head (the visualpath frame-DAG hidden in detect, the
analyzers artifact-DAG, the gate ladder, the product read-map). This is the thin
PROJECTION that reads all of them IN PLACE and renders ONE graph: the frame-grain
ingest (detect/landmarks) → the clip-grain stages/units → the engines → the gates
→ the products, each tagged with its grain (frame|clip) + backend (who runs it) +
artifact.

It AUTHORS no new declaration — every field comes from ANALYZERS / LADDER /
PRODUCTS. detect's two internal visualpath bus modules are shown as a one-LINE
annotation (DETECT_INTERNALS), NOT re-declared as nodes (2 nodes do not justify a
hand-kept mirror + a drift guard). Edges are DERIVED (depends, product reads, gate
reads), never hand-listed — copying visualpath's introspectability into the
clip-DAG without copying its runtime. Imports registry + gates ONLY (both
import-light: stdlib + numpy), so `momentscan map graph` stays torch/polars-free.
"""
from __future__ import annotations

from dataclasses import dataclass

from momentscan.infra.pipeline import gates, registry

# detect runs exactly 2 visualpath bus modules (resolver topo-orders them); shown
# inline, NOT re-declared as nodes. Source of truth = detect.py:62-69.
DETECT_INTERNALS = "FaceDetect → IoUTracker  (visualpath bus)"

# grain/backend for the frame-ingest pair — these run upstream of the clip runner
# (mirrors pipeline.UPSTREAM_OF_RUNNER; hardcoded here to keep the render import-light,
# i.e. free of the pipeline→stash→polars weight). Everything else is clip-grain.
_FRAME = {"detect": "visualpath-bus", "landmarks": "warm-ingest"}


@dataclass(frozen=True)
class Node:
    name: str
    kind: str       # stage | unit | engine | reference | gate | product
    grain: str      # frame | clip
    backend: str    # visualpath-bus | warm-ingest | pipeline-runner | inline | gate-ladder | product
    artifact: str   # stash path | "inline" | gate_trace | product outputs
    label: str      # short human descriptor (model / semantics / definition)


def _analyzer_backend(a) -> str:
    if a.name in _FRAME:
        return _FRAME[a.name]
    return {"unit": "inline", "stage": "pipeline-runner", "engine": "pipeline-runner"}[a.kind]


def nodes() -> list[Node]:
    """Project the 2.5 declarations into ONE uniform node list (a derived VIEW)."""
    ns: list[Node] = []
    for a in registry.ANALYZERS:
        grain = "frame" if a.name in _FRAME else "clip"
        ns.append(Node(a.name, a.kind, grain, _analyzer_backend(a), a.artifact, a.model))
    for n in gates.LADDER:
        label = f"{n.semantics} · {n.tier}" if n.kind == "gate" else "cohort stat"
        ns.append(Node(n.name, n.kind, "clip", "gate-ladder", "gate_trace.parquet", label))
    for p in registry.PRODUCTS:
        ns.append(Node(p.name, "product", "clip", "product", ", ".join(p.outputs),
                       f"[{p.state}] {p.definition}"))
    return ns


def edges() -> list[tuple[str, str, str]]:
    """(src, dst, kind) — all DERIVED from the declarations, never hand-listed.
    depends (analyzer→analyzer), reads (product→stage), gate-reads (gate→ladder node).
    Raw-signal gate reads (blur/blink/iddev…) are NOT edges here: they are inputs
    assembled inline by the engine, surfaced separately by unjoined_reads()."""
    ladder_names = {n.name for n in gates.LADDER}
    es: list[tuple[str, str, str]] = []
    for a in registry.ANALYZERS:
        for d in a.depends:
            es.append((d, a.name, "depends"))
    for p in registry.PRODUCTS:
        for stage, _keys in p.reads:
            es.append((stage, p.name, "reads"))
    for n in gates.LADDER:
        for r in n.reads:
            if r in ladder_names:                 # intra-ladder edge (id_ok→clean_ref…)
                es.append((r, n.name, "gate-reads"))
    return es


def unjoined_reads() -> dict[str, list[str]]:
    """Honesty side-channel: declared `reads` names that do NOT resolve to a catalog
    node. Products SHOULD all resolve (they reference analyzer names); gate reads
    that aren't ladder nodes are the engine's inline-assembled SIGNALS (expected —
    ③ checks them against gates.SIGNAL_INPUTS, not the analyzer catalog)."""
    analyzer_names = {a.name for a in registry.ANALYZERS}
    ladder_names = {n.name for n in gates.LADDER}
    out: dict[str, list[str]] = {"product": [], "gate-signal": []}
    for p in registry.PRODUCTS:
        for stage, _ in p.reads:
            if stage not in analyzer_names:
                out["product"].append(f"{p.name} → {stage}")
    for n in gates.LADDER:
        for r in n.reads:
            if r not in ladder_names and r not in analyzer_names:
                out["gate-signal"].append(f"{n.name} → {r}")
    return out


def render_text() -> str:
    """The unified one-screen view: frame ingest → clip stages/units → engines →
    gates → products, with grain/backend/artifact and derived edges. Reuses the
    same fields `momentscan map analyzers`/`products` show, in ONE drawing."""
    ns = nodes()
    by = {}
    for n in ns:
        by.setdefault((n.grain, n.kind), []).append(n)
    dep = {}
    rd = {}
    for src, dst, k in edges():
        (dep if k == "depends" else rd).setdefault(dst, []).append(src)

    L = ["", "── declared graph — frame ⇒ clip · what runs · reads what · → artifact ──"]

    def emit(title, key, show_dep=True):
        items = by.get(key, [])
        if not items:
            return
        L.append(f"\n{title}")
        for n in sorted(items, key=lambda x: x.name):
            dd = ("  ← " + ", ".join(dep.get(n.name, []))) if show_dep and dep.get(n.name) else ""
            L.append(f"  {n.name:<14}[{n.backend:<14}] → {n.artifact}{dd}")
            if n.name == "detect":
                L.append(f"  {'':<14} └ {DETECT_INTERNALS}")

    emit("FRAME-grain ingest:", ("frame", "stage"))
    emit("CLIP-grain stages (pipeline-runner):", ("clip", "stage"))
    emit("CLIP-grain units (inline signals):", ("clip", "unit"))
    emit("ENGINES (product output):", ("clip", "engine"))

    gnodes = [n for n in ns if n.kind in ("gate", "reference")]
    if gnodes:
        L.append("\nGATES (gate-ladder → gate_trace.parquet, execution order):")
        for n in gnodes:   # LADDER order preserved (nodes() appends in order)
            gr = (" ← " + ", ".join(rd.get(n.name, []))) if rd.get(n.name) else ""
            L.append(f"  {n.label:<22} {n.name:<16}{gr}")

    pnodes = [n for n in ns if n.kind == "product"]
    if pnodes:
        L.append("\nPRODUCTS (vertical reads → outputs):")
        for n in pnodes:
            reads = ", ".join(rd.get(n.name, []))
            L.append(f"  {n.name:<10}{n.label}")
            L.append(f"  {'':<10}  ← {reads}")
            L.append(f"  {'':<10}  → {n.artifact}")

    L.append("\nrun order (clip DAG): " + " → ".join(a.name for a in registry.topo_order()))

    uj = unjoined_reads()
    if uj["product"]:
        L.append("\n⚠ product reads not resolving to a catalog node: " + "; ".join(uj["product"]))
    if uj["gate-signal"]:
        L.append(f"\n  ({len(uj['gate-signal'])} gate reads are inline-assembled signals, "
                 "not catalog producers — checked against gates.SIGNAL_INPUTS by `momentscan verify registry`)")
    return "\n".join(L) + "\n"

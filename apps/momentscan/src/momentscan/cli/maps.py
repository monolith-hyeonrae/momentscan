"""map 가족 — 선언 지도 (읽기-전용 introspection): analyzers · products · cascade · frame · graph."""

from __future__ import annotations

import argparse
import json


def _cmd_analyzers(args: argparse.Namespace) -> int:
    from momentscan.engine.analyzers import ANALYZERS, topo_order

    if args.json:
        from dataclasses import asdict
        print(json.dumps([asdict(a) for a in ANALYZERS], ensure_ascii=False, indent=2))
        return 0
    order = {a.name: i for i, a in enumerate(topo_order())}
    by_kind: dict[str, list] = {}
    for a in ANALYZERS:
        by_kind.setdefault(a.kind, []).append(a)
    for kind in ("stage", "unit", "engine"):
        print(f"\n── {kind} ──")
        for a in sorted(by_kind.get(kind, []), key=lambda a: order[a.name]):
            dep = (" ← " + ", ".join(a.depends)) if a.depends else ""
            print(f"  {a.name:<13} [{a.output_kind:<11}] {a.model}")
            print(f"  {'':<13}  → {a.artifact}{dep}")
    print("\n── run order (DAG) ──\n  " + " → ".join(a.name for a in topo_order()))
    return 0


def _cmd_products(args: argparse.Namespace) -> int:
    from momentscan.engine import analyzers as A

    if args.json:
        from dataclasses import asdict
        print(json.dumps([asdict(p) for p in A.PRODUCTS], ensure_ascii=False, indent=2))
        return 0
    print("\n── products (vertical read-map · what each deliverable reads across the horizontal pipeline) ──")
    for p in A.PRODUCTS:
        print(f"\n{p.name:<11} [{p.state:<6}] {p.operation}")
        print(f"  {p.definition}")
        print(f"  emitted by : {', '.join(p.emitted_by)}")
        print("  reads      :")
        for stage, keys in p.reads:
            art = A.get(stage).artifact
            ks = ", ".join(keys) if keys else "—"
            print(f"    {stage:<13}{art:<22} ← {ks}")
        print(f"  outputs    : {', '.join(p.outputs)}")
        if p.note:
            print(f"  note       : {p.note}")
    print("\n  (producer view: `momentscan map analyzers` · frozen = own module earned, molten = kept consolidated on purpose)")
    return 0


def _cmd_cascade(args: argparse.Namespace) -> int:
    """The data lineage stated plainly: INPUT → ①FEATURE/②GATE (intermediate, stash)
    → ③PRODUCT (FINAL, egress). DERIVED from ANALYZERS (.artifact) + PRODUCTS (.egress),
    so it cannot drift from what actually runs. Same ①②③ as the run-watch banners."""
    from momentscan.engine import analyzers as A
    from momentscan.engine.analyzers import topo_order

    stages = [a for a in topo_order() if a.kind == "stage"]
    if args.json:
        # the machine view = the Storage port contract: what to fetch (input), what
        # is scratch (intermediate), what to upload (final/egress).
        print(json.dumps({
            "input": {"source": "video → frames", "weights": sorted({a.model for a in stages})},
            "intermediate": {a.name: a.artifact for a in stages} | {"gate": "gate_trace.parquet"},
            "final": {p.name: list(p.egress) for p in A.PRODUCTS},
            "tiers": A.ARTIFACT_TIERS,          # R12 — 산출물→tier (manifest.json과 동일 근거)
        }, ensure_ascii=False, indent=2))
        return 0

    print("\n── cascade · data lineage  (INPUT → INTERMEDIATE → FINAL) ──")
    print("\nINPUT   (crosses the service boundary inward · S3-in / Job)")
    print(f"  {'source video':<13} → frames           (FileSource, decode @ fps)")
    print(f"  {'frozen weights':<13}   per-stage models   (see `momentscan map analyzers`; tracked by freshness)")

    print("\n① FEATURE EXTRACTION   (intermediate — stays in the stash · tier=substrate)")
    for a in stages:
        print(f"  {a.name:<12} → {a.artifact:<22} ({a.model})")

    print("\n② GATE   (intermediate — the decision trace · tier=substrate)")
    print(f"  {'portrait':<12} → {'gate_trace.parquet':<22} (gates.evaluate ladder · T0 valid · T1 sharp · T2 view)")

    print("\n③ PRODUCT   (FINAL — crosses the boundary outward · S3-out / Result · tier=product)")
    for p in A.PRODUCTS:
        fin = ", ".join(p.egress) if p.egress else "(none wired)"
        inter = [o for o in p.outputs if o not in p.egress]
        flag = "" if p.egress else "   ⚠ no clean deliverable yet"
        print(f"  {p.name:<12} → {fin}{flag}")
        if inter:
            print(f"  {'':<12}   (intermediate: {', '.join(inter)})")
    print("\n④ RUN RECORDS & RENDERS   (경계 밖으로 안 나감 — tier=ops/surface)")
    _extras = sorted((f, t) for f, t in A.EXTRA_ARTIFACT_TIERS.items() if t in ("ops", "surface"))
    for _f, _t in _extras:
        print(f"  {_t:<12} · {_f}")
    print("\n  producer detail → `momentscan map analyzers`   ·   vertical read-map → `momentscan map products`")
    return 0


def _cmd_frame(args: argparse.Namespace) -> int:
    """The canonical-frame contract stated plainly — origin/axes/scale/basis/reference
    + provenance. The coordinate analogue of gates.py / `momentscan map products`: ONE
    declared frame every consumer (appearance/portrait/select/inspector/eval) reads
    via signals.py (verified single home)."""
    from momentscan.readings.geometry import CANONICAL_FRAME as F
    from momentscan.readings.geometry import frame_provenance

    pv = frame_provenance()
    if args.json:
        from dataclasses import asdict
        d = asdict(F)
        d["reference"] = str(F.reference)
        d["provenance"] = pv
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return 0
    ref = pv["reference"] + ("  [sha %s · %d verts · present]" % (pv["sha256"], pv["n_verts"])
                             if pv.get("present") else "  [MISSING]")
    flip = tuple(int(s) for s in F.axis_flip)
    print(f"\n── canonical frame  ({F.name}) ──")
    print(f"  reference : {ref}")
    print(f"  origin    : {F.origin}   (translation removed; no fixed anatomical anchor)")
    print(f"  axes      : flip (x,y,z)={flip} = π about x → {F.handedness}-handed (+x right, +y up, +z toward camera)")
    print(f"              guard: det(flip)=+1, a proper rotation (y-only would be a reflection)")
    print(f"  scale     : {F.scale}   (UNITLESS — no metric length)")
    print(f"  basis     : distribution/PCA = {F.basis_full} verts (incl. iris)  ·  template/ratios = {F.basis_mesh} (excl. iris)")
    print(f"              ⚠ two bases coexist — unify candidate (settle under split-half eval · STEP 2)")
    print(f"  pose      : {F.pose_convention} — referenced, not redefined")
    print(f"  consumers : geometry.canonicalize / norm468 / template · pose.euler_from_transform  (verified single home)")
    return 0


def _cmd_graph(args: argparse.Namespace) -> int:
    from momentscan.engine import graph

    if args.json:
        from dataclasses import asdict
        print(json.dumps({"nodes": [asdict(n) for n in graph.nodes()], "edges": graph.edges()},
                         ensure_ascii=False, indent=2))
        return 0
    print(graph.render_text())
    return 0


def register(sub, common: argparse.ArgumentParser) -> None:
    # ── map 그룹 — 선언 지도 (전부 읽기-전용 introspection) ──────────────────
    pmap = sub.add_parser("map", parents=[common],
                          help="선언 지도 — analyzers · products · cascade · frame · graph")
    msub = pmap.add_subparsers(dest="map_cmd", required=True,
                               metavar="{analyzers,products,cascade,frame,graph}")
    pan = msub.add_parser("analyzers", parents=[common],
                         help="introspect the analyzer registry (producers · output-kinds · DAG order)")
    pan.add_argument("--json", action="store_true", help="emit the full catalog as JSON")
    pan.set_defaults(func=_cmd_analyzers)

    ppr = msub.add_parser("products", parents=[common],
                         help="the product read-map (vertical: what each deliverable reads across stages)")
    ppr.add_argument("--json", action="store_true", help="emit the product map as JSON")
    ppr.set_defaults(func=_cmd_products)

    pcas = msub.add_parser("cascade", parents=[common],
                          help="data lineage stated plainly: INPUT → ①FEATURE/②GATE (stash) → ③PRODUCT (egress)")
    pcas.add_argument("--json", action="store_true", help="emit lineage as JSON (the Storage-port fetch/scratch/upload contract)")
    pcas.set_defaults(func=_cmd_cascade)

    pfr = msub.add_parser("frame", parents=[common],
                         help="the canonical-frame contract (origin/axes/scale/basis/reference + provenance)")
    pfr.add_argument("--json", action="store_true", help="emit the frame contract + provenance as JSON")
    pfr.set_defaults(func=_cmd_frame)

    pgr = msub.add_parser("graph", parents=[common],
                         help="the ONE declared graph: frame ingest → stages → units → engines → gates → products")
    pgr.add_argument("--json", action="store_true", help="emit nodes + edges as JSON")
    pgr.set_defaults(func=_cmd_graph)

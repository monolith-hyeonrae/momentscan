"""Source-freshness for stage artifacts — the build-system rule the pipeline lacked.

An artifact is STALE when the algorithm that produced it changed AFTER it was
written: ``source_mtime(stage) > artifact_mtime``. The pipeline was *resumable*
(skip if the artifact EXISTS) but not *incremental* (re-run if the SOURCE
changed) — so a code edit followed by ``momentscan run`` silently kept the prior
output, and the inspector faithfully showed the wrong algorithm's result (the
test_3 valence-redefinition case). This restores the Make rule: skip a stage only
if its artifact is newer than its source.

``source_mtime`` walks the transitive first-party import closure of the stage's
module — resolved by FILESYSTEM path, never importing the module (no GPU/model
load) — so a change to a shared dep (gates, signals, …) marks every dependent
stage stale. Cross-package aware: features/scene live in a sibling package.

No git here (the tree isn't a repo), so mtime IS the fingerprint. It is coarse in
the SAFE direction only: a cosmetic edit may flag a needless re-run (cheap); it
never shows a stale result as fresh (the dangerous direction the researcher asked
us to close).
"""
from __future__ import annotations

import ast
import importlib.util
from functools import lru_cache
from pathlib import Path

FIRST_PARTY = ("momentscan", "momentscan_features_specialist45d")

# I/O plumbing imported by EVERY stage — its changes are storage format, not the
# stage's algorithm. Counting it would make a single stash edit mark every artifact
# stale (the signal would always fire = useless). Excluded from closures so staleness
# tracks ALGORITHM change. Honest gap: a stash change that alters VALUES is not caught
# here — re-run with --force after an I/O-layer format/value change.
INFRA = frozenset({"stash", "telemetry"})

# stage name → its primary algorithm module (what the pipeline wrapper invokes).
# Not always identity: likeness→appearance, headpose6d→headpose, and scene/features
# live in the sibling features package. Kept in lockstep with RUNNERS by an
# import-time assert in pipeline.py.
STAGE_MODULE = {
    "attribute":  "momentscan.stages.attribute",
    "tubelets":   "momentscan.stages.tubelets",
    "scene":      "momentscan_features_specialist45d.scene",
    "features":   "momentscan_features_specialist45d.extractor",
    "crops":      "momentscan.stages.crops",
    "parse":      "momentscan.stages.parse",
    "fashion":    "momentscan.stages.fashion",
    "headpose6d": "momentscan.stages.headpose",
    "emotion":    "momentscan.domains.emotion",
    "portrait":   "momentscan.products.portrait",
    "likeness":   "momentscan.products.appearance",
    "select":     "momentscan.products.select",
}


def _is_first_party(modname: str) -> bool:
    return modname.split(".")[0] in FIRST_PARTY


@lru_cache(maxsize=None)
def _pkg_dir(top: str) -> Path | None:
    """Directory of a first-party top-level package, WITHOUT importing its modules.

    `momentscan` is resolved from this file's own path (zero import). A sibling
    package is located via find_spec once (its __init__ runs at most once/process).
    """
    if top == "momentscan":
        base = Path(__file__).resolve().parents[1]   # this file: momentscan/verify/freshness.py
        assert base.name == "momentscan", base       # guards the NEXT file move of this module
        return base
    try:
        spec = importlib.util.find_spec(top)
    except (ImportError, AttributeError, ValueError):
        return None
    locs = list(spec.submodule_search_locations) if spec and spec.submodule_search_locations else []
    return Path(locs[0]) if locs else None


@lru_cache(maxsize=None)
def _origin(modname: str) -> str | None:
    """Resolve a dotted module name to its .py path by FILESYSTEM construction.

    Returns None for names that are not modules (e.g. an imported symbol) or for
    non-first-party / namespace packages.
    """
    if not _is_first_party(modname):
        return None
    parts = modname.split(".")
    base = _pkg_dir(parts[0])
    if base is None:
        return None
    p = base / "__init__.py" if len(parts) == 1 else base.joinpath(*parts[1:]).with_suffix(".py")
    return str(p) if p.exists() else None


@lru_cache(maxsize=None)
def _direct_imports(py_path: str) -> frozenset[str]:
    """First-party module names imported by a source file (absolute imports)."""
    out: set[str] = set()
    try:
        tree = ast.parse(Path(py_path).read_text())
    except (OSError, SyntaxError):
        return frozenset()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.add(node.module)                          # from momentscan.gates import X
            for a in node.names:
                out.add(node.module + "." + a.name)       # from momentscan import gates
        elif isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name)                           # import momentscan.gates
    def keep(m: str) -> bool:
        parts = m.split(".")
        return _is_first_party(m) and not (len(parts) >= 2 and parts[1] in INFRA)
    return frozenset(m for m in out if keep(m))


@lru_cache(maxsize=None)
def _closure_modules(modname: str) -> frozenset[str]:
    """All first-party module NAMES in the transitive import closure of `modname`."""
    seen: set[str] = set()
    stack = [modname]
    while stack:
        m = stack.pop()
        if m in seen:
            continue
        seen.add(m)
        f = _origin(m)
        if f:
            stack.extend(_direct_imports(f))
    return frozenset(seen)


@lru_cache(maxsize=None)
def _closure_files(modname: str) -> frozenset[str]:
    """All first-party .py files in the transitive import closure of `modname`."""
    return frozenset(f for m in _closure_modules(modname) if (f := _origin(m)))


@lru_cache(maxsize=1)
def _external_deps() -> dict[str, tuple[Path, ...]]:
    """module name → external (non-.py) files whose change alters its OUTPUT.

    Python source isn't the whole algorithm: a stage also depends on model weights
    and data templates loaded at runtime (not imported), so swapping a model is an
    invisible algorithm change unless we stat those files too — the mtime analogue of
    openpilot pinning a weight hash. Imported LAZILY from the owning module so the
    path stays single-sourced (no drift) without loading the heavy model libs.
    """
    deps: dict[str, tuple[Path, ...]] = {}
    try:
        from momentscan.stages.headpose import DEFAULT_ONNX            # 6DRepNet weights
        deps["momentscan.stages.headpose"] = (Path(DEFAULT_ONNX),)
    except Exception:
        pass
    try:
        from momentscan.domains.signals import CANONICAL_OBJ            # MediaPipe canonical mesh
        deps["momentscan.domains.signals"] = (Path(CANONICAL_OBJ),)
    except Exception:
        pass
    return deps


def source_mtime(modname: str) -> float:
    """Newest mtime across the module's transitive first-party source AND the external
    model/data files any module in that closure depends on (0.0 if none resolve)."""
    ext = _external_deps()
    mt = 0.0
    for m in _closure_modules(modname):
        for p in (_origin(m), *(str(x) for x in ext.get(m, ()))):
            if not p:
                continue
            try:
                mt = max(mt, Path(p).stat().st_mtime)
            except OSError:
                continue
    return mt


def is_stale(artifact, modname: str) -> bool:
    """True iff `artifact` exists but predates the source of `modname`.

    Absent artifact ⇒ False (it is missing, not stale — the pipeline runs it as new).
    Unknown/empty module ⇒ False (degrades to the old exists-only behaviour).
    """
    if not modname:
        return False
    try:
        amt = Path(artifact).stat().st_mtime
    except OSError:
        return False
    return amt < source_mtime(modname)

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
# dotted-prefix (NOT a bare segment): A″ 이동 후 store 는 infra/store 밑이라 parts[1]
# 매칭("store")이 깨졌다 — infra 전체를 뺄 수는 없다(media=픽셀 규약·pipeline 은
# 추적 유지). 정확히 이 서브패키지(+telemetry=store 내부)만 접두-매칭으로 제외한다.
INFRA = ("momentscan.infra.store",)   # infra/store/ 전체(stash·ports·telemetry) — IO 배관만 클로저 제외

# stage name → its primary algorithm module (what the pipeline wrapper invokes).
# Not always identity: headpose6d→headpose, emotion→readings.emotion, and scene/features
# live in the sibling features package. Kept in lockstep with RUNNERS by an
# import-time assert in pipeline.py.
STAGE_MODULE = {
    "attribute":  "momentscan.perception.subjects.attribute",
    "tubelets":   "momentscan.perception.subjects.tubelets",
    "scene":      "momentscan.perception.extraction.scene",        # thin adapter; closure follows into
    "features":   "momentscan.perception.extraction.features",     # the specialist45d backend it imports
    "crops":      "momentscan.perception.subjects.crops",
    "parse":      "momentscan.perception.extraction.parse",
    "fashion":    "momentscan.perception.extraction.fashion",
    "headpose6d": "momentscan.perception.extraction.headpose",
    "emotion":    "momentscan.perception.readings.emotion",
    "gates":      "momentscan.perception.gates",           # R10: gate_trace is a stage; closure = gates + signals/emotion/pose
    "portrait":   "momentscan.products.portrait",
    "likeness":   "momentscan.products.likeness",
    "recipe":     "momentscan.products.recipe",       # closure follows into face_axes + recipe_axes (캘리 상수)
    "select":     "momentscan.products.select",
    "highlight":  "momentscan.products.highlight",
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
        base = Path(__file__).resolve().parents[2]   # this file: momentscan/infra/pipeline/freshness.py
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
        tree = ast.parse(Path(py_path).read_text(encoding="utf-8"))
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
        return _is_first_party(m) and not any(m == pre or m.startswith(pre + ".") for pre in INFRA)
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
        from momentscan.perception.extraction.headpose import DEFAULT_ONNX  # 6DRepNet weights
        deps["momentscan.perception.extraction.headpose"] = (Path(DEFAULT_ONNX),)
    except Exception:
        pass
    try:
        from momentscan.perception.readings.geometry import CANONICAL_OBJ  # MediaPipe canonical mesh
        deps["momentscan.perception.readings.geometry"] = (Path(CANONICAL_OBJ),)
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


def artifact_stale(artifact_mtime: float, upstream_mtimes, eps: float = 1e-6) -> bool:
    """R5 artifact-edge: 직접 상류 산출물 중 하나라도 내 산출물보다 새로우면 stale.

    순수 함수 — 파일시스템 접근은 호출부(pipeline) 몫. 이 분리는 §6d A안 대비:
    visualpath SkipPolicy 포트의 참조 구현으로 그대로 졸업할 수 있게.
    """
    return any(u > artifact_mtime + eps for u in upstream_mtimes)

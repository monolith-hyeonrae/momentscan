"""replay.py — the standing behavioural regression guard (the byte-identity habit, automated).

The team verifies byte-identity after every refactor BY HAND (re-run a clip, diff
artifacts). This makes that a STANDING command: re-run the DETERMINISTIC CPU stages
(emotion/likeness/portrait/select — the reading + product layer, NO model inference) on a
clip's frozen inputs into a TEMP stash, and diff the regenerated outputs against the
on-disk references with per-field IGNORE (volatile: timestamps/ms/elapsed/paths) + float
TOLERANCE (abs+rel — openpilot's process_replay). NOT byte-identity: float columns drift on
a BLAS/torch bump and byte-refs would rot, training you to ignore real failures.

This is the DYNAMIC-value guard — distinct from `momentscan check` (STATIC declaration
drift) and the frozen-pair eval (product QUALITY). Three layers, distinct failure modes
([[openpilot-lessons]]). The model stages (detect/features/parse/headpose/fashion/scene)
are NOT replayed: they need GPU and their outputs ARE the frozen inputs here.
"""
from __future__ import annotations

import json
import math
import shutil
import tempfile
from pathlib import Path

# deterministic CPU stages re-run (their inputs are the frozen model-stage artifacts)
REPLAY_STAGES = ("emotion", "likeness", "portrait", "select")
# volatile fields excluded from the diff (run-to-run noise, not behaviour)
IGNORE = {"elapsed_s", "ms", "emotion", "portraits_dir", "n_portraits", "timestamp",
          "processed_at_unix", "processed_at_iso", "started_at_unix", "started_at_iso",
          "source_uri", "source_bytes", "source_mtime", "elapsed_ms"}
# the reading + product outputs diffed (candidates.jsonl is append/timestamp-shaped → v2)
JSON_ARTIFACTS = ("emotion.json", "likeness.json", "portraits/portrait.json")
PARQUET_ARTIFACTS = ("emotion_frame.parquet", "gate_trace.parquet")
ATOL, RTOL = 1e-6, 1e-6


def _close(a, b) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        try:
            fa, fb = float(a), float(b)
        except (TypeError, ValueError):
            return a == b
        if math.isnan(fa) and math.isnan(fb):
            return True
        if math.isnan(fa) or math.isnan(fb):
            return False
        return abs(fa - fb) <= max(ATOL, RTOL * max(abs(fa), abs(fb)))
    return a == b


def _json_diff(a, b, path="") -> list[str]:
    out: list[str] = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k in IGNORE:
                continue
            if k not in a or k not in b:
                out.append(f"{path}.{k}: present in one side only")
                continue
            out += _json_diff(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: len {len(a)} != {len(b)}")
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                out += _json_diff(x, y, f"{path}[{i}]")
    elif not _close(a, b):
        out.append(f"{path}: {a!r} vs {b!r}")
    return out


def _parquet_diff(ref: Path, new: Path) -> list[str]:
    import numpy as np
    import polars as pl
    a, b = pl.read_parquet(ref), pl.read_parquet(new)
    if a.columns != b.columns:
        return [f"columns {a.columns} != {b.columns}"]
    if a.shape != b.shape:
        return [f"shape {a.shape} != {b.shape}"]
    out: list[str] = []
    for c in a.columns:
        dt = a[c].dtype
        is_float = dt in (pl.Float32, pl.Float64) or (dt == pl.List and dt.inner in (pl.Float32, pl.Float64))
        if is_float:
            x = np.array(a[c].to_list(), float).ravel()
            y = np.array(b[c].to_list(), float).ravel()
            if x.shape != y.shape or not np.allclose(x, y, atol=ATOL, rtol=RTOL, equal_nan=True):
                out.append(f"col {c!r}: float mismatch beyond tolerance")
        elif not a[c].equals(b[c]):
            out.append(f"col {c!r}: value mismatch")
    return out


def replay_check(out_root, clip_id: str, *, fps: int = 6) -> tuple[bool, dict]:
    """Re-run the CPU stages on a TEMP copy of the clip's frozen inputs, diff the
    regenerated outputs against the on-disk references (ignore volatile + float tol).
    Returns (ok, {artifact: [diffs]}). Pure: nothing on the real stash is touched."""
    import logging

    from momentscan.pipeline import run_pipeline
    from momentscan.stash import clip_dir

    src = clip_dir(Path(out_root), clip_id)
    tmp_root = Path(tempfile.mkdtemp(prefix="msreplay_"))
    _log = logging.getLogger("momentscan")
    _lvl = _log.level
    _log.setLevel(logging.WARNING)   # the replay is a check, not a run — quiet the stage logs
    try:
        shutil.copytree(src, tmp_root / clip_id)
        run_pipeline(str(tmp_root), clip_id, fps=fps, force=True, only=set(REPLAY_STAGES), watch=False)
        report: dict = {}
        for art in JSON_ARTIFACTS:
            ref, new = src / art, tmp_root / clip_id / art
            if not ref.exists() or not new.exists():
                continue
            d = _json_diff(json.loads(ref.read_text()), json.loads(new.read_text()))
            if d:
                report[art] = d
        for art in PARQUET_ARTIFACTS:
            ref, new = src / art, tmp_root / clip_id / art
            if not ref.exists() or not new.exists():
                continue
            d = _parquet_diff(ref, new)
            if d:
                report[art] = d
        return (not report, report)
    finally:
        _log.setLevel(_lvl)
        shutil.rmtree(tmp_root, ignore_errors=True)

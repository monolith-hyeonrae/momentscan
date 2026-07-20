"""Stash — the on-disk interface between the decoupled pipeline stages.

Each stage reads the previous stage's stash output and writes its own; no stage
shares a process or venv with another (the offline L1/L2 decoupling). The clip
id keys everything, so one clip can be reprocessed / deleted / debugged in
isolation. The triple ``(clip_id, track_id, rider_role)`` threads through all
stages.

    stash/{clip_id}/
    ├── process_trace.jsonl        detect      (per-frame processing trace, detect.py)
    ├── stitch.json                detect      (re-id merges + track purity, stitch.py)
    ├── tubelets.parquet           Step 0      (tubelets.py)
    ├── features/{track}.parquet   extractor   (plugins/features-*)   track in {A, B}
    ├── landmarks.parquet          extractor   (raw landmark observation track)
    └── candidates.jsonl           select      (select.py)

Phase 1 fixes the schemas — the column maps below ARE the contract. The
read/write bodies are wired in Phase 2, when there is data to move.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from momentscan.infra.store.telemetry import CandidateLog

# ── tubelets.parquet — one row per (track_id, frame) ─────────────────────────
# Step 0 output. Bystanders / staff are dropped; only rider tracks are written.
# rider_role is denormalized onto each row (PoC: the table is tiny; a groupby on
# track_id reconstructs a tubelet).
TUBELET_COLUMNS: dict[str, str] = {
    "clip_id": "str",
    "track_id": "int64",
    "rider_role": "str",              # "main" | "auxiliary"  (depth-primary; jepa-poc A2)
    "frame_idx": "int64",
    "timestamp_ms": "int64",
    "bbox": "list<float32>",          # [x1, y1, x2, y2] absolute px (visualbus.BBox convention)
    "det_score": "float32",
    "depth": "float64?",              # nullable — main/aux attribution (computed; not float32-exact)
    "scene_phase": "str",             # "boarding" | "ride"
    "embedding": "list<float32>?",    # nullable — face re-id embedding (stitch provenance)
    "crop_ref": "str",                # path/uri the extractor loads
}

# ── features/{track}.parquet — one row per (track_id, frame) ──────────────────
# Extractor output. Identical layout for Track A (D=45) and Track B (D=V-JEPA);
# only `feature_space` and the vector length differ — that sameness is what makes
# the tracks comparable. Missing dims are NaN, never a dropped row (jepa-poc A4).
FEATURE_COLUMNS: dict[str, str] = {
    "clip_id": "str",
    "track_id": "int64",
    "rider_role": "str",
    "frame_idx": "int64",
    "feature_space": "str",           # "specialist45d" | "vjepa"
    "feature": "list<float32>",       # length D; missing dims = NaN
}

# ── detections.parquet — one row per (frame, detection) ──────────────────────
# Detect+track output (pre-attribution): boxes with their temporal anchor
# (track_id), before re-id stitch / depth attribution turn them into tubelets.
# The honest product of the detect+track layers; tubelets.parquet is filled
# later, once subject stitch + rider_role exist (Step 0 proper).
DETECTION_COLUMNS: dict[str, str] = {
    "clip_id": "str",
    "frame_idx": "int64",
    "det_id": "int64",                # detector id, clip-scoped (reset per clip)
    "track_id": "int64",              # IoU temporal anchor, clip-scoped, immutable
    "subject_id": "int64",            # re-id stitched identity (= min track_id of component)
    "bbox": "list<float32>",          # [x1, y1, x2, y2] absolute px
    "score": "float32",
    "embedding": "list<float32>?",    # nullable — buffalo_l face embedding
}

# ── landmarks.parquet — one row per (track_id, frame) where the mesh fit ─────
# Raw landmark OBSERVATION track (appearance products read geometry from the
# distribution, never from one frame). Stored raw + per-frame transform;
# canonicalization (un-rotate, scale-norm) is a reading-layer concern — same
# split as AU raw-vs-normalized.
LANDMARK_COLUMNS: dict[str, str] = {
    "clip_id": "str",
    "track_id": "int64",
    "rider_role": "str",
    "frame_idx": "int64",
    "landmarks": "list<float32>",     # 478×3 flattened, normalized to crop_box
    "transform": "list<float32>",     # 4×4 row-major, canonical face → camera
    "crop_box": "list<float32>",      # [x1,y1,x2,y2] frame px of the pose crop
    "blendshapes": "list<float32>",   # 52 coeffs, specialists.BLENDSHAPE_ORDER
}

# candidates.jsonl — one CandidateLog (telemetry.py) per line.

TRACKS = ("A", "B")  # A = specialist45d, B = vjepa


# ── path conventions (usable now; I/O is Phase 2) ────────────────────────────

def clip_dir(stash_root: Path, clip_id: str) -> Path:
    return Path(stash_root) / clip_id


def tubelets_path(stash_root: Path, clip_id: str) -> Path:
    return clip_dir(stash_root, clip_id) / "tubelets.parquet"


def features_path(stash_root: Path, clip_id: str, track: str) -> Path:
    return clip_dir(stash_root, clip_id) / "features" / f"{track}.parquet"


def detections_path(stash_root: Path, clip_id: str) -> Path:
    return clip_dir(stash_root, clip_id) / "detections.parquet"


def candidates_path(stash_root: Path, clip_id: str) -> Path:
    return clip_dir(stash_root, clip_id) / "candidates.jsonl"


def attribution_path(stash_root: Path, clip_id: str) -> Path:
    return clip_dir(stash_root, clip_id) / "attribution.json"


def process_trace_path(stash_root: Path, clip_id: str) -> Path:
    return clip_dir(stash_root, clip_id) / "process_trace.jsonl"


def stitch_path(stash_root: Path, clip_id: str) -> Path:
    return clip_dir(stash_root, clip_id) / "stitch.json"


def landmarks_path(stash_root: Path, clip_id: str) -> Path:
    return clip_dir(stash_root, clip_id) / "landmarks.parquet"


def appearance_path(stash_root: Path, clip_id: str) -> Path:
    return clip_dir(stash_root, clip_id) / "likeness.json"


def recipe_dir(stash_root: Path, clip_id: str) -> Path:
    return clip_dir(stash_root, clip_id) / "recipe"


def scene_path(stash_root: Path, clip_id: str) -> Path:
    """E012 — frame-grain SCENE embedding stream (clip-level, rider-free):
    the observation the highlight 장면 축 reads (전경-배경의 배경 측)."""
    return clip_dir(stash_root, clip_id) / "scene.parquet"


# ── I/O ──────────────────────────────────────────────────────────────────────
# Stages hand off via these. Rows are plain dicts keyed by the COLUMN maps above;
# list-valued columns (bbox / embedding / feature) are python lists. The schema
# is validated on write so a stage can't silently emit the wrong columns.


def _validate(rows: list[dict], columns: dict[str, str], *, name: str) -> None:
    # '?' nullable marker lives in the dtype VALUE (e.g. "float64?" — the same spec
    # _pl_dtype rstrips), NOT the key. Three columns already declare it (tubelets
    # depth/embedding, detections embedding) — the old key-side lookup silently
    # treated them as required (fixed 2026-07-02).
    required = {k for k, v in columns.items() if not v.endswith("?")}
    allowed = set(columns)
    for i, row in enumerate(rows):
        missing = required - row.keys()
        extra = row.keys() - allowed
        if missing or extra:
            raise ValueError(
                f"{name} row {i}: missing={sorted(missing)} unexpected={sorted(extra)}"
            )


def _pl_dtype(spec: str):
    """Declared dtype string → polars dtype ('?' nullability is polars' default)."""
    return {
        "int64": pl.Int64, "float32": pl.Float32, "float64": pl.Float64,
        "str": pl.Utf8, "bool": pl.Boolean,
        "list<float32>": pl.List(pl.Float32), "list<float64>": pl.List(pl.Float64),
    }[spec.rstrip("?")]


def _to_table(rows: list[dict], columns: dict) -> pl.DataFrame:
    """Build the frame in declared column order and CAST every column to its declared
    dtype — the contract enforced at the write boundary (capnp-style: a value that
    can't cast RAISES here, not downstream). Declared float32 is the model's NATIVE
    precision; the python-list write path would otherwise upcast it to float64 (≈2×
    the bytes for the identical values — verified lossless on the corpus). Genuinely
    float64 columns (computed, e.g. depth) are declared float64 and stay float64."""
    cols = list(columns)
    df = pl.DataFrame(rows, infer_schema_length=None).select(cols)
    return df.cast({c: _pl_dtype(columns[c]) for c in cols})


def write_tubelets(stash_root: Path, clip_id: str, rows: list[dict]) -> Path:
    _validate(rows, TUBELET_COLUMNS, name="tubelets")
    p = tubelets_path(stash_root, clip_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    _to_table(rows, TUBELET_COLUMNS).write_parquet(p)
    return p


def read_tubelets(stash_root: Path, clip_id: str) -> pl.DataFrame:
    return pl.read_parquet(tubelets_path(stash_root, clip_id))


def write_detections(stash_root: Path, clip_id: str, rows: list[dict]) -> Path:
    _validate(rows, DETECTION_COLUMNS, name="detections")
    p = detections_path(stash_root, clip_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    _to_table(rows, DETECTION_COLUMNS).write_parquet(p)
    return p


def read_detections(stash_root: Path, clip_id: str) -> pl.DataFrame:
    return pl.read_parquet(detections_path(stash_root, clip_id))


def write_features(stash_root: Path, clip_id: str, track: str, rows: list[dict]) -> Path:
    if track not in TRACKS:
        raise ValueError(f"track must be one of {TRACKS}, got {track!r}")
    _validate(rows, FEATURE_COLUMNS, name="features")
    p = features_path(stash_root, clip_id, track)
    p.parent.mkdir(parents=True, exist_ok=True)
    _to_table(rows, FEATURE_COLUMNS).write_parquet(p)
    return p


def read_features(stash_root: Path, clip_id: str, track: str) -> pl.DataFrame:
    return pl.read_parquet(features_path(stash_root, clip_id, track))


def append_candidate(stash_root: Path, clip_id: str, log: CandidateLog) -> None:
    p = candidates_path(stash_root, clip_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(log.to_json() + "\n")


def read_candidates(stash_root: Path, clip_id: str) -> list[dict]:
    p = candidates_path(stash_root, clip_id)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_attribution(stash_root: Path, clip_id: str, record: dict) -> Path:
    """step0b output — rider roles + the whole-clip validity evidence
    (votes, margin, per-sample depths, flip segments). JSON, not parquet:
    one nested record per clip, read by humans and the report as-is."""
    p = attribution_path(stash_root, clip_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def read_attribution(stash_root: Path, clip_id: str) -> dict | None:
    p = attribution_path(stash_root, clip_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def write_landmarks(stash_root: Path, clip_id: str, rows: list[dict]) -> Path:
    _validate(rows, LANDMARK_COLUMNS, name="landmarks")
    p = landmarks_path(stash_root, clip_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    _to_table(rows, LANDMARK_COLUMNS).write_parquet(p)
    return p


def read_landmarks(stash_root: Path, clip_id: str) -> pl.DataFrame:
    return pl.read_parquet(landmarks_path(stash_root, clip_id))


SCENE_COLUMNS = {
    "clip_id": "str", "frame_idx": "int64",
    "embedding": "list<float32>", "customer_embedding": "list<float32>?",
    "bg_embedding": "list<float32>", "model": "str",
}


def write_scene(stash_root: Path, clip_id: str, rows: list[dict]) -> Path:
    _validate(rows, SCENE_COLUMNS, name="scene")
    p = scene_path(stash_root, clip_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    _to_table(rows, SCENE_COLUMNS).write_parquet(p)
    return p


def read_scene(stash_root: Path, clip_id: str) -> pl.DataFrame:
    return pl.read_parquet(scene_path(stash_root, clip_id))


def write_appearance(stash_root: Path, clip_id: str, record: dict) -> Path:
    """appearance reading output — per rider: canonical mean-face geometry,
    PCA axes + eigenvalues (confidence), split-half stability, sample frames.
    The product IS the measurement; frames are samples, not the deliverable."""
    p = appearance_path(stash_root, clip_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def read_appearance(stash_root: Path, clip_id: str) -> dict | None:
    p = appearance_path(stash_root, clip_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def write_recipes(stash_root: Path, clip_id: str, recipes: dict[str, dict]) -> Path:
    """recipe 스테이지 출력 — rider 별 {image_id}.recipe.json + manifest.json 을
    recipe/ 밑에 쓴다. manifest = 재개 프로브(runner)이자 read_recipes 의 인덱스.
    manifest 경로를 반환(빈 recipes 여도 manifest 는 쓴다 → 결정적 재개)."""
    rdir = recipe_dir(stash_root, clip_id)
    rdir.mkdir(parents=True, exist_ok=True)
    for image_id, rec in recipes.items():
        (rdir / f"{image_id}.recipe.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {"schema": "momentscan.recipe.manifest/v0", "clip_id": clip_id,
                "recipes": sorted(recipes)}
    mp = rdir / "manifest.json"
    mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return mp


def read_recipes(stash_root: Path, clip_id: str) -> dict[str, dict] | None:
    """image_id → recipe 레코드. manifest 부재 시 None(스테이지 미실행)."""
    mp = recipe_dir(stash_root, clip_id) / "manifest.json"
    if not mp.exists():
        return None
    manifest = json.loads(mp.read_text(encoding="utf-8"))
    rdir = recipe_dir(stash_root, clip_id)
    return {iid: json.loads((rdir / f"{iid}.recipe.json").read_text(encoding="utf-8"))
            for iid in manifest.get("recipes", [])}


def write_stitch(stash_root: Path, clip_id: str, record: dict) -> Path:
    """detect output — re-id stitch evidence: which tracks merged into which
    subject at what cosine, plus per-track identity-purity diagnostics. The
    timeline's stitch links and purity marks are a pure function of this."""
    p = stitch_path(stash_root, clip_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def read_stitch(stash_root: Path, clip_id: str) -> dict | None:
    p = stitch_path(stash_root, clip_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def write_process_trace(stash_root: Path, clip_id: str, rows: list[dict]) -> Path:
    """detect output — one JSON object per processed frame: {frame_idx,
    t_rel_ms, n_faces, modules: {name: ms}, errors?}. The unit-input
    processing record the timeline viz is a pure function of."""
    p = process_trace_path(stash_root, clip_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return p


def read_process_trace(stash_root: Path, clip_id: str) -> list[dict]:
    p = process_trace_path(stash_root, clip_id)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


# ── Phase-2 completion: the remaining post-detect artifacts ──────────────────
# parse / headpose / fashion / emotion / portrait / gate_trace used to be written
# by direct `pl.write_parquet(cdir/…)` / `write_text` calls inside their producers,
# bypassing this seam. Routed through here so EVERY artifact resolves its path and
# serialization in ONE place — the single swap point when the backend moves from
# local disk to S3 (the Storage port). Serialization MIRRORS each producer exactly
# (compact JSON, no-cast parquet) so the routing is byte-/data-identical. Optional
# reads return None when absent (parse/headpose/fashion degrade gracefully).

PARSE_COLUMNS: dict[str, str] = {
    "track_id": "int64", "frame_idx": "int64",
    "eyes_vis": "float64", "mouth_vis": "float64", "glasses_frac": "float64",
    "eye_lum_rel": "float64", "hat_frac": "float64", "cloth_frac": "float64",
    "skin_frac": "float64", "skin_lum": "float64",
    "skin_clip_hi": "float64", "skin_clip_lo": "float64", "skin_contrast": "float64",
    "skin_entropy": "float64", "face_micro": "float64",
}

HEADPOSE_COLUMNS: dict[str, str] = {
    "track_id": "int64", "frame_idx": "int64",
    "yaw": "float64", "pitch": "float64", "roll": "float64",
}

# gates.trace_rows() builds these (the gate's per-frame self-record).
# Floats are computed gate signals (float64, kept truthful); rest are int/str/bool.
GATE_TRACE_COLUMNS = {
    "track_id": "int64", "frame_idx": "int64",
    "yaw_f": "float64", "pit_f": "float64", "rol_f": "float64", "pose_src": "str",
    "mp_yaw_raw": "float64", "sixd_yaw_raw": "float64", "pose_class": "str", "frontal_clean": "bool",
    "blink": "float64", "smile": "float64", "jaw": "float64", "blur": "float64", "iddev": "float64",
    "clean_ref": "float64", "sharp_ok": "bool",
    "skin_entropy": "float64", "skin_frac": "float64", "exposure_ok": "bool", "mask_valid": "bool",
    "id_ok": "bool", "id_valid": "bool", "cos_self": "float64", "cos_other": "float64",
    "em_conf": "float64", "expr_ok": "bool", "em_vel": "float64", "face_present": "bool",
    "sunglasses_v": "bool", "masked_v": "bool",
    "fashion": "bool", "valid": "bool", "have_bs": "bool", "pose_finite": "bool",
    "eyes_ok": "bool", "query_dist": "float64", "query_ok": "bool",
    "admit": "bool", "quarter_ok": "bool", "side_raw": "bool",
    "side_ok": "bool", "reason": "str",
}


def parse_path(stash_root: Path, clip_id: str) -> Path:
    return clip_dir(stash_root, clip_id) / "parse.parquet"


def headpose_path(stash_root: Path, clip_id: str) -> Path:
    return clip_dir(stash_root, clip_id) / "headpose.parquet"


def fashion_path(stash_root: Path, clip_id: str) -> Path:
    return clip_dir(stash_root, clip_id) / "fashion.json"


def emotion_path(stash_root: Path, clip_id: str) -> Path:
    return clip_dir(stash_root, clip_id) / "emotion.json"


def portrait_path(stash_root: Path, clip_id: str) -> Path:
    return clip_dir(stash_root, clip_id) / "portraits" / "portrait.json"


def gate_trace_path(stash_root: Path, clip_id: str) -> Path:
    return clip_dir(stash_root, clip_id) / "gate_trace.parquet"


def provenance_path(stash_root: Path, clip_id: str) -> Path:
    return clip_dir(stash_root, clip_id) / "provenance.json"


def write_parse(stash_root: Path, clip_id: str, rows: list[dict]) -> Path:
    _validate(rows, PARSE_COLUMNS, name="parse")
    p = parse_path(stash_root, clip_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    _to_table(rows, PARSE_COLUMNS).write_parquet(p)
    return p


def read_parse(stash_root: Path, clip_id: str) -> pl.DataFrame | None:
    p = parse_path(stash_root, clip_id)
    return pl.read_parquet(p) if p.exists() else None


def write_headpose(stash_root: Path, clip_id: str, rows: list[dict]) -> Path:
    _validate(rows, HEADPOSE_COLUMNS, name="headpose")
    p = headpose_path(stash_root, clip_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    _to_table(rows, HEADPOSE_COLUMNS).write_parquet(p)
    return p


def read_headpose(stash_root: Path, clip_id: str) -> pl.DataFrame | None:
    p = headpose_path(stash_root, clip_id)
    return pl.read_parquet(p) if p.exists() else None


def write_gate_trace(stash_root: Path, clip_id: str, rows: list[dict]) -> Path:
    _validate(rows, GATE_TRACE_COLUMNS, name="gate_trace")
    p = gate_trace_path(stash_root, clip_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    _to_table(rows, GATE_TRACE_COLUMNS).write_parquet(p)
    return p


def read_gate_trace(stash_root: Path, clip_id: str) -> pl.DataFrame | None:
    p = gate_trace_path(stash_root, clip_id)
    return pl.read_parquet(p) if p.exists() else None


def write_fashion(stash_root: Path, clip_id: str, record: dict) -> Path:
    """FashionCLIP typed-accessory reading per subject. Compact JSON (mirrors the
    producer: ensure_ascii=False, separators=(",", ":"))."""
    p = fashion_path(stash_root, clip_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(record, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return p


def read_fashion(stash_root: Path, clip_id: str) -> dict | None:
    p = fashion_path(stash_root, clip_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def write_emotion(stash_root: Path, clip_id: str, record: dict) -> Path:
    """Per-person RIDE-conditioned valence baseline. Compact JSON (mirrors producer)."""
    p = emotion_path(stash_root, clip_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(record, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return p


def read_emotion(stash_root: Path, clip_id: str) -> dict | None:
    p = emotion_path(stash_root, clip_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def job_path(stash_root: Path, clip_id: str) -> Path:
    return clip_dir(stash_root, clip_id) / "job.json"


def write_job(stash_root: Path, clip_id: str, record: dict) -> Path:
    """The REQUEST record (contracts C1 Job, first materialization): what was asked —
    subject_query · fps · source. provenance.json = what was processed; this = what
    was requested. Stages that dispatch on the request (attribute → subject query)
    read it instead of threading params through every runner signature."""
    p = job_path(stash_root, clip_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(record, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return p


def read_job(stash_root: Path, clip_id: str) -> dict | None:
    p = job_path(stash_root, clip_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def result_path(stash_root: Path, clip_id: str) -> Path:
    return clip_dir(stash_root, clip_id) / "result.json"


def write_result(stash_root: Path, clip_id: str, record: dict) -> Path:
    """The RESPONSE record (contracts C1 Result): where the outputs landed —
    output_prefix · outputs{product→uris} · ok/failure. job.json = 요청,
    provenance.json = 처리, result.json = 응답. 서비스 멱등의 근거: 존재+ok면
    재계산 없이 이 경로들을 반환한다 (Kafka 재전송·재요청 안전)."""
    p = result_path(stash_root, clip_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(record, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return p


def read_result(stash_root: Path, clip_id: str) -> dict | None:
    p = result_path(stash_root, clip_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def select_path(stash_root: Path, clip_id: str) -> Path:
    return clip_dir(stash_root, clip_id) / "select.json"


def write_select(stash_root: Path, clip_id: str, record: dict) -> Path:
    """Select engine summary (per-rider likeness picks). ALSO the stage's
    resumability probe: select only APPENDS to the shared candidates.jsonl (which
    portrait creates first), so probing candidates.jsonl false-skipped select on any
    fresh one-command run — the stage needs an artifact only IT writes."""
    p = select_path(stash_root, clip_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(record, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return p


def read_select(stash_root: Path, clip_id: str) -> dict | None:
    p = select_path(stash_root, clip_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def highlight_path(stash_root: Path, clip_id: str) -> Path:
    return clip_dir(stash_root, clip_id) / "highlight.json"


def write_highlight(stash_root: Path, clip_id: str, record: dict) -> Path:
    """Highlight product record (합동 WHEN 악구 세그먼트) — the product's authoritative
    artifact AND the stage's resumability probe. 2026-07-03 졸업: candidates.jsonl은
    select(likeness 로그) 소유로 남고 highlight는 여기만 쓴다 (공유 가변 파일의
    스테이지-횡단 소유 금지 — portrait unlink 레이스·select false-skip의 교훈)."""
    p = highlight_path(stash_root, clip_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(record, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return p


def read_highlight(stash_root: Path, clip_id: str) -> dict | None:
    p = highlight_path(stash_root, clip_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def write_portrait(stash_root: Path, clip_id: str, record: dict) -> Path:
    """Portrait engine summary (per subject: views, picks, gate counts). Compact JSON
    (mirrors producer); lives under portraits/ beside the *.png extractions."""
    p = portrait_path(stash_root, clip_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(record, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return p


def read_portrait(stash_root: Path, clip_id: str) -> dict | None:
    p = portrait_path(stash_root, clip_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def write_provenance(stash_root: Path, clip_id: str, record: dict) -> Path:
    """Per-clip audit/idempotency record — what source produced these artifacts,
    when, with what fps. The Storage port's traceability seam: source media (S3
    objects) expires (~1 week), so this is the durable answer to "what made this".
    Per-clip only — NOTHING accumulates across visits (no person memory)."""
    p = provenance_path(stash_root, clip_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def read_provenance(stash_root: Path, clip_id: str) -> dict | None:
    p = provenance_path(stash_root, clip_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def run_path(stash_root: Path, clip_id: str) -> Path:
    return clip_dir(stash_root, clip_id) / "run.json"


def manifest_path(stash_root: Path, clip_id: str) -> Path:
    return clip_dir(stash_root, clip_id) / "manifest.json"


def write_manifest(stash_root: Path, clip_id: str, record: dict) -> Path:
    """R12 — per-clip 산출물 tier 지도 {파일→substrate|product|surface|ops}.
    "이 클립 디렉토리의 각 파일은 무엇인가"에 선언이 답하게 하는 기록.
    매 런 마지막에 last-run-wins로 재기록(run.json과 같은 규칙)."""
    p = manifest_path(stash_root, clip_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def write_run(stash_root: Path, clip_id: str, record: dict) -> Path:
    """Per-clip RUN trace — OBSERVABILITY of run behaviour: what ran, how long, what
    failed (the operational complement to provenance.json's run-IDENTITY; the
    openpilot rlog/loggerd analogue). Each stage row's `name` is a registry.ANALYZERS
    node, so the declared graph keys it. Per-clip, last-run-wins (nothing accumulates,
    same rule as provenance)."""
    p = run_path(stash_root, clip_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def read_run(stash_root: Path, clip_id: str) -> dict | None:
    p = run_path(stash_root, clip_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


EMOTION_FRAME_COLUMNS = {
    "track_id": "int64", "frame_idx": "int64",
    "valence": "float64", "em_conf": "float64", "arousal": "float64",
}


def emotion_frame_path(stash_root: Path, clip_id: str) -> Path:
    return clip_dir(stash_root, clip_id) / "emotion_frame.parquet"


def write_emotion_frame(stash_root: Path, clip_id: str, rows: list[dict]) -> Path:
    """Per-(track,frame) emotion valence/em_conf/arousal — OBSERVABILITY: the per-frame
    half of the emotion reading the inspector used to RE-COMPUTE (emotion.json persists
    only the per-person baseline). float64 = FULL precision ON PURPOSE: the inspector
    rounds to 4dp at read-side, so a full-precision persisted value reads back
    byte-identical to the recompute (the gate_trace generalization, on a live channel)."""
    p = emotion_frame_path(stash_root, clip_id)
    _validate(rows, EMOTION_FRAME_COLUMNS, name="emotion_frame")
    p.parent.mkdir(parents=True, exist_ok=True)
    _to_table(rows, EMOTION_FRAME_COLUMNS).write_parquet(p)
    return p


def read_emotion_frame(stash_root: Path, clip_id: str) -> pl.DataFrame | None:
    p = emotion_frame_path(stash_root, clip_id)
    return pl.read_parquet(p) if p.exists() else None

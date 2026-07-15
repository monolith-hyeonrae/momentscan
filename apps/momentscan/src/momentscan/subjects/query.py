"""SubjectQuery — the 0th query's dispatcher + the reference_face strategy (C2).

"WHO is this run about" is criterion matching like everything else: the query's
SOURCE picks its SPACE (seat rule → depth policy · reference face → biometric
embedding). Every strategy converges to the SAME attribution.json record shape
(roles + evidence) → tubelets and everything downstream never change (C3).

reference_face (implemented 2026-07-03): a reference photo → ArcFace embedding
→ cos against each subject's detection-embedding centroid → target subject.
Threshold measured on the corpus (same-clip portrait refs): same-person cos
0.48–0.80 (min = a MASKED wearer) vs cross-person max 0.166 → TAU_REF=0.30
holds margin both ways. Caveat: same-clip refs are the upper bound; cross-day
reference generalization is unmeasured (no data yet).
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np
import polars as pl

from momentscan.store.stash import read_detections, write_attribution

log = logging.getLogger("momentscan.subjects.query")

TAU_REF = 0.30    # measured (see module docstring); below = "this person is not in the clip"
MIN_EMB = 10      # a subject needs this many embeddings for a trustworthy centroid


def parse_subject_query(s: str | None) -> dict:
    """CLI/Job string → SubjectQuery {strategy, params}.
    None/"seat" → seat_rule (the current default) · "face:<photo>" → reference_face."""
    if not s or s == "seat":
        return {"strategy": "seat_rule", "params": {}}
    if s.startswith("face:"):
        return {"strategy": "reference_face", "params": {"ref": s[len("face:"):]}}
    raise ValueError(f"unknown subject query {s!r} (expected 'seat' or 'face:<photo>')")


def _ref_embedding(ref_path: str | Path) -> np.ndarray | None:
    """Reference photo → normalized ArcFace embedding of its LARGEST face.
    Same model pack as detect (buffalo_l), detection+recognition only."""
    import contextlib
    import io

    import cv2

    img = cv2.imread(str(ref_path))
    if img is None:
        return None
    with contextlib.redirect_stdout(io.StringIO()):   # insightface provider dumps
        from insightface.app import FaceAnalysis
        app = FaceAnalysis(name="buffalo_l", allowed_modules=["detection", "recognition"])
        app.prepare(ctx_id=0, det_size=(640, 640))
    faces = app.get(img)
    if not faces:
        return None
    f = max(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))
    return np.asarray(f.normed_embedding, dtype=np.float32)


def resolve_reference_face(out_root, clip_id: str, ref_path: str | Path,
                           *, tau: float = TAU_REF) -> dict:
    """reference_face strategy → the attribution.json record (same shape as the
    seat rule: roles + valid + evidence), written to the stash.

    roles = {target: "main"} ONLY — the query semantics is "this run is about
    THIS person": other subjects are not constituted (fancam semantics). valid
    honesty: no subject above tau → valid=False, roles={} (downstream tubelets
    refuses loudly rather than constituting the wrong person)."""
    t0 = time.perf_counter()
    e = _ref_embedding(ref_path)
    record: dict = {"clip_id": clip_id, "method": "reference-face",
                    "ref": str(ref_path), "tau": tau}
    if e is None:
        record.update({"ride_type": "NONE", "roles": {}, "valid": False,
                       "reason": "no face found in the reference photo", "cos": {}})
    else:
        det = read_detections(out_root, clip_id)
        cos: dict[int, float] = {}
        for sid in det["subject_id"].unique().to_list():
            E = np.array([r for r in det.filter(pl.col("subject_id") == sid)["embedding"].to_list()
                          if r is not None], dtype=np.float32)
            if len(E) < MIN_EMB:
                continue
            E /= (np.linalg.norm(E, axis=1, keepdims=True) + 1e-9)
            c = E.mean(0)
            c /= np.linalg.norm(c)
            cos[int(sid)] = round(float(e @ c), 4)
        record["cos"] = {str(k): v for k, v in sorted(cos.items())}
        record["candidates"] = sorted(cos)
        if not cos:
            record.update({"ride_type": "NONE", "roles": {}, "valid": False,
                           "reason": "no subject with enough embeddings"})
        else:
            best = max(cos, key=cos.get)
            rest = sorted((v for k, v in cos.items() if k != best), reverse=True)
            conf, margin = cos[best], round(cos[best] - (rest[0] if rest else 0.0), 4)
            valid = conf >= tau
            record.update({
                "ride_type": "QUERY",
                "roles": {str(best): "main"} if valid else {},
                "confidence": conf, "margin": margin, "valid": valid,
            })
            if not valid:
                record["reason"] = f"best cos {conf} < tau {tau} — reference person not in this clip"
            # a close runner-up is usually an UNSTITCHED FRAGMENT of the same person
            # (measured: s18's ref pulls its own fragment s13 to 0.40) — surface it.
            if valid and margin < 0.15:
                record["note"] = "low margin — runner-up may be an unstitched fragment of the target"
    path = write_attribution(out_root, clip_id, record)
    record["elapsed_s"] = round(time.perf_counter() - t0, 3)
    lvl = logging.INFO if record["valid"] else logging.WARNING
    log.log(lvl, "subject_query.done", extra={k: record.get(k) for k in
            ("method", "roles", "confidence", "margin", "valid", "reason")})
    record["attribution_path"] = str(path)
    return record

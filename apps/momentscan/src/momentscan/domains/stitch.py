"""Re-id stitch — broken tracks → subjects (step0a, second half).

Track vs Subject (README data model): ``track_id`` is the *immutable* temporal
anchor (IoU association — short, breaks easily); ``subject_id`` is the *mutable*
identity anchor that re-joins broken tracks by face embedding. A rider whose
track breaks (head turn, occlusion) keeps ONE subject across the pieces — which
is what Profile accumulation and per-person residuals anchor on.

This is a pure post-pass over the collected detection rows at clip end, NOT a
bus module: the bus carries immutable per-frame signals; subject assignment is
a clip-scope, revisable aggregation.

Ported spirit: personmemory ``MemoryBank`` (cosine on L2-normalized ArcFace
embeddings, ``tau_merge=0.5``). Postgres/pgvector and EMA bank state dropped —
within one clip a track's representative is simply its normalized mean.

Stitch guards (anchor boundaries are sacred — a merged/swapped anchor poisons
every Profile built on it):
  - **temporal overlap** — tracks sharing any frame are different people by
    definition (two faces in one frame); never stitched, whatever the cosine.
  - tracks without embeddings stay their own subject.
"""

from __future__ import annotations

import numpy as np

STITCH_TAU = 0.5  # cosine ≥ tau → same person (legacy MemoryBank tau_merge)


def stitch_tracks(rows: list[dict], *, tau: float = STITCH_TAU) -> dict:
    """Assign ``subject_id`` to every row in place; return stitch summary.

    ``subject_id`` = the smallest ``track_id`` in the stitched component, so it
    is stable, clip-scoped, and equals ``track_id`` wherever no stitch happened.
    """
    frames: dict[int, set[int]] = {}
    embs: dict[int, list[np.ndarray]] = {}
    for r in rows:
        tid = r["track_id"]
        frames.setdefault(tid, set()).add(r["frame_idx"])
        if r.get("embedding") is not None:
            embs.setdefault(tid, []).append(np.asarray(r["embedding"], dtype=np.float32))

    reps: dict[int, np.ndarray] = {}
    for tid, vecs in embs.items():
        m = np.mean(vecs, axis=0)
        n = float(np.linalg.norm(m))
        if n > 0:
            reps[tid] = m / n

    # Union-find over stitchable pairs.
    parent = {tid: tid for tid in frames}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    tids = sorted(frames)
    merges: list[dict] = []
    for i, a in enumerate(tids):
        for b in tids[i + 1:]:
            if a not in reps or b not in reps:
                continue
            if frames[a] & frames[b]:        # co-occurring → two people. Never.
                continue
            cos = float(reps[a] @ reps[b])
            if cos >= tau:
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)
                    merges.append({"tracks": [a, b], "cos": round(cos, 3)})

    for r in rows:
        r["subject_id"] = find(r["track_id"])

    subjects: list[dict] = []
    for sid in sorted({find(t) for t in tids}):
        member_tids = [t for t in tids if find(t) == sid]
        member_reps = [reps[t] for t in member_tids if t in reps]
        coherence = None
        if len(member_reps) >= 2:
            center = np.mean(member_reps, axis=0)
            center /= np.linalg.norm(center)
            coherence = round(float(min(v @ center for v in member_reps)), 3)
        subjects.append({
            "subject_id": sid,
            "tracks": member_tids,
            "length": sum(len(frames[t]) for t in member_tids),
            "coherence": coherence,      # min member→center cos; low = unstable_subject
        })

    return {"n_subjects": len(subjects), "subjects": subjects, "stitches": merges}


def track_purity(rows: list[dict], *, tau: float = 0.35, min_run: int = 3) -> list[dict]:
    """Within-track identity self-consistency — flags the failure mode stitch
    CANNOT fix: an IoU-continuous track that swaps person mid-span (crossing
    occlusion, aux ducking behind main). Per track, each frame embedding's
    cosine to the track representative; a sustained low-cos run marks frames
    where the track may not be the same person. Diagnostic only — rendered on
    the timeline and reported in stitch.json; no automatic split until
    measured cases justify one.
    """
    by_tid: dict[int, list[tuple[int, np.ndarray]]] = {}
    for r in rows:
        if r.get("embedding") is not None:
            v = np.asarray(r["embedding"], dtype=np.float32)
            n = float(np.linalg.norm(v))
            if n > 0:
                by_tid.setdefault(r["track_id"], []).append((r["frame_idx"], v / n))

    out: list[dict] = []
    for tid in sorted(by_tid):
        frames_v = sorted(by_tid[tid], key=lambda fv: fv[0])
        mat = np.stack([v for _, v in frames_v])
        rep = mat.mean(axis=0)
        rep /= np.linalg.norm(rep)
        cos = mat @ rep
        runs: list[tuple[int, int]] = []
        start = None
        for i, c in enumerate(cos):
            if c < tau:
                start = i if start is None else start
            elif start is not None:
                if i - start >= min_run:
                    runs.append((start, i - 1))
                start = None
        if start is not None and len(cos) - start >= min_run:
            runs.append((start, len(cos) - 1))
        out.append({
            "track_id": tid,
            "n_emb": len(frames_v),
            "min_cos": round(float(cos.min()), 3),
            "p05_cos": round(float(np.percentile(cos, 5)), 3),
            "suspect_runs": [
                {"start_frame": frames_v[a][0], "end_frame": frames_v[b][0],
                 "min_cos": round(float(cos[a:b + 1].min()), 3)}
                for a, b in runs
            ],
        })
    return out

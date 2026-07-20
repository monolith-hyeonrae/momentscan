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

STITCH_TAU = 0.5    # cosine ≥ tau → same person (legacy MemoryBank tau_merge)
# tier-2 조각 구조(2026-07-06): 절대 τ는 대비-명백 조각을 놓친다 — test_0 s13→s18이
# cos 0.496으로 머리카락 차이 미달(차선 후보와의 마진은 0.284로 명백). identity
# 게이트의 상대귀속 문법 재적용: 중첩 0 AND cos ≥ FRAG_TAU AND (cos − 차선) ≥
# FRAG_MARGIN. 코퍼스 측정 앵커: 음성 대조군(중첩>0=물리적 타인) max 0.32 →
# floor 0.40; mask_2 유령-먼지 쌍들의 마진 ≤0.031 → margin 0.15가 정확히 자름
# (s13 0.284 · dual_2 s2→s0 0.426 통과). 방향 없음(union) — 유지 근거는 정체성.
FRAG_TAU = 0.40
FRAG_MARGIN = 0.15


def stitch_tracks(rows: list[dict], *, tau: float = STITCH_TAU,
                  frag_tau: float = FRAG_TAU, frag_margin: float = FRAG_MARGIN) -> dict:
    """Assign ``subject_id`` to every row in place; return stitch summary.

    ``subject_id`` = the smallest ``track_id`` in the stitched component (tier-1),
    so it is stable, clip-scoped, and equals ``track_id`` wherever no stitch
    happened. 예외: tier-2 조각 구조는 **호스트(프레임 多)의 id를 유지** — 하류·
    동결 eval의 키 연속성 (조각이 라이더 id를 삼키면 안 된다).
    두 단: tier-1 = 절대 cos ≥ tau (트랙 쌍) · tier-2 = 컴포넌트 쌍의 상대귀속
    조각 구조(위 상수 주석) — 둘 다 시간중첩 가드가 최상위 (공존 = 타인, 예외 없음).
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

    # ── tier-2: 조각 구조 (컴포넌트 수준 상대귀속) — 고정점까지 반복 ──────────
    frag_merges: list[dict] = []
    while True:
        comp_tracks: dict[int, list[int]] = {}
        for t in tids:
            comp_tracks.setdefault(find(t), []).append(t)
        comps = sorted(comp_tracks)
        crep: dict[int, np.ndarray] = {}
        cframes: dict[int, set[int]] = {}
        for c, members in comp_tracks.items():
            vecs = [v for t in members if t in embs for v in embs[t]]
            fr = set().union(*(frames[t] for t in members))
            cframes[c] = fr
            if vecs:
                m = np.mean(vecs, axis=0)
                n = float(np.linalg.norm(m))
                if n > 0:
                    crep[c] = m / n
        cos_of = {}
        for i, a in enumerate(comps):
            for b in comps[i + 1:]:
                if a in crep and b in crep:
                    cos_of[(a, b)] = float(crep[a] @ crep[b])
        merged = False
        for (a, b), cos in sorted(cos_of.items(), key=lambda kv: -kv[1]):
            if cos < frag_tau or (cframes[a] & cframes[b]):
                continue
            # 차선 = 쌍의 양쪽 각각이 제3 컴포넌트와 갖는 최고 cos (엄격판: 양쪽 다
            # 대비-명백해야 병합 — 두 호스트 사이에서 애매한 허브-조각을 막는다)
            second = max((cos_of.get((min(x, c), max(x, c)), -1.0)
                          for x in (a, b) for c in comps if c not in (a, b)), default=-1.0)
            if cos - second < frag_margin:
                continue
            # tier-2는 호스트(프레임 多)가 subject_id 유지 — "조각이 호스트에 합류".
            # min-id면 조각(작은 id)이 라이더 id를 삼켜 동결 eval·하류 키 연속성이
            # 깨진다 (s13이 s18을 흡수하는 사고). tier-1의 min-id 관행은 불변.
            host, frag = (a, b) if len(cframes[a]) >= len(cframes[b]) else (b, a)
            parent[find(frag)] = find(host)
            frag_merges.append({"components": [a, b], "cos": round(cos, 3),
                                "second": round(second, 3),
                                "margin": round(cos - second, 3)})
            merged = True
            break                                # 컴포넌트가 바뀌었으니 재계산
        if not merged:
            break

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

    return {"n_subjects": len(subjects), "subjects": subjects, "stitches": merges,
            "frag_stitches": frag_merges}   # tier-2 관측면 — 인스펙터/감사가 근거를 봄


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

"""3d — shared seed eval harness (jepa-poc §6). Eval-only labels, never training.

The SAME harness scores Track A and Track B (both write the same
candidates.jsonl schema) — that sameness is what makes the comparison fair.
Do NOT fork it per track. The decision gate runs on these numbers. Include
same-clip rider pairs as a person-conditioning probe (§5): two riders share
one forcing function, so trajectory differences are purely person-conditioned.

Label schema — one JSON line per labeled item in ``<stash>/eval/labels.jsonl``
(developer-picked ~50 good / ~50 bad per product; a VLM may pre-label, a human
verifies):

    {"clip_id", "track_id", "product": "likeness"|"highlight",
     "frame_idx": int, "verdict": "good"|"bad", "note": str}

Scoring (per product, across all clips with candidates):
  - **precision@1 / hit@K** — pick lands within ``tol`` frames of a labeled
    GOOD moment (pick near a labeled BAD counts against precision@1).
  - **recall@K** — fraction of labeled good moments covered by any candidate.

``make_template`` bootstraps labeling: renders current candidates as a review
sheet (frames + ids) and emits pre-filled rows with empty verdicts to fill.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import cv2

from momentscan.stash import read_candidates

log = logging.getLogger("momentscan.eval")

# Frozen label files (pairs.jsonl / pair_verdicts.jsonl, 168 pairs) carry the
# RETIRED product name "profile" — data is immutable; the live reading is
# named likeness. Map at scoring time, never rewrite the files.
PRODUCT_ALIAS = {"profile": "likeness"}

TOL_FRAMES = 12          # ±2s at 6fps: a pick this close to a labeled moment "matches" it


def _labels_path(out_root) -> Path:
    return Path(out_root) / "eval" / "labels.jsonl"


def load_labels(out_root) -> list[dict]:
    p = _labels_path(out_root)
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _cand_frames(c: dict) -> list[int]:
    picks = [c["pick"], *c.get("alternatives", [])]
    return [p["frame_idx"] if "frame_idx" in p else p["peak_frame"] for p in picks]


def score(out_root, clip_ids: list[str], *, tol: int = TOL_FRAMES) -> dict:
    labels = load_labels(out_root)
    if not labels:
        return {"ok": False, "error": f"no labels at {_labels_path(out_root)}"}
    by_key: dict[tuple, list[dict]] = {}
    for c in (c for cid in clip_ids for c in read_candidates(Path(out_root), cid)):
        by_key.setdefault((c["clip_id"], c["track_id"], c["product"]), []).append(c)

    out: dict = {"ok": True, "n_labels": len(labels), "products": {}}
    for product in ("likeness", "highlight"):
        plabels = [L for L in labels if L["product"] == product]
        if not plabels:
            continue
        good = [L for L in plabels if L["verdict"] == "good"]
        hit1 = hitk = covered = picks1 = 0
        for (cid, tid, prod), cands in by_key.items():
            if prod != product:
                continue
            glab = [L["frame_idx"] for L in good if L["clip_id"] == cid and L["track_id"] == tid]
            blab = [L["frame_idx"] for L in plabels
                    if L["verdict"] == "bad" and L["clip_id"] == cid and L["track_id"] == tid]

            def near(f: int, ls: list[int]) -> bool:
                return any(abs(f - x) <= tol for x in ls)

            for c in cands:
                frames = _cand_frames(c)
                picks1 += 1
                if near(frames[0], glab) and not near(frames[0], blab):
                    hit1 += 1
                if any(near(f, glab) for f in frames):
                    hitk += 1
        for L in good:
            cands = by_key.get((L["clip_id"], L["track_id"], product), [])
            allf = [f for c in cands for f in _cand_frames(c)]
            if any(abs(L["frame_idx"] - f) <= tol for f in allf):
                covered += 1
        out["products"][product] = {
            "n_good": len(good), "n_bad": len(plabels) - len(good),
            "precision@1": round(hit1 / picks1, 3) if picks1 else None,
            "hit@K": round(hitk / picks1, 3) if picks1 else None,
            "recall@K": round(covered / len(good), 3) if good else None,
        }
    log.info("eval.done", extra=out)
    return out


def make_template(out_root, clip_id: str, *, tile_w: int = 480) -> dict:
    """Review sheet + empty-verdict label rows for one clip's candidates."""
    cands = read_candidates(Path(out_root), clip_id)
    if not cands:
        return {"ok": False, "error": "no candidates — run `momentscan select` first"}
    eval_dir = Path(out_root) / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)

    trace = Path(out_root) / clip_id / "detect.mp4"
    cap = cv2.VideoCapture(str(trace))
    tiles, rows = [], []
    for c in cands:
        for p in [c["pick"], *c.get("alternatives", [])]:
            f = int(p.get("frame_idx", p.get("peak_frame")))
            cap.set(cv2.CAP_PROP_POS_FRAMES, f)
            ok, img = cap.read()
            if not ok:
                continue
            h, w = img.shape[:2]
            img = cv2.resize(img, (tile_w, int(h * tile_w / w)))
            label = f"{c['product']} {c['rider_role']} f={f}"
            cv2.putText(img, label, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
            cv2.putText(img, label, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            tiles.append(img)
            rows.append({"clip_id": clip_id, "track_id": c["track_id"],
                         "product": c["product"], "frame_idx": f, "verdict": "", "note": ""})
    cap.release()

    sheet = eval_dir / f"{clip_id}_review.jpg"
    n3 = len(tiles) - len(tiles) % 3
    rows_img = [cv2.hconcat(tiles[i:i + 3]) for i in range(0, n3, 3)] or tiles[:1]
    cv2.imwrite(str(sheet), cv2.vconcat(rows_img))
    tmpl = eval_dir / f"{clip_id}_labels_template.jsonl"
    tmpl.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    result = {"ok": True, "clip_id": clip_id, "n_items": len(rows),
              "review_sheet": str(sheet), "template": str(tmpl),
              "labels_path": str(_labels_path(out_root))}
    log.info("eval.template", extra=result)
    return result


# ── pairwise eval (the eval of record — see pairwise-labeling-principle) ─────
# Absolute verdicts drift between/within labelers; A-vs-B with an explicit
# product question is stable, and matches the future buy/choose/skip signal.

import random as _random

import polars as _pl


def make_pairs(out_root, *, n_random: int = 2, seed: int = 7,
               products: tuple[str, ...] = ("likeness", "highlight"),
               out_name: str = "pairs.jsonl",
               cross_vs: str | None = None,
               roles: tuple[str, ...] | None = None) -> dict:
    """Generate comparison pairs per (clip, track, product) into eval/<out_name>.

    Pairs: rank-adjacent candidates (system claims c1>c2>c3) + each extreme
    candidate vs a random same-track frame (system claims candidate>random).
    ``system_pref`` records the system's claim — scoring = human agreement.

    ``products``/``out_name`` keep lanes separate — the frozen 168-pair lane
    (pairs.jsonl) is never regenerated for a new product. ``cross_vs`` adds a
    top-vs-top pair against another product's pick on the same track (e.g.
    portrait_top vs profile_top under the PORTRAIT question — directly tests
    대표 사진 ≠ 무표정 측정 컷).
    """
    rng = _random.Random(seed)
    ev = Path(out_root) / "eval"
    pairs = []
    for cdir in sorted(Path(out_root).glob("*/candidates.jsonl")):
        clip_id = cdir.parent.name
        tubes = _pl.read_parquet(cdir.parent / "tubelets.parquet")
        cands = read_candidates(Path(out_root), clip_id)
        tops = {(c["track_id"], c["product"]): _cand_frames(c)[0] for c in cands}
        for c in cands:
            if c["product"] not in products:
                continue
            if roles is not None and c["rider_role"] not in roles:
                continue   # e.g. portrait lane = main only (aux: small/masked → noisy taste)
            frames = _cand_frames(c)
            tt = tubes.filter((_pl.col("track_id") == c["track_id"])
                              & (_pl.col("scene_phase") == "ride"))
            pool = [f for f in tt["frame_idx"].to_list() if all(abs(f - x) > 12 for x in frames)]
            rnd = rng.sample(pool, min(n_random, len(pool))) if pool else []
            duos = [(frames[i], frames[i + 1]) for i in range(len(frames) - 1)]
            duos += [(frames[0], rnd[0])] if rnd else []
            duos += [(frames[-1], rnd[-1])] if len(rnd) > 1 else []
            if cross_vs is not None:
                other = tops.get((c["track_id"], cross_vs))
                if other is not None and other != frames[0]:
                    duos.append((frames[0], other))
            for a, b in duos:
                flip = rng.random() < 0.5          # don't let "left = system pick" leak
                A, B = (b, a) if flip else (a, b)
                pairs.append({"clip_id": clip_id, "track_id": c["track_id"],
                              "rider_role": c["rider_role"], "product": c["product"],
                              "a_frame": int(A), "b_frame": int(B),
                              "system_pref": "b" if flip else "a"})
    ev.mkdir(parents=True, exist_ok=True)
    (ev / out_name).write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in pairs) + "\n", encoding="utf-8")
    out = {"ok": True, "n_pairs": len(pairs), "pairs_path": str(ev / out_name)}
    log.info("eval.pairs", extra=out)
    return out


def make_segment_pairs(out_root, *, seed: int = 11, fps: int = 6,
                       out_name: str = "pairs_segment.jsonl") -> dict:
    """E010 segment eval lane — the measuring stick for boundaries and sets.

    Highlight SEGMENTS compared as PLAYING clips (a moment is a span, not a
    still). Three pair kinds per main track (docs/products.md highlight §평가):
      - vs-random-window  candidate seg vs a random same-length ride window
                          (system claims candidate)      → WHEN recall floor
      - rank-adjacent     #1 vs #2, #2 vs #3             → ranking precision
      - boundary          same moment, v2 boundary vs +2s-shifted boundary
                          (system claims v2)             → boundary quality
    product strings: "highlight_segment" / "highlight_boundary" (the boundary
    question is different — 잘림의 자연스러움, not 순간의 가치).
    """
    rng = _random.Random(seed)
    ev = Path(out_root) / "eval"
    pairs = []
    shift = 2 * fps                                       # boundary perturbation

    for cdir in sorted(Path(out_root).glob("*/candidates.jsonl")):
        clip_id = cdir.parent.name
        tubes = _pl.read_parquet(cdir.parent / "tubelets.parquet")
        for c in read_candidates(Path(out_root), clip_id):
            if c["product"] != "highlight" or c["rider_role"] != "main":
                continue
            tt = tubes.filter((_pl.col("track_id") == c["track_id"])
                              & (_pl.col("scene_phase") == "ride"))
            ts_of = dict(zip(tt["frame_idx"], tt["timestamp_ms"], strict=True))
            ride_fx = sorted(ts_of)
            if not ride_fx:
                continue

            def span_f(seg) -> tuple[int, int]:           # ms → nearest ride frames
                fa = min(ride_fx, key=lambda f: abs(ts_of[f] - seg["start_ms"]))
                fb = min(ride_fx, key=lambda f: abs(ts_of[f] - seg["end_ms"]))
                return int(fa), int(max(fb, fa + 1))

            segs = [c["pick"], *(c.get("alternatives") or [])]
            spans = [span_f(s) for s in segs]
            duos: list[tuple[tuple, tuple, str]] = []
            # rank-adjacent
            for i in range(len(spans) - 1):
                duos.append((spans[i], spans[i + 1], "highlight_segment"))
            # vs-random-window: same length, inside ride, not overlapping cands
            f_lo, f_hi = ride_fx[0], ride_fx[-1]
            for sp in spans[:2]:
                L = sp[1] - sp[0]
                cand_starts = [s for s in range(f_lo, f_hi - L)
                               if all(s + L < a or s > b for a, b in spans)]
                if cand_starts:
                    s0 = rng.choice(cand_starts)
                    duos.append((sp, (s0, s0 + L), "highlight_segment"))
            # boundary: top seg vs +2s-shifted copy (same moment, worse cut)
            a, b = spans[0]
            if b + shift <= f_hi:
                duos.append(((a, b), (a + shift, b + shift), "highlight_boundary"))

            for sa, sb, product in duos:
                flip = rng.random() < 0.5
                A, B = (sb, sa) if flip else (sa, sb)
                pairs.append({
                    "clip_id": clip_id, "track_id": c["track_id"],
                    "rider_role": c["rider_role"], "product": product,
                    "a_frame": int(A[0]), "b_frame": int(B[0]),  # span starts = verdict key
                    "a_span": [int(A[0]), int(A[1])], "b_span": [int(B[0]), int(B[1])],
                    "system_pref": "b" if flip else "a"})

    ev.mkdir(parents=True, exist_ok=True)
    (ev / out_name).write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in pairs) + "\n", encoding="utf-8")
    out = {"ok": True, "n_pairs": len(pairs), "pairs_path": str(ev / out_name)}
    log.info("eval.segment_pairs", extra=out)
    return out


def score_pairs(out_root, *, verdicts_name: str = "pair_verdicts.jsonl") -> dict:
    """Agreement between the system's preference claims and human winners."""
    vp = Path(out_root) / "eval" / verdicts_name
    if not vp.exists():
        return {"ok": False, "error": f"no verdicts at {vp}"}
    rows = [json.loads(ln) for ln in vp.read_text(encoding="utf-8").splitlines() if ln.strip()]
    out: dict = {"ok": True, "n_verdicts": len(rows), "products": {}}
    for r in rows:
        r["product"] = PRODUCT_ALIAS.get(r["product"], r["product"])   # display name only
    for product in sorted({r["product"] for r in rows}):
        pr = [r for r in rows if r["product"] == product and r.get("winner")]
        decided = [r for r in pr if r["winner"] in ("a", "b")]
        agree = sum(1 for r in decided if r["winner"] == r["system_pref"])
        out["products"][product] = {
            "n": len(pr), "n_decided": len(decided), "n_tie": len(pr) - len(decided),
            "agreement": round(agree / len(decided), 3) if decided else None,
        }
    log.info("eval.pairs.score", extra=out)
    return out


def rescore_pairs(out_root) -> dict:
    """Re-derive the SYSTEM's preference per labeled pair from the *current*
    features/policy, then score against the frozen human winners. This is how
    one labeling session measures every system version (E-log methodology):
    human winners are pinned to frame pairs; system_pref is recomputed.
    """
    import numpy as np

    from momentscan.products.select import frame_scores

    vp = Path(out_root) / "eval" / "pair_verdicts.jsonl"
    if not vp.exists():
        return {"ok": False, "error": f"no verdicts at {vp}"}
    verdicts = [json.loads(ln) for ln in vp.read_text(encoding="utf-8").splitlines() if ln.strip()]
    pvp = Path(out_root) / "eval" / "pair_verdicts_portrait.jsonl"   # portrait lane (E008)
    if pvp.exists():
        verdicts += [json.loads(ln) for ln in pvp.read_text(encoding="utf-8").splitlines() if ln.strip()]

    cache: dict = {}

    def scores_for(clip_id, tid):
        if (clip_id, tid) not in cache:
            s_ = frame_scores(out_root, clip_id, tid)
            cache[(clip_id, tid)] = {
                k: dict(zip(s_["fx"].tolist(), s_[k].tolist(), strict=True))
                for k in ("likeness", "highlight", "portrait")
            }
        return cache[(clip_id, tid)]

    res: dict = {"ok": True, "products": {}}
    agg: dict = {}
    for v in verdicts:
        if v["winner"] not in ("a", "b"):
            continue
        prod = PRODUCT_ALIAS.get(v["product"], v["product"])
        s = scores_for(v["clip_id"], v["track_id"])[prod]
        sa, sb = s.get(v["a_frame"]), s.get(v["b_frame"])
        if sa is None or sb is None or not (np.isfinite(sa) and np.isfinite(sb)):
            continue
        pref = "a" if sa > sb else "b"
        d_, a_ = agg.get(prod, (0, 0))
        agg[prod] = (d_ + 1, a_ + (1 if pref == v["winner"] else 0))
    for prod, (d_, a_) in agg.items():
        res["products"][prod] = {"n_decided": d_, "agreement": round(a_ / d_, 3) if d_ else None}
    log.info("eval.rescore", extra=res)
    return res

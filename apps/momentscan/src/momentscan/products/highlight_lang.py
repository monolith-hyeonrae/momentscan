"""highlight-lang — the CONTEXT-conditioned WHEN, matched in language space.

highlight's criterion lives in the attraction's CONTEXT (docs/criterion-source.md):
a highlight = the rider achieving what THIS attraction expects. That criterion is
naturally a *sentence* ("a joyful peak reaction while descending"), not a geometric
target — and it varies per attraction (soccer≠racing). So this stage:

  1. DESCRIBES each candidate moment in structured language, composing tools by their
     STRENGTH — our person-relative signals for the REACTION (image encoders are weak
     at fine expression), an image encoder for the SCENE/context (where CLIP is strong),
     temporal signals for WHEN/phase.
  2. MATCHES that description to the authored attraction EXPECTATION with an LLM judge
     (natural language — resolves compound/nuanced conditions where CLIP cosine ties).

Cost: the generic WHEN (select.frame_scores) pre-filters a handful of CANDIDATES;
the LLM judges them ALL in ONE call — feasible at 2000 clips/day. The EXPECTATION is
a preset = the context control (edit text per attraction, no recoding).

Pilot findings behind this (memory core-criterion-source): image-CLIP on faces fails
(encoder weak at expression); signal→sentence→LLM-judge resolves compound conditions
(joyful AND facing-camera) that CLIP cosine cannot; CLIP IS decisive on SCENE.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import numpy as np

from momentscan.store.stash import clip_dir

# ── the authored attraction EXPECTATIONS — the CONTEXT control ────────────────
# Edit / add per attraction. A different attraction = a different sentence here, no
# code change (criterion-source: highlight's criterion comes from the context).
EXPECTATIONS: dict[str, str] = {
    "default": (
        "A peak highlight moment for an outdoor go-kart hill-descent ride: the rider "
        "bursts into a big joyful, excited, open-mouthed reaction — laughing or cheering "
        "with delight — while riding downhill. Turned-away, blurry, calm, or merely "
        "neutral moments are NOT highlights."
    ),
    # a DIFFERENT attraction criterion — same machinery, different retrieval (context control).
    "thrill_tense": (
        "A highlight for a scary thrill ride: the rider shows a tense, scared, nervous, "
        "white-knuckle frightened reaction. Calm or purely joyful/laughing moments are NOT the target."
    ),
}

# scene / attraction-context descriptions for the CLIP scene reader (its strength).
SCENE_PROMPTS = [
    "at the starting area, stationary, about to begin",
    "going downhill on a go-kart with an open road ahead",
    "surrounded by dry grass, reeds and open sky outdoors",
    "next to a building, wall or structure",
    "moving fast with strong motion mid-ride",
]

CLIP_MODEL = "openai/clip-vit-large-patch14"
JUDGE_MODEL = "Qwen/Qwen2.5-VL-3B-Instruct"
TOP_K = 24            # candidates the generic WHEN proposes for the LLM to judge
JUDGE_CHUNK = 6       # LLM judges this many at a time (small = no repetition lock-in)
CAND_SEP_S = 1.5      # min temporal separation between candidates (dedup)
IMPACT_BURST = 3.0    # impact above this reads as a "sudden burst"


def _describe(v: float, jaw: float, smile: float, impact: float,
              pose_class: str, rel_bright: bool, scene: str) -> str:
    """A moment → structured sentence: [reaction (our signals)] + [scene (image)] +
    [action (temporal)]. Reaction is person-relative where the baseline allows."""
    # reaction is driven by the ACCURATE emotion signal (valence), NOT brittle jaw geometry
    # (a val=0.9 laugh with jaw just under a threshold must not read as a mild smile). The
    # mouth-open geometry is a modifier, not the gate.
    mouth = ", mouth wide open" if jaw > 0.22 else ""
    if v > 0.55:
        react = f"a big, intense, joyful reaction — clearly delighted, laughing or cheering{mouth}"
    elif v > 0.25:
        react = f"a clearly happy, positive, smiling reaction{mouth}"
    elif v > 0.1:
        react = "a mild, mildly-pleasant expression"
    elif v < -0.15:
        react = "a tense, uneasy, nervous, negative expression"
    else:
        react = "a calm, neutral, unremarkable face"
    pose = "turned to the side" if pose_class == "side" else "facing forward"
    burst = "in a sudden burst of reaction" if impact > IMPACT_BURST else "steadily"
    rel = " unusually expressive for this person," if rel_bright else ""
    return f"A rider showing {react}, {pose},{rel} {burst}, {scene}."


def _pick_candidates(fx, when, is_ride, fps: int, top_k: int) -> list[int]:
    """Generic-WHEN top-k candidate frame indices, temporally deduped, ride-only."""
    order = [i for i in np.argsort(-np.nan_to_num(when, nan=-1.0))
             if is_ride[i] and np.isfinite(when[i])]
    sep = int(CAND_SEP_S * fps)
    picked: list[int] = []
    for i in order:
        f = int(fx[i])
        if all(abs(f - int(fx[j])) >= sep for j in picked):
            picked.append(i)
        if len(picked) >= top_k:
            break
    return picked


def _clip_scene(crops: list) -> list[str]:
    """CLIP scene label per crop — the image encoder on its STRENGTH (scene/context)."""
    import torch
    from transformers import CLIPModel, CLIPProcessor
    model = CLIPModel.from_pretrained(CLIP_MODEL).to("cuda" if torch.cuda.is_available() else "cpu").eval()
    proc = CLIPProcessor.from_pretrained(CLIP_MODEL, use_fast=True)
    dev = model.device
    inp = proc(text=SCENE_PROMPTS, images=crops, return_tensors="pt", padding=True).to(dev)
    with torch.no_grad():
        prob = model(**inp).logits_per_image.softmax(-1).cpu().numpy()
    labels = [SCENE_PROMPTS[int(p.argmax())].split(",")[0] for p in prob]
    del model, inp                      # free the scene encoder before the LLM judge loads
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return labels


def _llm_judge(descriptions: list[str], expectation: str) -> list[float]:
    """Qwen natural-language judge — one call rates all candidates 0-10 vs the
    expectation (resolves compound/nuance CLIP cosine cannot). Text-only (no
    torchvision needed). Missing/garbled scores → 0.0."""
    import torch
    from transformers import AutoTokenizer, Qwen2_5_VLForConditionalGeneration
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    tok = AutoTokenizer.from_pretrained(JUDGE_MODEL)
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        JUDGE_MODEL, torch_dtype=torch.bfloat16, device_map="cuda").eval()
    # TWO things are load-bearing on a 3B judge:
    #  (1) reasoning — a terse "N: score" collapses to noise; a short reason first is accurate.
    #  (2) SMALL chunks — in a long list the model repetition-locks ("0 - No joyful reaction"
    #      for all, even an obvious laugh). ~6 per call keeps fresh attention (verified).
    scores = [0.0] * len(descriptions)
    for s0 in range(0, len(descriptions), JUDGE_CHUNK):
        chunk = descriptions[s0:s0 + JUDGE_CHUNK]
        prompt = (
            "You are selecting highlight moments for a ride video.\n"
            f"HIGHLIGHT EXPECTATION: {expectation}\n\n"
            "For each numbered moment description, give a match score 0-10 (10 = strongly matches "
            "the expectation, 0 = does not) and a very short reason. The joyful reaction itself is "
            "what matters most. Reply one per line as `N: score - reason`.\n\n"
            + "\n".join(f"{i + 1}. {d}" for i, d in enumerate(chunk)))
        msgs = [{"role": "user", "content": prompt}]
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inp = tok([text], return_tensors="pt").to(model.device)
        with torch.no_grad():
            out = model.generate(**inp, max_new_tokens=48 * len(chunk) + 64, do_sample=False)
        resp = tok.batch_decode(out[:, inp.input_ids.shape[1]:], skip_special_tokens=True)[0]
        for m in re.finditer(r"(?m)^\s*(\d+)\s*[:\.\)]\s*(\d+(?:\.\d+)?)", resp):
            idx, sc = int(m.group(1)) - 1, float(m.group(2))
            if 0 <= idx < len(chunk):
                scores[s0 + idx] = min(sc, 10.0) / 10.0
    return scores


def score_highlight_lang(out_root, clip_id: str, *, expectation: str = "default",
                         top_k: int = TOP_K, fps: int = 6) -> dict:
    """Language-matched, context-conditioned highlight scoring. Writes highlight_lang.json."""
    import cv2
    import polars as pl

    from momentscan.products.select import frame_scores

    t0 = time.perf_counter()
    exp_text = EXPECTATIONS.get(expectation, EXPECTATIONS["default"])
    cdir = clip_dir(Path(out_root), clip_id)

    det_path = cdir / "detections.parquet"
    if not det_path.exists():
        return {"clip_id": clip_id, "ok": False, "reason": "no detections.parquet"}
    D = pl.read_parquet(det_path)
    tid = int(D.group_by("track_id").len().sort("len", descending=True)["track_id"][0])
    bbm = {(r["track_id"], r["frame_idx"]): r["bbox"] for r in D.iter_rows(named=True)}

    fs = frame_scores(out_root, clip_id, tid, fps=fps)
    fx = np.asarray(fs["fx"])
    when = np.asarray(fs["when"], float)
    val = np.asarray(fs["valence"], float)
    imp = np.asarray(fs["impact"], float)
    isr = np.asarray(fs["is_ride"])

    cand = _pick_candidates(fx, when, isr, fps, top_k)
    if not cand:
        return {"clip_id": clip_id, "ok": False, "reason": "no ride candidates"}

    # per-frame reaction signals (gate_trace) + person baseline (emotion.json)
    gt = pl.read_parquet(cdir / "gate_trace.parquet").filter(pl.col("track_id") == tid)
    gm = {r["frame_idx"]: r for r in gt.iter_rows(named=True)}
    ej = cdir / "emotion.json"
    p90 = 1.0
    if ej.exists():
        base = json.loads(ej.read_text(encoding="utf-8")).get("riders", {}).get(str(tid), {}).get("baseline", {})
        p90 = base.get("p90", 1.0) or 1.0

    # wide crops of the candidates from the source window (for the CLIP scene read).
    src = cdir / "detect_h264.mp4"
    src = src if src.exists() else Path.home() / "Videos" / "reaction_test" / f"{clip_id}.mp4"
    if not src.exists():
        return {"clip_id": clip_id, "ok": False, "reason": "no source video for scene read (crop track window expired)"}
    from PIL import Image
    cap = cv2.VideoCapture(str(src))

    def _wide(fr, bb):
        H, W = fr.shape[:2]
        x0, y0, x1, y1 = bb
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        w, h = (x1 - x0) * 3.4, (y1 - y0) * 3.8
        cy += h * 0.10
        a, b, c, d = max(0, int(cx - w / 2)), max(0, int(cy - h / 2)), min(W, int(cx + w / 2)), min(H, int(cy + h / 2))
        cc = fr[b:d, a:c]
        return Image.fromarray(cv2.cvtColor(cc, cv2.COLOR_BGR2RGB)) if cc.size else None

    crops, keep = [], []
    for i in cand:
        f = int(fx[i])
        if (tid, f) not in bbm:
            continue
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, fr = cap.read()
        if not ok:
            continue
        im = _wide(fr, bbm[(tid, f)])
        if im is not None:
            crops.append(im)
            keep.append(i)
    cap.release()
    if not crops:
        return {"clip_id": clip_id, "ok": False, "reason": "candidate crops unreadable"}

    scenes = _clip_scene(crops)
    descs = []
    for i, sc in zip(keep, scenes):
        f = int(fx[i])
        r = gm.get(f, {})
        descs.append(_describe(val[i], r.get("jaw") or 0.0, r.get("smile") or 0.0, imp[i],
                               r.get("pose_class", ""), val[i] >= p90, sc))
    lang = _llm_judge(descs, exp_text)

    cands = sorted(
        ({"frame": int(fx[i]), "when_generic": round(float(when[i]), 3),
          "lang_score": round(float(s), 3), "valence": round(float(val[i]), 3),
          "scene": sc, "description": d}
         for i, s, sc, d in zip(keep, lang, scenes, descs)),
        key=lambda c: -c["lang_score"])
    record = {"clip_id": clip_id, "track_id": tid, "expectation": expectation,
              "expectation_text": exp_text, "n_candidates": len(cands), "candidates": cands,
              "ok": bool(cands)}
    (cdir / "highlight_lang.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    record["ms"] = int((time.perf_counter() - t0) * 1000)
    return record

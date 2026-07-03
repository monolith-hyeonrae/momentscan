"""FashionCLIP enrichment — typed visit-scoped fashion attributes (eyewear style,
headwear, face covering) via patrickjohncyh/fashion-clip zero-shot over the crop
track. Refines parse.py's cheap presence (worn/not) into TYPED attributes,
collected on likeness ("오늘 이 사람의 ID"). Mirrors appearance-engine's
FashionCLIPClassifier (Cat A — Accessory); prompts are face-crop oriented (the
crop track is face-framed, so clothing/Cat-W stays in the body-crop adapter).

Fashion is visit-invariant, so a sample of frames per subject is enough.
Layout: <out>/<clip>/fashion.json
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import cv2
import numpy as np

from momentscan.stash import clip_dir, write_fashion

log = logging.getLogger("momentscan.fashion")

MODEL = "patrickjohncyh/fashion-clip"
_MEAN = np.array([0.48145466, 0.4578275, 0.40821073], np.float32)
_STD = np.array([0.26862954, 0.26130258, 0.27577711], np.float32)
N_SAMPLE = 12

# face-crop accessory prompt sets (label, prompt) — fashion-clip distribution.
_PROMPTS: dict[str, list[tuple[str, str]]] = {
    "eyewear": [
        ("none", "a face with no glasses"),
        ("clear_glasses", "a face wearing clear prescription eyeglasses"),
        ("sunglasses", "a face wearing dark sunglasses"),
    ],
    "headwear": [
        ("none", "a bare head with no hat"),
        ("cap", "a person wearing a baseball cap"),
        ("beanie", "a person wearing a knit beanie"),
        ("bucket_hat", "a person wearing a bucket hat"),
        ("hood", "a person wearing a jacket hood over the head"),
    ],
    "covering": [
        ("none", "a face with the mouth and nose uncovered"),
        ("mask", "a face wearing a protective face mask over the mouth and nose"),
        ("scarf", "a scarf or neck gaiter covering the lower face"),
    ],
}


def _preprocess(imgs_bgr: list[np.ndarray]) -> np.ndarray:
    out = []
    for im in imgs_bgr:
        rgb = cv2.cvtColor(cv2.resize(im, (224, 224)), cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        out.append((rgb - _MEAN) / _STD)
    return np.stack(out).transpose(0, 3, 1, 2)        # (B,3,224,224)


def _sample_frames(path: Path, n: int) -> list[np.ndarray]:
    cap = cv2.VideoCapture(str(path))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        cap.release(); return []
    idxs = np.linspace(0, total - 1, min(n, total)).astype(int)
    out = []
    for i in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i)); ok, img = cap.read()
        if ok:
            out.append(img)
    cap.release()
    return out


def extract_fashion(out_root, clip_id: str, *, fps: int = 6) -> dict:
    import torch
    from transformers import CLIPModel, CLIPTokenizer

    t0 = time.perf_counter()
    cdir = clip_dir(Path(out_root), clip_id)
    man_path = cdir / "crops" / "manifest.json"
    if not man_path.exists():
        return {"clip_id": clip_id, "ok": False, "reason": "no crop track (run `crops` first)"}
    manifest = json.loads(man_path.read_text(encoding="utf-8"))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = CLIPModel.from_pretrained(MODEL).to(device).eval()
    tok = CLIPTokenizer.from_pretrained(MODEL)

    # pre-tokenize prompts per axis (text fixed; visit-invariant)
    text = {axis: (tok([c[1] for c in ch], padding=True, return_tensors="pt").to(device),
                   [c[0] for c in ch]) for axis, ch in _PROMPTS.items()}

    subjects = []
    for s in manifest["subjects"]:
        frames = _sample_frames(cdir / "crops" / s["file"], N_SAMPLE)
        if not frames:
            continue
        px = torch.from_numpy(_preprocess(frames)).to(device)
        attrs = {}
        for axis, (enc, labels) in text.items():
            with torch.no_grad():
                out = model(input_ids=enc["input_ids"], attention_mask=enc["attention_mask"],
                            pixel_values=px)
            prob = out.logits_per_image.softmax(dim=-1).mean(0).cpu().numpy()  # mean over frames
            j = int(prob.argmax())
            attrs[axis] = {"winner": labels[j], "conf": round(float(prob[j]), 3),
                           "probs": {lab: round(float(p), 3) for lab, p in zip(labels, prob)}}
        subjects.append({"subject_id": int(s["subject_id"]), "role": s["role"],
                         "n_sampled": len(frames), **attrs})

    record = {"clip_id": clip_id, "model": MODEL.split("/")[-1], "subjects": subjects, "ok": bool(subjects)}
    write_fashion(out_root, clip_id, record)
    record["ms"] = int((time.perf_counter() - t0) * 1000)
    log.info("fashion.done", extra={"clip_id": clip_id, "n_subjects": len(subjects)})
    return record

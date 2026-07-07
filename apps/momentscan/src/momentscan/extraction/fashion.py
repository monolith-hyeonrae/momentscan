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


# ── color identity — appearance-engine Cat W #86-89 포팅 (P1-2b, 2026-07-07) ──
# 원본: component2/color_identity.py — "외부 stylistic surface"(의상+모자+안경+귀걸이+
# 목걸이; 헤어/피부 자연색 제외)의 Lab K-means 팔레트. momentscan판 = **방문-집계**:
# 프레임별이 아니라 같은 12-프레임 샘플의 픽셀을 풀링해 방문 전체의 팔레트 하나.
# SegFormer는 parse.py와 같은 모델(라벨맵 홈 = parse.py의 CelebAMask-HQ 인덱스).
_SEG_MODEL = "jonathandinu/face-parsing"
_EYE_G, _HAT, _EAR_R, _NECK_L, _CLOTH = 3, 14, 15, 16, 18
_STYLE_LABELS = (_CLOTH, _HAT, _EYE_G, _EAR_R, _NECK_L)
# 소유권 규칙 (momentscan 신규 — 원본은 단일-인물 per-image라 불요): 크롭 프레임에
# 타인의 어깨/패딩이 크게 걸치므로(감사 ⓓ), "프레임의 모든 cloth"가 아니라 **이
# subject의 cloth**만 — 중심-최근접 얼굴 성분을 씨앗으로, 헤어/목을 다리 삼아
# 인접 성분을 반복 흡수하는 영역-성장. (cap_1 s0: 전경 타인 패딩이 팔레트를 지배
# → near-black 오염을 육안 디버그로 확인, 이 규칙이 수리.)
_FACE_SEED = (1, 2, 4, 5, 6, 7, 10, 11, 12)   # skin·nose·eyes·brows·lips
_HAIR, _NECK = 13, 17                           # 연결 통로 (팔레트엔 미포함)
_HEAD_ONLY = (_HAT, _EAR_R)                     # 헤어-다리로만 허용되는 라벨 (비니 등)
_GROW_PX = 7                                    # 인접 판정 팽창 반경
# 다리 규칙: cloth/eye_g/neck_l = 얼굴∪(얼굴-인접 목) 직접-인접만 — 헤어를 다리로
# 쓰면 헤어에 닿은 타인 어깨가 딸려온다(cap_1 프레임 4·6 잔류 누수로 실증).
# hat/ear_r만 얼굴-인접 헤어를 추가 다리로 (비니는 헤어 위에만 닿음).
_SEG_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_SEG_STD = np.array([0.229, 0.224, 0.225], np.float32)
_CI_K = 5                # 원본 상수 그대로 (K-means k)
_CI_HL_AREA = 0.05       # highlight 자격: 면적 비율 하한
_CI_MIN_PX = 200         # 미만 = 관측 부족 → None (정직한 결측)
_CI_PX_CAP = 2000        # 프레임당 픽셀 상한 (풀링 균형)


def _lab_to_hex(lab) -> str:
    from skimage.color import lab2rgb
    rgb = np.clip(lab2rgb(np.asarray(lab, np.float64).reshape(1, 1, 3)).reshape(3), 0, 1)
    return "#%02x%02x%02x" % tuple(int(round(float(v) * 255)) for v in rgb)


def _adjacent_comps(target: np.ndarray, seed_reach: np.ndarray) -> np.ndarray:
    """target 라벨 마스크의 연결 성분 중 seed_reach와 교차하는 것들의 합집합."""
    n, cc = cv2.connectedComponents(target.astype(np.uint8))
    out = np.zeros_like(target, dtype=bool)
    if n <= 1:
        return out
    for i in np.unique(cc[seed_reach & target.astype(bool)]):
        if i > 0:
            out |= (cc == i)
    return out


def _owner_style_mask(m: np.ndarray) -> tuple[np.ndarray, float | None]:
    """subject-소유 스타일 픽셀만 + 소유자 hair/face 픽셀비. 씨앗 = 중심-최근접 얼굴
    성분; cloth/안경류는 얼굴∪소유자-목 직접-인접, 모자류는 +소유자-헤어 인접.
    hair 비율 = hair_match 관측성 신호 (P1-④ⓓ: 후드-업이면 hair≈0 — typed headwear
    레인은 내려진 재킷 후드를 conf 0.9+로도 오인해 신호로 못 씀, mask_1 실증).
    얼굴 없음 → (빈 마스크, None)."""
    face = np.isin(m, _FACE_SEED).astype(np.uint8)
    n, cc = cv2.connectedComponents(face)
    if n <= 1:
        return np.zeros_like(face, dtype=bool), None
    # 얼굴 자격 검증: skin 성분이 눈/코/입 라벨을 실제로 포함해야 얼굴 — 손/목덜미
    # 같은 맨살 성분이 "얼굴"로 등록되면 소유자의 손이 닿는 자기 옷 전체가 taint로
    # 전멸한다 (dual_1 s0 = 전 프레임 own 0의 원인이었음).
    facial_core = np.isin(m, (2, 4, 5, 6, 7, 10, 11, 12))   # nose·eyes·brows·lips
    h, w = m.shape
    cy, cx = h * 0.4, w * 0.5                      # 크롭 기하: 소유자 얼굴 ≈ 중앙 상단
    best, best_d = 0, 1e18
    qualified: list[int] = []
    for i in range(1, n):
        comp = (cc == i)
        if int(comp.sum()) < 50 or int((comp & facial_core).sum()) < 30:
            continue                                # 이목구비 없는 skin 덩어리 = 손/몸
        qualified.append(i)
        ys, xs = np.nonzero(comp)
        d = (ys.mean() - cy) ** 2 + (xs.mean() - cx) ** 2
        if d < best_d:
            best, best_d = i, d
    if best == 0:
        return np.zeros_like(face, dtype=bool), None
    owner_face = (cc == best)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (_GROW_PX, _GROW_PX))
    reach_face = cv2.dilate(owner_face.astype(np.uint8), kernel).astype(bool)
    # 타인 얼굴(프레임에 걸친) — 배제가 아니라 **접촉-다수결**의 상대측. 이진 taint는
    # 어깨-맞댄 duo(dual_1)에서 두 사람 옷이 양쪽 얼굴에 다 닿아 전멸을 낳았다.
    others = np.isin(cc, [q for q in qualified if q != best])
    reach_others = cv2.dilate(others.astype(np.uint8), kernel).astype(bool) if others.any() else \
        np.zeros_like(owner_face, dtype=bool)

    owner_neck = _adjacent_comps(m == _NECK, reach_face)
    owner_hair = _adjacent_comps(m == _HAIR, reach_face)
    hair_ratio = float(owner_hair.sum()) / max(float(owner_face.sum()), 1.0)
    reach_body = cv2.dilate((owner_face | owner_neck).astype(np.uint8), kernel).astype(bool)
    reach_head = cv2.dilate((owner_face | owner_hair).astype(np.uint8), kernel).astype(bool)

    body_labels = tuple(l for l in _STYLE_LABELS if l not in _HEAD_ONLY)
    cand = _adjacent_comps(np.isin(m, body_labels), reach_body) & np.isin(m, body_labels)
    cand |= _adjacent_comps(np.isin(m, _HEAD_ONLY), reach_head) & np.isin(m, _HEAD_ONLY)
    if not reach_others.any():
        return cand, hair_ratio
    # 성분별 소유 배정: 소유자 도달면과의 접촉량 ≥ 타인 도달면과의 접촉량이어야 채택.
    reach_own = reach_body | reach_head
    n_s, scc = cv2.connectedComponents(np.isin(m, _STYLE_LABELS).astype(np.uint8))
    out = np.zeros_like(owner_face, dtype=bool)
    for i in np.unique(scc[cand]):
        if i == 0:
            continue
        comp = (scc == i)
        if int((comp & reach_own).sum()) >= int((comp & reach_others).sum()):
            out |= comp & cand
    return out, hair_ratio


def _color_identity(frames_bgr: list[np.ndarray], seg_model, device) -> tuple[dict | None, dict | None]:
    """방문-집계 의상 팔레트 → ({primary, secondary, highlight, palette_diversity},
    hair 관측성). 각 색 = {lab, hex, area}; highlight = 면적>5% 중 최고 채도 (없으면
    'neutral'). hair = {visible_frac: 소유자 hair/face 픽셀비 중앙값, n_frames} —
    후드-업이면 ≈0 (hair_match 이음매의 결측 신호)."""
    import torch
    from skimage.color import rgb2lab

    rng = np.random.default_rng(0)
    pool: list[np.ndarray] = []
    hair_ratios: list[float] = []
    for im in frames_bgr:
        rgb = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
        x = (cv2.resize(rgb, (512, 512)).astype(np.float32) / 255.0 - _SEG_MEAN) / _SEG_STD
        t = torch.from_numpy(x[None]).permute(0, 3, 1, 2).to(device)
        with torch.no_grad():
            logits = seg_model(pixel_values=t).logits
        up = torch.nn.functional.interpolate(logits, size=rgb.shape[:2],
                                             mode="bilinear", align_corners=False)
        m = up.argmax(1).cpu().numpy()[0]
        own, hr = _owner_style_mask(m)
        if hr is not None:
            hair_ratios.append(hr)
        px = rgb[own]
        if len(px) > _CI_PX_CAP:
            px = px[rng.choice(len(px), _CI_PX_CAP, replace=False)]
        if len(px):
            pool.append(px)
    hair = {"visible_frac": round(float(np.median(hair_ratios)), 3),
            "n_frames": len(hair_ratios)} if hair_ratios else None
    if not pool:
        return None, hair
    allpx = np.concatenate(pool)
    if len(allpx) < _CI_MIN_PX:
        return None, hair
    lab_all = rgb2lab((allpx.astype(np.float32) / 255.0).reshape(-1, 1, 3)).reshape(-1, 3)
    sample = lab_all if len(lab_all) <= 5000 else \
        lab_all[np.random.default_rng(0).choice(len(lab_all), 5000, replace=False)]
    from sklearn.cluster import KMeans
    km = KMeans(n_clusters=_CI_K, n_init=3, random_state=0).fit(sample)
    centers = km.cluster_centers_
    sizes = np.bincount(km.predict(lab_all), minlength=_CI_K).astype(np.int64)
    ratios = sizes / max(int(sizes.sum()), 1)
    order = np.argsort(-sizes)
    chroma = np.sqrt(centers[:, 1] ** 2 + centers[:, 2] ** 2)
    elig = np.where(ratios > _CI_HL_AREA)[0]
    hl = int(elig[np.argmax(chroma[elig])]) if len(elig) else None
    p = ratios[ratios > 1e-9]
    ent = float(-(p * np.log(p)).sum())

    def _c(i: int) -> dict:
        return {"lab": [round(float(v), 2) for v in centers[i]],
                "hex": _lab_to_hex(centers[i]), "area": round(float(ratios[i]), 3)}

    return {"primary": _c(int(order[0])), "secondary": _c(int(order[1])),
            "highlight": _c(hl) if hl is not None else "neutral",
            "palette_diversity": round(ent, 3),
            "n_px": int(sizes.sum()), "n_frames": len(pool)}, hair


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
    from transformers import SegformerForSemanticSegmentation
    seg = SegformerForSemanticSegmentation.from_pretrained(_SEG_MODEL).to(device).eval()

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
        ci, hair = _color_identity(frames, seg, device)
        subjects.append({"subject_id": int(s["subject_id"]), "role": s["role"],
                         "n_sampled": len(frames), **attrs,
                         "color_identity": ci, "hair": hair})

    record = {"clip_id": clip_id, "model": MODEL.split("/")[-1], "subjects": subjects, "ok": bool(subjects)}
    write_fashion(out_root, clip_id, record)
    record["ms"] = int((time.perf_counter() - t0) * 1000)
    log.info("fashion.done", extra={"clip_id": clip_id, "n_subjects": len(subjects)})
    return record

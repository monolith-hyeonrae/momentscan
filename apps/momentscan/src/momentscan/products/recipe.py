"""recipe — likeness.json → per-rider face recipe (88축 스키마, 오늘 Cat G 37축 채움).

출처: appearance-engine `adapters/momentscan.py` 변환 규약 흡수 (2026-07-20,
absorption-plan §1 A1). 구 어댑터는 별도 레포에서 momentscan 의 likeness.json 을
읽어 face recipe 를 조립했다 — 그 사상(mapping)을 momentscan 내부 스테이지로
들여왔다. 절단면(one-step-removed)은 레포-간 → 패키지-간으로 줄었을 뿐 산다:
recipe 는 likeness *답의 사상*이지 네 번째 질문(Product)이 아니다(엔진=질문 원칙,
change-forecast ④). 그래서 Product 신설 없이 likeness Product 의 outputs 에 recipe
를 additive 로 얹고, egress(Result 계약)에선 뺀다.

경계 계약: likeness.json(C11/LikenessV1)을 **읽기 전용**으로 소비한다 —
`validate_likeness` 로 형태를 확인하고(소비 지점 fail-fast) 읽기만, likeness.json 은
절대 쓰지 않는다. 기하 공식은 `perception/readings/face_axes.py`(측정 기판 비밀),
축 라벨·캘리 range 는 `recipe_axes.py`(도메인 정책 비밀) — 비밀 2종 분리.

좌표 변환 (A1 규약): momentscan 정준 좌표(y-up, z-out, RMS≈1)는 표정-회귀 neutral
(폴백=robust center)을 트랙 전체로 집계한 것이라 frontality 는 구성상 1.0 —
단일 정면 프레임이 아니다. face_axes 는 이미지 픽셀 규약(y-down)을 기대하므로
neutral>center 를 flip[1,-1,-1] → ×_PSEUDO_SCALE → +_PIXEL_MARGIN 으로 사영한다.
G 축은 전부 비율/각도라 스케일은 무차원(값은 pseudo-scale 에 불변).

채우지 못한 카테고리(Hair/Color/Accessories/Semantic/Wear)는 픽셀-속성 관측 스트림이
필요해 momentscan 이 아직 방출하지 않는다 — `unfilled` 에 사유와 함께 정직 보고,
절대 조용히 드롭하지 않는다.

원장 ④ 동승 (refactor-plan 미결 원장 ④): recipe 는 likeness.json 이 이미 방출하는
face_id·fashion·color_identity·samples 를 additive `"likeness"` 블록으로 패스스루한다 —
recipe.json 을 프리뷰의 단일 persisted 입력으로 완성하려는 소비 이음매다(C11 v1·
categories·unfilled 전부 무변). 그 필드로 H/A/W 축을 실제 *채우는* 사상은 D4 아카이브
enum 이 필요하고 unfilled 를 바꿔 특성화 골든과 충돌하므로 별도 후속으로 남긴다.
"""

from __future__ import annotations

import logging
import time

import numpy as np

from momentscan.infra.contracts import validate_likeness
from momentscan.infra.store.stash import read_appearance, write_recipes

from momentscan.perception.readings.face_axes import face_axes

from momentscan.products.recipe_axes import (
    _CALIBRATED_G_RANGES,
    G_AXES,
    G_CATEGORY_NAME,
    REGISTRY_VERSION,
    UNFILLED_AXES,
)

log = logging.getLogger("momentscan.recipe")

RECIPE_SCHEMA = "momentscan.recipe/v1"

# canonical(RMS≈1) → pseudo-pixel scale. 값 자체는 임의 — 전 G축이 비율/각도라
# 스케일 무차원이다. 좌표를 제정신 픽셀 범위에 두는 용도(A1). 캘리 아님.
_PSEUDO_SCALE = 200.0
# 좌상단 여백(px): 좌표를 양의 픽셀 공간으로 민다(min → +margin). 이미지 규약 정합용.
_PIXEL_MARGIN = 16.0
# 정준(y-up, z-out) → 이미지(y-down, z-in) 축 뒤집기. float32 유지 = 구 어댑터와
# 비트 경로 동일(특성화가 golden 과 ~1e-6 로 일치하는 근거).
_CANON_TO_IMAGE = np.array([1.0, -1.0, -1.0], dtype=np.float32)
# 출력 값 반올림 자릿수 — golden(구 어댑터) round(…, 6) 관례.
_VALUE_DECIMALS = 6

# name → (axis_id, korean, type, time_scale, description) · G01…G37 순서 목록.
_NAME_TO_META = {name: (aid, korean, typ, ts, desc)
                 for (aid, name, korean, typ, ts, desc) in G_AXES}
_G_ORDER = tuple(aid for (aid, *_rest) in G_AXES)


def _landmarks_from_rider(rider: dict) -> tuple[np.ndarray, str] | None:
    """rider 의 집계 기하 → 이미지-픽셀 랜드마크 (K,3) + 어느 기하를 썼는지.

    표정-회귀 neutral 우선, 없으면 raw robust center(구 ref) 폴백. 정준→이미지
    변환은 모듈 상단 상수 규약(A1). None = 기하 없음(측정 실패)."""
    which, geom = "neutral", (rider.get("neutral") or {}).get("center")
    if geom is None:
        which, geom = "center", rider.get("center")
    if geom is None:
        return None

    pts = np.asarray(geom, dtype=np.float32).reshape(-1, 3)
    pts = pts * _CANON_TO_IMAGE
    pts = pts * _PSEUDO_SCALE
    pts[:, :2] -= pts[:, :2].min(axis=0) - _PIXEL_MARGIN      # into positive pixel space

    return pts, which


def _axis_entry(name: str, value: str | float) -> tuple[str, dict]:
    """(axis_id, recipe 엔트리) — face_axes 값에 정책 메타 + 캘리 range 를 입힌다."""
    aid, korean, typ, ts, desc = _NAME_TO_META[name]
    rng = _CALIBRATED_G_RANGES.get(aid)
    entry = {
        "korean": korean,
        "name": name,
        "value": value if isinstance(value, (str, bool)) else round(float(value), _VALUE_DECIMALS),
        "type": typ,
        "time_scale": ts,
        "range": list(rng) if rng is not None else None,
        "description": desc,
    }
    return aid, entry


def _unfilled_report(filled_ids: set[str]) -> dict[str, list[str]]:
    """카테고리명 → 채우지 못한 axis_id 목록(순서 보존). G 축이 축퇴로 빠지면
    'Face Geometry' 도 여기 뜬다(정상은 전 G 채움 → G 카테고리 미등장)."""
    unfilled: dict[str, list[str]] = {}
    g_missing = [aid for aid in _G_ORDER if aid not in filled_ids]
    if g_missing:
        unfilled[G_CATEGORY_NAME] = g_missing
    for cat_name, ids in UNFILLED_AXES:
        missing = [aid for aid in ids if aid not in filled_ids]
        if missing:
            unfilled[cat_name] = missing
    return unfilled


def _recipe_from_rider(clip_id: str, tid: str, rider: dict) -> dict | None:
    """한 rider → recipe 레코드(88축 스키마, Cat G 채움 + unfilled 정직 보고)."""
    built = _landmarks_from_rider(rider)
    if built is None:
        return None
    pts, which = built

    values = face_axes(pts)
    filled: dict[str, dict] = {}
    for name, value in values.items():
        aid, entry = _axis_entry(name, value)
        filled[aid] = entry

    filled_ids = set(filled)
    geometry = {aid: filled[aid] for aid in _G_ORDER if aid in filled}
    categories = {G_CATEGORY_NAME: geometry} if geometry else {}

    return {
        "image_id": f"{clip_id}_t{tid}",
        "n_axes": len(filled_ids),
        "registry_version": REGISTRY_VERSION,
        "source": {
            "stage": RECIPE_SCHEMA,
            "geometry": which,                                # neutral | center
            "rider_role": rider.get("role"),
            "n_obs": rider.get("n_obs"),
            "split_half_drift": rider.get("split_half_drift"),
            "neutral_var_explained": (rider.get("neutral") or {}).get("var_explained"),
        },
        "categories": categories,
        "unfilled": _unfilled_report(filled_ids),
        # 원장 ④ 동승: likeness.json 이 이미 방출하는 비-기하 필드를 recipe 로 additive
        # 패스스루한다(어댑터-측 소비 확장, C11 v1 무변·categories/unfilled 불변). 목적 =
        # recipe.json 을 프리뷰(track lk-preview)의 **단일 persisted 입력**으로 완성 —
        # 순수 렌더러가 likeness.json 을 따로 열지 않게. H/A/W 축을 실제로 *채우는*
        # 것(enum 사상)은 D4 아카이브 어휘가 필요 + unfilled 를 바꿔 특성화와 충돌하므로
        # 별도 후속(원장 ④ 본체). 여기선 필드를 나른다(소비 이음매 신설).
        "likeness": {
            "face_id": rider.get("face_id"),
            "fashion": rider.get("fashion"),
            "color_identity": rider.get("color_identity"),
            "samples": rider.get("samples"),
        },
    }


def recipe_clip(out_root, clip_id: str) -> dict:
    """likeness.json 의 rider 별 face recipe 를 산출 — recipe/{image_id}.recipe.json.

    likeness.json 을 읽기 전용으로 소비(validate_likeness 로 형태 확인 후 읽기만)."""
    t0 = time.perf_counter()
    record = read_appearance(out_root, clip_id)
    if record is None:
        return {"clip_id": clip_id, "ok": False, "reason": "no likeness.json"}

    validate_likeness(record, clip_id=clip_id)               # C11 소비 지점 형태 검증(읽기 전용)

    recipes: dict[str, dict] = {}
    for tid, rider in (record.get("riders") or {}).items():
        r = _recipe_from_rider(clip_id, tid, rider)
        if r is not None:
            recipes[r["image_id"]] = r

    path = write_recipes(out_root, clip_id, recipes)
    elapsed_s = round(time.perf_counter() - t0, 3)
    log.info("recipe.done", extra={"clip_id": clip_id, "n_recipes": len(recipes), "elapsed_s": elapsed_s})
    return {"clip_id": clip_id, "ok": bool(recipes), "n_recipes": len(recipes),
            "recipe_dir": str(path.parent), "elapsed_s": elapsed_s}

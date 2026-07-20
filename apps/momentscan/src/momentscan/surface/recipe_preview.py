"""recipe.json → 13 shape key 투영 + 디자이너 리그 blender 프리뷰 렌더.

출처: appearance-engine `blender_export.py`(13키 투영·HAIR_LIBRARY 선택) +
`blender_render.py`(헤드-온리 하니스) 흡수 (2026-07-20, absorption-plan §1 A4·A5).
구 어댑터는 별도 레포에서 88축 recipe 를 디자이너 blend 의 shape key 로 사영해
프리뷰 PNG 를 냈다 — 그 사상과 렌더 하니스를 momentscan surface tier 로 들여왔다.

**두 경계로 나뉜다** (§2 선택-의존 사다리):
  1. 투영(`project_shape_keys`·`select_hair`) = 순수 수학. blender 불요 — recipe.json
     의 Cat G 값을 캘리 range 로 정규화(→[0,1])하고 shape key 별로 집계한다.
  2. 렌더(`render_recipe_montage`) = blender 바이너리 subprocess. 없으면 조용히
     열화하지 않고 CLI 경계에서 exit 2(설치 힌트) — venv 엔 bpy 가 없고(설계),
     디자이너 blend 를 blender-내부 python 이 연다.
투영과 렌더를 함수 경계로 분리해, 투영은 특성화 골든으로 봉인 가능하다.

surface 계약("persisted payload 위 순수 렌더러"): 입력 = recipe.json(recipe 스테이지가
persist). 프리뷰는 run 자동 산출이 아니라 온디맨드(무거운 것=온디맨드 선례) — 렌더
PNG 는 stash(output/l2)에 쓰지 않고 호출자가 지정한 preview-out 으로 나간다.

blend 판정(2026-07-20 실측): `_DEFAULT_BLEND`(body+basic_260527.blend, 449M)만
SHAPE_KEY_MAP 의 13키(head+base)·HAIR_LIBRARY 의 14 hair 메시와 정합한다. 자매
파일 body+basic.blend(103M)는 shape key 7개(이름 상이)·hair 3개뿐 = 스키마 불일치.
구 blender_render docstring 의 "currently body+basic.blend" 는 stale 였다.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any, NamedTuple

log = logging.getLogger("momentscan.recipe_preview")

# ── 디자이너 리그 blend ────────────────────────────────────────────────────
#
# 13 shape key(head+base) + 14 hair 메시를 담은 디자이너 제공 에셋. D0 이후 우산
# 관리 에셋 홈(~/repo/p981/assets/blender/, 개인정보 blend 와 동거·접근 통제)으로
# 이동 예정 — 이동 시 이 상수만 교체하면 된다(freshness 가 blend 를 external dep 로
# 추적하므로 교체가 프리뷰 stale 로 인지된다). 어느 git 에도 없어 D0 즉시 위험(B2).
_DEFAULT_BLEND: Path = Path.home() / "Downloads" / "body+basic_260527.blend"

# blender-내부에서 도는 apply/render 스크립트(bpy 사용, momentscan 은 절대 import
# 하지 않고 subprocess 로만 실행). recipe_preview 옆에 둔다.
_BLENDER_SCRIPT: Path = Path(__file__).with_name("_recipe_blender.py")

# 렌더 해상도(px)·타깃 창(정면 헤드-온리). 구 하니스 512² 관례.
_RENDER_PX: int = 512
# blender subprocess 타임아웃(초) — 449M blend open + N 잡 렌더. 한 프로세스에서
# blend 를 한 번만 열고 잡을 순회하므로 클립 수에 선형(넉넉히).
_RENDER_TIMEOUT_S: int = 900

# ── shape key → source axis 사상 (A4) ──────────────────────────────────────
#
# 각 shape key = 한 개 이상 Cat G 축의 집계. 집계 = "축별 range-정규화 값의 평균"
# (L/R 쌍은 비대칭 가드 적용). 구 blender_export.SHAPE_KEY_MAP 그대로.
SHAPE_KEY_MAP: dict[str, tuple[str, ...]] = {
    "Eyebrow_Thickness": ("G28", "G29"),   # brow_thickness_ratio L/R
    "Eyebrow_Length":    ("G26", "G27"),   # brow_length_ratio L/R
    "Eyebrow_Slant":     ("G32", "G33"),   # brow_slope_deg L/R
    "Eyebrow_Distance":  ("G35",),         # inter_brow_distance_ratio
    "Eye_Slant":         ("G13", "G14"),   # eye_tilt_deg L/R
    "Eye_Spacing":       ("G12",),         # inter_eye_face_width_ratio
    "Eye_Size":          ("G06", "G07"),   # eye_width_ratio L/R
    "Chin_Length":       ("G36",),         # chin_length_ratio
    "Nose_Position":     ("G17",),         # nose_bridge_length_ratio
    "Mouth_Position":    ("G23",),         # philtrum_length_ratio
    "Mouth_Size":        ("G19", "G20"),   # upper / lower lip thickness
    "Mouse_Corner":      ("G22",),         # mouth_corner_angle_deg (키 스펠 "Mouse" — 소비자 스키마)
    "Mouth_Width":       ("G21",),         # mouth_width_ratio
}

SHAPE_KEY_MESH_GROUP: str = "head+base"

# L/R 비대칭 허용치(정규화 [0,1] 스케일). 이 간극을 넘으면 랜드마크 노이즈로 의심해
# neutral(0.5)에서 먼 쪽을 버리고 가까운 쪽만 취한다. 구 어댑터 실측 튜닝값.
_LR_ASYMMETRY_THRESHOLD: float = 0.55

# gain 상단(×배). 미세 개성을 과장해 육안 판정을 돕는 A/B 상단값 — 구 프리뷰
# preview_recipe_gain_ab.png 관례(1.0 vs 2.2). L-B user-동행 판정의 재료.
GAIN_HI: float = 2.2


class Variant(NamedTuple):
    """몽타주 한 열(변형)의 투영 설정 + 표시. 몽타주 기계는 열이 gain-A/B 든 캘리
    양안이든 무관하게 이 변형 목록만 순회한다(variant-제네릭).

    title = 열 헤더(예 "×2.2", "race981-calib"). slug = 셀 PNG 파일명용(파일시스템
    안전 — 같은 gain 두 테이블이 파일명 충돌하지 않게 변형별 고유). ranges =
    axis_id→(lo,hi) 캘리 테이블 override(None=recipe.json 구운 range=legacy)."""
    title: str
    slug: str
    gain: float = 1.0
    ranges: dict[str, Any] | None = None

# ── hair library (A4) ───────────────────────────────────────────────────────
#
# body+basic_260527.blend 의 13 hair 자산(hair08·hair10 은 카탈로그 부재). 각 항목
# axes = Qwen 축 지문. picker 는 관측 레코드 대비 점수화 — H 축 미방출이면 None 폴백.
# 시각-검색 하이브리드(retriever 주입)는 승계하지 않음(C2) — attribute 선택만.
HAIR_LIBRARY: list[dict[str, Any]] = [
    {"id": "hair01", "name": "트윈번 + 옆머리",
     "axes": {"length": "medium", "bang": "side",    "parting": "left",   "shape": "tied",     "volume": "med"},
     "tags": ["twin_bun", "cute_style", "side_bang"]},
    {"id": "hair02", "name": "연보라 짧은 샤기",
     "axes": {"length": "short",  "bang": "side",    "parting": "center", "shape": "shaggy",   "volume": "high"},
     "tags": ["compact_spike", "anime_spike"]},
    {"id": "hair03", "name": "양갈래 브레이드",
     "axes": {"length": "long",   "bang": "side",    "parting": "center", "shape": "braided",  "volume": "med"},
     "tags": ["twin_braid", "pigtail_braid"]},
    {"id": "hair04", "name": "센터파트 보브",
     "axes": {"length": "medium", "bang": "curtain", "parting": "center", "shape": "bob",      "volume": "med"},
     "tags": ["sym_bob", "face_framing"]},
    {"id": "hair05", "name": "사이드뱅 볼륨 숏헤어",
     "axes": {"length": "short",  "bang": "side",    "parting": "left",   "shape": "layered",  "volume": "high"},
     "tags": ["ahoge", "anime_boy", "volumized_top"]},
    {"id": "hair06", "name": "볼륨 커튼뱅 중단발",
     "axes": {"length": "medium", "bang": "curtain", "parting": "center", "shape": "layered",  "volume": "high"},
     "tags": ["soft_curtain", "round_volume"]},
    {"id": "hair07", "name": "단정한 사이드뱅 숏헤어",
     "axes": {"length": "short",  "bang": "side",    "parting": "right",  "shape": "straight", "volume": "med"},
     "tags": ["neat_short", "clean_silhouette"]},
    {"id": "hair09", "name": "연보라 샤기 스파이키",
     "axes": {"length": "short",  "bang": "side",    "parting": "center", "shape": "shaggy",   "volume": "high"},
     "tags": ["star_spike", "wide_spread"]},
    {"id": "hair11", "name": "짧은 스파이키 레이어드",
     "axes": {"length": "short",  "bang": "side",    "parting": "left",   "shape": "layered",  "volume": "high"},
     "tags": ["messy_spike", "anime_male"]},
    {"id": "hair12", "name": "짧은 보울컷 풀뱅",
     "axes": {"length": "short",  "bang": "full",    "parting": "center", "shape": "straight", "volume": "low"},
     "tags": ["bowl_cut", "compact"]},
    {"id": "hair13", "name": "짧은 컬리/웨이브",
     "axes": {"length": "short",  "bang": "none",    "parting": "none",   "shape": "wavy",     "volume": "high"},
     "tags": ["curly_short", "wide_silhouette"]},
    {"id": "hair14", "name": "긴 생머리 풀뱅 하프업",
     "axes": {"length": "long",   "bang": "full",    "parting": "center", "shape": "straight", "volume": "med"},
     "tags": ["half_up", "top_knot", "long_front"]},
    {"id": "hair15", "name": "비대칭 보브",
     "axes": {"length": "medium", "bang": "side",    "parting": "left",   "shape": "bob",      "volume": "med"},
     "tags": ["asym_bob", "one_side_long"]},
]

# 점수 가중 — length 가 척추, parting/bang/shape 강, volume 은 소프트(1).
_SCORE_WEIGHTS: dict[str, int] = {"length": 5, "parting": 3, "bang": 3, "shape": 3, "volume": 1}
_AXIS_TO_VALUE_KEY: dict[str, str] = {
    "length":  "H01",
    "bang":    "H11",
    "parting": "H08",
    "shape":   "H15",
    "volume":  "H07",
}
# H06 hair_style_category == "up-do" 가 tied/braided shape 와 맞을 때 보너스.
_UPDO_SHAPE_BONUS: int = 4
_UPDO_TARGET_SHAPES: frozenset[str] = frozenset({"tied", "braided"})


# ── 순수 투영 (blender 불요) ────────────────────────────────────────────────

def _normalize(value: float, lo: float, hi: float) -> float:
    if hi == lo:
        return 0.5
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def _aggregate_normed(normed: list[float]) -> float:
    """한 shape key 의 정규화 값들을 pool. 1개=통과, 2개(L/R)=평균(단 간극이 비대칭
    임계 초과면 0.5 에서 먼 쪽 폐기), 3개+=평균. 구 blender_export._aggregate_normed."""
    if len(normed) == 1:
        return normed[0]
    if len(normed) == 2:
        a, b = normed
        if abs(a - b) > _LR_ASYMMETRY_THRESHOLD:
            return a if abs(a - 0.5) < abs(b - 0.5) else b
        return (a + b) / 2.0
    return sum(normed) / len(normed)


def _apply_gain(value: float, gain: float) -> float:
    """[0,1] shape key 값에 gain 을 곱해 개성 편차를 과장(neutral=0 기준). 클램프."""
    return max(0.0, min(1.0, value * gain))


def _flat_axis_entries(recipe: dict) -> dict[str, dict]:
    """recipe.json categories → {axis_id: entry}. entry 는 value·range 를 지참."""
    flat: dict[str, dict] = {}
    for axes in recipe.get("categories", {}).values():
        flat.update(axes)
    return flat


def project_shape_keys(recipe: dict, *, gain: float = 1.0,
                       ranges: dict[str, Any] | None = None) -> dict[str, float]:
    """recipe.json → {shape_key: [0,1]}. Cat G 값을 캘리 range 로 정규화 후 shape
    key 별 집계(L/R 가드) + gain. 순수 함수 — blender 불요, 특성화 골든으로 봉인.

    ranges = axis_id → (lo, hi) 캘리 테이블 override(원장 ① 캘리 양안). None(기본)이면
    recipe.json 에 구워진 range 를 쓴다 = 골든과 비트-동일. 주어지면 정규화 창만 그
    테이블로 갈아끼운다(값·집계·가드·gain 불변) — 재캘리 A/B 의 한 열."""
    entries = _flat_axis_entries(recipe)

    out: dict[str, float] = {}
    for sk_name, source_ids in SHAPE_KEY_MAP.items():
        normed: list[float] = []
        for axis_id in source_ids:
            entry = entries.get(axis_id)
            if entry is None:
                continue
            raw = entry.get("value")
            if not isinstance(raw, (int, float)) or isinstance(raw, bool):
                continue
            rng = ranges.get(axis_id) if ranges is not None else entry.get("range")
            if not rng or len(rng) != 2:
                continue
            normed.append(_normalize(float(raw), float(rng[0]), float(rng[1])))

        if normed:
            out[sk_name] = _apply_gain(_aggregate_normed(normed), gain)

    return out


def select_hair(recipe: dict) -> tuple[str | None, list[dict[str, Any]]]:
    """recipe.json → (chosen_hair_id, 랭킹 후보). H 축 미방출(현 momentscan)이면
    (None, []) — 소비자는 hair 없는 에셋으로 폴백. 구 blender_export._select_hair."""
    values = {aid: entry.get("value") for aid, entry in _flat_axis_entries(recipe).items()}

    if values.get("H09") is True:                            # is_bald
        return None, []

    observed = {
        "length":  values.get("H01"),
        "bang":    values.get("H11"),
        "parting": values.get("H08"),
        "shape":   values.get("H15"),
        "style":   values.get("H06"),
    }
    if observed["length"] not in ("short", "medium", "long"):
        return None, []

    scored: list[tuple[int, dict[str, Any]]] = []
    for h in HAIR_LIBRARY:
        s = 0
        for k, weight in _SCORE_WEIGHTS.items():
            if observed.get(k) is not None and observed.get(k) == h["axes"].get(k):
                s += weight
        if observed.get("style") == "up-do" and h["axes"]["shape"] in _UPDO_TARGET_SHAPES:
            s += _UPDO_SHAPE_BONUS
        scored.append((s, h))

    scored.sort(key=lambda x: -x[0])
    chosen_id = scored[0][1]["id"] if scored and scored[0][0] > 0 else None
    ranked = [{"id": h["id"], "name": h["name"], "tags": h.get("tags", []),
               "score": s, "axes": h["axes"]} for s, h in scored]
    return chosen_id, ranked


# ── blender 가용성 (선택-의존 사다리) ────────────────────────────────────────

def blender_binary() -> str | None:
    """blender 바이너리 경로 — 없으면 None(선택-의존 경계). doctor·CLI 공용."""
    return shutil.which("blender")


# ── 렌더 (blender subprocess) ────────────────────────────────────────────────

def _render_jobs(blend: Path, jobs: list[dict], preview_out: Path) -> None:
    """blender 바이너리를 한 번 띄워 jobs(=셀들)을 순회 렌더. blend 를 한 번만
    열어(449M) 잡마다 shape key 리셋+적용+hair 가시성+렌더 — open 비용 상각.

    죽을 때는 지참물과 함께(code-style §3): subprocess 실패면 stderr 꼬리를 실어
    RuntimeError. 조용한 빈-렌더 열화 금지."""
    binary = blender_binary()
    if binary is None:
        raise RuntimeError(
            "blender 바이너리 없음(shutil.which('blender')=None) — "
            "snap: `sudo snap install blender --classic`")

    payload = {"blend": str(blend), "render_px": _RENDER_PX, "jobs": jobs}
    payload_path = preview_out / "_payload.json"
    payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    cmd = [binary, "--background", "--python", str(_BLENDER_SCRIPT), "--", str(payload_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=_RENDER_TIMEOUT_S)
    if proc.returncode != 0:
        tail = (proc.stdout + proc.stderr)[-1500:]
        raise RuntimeError(f"blender 렌더 실패(rc={proc.returncode}, jobs={len(jobs)}):\n{tail}")

    missing = [j["out_png"] for j in jobs if not Path(j["out_png"]).exists()]
    if missing:
        raise RuntimeError(f"blender 가 렌더 PNG 를 안 냄({len(missing)}/{len(jobs)}): {missing[:3]}")


def _real_thumbnail(clip_dir: Path) -> Path | None:
    """클립의 대표 실사 썸네일 — portraits/*_rep.png(없으면 None). 몽타주 real 열."""
    portraits = clip_dir / "portraits"
    if not portraits.is_dir():
        return None
    reps = sorted(portraits.glob("*_rep.png"))
    return reps[0] if reps else None


def _load_recipe(clip_dir: Path) -> tuple[str, dict] | None:
    """클립의 recipe.json 하나 로드 → (image_id, recipe). 없으면 None."""
    recipe_dir = clip_dir / "recipe"
    files = sorted(recipe_dir.glob("*.recipe.json")) if recipe_dir.is_dir() else []
    if not files:
        return None
    recipe = json.loads(files[0].read_text(encoding="utf-8"))
    return recipe.get("image_id", files[0].stem), recipe


def render_recipe_montage(
    out_root: Path | str,
    clip_ids: list[str],
    *,
    variants: list[Variant],
    preview_out: Path | str,
    blend: Path | str | None = None,
) -> dict:
    """clip 들의 recipe → 디자이너 리그 프리뷰 몽타주(행=클립, 열=real + 변형별 3D).

    variants = 렌더할 열들(gain-A/B 든 캘리 양안이든). preview_out 에 셀 PNG +
    montage.png. blender 없으면 RuntimeError(호출 CLI 가 exit 2 로 번역)."""
    out_root = Path(out_root)
    preview_out = Path(preview_out)
    preview_out.mkdir(parents=True, exist_ok=True)
    blend_path = Path(blend) if blend is not None else _DEFAULT_BLEND

    if not blend_path.exists():
        raise RuntimeError(f"blend 파일 없음: {blend_path} (D0 이관 후 _DEFAULT_BLEND 교체)")

    rows = _build_rows(out_root, clip_ids, variants, preview_out)
    if not rows:
        return {"ok": False, "reason": "no recipe.json for any clip", "clip_ids": clip_ids}

    jobs = [cell for row in rows for cell in row["cells"]]
    _render_jobs(blend_path, jobs, preview_out)

    montage_path = preview_out / "montage.png"
    _assemble_montage(rows, variants, montage_path, blend_path)

    log.info("recipe_preview.montage", extra={"n_clips": len(rows), "n_variants": len(variants),
                                              "montage": str(montage_path)})
    return {"ok": True, "montage": str(montage_path), "n_clips": len(rows),
            "variants": [v.title for v in variants], "blend": str(blend_path)}


def _build_rows(out_root: Path, clip_ids: list[str], variants: list[Variant],
                preview_out: Path) -> list[dict]:
    """클립별로 recipe 를 로드해 변형별 렌더 잡 + real 썸네일을 담은 행 목록 구성."""
    rows: list[dict] = []
    for clip_id in clip_ids:
        clip_dir = out_root / clip_id
        loaded = _load_recipe(clip_dir)
        if loaded is None:
            log.warning("recipe_preview.skip", extra={"clip_id": clip_id, "reason": "no recipe.json"})
            continue
        image_id, recipe = loaded
        chosen_hair, _ = select_hair(recipe)                 # 변형-불변 — 루프 밖

        cells = []
        for v in variants:
            shape_keys = project_shape_keys(recipe, gain=v.gain, ranges=v.ranges)
            out_png = preview_out / f"{image_id}_{v.slug}.png"
            cells.append({"shape_key_values": shape_keys, "chosen_hair": chosen_hair,
                          "out_png": str(out_png), "gain": v.gain})

        rows.append({"clip_id": clip_id, "image_id": image_id,
                     "real": _real_thumbnail(clip_dir), "cells": cells,
                     "n_mapped": len(cells[0]["shape_key_values"])})
    return rows


def _assemble_montage(rows: list[dict], variants: list[Variant],
                      montage_path: Path, blend: Path) -> None:
    """PIL 로 그리드 몽타주 조립 — 행=클립, 열=[real] + 변형별 3D. 셀 라벨·헤더 포함."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n_rows = len(rows)
    n_cols = 1 + len(variants)                                # real + 변형별
    n_mapped = rows[0]["n_mapped"] if rows else 0

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(n_cols * 2.6, n_rows * 2.6),
                             squeeze=False)
    fig.suptitle(f"likeness → face_recipe(13 shape keys) → designer rig: "
                 f"{' vs '.join(v.title for v in variants)} ({n_mapped}/13 keys mapped)",
                 fontsize=11, x=0.02, ha="left")

    col_titles = ["real"] + [v.title for v in variants]
    for j, title in enumerate(col_titles):
        axes[0][j].set_title(title, fontsize=10)

    for i, row in enumerate(rows):
        _draw_real(axes[i][0], row)
        for k, cell in enumerate(row["cells"]):
            _draw_cell(axes[i][k + 1], cell)

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(montage_path, dpi=110)
    plt.close(fig)


def _draw_real(ax, row: dict) -> None:
    import matplotlib.image as mpimg

    if row["real"] is not None and Path(row["real"]).exists():
        ax.imshow(mpimg.imread(str(row["real"])))
    else:
        ax.text(0.5, 0.5, "(no thumb)", ha="center", va="center", fontsize=8)
    ax.set_ylabel(row["clip_id"], fontsize=9, rotation=0, ha="right", va="center")
    ax.set_xticks([])
    ax.set_yticks([])


def _draw_cell(ax, cell: dict) -> None:
    import matplotlib.image as mpimg

    png = Path(cell["out_png"])
    if png.exists():
        ax.imshow(mpimg.imread(str(png)))
    else:
        ax.text(0.5, 0.5, "(render missing)", ha="center", va="center", fontsize=8)
    ax.axis("off")

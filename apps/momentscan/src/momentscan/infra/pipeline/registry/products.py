"""Product declaration map — the VERTICAL view (one entry per deliverable).

ANALYZERS (analyzers.py) is the PRODUCER catalog (horizontal: one entry per
pipeline stage). The three deliverables are VERTICAL reads cutting across 4–9
stages, and a flat module bag has no place to make that smear visible — so a
product's logic ends up scattered (likeness: distribution은 likeness.py, exemplar
픽은 select.py) or fused with a sibling (highlight는 select.py에 융합돼 있다가
2026-07-03 highlight.py로 졸업). This map DECLARES each product's full read-chain
WITHOUT moving any code: it names the stages/units a product reads and the keys it
consumes, so `momentscan map products` can draw the vertical the pipeline hides.
Artifacts are NOT restated here — a read references an analyzer by NAME and the
renderer resolves `.artifact` from the catalog, so this map cannot drift from the
producer's real output path.

`state` records whether a product's DEFINITION has frozen: a molten product is
kept consolidated on purpose (splitting it freezes a boundary research is still
moving), a frozen one has earned its own module (portrait already did). The map
answers the feeling of scatter with LEGIBILITY, not premature consolidation.

교차 drift assert(reads/emitted_by 가 ANALYZERS 에 실존)는 __init__ 로 — 여기 asserts
는 products 내부 정합만(state·operation·egress⊆outputs).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class Product:
    name: str                                       # the deliverable (likeness/portrait/highlight)
    definition: str                                 # one line: what it is
    question: str                                    # G2: the value question this product answers (change-forecast ④)
    operation: str                                  # integrate | select(static) | select(temporal)
    reads: tuple[tuple[str, tuple[str, ...]], ...]  # (analyzer name, keys) — the vertical read-chain
    emitted_by: tuple[str, ...]                     # engine analyzer name(s) that physically produce it
    outputs: tuple[str, ...]                         # artifacts / candidate products it lands
    state: str                                       # "frozen" (definition settled) | "molten" (still researched)
    scorer: str = ""                                 # G2: coordinate of the scoring entry point ("" = 미구축, 정직).
                                                     # molten ∧ scorer=="" → registry_drift warn: 답을 다시 쓰기
                                                     # 전에 질문의 채점기를 세운다(change-forecast ④-①)
    note: str = ""
    egress: tuple[str, ...] = ()                     # the subset of `outputs` that CROSSES the service
                                                     # boundary OUTWARD (S3-out / the Result contract); the
                                                     # rest of `outputs` are intermediate traces. This makes
                                                     # INPUT/INTERMEDIATE/FINAL unambiguous (input=source,
                                                     # FINAL=egress, everything else in the stash=intermediate)
                                                     # AND doubles as the deliverable contract the service uploads.


PRODUCTS: tuple[Product, ...] = (
    Product(
        name='likeness',
        definition='visit-invariant ID (오늘 이 사람) — distribution + exemplar picks · 주탑승자만(2026-07-07)',
        question='어떻게 이 고객의 외형 특성을 이해하나',
        operation='integrate',
        reads=(('landmarks', ('blendshapes', 'transform')), ('tubelets', ('embedding',)), ('features', ('em_happy', 'au12_lip_corner', 'au25_lips_part', 'head_yaw_dev', 'head_pitch', 'face_blur')), ('parse', ('glasses_frac', 'hat_frac', 'cloth_frac')), ('fashion', ('eyewear', 'headwear', 'covering'))),
        emitted_by=('likeness', 'select', 'recipe'),
        outputs=('likeness.json', 'candidates.jsonl[likeness]', 'recipe/*.recipe.json'),
        state='molten',
        scorer='',
        note='three homes: likeness.py=distribution reading, select.py=exemplar picks (distinct readings — NOT a split to consolidate yet), recipe.py=답의 사상(88축 face recipe, absorption-plan A1). recipe.json 은 additive output 이자 egress 제외 — 반출/채점기 무접촉',
        egress=('likeness.json',),
    ),
    Product(
        name='portrait',
        definition='query-extraction gate → clean crop-track pixels · 주탑승자만(2026-07-07)',
        question='어떻게 좋은 얼굴을 선택하나',
        operation='select(static)',
        reads=(('tubelets', ('embedding',)), ('identity_dev', ('identity_deviation',)), ('landmarks', ('blendshapes', 'transform')), ('expression', ('blink', 'jaw')), ('pose', ('yaw', 'pitch', 'roll')), ('headpose6d', ('yaw', 'pitch', 'roll')), ('face_quality', ('crop_blur',)), ('parse', ('eye_lum_rel', 'mouth_vis')), ('crops', ('crop track',))),
        emitted_by=('portrait',),
        outputs=('portraits/*.png', 'portraits/portrait.json', 'gate_trace.parquet', 'candidates.jsonl[portrait,portrait_set]'),
        state='frozen',
        scorer='',
        note='definition froze E008–E009, already its own module; gate verdicts via gates.evaluate → gate_trace; pose(frontal)+headpose6d(profile) fused',
        egress=('portraits/portrait.json', 'portraits/*.png'),
    ),
    Product(
        name='highlight',
        definition='WHEN×WHICH — attraction × customer reaction over a segment · aux first-class(함께한 순간)',
        question='좋은 순간이란 무엇인가',
        operation='select(temporal)',
        reads=(('features', ('em_* (→ fused_valence)', 'head_yaw_dev', 'face_blur')), ('scene', ('scene_change',)), ('tubelets', ('Δpose / motion',))),
        emitted_by=('highlight',),
        outputs=('highlight.json', 'highlights/*.mp4'),
        state='molten',
        scorer='momentscan.products.evals.harness:score_pairs (segment lane: pair_verdicts_segment.jsonl)',
        note="valence/arousal = emotion.fused_valence, a shared READING over features' em_* (NOT the emotion.json baseline — that is inspector-only / future portrait query); scene optional; frame_scores는 select.py 공유 기판을 소비(제품 정책만 highlight.py 소유 — 2026-07-03 졸업); 3rd WHEN + 궤적 방출 pending",
        egress=('highlight.json', 'highlights/*.mp4'),
    ),
)

_BY_PRODUCT = {p.name: p for p in PRODUCTS}

# products 내부 정합만 (교차 drift = reads/emitted_by 가 ANALYZERS 에 실존 = __init__).
for _p in PRODUCTS:
    assert _p.state in ("frozen", "molten"), f"product {_p.name}: bad state {_p.state!r}"
    assert _p.operation in ("integrate", "select(static)", "select(temporal)"), \
        f"product {_p.name}: bad operation {_p.operation!r}"
    # egress (the Result contract) must be a SUBSET of declared outputs — it cannot
    # name a deliverable the product does not actually land.
    for _e in _p.egress:
        assert _e in _p.outputs, f"product {_p.name}: egress {_e!r} is not a declared output"


def products() -> tuple[Product, ...]:
    return PRODUCTS


def product(name: str) -> Product:
    return _BY_PRODUCT[name]

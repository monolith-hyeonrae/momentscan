"""Analyzer catalog — the PRODUCER declaration (horizontal: one entry per unit/stage/engine).

Lists the *producers*: every unit analyzer (a pure fn in signals.py over an
already-extracted stream) and every stage analyzer (a model → a stash artifact),
each declaring its model, inputs, output-kind, artifact, and upstream `depends`.

Borrows the legacy's good ideas (declared deps → a dependency DAG; declared
capabilities; a discoverable catalog) WITHOUT its entry-point-plugin machinery —
a static, readable declaration instead. One place answers "what analyzers exist,
what does each produce, in what order do they run."

OUTPUT_KINDS drive generic consumption (e.g. the inspector renders a `timeline`
as a line lane, a `categorical` as a colour strip — analyzer ③).

접수 #7·#8 (decl-guards): registry.py 를 registry/ 패키지로 분할하고 선언을 키워드
인자로 재작성했다 — 필드가 이름을 달고 서서 읽힌다. tier 유효성·products 교차 drift
assert 는 __init__ 로(둘 다 임포트하는 유일한 곳). 소비자 임포트는 __init__ 재수출로 불변.
"""
from __future__ import annotations

from dataclasses import dataclass

# how a producer's output is shaped — the contract consumers render/read against.
OUTPUT_KINDS = (
    "timeline",     # per-frame continuous scalar(s) over the tubelet
    "categorical",  # per-frame discrete class (gate reason, track fragment)
    "embedding",    # per-frame vector
    "region",       # per-frame region fractions (segmentation)
    "aggregate",    # one visit-invariant conclusion per subject
    "selection",    # a product output (picked frames / segments)
)


@dataclass(frozen=True, kw_only=True)
class Analyzer:
    name: str
    kind: str                       # "unit" (signals.py fn) | "stage" (model→artifact) | "engine" (product)
    model: str                      # model / method behind it
    inputs: tuple[str, ...]         # streams / artifacts it reads
    output_kind: str                # one of OUTPUT_KINDS
    produces: tuple[str, ...]       # signal / field / file names it emits
    artifact: str                   # stash artifact, or "inline" for unit fns
    depends: tuple[str, ...] = ()   # upstream analyzer names (the DAG edges)
    note: str = ""
    needs_source: bool = False      # True = reads the raw video → run_pipeline must pass --source
    tier: str = "substrate"         # R12 — 측정 스테이지/unit의 기본은 substrate;
                                    # 제품 엔진만 "product"를 명시(예외: select는 공유
                                    # 채점 기판이라 substrate 유지 = D5 지위 정직화).
                                    # tier 유효성 검사는 __init__ (TIERS 와 교차)


ANALYZERS: tuple[Analyzer, ...] = (
    # ── stages: model → stash artifact ──────────────────────────────────────
    Analyzer(
        name='detect',
        kind='stage',
        model='FaceDetect + IoUTracker (ArcFace emb)',
        inputs=('frames',),
        output_kind='timeline',
        produces=('bbox', 'embedding', 'track_id', 'subject_id'),
        artifact='detections.parquet',
        note='track_id online; subject_id = clip-end re-id stitch',
    ),
    Analyzer(
        name='landmarks',
        kind='stage',
        model='MediaPipe FaceMesh',
        inputs=('frames', 'detect'),
        output_kind='timeline',
        produces=('blendshapes', 'transform', 'crop_box'),
        artifact='landmarks.parquet',
        depends=('detect',),
        note='⚠물리 landmarks.py 없음 — 실제 생산자=features 백엔드(plugins/features-specialist45d extractor.write_landmarks). freshness도 features 모듈로만 추적됨(선언된 사각 — 구조감사 D4, 근치=격리사다리/R14 몫)',
    ),
    Analyzer(
        name='attribute',
        kind='stage',
        model='depth (step0b)',
        inputs=('detect',),
        output_kind='aggregate',
        produces=('rider_role', 'depth'),
        artifact='attribution.json',
        depends=('detect',),
        note='main/aux = depth vote, not size',
        needs_source=True,
    ),
    Analyzer(
        name='tubelets',
        kind='stage',
        model='synthesis',
        inputs=('detect', 'attribute'),
        output_kind='timeline',
        produces=('tubelets',),
        artifact='tubelets.parquet',
        depends=('detect', 'attribute'),
        note='subject-keyed spatio-temporal volume',
        needs_source=True,
    ),
    Analyzer(
        name='scene',
        kind='stage',
        model='DINOv3',
        inputs=('frames', 'tubelets'),
        output_kind='embedding',
        produces=('cls', 'customer_embedding', 'bg_embedding'),
        artifact='scene.parquet',
        depends=('tubelets',),
        note='node: extraction/scene.py → backend: plugins/features-specialist45d (isolated)',
        needs_source=True,
    ),
    Analyzer(
        name='features',
        kind='stage',
        model='HSEmotion + LibreFace + MediaPipe + DPR-SH + pixel',
        inputs=('tubelets',),
        output_kind='timeline',
        produces=('registry.py FIELDS (67D)',),
        artifact='features.parquet',
        depends=('tubelets',),
        note='node: extraction/features.py → backend: plugins/features-specialist45d (isolated)',
        needs_source=True,
    ),
    Analyzer(
        name='crops',
        kind='stage',
        model='ffmpeg crop track (clean)',
        inputs=('tubelets', 'source'),
        output_kind='selection',
        produces=('crop track s{sid}.mp4', 'manifest.json'),
        artifact='crops/',
        depends=('tubelets',),
        note='data-retention: source expires; crops persist',
        needs_source=True,
    ),
    Analyzer(
        name='parse',
        kind='stage',
        model='landmark soft-Gaussian quality + SegFormer occlusion',
        inputs=('crops', 'landmarks', 'tubelets'),
        output_kind='region',
        produces=('skin_entropy', 'skin_lum', 'face_micro', 'eye_lum_rel', 'mouth_vis', 'glasses_frac', 'hat_frac', 'cloth_frac'),
        artifact='parse.parquet',
        depends=('crops', 'landmarks', 'detect'),
        note='QUALITY=landmark Gaussian region; occlusion/fashion=SegFormer (deferred→FashionCLIP)',
    ),
    Analyzer(
        name='fashion',
        kind='stage',
        model='FashionCLIP (patrickjohncyh)',
        inputs=('crops',),
        output_kind='aggregate',
        produces=('eyewear', 'headwear', 'covering'),
        artifact='fashion.json',
        depends=('crops',),
        note='typed accessory; complementary to parse',
    ),
    Analyzer(
        name='headpose6d',
        kind='stage',
        model='6DRepNet (300W-LP, full-range, ONNX)',
        inputs=('crops',),
        output_kind='timeline',
        produces=('yaw', 'pitch', 'roll'),
        artifact='headpose.parquet',
        depends=('crops',),
        note='profile-capable; fills MediaPipe NaN; yaw sign-aligned (adapter)',
    ),
    Analyzer(
        name='emotion',
        kind='stage',
        model='HSEmotion+LibreFace fusion → person-relative valence',
        inputs=('features', 'tubelets'),
        output_kind='aggregate',
        produces=('valence_signed', 'em_conf', 'arousal', 'per-person RIDE baseline'),
        artifact='emotion.json',
        depends=('features', 'tubelets'),
        note='shared emotion reading; emotion.json = per-person baseline, emotion_frame.parquet = per-frame valence/em_conf/arousal (observability trace the inspector reads)',
    ),
    Analyzer(
        name='gates',
        kind='stage',
        model='gate ladder (gates.evaluate → per-subject verdicts)',
        inputs=('tubelets', 'landmarks', 'crops', 'parse', 'headpose6d', 'features'),
        output_kind='categorical',
        produces=('reason', 'valid', 'admit', 'quarter_ok', 'side_ok'),
        artifact='gate_trace.parquet',
        depends=('tubelets', 'landmarks', 'crops', 'parse', 'headpose6d', 'features'),
        note='R10: the DECISION layer as a STAGE (measurement V01~V05), no longer a step inside portrait — un-hostages likeness/select freshness (L9/D2). Assembles per-frame signals then runs the ladder for ALL subjects. features is an optional-DEGRADING read at runtime (absent → em_conf NaN → expr_ok passes), but it DOES change the verdicts when present (em_conf gates expr_ok), so it is a declared depend for freshness/closure honesty',
    ),

    # ── unit analyzers: pure fns in signals.py over a stream (inline);
    #    pose graduated to its own domain module pose.py (fusion+quantizer+thresholds) ──
    Analyzer(
        name='pose',
        kind='unit',
        model='MediaPipe transform → euler',
        inputs=('landmarks.transform',),
        output_kind='timeline',
        produces=('yaw', 'pitch', 'roll'),
        artifact='inline',
        depends=('landmarks',),
        note='frontal-precise; NaN on profiles → fused with headpose6d (pose.fuse_pose)',
    ),
    Analyzer(
        name='expression',
        kind='unit',
        model='MediaPipe blendshape',
        inputs=('landmarks.blendshapes',),
        output_kind='timeline',
        produces=('blink', 'smile', 'jaw', 'expr_magnitude'),
        artifact='inline',
        depends=('landmarks',),
    ),
    Analyzer(
        name='face_quality',
        kind='unit',
        model='pixel (Laplacian)',
        inputs=('crops',),
        output_kind='timeline',
        produces=('crop_blur', 'crop_lighting (bright, harsh)'),
        artifact='inline',
        depends=('crops',),
    ),
    Analyzer(
        name='identity_dev',
        kind='unit',
        model='ArcFace centroid cosine',
        inputs=('detect.embedding',),
        output_kind='timeline',
        produces=('identity_deviation',),
        artifact='inline',
        depends=('detect',),
        note='self-relative; nuisance-entangled (probe-0)',
    ),

    # ── engines: consume analyzers → product output ─────────────────────────
    Analyzer(
        name='portrait',
        kind='engine',
        model='synthetic-criterion gate + crop-track extract',
        inputs=('landmarks', 'face_quality', 'parse', 'crops', 'headpose6d'),
        output_kind='selection',
        produces=('portraits/*.png', 'candidates(portrait)'),
        artifact='portraits/',
        depends=('landmarks', 'parse', 'crops', 'headpose6d', 'gates'),
        note='fashion admit; 0-axis not ranked; side via headpose6d fallback. depends gates = reads the gate verdicts from gate_trace (R10: gate production is its own stage)',
        tier='product',
    ),
    Analyzer(
        name='likeness',
        kind='engine',
        model='landmark distribution + fashion reading',
        inputs=('landmarks', 'parse', 'fashion'),
        output_kind='aggregate',
        produces=('likeness.json (center, axes, fashion)',),
        artifact='likeness.json',
        depends=('landmarks', 'parse', 'fashion', 'gates'),
        note="visit-invariant ID; depends gates = consumes the shared ① `valid` verdict from gate_trace (face_id/geometry from valid frames). R11 declaration repair: likeness's real dependency is gate_trace (a STAGE, R10), NOT portrait — the old `portrait` edge was the L9 hostage and is removed (선언=정본, 실제 read와 정합). A gates.py change now re-runs gates → the R5 artifact-edge marks likeness stale → it re-runs (no portrait needed)",
        tier='product',
    ),
    Analyzer(
        name='recipe',
        kind='engine',
        model='face_axes 기하 공식 + 캘리 레지스트리 (recipe_axes)',
        inputs=('likeness',),
        output_kind='aggregate',
        produces=('recipe/{image_id}.recipe.json',),
        artifact='recipe/',
        depends=('likeness',),
        note="likeness.json 답의 사상(88축 recipe, 오늘 Cat G 37축). Product 신설 아님 —"
             " likeness Product 의 additive output(egress 제외). kind='engine' 은 질문이라서가"
             " 아니라 cascade(stage→engine) 상 likeness 뒤에 서려면 필요(select 의 substrate-engine"
             " 전례). likeness.json 을 validate_likeness 로 읽기 전용 소비(쓰지 않음). absorption-plan A1",
        tier='substrate',
    ),
    Analyzer(
        name='select',
        kind='engine',
        model='frame_scores → candidates',
        inputs=('features', 'tubelets'),
        output_kind='selection',
        produces=('candidates(likeness)',),
        artifact='candidates.jsonl',
        depends=('features', 'gates'),
        note='공유 채점 기판(frame_scores) + likeness 후보 로그; highlight는 2026-07-03 highlight.py로 졸업. depends gates = WHICH가 공유 ① `valid` 소비 (gate_trace, R10 이후 stage). R11 수리: select은 portrait 산출을 읽지 않는다(gate_trace만) — 헛(phantom) portrait 간선 제거',
    ),
    Analyzer(
        name='highlight',
        kind='engine',
        model='joint WHEN phrases → segments',
        inputs=('features', 'tubelets', 'scene'),
        output_kind='selection',
        produces=('highlight.json (segs)',),
        artifact='highlight.json',
        depends=('features', 'select', 'portrait'),
        note='합동 OR(max) WHEN 악구 + 정합성 방출(joy OR energy 축); frame_scores는 select의 기판을 소비 — depends select = 코드 의존(채점 정의 변경 시 함께 재실행)',
        tier='product',
    ),
)

_BY_NAME = {a.name: a for a in ANALYZERS}


def get(name: str) -> Analyzer:
    return _BY_NAME[name]


def by_output_kind(kind: str) -> list[Analyzer]:
    return [a for a in ANALYZERS if a.output_kind == kind]


def topo_order() -> list[Analyzer]:
    """Kahn topological sort over `depends` — a valid run order for the DAG."""
    indeg = {a.name: sum(1 for d in a.depends if d in _BY_NAME) for a in ANALYZERS}
    ready = [a for a in ANALYZERS if indeg[a.name] == 0]
    order: list[Analyzer] = []
    while ready:
        a = ready.pop(0)
        order.append(a)
        for b in ANALYZERS:
            if a.name in b.depends:
                indeg[b.name] -= 1
                if indeg[b.name] == 0:
                    ready.append(b)
    return order


def _depends_closure() -> dict[str, set[str]]:
    """Transitive `depends` closure per analyzer (everyone that must run before it)."""
    closure: dict[str, set[str]] = {}

    def walk(name: str, seen: frozenset[str]) -> set[str]:
        if name in closure:
            return closure[name]
        acc: set[str] = set()
        for d in _BY_NAME[name].depends:
            if d in _BY_NAME and d not in seen:
                acc.add(d)
                acc |= walk(d, seen | {d})
        closure[name] = acc
        return acc

    for a in ANALYZERS:
        walk(a.name, frozenset({a.name}))
    return closure

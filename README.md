# momentscan

> ⚠️ **PoC — 평가 단계 코드베이스** (2026-08 현재). 데일리 배치 평가로 정량·정성
> 퍼포먼스를 검증하는 것이 지금 목적이며, 운영 수준으로 가는 과정에서 내부 구조·
> 알고리즘·저장 형식의 **큰 변경이 예정**되어 있다. 외부에서 기대도 되는 경계는
> 두 개뿐이다 — **출력 계약**(반출물 likeness.json·provenance.json과 Result 스키마)
> 과 **API 계약**([docs/api/openapi.yaml](docs/api/openapi.yaml)). 내부 모듈을 직접
> import·의존하지 말 것(계약 밖은 예고 없이 바뀐다). 라이선스: 일부 모델 웨이트
> (insightface buffalo_l)가 **비상업 연구 라이선스**라 상업 운영 투입 전 교체 또는
> 합의가 필수다(내부 트래킹 중 — [docs/deploy-handoff.md](docs/deploy-handoff.md) 참조).

비디오/이미지에서 **인물 시그널의 분포를 추정하고, 그 분포를 읽어 답하는** 비전 분석 프로그램.

관련자의 이해 수준에 맞춰 세 겹으로 답한다:

- **한 문장** — 어트랙션을 탄 손님의 영상을 분석해, 그 사람의 **대표 사진(portrait)·하이라이트 클립(highlight)·아바타용 외형 정보(likeness)** 를 자동으로 뽑아주는 소프트웨어.
- **어떻게가 다른가** — 좋은 프레임 한 장을 고르는 게 아니라, 방문 내내 남긴 **시그널의 분포를 추정하고 세 번 읽는다** — 영향을 지운 *불변*(누구인가)·영향이 최선인 *한 점*(가장 좋은 모습)·맥락에 대한 *반응*(교감한 순간).
- **왜 자동촬영과 다른가** — 순간을 포착(capture)하는 게 아니라 사람을 **증류(distill)**한다. 묘사가 아니라 이해를 지향하는 분석기.

> 세 제품(likeness·portrait·highlight)의 정확한 정의·관계·명명은
> [`docs/products.md`](docs/products.md)가 단일 진실.

> **이 문서는 *도메인 design intent*다.** 코드가 왜 이렇게 배치되어 있는가
> (층 지도·격리 사다리·졸업 규칙·멤버십 테스트)는 [`ARCHITECTURE.md`](ARCHITECTURE.md),
> 실행 방법은 [`SETUP.md`](SETUP.md)에. visualstack 위에 부트스트랩된 파이프라인이 이미
> 돌아간다 — `uv sync && uv run momentscan run <clip>`.
>
> **북극성(2026-06-08~): [`docs/jepa-poc.md`](docs/jepa-poc.md).** 이 레포는 그 PoC의
> Track A/B selection + eval 거점으로 재정렬됨. 아래 `Distribution`+읽기 계약은 유효하되,
> PoC는 읽기를 `center`(→likeness) + `conditional-residual`(→highlight) 둘로 좁히고
> **feature-space 축**(45D | V-JEPA)을 더해 두 트랙을 같은 harness로 비교한다. 데이터
> 현실·attribution·occlusion 결정은 그 문서의 Appendix.

### 이 레포의 위치

p981 메타 레포(크로스-시스템 계약·결정 홈)의 멤버. 형제 레포 **visualstack**(일반
비전 substrate — visualbus·visualpath)을 경로 의존으로 끌어 쓰고, 그 위에서 세 제품을
만든다. (구 portrait981 모노레포에서의 분리·이주는 2026-07-07 완료 — 경위는 docs/.)

### 디렉토리 지도

| 위치 | 무엇 |
|---|---|
| `apps/momentscan/` | 제품 코드 (perception·products·surface·infra 층 — [`ARCHITECTURE.md`](ARCHITECTURE.md)) |
| `plugins/` | 격리 FeatureSource 스택 (Track A onnx/mediapipe · Track B torch/V-JEPA) |
| `policies/` | 선별 정책·신호 범위 (데이터) |
| `workbench/` | 연구 워크벤치 — 알고리즘 검증용 참조 구현·프로브 (제품 코드 아님, [`workbench/README.md`](workbench/README.md)) |
| `deploy/` | 컨테이너·관측 스택 ([`docs/deploy-handoff.md`](docs/deploy-handoff.md)) |
| `docs/` | 문서 사슬 (계약 C1~C12 → 원장 → 청사진; 진입은 [`docs/ids.md`](docs/ids.md)) |
| `fixtures/` | 특성화 골든·평가 라벨 |

---

## 무엇을 하는가

**인물 시그널의 분포를 추정하고(merge), 그 분포를 읽어(query) 답한다.** 이 한 문장이 전부다.

산출물을 나열하면 여러 가지로 보이지만 전부 같은 한 연산이다. "프로그램 = 산출물 N개"로 설명하면 무엇을 하는 프로그램인지 답답해지고, **"프로그램 = 분포 1개 + 읽는 방식"** 으로 보면 사라진다. 기능이 늘어도 새 산출이 아니라 *또 다른 읽기*로 흡수된다.

모든 산출은 **두 축의 조합**으로 생성된다.

**축 1 — 어느 분포인가** (anchor, `filter`로 결정)
- **외형**: 한 사람(`subject_id`)에 앵커된 분포. 느리게 변하는 정체성.
- **순간**: 한 시간 구간에 앵커된 분포. 휘발적인 사건.

**축 2 — 분포를 어떻게 읽는가** (reading)
- **중심 (표준)**: 분포의 중심 그 자체 — 기준선.
- **퍼짐 (다양성)**: 중심에서 고루 퍼진 표본 — 커버리지.
- **편차 (하이라이트)**: 중심에서 가장 튄 지점 — `distance(중심)`.

| anchor \ reading | 중심 (표준) | 퍼짐 (다양성) | 편차 (하이라이트) |
|---|---|---|---|
| **외형** (한 사람) | "그 사람다움" ✓ | 골고루 표본 ✓ | — |
| **순간** (한 구간) | — | — | 피크 순간 ✓ |

읽기는 anchor의 성격을 따른다: 외형은 느려서 **중심·퍼짐**이 의미 있고, 순간은 휘발적이라 **편차(피크)** 만 의미 있다 — "평균 프레임"은 아무도 원하지 않는다. 빈 칸은 지금 안 쓸 뿐, 같은 문법으로 언제든 생성 가능하다.

**실제 타겟 산출 3개 (다운스트림 활용)**

- **외형 중심** → 대체 캐릭터·아바타·캐리커처·PFP의 외형 레퍼런스.
  *cf. 기존 personmemory의 핵심만 추출, 도메인 의존 제거.*
- **외형 퍼짐** → AI 편집 영상에서 얼굴 일관성 보장용 reference set (주행 포스터·대회 프로필 등).
  *cf. 기존 5-class expression × 3-class pose 매트릭스 채우기의 일반화.*
- **순간 편차** → 하이라이트 포토·클립 생성의 입력.
  *cf. 기존 q×e×z 스코어링 + SlidingSmooth + OnlineZScore의 일반화.*

→ 세 산출 전부 **시그널 추출 → 분포 추정(merge) → 분포 읽기(distance/spread)** 라는 한 엔진의 다른 query다. 주타겟 트래킹은 산출이 아니라 분포를 어디에 앵커할지(`subject_id`)를 정해주는 기반 기술 — 다음 *분석 모델* 절에서 다룬다.

---

## 무엇을 풀지 않는가 (현재 범위 밖)

- **생성은 다운스트림의 몫**. 우리는 세 산출(외형 중심·외형 퍼짐·순간 편차)과 그 기반 시그널·태그를 제공하는 데까지. 하이라이트 클립 합성, 아바타·PFP 생성, AI 편집 영상의 페이스 가이드 적용은 별 시스템.
- 외부 시스템(파크코어, 라이드, 멤버, 워크플로우 등) 도메인 어휘.
- 시나리오·템플릿 오케스트레이션 (Highlight/Profile/굿즈/프로모션 같은 enum).
- REST/Kafka 등 외부 인터페이스 — 라이브러리·CLI가 안정된 이후에만 고려.
- 어노테이션 GUI / 라벨링 도구 — 학습 데이터 준비가 필요할 때 별 프로젝트로.

---

## 설계 원칙

- **도메인-agnostic**: 비즈니스 어휘를 코어에 들이지 않는다. 도메인 의미는 호출자가 annotation으로 붙인다.
- **검증된 추상화만**: 잘게 쪼개기 전에 평평한 단일 패키지로 시작. 두 번 이상 재사용된 것만 분리.
- **Scan = 1회 분석 수행**이라는 원자 단위 유지. 영속화·식별·전송은 Scan 위에 쌓는다.
- **시그널은 의미 있는 차원만**. "더 많은 차원"을 위해 차원을 늘리지 않는다.
- **시그널은 optional prior**: 활용층은 시그널의 어떤 부분집합으로도 동작해야 한다 (graceful degradation). 모듈 추가는 누적적·단조적이며 결측은 망가짐이 아니다 — *HunyuanWorld-Mirror 패턴*. 이 원칙이 향후 unified representation으로 가는 다리.
- **워밍 우선**: 모델 로딩은 한 번, 분석은 여러 번. 라이프사이클은 명시적.

---

## 분석 모델

세 산출 축은 모두 같은 엔진 위의 다른 query다. 엔진은 두 층과 두 연산으로 이뤄진다.

**두 층**

- **층 1 — 시그널 & 태그 생성 (heavy, GPU, frozen models + association)**
  얼굴 검출·표정·포즈·조명·랜드마크 등 raw 시그널 추출 + 그 위에 분류기·연관 로직으로 **내생적 태그**를 붙인다.
  - **주타겟 트래킹**도 여기에 속한다 — per-frame detection을 시간축 일관성으로 묶어 `subject_id` 태그를 만드는 일.
  - expression class·pose class 같은 분류 결과도 동일하게 내생적 태그.
  세 산출 축이 공유하는 비싼 부분. 한 번만 돈다.
  - 산출은 모두 **weak prior로 취급**된다. 어느 시그널이 빠져도 활용층은 동작 (설계 원칙 참조).
- **층 2 — 시그널 활용 (light, CPU, 로직)**
  per-scan: 하이라이트(시간축 분석), 다양성(표본 spread).
  cross-scan: 외형 표준 — 하지만 별도 라이프사이클이 아니라 *층 2의 응용*임. 아래 참조.

→ 층 1의 산출을 디스크에 stash 가능해야 한다. 새 활용 로직 짤 때 GPU를 다시 돌리지 않게 — iteration 속도의 결정적 요소.

**두 데이터 타입**

- **Scan** — 한 번의 분석 수행. 시간축(또는 인덱스 축) 위의 태그된 시그널 시퀀스.
- **Distribution** — 시그널의 분포 표현. Scan들을 merge한 결과거나, 그 자체를 직접 누적·갱신.

**두 연산**

- **merge** — `Scan ⊕ Scan → Distribution`, `Distribution ⊕ Scan → Distribution'`.
  결합법칙·항등원이 잘 정의되면 incremental update가 공짜로 따라옴 (Welford 누적의 일반화).
- **distance** — `(Scan|Distribution, Scan|Distribution) → score`. 입력 종류와 무관하게 단일 인터페이스.

→ 두 연산이 *세 읽기*를 만든다: **중심**과 **퍼짐**은 `merge` 결과 Distribution의 속성(mean / spread)을 그대로 읽고, **편차**는 그 Distribution에 대한 `distance`다. 정의 절의 anchor × reading은 결국 `filter → merge → {중심·퍼짐 읽기 | distance}`로 환원된다.

**코어 객체: Distribution (하나의 프로토콜)**

```python
class Distribution:                          # 시그널 종류별 구현, 인터페이스는 하나
    def merge(self, other: Scan | Distribution) -> Distribution: ...  # ⊕ (결합법칙·항등원)
    def center(self)            -> Vector:        ...   # 중심 읽기 → 표준
    def spread(self, n: int)    -> list[Sample]:  ...   # 퍼짐 읽기 → 다양성(커버리지 표본)
    def distance(self, point)   -> float:         ...   # 편차 읽기 → 하이라이트
```

- 내부 수학은 시그널 종류별로 다르다: signal-vector(Welford μ/Σ + PCA), appearance(eigenface), shape(eigen-landmark), category(vote count). **그러나 인터페이스는 하나** — `merge` + 세 읽기.
- 따라서 코어는 **"4종 통계 클래스 + 3종 셀렉터"가 아니라 `Distribution` 프로토콜(N 구현) + 3 읽기 함수**다. 산출 3개(외형 중심·외형 퍼짐·순간 편차)는 `(anchor, reading)` 프리셋일 뿐 별도 클래스가 아니다.
- **읽기는 타입-무관**: `center`/`spread`/`distance`는 어떤 Distribution 구현에도 동일하게 적용. 새 시그널 종류가 생기면 Distribution 구현 1개만 추가하면 세 읽기가 공짜로 따라온다.

**의미는 filter에서 나온다**

merge는 산술적 누적일 뿐이고, **무엇을 selecting해서 merge하느냐**가 결과의 의미를 결정한다.

| filter 조건 | 결과의 의미 |
|---|---|
| `pose == frontal` (모든 subject) | "정면 얼굴"의 시그널 표준 |
| `subject_id == X` (모든 scan) | 그 사람의 외형 분포 |
| `expression == smile` (모든 subject) | "웃음"의 레퍼런스 |
| `scan_id == S, t ∈ window` | 그 순간의 맥락 |

→ 세 산출 전부 같은 엔진의 다른 query (anchor × reading): 순간 편차 = `filter(window) → distance(중심)`, 외형 퍼짐 = `filter(subject) → spread`, 외형 중심 = `filter(subject) → merge`. 트래킹은 query가 아니라 query를 가능하게 하는 앵커(`subject_id`) 생성(층 1).

**태그의 두 종류**

- **외생적**: 호출자가 알려주는 것 — 알려진 subject_id, ride_id, 외부 식별자.
- **내생적**: 분석이 만들어내는 것 — 트래킹이 산출한 subject_id, face cluster id, expression class, pose class.

같은 키(예: `subject_id`)가 두 출처에서 모두 나올 수 있다. 둘은 `source` 필드로 명시 구분하고, query는 동일 인터페이스로 양쪽에 접근.

---

## 데이터 모델

### 3-level 구조

한 번의 `scan()` 호출이 세 level의 데이터를 산출한다.

| Level | 단위 | 무엇이 사는가 |
|---|---|---|
| **Scan** | 1회 호출 (보통 비디오 1개) | 입력 메타(path, fps, duration), 호출 시점·설정, 외생 태그(`ride_id`), scene-level 판정(`primary_subject_ids`, scene_type), tracks/subjects 요약, **health metrics** |
| **Frame** | 1 timestamp | `frame_idx`, `timestamp_ms`, frame-level signals (frame_quality, scene brightness, ...). detection이 없어도 존재. |
| **Detection** | 1 frame 안의 1 instance | `bbox`, `track_id`, `subject_id`, `face_embedding`(inline), detection-level signals (expression·pose·lighting·au ...), latent 옵션 column |

→ Detection이 1급 row. Frame은 detection들의 컨테이너 + frame-level 메타. Take는 별 타입이 아니라 *selected detection들의 view*.

### Track vs Subject 두 단계

| 단계 | 알고리즘 결 | mutable? |
|---|---|---|
| **Track** (`track_id`) | 시간적 association (frame 간 IoU·optical flow·short-term embedding). 짧고 빠름, 잘 끊김. | immutable |
| **Subject** (`subject_id`) | identity matching (full-vector face embedding cluster). 깨진 track 이어붙임. | mutable (사후 수정·재클러스터 가능) |

→ 동일 인물의 face_id가 한 비디오 안에서 끊기는 케이스가 흔하다. "track은 끊겼지만 subject는 같다"로 표현. **타겟 선정(누가 main subject)** 은 scan-level의 `primary_subject_ids` 1줄로 표현되고, detection에는 복제하지 않는다 (`subject_id ∈ primary_subject_ids`로 query).

### Track health metrics (모니터링 1급)

분석 끝나면 자동 산출되어 Scan에 박힌다:

- `track_count`, `subject_count` (둘이 다르면 머지가 일어났다는 뜻)
- per-track: `length`, `gap_count`, `embedding_variance`
- `suspicious_breaks`: 같은 embedding 군집인데 다른 track인 후보
- `unstable_subjects`: 한 subject 안의 embedding spread가 큰 경우

→ "이 비디오는 트래킹이 잘 됐나"가 한눈에. ad-hoc 스크립트가 아니라 표준 메타.

### 시그널 표현

**평탄 column + 그룹 prefix.**

```
expr__cheese, expr__chill, expr__edge, ...
pose__yaw, pose__pitch, pose__roll
lighting__sh_0, lighting__sh_1, ...
face_quality__blur, face_quality__exposure, ...
```

- nullable이 first-class — 빠진 시그널 = null column. world model의 optional prior와 직접 매핑.
- 모듈이 시그널을 declarative하게 registry에 등록 → schema 자동 조립.
- typed: dtype, unit, valid_range, 그룹 prefix가 schema 메타로 보존.
- vector(embedding·latent)는 `List<Float32>` column으로 inline.

### Signal provenance (1급 메타)

각 시그널 column에 5종 메타:

- `source_module` — face_detect_v2, hyperexpression_v1 ...
- `model_version`
- `confidence` — 모델이 알려주는 것
- `applied_at` — 산출 시점
- `is_prior` — world model 학습 시 conditioning으로 쓸 수 있는지

→ 모델을 갈아끼울 때 같은 column에 다른 source가 들어와도 추적 가능. 데이터 큐레이션 시 "이 분기의 데이터는 어떤 모델 조합인가"가 명확.

### Latent 옵션

face_embedding뿐 아니라 표정·포즈 모듈의 hidden representation도 보관할 수 있게 schema에 자리만 둔다 (`latent__expr`, `latent__pose` 등, List<Float32>, nullable). 비용 들 모듈에서만 활성화. 향후 unified representation의 입력 후보.

### 결측치 정책

- 시그널이 적용되지 않음 → null. 활용층 함수(distance/merge/filter)는 column별로 작동, null dim은 자동 스킵.
- 적용됐으나 실패 → 필요하면 `{signal}__status` 별 컬럼. 첫 모듈 붙일 때 결정.

### 저장 표현

> PoC 인스턴스화는 scan/frames/detections 대신 **tubelets / features/{A,B} / candidates** 3단으로 떨군다 — [`docs/data-contract.md`](docs/data-contract.md). 아래는 일반 모델.

```
stash/
└── {scan_id}/
    ├── scan.parquet         # 1 row
    ├── frames.parquet       # N rows
    ├── detections.parquet   # M rows (embedding inline)
    └── distribution.parquet # 이 scan에서 만든 분포(있다면)
```

- **parquet 3 테이블, scan별 디렉토리**. columnar이 분포·통계·query에 자연스럽고 polars/duckdb/pandas 다 지원.
- scan 단위 격리 → 한 scan만 재처리·삭제·디버깅 가능.
- cross-scan 쿼리는 `duckdb` glob (`stash/*/detections.parquet`)으로.

**in-memory**: polars DataFrame.

### Distribution 표현

- 우선 **sufficient statistics** (count, mean, M2 per dimension; Welford 누적). 메모리·머지 비용 작고 incremental update 공짜.
- 작은 분포·디버깅용은 **raw samples** 옵션. 동일 `Distribution.merge(...)` 인터페이스로.

---

## 모듈 인터페이스

visualpath/core의 `Module`을 확장한 spec. visualstack 부트 시 이 spec 그대로 박힘.

> **이 절은 *층 1*(시그널 생성) 스펙이다.** Module은 버스 위에서 SignalRow를 만든다. *층 2*(Distribution + 3 읽기)는 Module이 **아니다** — stash된 Scan parquet 위에서 도는 별도 대수(*분석 모델* 절의 `Distribution` 프로토콜 참조). 둘을 한 추상화로 합치지 말 것: 층 1은 "프레임→시그널", 층 2는 "시그널들→분포→읽기". `Summarizer`만 두 층의 경계에 선다(scan 종료 시 health metrics 같은 scan-level 요약 생성).

### 세 종류 + 라이프사이클

```python
class Module:                                          # 공통 베이스
    name: ClassVar[str]                                # "face.detect", "expression", ...
    produces: ClassVar[list[str]]                      # ["bbox", "expr__*", ...] — prefix 허용
    requires: ClassVar[list[str]] = []                 # signal-level (예: ["bbox", "roi__face"])
    optional_requires: ClassVar[list[str]] = []        # weak prior: 있으면 활용, 없어도 OK
    requires_module: ClassVar[list[str]] = []          # 부속: same-instance 의존만 예외적으로
    level: ClassVar[Literal["frame", "detection", "scan"]]
    model_version: ClassVar[str]
    is_prior: ClassVar[bool] = True                    # world model conditioning 후보 여부
    batch_size: ClassVar[int] = 1

    def load(self) -> None: ...                        # 모델 로딩 1회 (warm executor)
    def unload(self) -> None: ...                      # 모델 해제
    def declare(self) -> SignalSchema: ...             # produces를 expanded list + dtype/unit/range로

class FrozenAnalyzer(Module):                          # stateless after load
    def analyze(self, ctx: UnitContext) -> SignalRow | list[SignalRow]: ...
    def analyze_batch(self, ctxs: list[UnitContext]) -> list[SignalRow | list[SignalRow]]: ...

class TemporalProcessor(Module):                       # per-scan state
    def on_scan_start(self, scan_meta: ScanMeta) -> None: ...
    def on_frame(self, ctx: FrameContext) -> SignalRow | list[SignalRow]: ...
    def on_scan_end(self, scan_view: ScanView) -> SignalRow | list[SignalRow]: ...

class Summarizer(Module):                              # scan 종료 시 1회
    def summarize(self, scan: Scan) -> ScanRow: ...
```

### SignalRow 3종

```python
@dataclass(frozen=True, slots=True)
class FrameRow:     scan_id: str; frame_idx: int; timestamp_ms: int; signals: dict[str, Any]
@dataclass(frozen=True, slots=True)
class DetectionRow: scan_id: str; frame_idx: int; detection_id: int; bbox: BBox; signals: dict[str, Any]
@dataclass(frozen=True, slots=True)
class ScanRow:      scan_id: str; signals: dict[str, Any]
```

`signals: dict[str, Any]`은 runtime이 평탄 column으로 풀어 polars DataFrame에 누적. 모듈은 dict로 반환, 어디에 commit할지 모름.

### UnitContext

`FrameContext` / `DetectionContext` 두 종. 모두 **`requires`에 선언된 시그널만 노출** (의존성 위생). 다른 column 접근은 cheating으로 차단.

- FrameContext: frame data, frame_idx, timestamp, scan_meta, required signals dict
- DetectionContext: parent frame ref, detection_id, bbox, roi crop(있다면), required signals dict

### DAG 해석

- **signal-level 1급**: `requires=["bbox", "face_landmarks"]`. runtime이 토폴로지 정렬.
- **ROI도 시그널**: `requires=["roi__face"]`. 별도 ROI 인덱스 없음.
- **module-level 부속**: `requires_module=["face.detect"]`. same-instance state 의존 같은 예외만.
- **충돌 해소**: 같은 시그널 여러 producer 시 등록 순서 기본, config로 명시 override.

### 그룹 prefix declare

모듈은 `produces=["expr__*"]` 식 prefix 허용. `declare()`가 expanded list (`["expr__cheese", "expr__chill", ...]`) + dtype/unit/range 반환. dimension은 모듈이 결정.

### Runtime 책임

1. signal-level DAG 토폴로지 정렬
2. level에 따라 fan-out (frame iteration · detection iteration)
3. required signal column만 ctx에 inject
4. 모듈 반환 SignalRow를 polars DataFrame builder에 누적
5. **Provenance 5종 메타 자동 stamping** — `source_module = module.name`, `model_version`, `is_prior`, `applied_at = now`, `confidence`는 모듈이 SignalRow에 포함
6. scan 종료 시 DataFrame freeze → Scan 객체 + parquet 3-table 저장

---

## 구조

### momentscan 레포 내부

미정. 모듈 경계는 위 모델이 코드로 한 번 돌아간 뒤 자연스럽게 결정. *코드는 단일 패키지로 시작*, *기능은 조합 가능한 단위로 분리*가 합의된 원칙.

*"잘게 쪼개는 것 자체"가 문제가 아니라 "검증 없이 선행 분리"가 문제다.* visual\*/vpx는 portrait981에서 충분히 검증됐으므로 그대로 외부 의존성으로 활용한다. momentscan 본체 안에서 새로 분리할 모듈은 검증 뒤에만.

### 외부 의존 — 2 레포 분리

**visualstack** (`/home/hyeonrae/repo/monolith/visualstack/`) — visualbase + visualpath + vpx를 담는 단일 메타 워크스페이스 레포 (uv workspace). OSS 공개 염두로 도메인-agnostic·고유도 높은 이름. 합의 전까지 로컬에서 진행, 라이센스 TBD.

| 패키지 (visualstack 내부) | 역할 | 비고 |
|---|---|---|
| **visualbase** | 미디어 I/O, Frame, ROI, ImageSource, SourceProfile | media-io 코어. IPC/Trigger/Clipper/streaming/daemon은 `visualbase-extra`로 분리 (또는 미포함) |
| **visualpath** | Module 프로토콜, FlowGraph, warm executor, signal DAG, Worker 격리 | 분석 backbone. core/isolation/cli/pathway를 워크스페이스 멤버로 |
| **vpx** | Module SDK + reference plugins (face_detect, expression, pose, lighting, au, head_pose, face_parse, hand_gesture, frame_quality, face_quality, face_lighting) | **visualpath extensions SDK** 위상. 외부 plugin 개발자 진입로. plugin은 venv 격리·라이센스 격리(특히 yolov8 AGPL)로 각각 별 패키지 유지 |

**momentscan** (이 레포, `/home/hyeonrae/repo/monolith/momentscan/`) — 활용층 + 새 visualbind 기술. visualstack의 패키지들을 의존성으로 사용. `Distribution` 프로토콜 + 3 읽기(외형 중심·외형 퍼짐·순간 편차)의 거점.

**OSS 작업 원칙** (visualstack에 적용)
- 코드·이름·구조에 회사 도메인 어휘 X (이미 적용 중)
- author/email·git commit identity를 회사 계정에 묶지 않기
- LICENSE / CONTRIBUTING.md 파일 자리는 처음부터 두되 내용은 합의 후
- README에 라이센스 TBD 명시

### visualbind 처리

visualbind는 **층 2의 구현체** — `Distribution` 프로토콜 + 3 읽기. 기존 visualbind(65D 고정 + XGBoost 4단 judge)는 weak-prior 정신과 충돌(null=0 imputation, frame-level 압축, discrete class 환원)하며 "기술적으로 완성되었다고 볼 수 없는" 상태.

- **기존 visualbind**: portrait981이 운영 연속성을 위해 잠시 잔존 사용. 새 것이 검증되면 마이그레이션 후 폐기.
- **새 visualbind = `Distribution` 프로토콜 + N 구현 + 3 읽기.** 이게 *전체 표면*이다.

```
visualbind/
├── distribution/        # merge + center/spread/distance 구현 (시그널 종류별)
│   ├── signal.py        #   Welford μ/Σ + PCA + Mahalanobis      [구현됨]
│   ├── appearance.py    #   eigenface bank (frontal-gated)        [미구현]
│   ├── shape.py         #   eigen face-landmark                   [미구현]
│   └── category.py      #   per-attribute vote                    [미구현]
├── read.py              # center/spread/distance — 타입-무관 3 함수
└── preset.py            # (anchor, reading) 프리셋: 외형중심·외형퍼짐·순간편차
```

→ "statistics 4종 × selector 3종"의 4×3 표면이 아니라 **Distribution N구현 + 읽기 3함수**. selector는 클래스가 아니라 얇은 프리셋. *(현재 디스크의 `statistics/*` + `selector/*` 분리는 이 목표 구조로 수렴시킬 대상.)*

**robust path 우선**: 읽기 3종은 *휴리스틱 + 선형대수*만으로 동작 가능해야 한다(학습 모델 없이). 그 위에 *옵션*으로 학습 기반 projection을 얹는다 — 아래 *향후* 절. 즉 visualbind는 동시에 **(1) 지금 도는 분포 대수**이자 **(2) 장기 Unified Representation의 실험 베드**이며, (1)이 (2)에 의존하지 않는다.

장기 projection 후보(미정, 첫 시그널 stash 이후 결정): A. Aggregation transformer(Mirror식 token+mask) / B. Prototype·centroid / C. Contrastive·triplet / D. Energy·density. 데이터 모델(평탄 nullable + provenance + latent 옵션)은 A~D 모두를 막지 않게 설계됨.

---

## 향후 — Unified Representation

장기적으로 frozen 모델들의 시그널을 weak signal hint로 받아 **공통 공간에 projection되는 Facial World Model**을 만드는 방향. 참조: [HunyuanWorld-Mirror](https://github.com/Tencent-Hunyuan/HunyuanWorld-Mirror) — 어느 prior 부분집합으로도 동작하며, prior가 추가될수록 monotonic하게 개선되는 통합 아키텍처.

| Mirror | 우리 |
|---|---|
| Optional priors (intrinsics, depths, poses) | Optional weak signals (au, expression, pose, lighting, embedding, ...) |
| Unified output (point cloud, depth, normal, gaussian) | Unified facial representation (공통 공간 projection) |
| 어느 prior 부분집합으로도 동작 | 어느 frozen 모듈 부분집합으로도 동작 |
| Feature aggregation | 시그널들의 cross-modal aggregation |

현재 데이터 모델(평탄 nullable column + signal provenance + latent 옵션)이 이 방향과 충돌하지 않도록 설계됨. world model 학습은 아직 *현재 범위 밖*이지만, 데이터가 그쪽으로 누적되는 데 막힘이 없어야 한다.

---

## 외부 도구 검토

- **[pixeltable](https://www.pixeltable.com/)** (Apache 2.0) — declarative computed column·자동 dependency DAG·embedding index 등 우리 분석 모델과 결이 가까운 부분 있음. 그러나 (a) Distribution merge/distance/Welford 같은 우리 핵심 연산 부재, (b) 자체 SQLite-like DB와 우리 parquet 3-table·polars 결정 충돌, (c) plugin 생태계의 단일 인터페이스(vpx Module)와 UDF 추상화 충돌. → **prod 의존은 X. 학습·실험·서빙 등 인접 영역에서 옵션 도입 검토**. 참고할 패턴: 자동 dependency propagation의 UX, first-class multimodal type, embedding index 통합.

---

## 진행 상태

- [x] 비전·범위 합의
- [x] 분석 모델(두 층 + Scan/Distribution + merge/distance + filter-driven 의미) 합의
- [x] 데이터 모델(3-level + track/subject + 평탄 column + provenance + parquet stash) 합의
- [x] 장기 비전(Unified Representation, weak-prior 패턴) 합의
- [x] 위치 결정: 4 레포 분리(visualbase / visualpath / vpx / momentscan), portrait981은 도메인 통합 레이어
- [x] visual\*/vpx 평가 — visualpath/Module이 거의 정합, face.detect의 embedding+IoU 트래킹 이미 부합, visualbind는 새로 개발
- [x] 모듈 인터페이스 final spec (세 종류 + declarative attribute + signal-level DAG + SignalRow + UnitContext + runtime 책임)
- [x] 외부 도구 검토 (pixeltable: prod 의존 X, 인접 영역 옵션)
- [x] **정의 재정립** (2026-06-08): "산출물 N개" → **"분포 1개 + 3 읽기"**. anchor(외형/순간) × reading(중심·퍼짐·편차) 문법. "무엇을 하는 프로그램?"에 한 문장으로 답됨.
- [x] **층 2 계약 확정**: `Distribution` 프로토콜(N 구현) + `center`/`spread`/`distance` 3 읽기. "4종 statistics × 3종 selector" 4×3 표면은 이 구조로 수렴.
- [x] **JEPA PoC로 재정렬** (2026-06-08): 산출=Profile/Highlight, 트랙 A(45D)/B(V-JEPA). `Distribution`을 feature-space로 파라미터화해 둘을 같은 harness로 비교. 읽기는 PoC에서 `center`+`conditional-residual` 둘. spread·appearance/shape/category·4×3은 decision gate 이후. occlusion은 robust centroid로 흡수(legacy n=0 버그 동시 해결). → [`docs/jepa-poc.md`](docs/jepa-poc.md)
- visualstack 작업은 별 레포로 분리: `/home/hyeonrae/repo/monolith/visualstack/` (점검 + 전면 재설계 진행 중. 모듈 인터페이스/데이터 모델은 그 레포 안에서 다시 다듬어지며, 이 README의 해당 섹션들은 *출발점 가설*로만 취급).
PoC 마일스톤 (= 재개발 단계, [`docs/jepa-poc.md`](docs/jepa-poc.md) §6):

- [x] **Phase 0 — 골격**: legacy worker → `_legacy/` 보존, 워크스페이스 재구성(core `apps/momentscan` + 격리 extractor `plugins/features-{specialist45d,vjepa}`), `FeatureSource`/`CandidateLog` 계약 + 단계별 stub, 문서 reconcile. 컴파일·TOML 검증 통과.
- [x] **Phase 1 — 데이터 계약**: stash 3단(`tubelets`/`features/{A,B}`/`candidates.jsonl`) 스키마를 코드로 박음(`stash.py`), `(clip_id, track_id, rider_role)` 키 관통, `Distribution` 계약(robust center + NaN-tolerant + feature-space dim) 명문화. → [`docs/data-contract.md`](docs/data-contract.md). (high-D metric은 Phase 4로 보류)
- [ ] **Phase 2 — Step 0(공통) + 시각화**: detect+track→tubelet, re-id stitch, scene-phase, attribution = **depth 주판별**(A2). old portrait981 momentscan에서 **포팅**(depth seat assigner·ride_type·MemoryBank; scene-phase만 신규). depth는 visualstack `DepthEstimator`(bbox absolute xyxy). viz = stash의 순수 함수, **visualbus 결**(`apply_hint`+`cv2.VideoWriter` / `VideoFileSink`; vpx-viz 폐기) → trace.mp4 + report.html. → [`docs/phase2-plan.md`](docs/phase2-plan.md) · [`handoff`](docs/handoff-visualstack-depth-viz.md)
- [ ] **Phase 3 — Track A + eval harness**: per-track `Distribution`(45D) → `center`→Profile narrow+rank, `conditional-residual`→Highlight. contact sheet/montage/candidate-log. seed eval ~50/50 (`~/Videos/reaction_test`).
- [ ] **Phase 4 — Track B 드롭인**: 같은 harness에 V-JEPA feature(frozen+light head).
- [ ] **Decision gate**: B가 A를 이기나? 특히 occlusion/lighting drift에서?
- [ ] portrait981 정상화 / 프로젝트명 — gate 이후.

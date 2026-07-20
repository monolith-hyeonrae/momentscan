# momentscan 아키텍처 — 구조 계약의 단일 진실

> 도메인/제품 정의는 [`docs/products.md`](docs/products.md), 기준-출처 렌즈는
> [`docs/criterion-source.md`](docs/criterion-source.md), **경계 계약의 한눈 지도는
> [`docs/contracts.md`](docs/contracts.md)** (Job/Result·SubjectQuery·tubelets 경계 등).
> 살아있는 변화·비목표 원장 = [`docs/change-forecast.md`](docs/change-forecast.md)(축 A~L·철학 ①~④),
> 그 시점 심사 = [`docs/architecture-review-2026-07-16.md`](docs/architecture-review-2026-07-16.md).
> 이 문서는 **코드가 왜 이렇게 배치되어 있고, 새 코드가 어디에 앉아야 하는가**의
> 단일 진실이다. 각 패키지 `__init__.py`는 여기를 가리키는 한두 줄만 갖는다.
>
> **재작성 이력**: 2026-07-20, A″ 그룹화(infra/perception/products) 착지 후 전면
> 재작성 — 직전 동결본(2026-07-06)은 재배치 이전에 얼어 은닉-선언 사슬의 부패
> 정점이 되어 있었다(심사 §2 신규 갭 4). 경로는 이제 G4 pytest 가드가 지킨다(§9).

## ① 정체성 — momentscan은 세 가치 질문이 답해지는 곳

momentscan은 세 **가치 질문**을 답한다 (change-forecast ④):
- **likeness** — "어떻게 이 고객의 외형 특성을 이해하나" (기준=피사체·사실)
- **portrait** — "어떻게 좋은 얼굴을 선택하나" (기준=저작자 쿼리)
- **highlight** — "좋은 순간이란 무엇인가" (기준=어트랙션 맥락)

이것이 visualstack과의 역할 분담을 정한다: **visualstack = 기계 질문의 도구상자**
("어떻게 재고 나르고 저장하나"), **momentscan = 세 가치 질문이 답해지는 연구 공방**.
관계는 정확히 "도구를 벼리는 공방"과 "`bin/`에 설치하는 곳" — momentscan은 몰튼
정의를 끓이므로 통합이 정당하고, visualstack 졸업은 **인터페이스 동결 이벤트**로
frozen된 기계(stash·serve·pipeline 선언·media)만 이주한다. "간략해질수록 승리"의
구조적 형태가 이 분담이다.

## ② 지배 원칙

**/dev 원칙 (구조 투명성).** `/dev/video*`·`/etc/systemd`처럼, **프로그램을 실행하거나
커맨드를 치지 않아도 파일 트리 자체가 "무엇이 셋업되어 돌고 있나"를 답한다.**
디렉토리 하나 = 질문 하나. 파일 배치 전의 테스트: *"이 디렉토리의 `ls`가 여전히
자기 질문에 정직하게 답하는가?"* 이름이 내용의 계약이다 — `ls`가 거짓말하면 구조가
없는 것보다 나쁘다.

**벽은 변화 축을 인용한다.** 패키지·인터페이스·계약을 세우는 모든 결정은
change-forecast 원장의 축(A~L)을 인용한다 — **인용할 축이 없는 벽은 서브루틴
묶음이다**(Parnas가 경고한, 플로차트 단계를 모듈로 착각한 분할). 그래서 §③ 층
지도의 모든 행에 "인용 축" 열이 있다.

**숨기는 비밀 2종** (change-forecast ③ — 몰튼 개념의 분해):
- **알고리즘 선택** (관측 스테이지 층) — 영구 유동(SOTA 갱신·개발자 교체는 국면이
  아니라 상수). 봉사 = 문제-언어 스키마 고정 + 어댑터 1점 + 측정 검증. **얼 필요
  없다** — 안정 대상은 인터페이스지 구현이 아니다. 합격 시험: *"산출물 스키마 변경
  없이 알고리즘을 교체할 수 있는가"* (스키마가 문제 언어=각도·valence·AU·정준
  좌표면 통과, 솔루션 언어=모델 고유 표현이면 누설).
- **정의** (제품 엔진 층) — 진짜 몰튼("좋은 순간이란 무엇인가"). legible 통합 유지,
  졸업 규칙은 여기에만 적용.

보조 원칙:
- **변경의 축이 곧 구분의 축** — 같은 이유로 바뀌는 것은 같이 살고, 다른 이유로
  바뀌는 것은 떨어져 산다. 층마다 "왜 바뀌나 / 바뀌면 무엇을 치르나 / 어떻게
  검증하나"가 다르다.
- **이동은 작업이 지불한다** — 구조는 예상이 아니라 실증된 필요를 따라 자란다.
  (레거시는 예상 기반 패키징으로 무너졌다.)
- **molten은 크게, frozen은 정밀하게** — 정의가 끓는 것은 쪼개지 않는다.

## ③ 층 지도 — 디렉토리 = 질문 = 변경축 = 검증

### 4결 지도 — user의 네임스페이스 요구가 착지한 형태

최상위는 **4결**(질문 가족 4개)로 묶인다. 이 그룹화(A″, 2026-07-16/17)는 한 곳이
아니라 **3중으로 표현**되어 서로를 지킨다: **문서**(이 지도) · **isort**(내부 임포트
순서 infra→perception→products→기타, ruff "I" 강제, code-style §5) · **tier**(산출물
성질 선언, `infra/pipeline/registry/tiers.py`). 세 표현이 어긋나면 그중 하나가 거짓말한다.

| 그룹 | 한 문장 | 성격 |
|---|---|---|
| **infra/** | 돌게 하는 기계 — 제품 무관 시공 | 졸업석(visualstack 예약, R16/17 절단선), 얼면 통째 하차 |
| **perception/** | 픽셀 → 믿을 수 있는 읽기 | 관측; 단위기술 회전 지대(모델은 갈리고 계약은 언다) |
| **products/** | 세 가치 질문의 답 | 질문=안정·껍질=얼릴 수 있음·답=몰튼 (+ 공유 채점 기판 select) |
| **surface/·verify/** | 렌더 / 자기신뢰 | 소비자 · green의 정의 |

### 방향 표 — infra 내부의 의존은 한 방향으로만 읽힌다 (요구 #1)

infra 자식은 **관문(inbound)** 과 **배관(outbound)** 이 **잡(job) 계약을 이음매로만**
만난다 — 관문이 배관을 직접 얽지 않는다.

| 방향 | 자식 | 숨기는 비밀 | 인용 축 |
|---|---|---|---|
| inbound | `infra/cli/` | 명령 파싱·프로세스 기동 형태 (argv 방언→API 매핑) | F |
| inbound | `infra/serve/` | 회사 연동 방언 (transport·resultPath·인증·관측) | A · F |
| internal | `infra/pipeline/` | 실행 기계 (순서·신선도·선언⇄실행 정합) | G (졸업 예약석) |
| outbound | `infra/store/` | 저장 배치·백엔드 (S3 이행 시 수술 부위) | J |
| outbound | `infra/media.py` | 픽셀 인코딩 규약 (H.264 all-intra) | G (visualbase 예약석) |

### 전체 층 지도

| 위치 | 답하는 질문 | 숨기는 비밀 | 인용 축 | 검증 |
|---|---|---|---|---|
| `infra/` | 층들을 무엇으로 **잇고 돌리나** | 위 방향 표 (기계·배관·관문) | F·A·G·J | check · replay |
| `perception/extraction/` | 픽셀→관측의 **모델 선택** | 현재 이 측정을 구현하는 알고리즘 (어댑터 1점) | C | freshness + 모델 eval |
| `perception/subjects/` | 관측→**사람** 구성 | 트래킹·stitch (클립-스코프 가정 **내재**) | C · I | replay |
| `perception/readings/` | 측정을 어떻게 **해석**하나 | 문제-언어 공식 — **값은 갖지 않는다(값=preset)** | C | eval-gate(전 제품 델타) |
| `perception/gates.py` | 이 관측을 **믿어도 되나** | 판정 사다리 (REASONS 폐어휘·trace 스키마) | K | replay + gate_trace 감사 |
| `products/` | 무엇을 **내놓나** | 세 가치 질문의 **현재의 답** (정의·공식·몰튼) | D · H | frozen eval 쌍 |
| `products/select.py` | (제품 아님) 공유 **채점 기판** | frame_scores + WHEN 공식 물리 거처 (소유=highlight, G1) | D | frozen 168쌍 |
| `products/evals/` | 스스로를 어떻게 **채점하나** | 채점 방법론 (rescore=현재 코드 재계산, 영구) | — (E1) | 동결 인간 평결 |
| `surface/` | 사람에게 어떻게 **보여주나** | 렌더 형태 (구독자; 재계산 잔존 2곳=G10 어음) | — | 눈 (replay 밖) |
| `verify/` | 스스로를 어떻게 **믿나** | green의 정의 (tolerance·IGNORE·REPLAY 스테이지) | G · L | 스스로 |
| **preset/** (신설 예정) | 시설/카메라/기구 **의존 값** | ~60개 정책 임계 + fps (C9의 물리 실체) | B · E | test_preset 값 핀 |
| **contracts.py** (미구축, r6-egress) | wire 계약의 **형태 검증** | C1/C11 msgspec (LikenessV1·ResultV1) | L | missing-field raise |

> **preset/·contracts.py는 아직 없다** — B(정책 값)와 L(계약 검증) 축의 **예약된
> 은닉처**다. preset/은 likeness 트랙이, contracts.py는 r6-egress 트랙이 첫 지불자로
> 짓는다(§⑤·§⑨). 이 지도가 그 자리를 미리 선언해 둔다.

**extraction의 이중 멤버십 자백**: 상위 축 `extraction→subjects→readings→products`는
**데이터흐름 단계 절단이기도** 하다 — 정확히 Parnas가 경고한 모양이다. 이 레포가
살아남는 건 각 단계가 대체로 비밀과 일치하기 때문이고, **어긋나는 곳마다 잔여물이
고인다**: `infra/media.py`(단계 축엔 픽셀 유틸이나 비밀 축=인코딩 규약이라 infra로
졸업)를 `perception/subjects/crops.py`가 역참조하는 **패키지-레벨 양방향**이 그
증거다. 계약 체인(contracts.md)은 단방향인데 실물이 위반 — media의 진짜 예약석은
visualbase(졸업 4단계)이니 **그때까지는 소개가 정직해야 한다**. freshness는 이
엣지를 추적한다(crops 클로저가 `infra/media.py` 포함, `infra/store` 제외 = 픽셀 규약은
알고리즘, IO 배관은 아님).

## ④ 제품 엔진 3층 해부 — 질문이 곧 모듈

각 제품 엔진은 **질문**이며, 세 층으로 해부된다 (change-forecast ④). 세 층이 `Product`
선언 한 곳에 다 보인다(`infra/pipeline/registry/products.py`): `question` · (`egress`+`scorer`) · (`state`+공식).

1. **질문** (`Product.question`) — 안정. 제품 수명 동안 불변. 각 엔진 독스트링 첫 줄 = 자기 질문.
2. **껍질** — 얼릴 수 있음: 답의 **형식**(`egress` 계약 C1/C11) + 답의 **채점기**
   (`Product.scorer` — E1 회귀 세트·코드북 = 질문의 조작화, 몰튼 엔진의 인터페이스 절반).
3. **현재의 답** (`state="molten"` + 공식) — 몰튼(정의·공식·임계). 엔진의 비밀은 여기.

**G1 소유권 어음** — WHEN 공식은 `products/select.py`의 명명 PUBLIC 함수
`when_from_channels`에 단일홈이 있고, 독스트링이 소유권을 선언한다: *owner = highlight
engine; resident in select.py until R16/17 — 물리 이전은 energy 재편 트랙이 지불 가능.*
지리(select의 집)는 소유(highlight)와 분리되어 어음으로 남는다 — 미러(옛 highlight.py
3.0 리터럴 복제)는 구독으로 소거됐다.

**G2 채점기 압력** — `registry_drift`가 `state=="molten" ∧ scorer==""`이면 warn:
*"답을 다시 쓰기 전에 질문의 채점기를 세운다(원장 ④-①)"*. likeness가 이 노랑을 내는
게 정상(E1 압력); highlight는 scorer(세그먼트 평가 레인)가 있어 무경고.

**G12 eval 예약석** — E1 신-스키마 채점기의 정본 자리는 **E1 재개 트랙이 결정한다**
(파일 선점 없음). `products/evals/`는 방법론(rescore=현재 코드로 동결 평결에 재측정)을
쥐고, 그 방법론의 parquet 전환은 **영구 기각**(렌더러에 옳은 처방을 채점기에 적용 금지).

**졸업 규칙 (균일 성장)**:
- **L2 읽기 도메인 졸업**: 시그널 도메인은 *백엔드 ≥2 또는 융합/양자화 정책 보유* 시
  `signals.py`에서 자기 모듈로 (pose·geometry 완료 · identity가 다음, 6D-가림이 지불).
- **제품 졸업**: 정의가 얼면 자기 모듈로 (portrait E008-E009 후, highlight 2026-07-03).
  `products/select.py`는 제품이 아니라 공유 채점 기판 — tier=substrate(D5 정직화).
- 격리 승급: §⑦ 사다리 ①→②→③.

## ⑤ 정책의 집 — preset (C9의 물리 실체, 신설 예정)

시설/카메라/기구가 바뀌면 달라지는 값(정책 임계 ~60개 + fps)은 오늘 15파일에
산개(축 B=최대 노출)한다. 그 은닉처가 **preset/ 파이썬 모듈 패키지**다.

**O/X 판정 기준** (preset에 들어가는가):
- **O** — 시설/카메라/기구가 바뀌면 달라지는 값: `CAMERA_FRONTAL_DEG`(이 카메라의
  경험적 정면), phase 모델, 좌석 규칙, 기대 문장, 방출 노브.
- **X** — 연구가 바뀌면 달라지는 **공식/구조**: WHEN 합성(products), 게이트 사다리
  구조(perception/gates.py), 정준 프레임 계약(readings/geometry). 이것은 코드지 값이 아니다.

**왜 파이썬 모듈인가 (yaml/toml 기각)**: freshness가 transitive import 클로저 mtime을
보므로 **파이썬 모듈은 값 수정 → 소비 스테이지만 자동 stale**(세밀). toml은 클로저
밖이라 `_external_deps` 수동 등록 + 전체-stale 보수 결합이 강제된다 — L1/test_3(stale
오신뢰 사고 3회) 재발 경로. provenance 주석("E002"·"cap_1 캘리")과 blame 사슬도 상실.

**로딩 경로** (안A 경로 — 값은 인자로 흐른다):
```
Job.domain_profile ("race981" 기본)
   → run_pipeline 인자 (additive)
   → 초입 1회 해석 (미지 이름 = raise)  ── 여기가 preset을 아는 유일한 지점
   → job.json 기록 (provenance)
   → 소비 러너가 명시 kwargs 로 전달:  runner → stage(…, bands=preset.camera.bands)
```

**"함수는 preset을 모른다" = 명문화된 종착 형태 (G5).** 스테이지/게이트 함수는
preset을 임포트하지 않는다 — 값을 **인자로 받는다**. 신설 상수는 태어날 때부터
인자 전달(`pose_class(…, bands=preset.camera.bands)`). 과도기에만 정의부 1줄
재바인딩을 허용하되 종착은 이 형태이고, AST authority 테스트(G8)가 리터럴 재정의를
감시한다. **런타임 스위칭(요청별 preset 교체)은 두 번째 시설이 지불한다** — 시설 1개인
오늘 13러너 시그니처에 threading을 선지불하는 것은 C9 원문 위반.

## ⑥ 실행 기계 — stash를 파이프 삼은 make (정직한 경계)

실행 층은 이미 UNIX다: `infra/pipeline/runner.py`가 균일 러너 시그니처
`(probe, fn(out, clip, src, fps))` 13개를 topo 순서(`registry.topo_order`)로 돌리고,
skip = 산출물 존재 ∧ (소스 mtime ∧ 직접 상류 artifact보다 새로움). 소스 신선도
(`infra/pipeline/freshness.py`) = transitive import 클로저 + 외부 모델파일 lazy stat.
선언⇄실행⇄신선도 3중 정합을 import-time assert 2개와 `verify registry`가 강제하니
**"Makefile이 곧 실행 계획"** 성질까지 있다. tolerance replay는 make에 없는 회귀
게이트로 유비를 보강한다.

**유비가 거짓이 되는 4곳 (전부 자백 있음)**:
1. **값 변경 미포착** — `infra/store`(IO 배관)는 클로저에서 제외라, stash 포맷/값만
   바뀌면 mtime이 떠도 stale이 안 된다 → `--force` 수동 (freshness.py 자백).
2. **선언-물리 사각** — landmarks는 무모듈(실생산자=plugins 백엔드, D4)이라 freshness가
   features 모듈로만 추적. `features` 산출물도 선언 artifact='features.parquet' vs 실제
   `features/{track}.parquet` 디렉토리 불일치 (structure-audit 접수 #10, 별도 소형 트랙).
3. **외부 파일 수동 등록** — 모델 가중치(ONNX·canonical.obj)는 import 클로저 밖이라
   `_external_deps`에 수동 등록 의존; 미등록 모델 스왑은 미포착.
4. **네이티브 크래시 비격리** — 파이썬 예외만 record-and-continue, onnx/mediapipe
   segfault는 런 전체 사망. R16/17 격리는 **의도적 보류** — 트리거는 철학이 아니라
   run.json에 관측된 네이티브 크래시 빈도(§비목표).

## ⑦ 격리 사다리 — 경계는 항상, 격리는 필요할 때

레거시 vpx-plugins(+visualpath 자동 격리)의 **의도**를 기계 없이 유지한다. 어떤
추출기든 아래로 승급 가능; 승급은 그 필요가 실증될 때 지불한다.

| 단 | 격리 수준 | 지불 시점 | 현재 거주자 |
|---|---|---|---|
| ① | in-app 모듈 (경계만) | 무료 | parse · fashion · headpose |
| ② | workspace 패키지 (별도 venv 가능) | 의존성 충돌(onnx/torch) | features · scene → `plugins/features-specialist45d` |
| ③ | plugin + bus (프로세스·warm 상주) | 실시간/상주 필요 | detect · landmarks → visualstack plugins (visualpath DAG) |

- `plugins/` = 격리된 모델 **백엔드**(②단)이지 분석 노드가 아니다 — 노드는
  `perception/extraction/`의 얇은 어댑터(features.py·scene.py). [`plugins/README.md`](plugins/README.md) 참조.
- landmarks는 모듈 없는 유일한 노드 — 이미 ③단(ingest 기계가 visualstack
  face-landmarks 플러그인으로 생산). freshness 사각(§⑥-2)이 이 물리화의 대가다.
- ②단의 스왑 포트 = `infra/store/ports.py`의 `FeatureSource` (Track B/vjepa 예약석 —
  계약 완성이지 교체 실증은 아직; vjepa 소비자 0).

## ⑧ 좌표계 지도 — 공간마다 홈과 정합 규칙이 선언되어 있다

> 서술 스펙(투영표·측정 근거·invariant·변경 절차) = [`docs/coordinate-conventions.md`](docs/coordinate-conventions.md)

| 공간 | 규약 | 선언 홈 |
|---|---|---|
| 이미지/픽셀 | y-down · bbox=xyxy 절대픽셀 · 크롭=portrait_box(4:5) 레터박스 | `perception/subjects/crops.py`(ROI 기하) · `infra/media.py`(자르기/인코딩) |
| MP 오일러 (yaw·pitch·roll) | **정의적 홈 = `pose.euler_from_transform`** — 모든 백엔드가 여기 정합 · 의미 축이름=registry POSE 필드 | `perception/readings/pose.py` |
| 6DRepNet 원좌표 | MP 오일러의 **3축 전부 거울** → 어댑터가 (−y,−p,−r) 정렬 (축별 부호-corr 검증: raw −0.97/−0.70/−0.63 → flip 후 전부 양) | `perception/extraction/headpose.py` |
| 랜드마크 정준 프레임 | origin=centroid · axis_flip **(1,−1,−1)**=image↔camera(π about x, det=+1 가드) · scale=rms 무차원 · basis 478/468 | `perception/readings/geometry.py` CANONICAL_FRAME (+`momentscan map frame`) |
| ARKit blendshape | 52축 활성도(무차원) — 좌표 아님, 인덱스 계약=signals BS_* · 생성리그와 공유(render-query) | `perception/readings/signals.py` |

**규칙**: 새 포즈/기하 백엔드 추가 = 어댑터에서 정합 + **측정 검증(축별 부호-corr, 커버
교집합 프레임)** 필수 — "yaw만 맞추고 나머지는 통과"가 2026-07-02까지의 잠복 지뢰였다
(융합 스트림이 프레임 소스별 좌표 혼합; abs() 소비자만 있어 무사했지만 signed 소비
시작 순간 오염).

## ⑨ 검증 척추 — 모든 구조 변경의 게이트

| 도구 | 증명하는 것 |
|---|---|
| `momentscan verify registry` | 선언 drift 0 (STEPS⇄ANALYZERS⇄PRODUCTS⇄gate ladder) + G2 채점기 warn |
| `momentscan verify replay` | 행동 불변 (동결 입력 재실행 = tolerance-identical) |
| `momentscan verify api` | wire 계약 (인프로세스 서버 vs openapi.yaml) |
| `momentscan map graph`/`products`/`cascade` | 선언 그래프 렌더 (도는 선언 = 그려지는 선언) |
| freshness | 소스>산출물 staleness (import 클로저 + 외부 모델 mtime) |
| frozen eval 168쌍 | 로직 변경의 제품 델타 |
| **G4 경로-실존 pytest** | **문서 주소록도 D1급 가드** — docs + 이 문서(ARCHITECTURE.md)가 인용한 소스 경로가 실존하는지 grep-검사. "선언이 진실"을 자부하는 레포에서 선언 부패는 구조 부패와 동급이다(심사 §5-4). |

**"답을 다시 쓰기 전에 채점기를 세운다"** — E1(채점기)이 energy 재편(답 재작성)에
선행하는 순서의 구조적 근거(원장 ④-①). G2 warn이 이 순서를 기계화한다.

구조 변경의 규율: whole-file 이동 + import 재작성 → check → replay-check →
(렌더 경로는 **실렌더**까지 — import 스모크는 함수 내부 버그를 못 잡는다).
문자열 모듈 참조(`"momentscan.…"`)·**로거 이름**은 재작성기가 못 보므로 grep 전수 필수
(로거 이름은 관측 정체성이라 이동 시에도 **구 경로 유지**).

## ⑩ 멤버십 테스트 — 파일 배치 시

- `perception/extraction/`: *"전담 전문가가 소유·심화할 수 있는 신호 처리 전문분야인가?
  (모델이 관측하는가?)"* — detect·parse·fashion·headpose·features·scene.
  tubelets는 아니다(조립), crops도 아니다(영속화) → `perception/subjects/`.
- `perception/subjects/`: *"subject 계약이 바뀔 때 함께 바뀌는가?"* — attribute(좌석
  판정) → tubelets(**경계 계약**: 추출기는 tubelets만 읽는다, raw detections 금지) →
  crops(튜브의 픽셀, data retention) → stitch(re-id 병합). ROI **기하**(portrait_box)는
  subject 계약이라 여기; 자르기/인코딩 **실행**은 범용 규약이라 `infra/media.py`.
- `perception/readings/`: *"이 값을 바꾸면 세 제품이 전부 함께 바뀌어야 하는가?"*
  (백엔드-중립 해석 정책). signals=얇은 단일-백엔드 리더, geometry=정준 프레임 계약,
  pose=MP⊕6D 융합·양자화, emotion=valence 척추.
- `perception/gates.py`: *"가치 판단이 아니라 '이 관측을 믿어도 되나' 측정 질문인가?"*
  — gate=reject-route ≠ reading. 판정은 관측 계층의 이진 판별기지 순수 실행 기계가 아니다.
- `infra/`: *"제품과 무관한 배관/관문/실행 기계인가? (계약이 얼면 visualstack으로 통째
  떠날 수 있는가?)"* — cli·serve·pipeline·store·media.
- `products/`: *"세 가치 질문 중 하나의 '현재의 답'인가?"* — select는 예외(공유 기판,
  tier=substrate로 정직 선언; "ls products/가 정직한가" 테스트는 이 단서로 통과).
- **preset 멤버십**: *"시설/카메라/기구가 바뀌면 달라지는 **값**인가?"* (O) vs
  *"연구가 바뀌면 달라지는 **공식/구조**인가?"* (X — 코드지 값이 아니다). §⑤ O/X 기준.

## ⑪ 비목표 — 안 하는 것

전체 목록·재개 조건 = [`docs/change-forecast.md`](docs/change-forecast.md) 원장 ②.
요지: cross-visit 메모리 · utils/common 서랍 · 조기 visualstack 졸업 · 축 I(라이브)
선제 추상화(은닉 불가 축, 시점 오면 재작성) · Kafka/오토스케일/msgq · 네이티브 크래시
격리(실측 트리거 대기) · 전면 리포맷 · 2곳-중복의 홈 신설. 공통 규율: **새 레이어·
미니도구·2곳-중복 홈 없음**(원장 ②) — 인용할 변화 축이 없으면 벽을 세우지 않는다.

---

## 부록: "첫 15분" 문서 시험 (요구 #3 — 자기 검사)

이 문서가 제 역할을 하는지의 시험 = **신참이 코드를 실행하지 않고 하향 탐색으로
"기능군 → 모듈"에 도달하는가.** 3단 경로가 성립해야 한다:

1. **이 문서 →** §①로 "무엇을 하나"(세 가치 질문), §③ 4결 지도로 "어느 그룹인가"
   (예: "게이트 판정은 관측을 믿는 질문 → perception").
2. **임포트 블록 →** 아무 소비자 파일을 열면 임포트가 infra→perception→products 순으로
   그룹져 있어(isort "I" 강제), 의존 방향(시공→관측→제품)이 눈에 읽힌다.
3. **IDE 점프 →** §③/§⑧의 backtick 경로(`perception/gates.py` 등)로 바로 점프. 이
   경로들은 **G4 pytest가 실존을 지키므로**(§⑨) 문서가 낡아 죽은 주소를 가리키지 않는다.

**자기 검사 통과 조건**: 위 3단이 끊기지 않는다 = (a) 4결 지도가 모든 파일의 상위 그룹을
답하고, (b) isort 그룹 순서가 4결과 일치하고, (c) 인용된 경로가 전부 실존한다. 셋 중
하나라도 깨지면 이 문서는 "단일 진실" 자격을 잃는다 — 그래서 셋 다 기계(isort·G4)가
지킨다. 이 부록이 그 계약의 명문이다.

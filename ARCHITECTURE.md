# momentscan 아키텍처 — 구조 계약의 단일 진실

> 도메인/제품 정의는 [`docs/products.md`](docs/products.md), 기준-출처 렌즈는
> [`docs/criterion-source.md`](docs/criterion-source.md). 이 문서는 **코드가 왜
> 이렇게 배치되어 있고, 새 코드가 어디에 앉아야 하는가**의 단일 진실이다.
> 각 패키지 `__init__.py`는 여기를 가리키는 한두 줄만 갖는다.

## 지배 원칙 — /dev 원칙 (구조 투명성)

`/dev/video*`·`/etc/systemd`처럼, **프로그램을 실행하거나 커맨드를 치지 않아도
파일 트리 자체가 "무엇이 셋업되어 돌고 있나"를 답한다.** 디렉토리 하나 = 질문
하나. 파일을 배치하기 전의 테스트: *"이 디렉토리의 `ls`가 여전히 자기 질문에
정직하게 답하는가?"* 이름이 내용의 계약이다 — `ls`가 거짓말하면 구조가 없는
것보다 나쁘다.

보조 원칙:
- **변경의 축이 곧 구분의 축** — 같은 이유로 바뀌는 것은 같이 살고, 다른 이유로
  바뀌는 것은 떨어져 산다. 층마다 "왜 바뀌나 / 바뀌면 무엇을 치르나 / 어떻게
  검증하나"가 다르다.
- **이동은 작업이 지불한다** — 구조는 예상이 아니라 실증된 필요를 따라 자란다.
  (레거시는 예상 기반 패키징으로 무너졌다.)
- **molten은 크게, frozen은 정밀하게** — 정의가 끓는 것은 쪼개지 않는다.

## 층 지도 — 디렉토리 = 질문 = 변경축 = 검증

| 위치 | 답하는 질문 | 바뀌는 이유 | 검증 |
|---|---|---|---|
| `extraction/` | 어떤 **신호 분석**이 돌고 있나 | 모델 교체·백엔드 추가 | freshness + 모델 eval |
| `subjects/` | 신호가 붙을 **대상**은 어떻게 구성되나 | subject 계약 변경(누가·어떤 튜브·어떤 픽셀) | replay |
| `domains/` | 측정을 어떻게 **해석**하나 | 해석 정책 연구(융합·임계·양자화·기준계) | eval-gate(전 제품 델타) |
| `gates.py` | 무엇으로 **판정**하나 | 판정 규칙 | replay + gate_trace 감사 |
| `products/` | 무엇을 **내놓나** | 제품 정의(molten) | frozen eval 쌍 |
| `surface/` | 사람에게 어떻게 **보여주나** | 렌더 방식(행동 대가 0) | 눈 (replay 밖) |
| `verify/` | 스스로를 어떻게 **믿나** | 검증 방법론 자체 | 스스로 |
| top-level | 층들을 무엇으로 **잇나** | 러너(pipeline·ingest·daemon)·포트(stash·ports)·규약(media=인코딩)·선언(analyzers)·CLI | check |

멤버십 테스트 (파일 배치 시):
- `extraction/`: *"전담 전문가가 소유하고 심화할 수 있는 신호 처리 전문분야인가?
  (모델이 관측하는가?)"* — detect·parse·fashion·headpose·features·scene.
  tubelets는 아니다(조립), crops도 아니다(영속화) → subjects/.
- `subjects/`: *"subject 계약이 바뀔 때 함께 바뀌는가?"* — attribute(좌석 판정)
  → tubelets(**경계 계약**: 추출기는 tubelets만 읽는다, raw detections 금지)
  → crops(튜브의 픽셀, data retention). ROI **기하**(portrait_box)는 subject
  계약이라 여기; 자르기/인코딩 **실행**은 범용 유틸이라 `media.py`(H.264
  all-intra 규약의 단일 홈).
- `domains/`: *"이 값을 바꾸면 세 제품이 전부 함께 바뀌어야 하는가?"* (백엔드-중립
  해석 정책). signals=얇은 단일-백엔드 리더, geometry=정준 프레임 계약,
  pose=MP⊕6D 융합·양자화, emotion=valence 척추, stitch=identity 병합.

## 격리 사다리 — 경계는 항상, 격리는 필요할 때

레거시 vpx-plugins(+visualpath 자동 격리)의 **의도**를 기계 없이 유지한다.
어떤 추출기든 아래로 승급 가능; 승급은 그 필요가 실증될 때 지불한다.

| 단 | 격리 수준 | 지불 시점 | 현재 거주자 |
|---|---|---|---|
| ① | in-app 모듈 (경계만) | 무료 | parse · fashion · headpose |
| ② | workspace 패키지 (별도 venv 가능) | 의존성 충돌(onnx/torch) | features · scene → `plugins/features-specialist45d` |
| ③ | plugin + bus (프로세스·warm 상주) | 실시간/상주 필요 | detect · landmarks → visualstack plugins (visualpath DAG) |

- `plugins/` = 격리된 모델 **백엔드**(②단)이지 분석 노드가 아니다 — 노드는
  `extraction/`의 얇은 어댑터(features.py·scene.py). [`plugins/README.md`](plugins/README.md) 참조.
- landmarks는 모듈 없는 유일한 노드 — 이미 ③단(ingest 기계가 visualstack
  face-landmarks 플러그인으로 생산).
- ②단의 스왑 포트 = `ports.FeatureSource` (Track B/vjepa 예약석).

## 졸업 규칙 (균일 성장)

- **L2 도메인 졸업**: 시그널 도메인은 *백엔드 ≥2 또는 융합/양자화 정책 보유* 시
  signals.py에서 자기 모듈로 (pose 2026-07-02 · geometry 동일 · **identity가 다음**,
  6D-가림 작업이 지불). 근거: drift 지도 = 홈 없는 도메인 지도.
- **제품 졸업**: 정의가 얼면 자기 모듈로 (portrait이 E008-E009 후 그랬듯).
  molten인 동안은 통합 유지 (select = likeness picks + highlight, 본질 결합).
- 격리 승급: 위 사다리 ①→②→③.

## 좌표계 지도 — 공간마다 홈과 정합 규칙이 선언되어 있다

> 서술 스펙(투영표·측정 근거·invariant·변경 절차) = [`docs/coordinate-conventions.md`](docs/coordinate-conventions.md)

| 공간 | 규약 | 선언 홈 |
|---|---|---|
| 이미지/픽셀 | y-down · bbox=xyxy 절대픽셀 · 크롭=portrait_box(4:5) 레터박스 | `subjects/crops.py`(ROI 기하) · `media.py`(자르기/인코딩) |
| MP 오일러 (yaw·pitch·roll) | **정의적 홈 = `pose.euler_from_transform`** — 모든 백엔드가 여기에 정합 · 의미 축이름=registry:POSE_FIELDS | `domains/pose.py` |
| 6DRepNet 원좌표 | MP 오일러의 **3축 전부 거울** → 어댑터가 (−y,−p,−r) 정렬 (축별 부호-corr로 검증: raw −0.97/−0.70/−0.63 → flip 후 전부 양) | `extraction/headpose.py` |
| 랜드마크 정준 프레임 | origin=centroid · axis_flip **(1,−1,−1)**=image↔camera(π about x, det=+1 가드) · scale=rms 무차원 · basis 478/468 | `domains/geometry.py` CANONICAL_FRAME (+`momentscan frame`) |
| ARKit blendshape | 52축 활성도(무차원) — 좌표 아님, 인덱스 계약=signals.BS_* · 생성리그와 공유(render-query) | `domains/signals.py` |

**규칙**: 새 포즈/기하 백엔드 추가 = 어댑터에서 정합 + **측정 검증(축별 부호-corr, 커버 교집합 프레임)** 필수 —
"yaw만 맞추고 나머지는 통과"가 2026-07-02까지의 잠복 지뢰였다(융합 스트림이 프레임 소스별 좌표 혼합;
abs() 소비자만 있어 무사했지만 signed 소비 시작 순간 오염).

## 검증 척추 (모든 구조 변경의 게이트)

| 도구 | 증명하는 것 |
|---|---|
| `momentscan check` | 선언 drift 0 (STEPS⇄ANALYZERS⇄PRODUCTS⇄gate ladder) |
| `momentscan replay-check` | 행동 불변 (동결 입력 재실행 = tolerance-identical) |
| `momentscan graph` / `products` / `cascade` | 선언 그래프 렌더 (도는 선언 = 그려지는 선언) |
| freshness | 소스>산출물 staleness (import 클로저 + 외부 모델 mtime) |
| frozen eval 168쌍 | 로직 변경의 제품 델타 |

구조 변경의 규율: whole-file 이동 + import 재작성 → check → replay-check →
(렌더 경로는 **실렌더**까지 — import 스모크는 함수 내부 버그를 못 잡는다).
문자열 모듈 참조(`"momentscan.…"`)는 재작성기가 못 보므로 grep 전수 필수.

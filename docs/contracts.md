# momentscan 경계 계약 — 한눈 지도

> **운용 방식**: 간략하게 시작, 경계가 변할 때마다 이 문서를 같이 갱신한다(변경 커밋에 포함).
> 각 계약의 **권위는 코드/스키마의 홈**이고 이 문서는 지도다 — 홈이 있는 계약은 포인터만,
> 아직 홈이 없는 계약은 여기 서술이 임시 권위. 미정 경계는 빈 슬롯으로 이름만 올린다
> (에러가 아니라 "쓸 자리 표시"). 구조 계약은 [`ARCHITECTURE.md`](../ARCHITECTURE.md),
> 제품 정의는 [`products.md`](products.md).

## 계약 인덱스

| # | 경계 | 계약 | 권위(홈) | 드리프트 가드 |
|---|---|---|---|---|
| C1 | 서비스 ↔ momentscan | **Job/Result** (아래 초안) | 이 문서 (코드 홈 미정) | — |
| C2 | 대상 선정 (WHO) | **SubjectQuery** (아래) | 이 문서 → 구현 시 `subjects/` | — |
| C3 | 대상 구성 → 추출기 | tubelets 경계: *추출기는 tubelets만 읽는다, raw detections 금지* | `subjects/__init__` · `stash.TUBELET_COLUMNS` | `momentscan verify registry` |
| C4 | 스테이지 ↔ 스테이지 | stash 아티팩트 (per-artifact 컬럼맵·dtype 캐스트·`_validate`) | `stash.py` | write-시 validate |
| C5 | 게이트 → 소비자 | gate_trace (사다리 전 verdict + REASONS 어휘) | `gates.py trace_rows/REASONS` | import-시 assert + check |
| C6 | 특징 추출 → 제품 | registry FIELDS (46-dim 계약) + FeatureSource 포트 | specialist45d `registry.py` · `ports.py` | — |
| C7 | 좌표계 | 공간·투영·invariant | [`coordinate-conventions.md`](coordinate-conventions.md) · `geometry.CANONICAL_FRAME` | det=+1 assert · `momentscan map frame` |
| C8 | 제품 → 배달물 | egress (Result에 실리는 산출물 부분집합) | `analyzers.Product.egress` · `momentscan map cascade` | check |
| C9 | 도메인 지식 ↔ 코어 | **domain profile (preset)** — 빈 슬롯 | 미정 (두 번째 도메인이 지불) | — |
| C10 | 저장 서술 | 스테이지 분리·stash 레이아웃 | [`data-contract.md`](data-contract.md) | — |
| C11 | likeness → face_recipe | **likeness.json 스키마 v1 (동결)** — 아래 | `products/likeness.py` + 이 문서 §C11 | schema 필드 + verify replay |
| C12 | momentscan ↔ visualstack | **substrate 사용 경계** (임포트 화이트리스트) — 아래 | 이 문서 §C12 | R15 경계 테스트 (refactor-exec-plan) |

## C1 — Job/Result (초안 v1 — 알파 요구 반영 2026-07-03)

서비스 연동(S3 in/out · 2000 vids/day)과 재사용 설계가 공유하는 외곽 계약.
**알파 배포 형태(user)**: 로컬 서버 + AWS 서버에 올림 · 트리거 = **HTTP + Eureka**(등록),
**Kafka 고려**(→ 페이로드는 transport-agnostic: REST 바디 = Kafka 메시지 = 아래 Job JSON) ·
입력 = 처리할 **비디오 주소** · 출력 = **S3 또는 로컬의 지정 위치에 저장하고 저장 경로를 반환**.

```
Job {
  clip_id                            멱등키 (재처리 = 같은 키; 결정적 output prefix의 근거)
  source_uri                         비디오 주소 — s3://… | file://… (원본 ~1주 → provenance 지문)
  output_uri                         결과 저장 위치 — s3://…/prefix | 로컬 dir (생략 = 서버 기본)
  fps                                분석 fps (detect와 일치 필수, 현행 6)
  subject_query: SubjectQuery        C2 — 누구를 대상으로 (생략 = profile의 규칙)
  domain_profile: str                C9 — preset 이름 (현행 암묵값 = "race981")
  products: [str]                    단계 배포 스위치 (생략 = 열린 것 전부) — 아래 참조
}
Result {
  clip_id · ok · failure(스테이지·사유)
  output_prefix                      실제 저장 위치 (= 반환 계약의 핵심)
  outputs: {product → uri…}          열린 제품의 산출물 경로만:
    likeness  → likeness.json        방문-스코프 외형 ID — **스키마 동결 = §C11** (주탑승자만·color_identity 포함)
    portrait  → portrait.json·*.png  쿼리-추출 대표컷 + 뷰 세트
    highlight → highlight.json·*.mp4 세그먼트 기록 + 클립 (7d96185 졸업 — 제품별 산출물)
  provenance.json                    source 지문·처리시각 (audit·멱등성)
}
```

멱등성: 같은 clip_id 재요청 = 같은 output prefix, 완료 산출물은 재계산 없이 경로 반환
(파이프라인 resumability가 이미 이 의미론 — probe 파일 존재 = skip). Kafka 재전송 대비.

**와이어 계약 격상 (2026-07-07 — scan/gen 서버·레포 분리 전망)**: Result가 곧
**매니페스트**(작은 메타 + 큰 아티팩트의 uri 참조)이고 전달은 비동기·큐 — 이 설계
베팅은 이미 C1에 있었다. 분리가 강제하는 추가 규율 3: ①**스키마의 중립 지대** —
p981-contracts 소형 레포(JSON Schema만; R6의 msgspec→json-schema 산출물이 내용물;
gen 레포 실체화 전 임시 홈=docs/api) ②**semver 진화** — 현행 "v1"(additive 무표기)
에서 minor 표기(1.0→1.1: additive, →2.0: 파괴적)로; 소비자는 범위 핀(`>=1.0 <2.0`);
전환 시점=다음 파괴적 변경 또는 contracts 레포 분리 시 ③**매니페스트 보강(additive
후보)** — outputs 항목에 {contract, schema_version, sha256} 동봉(수신 측이 처리
가능 버전인지 선검사 + blob 무결성; provenance의 source 지문과 대칭).

**실행기 (2026-07-03 구현 · CLI 통합 07-06: `serve-http`→`serve`)**: `momentscan server start` = `service.py`(HTTP 어댑터 +
transport-agnostic `JobRunner`) + `eureka.py`(레지스트리 등록/갱신/해지, stdlib) +
stash `result.json`(응답 기록 = 멱등 근거). 운영 = [deploy-alpha.md](deploy-alpha.md).
e2e 검증: 접수 202→완료 245s→재요청 200/6ms 무재계산·outputs=열린 제품만·
mock-Eureka 수명주기 4단·로컬 배송 복사. 미검증 = S3 실계정(AWS 첫 배포 때 스모크).
**HTTP 표면의 정식 명세 = [api/openapi.yaml](api/openapi.yaml)** (회사 공유 산출물;
Eureka와 독립) · 명세⇄서버 일치의 회귀 게이트 = `momentscan verify api`(13항목,
인프로세스+가짜 파이프라인 — run_pipeline만 패치, 접수/큐/egress/배송/멱등은 실코드).

**단계 배포 (user 결정 2026-07-03)**: 세 제품 동시 오픈하지 않는다 — **likeness 확신
→ 1차 배포·알파테스트 → portrait → highlight 순차 오픈**. Result는 *열린* 제품의
산출물만 노출(egress = analyzers.PRODUCTS.egress의 부분집합); 내부 스테이지는 노출과
별개로 돈다(likeness가 portrait 스테이지의 gate_trace `valid`를 소비하듯,
**스테이지 의존 ≠ 제품 노출**). 제품마다 자기 산출물(likeness.json / portrait.json /
highlight.json)을 가진 구조가 이 스위치의 전제.

## 데이터흐름 체인 (가로축) — 7단, `ls`와 1:1 (2026-07-02, user 정식화)

```
Video ─▶ tubelet ─▶ subjectlet ─▶ 복합 신호 ─▶ 해석 ─▶ 판정 ─▶ 3 제품화
(Media)                           (specialist)  (domain)  (gates)
media.py  subjects/   subjects/    extraction/   domains/  gates.py  products/
ingest    tubelets    +crops(픽셀)  +plugins/     pose·emotion  사다리→   likeness
          (튜브 행)    +attribute    specialist45d geometry·    gate_trace portrait
                      (role·증거)                 signals                highlight
```

- **부트스트랩 예외**: detect·landmarks(관측)는 tubelet **앞**에서 돈다 — 구성 자체가 값싼
  관측(임베딩·depth)을 소비. 체인의 "복합 신호"는 subjectlet **위**에서 도는 풍부한 신호
  (전부 크롭트랙 소비; C3 정합 8c251ee로 선언이 아니라 사실이 됨).
- **scene 예외**: DINO scene은 클립-레벨·subject-무관 — subjectlet을 우회하는 유일한
  흐름 (highlight의 맥락 측 입력).
- 렌즈 직교: 이 체인=데이터가 **어떻게 흐르나**(가로) · criterion-source=제품별
  **무엇을 묻나**(세로) · 두-기계 읽기=이 체인의 subjectlet 지점에 그은 가장 굵은 절단선.

## 두-기계 읽기 — 이 경계가 momentscan의 정체성을 가른다 (2026-07-02)

```
관측(입력)          ① Subject Constitutor        subjectlet            ② Subject Analyzer
detect·landmarks →    대상을 세운다 (subjects/)  ── 경계 묶음 ──▶       그 사람을 읽는다
(extraction/,         stitch·attribute·          tube + pixels(crops)   extraction 신호 → gates
 관측 전문분야)        tubelets·crops              + role + 증거          → 3 readings (products/)
```
(detect는 ①의 멤버가 아니라 **관측 입력** — 멤버십은 extraction의 "신호 전문분야" 테스트가 우선.
stitch는 구성 정책이라 subjects/ 소속, 2026-07-02 이동.)

- **subjectlet** = 경계를 건너는 묶음의 이름 (tubelet=튜브 행만; 실제 계약물은
  튜브+크롭트랙+role+증거). ②는 subjectlet의 순수 소비자 — WHO를 재론하지 않는다.
- **고장 이분법**: 출력 이상 → 첫 질문 = "subjectlet이 옳은가(딴 사람·트랙 깨짐·크롭 불량)=①"
  vs "읽기가 옳은가(게이트·랭킹·기준)=②". 인스펙터의 FRAG/stitch/attribution 증거가 ① 담당.
- 유즈케이스 정합: 직캠=①만으로 제품(팬캠) · race981=①+② · LBE=①의 streaming 판.
  향후 서비스 워커 분리 경계 후보도 이 절단면.
- 정체성 문장: *momentscan은 영상에서 사람을 구성하고(constitute), 그 사람을 읽는다(read).*

## C2 — SubjectQuery (0번째 쿼리)

"누구인가"도 기준-매칭이다: 기준의 **출처가 공간을 결정** ([`criterion-source.md`](criterion-source.md)의 선정판).
바인딩 분리 — **규칙은 profile에(도메인당), 쿼리는 Job에(요청당)**.

**앵커≠불변 원칙 (user 정식화, 2026-07-03)**: 전략들은 **앵커(초기 지시)**의 종류일 뿐,
**유지 근거는 항상 정체성**이다 — 위치/사진/좌석은 "그 순간 누구"를 가리키는 손가락이고,
닿는 즉시 임베딩으로 변환돼 소멸한다. 불변의 위계: **위치=순간 정보 → face=방문-불변
(절대-불변 없음** — likeness의 방문-스코프 그대로; 교차-일 참조는 더 약함**)**.
정체성이 일하는 층 3: 쿼리 해석(Job당 1회, 앵커→subject) · 튜브 유지(트래커+stitch 임베딩) ·
튜브 수리(끊긴 조각 임베딩 재연결 — s13/s18 자동병합 후보). 배치에선 point→기존 튜브 직행;
**streaming(LBE)에서 이 순서가 문자 그대로 실행됨**(위치 부트스트랩→임베딩 유지). 이 원칙이
positional 좌석-금기와 정합: sway/가려짐은 유지-단계 문제인데 위치는 유지에 안 쓰임 — 위치의
위험은 지시 순간의 bbox 겹침뿐(margin으로 정직).

```
SubjectQuery { strategy, params }          진입: momentscan run --subject … → job.json(C1 첫 실체화)
  strategy = seat_rule        위치 규칙 · 정책+depth 증거 · 구현됨(subjects/attribute.py, 기본값)
           | reference_face   참조 얼굴 · 생체 임베딩 · **구현됨(subjects/query.py, 2026-07-03)**
           |                    "face:<photo>" → ArcFace cos vs subject 센트로이드 · TAU_REF=0.30
           |                    (측정: 동일인 0.48–0.80[min=s18 — P1-② 감사 판명: 마스크 아니라 블러/저품질 트랙] vs 교차 max 0.166;
           |                     동클립 참조=상한, 교차-일 일반화 미측정) · roles={target: main}만
           |                    · 저마진 노트=미스티치 조각 신호 · 미달 시 valid=False+reason
           |                    (tubelets가 reason 그대로 거부 — 엉뚱한 사람 구성 안 함)
           | positional       위치 쿼리 · 씬 기하 · **설계만(2026-07-03) — 소비자 나타나면 구현**
```
디스패치 홈=`pipeline._attribute`(job.json 읽고 전략 분기); 재쿼리는 `--force` 또는 새 `--out`
(freshness는 소스-변경 추적이지 요청-변경 추적이 아님 — 알려진 갭).

**positional 설계 (구현 보류)**: 위치 쿼리=튜브에 대한 공간 술어 리덕션(모델 불요) — 세 형태:
`point:t,x,y`(Job, 순간 조회=오퍼레이터 클릭·인스펙터 클릭이 자연 UI) · `zone:rect@t0-t1`
(존=profile 장소보정·시간창=Job, subject별 점유율) · 기하 규칙(nearest/largest, profile).
증거 균일 {confidence, margin, valid} → 같은 attribution.json.
**경계(운영 지식 → 코퍼스 정량 확인, 2026-07-03)**: race981 좌석 판정에 위치 신호 **금지**.
코퍼스 앵커 2건 — ①**dual_2=키 큰 보조탑승자**: aux 머리가 main보다 위(cy 0.21 vs 0.49),
공존 프레임 **63%에서 bbox x-구간 겹침**(중심점 중앙값 통계는 이를 숨김 — 측정 함정) ②**dual_1=
키 큰 주탑승자**: aux가 main-존재 프레임의 **63%에서 미검출**(가려짐) + 보일 때만=몸을 내민
순간이라 **가려진 대상의 위치 통계는 비전형 자세에서 표집됨**(위치 사전지식이 가장 필요한 대상
일수록 위치 증거가 가장 왜곡). → 좌석=depth vote 유지. zone은 **고정 설비가 분리를 보장하는
장소**(포토부스 레인·스테이션)로 제한; point는 순간 조회라 무관(겹침=정직한 저마진). 부산물:
x-교차=flip_segments 동종 트랙-스왑 증거 후보 · dual_1=우발적-가림 TODO의 자연 테스트 클립.

- **증거 계약 (전략 무관 균일)**: per-subject `{ confidence, valid, role }` —
  seat_rule은 이미 방출(margin·flip·valid); `valid=False` → likeness 축적 skip
  (poisoned-baseline 규칙). role(main/aux)=target/동반자 의미론; role별 배달 정책은 profile 소관.
- **수렴 불변식**: 모든 전략은 tubelets.parquet(C3)로 수렴 → 하류(추출기·게이트·제품) 무변경.
- 이중 신분: race981에선 첫 수, 직캠에선 선정+크롭트랙 자체가 배달물(팬캠).

## C2.5 — 트래커 교체 이음매 (2026-07-02, TPN 검토의 결론)

**결정: 지금 트래커 작업 없음** — 얼굴검출 기반 tubelet이 현 시나리오에서 문제없이 동작
(fragments는 stitch가 봉합; C3 정합으로 하류 민감성 제거됨). 계약의 요지는 **언제든
상위 트래커로 갈아탈 수 있는 상태의 유지**:

- **스왑 표면**: visualpath 트래커 플러그인(격리 ③단) + `subjects/stitch.py`(상위 트래커가
  자체 identity를 하면 우회 가능). 후보는 **detections 스키마**(per-frame bbox·embedding·
  track/subject id)로 수렴하면 그만 — tubelets(C3) 하류는 무변경.
- **심사 하니스**(주장 말고 측정): fragment/seam 센서스 · stitch 순도/coherence ·
  admit/제품 replay 델타.
- **심사 렌즈** (TPN에서 가져간 유일한 것): *시간 일관성은 사후 연계가 아니라 제안/연계
  시점의 속성* — 후보가 저신뢰/드랍 프레임을 통과해 튜브를 유지하는가 (현대의 값싼 구현
  =ByteTrack식 저신뢰 연계; 무거운 후보=SAM2 전파·쿼리-전파 계열). 튜브 단위 시간 판정
  개념은 이미 사다리에 존재(sustain·rolling_median·persistence).

## C9 — domain profile (빈 슬롯)

두 번째 도메인이 지불할 때 채운다. 예약 필드(현행 값의 홈):
`subject_rule`(좌석 구조) · `phase_model`(boarding/ride 2-means) · `portrait_query`(gates.PORTRAIT_QUERY)
· `expectations`(highlight_lang.EXPECTATIONS) · `knobs`(CLIP_LEN_S·RARITY_WIN_S·CAMERA_FRONTAL_DEG)
· `role_delivery`(main/aux별 배달). 후보 도메인: 어트랙션들·키즈 스포츠·직캠·포토부스·LBE.


## C11 — likeness.json 스키마 v1 (동결 2026-07-07 · P1-③)

**face_recipe 어댑터의 입력 계약**([[memory: likeness-face-recipe-purpose]] — 소비자 =
blendshape 메타데이터 변환 → 3D 캐릭터 개성 주입). 레코드에 `schema:
"momentscan.likeness/v1"` 도장. **버전 규율**: additive 필드 = v1 유지(소비자는 미지
필드 무시), 기존 필드의 의미/형태 변경 = v2 (어댑터와 동시 이행).

**스코프(2026-07-07)**: `riders` = **주탑승자만** (aux는 측정 신뢰 낮음 — P1-② 감사;
highlight만 aux first-class). 스키마 형태는 riders 맵 유지 (다좌석 확장 대비).

| 필드 (rider 내) | 형태 | 소비자 | 필수 |
|---|---|---|---|
| `center` | float[468×3] 정준 좌표 | **recipe 기하-개성** (몰프 계수 사상 원료) | ✔ |
| `n_obs` · `split_half_drift`(+`_raw` 대조군) · `resid_rms` · `evr_top5` | 스칼라/벡터 | 신뢰·재현성 (recipe가 신뢰 가중에 사용 가능) | ✔ |
| `axes` | 이름 붙은 개인 변이축 | recipe 보조 (변이 서술) | ✔ |
| `template` · `neutral` · `blendshapes` | 정준 기하 부속 | recipe 기하 보조 | ✔ |
| `face_id` | {model, n_emb, coherence_mean/p05, **low_confidence**, embedding[512]} | **diffusion 개인화**(InstantID류) — recipe와 별개 경로; (연구) MICA→FLAME β 다리 ⚠비상업. low_confidence(p05<0.5)=저품질 희석 주의 신호(게이트 아님) | ✔ |
| `fashion` | 불리언 레인(mask/hat/eyewear+frac+variable) + `clip` 타입 레인(hood/scarf/…) + **mask_override** | **캐릭터 액세서리** — `mask`=융합 확정치(P1-④ⓐ: 고신뢰 typed covering이 non-mask 지목 시 parse 불리언 기각, 오버라이드는 mask_override에 기록). ⚠headwear 타입 레인은 내려진 후드를 conf 0.9+로도 오인 — 단독 신뢰 금지 | ✔ |
| `color_identity` | {primary/secondary/highlight:{lab,hex,area}, palette_diversity, n_px, n_frames} \| null | **캐릭터 의상 팔레트** (Cat W #86-89) — null=관측부족(정직) · n_frames=신뢰 | ✔(nullable) |
| `samples` | {center_nearest[], pose_bins{frontal/left/right}, **hair**{visible_frac, observable}\|null} | **hair_match 입력**("같은 사람 1~3뷰") — bin 결측=측면 미관측(정직) · hair.observable=false=후드-업 등으로 hair 픽셀 부재(hair_match 건너뜀) | ✔ |
| 레코드 레벨 `separation` | [{tracks, dist, ratio_vs_drift}] | 진단 자(사람-간÷drift) — 소비자 아님 | ✔ |

알려진 정직 신호: color_identity.n_frames 얇음(dual_1 s0=1) · pose_bins 편측 ·
face_id.low_confidence(희석이지 오염 아님 — P1-② 육안) · samples.hair.observable.
P1-④(2026-07-07)에서 additive로 추가된 필드 = face_id.low_confidence ·
fashion.mask_override · samples.hair — v1 유지.

## C12 — momentscan ↔ visualstack 사용 경계 (2026-07-07)

visualstack(= 실시간 비전 에이전트 미들웨어/플랫폼 지향의 substrate 모노레포:
visualbus / visualpath / visualbind)에 대한 momentscan의 **전체 사용 표면**.
이 표 밖의 visualstack 임포트는 계약 위반 — 추가하려면 이 표를 같은 커밋에서 갱신.

### 허용 이음매 (임포트 화이트리스트)

| substrate API | 역할 | momentscan 사용처 |
|---|---|---|
| `visualbus.FileSource` | 원본 미디어 읽기의 표준 경로 | extraction/detect · ingest · subjects/attribute · subjects/tubelets · surface/cards |
| `visualbus.VideoFileSink` | 주석 비디오 싱크 (detect.mp4) | extraction/detect |
| `visualbus.DrawText/DrawBBox/apply_hint` | 프레임 렌더 힌트 | extraction/detect · ingest · surface/cards |
| `visualbus.VisualBus` | 프레임 pub/sub 버스 | extraction/detect (M01 내부에 한정) |
| `visualbus.structured_log` (`setup_logging`/`log_context`) | 구조화 JSON 로깅 — Loki 관측 계약의 기반 | __main__ · daemon · subjects/crops (+ 로깅 쓰는 전 모듈의 간접 기반) |
| `visualbus.control` (`ControlServer`/`call`) | UDS JSON-lines RPC 제어면 | daemon.py(서버) · __main__.py(server 명령 클라이언트) |
| `visualbus.timestamp.ns_to_seconds` | 시간 규약 | ingest · tubelets · cards |
| `visualbus.BBox` *(규약 차용)* | bbox = [x1,y1,x2,y2] 절대 px | stash.py 컬럼 규약 (임포트 아닌 convention) |
| `visualpath.core.Pipeline` | frame-domain 모듈 해석·topo 실행 | extraction/detect (M01 내부에 한정) |
| `visualpath.plugins.face_detect` (`FaceDetect`/`IoUTracker`) | 검출·추적 플러그인 | extraction/detect |
| `visualpath.plugins.depth.DepthEstimator` | depth 플러그인 (optional, ImportError→degrade) | subjects/attribute |

### 경계 규칙

1. **공개 API만** — visualstack 내부(밑줄 모듈) 임포트 금지.
2. **frame-domain에 한정** — visualpath Pipeline/VisualBus는 M01(과 M03 플러그인)
   안에서만. artifact-domain(M04~M12·제품)은 momentscan 자체 선언(analyzers.py)
   유지 — 집행 이원화는 의도된 결정 (refactor-exec-plan §6c).
3. **역류 금지 = 지식 방향의 규칙** (2026-07-07 정정 — user: 포트-어댑터 역전) —
   substrate가 도메인을 임포트하지 않는다는 뜻이지, 도메인 모듈의 **부착 금지가
   아니다**. 도메인 분석기/제품은 substrate가 정의한 포트(Module 등)를 구현한
   어댑터로 꽂히고 뺄 수 있어야 한다 — FaceDetect가 이미 그 모델. 방향은 항상
   도메인→포트(단방향).
4. **졸업 경로** — momentscan에서 범용성이 검증되고 정의가 언 조각은 visualstack으로
   졸업 후보 (consolidation 원칙: "정의 얼면 졸업").
5. enforcement = refactor-exec-plan **R15**(임포트 스캔 테스트가 이 표와 대조).

### visualstack 측 되먹임 (실소비자 하중 보고 — 별도 레포 작업)

momentscan이 검증한 하중-표면 = 안정화 1순위 API: **FileSource · structured_log ·
control.ControlServer · BBox convention**. 실시간 비전 에이전트 플랫폼 비전에서
이들이 코어 계약 후보 — semver·`__all__` 공개면 선언·deprecation 정책이 다음 수.

> ⚠C11 표기 정정(2026-07-20, r6 실측): center = **478×3**(iris 포함 MediaPipe 토폴로지) — 기존 표의 468×3은 오기. LikenessV1(infra/contracts.py)은 길이 미고정 list로 서술(토폴로지 변동 = 고비용 재결정 지점, change-forecast ③).

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
| C3 | 대상 구성 → 추출기 | tubelets 경계: *추출기는 tubelets만 읽는다, raw detections 금지* | `subjects/__init__` · `stash.TUBELET_COLUMNS` | `momentscan check` |
| C4 | 스테이지 ↔ 스테이지 | stash 아티팩트 (per-artifact 컬럼맵·dtype 캐스트·`_validate`) | `stash.py` | write-시 validate |
| C5 | 게이트 → 소비자 | gate_trace (사다리 전 verdict + REASONS 어휘) | `gates.py trace_rows/REASONS` | import-시 assert + check |
| C6 | 특징 추출 → 제품 | registry FIELDS (46-dim 계약) + FeatureSource 포트 | specialist45d `registry.py` · `ports.py` | — |
| C7 | 좌표계 | 공간·투영·invariant | [`coordinate-conventions.md`](coordinate-conventions.md) · `geometry.CANONICAL_FRAME` | det=+1 assert · `momentscan frame` |
| C8 | 제품 → 배달물 | egress (Result에 실리는 산출물 부분집합) | `analyzers.Product.egress` · `momentscan cascade` | check |
| C9 | 도메인 지식 ↔ 코어 | **domain profile (preset)** — 빈 슬롯 | 미정 (두 번째 도메인이 지불) | — |
| C10 | 저장 서술 | 스테이지 분리·stash 레이아웃 | [`data-contract.md`](data-contract.md) ⚠stale(ports.py 개명 미반영) | — |

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
    likeness  → likeness.json        방문-스코프 외형 ID (riders[].{분포·face_id·fashion})
    portrait  → portrait.json·*.png  쿼리-추출 대표컷 + 뷰 세트
    highlight → highlight.json·*.mp4 세그먼트 기록 + 클립 (7d96185 졸업 — 제품별 산출물)
  provenance.json                    source 지문·처리시각 (audit·멱등성)
}
```

멱등성: 같은 clip_id 재요청 = 같은 output prefix, 완료 산출물은 재계산 없이 경로 반환
(파이프라인 resumability가 이미 이 의미론 — probe 파일 존재 = skip). Kafka 재전송 대비.

**실행기 (2026-07-03 구현)**: `momentscan serve-http` = `service.py`(HTTP 어댑터 +
transport-agnostic `JobRunner`) + `eureka.py`(레지스트리 등록/갱신/해지, stdlib) +
stash `result.json`(응답 기록 = 멱등 근거). 운영 = [deploy-alpha.md](deploy-alpha.md).
e2e 검증: 접수 202→완료 245s→재요청 200/6ms 무재계산·outputs=열린 제품만·
mock-Eureka 수명주기 4단·로컬 배송 복사. 미검증 = S3 실계정(AWS 첫 배포 때 스모크).
**HTTP 표면의 정식 명세 = [api/openapi.yaml](api/openapi.yaml)** (회사 공유 산출물;
Eureka와 독립) · 명세⇄서버 일치의 회귀 게이트 = `momentscan api-check`(13항목,
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
           |                    (측정: 동일인 0.48–0.80[min=마스크 착용자] vs 교차 max 0.166;
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

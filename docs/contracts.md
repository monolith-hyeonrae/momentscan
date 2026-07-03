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

## C1 — Job/Result (초안 v0)

서비스 연동(S3 in/out · 2000 vids/day)과 재사용 설계가 공유하는 외곽 계약.

```
Job {
  clip_id                            멱등키 (재처리 = 같은 키)
  source_uri                         S3/파일 (원본 ~1주 보장 → provenance에 지문)
  fps                                분석 fps (detect와 일치 필수, 현행 6)
  subject_query: SubjectQuery        C2 — 누구를 대상으로 (생략 = profile의 규칙)
  domain_profile: str                C9 — preset 이름 (현행 암묵값 = "race981")
}
Result {
  clip_id · ok · failure(스테이지·사유)
  likeness.json                      방문-스코프 외형 ID (riders[].{분포·face_id·fashion})
  portraits/*.png + portrait.json    쿼리-추출 대표컷 + 뷰 세트
  highlights/*.mp4 (+ candidates)    세그먼트 클립  ⚠highlight.json 분리 예정
  provenance.json                    source 지문·처리시각 (audit·멱등성)
}
```

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

```
SubjectQuery { strategy, params }
  strategy = seat_rule        위치 규칙 · 정책+depth 증거 · 구현됨(subjects/attribute.py)
           | reference_face   참조 얼굴 · 생체 임베딩 · 기계 있음(ArcFace·stitch) 미배선
           | positional       위치 쿼리 · 씬 기하 · 미구현
           | all              전원 (현행 암묵 기본)
```

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

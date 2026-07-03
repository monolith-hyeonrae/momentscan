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

## C9 — domain profile (빈 슬롯)

두 번째 도메인이 지불할 때 채운다. 예약 필드(현행 값의 홈):
`subject_rule`(좌석 구조) · `phase_model`(boarding/ride 2-means) · `portrait_query`(gates.PORTRAIT_QUERY)
· `expectations`(highlight_lang.EXPECTATIONS) · `knobs`(CLIP_LEN_S·RARITY_WIN_S·CAMERA_FRONTAL_DEG)
· `role_delivery`(main/aux별 배달). 후보 도메인: 어트랙션들·키즈 스포츠·직캠·포토부스·LBE.

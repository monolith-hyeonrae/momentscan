# ID Registry — 분석기·게이트·제품 식별자

face-recipe의 축 ID(G01/H01/W86…)와 같은 원리를 momentscan의 구조물에 적용:
전체를 개발하다가 세부 연구가 필요할 때 **한 토큰으로 지칭**하기 위한 불변
식별자 (user 제안 2026-07-07).

**규율 (capnp field-id / openpilot 교훈과 동일):**
- ID는 **불변** — 파일명·함수명이 개명돼도 ID는 따라가지 않는다.
- 폐기된 ID는 **재사용 금지** (폐기 표기 후 결번 유지).
- 새 항목은 끝 번호에 추가. 카테고리 이동 금지.
- 네임스페이스: `M`=측정 스테이지, `V`=validity 게이트, `P`=제품,
  `C`=계약(contracts.md 기존 번호 그대로). face-recipe 축(G/C/H/A/S/W)과는
  문서 맥락이 달라 충돌 없음. ⚠주의: 기존 문서의 "P1-①~⑥"은 **Phase 1**
  표기 — 제품 P1(likeness)과 대상이 같아 실질 혼동은 낮으나, 앞으로 단계는
  "Phase N", 제품은 "P N"으로 구분해 쓴다.

## P — 제품 (단계 배포 순서와 일치)

| ID | 이름 | 산출물 | 상태 |
|---|---|---|---|
| P1 | likeness | likeness.json (C11 동결) | 알파 오픈 (Phase 1) |
| P2 | portrait | portraits/portrait.json | 내부 (Phase 2) |
| P3 | highlight | highlight.json | 내부 (Phase 3) |

## M — 측정 스테이지 (파이프라인 의존 순)

| ID | 스테이지 | 산출물 | 역할 |
|---|---|---|---|
| M01 | detect | detections.parquet · landmarks.parquet | 소스→검출/랜드마크 기판 |
| M02 | stitch | (detections 내 subject_id) | 트랙 조각 병합 (tier-1 코사인 / tier-2 상대귀속) |
| M03 | attribute | attribution.json | rider role (main/aux, depth vote) |
| M04 | tubelets | tubelets.parquet | subject 단위 시공간 튜브 |
| M05 | scene | scene.parquet | DINO CLS 장면 임베딩 |
| M06 | features | features/*.parquet | 46dim 레지스트리 (capnp식 field-id 보유) |
| M07 | crops | crops/manifest.json + s*.mp4 | 깨끗 크롭 트랙 영속화 (retention 대비) |
| M08 | parse | parse.parquet | SegFormer presence/skin 신호 (cheap) |
| M09 | fashion | fashion.json | FashionCLIP 타입 레인 + face-parsing (color_identity·hair) |
| M10 | headpose6d | headpose.parquet | 6D 헤드포즈 (v1은 MediaPipe 우선) |
| M11 | emotion | emotion.json | em_*/AU/duchenne/clip |
| M12 | select | select.json · candidates.jsonl | 공유 채점 기판 (frame_scores — 제품 아님) |

## V — validity 게이트 (gates.py, gate_trace.parquet)

| ID | 게이트 | 원리 |
|---|---|---|
| V01 | exposure | ISO29794-5 휘도히스토그램 엔트로피 (tone-invariant) |
| V02 | blur | 0.5×median floor + smear |
| V03 | pose | 3-way quantizer (MP⊕6D, guarded-promote) |
| V04 | identity | nearest-subject 상대귀속 (cos_self−cos_other) |
| V05 | face_present | identity 탈뭉침 때 분리된 존재 게이트 |

## C — 계약 (contracts.md 번호 그대로; 대표만 발췌)

C1 Job/Result (서비스) · C9 domain preset (자리) · C11 likeness.json v1 (P1 입력 계약).

## 경계 밖 (ID 미부여, 필요 시 확장)

service.py/eureka.py(실행기), stash/telemetry(인프라), 인스펙터/리포트(표면),
../appearance-engine(recipe — 자체 축 ID 체계 보유), ../hair(hair_match).

Enforcement 후보(미착수): `verify registry`가 이 표와 코드 레지스트리의
일치·ID 유일성을 체크. 지금은 문서가 정본.

## 연구 배정 경계로서의 ID (2026-07-07 — user 질문에 대한 판정)

**원칙**: ID가 개발자 1인에게 위임 가능한 연구 경계가 되는 조건 3:
1. **입출력이 계약** — consumes/produces가 stash 스키마(C4)로 고정. 연구자의 세계
   = 내 입력 아티팩트, 내 출력 아티팩트, 내 판정기. 내부는 전권.
2. **자기 판정기** — ID별 회귀 그물(특성화 테스트·replay·eval)이 있어야 "바꾸고
   기도"가 아니라 "바꾸고 측정"이 됨. (refactor-exec-plan R2가 전 ID 공통 전제)
3. **자유/동결의 명시** — 바꿔도 되는 것(내부 알고리즘·모델 선택) vs 동결(아티팩트
   스키마·C7 좌표·"게이트는 validity만" 같은 원칙)을 배정서에 적시.

**현재 등급**:
| 등급 | ID | 비고 |
|---|---|---|
| **즉시 배정 가능** | M05 scene · M08 parse · M09 fashion · M10 headpose · M11 emotion · V01 exposure · V02 blur · V03 pose · P1 likeness | 입출력 계약+판정 자료(판정 카드·감사·C11) 완비. 각자 미결 질문도 문서화돼 있음(예: M09 두-레인 융합 τ·V01 darkness-blind·P1 캘리브레이션) |
| **조건부** | M02 stitch+V04 identity(상대귀속 문법 공유 → **한 사람에게 묶어 배정**) · M12 select(P2/P3 공유 기판 → 두 제품 요구 조정 책임 명시) · P2/P3(경계는 성립하나 taste 라벨 축적이 선행) | 얽힘을 배정서에 명시하면 가능 |
| **배정 보류** | M01 detect·M04 tubelets(visualstack R16/R17 이관 예정 — 지금 배정하면 이관과 충돌) · M03 attribute(role 결정=도메인 정책과 얽힘) | 이관/정책 확정 후 |
| **배정 단위 아님** | C-계약 전부 | 계약은 소유물이 아니라 심판 — 변경은 양쪽 합의 |

**배정 메커니즘**: ID별 1장 연구 브리프 = 입출력(analyzers 선언에서)+판정 명령+
자유/동결 목록+미결 질문(메모리·plan에서 수확). visualstack A안(R16 isolation)이
실현되면 모듈별 환경 격리까지 얹혀 — 연구자마다 자기 의존(torch 버전 등)을 가질
수 있음 = "인프라 모르는 ML/CV 전문가" 채용 스토리의 실체.

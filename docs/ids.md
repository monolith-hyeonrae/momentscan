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

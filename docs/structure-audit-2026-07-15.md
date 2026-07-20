# momentscan 구조 재편 종합 평가서 (2026-07-15, main 1488385)

경로 약어: `SRC` = `/home/hyeonrae/repo/p981/momentscan/apps/momentscan/src/momentscan`. 핵심 앵커 3곳(pipeline.py:155 assert, analyzers.py:104-110 likeness 선언, verify/freshness.py:28-95)은 본 평가서 작성 시 직접 재확인함.

> 생성: 2026-07-15 구조 점검 워크플로(momentscan-structure-audit, 5렌즈 병렬 실측
> + 종합 — 렌즈 원문은 세션 journal). 발주 맥락: user "파일 구조가 마음에 안들어.
> 리팩토링 진행후 likeness 완성 작업 진행" — 본 문서가 그 점검의 정본.
> ⚠표의 트랙 1(dispatch-shim)은 본 문서 생성 직전 이미 착지됨(900c134).

---

## 1) 진단 — 측정된 아픈 점

**D1. freshness의 무증상 실패 모드 = 안전망 자체의 구멍 (재배치의 최대 지뢰이자 현존 결함)**
- 근거: `SRC/verify/freshness.py:41-55` STAGE_MODULE 13개 dotted-path 문자열 → `_origin()`(:82-95)이 경로 미존재 시 None → `p.exists()` False → source_mtime 0.0 → **is_stale 항상 False**. `SRC/pipeline.py:155-157`의 import-time assert는 직접 확인 결과 **키셋만** 비교(`set(freshness.STAGE_MODULE) == set(RUNNERS)`) — 경로 문자열의 실존은 검사하지 않음.
- 추가로 detect/landmarks는 `UPSTREAM_OF_RUNNER`(pipeline.py:102)라 STAGE_MODULE 밖 = **선언된 freshness 사각지대**. L1(freshness 사고 3회) 이력이 있는 시스템에서, 어떤 물리 이동이든 이 지뢰를 먼저 제거하지 않으면 "이동 성공처럼 보이는데 freshness가 조용히 실명"하는 실패가 가능하다.

**D2. likeness 신선도가 portrait 실행에 볼모 (L9, 선언에 자백됨)**
- 근거: `SRC/analyzers.py:107-110` 원문 — *"a gates.py change re-runs portrait but NOT likeness — … for now re-run engines together"*. gate_trace 생산이 `products/portrait.py:31`의 `gates.evaluate` 호출에 묶여 있고(렌즈2 #6), ②GATE 층은 카탈로그에 kind 자체가 없다.
- 최종 목표가 likeness 완성인데, 게이트 정책을 한 줄 고칠 때마다 "portrait 재실행 + likeness는 수동 재실행 기억"이라는 사람-의존 절차가 낀다. R10(gates 스테이지 독립)이 정확한 처방으로 이미 계획돼 있음(refactor-exec-plan.md:235-248).

**D3. 제품 closure 부재 — likeness 반복 루프가 13스테이지 전량 비용 (L10)**
- 근거: refactor-exec-plan.md:232 (products=[likeness]여도 전량 실행), 원장 ⑥ⓒ 알파 처리량 요구 43s/clip vs ~4min 콜드런(refactor-plan.md:239-240). likeness 트랙은 "수정→재실행→카드 육안"의 반복인데 매 사이클에 GPU 전량 비용이 붙는다. R11이 처방이고, 선언 DAG(`analyzers.depends`)가 이미 있어 closure 파생은 기계적이다.

**D4. landmarks = 유령 스테이지, 그런데 likeness의 핵심 입력**
- 근거: 카탈로그는 독립 stage 선언(analyzers.py:50), 물리 `landmarks.py` 부재, `landmarks.parquet`는 features 백엔드가 씀(`plugins/features-specialist45d/.../extractor.py:169`), freshness 사각(D1과 결합). C11의 `center`(468×3)가 landmarks 정준화 산물이므로, **likeness의 1차 원료 생산자가 트리에서 불가시 + stale 감지 불가**라는 이중 결함이다(렌즈2 #1·#2).

**D5. products/select.py — 제품 아닌 공유 기판이 제품 디렉토리에 살며 in-degree 6**
- 근거: ARCHITECTURE.md:76-77 자인("select.py는 제품이 아니라 공유 채점 기판"), 소비자 6곳(highlight:39, highlight_lang:168, verify/evalharness:333, surface/cards:499·923, surface/inspector:480, `__main__`), 그리고 PRODUCTS 선언에서 likeness의 emitted_by=(likeness, **select**)(analyzers.py:186). "ls products/가 정직한가" 테스트에 걸리는 유일 항목이자, 제품→제품 코드 의존(highlight→select)의 축. 단, 물리 이동 비용(소비자 6곳+STAGE_MODULE)이 커서 "지금 옮길 가치"는 별도 판단 필요.

**D6. 개명·재편 드리프트 — 문서/도크스트링이 거짓말하는 지점 누적**
- 근거: `products/likeness.py:1` docstring `"""appearance —`(폐기명), `verify/freshness.py:39` 주석 "likeness→appearance"(실제 맵은 :52에서 identity — 방금 재확인), `analyzers.py:194` "appearance.py=distribution reading"(미존재 파일), `domains/signals.py:1-2` 죽은 viz.py 참조, appearance-engine `adapters/momentscan.py:18-20` "does not emit yet"(실제로는 방출 중 = 원장 ④). 개별로는 경미하나 D4와 합쳐지면 "선언·주석을 믿을 수 있는가"라는 시스템의 핵심 자산(선언=데이터 원칙)을 침식한다.

비진단 메모(측정됐으나 지금 아프지 않음): transport 4파일 1,015 LOC의 무층 평면(렌즈1)은 ls 정직성 결함이 맞지만, 전원 visualstack 단계3 졸업 예정 모듈이라 §3에서 "옮기지 않을 이유"로 처리한다. cards.py 1124 LOC·`__main__.py` 761 LOC 비대도 실측이나 likeness 경로와 무관해 원장 기록 대상.

---

## 2) 재구조화 옵션

### 옵션 A — 선언-미러 물리 재배치 (대규모)
- 이동 목록: service/company/eureka/daemon → `serve/` 신설, gates.py → `gates/`, products/select.py → 기판 홈, ingest.py → extraction/, stash/ports/media/telemetry → `io/` 류, cards.py 6렌더러 분할, `_inspector_html.py` 자산화. 약 15+파일.
- 지뢰(렌즈5 체크리스트 전면 발동): STAGE_MODULE 13문자열(무증상 실명), `freshness.py:35` INFRA `parts[1]` 매칭(stash 이동 시 **전 산출물 상시-stale 폭주**), `__main__.py` lazy ~30곳(실행 시점 폭발), tests 4파일 + `test_company_shim.py:148` sys.modules 문자열, plugins 2패키지(stash/ports 소비), pyproject entry point, docs 상대링크·줄번호 인용 다수.
- 예상 diff: 파일 이동 15+, 경로 문자열 갱신 60~100라인, 문서 갱신 8+파일.
- 리스크: **높음**. 안전망 평가 — pytest 31은 `__main__` 서브커맨드를 test_verify_wrappers 23줄로만 스치고, replay는 산출물 byte-drift 검사라 "실행이 안 되는" 회귀와 "freshness 실명" 회귀를 못 잡는다. 결정적으로 pipeline/freshness/stash/service/eureka/daemon 전부 visualstack 단계1~3 졸업 예정 → **이중 이동**, visualstack-redesign.md:24-33·R12 각주("물리 재배치는 이 계획에서 제외")와 정면 충돌.
- 판정: 안전망 불충분 + 계획 충돌. 기각.

### 옵션 B — 선언 정합 + 지뢰 제거 + 실행그래프 수리 (물리 이동 0~1파일)
- 작업 목록:
  1. **assert 확장** — pipeline.py:155를 키셋 비교에서 `freshness._origin()` 실존 검사로 확장(렌즈5 소견 ②). D1의 무증상 모드를 loud-at-import로 전환. ~10라인.
  2. **R12 tier 선언** — analyzers.py에 `tier` 필드 + registry 체크 + map/report 그룹 렌더 + manifest.json. D5의 select는 이동 없이 `tier:"substrate"`로 지위만 정직화. 위험 없음(선언+렌더), 물리 재배치의 지도가 됨(R12 각주 그대로).
  3. **R10 gates 스테이지 독립** — portrait.py의 evaluate+write_gate_trace를 `"gates"` 스테이지로 추출, portrait은 read 전환. 가드=gate_trace **byte-identical**. D2 해소. STAGE_MODULE에 "gates" 항목 추가(assert가 강제).
  4. **R11 --product closure** — 선언 DAG에서 closure(p) 파생, `run --product likeness`, service Job.products 전달. D3 해소.
  5. **landmarks 정직화(D4 최소수리)** — analyzers.py:50 note에 실제 생산자(specialist45d extractor.py write_landmarks) 경로 명시 + freshness 사각을 UPSTREAM 주석에 자백 기록. 물리 landmarks.py 신설은 R14/visualstack 격리사다리③과 얽히므로 이번 범위 밖.
  6. **드리프트 청소(D6)** — appearance 잔재 4곳 + signals.py 죽은 참조 + adapters docstring. 주석-only ~20라인.
  7. (병행, 코드 무변경) **R8 임계값 인벤토리** — likeness 트랙 ⑦의 C9 preset 자리 지도.
- 지뢰: 3번이 STAGE_MODULE·RUNNERS 1항목 추가(assert가 커버), 4번이 service.py를 만짐(dispatch-shim 착지 후 순서로 회피). 나머지 사실상 0.
- 예상 diff: 합계 400~600라인, 파일 이동 0.
- 안전망 충분성: **충분** — R10은 byte-identical 가드(사실상 replay급), R11은 "closure 실행 산출물 = 전량 실행 산출물" 특성화로 검증 가능, R12는 registry 0 err. 가장 약한 고리(D1)를 1번이 선제 봉쇄.

### 옵션 C — 부분 이동 (select 강등 + transport 디렉토리)
- 이동 목록: products/select.py → 루트 `scoring.py` 또는 기판 디렉토리; service/company/eureka/daemon → `serve/`.
- 지뢰: select 소비자 6곳 + STAGE_MODULE "select" + `__main__` lazy + docs; transport는 test_company_shim(217 LOC, 방금 착지 중인 트랙의 검증물) 임포트 4곳 + apicheck + `service.py:123` `_openapi_path` parents-워크(이동 깊이 민감).
- 예상 diff: 경로 갱신 40~60라인 + 문서.
- 리스크: 중간. 그러나 **얻는 것이 ls 정직성뿐, likeness 완성 기여 0**. transport 4파일은 단계3 졸업 예정이라 이중 이동이고, select의 진짜 홈은 R16/R17 이후 ArtifactNode 재편 또는 visualstash 시점에 자연 결정된다. dispatch-shim이 방금 만진 파일들을 곧바로 다시 흔드는 시퀀싱 악수이기도 함.
- 판정: 보류(기각에 가까움).

---

## 3) 권장안: 옵션 B

이유:
1. **목적 정합** — 최종 목표는 리팩토링이 아니라 likeness 완성 작업의 용이화다. B의 R10/R11은 likeness 반복 루프의 두 실측 비용(D2 신선도 볼모, D3 전량 실행)을 직접 제거한다. A/C는 likeness에 기여하는 항목이 하나도 없다.
2. **기존 결정과 정합** — R12 각주("tier=선언만 지금, 물리 이동=별도 결정")와 visualstack-redesign.md의 처방("물리 이동 대신 선언(tier)+포트(ArtifactNode)로 논리 경계 먼저") 그대로. "어떤 층도 소비자보다 먼저 짓지 않는다" 원칙과도 일치.
3. **안전망 현실** — 현 안전망(pytest 31 + replay byte-drift + api 19 + registry)은 산출물 회귀에 강하고 **경로-문자열 회귀에 약하다**. 대규모 이동의 지배적 실패 모드(freshness 무증상 실명, lazy import 실행 시점 폭발)가 정확히 안전망의 사각이다. B는 그 사각을 좁히는 작업(assert 확장)을 포함하되 사각을 밟지 않는다.

**visualstack 졸업 예정 모듈 처리 방침 — "동결-in-place, 논리 경계만":**
- `pipeline.py`/`freshness.py`(→단계1 visualpath ArtifactNode), `stash.py` 기계+산출물 레이아웃(→단계2 visualstash), `service.py`/`eureka.py`/`daemon.py`/관측자산(→단계3 visualserve/scope), 미디어 경로(→단계4 visualbase)는 **물리 이동 금지**. 지금 하는 것은 tier 선언(visualstash가 수용 예정)과 R10/R11(R16/R17에서 resolver 질의로 자연 승계 — refactor-exec-plan.md:375-379가 명시)뿐이다. R16/R17 착수는 visualstack 소유자 결정 사항으로 이 트랙 범위 밖.
- C1/C11/C12 계약면: B의 어느 항목도 계약 형태를 건드리지 않음. R11의 Job.products는 C1에 additive(무버전 허용). `"momentscan.result/v1"`(service.py:45)·`"momentscan.likeness/v1"`(likeness.py:460)은 모듈 경로가 아닌 동결 스키마 ID — 어떤 rename에도 불가침.

---

## 4) 시퀀싱

**dispatch-shim → 구조 → likeness 순서는 옳다.** 단 구조 트랙은 리버트 단위를 위해 둘로 쪼갠다.

| 순서 | 트랙 | 내용 | 완료 기준 |
|---|---|---|---|
| 1 | track/dispatch-shim (진행 중) | 착지 우선. R11이 service.py(Job.products)를 만지므로 반드시 선행 | verify+특성화 green, test_company_shim 217 green, api-check 19, C1 무변(additive만) |
| 2 | track/struct-s1 (저위험 선언) | assert 확장(D1) + R12 tier + landmarks note 정직화(D4) + 드리프트 청소(D6) + R8 인벤토리(코드 무변경) | registry 0 err(전 산출물 tier) + report 4그룹 + manifest.json 존재 + pytest 31 green + `docs/preset-inventory.md` ≥25행 |
| 3 | track/struct-s2 (실행그래프 수리) | R10 gates 독립 → R11 --product closure. gate_trace 재계산이 걸리므로 **branch-scoped `--out`** 사용(stash는 브랜치를 안 탐) | gate_trace **byte-identical** + `run --product likeness` 산출물이 전량-실행과 특성화 동일 + replay 0드리프트 + service Job.products 경유 apicheck green |
| 4 | track/likeness-* | §5 순서 | 항목별(아래) |

근거: (a) s1은 위험 0(선언+렌더+주석)이라 빠른 머지·독립 리버트, (b) s2는 R10→R11 의존 사슬이라 한 트랙이 자연스럽고 byte-identical 가드가 완료 기준을 기계화, (c) s2가 likeness 트랙의 반복 비용을 낮추므로 likeness보다 먼저가 이득(4분 콜드런 → likeness closure만), (d) R8은 likeness ⑦의 C9 preset 착지 지도라 likeness 전에 있어야 한다.

---

## 5) likeness 완성 트랙 작업 순서

배열 원리: **코드-단독으로 프리뷰 사슬과 입력 품질을 먼저 복구·개선 → user-동행 판정을 한 세션에 묶는다**(판정 입력을 바꾸는 ⑦을 판정 앞에 두어 재판정 이중작업 방지; likeness 확신 단독 확정 금지 원칙 준수).

> **⚠ 방향 반전 (2026-07-20, user 결정 · track lk-recipe)**: 아래 1·2의 "appearance-engine에
> 정식 착지"·"adapters/momentscan.py" 방향은 **뒤집혔다** — 프리뷰=momentscan 소관,
> appearance-engine=배울 것 소진 시 삭제(absorption-plan). face_recipe 어댑터는
> momentscan `products/recipe.py` 스테이지 + `perception/readings/face_axes.py` 공식으로
> **흡수 완료**(track lk-recipe). 브리지(②)는 MPFB 재도입 없이 bpy+디자이너 blend 로
> lk-preview 에서 재구성(track lk-preview). 원장 ④ 소비 확장은 recipe 스테이지에서
> additive 패스스루로 착지. 아래 문장은 이력 보존을 위해 남긴다.

**Phase L-A: 코드-단독 (순차, 일부 병렬 가능)**
1. **② 브리지 재구성** — mpfb_recipe.py가 scratchpad 소실로 디스크에 없음(전역 탐색 0건). 잔존 몽타주(output/l2/preview_mpfb_*.png)를 참조해 appearance-engine에 정식 착지. **최우선인 이유: ①③⑤의 판정 수단(recipe→Blender 프리뷰)이 전부 이 사슬에 의존.**
2. **④ 어댑터 unfilled 채우기** — adapters/momentscan.py가 center/neutral/blendshapes만 읽음; momentscan이 이미 방출 중인 color_identity·fashion·samples.hair를 소비(C11 additive 소비 확장, 계약 무변). stale docstring(:18-20) 동시 수정. 프리뷰가 풍부해져 user 세션의 판정 가치 상승.
3. **⑦ pre-ride phase 조건화** — likeness.py:250-259 pose_bins·fashion.py:228-279 샘플링에 tubelets의 scene_phase 조건화. 정책 상수는 C9 preset 자리(R8 인벤토리가 지도). **①③⑤ 판정 입력(hair/pose_bins)을 바꾸므로 user 세션 전에 착지** — 특히 ⑤ test_12 hair(빨간 등받이 교란 의심)는 pre-ride 프레임에서 양상이 달라질 수 있어 조사 전에 반영해야 조사가 유효하다.
4. **① 캘리브레이션 구현부** — registry 재캘리 vs 어댑터 보정(_PSEUDO_SCALE=200 분포 어긋남) 양안 구현 + A/B 몽타주 생성. 확정은 하지 않음.
5. **⑥ⓐ S3 실계정 스모크 + ⑥ⓒ 처리량 관측** — ops 단독, 1~4와 병렬 가능. ⓒ는 struct-s2(R11) 착지 후 측정해야 의미 있음(likeness closure 실행이 43s/clip 목표의 주 지렛대).

**Phase L-B: user-동행 세션 (몽타주·프리뷰 일괄 준비 후 한 번에)**
6. **① 판정** — 4키 포화(Brow_Thickness·Mouth_Size·Mouse_Corner·Brow_Slant)의 재캘리/보정 선택, 프리뷰 육안. 단독 확정 금지 원칙.
7. **③ gain 판정** — ×2.2 근방, ②로 재생성한 A/B 몽타주(잔존 preview_recipe_gain_ab.png 참조). 미학·개성 판단 = user 몫.
8. **⑤ test_12 hair 오검출 동행 조사** — 원장 원문 + memory 원칙(likeness-confidence-together)이 동행을 명시. ⑦ 반영 후 데이터로.
- 세션 형식: show-don't-tell 원칙에 따라 판정 근거 분해 카드/몽타주로 준비.

**Phase L-C: 외부 의존·협의 (도착 시점 비동기)**
9. **⑥ⓑ 회사 Eureka 실서버 등록** — 회사 질문 5 회신 대기(블록). company.py:19,133 resultPath 임시매핑도 같은 회신에 묶임.
10. **⑥ 알파 피드백 계기 설계** — user 협의, E1(수용집합/의도별 구간 라벨 원형)과 병합. E1 재개 블록(test_3 P2 카드 판정)과 같은 세션으로 묶는 것이 효율적.

**요약 한 줄**: 물리 재배치는 하지 않는다(졸업 예정 모듈=이중 이동, 안전망=경로 회귀에 사각). 대신 assert 확장으로 지뢰를 제거하고, R12(선언)·R10(gate 독립)·R11(product closure)로 likeness 반복 루프의 실측 비용 두 개를 걷어낸 뒤, 브리지 재구성→어댑터→phase 조건화→캘리 순의 코드-단독 작업으로 프리뷰 사슬을 복구하고 user-동행 판정을 한 세션에 몰아 likeness를 닫는다.
---

## 6) 접수 — user 구조 불만 (2026-07-15, 하나씩 수집 중)

**#1 루트 평면 나열 (접수·설계 합의)**: 루트 14파일·3,918 LOC에 다섯 성질
(외부접점 1,015 / 실행기계 611 / 저장 798 / 게이트 537 / 관문 940)이 무경계
나열 — eureka 같은 외부-시스템 접점이 "기능 중 하나"처럼 보임. **판정 갱신**:
소유자 우선순위에 ls 정직성이 명시됨 → 물리 재배치 기각을 철회하고
"루트=경계 패키지만"으로. 목표 트리: `serve/`(service·company·eureka·daemon)
· `engine/`(pipeline·analyzers) · `store/`(stash·ports·media·telemetry) ·
ingest→extraction/ · 루트 잔류=__main__. 이름을 visualstack 졸업석
(visualserve/visualpath/visualstash)과 정렬 = 이중-이동이 아니라 졸업 리허설.
순서: assert 확장 선행 → serve/ tranche(STAGE_MODULE 무관, 최저 지뢰) →
store/·engine/(STAGE_MODULE 13문자열 + INFRA parts[1] 매칭 가드 핀 후).

**#2 domains/ 이름 모호 (접수·개명안)**: 실체=신호 해석 정책 단일 홈
(emotion 융합 valence·geometry 정준 프레임·pose 융합/임계·signals 단위 함수;
멤버십="한 값이 세 제품을 함께 바꾸는가"). 이중 결함 — 이름이 자기 설명을
못 해 독스트링이 해명 + C1 `domain_profile`(어트랙션 도메인, C9)과 의미 충돌
= 오독 유도. **개명 권고: `readings/`**(프로젝트 문법 anchor×reading과 일치;
차선=signals/는 내부 signals.py와 한 겹 더). 지뢰: freshness.py:50·:160 문자열
2곳 + 임포트 ~10곳 — assert 확장 후 tranche 편입.

**#3 공통부/미니도구 검토 (접수·처분 완료 — commons-audit 워크플로 3렌즈)**:
openpilot tools/ 영감(조직-범용 도구 보유 여부). **실측 판정**: ①미니도구
분리 = 공집합 — 레포-간 중복 0(appearance-engine 임포트 0건), 현존 제2소비자는
plugins→stash(visualstash 졸업석)뿐, eureka/company의 확실한-미래 소비자
(momentgen 디스패치)는 미니도구가 아니라 visualserve 졸업 게이트의 조기 트리거.
조직 공구함의 자리 = momentscan 내부가 아니라 visualstack 자체(Rails 비전).
②대신 **레포 내 중복 17군집 실측**(순 −350 LOC): stash JSON/parquet 12+9쌍 →
artifact registry 테이블화 · stash 우회 직접읽기 14곳(S3 포트 스왑 누수) ·
L2/코사인 11곳 재구현 · bbox 크롭 5곳(배율 5종 산개) · parse≡headpose 문자동일
루프 · ImageNet 상수 3중복 · cards 렌더 프리미티브 5중복 · eureka≡company
401 재시도 2벌 · **pipeline.py:187,195 naive 타임스탬프 실버그**. 신설 모듈은
extraction/preprocess.py·surface/canvas.py 2개뿐(소비자 3+ 실존), utils/common
서랍 금지 유지. ③과잉-작업 경계: 2곳-중복은 홈 신설 금지·접힘은 이동 tranche에
혼입 금지(순수 이동 유지)·store 접힘=byte-identical / 수치 접힘=tolerance.
④트랙 편입: naive 타임스탬프 2줄=struct-s1 동승 / track/fold-store(tranche 후)
/ fold-signals·fold-pixel·fold-serve=likeness-후(활성 수술 부위 회피). 이식-가능
재고 9항목=refactor-plan.md 원장에 기록.

**#4 verify/ 역할 혼합 (접수·처분안)**: 실측 = 4성질 동거 — 가드(apicheck 171·
replay 128·doctor 76) / **런타임 기계(freshness 203 — pipeline 매 런 소비,
검증 아님)** / **연구 평가(evalharness 370 — E1 킷인데 짝꿍 label_server는
surface/에 = 두 패키지에 분산)** / 선언 지도 렌더(graph 161). 처분:
freshness→engine/ (접수 #1 물음표 확정) · **evals/ 신설**(evalharness+
label_server 재결합 — E1=1급 연구 자산이 트리에 가시화, E1 재개 직전 시의성)
· graph→engine/ 약한 선호 · verify/ 잔류=가드 3종(이름=내용). CLI 표면 불변.
지뢰: 소비자 ~11곳 전부 평범 임포트, STAGE_MODULE은 freshness가 담는 쪽이라
자기 이동 무해 — assert 확장 후 tranche 편입.

**#5 __main__ 비대·clean-code 규칙 부재 (접수·처분안)**: 해부 = 761 LOC 중
main() 파서 조립 모놀리스 198줄 + 핸들러 23개(대부분 7~30줄로 얇음; 비대는
_cmd_run 64·_cmd_serve 46·_cmd_status 44·_cmd_cascade 42). 진단 — 함수 품질
문제가 아니라 "23핸들러+198줄 조립이 한 파일"의 물리 뭉침; CLI 가족(run/서버/
verify/지도/표면)이 help엔 있는데 파일엔 안 비침(접수 #1 동일 병리). 처분:
**cli/ 패키지 분할** — 가족별 모듈이 자기 subparser 등록+핸들러 소유,
__main__=3줄 재수출(entry point "momentscan.__main__:main" 문자열 불변 = 지뢰
0), main()=조립 뼈대 ~40줄. 이동 tranche 편입(leaf라 지뢰 최소, subprocess
테스트가 CLI명 기반이라 무해). **clean-code 규칙: 성문화 0이 사실**(스타일
문서 없음·ruff 미설치 — R9 미착지). 암묵 하우스 스타일은 강함(모듈 독스트링=
계약·정직한 실패·구조화 로그·선언=단일 권위·stdlib 우선·책임 명명) — 처분:
docs/code-style.md로 관측된 규칙 성문화(도그마 수입 아님) + R9 ruff 착지
(검사만·baseline·신규 위반만) + pytest 래퍼. → struct-s1 동승.

---

## 7) 최종 트랙 계획 (접수 #1~#5 종합 — 2026-07-15 확정)

**track/struct-s1** (선언·가드·성문화 — 물리 이동 0):
①assert 확장(D1: STAGE_MODULE 경로 실존을 import-time에 강제) ②R12 tier 선언
(analyzers tier 필드+registry 체크+map/report tier 그룹+per-clip manifest.json)
③landmarks 정직화(D4 최소) ④D6 드리프트 청소+E2 naive 타임스탬프 ⑤R9 ruff
착지(검사만·baseline)+code-style.md enforcement ⑥R8 임계값 인벤토리.
완료 = registry 0err(전 산출물 tier)·pytest green·tier 그룹 렌더·manifest 존재·
ruff baseline·preset-inventory.md.

**move tranches** (물리 이동 — 지뢰 밀도 순, 각 tranche=순수 이동만):
T1 serve/(service·company·eureka·daemon) → T2 readings/(domains 개명) →
T3 engine/(pipeline·analyzers·freshness[verify→]·graph)+evals/(evalharness+
label_server) → T4 store/(stash·ports·media·telemetry — INFRA parts[1] 가드 핀
선행) → T5 cli/(__main__ 분할)+ingest→extraction/.
각 완료 = pytest·api·registry·replay green + 지뢰 체크리스트 소거.

**struct-s2**: R10 gates 독립(gate_trace byte-identical) → R11 --product closure
(branch-scoped --out). → **track/fold-store**(stash 레지스트리화 — likeness 뒤로
이월 가능) → **likeness 트랙**(L-A 코드단독: ②브리지→④어댑터→⑦phase→①캘리
양안 / L-B user-동행 판정 세션 / L-C 외부 대기) → fold-signals·fold-pixel·
fold-serve(likeness 후).

**T1 serve/ 착지 (2026-07-15)**: service·company·eureka·daemon → `serve/`
(외부 접점 항구, visualserve 졸업석 이름 정렬). 갱신=임포트 5파일(+테스트
mock.patch 문자열), `_openapi_path`=parents 순회라 깊이-불변 확인. **결정:
로거 이름은 구 경로 유지**(momentscan.service 등 — 관측 정체성은 물리 배치와
독립, Loki 라벨 연속성). 검증=pytest 38·api 19·registry 0err·replay 0drift·
라이브 기동/해지 스모크(:18099)·ruff 75 불변.

**T2 readings/ 착지 (2026-07-15)**: domains/ → `readings/` 개명 (접수 #2 —
C1 domain_profile과 의미 충돌 해소, anchor×reading 문법 정렬). freshness 문자열
2곳(emotion 매핑·geometry 외부모델 키)이 정확히 D1 assert의 보호 대상이었고
일괄 갱신, 소비자 11파일. 검증=pytest 38·registry 0err·api 19·replay 0drift·
map frame 스모크.

**T3 engine/·evals/ 착지 (2026-07-15)**: pipeline·analyzers·freshness(verify→)·
graph(verify→) → `engine/` / evalharness→`evals/harness`·label_server(surface→)
→`evals/` (E1 킷 재결합). verify/=가드 3종 잔류(apicheck·replay·doctor,
자기소개 갱신). 함정 1건 실증: 복합 임포트(`from momentscan import analyzers,
gates`)가 일괄 치환에 걸려 gates까지 끌려감 — pytest가 즉시 적발(fail-fast
그물 동작 증명), 2곳 분리 수리. 검증=pytest 38·registry 0err·api 19·replay
0drift·map graph·verify eval.

**T4 store/ 착지 (2026-07-15)**: stash·ports·telemetry → `store/`(visualstash
졸업석). **media는 계획 수정 — extraction/media.py로**(저장이 아니라 픽셀/인코딩
규약, 졸업석=visualbase; store/행이면 INFRA 제외에 휩쓸려 media 수정이 stale을
못 일으키는 의미 변화가 생겼음). freshness INFRA={"stash","telemetry"}→{"store"}
(parts[1] 매칭 지뢰 해소) + 행동 핀(crops 클로저: store 제외·media 포함).
최상위 재수출(momentscan.Tubelet 등)로 plugins 소비 불변, plugins 내부 stash
임포트도 갱신(29파일). 검증=pytest 39·registry 0err·api 19·replay 0drift·
plugin import 스모크.

**T5 cli/ 착지 (2026-07-15, 위임 에이전트 실행)**: __main__ 767→5줄 스텁
(entry point 문자열 불변), cli/ 가족 5모듈(run 100·server 239·verify 121·
maps 174·surfaces 116)+조립 __init__ 67. ingest→extraction/ (소비자 1건).
순수 이동 — 핸들러/파서 로직 무변경, --help 동사 집합·서브그룹·help 문자열
동일(최상위 순서만 가족순 재정렬 — 수용). 검증=pytest 39·api 19·registry
0err·replay 0drift·ruff 75 불변·cascade/graph/status 스모크.

**이동 tranche 전체 완료 (T1~T5)** — 최종 트리: serve/·engine/·store/·
readings/·evals/·cli/·verify/(가드만)·extraction/(+media·ingest)·subjects/·
products/·surface/ + __main__ 스텁. 루트 평면 파일 14→1(스텁). 다음=struct-s2
(R10 gates 독립→R11 --product closure) → likeness 트랙.


**접수 #6~#9 (2026-07-16, 청사진 실행 중 수집)**: #6 engine/→**pipeline/**
(runtime/orchestration 모호 + "engine" 낱말이 제품 엔진(=질문)과 충돌 — 개명
확정, 내부 pipeline.py→runner.py) · #7 analyzers.py→**registry.py**(자기소개·
verify registry 동사와 정합; 내부 혼재는 **(a) 시점**=decl-guards에서 registry
패키지 분할[analyzers/products/tiers + __init__ 교차 assert]) · #8 **선언
키워드화**(위치 인자가 가독성 주범 — kw_only=True로 언어-강제, decl-guards
편입) · #9 **detect.py→subjects/**(대상 확립 사슬=한 연구 경계인데 물리가
한가운데를 갈랐음 — 심사의 extraction⇄subjects 양방향이 그 상처; T6 동승,
단방향 해소). 중앙 등록 유지 확정(자체-등록=레거시 붕괴 원인·import-light
카탈로그 사망; 지역성은 enforcement+분할이 봉사).

**struct-s2 착지 (2026-07-16, 111310e — 6번째)**: R10 gates 독립 스테이지
(byte-identical 증명)+portrait 순수 독자(스키마 +3 additive)+gates→engine/+
R11 --product closure(emitted_by 기반 — select 포함이 선언-정직)+likeness/
select 선언 수리(phantom portrait 간선 제거). 코퍼스 gate_trace 15클립 재생산
(스키마 43컬럼). ruff 75→58 래칫. 노출 축 K·D3 폐쇄.
**접수 #10 (에이전트 발견, 2026-07-20 decl-guards 중)**: features 분석기 선언
artifact='features.parquet' vs 실제 산출 `features/{track}.parquet` 디렉토리 —
선언-실제 불일치(D4 계열). classify는 G3 등재로 커버, **선언 수정은 별도 소형
트랙**(freshness probe·ARTIFACT_TIERS 파생 영향 검토 동반).

**when-home·T7·decl-guards 착지 (2026-07-20)**: fc80717(WHEN 단일홈)·556e89e
(A″: infra/perception/products+evals — user 그림의 시공)·decl-guards 머지
(registry 패키지 분할·kw_only·question/scorer·G2 warn 활성[likeness 노랑=E1
압력]·G3/G4·isort 4결). pytest 41·ruff 57. 잔여: ARCHITECTURE.md 재작성 →
r6-egress → likeness 트랙.

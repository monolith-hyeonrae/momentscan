> 생성: architecture-redesign-panel 워크플로 (독립 설계 3안[보수·질문-우선·껍질-우선] → 교차 심사 2인[중립·연구자-관점] → 종합). 철학 정본 = change-forecast.md, 심사 = architecture-review-2026-07-16.md.
> 상태: user 결정 대기 (§4) — 확정 전 실행 금지.

# 최종 청사진 — 정책·공식의 이주, 계약의 실체화 (2026-07-16)

> 실측 기준: `/home/hyeonrae/repo/p981/momentscan` main 6480c05 · 패키지 루트 = `apps/momentscan/src/momentscan/`. 정본 철학 = `docs/change-forecast.md`(원장 ①~④), 심사 앵커 = `docs/architecture-review-2026-07-16.md`. 코드 무변경 — 이 문서는 설계다.

## 1. 채택 골격과 이유

**골격 = 안A(보수적 최소주의).** 두 심사가 독립적으로 공히 1위 판정(심사1: A 30 > C 28 > B 25 · 심사2: A 31 > B 26 = C 26)이며, 판정 근거가 서로 일치한다 — ③이주 비용(심사1 5점·심사2 5점: "리버트=머지 한 방 크기 유지")과 ④연구 인체공학(심사2 5점: "likeness 지연 0 · 세밀 stale · 수술 부위 1함수"), ⑤졸업 호환·⑦비목표(양 심사 5점: "'이동은 작업이 지불한다'가 원장 ②의 가장 충실한 집행")에서 A가 유일하게 무결점이다. 선언된 우선순위(struct-s2 → likeness)와 유일하게 무마찰이라는 점이 결정적이다.

단, 두 심사가 지목한 A의 결함 3건을 접목으로 보정한다: (i) D축 처방이 반쪽("이름은 주되 소유권을 안 옮김" — 심사1), (ii) R6 무편입(L3 헛점은 현재형인데 likeness 알파가 회사 대면 — 심사2), (iii) 과도기 재바인딩의 만료 기계 부재(심사2 만성결함 ii).

**접목 원장** (전 항목 출처·이유 명기):

| ID | 출처 | 접목 내용 | 이유 (심사 인용) |
|---|---|---|---|
| G1 | 안B | WHEN 명명 함수에 **소유권 선언 독스트링** — "owner = highlight engine; resident in select.py until R16/17; 물리 이전은 energy 재편 트랙이 지불 가능" | 심사1 접목#1: A의 명명 승격은 "미러를 죽이지만 소유권을 안 옮긴다" — 어음 발행으로 D축 종결을 0비용 보정 |
| G2 | 안C | registry warn: `state=="molten" ∧ scorer==""` | 양 심사 공통(심사1 #2·심사2 #1): "답을 다시 쓰기 전에 채점기를 세운다"(원장 ④-①)의 기계화, 비용 ~0 |
| G3 | 안C | **stash 등록 의무 enforcement** — 미등록 산출물 = registry error | 양 심사 공통(심사1 #3·심사2 #2): "무소유 5족째를 막는 유일한 안", R15 계열이라 미니도구 아님 |
| G4 | 안B·C | ARCHITECTURE.md **경로-실존 pytest 가드** (grep 수준) | 양 심사 공통(심사1 #4·심사2 #7): "문서 주소록에도 D1급 가드" — A에만 없던 항목 |
| G5 | 안B | **"함수는 preset을 모른다" = 명문화된 종착 형태** + likeness ⑦이 신설하는 상수는 태어날 때부터 인자 전달(`pose_class(…, bands=preset.camera.bands)`) | 양 심사 공통(심사1 #5·심사2 #5): 재바인딩 패턴 증식을 막는 성장 규칙, A 잔여 리스크 ①(숨은 전역 오독)의 실질 완화 |
| G6 | 안B | Preset 스키마의 **그룹 하위구조**(camera/phase/likeness/portrait/highlight/delivery 블록) | 심사2 #6: C9 예약 필드(contracts.md:188-190)와 1:1 대응, G5 인자-전달 문법과 자연 결합 |
| G7 | 안B | `tests/test_preset.py` — race981 값 **전수 특성화 핀** | 심사1 #8: import-time assert보다 강한 동결 장치, msgspec 없이 성립 |
| G8 | 안C | **AST authority test** — 이주된 상수명의 리터럴 재정의 금지(R15 문법 재사용) | 심사1 #7: "단일홈이라는 주장을 주장이 아니라 검사로" |
| G9 | 안C | **R6 착지 편입** — 단 LikenessV1/ResultV1만, **PresetV1 제외** | 심사2 #3: L3 현재형+알파 회사 대면. PresetV1 제외 = 심사1 ⑤ "씨앗 심긴 이중 이동" 회피 |
| G10 | 안C(형태)+심사1(시점) | **scores.parquet 예약석** — 시점 = energy 재편이 채널을 안정시킨 **직후**(gate_trace 전례의 올바른 재현), 형태 = **렌더러(cards/inspector) 전용, harness 제외** | 두 심사의 충돌을 중재: 심사1 #10(몰튼 위 영속 스키마 금지 — 시점) + 심사2 #4(rescore 루프 보존 — 형태). harness.py:325 실측("one labeling session measures every system version")이 harness의 함수 구독을 영구 확정 |
| G11 | 안B | **대안 순서의 명시적 자백 형식** | 심사1 #9: 우선순위 의존 선택지를 소유자 결정 변수로 노출 — §4가 그 집행 |
| G12 | 안B | eval.py **예약석의 원리 한 줄**(파일 생성 없음) — "E1 신-스키마 채점기의 정본 자리는 E1 재개 트랙이 결정한다" | 심사2 #8: B의 통찰(채점기=껍질의 절반)을 A의 scorer 필드와 모순 없이 보존 |

## 2. 목표 아키텍처 지도

각 경계 = 숨기는 비밀 한 문장 + 인용 축(change-forecast.md ① A~L). **굵게** = 이 청사진의 변경분.

```
momentscan/  (apps/momentscan/src/momentscan/)
├ __main__.py     스텁 (T5 결과, 무변)
├ cli/            비밀: 명령 파싱·프로세스 기동 형태                    축 F
├ serve/          비밀: 회사 연동 방언(transport·resultPath·인증·관측)   축 A·F — 어댑터 내 수술로 흡수
├ engine/         비밀: 실행 기계(순서·신선도·선언⇄실행 정합)            축 G(졸업 예약석)
│  └ gates.py     비밀: 관측-신뢰 판정(사다리·REASONS 폐어휘·trace 스키마) 축 K ← **루트에서 이주** (자기선언 "sibling to analyzers.py"가 비로소 참)
├ store/          비밀: 저장 배치·백엔드(S3 이행 시 수술 부위)           축 J
├ extraction/     비밀: 픽셀→관측의 모델 선택(어댑터 1점)               축 C · media/ingest=visualbase 예약석(축 G, 이중 멤버십 자백만)
├ subjects/       비밀: 관측→사람 구성(트래킹·stitch — 클립-스코프 내재)  축 C·I(승인된 노출 — 은닉 안 함)
├ readings/       비밀: 문제-언어 공식 — **값은 갖지 않는다(값=preset)**  축 C
├ products/       비밀: 세 가치 질문의 "현재의 답"(정의·공식·몰튼)        축 D·H — D는 WHEN 명명 함수+소유권 선언으로 은닉
│  └ select.py    공유 채점 기판 — 지리 무변(M5 이연), WHEN 공식의 물리 거처(소유는 highlight, G1)
├ preset/         비밀: 시설/카메라/기구 의존 값 — **신설** (C9의 물리 실체) 축 B·E
├ surface/        비밀: 렌더 형태(구독자 — 재계산 잔존 2곳은 G10 어음)     — (소비자)
├ evals/          비밀: 채점 방법론(rescore=현재 코드 재계산, 영구)        — (E1)
├ verify/         비밀: 검증 항목·완료 기준                            축 G·L
└ contracts.py    비밀: wire 계약의 형태 검증(C1/C11) — **R6 착지** (G9)   축 L
```

노출 3축의 은닉처: **B → `preset/`** (15파일 산개 → 1홈) · **D → `select.py`의 명명 PUBLIC 함수 + 소유권 선언** (미러 소멸) · **K → `engine/gates.py`** (R10 동승). 샘 2축의 처방: **J → fold-store**(기존 계획+4족 편입) · **L → `contracts.py`**(G9).

## 3. 7문에 대한 확정 답

**Q1. C9 preset의 물리 형태** — **파이썬 모듈 패키지 `momentscan/preset/`, frozen dataclass, 데이터 파일(yaml/toml) 기각.** 기각 근거는 실측이다: freshness가 transitive import 클로저 mtime을 보므로 파이썬 모듈은 값 수정 → 소비 스테이지만 자동 stale(세밀), toml은 클로저 밖이라 `_external_deps` 수동 등록+전체-stale 보수 결합이 강제된다(심사2: "toml이 오늘 사는 것은 0, 파는 것은 레포 최대 무료 자산"; L1/test_3 재발 경로). 스키마 = `Preset(camera=…, phase=…, likeness=…, portrait=…, highlight=…, delivery=…, subject_rule·role_delivery=Optional 예약)` 그룹 구조(G6, C9 예약 필드 1:1). 동결 장치 = import-time assert + `test_preset.py` 값 전수 핀(G7) + AST authority test(G8). msgspec 기각 — R6은 wire 전용, preset은 경계를 안 넘는다(C1이 나르는 것은 `domain_profile` 이름뿐). 로딩 = 안A 경로: Job.domain_profile("race981" 기본) → run_pipeline 인자(additive) → 초입 1회 해석(미지 이름=raise) → job.json 기록 → 소비 러너 명시 kwargs. **과도기**: 기존 상수는 정의부 1줄 재바인딩 허용(T4 재수출 전례), 단 **종착 형태 = "함수는 preset을 모른다"를 명문화**(G5)하고 ⑦이 신설하는 상수는 태어날 때부터 인자 전달. 런타임 스위칭은 두 번째 시설이 지불(C9 원문). 1차 이주 = 안A §1 상수군(CAMERA_FRONTAL_DEG+BIN_EDGE_DEG 짝, `_F_*` 군, FACE_ID_*, ⑦ 신설분) — 60개 일괄 금지, 트랙별 값-불변.

**Q2. WHEN/채점 공식의 집** — **select.py 유지 + `when_from_channels(impact, rarity, scene, valence) → (when, drivers)` 명명 PUBLIC 승격**(rolling_median의 "inspector subscribes to THIS" 전례, select.py:79-83) **+ 소유권 선언 독스트링(G1)**. highlight.py:180-185 미러(3.0 리터럴·max 구조 복제)는 구독으로 소거 — 공식 리터럴은 한 곳만 남는다. **harness rescore는 함수 구독 영구 유지**(방법론 그 자체 — 실측 확정). scores.parquet는 지금 안 만든다 — fold-store에 예약석(G10): 시점=energy 재편 후 채널 안정 직후, 형태=렌더러 전용. select.py 지리 무변(M5, R16/17 자연 결정). 가드: highlight.json **byte-identical** · replay 0드리프트 · 특성화 green.

**Q3. gates.py의 최종 홈** — **`engine/gates.py`. struct-s2 트랙 안, R10 착지 직후 후속 커밋.** 세 안·두 심사 만장일치. 가드 공유(R10의 gate_trace byte-identical이 이동 검증 겸용, D1 assert가 dotted-path 실존 강제). REASONS/REASON_COLORS는 어휘와 동행. 후속: preset 2차 이주 시 `evaluate(signals, *, query=…)` 인자화 — **engine/은 preset을 임포트하지 않고 러너가 전달**(G5 문법의 적용, 안B §3 채용). C의 관찰을 기록으로 남긴다: 캘리브레이션 값이 preset으로 빠지면 gates.py는 거의 순수 선언 카탈로그가 되어 analyzers.py의 진짜 형제가 된다.

**Q4. 질문 해부(3층)의 표현** — **products/ 이름 유지, 물리 분할 없음.** `Product`에 `question: str`(원장 ④의 세 문장) + `scorer: str`(E1 채점기 좌표, 미구축=빈 문자열=정직) 필드 추가 — 기존 `egress`(껍질의 형식 절반)·`state`(몰튼 여부)와 합쳐 3층이 선언 한 곳에 다 보인다. **registry warn: molten ∧ scorer 빈 값**(G2). 렌더 = `momentscan map products`(위임 브리프 한 방 출력 = 원장 ④ 따름정리④). 각 엔진 독스트링 첫 줄 = 자기 질문. eval.py는 파일 생성 없이 원리 한 줄만 예약(G12). B의 패키지화(T6)는 기각이 아니라 이연 — §4-D4.

**Q5. 새 ARCHITECTURE.md 목차** — 안A §5의 11절 골격 승계 + 접목 4점: ①정체성(세 가치 질문 vs visualstack=기계 질문) ②지배 원칙(/dev 원칙 + 비밀 2종 + "벽은 변화 축을 인용한다" — 인용 축 없는 벽=서브루틴 묶음) ③층 지도(12행+contracts.py: 질문·숨기는 비밀·**인용 축 A~L**·검증 4열; extraction의 이중 멤버십 자백) ④제품 엔진 3층 해부(+G1 소유권 어음, +G12 eval 예약석 한 줄, 졸업 규칙) ⑤정책의 집(preset — O/X 판정 기준·**로딩 경로 다이어그램**(안B TOC 채용)·**"함수는 preset을 모른다=종착 형태"(G5)**·"두 번째 시설이 threading을 지불") ⑥실행 기계(make 유비의 정직한 경계+깨지는 4곳 자백) ⑦격리 사다리 ⑧좌표계 지도 ⑨검증 척추(+**경로-실존 pytest 가드 G4**, +"답을 다시 쓰기 전에 채점기를 세운다") ⑩멤버십 테스트(갱신판+preset 멤버십="시설이 바뀌면 달라지는 값인가") ⑪비목표(원장 ② 포인터만). 재작성 시점 = preset 뼈대+gates 이동 착지 후, main 직행. 부패 해소 동승(root `__init__` "domains" 잔존 등 4곳·data-contract.md 링크·refactor-exec-plan.md:96).

**Q6. 이주 시퀀싱** — §5의 트랙 테이블.

**Q7. 하지 않는 것** — §6의 기각 원장. 안A §7 전체 승계(products/·select 재배치 없음, yaml·로더·threading 없음, media 이중 이동 없음, 축 I 추상화 없음, serve/store/engine 절단면 무접촉, 60개 일괄 이주 없음) + 접목 과정의 기각분 추가.

## 4. user 결정 필요 항목 (설계자 재량 밖 — G11 형식)

**D1. when-home 트랙의 시점** — likeness 앞이냐 뒤냐.
- (a) **struct-s2 직후 즉시** — 권고. ~50줄 소형이라 likeness 지연이 실질 0이고, 축 D "연구 착수 전 필수"(change-forecast:19)를 가장 싼 시점(수술 부위 비활성)에 선급.
- (b) likeness L-A 뒤로 — likeness가 절대 최우선이고 반나절도 아까우면. 비용: energy 재편이 가까워질수록 두-곳-동시-수술 위험 증가.

**D2. r6-egress(contracts.py) 시점** — 회사 일정 지식은 소유자에게 있다.
- (a) **likeness 트랙과 병렬 소형 트랙, 알파의 회사-소비 전 착지** — 권고. L3("위반이 소비자 측에서 발견")은 현재형이고 인터페이스 공유 의무가 "빠른 시일"이다.
- (b) 알파 착지 직후. (c) 기존 계획 순위 유지(후순위) — L3 리스크 수용 시.

**D3. molten∧scorer-empty warn의 활성 시점** — 켜면 likeness·highlight 두 몰튼 제품이 E1 채점기 좌표를 채울 때까지 `verify registry`에 상시 warn이 뜬다.
- (a) **즉시 활성** — 권고. 정직한 노랑이 원장 ④-①의 기계화 그 자체이며 E1 재개 압력으로 작동.
- (b) E1 재개 트랙에서 활성 — 상시 경고를 소음으로 본다면.

**D4. 안B 질문-패키지화(T6-products)의 재상정 시점** — 이것은 기각이 아니라 이연이다(종착 형태의 Parnas 완결성은 양 심사가 인정: 심사1 ①=5점 "종착 형태는 가장 옳다").
- (a) **R16/17 ArtifactNode 시점 재평가** — 권고. select 지위의 자연 결정(M5)과 동시, 새 정보(스테이지 그래프의 물리화)가 그때 생긴다.
- (b) likeness 착지 직후 재평가. (c) 영구 기각 — 위임(1인 브리프=ls 한 번)이 영영 불필요하다고 판단하면.

## 5. 이주 계획 (트랙 단위)

원칙: **"이동은 작업이 지불한다"**(안A — 심사1 접목#6이 전 안에 이식 권고한 비용 규율). E1 재개(user-동행)는 전 트랙과 무접촉·인터리브 자유.

| # | 트랙 | 신규? | 스코프 | 완료 기준·가드 | 기존 계획 합류점 |
|---|---|---|---|---|---|
| 1 | **struct-s2** | 기존+편승 1커밋 | R10 gates 스테이지 독립 → **gates.py→engine/ 순수 이동**(후속 커밋) → R11 closure | gate_trace **byte-identical** · D1 assert · replay 0드리프트 · apicheck | 확정된 다음 트랙 그대로 (축 K) |
| 2 | main 직행 | — | fold-store 스코프 각주: 무소유 4족(highlight_lang.json·highlights/·s{sid}.mp4·detect_h264.mp4) 편입 + **scores.parquet 예약석(G10)** 명기; 문서 드리프트 수리 | docs-only | — |
| 3 | **track/when-home** (~50줄) | 신규 | `when_from_channels` 명명 승격 + 소유권 독스트링(G1) + highlight.py 미러 소거→구독 | highlight.json **byte-identical** · replay · 특성화 green | 시점=D1 결정; energy 재편 전 필수 |
| 4 | **likeness L-A** 첫 커밋 | 기존 트랙 동승 | `preset/` 뼈대(그룹 스키마 G6) + 1차 값-불변 이주(Q1 상수군) + test_preset 핀(G7) + AST authority(G8); **⑦ 신설 상수는 인자-전달 문법(G5)으로 탄생** | likeness.json/fashion 특성화 값 동일(refactor-exec-plan §5 기준값) · pytest green · replay 0드리프트 | structure-audit §5-3 "⑦ 정책 상수는 C9 자리"의 집행 |
| 5 | **track/decl-guards** (소형; 4에 동승 가능) | 신규 | `Product.question/scorer` + registry warn(G2, 활성 시점=D3) + 무소유 4족 tier 선언 + **stash 등록 의무 error(G3)** + `map products` 렌더 + 경로-실존 pytest(G4) | registry 0err(warn 허용) · api green · map 렌더 확인 | R15 계열 enforcement |
| 6 | main 직행 | — | ARCHITECTURE.md 재작성(Q5 목차) + `__init__` 정합 | G4 pytest green | preset 뼈대+gates 이동 착지 후 |
| 7 | **track/r6-egress** (소형) | 신규 | `contracts.py`: LikenessV1·ResultV1 msgspec(**PresetV1 없음**, G9) | 15클립 재검증 · missing-field raise 테스트 · api green | 시점=D2; C11 절단면의 검증 기계 (축 L) |
| 8 | **fold-store** | 기존(이월 가능) | 기존 스코프 + 4족 accessor 편입 + scores.parquet 예약석 보관 | store 접힘 byte-identical | 기존 계획 그대로 |
| 후속 | **energy 재편**(D 연구) | 기존 | `when_from_channels` 단일 수술 + preset 3차(EXPECTATIONS·SCENE_PROMPTS·방출 노브·intent) + **scores.parquet 실체화 여부 결정**(G10 — 채널 안정 직후가 옳은 시점) | E1 메트릭 비퇴행(E4) | E1 완료 후 |
| 후속 | **쿼리 저작** | 기존 | preset 2차(PORTRAIT_QUERY/W·QUERY_DIST_MAX) — `evaluate` 인자화, engine은 preset 무임포트 | gate_trace 특성화 | R10 착지 후 |

## 6. 의도적으로 거부한 것들

**안B에서 기각**:
- **T6-products 패키지화(지금)** — 양 심사의 최대 감점 사유: likeness 2~3트랙 지연에 얻는 것이 ls 정직성·브리프뿐(어제 감사의 옵션 C 기각 논리 재상연, B 스스로 자백), Product 선언 이주의 순환 임포트 미계상(심사2 치명 ii), analyzers.py drift-assert의 한-장-검증을 임포트-규율 약속으로 격하(심사1). → **이연**(D4)이지 사형이 아님.
- **select.py → readings/scoring.py** — M5의 계획된 이연을 새 정보 없이 선점(심사2 ⑤); in-degree 8 재배선+STAGE_MODULE 재주조는 지금 순비용.
- **13러너 시그니처 preset threading(지금)** — 시설 1개인 오늘의 선지불 배관(심사1 ⑦·심사2 ⑦), C9 원문 "두 번째 도메인이 지불" 위반.
- **when.py 물리 신설(지금)** — 명명 함수+소유권 선언(G1)이 D축 은닉을 충족; 물리 이전은 energy 재편 트랙의 선택지로 남긴다.

**안C에서 기각**:
- **toml/yaml + 로더** — freshness import-클로저 이탈 = 수동 `_external_deps` 등록(opt-in)에 안전을 위탁, 누락=test_3(stale 오신뢰, 사고 3회) 재발 경로(심사1 치명2); 보수적 전체-stale 결합은 캘리브레이션 스윕의 최악해(심사2 치명 i); provenance 주석("E002"·"calibrated on cap_1")과 blame 사슬 상실.
- **PresetV1의 contracts.py 동거** — 도메인-내부 스키마와 wire 계약을 한 파일에 = p981-contracts 분리 시 도로 갈라낼 이중 이동의 씨앗(심사1 ⑤). preset은 경계를 안 넘는다.
- **scores.parquet 즉시 영속화** — gate_trace 전례의 시점 오독: 전례는 어휘가 *안정된 뒤* 영속화됐다(심사1 치명1). 몰튼 채널 위 산출물 계약은 energy 재편의 매 반복에 스키마+구독자 이행을 청구한다. → 시점만 이연(G10).
- **harness의 parquet 구독 전환** — rescore_pairs의 방법론("현재 코드로 재계산해 동결 인간 평결에 대 측정", harness.py:325-333 실측)을 반전시키는 과잉 일반화(심사2 치명 ii). 렌더러에 옳은 처방을 채점기에 적용하지 않는다 — **영구 기각**.
- **import-시 재바인딩을 종착 형태로** — 과도기 한정으로만 수용, 종착 형태는 G5로 명문화하고 G8이 감시.

**안A 자체에서 보정·기각**:
- "D축은 이름만 부족했다"는 하향 재해석 — G1 소유권 선언으로 보정(심사1 치명 결함 지적 수용).
- R6 무편입 — G9로 보정(심사2 만성결함 iii).
- cards 재계산 존치의 무기한 방치 — 존치 자체는 유지(시점 규율)하되 G10 예약석으로 어음을 발행하고, 과도기 안전망이 freshness ⚠STALE임을 문서에 명시.

**공통(전 안 합의 승계)**: 축 I(라이브) 선제 추상화 없음 · extraction⇄subjects 양방향(media) 물리 수리 없음(visualbase 예약석, 소개 정직화만) · serve/store/engine 절단면 무접촉(졸업석 보존) · products/ 개명 없음(인용할 변화 축 부재) · 60개 상수 일괄 이주 없음(O/X 구분이 설계의 절반) · 새 레이어·미니도구·2곳-중복 홈 없음(원장 ②).

---

**한 문장 요약**: 안A의 골격(신규 홈 2개 — preset/과 WHEN 명명 함수, gates 이동 1건, 나머지는 선언·문서) 위에, 양 심사가 공통 권고한 enforcement 4종(G2·G3·G4·G8)과 B의 절단 문법(G5·G6), C의 계약 실체화(G9)를 접목하고, 유일한 심사 간 충돌(scores.parquet)은 "형태는 C, 시점은 gate_trace 전례"로 중재했다 — 모든 트랙이 값-불변·byte-identical 가드를 갖고, likeness는 4번 트랙에서 대기 없이 열린다.
---

## 결정 기록 (user, 2026-07-16): D1~D4 전부 권고안 채택

D1=(a) when-home은 struct-s2 직후 즉시 · D2=(a) r6-egress는 likeness 병렬,
회사-소비 전 착지 · D3=(a) molten∧scorer-empty warn 즉시 활성 ·
D4=(a) 질문-패키지화는 R16/17 시점 재평가. → §5 트랙 테이블 순서로 실행 개시.

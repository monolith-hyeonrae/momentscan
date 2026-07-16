> 발주: user 2026-07-16 — Parnas 정보 은닉(무엇을 숨기는가·6개월 변화 축)과
> UNIX 작은 도구+파이프 철학으로 T1~T5 직후 구조를 재심사. 생성 =
> architecture-review 워크플로(4렌즈 실측+스팟체크 9건). 상설 원장은
> change-forecast.md — 이 문서는 그 시점 심사다.

# momentscan 구조 재심사 보고 — Parnas 정보 은닉 × UNIX 도구 철학

**2026-07-16 · main 6480c05 (T1~T5 착지 익일) · 근거: 4렌즈 실측 + 본 심사 스팟체크 9건(전부 실측과 일치: extraction⇄subjects 양방향 임포트, gates.py "sibling" 자기선언, STAGE_MODULE 13경로, root `__init__` "domains" 잔존, highlight_lang.json 리터럴 양측, surface "No recomputation" 선언, ARCHITECTURE.md 995efc5=2026-07-06 동결, select 소비자 8파일, cards.py frame_scores 재계산). 수정 없음, 분석만.**

---

## 1) 한 장 요약 — 지금 구조는 무엇의 형태인가

**첫째**, 실행 층은 이미 UNIX다 — momentscan의 뼈대는 "stash(파일시스템)를 파이프 삼은 make-스타일 필터 13개"이고(균일 러너 시그니처 · mtime+임포트클로저 증분 · exit code 규율 · 교체 문법 3회 실증), 어제의 T1~T5는 그 뼈대 위에 패키지 이름으로 비밀 경계를 입힌 이사였으며 이사 자체는 무결하다(깨진 참조 0, 신경로 테스트, D1 assert 가동).

**둘째**, 그러나 Parnas의 기준 질문 — "6개월 뒤 무엇이 바뀌고, 각각을 무엇 뒤에 숨겼나" — 로 재면 이사는 절반이다: 6개월 내 가장 확실한 두 변화 축, 정책 임계 ~60개(B1/C9)와 highlight WHEN 재편(D)이 **어떤 은닉처 뒤에도 없이 15파일/3파일에 산개**해 있고, 어제 옮긴 것은 파일이지 비밀이 아니어서 다음 변경의 청구서는 옮기지 않은 상수와 공식 앞으로 발행된다.

**셋째**, 남은 위반 대부분은 좌표가 찍혀 있으나(R10/R11 즉시, C9 · fold-store · 졸업 로드맵 대기) 두 가지가 계획 밖에서 썩고 있다 — 은닉 선언 사슬의 정점(ARCHITECTURE.md가 재배치 이전에 동결된 채 `__init__` 5곳이 "단일 진실"로 위임)이 거짓이 되었고, stash 우회는 감사가 센 14곳에서 하나도 줄지 않은 채 **신생 코드(highlight_lang)가 우회 패턴을 복제·증식**시키고 있다.

---

## 2) Parnas 심사표 — 변화 축 × 은닉처

판정 기준: **숨겨짐**=축이 바뀔 때 수술 부위가 한 경계 안 / **샘**=경계는 있으나 지식이 새어 있음 / **노출**=은닉처 없음, 변경이 산개 수술.

| 축 (확률) | 오늘의 은닉처 또는 산개 실측 | 판정 | 처방 |
|---|---|---|---|
| **A1** resultPath 매핑 ● | serve/company.py 한 곳, 임시 매핑도 자백 주석과 동거(:19, :135) | **숨겨짐** | 불요 — 회신 도착 시 어댑터 내 수술 [기존 설계] |
| **A2** 인바운드 인증 ● | 비밀 자체가 아직 부재하나 자리=serve/ 한 곳(service.py 핸들러) | **숨겨짐(예약)** | 불요 [기존] |
| **A3** 관측 방언(actuator·메타) ◐ | serve/eureka.py+company.py | **숨겨짐** | 불요 [기존] |
| **A4** 트리거 transport ◐ | C1 transport-agnostic 선언 + 어댑터 증설 설계 | **숨겨짐** | 불요 [기존] |
| **B1** C9 정책 임계 ~60개 ◐ | **15파일 산개** — products 51 · readings 12 · gates.py · subjects (preset-inventory.md 302행이 유일한 지도) | **노출 (최대)** | C9 preset 실체화 [계획 — likeness ⑦이 첫 지불자로 확정 대기] |
| **B2** fps=6 ○ | 3곳 산개(service.py:172 · pipeline.py:184 · 스테이지 기본인자) | **노출** | C9 합류 [계획] |
| **C1** headpose 융합 재편 ○ | 부호 어댑터(headpose.py:12-21) + 융합 정책 단일홈(pose.py:89-99) | **숨겨짐** | — |
| **C2** SegFormer→FashionCLIP ◐ | fashion.py+parse.py 2곳, 라벨맵 홈 공유 | **숨겨짐(경미)** | 결정 경로 확정됨 [기존] |
| **C3** features A/B 스왑 ○ | ports.FeatureSource Protocol 1점(ports.py:56) | **숨겨짐** | — 단 §4(c) 참조: 계약만 완성, 실증 미완 |
| **C4** MARLIN·비디오-CLIP 승격 ◐ | highlight_lang 1파일이나 select.py RARITY_FIELDS 46-dim state 계약과 결합 | **샘** | E1 후 — select state 계약이 걸림돌 [**신규 주의**] |
| **D** WHEN/WHICH 재편 ● | select.py:182-249 정본 + **highlight.py:185 미러(복제)** + highlight_lang 미통합 = 3파일 | **노출** | **신규 갭** — E1 후 1순위 연구로 등록만 됨, WHEN 단일홈 구조 처방은 부재 |
| **E** 시설/기구 확장 ○ | =B1과 동일 산개 + phase 모델(tubelets.py 2-means)·좌석 규칙·EXPECTATIONS 문장 | **노출** | C9 [계획] |
| **F** 배포 k8s ◐ | serve/ 한 곳 — 단 graceful shutdown=JobRunner 수명주기 수술, MAX_INFLIGHT=1 하드코딩 | **숨겨짐~샘** | 배포 시점 [기존] |
| **G** visualstack 졸업 ●방향 | 패키지 절단면 물리화 완료(T1~T5=리허설, serve/store=졸업석 이름) | **숨겨짐** | C12 화이트리스트 enforcement=R15 **미착지**가 잔여 [계획] |
| **H** likeness 캘리·gain ● | C11 계약이 두-레포 절단면(additive 소비 확장) | **숨겨짐** | 트랙 열림 [계획] |
| **H2** phase 조건화 ⑦ ● | likeness.py+fashion.py 2곳, 정책 상수는 C9 자리 | **샘** | C9 합류 [계획] |
| **I** 배치→라이브 전환 ○ | 클립-스코프 가정이 **알고리즘 자체에 내재**(stitch 전역병합 · select 클립분포 rarity · emotion 클립 baseline) | **노출(등록된 부채)** | 없음 — visualpath topic-flow 예약석 [의도적, §5-5 참조] |
| **J** S3/스토리지 ◐ | 쓰기=stash 1곳 ✓ / **읽기 우회 14곳 + 무소유 산출물 4족**(ARTIFACT_TIERS 밖) | **샘 (악화 중)** | fold-store [계획] + **신규 갭**: 무소유 4족이 fold-store 스코프에 명시돼 있지 않음 |
| **K** gates 독립 + closure ● | gate_trace 생산이 portrait 내부(D2) · 타겟 빌드 부재(D3) | **노출** | R10/R11 = struct-s2 [계획 — 바로 다음 트랙, 유일하게 "즉시"] |
| **L** 계약 semver ◐ | 도장 2곳(service.py:45 · likeness.py:460), **검증 기계 0**(R6 미착지 = L3 헛점: 위반이 소비자 측에서 발견됨) | **샘** | R6 [계획·미착지] |
| **M1·M2·M3·M7·M8** ○ | 각각 detections 스키마 수렴점 / 디스패치 홈 예약 / evals 재결합 / 자백 주석 / 보류 결정 문서화 | **숨겨짐** | — |
| **M4** landmarks 유령 물리화 ○ | 실생산자=plugins 내부, 선언-물리 불일치를 analyzers.py:59-62가 자백 | **샘** | R14/사다리③ [계획·보류] |
| **M5** select.py 홈 ○ | products/에 기판, **in-degree 7~8로 증가**(스팟체크: readings/signals.py 참조 포함 8파일) | **샘** | R16/17 시점 자연 결정 [계획된 이연] |
| **M6** role_delivery ○ | C9 예약 필드 | **노출(B1 합류)** | C9 [계획] |

### 판독 — 계획이 커버하는 것과 계획 밖의 것

**계획된 처방으로 커버**: K(R10/R11) · B/E/H2/M6(C9) · J-14곳(fold-store) · G(졸업 로드맵+R15) · L(R6) · M4(R14) · M5(R16/17). 이 목록의 문제는 방향이 아니라 **시제**다 — R6·R15는 미착지인 채 L3 헛점("계약 위반이 소비자 측에서 발견됨")이 현재형이고, C9는 "빈 슬롯"인 채 산개가 60개다.

**신규 갭 (어떤 R에도 매핑 안 됨)**:
1. **WHEN 공식 이중 정본** — select 정본 vs highlight.py:185 미러. D축이 E1 후 1순위 확정인데 착수 전 단일홈 처방이 없다. 연구가 열리는 순간 두 곳을 동시 수술하거나 드리프트를 낳는다.
2. **extraction⇄subjects 패키지-레벨 양방향** (detect.py:41→stitch, parse.py:35→crops ↔ crops.py:26→media) — T4의 media.py 배치가 만든 상호인지. 계약 체인(contracts.md:88)은 단방향인데 실물이 위반.
3. **무소유 산출물 4족** (highlight_lang.json · highlights/ · s{sid}.mp4 명명 재조립 · detect_h264.mp4) — reader/writer 쌍도, tier 선언도 없는 파일들. fold-store가 14곳 우회를 겨누지만 이 4족의 편입은 어디에도 명시 안 됨.
4. **자기소개 부패 사슬** — root `__init__`이 "layout contract는 ARCHITECTURE.md가 단일 진실"이라 위임하는데 그 진실이 재배치 이전(2026-07-06)에 동결, `domains/` 5회 잔존. 하위로 `__init__` 4곳 거짓(extraction 멤버십·products select 무단서·surface label UI/No recomputation·root domains), data-contract.md:7-8은 **실제 깨진 링크**, refactor-exec-plan.md:96은 **미착지 작업 R3의 위치 지시가 옛 경로**.
5. **surface 재계산** — "No recomputation" 선언 아래 cards.py 2곳이 products.select의 frame_scores/rolling_median을 임포트해 재계산(스팟체크 확인). 단일홈 임포트라 Parnas적으로는 합법이나, 패키지 자신의 계약("persisted payload 위 순수 렌더러")과 freshness 원칙(영속화가 처방, gate_trace 전례) 위반.
6. **extraction⇄surface lazy 순환** — detect.py:281이 surface.cards 렌더러 호출(하층→프론트엔드 역류).
7. 소형 리터럴 산개: serve http-*.json 3곳 · crops/manifest.json 스키마 5곳 · cli의 eval 경로 1곳.

**구조적 관찰 하나**: 판정의 분포가 방향을 말해준다. **외부-강제 축(A·F·G·H)은 전부 숨겨졌고, 내부-연구 축(B·D·K·I)일수록 노출**이다. 이유는 명백하다 — 외부 방언은 어댑터 뒤에 숨기기 쉽고, 연구 정책은 정의가 끓는 중이라 은닉처(C9)가 "빈 슬롯"으로 미뤄져 있기 때문. 즉 이 레포의 Parnas 부채는 게으름이 아니라 몰튼 정책의 의도적 이연인데(§5-1), **이연의 만기가 왔다는 것이 렌즈2의 실측**이다: likeness ⑦과 E1-후 energy 재편이 6개월 시계 안에서 그 빈 슬롯을 첫 지불자로 호출한다.

---

## 3) 비밀 없는 모듈 판정 — 서브루틴 묶음이 있는가

**총평: Parnas가 경고한 순수 서브루틴 묶음(플로차트 단계를 모듈로 착각한 분할)은 없다.** 가장 얇은 cli/조차 "argv 방언→API 매핑"이라는 은닉 직무가 있고, verify/는 "green의 정의"(tolerance·IGNORE·REPLAY_STAGES)라는 진짜 비밀을 쥔다. store/는 순수 싱크(외부 임포트 0), serve/는 방언 흔적 경계 밖 0 — 이 넷은 실측상 교과서적이다.

다만 **"비밀 결손"의 세 변종**이 있고, 셋 다 어제 재배치가 남긴 것이거나 키운 것이다:

- **extraction/ — 멤버십 테스트 붕괴 (묶음화 표류의 시작).** 자기선언 "one research specialty per module (a model observing)"을 media.py(픽셀/인코딩 유틸)와 ingest.py(decode/trace)가 통과하지 못한다. T4/T5가 갈 곳 없는 파일을 여기 넣고 소개를 안 고쳤다. 결과가 즉시 구조로 발현했다 — subjects/crops가 상류 패키지의 유틸(media)을 역참조하는 양방향이 그것이다. "추출하는 것들의 서랍"으로 표류하는 첫 증상이며, media.py의 진짜 예약석은 visualbase(졸업 4단계)로 이미 정해져 있으니 **그때까지는 최소한 소개가 정직해야 한다**(이중 멤버십 자백).
- **readings/ — 선언한 비밀의 절반이 남의 집.** "신호→의미 변환"이 선언인데 의미 임계 O 100건 중 12건만 보유, 51건이 products에 있다(BIN_EDGE_DEG=15°가 CAMERA_FRONTAL_DEG=12와 짝인데 다른 집, valence 4단 양자화가 emotion.py 밖). 비밀이 없는 모듈이 아니라 **비밀이 덜 이사 온 모듈** — C9가 예정된 은닉처라는 답은 있으나, 그 전까지 readings의 이름은 실체보다 크다.
- **products/ — 이중 정체.** select.py(기판, in-degree 7~8)가 제품 디렉토리에 있어 "ls products/가 정직한가" 테스트(구조 투명성 원칙)가 계속 실패한다. 감사 D5가 tier로 선언해놓고 `__init__`은 무단서 "product engine"으로 소개 — 선언과 자기소개가 서로 다른 말을 한다.

**상위 축 자체의 이중성도 정면으로 말해두겠다.** extraction→subjects→readings→products는 **데이터흐름 단계 절단이기도 하다** — 정확히 Parnas가 경고한 모양이다. 이 레포가 살아남은 이유는 각 단계가 우연히 비밀과 *대체로* 일치하기 때문이다(모델 백엔드 / 정체성 대수 / 의미 변환 / 취향). 그러나 일치가 깨지는 곳마다 잔여물이 고인다는 것이 그 이중성의 증거다: media(단계 축엔 집이 있으나 비밀 축엔 없음), select(비밀 축엔 기판이나 단계 축에선 products), gates.py(판정이라는 비밀이 단계 사이에 낌), WHEN 미러(공식이라는 비밀이 단계 축에 집이 없어 복제됨). **잔여물의 위치가 곧 두 분할 기준의 차이 지도다.**

**gates.py 루트 잔류의 처분**: 이연은 정당하다 — R10이 바로 다음 트랙에서 실행 이음매 자체(portrait 내 `gates.evaluate` 인라인→독립 스테이지)를 수술하므로, 지금 옮기면 활성 수술 부위 이중 터치에 dotted-path 2회 주조다. 홈은 1순위 engine/에 동의한다(자기선언이 analyzers의 형제, graph.py가 이미 둘을 한 장에 렌더, R10 후 STAGE_MODULE["gates"]의 자리). readings/ 부적합도 동의(gate=reject-route ≠ reading, 감사 taxonomy). 단 두 가지는 지적한다: (i) 이연에도 유지비가 있다 — 첫 줄 "sibling to analyzers.py"가 이미 물리적 거짓(스팟체크 확인)이고, 루트 잔류는 어떤 패키지의 비밀 선언에도 안 잡히는 무적(無籍) 상태다. (ii) 진짜 문제는 지리가 아니라 **집행 위치**다 — 기준(코드)은 단일홈으로 완벽히 숨었으나 기준 *변경의 파급*이 portrait 실행에 볼모(gates 변경→portrait만 재실행, likeness는 stale)라는 D2가 Parnas적 실해이며, R10 착지와 함께 이주 1회로 닫는 것이 맞다.

---

## 4) UNIX 판정

### (a) 이미 파이프인 것 — 유비는 어디까지 정직한가

**"make"까지는 정직하다.** 균일 러너 시그니처 13개 `(probe, fn(out, clip, src, fps))`, skip=존재∧(소스 mtime∧직접 상류 artifact보다 새로움), 소스 신선도=transitive import 클로저+외부 모델파일 lazy stat, 연쇄는 topo 순서가 자연 전파 — Makefile의 의미론을 임포트 그래프 위에 재구현한 것이고, 선언⇄실행⇄신선도 3중 정합을 import-time assert 2개와 `verify registry`가 강제하니 "Makefile이 곧 실행 계획" 성질까지 있다. tolerance replay는 make에 없는 회귀 게이트로 유비를 오히려 보강한다.

**"sh"는 아니다 — 그리고 그건 결함이 아니라 선택이다.** UNIX 파이프의 힘은 매체의 무지(byte stream)인데 stash는 typed read/write 쌍 46개의 강한 스키마 파이프다(sh보다 PowerShell에 가깝다). 수치 연구 데이터에 텍스트 스트림은 거짓 소박함이므로 선택 자체는 옳다 — 대가는 §5-2에서 논한다.

**유비가 거짓말이 되는 갭 4곳(전부 자백은 있음)**: ① INFRA(store/) 클로저 제외 — stash 포맷 변경이 값을 바꿔도 stale 안 됨, `--force` 수동(freshness.py:30-35 자백, 스팟체크 확인). ② detect/landmarks가 러너 밖 = freshness 사각 선언(D4). ③ make target 부재 — `--product likeness` closure가 R11 전까지 없어 지금은 전량 실행 또는 수동 `--only` 조합. ④ 파이프를 안 쓰는 소비자 14곳+무소유 4족 — 파이프 규율의 실측 위반.

### (b) 한 덩어리로 남은 곳과 그 대가

- **13스테이지 1프로세스, 서비스도 동일 프로세스 직호출.** 크래시 격리=파이썬 예외 record-and-continue뿐, 네이티브 크래시(onnx/mediapipe segfault)=런 전체 사망. 그러나 **오늘 지불 중인 실비용은 리스크가 아니라 처리량이다**: likeness closure 43s면 될 것을 전량 4min 도는 것(D3), 그리고 MAX_INFLIGHT=1. 격리(R16/17)는 의도적 보류이고 §5-3에서 다루지만, R11은 격리 없이도 처리량을 푸는 지렛대라 순서가 옳다.
- **gate_trace가 portrait 안(D2)** — 이 레포에서 가장 나쁜 유형의 결합이다. freshness가 artifact-매개 의존을 절반만 봐서 "gates 변경→likeness stale 미감지"가 선언에 자백돼 있는데, 이 레포는 **stale 결과 오신뢰 사고 이력(test_3)이 문서화된 곳**이다. 같은 병의 재발 경로를 알면서 열어둔 셈이고, R10이 바로 다음 트랙인 것이 유일한 변호다.
- **몰튼 제품 비분리** — likeness "two homes"·highlight 3파일은 UNIX 위반이 아니라 **결정된 비분리**다("정의가 끓는 것은 쪼개지 않는다" + 졸업 규칙 + 전례 2건). 작은 도구화가 시점 이벤트로 설계된 것 — 판정은 §5-1로.

### (c) "갈아끼우기" 실증과 반례

**실증 3건, 문법이 동일하다** — 출력 계약 고정 + 어댑터 1점 + 측정 검증: headpose(교체가 아닌 병렬 추가+융합, 부호-corr 측정으로 좌표 정합), subject_query(모든 전략이 동일 attribution.json 방출→하류 불변, C3), features A/B(FeatureSource Protocol). "개선된 도구로 갈아끼우면 시스템이 좋아진다"가 이 레포에서 실제로 작동한 절차다.

**반례도 정면으로**: ① features 포트는 **계약 완성이지 교체 실증이 아니다** — vjepa 소비자 0, 스왑은 config가 아니라 어댑터 파일의 import 1줄 편집. 실전에서 한 번도 안 갈아끼운 소켓이다. ② WHEN 공식은 교체 대신 **복제**됐다(highlight.py 미러) — 도구를 갈아끼우는 문화에서 가장 반대편의 수. ③ highlight_lang은 파이프 규율 밖에서 추가된 새 도구다 — 산출물이 tier 선언에 없고 읽기 3곳·쓰기 1곳 전부 리터럴. **도구상자에 도구를 넣은 게 아니라 작업대 위에 놓고 간 것**이며, 우회 14곳이 감사 후 0건 해소인 채 신생 코드가 패턴을 복제한다는 건 규율이 문서로는 전파되지 않고 있다는 실측이다.

**momentscan ↔ visualstack 역할 분담의 독해**: 이 철학에서 둘의 관계는 정확히 **"도구를 벼리는 공방"과 "bin/에 설치하는 곳"**이다. momentscan은 몰튼 정의를 끓이는 연구 공방이라 통합이 정당하고, visualstack 졸업은 "인터페이스 동결" 이벤트 — frozen된 기계(stash·serve·pipeline 선언·media)만 이주한다. T1~T5가 졸업석 이름(serve/·store/)으로 절단면을 물리화한 것은 이 분담의 리허설로 정확하다. **위험은 하나**: 졸업이 무기 연기되면(착수="소유자 결정" 대기) frozen 기계가 몰튼 이웃의 우회에 노출된 채 방치된다 — stash 649줄이 지금 그 상태다. 도구는 굳었는데 사용 규율은 안 굳었다.

---

## 5) 긴장 지점 — 소유자와의 대화 의제

**5-1. 몰튼 제품은 인터페이스 뒤에 못 숨는다 — Parnas와 연구 변동성의 긴장.** Parnas는 "바뀔 결정을 미리 식별해 숨겨라"인데, 몰튼 제품의 정의는 "바뀔 결정"이 아니라 **아직 결정이 아닌 것**이다 — 숨길 비밀이 성립 전이다. 내 입장: 현행 정책("molten은 크게, frozen은 정밀하게"+졸업 규칙)은 Parnas 위반이 아니라 Parnas의 시간축 적용이며 옳다. 단 두 조건이 붙는다. 첫째, 몰튼 면제가 면허가 되지 않으려면 졸업 판정이 정기적이어야 하고(tier 선언이 그 장치 — 그러나 tier 선언조차 자기소개와 어긋나는 지금 상태로는 장치가 녹슨다), 둘째, **몰튼 안에서도 데이터 계약은 얼릴 수 있다** — likeness가 gate_trace의 `frontal_clean` 컬럼(데이터)만 소비하는 것이 모범 사례다. C9 preset이 정확히 이 원리다: 정책 *값*은 끓게 두되 정책의 *자리*(스키마)를 얼리는 것. 그래서 C9 실체화는 "몰튼이니 못 숨긴다"의 반례이자, 6개월 축 중 레버리지가 가장 높은 선행 투자다.

**5-2. stash 파이프의 스키마 결합 — UNIX를 버렸으면 Parnas라도 지켜라.** stash는 universal byte stream을 포기하고 typed 계약을 택했다. 연구 데이터에 옳은 선택이다 — 단, 그 선택의 대가는 "스키마 지식이 한 곳에 있을 것"인데 현재는 accessor 46쌍 옆에 우회 14곳+무소유 4족으로 **둘 다 아닌 중간태**다. 내 입장: 우회의 원인을 도덕이 아니라 마찰로 진단해야 한다 — 649줄 단일 파일에 read/write 쌍을 추가하는 비용이 리터럴 한 줄보다 비싸게 느껴지는 순간 우회는 계속 발생한다(highlight_lang이 산 증거). fold-store의 처방 형태가 중요하다: 단순 이사(레이아웃 정리)가 아니라 **등록 마찰을 낮추는 레지스트리**(테이블 한 줄 추가=accessor·tier·freshness 동시 획득)여야 우회가 경제적으로 소멸한다. 그 전까지는 "새 산출물은 ARTIFACT_TIERS에 없으면 CI가 잡는다" 수준의 값싼 enforcement라도 논의할 가치가 있다.

**5-3. 단일 GPU 프로세스 vs 크래시 격리 — 철학이 아니라 실측이 우선순위를 정해야 한다.** UNIX 잣대로 13스테이지 1프로세스는 명백 위반이나, GPU 7.6GB·모델 웜업 비용이 프로세스-퍼-스테이지를 비싸게 만든다. 내 입장: R16/17 보류는 옳고, 보류를 유지하는 근거를 "비용이 크다"가 아니라 **관측된 네이티브 크래시 빈도**로 유지하라 — record-and-continue가 파이썬 예외를 잡는 한, run.json에 남는 실패 통계가 격리 투자의 트리거여야지 철학이 트리거면 과잉 설계다. 반대로 같은 "작게 돌리기" 계열에서 R11(closure)은 격리 없이 처리량 ~6배를 여는 수라서, "UNIX적 개선 중 싼 것부터"라는 순서(R10/R11 먼저, 격리는 데이터 대기)는 두 철학 모두에 부합한다. 단 k8s 배포(축 F)가 오면 계산이 바뀐다 — pod 재시작이 공짜 격리를 주므로, 격리 투자 판단은 배포 형태 결정과 묶어서 해야 한다.

**5-4. engine의 주소록 문제 — make는 모든 타겟을 알아야 하지만, 아는 방식이 이사 비용을 정한다.** STAGE_MODULE 13 dotted-path+RUNNERS probe relpath는 전 시스템 물리 배치의 거울이라 모든 이사가 engine을 터치한다 — T1~T5 내내 지불했던 비용이다. 내 입장: Makefile이 타겟을 아는 것은 집행기의 본질이라 수용하되, 이것은 "숨겨진 결합"이 아니라 **가드된 명시적 결합**(D1 assert 2중, loud-at-import)이라는 점이 이 레포가 잘한 부분이다. 남은 예정 이사는 gates.py(R10 시) 하나뿐이므로 주소록은 곧 안정되고, visualpath ArtifactNode(R16/17)가 선언을 노드로 옮기면 자연 해소된다. 다만 같은 논리로 **ARCHITECTURE.md도 주소록**이다 — 코드 주소록은 assert가 지키는데 문서 주소록은 지키는 기계가 없어 조용히 썩었다. "선언이 진실"을 자부하는 레포에서 선언 부패는 구조 부패와 동급이며, 문서 정합에도 D1 같은 값싼 가드(경로 실존 grep 수준)가 필요한가는 소유자 판단 사안이다.

**5-5. 패키지 축의 이중성 — 다음 이사는 파일이 아니라 상수와 공식이어야 한다.** §3에서 보였듯 상위 축은 데이터흐름 절단과 비밀 절단이 대체로 일치해서 사는 구조이고, 어긋나는 곳(media·select·gates·WHEN)마다 잔여물이 고였다. 여기에 축 I(라이브 전환)를 겹치면 긴장이 선명해진다: 클립-스코프 가정은 인터페이스 뒤에 숨길 수 없다 — stitch 전역병합·클립분포 rarity·클립 baseline은 **알고리즘의 정의 자체**라서, Parnas적 은닉의 대상이 아니라 재작성의 대상이다. 내 입장: I를 지금 숨기려는 시도는 하지 마라(추상화 비용만 내고 보호는 못 받는다, ○ 확률이 이를 정당화) — 대신 6개월 시계에서 확정인 B(C9)와 D(WHEN 단일홈)에 투자를 몰아라. 이 둘은 "새 패키지"가 아니라 **새 축의 은닉처**(도메인 정책·판정 공식)라서 어제 같은 파일 이사로는 절대 해결되지 않는다. 어제의 재배치는 지리를 정리했다 — 이 잣대가 요구하는 다음 수는 지리가 아니라 **정책의 이주**다.

---

### 부록: 판정 요약 서열

- **두 철학 모두에서 건강**: serve(방언 은닉 0누설) · store 쓰기면(순수 싱크) · verify(green의 정의) · ports(교체 계약) · engine(가드된 주소록) · T1~T5 이사 무결성.
- **계획이 이미 겨눈 위반(시제만 문제)**: K→R10/R11(즉시) · B/E→C9(likeness ⑦이 만기) · J→fold-store · G→R15 · L→R6.
- **계획 밖 신규 갭(이번 심사의 추가분)**: WHEN 이중 정본 · extraction⇄subjects 양방향 · 무소유 산출물 4족의 스코프 누락 · 자기소개 사슬 부패(정점 ARCHITECTURE.md) · surface 재계산 · extraction⇄surface 역류 · 소형 리터럴 3건.
- **의도적 비-은닉으로 승인**: 몰튼 비분리(졸업 규칙이 출구) · 축 I(라이브) 미은닉 · 격리 보류(단 트리거를 실측으로).
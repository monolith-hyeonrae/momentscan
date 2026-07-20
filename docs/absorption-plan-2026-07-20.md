> 생성: appearance-engine-absorption-audit 워크플로(3렌즈+판정). user 결정:
> 프리뷰=momentscan 소관, appearance-engine=배울 것 소진 시 삭제.
> 멤버 삭제 판정은 우산 bead — 이 문서는 momentscan 측 실행 계획 정본.

# appearance-engine 처분안 (설계 전용 — 수정 없음)

전제: user 결정 "프리뷰=momentscan 소관, appearance-engine=배울 것 소진 시 삭제". 멤버 삭제=우산 bead. C11 v1 불변(additive만). 수용처 좌표는 실측 확인 완료(`apps/momentscan/src/momentscan/{products,surface,perception,preset,infra/pipeline}` 실존, refactor-plan L-A/L-B 원장·ids.md:58,150-154·output/l2 잔존물 재확인).

---

## 1) 3버킷 처분표

### (A) momentscan 흡수 — 7건

| # | 자산 | 수용처 | 형태 | 근거 |
|---|---|---|---|---|
| A1 | `adapters/momentscan.py` 변환 규약 전체 — flip `[1,-1,-1]`·`_PSEUDO_SCALE=200`·+16 오프셋·neutral>center 폴백·frontality=1.0·unfilled 정직 보고·provenance 블록 | `products/recipe.py` **신설 독립 스테이지** — `depends=('likeness',)`, likeness.json만 읽고 per-rider recipe.json 방출 | 수용처 감사 C안 절충 채택: **Product 신설 없이** likeness Product `outputs`에 recipe.json additive, **egress 제외**. 근거: A안=생산자·소비자 융합으로 C11 절단면의 사회적 기능 훼손, B안=gen의 표면 소비 역류 예약. 엔진=질문 원칙상 recipe는 네 번째 질문이 아니라 답의 사상 → Product 아님. one-step-removed가 레포-간→패키지-간으로 줄지만 절단면은 산다. stale docstring(:18-20 "does not emit yet")은 포팅본에서 정정 | contracts.md:204(C11 소비자 표 "몰프 계수 사상 원료"), likeness.py:503 절단면 도장 |
| A2 | `component2/geometry.py` Cat G 37축 수학(453 LOC, numpy-only) + 인덱스표(:34-81) + `types.py` 필요분 | `perception/readings/` 신규 모듈(예: `face_axes.py`) — 공식만, 값 없음 | **비밀 2종 집행**: 기하 수학=측정 기판 비밀, 축ID·라벨·range=도메인 정책 비밀 → 한 파일에 섞지 않음. 소비자 실존(A1 스테이지)이라 비목표("소비자보다 먼저 짓지 않는다") 저촉 없음. `products/likeness.py:89-104 face_ratios`(7비율)의 상위집합이나 **face_ratios 통합은 트랙 밖 — 원장 기록만** | readings 멤버십 "문제-언어 공식, 값 없음" |
| A3 | `output/registry.json` 88축 정책(한글라벨·time_scale·choices) + `build_axes_registry.py:45-65` `_CALIBRATED_G_RANGES` 캘리 수치 + `axis_id_map.py` PREFIX_MAP | `products/recipe.py`(비대하면 동반 `recipe_axes.py`) **파이썬 모듈 상수** | 수용처 감사 후보 i 채택(freshness 우세): 값 수정→recipe/프리뷰만 자동 stale, json이면 `_external_deps` 수동 등재 누락=test_3 재발 경로. `preset/race981.py:23-37` "값+단위+근거" 관례로 `calibrated:sample_1[p5,p95]` blame 유지. **preset 불합격 확정** — range는 캘리 코퍼스 축이지 시설 축 아님(장비-색 제외 리스트와 반대) | freshness.py 클로저, blueprint Q5-⑩ 멤버십 테스트 |
| A4 | `blender_export.py` — SHAPE_KEY_MAP 13키(`Mouse_Corner` 스펠 고정 포함)·range-normalize→mean 집계·L/R 비대칭 0.55 폐기 규칙·HAIR_LIBRARY 13지문+가중치(length=5·parting/bang/shape=3·volume=1)+up-do 보너스+masc 필터+is_bald | `surface/recipe_preview.py` **신설** — 13키 투영은 프리뷰 내부 단계. blender.json 미영속(또는 surface tier 파생물), recipe.json(88축)만 스테이지 산출 | 13키 투영의 현존 소비자=프리뷰뿐(gen은 구상, ids.md:115-118 status=구상·구현 0) → **p981.if 격상·스테이지 산출 승격 모두 보류** = 비목표 원장 준수. gen 실구현 시 그때 격상. hair 검색 hybrid(retriever 주입)는 승계 안 함 — attribute-only 선택 로직만 | blender_export.py:37-154, 소비자 감사 §1 |
| A5 | `blender_render.py` 하니스 전체(re-open=리셋·비Basis 0 리셋·hair 가시성·bbox 자동 카메라 50mm·key/fill·EEVEE Next 폴백·512²) + `render_hair_references.py` | `surface/recipe_preview.py` 렌더 함수부 | bpy=선택-의존 사다리 3단(§2 참조). surface 계약("persisted payload 위 순수 렌더러") 부합 — recipe.json이 persisted 입력 | surface/__init__.py:1-5, service.py:322-326 온디맨드 선례 |
| A6 | `output/recipes_momentscan/` 21건 recipe.json | momentscan tests **특성화 골든 fixture**(선별본) | source.ref는 구 monolith 경로라 stale이나 **값은 구 어댑터의 유일한 실행 물증** → 포팅 완료 기준=tolerance 일치의 심판. C11 정정 각주(contracts.md:263 center=478×3, reshape(-1,3) 무해)도 특성화에 포함해 재확인 | openpilot 교훈: replay=byte 아닌 tolerance |
| A7 | tests 4종의 stub-랜드마크 검증 아이디어 | A2/A1 특성화 테스트 재료 | 파일 자체는 폐기, 스텁 설계만 승계 | — |

### (B) 우산·계약 승격 — 4건

| # | 자산 | 승격처 | 형태 | 근거 |
|---|---|---|---|---|
| B1 | **디자이너 리그 계약**: 13키 스키마(+오탈자 고정)·`head+base` 메시 그룹·blend 14 hair 메시 목록·1:1 매핑 선언·13 vs 14 문서 불일치 각주 | 우산 문서(예: `~/repo/p981/contracts/facerig.md` 또는 architecture.md 부록) — **기록이지 p981.if 버전 도장 아님** | 정본 포인터=momentscan 코드 상수(A4), 우산 문서=계약 서사·에셋 지문·소비자(디자인팀 blend) 관계만. p981.if 격상은 gen(sty-a1·d9) 실구현 시 — 지금 도장하면 소비자 없는 계약 | blender_export.py:49 오탈자 주석, blender_render.py:24-36 identity map 선언 |
| B2 | `~/Downloads/body+basic_260527.blend`(449M) + `body+basic.blend`(103M) | 우산 관리 에셋 홈(git 밖, 예: `~/repo/p981/assets/blender/`) + **sha256 지문을 B1 문서·bead에 기록** + 외부 백업 1부 | **삭제와 무관하게 지금 위험**(어느 git에도 없음, Downloads 소실=사슬 절단). D0 즉시 항목 | 자산 감사 §3-6 |
| B3 | 멤버 삭제 결정·dep 그래프 정리 | 우산 bead + `ids.md:150-154`(경계 밖 문단에서 appearance-engine 제거, face_recipe dep을 momentscan 내부 스테이지로) + `members.yaml:21-25` 행 제거·`:38-41` face-recipe dep 선언 갱신 | 멤버 삭제=우산 결정 원칙 | ids.md:153-154, members.yaml |
| B4 | 디자인팀 배송 이력(zip 4종+result_package_2nd, 2026-05-28~29 일회성) | bead 내 한 줄 이력(관계 종결 기록) | zip 실물은 C5 폐기 — 이력만 남김 | 소비자 감사 §1 "지속 피드 아님" |

### (C) 폐기 — 이유 명기

| # | 자산 | 이유 |
|---|---|---|
| C1 | `pipeline.py`·`collector.py`·`source.py`·`analysis.py`·`data/` 3파일 | 이미지-배치/visualpath 시대 기계. likeness 사슬 무관, momentscan 기능과 중복, 소비자 0 |
| C2 | `hair_retrieval.py`(434) + `output/hair_references/` 14 PNG | 검색 방향은 `../hair` hair_match가 승계(자체 렌더 사본 보유, appearance-engine 디렉토리 의존 0 — match_attr.py:19). 갤러리 PNG는 A5 흡수 후 blend에서 재생성 가능 |
| C3 | `component2/` 나머지 13파일(color·hair_color·accessories·clothing·face_parsing·qwen2vl·대안 분류기) | unfilled 51축 참조 구현이나 W(color_identity)·fashion은 momentscan 자체 구현 완료(fashion.py:4,52 — 흡수 전례이자 원조 격하 근거). 원장 ④는 **이미 방출된 C11 필드의 어댑터-측 소비 확장**이라 component2 불요. H/S축 Qwen 프롬프트+enum은 D4 아카이브에 잔존 — 재수요 시 복구 경로 |
| C4 | scripts 일회성 실험(qwen bald 2종·facellava 3종·visualize_phase1·extract_* 등)·`demo.py`·`demo_batch.py`·`build_recipes.py`·`package_design.py`·`build_axes_registry.py` 생성기 로직 | demo.py는 풀사슬 참조본으로 트랙 1·2 구현 중 참조 후 폐기(아카이브 잔존). 생성기는 sample_1 전제라 재사용 가치 없음 — 재캘리(원장 ①)는 momentscan 코퍼스 기준 새 도구가 소관 |
| C5 | `output/design_package_*` 4세트+zip(~330M)·`result_package_2nd` preview/recipe부 | **지인 사진=개인정보성**. git 미추적이라 레포 삭제 시 자동 소멸이나 **파기 의도를 bead에서 user 확인 후** 실행(자산 감사 체크리스트 항목 승계). raw 사진은 D4 아카이브에도 미포함(git bundle=tracked만이라 자동 제외됨 — 이 성질이 안전장치) |
| C6 | `output/result_package_2nd/raw/` 사진 사본 | 폐기 아니라 **이관**: hair_match 7스크립트의 하드코딩 입력(`{coarse_head,…}.py:13-21`) → hair 멤버 관리 하(예: `~/repo/p981/hair/data/`)로 이동+경로 갱신. **hair 세션 트랙 소관**(트랙-스코프 규율상 이 처분안에서 실행 안 함) |
| C7 | `output/demo_batch/`·`recipes/`·`test/`(~22M)·recipes_momentscan 비선별분·`.venv`(7.1G)·`utils/` 등 잔여 | sample_1 데모 산출·재생성물·환경. 아카이브 잔존으로 충분 |

폐기의 실행 형태: 삭제 직전 `git bundle`(14182ed 단일 커밋, tracked-only=개인정보 raw 자동 제외) 1파일을 우산 관리 하 보관 → 디렉토리 삭제. experiments.md:266-284 어댑터 경위는 momentscan 문서에 이미 있어 이관 불요.

---

## 2) 프리뷰 재구성 설계 (momentscan 내 최소 사슬)

```
likeness.json (C11 v1, validate_likeness 통과 레코드를 외부 소비자처럼 읽기만)
  │  스테이지 recipe (products/recipe.py) — analyzers 등재 depends=('likeness',)
  │  공식=perception/readings/face_axes.py(37축) · 정책/캘리=모듈 상수(A3)
  │  변환 규약: neutral>center → flip[1,-1,-1] → _PSEUDO_SCALE=200 → +16 (A1)
  ▼
recipe.json (per-rider 88축+unfilled 정직 보고+provenance; likeness outputs additive, egress 제외)
  │  surface/recipe_preview.py — 순수 렌더러 (persisted recipe.json 위)
  │  13키 투영(range-norm→mean, L/R 0.55) + HAIR_LIBRARY attribute 선택 + bpy 렌더
  ▼
per-subject PNG + 몽타주 (tier="surface" — tiers.py "appearance_card.png" 전례 옆 한 줄)
```

**등재 4점**
- analyzers: 스테이지 `recipe` 등재. Product 신설 없음 — likeness Product `outputs`에 recipe.json additive(egress 제외 → Result 반출·회사 대면·C11 v1 전부 무변).
- freshness: recipe.py·face_axes.py는 import 클로저 자동. 캘리=파이썬 상수라 값 수정→recipe만 stale(세밀 판정이 후보 i 채택의 핵심 배당). `.blend`는 `freshness._external_deps` lazy 등재(freshness.py:145-166 ONNX·canonical.obj 전례).
- bpy 선택-의존 사다리(boto3 전례 3단): 함수-내부 lazy import(cards.py:751-777 관례) / `verify/doctor.py` `optional=True` 행 추가(○ 경고) / CLI에서 부재 시 exit 2+설치 힌트(cli/surfaces.py:19-23 highlight-lang torch 전례). 프리뷰는 run 자동 렌더에 **넣지 않음** — report=자동·무거운 것=온디맨드라는 service.py:322-326 선례 그대로.
- CLI: `momentscan viz recipe <clip…> [--gain 2.2] [--calib recal|adapter] [--ab gain|calib]` — viz 애그리게이터 편입.

**L-B 판정 요구 충족**
- ① 4키 포화: recipe 스테이지가 캘리 양안(`registry 재캘리` vs `어댑터 보정`)을 파라미터로 노출, `--ab calib`가 두 벌 몽타주 생성. 양안 **구현**은 원장 ① (Phase L-A 4) 그대로 — 좌표만 momentscan으로 이동. **확정은 user 동행**(단독 확정 금지), 트랙 완료 기준에서 분리.
- ③ gain: 13키 투영에 gain 파라미터, `--ab gain`이 ×2.2 근방 A/B 몽타주 생성. 참조본=`output/l2/preview_recipe_gain_ab.png`(보존 — refactor-exec-plan.md:399 삭제·재생성 금지 우산 아래).

**원장 ②·①과의 관계**: 원장 ②(mpfb 브리지 재구성)는 이 설계로 **대체 이행** — 산출 요건은 "①③⑤ 판정 수단(recipe→프리뷰) 복구"이지 MPFB 자체가 아니며, bpy+디자이너 blend 정본이 요건을 충족. MPFB 재도입 없음, 잔존 몽타주 4장(preview_mpfb_*)은 판정 참조본으로 보존. `structure-audit-2026-07-15.md:102`의 "appearance-engine에 정식 착지" 문구는 user 결정으로 반전 — 트랙 1에서 문서 갱신. 원장 ①은 포팅 후 좌표에서 실행(흡수 선행이 순서 제약).

---

## 3) 삭제 전제조건 체크리스트 (살아있는 소비자별)

| 소비자 | 전제조건 | 판정 기준 |
|---|---|---|
| momentscan likeness 사슬(유일 코드 소비자, 역방향) | **D1** 트랙 1·2 착지 | 특성화: 신 recipe 출력이 골든 21건(A6)과 tolerance 일치 + unfilled 보고 동일 + verify registry green; 프리뷰: 몽타주 PNG 생성이 잔존 preview_*와 구도 동급 |
| hair_match 7스크립트 | **D2** result_package_2nd/raw 이관+경로 갱신(hair 세션 트랙) | 7스크립트가 신규 경로로 실행 가능(현재는 monolith 심링크 경유 해석 — 레포 삭제 시 즉사) |
| 디자인팀(사람) | **D3-a** 13키 계약 우산 기록(B1) + **D0** blend 2파일 sha256 확보(B2) | 배송 관계 종결 bead 기록; blend 소실 위험 해소 |
| gen·face-recipe(선언-만) | **D3-b** ids.md:150-154·members.yaml:21-25,38-41·contracts.md:195·refactor-exec-plan.md:13 참조 갱신 | "face_recipe 어댑터" 좌표가 momentscan 내부 스테이지를 가리킴; C11 형태 무변(문서 갱신은 additive) |
| C11 계약 자체 | 없음 — 무영향 | recipe.json 출력을 커버하는 p981.if.* 계약 부재 실측; 살아있는 계약 관계는 입력 방향뿐 |
| (안전망) | **D4** git bundle 아카이브(tracked-only) 우산 보관 · **D5** design_package 개인정보 산출물 파기 의도 user 확인(bead 항목) | bundle 생성 확인; user 확인 회신 |

**삭제 실행(D6)**: D0~D5 전부 green 후에만 — bead 회신 커밋 + members.yaml 제거 + ids.md dep 정리 + 디렉토리 삭제. 캘리 4키·gain **판정(L-B)은 삭제 전제조건이 아님** — 판정 재료(양안 구현+A/B 몽타주)가 momentscan에 있으면 appearance-engine은 불필요.

---

## 4) 트랙 분해

**momentscan 트랙 2개** (세션=한 트랙, track/<id> 브랜치, 머지 착지):

- **트랙 1 `track/lk-recipe`** (원장 ② 대체 전반부 + ④ 동승): `products/recipe.py` 스테이지 + `perception/readings/face_axes.py` + 캘리/정책 모듈 상수 + analyzers·tiers·freshness 등재 + 원장 ④(face_id·fashion·color_identity·samples additive 소비, stale docstring 정정) + 골든 fixture 반입 + 문서 갱신(contracts.md C11 소비자 표·structure-audit:102 반전 각주).
  완료 기준: ① 특성화 green(골든 21건 tolerance) ② verify registry green ③ 캘리 상수 수정 시 recipe만 stale(freshness 실증) ④ C11 소비가 읽기 전용(validate_likeness 경유)임을 코드 리뷰로 확인.
- **트랙 2 `track/lk-preview`** (원장 ② 대체 후반부): `surface/recipe_preview.py`(13키 투영+HAIR_LIBRARY 선택+bpy 렌더+몽타주+`--ab gain|calib`) + doctor optional 행 + CLI + `.blend` `_external_deps` 등재.
  완료 기준: ① bpy 환경에서 test 클립 몽타주 PNG 생성 ② bpy 부재 환경에서 exit 2 힌트+doctor ○ ③ `--ab gain` 출력이 잔존 preview_recipe_gain_ab.png와 비교 가능한 형식 ④ freshness가 blend mtime 변화를 인지.
- (후속, 삭제와 독립) 원장 ① 캘리 양안 구현 → L-B user-동행 판정 세션(①③ 일괄) — 기존 refactor-plan Phase L-A 4 → L-B 6·7 순서 그대로, 좌표만 이동.

**hair 트랙 1개** (hair 멤버 세션): raw_2nd 이관+7스크립트 경로 갱신(D2). HAIR_LIBRARY 지문 표는 momentscan이 정본이 되므로 hair_match 측 필요 발생 시 참조 방향만 기록.

**우산 bead 내용** (`git -C ~/repo/p981` 커밋, mailbox/momentscan.md 경유):
1. 결정문: appearance-engine 삭제(배울 것 소진 시) · 프리뷰 소관=momentscan(기존 "appearance-engine 정식 착지" 방향 반전 공지).
2. D0 즉시 항목: blend 2파일(449M/103M) Downloads→우산 에셋 홈+sha256+백업 — **삭제 일정과 무관, 지금 위험**.
3. 전제조건 D1~D5 체크리스트(§3)와 소관 배정(D1=momentscan 트랙 2개, D2=hair 트랙, D3=우산 문서, D4·D6=우산 실행).
4. user 확인 요청 2건: (a) design_package_* 지인 사진 ~330M 파기 의도(D5) (b) face-recipe README 스텁의 후속 처분(dep 선언 갱신만 vs 스텁 자체 폐기 — 기록만, 이번 범위 밖).
5. 디자이너 13키 계약 기록 위치(B1)와 "p981.if 격상은 gen 실구현 시" 유보 선언.

**원칙 준수 확인**: 비밀 2종(공식=readings/정책·캘리=products 상수 분리) · 엔진=질문(Product 신설 없음) · 껍질(recipe.json egress 제외 — 반출·채점기 무접촉) · 비목표 원장(13키 p981.if 격상 보류=소비자 선행 원칙; recipe 스테이지 신설 비용은 원장 ②가 지불) · C11 v1 additive-only(소비 확장·outputs 추가·문서 갱신 전부 additive).

수정한 파일 없음(읽기 전용 실측·설계). 주요 좌표: `/home/hyeonrae/repo/p981/momentscan/apps/momentscan/src/momentscan/{products,surface,perception,infra/pipeline}` · `/home/hyeonrae/repo/p981/momentscan/docs/refactor-plan.md:148-156` · `/home/hyeonrae/repo/p981/ids.md:58,150-154` · `/home/hyeonrae/repo/p981/appearance-engine/src/appearance_engine/`.
---

## 개정 (user 교정, 2026-07-20): C5 파기 → 보관

**지인 사진 = 테스트 픽스처.** 디자인팀이 가끔 "이 사람에 대해 출력 테스트"를
요청 — 시스템은 비디오 타겟이지만 **이미지 수준 평가 요구가 실재**한다.
- C5 처분 변경: design_package raw 사진 = **파기 금지, 보관** — appearance-engine
  삭제 전에 우산 관리 에셋 홈(git 밖, blend 파일 D0과 동거 — 개인정보라 접근
  통제)으로 이관. C6(hair 이관분)과 단일 홈 조율(사진 세트는 hair_match 입력과
  디자인팀 테스트 요청의 이중 용도).
- **신규 관측 (원장 후보)**: "이미지 1장 → recipe/프리뷰" 요청 레인 — 현 흡수
  설계의 recipe 스테이지는 likeness.json(비디오 산출)을 입력으로 하므로, 이미지
  요청에는 이미지→likeness-lite 경로(단일 프레임 랜드마크→center/blendshapes
  유사 레코드)가 필요. **지금 짓지 않음**(가끔-요청, 소비자-선행 원칙) — 요청이
  다시 오는 시점에 lk-preview 위에 소형 레인으로. change-forecast 비목표 원장에
  재개 조건("디자인팀 이미지 테스트 요청 도착 시")으로 등재.

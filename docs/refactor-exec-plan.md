# momentscan 리팩토링 실행 계획 (2026-07-07)

**계획만. 코드 변경 없음. 실행자는 이 문서 + 코드만으로 완주할 수 있어야 한다.**
경로 기준: 레포 루트 = `/home/hyeonrae/repo/monolith/momentscan`, 패키지 =
`apps/momentscan/src/momentscan/`. ID는 `docs/ids.md`(M/V/P/C)를 따른다.

---

## 1. 현재 이해 (실행자 컨텍스트)

momentscan = 놀이기구 탑승 영상 1클립 → 세 제품을 뽑는 배치 파이프라인.
- **P1 likeness**(알파 오픈): 방문-스코프 외형 ID → likeness.json (스키마 동결 C11,
  `momentscan.likeness/v1`). 소비자 = ../appearance-engine의 face_recipe 어댑터.
- **P2 portrait / P3 highlight**(내부): 대표 컷 / 하이라이트 세그.
- 실행 경로 둘: CLI `momentscan run <clip>` / HTTP 서비스(`server start`, C1 Job/Result,
  Eureka 등록, 멱등 result.json).
- 파이프라인 = `pipeline.py`의 RUNNERS(M01~M12, :111-124) + `analyzers.py`의 선언 DAG
  (topo 순서·의존의 단일 정본). resumability = "산출물 존재 && 코드 fresh → skip"
  (`freshness.py`: 스테이지 모듈의 transitive import 클로저 mtime).
- 검증 자산(전부 CLI): `momentscan verify registry`(선언 drift, 0 err 기준) /
  `verify api`(openapi.yaml 계약 19항목) / `verify replay <clip>`(CPU 스테이지 frozen
  입력 재실행 byte-diff). **pytest 부재. CI 부재. ruff/mypy 부재. uv.lock은 존재.**
- 코퍼스 = `output/l2/`의 15클립(test_0…251227002408802). GPU 스테이지(M05 scene,
  M09 fashion, M11 emotion 등)는 모델 필요 — replay는 CPU 스테이지만 커버.

## 2. 기존 방향의 논리적 헛점 (이 계획이 겨냥하는 것)

| # | 헛점 | 증거 | 대응 항목 |
|---|---|---|---|
| L1 | **freshness 계약 불완전** — "freshness=런의 속성"이라 선언했으나 코드-mtime만 보고 **상류 산출물 갱신을 안 봄**. detections를 재기록해도 하류가 skip | 동일 사고 3회 실증(세션 기록), pipeline.py:204-210 | R5 |
| L2 | **enforcement 절반** — openpilot 교훈("갭=아키텍처 아닌 enforcement")을 받아 verify CLI는 만들었으나 **아무도 자동으로 안 돌림**. 사람이 기억해야 하는 검증 = 침묵 회귀 | pytest/CI 부재 | R2 |
| L3 | **동결 ≠ 검증** — C11은 문서+`schema` 문자열 도장뿐, 기계 검증 없음. 회사가 소비할 페이로드의 위반이 소비자 측 런타임에서야 발견됨 | products/likeness.py에 검증 없음 | R6 |
| L4 | **조용한 무시** — `run --only <오타>`가 에러 없이 전 스테이지를 건너뜀(오늘 실증: "appearance" 오타로 재계산 누락) | pipeline.py:182-183 | R3 |
| L5 | **침묵 열화** — `_gate_cohorts`/`_face_ids`의 `except Exception: return {}`: cohort 없이 진행하면 품질이 떨어진 산출물이 *정상처럼* 나옴. "정직한 실패 모드" 원칙과 모순 | products/likeness.py:300 등 | R4 |
| L6 | **정책 상수 산개** — C9 preset은 "자리"로만 존재. 임계값들이 likeness.py(`_F_*`)·gates.py·highlight.py에 흩어짐 → 다른 시설/기구로 이식 시 코드 수정 필요 | 각 파일 상수 | R8(인벤토리) |
| L7 | **버전 도장 비대칭** — likeness.json만 schema 필드 보유. portrait/highlight/gate_trace는 알고리즘 버전이 바뀌어도 산출물에 흔적이 없음(레거시 stale-오신뢰 사고의 원류) | 각 제품 write | R7 |
| L8 | **GPU 스테이지 검증 공백** — replay는 CPU만. M09/M11 변경은 육안 diff 의존 | verify/replay 구현 | R2의 특성화 테스트가 산출물 수준에서 완화 |

## 3. 사용 용이성 제안 (실행자 범위 밖 — 소유자 결정용 기록)

- **C11의 JSON Schema 파일 공개**(`docs/api/likeness.schema.json`): 회사 소비자가
  자기 쪽에서 기계 검증 가능. R6의 검증 모델에서 자동 생성 가능(msgspec→json-schema).
- **quickstart 한 장**: `README.md`에 ①`momentscan run <video.mp4>` 한 방(이미 동작)
  ②서비스 curl 3줄(POST /jobs → poll → report_url) ③`/docs` Swagger 안내. 신뢰 축 =
  report_url(사람용)과 result.json(기계용)이 같은 사실을 가리킨다는 것.
- **에러의 행동 지침화**: failure 레코드(stage+error)는 이미 좋음. `doctor`를
  quickstart 1단계로 못박기.
- ids.md를 `momentscan map` 출력에 병기(M/V/P ID 노출)하면 대화-지칭이 코드 표면과
  일치 — 소형 후속.
- **배송 풀해상도 재크롭(L13)**: 서비스 배송 단계에서 portrait 대표컷·highlight
  세그를 source_cache의 원본으로부터 재추출(분석=크롭트랙 유지, 배송만 원본).
  제품 체감 품질 직결 — visualbase 의도의 올바른 착지점. 기능 추가라 소유자 결정.

## 4. 파이썬 생태계 안정성 점검 (채택/기각 근거)

| 도구 | 판단 | 근거 |
|---|---|---|
| **pytest + hypothesis** | 채택 (R2) | 특성화 테스트 + `signals.canonicalize` 속성 검증(det=+1, RMS=1)은 property-based가 정확히 맞는 자리. hypothesis는 dev-dep |
| **msgspec** | 채택 (R6) | C11/Result 기계 검증. 순수 C 확장·의존 0·`Struct`→JSON Schema 생성 가능. pydantic보다 AK-47 정신에 부합 |
| **ruff** | 채택, 검사만 (R9) | 미래 편집 가드레일. **전면 리포맷 금지**(diff 오염) — baseline 카운트 기록 후 신규 위반만 막는 용도 |
| pydantic | 기각 | msgspec으로 충분, 무겁다 |
| structlog | 기각 | 자체 구조화 JSON 로깅이 이미 Loki 계약에 맞춰져 있음 |
| tenacity/retry | 기각 | stdlib로 충분, 서비스는 이미 멱등 |
| pre-commit | 보류 | CI 부재 상태에선 로컬 훅이 유일한 강제선이나, 팀 합의 필요 |

## 5. 안전망 (항목 R0 — 반드시 먼저)

1. `git status` 클린 확인. 더럽다면 중단하고 보고.
2. 기준 커밋: `git add -A && git commit -m "checkpoint before refactor-exec-plan"` —
   ⚠ **커밋 메시지에 Claude co-author 트레일러 금지, `-m`에 백틱 금지**(셸 치환 사고
   이력). 여러 줄이면 파일로 써서 `-F` 사용.
3. 기준 검증 3종 실행·결과 기록(이 값이 전 항목의 회귀 기준):
   ```
   .venv/bin/momentscan verify registry   # 기대: 0 error(s), 1 warning(s) (scene 경고는 기존)
   .venv/bin/momentscan verify api        # 기대: api-check: 19/19 통과
   .venv/bin/momentscan verify replay test_3 --out output/l2   # 기대: drift 0
   ```
4. 특성화 기준값(→ R2에서 테스트로 전환). 모두 `output/l2/test_3/likeness.json` 기준:
   - `schema == "momentscan.likeness/v1"`; `riders` 키 == `{"0"}`; `riders["0"].role == "main"`
   - `riders["0"].n_obs == 648`; `face_id.coherence_p05 == 0.752 (±1e-3)`;
     `face_id.low_confidence is False`
   - `fashion.mask is False`; `fashion.mask_override is None`
   - `samples.hair == {"visible_frac": 0.881, "n_frames": 12, "observable": True}`
   - `color_identity.primary.hex == "#140e11"`
   - `separation`은 리스트이고 각 항에 `tracks/dist/ratio_vs_drift` 키
   - run.json: `stages`에 M01~M12 이름 존재(전부 skipped여도 됨)
   - dual_3: `riders["0"].fashion.mask is False` **and** `mask_override.winner == "scarf"`
   - mask_2: `riders["0"].fashion.mask is True`
   - test_12: `riders["0"].samples.hair.observable is False`

## 6. 작업 항목 (실행 순서)

### R1 — `--only` 오타를 에러로
- **위치**: `apps/momentscan/src/momentscan/pipeline.py:182-183`
- **문제**: 미지 스테이지명이 조용히 필터-아웃 → 아무것도 안 돌고 성공처럼 끝남 (L4).
- **방법**:
  ```python
  if only:
      known = {a.name for a in order} | set(UPSTREAM_OF_RUNNER)
      unknown = [n for n in only if n not in known]
      if unknown:
          raise ValueError(f"unknown stage(s) {unknown}; valid: {sorted(known)}")
      order = [a for a in order if a.name in only]
  ```
  (UPSTREAM_OF_RUNNER 집합이 파일 상단에 있음 — 이름만 허용 목록에 포함, 실행은 불변.)
- **완료 기준**: `momentscan run test_3 --out output/l2 --only appearance` → 비-0 종료
  + 메시지에 `likeness` 포함. `--only likeness` → 기존과 동일 동작(1 ran).
- **위험/복원**: service.py는 only 미사용(grep으로 확인) → 영향 없음. 실패 시 revert.
- **의존**: R0.

### R2 — pytest 도입 + 특성화 테스트 + 속성 테스트
- **위치**: 신규 `apps/momentscan/tests/` (`test_characterization.py`,
  `test_canonicalize.py`, `test_verify_wrappers.py`), `pyproject.toml`(dev-deps).
- **문제**: L2 — 검증이 사람 기억에 의존.
- **방법**: ① `uv add --dev pytest hypothesis` ② R0-4의 기준값을 assert로 옮긴
  `test_characterization.py`(파일 없으면 `pytest.skip("corpus not present")`) ③
  `test_canonicalize.py`: hypothesis로 (N,468,3) 랜덤 + 유효 transform 생성 →
  `signals.canonicalize` 결과의 회전행렬 det≈+1, RMS≈1.0 (±1e-6) 단언 ④
  `test_verify_wrappers.py`: `subprocess`로 verify registry/api 실행, 종료코드 0 단언.
- **완료 기준**: `uv run pytest apps/momentscan/tests -q` → all passed (코퍼스 있는
  로컬 기준). 코퍼스 없는 환경에서는 특성화만 skip.
- **위험/복원**: 프로덕션 코드 무변경(추가만). revert 자유.
- **의존**: R0.

### R3 — 침묵 열화에 로그 (P1 경로)
- **위치**: `products/likeness.py` — `_gate_cohorts`의 `except Exception: return {}`
  (:300 부근), `_face_ids`의 조기 `return {}` 경로, `_fashion_reading`의
  `read_parse → None` 경로.
- **문제**: L5 — degrade가 관측 불가.
- **방법**: 각 지점에 `log.warning("likeness.degraded", extra={"clip_id": clip_id,
  "lane": "<gate_cohorts|face_ids|fashion>", "reason": str(e) 또는 "artifact missing"})`
  1줄씩. 반환값·제어 흐름 불변.
- **완료 기준**: `uv run pytest`(R2) 전부 통과 + `momentscan run test_3 --only likeness
  --force` 후 likeness.json이 R0 기준값과 동일(로그만 추가되었으므로).
- **위험/복원**: 없음/revert. **의존**: R2.

### R4 — portrait/highlight 산출물에 schema 도장
- **위치**: `products/portrait.py`(portrait.json 조립부), `products/highlight.py`
  (highlight.json 조립부).
- **문제**: L7 — 버전 무표식 산출물.
- **방법**: 각 레코드 최상위에 `"schema": "momentscan.portrait/v0"` /
  `"momentscan.highlight/v0"` 추가(v0 = 미동결 표기). contracts.md C11 아래에 두 줄
  각주 추가: "v0 = 스키마 미동결, 필드는 예고 없이 변경될 수 있음".
- **완료 기준**: `momentscan run test_3 --only portrait highlight --force` 후 두 JSON에
  schema 키 존재, report/inspector 렌더 정상(`momentscan report test_3` 비-0 아님).
- **위험/복원**: 소비자는 dict.get 접근이라 additive 안전. revert 자유. **의존**: R2.

### R5 — artifact-edge freshness (핵심 수리)
- **위치**: `pipeline.py:204-210`(skip 블록) + `freshness.py`(헬퍼 추가).
- **문제**: L1 — 상류 산출물 갱신이 하류를 stale시키지 못함(사고 3회).
- **방법**: ① analyzers.py의 선언 의존에서 **직접 상류 산출물 경로**를 끌어온다:
  RUNNERS에 있는 상류는 그 probe, RUNNERS 밖 상류(detect 등)는 신규 매핑
  `UPSTREAM_ARTIFACTS = {"detect": ["detections.parquet", "landmarks.parquet"], ...}`
  (analyzers.py의 의존 선언을 열어 정확한 이름으로 작성). ② skip 판정에 추가:
  ```python
  up = [cdir / p for p in upstream_probes(a.name) if (cdir / p).exists()]
  art = cdir / probe
  if any(u.stat().st_mtime > art.stat().st_mtime + 1e-6 for u in up):
      stale = True; stale_why = "upstream artifact newer"
  ```
  기존 코드-mtime stale과 OR. run.json reason에 stale_why 반영.
- **완료 기준**: ① 연속 2회 `momentscan run test_3 --out output/l2` → 2회차 전부
  `cached (fresh)` (거짓-stale 없음) ② `touch output/l2/test_3/detections.parquet` 후
  run → detections 소비 스테이지들이 재실행(run.json reason="upstream artifact newer")
  ③ `uv run pytest` 통과 ④ `verify replay test_3` drift 0.
- **위험**: 거짓-stale 연쇄(형제 스테이지가 공유 파일을 만질 때). **직접 의존만** 보고,
  완료 기준 ①이 그 가드. 실패 시: 이 커밋만 revert하면 기존 skip 의미로 복귀.
- **의존**: R2 (테스트 그물 위에서 수행).

### R6 — C11·Result 기계 검증 (msgspec)
- **위치**: 신규 `apps/momentscan/src/momentscan/contracts.py`;
  `products/likeness.py`의 `write_appearance` 직전; `service.py`의 deliver 직전.
- **문제**: L3 — 계약 위반이 소비자 측에서 발견됨.
- **방법**: ① `uv add msgspec` ② `contracts.py`에 msgspec.Struct로 LikenessV1(필수:
  schema/clip_id/riders{role,n_obs,center(1404 float),face_id,fashion,samples}·
  separation)과 ResultV1(C1의 필수 키) 정의 — **contracts.md C11 표의 ✔ 필드만 필수,
  나머지는 Optional** ③ 쓰기 직전 `msgspec.convert(record, LikenessV1)` 시도, 실패 시
  raise(멈추는 게 계약임 — 조용한 위반 배송 금지) ④ `momentscan verify api`에 검증
  활성 여부 1항목 추가(20번째).
- **완료 기준**: 코퍼스 15클립 `--only likeness --force` 전부 성공(기존 산출물이 모델을
  통과함을 증명) + 필드 하나 제거한 사본으로 단위 테스트에서 raise 확인
  (`tests/test_contracts.py::test_likeness_missing_field_raises`) + api-check 20/20.
- **위험**: 모델이 실제보다 엄격하면 정상 런이 죽음 → 완료 기준의 15/15가 가드.
  실패 시 검증 호출 1줄만 주석 처리해도 복귀(모델 파일은 무해).
- **의존**: R2, R5.

### R7 — gate_trace에 버전 컬럼
- **위치**: `gates.py`의 gate_trace.parquet 기록부.
- **문제**: L7 잔여 — 게이트 정책 변경이 trace에 무표식.
- **방법**: 상수 `GATE_POLICY = "v2026-06-30"`(clean_ref 극성 잠금일) 추가, trace에
  동일 값 컬럼 1개. 완료 기준: 재실행 후 컬럼 존재 + `verify replay` drift 0(replay가
  컬럼 추가를 diff로 보면 기준 재생성 절차를 replay 문서대로 수행).
- **위험/복원**: 낮음/revert. **의존**: R5.

### R8 — 임계값 인벤토리 (이동 금지, 조사만)
- **위치**: 신규 `docs/preset-inventory.md`.
- **문제**: L6 — C9 preset을 지을 때 무엇을 옮길지 지도가 없음.
- **방법**: `grep -n "TAU\|FLOOR\|_F_\|THRESH\|= 0\.\|_MIN\|_MAX" `를 products/·gates.py·
  extraction/에 돌려 **파일:라인·이름·값·의미·소비자** 5열 표로 정리. 코드 무변경.
- **완료 기준**: 표에 최소 25행, 각 행에 5열 전부. `git diff --stat`이 docs만.
- **위험**: 없음. **의존**: 없음(순서 자유).

### R9 — ruff 도입 (검사만)
- **위치**: `pyproject.toml`.
- **문제**: 편집 가드레일 부재.
- **방법**: `uv add --dev ruff`; `[tool.ruff]`에 `line-length = 100`,
  `lint.select = ["E","F","W","I","B"]`, `lint.ignore`는 첫 실행에서 대량 발생하는
  코드 3개까지 명시적으로 추가(예: E501). `uv run ruff check apps/momentscan --statistics`
  결과를 이 파일 하단에 baseline으로 기록.
- **완료 기준**: ruff check 종료코드 0 (ignore 조정으로) + **소스 파일 diff 0**.
- **위험**: 없음(설정만). **의존**: 없음.

## 6b. 제품 수직 분리 검토 (2026-07-07 추가 — user 제안 편입)

**제안 요지**: P1/P2/P3은 공통 기판을 공유하되 계산 방식이 전혀 다르다. stash가
중간값을 들고 있으니 "필요한 stash 없으면 계산, 있으면 재활용"으로 **제품별
수요-주도 실행**이 가능해야 하고, 디버그 시각화도 제품별로 분리, 산출물도
최종/중간 구분이 명확해야 한다.

**검토 판정: 타당하며, 구조가 이미 절반을 갖고 있다** — analyzers.py 선언 DAG(의존
정본)+stash resumability가 있으므로 closure(P)를 파생해 그 부분그래프만 돌리면
된다. 단, 제안이 드러낸 **추가 헛점 3개**:

| # | 헛점 | 증거 |
|---|---|---|
| L9 | **P1→P2 숨은 결합**: gate_trace.parquet(V01~V05의 판정)을 **portrait 실행기가 생산**(portrait.py:427)하고 likeness가 소비(likeness.py:53). 전체-캐스케이드가 항상 돌아서 은폐돼 있었음. 제품 분리 시 closure(P1)이 P2를 끌어들이는 오류가 됨 | grep 확정 |
| L10 | **전량-계산 낭비**: 서비스가 products=[likeness]여도 13 스테이지 전부 실행. closure(P1)={M01,M02,M03,M06,M07,M08,M09,+gates} — scene(M05)·headpose6d(M10)·emotion(M11)·select(M12) 불필요. 2000 vids/day에서 GPU 낭비 실질적 | likeness.py의 read_* 목록 |
| L11 | **stash 평면 산개**: clip 디렉토리에 기판(parquet)·제품(json)·표면(html/png)·운영(run/provenance/result)이 한 층에 섞임. 최종/중간 구분이 파일명 지식에 의존 | output/l2/* 목록 |

### R10 — gates 스테이지 독립 (L9 수리; R11의 전제)
- **위치**: `products/portrait.py`(PASS 1 게이트 평가+write_gate_trace :427 부근을 분리),
  신규 `extraction/` 또는 `gates.py`에 스테이지 진입 함수, `pipeline.py` RUNNERS에
  `"gates": ("gate_trace.parquet", _gates)` 추가(M09 뒤·제품들 앞), `analyzers.py`에
  선언 추가(likeness/portrait의 의존을 gates로 갱신).
- **문제**: 게이트는 측정(V01~V05)인데 제품 실행기 안에 살아 P1←P2 결합.
- **방법**: portrait.py의 게이트 평가 블록을 함수로 추출해 스테이지로 등록. portrait은
  read_gate_trace로 전환(자기 재평가 삭제). **행동 불변이 목표** — 같은 입력, 같은
  gate_trace 바이트.
- **완료 기준**: `--force` 전체 재실행 후 ①gate_trace.parquet가 기존과 **byte-identical**
  (`cmp` 또는 parquet 정렬-후 diff) ②run.json에 gates 스테이지 등장 ③특성화 테스트
  전부 통과 ④`verify replay test_3` drift 0.
- **위험/복원**: 추출 시 평가 순서·시드가 바뀌면 trace가 달라짐 → byte 비교가 가드.
  실패 시 커밋 revert. **의존**: R2, R5.

### R11 — 제품 closure 실행 (`run --product`)
- **위치**: `pipeline.py` run_pipeline(only 파라미터 인접), `__main__.py`(run 파서),
  `service.py`(Job.products → closure 합집합).
- **문제**: L10.
- **방법**: `closure(p) = analyzers 선언 DAG에서 p의 상류 전체` 파생 함수 추가 →
  `--product likeness|portrait|highlight`(복수 허용)가 order를 closure 합집합으로
  제한. `--only`(스테이지 지정)와 상호배타. service는 job.products를 그대로 전달.
- **완료 기준**: ①깨끗한 사본 클립에서 `run <clip> --product likeness` → run.json의
  ran ⊆ {detect,stitch,attribute,tubelets,features,crops,parse,fashion,gates,likeness}
  이고 scene/emotion/headpose6d/select **부재** ②그 likeness.json이 전체-런 산출과
  동일(특성화 값 비교) ③서비스 e2e: products=[likeness] 잡이 동일 결과.
- **위험/복원**: closure 누락(숨은 read_*)이면 스테이지가 결측 artifact로 실패 —
  L4 수리(R1) 덕에 조용히 안 죽고 드러남. analyzers 선언과 실제 read_*의 괴리가
  있으면 선언을 고치는 것이 수리(선언=정본). revert 자유. **의존**: R10.

### R12 — 산출물 tier 선언 (L11 1단계: 물리 이동 없이 논리 구분)
- **위치**: `analyzers.py`(각 선언에 `tier: "substrate"|"product"|"surface"|"ops"` 필드),
  `verify/registry` 체크 추가, `momentscan map cascade`·report의 파일 목록을 tier
  그룹으로 렌더, per-clip `manifest.json`에 {파일→tier} 기록.
- **완료 기준**: registry 0 err(전 산출물 tier 보유) + report 하단 목록이 4그룹 표시
  + manifest.json 존재.
- **위험**: 없음(선언+렌더). **의존**: R2.
- **⚠물리 재배치(stash/·products/·surface/ 하위 디렉토리로 이동)는 이 계획에서 제외**
  — 기존 코퍼스·replay 기준·모든 read_* 경로·서비스 egress를 깨는 마이그레이션이라
  별도 결정 필요. R12의 tier 선언이 그 마이그레이션의 지도가 된다.

### R13 — 제품별 디버그 페이지 분리
- **위치**: `surface/report.py`·`cards.py` — 단일 index.html에서 제품 섹션을
  `report_p1.html`/`report_p2.html`/`report_p3.html`로 분리, 공통 기판(타임라인·
  게이트 사다리·M-스테이지 상태)은 `report_substrate.html`, index.html은 4링크+
  요약만. products_open 잠금 배지 로직은 페이지 단위로 이동.
- **완료 기준**: `momentscan report test_3` 후 5파일 존재·각각 브라우저 렌더 정상,
  result.json 있는 클립에서 미오픈 제품 페이지에 잠금 배지, 인스펙터(한-런 창)는
  변경 없음.
- **위험/복원**: 렌더 전용, revert 자유. **의존**: R12(그룹화 재사용).

## 6c. substrate 활용 점검 (visualpath / visualbase — 2026-07-07 추가)

**의도(설계 당시)**: visualpath = 분석 모듈 플러그인 슬롯·관계 선언→해석 실행·환경
격리. visualbase(visualstack 실멤버로는 visualbus/visualbind가 근연) = 원본 미디어
기판 — 분석기에 분석용 미디어 제공 + **분석 결과를 트리거로 원본을 편집/메시지
처리하는 액션 미들웨어**.

**실사용 현황** (⚠2026-07-07 정정 — 초판은 visualbus 사용을 놓쳤음):
- **visualpath**: M01 detect 내부(frame-bus 2모듈: FaceDetect→IoUTracker,
  detect.py:37-38)와 M03의 DepthEstimator 플러그인뿐. M04~M12는 자체 RUNNERS/
  analyzers.py 선언으로 재발명.
- **visualbus: 광범위 직접 사용 — 사실상 momentscan의 최심층 substrate.**
  ①미디어 소스 기판: `FileSource`가 원본 접근의 표준 경로(detect·ingest·attribute·
  tubelets·surface/cards 전부), `VideoFileSink`(detect.mp4), `DrawText/DrawBBox/
  apply_hint`(렌더), `VisualBus`(detect의 버스) ②제어면: daemon.py=visualbus의
  `ControlServer`(UDS JSON-lines RPC), server 명령=`visualbus.control.call`
  ③구조화 로깅: `visualbus.structured_log`(setup_logging/log_context)가 전 로깅·
  Loki 계약의 기반 ④규약: stash.py bbox가 visualbus.BBox convention, timestamp
  유틸. media.py는 크롭 산술 등 소형 보조일 뿐 소스 접근 기판이 아님.
- visualbus에서 **안 쓰는 것**: pub/sub 버스 본체의 detect-밖 사용, 그리고
  **액션 미들웨어 역할**(결과 트리거→원본 편집/메시지) — 제품 픽셀은 전부 분석
  스트림에서(portrait=크롭트랙, portrait.py:162). L13은 이 절반에 대한 것.

**판정**:
- **집행 이원화는 옳다(유지)**: frame-domain(스트리밍 bus)과 artifact-domain(클립
  배치+resumability)은 실행 체제가 다르고 visualpath는 전자용. 레거시(portrait981)
  붕괴가 과-아키텍처에서 왔으므로 M-스테이지를 플러그인 슬롯에 강제 편입하는 것은
  역행. 단, 대가로 잃은 것을 명시 보류로 기록:
  | # | 잃은 것 | 처분 |
  |---|---|---|
  | L12 | 선언 이원화 잔여 — verify/graph.py가 렌더로 봉합했으나 detect 내부가 hand-list(`DETECT_INTERNALS` 상수)라 실제 visualpath Pipeline 구성과 어긋나도 모름; 환경(네이티브 크래시) 격리 미착수 | **R14**(drift-test) / 격리는 의도적 보류 |
  | L13 | **배송 품질 천장 = 분석 해상도** — visualbase의 "결과 트리거→원본 편집" 역할 부재로 portrait/highlight 픽셀이 fps6·크롭 해상도에 갇힘. 서비스 잡 시점엔 원본이 source_cache에 **있으므로**(fetch 직후) 풀해상도 재크롭이 retention 결정(소스 ~1주 만료→크롭트랙 영속)과 모순 없이 가능 | §3 소유자 결정 항목(기능 추가라 실행자 범위 밖) |
- **"visualbase" 의도의 현재 지형**: 미디어-기판 절반은 **visualbus로 이미 실현**
  (FileSource가 전 소스 접근의 표준 경로). 액션 미들웨어 절반 중 배송·리포트·메시지
  자리는 C1 서비스(collect_egress/deliver, transport-agnostic)에 착지. 남은 것은
  L13(원본 재접근 편집)뿐이며, 별도 패키지가 아니라 서비스 배송 단계의 후처리로
  들어가는 것이 맞다 — 구현 시 visualbus FileSource를 그대로 쓰면 규약 일관.

**경계의 정본 = contracts.md §C12** (2026-07-07 신설): momentscan↔visualstack 사용
표면 전체가 임포트 화이트리스트로 명문화됨(공개 API만·frame-domain 한정·역류 금지·
졸업 경로). R15가 그 enforcement.

### R15 — C12 경계 테스트 (visualstack 임포트 화이트리스트 enforcement)
- **위치**: `apps/momentscan/tests/test_substrate_boundary.py`(신규).
- **문제**: C12 화이트리스트가 문서뿐이면 새 임포트가 조용히 경계를 넓힌다.
- **방법**: 테스트가 `apps/momentscan/src/momentscan/**/*.py`를 AST 파싱해
  `visualbus`/`visualpath`/`visualbind`로 시작하는 모든 임포트를 (모듈경로, 임포트명)
  으로 수집 → C12 표를 그대로 옮긴 상수 `ALLOWED: dict[str, set[str]]`(파일→허용
  임포트 집합)와 비교. 초과분 발견 시 "C12 갱신과 함께만 추가하라"는 메시지로 실패.
  밑줄-내부 모듈(`visualbus._*`) 임포트는 무조건 실패.
- **완료 기준**: `uv run pytest apps/momentscan/tests/test_substrate_boundary.py -q`
  통과; detect.py에 가짜 `from visualbus import Foo` 추가 시 실패 확인 후 복원.
- **위험/복원**: 추가 전용/revert. **의존**: R2.

### R14 — detect 내부 선언 drift-test (L12 소형 수리)
- **위치**: `apps/momentscan/tests/test_graph_drift.py`(신규), 참조:
  `verify/graph.py:26-28`(DETECT_INTERNALS 하드코딩), `extraction/detect.py:37-38`.
- **문제**: hand-list된 detect 내부 표현이 실제 visualpath Pipeline 구성과 어긋나도
  침묵.
- **방법**: 테스트에서 detect.py가 구성하는 Pipeline의 모듈 클래스명 시퀀스를
  introspect(임포트만, 실행 없음 — `FaceDetect`/`IoUTracker` 임포트 가능성은
  visualpath 설치 여부에 따라 `pytest.importorskip("visualpath")`)하여
  `graph.DETECT_INTERNALS` 문자열과 일치 단언.
- **완료 기준**: `uv run pytest apps/momentscan/tests/test_graph_drift.py -q` 통과;
  DETECT_INTERNALS를 일부러 바꾸면 실패하는지 1회 확인 후 복원.
- **위험/복원**: 추가 전용/revert. **의존**: R2.

## 7. 하지 말아야 할 것

- 기능 추가 금지(§3 사용성 제안 포함 — 소유자 결정 대기).
- **전면 리포맷/일괄 rename 금지**(ruff format, isort 일괄 적용 금지).
- 의존 라이브러리 버전 업데이트 금지(uv.lock의 기존 핀 유지; 추가만 허용된 항목에서).
- `output/l2/` 코퍼스 삭제·재생성 금지(기준값의 원천).
- momentscan 커밋에 Claude co-author 트레일러 금지.
- `_legacy/`·`experiments/`·`../appearance-engine`·`../hair` 수정 금지.
- 스키마 의미 변경 금지(C11 additive 규율 — 필드 제거/개명은 v2 절차).
- 서버 원격 shutdown 엔드포인트 추가 금지(의도적 부재).

## 8. 실행자 지침 (복사-붙여넣기용)

> momentscan 리팩토링을 `docs/refactor-exec-plan.md`대로 수행하라.
> 1. R0(안전망)을 먼저 실행하고 기준 검증 3종의 실제 출력을 기록하라.
> 2. 항목은 **한 번에 하나**, 순서 R1→R2→R3→R4→R5→R6→R7→**R10→R11→R12→R13**→R8→R9.
> 3. 각 항목 완료 시 **그 항목만 담은 커밋 1개**(메시지 앞에 항목 ID, 예:
>    "R5: artifact-edge freshness"). co-author 트레일러 금지, 백틱 금지.
> 4. 각 항목의 "완료 기준" 명령을 실행해 예상 결과와 대조하라. 불일치하면
>    **중단하고 현재 상태·명령 출력·의심 원인을 보고**하라. 다음 항목으로 넘어가지 마라.
> 5. 매 항목 후 `uv run pytest apps/momentscan/tests -q`(R2 이후)와
>    `momentscan verify registry`가 깨끗한지 확인하라.
> 6. §7 "하지 말아야 할 것"은 선의라도 위반 금지.

## 9. 계획 자체 검증 (순서 추적)

R1(파서 가드)은 이후 항목의 어떤 명령도 바꾸지 않음(전부 유효 스테이지명 사용) →
R2는 추가-전용 → R3·R4는 R2의 테스트가 회귀 그물(R4의 schema 키는 특성화 테스트가
키 "부재"를 단언하지 않으므로 충돌 없음 — R0-4 기준값은 존재 필드만 단언) →
R5는 mtime 비교 추가라 R2 특성화(값 단언)와 독립, 완료 기준 ①이 무한 재실행 가드 →
R6은 R5 뒤라 --force 재실행이 신선한 파이프에서 수행됨 → R7의 컬럼 추가는 replay
기준 재생성 절차 필요를 항목 내 명시 → **R10은 gate_trace byte-identical이 가드라
R2 특성화·R7 버전 컬럼과 충돌 없음(R7이 먼저면 R10의 byte 비교는 R7-이후 기준으로)
→ R11은 R10이 만든 gates 스테이지를 closure에 포함(전제 충족) → R12는 선언 추가라
R11의 closure 파생과 독립 → R13은 R12의 그룹만 소비** → R8·R9는 무변경. 전제 파괴
없음. ✓

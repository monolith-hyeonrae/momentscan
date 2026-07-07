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
> 2. 항목은 **한 번에 하나**, 문서의 순서(R1→R2→R3→R4→R5→R6→R7→R8→R9)대로.
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
기준 재생성 절차 필요를 항목 내 명시 → R8·R9는 무변경. 전제 파괴 없음. ✓

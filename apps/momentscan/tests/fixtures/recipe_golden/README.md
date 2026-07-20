# recipe 특성화 골든 — 선별본 (14/21)

`test_recipe_characterization.py` 가 읽는 입력↔출력 쌍. **신 포팅(products/recipe.py +
perception/readings/face_axes.py)이 구 appearance-engine 어댑터의 실행 물증을 재현함을
봉인**한다 (absorption-plan §1 A6, §4 트랙 1 완료기준 ①).

## 레이아웃
- `expected/{image_id}.recipe.json` — 구 어댑터 산출(골든). 출처 = appearance-engine
  `output/recipes_momentscan/`. **구 어댑터의 유일한 실행 물증** — 값 tolerance 일치가
  포팅 심판.
- `inputs/{clip}.likeness.json` — 그 골든을 만든 rider 를 담은 likeness.json **frozen
  사본**. 코퍼스 재독 금지(output/l2 의 likeness 는 이후 방문마다 재집계로 변함) — 여기
  frozen 본만 읽는다.

## 왜 21건이 아니라 14건인가 (선별본)

골든 21건은 likeness 가 **main+auxiliary rider 를 모두** 방출하던 시절 산출이다. 현
파이프라인은 **main rider 만** 방출한다(P1-② 제품 스코프, 2026-07-07 · likeness.py
`appearance_clip` 의 `role != "main" → continue`). 그래서 21건 중:

- **14건 채택** — main rider. 현 코퍼스에 그 rider 가 그대로 있고 provenance(role·
  `split_half_drift`·`neutral_var_explained`·`n_obs`)가 골든과 **비트-동일** = 골든을
  만든 그 rider 그대로. 신 recipe 출력이 골든과 tolerance(실측 최대 편차 ~1.5e-5, float32
  경로 + likeness.json 5-decimal 직렬화 노이즈) 일치 + unfilled 보고 동일.
- **7건 제외** — 원 입력 소실(output/ gitignore + 구 appearance_ref.json 개명·재실행,
  파일시스템/그git 어디에도 없음):
  - aux rider 6건 (`cap_1_t0` · `dual_1_t1` · `dual_2_t0` · `dual_3_t4` · `mask_1_t1` ·
    `test_0_t18`) — 현 파이프가 더 이상 방출하지 않음(main-only). 재현 불가는 스코프
    변경의 정상 귀결이지 포팅 결함 아님.
  - main rider 1건 (`test_4_t0`) — 코퍼스 재집계로 그 클립 main rider 의 `n_obs` 가
    696→346 으로 변함(트랙/집계 변동). 골든을 만든 원 기하가 소실.

A6 이 "선별본"을 명시하므로 14건 채택은 계획의 의도. 7건 제외는 골든 입력 재현 불가를
정직 기록한 것(추측으로 대체 입력을 만들지 않음).

## 재현 절차 (기록)
1. 각 클립 `output/l2/{clip}/likeness.json` 를 `inputs/{clip}.likeness.json` 로 frozen 복사.
2. `expected/` = appearance-engine `output/recipes_momentscan/{image_id}.recipe.json` 복사.
3. 검증: 신 recipe 출력의 provenance(role·drift·var_explained·n_obs)가 골든과 동일함을
   확인 후 채택(= 같은 rider 라는 증거).

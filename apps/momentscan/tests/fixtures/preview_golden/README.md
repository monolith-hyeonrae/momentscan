# preview_golden — 13 shape key 투영 특성화 골든

`shape_keys.json` = `{image_id: {shape_key: value}}`. track/lk-preview 의
`recipe_preview.project_shape_keys(recipe, gain=1.0)` 가 구 appearance-engine
`blender_export._compute_shape_keys` 의 수학을 재현하는지 봉인한다.

## 생성 경위 (재현 불필요 — 봉인본)

입력 = 자매 골든 `../recipe_golden/expected/*.recipe.json`(구 어댑터의 유일한 실행
물증, 14건). 각 recipe.json 의 Cat G 엔트리에서 `values={aid: value}` +
`registry_axes={aid: {range}}` 를 복원해 구 `_compute_shape_keys` 를 돌린 결과.

생성 시점(2026-07-20) 실측: 구 함수와 신 `project_shape_keys(gain=1.0)` 의 셀별
최대 편차 = **0.0**(비트-동일). 두 코드가 같은 recipe.json 값을 입력으로 같은
range-정규화 + L/R 비대칭 가드 + 평균 집계를 하기 때문. 골든은 그 *수학*을 잠근다 —
포팅 버그(잘못된 축 튜플/부호/가드 누락)는 O(0.01~1) 이동으로 잡힌다.

appearance-engine 삭제(D6) 후에도 이 골든만으로 특성화가 성립하도록 값을 frozen
했다(구 코드 import 없음). L/R 가드는 코퍼스 실데이터에서 발화한다(dual_2_t1
Eyebrow_Length·Eye_Size, test_5_t0 Eyebrow_Length) — 골든이 가드 경로를 이미 포함.

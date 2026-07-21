# fixtures/eval — 사람-판정 GT (git-추적)

사람이 남긴 판정 깃발의 영구 홈. `output/`(gitignore, 재계산 대상)과 달리 **사람 판정은
재계산 불가**라 레포에 산다. 원형 = 수용 집합(P2, docs/eval-plan.md) — 절대 점수 아님.

## workbench_gt.jsonl — likeness 표본 샘플링 GT (원장 ⑫)

샘플링 워크벤치(`scratchpad_workbench.py` → workbench.html)에서 프레임 클릭으로 축적,
export 버튼이 내려주는 파일을 여기 저장(append 병합 가능 — 같은 clip:frame의 나중
판정이 이김). 행 스키마:

```json
{"schema": "momentscan.workbench-gt/v0", "clip": "dual_2", "frame": 662,
 "role": "center", "flag": "pos", "corpus": "output/l2", "ts": "..."}
```

- `role`: 깃발의 축 — v0은 `center`(대표 표본 적합)만. hair 빈은 v1에서 role 추가.
- `flag`: `pos`(이 프레임이 뽑히면 좋다) / `neg`(뽑히면 안 된다). 깃발 없음=무의견
  (수용-집합 의미론: 표기 안 된 프레임에 대한 주장 없음).
- `corpus`: 프레임 인덱스의 기준 코퍼스. 클립 소스가 재인코딩되면 무효 — detect.mp4
  기준 frame_idx.
- 소비자: 워크벤치 import(오버레이·설정 채점 `픽∩pos / 픽∩neg`) → 이후 샘플링 정책
  회귀 측정(evals 하니스 편입은 착지 트랙에서).

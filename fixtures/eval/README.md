# fixtures/eval — 사람-판정 GT (git-추적)

사람이 남긴 판정 깃발의 영구 홈. `output/`(gitignore, 재계산 대상)과 달리 **사람 판정은
재계산 불가**라 레포에 산다. 원형 = 수용 집합(P2, docs/eval-plan.md) — 절대 점수 아님.

## workbench_gt.jsonl — likeness 표본 샘플링 GT (원장 ⑫)

샘플링 워크벤치(`momentscan workbench` — 정식 표면, v0 계기=`scratchpad_workbench.py`)
에서 프레임 클릭으로 축적. 클릭 = 서버가 이 파일에 즉시 병합-쓰기(POST /api/gt,
원자적 — 같은 clip:frame:role의 나중 판정이 이김·flag 해제=행 제거), 재기동 시 복원.
export 버튼 = 백업용(.jsonl 다운로드; append 병합 가능·import = 서버 재-POST). 행 스키마:

```json
{"schema": "momentscan.workbench-gt/v0", "clip": "dual_2", "frame": 662,
 "role": "center", "flag": "pos", "corpus": "output/l2", "ts": "..."}
```

- `role`: 깃발의 축 — v0은 `center`(대표 표본 적합)만. hair 빈은 v1에서 role 추가.
- `flag`: `pos`(이 프레임이 뽑히면 좋다) / `neg`(뽑히면 안 된다). 깃발 없음=무의견
  (수용-집합 의미론: 표기 안 된 프레임에 대한 주장 없음).
- `corpus`: 프레임 인덱스의 기준 코퍼스. 클립 소스가 재인코딩되면 무효 — detect.mp4
  기준 frame_idx. 서버는 `--out` 문자열을 그대로 도장(레포 루트 상대 관례: 메인
  코퍼스 = `output/l2`) — 워크벤치 뷰 복원도 이 라벨이 일치하는 행만 적용한다.
- 소비자: 워크벤치 로드 복원(오버레이·설정 채점 `픽∩pos / 픽∩neg`) → 이후 샘플링
  정책 회귀 측정(evals 하니스 편입은 착지 트랙에서).

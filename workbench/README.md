# workbench — 연구 워크벤치 (제품 코드 아님)

알고리즘을 **제품 코드에 넣기 전에** 검증하는 참조 구현 모음. 구현의 기준
사본은 여기이고, 검증을 통과한 알고리즘만 제품 코드로 옮긴다. 검증 방식:
실제 영상과 눈으로 대조하며 측정값을 점검하고, 어긋나면 바로 수리한다.
기각한 시도도 기록에 남긴다(작업 기록: `docs/refactor-plan.md`).

| 파일 | 무엇 |
|---|---|
| `scratchpad_workbench.py` | **정적 HTML 워크벤치** (선별 기준 다이얼·타임라인·검사 뷰) — 샘플링 알고리즘의 주 작업장 |
| `scratchpad_likeness_*.py` | likeness 채널별 검증 스크립트 (sat=피부색·light=조명·pool=후보 풀·diag=판정 카드·v7=선별 시뮬레이션) |
| `scratchpad_sapiens_probe.py` | Sapiens 2 모델 특성 조사 3단계 (전용 venv 구성법은 독스트링에) |
| `scratchpad_meshref_blender.py` | 측정 메쉬 렌더 (likeness 표현력 상한의 기준 이미지) |
| `scratchpad_emb_occlusion.py` / `scratchpad_l2.py` / `scratchpad_render.py` | 가림-임베딩 조사·L2 점검·렌더 보조 |
| `experiments/` | 일회성 조사 스크립트 (작업 기록이 인용하는 근거) |

실행 방법 (cwd는 **레포 루트**여야 한다 — 산출물 경로가 루트 기준 상대 경로):

```bash
.venv/bin/python workbench/scratchpad_workbench.py output/l2/workbench   # 8클립 ~11분
```

⚠ 고객 픽셀(얼굴 이미지 등)은 리포에 넣지 않는다 — 산출물은 `output/`(ignore),
로컬 보존은 `/experiments/media/`(ignore), 커밋 차단 훅=`.githooks/pre-commit`.

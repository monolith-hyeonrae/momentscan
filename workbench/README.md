# workbench — 연구 워크벤치 (제품 코드 아님)

알고리즘을 **제품에 이식하기 전에** 검증하는 참조 구현·프로브들. 여기가 정본이고
제품(parse 등)으로의 이식은 트랙(lk-sampling2 등)으로 착지한다. 검증 방식 =
채널-단위 1층 루프(실물 앵커 → 계기 해부 → 즉시 수리 → 기각도 정직 기록) —
경위와 판정은 `docs/refactor-plan.md` 원장.

| 파일 | 무엇 |
|---|---|
| `scratchpad_workbench.py` | **정적 HTML 워크벤치** (다이얼·타임라인·검사 뷰) — 샘플링 알고리즘의 주 작업장 |
| `scratchpad_likeness_*.py` | likeness 채널별 프로브 (sat=피부 HSV·light=조명·pool=풀 시트·diag=판정 카드·v7=선별 시뮬) |
| `scratchpad_sapiens_probe.py` | Sapiens 2 특성화 3단 프로브 (전용 venv 레시피=독스트링) |
| `scratchpad_meshref_blender.py` | 측정-메쉬 렌더 (likeness 표현력 상한 기준물) |
| `scratchpad_emb_occlusion.py` / `scratchpad_l2.py` / `scratchpad_render.py` | 가림 임베딩·L2 감사·렌더 보조 |
| `experiments/` | 일회성 프로브 기록 (원장이 인용하는 물증 스크립트) |

실행 관례 (cwd=**레포 루트** 필수 — 산출물 경로가 루트-상대):

```bash
.venv/bin/python workbench/scratchpad_workbench.py output/l2/workbench   # 8클립 ~11분
```

⚠ 고객 픽셀(얼굴 이미지 등)은 리포에 넣지 않는다 — 산출물은 `output/`(ignore),
로컬 보존은 `/experiments/media/`(ignore), 커밋 차단 훅=`.githooks/pre-commit`.

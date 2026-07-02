# momentscan — 복잡도 감사 & refactor 계획 (2026-07-01)

---
## ▶ 진행 (2026-07-02): 상위 5 타깃 전부 완료 — 다음 = 로직(6D-가림)

**실행 = 1(+6 흡수) → 3 → 2 → 5 → 7. 전부 `check` 0err + replay-check tolerance-identical
(cap_1·dual_3).** verify 루프는 유지: 변경 → check → replay-check(additive면 ref 재동결 후).

1. ✅ **[rank 1+6] `pose.py` 도메인 홈 신설** — 계획(signals.fuse_pose)에서 **격상**. 근거=사용자
   통찰: 코드 구조가 논리 아키텍처를 반영 안 함(L2만 물리 홈 부재) → pose 전문가 경계 모호,
   폐기가능한 실험 불가. 내용: `euler_from_transform`(signals→)·`fuse_pose`(portrait 인라인→)·
   `pose_class`(gates._pose_class→)·상수 5개(POSE_MAX·FRONTAL 15 routing·SIDE·CORROB +
   **CAMERA_FRONTAL_DEG=12 E002** — 같은 이름의 두 사실을 이름으로 분리, appearance/select 사본
   삭제). 소비자 7파일 구독화. **전문가 영토 = headpose.py(백엔드 어댑터) + pose.py(정책)**;
   실험 루프 = v2 함수 작성→콜사이트 1줄 플립→replay/eval→keep-or-delete.
2. ✅ **[rank 3] `gates.query_dist(get)` 단일** — 게이트/trace/portrait-warm 3중복 → dict-loop
   1홈(getter 주입: G·dict.__getitem__ 겸용). dim 추가 = PORTRAIT_QUERY 한 줄.
3. ✅ **[rank 2] frontal_clean 영속화** — trace_rows+stash 스키마(additive)·appearance/viz 재유도
   삭제하고 컬럼 소비. 컬럼≡재유도 정확 동치 검증(cap_1 504/745 true).
4. ✅ **[rank 5] emotion 정리** — EM8=EM_ALL 파생(+**portrait.EM 제3사본도 제거**; 소비자 순서-무관
   확인: conf=이름 기반·vel=Σ|Δsoftmax|)·write_emotion_frame `_validate` 추가·헤더 stale
   ("STEP 0 adds NO artifact") 수정.
5. ✅ **[rank 7] stash nullable-axis 수정** — required를 dtype VALUE 기준으로. **발견: 버그가
   라이브였음** — tubelets depth/embedding·detections embedding 3컬럼이 이미 `?` 선언 →
   조용히 required 취급되고 있었음(주석 "no '?' keys today"도 거짓이었음).

**⚠ 절차 교훈(ref staleness)**: 첫 replay FAIL — 픽스처 ref가 전일 additive `rep.terms` 이전
동결. diff가 그 필드뿐임을 확인 후 ref 재동결. **additive 변경은 픽스처 ref 갱신까지가 한 단위.**

### L2 도메인 홈 — "drift 지도 = 홈 없는 도메인 지도" (2026-07-02 관찰)

flavor-1 drift는 무작위가 아니라 홈 없는 도메인의 그림자였다: FRONTAL_DEG×2+융합 인라인→pose
(오늘 졸업) · frontal_clean 재유도→identity/cohort · query_dist×3→query 기준 · EM8→emotion 홈 밖 잔재.
**졸업 규칙(균일)**: 시그널 도메인은 *백엔드 ≥2 또는 융합/양자화 정책 보유* 시 signals.py→자기 모듈.
반증 사례가 규칙을 지지: emotion.fused_valence는 홈이 있고(emotion.py) 거긴 drift가 없었다.
- **identity = 2번 후보** (pose와 동형): cross-subject cos_self/cos_other가 **portrait.py PASS 2
  (:249·:281) 인라인** · iddev=signals · clean_ref/TAU들=gates · face_id core=appearance · stitch.py.
  **6D-가림 로직이 id_valid를 건드릴 때 그 작업의 일부로 졸업 — 미리 만들지 말 것.**
- emotion = 핵 존재, STEP4+ 때 잔여 통합. blur/노출/scene/occlusion = 단일 백엔드·홈 있음, 잔류.
- open: appearance.BIN_EDGE_DEG=15는 routing FRONTAL 15와 같은 값·다른 사실일 가능성 — 병합 보류.

### 파일 구조 재구조 완료 (2026-07-02, 커밋 7d7ca68)

**flat 33모듈 → L0–L4 미러** (전부 whole-file 이동, 분할/병합 0):
`stages/`(L0-L1 어댑터 10) · `domains/`(L2: signals·pose·emotion) · `products/`(L4 4) ·
`surface/`(viz·inspector·label) · `verify/`(replay·freshness·eval·graph) + top-level 척추
(`__main__·pipeline·stash·analyzers·features·telemetry·gates`). readings.py 삭제(소비자 0).
**git init + baseline(a63c040)** — 06-24부터 standing queue였던 항목; 커밋은 co-author 트레일러 없이(사용자 선호).
**이동이 노출한 잠복 결합 3건(전부 freshness)**: ①`_pkg_dir`가 자기 파일 위치로 패키지 루트 유도
(→parents[1]+가드 assert) ②`STAGE_MODULE` 모듈명 문자열 하드코딩 ③외부모델 dep 키 — 문자열 모듈참조는
import 재작성기가 못 봄, **이동 시 `grep "['\"]momentscan\."` 전수(로거 제외) 필수**.
검증: 31모듈 import 스모크·check 0err·replay 0drift×2·freshness closure/is_stale 실호출·inspect 렌더.

**+ stages 노드 완전성 (9d96c2c)**: user "stages vs plugins/45D 역할 구분이 구조에서 안 읽힘" →
진단 = 갈림 기준이 계층이 아니라 의존성 격리 + features/scene은 앱에 노드 파일조차 없음(pipeline
인라인 래퍼). 해법 = `stages/features.py`·`scene.py` 얇은 어댑터 신설(`ls stages/`=DAG 12노드 전체) ·
plugins = 격리 모델 백엔드로 선언(plugins/README·stages/__init__·analyzers 노트: 의존성 이음매 +
FeatureSource 포트 + 서비스 워커 경계) · freshness STAGE_MODULE→어댑터(클로저가 백엔드까지 추적 검증) ·
앱 __init__ stale JEPA 프레이밍→3제품+레이아웃 지도. vjepa 스텁=예약석 유지(연구 결정이라 정리로 안 지움).

### 다음: 로직 재개 — 6D-가림 신뢰도

이음매 = `pose.fuse_pose`(docstring에 blind spot 명시해둠) + `id_valid`. 절차: **영향 측정**
(가림-구제 49프레임 델타: likeness/portrait/highlight) → **eval-gate** → iddev 가드.
기회주의 잔여: rank 4(frame_scores 폐기 스코어러)·8(crop_ref)·9(dead-code)·10(술어 공유)·11(infra).

**운영 제약**: `.venv/bin/python`·`.venv/bin/momentscan` · out=`output/l2`(replay-check 기본이 `output`이라
필수) · features 재추출 `--fps 6` · pkill 금지(셸 죽음) · 소스 `/home/hyeonrae/Videos/reaction_test/`.
**세션 맥락**: 대화는 안 이어짐 → 이 문서 + `~/.claude/projects/-home-hyeonrae-repo-monolith-momentscan/memory/`
(MEMORY.md 자동 로드)가 재개 매개. 계정 변경은 무관, 머신 바뀌면 memory폴더+repo 같이 이동.

---


15-유닛 병렬 감사 → 교차-파일 합성 → 우선순위 계획. 모듈별 복잡도를 **본질적(keep)
vs 우발적(refactor)**으로 분류.

## 판정: ~80/20 본질적/우발적 — "레거시보다 복잡"은 대부분 정당

문제가 진짜 어려워서 복잡한 거다: 3 결합 제품(likeness/portrait/highlight)이 하나의
molten 공유 신호 substrate를 읽고, validity→policy→routing 게이트 사다리, 분포기반
정체성, 멀티모델 추출 fan-in, anti-drift 선언 척추(DAG+drift guard). 큰 파일들
(gates/select/appearance/_inspector_html/stash)은 다 **정당한 이유로** 복잡.

**우발적 20% = drift지 아키텍처가 아니다.** 레거시가 무너진 plugin-machinery/hexagonal
과잉과 **다른 종류**. 세 flavor:
1. **단일 사실이 여러 곳에 타이핑되고 prose로만 동기화** — FRONTAL_DEG(12/15), ImageNet
   mean/std(×4), query 거리(×3), frontal_clean, portrait-box 기하(Python+JS), pose/blink 임계.
2. **폐기됐는데 아직 계산/반환되는 잔재** — frame_scores 안의 폐기 곱셈식 portrait 스코어러,
   crop_ref, readings.py, stale docstring.
3. **진짜 죽은 헬퍼/필드 + 잠복 버그** — stash nullable-axis 가드 버그, emotion writer가
   _validate 건너뜀.

**핵심**: 우발적 복잡도가 **다음 로직 작업 예정 지점(pose 융합·query 합성·clean-frontal
코호트)에 정확히 몰려 있다.** 상위 타깃 수정 = in-flight 작업을 직접 unblock.

## 우선순위 타깃 (우발적만)

| # | 타깃 | 무엇을 없애나 | 어떤 다음 로직을 unblock | 노력 |
|---|---|---|---|---|
| **1** | **pose 융합 단일홈** `signals.fuse_pose()` — portrait.py 인라인 np.where 대체 (gates._pose_class 양자화기는 유지) | MP⊕6D 융합이 portrait.py(제품)와 gates에 2가지로 분산 | **6D-가림/pose-routing 신뢰도**(우리가 하려던 것) — 한 곳 수정으로 제품+양자화기 모두 상속 | low |
| **2** | **frontal_clean을 gate_trace 컬럼으로 영속화** — appearance/viz가 재유도 대신 소비 | clean-frontal 코호트를 2곳이 prose-match로 재유도 | gate-taxonomy/clean_ref-polarity 정제 | low |
| **3** | **`gates.query_dist()` 단일** — gate/trace/portrait ranking이 공유 | query 거리 3중복(portrait는 dims 하드코딩 → 4번째 dim 추가시 랭킹서 조용히 누락) | **② query-synthesis**(portrait 미구현 부분) | med |
| **4** | **폐기 곱셈식 portrait 스코어러**를 frame_scores서 분리 | frame_scores가 안 내보내는 제품을 여전히 계산(likeness+highlight 라이브 코드에 섞임) | select.frame_scores 가독 편집 | med |
| **5** | **emotion 정리** — EM8 중복 삭제·write_emotion_frame에 _validate 추가·stale docstring | 8-카테고리 2복사·유일하게 write-guard 빠진 writer | emotion STEP 1-3(valence/baseline) | low |
| 6 | FRONTAL_DEG 12/15 단일홈(signals) | E002 카메라 사실 2복사 | 카메라축 재측정 | low |
| **7** | **stash._validate nullable-axis 버그 수정** | `?` 마커가 VALUE에 있는데 _validate는 KEY에서 찾음 → nullable 컬럼이 조용히 required 취급 (잠복 버그) | nullable 컬럼(depth/embedding) 안전 추가 | low |
| 8 | 죽은 crop_ref 컬럼 삭제 | 아무도 파싱 안 하는 ~2.5k행/클립 URI(폐기된 decode plan) | crop-track 스키마 명료 | low |
| 9 | dead-code sweep | readings.py 전체·by_tier·applies_to·_closure_files·sec·미사용 param 등 | 선언 척추 표면적 축소 | low |
| 10 | frontal_pose/quarter_ok 공유 술어 추출 | 8-term 술어 2복사(과거 "served side에 blur reject" 버그류) | ② query-synthesis (3 보완) | med |
| 11 | 저가치 infra 중복(ImageNet×4·pbox Python+JS·label lane) | 안정 상수 2-4 홈(일부 이미 drift) | (로직 unblock 없음, 기회주의적) | med |

## KEEP (본질적 — 건드리지 말 것)

3-제품×molten-substrate 설계 전체 · gates 게이트 사다리+상대귀속+guarded 양자화기 ·
appearance 분포 리딩(PCA/eigen-stability/cohort polarity) · signals CanonicalFrame 계약 ·
stash 명시적 per-artifact 컬럼맵(테이블화 안 함=레거시 dead-abstraction 회피) ·
analyzers/pipeline/graph 선언 척추+drift guard · 멀티모델 추출 fan-in+도메인 어댑터 ·
specialist45d 67D 계약 · freshness/replay/eval 3-검증 · Step-0 앵커 파이프 ·
E-log 튜닝된 연구 노브(CLIP_LEN_S/RARITY_WIN_S/PORTRAIT_QUERY 등 molten 값).

## 추천 시퀀스

**low-effort AND 다음 로직 unblock을 먼저**: 1(pose 홈) → 2(frontal_clean) → 5(emotion)
→ 7(stash 버그) → 3(query_dist). 그 위에서 pose-가림 로직 재개. 8·9·11은 기회주의적.
전부 replay byte-identity 가드 통과 필수(additive 스키마/순수 이동).

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

**+ stages 순수화 (c293e62)**: user "ls stages/가 분석노드로 안 읽힘" → 3종 혼재 해소:
분석노드 9 잔류 / ingest·daemon→top-level(pipeline 러너 가족) / stitch→domains/(identity 예비석).
**stages/의 계약 = "무슨 분석이 도는가", 기계는 아님.** landmarks(모듈 없는 노드)는 __init__에 선언.

**+ 전 파일 역할감사 → 경계 재설계 (c692673 · 0066fd3, user와 4결정)**:
① `stages/`→**`extraction/`** 개명(내용=L1 추출 노드만; 상위 레이어 스테이지는 자기 레이어 홈 —
이름이 이제 그걸 말함) ② **`domains/geometry.py` 졸업**(CanonicalFrame 계약+canonicalize/norm468/
template+.obj dep; signals.py=얇은 단일-백엔드 리더만) · rolling_median→select 공개이름(인스펙터 구독) ·
사적 층간 import 3건 공개화(canonicalize·rolling_median·portrait_box) ③ 이름 정렬: `features.py`→
**`ports.py`**(features 3중 충돌 해소) · `appearance.py`→**`likeness.py`**(stage=제품=파일; 함수명 유지)
④ **viz.py(1695) 분할**: `surface/cards.py`(제품/과정 렌더러 1121)+`surface/inspector.py`(한-런 창 589).
분할이 잠복버그 노출: sed 순서 탓 `signals.canonicalize` 잔존(함수-내부라 import 스모크 무감) →
geometry.canonicalize + **inspect 실렌더로 증명**. 교훈: 전역 rename sed는 좁은 패턴부터.

**+ extraction 정합 세션 (4a90269, user "tubelets는 extractor야?")**: extraction/이 캐스케이드
위상으로 잘려 있던 것을 **user의 멤버십 테스트**("개별 신호 처리로 연구될 전문분야인가")로 재단 —
내 테스트("모델 교체가 변경 이유인가")와 같은 멤버십으로 수렴. `extraction/`=신호 전문분야만
(detect parse fashion headpose features scene; detect는 관측 전문분야라 잔류) · **`subjects/` 신설**
=신호가 붙을 대상 구성(attribute→tubelets[경계계약]→crops). **격리 사다리 선언**(①in-app ②workspace
pkg ③plugin+bus)=레거시 vpx-plugins 의도를 기계 없이 유지. **지배 원칙 확정(user)**: /dev 원칙 —
실행 없이 트리가 "무엇이 돌고 있나"를 답한다(ls extraction/=신호 분석 리스트).

### ~~다음: 로직 재개 — 6D-가림 신뢰도~~ → 완료 (2026-07-02 저녁)

측정이 iddev 가드를 **반증**(구제=정당), 진짜 오염=parse 프로필-맹 → 판정가능성 가드로 수리(1afb8c7).
이어서 6D 3축 좌표 정합(ca01590)·3축 불일치 가드도 측정-반증(4c188c3)·인스펙터 정합 가시화(6cce2f2).
상세=session-resume-point 메모리 (4)~(8).

### ~~▶ 다음 재개 (2026-07-03~)~~ → 진행됨 (07-03: C3 정합·채택 3종·SubjectQuery)

07-03 실행분: C3 정합(subjectlet 소비, parse 실버그 수리 8c251ee) · 7단 체인(14b5610) ·
채택 3종 doctor/원커맨드/report+quiet(44b8f21·a10beef) · **C2 reference_face 구현**(815dfbd,
τ=0.30 측정) · positional 설계 동결+코퍼스 앵커(751f28b·611ed3d). 상세=session-resume-point (11)~(17).

### ~~`--subject` 전체 파이프 통합 검증~~ → PASS (2026-07-03, 선등록 6항목)

face:s2로 12스테이지 완주(320s): 구성축 전부 단일-subject·portrait/likeness=코퍼스와 동일값·
job.json·report. 선등록 델타(단독 vs 상대귀속 id경로)=0. **부산물 발견**: 단독-highlight 0세그
= s2 전클립 valence 음수(양수 1%)×절대 VAL_EMIT_FLOOR — **육안확인 웃음도 valence 음수**
(head-back laugh를 em_*가 부정 분류; energetic-neg 가족). 코퍼스 3세그=동승자 valence가
가려온 것 → **face-쿼리 팬캠이 보류된 highlight-desirability 이슈가 가장 아픈 유즈케이스**
([[emotion-first-class-reading]] 사례 등록; 수정은 기존 결정대로 전용 세션에).

### ~~highlight-desirability 슬라이스 1 (방출)~~ → DONE (2026-07-03, f5e34b0)

user 프레임 정식화(하이라이트=**맥락적 정합성**≠anomaly≠얼굴-baseline; 감정=**궤적 likelihood**)
위에서 방출 게이트 교체: valence-단독 floor → **타겟-축 양성 증거 OR**(joy=valence≥−0.1 /
thrill·energy=arousal≥0.30, 코퍼스 302창 스윕 앵커). person-relative 방출은 측정으로 기각
(test_2 시종-미소 탑승자의 자연-미소 피크 5/5 전멸). 판정: s2-솔로 팬캠 0→3(웃음 f487 복구)·
test_2 3→3·test_3 1→1(찡그림 wa≤0.086)·12/15 클립 불변·rescore_pairs 클린.
viz=output/l2/lane_emit_congruence.png. 남은 조각: 파묻힌-입 spurious arousal 방어
(mouth_vis 판독-가능성 조건화, dual_1 parse 재런 필요) · WHEN/WHICH energy 재편(06-29 설계) ·
창 형태(onset/release) 방출 · 궤적 표상(장기, substrate 연구 레인).

### ▶ 현재 (2026-07-08) — 종합 판단 확정: 평가 기판(E-트랙) 선행, 본작업 = track/r0-r2

**종합 문장(user 확정): 사이클(누더기→복잡성 폭발→정체→재정리)을 끊는 건 더 좋은
아키텍처가 아니라 측정 가능성과 경계.** 외부 대화 2건 검토 결과 방법(2-스트림·쿼리
정합)은 우리 두-레인 ZVMR의 재도출 — 없는 절반은 평가 기판.

**E-트랙 (신설 — 품질 그물; R2=안정성 그물과 쌍):** 세부 = [eval-plan.md](eval-plan.md)
- **E1 회귀 세트**: 라벨 원형 = **수용 집합(P2)/의도별 수용 구간(P3)** — 쌍대는
  영역-간 보조로 강등(수용 영역 안 쌍대=동전던지기, user 실증). 두 라벨 패스 분리.
  씨앗 = 이름 붙은 사건들 + 15코퍼스. portrait 집합-내 = **쿼리-조건부 평평**
  (0축 결정 유지, 약순위 도입 안 함).
- **E2 `momentscan why <clip> <frame>`**: 탈락 사유서 — gate_trace(REASONS)·candidates·
  frame_scores 위 단일 질의 표면 (재료 완비, 표면만 부재).
- **E4 D4 명문화**: 승격 = R2 green + 회귀 메트릭 비퇴행 + 판정카드 user 확정
  (= rq 판정기 = ship gate; 합의 후 우산 architecture.md D4로 bead).
- **E3 ablation 하니스**: 46-dim leave-one-out on 회귀 세트 — dead weight의 기계적
  퇴출(측정으로 줄인다).

**방법 연구 등록 (착수는 E1 후 — 새 신호는 측정 기판 위에서만):**
- **SEREP**(Ubisoft La Forge, ICCV25) = 표정-정체성 semantic 분리 학습(비제어 단안,
  cycle consistency) — 우리 이층(neutral+blendshapes.profile 습관 시그니처)의 학습판,
  "습관 눈매=아이덴티티"(user 2026-07-20) 정식화. **MultiREX 벤치**(8 id×5뷰×극단표정,
  GT 메쉬 10K, FLAME neutral, eval 코드) = **E1 외부 자 후보**: 정준화·neutral의
  포즈-횡단 오차 + ⑧ 정면-전용의 정량 검증. ⚠CC-BY-NC 연구 전용(내부 eval 방어
  가능, 상업 학습 금지). 모델 코드 미공개. 정본=[[serep-mosar-lens]] 메모리.
- **MoSAR**(CVPR24) = 이미지 1장→릴라이터블 아바타(기하+반사율 5종) — 비목표
  "이미지-1장 레인"의 기성 지도(재개 조건 발동 시 참조) + Cat C·relight 컨테이너화
  원료 개념. 데이터셋 CC BY-NC-ND=관찰 전용, 모델 코드 미공개.
- **MARLIN**(CVPR23, 자기지도 얼굴 영상 인코더) = "감정=궤적 likelihood"의 기판 후보.
  mdl 등록(ids.md, 라이선스⚠확인 1순위). 첫 실험 = 코퍼스 궤적이 이름 붙은 사건들을
  우리 46-dim/em_*보다 잘 가르는가. **동결 제약: baseline-편차를 랭킹 성분으로 쓰지
  말 것**(test_2 기각 — 기준=쿼리, 편차=게이트). 정렬 병목은 우리 설계가 우회
  (두-레인 언어화가 다리; portrait 쿼리=정준좌표) — MARLIN 초기 직무는 정렬 불요 자리.
- **VMR 사다리 갱신**: Moment-DETR 구세대. 1단(Qwen2.5-VL grounding 스모크) 유효
  유지; 후순위에 TRACE(ICLR25)·TimeExpert(ICCV25)·VTG-GPT(tuning-free) 추가;
  QD-DETR류는 시간 헤드 distill 자리 옵션. **차별점: 문헌은 viewer-reaction, 우리는
  in-video subject-reaction**(당사자 반응 — 맥락과 반응이 같은 프레임에 공존).

**프로세스**: 트랙-스코프 규율 확정(CLAUDE.md 하드룰) — 세션=한 트랙, 트랙=브랜치,
착지=머지, stash는 브랜치 안 탐. 본작업 = `track/r0-r2`(R0 안전망→R2 특성화 그물,
mb-r17m 내부 게이트 겸함) ∥ E1 라벨 스키마 초안(user 검토 체크포인트).

**likeness 미결 원장**(재개 시 입구): ①recipe registry 캘리브레이션 불일치(4키
가장자리: Brow_Thickness≈0·Mouth_Size≈0.9·Mouse_Corner 하향·Brow_Slant 상향 —
재캘리 vs 어댑터 보정) → **양안 준비 완료 2026-07-20**(머지 284cf53: race981 테이블
[15 rider, 정면-전용 ⑧ 기하]+`viz-recipe --ab calib`; 계통 오프셋=구 캘리의 posed-
스튜디오 편향[G22 입꼬리 p95 53°→26°] 실증, 4키 p50 재중심; **recipe 기본=legacy
유지, 전환=L-B user 판정 후 1줄 커밋**) ②recipe→MPFB 브리지 착지(scratchpad/mpfb_recipe.py →
appearance-engine) ③프리뷰 gain(×2.2 근방) ④어댑터 unfilled 채우기(color_identity·
fashion·samples.hair 방출됨) ⑤test_12 hair 세그 오검출 조사(user 동행)

> **갱신 (2026-07-20, track lk-recipe — appearance-engine 흡수 전반부)**: 어댑터가
> momentscan 내부로 흡수됐다 — 기하 공식=`perception/readings/face_axes.py`(Cat G 37축),
> 스테이지=`products/recipe.py`(likeness.json 읽기 전용 소비 → recipe/*.recipe.json),
> 캘리·정책 상수=`products/recipe_axes.py`. ②는 방향 반전(MPFB 재도입 없이 lk-preview
> 에서 bpy+디자이너 blend 로 재구성) — 흡수 전반부(recipe)는 lk-recipe, 후반부(preview)는
> lk-preview. ④는 **부분 착지**: face_id·fashion·color_identity·samples 를 recipe.json
> additive `"likeness"` 블록으로 패스스루(소비 이음매 신설). **잔여 ④ 본체** = 그 필드로
> H/A/W 축을 실제 *채우는* enum 사상(D4 아카이브 어휘 필요 + unfilled 변경 → 골든
> 재동결 동반). ① 캘리 양안 구현은 흡수 후 momentscan 좌표에서(순서 제약).
⑥P1-⑤~⑥(알파 피드백 계기[→E1과 병합]·S3 스모크·회사 Eureka)
⑦**hair/pose_bins 수집의 boarding-phase 선호**(user 2026-07-14, test_3 라벨 중 발견: 활강 전=바람에 헤어 안 망가짐·얼굴 일그러짐 덜함 — samples.pose_bins/hair_match 입력을 pre-ride 프레임 우선으로; phase-conditioned readings의 likeness 적용). → **착지 2026-07-20** (b) 빈-내 소프트: 3뷰 보존+빈별 boarding 선호.
⑧**랜드마크 정준화 = 정면 전용**(user 2026-07-20, appearance card A/B 판독 중 방향 확정): 측면 얼굴은 랜드마크 정준화(neutral/center 집계)에 쓰지 않는다 — 측면의 직무는 **헤어스타일 추론 향상**(hair_match 입력)뿐. 정준 기하는 가급적 정면 빈에서만 추론. ⚠값-변경 트랙(likeness 특성화 핀 이동 예상, 델타 설명 문법; recipe 골든은 입력-고정 fixture라 무영향). **원장 ① 캘리 양안보다 선행해야**(캘리는 정면-전용 기하 위에서).
⑩**13키 표현 어휘 갭**(user 관찰 2026-07-20, race981 A/B 판정 중: "개인 특성[얼굴형·
눈 쳐짐·눈 간격]이 두드러지지 않아 재미없다 — 쉐입키의 한계인가?"): 실측 = 측정
37축 중 13키가 소비 19축, **미표현 18축** — 특히 **얼굴형 계열 5축 전멸**(G01 폭높이비·
G02 턱폭비·G03 턱각·G04 광대·G05 이마; 13키의 윤곽 몰프=Chin_Length뿐)·눈 개방형태
4축(G08~11)·코 3축(G15/16/18). 처방 4갈래: (a)gain 노브(즉시, L-B ③) (b)**디자이너
키 확장 협의 = B1 계약 진화**(미표현 18축 리스트가 협의 재료 — 우산 bead 후보)
(c)키당 변위 폭은 리그 저작 영역 (d)렌더 placeholder(민머리·magenta 눈)가 지각 차이를
가림 — hair(H축) 착지 시 개인차 지각 상승 예상. 캘리 전환(446e1db)과 별개 축.
⑨**표본 스크리닝 2종**(user 2026-07-20, 카드 육안 판독: 어두운 크롭·눈감은 크롭이 표본에 선택됨): (a) 밝기 — exposure 게이트는 entropy-only **유지**(validity 판정, 어두움=recoverable 결정 불변), 대신 **표본/정준화 선발 랭킹**에 face_micro(parse DESCRIPTIVE 보존분) 투입 — exposure-gate 결정 때 예약해둔 자리 그대로. (b) 눈감음 — blink 신호(blendshape eyeBlink/EAR)로 표본 선발에서 제외. 둘 다 게이트 신설 아님 = selection 정책.
   → **선발 정책 확정 (2026-07-20, 진단 카드 v0~v6.2 + FIQA A/B/C 판정, user 동행)**:
   대표(c-슬롯) = ①**보이는-정면**: sym(뺨 x-거리 log비)<0.6 **∧** |yaw dev|<15°
   — 상호 환각 방어(yaw는 f16 오분류·sym은 극단 yaw서 f260 환각, 실측) ②**눈동자
   -가시 floor**: 눈꺼풀 개구/홍채 지름 **≥0.4**(절대량 — ARKit blink/squint는 야외
   포화로 폐기, EAR-백분위는 실눈형 트랙서 미보장; 0.5→0.4 재캘리=user f510 판정
   "0.43인데 형태 측정·portrait 용도로 훌륭" — floor 직무=감김 배제지 개방 최대화
   아님, 표정 온전 > 눈동자 마진) ③점수 = 0.40 무표정(정면 위에서만
   신뢰) + 0.25 pupil + 0.35 품질3축 nan-skip 평균(선명·face_micro·**buffalo_l
   embedding_norm** — raw 저장 덕에 공짜) ④시간 간격 ≥2s ⑤사다리 완화+FB 정직
   표기(boarding 선호는 같은 단 안에서만 — 탑승-측면이 라이드-정면을 못 이김).
   헤어뷰 빈(left/right)=측면 전용 유지(눈뜸 floor pct40). **FIQA 판정**: CR-FIQA=
   CC-BY-NC 탈락(라이선스 게이트)·MagFace(Apache-2.0, sha256 검증)=단독 백본 탈락
   (인식-효용은 눈동자 미흡수: pu 0.33 게슴츠레를 mg100%로 선발, 6클립 실측)·pupil
   floor 유지 + 품질축만 MagFace 교체(C′)=공짜 3축과 픽 동일(test_3 3/3 일치) →
   **한계효용 0, 도입 안 함**(모델 283MB+GPU 패스 비용 불가). MagFace 스코어러는
   scratchpad 보존 = E1 eval-baseline 후보(exposure-gate 때 예약한 자리).

   → **⑧⑨ 착지 (2026-07-20, track/lk-sampling)**: 신호 홈=`perception/readings/
   face_signals.py`(pupil_visibility·visual_frontality·eye_openness, 측정 공식만) ·
   정책=`products/likeness.py`(사다리 상수 모듈-top + `_pick3`; face_micro=parse·
   embedding_norm=detections raw L2 읽기 전용). ⑧=center(median)·neutral 회귀 입력을
   frontal_clean 코호트로 제한(폴백 문턱=face_id_min_frontal 재사용), PCA·축·blendshape
   통계·split_half_drift 는 valid 전폭 유지. **15클립 전/후 델타 = 설명 가능**: 불변
   확인(n_obs·split_half_drift·resid_rms·evr·face_id p05·fashion·hair 전부 byte-identical
   15/15) · ⑧ center RMS 이동 0.003~0.058·neutral 0.015~0.075(정면 제한) · ⑨ samples
   전면 교체(dual_2·test_12 = boarding rung 발화로 ⑦ 보존 실증). replay=likeness.json
   만 변경(gate_trace·portrait·emotion 무영향). 코퍼스 재계산·replay-ref 재동결은 머지 후
   공유 스윕(트랙-스코프). pytest 127·registry 0err·ruff 57·recipe 골든 15 무영향.

⑪**표본 신뢰 개정 — phase 강등·정체성-판독성 축**(user 동행 판정 2026-07-21; 발단="선정
crop이 부적절해 결정된 likeness에 신뢰가 없다"; 실증 계기=풀 시트 `scratchpad_likeness_pool.py`
·가림 프로브 `scratchpad_emb_occlusion.py`):
   (a) **center_nearest의 phase 선호 제거** — 외형 단서는 boarding 불요(user: "수집범위
   제한이 오히려 악영향"). 증거=dual_2 픽 f6/f9/f10(최소 간격 1프레임 — boarding 창 안에서
   gap 사다리가 0까지 붕괴한 첫 1초 3연사)·boarding 실측 f0~13 단 14프레임, ride 전역엔
   양질 정면 다수(풀 시트). 시간-다양성(gap floor) > phase 선호.
   (b) pose_bins(hair)는 boarding 소프트 선호 **유지** — ⑦ 물리 근거(바람 전 헤어) 유효,
   빈-내 폴백 이미 존재.
   (c) **identity-legibility 축 신설**: cos_self(detect raw embedding 정규화→트랙 중앙값
   코사인; 비교는 빈-내/풀-내 **상대** — 측면은 정면보다 자연히 낮아 절대 비교 금지)를
   빈 Q 4축째 + center 사다리 가드로. 증거=dual_2 **세 빈 픽 전부 바닥 10%**(frontal 9%·
   left 5%·right 2%) — 현행 Q(눈뜸·micro·선명)=identity-blind; right f1205 반가림=cs 0.571
   바닥 2%인데 **norm 65% = norm은 가림 맹목**(q3의 norm 유지하되 한계 명기). clean_ref
   극성(likeness=수렴)과 정합.
   (d) **입-가림 소프트 선호**(user: 비디오 안에 입 가림/노출 변동 실재 — 안 가려진 경우
   우선): mouth_vis(parse 보존분)를 상대 선호 축으로. 하드 스크린 금지 — 목도리 클립은
   포화(dual_2 right p50=0.000; 착용물=fashion 원칙과 충돌 방지).
   (e) **조명 상태 = phase가 재던 것의 실측 대체**(user: 탑승 지점↔활강 지점 조명차 실재,
   밝을수록 영상 선명 이점): phase 조건부를 지우는 대신 밝기·선명 축(기존 face_micro·
   sharp)이 그 이점을 직접 잰다 — 가중/사다리 위치는 v7 카드 판정으로.
   → **실측 정정(2026-07-21, user "얼굴면 조도 분석/기준이 없다")**: micro/sharp는 조도
   대체 불가 — corr(skin_lum, face_micro)=+0.24~+0.85(클립별, test_4 최저). **skin_lum
   직접 축 신설**(parse 보존분; lum_eff=skin_lum×(1−skin_clip_hi), **풀-내 상대 랭크만**
   — 스케일 클립별 75~198로 절대 floor 금지=노출 게이트 교훈). **boarding 밝기 우위
   실측**: test_3 179/90·dual_2 170/75·test_4 169/82(≈2×) — phase 선호가 우연히 주던
   조도 이점의 정체; (a)로 phase를 지우면 이 축이 그 자리를 직접 잰다(v7→v7.1 dual_2
   픽이 어두운-ride 3장→밝은 boarding 1+ride 2 혼합으로 복원 실증). 발견 2: ①test_12
   washout(skin_lum 218~230 백화-외관)이 skin_clip_hi에 안 잡힘(max 0.01 — 245 미만
   포화) → 백화 페널티 무력, 밝음-이득 상한 다이얼 후보(예: 풀 p75 초과 이득 절단)
   ②조도·cs 축이 hair 빈 픽을 정면-쪽 경계로 끌어당김(left 픽 dev −15.1 = 경계 0.1°
   통과, 구 −23~−33 대비 얕음) — side view 직무(헤어 각도)와 긴장, 빈은 각도-깊이
   선호 또는 cs/lt 가중 축소 판정 필요. 계기=scratchpad_likeness_light.py(조도 지형
   카드)·scratchpad_likeness_v7.py(v7.1, light 축 0.20+빈 Q6).
   → **채도 v2(2026-07-21, user 발상 "같은 카메라·같은 사람이면 채도 차이가 빛 좋은
   장면을 가른다")**: HSV-S는 **기각** — S=chroma/명도 비율이라 밝기와 반비례(실측
   corr(S,V) −0.76~−0.90, user가 생동으로 지목한 international_1 초반이 S 저값으로
   반전). 지각 생동감의 자 = **절대 chroma(max−min, 생산 skin 마스크 동일)**:
   international_1 초반 84.3 vs 풀 p50 49.0(+72%, user 판독 그대로) · 건강 클립
   corr(ch,lum)=+0.65~+0.99 · **test_12만 −0.44 = 백화 서명**(clip_hi 무력 지점을
   상관 부호 하나가 가름). light 축 = mean(rank lum_eff, rank chroma) **복합**(v7.2):
   합의(건강)/거부권(백화) 구조 — 실증: dual_2 청색-캐스트 f6 자동 탈락(캐스트→skin
   chroma 저하 = 색온도 우려 부분 흡수) · test_12 백화 회피. 잔여 의문: test_12 신규
   픽 f240=안경 글레어+측방 시선의 chroma 고값 승격 — 글레어/시선은 chroma 사각.
   생산 편입 = parse additive 2열(skin_chroma·chroma_std, 동일 마스크 1채널 추가)
   + 코퍼스 parse 재계산 동반. 계기=scratchpad_likeness_sat.py(chroma 지형 카드).
   (노트) **likeness 후보 샘플링 ≈ portrait 후보 샘플링**(user 관찰 2026-07-21): 표본-품질
   축(선명·밝기·가림·정체성-판독성·시선·표정)은 두 제품 공용 후보 — 졸업 규칙 관점의
   selection 기판 후보. 설계 시 likeness-특이(수렴 극성·무표정 선호) vs 공용 축을 분리
   표기해 둘 것.
   → **봉인 체계 재편(user 정식화 2026-07-22): 미결 다이얼 5종 → 상태 5그룹** —
   "**포즈의 상태 / 표정·얼굴의 상태 / 빛의 상태 / 영상의 상태 / 왜곡의 상태**"가 1단
   품질 스크린의 그룹 좌표계(워크벤치 퍼널·타임라인 단위도 그룹으로 정렬 = 분류가 역학).
   판정 반영: ②글레어+⑤cs floor **병합** — cs(정체성 판독성)가 가림·글레어·역광-왜곡을
   한 질문으로 겸직(user: "글레어 필터=역광 얼굴 왜곡 필터링") · ③hair 빈 각도 = 다이얼
   아닌 **별도 쿼리 세트**(yaw 밴드-쿼리의 인스턴스 — 각도-깊이 긴장은 밴드 정의로 해소)
   · ①light **세분화**: 얼굴면 광학(skin_lum·chroma + 심층=face_light_lr/tb[방향성]·
   harsh[거칠기]·SH9 — **이미 측정됨**, relight 메모 '입체감 floor' 예약석) vs **영상
   전체 품질**(프레임 선명·노출 — 카메라 품질) 분리. 배치 교정: mouth_vis=왜곡(가림)
   그룹·q3 분해=선명·micro→영상/norm→왜곡. 계기=워크벤치 v0.7(5그룹 재배치+심층 축
   dp/hh/sp 기본-off=셀프테스트 불변). 남은 판정=각 그룹의 채택값(test_4 재심 포함).
   계기 정비: 진단 카드 CAND C(MagFace) 행 제거(user "비교 무의미"). 시선(eyeLook) 하드
   스크린 **기각 실증**: international_1은 렌즈 응시가 eyeLookDown 0.4~0.6으로 읽힘(탑승
   카메라 눈높이-아래 기하) — 쓰려면 클립-내 상대 귀속+검증 프로브 선행. 미결 판정 2:
   무표정 절대 상한(test_3 픽 ex 0.62~0.64 — 상대 랭킹 한계) · 소재-한계 자백 필드(test_0/
   test_12=풀 전체가 하방/상방-롤, 픽은 풀을 정직 대표 — likeness가 표본 풀 품질을 자백할
   지). **다음 = v7 진단 카드(신 사다리 A/B) → user 봉인 → 트랙 발사**(⑧⑨ 선례 프로세스).
⑫**샘플링 워크벤치 + 선별 2단 구조**(user 정식화·도구 3종 발상 2026-07-21): user 문안
"품질 스크리닝으로 후보군의 **결정경계**를 좁히고, 대표성으로 우선순위 **깃발**을 꽂는다"
= 선별의 2단 명시화 — 1단 품질 스크린(**공용**: likeness≈portrait, ⑪ 노트의 실체; 극성
동일 축=선명·조도·chroma·가림·글레어) / 2단 대표성 랭킹(**제품-특이**: likeness=수렴
[무표정·다양성] vs portrait=발산 — clean_ref 극성 그대로). 미결 다이얼 5종을 이 축으로
분류: 품질(light 가중·f240 글레어·cs floor)/대표성(무표정 상한)/직무(hair 빈 각도).
   **도구 3종(user 발상)을 한 도구의 세 층으로 통합**: 데이터층=frame_table 와이드 뷰
   (프로브 4종이 반복한 조인의 단일홈; stash 읽기-전용 파생, 영속화 없음=이중-진실 방지)
   · 인터랙션층=HTML 다이얼 시뮬레이터(퍼널 카운트·A/B 프리셋·생존 풀 그리드; 측정=영속
   이라 스크린/랭킹은 JS 실시간; **드리프트 방어**=사다리 대신 명시-floor 의미론+로드 시
   셀프테스트 JS≡python[기본 설정=v7.2 픽 6/6 재현]+봉인 전 파이썬 카드 재확인) · 축적층
   =클릭 GT(pos/neg 순환, 수용-집합 P2 원형의 샘플링 적용; 프레임-수준=정책-강건; **홈=
   fixtures/eval**[user 확정, README 스키마 momentscan.workbench-gt/v0], v0=export 버튼
   [서버 무변경]). 계기=`scratchpad_workbench.py`. 스코프 v0=center 픽(hair 빈=v1).
   프로세스 재편: 다이얼 점검=카드 왕복 → **user 직접 탐색+GT 축적 → 봉인 → 트랙 착지**
   (GT-채점 증거 지참).
   (노트) **pixeltable 판정**(user 반문 "중복=fit이면 위임/visualstack 내장?"): fit은
   실재하나 층-의존 — 잘 맞는 층(per-frame 계산 컬럼)=우리에겐 이미 동결·저비용 부분,
   안 맞는 층=몰튼 연구부(코호트-상대 게이트·추적·전역 stitch·풀-상대 선별 = row-wise
   아님), 비이전 층=enforcement(계약·특성화 핀·replay tolerance·가드). 운영 무게(embedded
   Postgres vs ls-able parquet — 회사 워커·엣지 이식성, structure-transparency)·이행 비용
   (골든/replay 재구축)·two-truth 전환기 위험. **결론: 진실(stash)은 비위임, 인체공학은
   위임** — frame_table이 80%, 실험이 코호트-횡단·시맨틱 검색으로 자라면 "stash=진실 +
   pixeltable=분석 렌즈"(additive·가역, stash를 import하는 소비자)로 재상정. visualstack
   내장 = R16 ArtifactNode 자리의 **엔진 후보**로 소비자-지불 시 검토(우산 bead 후보).
   (정체성 문장, user 2026-07-22) **inspect vs workbench**: "inspect=시스템이 처리한
   결과를 잘 보여주는 데 집중 / workbench=사람이 신호에 대한 쿼리를 직접 조작해 결과가
   어떻게 나오는지 보며 **통계적 결정을 디자인**하는 도구" — v1 콘솔 문서/도움말 문안
   후보.
   (비전+플랫폼 판정, user 2026-07-22 오후) **완전한 분석 도구 / tool-first 방법론**:
   의료 AI 선례(해부학 구조별 영상처리 도구를 먼저 세워 시스템 개발 방향을 잡음)를
   우리 문제에 사상 — "비디오 열기→기판 갱신→신호 조정→**moment를 두드러지게**"가
   워크벤치의 종착 워크플로(user: "CV 작업의 통계적 디버거이자 프로파일러"; 접수 #13
   적발이 실증). 레인 지도 = 등록/기판[v1 완성] · 다이얼/분포/타임라인[v0.6 완성] ·
   부분 재실행 버튼[v1.1] · **플레이어+신호 커브 멀티트랙**[highlight WHEN의 도구] ·
   쿼리 레이어(밴드→표정 시그니처→언어)[portrait/highlight 모드] · GT role 확장 —
   **세 제품 사다리 순으로 성장**. HTML 충분성 판정: 계산=파이프라인/뷰=순수 렌더러
   구조라 브라우저 안전지대(행×신호+썸네일+캔버스; 의료 네이티브의 근거였던 뷰어-내
   볼륨 계산이 우리엔 없음) + 반복속도=계기 성능(하루 v0→v0.6 실증) + frame_table/GT/
   서버 API가 계약이라 **프런트 교체 자유 확보**(HTML이 나중을 잠그지 않음). 라이브
   스트림 급 요구는 visualstack 관측 계층 몫. v0.1~v0.3 부속(2026-07-22, user 피드백 왕복): 단일-클립 탭 뷰(동시 6클립=과복잡)
   ·224px 썸네일/호버 확대·타임라인 스트립(프레임 틱=생존/첫-실패 스크린 7색·boarding
   밴드·픽 마커·GT 점·호버 미리보기·클릭 GT) · **포즈 그라운딩**(예시-쿼리: Shift+클릭=
   그 프레임이 통과하는 최소 경계로 sym/yaw 세팅 · 포즈 눈금 사다리[yaw/sym 오름 8장,
   타일 클릭=그라운딩] — render-query "시각→기준=저작"의 동형) · **pitch 다이얼 신설**
   (head_pitch 클립-중앙값 상대 |pc|, 기본 off=셀프테스트 불변; test_0 하방 케이스 과녁,
   결측=통과 — 절대 비교 금지 원칙 유지).
   → **v1 표면 승격 착지 (2026-07-22, track/lk-workbench)**: `momentscan workbench
   [--out --port(8902) --gt --no-jobs]` — 비디오 등록(JobRunner 본체 재사용, likeness
   클로저 잡)→기판 완료 클립 다이얼 해석→클릭 GT 즉시 저장(fixtures/eval 병합-쓰기,
   재기동 복원)의 연구 콘솔. frame_table 단일홈=`surface/workbench.py`(v0.5=main
   5f1bdd9 값-동일 승격 — 전 행 파리티 0 diff·셀프테스트 픽 test_3=[29,511,352]·
   dual_2=[34,1052,662] 재현; pupil/sym=face_signals 단일홈 소비), 캐시=`<out>/
   workbench/cache` mtime+버전(stash 아님=freshness 비등재), chroma=detect.mp4
   디코드(이음매: lk-sampling2 가 parse 에 skin_chroma 착지 시 읽기 교체). 서버=
   `surface/workbench_server.py` 경량 신설(C1 면 무접촉 — api 19/19 불변; 몰튼 내부
   스키마를 계약면에 동결시키지 않기 위해), 프런트=v0.5 이식(`_workbench_html.py`,
   const WB 주입=순수 렌더러; 타임라인·포즈 그라운딩·pitch·분포 지도·yaw 밴드 포함).
   봉인=test_workbench.py(GT 병합·픽 의미론[밴드·pitch]·JS DEF≡python 상수 짝·재기동
   복원·등록 배선 + 코퍼스-게이트 셀프테스트 픽 고정). 이연(v1.1): hair 빈 role 뷰·
   15클립 UI 최적화·S3 등록. 스크래치 E2E(등록→완주→열람)=트랙 보고.

### (완료 기록) P1-④까지의 트랙 — ③ 동결 완료, P1-④ 실패 모드

~~P1-2b color identity~~ → **DONE 5c34f2d**. ~~P1-③ 스키마 동결~~ → **DONE** —
contracts.md **C11** (schema="momentscan.likeness/v1" 도장·필드→소비자 표·additive 규율).
**+ 제품 스코프 확정(user)**: likeness·portrait=**주탑승자만**(aux=측정 신뢰 낮음, 감사 실증) /
highlight=aux first-class("함께한다"는 맥락). 구현=제품 방출 필터만, 스테이지·trace 전원 유지
(aux 센트로이드=상대귀속 rival·aux features=highlight 입력). 코퍼스 15/15 main-only 판정 ✓.
지금: **P1-④ 실패 모드** (감사 ⓐ~ⓔ 입력) — ⓐ두-레인 융합(_F_FUSE_TAU 0.75, 오버라이드
기록) ⓑface_id.low_confidence(p05<0.5) ⓒ~~pose_bin 품질-최고 선발~~(감사 때 선반영)
ⓓsamples.hair(owner hair/face 픽셀비 — **typed headwear로 못 함**: 내려진 재킷 후드를
conf 0.946으로도 hood 오인, mask_1 육안 실증; 세그 직접 측정으로) — 전부 additive, v1 유지.

### (계보) 척추 = 단계 배포 (user 결정 2026-07-03)

**"세 제품 출력에 아직 확신이 없다 → likeness 먼저 확실히 해서 1차 배포·알파테스트,
portrait/highlight는 추가 연구 후 순차 오픈."** 이 결정이 아래 모든 후보의 우선순위를
정렬한다 (contracts.md C1에 products 스위치 등재; 스테이지 의존 ≠ 제품 노출).

**Phase 1 — likeness 확신 + 1차 배포 (지금의 주전선):**
1. ~~**미스티치 조각 자동병합**~~ → **DONE (2026-07-06, 7aa5470)** — stitch tier-2
   상대귀속(중첩0 · cos≥0.40 · 마진≥0.15, 코퍼스 99쌍 측정 앵커; 호스트가 id 유지).
   15/15 판정·replay 0드리프트. 정직 델타: s18 +1 유효관측(조각 프레임 대부분
   게이트-거부 — 실가치는 구성 정확성)·dual_2 +2. viz=lane_fragment_stitch.png.
   부산물: artifact-dep freshness 갭 3번째 실증(detections 재기록이 mtime-fresh
   소비자를 못 stale — --force 필요).
2. ~~**코퍼스 전수 육안 감사**~~ → **DONE (2026-07-06)** — 15클립 21라이더 5렌즈,
   판정 카드=output/l2/audit_likeness_p1.png. **선행 발견: 코퍼스 6클립이 crops/parse/
   fashion 이전 시대 산출물**(fashion=null) → 백필로 전 코퍼스 현대 체인 정렬.
   **건강**: 정체성 무결(coherence 저점 전수 육안=타인 혼입 0, 원인=역광 washout·블러·
   손가림) · portrait_box 헤어 안 자름 · cap_1(마스크+선글라스)/mask_*(마스크)/dual_1
   (scarf·hood 구분) fashion 정확 · separation 중앙값 ~3 (dual_2 4.6).
   **발견(수리 대상, 아래 4에 합류)**: ⓐfashion 불리언-레인 마스크 FP 2건(dual_3 s0
   frac0.511=**scarf 0.915**·test_0 s18 frac1.0=**none 0.852** — 타입 레인이 정답 보유
   → 두-레인 융합 수리; **오랜 watch "dual_3 s0 mask 0.511" = scarf로 해소**) ⓑface_id
   valid-폴백이 저품질 임베딩 흡수(p05<0.5 4명 — 품질 문제, 오염 아님) ⓒpose_bin
   대표가 품질-무관 선발(블러가 hair 입력 대표) ⓓ크롭 타인 혼입(dual_2 right)·후드=
   hair 관측불가 → hair 이음매에 정직한 결측/오염 신호 필요 ⓔdual_1 separation 1.4
   (가림 클립 기하 불안정 — recipe 경계 사례).
2b. ~~**color identity 포팅**~~ → **DONE (2026-07-07)** — Cat W #86-89를 fashion.py에
   착지(방문-집계 Lab K-means k=5 → primary/secondary/highlight/diversity + hex/area/
   n_px/n_frames), likeness.json rider 최상위 `color_identity`로 배달·report 팔레트 칩.
   **포팅이 신규 문제를 낳고 풀었다 — 소유권**: 원본은 단일-인물 per-image라 없던
   "프레임 안 타인 옷" 오염(감사 ⓓ 재현: cap_1 전경 패딩이 팔레트 지배) → **소유자
   영역-성장 규칙**: 중심-최근접 얼굴(이목구비-자격: 손=skin 덩어리 배제 — dual_1
   전멸 원인이었음) 씨앗, cloth=얼굴∪목 직접-인접·모자류=+헤어 다리, 타인 얼굴과는
   **접촉-다수결 배정**(이진 taint는 어깨-맞댄 duo 전멸). 판정: 21/21 팔레트·실물
   부합(카키/파랑저지/핑크 등, 겨울-다크 지배=정직) 카드=lane_color_identity.png.
   **잔류 한계(기록)**: ①좌석 하네스/RACE81 시트커버=cloth 오분류 혼입 → **C9 preset
   장비-색 제외 리스트가 정답 자리** ②타인 얼굴이 프레임 밖이면 접촉-누수 못 끊음
   (풀링이 희석) ③착용 마스크=skin 분류라 팔레트 제외 ④dual_1 s0 n_frames=1 얇음
   (n_frames가 신뢰 표기). clothing 6축(#80-85)은 별도 판단 유지.
3. **likeness.json 스키마 동결 → C-계약 승격** — **face_recipe 어댑터의 입력 계약**으로서
   동결 (필수/선택 필드를 recipe 요구에서 도출; data-contract.md stale 해소 겸;
   "인터페이스 정의 빠른 공유 의무"의 실체). **recipe 측 계약 메모(user)**: hair_match
   결과는 face-recipe에 당연 포함 · **recipe→Blender 프리뷰 필요**(임의 3D 얼굴 모델에
   적용한 렌더) — 이중 트랙: ①기하 검증=repo의 canonical_face_model.obj(468 토폴로지
   = likeness center 직접 변형, 자산 0) ②캐릭터 프리뷰=**MPFB2**(CC0·얼굴 몰프 수백 축→쉐이프키·
   과장=캐리커쳐·클레이 룩; VRoid는 user 기각 — 애니 스타일; 최종 모델=디자인팀 제공
   예정이라 임시) / 차선 FLAME(⚠연구 라이선스) — StdGEN(../hair, 단일이미지→분해
   캐릭터 생성)은 별도 레인. **MICA**(Zielon, user 발견): ArcFace 임베딩→FLAME β(정체성
   300·메트리컬·중립) — **face_id→β→쉐이프키의 기성 다리** + β-공간 separation=감사 보강
   후보(P1-② 뒤 파일럿). ⚠MPI 비상업+상업용-학습-금지 명시(우회 증류 불가) — 알파 내부
   검증 한정, 상업=협상 또는 자체 사상(landmark center→디자인팀 몰프 회귀).
4. ~~**실패 모드의 정직한 표면화**~~ → **DONE (2026-07-07, 48e07ab)** — 감사 ⓐ~ⓓ 전부
   additive로 v1 내 착지: ⓐmask 두-레인 융합(τ=0.75, `mask_override` 기록 — dual_3 s0
   scarf FP 해소·진짜 착용자 보존·역방향 승격은 증거 없어 미적용) ⓑ`face_id.low_confidence`
   (p05<0.5 희석 주의 — main 전원 floor 위=코퍼스 휴면, 알파 신규 입력의 자리)
   ⓒbin-내 최선명 선발(감사 때 선반영) ⓓ`samples.hair`(owner hair/face 픽셀비, τ=0.1,
   observable=false→hair_match 건너뜀 — **typed headwear 기각**: 내려진 재킷 후드를
   conf 0.946으로 오인[mask_1 육안]; 세그 픽셀이 가림[≤0.049] vs 맨머리[≥0.5]를
   10× 여백으로 가름). 판정 카드=lane_failure_modes.png.
   **⚠user 교정(2026-07-07)**: 가림 4명 중 **test_12는 오판** — 실물=맨머리+얼굴
   뒤 빨간 의자(등받이 높은 차량)를 내가 후드로 오독; frac 0.0은 세그 오검출 의심
   (빨간 등받이 교란?). 방향은 보수적(FP=기회 상실이지 오염 아님)이나 원인 조사
   = user 동행 항목. 확정 가림=dual_1 s0(후드)·dual_2 s1(후드+앞머리)·cap_1 s1(캡).
   **프로세스 교훈: likeness 확신의 육안 참값은 단독 확정 금지 — user 확인 필수.**
   잔여(ⓓ 후속): 크롭 타인 혼입(dual_2 right bin) 신호는 face-count 세그 필요 — 보류.
   ⓔdual_1 sep 1.4=경계 사례 기록 유지(수리 아닌 관찰).
5. ~~**배포 이음매**~~ → **구현 DONE (2026-07-03)** — `service.py`(serve-http) +
   `eureka.py` + `result.json`; e2e = 202→245s 완주→재요청 6ms 무재계산·outputs=열린
   제품만·mock-Eureka 4단·로컬 배송. 운영 = docs/deploy-alpha.md.
   **남은 검증**: ⓐ S3 실계정 스모크(AWS 첫 배포 때 — boto3는 doctor ○ 선택 항목)
   ⓑ 회사 Eureka 실서버 등록(URL·앱 네이밍·인바운드 3종 확인 필요)
   ⓒ 알파 부하에서 단일-워커 처리량 관측(2000/day = 43s/clip 필요 vs 현행 ~4min/clip
   콜드런 — 알파 볼륨으로 시작, 스케일은 노드 추가=같은 이름 등록).
6. **알파 피드백 계기**: 무엇을 물을지 설계 (pairwise 원칙 — "이 요약이 그 사람 같나").

**Phase 2 — portrait 오픈 (알파 진행과 병행 연구):** portrait ② query-synthesis ·
계절/사용자 쿼리 preset · 우발적-가림 게이트(dual_1) — 굴욕샷 방어가 곧 제품 신뢰.

**Phase 3 — highlight 오픈 (연구 밀도 최대):** VMR 레인(아래) · desirability 후속
(mouth_vis 조건화·WHEN/WHICH energy 재편·창 형태 방출) · C9 preset(방출 τ·CLIP_LEN).

---

**VMR 레인 (user 확정 2026-07-03: "VMR 관점에서의 시도도 해봐야겠다" — Phase 3 연구 본체)** — highlight의 메인
방법론 = Zero-Shot Video Moment Retrieval (memory core-criterion-source에 정식화; 언어 쿼리로
순간 검색, CLIP이 못 하는 표정/감정/포즈는 frozen 신호→구조화 문장으로 = 두-레인 서술 분할).
우리 필터: E011로 경계 회귀는 불필요 — 수입 대상 = 관련도 채점·장면 인코더·오케스트레이션 패턴.
사다리 (순서 = 값싼 것부터):
1. **Qwen2.5-VL 네이티브 temporal grounding 스모크** — 이미 캐시된 3B의 미사용 기능
   (MRoPE 절대시간, 초 단위 타임스탬프 출력). 선행 = env: torchvision·qwen-vl-utils 설치
   (Q2 LoRA 메모에도 기록된 그 작업). 실험 = 서브샘플 프레임 + EXPECTATION 쿼리 → 타임스탬프
   vs 우리 WHEN 피크/highlight.json 세그 대조 = 독립 2차 의견. 판정 = 코퍼스 15클립에서
   일치/불일치 분해 + 불일치 육안.
2. **장면 레인 승격**: 이미지-CLIP → 비디오-레벨 임베딩 (InternVideo2/LanguageBind/ViCLIP 중
   7.6GB에 맞는 것) — "코너링의 긴박함" 같은 모션 맥락은 이미지 단위로 안 보임.
   SCENE_PROMPTS 매칭 교체 A/B. (SigLIP 차단은 sentencepiece 미설치였음 — 설치로 해소 가능.)
3. **Moment-GPT 쿼리-재서술 규율** (arXiv 2501.07972): EXPECTATION 저작 시 언어 편향 제거
   단계 도입 — 코드 수입 아닌 프롬프트 규율.
4. (라벨 축적 후) QVHighlights 가족 saliency 헤드 fine-tune — pairwise 세그 라벨 재활용. 보류.
연결: highlight-lang 파이프(구축됨, select 미통합)가 이 레인의 본체 — VMR 시도의 판정자는
동결 세그 쌍 + 육안, 성공 기준 = generic WHEN이 놓친 맥락-순간을 언어 쿼리가 회수하는가.

(기존 "기타 후보"는 위 Phase 1~3으로 재배열됨 — 자동병합→P1 · 우발적-가림→P2 ·
desirability 후속·C9→P3.)
~~highlight.json deliverable 분리~~ → DONE 7d96185 (2026-07-03 **highlight 졸업**, 파일+산출물
한 묶음: products/highlight.py·highlight.json·candidates=likeness 전용·소비자 5곳 이주·
15/15 세그 스냅샷 동일·rescore 불변; user 지적 "products/ ls에서 highlight만 select.py"가 트리거).
watch: dual_3 s0 mask 0.511 육안 · pitch 부호 시각 고정 · data-contract.md stale ·
기회주의 refactor 잔여(rank 4·8·9·10·11).

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

## 이식-가능 재고 인벤토리 (2026-07-15 commons-audit 실측 — 기록만, 분리 금지)

도메인-지식 0(또는 얇은 껍질)이라 조직-범용 이식이 가능한 조각들. **전부
제2소비자 미실존 또는 졸업석 예약** → 지금 분리하지 않는다(visualbind 전례).
졸업 게이트가 열릴 때 이 목록이 절단선 지도가 된다.

1. eureka.py 전체(192 LOC, stdlib-only) — TokenProvider+EurekaClient → visualserve
2. media.py 전체(66 LOC) → visualbase 근연
3. freshness.py 엔진(~117 LOC, FIRST_PARTY/INFRA 인자화 필요) → visualpath
4. service.py 프리미티브 — fetch_source/deliver/_split_s3/_gpu_snapshot/
   node_identity(≈78 LOC 완전범용) + build_server/JobRunner 골격(≈210 LOC) → visualserve
5. stash IO 3종(_validate/_pl_dtype/_to_table, 31 LOC) → visualstash
6. replay diff 3종(_close/_json_diff/_parquet_diff, ≈51 LOC)
7. label_server.py(175 LOC) — 라벨링 하니스
8. subjects/stitch.py(≈164 LOC) — 코사인 union-find re-id 병합
9. apicheck 하니스 골격(≈60 LOC) + daemon.serve 골격(60 LOC, visualbus 의존 주의)

레포-간 중복 실측: appearance-engine→momentscan 코드 임포트 0건, parquet IO·
몽타주 헬퍼 중복 0건 — 현존 코드 제2소비자는 plugins→stash(승인된 이음매)뿐.
momentgen은 likeness.json 파일 계약만 소비(코드 의존 금지 명시) — momentgen이
회사 디스패치 대상이 되는 사건 = visualserve 단계3 게이트의 조기 트리거.

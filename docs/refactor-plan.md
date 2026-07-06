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

### ▶ 다음 재개 (2026-07-04~) — 척추 = 단계 배포 (user 결정 2026-07-03)

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
2. **코퍼스 전수 육안 감사** — **자(尺) = face_recipe 적합성** (user 2026-07-06:
   likeness→face_recipe[blendshape 메타데이터]→3D 캐릭터 개성 주입이 목적;
   memory likeness-face-recipe-purpose): ①기하 center/axes=재현(drift)+**separation**
   (사람-간≫사람-내 = "개성 주입" 성립 조건)+ARKit 사상 가능성 ②face_id=diffusion
   개인화 경로(별개 소비자) ③fashion=캐릭터 액세서리 입력(타입 정확도; mask/cap=에지)
   ④**멀티뷰 샘플=hair 이음매 적합성**(hair_match Gemini recommend의 "같은 사람 1~3뷰"
   입력 — 측면 커버리지·크롭이 헤어를 자르는가) ⑤n_obs. 판정 카드로 남김.
2b. **color identity 포팅** (user 2026-07-06: "의상 기반 컬러 팔레트도 이 작업에 포함") —
   출처 = `../appearance-engine/component2/color_identity.py` **Cat W #86-89**:
   통합 마스크(cloth+hat+glasses+earring+necklace = "외부 stylistic surface",
   헤어/얼굴 자연색 제외) → Lab K-means k=5 → primary/secondary/highlight(최고 채도·
   면적>5%)/palette_diversity(Shannon). momentscan판 = **방문-집계**(프레임별이 아니라
   방문 전체 통합 팔레트, fashion 리딩과 같은 judgeable-코호트 조건) → likeness.json
   `color_identity` 필드. **스키마 동결(3) 전에 착지** — recipe의 의상 팔레트 입력.
   (clothing 타입 6축 Cat W #80-85는 FashionCLIP 프롬프트 세트 재활용 후보 — 별도 판단.)
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
4. **실패 모드의 정직한 표면화**: n_obs 부족·가림-지배·스티치 잔여 의심 시 확신 대신
   불확실성 필드 — 알파에서 신뢰를 깎는 건 틀린 답이 아니라 *자신만만한* 틀린 답.
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

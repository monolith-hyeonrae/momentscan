# preset 인벤토리 — 정책/임계값 상수 전수 (R8, 2026-07-15)

> C9 preset의 착지 지도. **O = preset 후보**(다른 시설·기구·카메라·운영이면
> 달라질 값 — race981 preset이 소유해야 할 자리) / X = 알고리즘·프로토콜 내재 /
> 판단불가 = 통계 가드 성격(대부분 fps·클립 길이에 간접 의존). 코드 무변경 —
> 이 문서는 지도이지 마이그레이션이 아니다. 생성 = preset-inventory-scan
> 워크플로(6 파일군 병렬, 근거 앵커 포함). likeness ⑦(phase 조건화)과 C9
> preset 설계가 이 표에서 O 항목을 끌어다 쓴다.


## P1 likeness

| 상수 | 값 | 위치(파일:라인) | 의미 | preset 후보(O/X/판단불가) + 근거 |
|---|---|---|---|---|
| CLIP_LEN_S | 3.0 | highlight.py:49 | 배달(하이라이트 클립) 고정 창 길이(초) | O — 주석 자체가 "프리셋 소유 파라미터(릴 템플릿·어트랙션별 규격); 여기는 기본값" 명시 |
| CLIP_LEAD_FRAC | 1/2 | highlight.py:50 | 창 안에서 WHEN 피크의 위치(대칭 캡처) | O — 릴 규격의 일부(리드/여운 비율), Live Photo 대칭 채택은 제품 결정이지 알고리즘 필연 아님 |
| VAL_EMIT_FLOOR | -0.1 | highlight.py:51 | 창 평균 valence가 이 미만이면 joy 축 실패(찡그림 창 방출 금지) | O — "긍정 순간" 정의의 임계, 어트랙션(공포 라이드 등)마다 반대일 수 있음(EXPECTATIONS의 thrill_tense와 충돌 가능) |
| AROUSAL_EMIT_TAU | 0.30 | highlight.py:62 | thrill/energy 축 방출 임계(창 평균 arousal) | O — 특정 코퍼스 스윕(test_3/test_0 s2)으로 앵커한 값, 시설·카메라·고객층 바뀌면 재스윕 대상 |
| MAX_PHRASE_S | 12.0 | highlight.py:63 | 악구 최대 길이 캡("순간은 챕터가 아니다") | O — 제품 제약(방출물 규격 계열), 어트랙션 이벤트 지속시간에 따라 달라질 수 있음 |
| (인라인) min finite | 10 | highlight.py:85 | WHEN 유효 프레임이 10 미만이면 세그먼트 시도 포기 | 판단불가 — 퇴화 입력 가드지만 fps·클립 길이에 묶인 카운트라 환경 따라 스케일 필요 여지 |
| (인라인) 스무딩 창 | 3 | highlight.py:87 | rolling_median 창(1-프레임 스파이크 제거) | 판단불가 — 스파이크 킬 목적은 알고리즘 내재나, 프레임 수 기준이라 fps 바뀌면 실효 시간이 변함 |
| (인라인) half-height | 0.5 (× peak) | highlight.py:98 | 악구 경계 = 피크 반높이 확장 | X — "half-height arc"가 악구 정의 그 자체(알고리즘 내재) |
| (인라인) gap_ms | 2000 | highlight.py:102 | 관측 공백 >2s면 악구 절단(안 보이던 구간을 가로지르는 악구 없음) | 판단불가 — 원리는 내재적이나 2s라는 수치는 트랙 관측 밀도(카메라 배치·검출률)에 의존 |
| (인라인) min arc | 3 (프레임) | highlight.py:115 | 악구 최소 길이("an arc, not a blip") | 판단불가 — 취지는 내재적, 수치는 fps 종속(6fps에서 0.5s) |
| (인라인) kind-sep 배율 | 0.5 (× median pairwise dist) | highlight.py:142 | 종류-중복 억제 임계 τ = 쌍거리 중앙값의 절반 | 판단불가 — 데이터-적응형이라 절대값은 아니나 0.5 배율 자체는 중복 허용도 정책 |
| max_overlap_ms | 0.25 × CLIP_LEN_S × 1000 | highlight.py:143 | 두 세그먼트 창 겹침 허용 상한(창의 25%) | O — "같은 초를 두 번 판다" 방지의 허용치, 방출 규격 계열 정책 |
| (인라인) valence 가중 | 3.0 | highlight.py:185 | 드라이버 분해 표시용 when = max(impact, rarity, scene, 3·val⁺)의 val 가중 | 판단불가 — 가중치 자체는 정책이나 정본은 select.py의 WHEN 공식(여기는 미러) — 단독 preset화하면 드리프트 위험, select와 한 몸으로 |
| fps 기본값 | 6 | highlight.py:238 / highlight_lang.py:163 | 프레임 채점 샘플링 fps 기본 | 판단불가 — 파이프라인 공통 샘플링 관습(스테이지 간 정합 필요), 배포 환경보다는 기판 계약에 가까움 |
| top_k 기본 (import) | TOP_K (select.py 소유) | highlight.py:39,238 | 클립당 방출 세그먼트 수 상한 | O — 방출 개수는 릴 규격/운영 정책(정의 위치는 select.py라 인벤토리는 그쪽에서) |
| EXPECTATIONS["default"] | go-kart hill-descent joyful 문장 | highlight_lang.py:37-49 | 어트랙션별 하이라이트 기준 문장(LLM judge의 기준) | O — 파일 주석이 명시적으로 "The EXPECTATION is a preset = the context control"; 어트랙션마다 문장만 교체 |
| EXPECTATIONS["thrill_tense"] | 공포 라이드 tense 문장 | highlight_lang.py:45-48 | 다른 어트랙션 기준 예시(같은 기계, 다른 검색) | O — 위와 동일, preset 사전의 항목 |
| SCENE_PROMPTS | 5개 장면 문장 (starting area / downhill go-kart / dry grass·reeds / building / fast motion) | highlight_lang.py:52-58 | CLIP 장면 분류 프롬프트 | O — 내용이 이 시설(고카트 언덕·갈대밭) 전용, 다른 시설이면 문장 전면 교체 |
| CLIP_MODEL | "openai/clip-vit-large-patch14" | highlight_lang.py:60 | 장면 리더 모델 ID | 판단불가 — 시설별이 아닌 알고리즘 기판 선택이나, 배포(하드웨어/라이선스) 사정으로 바뀔 수는 있음 — preset보다는 model-inventory 소관 |
| JUDGE_MODEL | "Qwen/Qwen2.5-VL-3B-Instruct" | highlight_lang.py:61 | LLM judge 모델 ID | 판단불가 — 위와 동일; 단 JUDGE_CHUNK 등 동반 상수가 이 모델 거동에 맞춰 검증됨(교체 시 세트로) |
| TOP_K | 24 | highlight_lang.py:62 | 제네릭 WHEN이 LLM에 제안하는 후보 수 | O — 비용/처리량(2000 clips/day) 정책, 운영 환경 따라 조정 대상 |
| JUDGE_CHUNK | 6 | highlight_lang.py:63 | LLM이 한 번에 판정하는 후보 수 | X — 3B judge의 repetition lock-in 회피용으로 실증된 모델-내재 값(JUDGE_MODEL에 종속) |
| CAND_SEP_S | 1.5 | highlight_lang.py:64 | 후보 간 최소 시간 간격(중복 제거) | O — 순간 밀도(어트랙션 이벤트 템포)에 따라 달라질 수 있는 정책 |
| IMPACT_BURST | 3.0 | highlight_lang.py:65 | impact가 이 이상이면 "sudden burst"로 서술 | 판단불가 — impact가 z⁺ 평균이라 단위는 준-보편적이나, 서술 문턱 자체는 튜닝된 정책 |
| (인라인) jaw 문턱 | 0.22 | highlight_lang.py:75 | jaw open이 이 초과면 "mouth wide open" 수식어 | 판단불가 — blendshape 기하 문턱(좌표계약에 묶임)이지만 값 자체는 튜닝치 |
| (인라인) valence 밴드 | 0.55 / 0.25 / 0.1 / -0.15 | highlight_lang.py:76,78,80,82 | 서술 문장용 valence 4단 양자화(big joyful / happy / mild / tense) | 판단불가 — 서술 정책이라 preset 성격이 있으나 EXPECTATIONS·judge 프롬프트와 의미 결합(단독 교체 시 언어-매칭 정합 붕괴) |
| (인라인) p90 fallback | 1.0 | highlight_lang.py:199 | baseline 부재 시 p90 기본값(rel_bright 사실상 비활성) | X — 결측 방어 기본값(퇴화 처리), 환경 따라 달라질 값 아님 |
| (인라인) fallback 소스 경로 | ~/Videos/reaction_test/{clip_id}.mp4 | highlight_lang.py:203 | detect_h264 부재 시 원본 폴백 경로 | O — 개발 머신 하드코딩 경로, 배포 환경이면 반드시 달라짐(preset이라기보다 ops 설정이나 코드 상수로 남으면 안 됨) |
| (인라인) 크롭 확대 배율 | 3.4 (w), 3.8 (h) | highlight_lang.py:213 | 장면 읽기용 wide crop 크기(bbox 대비) | O — 카메라 화각·피사체 거리·프레이밍에 종속, 시설/카메라 마운트 바뀌면 재조정 |
| (인라인) 크롭 세로 오프셋 | 0.10 (× h) | highlight_lang.py:214 | wide crop 중심을 아래로 10% 이동(몸/장면 포함) | O — 위와 동일한 프레이밍 상수 |
| (인라인) 토큰 예산 | 48 × chunk + 64 | highlight_lang.py:153 | judge 응답 max_new_tokens(항목당 짧은 이유 포함 예산) | X — 프롬프트 프로토콜("N: score - reason")에 맞춘 모델-프로토콜 상수 |
| (인라인) 점수 스케일 | 10.0 (min·나눗셈) | highlight_lang.py:158 | 0-10 점수를 0-1로 정규화(프롬프트 규격 고정) | X — 프롬프트가 선언한 프로토콜 고정값 |


## P2 portrait + select 기판

| 상수(이름 또는 인라인 값) | 값 | 위치(파일:라인) | 의미 한 줄 | preset 후보 여부(O/X/판단불가) + 근거 |
|---|---|---|---|---|
| `N_LM` | 478 | likeness.py:67 | MediaPipe 얼굴 랜드마크 개수 (배열 reshape 계약) | X — 좌표계약(정준 프레임 basis 478) 고정 프로토콜 값 |
| `BIN_EDGE_DEG` | 15.0 | likeness.py:69 | \|yaw−frontal\| < 이 값이면 frontal 빈, 아니면 left/right (hair 멀티뷰 pose 빈 경계) | O — 카메라 배치·기구 지오메트리에 따라 빈 경계가 달라짐 (CAMERA_FRONTAL_DEG와 짝) |
| `CAMERA_FRONTAL_DEG` (임포트) | 12.0 (pose.py:34 정의) | likeness.py:35,254 | 이 카메라의 경험적 정면 yaw (E002, off-axis 마운트) | O — 정의부 주석부터 "this camera's EMPIRICAL frontal"; 시설/카메라마다 필히 재보정 |
| `_IDX` (메시 인덱스 14개) | brow_top=10, chin=152 등 | likeness.py:74-77 | 인체계측 비율 계산용 표준 메시 정점 인덱스 어휘 | X — MediaPipe 468 메시 토폴로지에 결박된 알고리즘 내재 상수 |
| 인라인 `h < 5` | 5 | likeness.py:102 | split-half drift 계산 최소 반쪽 표본 수 (미만 시 NaN) | 판단불가 — 통계 최소표본 성격이나 fps·클립 길이(운영환경)에 민감 |
| 인라인 `>= 10` (keep.sum) | 10 | likeness.py:121 | valid 필터 적용 후 남는 프레임이 이 미만이면 필터 포기 (degrade 가드) | O — FACE_ID_MIN_FRONTAL과 동일 패턴의 최소 관측 정책; fps·탑승 시간 의존 |
| 인라인 `len(lm) < 10` | 10 | likeness.py:123 | 트랙 리딩 자체의 최소 프레임 수 (미만 시 트랙 스킵) | O — 최소 관측 정책, 프레임레이트·구간 길이에 따라 달라질 값 |
| 인라인 `1e-18` | 1e-18 | likeness.py:136 | EVR 분모 0 방지 epsilon | X — 수치 안정 가드, 환경 무관 |
| 인라인 `[:5]` (evr) | 5 | likeness.py:136,266 | 기록하는 EVR 상위 고유값 개수 | X — 리포트 포맷 크기, 정책 아님 |
| 인라인 `Vt[:3]` / `range(3)` | 3 | likeness.py:137,155 | 라벨링·스코어 계산하는 상위 PC 개수 | 판단불가 — 분석 깊이 선택이나 시설 의존성은 없음 (리포트 성격에 가까움) |
| 인라인 `m.sum() > 10` | 10 | likeness.py:159 | PC-특징 상관 계산 최소 유한 표본 수 | 판단불가 — 통계 가드이나 위 최소 관측 정책들과 같은 축 |
| 인라인 `1e-9` | 1e-9 | likeness.py:159 | 표준편차 0 (상수 특징) 상관 계산 배제 epsilon | X — 수치 안정 가드 |
| 인라인 `[:2]` (top_corr) | 2 | likeness.py:161 | 축 라벨에 기록하는 상위 상관 특징 개수 | X — 리포트 포맷 크기 |
| 인라인 `n != "_neutral" and not startswith("eyeLook")` | 문자열 필터 | likeness.py:186-187 | 표정 레벨 계산에서 중립·시선 blendshape 제외 (시선≠표정) | X — 표정 정의 자체에 내재한 알고리즘 규약 (ARKit 이름 계약) |
| 인라인 `expr_level < 0.3` | 0.3 | likeness.py:189 | "calm(무표정)" 프레임 판정 임계 (blendshape max) | O — 주석이 야외 squint로 calm 0.3~1.8%뿐이라 증언; 실내외·조명 등 운영환경에 따라 calm 정의가 흔들림 |
| 인라인 `calm.sum() >= 10` | 10 | likeness.py:191 | calm_center 계산 최소 calm 프레임 수 | 판단불가 — 최소 표본 가드, fps 의존 가능 |
| 인라인 `np.percentile(B, 90)` | 90 | likeness.py:196 | blendshape 프로파일 시그니처의 상단 통계 (profile=[median,p90]) | X — 소비자(Blender shape key) 대면 스키마 정의의 일부 |
| 인라인 `np.argsort(-med)[:5]` | 5 | likeness.py:197 | median_top에 기록하는 상위 blendshape 개수 | X — 리포트 포맷 크기 |
| 인라인 `lam = 0.01 * len(fx)` | 0.01 | likeness.py:215 | 무표정 회귀 ridge 정규화 강도 (표본수 비례) | X — 회귀 하이퍼파라미터, 알고리즘 내재 (시설 아닌 모델 문제) |
| 인라인 `h >= 30` | 30 | likeness.py:229 | neutral split-half drift 계산 최소 반쪽 표본 수 | 판단불가 — 외삽 위험 측정기의 통계 가드이나 클립 길이·fps 의존 |
| 인라인 `argsort(dist_c)[:3]` | 3 | likeness.py:252 | center-nearest 대표 프레임 샘플 개수 | 판단불가 — 산출물(정준 이미지 후보) 개수 = 소비자 정책일 수 있으나 시설 의존은 아님 |
| `FACE_ID_MIN_FRONTAL` | 10 | likeness.py:276 | clean-frontal 프레임이 이 미만이면 face_id 센트로이드를 `valid` 전체로 폴백 (측면 위주 트랙 기아 방지) | O — 명시적 폴백 정책; 카메라 각도·fps에 따라 frontal 프레임 수 분포가 달라짐 |
| `FACE_ID_P05_FLOOR` | 0.5 | likeness.py:277 | coherence_p05가 이 미만이면 low_confidence 플래그 (소비자 주의 신호, 게이트 아님) | O — 품질 신호 임계; 코퍼스(P1-② 감사) 보정값으로 임베딩 모델·환경 바뀌면 재보정 |
| 인라인 `np.percentile(cos, 5)` | 5 | likeness.py:324 | face_id 응집도 지표를 5퍼센타일로 정의 | X — 지표 정의(꼬리 통계 선택), FACE_ID_P05_FLOOR의 자 |
| 인라인 `"buffalo_l"` | "buffalo_l" | likeness.py:326 | 임베딩 출처 모델명 기록 (provenance 라벨) | X — 기록값; 실제 모델 선택은 tubelets 스테이지 소유 |
| `_F_EYEWEAR` | 0.03 | likeness.py:337 | glasses_frac > 이 값 → 안경류 착용 프레임 판정 | O — 소스 주석이 직접 "preset policy, calibrated on cap_1" 선언 |
| `_F_SUN_LUM` | 0.7 | likeness.py:337 | 안경 착용 중 eye_lum_rel < 이 값 → 선글라스 판정 | O — 동일 (cap_1 보정; 조명 환경 의존) |
| `_F_MASK` | 0.01 | likeness.py:337 | mouth_vis < 이 값 → 마스크 프레임 판정 | O — 동일 (cap_1 보정) |
| `_F_HAT` | 0.05 | likeness.py:337 | hat_frac > 이 값 → 모자 프레임 판정 | O — 동일 (cap_1 보정) |
| `_F_WORN` | 0.5 | likeness.py:337 | 프레임 비율 ≥ 이 값 → "지속 착용(worn)" 결론 | O — 동일; 착용 지속성 정의는 탑승 패턴 의존 |
| `_F_MIN_JUDGEABLE` | 10 | likeness.py:338 | clean-frontal 행이 이 미만이면 전체 행 폴백 (측면 위주 트랙) | O — FACE_ID_MIN_FRONTAL 패턴의 최소 관측 정책 |
| `_F_FUSE_TAU` | 0.75 | likeness.py:339 | typed covering 신뢰 ≥ 이 값이면 parse mask 불리언 기각 (두-레인 융합) | O — 주석 명시 "fusion = preset"; FashionCLIP 신뢰 스케일 보정값 (dual_3 근거) |
| `_HAIR_OBS_TAU` | 0.1 | likeness.py:340 | hair/face 픽셀비 중앙값 < 이 값 → hair 관측불가 (후드-업) | O — 관측가능성 판정 임계, 크롭/카메라 스케일 의존 |
| 인라인 `fill_null(1.0)` | 1.0 | likeness.py:385 | eye_lum_rel 결측 시 밝음(=선글라스 아님)으로 간주하는 극성 기본값 | 판단불가 — 결측 처리 규약이지만 극성 선택은 정책적 (보수 방향 선택) |
| 인라인 `sun_f >= 0.4` | 0.4 | likeness.py:389 | 안경 착용자 중 선글라스 프레임 비율 ≥ 이 값 → "sunglasses" 타입 확정 | O — _F_* 군과 같은 cap_1 보정 계열의 인라인 잔존값 (이름 없는 매직) |
| 인라인 `0.3 < f < 0.7` | 0.3 / 0.7 | likeness.py:401 | 착용 비율 중간대 → 'variable'(탑승 중 착탈) 판정 밴드 | O — 착탈 해석 밴드, 탑승 시간·행동 패턴 의존 정책 |
| 인라인 `"momentscan.likeness/v1"` | 문자열 | likeness.py:460 | 출력 스키마 버전 태그 (P1-③ 동결, contracts.md C11) | X — 계약 고정값; 변경 = 버전 규율(additive만 무버전) 대상 |


## P3 highlight(+lang)

| 상수(이름 또는 인라인 값) | 값 | 위치(파일:라인) | 의미 한 줄 | preset 후보 여부(O/X/판단불가) + 근거 |
|---|---|---|---|---|
| `fps_default` / `fps` 기본 | 6 | service.py:172, service.py:481, pipeline.py:177 | 분석 프레임 샘플링 기본 fps | **O** — 카메라·기구·클립 길이에 따라 달라질 도메인 파라미터; Job 필드/CLI로 이미 노출되나 기본값이 3곳에 산개(단일홈=preset 자리) |
| `open_products` 기본 | `("likeness",)` | service.py:173, service.py:482 | 단계 배포에서 기본으로 여는 제품 집합 | 판단불가 — 운영환경별로 다르나 도메인 임계값이 아닌 배포 스위치(CLI 인자화 완료); preset보단 배포 구성에 가까움 |
| `_GPU_CACHE` TTL | 5.0 s | service.py:148 | nvidia-smi 스냅샷 캐시 주기 | X — 관측 인프라 튜닝 값 |
| nvidia-smi `timeout` | 5 s | service.py:153, 157 | GPU 조회 서브프로세스 타임아웃 | X — 인프라 |
| `HEALTH_LOG_S` | 30 s | service.py:470 | health 게이지의 주기 스냅샷 로그(Loki 레인) 간격 | X — 관측 인프라(Zabbix 폴링의 로그판) |
| `port` 기본 | 8080 | service.py:354, 481 | HTTP 서비스 기본 포트 | X — 인프라, CLI 재정의 |
| `bind` | `"0.0.0.0"` | service.py:354 | 리슨 주소 | X — 인프라 |
| `APP_NAME` | `"momentscan"` | service.py:44 | 서비스/Eureka 등록 이름 | X — 시스템 정체성(계약; `app_name` 인자로 재정의 가능) |
| `RESULT_SCHEMA` | `"momentscan.result/v1"` | service.py:45 | C1 Result 스키마 버전 태그 | X — 계약 고정값(변경=버전 절차) |
| health `"status"` 값 | `"UP"` | service.py:345 | health 상태 문자열 | X — Spring health 관례(Eureka/Zabbix 소비 계약) |
| swagger CDN URL | `unpkg.com/swagger-ui-dist@5` | service.py:131, 133 | /docs UI 자산 출처 | X — 배포 인프라(폐쇄망이면 로컬 서빙 필요하나 preset 아닌 배포 이슈) |
| 런타임 레코드 경로 | `~/.cache/momentscan/http-{port}.json` | service.py:525 | `momentscan status`의 로컬 발견 관례 지점 | X — 관례/프로토콜 |
| `GROUP` | `"MOMENT_SCAN_PROCESS"` | company.py:34 | control ProcessGroup enum과 동일해야 하는 echo 문자열 | X — 회사 계약 고정 |
| `MAX_INFLIGHT` | 1 | company.py:35 | 동시 수락 잡 수(초과=10002로 분산 유도) | **O** — "단일 GPU 7.6GB" 하드웨어 가정의 하드코딩; 노드 GPU/워커 구성 따라 달라질 운영 파라미터 |
| `OK` 코드 | `"00000"` | company.py:38 | ApiReturnModel 수락 코드 | X — mommos 계약(jar 판독) |
| `BUSY` 코드 | `"ACTIVITY-VIDEO-PROCESS.10002"` | company.py:39 | 포화 응답 코드(control이 벌점 없이 다음 워커 시도) | X — 회사 계약 |
| `WRONG` 코드 | `"ACTIVITY-VIDEO-PROCESS.10001"` | company.py:40 | 잘못된 파라미터 응답 코드 | X — 회사 계약 |
| clip_id 파생 규칙 | `f"wf{wf}-{media_type}"` | company.py:95 | workflowId→clip_id 멱등 키 관례 | X — 프로토콜 관례(변경 시 멱등성 깨짐) |
| 콜백 URL 패턴 | `{control}/process/moment-scan/{wf}` | company.py:139 | 완료 콜백 목적지 경로 | X — 회사 계약 |
| 콜백 `timeout` | 15 s | company.py:158 | 완료 콜백 POST 타임아웃 | X — 네트워크 인프라 |
| `RENEWAL_S` | 30 s | eureka.py:36 | Eureka heartbeat(렌트 갱신) 주기 | X — Spring Cloud 기본과 정합해야 하는 프로토콜 값(서버 설정과 짝) |
| `DURATION_S` | 90 s | eureka.py:37 | heartbeat 부재 시 축출 리스 기간 | X — 동일(Eureka 서버 기본 정합) |
| `TOKEN_MARGIN_S` | 60 s | eureka.py:38 | 토큰 만료 이만큼 전부터 선갱신(경계 레이스 방지) | X — 인증 인프라 안전 마진 |
| OAuth `scope` 기본 | `"api.write api.read"` | eureka.py:49, service.py:498 | client_credentials 요청 scope | X — 회사 인증 서버 계약(env `EUREKA_TOKEN_SCOPE` 재정의) |
| `expires_in` 폴백 | 300 s | eureka.py:72 | 토큰 응답에 expires_in 부재 시 가정 수명 | X — 프로토콜 방어 기본값 |
| 토큰 발급 `timeout` | 15 s | eureka.py:69 | 토큰 POST 타임아웃 | X — 인프라 |
| Eureka 호출 `timeout` | 10 s | eureka.py:122 | 등록/heartbeat/해지 HTTP 타임아웃 | X — 인프라 |
| 더미 목적지 IP | `"10.255.255.255"` | eureka.py:84 | 외향 인터페이스 IP 발견용(실패킷 미발신) | X — 알고리즘 내재 트릭 |
| `securePort` | 443 (`@enabled: false`) | eureka.py:146 | 등록 payload 보안 포트 필드 | X — Eureka 프로토콜 고정(비활성 선언) |
| `dataCenterInfo` | `"…InstanceInfo$DefaultDataCenterInfo"` / `"MyOwn"` | eureka.py:151-152 | Eureka 역직렬화 계약 — 정확히 이 문자열이어야 함 | X — 프로토콜 고정 |
| `health_path`/`status_path` | `"/health"` / `"/info"` | eureka.py:96-97 | 등록 시 광고하는 헬스/상태 URL 경로 | X — service.py 라우트 관례와 짝 |
| instance_id 형식 | `"{ip}:{app}:{port}"` | eureka.py:105 | Spring 관례 인스턴스 ID | X — 관례 |
| `TRACKS` | `("A", "B")` | stash.py:95 | feature 트랙 enum(A=specialist45d, B=vjepa) | X — 스키마/알고리즘 내재 |
| 스키마 컬럼맵 9종 | TUBELET/FEATURE/DETECTION/LANDMARK/SCENE/PARSE/HEADPOSE/GATE_TRACE/EMOTION_FRAME`_COLUMNS` | stash.py:34-91, 271-275, 353-382, 610-613 | 산출물 parquet 스키마 계약(쓰기 경계 validate+cast) | X — 계약(변경=버전 절차) |
| 산출물 파일명 레이아웃 | `"tubelets.parquet"`·`"likeness.json"` 등 ~20종 | stash.py:100-145, 385-617 | 클립 디렉토리 레이아웃 관례(resumability probe와 짝) | X — 계약/관례(Storage 포트 단일 교체점) |
| low-admit 경고 임계 | 0.30 | pipeline.py:169 | portrait 게이트 admit 비율이 이 미만이면 watch-log ⚠ 표시 | **O** — 시설·기구별 기대 통과율이 다를 수 있는 정책 임계값(단, 관측 경고 전용이라 영향은 로그 한정) |
| `UPSTREAM_OF_RUNNER` | `("detect", "landmarks")` | pipeline.py:102 | 러너 밖(warm-daemon/step0)에서 도는 스테이지의 의도적 제외 선언 | X — 아키텍처 내재 |
| `RUNNERS` probe 경로 14종 | `"attribution.json"` 등 | pipeline.py:110-124 | 스테이지별 resumability 존재-프로브 파일 | X — stash 레이아웃 계약과 짝 |


## 게이트·신호 도메인

| 상수(이름 또는 인라인 값) | 값 | 위치(파일:라인) | 의미 한 줄 | preset 후보 여부(O/X/판단불가) + 근거 |
|---|---|---|---|---|
| `DEFAULT_MODEL_ROOT` | `~/.insightface` | extraction/detect.py:45 | buffalo_l 모델 팩 경로 | O — 배포 호스트별 달라지는 환경 경로 (정책 임계는 아니지만 preset/설정 자리) |
| `min_score` (warm_init 기본값) | 0.5 | extraction/detect.py:57 | 얼굴 검출 confidence 하한 | O — 카메라 화질·설치 각도에 따라 재조정될 검출 민감도 |
| fps fallback | 30.0 | extraction/detect.py:219 | 프로파일에 fps 없을 때 출력 fps 가정 | 판단불가 — 시설 카메라 사양 결부지만 디코드 fallback 관례이기도 |
| HUD 텍스트 상수 | x=12, y=26, color=(235,235,235), font_scale=0.55 | extraction/detect.py:234-235 | 트레이스 영상 프레임번호 오버레이 코스메틱 | X — 관측용 시각화 상수, 운영환경 무관 |
| `MODEL` | "patrickjohncyh/fashion-clip" | extraction/fashion.py:25 | zero-shot 패션 분류 백엔드 선택 | X — 모델 계약(교체=버전 이벤트), 시설 preset 아님 |
| `_MEAN`/`_STD` | CLIP 정규화 3벡터 | extraction/fashion.py:26-27 | CLIP 입력 정규화 프로토콜 | X — 모델 학습 시 고정된 프로토콜 상수 |
| `N_SAMPLE` | 12 | extraction/fashion.py:28 | subject당 패션 판정 샘플 프레임 수 | O — 정확도/비용 트레이드오프, 클립 길이·운영 스루풋 따라 조정 |
| `_PROMPTS` (라벨·프롬프트 세트) | eyewear 3종·headwear 5종·covering 3종 문자열 | extraction/fashion.py:31-49 | 액세서리 타입 어휘(zero-shot 클래스 정의) | O — 시설·계절·고객층(헬멧, 고글 등)에 따라 어휘가 달라지는 도메인 정책 |
| `_SEG_MODEL` | "jonathandinu/face-parsing" | extraction/fashion.py:57 | 색-identity용 SegFormer 백엔드 | X — 모델 계약 (parse.py와 라벨맵 홈 공유) |
| 라벨 인덱스 (`_EYE_G`=3, `_HAT`=14, `_EAR_R`=15, `_NECK_L`=16, `_CLOTH`=18, `_FACE_SEED`, `_HAIR`=13, `_NECK`=17) | CelebAMask-HQ 인덱스 | extraction/fashion.py:58-67 | 세그멘테이션 라벨맵 계약 | X — 모델 출력 좌표계약, 절대 preset 아님 |
| `_GROW_PX` | 7 | extraction/fashion.py:68 | 소유권 영역-성장 인접 판정 팽창 반경(px) | 판단불가 — 크롭 캔버스 해상도(560×448)에 결합된 값; 시설 preset보단 크롭 계약 종속 |
| `_CI_K` | 5 | extraction/fashion.py:74 | 의상 팔레트 K-means 군집 수 | 판단불가 — "원본 상수 그대로" 주석; 팔레트 세분도 정책이나 legacy 계약 성격 |
| `_CI_HL_AREA` | 0.05 | extraction/fashion.py:75 | highlight 색 자격 면적비 하한 | O — 팔레트 판독 정책 임계, 의상 다양성(시즌/시설) 따라 조정 여지 |
| `_CI_MIN_PX` | 200 | extraction/fashion.py:76 | 팔레트 판정 최소 픽셀(미만=정직한 결측) | O — 관측 충분성 정책, 크롭 해상도·카메라 거리 따라 재조정 |
| `_CI_PX_CAP` | 2000 | extraction/fashion.py:77 | 프레임당 풀링 픽셀 상한(균형) | O — 성능/균형 정책 노브 |
| 얼굴 씨앗 중심 가정 | cy=h×0.4, cx=w×0.5 | extraction/fashion.py:113 | 소유자 얼굴≈크롭 중앙 상단 가정 | X — crops.py portrait_box 기하 계약에 결합(크롭 규격이 바뀌면 함께, 시설 무관) |
| 얼굴 성분 자격 하한 | comp≥50px AND 이목구비≥30px | extraction/fashion.py:118 | 손/몸통 skin 덩어리를 얼굴에서 배제 | 판단불가 — 해상도 결합 매직값; 크롭 계약 종속이나 측정 근거 미기록 |
| K-means 표본 상한 / n_init / seed | 5000 / 3 / 0 | extraction/fashion.py:196-199 | 군집화 표본·재시작·재현성 | X — 통계 수렴/재현성 상수, 결과 정책 아님 |
| 모델 입력 크기 | seg 512², CLIP 224² | extraction/fashion.py:173,223 | 모델 규정 입력 해상도 | X — 모델 프로토콜 고정값 |
| CelebAMask-HQ 클래스 상수 | SKIN=1 … CLOTH=18, `FACE_CLASSES` | extraction/parse.py:42-44 | SegFormer 라벨맵 계약 | X — 모델 출력 계약 |
| `BATCH` | 4 | extraction/parse.py:45 | SegFormer 배치 크기("8 GB GPU용으로 작게") | O — 운영 GPU 사양에 따라 달라지는 하드웨어 노브 |
| `_SKIN_ANCHORS` | 랜드마크 인덱스 20개 | extraction/parse.py:50-51 | mid-skin 앵커(이마·볼·턱·콧등) 기하 정의 | X — MediaPipe-478 랜드마크 좌표계약 + 검증된 측정 기하 |
| `_SIG_FRAC` | 0.16 | extraction/parse.py:52 | point-Gaussian σ = 안간거리 비율(스케일 불변) | X — 검증으로 고정된 측정 기하 캘리브레이션, 시설 무관(스케일 불변 설계) |
| `_L_OUTER`/`_R_OUTER` | 33, 263 | extraction/parse.py:53 | 눈 바깥꼬리 랜드마크(안간거리 기준점) | X — 랜드마크 인덱스 계약 |
| 가중치 유효 마스크·최소 영역 | wgt>1e-3, m.sum()<50→None | extraction/parse.py:102-103 | 판정 불능(영역 과소) 컷 | 판단불가 — 해상도 결합 최소 픽셀; 크롭 캔버스 종속 |
| `skin_clip_hi`/`skin_clip_lo` 경계 | ≥250 / ≤6 | extraction/parse.py:120-121 | 8-bit 포화/암전 클리핑 픽셀 정의 | 판단불가 — 8-bit 프로토콜 근거지만 250/6 마진 자체는 캘리브레이션 성격 |
| 히스토그램 규격 | bins=256, range (0,256) | extraction/parse.py:109 | 노출 엔트로피(ISO29794-5 계열) 히스토그램 | X — 8-bit 표준 공식 고정값 |
| heartbeat 주기 | ci % 50 < BATCH | extraction/parse.py:215 | 진행 로그 케이던스 | X — 관측 코스메틱 |
| `_MEAN`/`_STD` (ImageNet) | 0.485… / 0.229… | extraction/parse.py:228-229, fashion.py:72-73, headpose.py:41-42 | ImageNet 정규화 프로토콜 | X — 모델 학습 고정 프로토콜 |
| `DEFAULT_ONNX` | `~/.insightface/models/6drepnet/sixdrepnet.onnx` | extraction/headpose.py:37 | 6DRepNet 가중치 경로 | O — 배포 환경 경로 (설정 자리) |
| `BATCH` | 16 | extraction/headpose.py:39 | 6DRepNet 추론 배치 | O — GPU 사양 노브 |
| 부호 어댑터 | (-yaw, -pit, -rol) 전축 반전 | extraction/headpose.py:88 | 6DRepNet→MediaPipe euler 좌표 미러 계약 | X — 측정 검증된 좌표계약(6/6 클립), 변경=계약 버전 이벤트 |
| stage 기본 fps | 6 | fashion.py:243 · parse.py:132 · headpose.py:53 · crops.py:61 | 크롭 트랙/분석 프레임레이트(주: fashion/parse/headpose에선 인자 미사용, 실효는 crops) | O — 분석 밀도 vs 비용, 기구 속도·클립 길이 따라 조정 |
| `MIN_PERSISTENCE` | 0.10 | subjects/attribute.py:42 | 라이더 후보 자격: 검출 프레임의 ≥10% 등장 | O — 유령/구경꾼 컷, 카메라 화각·탑승 시간 구조에 결부 |
| `DEFAULT_STRIDE` | 5 | subjects/attribute.py:43 | depth 표본화: 공출현 프레임 N개마다 1회 | O — 비용/증거 밀도 정책, fps 결부 |
| `MARGIN_VALID` | 0.7 | subjects/attribute.py:44 | depth 투표 마진 하한(미만=불신) | O — 좌석 기하(기구별 앞/뒤 depth 차) 따라 달라질 판정 임계 |
| `FLIP_RUN` | 3 | subjects/attribute.py:45 | 연속 소수표 N개=flip 세그먼트(스왑 신호) | O — 노이즈 강건성 카운트, stride·fps에 결부 |
| depth 방향 규약 | 큰 값=가까움 | subjects/attribute.py:167 | Depth-Anything 출력 부호 규약 | X — 모델 출력 계약 |
| `PASPECT`/`FACEH`/`EYE` | 0.8 / 0.62 / 0.42 | subjects/crops.py:32 | portrait box 기하(4:5, 얼굴=높이 62%, 눈높이 42%) | 판단불가 — 제품 프레이밍 정책(미학)이지만 parse.py·인스펙터가 동일 기하에 결합된 크로스-모듈 계약(변경=계약 버전) |
| `CANVAS_H` (W=448 파생) | 560 | subjects/crops.py:33-34 | 크롭 트랙 저장 캔버스 해상도 | 판단불가 — 저장 품질/용량 정책이나 하류 픽셀 임계들(_GROW_PX 등)이 결합 |
| `MARGIN` | 1.4 | subjects/crops.py:35 | portrait box 재프레이밍 여유 배율 | O — 하류 재프레이밍 헤드룸 정책 |
| subject 최소 프레임 | ≥20 | subjects/crops.py:80 | 크롭 트랙 생성 자격 하한 | O — fps=6 기준 ~3.3s; fps·기구 체류시간에 결부된 운영 컷 |
| `STITCH_TAU` | 0.5 | subjects/stitch.py:28 | tier-1 재-ID 병합 cosine 하한(legacy tau_merge) | O — 코퍼스 측정 임계; 카메라·조명 환경 바뀌면 임베딩 분포와 함께 재측정 대상 |
| `FRAG_TAU` | 0.40 | subjects/stitch.py:35 | tier-2 조각 병합 절대 floor(음성 대조 max 0.32 앵커) | O — 이 코퍼스에서 측정된 앵커, 환경 이동 시 재측정 |
| `FRAG_MARGIN` | 0.15 | subjects/stitch.py:36 | tier-2 상대귀속 마진(차선 대비) | O — 코퍼스 측정치(mask_2 ≤0.031 vs s13 0.284) |
| `track_purity` tau / min_run | 0.35 / 3 | subjects/stitch.py:158 | 트랙 내 정체성 스왑 의심 run 판정(진단 전용) | O — cosine 임계·run 길이 모두 코퍼스 튜닝 성격 |
| `TAU_REF` | 0.30 | subjects/query.py:28 | reference_face 매칭 하한(동일인 0.48–0.80 vs 타인 max 0.166 측정) | O — 코퍼스 측정 임계, cross-day 일반화 미측정 명시 |
| `MIN_EMB` | 10 | subjects/query.py:29 | centroid 신뢰에 필요한 최소 임베딩 수 | O — 통계 충분성 정책, fps·클립 길이 결부 |
| runner-up 경고 마진 | 0.15 | subjects/query.py:111 | 저마진=미봉합 조각 의심 note(인라인, FRAG_MARGIN과 값 동일하나 독립 선언) | O — 측정 기반 정책값; FRAG_MARGIN과의 이중 선언 자체가 preset 통합 근거 |
| `det_size` | (640, 640) | subjects/query.py:56 | insightface 검출 입력 크기 | X — 모델 표준 입력 프로토콜 |
| `SMOOTH_S` | 2.0 | subjects/tubelets.py:37 | 모션 신호 평활 창(초) | O — 기구 가감속 시간 스케일에 결부된 운영 파라미터 |
| `SUSTAIN_S` | 1.0 | subjects/tubelets.py:38 | ride 판정 유지 시간(초) | O — 기구 출발 특성(덜컹임 등)에 따라 조정 |
| `FLAT_RATIO` | 0.6 | subjects/tubelets.py:39 | 저/고 모션 군집 비 ≥0.6 → boarding 없음 판정 | O — 카메라 마운트 진동·기구 특성에 따른 분리 가능성 임계 |
| 모션 프록시 해상도 | 160px 폭 | subjects/tubelets.py:58-60 | 프레임차 계산용 다운스케일 폭 | 판단불가 — 성능 상수이나 임계가 자기보정(2-means)이라 결과 둔감; 초저해상 카메라에선 재고 |
| 2-means 반복 상한 | 20 | subjects/tubelets.py:79 | 클러스터 수렴 반복 한도 | X — 수렴 알고리즘 내재 상수 |
| timestamp fallback fps | 30 | subjects/tubelets.py:147 | ts 미보유 프레임의 ms 환산 가정 | 판단불가 — 카메라 사양 결부 fallback (detect.py:219와 동류) |
| `VIDEO_SUFFIXES` | {.mp4 .mov .mkv .avi .m4v} | ingest.py:34 | 인제스트 허용 컨테이너 확장자 | O — 시설 카메라/납품 포맷에 따라 달라지는 수용 정책 |
| `_PROGRESS_EVERY` | 100 | ingest.py:35 | 진행 로그 프레임 주기 | X — 관측 케이던스 코스메틱 |
| HUD 상수 | color=(0,255,0), font_scale=0.7, thickness=2, x=12, y=30+28i | ingest.py:57-60 | L0 트레이스 오버레이 코스메틱 | X — 시각화 전용 |
| fps fallback | 30.0 | ingest.py:107 | 트레이스 기록 fps 가정 | 판단불가 — 카메라 결부 fallback |
| fourcc | "mp4v" | ingest.py:110 | 트레이스 비디오 코덱 | X — 트레이스 전용 인코딩 선택(산출물 계약 아님) |


## 측정 스테이지(extraction·subjects·ingest)

| 상수(이름 또는 인라인 값) | 값 | 위치(파일:라인) | 의미 한 줄 | preset 후보 여부(O/X/판단불가) + 근거 |
|---|---|---|---|---|
| EYE_LUM_MIN | 0.7 | products/portrait.py:58 | 눈 영역 상대휘도가 미만이면 선글라스 판정 | O — 주석 명시 "Preset policy, calibrated on cap_1"(카메라·조명 환경 의존) |
| MOUTH_VIS_MIN | 0.01 | products/portrait.py:58 | 입 영역 가시비가 미만이면 마스크 판정 | O — 같은 "Preset policy" 주석, parse 모델·촬영 환경 의존 |
| MIN_ADMIT | 5 | products/portrait.py:61 | admit 프레임 미달 시 portrait 미생성(노이즈 누출 방지) | O — 제품 정책 하한; fps·체류시간이 다른 기구면 조정 여지 |
| ID_MIN_CENTROID | 10 | products/portrait.py:62 | ArcFace 센트로이드 신뢰에 필요한 최소 admit 수(미달=rescue/rival 없음) | 판단불가 — 통계 신뢰 하한이지만 fps·클립 길이에 연동돼 운영환경 영향 있음 |
| fps 기본값 | 6 | products/portrait.py:91 · select.py:136,370 | 분석 표본화율(초/프레임 환산의 기준 단위) | O — 파이프라인 운영 설정; 모든 초 단위 창·간격이 이 값에 곱해짐 |
| conf_fac 계수 | 0.7+0.5·e (clip 0–1) | products/portrait.py:312 | em_conf 모호성 소프트 감점(0→0.7 바닥, 0.6에서 포화) | X — HSEmotion softmax 의미에 묶인 tiebreak 내재 계수, 시설 무관 |
| stab_fac 계수 | 1.0−0.3·v, 바닥 0.5 | products/portrait.py:314 | 감정 전이 속도(anti-transition) 감점 | X — 같은 tiebreak 내재 계수 |
| front 정규화 분모 | 3·POSE_MAX_DEG | products/portrait.py:328 | 3축 각도합의 정면성 정규화 상한 | X — 3=축 개수(알고리즘 내재); 실질 임계는 POSE_MAX_DEG 쪽 |
| sep | 2·fps (=2초) | products/portrait.py:352 | rep/대안 후보 간 최소 시간 간격(중복 제거) | O — dedup 제품 정책; 기구 움직임 속도에 따라 조정 여지 |
| 후보 상한 | 5 | products/portrait.py:357 | rep+대안 최대 5장 | O — 산출물 개수 정책 |
| (임포트) BLINK_MAX | 0.45 | portrait.py:34,331 ← gates.py:42 | 눈뜸 tiebreak 정규화 상한(게이트와 단일 원천) | 판단불가 — blendshape 의미 내재이나 코퍼스 보정값 |
| (임포트) POSE_MAX_DEG / FRONTAL_DEG / SIDE_DEG | 20 / 15 / 50 (deg) | portrait.py:35,328,371–374 ← pose.py:24–29 | 정면 게이트 밴드·뷰 bin 경계(frontal/quarter/side) | O — 카메라 장착각·기구 배치에 따라 달라질 밴드(단일 홈=pose.py) |
| (임포트) QUERY_DIST_MAX | 0.38 | portrait.py:330 ← gates.py:79 | warm 쿼리 근접(③) 정규화 상한 — ② 게이트와 동일 척도 | O — 정의부 주석 "9-clip corpus 보정" = 코퍼스·저작 쿼리 의존 |
| FRONTAL_SIGMA | 20.0 | products/select.py:59 | likeness 정면 게이트 가우시안 σ | O — CAMERA_FRONTAL_DEG(카메라 경험값)와 짝인 카메라 의존 폭 |
| WHICH_YAW_SIGMA | 30.0 | products/select.py:60 | highlight WHICH의 head-turn 허용 σ(likeness보다 관대) | O — 카메라·제품 정책 폭 |
| BURN_IN_S | 3.0 | products/select.py:61,263 | ride 시작 후 highlight 채점 제외 구간(초) | O — 기구/코스 프로파일 의존(탑승 초기 안정화 시간) |
| TOP_K | 3 | products/select.py:62,370 | likeness 후보 개수 | O — 산출물 개수 정책 |
| RARITY_WIN_S | 2.0 | products/select.py:65,204 | 드묾(state-window) 창 크기(초) | 판단불가 — E010에서 측정 고정이나 기구 페이스가 다르면 재보정 여지 |
| RARITY_FIELDS | 31개 dim 튜플 | products/select.py:68–76 | 드묾 state 벡터 구성 차원(감정·포즈·프레이밍·조명) | X — 레지스트리 계약에 묶인 알고리즘 설계(시설 아님) |
| MAD→σ 계수 | 1.4826 | products/select.py:94 | robust-z의 MAD 일치 상수 | X — 통계 표준 상수 |
| 최소 윈도 수 | n<20→NaN | products/select.py:113 | 드묾 계산 성립 최소 표본 가드 | X — 통계 최소표본 가드(알고리즘 내재) |
| kNN 이웃 수 | max(5, n//10) | products/select.py:118 | 드묾 = 최근접 k개 윈도 평균거리의 k | X — rarity 정의 내재(윈도 수 비례 자기적응) |
| em_conf 결측 채움 | 0.5 | products/select.py:167 | em_conf NaN 시 중립값 | X — 중립 기본값(알고리즘 내재) |
| 조명 섹터 수 | 9 | products/select.py:73,75,168 | 3×3 조명 섹터 dim 수 | X — 피처 레지스트리 계약 고정값 |
| AU 목록 | 12개 AU dim | products/select.py:176–180 | au_energy(각성) 산출에 드는 AU 집합 | X — 알고리즘 설계(DISFA/LibreFace 계약) |
| yaw 결측 front 대체 | 0.25 | products/select.py:217 | 메시 결측(하드 턴/가림) 시 가시성 대체값 | 판단불가 — E005 라벨 측정으로 고정, 카메라 바뀌면 재보정 여지 |
| visibility 블렌드 | 0.3+0.7·front | products/select.py:218 | 검출 신뢰×포즈 가시성의 바닥/기울기 | 판단불가 — eval 튜닝 가중(시설보다 동결 라벨 의존) |
| valence→[0,1] 매핑 | 0.5+0.5·valence | products/select.py:221 | signed valence를 WHICH 곱셈 항으로 매핑 | X — 자명에 가까운 범위 매핑 |
| em_conf 바닥 블렌드 | 0.4+0.6·em_conf | products/select.py:221,282,353 | 굴욕사진(모호 softmax) 소프트 감점의 바닥 0.4 | 판단불가 — eval 튜닝 가중; 세 제품 공통이라 preset보다 코드 홈이 자연스러움 |
| val_when 스케일 | 3.0 | products/select.py:257 | 양성 valence 트리거를 impact z⁺~3과 경쟁하게 스케일 | 판단불가 — 채널 간 균형 계수(동결 평결로 고정) |
| ride 전용 조건 | phase=="ride" | products/select.py:243,263–264 | highlight 채점을 ride 구간으로 한정 | O — phase 조건은 도메인 정책("도메인 지식은 preset에" 원칙) |
| yaw 결측 likeness 게이트 대체 | 0.05 | products/select.py:268 | 메시 없는 프레임의 정면 게이트 값(강 벌점) | 판단불가 — eval 튜닝(0.25와 제품별 비대칭도 튜닝 결과) |
| 노출 목표·벌점 가중 | 0.45 / ×2.0 / pen×3.0 | products/select.py:279 | 이상 노출 0.45 편차 벌점 + 클리핑 벌점 가중 | 판단불가 — 목표 0.45는 조명 환경 의존(preset 여지 O 쪽), 가중 2.0/3.0은 eval 튜닝 |
| calm AU 가중 | 1.0−0.5·au_energy | products/select.py:275 | AU 에너지 절반 가중으로 calm 감점 | 판단불가 — eval 튜닝 가중 |
| likeness 합성 바닥 | 0.3+0.7·calm · 0.2+0.8·q01 | products/select.py:281 | 항 소거 방지 바닥/기울기 | X — 곱셈 합성 안정화 내재 계수 |
| boarding 보너스 | ride=1.0 / 비ride=1.15 | products/select.py:282 | 비탑승(boarding) 프레임 likeness 가산(무풍 선호) | O — phase 조건 도메인 정책; 기구별 boarding 특성 상이 |
| eyes 항 | 1.0−0.6·blink, 결측 0.75 | products/select.py:330 | 눈뜸 가중(blink 벌점 0.6)·메시 없으면 중립 0.75 | 판단불가 — eval 튜닝 가중 |
| pleasant 블렌드 | smile:valence = 0.5:0.5, 0.5+0.5 매핑 | products/select.py:335–337 | 미소 항 = smile bs와 양성 valence 50:50 | 판단불가 — E009a ablation으로 고정(동결 라벨 의존) |
| rep 스케일 | 2.0·median(d_center) | products/select.py:339–340 | 대표성 가우시안 스케일(자기 정규화) | X — median 기반 자기적응, 시설 무관 |
| lr 방향광 가산 | +0.2 | products/select.py:345 | 측면 방향광(입체감) 완만 가산 | 판단불가 — E009a 측정 고정, 실내외 조명 환경에 따라 재보정 여지 |
| 역광 벌점 | 0.25·clip(\|tb\|−0.45,0,0.5)/0.5 | products/select.py:346 | tb 0.45 초과 역광에 최대 25% 벌점 | 판단불가 — 임계 0.45·폭 0.5·가중 0.25가 조명 환경 의존 여지(야외/실내) |
| SH ambient 가산 | +0.2 | products/select.py:352 | 얼굴 수광량(face_sh_0) 가산 | 판단불가 — E009b 측정 고정 |
| portrait 품질 바닥 | 0.2+0.8·q01 | products/select.py:353 | 품질 항 소거 방지 바닥 | X — 합성 안정화 내재 계수 |
| likeness 후보 분리 | 2·fps (=2초) | products/select.py:390 | 후보 간 최소 간격(E001 인접 중복 방지) | O — dedup 정책(portrait sep와 동일 성격) |
| policy 태그 | 2.0 | products/select.py:397 | CandidateLog의 채점 정책 버전 표식 | X — 프로토콜 표식(임계값 아님) |
| feature_track 기본값 | "A" | products/select.py:370 | 소비할 피처 트랙 선택 기본값 | X — 스테이지 프로토콜 기본값 |
| 랜드마크 좌표 형상 | 478×3 / 4×4 | products/select.py:312–316 | MediaPipe 정준 좌표 계약(포인트 수·변환 행렬) | X — 좌표계약(canonical frame contract) 고정값 |
| (임포트) CAMERA_FRONTAL_DEG | 12.0 | select.py:50,216,268 ← pose.py:34 | 이 카메라의 경험적 정면 yaw(off-axis 장착) | O — 정의부 주석이 카메라 장착 의존을 명시(E002) |


## 서비스·인프라(참고 — 대부분 프로토콜 상수)

| 상수(이름 또는 인라인 값) | 값 | 위치(파일:라인) | 의미 한 줄 | preset 후보 여부(O/X/판단불가) + 근거 |
|---|---|---|---|---|
| BLINK_MAX | 0.45 | gates.py:42 | eyes_ok 게이트: 눈감음 blendshape 상한(이상이면 눈감김) | O — portrait 질의 정책의 일부(blink는 질의 차원), 질의가 preset-authorable로 명시됨 |
| JAW_MAX | 0.5 | gates.py:42 | frontal_pose/quarter_ok: 입벌림 상한 | O — 동일하게 portrait 질의 정책; 기구 성격(환호가 정상인 어트랙션)에 따라 조정 여지 |
| BLUR_FLOOR_FRAC | 0.5 | gates.py:43 | T1 선명도 floor = 이 값 × 피사체 blur 중앙값 | O — "덜컹거리는 어트랙션은 약한 블러가 정상"이라는 기구-의존 근거가 주석에 명시; 비율 자체가 정책 |
| BLUR_MIN_FRAMES | 10 | gates.py:44 | 이보다 짧은 트랙은 중앙값 노이즈 → floor 미적용 | O — fps·트랙 길이 의존 카운트(6fps 기준 ~1.7s); 표본화 바뀌면 재조정 |
| IDDEV_MARGIN | 0.12 | gates.py:45 | id_ok: clean_ref 대비 허용 자기-편차 마진 | O — 코퍼스 캘리브레이션 값; ArcFace 편차 분포는 카메라 거리·해상도·가림 패턴에 이동 |
| TAU_SELF | 0.42 | gates.py:48 | id_valid 강한 자기-유사 cos floor(무라이벌 경로) | O — 9클립 코퍼스에서 조정된 임베딩 임계(247프레임 오킬 사례로 재조정된 이력); 촬영 조건 의존 |
| TAU_LO | 0.30 | gates.py:49 | side일 때만 허용되는 완화 self floor | O — TAU_SELF와 한 세트로 캘리브레이션됨 |
| TAU_CREF | 0.32 | gates.py:50 | anchor_trust: 이 값 초과 자기-편차 중앙값 = 쓰레기 centroid | O — subject-level 오검출 판별 임계, 코퍼스 캘리브레이션 |
| SNO_DELTA | 0.05 | gates.py:51 | self_not_other: 라이벌 centroid 대비 이겨야 하는 cos 마진 | O — 다중 피사체 밀도(동승 인원 패턴)에 따라 판별력 달라질 수 있는 마진 |
| TAU_GROSS | 0.15 | gates.py:52 | 라이벌+마진 성립 시 완화되는 절대 cos gross-garbage floor | O — TAU_SELF 완화 폭 자체가 정책(clean-ref-polarity 결정의 산물) |
| MIN_SIDE_RUN | 3 | gates.py:60 | T2: side 프레임은 시간-연속 run ≥ 3 안에서만 인정 | O — fps 의존 카운트(6fps에서 0.5s); 표본화 변경 시 재조정 |
| ENT_FLOOR | 4.5 | gates.py:61 | T1 노출 validity: 피부 휘도히스토그램 엔트로피(bits) floor | 판단불가 — ISO/IEC 29794-5 공식은 톤-불변 설계로 이식 의도이나, 4.5라는 floor는 이 코퍼스 검증 값(비트심도·압축 다른 카메라에서 재검 여지) |
| EXPR_CONF_MIN | 0.30 | gates.py:65 | T3: HSEmotion 지배 카테고리 확률 floor(muddled softmax=애매 초상) | O — "얼마나 또렷해야 초상인가"는 portrait 정책 노브; 단 값의 스케일은 HSEmotion 모델 의존 |
| PORTRAIT_QUERY | blink 0.0 · smile 0.35 · jaw 0.10 | gates.py:77 | 저작된 기본 질의점("warm PFP") — canonical blendshape 좌표 | O — 주석에 "Seasonal/user queries = preset-authorable later" 명시, 가장 명백한 C9 후보 |
| PORTRAIT_QUERY_W | blink 1.0 · smile 1.0 · jaw 0.5 | gates.py:78 | 질의 차원별 가중(눈·미소 주, 입 부) | O — 질의와 한 몸으로 preset 저작 대상 |
| QUERY_DIST_MAX | 0.38 | gates.py:79 | 질의 근접 admit 밴드(가중 L2) | O — "9클립 코퍼스에서 캘리브레이션" 명시; 코호트 바뀌면 기아(starvation) 조건 재검 필요 |
| REASONS/SERVED (어휘) | "admit"·"quarter"·"side"·reject:* 등 | gates.py:88-100 | 프레임 판정 폐어휘 — 엔진·인스펙터 공유 계약 | X — 프로토콜 고정값(단일 소스 계약); 시설과 무관 |
| REASON_COLORS | #5ac85a 등 9색 | gates.py:94-99 | 판정별 인스펙터 색 — 어휘와 함께 이동하는 생성 계약 | X — UI 계약 상수(어휘와 구조적으로 결합), 운영 환경 정책 아님 |
| NaN 대체 상수 | -1.0 / 0.0 / 1.0 / floor값 | gates.py:149,151,177,181,260,269 | 결측 판정 방향 인코딩: 임베딩 결측=모든 floor 실패, 그 외 결측=unjudgeable→통과 | X — "결측은 reject 사유가 될 수 없다"는 알고리즘 내재 원칙의 인코딩 |
| max_gap (기본값) | 2 | gates.py:516 | _sustained: frame_idx 연속성 허용 갭(검출 구멍 관용) | O — fps·검출률 의존; MIN_SIDE_RUN과 한 세트로 재조정 대상 |
| EM_POS/EM_NEG/EM_UNSIGNED | happy=+ / sad·angry·fear·disgust·contempt=− / neutral·surprise=무부호 | emotion.py:48-50 | valence_signed의 고정 부호 사영(surprise는 bivalent 검증으로 arousal행) | X — HSEmotion 의미론에 대한 데이터 검증된 알고리즘 내재 결정(시설 무관) |
| AU_FIELDS | au1~au26 12종 | emotion.py:54-58 | LibreFace DISFA AU 목록 — arousal 증거 채널 | X — 모델 출력 계약 |
| N_MIN | 30 | emotion.py:115 | cold-start: person-relative baseline에 필요한 최소 ride 프레임 수 | O — fps 의존(6fps 기준 ride 5초)이자 기구의 ride 길이에 결부된 운영 값 |
| RANGE_EPS | 0.05 | emotion.py:116 | valence 스프레드 퇴화 판정(이하면 baseline 불신) | 판단불가 — 통계 퇴화 가드(모델 공간 성질)이나 클립 길이·표본화에 2차 의존 |
| 백분위 [10,25,50,75,90] | p10~p90 | emotion.py:137 | person-relative baseline의 분위 정의(emotion.json 스키마) | X — baseline 스키마 계약; person-relative 설계라 환경 강건 |
| 75 (arousal 분위) | P75 | emotion.py:139 | "intense" 판정 기준 = 본인 arousal 상위 사분위 | 판단불가 — person-relative라 환경 강건하나 'intense' 정의 자체는 노브 |
| 0.2 / −0.2 (coverage) | ±0.2 | emotion.py:144-145 | 절대 valence "진짜 긍정/부정" 경계(person-relative 아님을 주석이 명시) | O — 절대 경계는 고객군·기구 성격 따라 조정 여지; 주석 스스로 "open point #1" |
| 0.6 / −0.6 (coverage) | ±0.6 | emotion.py:144-145 | strong_pos/strong_neg 절대 경계 | O — 위와 동일 근거 |
| most_common(2) | 2 | emotion.py:149-150 | style_high/low에 담는 지배 감정 상위 개수 | X — 출력 스키마 크기(카운트 한계이나 판정에 불참) |
| fps (기본값) | 6 | emotion.py:160 | 분석 표본화 프레임레이트 기본값 | 판단불가 — 운영/파이프라인 설정이며 C9 시설 preset이라기보다 런 설정; 바꾸면 N_MIN·MIN_SIDE_RUN 등 프레임-카운트 임계와 연동 필요 |
| POSE_MAX_DEG | 20.0 | pose.py:24 | frontal_pose 질의 콘: yaw·pitch·roll 모두 이하 | O — portrait 정면 질의 정책; 카메라 마운트·기구 좌석 배치에 따라 조정 여지 |
| FRONTAL_DEG | 15.0 | pose.py:25 | frontal↔three-quarter 뷰 빈 경계(라우팅) | O — 뷰 빈 정책(얼굴-뷰 의미론이라 보편성은 있으나 경계값은 조정 가능) |
| SIDE_DEG | 50.0 | pose.py:29 | three-quarter↔profile 경계(6D yaw ≥ → side) | O — 동일 뷰 정책 세트 |
| CORROB_DEG | 30.0 | pose.py:30 | 6D≥SIDE를 실프로필로 인정하는 MP 부호일치 확인 하한(후드/글레어 오탐 배제) | O — 오탐 원인(후드·글레어)이 복장·조명 환경 의존; 단 제약 "CORROB_DEG > POSE_MAX_DEG"(admit 정면 불가침)는 preset화 시 함께 강제해야 |
| CAMERA_FRONTAL_DEG | 12.0 | pose.py:34 | 이 카메라의 경험적 정면 오프셋(off-axis 마운트, E002) | O — 주석이 "this camera's EMPIRICAL frontal"로 시설 카메라 의존을 명시; 최우선 preset 후보 |
| CANONICAL_OBJ | ~/.cache/visualstack/mediapipe/canonical_face_model.obj | geometry.py:21 | 정준 프레임의 참조 형상(외부 dep, provenance 추적) | X — 좌표계약의 레퍼런스(경로는 배포 환경 값이지 시설 정책 아님; 교체는 frame_provenance로 가시화) |
| origin="centroid" / scale="rms-unit" | centroid / rms-unit | geometry.py:52,55 | 정준 프레임의 원점·스케일 컨벤션 | X — 좌표계약; 열린 컨벤션이지만 split-half eval로 결정할 알고리즘 내재 사안(preset 아님) |
| axis_flip | (1, −1, −1) | geometry.py:53 | 이미지→카메라 공간 축 뒤집기(π about x, det=+1 guard로 동결) | X — 좌표계약 고정값; reflection 버그 방지 assert가 임포트 시 강제 |
| basis_full / basis_mesh | 478 / 468 | geometry.py:56-57 | 분포/PCA용(홍채 포함) vs 템플릿 비교용(제외) 정점 수 | X — MediaPipe 토폴로지 계약(열린 통일 후보이나 eval 사안) |
| BS_BLINK / BS_SMILE / BS_JAW | (9,10) / (42,43) / 25 | signals.py:14-16 | ARKit-52 blendshape 인덱스 계약 | X — 모델 출력 좌표 계약(프로토콜 고정값) |
| GaussianBlur σ | 2 | signals.py:50 | crop_lighting harshness 측정 전 스무딩 시그마 | 판단불가 — 알고리즘 파라미터이나 크롭 해상도(카메라·거리)에 민감할 수 있음; 현재 서술적(descriptive) 신호라 1차 preset 아님 |

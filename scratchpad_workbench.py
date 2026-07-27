"""샘플링 워크벤치 v0.12 (2026-07-23) — 원장 ⑪⑫ 계기. 참조 구현(콘솔 파리티의 정본).

v0.20 **mesh-LS 이중 자 병기**(user "v0.20 시공" + Sapiens 프로브 판정 후속): 백색상자
램버트 피팅(정준 obj 법선 110점[SKIN_ANCHORS∪CHEEK_PTS 1-링−눈테두리, user 교정
"렘브란트 핵심=눈아래 코좌우"] × 5×5 밝기, 강건 트림 LS)을 전 프레임 방출 — ma/me
(정준 방위/고도)·mr(|m|/a)·ag(DPR 합의각). **존 게이트 소스는 DPR la/le 유지**(전환=
2층 판정, 프로브 근거: DPR el 고평가 예비). 검사 뷰: mesh-LS 수치 병기+⚠방향 불신
배지(합의각>45° 또는 mr<0.3=f429 서명) + 픽-한정 시각화 3종(법선 화살[이미지 공간]
·**정준(코-중심) 빛 지도**[user 지시: 포즈 소거 좌표에서 "빛이 얼굴에 앉은 모양" —
canonicalize 동일 수학, 색=관측 밝기+얼굴-기준 광방향 화살]·램버트 산점[cosθ vs
밝기+피팅 직선]). 수학 노트: 피팅=카메라 공간(픽셀 소재지), 방향 출력=정준 회전
— 직교 동치라 결과 좌표는 이미 코-중심.
v0.20.1 **자기-가림 수리**(모의 렌더 자가 적발): 측면에서 등진(N_z≤0.05) 점이 배경/
머리칼을 표본해 지도에 유효 데이터처럼 표시 — 피팅 입력 선제 제외+시각화 v 플래그
(정준 지도·산점에서 제외, 트림점=회색).
v0.20.2 **역광 붕괴 수리**(pv mls 2/7 진단): 1차 피팅이 "빛=뒤"면 clamp-트림이 전
점을 죽여 None(f305 110→3). lit 트림=lit 모집단 충분(≥max(12, 30%))할 때만 + 붕괴
시 마지막 유효 피팅 반환 — 역광 프레임도 (낮은 신뢰의) 방향을 정직 방출.
v0.27.2 **용어 정정: 조명비(lighting ratio)**(user "차오름 근거가 어디냐 — 검색 안 됨": 차오름=내 조어였음을 자백, 기성 교과서 용어=조명비 key:fill로 전면 교체 · 검사 뷰=N:1 표기 · 우리 hd=반사광 근사 1/(1−hd):1).
v0.27.1 **표기=그림자 차오름 통일**(user 채택 "차오름 비율이 납득"): 다이얼·검사 뷰·사전을 차오름 문법으로(차오름 100%=소프트·0%=하드), 내부 값 hd=1−차오름 유지.
v0.27 **확산의 자=키:필(hd) 교체**(user 반증 "df −0.95에 방향 명확한 프레임 다수" — R²의 구조 결함 확정: 깊은 그림자=clamp 비선형이라 하드 극단도 R²≈0, 전체-가시점 계산이 트림-피팅과 불일치): hd=1−(그림자면/밝은면 중앙 밝기, cosθ 3분위 분할)=사진사의 키:필 비율. 검증=r2≤0.05 오분류 55장 중 15장 하드 복권(f529~537=렘브란트 이웃)·앵커 f532 0.62/f408 0.58·시각 상하위 분리 명확. R²=통계/산점 표시로 존치(클립 AUC는 R² 우위 — 직무 분리: 다이얼=프레임 자 hd, 클립 성향=lf·구간 지도). 세그먼트 분류도 hd로 통일.
v0.26.1 **확산 다이얼=양극 복귀**(user 정합 확인 "방향성 존재/소멸 방향 조정이면 충분"): 창(df+dfw)→단일 양극 슬라이더(0=전체·+=R²≥df 하드만·−=R²≤1+df 소프트만) — 그룹핑 직무는 구간 지도가 승계, 통과영역 초록 칠은 유지.
v0.26 **조명 구간 지도**(user "비슷한 부류끼리 그룹핑 안 됨" — R² 스칼라 창의 지각 한계 실증[좁은 창 안 lt 16~100·az 전방위 혼재]): 부류=결합 상태(방향×세기×확산)이고 그 단위는 시간 구간 — 카메라-기준 광방위(머리 회전 무관, mls_ca)+세기+R² 시계열을 블록 병합으로 분할, 구간 분류(직사/확산·평광/역광/어두움) → 타임라인 상단 색 밴드+범례. test_4 스모크=21구간, 렘브란트 앵커(f379·408)가 한 직사 구간에 정확히 동거.
v0.25.3 **창 시각 피드백**(user "선택 영역 색상"): 히스토그램 bandf 지원 — df·dfw 조작 시 창 구간 빈이 초록으로 칠해지고 양끝 마커 표시(전체=마커 없음). 게이트는 창으로 정상 동작 실증(중심 0.35→r2 0.2~0.5만).
v0.25.2 **확산 창(window) 쿼리**(user "임계값이 아니라 구간 선택"): df=창 중심(−0.05=전체·0=소프트~1=하드)+dfw=반폭 — 축 위를 창이 미끄러지며 "그 정도로 하드한" 구간을 직접 쿼리.
v0.25.1 **확산 양극 슬라이더**(user "한쪽=소프트·반대쪽=하드로 조정"): 밴드 2다이얼 → df 하나(중앙 0=전체, −쪽=R²≤1+df 소프트만, +쪽=R²≥df 하드만).
v0.25 **확산의 자=R² 교체(의제② 종결)**: 후보 4종 클립-앵커 중재(흐림 test_3·test_0
vs 직사 test_4·251227*) — **현직 DPR ldr=AUC 0.248 역방향 실증**(은퇴, 표시 대조만)
· mesh mr 0.537 · fc(얼굴대비) 0.519 · **R²=0.768 유일 분리**(test_3=0.00 자백).
③확산 다이얼=R² raw(0~1, 분산비라 클립-교차 절대 문턱 성립 — pct 함정 회피).
존에서 확산 조건 전면 제거(방향 실재 게이트=ag가 대행; R² 하한은 mesh-취약 프레임
[f532 트림 붕괴]을 오폭). **"소프트" 존 정체 정정→"프론트(밝은 정면광)"**: intl
f1~50 R²=0.59=반직사 — 소프트박스 라벨은 역방향 자(ldr) 위의 오명이었음.
v0.24 **빛 채널 4축 재편**(user "다이얼 4가지면 되지 않나 — 세기·방향·확산·그림자"):
계기 감사의 4질문과 동형 좌표 채택 — ①세기(lt) ②방향(존 선택=1급, az/el 밴드·합의각
=고급 접기) ③확산(방향성 밴드) ④그림자(hh). 사진사는 각도가 아니라 셋업을 고른다.
v0.23.1 **약어 사전 상주**(user "az·el 등 약어 모르겠다"): 마스터 탭에 전 약어 사전 — 도구는 자기 설명을 해야 한다.
v0.23 **방향 소스 전환: mesh 본선**(판정 완결): az 중재=밝기-무게중심 각(법선·램버트
무관, 눈-판정의 정량판) — 전 코퍼스 2802프레임 중앙오차 mesh 29.9° vs DPR 51.5°,
8클립 중 7승(무승부=확산 test_0)·f408 관측 +62°에 mesh +55°/DPR +14°. el 중재=Sapiens
(기존). → 존/게이트의 방위·고도=ma/me로 재배선(la/le=DPR은 대조 표시 유지), **합의
게이트 ag_max 다이얼 신설**(존 프리셋 45°, 기본 180=off — "방향 쿼리는 두 자 합의
시에만"). ld(방향성)는 잠정 DPR 유지 — softness 자(R²) 확정 시 교체(의제 2).
v0.22.1 **정준 지도 이중 화살**(az 소스 판정 대조: 노랑=mesh·파랑=DPR — 밝은 무리 위치와 두 화살을 한 그림에서 눈-판정).
v0.22 **계기 은퇴**(user 확정 "은퇴 후보 확정·제거"): 이미지-공간 세대 전면 정리 —
lr/tb(32×32 좌우/상하 비대칭)·dp(=pct|lr|+|tb|)·pa(볼빛−턱그늘)+다이얼·32×32 광량맵
·마스크 볼/턱 마커·bb 필드. 근거=정준 이중 자(DPR la/le/ldr + mesh ma/me/mr)가 전부
상위 호환(원장 ⑪-e 전수 감사). 빛 채널=3세부(조도·생동/정준 방향+존/거칠기)로 재편.
기본 off 다이얼 제거라 셀프테스트 불변.
v0.21.5 **계측점 밀도 110→64**(user "밀도 줄이자"): 선별 씨앗 30(SKIN_ANCHORS∪
CHEEK_PTS) 전부 보존+링 확장분은 정준 obj 좌표 FPS로 34점 — 미지수 4개에 과잉이던
방정식 수 감축, 데이터 ~40%↓. 앵커 안정(f532 az 44/el 19, 110점 대비 수 도 이내)·
역광/측면 생존(keep 25~27). 여유 항목: 강직사 정면 keep 13(가드 12 근접 — 흔들리면
target 72로). 프로브 도구=워크벤치 토폴로지 단일홈으로 통합.
v0.21.4 **광량맵 file:// 수리**(user "32×32에 아무것도 안 뜸"): getImageData가 onload
첫 줄이라 file:// canvas 오염(SecurityError)에서 전체 무산 — 시각=순수 drawImage
컬러 32×32 선(先)도장(오염 무관) + 그레이·블러·lr/tb 재현=try/catch(HTTP 서빙에서만).
v0.21.2 **클립-고정 밝기 척도**(user 판독 "f570은 어두운데 지도는 강렬"): 프레임별
min-max 스트레치가 어두운 프레임의 최대점을 최대 노랑으로 렌더 — SH 구면 캐비어트의
재생산. 지도·산점 색/y축을 클립 p2~p98(mrange)에 고정 → 프레임 간 세기 비교 성립,
캡션에 척도 명시.
v0.21 **지도·산점 전-프레임화**(user "모든 프레임에 법선 시각화가 없네"): 픽-한정
관례가 1층 임의-프레임 검증 직무와 불일치 — **정준 레이아웃은 프레임 불변**(정준화의
존재 이유)이므로 클립당 1회(mlay=중앙값 배치)만 싣고, 프레임엔 정수 압축 3배열만
(mi=밝기 0..255 · md=cosθ×100 · mq=0비가시/1관측/2피팅사용)+mf=[a,|m|]. 지도·산점
=전 프레임, 법선 화살(썸네일 오버레이)만 픽 한정 유지. data.js +~5MB 예상.
v0.20.3 **정준 지도 전점 채색**(user 판독 "정면인데 반쪽만 표시"): 트림점 회색 표시가
지도의 2/3을 지움 — 트림은 피팅용이지 관측 무효가 아님. 지도=전 가시점 밝기색(트림
구분은 산점도에만 유지).
v0.19.3 **소프트 존 + 존 세기 floor**(user 교정 "좋은 빛=f1~50 탑승장 / f269 렘=밋밋"):
f1~50 실측=클립 최고 세기(raw 휘도 118~175·채도 77~94)·정면(az±25)·el 34~40인데
**ldr 0.33~0.63(ld pct 0.4~12)** → ld≥50이 전멸시킴 — 밝고 부드러운 빛(소프트박스/
오픈셰이드 문법)은 방향성이 낮다. f269=방향만 렘브란트(az41/el55/ld59), 세기 바닥
(lt57/raw68) — 존에 level floor 부재. 처방: ①전 존 프리셋에 lt_min 60 ②ld_max 다이얼
신설(소프트 상한) ③**존 "소프트(밝은 확산)"** = lt≥75 ∧ ld≤30 ∧ az±30 ∧ el10~55.
리허설: 소프트 존 35장 전원 f0~50 적중 · 렘A+floor는 international_1에서 0(정직).
교훈: **방향성은 '좋은 빛'의 한 문법이지 필요조건이 아니다** — 존 3문법(하드 측광/
하드 정면광/소프트 정면광).
v0.19.2 **raw 성분 병기**(user 판독 "international_1 버플 생존이 조명과 거리 멂" 해부):
①존은 정답(f51~65 초반 좋은 빛)을 잡았으나 sym(웃음 비대칭 0.63~0.81)·pupil(눈웃음
0.32~0.38) 기본 게이트가 전멸시켜 그늘 프레임만 노출 ②그늘(f479·647~657)이 존을 통과
한 건 방향이 실제 상방(하늘광)이기 때문 — 가를 것은 직사광 vs 그늘=절대 채도·휘도인데
전 계기가 풀-상대 pct라 포화(ch 91.6 vs 92.1). 처방=rows에 lmr(raw 휘도)/chr(raw 색량)
병기+검사 뷰 표기. 존 raw-floor 다이얼은 2층.
v0.19.1 **확산-클립 배지**(user 관찰 "test_4만 존 효과 큼 = 유달리 강한 태양"): 존 반응
지도 실측 — test_4(lf 1.0) 렘A 18·버플 31 / international_1 버플 20(존이 다를 뿐 유효)
/ test_3 전존 0(렘브란트 부재의 정직 보고) / test_0(lf 0.27) 렘A 4=포즈-편향 누수.
azR(방위 응집도)은 배지 부적격(test_4 0.25=정당 다양 vs test_0 0.74=가짜 응집) →
헤더에 lf<0.35 ⚠확산 배지 + 존 행 캐비어트. 존 경계·lf 문턱 봉인=2층.
v0.19 **정준(얼굴-좌표) 광방향**(user "빛 계속 고도화", 1층 DPR 합격 후속): DPR SH를
canonicalize와 동일 수학으로 얼굴 좌표에 회전 — L_cam=(sh3,sh2,−sh1)→Rᵀ·L(R=T[:3,:3]).
새 계기 la(방위 0=정면 +=피사체좌 ±180=후방)·le(고도 +=위)·ldr(|SH₁|/DC)·ld(pct).
앵커 검증: f477 az−103=user "좌후방" 일치·f658 az170 el77=역광·f379 태양쪽 회전=az10.
빛 채널에 "정준 방향" 세부(다이얼 5종, 기본 off)+사진 문법 존 프리셋(렘브란트±/버터
플라이/해제)+검사 뷰 얼굴-좌표 구면(●=광방향, 후방=빨간 링)+⚠확산 캐비어트(ldr<0.25
=방위 신뢰불가, test_0 판정 반영). pa는 보조 강등(원장 ⑪-e).
v0.18.2 **lr 화살 반전 수리**(1층 SH 검사 중 적발, user 앵커 "test_4 태양=우측"): lr=
(좌−우) 정의라 우측광=음수인데 화살이 +lr로 그려져 어두운 쪽을 가리킴(tb축은 정상).
픽셀 실측(화면 우−좌 +38~+90)·DPR sh3(+)·구면 렌더(우반 밝음) 전부 우측 일치 — 계기
정상, 바늘만 반전. 화살=빛 쪽으로 통일.
v0.18.1 **영역 재배치**(user f379 판독: 볼=측면 광대 쏠림·턱=귀밑 끝 쏠림): 볼=눈밑
삼각형 infraorbital 10점(118/119/100/101/47+미러) · 턱=해부학 "턱→코 ½ 기준 하부 ¼"
밴드 16점(입아래~턱, 실루엣 안쪽 링 — 가우시안 목 누수 방지). f379 오버레이 자가 검증.
v0.18 **패턴 축(볼빛−턱그늘)**(user 2026-07-23 "빛이 들어오는 부위별 차등 — 볼 삼각형
=밝게·턱 후방 경계=그늘"): pattern=(볼 8점 가중휘도 − 턱후방 6점 가중휘도)/얼굴평균
— 프레임-내 스킨-영역 대비+정규화로 albedo 대체 소거(사진 조명 문법: 렘브란트/루프
계열; dp[방향 존재량]의 영역-해상 진화형; SH-시그니처 매칭은 SH 검증 후 2안). 풀-내
pct, 빛 채널 4번째 세부(pa_min 기본 off=셀프테스트 불변). 마스크 오버레이에 영역
마커(볼=청록·턱=주황) — 영역 인덱스 자가 검증.
v0.17 **빛 계기 투명화**(user: "스킨마스크 범위와 32×32 맵을 보고 싶다"): 검사 뷰
빛 모드에 ①skin 마스크 재현 오버레이(전 행 — 앵커 20·타원 hull 36·눈꼬리 2 좌표
선적, hull 클립+가우시안 σ=0.16 IOD) ②32×32 광량 맵 재현(bbox 크롭→그레이→5탭
블러, 픽셀 확대)+**lr/tb 즉석 재계산 vs 저장값 대조**(재현-일치 검증) ③lt 성분 분해
(휘도 pct+색량 pct, v0.16.1). 재현=224px 썸네일 근사 — 큰 어긋남만 의미.
v0.16 타임라인 sticky+결과/풀 박스 분리 · v0.15 **데크 좌측 이동**(user): 하단 →
좌측 사이드바(384px, 탭→브리지→트리→가로 페이더 세로 스택). 본문·검사 패널 배치 불변.
v0.14 채널 탭 내 **트리 구조**: 세부 채널 타이틀(1열·가지선)+다이얼, 밴드=한 세부
채널에 2다이얼(yaw 하한/상한·ex 밴드).
v0.13 **채널 탭 데크 + 미터 브리지 + 접이식 검사 패널**(user: "가로 스트립=조잡, 탭
분리 + 검사 접이식"): 데크=탭당 채널 하나(다이얼 전폭 2열 그리드+대형 분포 미터,
세로 페이더) · 탭에 S/M 미니 버튼(뮤트 탭=흐림) · 탭 선택=검사 뷰 모드 동기화 ·
**미터 브리지**(탭 바 우측 — 선택 프레임의 채널별 상태점수 가로 막대, 전 채널 상시
판독 유지) · 검사 패널 ◀▶ 핸들로 접기(데크·본문이 전폭 확장). 데크 높이 248px.
v0.12 콘솔 데크(가로 스트립) — v0.13으로 대체. 로직·데이터 불변(HTML-only).

v0.11 **축 solo/mute — 믹싱 콘솔 문법**(mb-wbsolo, 검증 2층 구조의 1층 도구): 상태
그룹 헤더에 [S][M] — mute=그 채널의 하드 게이트 해제+소프트 가중 0(다이얼 값은 보존,
오버라이드만) · solo=나머지 일괄 mute(재클릭=해제) · 뮤트 중엔 "믹스(뮤트 해제) 픽"
참조 행 표시 = solo-선택 vs 종합-선택 diff(1층→2층 다리). 뮤트는 시뮬 전용(셀프테스트
=뮤트 없음 기본에서만; 파이썬 미러 불변). 전 가중 0(예: 포즈 solo)이면 픽=밴드 내
시간순 — 중립 폴백.

v0.10 **상태 검사 뷰 + 3열 골격**(user: "다이얼마다 서로 다른 분석 시각화 — 빛=SH가
얼굴에 그리는 조명, 포즈=오버레이로 추정 검증"): 좌=다이얼(상태 아코디언·조작 시
해당 상태 모드로 자동 전환) / 중=타임라인+픽+풀 / 우=**상태 검사 패널**(선택 프레임
큰 이미지 + 모드별 렌더). 검사 모드: 포즈=랜드마크 와이어+ypr(픽 프레임 한정 선적,
전 프레임은 콘솔 온디맨드 확장 예정) · 표정=blendshape 상위 막대(픽 한정)+pu/ex ·
빛=**SH 구면 렌더**(face_sh_0..8, DPR 9계수→JS 실시간)+lr/tb 방향 화살표 · 영상=
Laplacian 선명 히트맵(픽 한정 사전렌더) · 왜곡=cs/mv 시계열 궤적+선택 마커.
**클릭 의미 변경**: 클릭=프레임 선택(검사 패널 갱신) · GT=검사 패널의 ＋/−/지움
버튼(오클릭 방지) · Shift+클릭=포즈 그라운딩 유지.

v0.9 상태-쿼리: 1단=상태별 스크린/밴드(포즈=밴드가 곧 쿼리·표정 ex_min~ex_max 밴드)
· 2단=상태 점수 4종 종합(얼굴=(2무표정+눈동자)/3·빛=조도생동[×lf]·영상=(선명+micro)/2
·왜곡=(cs+입가시+norm)/3) — v7.2 브리지 종료, 가드=JS≡python 셀프테스트.
v0.8 빛 판별력 lf(+분산-감쇠 ATT 토글) · v0.7 상태 5그룹(퍼널·타임라인 5색) ·
v0.6 공평 우주(전 행 썸네일·유령 레인·축=0..vf) · v0.5 yaw 부호-밴드 ·
v0.4 다이얼 분포 지도 · v0.3 포즈 그라운딩·pitch · v0.2 타임라인 · v0.1 단일-클립 탭.
층: frame_table(stash 읽기-전용 파생) + 시뮬레이터 + 클릭 GT(fixtures/eval, workbench-gt/v0).
승격(track/lk-workbench): 정식 표면 = momentscan workbench — 이 스크립트가 값-동일 참조 구현.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import polars as pl

sys.path.insert(0, "apps/momentscan/src")
from mediapipe.tasks.python.vision.face_landmarker import (
    FaceLandmarksConnections as _FLC,
)

from momentscan.infra.store.stash import read_landmarks, read_features, read_tubelets
from momentscan.perception.readings.geometry import canonicalize
from momentscan.preset import resolve

from momentscan_features_specialist45d.registry import INDEX
from momentscan_features_specialist45d.specialists import BLENDSHAPE_ORDER

from scratchpad_likeness_sat import skin_sv

RACE = resolve("race981")
FRONTAL_DEG = RACE.camera.frontal_deg
CLIPS = ("test_3", "test_12", "dual_2", "test_4", "test_0", "international_1",
         "251227002408570", "251227002408802")   # v0.21.3 실운영 클립 2종(user 요청)
THUMB = 224     # 저장 원치수 — 픽 행은 원치수, 풀은 112 축소 표시+호버 확대
EDGES = [[c.start, c.end] for c in (*_FLC.FACE_LANDMARKS_CONTOURS, *_FLC.FACE_LANDMARKS_NOSE)]

# 검사 뷰(빛) — skin 마스크 재현용: parse._quality와 동일 상수
SKIN_ANCHORS = (9, 107, 336, 151, 67, 297, 50, 280, 205, 425, 116, 345, 123, 352,
                152, 175, 200, 6, 197, 195)
EYE_CORNERS = (33, 263)
# v0.18 패턴 축(user 2026-07-23: 볼빛−턱그늘) — 영역 정의(오버레이로 자가 검증)
CHEEK_PTS = (118, 119, 100, 101, 47, 347, 348, 329, 330, 277)   # 눈밑 삼각형(infraorbital, 양측)
EYE_RING = frozenset((33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246,
                      263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466))
# (v0.22 은퇴: JAW_PTS·pa 패턴 축 — 정준 빛 지도가 상위 호환. CHEEK_PTS는 SKIN110 씨앗으로 존속)


def _oval_order():
    """FACE_OVAL 연결쌍을 체인 순서로 — hull 폴리곤 경로용."""
    conns = {c.start: c.end for c in _FLC.FACE_LANDMARKS_FACE_OVAL}
    start = next(iter(conns))
    seq = [start]
    while len(seq) <= len(conns):
        nxt = conns.get(seq[-1])
        if nxt is None or nxt == start:
            break
        seq.append(nxt)
    return seq


OVAL_ORDER = _oval_order()

# 기본 설정 — JS DEF와 문자 그대로 동일해야 함 (셀프테스트 = JS≡python 가드)
DEFAULT_CFG = {"sym_max": 0.6, "dev_lo": -15.0, "dev_hi": 15.0, "pt_max": 99.0, "pu_min": 0.4,
               "cs_min": 0.0, "mv_min": 0.0, "lt_min": 0.0, "ex_min": 0.0, "ex_max": 1.0,
               "gap_min": 12, "hh_max": 100.0, "sp_min": 0.0,
               "df": 0.0, "la_lo": -180.0, "la_hi": 180.0, "le_lo": -90.0, "le_hi": 90.0,
               "ag_max": 180.0,
               "w_face": 0.45, "w_light": 0.20, "w_image": 0.15, "w_distort": 0.20}


def state_scores(r):
    """상태 점수 4종 — r=[무표정,눈동자,선명,micro,norm,cs,입가시,빛] rank01."""
    re_, rp_, rs_, rm_, rn_, rc_, rv_, rl_ = r
    return ((2 * re_ + rp_) / 3, rl_, (rs_ + rm_) / 2, (rc_ + rv_ + rn_) / 3)


def face_signals(P):
    def d2(a, b):
        return np.linalg.norm(P[:, a, :2] - P[:, b, :2], axis=1)
    r_iris = (d2(469, 471) + d2(470, 472)) / 2 + 1e-9
    l_iris = (d2(474, 476) + d2(475, 477)) / 2 + 1e-9
    pupil = (d2(159, 145) / r_iris + d2(386, 374) / l_iris) / 2
    dr = np.abs(P[:, 1, 0] - P[:, 234, 0]) + 1e-9
    dl = np.abs(P[:, 454, 0] - P[:, 1, 0]) + 1e-9
    return pupil, np.abs(np.log(dr / dl))


def pct_rank(x):
    out = np.full(len(x), np.nan)
    fin = np.isfinite(x)
    if fin.sum():
        v = x[fin]
        out[fin] = np.array([float(np.mean(v <= xi)) * 100 for xi in x[fin]])
    return out


def rank01(x, flip=False):
    r = np.argsort(np.argsort(np.nan_to_num(x, nan=(np.inf if flip else -np.inf))))
    r = r / max(len(x) - 1, 1)
    return 1 - r if flip else r


def _mesh_topology(target=64):
    """v0.20 mesh-LS 재료 — 정준 obj faces + 스킨 점. obj=geometry.CANONICAL_OBJ 단일홈.

    v0.21.5(user "밀도 줄이자"): 선별 씨앗(SKIN_ANCHORS∪CHEEK_PTS) 전부 보존 +
    1-링 확장분은 정준 obj 좌표 farthest-point 샘플링으로 target까지 — 미지수 4개에
    110 방정식은 과잉, 단 측면 가시성-필터·강건 트림 뒤에도 ≥12점이 남을 여유는 유지."""
    from momentscan.perception.readings.geometry import CANONICAL_OBJ
    faces, verts = [], []
    for ln in Path(CANONICAL_OBJ).read_text(encoding="utf-8").splitlines():
        if ln.startswith("f "):
            faces.append([int(p.split("/")[0]) - 1 for p in ln.split()[1:4]])
        elif ln.startswith("v "):
            verts.append([float(p) for p in ln.split()[1:4]])
    faces = np.array(faces, int)
    V = np.array(verts)
    adj = {}
    for tri in faces:
        for a in tri:
            adj.setdefault(int(a), set()).update(int(b) for b in tri if b != a)
    seeds = {i for i in (set(SKIN_ANCHORS) | set(CHEEK_PTS)) if i < 468}
    ring = set()
    for a in seeds:
        ring |= adj.get(a, set())
    ring = {i for i in ring if i < 468} - seeds - EYE_RING
    sel = sorted(seeds)
    cand = sorted(ring)
    while len(sel) < target and cand:
        d = np.array([min(np.linalg.norm(V[c] - V[s]) for s in sel) for c in cand])
        j = int(np.argmax(d))
        sel.append(cand.pop(j))
    return faces, np.array(sorted(sel), int)


MESH_FACES, SKIN110 = _mesh_topology()


def _vertex_normals(v):
    """v (468,3) flipped-camera 좌표 → 단위 법선, 카메라 쪽 배향."""
    nrm = np.zeros_like(v)
    t0, t1, t2 = v[MESH_FACES[:, 0]], v[MESH_FACES[:, 1]], v[MESH_FACES[:, 2]]
    fn = np.cross(t1 - t0, t2 - t0)
    for k in range(3):
        np.add.at(nrm, MESH_FACES[:, k], fn)
    nrm /= (np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9)
    if np.nanmean(nrm[:, 2]) < 0:
        nrm = -nrm
    return nrm


def _fit_light_gray(I, N):
    """I (P,) 밝기 × N (P,3) 법선 → (a, m(3,), keep) 강건 램버트 LS. None=실패.

    clamp-트림(음영면 제거)은 lit 모집단이 충분할 때만 — 역광이면 대부분이 unlit인
    게 정상이라 무조건 트림하면 자멸한다(f305: 110→3→붕괴, v0.20.2 수리)."""
    keep = np.isfinite(I)
    if keep.sum() < 12:
        return None
    A_full = np.concatenate([np.ones((len(I), 1)), N], axis=1)
    th = None
    for _ in range(3):
        if keep.sum() < 12:
            break
        th, *_ = np.linalg.lstsq(A_full[keep], I[keep], rcond=None)
        r = np.abs(A_full @ th - I)
        m = th[1:]
        lit = (N @ (m / (np.linalg.norm(m) + 1e-9))) > -0.05
        nxt = keep & (r <= np.percentile(r[keep], 75)) & np.isfinite(I)
        if lit.sum() >= max(12, 0.3 * keep.sum()):
            nxt = nxt & lit
        keep = nxt
    if th is None:
        return None
    return float(th[0]), th[1:], keep


def _mls_frame(frm, P_i, cbv, gray_full=None):
    """한 프레임 mesh-LS — (a, m, keep, N110, xy478, I110) 또는 None."""
    H0, W0 = frm.shape[:2]
    cw, ch = cbv[2] - cbv[0], cbv[3] - cbv[1]
    if cw <= 1 or ch <= 1:
        return None
    xy = np.stack([cbv[0] + P_i[:, 0] * cw, cbv[1] + P_i[:, 1] * ch], 1)
    if gray_full is None:
        gray_full = cv2.cvtColor(frm, cv2.COLOR_BGR2GRAY).astype(np.float32)
    I = np.full(len(SKIN110), np.nan)
    for k, j in enumerate(SKIN110):
        x, y = int(round(xy[j, 0])), int(round(xy[j, 1]))
        if 2 <= x < W0 - 2 and 2 <= y < H0 - 2:
            I[k] = gray_full[y - 2:y + 3, x - 2:x + 3].mean()
    v3 = np.stack([P_i[:468, 0] * cw, P_i[:468, 1] * ch, P_i[:468, 2] * cw], 1)
    v3 *= np.array([1.0, -1.0, -1.0])
    N = _vertex_normals(v3)[SKIN110]
    I[N[:, 2] <= 0.05] = np.nan   # 자기-가림(카메라 등짐) 점 = 배경/머리칼 표본 — 선제 제외
    fit = _fit_light_gray(I, N)
    if fit is None:
        return None
    a, m, keep = fit
    return a, m, keep, N, xy, I, v3


def frame_table(clip_id: str, out_root: Path):
    """클립 main rider의 전 신호 와이드 테이블 (+유령 우주·검사 뷰 컨텍스트)."""
    rec = json.load(open(out_root / clip_id / "likeness.json"))
    tid, rider = next((int(t), r) for t, r in rec["riders"].items() if r.get("role") == "main")
    lmr = read_landmarks(out_root, clip_id).filter(pl.col("track_id") == tid).sort("frame_idx")
    lm_all_cb = {int(f): tuple(float(v) for v in b)
                 for f, b in zip(lmr["frame_idx"].to_list(), lmr["crop_box"].to_list())}
    gt = pl.read_parquet(out_root / clip_id / "gate_trace.parquet").filter(pl.col("track_id") == tid)
    valid = set(gt.filter(pl.col("valid"))["frame_idx"].to_list())
    lm = lmr
    keep = lm["frame_idx"].is_in(list(valid))
    if int(keep.sum()) >= 10:
        lm = lm.filter(keep)
    fx = lm["frame_idx"].to_numpy()
    n = len(fx)
    P = np.array(lm["landmarks"].to_list(), dtype=np.float64).reshape(n, 478, 3)
    T = np.array(lm["transform"].to_list(), dtype=np.float64).reshape(n, 4, 4)
    cb = np.array(lm["crop_box"].to_list(), dtype=np.float64)
    canonicalize(P, T, cb)

    feats = read_features(out_root, clip_id, "A").filter(pl.col("track_id") == tid).sort("frame_idx")
    pos = {f: i for i, f in enumerate(feats["frame_idx"].to_numpy())}
    M = np.array(feats["feature"].to_list(), dtype=np.float64)
    sel = np.array([pos[f] for f in fx])
    yaw = M[sel, INDEX["head_yaw_dev"]]
    pitch = M[sel, INDEX["head_pitch"]]
    roll = M[sel, INDEX["head_roll"]]
    blur = M[sel, INDEX["face_blur"]]
    light_hh = M[sel, INDEX["face_light_harsh"]]
    SH = np.stack([M[sel, INDEX[f"face_sh_{k}"]] for k in range(9)], axis=1)   # 검사 뷰(빛)

    pq = pl.read_parquet(out_root / clip_id / "parse.parquet").filter(pl.col("track_id") == tid)
    g = lambda col: (dict(zip(pq["frame_idx"].to_list(), pq[col].to_list())) if col in pq.columns else {})
    micro_of, mv_of, lum_of, hi_of = g("face_micro"), g("mouth_vis"), g("skin_lum"), g("skin_clip_hi")
    micro = np.array([micro_of.get(int(f), np.nan) for f in fx], float)
    mv = np.array([mv_of.get(int(f), np.nan) for f in fx], float)
    lum = np.array([lum_of.get(int(f), np.nan) for f in fx], float)
    chi = np.array([hi_of.get(int(f), np.nan) for f in fx], float)
    lum_eff = lum * (1.0 - np.nan_to_num(chi, nan=0.0))

    det_all = pl.read_parquet(out_root / clip_id / "detections.parquet")
    det = det_all.filter(pl.col("track_id") == tid)
    det_bbox = {int(f): tuple(float(v) for v in b)
                for f, b in zip(det["frame_idx"].to_list(), det["bbox"].to_list()) if b is not None}
    frag_bbox = {}
    if "subject_id" in det_all.columns:
        sids = det["subject_id"].drop_nulls().unique().to_list()
        if sids:
            fr = det_all.filter(pl.col("subject_id").is_in(sids) & (pl.col("track_id") != tid))
            frag_bbox = {int(f): tuple(float(v) for v in b)
                         for f, b in zip(fr["frame_idx"].to_list(), fr["bbox"].to_list()) if b is not None}
    erows = [(int(f), np.asarray(e, float)) for f, e in
             zip(det["frame_idx"].to_list(), det["embedding"].to_list()) if e is not None]
    cs = np.full(n, np.nan)
    nrm = np.full(n, np.nan)
    if len(erows) >= 10:
        dfr = np.array([f for f, _ in erows])
        dE = np.stack([e for _, e in erows])
        dn = np.linalg.norm(dE, axis=1)
        Eh = dE / dn[:, None]
        c0 = np.median(Eh, axis=0)
        c0 /= np.linalg.norm(c0)
        cs_of = dict(zip(dfr.tolist(), (Eh @ c0).tolist()))
        nm_of = dict(zip(dfr.tolist(), dn.tolist()))
        cs = np.array([cs_of.get(int(f), np.nan) for f in fx])
        nrm = np.array([nm_of.get(int(f), np.nan) for f in fx])

    tb = read_tubelets(out_root, clip_id).filter(pl.col("track_id") == tid)
    ph = dict(zip(tb["frame_idx"].to_list(), tb["scene_phase"].to_list()))
    board = np.array([ph.get(int(f)) == "boarding" for f in fx])

    B = np.array(lm["blendshapes"].to_list(), dtype=np.float64)
    ecols = [i for i, nm_ in enumerate(BLENDSHAPE_ORDER)
             if nm_ != "_neutral" and not nm_.startswith("eyeLook")]
    expr = B[:, ecols].max(axis=1)
    pupil, sym = face_signals(P)
    return dict(tid=tid, rider=rider, fx=fx, cb=cb, P=P, yaw=yaw, pitch=pitch, roll=roll,
                blur=blur, micro=micro, mv=mv, lum_eff=lum_eff, cs=cs, nrm=nrm, board=board,
                expr=expr, pupil=pupil, sym=sym, lm_all_cb=lm_all_cb, det_bbox=det_bbox,
                frag_bbox=frag_bbox, light_hh=light_hh,
                SH=SH, B=B, R3=T[:, :3, :3])


def compute_picks(rows, cfg):
    """JS 시뮬레이터와 문자 그대로 동일한 의미론 (반올림된 shipped 값 위에서)."""
    surv = [r for r in rows
            if r["sy"] < cfg["sym_max"] and cfg["dev_lo"] < r["dv"] < cfg["dev_hi"]
            and abs(r["pc"]) < cfg["pt_max"]
            and r["pu"] >= cfg["pu_min"]
            and (r["cs"] is None or r["cs"] >= cfg["cs_min"])
            and (r["mv"] is None or r["mv"] >= cfg["mv_min"])
            and (r["lt"] is None or r["lt"] >= cfg["lt_min"])
            and (r["hd"] is None or cfg["df"] == 0
                 or (cfg["df"] > 0 and r["hd"] >= cfg["df"])
                 or (cfg["df"] < 0 and r["hd"] <= 1 + cfg["df"]))
            and (r["ma"] is None or cfg["la_lo"] <= r["ma"] <= cfg["la_hi"])
            and (r["me"] is None or cfg["le_lo"] <= r["me"] <= cfg["le_hi"])
            and (r["ag"] is None or r["ag"] <= cfg["ag_max"])
            and (r["hh"] is None or r["hh"] <= cfg["hh_max"])
            and (r["sp"] is None or r["sp"] >= cfg["sp_min"])
            and cfg["ex_min"] <= r["ex"] <= cfg["ex_max"]]
    for r in surv:
        sf, sl, si, sd = state_scores(r["r"])
        r["_s"] = (cfg["w_face"] * sf + cfg["w_light"] * sl
                   + cfg["w_image"] * si + cfg["w_distort"] * sd)
    surv.sort(key=lambda r: -r["_s"])
    got = []
    for r in surv:
        if all(abs(r["f"] - o["f"]) >= cfg["gap_min"] for o in got):
            got.append(r)
        if len(got) == 3:
            break
    return [r["f"] for r in got]


def build_clip(clip_id, out_root, wb_dir):
    t = frame_table(clip_id, out_root)
    fx, cb, P = t["fx"], t["cb"], t["P"]
    n = len(fx)

    dev = t["yaw"] - FRONTAL_DEG
    cur = [f for f in t["rider"]["samples"]["center_nearest"]]
    bins = t["rider"]["samples"].get("pose_bins", {})
    row_of = {int(f): i for i, f in enumerate(fx)}
    fxset = set(row_of)
    inv_f = sorted(set(t["lm_all_cb"]) - fxset)
    det_f = sorted(set(t["det_bbox"]) - set(t["lm_all_cb"]))
    frag_f = sorted(set(t["frag_bbox"]) - set(t["det_bbox"]) - set(t["lm_all_cb"]))
    ghost_kind = {**{f: "inv" for f in inv_f}, **{f: "det" for f in det_f},
                  **{f: "frag" for f in frag_f}}
    ghost_thumb = set()
    for kfs in (inv_f, det_f, frag_f):
        if len(kfs) > 60:
            ghost_thumb |= {kfs[i] for i in np.unique(np.linspace(0, len(kfs) - 1, 60).astype(int))}
        else:
            ghost_thumb |= set(kfs)

    def _sq(b, W0, H0, pad=1.3):
        x1, y1, x2, y2 = b
        cx, cy, s = (x1 + x2) / 2, (y1 + y2) / 2, max(x2 - x1, y2 - y1) * pad / 2
        return max(0, int(cx - s)), max(0, int(cy - s)), min(W0, int(cx + s)), min(H0, int(cy + s))

    chroma = np.full(n, np.nan)
    mls_az = np.full(n, np.nan)  # v0.20 mesh-LS 이중 자(백색상자 램버트 피팅)
    mls_el = np.full(n, np.nan)
    mls_r = np.full(n, np.nan)
    mls_ag = np.full(n, np.nan)  # DPR 합의각(카메라 프레임, 도)
    K110 = len(SKIN110)          # v0.21 전-프레임 빛 지도·산점 재료(정수 압축)
    mi_arr = np.full((n, K110), -1, np.int16)    # 밝기 0..255, -1=무효
    md_arr = np.full((n, K110), -127, np.int16)  # cosθ×100, -127=무효
    mq_arr = np.zeros((n, K110), np.int8)        # 0=비가시 1=관측(트림) 2=피팅사용
    mf_a = np.full(n, np.nan)
    mf_m = np.full(n, np.nan)
    mls_ca = np.full(n, np.nan)   # v0.26 카메라-기준 광방위(머리 회전 무관 — 구간 분할용)
    c_acc = np.full((n, K110, 2), np.nan)        # 정준 xy(클립 중앙값 → mlay)
    tdir = wb_dir / "thumbs" / clip_id
    tdir.mkdir(parents=True, exist_ok=True)
    thumb_ok = set()
    cap = cv2.VideoCapture(str(out_root / clip_id / "detect.mp4"))
    vf = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fidx = 0
    while True:
        ok, frm = cap.read()
        if not ok:
            break
        H0, W0 = frm.shape[:2]
        i = row_of.get(fidx)
        box = None
        if i is not None:
            cbv = cb[i]
            pts = np.stack([cbv[0] + P[i, :, 0] * (cbv[2] - cbv[0]),
                            cbv[1] + P[i, :, 1] * (cbv[3] - cbv[1])], 1)
            r = skin_sv(frm, pts, cbv)
            if r is not None:
                chroma[i] = r[3]
            mfit = _mls_frame(frm, P[i], cbv)
            if mfit is not None:
                a_m, m_m, keep_m, N_m, _, I_m, v3_m = mfit
                mag = float(np.linalg.norm(m_m))
                if mag > 1e-6:
                    l_m = m_m / mag
                    mls_ca[i] = np.degrees(np.arctan2(l_m[0], l_m[2]))
                    Lf_m = t["R3"][i].T @ l_m
                    mls_az[i] = np.degrees(np.arctan2(Lf_m[0], Lf_m[2]))
                    mls_el[i] = np.degrees(np.arcsin(np.clip(Lf_m[1], -1, 1)))
                    mls_r[i] = min(mag / max(a_m, 1e-3), 99.0)   # a→0 병리 표시 캡
                    sh_m = t["SH"][i]
                    if np.isfinite(sh_m).all():
                        Ld_m = np.array([sh_m[3], sh_m[2], -sh_m[1]])
                        Ld_m /= (np.linalg.norm(Ld_m) + 1e-9)
                        mls_ag[i] = np.degrees(np.arccos(np.clip(float(l_m @ Ld_m), -1, 1)))
                    fin_m = np.isfinite(I_m)
                    vis_m = (N_m[:, 2] > 0.05) & fin_m
                    mi_arr[i] = np.where(fin_m, np.clip(np.nan_to_num(I_m), 0, 255), -1).astype(np.int16)
                    md_arr[i] = np.where(fin_m, np.clip(np.nan_to_num(N_m @ l_m) * 100, -100, 100), -127).astype(np.int16)
                    mq_arr[i] = np.where(~vis_m, 0, np.where(keep_m, 2, 1)).astype(np.int8)
                    mf_a[i], mf_m[i] = a_m, mag
                    v3c_m = v3_m - v3_m.mean(axis=0)
                    c3_m = (t["R3"][i].T @ v3c_m.T).T
                    c3_m /= (np.sqrt((c3_m ** 2).sum(axis=1).mean()) + 1e-9)
                    c_acc[i] = c3_m[SKIN110, :2]
            box = tuple(cbv)
        elif fidx in ghost_thumb:
            k = ghost_kind[fidx]
            box = (t["lm_all_cb"].get(fidx) if k == "inv"
                   else _sq(t["det_bbox"].get(fidx) or t["frag_bbox"].get(fidx), W0, H0))
        if box is not None:
            x1, y1, x2, y2 = (int(v) for v in box)
            if x2 - x1 > 1 and y2 - y1 > 1:
                tile = cv2.resize(frm[max(0, y1):y2, max(0, x1):x2], (THUMB, THUMB))
                cv2.imwrite(str(tdir / f"f{fidx:05d}.jpg"), tile,
                            [cv2.IMWRITE_JPEG_QUALITY, 82])
                thumb_ok.add(fidx)
        fidx += 1
    cap.release()
    vf = max(vf, fidx)
    covered = fxset | set(ghost_kind)
    absent = []
    _st = None
    for f in range(vf):
        if f not in covered:
            if _st is None:
                _st = f
        elif _st is not None:
            absent.append([_st, f - 1])
            _st = None
    if _st is not None:
        absent.append([_st, vf - 1])
    ghost = [{"f": f, "k": k,
              "th": (f"thumbs/{clip_id}/f{f:05d}.jpg" if f in thumb_ok else None)}
             for f, k in sorted(ghost_kind.items())]

    micro_pct, sharp_pct = pct_rank(t["micro"]), pct_rank(t["blur"])
    norm_pct, cs_pct, mv_pct = pct_rank(t["nrm"]), pct_rank(t["cs"]), pct_rank(t["mv"])
    lum_pct, ch_pct = pct_rank(t["lum_eff"]), pct_rank(chroma)   # lt 성분 분해(1층 판독용)
    light_pct = np.nanmean(np.vstack([lum_pct, ch_pct]), axis=0)
    hh_pct = pct_rank(t["light_hh"])

    # v0.19 정준(얼굴-좌표) 광방향 — DPR 이미지 관례(sh1=깊이 안+, sh2=상+, sh3=우+)
    # → CANONICAL_FRAME axis_flip과 동일 표기 L_cam=(sh3,sh2,−sh1) → Rᵀ·L (canonicalize
    # 수학 그대로). az 0=정면 +=피사체 좌 ±180=후방 / el +=위. 앵커 검증: f477 az−103
    # (좌후방=user 실물 일치)·f658 az170 el77(역광)·test_0 확산=az 신뢰불가(ldr 게이트).
    SHa, R3 = t["SH"], t["R3"]
    Lc = np.stack([SHa[:, 3], SHa[:, 2], -SHa[:, 1]], axis=1)
    lmag = np.linalg.norm(Lc, axis=1)
    Lf = np.einsum("nji,nj->ni", R3, Lc)
    with np.errstate(invalid="ignore"):
        la_deg = np.degrees(np.arctan2(Lf[:, 0], Lf[:, 2]))
        le_deg = np.degrees(np.arcsin(np.clip(Lf[:, 1] / (lmag + 1e-9), -1, 1)))
        ldr_raw = lmag / np.maximum(SHa[:, 0], 1e-6)
    bad_sh = ~np.isfinite(SHa).all(axis=1)
    la_deg[bad_sh] = np.nan
    le_deg[bad_sh] = np.nan
    ldr_raw[bad_sh] = np.nan
    ld_pct = pct_rank(ldr_raw)

    # v0.25 확산의 자 = R²(램버트 설명력, raw 0~1 — 분산 비율이라 클립-교차 절대 문턱
    # 성립; DPR ldr은 하드/소프트 클립 분리 AUC 0.248=역방향 실증으로 확산 자에서 은퇴)
    r2_arr = np.full(n, np.nan)
    hd_arr = np.full(n, np.nan)   # v0.27 키:필 하드니스(1−그림자면/밝은면) — 확산 축의 자
    for i2 in range(n):
        if not np.isfinite(mf_m[i2]):
            continue
        I2 = mi_arr[i2].astype(float)
        d2 = md_arr[i2].astype(float) / 100.0
        m2 = (I2 >= 0) & (mq_arr[i2] > 0) & (np.abs(d2) <= 1.0)
        if m2.sum() < 15:
            continue
        Iv, dv2 = I2[m2], d2[m2]
        sst = ((Iv - Iv.mean()) ** 2).sum()
        if sst <= 1e-6:
            r2_arr[i2] = 0.0
            continue
        ssr = ((Iv - (mf_a[i2] + mf_m[i2] * dv2)) ** 2).sum()
        r2_arr[i2] = max(0.0, 1.0 - ssr / sst)
        t1_, t2_ = np.percentile(dv2, [33, 67])
        lit_, sh_ = Iv[dv2 >= t2_], Iv[dv2 <= t1_]
        if len(lit_) >= 5 and len(sh_) >= 5 and np.median(lit_) >= 5:
            hd_arr[i2] = float(np.clip(1.0 - np.median(sh_) / np.median(lit_), 0, 1))

    def _spread(v):
        fin = v[np.isfinite(v)]
        if len(fin) < 10:
            return 0.0
        p10, p50, p90 = np.percentile(fin, [10, 50, 90])
        return float((p90 - p10) / (abs(p50) + 1e-6))
    lf = round(min(1.0, 0.5 * (_spread(t["lum_eff"]) + _spread(chroma)) / 0.8), 2)

    R = np.stack([rank01(t["expr"], flip=True), rank01(t["pupil"]),
                  rank01(sharp_pct), rank01(micro_pct), rank01(norm_pct),
                  rank01(cs_pct), rank01(mv_pct), rank01(light_pct)], axis=1)

    def num(v, nd=2):
        return None if not np.isfinite(v) else round(float(v), nd)

    pt = t["pitch"]
    pt_med = float(np.nanmedian(pt)) if np.isfinite(pt).any() else 0.0

    def _pts(i, idxs):
        return [[round(float(P[i, j, 0]), 3), round(float(P[i, j, 1]), 3)] for j in idxs]

    rows = []
    for i in range(n):
        sh_i = t["SH"][i]
        rows.append({"f": int(fx[i]), "b": int(t["board"][i]),
                     "pt": num(pt[i], 1),
                     "pc": round(float(pt[i] - pt_med), 1) if np.isfinite(pt[i]) else 0.0,
                     "rl": num(t["roll"][i], 1),
                     "sh": ([round(float(v), 3) for v in sh_i] if np.isfinite(sh_i).all() else None),
                     "sy": round(float(t["sym"][i]), 3) if np.isfinite(t["sym"][i]) else 9.9,
                     "dv": round(float(dev[i]), 1) if np.isfinite(dev[i]) else 99.0,
                     "pu": round(float(t["pupil"][i]), 3) if np.isfinite(t["pupil"][i]) else 0.0,
                     "ex": round(float(t["expr"][i]), 3) if np.isfinite(t["expr"][i]) else 1.0,
                     "cs": num(cs_pct[i], 1), "mv": num(mv_pct[i], 1), "lt": num(light_pct[i], 1),
                     "lm": num(lum_pct[i], 1), "ch": num(ch_pct[i], 1),
                     "hh": num(hh_pct[i], 1), "sp": num(sharp_pct[i], 1),
                     "lmr": num(t["lum_eff"][i], 1), "chr": num(chroma[i], 1),
                     "ma": num(mls_az[i], 0), "me": num(mls_el[i], 0),
                     "mr": num(mls_r[i], 2), "ag": num(mls_ag[i], 0),
                     "mi": ([int(v) for v in mi_arr[i]] if np.isfinite(mf_m[i]) else None),
                     "md": ([int(v) for v in md_arr[i]] if np.isfinite(mf_m[i]) else None),
                     "mq": ([int(v) for v in mq_arr[i]] if np.isfinite(mf_m[i]) else None),
                     "mf": ([num(mf_a[i], 1), num(mf_m[i], 1)] if np.isfinite(mf_m[i]) else None),
                     "r2": num(r2_arr[i], 2), "hd": num(hd_arr[i], 2),
                     "la": num(la_deg[i], 0), "le": num(le_deg[i], 0),
                     "ldr": num(ldr_raw[i], 2), "ld": num(ld_pct[i], 1),
                     "rm": ([round(float(v), 3) for v in R3[i].ravel()]
                            if np.isfinite(sh_i).all() and np.isfinite(R3[i]).all() else None),
                     "r": [round(float(v), 4) for v in R[i]],
                     "sk": {"a": _pts(i, SKIN_ANCHORS), "o": _pts(i, OVAL_ORDER),
                            "e": _pts(i, EYE_CORNERS)},
                     "th": (f"thumbs/{clip_id}/f{int(fx[i]):05d}.jpg" if int(fx[i]) in thumb_ok else None)})
    selftest = compute_picks([dict(r) for r in rows], DEFAULT_CFG)

    # ── 검사 뷰(픽 한정) 자산: 랜드마크 2D·blendshape 상위·Laplacian 히트맵 ──
    pickset = sorted({int(f) for f in (*cur, *selftest, *bins.values()) if int(f) in row_of})
    pv = {}
    cap = cv2.VideoCapture(str(out_root / clip_id / "detect.mp4"))
    for f in pickset:
        i = row_of[f]
        lm2 = [[round(float(x), 3), round(float(y), 3)] for x, y in P[i, :, :2]]
        bs_row = t["B"][i]
        top = np.argsort(-bs_row)
        bs_top = [[BLENDSHAPE_ORDER[j], round(float(bs_row[j]), 3)]
                  for j in top if BLENDSHAPE_ORDER[j] != "_neutral"][:8]
        lap_ok = 0
        cbv = cb[i]
        x1, y1, x2, y2 = (int(v) for v in cbv)
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, frm = cap.read()
        if ok and x2 - x1 > 1 and y2 - y1 > 1:
            gray = cv2.cvtColor(frm[max(0, y1):y2, max(0, x1):x2], cv2.COLOR_BGR2GRAY)
            lap = np.abs(cv2.Laplacian(gray, cv2.CV_32F, ksize=3))
            hi = np.percentile(lap, 99) + 1e-6
            lapu = np.clip(lap / hi * 255, 0, 255).astype(np.uint8)
            cv2.imwrite(str(tdir / f"f{f:05d}_lap.jpg"),
                        cv2.resize(lapu, (THUMB, THUMB)), [cv2.IMWRITE_JPEG_QUALITY, 80])
            lap_ok = 1
        mls = None
        if ok:
            mfit = _mls_frame(frm, P[i], cbv)
            if mfit is not None:
                a_m, m_m, keep_m, N_m, xy_m, I_m, v3_m = mfit
                mag = float(np.linalg.norm(m_m))
                if mag > 1e-6:
                    l_m = m_m / mag
                    ndl = N_m @ l_m
                    # v0.21: 지도·산점 재료는 rows(전 프레임)로 이관 — pv는 화살 재료만
                    w_c, h_c = max(cbv[2] - cbv[0], 1e-6), max(cbv[3] - cbv[1], 1e-6)
                    mls = {"p": [[round(float((xy_m[j, 0] - cbv[0]) / w_c), 3),
                                  round(float((xy_m[j, 1] - cbv[1]) / h_c), 3)] for j in SKIN110],
                           "n": [[round(float(N_m[k, 0]), 2), round(float(-N_m[k, 1]), 2)]
                                 for k in range(len(SKIN110))],
                           "d": [round(float(v), 2) for v in ndl]}
        pv[str(f)] = {"lm": lm2, "bs": bs_top, "rl": num(t["roll"][i], 1), "lap": lap_ok,
                      "mls": mls}
    cap.release()

    mlay = None
    if np.isfinite(c_acc).any():
        med_lay = np.nanmedian(c_acc, axis=0)
        if np.isfinite(med_lay).all():
            mlay = [[round(float(x), 2), round(float(y), 2)] for x, y in med_lay]
    mi_valid = mi_arr[mi_arr >= 0]
    mrange = ([int(np.percentile(mi_valid, 2)), int(np.percentile(mi_valid, 98))]
              if len(mi_valid) > 100 else None)   # v0.21.2 클립-고정 밝기 척도

    # v0.26 조명 구간 지도 — (카메라-기준 방향, 세기, 확산) 결합 상태의 시계열 분할.
    # 카메라-기준인 이유: 태양은 머리가 돌아도 카메라 좌표에서 불변 → 구간=장면 조명 변화.
    def _smed(x, k=7):
        out = np.copy(x)
        for i2 in range(len(x)):
            w = x[max(0, i2 - k):i2 + k + 1]
            w = w[np.isfinite(w)]
            out[i2] = np.median(w) if len(w) else np.nan
        return out

    lseg = []
    if n > 30:
        cax = _smed(np.cos(np.radians(mls_ca)))
        cay = _smed(np.sin(np.radians(mls_ca)))
        lum_n = _smed(np.clip(np.nan_to_num(t["lum_eff"], nan=np.nan) / 255.0, 0, 1))
        hds = _smed(hd_arr)
        feat = np.stack([0.7 * cax, 0.7 * cay, 1.0 * lum_n, 0.8 * hds], 1)
        BLK = 12
        merged = []
        for b0 in range(0, n, BLK):
            segf = feat[b0:b0 + BLK]
            fin = np.isfinite(segf).all(axis=1)
            mv = segf[fin].mean(0) if fin.sum() >= 4 else None
            blk = [b0, min(b0 + BLK, n), mv]
            if merged and merged[-1][2] is not None and mv is not None                and float(np.linalg.norm(merged[-1][2] - mv)) < 0.22:
                w0 = merged[-1][1] - merged[-1][0]
                w1 = blk[1] - blk[0]
                merged[-1][2] = (merged[-1][2] * w0 + mv * w1) / (w0 + w1)
                merged[-1][1] = blk[1]
            elif merged and merged[-1][2] is None and mv is None:
                merged[-1][1] = blk[1]
            else:
                merged.append(blk)
        for i0, i1, mv in merged:
            f0, f1 = int(fx[i0]), int(fx[min(i1, n) - 1])
            if mv is None:
                lseg.append([f0, f1, "na"])
                continue
            seg_ca = float(np.degrees(np.arctan2(mv[1], mv[0])))
            seg_lm = mv[2] * 255.0
            seg_hd = mv[3] / 0.8
            cls = ("dark" if seg_lm < 55 else
                   "back" if abs(seg_ca) > 110 else
                   "hard" if seg_hd >= 0.42 else "flat")
            lseg.append([f0, f1, cls])

    return {"clip": clip_id, "tid": t["tid"], "n": n, "vf": vf, "cur": cur, "lf": lf,
            "mlay": mlay, "mrange": mrange, "lseg": lseg,
            "selftest": selftest, "rows": rows, "ghost": ghost, "absent": absent, "pv": pv}


HTML = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><title>likeness sampling workbench v0.10</title>
<style>
body{background:#161616;color:#ddd;font:13px/1.45 system-ui,sans-serif;margin:0}
#top{position:sticky;top:0;background:#1d1d1d;border-bottom:1px solid #333;padding:8px 14px;z-index:9}
#selftest{font-weight:600}
.ok{color:#7c6} .bad{color:#e66}
#insp{position:fixed;right:0;top:78px;bottom:0;width:340px;overflow:auto;background:#1b1b1b;
  border-left:1px solid #333;padding:10px 12px;box-sizing:border-box;z-index:8}
#deck{position:fixed;left:0;top:78px;bottom:0;width:384px;background:#191919;
  border-right:2px solid #3a3a3a;padding:8px 12px;box-sizing:border-box;z-index:8;overflow-y:auto}
#dtabs{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:6px}
.dtab{padding:3px 12px;border:1px solid #444;border-radius:4px 4px 0 0;cursor:pointer;
  font-size:12px;color:#aaa;display:flex;align-items:center;gap:6px}
.dtab.cur{background:#262f38;color:#dfeaf5;border-color:#6a92b8;font-weight:600}
.dtab.dm{opacity:.45}
.dtab .sm{font-size:9px;border:1px solid #555;border-radius:2px;padding:0 4px;color:#999}
.dtab .sm.on{color:#161616;font-weight:700}
.dtab .sm.s.on{background:#d8c455;border-color:#d8c455}
.dtab .sm.m.on{background:#e06666;border-color:#e06666}
#bridge{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:4px 0 8px;
  padding-bottom:6px;border-bottom:1px solid #2c2c2c}
.bm{font-size:10px;color:#889}
.bm .bar{display:inline-block;width:44px;height:8px;background:#141414;border:1px solid #2c2c2c;
  vertical-align:middle;margin-left:4px}
.bm .bar i{display:block;height:100%}
.chanview{display:block}
.chanview .body{display:block}
.chanview .dial{margin:4px 0 8px}
.chanview .dial label{font-size:12.5px}
.chanview.gmuted .body{opacity:.4}
.subch{border-left:2px solid #3a4a5a;margin:6px 0 10px 4px;padding-left:12px}
.subttl{font-size:12px;font-weight:600;color:#9ad;margin-bottom:2px}
.fblock{display:flex;gap:10px;align-items:center;padding:8px 4px 0;border-top:1px solid #2c2c2c;
  margin-top:8px}
.fader{flex:1;display:flex;gap:8px;align-items:center}
.fader input{flex:1}
.fader .fv{font-size:12px;color:#fc6;min-width:34px;text-align:right}
.mlbl{font-size:10px;color:#777}
#inspToggle{position:fixed;right:340px;top:84px;z-index:12;background:#2a2a2a;border:1px solid #555;
  color:#bbb;border-radius:3px 0 0 3px;cursor:pointer;padding:4px 5px;font-size:11px}
body.inspc #inspToggle{right:0}
body.inspc #insp{display:none}
body.inspc #main{margin-right:30px}
#main{margin-left:384px;margin-right:340px;margin-bottom:20px;padding:10px 16px}
#sticky{position:sticky;top:78px;background:#161616;z-index:5;padding:4px 0 6px;
  border-bottom:1px solid #2c2c2c}
.box{border:1px solid #2a2a2a;border-radius:6px;padding:10px 14px;margin:14px 0;background:#191919}
.box .boxttl{font-size:12px;font-weight:600;color:#9ad;margin-bottom:6px}
.grp{margin:10px 0 4px;color:#9ad;font-weight:600;font-size:12px;text-transform:uppercase;cursor:pointer;
  display:flex;align-items:center;gap:6px}
.grp .arr{color:#678}
.grp .sm{font-size:10px;border:1px solid #555;border-radius:2px;padding:0 5px;color:#999;cursor:pointer}
.grp .sm.on{color:#161616;font-weight:700}
.grp .sm.s.on{background:#d8c455;border-color:#d8c455}
.grp .sm.m.on{background:#e06666;border-color:#e06666}
.gmute{opacity:.35}
.dial{margin:6px 0}
.dial label{display:flex;justify-content:space-between;font-size:12px;color:#bbb}
.dial.mod label{color:#fc6}
.dial.mod label::after{content:" •"}
.dial input[type=range]{width:100%}
.dh{display:block;background:#141414;border:1px solid #2e2e2e;margin-top:1px}
#tabs{display:flex;gap:6px;flex-wrap:wrap;margin:4px 0 10px}
.tab{padding:4px 10px;border:1px solid #444;border-radius:4px;cursor:pointer;font-size:12px;color:#aaa}
.tab.cur{background:#28343f;color:#dfeaf5;border-color:#6a92b8}
.tab .b{color:#9a8} .tab .g{color:#cb8}
.funnel{margin:6px 0 10px;max-width:560px}
.fr{display:flex;align-items:center;gap:8px;font-size:11px;color:#9a8;margin:1px 0}
.fr .lbl{width:52px;text-align:right;color:#8b9}
.fr .bar{height:9px;border-radius:2px}
.fr .cnt{color:#bcb}
.rowlbl{color:#89b;font-size:11px;margin-top:12px}
.strip{display:flex;gap:6px;flex-wrap:wrap;margin:4px 0}
.cell{position:relative;cursor:pointer}
.strip.sm .cell,.strip.sm .cell img,.strip.sm .cell .noimg{width:112px}
.strip.sm .cell img,.strip.sm .cell .noimg{height:112px}
.strip.big .cell,.strip.big .cell img,.strip.big .cell .noimg{width:224px}
.strip.big .cell img,.strip.big .cell .noimg{height:224px}
.cell img{display:block;border:2px solid #444;box-sizing:border-box;transition:transform .07s}
.strip.sm .cell:hover img{transform:scale(2);position:relative;z-index:8;border-color:#9cf}
.strip.big .cell:hover img{transform:scale(1.4);position:relative;z-index:8;border-color:#9cf}
.cell .noimg{border:2px dashed #444;box-sizing:border-box;display:flex;align-items:center;
  justify-content:center;color:#666;font-size:10px}
.cell .cap{font-size:10px;color:#aaa;line-height:1.25;margin-top:1px}
.cell.pos img,.cell.pos .noimg{border-color:#5c5}
.cell.neg img,.cell.neg .noimg{border-color:#e55}
.cell.selg img{box-shadow:0 0 0 2px #f90}
.cell .flag{position:absolute;top:2px;right:2px;font-size:12px;color:#fff;text-shadow:0 0 3px #000}
.pickA img{outline:2px solid #7ac} .pickB img{outline:2px dashed #ca7}
.diff img{outline-color:#f80 !important}
#tl{position:relative;margin:8px 0 2px;max-width:1004px}
#tl canvas{display:block;background:#101010;border:1px solid #333;cursor:crosshair}
#tlTip{position:absolute;display:none;background:#222;border:1px solid #555;padding:4px;
  z-index:20;pointer-events:none;font-size:10px;color:#ccc;line-height:1.3}
#tlTip img{width:112px;height:112px;display:block;border:1px solid #444;margin-bottom:2px}
.legend{font-size:10px;color:#999;margin:2px 0 10px}
.legend span{display:inline-block;margin-right:11px}
.legend i{display:inline-block;width:9px;height:9px;margin-right:3px;vertical-align:-1px}
.itabs{display:flex;gap:4px;flex-wrap:wrap;margin:6px 0}
.itab{padding:2px 8px;border:1px solid #444;border-radius:3px;cursor:pointer;font-size:11px;color:#aaa}
.itab.cur{background:#3a3226;color:#fc6;border-color:#a86}
#inspImg{width:300px;height:300px;display:block;border:1px solid #444;background:#111}
.ibar{display:flex;align-items:center;gap:6px;font-size:11px;margin:2px 0}
.ibar .nm{width:130px;color:#aab;text-align:right;overflow:hidden;white-space:nowrap}
.ibar .bv{height:9px;background:#7a9ac0}
.gtbtn button{margin-right:6px}
button{background:#2a2a2a;color:#ddd;border:1px solid #555;border-radius:3px;
  padding:3px 10px;margin-right:6px;cursor:pointer}
button:hover{background:#383838}
.gtscore{color:#cb8;font-size:12px;margin-left:12px}
.note{color:#777;font-size:11px}
</style></head><body>
<div id="top">
 <span id="selftest">selftest…</span>
 <button onclick="snapshotB()">현재 설정 → B 저장</button>
 <button onclick="clearB()">B 지우기</button>
 <button onclick="resetA()">A 기본값</button>
 <button onclick="exportGT()">GT export (.jsonl)</button>
 <input type="file" id="gtfile" style="display:none" onchange="importGT(this)">
 <button onclick="document.getElementById('gtfile').click()">GT import</button>
 <span class="gtscore" id="gtscore"></span>
 <div class="note"><b>클릭=프레임 선택(우측 검사)</b> · GT=검사 패널 ＋/− 버튼 · Shift+클릭=포즈 그라운딩 · 호버=확대 · ←→=클립 · 저장 홈=fixtures/eval/</div>
</div>
<div id="main"></div><div id="insp"></div><div id="deck"></div>
<button id="inspToggle" onclick="document.body.classList.toggle('inspc')">◀▶</button>
<script src="data.js"></script>
<script>
const DIALS=[
 ["포즈"],
 ["sym_max","보이는-정면 sym <",0.3,2.0,0.05],
 ["dev_lo","yaw dev 하한 > (밴드)",-90,89,1],
 ["dev_hi","yaw dev 상한 < (밴드)",-89,90,1],
 ["pt_max","|pitch dev| < (클립상대·99=off)",3,99,1],
 ["표정·얼굴"],
 ["pu_min","눈동자 pupil >=",0,0.8,0.01],
 ["ex_min","표정 ex 하한 >= (밴드)",0,0.8,0.05],
 ["ex_max","표정 ex 상한 <= (밴드)",0.2,1.0,0.05],
 ["빛"],
 ["lt_min","조도·생동 lt pct >=",0,90,5],
 ["hh_max","거칠기 hh pct <=",10,100,5],
 ["df","확산: ◀ − 조명비 낮음(~2:1 소프트)만 · 0=전체 · + 조명비 높음(4:1+ 하드)만 ▶",-0.95,0.95,0.05],
 ["la_lo","정준 방위 az 하한 (소스=mesh-LS · 0=정면 +=피사체좌)",-180,180,5],
 ["la_hi","정준 방위 az 상한",-180,180,5],
 ["le_lo","정준 고도 el 하한 (소스=mesh-LS · +=위)",-90,90,5],
 ["le_hi","정준 고도 el 상한",-90,90,5],
 ["ag_max","이중 자 합의각 <= (도 · 180=off)",15,180,5],
 ["영상"],
 ["sp_min","선명 sp pct >=",0,90,5],
 ["왜곡"],
 ["cs_min","정체성 cs pct >=",0,90,5],
 ["mv_min","입-가시 mv pct >=",0,90,5],
 ["종합"],
 ["w_face","w 표정·얼굴 상태",0,0.8,0.05],
 ["w_light","w 빛 상태",0,0.8,0.05],
 ["w_image","w 영상 상태",0,0.8,0.05],
 ["w_distort","w 왜곡(판독성) 상태",0,0.8,0.05],
 ["gap_min","픽 간 최소 프레임 gap",0,60,2],
];
const DEF={sym_max:0.6,dev_lo:-15,dev_hi:15,pt_max:99,pu_min:0.4,cs_min:0,mv_min:0,lt_min:0,
           ex_min:0,ex_max:1.0,gap_min:12,hh_max:100,sp_min:0,
           df:0,la_lo:-180,la_hi:180,le_lo:-90,le_hi:90,ag_max:180,
           w_face:0.45,w_light:0.20,w_image:0.15,w_distort:0.20};
let A={...DEF}, Bcfg=null, GT={}, cur=0, sortMode="time", poseOpen=false, ATT=false;
let selF=null, iMode="포즈", collapsed={};
let _rp=false;   // 렌더 스로틀(rAF) — 풀 전체 표시 + 드래그 부드러움 양립
function scheduleRender(){if(_rp)return;_rp=true;requestAnimationFrame(()=>{_rp=false;render();});}
const STAGES=["포즈","표정·얼굴","빛","영상","왜곡"];
let MUTE={"포즈":false,"표정·얼굴":false,"빛":false,"영상":false,"왜곡":false};   // v0.11 채널 M
const NOMUTE={"포즈":false,"표정·얼굴":false,"빛":false,"영상":false,"왜곡":false};
function anyMute(){return STAGES.some(s=>MUTE[s]);}
function muteG(g){MUTE[g]=!MUTE[g];buildPanel();render();}
function soloG(g){
 const isSolo=!MUTE[g]&&STAGES.every(s=>s==g||MUTE[s]);
 if(isSolo){for(const s of STAGES)MUTE[s]=false;}
 else{for(const s of STAGES)MUTE[s]=(s!=g);}
 buildPanel();render();}
const SCOL=["#c98a4a","#e08aa8","#d8c455","#55aacc","#b070d0"];
const SURV="#69d069";
const K2G={sym_max:"포즈",dev_lo:"포즈",dev_hi:"포즈",pt_max:"포즈",
 pu_min:"표정·얼굴",ex_min:"표정·얼굴",ex_max:"표정·얼굴",
 lt_min:"빛",hh_max:"빛",sp_min:"영상",cs_min:"왜곡",mv_min:"왜곡",
 df:"빛",la_lo:"빛",la_hi:"빛",le_lo:"빛",le_hi:"빛",ag_max:"빛",
 w_face:"표정·얼굴",w_light:"빛",w_image:"영상",w_distort:"왜곡"};

function gPass(r,c,g){   // 채널별 하드 게이트 (v0.11: mute=게이트 해제)
 if(g==0)return r.sy<c.sym_max&&r.dv>c.dev_lo&&r.dv<c.dev_hi&&Math.abs(r.pc)<c.pt_max;
 if(g==1)return r.pu>=c.pu_min&&r.ex>=c.ex_min&&r.ex<=c.ex_max;
 if(g==2)return (r.lt==null||r.lt>=c.lt_min)&&(r.hh==null||r.hh<=c.hh_max)&&(r.hd==null||c.df==0||(c.df>0?r.hd>=c.df:r.hd<=1+c.df))&&(r.ma==null||(r.ma>=c.la_lo&&r.ma<=c.la_hi))&&(r.me==null||(r.me>=c.le_lo&&r.me<=c.le_hi))&&(r.ag==null||r.ag<=c.ag_max);
 if(g==3)return r.sp==null||r.sp>=c.sp_min;
 return (r.cs==null||r.cs>=c.cs_min)&&(r.mv==null||r.mv>=c.mv_min);}
function firstFail(r,c,M){
 M=M||MUTE;
 for(let g=0;g<5;g++){if(!M[STAGES[g]]&&!gPass(r,c,g))return g;}
 return -1;}
function pass(r,c,M){return firstFail(r,c,M)<0;}
function funnel(rows,c,M){
 M=M||MUTE;
 const out=[rows.length];
 let cur_=rows;
 for(let g=0;g<5;g++){
  if(!M[STAGES[g]])cur_=cur_.filter(r=>gPass(r,c,g));
  out.push(cur_.length);}
 return out;}
function stateScores(rr){
 return [(2*rr[0]+rr[1])/3, rr[7], (rr[2]+rr[3])/2, (rr[5]+rr[6]+rr[4])/3];}
function score(r,c,lf,M){
 M=M||MUTE;
 const [sf,sl,si,sd]=stateScores(r.r);
 const wl=ATT?c.w_light*(lf==null?1:lf):c.w_light;
 return (M["표정·얼굴"]?0:c.w_face)*sf+(M["빛"]?0:wl)*sl
  +(M["영상"]?0:c.w_image)*si+(M["왜곡"]?0:c.w_distort)*sd;}
function picks(rows,c,lf,M){
 M=M||MUTE;
 const sv=rows.filter(r=>pass(r,c,M));
 sv.forEach(r=>r._s=score(r,c,lf,M));
 sv.sort((a,b)=>b._s-a._s);
 const got=[];
 for(const r of sv){if(got.every(o=>Math.abs(r.f-o.f)>=c.gap_min))got.push(r);if(got.length==3)break;}
 return got.map(r=>r.f);}

function cellHTML(clip,r,cls){
 const k=clip+":"+r.f, fl=GT[k]||"";
 const sel=(selF==r.f)?" selg":"";
 const img=r.th?`<img src="${r.th}" loading="lazy">`:`<div class="noimg">f${r.f}<br>(no thumb)</div>`;
 const cap=`f${r.f} ex${r.ex} pu${r.pu}<br>cs${r.cs==null?"--":r.cs} mv${r.mv==null?"--":r.mv} lt${r.lt==null?"--":r.lt}`;
 const mark=fl=="pos"?"O":fl=="neg"?"X":"";
 return `<div class="cell ${fl} ${cls||""}${sel}" onclick="onCell(event,'${clip}',${r.f})">${img}
   <span class="flag">${mark}</span><div class="cap">${cap}</div></div>`;}

function funnelHTML(fn){
 const names=["전체",...STAGES];
 const cols=["#666",...SCOL.slice(0,STAGES.length-1),SURV];
 const mx=Math.max(fn[0],1), last=fn.length-1;
 return `<div class="funnel">`+fn.map((v,i)=>
  `<div class="fr${i==last?" last":""}"><span class="lbl">${names[i]}</span>
   <span class="bar" style="width:${Math.max(2,Math.round(280*v/mx))}px;background:${cols[i]}"></span>
   <span class="cnt">${v}</span></div>`).join("")+
  (fn[last]<3?`<div class="fr"><span class="lbl"></span><span style="color:#e66">⚠ 풀&lt;3</span></div>`:``)+`</div>`;}

function legendHTML(){
 return `<div class="legend"><span><i style="background:${SURV}"></i>생존</span>`+
  STAGES.map((s,i)=>`<span><i style="background:${SCOL[i]}"></i>${s}에 걸러짐</span>`).join("")+
  `<span><i style="background:rgba(80,170,180,.5)"></i>boarding</span>
   <span><i style="background:#7ac"></i>A 픽</span><span><i style="border:1px dashed #ca7;width:7px;height:7px"></i>B 픽</span>
   <span style="margin-left:8px">유령:</span>
   <span><i style="background:#a05244"></i>무효</span><span><i style="background:#5a78a0"></i>미측정</span>
   <span><i style="background:#8a70b0"></i>파편</span><span><i style="background:#3a3a3a"></i>무검출</span>
   <span style="margin-left:8px">조명 구간(상단 밴드):</span>
   <span><i style="background:#d98a3d"></i>직사</span><span><i style="background:#4aa7a0"></i>확산·평광</span>
   <span><i style="background:#9a6fd0"></i>역광</span><span><i style="background:#5a6a7a"></i>어두움</span></div>`;}

function render(){
 const sy0=window.scrollY;
 let st_ok=true,st_msg=[],gtP=0,gtN=0,gtPB=0,gtNB=0;
 const isDef=JSON.stringify(A)==JSON.stringify(DEF);
 const meta=WB.clips.map(C=>{
  const pA=picks(C.rows,A,C.lf), fn=funnel(C.rows,A);
  const pB=Bcfg?picks(C.rows,Bcfg,C.lf):null;
  if(isDef&&!ATT&&!anyMute()){const same=JSON.stringify(pA.slice().sort((a,b)=>a-b))==JSON.stringify(C.selftest.slice().sort((a,b)=>a-b));
   if(!same){st_ok=false;st_msg.push(C.clip);}}
  pA.forEach(f=>{const g=GT[C.clip+":"+f];if(g=="pos")gtP++;if(g=="neg")gtN++;});
  if(pB)pB.forEach(f=>{const g=GT[C.clip+":"+f];if(g=="pos")gtPB++;if(g=="neg")gtNB++;});
  let p=0,ng=0;for(const k in GT){if(k.startsWith(C.clip+":")){GT[k]=="pos"?p++:ng++;}}
  return {pA,pB,fn,p,ng,alive:fn[fn.length-1]};});

 const tabs=WB.clips.map((C,i)=>
  `<span class="tab${i==cur?" cur":""}" onclick="cur=${i};selF=null;render()">${C.clip}
   <span class="b">${meta[i].alive}</span>${meta[i].p+meta[i].ng?`<span class="g"> +${meta[i].p}/−${meta[i].ng}</span>`:""}</span>`).join("");

 const C=WB.clips[cur], m=meta[cur];
 if(selF==null||!C.rows.some(r=>r.f==selF)) selF=(m.pA[0]!=null?m.pA[0]:(C.rows[0]&&C.rows[0].f));
 const byf={};C.rows.forEach(r=>byf[r.f]=r);
 const setA=new Set(m.pA), setB=m.pB?new Set(m.pB):null;
 const gInv=C.ghost.filter(g=>g.k=="inv").length, gDet=C.ghost.filter(g=>g.k=="det").length,
       gFrag=C.ghost.filter(g=>g.k=="frag").length,
       gAbs=C.absent.reduce((a,r)=>a+r[1]-r[0]+1,0);
 let h=`<div id="sticky"><div id="tabs">${tabs}</div><b>${C.clip}</b> t${C.tid} <span class="note">비디오 ${C.vf}f = 측정 ${C.n}`+
  (gInv?` + 무효 ${gInv}`:"")+(gDet?` + 미측정 ${gDet}`:"")+(gFrag?` + 파편 ${gFrag}`:"")+(gAbs?` + 무검출 ${gAbs}`:"")+
  ` · <b>빛 판별력 lf=${C.lf==null?"?":C.lf}</b>${C.lf!=null&&C.lf<0.35?` <span style="color:#e88"><b>⚠확산 클립 — 방위·존 판독 금지(포즈-편향)</b></span>`:""}${ATT?` <span style="color:#fc6">(감쇠: w_light ${A.w_light}→${(A.w_light*(C.lf==null?1:C.lf)).toFixed(2)})</span>`:""}`+
  (anyMute()?` · <span style="color:#e06666"><b>${STAGES.filter(s=>!MUTE[s]).length==1?"SOLO: "+STAGES.find(s=>!MUTE[s]):"MUTE: "+STAGES.filter(s=>MUTE[s]).join(", ")}</b></span>`:"")+
  ` · 풀 정렬:</span>
  <button onclick="sortMode=sortMode=='time'?'score':'time';render()">${sortMode=='time'?'시간순':'점수순'}</button>
  <button onclick="poseOpen=!poseOpen;render()">포즈 눈금 ${poseOpen?'닫기':'보기'}</button>
  <label style="font-size:12px;color:#bbb;margin-left:6px"><input type="checkbox" ${ATT?"checked":""}
   onchange="ATT=this.checked;render()"> 빛 분산-감쇠(시험)</label>`;
 h+=`<div id="tl"><canvas id="tlc" width="1000" height="44"></canvas><div id="tlTip"></div></div>`+legendHTML()+`</div>`;
 h+=`<div class="box"><div class="boxttl">결과 — 퍼널·픽</div>`+funnelHTML(m.fn);
 if(poseOpen){
  const wt=C.rows.filter(r=>r.th);
  const samp=a=>{if(a.length<=8)return a;const o=[];for(let i=0;i<8;i++)o.push(a[Math.round(i*(a.length-1)/7)]);return [...new Set(o)];};
  const byDev=samp(wt.slice().sort((a,b)=>a.dv-b.dv));
  const bySy=samp(wt.slice().sort((a,b)=>a.sy-b.sy));
  const pose=r=>{const ff=firstFail(r,A);const dim=(ff===0||ff===1)?"opacity:.35":"";
   return `<div class="cell" style="${dim}" onclick="groundPose('${C.clip}',${r.f})"><img src="${r.th}" loading="lazy">
    <div class="cap">dv${r.dv} sy${r.sy}<br>pt${r.pt==null?"--":r.pt} pc${r.pc}</div></div>`;};
  h+=`<div class="rowlbl">포즈 눈금 — yaw 사다리 (좌→정면→우 · 클릭=밴드 확장 그라운딩 · 흐림=포즈 스크린에 걸러짐)</div>
   <div class="strip sm">`+byDev.map(pose).join("")+`</div>
   <div class="rowlbl">포즈 눈금 — sym 사다리</div><div class="strip sm">`+bySy.map(pose).join("")+`</div>`;
 }
 h+=`<div class="rowlbl">CURRENT (생산 likeness.json)</div><div class="strip sm">`+
   C.cur.map(f=>byf[f]?cellHTML(C.clip,byf[f],""):"").join("")+`</div>`;
 h+=`<div class="rowlbl">A 픽</div><div class="strip big">`+
   m.pA.map(f=>cellHTML(C.clip,byf[f],"pickA"+(setB&&!setB.has(f)?" diff":""))).join("")+`</div>`;
 if(m.pB)h+=`<div class="rowlbl">B 픽</div><div class="strip big">`+
   m.pB.map(f=>cellHTML(C.clip,byf[f],"pickB"+(!setA.has(f)?" diff":""))).join("")+`</div>`;
 if(anyMute()){   // v0.11 diff 뷰: solo/뮤트 선택 vs 종합(뮤트 해제) 선택 — 1층→2층 다리
  const pRef=picks(C.rows,A,C.lf,NOMUTE);
  h+=`<div class="rowlbl">믹스 픽 (뮤트 해제 기준 — 주황 외곽=현재 solo/뮤트 픽과 불일치)</div><div class="strip big">`+
   pRef.map(f=>byf[f]?cellHTML(C.clip,byf[f],(setA.has(f)?"":"diff ")+"pickB"):"").join("")+`</div>`;
 }
 h+=`</div>`;   // 결과 박스 닫기
 const sv=C.rows.filter(r=>pass(r,A));
 sv.forEach(r=>r._s=score(r,A,C.lf));
 const ordered=sortMode=="time"?sv.slice().sort((a,b)=>a.f-b.f):sv.slice().sort((a,b)=>b._s-a._s);
 h+=`<div class="box"><div class="boxttl">생존 풀 (A, ${sv.length}행 전체 · ${sortMode=='time'?'시간순':'점수순'})</div>
  <div class="strip sm">`+ordered.map(r=>cellHTML(C.clip,r,"")).join("")+`</div></div>`;
 document.getElementById("main").innerHTML=h;
 drawTimeline(C,m);
 drawDialHists(C,m);
 renderInsp(C,m);

 const st=document.getElementById("selftest");
 if(isDef&&!ATT&&!anyMute()){st.textContent=st_ok?"selftest OK — JS ≡ python (기본 설정)":"selftest FAIL: "+st_msg.join(",");
  st.className=st_ok?"ok":"bad";}
 else{st.textContent="탐색 중 (기본값 아님/뮤트 중 — selftest는 기본값·전 채널에서만)";st.className="";}
 const tot=Object.keys(GT).length;
 document.getElementById("gtscore").textContent=
  tot?`GT ${tot}개 · A: +${gtP}/−${gtN}`+(Bcfg?` · B: +${gtPB}/−${gtNB}`:""):"";
 const ms=document.getElementById("mstat");
 if(ms)ms.innerHTML=`생존 ${m.fn[m.fn.length-1]}행 → 픽 ${m.pA.length}장`+(Bcfg?`<br>B 프리셋 활성`:``)+(anyMute()?`<br><span style="color:#e06666">뮤트 중</span>`:``);
 for(const d of DIALS){if(d.length==1)continue;const k=d[0];
  const el=document.getElementById("d_"+k);
  if(el)el.className="dial"+(A[k]!=DEF[k]?" mod":"")+((K2G[k]&&MUTE[K2G[k]])?" gmute":"");}
 window.scrollTo(0,sy0);
}

const HSPEC={
 sym_max:{f:r=>r.sy,dir:"below"},
 dev_hi:{f:r=>r.dv,band:["dev_lo","dev_hi"]},
 pt_max:{f:r=>Math.abs(r.pc),dir:"below"},
 pu_min:{f:r=>r.pu,dir:"above"},
 cs_min:{f:r=>r.cs,dir:"above"},
 mv_min:{f:r=>r.mv,dir:"above"},
 lt_min:{f:r=>r.lt,dir:"above"},
 df:{f:r=>r.hd,bandf:c=>c.df==0?null:(c.df>0?[c.df,1]:[0,1+c.df])},
 la_hi:{f:r=>r.ma,band:["la_lo","la_hi"]},
 le_hi:{f:r=>r.me,band:["le_lo","le_hi"]},
 ag_max:{f:r=>r.ag,dir:"below"},
 hh_max:{f:r=>r.hh,dir:"below"},
 sp_min:{f:r=>r.sp,dir:"above"},
 ex_max:{f:r=>r.ex,band:["ex_min","ex_max"]},
};
function drawDialHists(C,m){
 const byf={};C.rows.forEach(r=>byf[r.f]=r);
 for(const d of DIALS){
  if(d.length==1)continue;
  const [k,,mn,mx]=d, sp=HSPEC[k];
  if(!sp)continue;
  const cv=document.getElementById("h_"+k);
  if(!cv)continue;
  const ctx=cv.getContext("2d"), W=cv.width, H=cv.height;
  ctx.clearRect(0,0,W,H);
  const vals=[];
  for(const r of C.rows){const v=sp.f(r);if(v!=null&&isFinite(v))vals.push(v);}
  const NB=40, bins=new Array(NB).fill(0);
  for(const v of vals){let b=Math.floor((Math.min(mx,Math.max(mn,v))-mn)/(mx-mn)*NB);
   if(b>=NB)b=NB-1;if(b<0)b=0;bins[b]++;}
  const bm=Math.max(...bins,1), thr=A[k];
  const bf=sp.bandf?sp.bandf(A):undefined;
  const isBand=!!sp.band||(bf!==undefined&&bf!==null), bandOff=(sp.bandf&&bf===null);
  const blo=bf?bf[0]:(sp.band?A[sp.band[0]]:null), bhi=bf?bf[1]:(sp.band?A[sp.band[1]]:null);
  const tx=v=>4+(Math.min(mx,Math.max(mn,v))-mn)/(mx-mn)*(W-8);
  const inPass=v=>bandOff?true:(isBand?(v>=blo&&v<=bhi):(sp.dir=="below"?v<thr:v>=thr));
  for(let i=0;i<NB;i++){
   const x0=4+i*(W-8)/NB, bh=Math.round((H-13)*bins[i]/bm);
   const mid=mn+(i+0.5)*(mx-mn)/NB;
   ctx.fillStyle=inPass(mid)?"#6f9b6f":"#484848";
   ctx.fillRect(x0,H-3-bh,Math.max(1,(W-8)/NB-1),bh);
  }
  ctx.fillStyle="#fc6";
  if(bandOff){}
  else if(isBand){ctx.fillRect(tx(blo)-0.8,1,1.6,H-2);ctx.fillRect(tx(bhi)-0.8,1,1.6,H-2);}
  else ctx.fillRect(tx(thr)-0.8,1,1.6,H-2);
  ctx.fillStyle="#7ac";
  for(const f of m.pA){const r=byf[f];if(!r)continue;const v=sp.f(r);if(v==null||!isFinite(v))continue;
   const x=tx(v);ctx.beginPath();ctx.moveTo(x,H-2);ctx.lineTo(x-3,H-9);ctx.lineTo(x+3,H-9);ctx.closePath();ctx.fill();}
  let np=0;
  for(const v of vals){if(inPass(v))np++;}
  ctx.fillStyle="#bbb";ctx.font="9px sans-serif";ctx.textAlign="right";
  ctx.fillText(Math.round(100*np/Math.max(vals.length,1))+"%",W-3,9);
  ctx.textAlign="left";
 }
}

function drawTimeline(C,m){
 const cv=document.getElementById("tlc");
 if(!cv)return;
 const ctx=cv.getContext("2d"), W=cv.width, H=cv.height;
 ctx.clearRect(0,0,W,H);
 const fmin=0, fmax=Math.max(C.vf-1, 1);
 const X=f=>4+(f-fmin)/(fmax-fmin)*(W-8);
 ctx.fillStyle="rgba(80,170,180,0.22)";
 for(const r of C.rows) if(r.b) ctx.fillRect(X(r.f)-1,0,2.2,H-8);
 if(C.lseg){const LC={hard:"#d98a3d",flat:"#4aa7a0",back:"#9a6fd0",dark:"#5a6a7a",na:"#333"};
  for(const sg of C.lseg){ctx.fillStyle=LC[sg[2]]||"#333";
   ctx.fillRect(X(sg[0]),0,Math.max(1.5,X(sg[1])-X(sg[0])),5);}}
 for(const r of C.rows){
  const ff=firstFail(r,A);
  ctx.fillStyle=ff<0?SURV:SCOL[ff];
  if(ff<0) ctx.fillRect(X(r.f),12,1.7,H-20);
  else     ctx.fillRect(X(r.f),20,1.4,H-28);
 }
 ctx.fillStyle="#3a3a3a";
 for(const ab of C.absent) ctx.fillRect(X(ab[0]),H-7,Math.max(1.5,X(ab[1])-X(ab[0])+1.5),6);
 const GCOL={inv:"#a05244",det:"#5a78a0",frag:"#8a70b0"};
 for(const g of C.ghost){ctx.fillStyle=GCOL[g.k];ctx.fillRect(X(g.f),H-7,1.6,6);}
 ctx.fillStyle="#7ac";
 for(const f of m.pA) ctx.fillRect(X(f)-1.5,9,3,H-17);
 if(m.pB){ctx.strokeStyle="#ca7";ctx.setLineDash([3,2]);
  for(const f of m.pB) ctx.strokeRect(X(f)-2.5,9,5,H-18);
  ctx.setLineDash([]);}
 if(selF!=null){ctx.strokeStyle="#f90";ctx.strokeRect(X(selF)-2.5,1,5,H-2);}
 for(const r of C.rows){
  const g=GT[C.clip+":"+r.f];
  if(!g)continue;
  ctx.fillStyle=g=="pos"?"#4e4":"#e44";
  ctx.beginPath();ctx.arc(X(r.f),4.5,2.6,0,7);ctx.fill();
 }
 const tip=document.getElementById("tlTip");
 const GLBL={inv:"게이트-무효 (측정됨, valid 밖)",det:"미측정 — 검출만 (랜드마크 없음)",
             frag:"트랙 파편 (동일 인물 추정)"};
 const uni=C.rows.map(r=>({f:r.f,row:r})).concat(C.ghost.map(g=>({f:g.f,g:g})))
   .sort((a,b)=>a.f-b.f);
 const nearest=x=>{const fe=fmin+(x-4)/(W-8)*(fmax-fmin);
  let bi=0,bd=1e9;
  for(let i=0;i<uni.length;i++){const d=Math.abs(uni[i].f-fe);if(d<bd){bd=d;bi=i;}}
  return uni[bi];};
 cv.onmousemove=e=>{
  const rect=cv.getBoundingClientRect(), x=e.clientX-rect.left;
  const o=nearest(x);
  const gflag=GT[C.clip+":"+o.f], gs=gflag?` · GT:${gflag=="pos"?"＋":"−"}`:"";
  if(o.row){
   const r=o.row, ff=firstFail(r,A);
   const st=ff<0?`<span style="color:${SURV}">생존</span>`:`<span style="color:${SCOL[ff]}">${STAGES[ff]}에 걸러짐</span>`;
   const ss=stateScores(r.r);
   tip.innerHTML=(r.th?`<img src="${r.th}" loading="lazy">`:"")+
    `f${r.f} ${st}${gs}<br>ex${r.ex} pu${r.pu} sy${r.sy} dv${r.dv}<br>상태: 얼굴${ss[0].toFixed(2)} 빛${ss[1].toFixed(2)} 영상${ss[2].toFixed(2)} 왜곡${ss[3].toFixed(2)}`;
  }else{
   const g=o.g;
   tip.innerHTML=(g.th?`<img src="${g.th}" loading="lazy">`:"")+
    `f${g.f} <span style="color:${GCOL[g.k]}">${GLBL[g.k]}</span>${gs}<br>측정 신호 없음`;
  }
  tip.style.display="block";
  tip.style.left=Math.min(x+14,W-140)+"px";
  tip.style.top="46px";
 };
 cv.onmouseleave=()=>{tip.style.display="none";};
 cv.onclick=e=>{
  const rect=cv.getBoundingClientRect();
  const o=nearest(e.clientX-rect.left);
  if(e.shiftKey&&o.row){groundPose(C.clip,o.f);return;}
  selF=o.f;render();
 };
}

// ── 검사 패널(v0.10): 활성 상태의 분석 시각화 ─────────────────────────
function drawMask(r){   // v0.17: skin 마스크 재현 — hull 클립 + 20앵커 가우시안(σ=0.16 IOD)
 const cv=document.getElementById("mkc");
 if(!cv||!r.sk||!r.th)return;
 const ctx=cv.getContext("2d"), img=new Image();
 img.onload=()=>{
  ctx.drawImage(img,0,0,224,224);
  const o=r.sk.o.map(p=>[p[0]*224,p[1]*224]);
  const path=()=>{ctx.beginPath();ctx.moveTo(o[0][0],o[0][1]);
   for(const p of o.slice(1))ctx.lineTo(p[0],p[1]);ctx.closePath();};
  const iod=Math.hypot((r.sk.e[0][0]-r.sk.e[1][0])*224,(r.sk.e[0][1]-r.sk.e[1][1])*224);
  const sig=Math.max(0.16*iod,2);
  ctx.save();path();ctx.clip();
  ctx.globalCompositeOperation="lighter";
  for(const a of r.sk.a){
   const g=ctx.createRadialGradient(a[0]*224,a[1]*224,0,a[0]*224,a[1]*224,2.5*sig);
   g.addColorStop(0,"rgba(60,255,120,0.30)");g.addColorStop(1,"rgba(60,255,120,0)");
   ctx.fillStyle=g;ctx.fillRect(0,0,224,224);}
  ctx.restore();
  ctx.strokeStyle="rgba(120,220,140,0.85)";ctx.lineWidth=1;path();ctx.stroke();
 };
 img.src=r.th;}
function shEval(sh,x,y,z){
 return sh[0]*0.2821+sh[1]*0.4886*y+sh[2]*0.4886*z+sh[3]*0.4886*x
  +sh[4]*1.0925*x*y+sh[5]*1.0925*y*z+sh[6]*0.3154*(3*z*z-1)
  +sh[7]*1.0925*x*z+sh[8]*0.5462*(x*x-y*y);}
function renderInsp(C,m){
 const el=document.getElementById("insp");
 const r=C.rows.find(r=>r.f==selF);
 if(!r){el.innerHTML=`<div class="note">프레임을 클릭해 선택하세요.</div>`;return;}
 const ss=stateScores(r.r), pv=(C.pv||{})[String(r.f)];
 const gflag=GT[C.clip+":"+r.f]||"";
 const tabs=STAGES.map(s=>`<span class="itab${s==iMode?" cur":""}" onclick="iMode='${s}';render()">${s}</span>`).join("");
 let body="";
 if(iMode=="포즈"){
  body=`<canvas id="ovl" width="300" height="300" style="border:1px solid #444"></canvas>
   <div class="note">yaw dev ${r.dv}° · pitch ${r.pt==null?"--":r.pt}°(Δ${r.pc}) · roll ${r.rl==null?"--":r.rl}° · sym ${r.sy}</div>
   <div class="note">${pv?"랜드마크 오버레이 = 추정 검증":"오버레이는 픽 프레임 한정 (콘솔 온디맨드 확장 예정)"}</div>`;
 }else if(iMode=="표정·얼굴"){
  body=pv?`<div>${pv.bs.map(([nm,v])=>`<div class="ibar"><span class="nm">${nm}</span>
    <span class="bv" style="width:${Math.round(v*150)}px"></span> ${v}</div>`).join("")}</div>
    <div class="note">pupil ${r.pu} · ex(비 eyeLook 최대) ${r.ex}</div>`
   :`<div class="note">blendshape 상세는 픽 프레임 한정. pupil ${r.pu} · ex ${r.ex}</div>`;
 }else if(iMode=="빛"){
  body=`<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:flex-start">
    <div><canvas id="mkc" width="224" height="224" style="border:1px solid #444"></canvas>
     <div class="note" style="text-align:center">skin 마스크 (초록=가중, 선=타원 hull)</div></div>
   </div>
   <div style="display:flex;gap:10px;align-items:flex-start;margin-top:8px">
    <div><canvas id="shc" width="96" height="96" style="border:1px solid #444"></canvas>
     <div class="note" style="text-align:center">SH 조명 구면</div></div>
    <div><canvas id="fsc" width="96" height="96" style="border:1px solid #444"></canvas>
     <div class="note" style="text-align:center">얼굴-좌표 구면 ●=광방향</div></div></div>
   ${r.mi?`<div style="margin-top:8px">`+(pv&&pv.mls?`<canvas id="mlc" width="300" height="300" style="border:1px solid #444"></canvas>
    <div class="note">법선 화살 — 색=<b>cosθ 예측</b>(광원 향한 정도=산점 x축; 빨강=정면·파랑=등짐 · 픽 한정)</div>`
    :`<div class="note">법선 화살(썸네일 오버레이)은 픽 프레임 한정</div>`)+`
    <canvas id="mcc" width="300" height="300" style="border:1px solid #444;margin-top:4px"></canvas>
    <div class="note">정준(코-중심) 빛 지도 — 포즈 소거, 색=<b>관측 밝기</b>(열 척도, <b>클립-고정 ${C.mrange?C.mrange[0]+"~"+C.mrange[1]:"프레임"}</b> 기준=산점 y축) · 광방향 화살: <span style="color:#ffd24d"><b>노랑=mesh</b></span> vs <span style="color:#5ab4ff"><b>파랑=DPR</b></span> (az 소스 판정 대조)</div>
    <canvas id="msc" width="300" height="170" style="border:1px solid #444;margin-top:4px"></canvas>
    <div class="note">램버트 산점: cosθ vs 밝기 · 직선=피팅 ${r.mf?r.mf[0]+"+"+r.mf[1]+"·cosθ":"--"} (회색=피팅 미사용)</div></div>`
   :`<div class="note" style="margin-top:6px">mesh-LS 측정 없음 (이 프레임)</div>`}
   <div class="note"><b>lt ${r.lt==null?"--":r.lt}% = (휘도 ${r.lm==null?"--":r.lm}% + 색량 ${r.ch==null?"--":r.ch}%)/2</b> · raw 휘도 ${r.lmr==null?"--":r.lmr} / 색량 ${r.chr==null?"--":r.chr} <span style="color:#987">(pct 포화 대조용)</span><br>
    거칠기 hh ${r.hh==null?"--":r.hh}%<br>
    <b>정준 az ${r.la==null?"--":r.la}° · el ${r.le==null?"--":r.le}°</b> (0=정면 +=피사체좌/위) · 방향성 ldr ${r.ldr==null?"--":r.ldr}, ld ${r.ld==null?"--":r.ld}%${r.ldr!=null&&r.ldr<0.25?' <span style="color:#e88">⚠확산—방위 신뢰불가</span>':""}<br>
    <b>mesh-LS az ${r.ma==null?"--":r.ma}° · el ${r.me==null?"--":r.me}°</b> · 조명비 ≈ ${r.hd==null?"--":(r.hd>=0.95?"20:1+":(1/(1-r.hd)).toFixed(1)+":1")} (hd ${r.hd==null?"--":r.hd}) · R² ${r.r2==null?"--":r.r2} · 방향성 ${r.mr==null?"--":r.mr} · DPR 합의 ${r.ag==null?"--":r.ag+"°"}${(r.ag!=null&&r.ag>45)||(r.mr!=null&&r.mr<0.3)?' <span style="color:#e88">⚠방향 불신('+(r.ag!=null&&r.ag>45?"이중 자 불일치":"무방향")+')</span>':""}<br>
    클립 판별력 lf=${C.lf}</div>`;
 }else if(iMode=="영상"){
  body=(pv&&pv.lap)?`<img src="thumbs/${C.clip}/f${String(r.f).padStart(5,"0")}_lap.jpg" style="width:224px;border:1px solid #444">
    <div class="note">Laplacian 선명 히트맵 (밝음=엣지 살아있음)</div>
    <div class="note">선명 sp ${r.sp==null?"--":r.sp}%</div>`
   :`<div class="note">선명 히트맵은 픽 프레임 한정. sp ${r.sp==null?"--":r.sp}%</div>`;
 }else{ // 왜곡
  body=`<canvas id="csc" width="300" height="80" style="border:1px solid #444"></canvas>
   <div class="note">실선=cs(정체성 판독성 pct) · 점선=mv(입-가시 pct) · 주황=선택 프레임</div>
   <div class="note">cs ${r.cs==null?"--":r.cs}% · mv ${r.mv==null?"--":r.mv}% · norm rank ${(r.r[4]*100).toFixed(0)}%</div>`;
 }
 el.innerHTML=`<div class="rowlbl">검사 — f${r.f} ${r.b?"(boarding)":""}</div>
  <img id="inspImg" src="${r.th||""}" ${r.th?"":'style="opacity:.2"'}>
  <div class="note" style="margin:4px 0">상태점수: 얼굴 <b>${ss[0].toFixed(2)}</b> · 빛 <b>${ss[1].toFixed(2)}</b> · 영상 <b>${ss[2].toFixed(2)}</b> · 왜곡 <b>${ss[3].toFixed(2)}</b></div>
  <div class="gtbtn">GT: <button onclick="setGT('pos')" ${gflag=="pos"?'style="border-color:#5c5;color:#5c5"':''}>＋ 긍정</button>
   <button onclick="setGT('neg')" ${gflag=="neg"?'style="border-color:#e55;color:#e55"':''}>− 부정</button>
   <button onclick="setGT(null)">지움</button></div>
  <div class="itabs">${tabs}</div>${body}`;
 if(iMode=="포즈"){
  const cv=document.getElementById("ovl"), ctx=cv.getContext("2d");
  const img=new Image();
  img.onload=()=>{ctx.drawImage(img,0,0,300,300);
   if(pv){ctx.strokeStyle="rgba(80,255,120,0.8)";ctx.lineWidth=1;
    for(const [a,b] of WB.edges){const p=pv.lm[a],q=pv.lm[b];
     ctx.beginPath();ctx.moveTo(p[0]*300,p[1]*300);ctx.lineTo(q[0]*300,q[1]*300);ctx.stroke();}}};
  if(r.th)img.src=r.th;
 }else if(iMode=="빛"){
  drawMask(r);
 }
 if(iMode=="빛"&&r.sh){
  const cv=document.getElementById("shc"), ctx=cv.getContext("2d");
  const im=ctx.createImageData(96,96);
  let lo=1e9,hi=-1e9;const vals=new Float32Array(96*96).fill(NaN);
  for(let py=0;py<96;py++)for(let px=0;px<96;px++){
   const x=(px-48)/46,y=(py-48)/46,r2=x*x+y*y;
   if(r2>1)continue;
   const z=Math.sqrt(1-r2);
   const v=shEval(r.sh,x,-y,z);
   vals[py*96+px]=v;if(v<lo)lo=v;if(v>hi)hi=v;}
  for(let i=0;i<96*96;i++){const v=vals[i];
   const g=isNaN(v)?22:Math.round((v-lo)/(hi-lo+1e-9)*235+20);
   im.data[i*4]=g;im.data[i*4+1]=g;im.data[i*4+2]=g;im.data[i*4+3]=255;}
  ctx.putImageData(im,0,0);
  // v0.19 얼굴-좌표 구면: n_face → n_cam=R·n → DPR 슬롯(x=우, y=깊이안=−z_cam, z=상=y_cam)
  if(r.rm){
   const fc=document.getElementById("fsc"), f2=fc.getContext("2d");
   const fim=f2.createImageData(96,96);
   let flo=1e9,fhi=-1e9;const fvals=new Float32Array(96*96).fill(NaN);
   const R=r.rm;
   for(let py=0;py<96;py++)for(let px=0;px<96;px++){
    const x=(px-48)/46,yu=-(py-48)/46,r2=x*x+yu*yu;
    if(r2>1)continue;
    const z=Math.sqrt(1-r2);
    const cx=R[0]*x+R[1]*yu+R[2]*z, cy=R[3]*x+R[4]*yu+R[5]*z, cz=R[6]*x+R[7]*yu+R[8]*z;
    const v=shEval(r.sh,cx,-cz,cy);
    fvals[py*96+px]=v;if(v<flo)flo=v;if(v>fhi)fhi=v;}
   for(let i=0;i<96*96;i++){const v=fvals[i];
    const g=isNaN(v)?22:Math.round((v-flo)/(fhi-flo+1e-9)*235+20);
    fim.data[i*4]=g;fim.data[i*4+1]=g;fim.data[i*4+2]=g;fim.data[i*4+3]=255;}
   f2.putImageData(fim,0,0);
   if(r.la!=null&&r.le!=null){
    const azr=r.la*Math.PI/180, elr=r.le*Math.PI/180;
    const lx=Math.sin(azr)*Math.cos(elr), ly=Math.sin(elr), lz=Math.cos(azr)*Math.cos(elr);
    const dx=48+lx*44, dy=48-ly*44;
    f2.beginPath();f2.arc(dx,dy,4,0,7);
    if(lz>=0){f2.fillStyle="#ffd24d";f2.fill();}
    else{f2.strokeStyle="#e55";f2.lineWidth=2;f2.stroke();}}
  }
 }
 if(iMode=="빛"&&r.mi){   // v0.21 지도·산점=전 프레임(rows), 화살=픽 한정(pv)
  if(pv&&pv.mls){
   const M=pv.mls;
   const cA=document.getElementById("mlc");
   if(cA){const xA=cA.getContext("2d");const imA=new Image();
    imA.onload=()=>{xA.globalAlpha=0.42;xA.drawImage(imA,0,0,300,300);xA.globalAlpha=1;
     for(let k=0;k<M.p.length;k++){
      const x=M.p[k][0]*300,y=M.p[k][1]*300;
      xA.strokeStyle=`hsl(${(1-M.d[k])/2*240},85%,60%)`;xA.lineWidth=1.6;
      xA.beginPath();xA.moveTo(x,y);xA.lineTo(x+M.n[k][0]*15,y+M.n[k][1]*15);xA.stroke();}};
    if(r.th)imA.src=r.th;}}
  const vals=r.mi.filter(v=>v>=0);
  const lo=C.mrange?C.mrange[0]:Math.min(...vals), hi=C.mrange?C.mrange[1]:Math.max(...vals);   // 클립-고정 척도
  const cC=document.getElementById("mcc");
  if(cC&&C.mlay){const xC=cC.getContext("2d");
   xC.fillStyle="#1c1c1c";xC.fillRect(0,0,300,300);
   for(let k=0;k<r.mi.length;k++){if(r.mi[k]<0||r.mq[k]==0)continue;
    const x=150+C.mlay[k][0]*95,y=150-C.mlay[k][1]*95;
    const tb2=Math.max(0,Math.min(1,(r.mi[k]-lo)/(hi-lo+1e-9)));
    xC.fillStyle=`hsl(${(270+tb2*150)%360},88%,${30+tb2*38}%)`;   // 열 척도(보라→빨강→노랑)
    xC.beginPath();xC.arc(x,y,6.5,0,7);xC.fill();}
   const arw=(az,el,col,w)=>{const a2=az*Math.PI/180,e2=el*Math.PI/180;
    const dx=Math.sin(a2)*Math.cos(e2),dy=Math.sin(e2);
    xC.strokeStyle=col;xC.lineWidth=w;xC.beginPath();xC.moveTo(150,150);
    xC.lineTo(150+dx*95,150-dy*95);xC.stroke();
    xC.fillStyle=col;xC.beginPath();xC.arc(150+dx*95,150-dy*95,w+1,0,7);xC.fill();};
   if(r.la!=null&&r.le!=null)arw(r.la,r.le,"#5ab4ff",2);   // 파랑=DPR (az 판정 대조용)
   if(r.ma!=null&&r.me!=null)arw(r.ma,r.me,"#ffd24d",3);   // 노랑=mesh
   xC.fillStyle="#888";xC.font="10px sans-serif";
   xC.fillText("피사체 좌 →",232,292);xC.fillText("위 ↑",6,14);}
  const cS=document.getElementById("msc");
  if(cS&&r.mf){const xS=cS.getContext("2d");
   xS.fillStyle="#222";xS.fillRect(0,0,300,170);
   const px=d=>20+(d+1)/2*260, py=v=>158-Math.max(0,Math.min(1,(v-lo)/(hi-lo+1e-9)))*140;
   xS.strokeStyle="#ffd24d";xS.lineWidth=2;xS.beginPath();
   xS.moveTo(px(-1),py(r.mf[0]-r.mf[1]));xS.lineTo(px(1),py(r.mf[0]+r.mf[1]));xS.stroke();
   for(let k=0;k<r.mi.length;k++){if(r.mi[k]<0||r.md[k]==-127||r.mq[k]==0)continue;
    xS.fillStyle=r.mq[k]==2?"#fc6":"#666";
    xS.beginPath();xS.arc(px(r.md[k]/100),py(r.mi[k]),2.6,0,7);xS.fill();}
   xS.fillStyle="#999";xS.font="10px sans-serif";
   xS.fillText("cosθ→",260,166);xS.fillText("밝기↑",4,12);}
 }
 if(iMode=="왜곡"){
  const cv=document.getElementById("csc"), ctx=cv.getContext("2d");
  ctx.fillStyle="#141414";ctx.fillRect(0,0,300,80);
  const X=f=>4+f/Math.max(C.vf-1,1)*292;
  const plot=(get,style,dash)=>{ctx.strokeStyle=style;ctx.setLineDash(dash||[]);
   ctx.beginPath();let started=false;
   for(const q of C.rows){const v=get(q);if(v==null)continue;
    const x=X(q.f),y=76-v/100*72;
    if(!started){ctx.moveTo(x,y);started=true;}else ctx.lineTo(x,y);}
   ctx.stroke();ctx.setLineDash([]);};
  plot(q=>q.cs,"#b070d0");
  plot(q=>q.mv,"#55aacc",[3,2]);
  ctx.strokeStyle="#f90";ctx.beginPath();ctx.moveTo(X(r.f),2);ctx.lineTo(X(r.f),78);ctx.stroke();
 }
 // v0.13 미터 브리지: 선택 프레임의 상태점수 실시간 (탭 바 우측, 전 채널 상시)
 const mm={"표정·얼굴":ss[0],"빛":ss[1],"영상":ss[2],"왜곡":ss[3]};
 for(const g in mm){const el2=document.getElementById("mt_"+g);
  if(el2)el2.style.width=Math.round(mm[g]*100)+"%";}
 const mp=document.getElementById("mt_포즈");
 if(mp)mp.textContent=`포즈 dv${r.dv} sy${r.sy}`;
}
function onCell(e,clip,f){
 if(e&&e.shiftKey){groundPose(clip,f);return;}
 selF=f;render();}
function setGT(v){
 const C=WB.clips[cur];
 const k=C.clip+":"+selF;
 if(v)GT[k]=v;else delete GT[k];
 render();}
function groundPose(clip,f){
 const C=WB.clips.find(c=>c.clip==clip);
 const r=C&&C.rows.find(r=>r.f==f);
 if(!r)return;
 A.sym_max=Math.min(2.0,Math.round((Math.floor(r.sy/0.05)+1)*5)/100);
 A.dev_lo=Math.min(A.dev_lo,Math.max(-90,Math.floor(r.dv)-1));
 A.dev_hi=Math.max(A.dev_hi,Math.min(90,Math.floor(r.dv)+1));
 if(A.pt_max<99)A.pt_max=Math.max(A.pt_max,Math.min(99,Math.floor(Math.abs(r.pc))+1));
 buildPanel();render();}
function snapshotB(){Bcfg={...A};render();}
function clearB(){Bcfg=null;render();}
function resetA(){A={...DEF};buildPanel();render();}
function exportGT(){
 const lines=Object.entries(GT).map(([k,v])=>{const i=k.indexOf(":");
  return JSON.stringify({schema:"momentscan.workbench-gt/v0",clip:k.slice(0,i),frame:+k.slice(i+1),
    role:"center",flag:v,corpus:"output/l2",ts:new Date().toISOString()});});
 const blob=new Blob([lines.join("\\n")+"\\n"],{type:"application/jsonl"});
 const a=document.createElement("a");a.href=URL.createObjectURL(blob);
 a.download="workbench_gt.jsonl";a.click();}
function importGT(inp){const fr=new FileReader();fr.onload=()=>{
 fr.result.split("\\n").filter(x=>x.trim()).forEach(l=>{try{const o=JSON.parse(l);
  if(o.flag)GT[o.clip+":"+o.frame]=o.flag;}catch(e){}});render();};
 fr.readAsText(inp.files[0]);}
const D2META={};for(const d of DIALS){if(d.length>1)D2META[d[0]]=d;}
const STRIPS=[   // v0.14: 채널 → 세부 채널(트리) → 다이얼
 {g:"포즈",fader:null,subs:[
   {t:"보이는-정면 (뺨 대칭)",dials:["sym_max"]},
   {t:"yaw 밴드 (좌− / 우+)",dials:["dev_lo","dev_hi"]},
   {t:"pitch (클립상대)",dials:["pt_max"]}]},
 {g:"표정·얼굴",fader:"w_face",subs:[
   {t:"눈동자 가시",dials:["pu_min"]},
   {t:"표정 밴드",dials:["ex_min","ex_max"]}]},
 {g:"빛",fader:"w_light",subs:[
   {t:"① 세기 (조도·생동 lum×chroma)",dials:["lt_min"]},
   {t:"② 방향 — 존 선택 (본선=mesh-LS·대조=DPR)",dials:[],zones:1,adv:["la_lo","la_hi","le_lo","le_hi","ag_max"]},
   {t:"③ 확산 — 조명비 key:fill lighting ratio (낮음=소프트·높음=하드)",dials:["df"]},
   {t:"④ 그림자 (거칠기)",dials:["hh_max"]}]},
 {g:"영상",fader:"w_image",subs:[
   {t:"선명 (face blur)",dials:["sp_min"]}]},
 {g:"왜곡",fader:"w_distort",subs:[
   {t:"정체성 판독성 (cos_self)",dials:["cs_min"]},
   {t:"입-가시 (가림)",dials:["mv_min"]}]},
];
const MCOL={"표정·얼굴":"#e08aa8","빛":"#d8c455","영상":"#55aacc","왜곡":"#b070d0"};
let deckTab="포즈";
function setTab(g){deckTab=g;if(STAGES.includes(g))iMode=g;buildPanel();render();}
function setZone(z){   // v0.19 사진 문법 존 프리셋 (정준 az/el 다이얼 일괄)
 const Z={remA:{la_lo:20,la_hi:60,le_lo:10,le_hi:55,df:0,lt_min:60,ag_max:45},
          remB:{la_lo:-60,la_hi:-20,le_lo:10,le_hi:55,df:0,lt_min:60,ag_max:45},
          bfly:{la_lo:-15,la_hi:15,le_lo:20,le_hi:60,df:0,lt_min:60,ag_max:45},
          front:{la_lo:-30,la_hi:30,le_lo:10,le_hi:55,df:0,lt_min:75,ag_max:45},
          zoff:{la_lo:-180,la_hi:180,le_lo:-90,le_hi:90,df:0,lt_min:0,ag_max:180}};
 Object.assign(A,Z[z]);iMode="빛";buildPanel();render();}
function dialHTML(k){
 const [,lbl,mn,mx,stp]=D2META[k];
 return `<div class="dial" id="d_${k}"><label>${lbl}<span id="v_${k}">${A[k]}</span></label>
  <input type="range" min="${mn}" max="${mx}" step="${stp}" value="${A[k]}"
   oninput="A['${k}']=+this.value;document.getElementById('v_${k}').textContent=this.value;
    if(K2G['${k}']&&STAGES.includes(K2G['${k}']))iMode=K2G['${k}'];scheduleRender()">`+
  (HSPEC[k]?`<canvas class="dh" id="h_${k}" width="300" height="34" style="width:100%"></canvas>`:``)+`</div>`;}
function buildPanel(){   // v0.13: 채널 탭 데크 + 미터 브리지
 const p=document.getElementById("deck");
 let tabs=STRIPS.map(S=>{
  const g=S.g;
  const isSolo=!MUTE[g]&&STAGES.every(s=>s==g||MUTE[s]);
  return `<span class="dtab${deckTab==g?" cur":""}${MUTE[g]?" dm":""}" onclick="setTab('${g}')">${g}
   <span class="sm s${isSolo?" on":""}" onclick="event.stopPropagation();soloG('${g}')">S</span>
   <span class="sm m${MUTE[g]?" on":""}" onclick="event.stopPropagation();muteG('${g}')">M</span></span>`;
 }).join("")+`<span class="dtab${deckTab=="마스터"?" cur":""}" onclick="setTab('마스터')" style="color:#cb8">마스터</span>`;
 const bridge=`<div id="bridge">`+STAGES.slice(1).map(g=>
  `<span class="bm">${g}<span class="bar"><i id="mt_${g}" style="width:0;background:${MCOL[g]}"></i></span></span>`).join("")+
  `<span class="bm" id="mt_포즈" style="color:#c98a4a"></span></div>`;
 let body="";
 if(deckTab=="마스터"){
  body=`<div class="chanview"><div class="body">`+dialHTML("gap_min")+
   `<label style="font-size:12px;color:#bbb;display:block;margin:8px 0"><input type="checkbox" ${ATT?"checked":""}
     onchange="ATT=this.checked;render()"> 빛 분산-감쇠(lf)</label></div>
   <div class="fblock"><div class="note"><span id="mstat"></span><br><br>
    <b>S</b>=솔로(1층 검증) · <b>M</b>=뮤트(게이트 해제+가중 0)<br>
    다이얼 터치 → 우측 검사 뷰 전환 · 주황 •=기본값 이탈<br><br>
    <b>약어 사전</b> (방향=얼굴-기준 정준 좌표)<br>
    <b>mesh-LS</b>=랜드마크 메쉬 법선×<b>L</b>east <b>S</b>quares(최소제곱) 램버트 역산 — 물리 자 / <b>DPR</b>=학습 조명 추정기<br>
    <b>az</b> 방위각(0=정면 +=피사체좌 ±180=후방) · <b>el</b> 고도각(+=위)<br>
    <b>ma/me</b>=mesh-LS az/el(본선) · <b>la/le</b>=DPR az/el(대조)<br>
    <b>ag</b> 두 자 합의각 · <b>mr</b> mesh 방향성 · <b>ld/ldr</b> DPR 방향성 pct/raw<br>
    <b>lt</b> 조도·생동=(lm 휘도+ch 색량)/2 · <b>lmr/chr</b> raw · <b>hd</b> 확산=1−(그림자면/밝은면) → 조명비 key:fill ≈ 1/(1−hd):1 (2:1=소프트·8:1=하드, 사진 표준 용어=lighting ratio) · <b>hh</b> 거칠기 · <b>lf</b> 클립 빛 판별력<br>
    <b>dv</b> yaw 편차 · <b>sy</b> 뺨 대칭 · <b>pt/pc</b> pitch/클립Δ · <b>rl</b> roll · <b>pu</b> 눈동자 가시<br>
    <b>ex</b> 표정 강도 · <b>sp</b> 선명 · <b>cs</b> 정체성 판독성 · <b>mv</b> 입 가시</div></div></div>`;
 }else{
  const S=STRIPS.find(s=>s.g==deckTab);
  body=`<div class="chanview${MUTE[S.g]?" gmuted":""}"><div class="body">`+
   S.subs.map(sub=>`<div class="subch"><div class="subttl">${sub.t}</div>`+
    (sub.zones?`<div style="margin:2px 0 5px">`+[["remA","렘브란트 az+"],["remB","렘브란트 az−"],
      ["bfly","버터플라이"],["front","프론트(밝은 정면광)"],["zoff","존 해제"]].map(([z,l])=>
      `<button onclick="setZone('${z}')" style="font-size:10px;background:#333;color:#d8c455;border:1px solid #555;border-radius:3px;margin-right:4px;cursor:pointer;padding:1px 6px">${l}</button>`).join("")+
      `<div style="font-size:10px;color:#987;margin-top:2px">존=방향성 클립 전용 — 헤더 lf·⚠확산 배지 확인</div></div>`:"")+
    sub.dials.map(dialHTML).join("")+
    (sub.adv?`<details style="margin-top:4px"><summary style="font-size:11px;color:#987;cursor:pointer">고급 — 밴드 직접 조작</summary>`+sub.adv.map(dialHTML).join("")+`</details>`:"")+`</div>`).join("")+`</div><div class="fblock">`+
   (S.fader?`<div class="fader"><span class="mlbl">가중 페이더</span>
     <input type="range" min="0" max="0.8" step="0.05" value="${A[S.fader]}"
      oninput="A['${S.fader}']=+this.value;document.getElementById('fv_${S.fader}').textContent=this.value;iMode='${S.g}';scheduleRender()">
     <span class="fv" id="fv_${S.fader}">${A[S.fader]}</span></div>`
    :`<div class="note" style="font-size:11px">밴드=쿼리 (점수 없음)</div>`)+
   `</div></div>`;
 }
 p.innerHTML=`<div id="dtabs">${tabs}</div>${bridge}${body}`;}
document.addEventListener("keydown",e=>{
 if(e.target.tagName=="INPUT")return;
 if(e.key=="ArrowRight"){cur=(cur+1)%WB.clips.length;selF=null;render();}
 if(e.key=="ArrowLeft"){cur=(cur+WB.clips.length-1)%WB.clips.length;selF=null;render();}});
buildPanel();render();
</script></body></html>
"""

if __name__ == "__main__":
    out_root = Path("output/l2")
    dst = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("workbench_out")
    wb = dst
    wb.mkdir(parents=True, exist_ok=True)
    clips = []
    for clip in CLIPS:
        try:
            clips.append(build_clip(clip, out_root, wb))
            print(f"{clip}: rows={clips[-1]['n']} selftest={clips[-1]['selftest']}")
        except Exception as e:
            print(f"{clip}: FAIL {type(e).__name__}: {e}")
    (wb / "data.js").write_text(
        "const WB=" + json.dumps({"clips": clips, "edges": EDGES}, ensure_ascii=False) + ";",
        encoding="utf-8")
    (wb / "workbench.html").write_text(HTML, encoding="utf-8")
    print("workbench:", wb / "workbench.html")

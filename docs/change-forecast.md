# 변화 예측·비목표 원장 (change forecast — SRS의 살아있는 절)

> **Parnas 분해 기준의 상설 입력** (user 발제 2026-07-16: "무엇이 변할 것인가와
> 무엇을 안 할 것인가를 따로 정리하지 않았었다 — SRS가 그걸 요구한 이유를
> 몸소 깨달았다"). 규율: **벽(패키지·인터페이스·계약)을 세우는 모든 트랙은
> 이 원장의 축을 인용한다** — 인용할 축이 없으면 그 벽은 서브루틴 묶음이다.
> 갱신 = 결정이 생길 때마다. 시점 심사 = docs/architecture-review-2026-07-16.md
> (판정 근거 앵커는 그쪽).

## ① 변화 예측 원장 — 6개월 시계 (2026-07-16 기준)

확률: ●확정/높음 ◐중간 ○장기·조건부. 판정: 숨겨짐/샘/노출(심사보고 §2).

| 축 | 무엇이 바뀌나 | 확률 | 은닉처(오늘) | 판정 | 처방 |
|---|---|---|---|---|---|
| A | 회사 연동 방언 (resultPath 매핑·인바운드 인증·관측·transport) | ● | serve/ 한 곳 | 숨겨짐 | 회신 도착 시 어댑터 내 수술 |
| B | **정책 임계 ~60개 + fps** (C9 — 시설/카메라/기구 의존값 전부) | ◐→● | **15파일 산개** (지도=preset-inventory.md) | **노출(최대)** | **C9 preset 실체화 — likeness ⑦이 첫 지불자** |
| C | 모델 백엔드 (headpose 융합·SegFormer→FashionCLIP·features A/B·MARLIN 승격) | ◐ | 어댑터/포트 각 1점 (MARLIN만 select state 계약과 결합) | 숨겨짐 (C4만 샘) | features 포트=계약만 완성, 첫 실스왑 때 실증 |
| D | **highlight WHEN/WHICH 재편** (E1 후 1순위 연구) | ● | select 정본+**highlight.py 미러 복제**+lang 미통합 = 3파일 | **노출** | **신규: WHEN 공식 단일홈** — 연구 착수 전 필수 |
| E | 시설/기구 확장 (race981→타 어트랙션: phase 모델·좌석 규칙·기대 문장) | ○ | B와 동일 산개 | 노출 | C9 합류 |
| F | 배포 형태 (docker→k8s, graceful, MAX_INFLIGHT) | ◐ | serve/ (JobRunner 수명주기만 걸침) | 숨겨짐~샘 | 배포 시점 |
| G | visualstack 졸업 (stash·serve·pipeline 선언·media) | ●방향 | 패키지 절단면 물리화 완료(T1~T5) | 숨겨짐 | R15(C12 enforcement) 잔여 |
| H | likeness 캘리·gain·phase 조건화 | ● | C11 계약 절단면 / ⑦은 2파일+C9 자리 | 숨겨짐~샘 | likeness 트랙 |
| I | 배치→라이브 전환 | ○ | 클립-스코프 가정이 **알고리즘 정의에 내재** (stitch 전역병합·클립분포 rarity·클립 baseline) | 노출(승인) | **숨기지 않는다** — 은닉 불가 축, 시점 오면 재작성 (visualpath topic-flow 예약석) |
| J | 스토리지 형태 (S3 이행) | ◐ | 쓰기=stash 1곳 ✓ / 읽기 우회 14곳+무소유 산출물 4족 | **샘(악화 중)** | fold-store = 마찰 낮추는 레지스트리 + 무소유 4족 편입 명시 |
| K | gates 독립·제품 closure | ● | gate_trace 생산이 portrait 안 | 노출 | **R10/R11 = 바로 다음 트랙** |
| L | 계약 진화 (C1/C11 semver) | ◐ | 도장 2곳, 검증 기계 0 | 샘 | R6 msgspec |

**구조적 판독**: 외부-강제 축(A·F·G·H)은 전부 숨겨졌고 내부-연구 축(B·D·K·I)일수록
노출 — 몰튼 정책의 의도적 이연이었으나 **B와 D는 6개월 시계 안에 만기가 왔다**.
다음 투자는 파일 이사가 아니라 **정책(상수·공식)의 이주**다.

## ② 비목표 원장 — 안 하는 것과 재개 조건

| 안 하는 것 | 왜 (근거 결정/사고) | 재개 조건 |
|---|---|---|
| cross-visit 사람 메모리 (personmemory 부활) | 연동=무상태 per-clip으로 충분; cross-visit=제품 가정이지 기술 기반 아님 (2026-06-24 결정) | cross-visit이 제품 요구로 실재할 때 |
| 미니도구 분리·utils/common 서랍 | commons-audit 공집합 판정(레포-간 중복 0)·visualbind 전례(소비자 0층) | 두 번째 **코드**-소비자 실존 |
| visualserve/visualstash 조기 졸업 | "어떤 층도 소비자보다 먼저 짓지 않는다" — 로드맵 게이트 | visualstash=단계2 / visualserve=momentgen 디스패치 확정 or 알파 안정 |
| 네이티브 스테이지 크래시 격리 (R14 사다리③·R16) | GPU 웜업·프로세스 비용; record-and-continue가 파이썬 예외 커버 | run.json 실패 통계에 **네이티브 크래시 관측** (철학이 아니라 실측이 트리거) · k8s 결정과 묶어 재계산 |
| Kafka consumer·오토스케일·워커풀 | C1 transport-agnostic — 어댑터만 추가하면 됨 | 회사 transport 확정 |
| msgq/실시간 IPC 기계 (openpilot식) | AK-47 위반 — 배치에 불요 (2026-06-24) | 라이브 모드(축 I) 착수 |
| 축 I(라이브)의 선제 추상화 | 은닉 불가 축 — 추상화 비용만 내고 보호 못 받음 (심사 §5-5) | 라이브가 로드맵 확정 시 재작성으로 |
| 자체 통합 운영 대시보드 | 회사 Grafana(Zabbix+Loki) 합류 결정 (2026-07-06) | — |
| 전면 리포맷·소급 스타일 적용 | diff 오염 (R9·code-style 명시) | 없음 (영구) |
| 원격 shutdown 엔드포인트 | 네트워크에서 끌 수 있는 서비스=footgun (2026-07-06) | 없음 |
| Jetson Orin NX 활용 | momentscan 완성 우선 (user 2026-07-14) | 완성 후 — 3단 평가 기록 있음 |
| portrait 미학 랭킹 (0축) | 미학=주관 0축, 집합-내=쿼리-조건부 평평 (2026-06-19 교정) | 제품 결정 (taste는 사람 라벨 자리) |
| E1 라벨의 학습 사용 | eval-only 원칙 (eval-plan) | 별도 결정 (QVHighlights 방식 재사용은 예약) |
| 2곳-중복의 홈 신설 | 과잉-작업 경계 (commons-audit §3) | 홈이 이미 생기면 2곳도 접는다 |

> ⚠제품-스코프 비목표(위 표의 아래쪽 일부)는 우산(p981) 레벨 결정과 겹친다 —
> 상위 정본 위치는 user와 논의 중 (2026-07-16).

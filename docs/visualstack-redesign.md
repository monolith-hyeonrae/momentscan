# visualstack 전면 재설계 제안 — "비전 에이전트의 Rails"

작성 위치가 momentscan인 이유(user, 2026-07-07): **momentscan이 첫 실사용 사례**이고,
Rails가 Basecamp에서 추출됐듯 visualstack v2는 추상 설계가 아니라 **작동하는 소비자
로부터의 추출**이어야 한다. 성공 척도 = **momentscan이 간략해질수록 visualstack의
승리**. 레거시(portrait981)가 소비자 없는 과-아키텍처로 무너진 역사가 이 방법론의
근거다.

## 0. 비전과 시장

**visualstack = 현대화된 실시간 비전 에이전트의 미들웨어/플랫폼.**
상상 소비자: momentscan-v1…v10 · 트랙캠 통과-차량 추적 · OCR 번호판 체크인 ·
실시간 얼굴 인식 · LBE 스트리밍. 공통점: *미디어 소스*(파일/카메라)에서 *분석
모듈*(도메인 전문가의 것)을 거쳐 *제품*(판정/산출물/액션)으로 — 인프라는 전부 같고
가운데만 다르다. **채용 경쟁력**: 인프라 지식 없는 ML/CV 전문가가 Module 하나를
구현하면 실행·격리·GPU 계량·관측 대시보드·서비스 면·멱등성을 공짜로 얻는다.

**프로덕션 카메라가 가치를 극대화하는 지점**(트랙캠 계획): 일반 비전 카메라와 달리
로그 프로파일·컬러 그레이딩·타임코드가 일급 개념 — 이건 애플리케이션이 아니라
**미디어 기판의 책임**이다(§2 visualbase).

## 1. momentscan이 증명/재발명한 것 (추출 원료 목록)

| momentscan에서 | 정체 | 졸업처 |
|---|---|---|
| visualbus FileSource·Sink·Draw·BBox·timestamp | 하중 검증된 미디어 API | visualbase |
| visualbus structured_log + Grafana/Loki/promtail 자산 + GPU beat | 관측 3층 | visualscope |
| visualbus control(UDS RPC)+daemon | 제어면 | visualbind(역할 확정) |
| analyzers.py(선언 카탈로그)+RUNNERS+pipeline.py(topo·skip)+freshness.py | **artifact-대수 오케스트레이션의 재발명** | visualpath ArtifactNode |
| stash.py(컬럼맵·dtype 검증·아티팩트 홈)+provenance+tier(R12) | 아티팩트 영속 | visualstash |
| service.py(Job/Result·transport-agnostic·멱등)+eureka.py | 서비스 면 | visualserve |
| verify registry/graph/replay 패턴 | 계약 drift 가드 | 각 층이 자기 가드 동봉 |
| ImportError→degrade·정직 실패 기록·측정-먼저 | 문화 | 설계 원칙 |

## 2. 목표 아키텍처 (6층)

```
L0 visualbase   미디어 기판: Source 포트(File/Camera/GenICam·NDI·SDI/RTSP),
                Sink, Frame(컬러스페이스 태그·타임코드·메타 전파), 컬러 파이프
                (log→LUT), 기하 규약(BBox), 시간 규약
                ★프록시 워크플로: "분석은 프록시, 배송은 마스터" (영상 제작의
                proxy/master 개념 이식 — momentscan L13 교훈의 일반화)
L1 visualbus    수송: topics·pub/sub·signal/trigger·backpressure (인프로세스 우선,
                IPC/msgq는 소비자가 요구할 때)
L2 visualstash  영속: 아티팩트 스키마(컬럼·dtype)·tier(substrate/product/surface/ops)·
                provenance·retention·freshness 지문
L3 visualpath   오케스트레이션: 두 노드 대수를 한 선언 공간에 —
                StreamModule(topic-flow, 기존) + ArtifactNode(artifact-flow, R16)
                resolver(topo·closure 질의)·SkipPolicy 포트·isolation(서브프로세스)·
                스케줄러(realtime loop | batch)
L4 visualserve  제품 면: Job/Result 계약·HTTP/Kafka 어댑터·레지스트리(Eureka) 어댑터·
                멱등성·health/GPU beat
L5 visualscope  관측: structured_log·run trace·대시보드 자산 자동 프로비저닝·HUD
```
의존은 아래→위 금지(단방향), 도메인은 어느 층도 임포트하지 않고 **포트에 부착**
(C12 규칙 3 — 포트-어댑터 역전). 각 층은 자기 계약의 drift 가드를 동봉(enforcement
가 아키텍처보다 중요 — openpilot 교훈).

## 3. DX — Rails 순간 (convention over configuration)

```python
# 번호판 체크인 시스템 — ML 전문가가 쓰는 전부
from visualstack import App, Camera

app = App("platecheck", preset="parking-kr")
app.source(Camera("genicam://cam0", color="clog3->rec709.cube"))

@app.module(consumes="frames", produces="plates")     # StreamModule
class PlateOCR:
    def on_frame(self, topic, frame, bus): ...

@app.artifact(consumes=["plates"], produces="checkins.parquet", tier="product")
def checkin(stash, clip_id, ctx): ...                 # ArtifactNode

app.run()          # 실시간 | visualstack run video.mp4 (배치, resumable)
                   # visualstack serve (Job/Result·Eureka·대시보드 포함)
```
스캐폴딩: `visualstack new <app>` / `visualstack g module <Name>` / `visualstack doctor`.
momentscan-v2는 이 형태로: 선언(M01~M12·V·P)+모듈 본체+preset+렌더러만 남는다 —
현행 11.4k LOC 중 pipeline/freshness/stash-기계/service/eureka/daemon/관측자산
≈ **2.5~3k LOC가 기판으로 졸업**, 이후의 momentscan-v3…v10과 트랙캠·OCR이 그걸
공짜로 받는다.

## 4. 이행 로드맵 (실소비자 동반 — 단계마다 momentscan 테스트 그물 위에서)

| 단계 | 내용 | 게이트 |
|---|---|---|
| 0 | C12 경계+R15 enforcement (완료/계획) — 추출 원료의 정확한 재고 | — |
| 1 | **R16** ArtifactNode 포트+resolver closure+SkipPolicy / **R17** momentscan 이관 | R2 특성화 그물, R5 순수함수 |
| 2 | visualstash 추출(스키마=데이터 선언, tier=R12 결과 수용) | 이관 후 replay 0드리프트 |
| 3 | visualserve/visualscope 추출 | 알파 안정 후(회사 연동 무중단) |
| 4 | visualbase 분리+프로 카메라 소스(GenICam·컬러 파이프·프록시/마스터) | 트랙캠 프로젝트 착수가 지불 |
| 5 | visualbus IPC·실시간 스케줄러 강화 | LBE/스트리밍 소비자가 지불 |

**원칙: 어떤 층도 소비자보다 먼저 짓지 않는다** — "두 번째 소비자가 지불한다"
(C9 preset 원칙의 기판판). 단계마다 momentscan은 계약(C1·C11) 불변으로 돌아간다.

## 5. 설계 원칙 (momentscan에서 검증된 것의 승격)

1. **추출이지 발명이 아니다** — Rails=Basecamp 추출; 층의 API는 momentscan 사용
   표면에서 시작한다.
2. **AK-47 Layer 0** — 각 층은 stdlib-근접 최소로 시작, 소비자가 요구를 지불할 때
   자란다.
3. **enforcement 동봉** — 계약마다 drift 테스트가 같은 패키지에 산다.
4. **정직한 열화** — 의존 결측=선언된 degrade+로그, 침묵 금지.
5. **한 선언 공간** — legibility와 observability는 같은 그래프에 매단다(모든 노드는
   선언되고, 선언된 것만 관측된다).
6. **프록시/마스터 분리** — 분석 스트림과 배송 품질은 다른 요구; 기판이 둘 다
   1급으로 안다.
7. **frozen substrate / molten domain** — 도메인(분석기·preset·제품)은 앱에 남고
   뜨겁게 변한다; 기판은 얼어 있고 semver·`__all__`·deprecation으로 말한다.

## 6. 리스크와 정직한 한계

- **프레임워크 함정**(portrait981의 사인): 로드맵 게이트가 방어 — 소비자 없는 층
  건설 금지.
- **동시 개발 대역폭**(그동안 방치된 이유): 단계 1(R16/R17)만으로도 L12·R11·R14가
  구조로 풀리므로, **단계 1이 최소 투자·최대 회수 지점**. 이후 단계는 각각 독립
  결정.
- visualbind의 현 역할 불명 — 재설계에서 제어면(control+fleet CLI)으로 확정하거나
  통폐합 결정 필요.
- 알파 기간 중 이관 리스크: R2 특성화+replay가 그물; 회사-대면 계약(C1)은 어떤
  단계에서도 불변.

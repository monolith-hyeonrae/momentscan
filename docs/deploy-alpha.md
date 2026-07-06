# 알파 배포 런북 — serve(HTTP) · Eureka · S3

> 계약 = [contracts.md C1 v1](contracts.md) · **API 명세(회사 공유용) =
> [api/openapi.yaml](api/openapi.yaml)** · 계약 회귀 테스트 = `momentscan api-check`
> (인프로세스, GPU/Eureka 불필요 — 명세와 서버의 일치를 13항목 검증).
> 실행기 = `momentscan server start` (`service.py` — 외부 HTTP 면; `daemon.py`의
> UDS 제어면과 별개).

## 1. 기동 (로컬 서버 / AWS 서버 동일)

```bash
momentscan server start --port 8080 --out /data/stash --fps 6 \
    --products likeness \                        # 단계 배포 스위치 (Phase 1 = likeness만)
    --eureka http://<회사-eureka>:8761/eureka \   # 주면 등록, 빼면 등록 없이 HTTP만
    --advertise-host <이 노드의 IP>               # 생략 = 자동 감지 (아래 §3 주의)
```

동작: FIFO 단일 워커(GPU 직렬화) · warm detect 캐시(첫 잡만 모델 로드) ·
멱등(clip_id 재요청 = 재계산 없이 기존 경로 반환, `result.json`이 근거).
**상태 확인 = `momentscan server status`** — 두 서버 면(UDS 데몬 + HTTP)을 다 점검:
serve는 기동 시 `~/.cache/momentscan/http-{port}.json` 런타임 레코드를 남기고
status가 그걸로 발견해 `/health`를 찔러본다 (무응답 기록 = ⚠ 죽은 프로세스 표시).

**종료 = `momentscan server stop [--port N]`** — 레코드의 pid로 SIGTERM.
Ctrl-C(포그라운드)·`kill <pid>`·systemd stop 전부 같은 우아한 경로: **유레카 즉시
해지**(90s 축출 대기 없음)·레코드 삭제·`service.stopped` 로그(대시보드에 종료 흔적).
`kill -9`만 잔재를 남기고, 그건 status ⚠가 잡아 rm 힌트를 준다. 원격 shutdown
엔드포인트는 **의도적으로 없음** — 네트워크에서 끌 수 있는 서비스는 footgun.

```
POST /jobs        {clip_id, source_uri, output_uri?, fps?, products?, subject_query?}
                  → 202 {status, output_prefix, poll} | 200 (이미 완료 = Result)
GET  /jobs/{id}   → queued|running / Result / failed
GET  /health      → {"status":"UP", node, gpu, queue, …}    (Eureka healthCheckUrl)
GET  /info        → 앱 메타                                  (Eureka statusPageUrl)
GET  /docs        → Swagger UI (FastAPI /docs 상당 — 정본 openapi.yaml 렌더;
GET  /openapi.yaml   UI의 JS는 unpkg CDN이라 오프라인이면 yaml 원문으로)
```

## 2. Eureka — 처음이라면 이것만 알면 된다

Eureka = **전화번호부**다. 등록은 "MOMENTSCAN이라는 이름의 인스턴스가
`10.x.x.x:8080`에 살아 있다"를 선언하는 것이 전부고, **실제 트래픽은 Eureka를
거치지 않는다** — 회사 게이트웨이/서비스가 번호부에서 주소를 찾아 우리 HTTP로
직접 온다. 수명주기 4단 (전부 평범한 HTTP, `eureka.py`가 자동 수행):

| 단계 | 호출 | 주기 | 의미 |
|---|---|---|---|
| 등록 | `POST /eureka/apps/MOMENTSCAN` | 기동 시 | 번호부에 이름:주소 기입 (status UP) |
| 갱신 | `PUT /eureka/apps/MOMENTSCAN/{id}` | 30s | "아직 살아있음" heartbeat (렌트 갱신) |
| 축출 | (없음 — 서버가 함) | 90s 무응답 시 | 죽은 노드를 번호부에서 자동 제거 |
| 해지 | `DELETE /eureka/apps/MOMENTSCAN/{id}` | 종료 시 | 정상 종료 = 즉시 제거 (90s 대기 없음) |

- heartbeat이 404를 받으면(Eureka 재시작/축출) 자동 재등록한다.
- 회사 측 소비: Spring 서비스는 `http://MOMENTSCAN/jobs`처럼 **앱 이름으로**
  호출(클라이언트-사이드 LB가 번호부에서 인스턴스 해석). 노드를 늘리면 같은
  이름으로 여러 인스턴스가 등록되고 호출이 분산된다 — 우리 쪽 코드 변경 없음.
- **회사에 물어볼 것 3가지**: ① Eureka 서버 URL(예: `http://host:8761/eureka`)
  ② 앱 네이밍 규칙(기본 `momentscan`, `--app-name`으로 변경) ③ 우리 노드
  포트로 인바운드가 열려 있는지 (등록해도 게이트웨이가 못 들어오면 무의미).

## 3. AWS 노드 추가 사항

- `uv pip install boto3` (s3:// 반입/반출용 — doctor가 ○ 선택 항목으로 점검).
- IAM: source 버킷 `GetObject` + output 버킷 `PutObject`.
- 보안그룹: 서비스 포트 인바운드(회사망/게이트웨이 대역) 허용.
- `--advertise-host`: EC2에서 자동 감지는 **사설 IP**를 잡는다 — 회사망과 VPC가
  피어링돼 있으면 그대로 맞고, 아니면 도달 가능한 주소를 명시할 것.
  (Eureka에 등록된 주소로 게이트웨이가 "직접" 오기 때문에 이 값이 곧 라우팅 주소다.)

## 4. 입출력 규약 (C1 요약)

- `source_uri`: `s3://bucket/key.mp4` | `/local/path.mp4` | `file://…` —
  s3는 stash의 `source_cache/`로 내려받아 처리.
- `output_uri` 생략 = stash 경로를 그대로 반환 / 로컬 dir = 복사 / `s3://prefix`
  = 업로드. 어느 쪽이든 Result의 `output_prefix`·`outputs{제품→경로들}`로
  **저장 경로를 반환**한다.
- 반출 파일 = `analyzers.PRODUCTS`의 egress 선언 ∩ **열린 제품**(`--products`).
  Phase 1은 likeness.json + provenance.json만 밖으로 나간다.

## 5. 관측 — 회사 Grafana(Zabbix+Loki) 합류, 자체 대시보드 없음

분업: **Zabbix**=생존·게이지·알람(`/health` JSON을 HTTP agent+JSONPath로 폴링 —
트리거: `status≠UP`·`queue>N`·`failed 증가`) / **Loki**=율·지연분포·이벤트
(구조화 JSON 로그 — traceback도 `exception` 필드로 한-줄) / **클립 단위 "왜"**=
노드의 inspect·report (플릿 화면에서 clip_id 보고 드릴다운).

⚠ **관측 단위 = `serve`(HTTP 면) 노드**다. `momentscan server start --daemon`(UDS 웜 데몬)은
로컬 연구/운영자 도구라 관측 레인에 안 잡힌다 — 대시보드의 모든 것은 *방출된 로그*에서
파생되고(Grafana는 아무것도 probe하지 않음), health beat·node 도장은 HTTP 면만
낸다. "살아있는 노드" 패널 = 최근 2m 내 `service.health`를 낸 node 수. (데몬을
굳이 보이게 하려면 `momentscan server start --daemon --log-format json >> ~/logs/momentscan-daemon.log`
— daemon.heartbeat이 이벤트 스트림에 뜨지만 노드 수에는 안 잡힌다, 의도된 경계.)

**로컬 검증 스택** = [`deploy/observability/`](../deploy/observability/) —
Grafana+Loki+promtail 3컨테이너 (~500MB램):

```bash
momentscan server start --port 8080 …     # 로그는 기본으로 ~/logs/momentscan-{port}.log (JSON)
cd deploy/observability && MOMENTSCAN_LOG_DIR=$HOME/logs docker compose up -d
# → http://localhost:3000 (익명 Admin) · 대시보드 "momentscan · ops"
```

⚠ 로그 싱크는 **서비스 기본값**이다 — 셸 리다이렉트 불필요 (터미널에서 그냥 띄워도
관측 레인에 잡힘; `--log-file`로 바꾸고 `-`는 기존 stderr). 노드마다 자기 파일이라
한 머신 다중 인스턴스도 안 섞인다.

여기서 검증된 것이 그대로 회사로 이식된다 — **바꿀 곳만**: promtail `clients.url`
(+`tenant_id`/`basic_auth`, 모니터링 팀 확인)·`labels.env` **dev→alpha**(라벨 격리 —
운영 쿼리 오염 방지). 대시보드는 `momentscan-ops.json` import.
규율: `clip_id`는 라벨 승격 금지(카디널리티) — 본문 필드로 두고 `| json` 필터.

**노드 구분(멀티노드)**: 서비스가 기동 시 노드 정체성 `node`("advertise-host:port",
Eureka 광고 주소와 같은 근거)를 **모든 로그 라인·Result·/health·/info에 도장** 찍고,
promtail이 본문의 `node`를 라벨로 승격한다 → 노드별 promtail 설정 차이가 불필요하고
(전 노드 동일 설정), Loki에서 `sum by (node)` 분해·Result의 `node`로 "이 결과를 만든
서버" 추적이 된다.

**GPU 점유("누가 얼만큼")**: `/health.gpu = {self_mb, used_mb, total_mb}` — self=그
노드 프로세스의 점유(nvidia-smi pid 매칭, 5s 캐시), used=장치 전체(타 프로세스 포함),
GPU 없는 노드=null. health beat에 실려 대시보드 "GPU 점유" 패널(노드별 자기점유 vs
장치 사용/용량)이 그린다. Zabbix 트리거 후보: `$.gpu.used_mb / $.gpu.total_mb > 0.9`.
`momentscan server status`도 노드별 `gpu 자기/사용/총`을 표시. ⚠ 단일 GPU 머신에서 처리
노드는 하나만 — 이 패널이 그 규율의 감시자다 (두 노드 자기점유가 동시에 오르면 OOM 임박).

**잡 수명주기 가시성**: `service.job.accepted → started → done | failed` 이벤트가
전부 `clip_id`·`source_uri`(무슨 비디오)·`output_prefix`(출력했는지)를 담는다 —
대시보드 "잡 수명주기" 테이블이 이걸 행으로 보여주고, **clip_id 클릭 =
`http://<node>/reports/<clip_id>/`** (데이터 링크).

**개별 scan inspect 확인(드릴다운)**: 각 노드가 자기 stash의 클립 리포트를
읽기-전용 정적 서빙한다 — `GET /reports/{clip_id}/` = index.html(+상대 자산:
portrait·highlight mp4·**inspect/clip.html**). 잡 완료 시 서비스가 report를 자동
렌더하고 Result에 `report_url`을 담는다. inspect 페이지 자체는 무거워서(비디오
트랜스코드) 자동 렌더 안 함 — 연구자가 그 노드에서 `momentscan inspect <clip>`을
돌리면 그 순간부터 같은 URL 밑에서 서빙된다. 경로 탈출은 이중 가드(세그먼트
검사+resolve 격리, api-check가 회귀 검증).

회사 확인 질문 (유레카 3종에 추가): ④ Loki push 엔드포인트·인증·테넌트
⑤ promtail/alloy가 로그를 어디서 집나(파일 tail vs journald) ⑥ Zabbix HTTP agent
아이템 사용 절차 (호스트 등록은 그쪽 운영 절차 — Zabbix에는 자동 발견 시너지 없음).

## 6. 아직 없는 것 (의도된 보류)

- 인증(알파 = 사내망 가정) · Kafka consumer(같은 Job JSON을 먹는 어댑터만 추가하면
  됨 — 페이로드 transport-agnostic) · 오토스케일/워커풀 · S3 실계정 검증(코드는
  있고 mock 없이 미검증 — AWS 첫 배포 때 스모크 필수).

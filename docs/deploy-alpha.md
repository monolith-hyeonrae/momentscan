# 알파 배포 런북 — serve-http · Eureka · S3

> 계약 = [contracts.md C1 v1](contracts.md) · **API 명세(회사 공유용) =
> [api/openapi.yaml](api/openapi.yaml)** · 계약 회귀 테스트 = `momentscan api-check`
> (인프로세스, GPU/Eureka 불필요 — 명세와 서버의 일치를 13항목 검증).
> 실행기 = `momentscan serve-http` (`service.py` — 외부 HTTP 면; `daemon.py`의
> UDS 제어면과 별개).

## 1. 기동 (로컬 서버 / AWS 서버 동일)

```bash
momentscan serve-http --port 8080 --out /data/stash --fps 6 \
    --products likeness \                        # 단계 배포 스위치 (Phase 1 = likeness만)
    --eureka http://<회사-eureka>:8761/eureka \   # 주면 등록, 빼면 등록 없이 HTTP만
    --advertise-host <이 노드의 IP>               # 생략 = 자동 감지 (아래 §3 주의)
```

동작: FIFO 단일 워커(GPU 직렬화) · warm detect 캐시(첫 잡만 모델 로드) ·
멱등(clip_id 재요청 = 재계산 없이 기존 경로 반환, `result.json`이 근거).

```
POST /jobs        {clip_id, source_uri, output_uri?, fps?, products?, subject_query?}
                  → 202 {status, output_prefix, poll} | 200 (이미 완료 = Result)
GET  /jobs/{id}   → queued|running / Result / failed
GET  /health      → {"status":"UP", queue, running, …}     (Eureka healthCheckUrl)
GET  /info        → 앱 메타                                  (Eureka statusPageUrl)
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

## 5. 아직 없는 것 (의도된 보류)

- 인증(알파 = 사내망 가정) · Kafka consumer(같은 Job JSON을 먹는 어댑터만 추가하면
  됨 — 페이로드 transport-agnostic) · 오토스케일/워커풀 · S3 실계정 검증(코드는
  있고 mock 없이 미검증 — AWS 첫 배포 때 스모크 필수).

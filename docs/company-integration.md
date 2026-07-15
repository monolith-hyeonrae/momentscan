# 회사 연동 관례 노트 — cju-activity-video-* 실물 분석 (2026-07-15)

출처: `~/repo/monolith.extern/`의 회사 실사용 프로그램 2개
(cju-activity-video-**control** · cju-activity-video-**process**) 설정·구조 정독.
**⚠비밀값(자격·키·웹훅)은 이 문서에 절대 복제하지 않는다** — 원본 loc 프로파일에
실계정이 들어 있으므로 monolith.extern 자체를 어떤 레포에도 커밋 금지.

## 토폴로지 (가정 교정)

**"중앙 Eureka" 아님** — `cju-activity-video-control`(오케스트레이터)이 **Eureka
서버를 내장**하고(`register-with-eureka: false` + `fetch-registry: false` +
`eureka.server.*` = standalone 서버 구성), 워커들이 거기에 등록한다:

```
디바이스 신호 → SQS(CJU_ACTIVITY_VIDEO) → control(단일 활성 오케스트레이터)
                                            ├─ 내장 Eureka: /activity-video/control/eureka
                                            ├─ MySQL(read/write) · Kafka(Confluent) · Slack
                                            └─ 디스패치 → process 워커(REST, Eureka 발견)
                                                            └─ 완료 시 control로 **비동기 콜백**
```

- 등록 URL: prd `https://api.cju.981park.com/activity-video/control/eureka` ·
  dev `https://dev-api.cju.981park.com/activity-video/control/eureka` ·
  loc `http://localhost:8081/eureka`
- momentscan의 등록 대상은 **우리 도메인의 control-급 서비스가 내장할 Eureka**일
  가능성이 큼 (또는 저 video control에 직접) — 회사 확인 필요 질문으로 유지.

## 워커(process) 등록 관례 = momentscan이 흉내낼 것

```yaml
spring.application.name: cju-activity-video-process   # 소문자 케밥 (Eureka가 내부 대문자화)
eureka:
  instance:
    prefer-ip-address: true                            # IP 광고 (우리 --advertise-host와 일치)
  client:
    service-url:
      defaultZone: https://api.cju.981park.com/activity-video/control/eureka
```

- 하트비트/리스 커스텀 없음 = Spring 기본(갱신 30s/축출 90s) — **우리 eureka.py
  기본값과 일치.**
- 앱 네이밍 후보: `cju-activity-video-scan` 류 (회사 결정 필요 질문).

## 그 외 관례 (연동 시 참조)

| 항목 | 값/패턴 |
|---|---|
| S3 | 버킷 `981park-media-cju` (dev: `dev-981park-media-cju`) · root: `edit`(비디오)/`thumb`(이미지) · 리전 ap-northeast-2 · 자격=기본 체인(운영 EKS Pod Identity, 로컬 표준 env/credentials) |
| 서빙 | CloudFront `media.cju.981park.com` (dev `jeju-media.981park.net`) |
| 관측 | actuator 전 엔드포인트 노출, health show-details — Zabbix가 `/actuator/health`를 볼 가능성 → **우리 /health에 actuator-호환 alias 후보** |
| 인증 | **서비스-간 OAuth2 client-credentials(JWT, sgp accounts 서버)** — 우리 서비스 현재 무인증. 연동 시 요구 가능성 높음 → 질문 목록 추가 |
| 수명주기 | graceful shutdown 표준(워커 유예 180s — 처리중 잡 완주 배려), k8s 배포 |
| 워커 수신 | REST(multipart 100MB 설정 = 파일 수신 엔드포인트 존재), 완료는 **콜백**(control URL 호출) — 우리 C1은 202+poll이라 **콜백 어댑터가 연동 갭** (transport-agnostic 설계라 어댑터 소형) |
| 이벤트 | Kafka Confluent Cloud(SASL_SSL + schema registry) — C1 페이로드의 Kafka 자리와 부합 |

## 로컬 테스트 (2026-07-15)

vanilla Spring Cloud Netflix Eureka 서버(docker `steeltoeoss/eureka-server`,
:8761)에 우리 stdlib eureka.py를 실등록 — mock이 아닌 **실제 Netflix 구현**과의
프로토콜 호환 검증. (control 앱 직접 부팅은 DB/Kafka/OAuth 의존이라 보류;
Eureka 프로토콜은 표준이라 vanilla로 동등.)

## 회사에 남은 질문 (갱신)

1. momentscan의 등록 대상 Eureka = 어느 control? (신규 도메인 control 예정 여부)
2. 앱 네이밍 확정 (`cju-activity-video-scan`? `cju-momentscan`?)
3. **서비스-간 인증**: 우리 API 호출에 OAuth2 client-credentials 요구되는지 —
   요구되면 JWT 검증(리소스 서버) 추가 필요
4. 잡 전달 방식: control 디스패치(REST)+콜백인지, 우리 C1(202+poll)로 합의 가능한지
5. S3 버킷/프리픽스: 우리 산출물의 지정 위치 (`981park-media-cju/<root>?`)
6. Loki/Zabbix: 우리 구조화 로그의 수집 경로

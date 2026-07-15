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

## 로컬 실검증 결과 (2026-07-15 — control 실물 상대)

- **loc 프로파일 실행 실측**: dev DB(3306)는 VPN에서도 ACL로 불가 + placeholder
  3개 누락(PARK_CLUB/SGP_MEMBER/CJU_GAME_API_URL) → **로컬 MySQL(docker) +
  프로퍼티 오버라이드(datasource·SQS off) + 더미 URL env**로 부팅 성공. 빈
  스키마는 **등록엔 무해하나 `/manage/eureka-ui`는 죽인다**(컨트롤러가
  video_process 이력도 조회 → JSON 에러 반환). 해법=`--spring.jpa.hibernate.ddl-auto=update`
  … 인데 BaseEntity reg_dt/mod_dt의 `DEFAULT CONVERT_TZ(...)` columnDefinition을
  MySQL이 거부해 9/11 테이블 생성 실패(회사는 스키마 외부관리라 안 밟는 지뢰) →
  부팅 로그의 실패 DDL 수거·default를 CURRENT_TIMESTAMP로 치환해 수동 적용하면
  UI 정상(로컬 타임스탬프만 UTC 표기).
- **⚠Eureka 인증 요구 확정(실측)**: SecurityConfig가 eureka-ui·peer-replication·
  /api만 permitAll, **나머지 전부 JWT** — 등록도 무토큰이면 401. 증명된 흐름:
  계정서버 client_credentials(Basic id:secret, scope api.write api.read,
  만료 24h) → 등록 204·하트비트 200·조회·해지 200 (해지 후 GET ~30s 잔상 =
  서버 응답 캐시, 정상).
- **momentscan 구현 완료(57a46bb)**: eureka.TokenProvider(캐시·60s 만료마진·
  401 시 강제갱신 1회 재시도) — 자격은 **env로만**: `EUREKA_TOKEN_URI` /
  `EUREKA_CLIENT_ID` / `EUREKA_CLIENT_SECRET` (+`EUREKA_TOKEN_SCOPE`).
  라이브 e2e = 실물 control 상대 전 수명주기 PASS.
- 부산물: control 빈 체인에 **VideoTrackcamService** 존재 — 트랙캠이 이 시스템
  가족에 이미 있음(visualstack 로드맵 4단의 소비자 맥락).
- **video-process 워커 실기동(같은 날)**: loc + `spring.datasource.read/write.*`
  로컬 MySQL 오버라이드(jdbc-url은 라이브러리 sgp-mommos-support의
  DataSourceConfigSupport가 바인딩 — loc yml엔 아예 없음) + ffmpeg 경로
  교체(loc 기본이 macOS homebrew 경로)로 부팅, **내장 Eureka에 정상 등록** —
  eureka-ui에 momentscan과 나란히 표시. 워커의 JWT 부착 =
  `RestTemplateDiscoveryClientOptionalArgs` + `HeaderHttpRequestInterceptor`
  (OAuth2AuthorizedClientManager→setBearerAuth) — 우리 TokenProvider와 동형.
- **등록 페이로드 비교(실측)**: instanceId(ip:app:port)·lease 30/90·MyOwn·vip
  전부 우리와 일치. 차이 2: ①healthCheckUrl=`/actuator/health`(우리 `/health` —
  alias 후보 재확인) ②**metadata `service-available-status` = 진행중 잡 수**
  (워커 EurekaMetaService가 잡 시작/종료마다 증감, control EurekaClientService가
  `processCount`로 읽어 디스패치 판단) — **디스패치가 Eureka 메타데이터 위의
  부하 신호 관례**임을 확인. momentscan이 디스패치 대상이 되면 같은 키 방출
  필요(또는 C1 202+poll 합의) → 질문 4의 실측 세부.

- **dev 환경 실등록(같은 날)**: `https://dev-api.cju.981park.com/activity-video/control/eureka`에
  같은 자격·같은 코드로 등록 204 → 실운영 워커 pod와 나란히 UP → 해지 200.
  추가 증명: HTTPS+게이트웨이 경로 통과, dev control이 같은 client 자격 수용,
  응답 캐시(~30s) 동일. dev 워커 instanceId=k8s pod명 기반(`pod-name:app`) —
  우리 `ip:app:port`와 다른 관례지만 둘 다 유효.

## 잡 디스패치 프로토콜 — 실코드 판독 (2026-07-15, E2E 사슬)

**⚡control에 momentscan 자리가 이미 예약돼 있다**: `ProcessGroup.MOMENT_SCAN_PROCESS
("CJU-ACTIVITY-MOMENT-SCAN-PROCESS")` + `MomentScanApi`(테스트 트리거·콜백) +
`MomentScanService`(그룹 큐) + `ActivityMediaType.MOMENT_SCAN`. → 질문 1·2가
코드로 답변됨(등록 대상=video control 자체, 앱명=`cju-activity-moment-scan-process`).

전체 흐름 (파일: control `VideoExecute`/`ProcessSendClient(Api)`/`MomentScanApi` ·
worker `VideoProcessApi`/`VideoProcessSpringEvent`/`VideoProcessCallBackSpringEvent`/
`S3Client`/`FileManager`):

1. **기원**: 디바이스→SQS→control 그룹 큐. 테스트 트리거
   `POST /api/moment-scan/test/{workflowId}` (**permitAll — 로컬 리허설에 사용
   가능**; 단 parameter=null로 큐잉됨, 수신측은 null 파라미터 허용 필요).
2. **디스패치**: 10s 스케줄러가 그룹별 Eureka UP 인스턴스 순회, 큐 peek 후
   Feign `POST {homePageUrl}/video/process/{mediaType}` (connect 3s / read 60s;
   본문=ProcessClientRequestDTO{workflowId, group, mediaType,
   parameter.source={requestS3Video/Audio/OverlayVideo/Thumbnail = S3 key}}).
   통신 실패=쿨다운 블랙리스트+다음 서버 failover; 큐 유지.
3. **워커 수락**: in-flight≥MAX면 `UNAVAILABLE_CLIENT`(=ACTIVITY-VIDEO-PROCESS.
   10002 — control이 벌점 없이 다음 인스턴스 시도), 아니면 메타 카운터 +1 →
   **비동기 이벤트 발행 후 즉시 ok()** (동기 ACK, 처리는 백그라운드).
4. **처리**: `fileManager.downloadIfNotEmpty(source.requestS3Video)` —
   S3Client.getObject(videoBucket, key) 스트리밍, **재시도 6회 지수백오프(1s~)**,
   workflowId-키 임시파일 → ffmpeg/opencv 실행.
5. **업로드**: uploadFile(video)/uploadFileIfExists(thumb) — **object key가 그대로
   CloudFront 경로**, 결과=UploadFilePathResultDTO{resultS3Video(+size),
   resultS3Thumbnail(+Intro), resultCdn* 3종}.
6. **콜백(실패여도 반드시)**: `POST {control}/process/video/{workflowId}`
   (momentscan 그룹은 `/process/moment-scan/{workflowId}`) 본문=
   ProcessClientResultDTO{workflowId, videoProcessSeq, mediaType, group echo,
   resultPath, status=VIDEO_SUCCESS|실패, errorMessage}. **응답 data에 다음 잡이
   실려올 수 있음**(같은 워커 체이닝 = S3 재다운로드 절약) — 없으면 카운터 −1.
7. **정리**: finally에서 workflowId 임시파일 삭제. 회수: failCount≥3 드롭(데드레터
   TODO)·워커 소실/유휴 10분이면 재큐잉. 원격 드레인=`POST /video/config/initProcess
   ?count=999`(control의 enabledClient).

**momentscan 어댑터 — 구현 완료 (track/dispatch-shim, `company.py`)**: ①앱명
`cju-activity-moment-scan-process` 등록 ②`POST /video/process/{mediaType}` shim
(수락 OK/포화 10002, parameter→C1 Job 변환) ③소스 해석=단계 배치(로컬 경로
그대로 / 상대 key→`--s3-bucket` 해석 / 해석불가=수락 후 정직 VIDEO_ERROR 완주)
④완료 콜백 `/process/moment-scan/{workflowId}` Bearer(성공/실패 모두, 401 1회
재갱신) ⑤C1 202+poll은 내부 정본 유지. 잔여=service-available-status 메타 갱신
(busy는 응답 코드로 이미 동작)·resultPath 실매핑(질문 4).

**로컬 풀-루프 리허설 PASS (2026-07-15, 실물 control 상대)**: control 테스트
트리거(`/api/moment-scan/test/{wf}`)→10s 스케줄러가 그룹명으로 우리를 발견·
디스패치(null parameter→VIDEO_ERROR 완주로 큐 정리 확인) + 처리 중 busy
10002→control 10s 재시도 관측 + 직접 디스패치(wf777, 로컬 소스)→**전 파이프라인
→VIDEO_SUCCESS 콜백→control 수신** 확인. 이 리허설이 C1 잠복 버그 계보를
적발: 클립 정체성이 파일명 stem에 은닉(detect + needs_source 스테이지들,
일부는 심링크도 resolve()로 풀어버림) → detect clip_id 인자 + 서비스 하드링크
별칭 이음매로 완화(L14, pytest 9핀).

## 회사에 남은 질문 (갱신 2026-07-15 — 코드 판독 후)

1. ~~등록 대상 Eureka~~ → **코드로 확정**: video control 자체
   (MOMENT_SCAN_PROCESS 그룹 예약 존재). 확인만: 이 예약이 우리 배치 계획인지.
2. ~~앱 네이밍~~ → **코드로 확정**: `cju-activity-moment-scan-process`.
3. 인증 잔여: 우리 API 리소스-서버 검증 필요 여부 + 우리 전용 client-id 발급
   (디스패치 Feign은 requestInterceptor로 JWT를 실어옴 — 검증 구현 필요 가능성 높음).
4. ~~잡 전달 방식~~ → **코드로 확정**: 디스패치+콜백(+체이닝). 남은 것:
   MOMENT_SCAN용 ProcessMediaParameter 구체 클래스(소스 키 구성)와 우리
   ResultDTO 매핑 필드 합의(resultPath에 뭘 채울지 — likeness JSON의 자리).
5. S3 버킷/프리픽스: 우리 산출물의 지정 위치 (`981park-media-cju/<root>?`)
6. Loki/Zabbix: 우리 구조화 로그의 수집 경로

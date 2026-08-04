# momentscan 배포 가이드 — DevOps 핸드오프

> 인프라(ASG·IAM·네트워크)를 설정하는 DevOps 팀을 위한 문서. 이 문서만으로
> 인스턴스를 띄울 수 있도록 작성했다. 검증 기록과 배경은
> [deploy-alpha.md](deploy-alpha.md) §3b, 회사 연동 프로토콜은
> [company-integration.md](company-integration.md) 참고. (2026-08-03 기준)

## 배포 구성 요소

| 항목 | 값 |
|---|---|
| 컨테이너 이미지 | `ghcr.io/monolith-hyeonrae/momentscan:main` (11.9GB). ECR 발급 후 이관 예정 — 아래 요청 사항 1 |
| 모델 웨이트 번들 | `s3://dev-981park-media-cju/moment-scan/models/momentscan-models-v1.tar` (2.5GB). 컨테이너가 부팅 시 내려받아 압축 해제. 운영 버킷 내 위치는 협의 필요 |
| 서비스 형태 | Eureka에 등록되는 워커. control이 작업을 분배하고, 결과는 S3 업로드 + 콜백으로 반환. 인스턴스당 동시 1건 처리 — 초과 요청에는 10002 코드로 응답하고 control이 다른 인스턴스로 재시도 |

## 인스턴스 요구 사항

- GPU 1개 (T4급 이상, g4dn.xlarge 상당). 작업당 VRAM 사용량은 최대 약 4GB.
  스팟 mixed-instances로 g4dn/g5/g6 계열을 섞어도 된다. CUDA 라이브러리는
  이미지에 포함되어 있으므로 호스트에는 NVIDIA 드라이버와
  nvidia-container-toolkit만 있으면 된다.
- 디스크 40GB 이상 (이미지 12GB + 웨이트 2.5GB + 작업 공간과 로그).
- 부팅 소요 시간: 이미지 pull(리전 내 수 분) + 웨이트 압축 해제(1~2분).
  개장 15분 전에 미리 띄우는 스케줄을 권장.
- 부팅에 외부 인터넷 접근은 필요 없다. S3, 컨테이너 레지스트리, Eureka에만
  닿으면 된다.

## IAM — 인스턴스 역할 최소 권한

- `s3:GetObject` — `moment-scan/models/*` (웨이트), `video/original/*` (소스 영상)
- `s3:PutObject` — `moment-scan/out/*` (결과 업로드)
- ECR 이관 시 pull 권한 추가. GHCR을 유지하면 읽기용 PAT를 인스턴스에 배치해야
  하므로 ECR을 권장한다.

> S3 사용 범위(2026-08-03 합의): momentscan이 스스로 쓰는 모든 객체는 버킷
> 최상위 `moment-scan/` 아래로 제한한다(models/ · out/ · sources/). 그 밖의
> 경로는 작업 요청에 명시된 소스 키를 읽기만 한다. 전용 버킷 전환 여부는
> 요청 사항 2와 함께 협의.

## 실행 방법 (user-data 참조 구현)

```bash
docker run -d --name momentscan --gpus all --restart unless-stopped \
  --stop-timeout 120 -p 8080:8080 \
  -v ms-data:/data -v ms-home:/root \
  --env-file /etc/momentscan.env \
  ghcr.io/monolith-hyeonrae/momentscan:main
```

`/etc/momentscan.env` (전체 항목과 설명은 리포 `deploy/docker/env.example`):

```
MS_MODELS_URI=s3://…/moment-scan/models/momentscan-models-v1.tar
MS_PORT=8080
MS_PRODUCTS=likeness
MS_APP_NAME=cju-activity-moment-scan-process
MS_EUREKA=https://…/activity-video/control/eureka
MS_CONTROL_URL=https://…/activity-video/control
MS_S3_BUCKET=<소스 버킷>
MS_OUTPUT_URI=s3://<버킷>/moment-scan/out
EUREKA_TOKEN_URI=…        # OAuth2 client_credentials (Eureka 등록·콜백 인증)
EUREKA_CLIENT_ID=…
EUREKA_CLIENT_SECRET=…
```

- 헬스체크: `GET :8080/health` → `{"status":"UP", gpu, queue, …}`.
  Eureka healthCheckUrl로도 같은 주소가 등록된다.
- 로그: `/data/logs/momentscan-8080.log` (JSON 구조화 — Loki 수집 경로는 협의)

## 종료와 스팟 중단 처리 — lifecycle hook 불필요

- SIGTERM을 받으면 Eureka에서 즉시 등록 해제하고(90초 축출을 기다리지 않음)
  종료한다. `docker stop`(위 설정의 `--stop-timeout 120`)이 이 경로를 그대로 탄다.
- 스팟 중단: 컨테이너가 IMDSv2의 spot/instance-action을 5초 주기로 직접
  확인하다가, 중단 예고가 오면 스스로 SIGTERM 경로로 종료한다. 따라서 ASG
  lifecycle hook이나 별도 중단 핸들러가 필요 없다. 처리 중이던 작업은 control이
  10분 후 다른 인스턴스로 재배정한다.
- 스케일-인도 같은 방식이다. 그냥 terminate하면 된다 — 데이터는 전부 S3에 있고
  인스턴스는 상태를 갖지 않는다.

## 스케일링 기준

- 1차 기준은 시간 스케줄(개장 시간, 계절에 따라 변동) — capacity 0↔N.
- 처리량 산정: 작업당 40~150초(영상 길이에 따라 다름) × 인스턴스당 동시 1건.
  control은 10초 주기로 Eureka의 UP 인스턴스를 순회하며 작업을 분배한다.

## 요청 사항

1. **ECR 리포지토리 생성**: `981park-moment-scan` (기존 이름 규칙에 맞춤).
   현재 개발 계정에는 ecr:CreateRepository 권한이 없다(2026-08-03 확인).
   CI가 push할 자격 증명도 함께 필요하다(OIDC 역할 권장).
2. 인스턴스 IAM 역할(위 최소 권한) + 운영 버킷의 웨이트 번들 위치.
3. EUREKA_* 운영 자격 증명(client_credentials). dev 자격으로는 검증 완료(2026-07-15).
4. JSON 로그의 Loki/Zabbix 수집 경로.

## 검증 범위

로컬 GPU 장비의 컨테이너에서 전 구간 테스트 완료(2026-08-03): Eureka 등록과
해제, 작업 수신과 포화 시 10002 응답, S3 소스 다운로드(.ts/.mp4) → 11단계
파이프라인 → S3 결과 업로드, 성공/실패 콜백, 오프라인 모델 로드, SIGTERM 정상
종료. 아직 확인하지 못한 것: 실제 스팟 중단 이벤트, 운영 Eureka 서버 대상 등록.

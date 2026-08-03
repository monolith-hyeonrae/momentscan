# momentscan 배포 핸드오프 — DevOps용 런치 계약 (2026-08-03)

> 대상 독자: 인프라(ASG·IAM·네트워크)를 셋업하는 DevOps.
> 여기 적힌 것만으로 인스턴스가 뜨도록 쓰였다. 배경·검증 기록은
> [deploy-alpha.md](deploy-alpha.md) §3b, 회사 연동 프로토콜은
> [company-integration.md](company-integration.md).

## 물건

| 항목 | 값 |
|---|---|
| 이미지 | `ghcr.io/monolith-hyeonrae/momentscan:main` (11.9GB; ECR 발급 시 이관 — 아래 요청) |
| 웨이트 번들 | `s3://dev-981park-media-cju/moment-scan/models/momentscan-models-v1.tar` (2.5GB — 부팅 시 컨테이너가 자가 전개, 운영 버킷 자리 협의 필요) |
| 역할 | Eureka 워커 — control이 디스패치, 결과는 S3 반출 + 콜백. **인스턴스당 동시 1잡**(포화 시 10002 응답 → control이 다음 인스턴스로) |

## 인스턴스 요구

- **GPU 1개** (T4급 이상 — g4dn.xlarge 상당; 실측 피크 VRAM ~4GB/잡).
  스팟 mixed-instances 구성 시 g4dn/g5/g6 계열 혼합 무방 (CUDA는 이미지가 수반,
  호스트는 NVIDIA 드라이버 + nvidia-container-toolkit만).
- 디스크 **40GB+** (이미지 12GB + 번들 2.5GB + 잡 작업공간·로그).
- 부팅 소요: pull(리전 내 수 분) + 번들 전개(1~2분) → 개장 15분 전 warm-up 스케줄 권장.
- 콜드부팅에 외부 인터넷 불필요(HF 오프라인 고정) — S3·레지스트리·Eureka만 닿으면 됨.

## IAM (인스턴스 역할 최소 권한)

- `s3:GetObject` — `moment-scan/models/*` (웨이트), `video/original/*` (소스)
- `s3:PutObject` — `moment-scan/out/*` (결과 반출)
- ECR 이관 시 pull 권한 (GHCR 유지 시 read-only PAT를 인스턴스에 배치해야 하므로 ECR 권장)

> **작업 공간 규약(2026-08-03)**: momentscan의 자발적 쓰기는 전부 버킷 최상위
> `moment-scan/` 단일 루트 아래(models/·out/·sources/) — 공유 버킷을 어지럽히지
> 않기 위한 소유 경계이자 삭제 경계(`rm --recursive` 한 방). 루트 밖은 디스패치가
> 명시한 소스 키의 읽기만. 정식 자리(전용 버킷)는 아래 요청 2와 함께 협의.

## 실행 계약 (user-data 참조 구현)

```bash
docker run -d --name momentscan --gpus all --restart unless-stopped \
  --stop-timeout 120 -p 8080:8080 \
  -v ms-data:/data -v ms-home:/root \
  --env-file /etc/momentscan.env \
  ghcr.io/monolith-hyeonrae/momentscan:main
```

`/etc/momentscan.env` (전체 계약 = 리포 `deploy/docker/env.example`):

```
MS_MODELS_URI=s3://…/moment-scan/models/momentscan-models-v1.tar
MS_PORT=8080
MS_PRODUCTS=likeness
MS_APP_NAME=cju-activity-moment-scan-process
MS_EUREKA=https://…/activity-video/control/eureka
MS_CONTROL_URL=https://…/activity-video/control
MS_S3_BUCKET=<소스 버킷>
MS_OUTPUT_URI=s3://<버킷>/moment-scan/out
EUREKA_TOKEN_URI=…        # OAuth2 client_credentials (등록·콜백 JWT)
EUREKA_CLIENT_ID=…
EUREKA_CLIENT_SECRET=…
```

- 헬스체크: `GET :8080/health` → `{"status":"UP", gpu, queue, …}` (Eureka healthCheckUrl로도 등록됨)
- 로그: `/data/logs/momentscan-8080.log` (구조화 JSON — Loki 수집 경로 협의)

## 종료·스팟 규약 (lifecycle hook 불필요)

- **SIGTERM = 우아한 종료**: Eureka 즉시 해지(90s 축출 대기 없음) → 프로세스 종료.
  `docker stop`(위 `--stop-timeout 120`)이 그대로 그 경로.
- **스팟 회수**: 컨테이너가 IMDSv2 `spot/instance-action`을 5s 주기 자가 감시 —
  회수 예고 시 스스로 SIGTERM 경로 진입. **ASG lifecycle hook·중단 핸들러 불필요.**
  진행 중이던 잡은 control의 재큐잉 규약(워커 소실 10분)으로 회수됨.
- 스케일-인도 동일: 그냥 terminate하면 됨(데이터는 전부 S3, 인스턴스 무상태).

## 스케일 신호

- 시간 스케줄(개장 시간, 계절 가변)이 1차 — capacity 0↔N.
- 처리량: 잡당 40~150s(클립 길이 의존) × 인스턴스당 1잡 → 목표 처리량/디스패치
  지연으로 N 산정. control 디스패치는 10s 주기 Eureka UP 인스턴스 순회.

## DevOps에 요청 (미결)

1. **ECR 리포 발급**: `981park-moment-scan` (기존 네이밍 관례 준수;
   `ecr:CreateRepository` 권한 부재 실측 2026-08-03) + CI push 자격(OIDC 역할 권장).
2. 인스턴스 IAM 역할(위 최소 권한) + 운영 버킷 웨이트 번들 자리.
3. EUREKA_* 운영(client_credentials) 자격 — dev 자격은 검증 완료(2026-07-15).
4. 구조화 로그의 Loki/Zabbix 수집 경로.

## 검증 상태 (이 계약이 실증된 범위)

로컬 GPU 머신에서 컨테이너 E2E 전 구간 PASS (2026-08-03): Eureka 등록/해지 ·
디스패치 수락/포화 10002 · S3 소스 반입(.ts/.mp4) → 11스테이지 → S3 반출 ·
성공/실패 콜백 · 오프라인 모델 로드(doctor 13/15) · SIGTERM 우아 종료.
미실증: 실제 스팟 회수 시나리오(IMDS 실이벤트), 운영 Eureka 상대 등록.

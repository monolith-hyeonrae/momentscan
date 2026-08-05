#!/bin/bash
# momentscan 컨테이너 entrypoint — ①웨이트 번들 전개 ②스팟 회수 감시 ③서버 기동.
#
# env 계약 (MS_* = momentscan 플래그 매핑, 미설정 = 해당 플래그 생략):
#   MS_MODELS_URI      s3://.../momentscan-models-vN.tar  (웨이트 번들; 생략=전개 스킵)
#   MS_PORT=8080  MS_OUT=/data/out  MS_PRODUCTS=likeness
#   MS_APP_NAME / MS_EUREKA / MS_CONTROL_URL / MS_S3_BUCKET / MS_OUTPUT_URI
#   MS_ADVERTISE_HOST / MS_FPS
#   MS_LOG_FILE        로그 목적지 (기본 "-" = stdout — K8s/ArgoCD 로그 관례.
#                      파일 수집 환경이면 /data/logs/... 경로 지정)
#   EUREKA_TOKEN_URI / EUREKA_CLIENT_ID / EUREKA_CLIENT_SECRET (회사 Eureka JWT — env로만)
#
# 종료 규약: SIGTERM(docker stop·스팟 예고) → 서버의 우아한 경로(유레카 즉시 해지).
set -euo pipefail

log() { echo "[entrypoint] $*"; }

# ── ① 웨이트 번들: $HOME 아래로 전개 (마커로 멱등 — /root를 볼륨으로 주면 웜 캐시) ──
if [[ -n "${MS_MODELS_URI:-}" ]]; then
    marker="$HOME/.momentscan-models.done"
    if [[ -f "$marker" && "$(cat "$marker")" == "$MS_MODELS_URI" ]]; then
        log "웨이트 번들 이미 전개됨 ($MS_MODELS_URI) — 스킵"
    else
        log "웨이트 번들 다운로드: $MS_MODELS_URI"
        aws s3 cp "$MS_MODELS_URI" /tmp/models.tar --only-show-errors
        tar -xf /tmp/models.tar -C "$HOME" && rm /tmp/models.tar
        echo "$MS_MODELS_URI" > "$marker"
        log "웨이트 전개 완료: $(du -sh "$HOME/.portrait981" 2>/dev/null | cut -f1) portrait981"
    fi
fi

# ── ③ 서버 기동 준비 (감시는 서버 PID가 필요해 먼저 조립) ──
mkdir -p "${MS_OUT:=/data/out}" /data/logs
args=(server start --port "${MS_PORT:=8080}" --out "$MS_OUT"
      --log-file "${MS_LOG_FILE:--}")
[[ -n "${MS_PRODUCTS:-}"       ]] && args+=(--products "$MS_PRODUCTS")
[[ -n "${MS_APP_NAME:-}"       ]] && args+=(--app-name "$MS_APP_NAME")
[[ -n "${MS_EUREKA:-}"         ]] && args+=(--eureka "$MS_EUREKA")
[[ -n "${MS_CONTROL_URL:-}"    ]] && args+=(--control-url "$MS_CONTROL_URL")
[[ -n "${MS_S3_BUCKET:-}"      ]] && args+=(--s3-bucket "$MS_S3_BUCKET")
[[ -n "${MS_OUTPUT_URI:-}"     ]] && args+=(--output-uri "$MS_OUTPUT_URI")
[[ -n "${MS_ADVERTISE_HOST:-}" ]] && args+=(--advertise-host "$MS_ADVERTISE_HOST")
[[ -n "${MS_FPS:-}"            ]] && args+=(--fps "$MS_FPS")

momentscan "${args[@]}" &
SRV=$!
log "momentscan server pid=$SRV port=$MS_PORT"

# SIGTERM/SIGINT → 서버에 중계 (서버 자체가 유레카 해지·레코드 삭제의 우아한 경로 보유)
forward() { log "종료 신호 수신 — 서버에 SIGTERM 중계"; kill -TERM "$SRV" 2>/dev/null || true; }
trap forward TERM INT

# ── ② 스팟 회수 예고 감시 (IMDSv2) — AWS 밖(온프레미스·로컬)에선 조용히 무동작 ──
(
    while kill -0 "$SRV" 2>/dev/null; do
        tok=$(curl -sf -m 2 -X PUT "http://169.254.169.254/latest/api/token" \
              -H "X-aws-ec2-metadata-token-ttl-seconds: 60" 2>/dev/null) || { sleep 30; continue; }
        if curl -sf -m 2 -H "X-aws-ec2-metadata-token: $tok" \
                "http://169.254.169.254/latest/meta-data/spot/instance-action" >/dev/null 2>&1; then
            log "스팟 회수 예고 감지 — 우아한 종료 개시 (유레카 해지, 진행 잡은 control이 재큐잉)"
            kill -TERM "$SRV" 2>/dev/null || true
            exit 0
        fi
        sleep 5
    done
) &

wait "$SRV"
rc=$?
log "server 종료 rc=$rc"
exit "$rc"

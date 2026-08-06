#!/usr/bin/env bash
# dev 환경 스모크 테스트 — 게이트웨이 경유로 헬스체크 → 작업 투입 → 완료 대기 → 결과 확인.
#
# 사용법:
#   deploy/smoke-dev.sh                      # 기본 검증 클립으로 1회 왕복
#   deploy/smoke-dev.sh s3://버킷/키.mp4      # 다른 소스 영상으로
#   BASE=http://localhost:8080 deploy/smoke-dev.sh   # 게이트웨이 대신 직접 주소로
#
# 성공 기준: 마지막 출력이 "ok": true 이고 S3에 likeness.json + provenance.json 생성.
# 소요 시간(T4 실측): 파드의 첫 작업은 모델 로드 포함 8~10분, 이후 작업은 2~4분.
set -euo pipefail

BASE="${BASE:-https://dev-api.cju.981park.com/activity-video/moment/scan}"
SOURCE="${1:-s3://dev-981park-media-cju/moment-scan/sources/verify/20260728/test_3.mp4}"
CLIP="smoke-$(date +%m%d%H%M%S)"
TIMEOUT_S=900

json() { python3 -m json.tool 2>/dev/null || cat; }

echo "== 1. 헬스체크 ($BASE) =="
HEALTH=$(curl -sf -m 10 "$BASE/health")
echo "$HEALTH" | json
echo "$HEALTH" | grep -q '"UP"' || { echo "서버가 UP이 아닙니다 — 중단"; exit 1; }
echo "$HEALTH" | grep -q '"total_mb"' || echo "주의: gpu 필드가 비어 있습니다 (CPU 폴백으로 느려짐)"

echo
echo "== 2. 작업 투입 (clip_id=$CLIP) =="
curl -sf -m 10 -X POST "$BASE/jobs" -H 'Content-Type: application/json' \
     -d "{\"clip_id\": \"$CLIP\", \"source_uri\": \"$SOURCE\", \"products\": [\"likeness\"]}" | json

echo
echo "== 3. 완료 대기 (최대 ${TIMEOUT_S}s, 15s 간격) =="
deadline=$(( $(date +%s) + TIMEOUT_S ))
while :; do
    R=$(curl -sf -m 10 "$BASE/jobs/$CLIP")
    if echo "$R" | grep -qE '"ok"|"failed"'; then break; fi
    if [ "$(date +%s)" -ge "$deadline" ]; then echo "시간 초과 — 마지막 응답:"; echo "$R" | json; exit 1; fi
    STATE=$(echo "$R" | python3 -c "import sys, json; d = json.load(sys.stdin); print(d.get('status', '?'), '(대기열', d.get('queue_depth', '?'), ')')" 2>/dev/null || echo "?")
    echo "  $(date +%H:%M:%S) $STATE"
    sleep 15
done
echo "$R" | json
echo "$R" | grep -q '"ok": *true' || { echo "작업 실패 — 위 failure 필드 확인"; exit 1; }

echo
echo "== 4. S3 결과 확인 =="
PREFIX=$(echo "$R" | python3 -c "import sys, json; print(json.load(sys.stdin)['output_prefix'])")
if command -v aws >/dev/null; then
    aws s3 ls "$PREFIX/"
else
    echo "aws CLI 없음 — 결과 위치: $PREFIX/"
fi

echo
echo "성공: $CLIP 완주 (결과: $PREFIX/)"

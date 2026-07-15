"""company — cju-activity-video control 디스패치 방언 어댑터 (C1 위의 얇은 shim).

회사 control은 워커를 Eureka에서 찾아 자기 방언으로 잡을 민다 (2026-07-15
실코드 판독 — docs/company-integration.md "잡 디스패치 프로토콜"):

  수신   POST /video/process/{mediaType}   본문 = ProcessClientRequestDTO
         응답은 HTTP 200 + ApiReturnModel {code,message,data} — 의미는 code가 말한다:
           "00000"                        = 수락 (처리는 비동기, 즉시 반환)
           "ACTIVITY-VIDEO-PROCESS.10002" = 포화 → control이 벌점 없이 다음 워커 시도
  완료   POST {control}/process/moment-scan/{workflowId}   (성공/실패 모두, Bearer)
         본문 = ProcessClientResultDTO (status=VIDEO_SUCCESS|VIDEO_ERROR)

C1(/jobs 202+poll)은 내부 정본으로 유지 — 이 모듈은 방언↔C1 변환과 콜백만 안다.
소스 해석은 단계 배치(user 2026-07-15): 로컬 경로면 그대로 처리, S3 key면
등록된 버킷(--s3-bucket)으로 해석. 버킷 미등록 상태의 key는 수락 후 정직한
VIDEO_ERROR 콜백으로 완주한다(control이 큐에서 제거하도록 — 응답 코드로
거부하면 failCount만 쌓이고 잡이 큐에 남는다).

아직 아닌 것(회사 합의 대기): resultPath 필드 매핑(임시=output_prefix),
service-available-status 메타데이터 갱신(busy 판정은 응답 코드로 이미 동작),
콜백 실패 재시도(회사 워커도 없음 — 로그만).
"""

from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request

log = logging.getLogger("momentscan.company")

GROUP = "MOMENT_SCAN_PROCESS"        # control ProcessGroup enum과 동일 문자열 (echo 계약)
MAX_INFLIGHT = 1                     # 단일 GPU 노드 = 동시 1잡; 초과는 10002로 분산 유도

# mommos ApiReturnModel 형태 (jar 판독: {code,message,data}, OK="00000")
OK = {"code": "00000", "message": "OK", "data": None}
BUSY = {"code": "ACTIVITY-VIDEO-PROCESS.10002", "message": "unavailable client", "data": None}
WRONG = {"code": "ACTIVITY-VIDEO-PROCESS.10001", "message": "wrong parameter", "data": None}


def resolve_source(raw: str | None, bucket: str | None) -> str | None:
    """회사 소스 필드(parameter.source.requestS3Video) → C1 source_uri.

      s3://… · file://… · 절대경로  → 그대로 (fetch_source가 소화)
      상대 key + 버킷 등록           → s3://{bucket}/{key}
      상대 key + 버킷 미등록 / 부재   → None (호출측이 정직 실패 콜백으로 완주)
    """
    if not raw:
        return None
    if raw.startswith(("s3://", "file://", "/")):
        return raw
    if bucket:
        return f"s3://{bucket}/{raw.lstrip('/')}"
    return None


class CompanyShim:
    """디스패치 수신 → C1 Job 변환 → 완료 콜백. runner(C1 JobRunner)는 무변경 소비."""

    def __init__(self, runner, control_url: str, *, s3_bucket: str | None = None,
                 token_provider=None):
        self.runner = runner
        self.control_url = control_url.rstrip("/")
        self.s3_bucket = s3_bucket
        self.token_provider = token_provider

    # ── 수신 ────────────────────────────────────────────────────────────────
    def handle_process(self, media_type: str, dto: dict) -> tuple[int, dict]:
        wf = dto.get("workflowId")
        if wf is None:
            return 200, WRONG
        if self._inflight() >= MAX_INFLIGHT:
            log.info("company.dispatch.busy", extra={"workflow_id": wf})
            return 200, BUSY

        param = dto.get("parameter") or {}
        ctx = {"workflow_id": wf,
               "process_id": param.get("processId"),
               "media_type": dto.get("mediaType") or media_type,
               "sub_type": param.get("subType"),
               "is_test": param.get("isTest")}
        raw = (param.get("source") or {}).get("requestS3Video")
        src = resolve_source(raw, self.s3_bucket)
        if src is None:
            # 소스 부재(테스트 트리거의 parameter=null 포함)/해석 불가 — 수락 후 즉시 실패 콜백
            log.warning("company.dispatch.nosource",
                        extra={"workflow_id": wf, "raw_source": raw,
                               "s3_bucket": self.s3_bucket})
            self._async_callback(ctx, None, f"no resolvable source (raw={raw!r}, "
                                            f"s3_bucket={self.s3_bucket!r})")
            return 200, OK

        clip_id = f"wf{wf}-{str(ctx['media_type']).lower()}"
        code, payload = self.runner.submit({
            "clip_id": clip_id, "source_uri": src,
            "_on_complete": lambda st, ctx=ctx: self._on_complete(ctx, st)})
        if code == 200:                                  # 멱등: 이미 완료 → 즉시 성공 콜백
            self._async_callback(ctx, payload, None)
        elif code != 202:                                # 수리 거부(400 등) → 정직 실패 콜백
            self._async_callback(ctx, None, json.dumps(payload, ensure_ascii=False))
        log.info("company.dispatch.accepted",
                 extra={"workflow_id": wf, "clip_id": clip_id, "source_uri": src,
                        "code": code})
        return 200, OK

    def _inflight(self) -> int:
        return sum(1 for s in self.runner.jobs.values()
                   if s["status"] in ("queued", "running"))

    # ── 콜백 ────────────────────────────────────────────────────────────────
    def _on_complete(self, ctx: dict, st: dict) -> None:
        """JobRunner._work 완료 훅 (done/failed 공통) — 성공/실패 모두 콜백."""
        if st["status"] == "done":
            self._callback(ctx, st["result"], None)
        else:
            self._callback(ctx, None, json.dumps(st.get("error") or {}, ensure_ascii=False))

    def _async_callback(self, ctx: dict, result: dict | None, error: str | None) -> None:
        threading.Thread(target=self._callback, args=(ctx, result, error),
                         daemon=True).start()

    def _callback(self, ctx: dict, result: dict | None, error: str | None) -> None:
        ok = result is not None
        body = {
            "workflowId": ctx["workflow_id"],
            "videoProcessSeq": ctx.get("process_id"),
            "isTest": ctx.get("is_test"),
            "subType": ctx.get("sub_type"),
            "mediaType": ctx.get("media_type"),
            "group": GROUP,
            # ⚠임시 매핑: 우리 산출물(likeness.json 등)의 자리는 회사 합의 대기
            # (company-integration.md 질문 4) — 지금은 저장 prefix를 실어 보낸다.
            "resultPath": ({"resultS3Video": result.get("output_prefix")} if ok else None),
            "status": "VIDEO_SUCCESS" if ok else "VIDEO_ERROR",
            "errorMessage": error,
        }
        url = f"{self.control_url}/process/moment-scan/{ctx['workflow_id']}"
        code = self._post(url, body)
        if code == 401 and self.token_provider:          # 만료 레이스 — 강제갱신 1회 재시도
            self.token_provider.token(force_refresh=True)
            code = self._post(url, body)
        lvl = logging.INFO if code == 200 else logging.WARNING
        log.log(lvl, "company.callback",
                extra={"workflow_id": ctx["workflow_id"], "status": body["status"],
                       "code": code})

    def _post(self, url: str, body: dict) -> int:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token_provider:
            tok = self.token_provider.token()
            if tok:
                headers["Authorization"] = f"Bearer {tok}"
        req = urllib.request.Request(url, method="POST",
                                     data=json.dumps(body).encode("utf-8"), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code
        except Exception as e:                           # 네트워크 순단 — 회사 워커와 동일하게 로그만
            log.warning("company.callback.error", extra={"url": url, "error": str(e)})
            return -1

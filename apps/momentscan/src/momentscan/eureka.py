"""eureka — Netflix Eureka(Spring Cloud 서비스 디스커버리) 레지스트리 어댑터.

회사 인프라의 Eureka 서버에 이 노드를 등록해 회사 게이트웨이/서비스가 우리를
"이름"으로 찾게 한다. 동작 원리 (전부 평범한 HTTP — JVM 불필요):

  1) 등록     POST   {server}/apps/{APP}            instance JSON, status=UP → 204
  2) 갱신     PUT    {server}/apps/{APP}/{ID}       30s마다 heartbeat(렌트 갱신) → 200
              (404 = 서버 재시작/축출로 등록이 사라짐 → 재등록)
  3) 축출     heartbeat이 durationInSecs(90s) 동안 없으면 레지스트리가 자동 제거
              — 죽은 노드가 라우팅 대상에 남지 않게 하는 메커니즘.
  4) 해지     DELETE {server}/apps/{APP}/{ID}       정상 종료 시 즉시 제거.

소비 측: 클라이언트(Spring 게이트웨이·타 서비스)는 GET {server}/apps/{APP}으로
UP 인스턴스 목록(host:port)을 받아 클라이언트-사이드 로드밸런싱으로 호출한다.
즉 등록 = "MOMENTSCAN이라는 이름은 이 host:port다"를 선언하는 것이 전부고,
실제 요청은 Eureka를 거치지 않고 우리 HTTP 면(service.py)으로 직접 온다.

stdlib-only(urllib) — py-eureka-client 같은 의존성 대신 위 4개 HTTP 호출을
그대로 쓴다(AK-47). Spring 기본과 맞춘 값: renewal 30s / duration 90s.
"""

from __future__ import annotations

import json
import logging
import socket
import threading
import urllib.error
import urllib.request

log = logging.getLogger("momentscan.eureka")

RENEWAL_S = 30          # Spring Cloud 기본 heartbeat 주기
DURATION_S = 90         # 이만큼 heartbeat 없으면 축출 (기본값)


def _local_ip() -> str:
    """바깥으로 나가는 인터페이스의 IP — hostname 해석이 127.x로 빠지는 함정 회피."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))       # 실제 패킷은 안 나감
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class EurekaClient:
    """한 인스턴스의 등록 수명주기: start() = 등록 + heartbeat 스레드, stop() = 해지."""

    def __init__(self, server_url: str, app: str, *, port: int,
                 host: str | None = None, health_path: str = "/health",
                 status_path: str = "/info"):
        self.server = server_url.rstrip("/")            # 예: http://eureka:8761/eureka
        self.app = app.upper()                          # Eureka는 앱 이름을 대문자로 정규화
        self.ip = host or _local_ip()
        self.host = self.ip                             # 사내망: IP를 hostName으로 쓰는 게 해석 확실
        self.port = int(port)
        self.instance_id = f"{self.ip}:{app.lower()}:{self.port}"   # Spring 관례
        base = f"http://{self.ip}:{self.port}"
        self.health_url = base + health_path
        self.status_url = base + status_path
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ── 4개의 HTTP 호출 ────────────────────────────────────────────────────
    def _call(self, method: str, path: str, body: dict | None = None) -> int:
        req = urllib.request.Request(
            self.server + path, method=method,
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            headers={"Content-Type": "application/json", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    def register(self) -> bool:
        payload = {"instance": {
            "instanceId": self.instance_id,
            "hostName": self.host,
            "app": self.app,
            "ipAddr": self.ip,
            "vipAddress": self.app.lower(),             # 클라이언트가 찾는 논리 이름
            "secureVipAddress": self.app.lower(),
            "status": "UP",
            "port": {"$": self.port, "@enabled": "true"},
            "securePort": {"$": 443, "@enabled": "false"},
            "healthCheckUrl": self.health_url,
            "statusPageUrl": self.status_url,
            "homePageUrl": f"http://{self.ip}:{self.port}/",
            # 정확히 이 @class 문자열이어야 함 — Eureka 역직렬화 계약 (AWS가 아니면 MyOwn)
            "dataCenterInfo": {"@class": "com.netflix.appinfo.InstanceInfo$DefaultDataCenterInfo",
                               "name": "MyOwn"},
            "leaseInfo": {"renewalIntervalInSecs": RENEWAL_S, "durationInSecs": DURATION_S},
        }}
        code = self._call("POST", f"/apps/{self.app}", payload)
        ok = code == 204
        log.log(logging.INFO if ok else logging.WARNING, "eureka.register",
                extra={"app": self.app, "instance": self.instance_id, "code": code})
        return ok

    def heartbeat(self) -> None:
        code = self._call("PUT", f"/apps/{self.app}/{self.instance_id}")
        if code == 404:            # 서버 재시작/축출 → 등록이 사라진 상태
            log.warning("eureka.heartbeat.lost", extra={"instance": self.instance_id})
            self.register()
        elif code != 200:
            log.warning("eureka.heartbeat.fail", extra={"code": code})

    def deregister(self) -> None:
        code = self._call("DELETE", f"/apps/{self.app}/{self.instance_id}")
        log.info("eureka.deregister", extra={"instance": self.instance_id, "code": code})

    # ── 수명주기 ──────────────────────────────────────────────────────────
    def start(self) -> None:
        self.register()

        def _loop() -> None:
            while not self._stop.wait(RENEWAL_S):
                try:
                    self.heartbeat()
                except Exception as e:        # 네트워크 순단이 서비스를 죽이면 안 됨
                    log.warning("eureka.heartbeat.error", extra={"error": str(e)})

        self._thread = threading.Thread(target=_loop, name="eureka-heartbeat", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        try:
            self.deregister()
        except Exception as e:
            log.warning("eureka.deregister.error", extra={"error": str(e)})

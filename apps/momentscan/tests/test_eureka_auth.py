"""Eureka Bearer 인증 (2026-07-15 회사 실측 요구) — TokenProvider 캐시·만료 마진,
_call의 Authorization 부착, 401→강제갱신 1회 재시도."""
import json
from unittest import mock

from momentscan.serve.eureka import EurekaClient, TokenProvider


def _provider_with(monkeypatch_target, responses):
    """urlopen을 스텁해 토큰 응답 시퀀스를 흘리는 TokenProvider."""
    tp = TokenProvider("http://accounts.test/oauth2/token", "cid", "sec")
    calls = {"n": 0}

    class _Resp:
        def __init__(self, body): self._b = json.dumps(body).encode()
        def read(self): return self._b
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=0):
        body = responses[min(calls["n"], len(responses) - 1)]
        calls["n"] += 1
        return _Resp(body)

    return tp, fake_urlopen, calls


def test_token_cached_within_margin():
    tp, fake, calls = _provider_with(None, [{"access_token": "T1", "expires_in": 3600}])
    with mock.patch("momentscan.serve.eureka.urllib.request.urlopen", fake):
        assert tp.token() == "T1"
        assert tp.token() == "T1"          # 캐시 — 재발급 없음
    assert calls["n"] == 1


def test_token_refresh_near_expiry():
    tp, fake, calls = _provider_with(None, [
        {"access_token": "T1", "expires_in": 30},   # TOKEN_MARGIN_S(60) 안 → 즉시 만료 취급
        {"access_token": "T2", "expires_in": 3600},
    ])
    with mock.patch("momentscan.serve.eureka.urllib.request.urlopen", fake):
        assert tp.token() == "T1"
        assert tp.token() == "T2"          # 마진 규칙이 재발급 강제
    assert calls["n"] == 2


def test_call_attaches_bearer_and_retries_once_on_401():
    tp = TokenProvider("http://accounts.test/oauth2/token", "cid", "sec")
    tokens = iter(["OLD", "NEW"])
    tp.token = lambda force_refresh=False: next(tokens)   # provider 스텁

    ec = EurekaClient("http://eureka.test/eureka", "momentscan", port=1,
                      host="1.2.3.4", token_provider=tp)
    seen = []

    def fake_do(method, path, body, token):
        seen.append(token)
        return 401 if token == "OLD" else 204              # 첫 토큰은 만료 → 401

    ec._do = fake_do
    assert ec._call("POST", "/apps/MOMENTSCAN", {}) == 204
    assert seen == ["OLD", "NEW"]                          # 정확히 1회 재시도


def test_call_no_auth_without_provider():
    ec = EurekaClient("http://eureka.test/eureka", "momentscan", port=1, host="1.2.3.4")
    captured = {}

    def fake_do(method, path, body, token):
        captured["token"] = token
        return 204

    ec._do = fake_do
    assert ec._call("PUT", "/apps/X/Y") == 204
    assert captured["token"] is None                       # 무-provider = 기존 무인증 경로 불변

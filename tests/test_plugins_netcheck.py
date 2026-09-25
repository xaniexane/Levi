"""Tests for levi.plugins.netcheck — the honest HTTP reachability probe.

Proofs: real answers only (status/latency/body peek from a fake
transport), deny-closed URL rules (scheme allow-list, no credentials in
URL, no host), timeout and body-cap bounds, and the credentialless
"public" sentinel. The network is faked by patching the opener builder —
no test touches the wire.
"""

from __future__ import annotations


import pytest

import levi.plugins.netcheck as netcheck_mod
from levi.plugins.netcheck import NetcheckConnector
from levi.plugins.registry import InvalidParams


class _Headers(dict):
    def items(self):
        return super().items()


class _FakeResponse:
    def __init__(
        self,
        status=200,
        reason="OK",
        body=b"hello world",
        url="http://example.com/",
        headers=None,
    ):
        self.status = status
        self.reason = reason
        self._body = body
        self._url = url
        self.headers = _Headers(headers or {"content-type": "text/plain"})

    def geturl(self):
        return self._url

    def read(self, n=-1):
        return self._body if n < 0 else self._body[:n]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_opener(monkeypatch, response):
    class _Opener:
        def open(self, request, timeout=None):
            return response

    monkeypatch.setattr(netcheck_mod.urllib.request, "build_opener", lambda: _Opener())


@pytest.fixture()
def conn():
    return NetcheckConnector()


def test_head_reports_real_status_and_latency(monkeypatch, conn):
    _fake_opener(monkeypatch, _FakeResponse(status=200, reason="OK"))
    result = conn.execute("head", {"url": "http://example.com/"})
    assert result.ok is True
    assert result.status == "ok"
    assert result.data["status"] == 200
    assert result.data["latency_ms"] >= 0
    assert result.data["requested_url"] == "http://example.com/"
    assert result.request_made is True


def test_get_returns_capped_body_peek(monkeypatch, conn):
    body = b"x" * 1000
    _fake_opener(monkeypatch, _FakeResponse(status=200, body=body))
    result = conn.execute("get", {"url": "https://example.com/big", "max_bytes": 64})
    assert result.ok is True
    assert result.data["truncated"] is True
    assert result.data["body_bytes"] == 64
    assert len(result.data["body_peek"]) <= 512


def test_error_status_is_an_honest_answer(monkeypatch, conn):
    _fake_opener(monkeypatch, _FakeResponse(status=404, reason="Not Found"))
    result = conn.execute("head", {"url": "http://example.com/nope"})
    assert result.ok is True  # the call worked; the server said 404
    assert result.data["status"] == 404
    assert result.data["ok"] is False


def test_ftp_scheme_refused(monkeypatch, conn):
    _fake_opener(monkeypatch, _FakeResponse())
    result = conn.execute("head", {"url": "ftp://example.com/x"})
    assert result.ok is False
    assert result.status == "invalid_params"
    assert result.request_made is False


def test_credentials_in_url_refused(monkeypatch, conn):
    _fake_opener(monkeypatch, _FakeResponse())
    result = conn.execute("head", {"url": "https://user:pass@example.com/"})
    assert result.ok is False
    assert result.status == "invalid_params"
    assert result.request_made is False


def test_missing_host_refused(monkeypatch, conn):
    _fake_opener(monkeypatch, _FakeResponse())
    result = conn.execute("get", {"url": "https://"})
    assert result.ok is False
    assert result.status == "invalid_params"


def test_timeout_bounds(monkeypatch, conn):
    _fake_opener(monkeypatch, _FakeResponse())
    for bad in (0, 0.5, 31, 9999):
        result = conn.execute(
            "head", {"url": "http://example.com/", "timeout_sec": bad}
        )
        assert result.ok is False and result.status == "invalid_params"


def test_max_bytes_bounds(monkeypatch, conn):
    _fake_opener(monkeypatch, _FakeResponse())
    for bad in (0, -1, 2_097_153, "lots"):
        result = conn.execute("get", {"url": "http://example.com/", "max_bytes": bad})
        assert result.ok is False and result.status == "invalid_params"


def test_unknown_operation_is_honest(monkeypatch, conn):
    _fake_opener(monkeypatch, _FakeResponse())
    result = conn.execute("ping", {"url": "http://example.com/"})
    assert result.ok is False
    assert result.status == "unknown_operation"
    assert result.request_made is False


def test_credentialless_by_design(conn):
    assert conn.credential() == "public"
    # never a write op, so confirmation can never gate
    assert all(not op.write for op in conn.operations)


def test_failure_raises_honest_api_error(monkeypatch, conn):
    import urllib.error

    class _FailOpener:
        def open(self, request, timeout=None):
            raise urllib.error.URLError("boom")

    monkeypatch.setattr(
        netcheck_mod.urllib.request, "build_opener", lambda: _FailOpener()
    )
    result = conn.execute("head", {"url": "http://example.com/"})
    assert result.ok is False
    assert result.status == "api_error"
    assert result.request_made is False


def test_guard_helpers_raise_invalid_params():
    with pytest.raises(InvalidParams):
        netcheck_mod._guarded_url("not a url")
    with pytest.raises(InvalidParams):
        netcheck_mod._guarded_url(None)
    with pytest.raises(InvalidParams):
        netcheck_mod._guarded_timeout("soon")

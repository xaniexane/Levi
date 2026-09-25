"""Webhook connector tests (hermetic, stdlib-only).

No test here touches the network: every success-path test injects a
fake transport; the missing-credential and confirmation gates are
exercised against the real ``execute()`` path.
"""

from __future__ import annotations

import pytest

import levi.plugins.webhook as webhook
from levi.plugins.registry import get_connector


@pytest.fixture()
def conn():
    connector = get_connector("webhook")
    assert connector is not None
    return connector


@pytest.fixture()
def env_url(monkeypatch):
    monkeypatch.setenv("LEVI_WEBHOOK_URL", "https://hooks.example.com/abc")
    yield "https://hooks.example.com/abc"
    monkeypatch.delenv("LEVI_WEBHOOK_URL", raising=False)


def test_registered_in_catalog(conn):
    assert conn.display_name == "Outbound Webhook"
    assert conn.credential_env_var == "LEVI_WEBHOOK_URL"
    # post is a write op → confirmation is forced at class-definition time.
    assert conn.requires_confirmation is True


def test_missing_credential_names_the_var(conn, monkeypatch):
    monkeypatch.delenv("LEVI_WEBHOOK_URL", raising=False)
    result = conn.execute("post", {"payload": {"a": 1}}, confirm=True)
    assert result.ok is False
    assert result.status == "missing_credential"
    assert "LEVI_WEBHOOK_URL" in result.message


def test_confirmation_gate(conn, env_url):
    result = conn.execute("post", {"payload": {"a": 1}})
    assert result.ok is False
    assert result.status == "confirmation_required"


def test_post_reaches_injected_transport(conn, env_url):
    calls = []

    def fake_transport(method, url, token, body):
        calls.append((method, url, body))
        return {"echo": "accepted"}

    result = conn.execute(
        "post",
        {"payload": {"hello": "world"}, "event": "levi.ping"},
        confirm=True,
        transport=fake_transport,
    )
    assert result.ok is True
    assert result.status == "ok"
    assert result.data["delivered"] is True
    assert result.data["echo"] == "accepted"
    assert len(calls) == 1
    method, url, body = calls[0]
    assert method == "POST"
    assert url == env_url
    # The bearer-secret URL must never be echoed back into the payload.
    assert env_url not in repr(body)


def test_invalid_url_refused(conn, monkeypatch):
    monkeypatch.setenv("LEVI_WEBHOOK_URL", "not-a-url")
    calls = []

    def fake_transport(method, url, token, body):
        calls.append(1)
        return {}

    result = conn.execute(
        "post", {"payload": {"a": 1}}, confirm=True, transport=fake_transport
    )
    assert result.ok is False
    assert result.status == "invalid_params"
    assert calls == []


def test_non_json_payload_refused(conn, env_url):
    result = conn.execute("post", {"payload": object()}, confirm=True)
    assert result.ok is False
    assert result.status == "invalid_params"


def test_missing_payload_refused(conn, env_url):
    result = conn.execute("post", {}, confirm=True)
    assert result.ok is False
    assert result.status == "invalid_params"


def test_forbidden_headers_refused(conn, env_url):
    result = conn.execute(
        "post",
        {"payload": {"a": 1}, "headers": {"Authorization": "Bearer x"}},
        confirm=True,
    )
    assert result.ok is False
    assert result.status == "invalid_params"


def test_transport_failure_is_api_error_not_simulated_success(conn, env_url):
    def boom(method, url, token, body):
        raise webhook.ConnectorAPIError("target down")

    result = conn.execute("post", {"payload": {"a": 1}}, confirm=True, transport=boom)
    assert result.ok is False
    assert result.status == "api_error"
    # The bearer-secret URL must never leak into the message.
    assert env_url not in result.message


def test_default_transport_refuses_without_network(monkeypatch, conn):
    # Blank URL → invalid_params before any network access.
    monkeypatch.setenv("LEVI_WEBHOOK_URL", "   ")
    result = conn.execute("post", {"payload": {"a": 1}}, confirm=True)
    assert result.ok is False
    assert result.status == "missing_credential"

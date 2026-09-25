"""Contract tests for the plugin connector registry (blueprint §1.5, §3).

Hermetic: no network, no HOME writes. A fake transport stands in for the
real one; the point under test is that ``execute()`` is honest by
construction — it must never simulate success.
"""

import pytest

from levi.plugins.registry import (
    Capability,
    Connector,
    Operation,
    get_connector,
    list_connectors,
    register_connector,
)


class _ReadStub(Connector):
    id = "stub-read"
    display_name = "Read Stub"
    credential_env_var = "LEVI_TEST_STUB_TOKEN"
    capabilities = (Capability("read.thing", "Reads things"),)
    operations = (Operation("ping", "Returns pong", params=()),)

    def perform(self, operation, params, token, transport):
        if transport is not None:
            return transport("GET", "/ping", token, None)
        return {"pong": True}


class _UnwiredStub(Connector):
    """Has a credential but never wired ``_call_api`` — the base raises
    TransportNotWired."""

    id = "stub-unwired"
    display_name = "Unwired Stub"
    credential_env_var = "LEVI_TEST_UNWIRED_TOKEN"
    capabilities = (Capability("read.thing", "Reads things"),)
    operations = (Operation("ping", "Returns pong", params=()),)

    def perform(self, operation, params, token, transport):
        if transport is not None:
            return transport("GET", "/ping", token, None)
        return self._call_api("GET", "/ping", token)


class _WriteStub(Connector):
    id = "stub-write"
    display_name = "Write Stub"
    credential_env_var = "LEVI_TEST_WRITE_TOKEN"
    capabilities = (Capability("write.thing", "Writes things", write=True),)
    operations = (Operation("do_write", "Writes a thing", write=True, params=()),)
    # A deliberate attempt to opt out — the registry must force this True.
    requires_confirmation = False

    def perform(self, operation, params, token, transport):
        if transport is not None:
            return transport("POST", "/write", token, {})
        return self._call_api("POST", "/write", token, {})


class _FakeTransport:
    def __init__(self):
        self.calls = []

    def __call__(self, method, path, token, body):
        self.calls.append(
            {"method": method, "path": path, "token": token, "body": body}
        )
        return {"ok": True}


# -- missing credential ----------------------------------------------------


def test_missing_credential_states_exactly_what_is_missing(monkeypatch):
    monkeypatch.delenv("LEVI_TEST_STUB_TOKEN", raising=False)
    fake = _FakeTransport()
    res = _ReadStub().execute("ping", transport=fake)
    assert not res.ok
    assert res.status == "missing_credential"
    assert "set LEVI_TEST_STUB_TOKEN" in res.message
    assert not res.request_made
    assert res.data is None
    assert fake.calls == [], "nothing may be sent without a credential"


def test_blank_credential_counts_as_missing(monkeypatch):
    monkeypatch.setenv("LEVI_TEST_STUB_TOKEN", "   ")
    fake = _FakeTransport()
    res = _ReadStub().execute("ping", transport=fake)
    assert not res.ok and res.status == "missing_credential"
    assert fake.calls == []


# -- confirmation gate -----------------------------------------------------


def test_write_capability_forces_requires_confirmation():
    # Blueprint §1.5: no per-feature override — the class body said False,
    # the registry forced it True.
    assert _WriteStub.requires_confirmation is True


def test_write_without_confirm_is_refused_and_sends_nothing(monkeypatch):
    monkeypatch.setenv("LEVI_TEST_WRITE_TOKEN", "sekret")
    fake = _FakeTransport()
    res = _WriteStub().execute("do_write", transport=fake)
    assert not res.ok
    assert res.status == "confirmation_required"
    assert not res.request_made
    assert fake.calls == [], "a write must never reach the transport unconfirmed"


def test_write_with_confirm_reaches_transport(monkeypatch):
    monkeypatch.setenv("LEVI_TEST_WRITE_TOKEN", "sekret")
    fake = _FakeTransport()
    res = _WriteStub().execute("do_write", confirm=True, transport=fake)
    assert res.ok and res.status == "ok"
    assert res.request_made
    assert fake.calls[0]["method"] == "POST"
    assert fake.calls[0]["token"] == "sekret"


def test_read_does_not_require_confirmation(monkeypatch):
    monkeypatch.setenv("LEVI_TEST_STUB_TOKEN", "sekret")
    fake = _FakeTransport()
    res = _ReadStub().execute("ping", transport=fake)
    assert res.ok
    assert fake.calls[0]["method"] == "GET"


# -- transport not wired ----------------------------------------------------


def test_credential_but_no_transport_is_stated_plainly(monkeypatch):
    monkeypatch.setenv("LEVI_TEST_UNWIRED_TOKEN", "sekret")
    res = _UnwiredStub().execute("ping")  # no transport injected
    assert not res.ok
    assert res.status == "transport_not_wired"
    assert "no transport is wired" in res.message
    assert "nothing was sent" in res.message
    assert not res.request_made


# -- unknown operations -----------------------------------------------------


def test_unknown_operation_sends_nothing(monkeypatch):
    monkeypatch.setenv("LEVI_TEST_STUB_TOKEN", "sekret")
    fake = _FakeTransport()
    res = _ReadStub().execute("nope", transport=fake)
    assert not res.ok
    assert res.status == "unknown_operation"
    assert "nope" in res.message
    assert fake.calls == []


# -- registry ---------------------------------------------------------------


def test_registry_registers_lists_and_gets():
    register_connector(_WriteStub)
    assert get_connector("stub-write").id == "stub-write"
    assert get_connector("does-not-exist") is None
    assert "stub-write" in {c.id for c in list_connectors()}


def test_registry_rejects_connector_without_credential_env_var():
    class _Bad(Connector):
        id = "stub-bad"

        def perform(self, operation, params, token, transport):
            return {}

    with pytest.raises(ValueError, match="credential_env_var"):
        register_connector(_Bad)


def test_execute_validates_call_shape_before_anything(monkeypatch):
    monkeypatch.setenv("LEVI_TEST_STUB_TOKEN", "tok")
    c = _ReadStub()

    res = c.execute("", {})
    assert res.ok is False and res.status == "invalid_params"
    assert res.request_made is False

    res = c.execute("ping", "not-a-dict")  # type: ignore[arg-type]
    assert res.ok is False and res.status == "invalid_params"

    res = c.execute("ping", {}, confirm="yes")  # type: ignore[arg-type]
    assert res.ok is False and res.status == "invalid_params"

    res = c.execute("ping", {}, transport="nope")  # type: ignore[arg-type]
    assert res.ok is False and res.status == "invalid_params"


def test_execute_turns_unexpected_connector_failure_into_safe_result(monkeypatch):
    class _Boom(_ReadStub):
        id = "stub-boom"

        def perform(self, operation, params, token, transport):
            # Exception text may carry secrets (URLs, headers, bodies) —
            # it must never reach the result message.
            raise RuntimeError("kaboom: bearer tok")

    monkeypatch.setenv("LEVI_TEST_STUB_TOKEN", "tok")
    res = _Boom().execute("ping", {})
    assert res.ok is False
    assert res.status == "internal_error"
    assert "RuntimeError" in res.message
    assert "kaboom" not in res.message
    assert "tok" not in res.message
    assert res.request_made is False

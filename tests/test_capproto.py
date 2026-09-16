"""Hermetic tests for levi.capproto — no network beyond local sockets,
tmp HOME, shared per-test telescript secret via env var."""

import json
import os

import pytest

from levi.capproto import SHELF
from levi.capproto.demo import build_kvnote_service, run_demo
from levi.capproto.protocol import (
    ProtocolError,
    ServiceSpec,
    error_response,
    msg_call,
    msg_hello,
    ok_response,
    validate_message,
)
from levi.capproto.tokens import (
    AttenuationError,
    MintLedger,
    attenuate,
    decode,
    default_home,
)
from levi.capproto.transport import CapCallError, CapClient, CapServer
from levi.revival.telescript import (
    ActionRefused,
    ExpiredToken,
    InvalidSignature,
    issue,
    permits,
    verify,
)


@pytest.fixture()
def secret(monkeypatch):
    monkeypatch.setenv("LEVI_TELESCRIPT_SECRET", "test-secret-capproto")


@pytest.fixture()
def herm_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LEVI_HOME", raising=False)
    return tmp_path / ".levi" / "capproto"


def _broad(secret):
    return issue("issuer", "grantee", ["kvnote.get", "kvnote.put", "kvnote.list"],
                 ttl_seconds=300)


# -- shelf -----------------------------------------------------------------

def test_shelf_shape():
    assert SHELF["name"] and SHELF["summary"] and len(SHELF["items"]) >= 4


# -- attenuation -----------------------------------------------------------

def test_attenuate_narrows(secret):
    child = attenuate(_broad(secret), actions=["kvnote.get"], ttl_seconds=60)
    cap = verify(child)
    assert list(cap.actions) == ["kvnote.get"]
    assert cap.issuer == "issuer" and cap.grantee == "grantee"


def test_attenuate_refuses_widening_pattern(secret):
    with pytest.raises(AttenuationError):
        attenuate(_broad(secret), actions=["kvnote.get", "kvnote.del"])


def test_attenuate_refuses_longer_ttl(secret):
    with pytest.raises(AttenuationError):
        attenuate(_broad(secret), ttl_seconds=3600)


def test_attenuate_refuses_bad_parent(secret):
    with pytest.raises(Exception):
        attenuate("not.a.token", actions=["kvnote.get"])


def test_attenuate_chains(secret):
    c1 = attenuate(_broad(secret), actions=["kvnote.get", "kvnote.list"])
    c2 = attenuate(c1, actions=["kvnote.get"], ttl_seconds=30)
    cap = verify(c2)
    assert list(cap.actions) == ["kvnote.get"]


def test_attenuate_default_keeps_parent_actions(secret):
    child = attenuate(_broad(secret), ttl_seconds=60)
    assert set(verify(child).actions) == {"kvnote.get", "kvnote.put", "kvnote.list"}


def test_decode_is_untrusted_view(secret):
    claims = decode(_broad(secret))
    assert claims["iss"] == "issuer" and claims["sub"] == "grantee"
    # tampered copy still "decodes" — verification is what refuses it
    bad = _broad(secret)[:-2] + "xx"
    decode(bad)
    with pytest.raises(InvalidSignature):
        verify(bad)


# -- ledger ----------------------------------------------------------------

def test_ledger_records_and_rebuilds_revocations(secret, herm_home):
    ledger = MintLedger(herm_home)
    tok = _broad(secret)
    ledger.record_issued(tok)
    child = attenuate(tok, actions=["kvnote.get"], ledger=ledger)
    ledger.record_revoked(child)
    events = [e["event"] for e in ledger.entries()]
    assert events == ["issued", "attenuated", "revoked"]
    rl = ledger.revocation_list()
    assert len(rl) == 1
    with pytest.raises(Exception):
        verify(child, revocations=rl)


def test_ledger_home_is_owner_only(secret, herm_home):
    MintLedger(herm_home)
    assert herm_home.stat().st_mode & 0o777 == 0o700


# -- protocol messages -----------------------------------------------------

def test_message_validation(secret):
    m = validate_message(msg_call("kvnote", "get", "tok"))
    assert m["v"] == "capproto/1"
    with pytest.raises(ProtocolError):
        validate_message({"v": "capproto/9", "id": "x", "op": "bye"})
    with pytest.raises(ProtocolError):
        validate_message(msg_hello("agent") | {"op": "nuke"})
    with pytest.raises(ProtocolError):
        validate_message({"v": "capproto/1"})  # no op


def test_responses_shape():
    ok = ok_response("i1", {"a": 1})
    assert ok["ok"] is True and ok["id"] == "i1"
    err = error_response("i2", "refused", "no")
    assert err["ok"] is False and err["error_type"] == "refused"
    # unknown error types are coerced, never invented
    assert error_response("i3", "mystery", "x")["error_type"] == "server"


# -- service dispatch ------------------------------------------------------

def _spec():
    spec = ServiceSpec("demo")
    spec.add_verb("ping", lambda: {"pong": True}, summary="ping")
    spec.add_verb("echo", lambda text: {"text": text}, required_args=["text"])
    return spec


def test_dispatch_gates_by_capability(secret):
    spec = _spec()
    tok = issue("i", "g", ["demo.ping"], ttl_seconds=60)
    assert spec.dispatch("ping", tok, {}) == {"pong": True}
    with pytest.raises(ActionRefused):
        spec.dispatch("echo", tok, {"text": "hi"})


def test_dispatch_unknown_verb_and_bad_args(secret):
    spec = _spec()
    tok = issue("i", "g", ["demo.*"], ttl_seconds=60)
    with pytest.raises(ProtocolError):
        spec.dispatch("nope", tok, {})
    with pytest.raises(ProtocolError):
        spec.dispatch("echo", tok, {})


def test_dispatch_refuses_expired(secret):
    spec = _spec()
    tok = issue("i", "g", ["demo.ping"], ttl_seconds=-1)
    with pytest.raises(ExpiredToken):
        spec.dispatch("ping", tok, {})


def test_service_revoke(secret):
    spec = _spec()
    tok = issue("i", "g", ["demo.ping"], ttl_seconds=600)
    spec.revoke_token(tok)
    with pytest.raises(Exception):
        spec.dispatch("ping", tok, {})


# -- transport roundtrip ---------------------------------------------------

def test_socket_roundtrip_refusals(secret, herm_home):
    spec = build_kvnote_service()
    server = CapServer(spec, home=herm_home).start()
    client = CapClient(home=herm_home, name="kvnote").connect()
    try:
        hello = client.hello("tester")
        assert "kvnote" in hello["service"]["service"]
        broad = issue("i", "g", ["kvnote.put", "kvnote.get"], ttl_seconds=300)
        assert client.call("kvnote", "put", broad, {"key": "k", "value": "v"})["stored"] is True
        narrow = attenuate(broad, actions=["kvnote.get"])
        with pytest.raises(CapCallError) as ei:
            client.call("kvnote", "put", narrow, {"key": "k", "value": "v"})
        assert ei.value.error_type == "refused"
        assert client.call("kvnote", "get", narrow, {"key": "k"})["value"] == "v"
        with pytest.raises(CapCallError) as ei2:
            client.call("kvnote", "nope", broad, {})
        assert ei2.value.error_type == "unknown_verb"
    finally:
        client.close()
        server.stop()


def test_demo_runs_end_to_end(secret, herm_home):
    lines = run_demo(herm_home)
    text = "\n".join(lines)
    assert "attenuated to read-only" in text
    assert "refused as designed" in text
    assert "revoked token refused" in text


def test_client_no_endpoint(secret, herm_home):
    client = CapClient(home=herm_home, name="nothing-here")
    with pytest.raises(Exception):
        client.connect()


# -- CLI -------------------------------------------------------------------

def test_cli_issue_verify_attenuate(secret, herm_home, capsys, monkeypatch):
    from levi.capproto.__main__ import main

    monkeypatch.setenv("LEVI_HOME", str(herm_home.parent))
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0
    capsys.readouterr()  # drain --help usage text
    assert main(["issue", "--issuer", "i", "--grantee", "g",
                 "--action", "kvnote.get", "--ttl", "120"]) == 0
    token = capsys.readouterr().out.strip()
    assert token.count(".") == 1
    assert main(["verify", "--token", token]) == 0
    out = capsys.readouterr().out
    assert '"iss": "i"' in out
    assert main(["attenuate", "--token", token, "--action", "kvnote.get",
                 "--ttl", "30"]) == 0
    child = capsys.readouterr().out.strip()
    # widening must fail with exit 1
    assert main(["attenuate", "--token", child, "--action", "kvnote.put"]) == 1
    assert main(["verify", "--token", "garbage"]) == 1


def test_cli_demo(secret, herm_home, capsys, monkeypatch):
    from levi.capproto.__main__ import main

    monkeypatch.setenv("LEVI_HOME", str(herm_home.parent))
    assert main(["demo"]) == 0
    assert "endpoint:" in capsys.readouterr().out

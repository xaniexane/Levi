"""Hermetic tests for revival.telescript (capability-bounded execution).

No network, no HOME dependence, deterministic. The per-process HMAC secret
is regenerated per test via reset_process_secret() so tokens never leak
across tests.
"""

import time

import pytest

from core.levi.revival import telescript as ts


@pytest.fixture(autouse=True)
def _fresh_secret():
    ts.reset_process_secret()
    yield
    ts.reset_process_secret()


def _cap(**kw):
    kw.setdefault("issuer", "levi")
    kw.setdefault("grantee", "agent-1")
    kw.setdefault("actions", ["memory.store", "memory.recall"])
    kw.setdefault("ttl_seconds", 60)
    return ts.issue(**kw)


# -- grant / verify round trip ------------------------------------------------


def test_issue_verify_round_trip():
    token = _cap()
    cap = ts.verify(token, expected_grantee="agent-1")
    assert cap.issuer == "levi"
    assert cap.grantee == "agent-1"
    assert cap.actions == ("memory.store", "memory.recall")
    assert not cap.is_expired()


def test_empty_actions_is_deny_closed():
    token = _cap(actions=[])
    cap = ts.verify(token)
    assert not ts.permits(cap, "anything.at.all")


# -- fail-closed refusals -----------------------------------------------------


def test_malformed_token_refused():
    for bad in ("", "no-dot-here", "a.b.c", "!!!.!!!", "."):
        with pytest.raises(ts.CapabilityError):
            ts.verify(bad)


def test_tampered_payload_refused():
    token = _cap()
    payload, sig = token.split(".")
    tampered = payload[:-2] + ("AA" if not payload.endswith("AA") else "BB")
    with pytest.raises(ts.InvalidSignature):
        ts.verify(tampered + "." + sig)


def test_tampered_signature_refused():
    token = _cap()
    payload, sig = token.split(".")
    bad_sig = ("A" * len(sig)) if not sig.startswith("A") else ("B" * len(sig))
    with pytest.raises(ts.InvalidSignature):
        ts.verify(payload + "." + bad_sig)


def test_expired_token_refused():
    token = _cap(ttl_seconds=-1)
    with pytest.raises(ts.ExpiredToken):
        ts.verify(token)


def test_expiry_boundary():
    token = _cap(ttl_seconds=10)
    with pytest.raises(ts.ExpiredToken):
        ts.verify(token, now=time.time() + 11)
    ts.verify(token, now=time.time() + 5)  # still valid


def test_wrong_grantee_refused():
    token = _cap(grantee="agent-1")
    with pytest.raises(ts.WrongGrantee):
        ts.verify(token, expected_grantee="agent-2")


def test_token_from_other_secret_refused():
    token = _cap()
    ts.reset_process_secret()  # different secret now
    with pytest.raises(ts.InvalidSignature):
        ts.verify(token)


def test_invalid_pattern_rejected_at_issue():
    with pytest.raises(ValueError):
        ts.issue("levi", "agent-1", ["re:([broken"], ttl_seconds=60)
    with pytest.raises(ValueError):
        ts.issue("levi", "agent-1", [""], ttl_seconds=60)


# -- action patterns ----------------------------------------------------------


def test_exact_and_wildcard_patterns():
    cap = ts.verify(ts.issue("levi", "a", ["memory.store", "tool.*"], ttl_seconds=60))
    assert ts.permits(cap, "memory.store")
    assert ts.permits(cap, "tool.exec")
    assert ts.permits(cap, "tool.")
    assert not ts.permits(cap, "memory.recall")
    assert not ts.permits(cap, "other.exec")


def test_regex_patterns():
    cap = ts.verify(
        ts.issue("levi", "a", [r"re:^memory\.(store|recall)$"], ttl_seconds=60)
    )
    assert ts.permits(cap, "memory.store")
    assert ts.permits(cap, "memory.recall")
    assert not ts.permits(cap, "memory.store.extra")
    assert not ts.permits(cap, "xmemory.store")


def test_bare_star_matches_everything():
    cap = ts.verify(ts.issue("levi", "a", ["*"], ttl_seconds=60))
    assert ts.permits(cap, "anything.at.all")


def test_non_string_action_never_permits():
    cap = ts.verify(_cap())
    assert not ts.permits(cap, "")
    assert not ts.permits(cap, None)  # type: ignore[arg-type]


# -- revocation ---------------------------------------------------------------


def test_revoked_token_refused():
    token = _cap()
    rl = ts.RevocationList()
    ts.verify(token, revocations=rl)  # fine before revocation
    rl.revoke(token)
    with pytest.raises(ts.RevokedToken):
        ts.verify(token, revocations=rl)


def test_revoke_by_nonce():
    token = _cap()
    cap = ts.verify(token)
    rl = ts.RevocationList()
    rl.revoke(cap.nonce)
    assert len(rl) == 1
    with pytest.raises(ts.RevokedToken):
        ts.verify(token, revocations=rl)


# -- guarded_call --------------------------------------------------------------


def test_guarded_call_executes_when_permitted():
    token = _cap()
    calls = []

    def tool(x, y=0):
        calls.append((x, y))
        return x + y

    assert ts.guarded_call(token, "memory.store", tool, 2, y=3) == 5
    assert calls == [(2, 3)]


def test_guarded_call_refuses_unpermitted_action():
    token = _cap()
    called = []

    def tool():
        called.append(True)

    with pytest.raises(ts.ActionRefused):
        ts.guarded_call(token, "vault.export", tool)
    assert called == []  # tool NEVER ran


def test_guarded_call_refuses_bad_token_without_running():
    called = []

    def tool():
        called.append(True)

    with pytest.raises(ts.CapabilityError):
        ts.guarded_call("garbage", "memory.store", tool)
    assert called == []


def test_guarded_call_enforces_grantee_and_revocation():
    token = _cap(grantee="agent-1")
    with pytest.raises(ts.WrongGrantee):
        ts.guarded_call(token, "memory.store", lambda: None, expected_grantee="agent-9")
    rl = ts.RevocationList()
    rl.revoke(token)
    with pytest.raises(ts.RevokedToken):
        ts.guarded_call(token, "memory.store", lambda: None, revocations=rl)


def test_tool_errors_propagate_unchanged():
    token = _cap()

    def boom():
        raise RuntimeError("tool blew up")

    with pytest.raises(RuntimeError, match="tool blew up"):
        ts.guarded_call(token, "memory.store", boom)


def test_guarded_executor_uses_first_permitting_token():
    t1 = ts.issue("levi", "agent-1", ["a.one"], ttl_seconds=60)
    t2 = ts.issue("levi", "agent-1", ["b.two"], ttl_seconds=60)
    ex = ts.GuardedExecutor(grantee="agent-1", tokens=[t1, t2])
    assert ex.call("b.two", lambda: "ran-b") == "ran-b"
    with pytest.raises(ts.ActionRefused):
        ex.call("c.three", lambda: "nope")

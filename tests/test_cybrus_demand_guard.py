"""Invariant tests for the Cybrus DemandPulse guard (levi.cybrus.demand_guard).

The PROOF gate for laws DG1-DG6 — machine-checked invariants, honestly
named: nothing here is formally proven, only tested against the laws.

Hermetic: LEVI_HOME is monkeypatched to a tmp dir — no real HOME
writes, no network. Includes the RED-team assertions: grant forgery on
the store, alert-path spoofing, and a compromised DemandPulse trying to
command Cybrus (must fail — DG5).
"""

import json

import pytest

from levi.cybrus import demand_guard as dg
from levi.cybrus.audit import AuditEngine
from levi.cybrus.demand_guard import (
    DemandGuardError,
    GuardedDemandStore,
    require_grant,
)
from levi.cybrus.tokens import TokenEngine


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture()
def store(tmp_path):
    return GuardedDemandStore(
        path=tmp_path / "demand_pulse.json",
        alert_path=tmp_path / "demand_alerts.json",
    )


def _issue(scope, ttl=3600, kind="api"):
    token_id, plaintext = TokenEngine().issue(
        scopes=[scope], ttl_seconds=ttl, kind=kind, label=f"test:{scope}"
    )
    return token_id, plaintext


def _audit_tail(n=50):
    return AuditEngine().tail(n)


# --- DG1: no read without a grant receipt ---------------------------------


def test_laws_declared(home):
    assert [lid for lid, _ in dg.LAWS] == ["DG1", "DG2", "DG3", "DG4", "DG5", "DG6"]


def test_read_without_credential_refused(home, store):
    with pytest.raises(DemandGuardError):
        store.authorize(None, dg.SCOPE_READ)
    with pytest.raises(DemandGuardError):
        store.authorize("", dg.SCOPE_READ)


def test_read_with_forged_token_refused(home, store):
    # RED: a made-up token string is not a grant receipt.
    with pytest.raises(DemandGuardError):
        store.authorize("forged-token-not-issued-by-cybrus", dg.SCOPE_READ)


def test_read_with_wrong_scope_refused(home, store):
    _, write_tok = _issue(dg.SCOPE_WRITE)
    with pytest.raises(DemandGuardError):
        store.authorize(write_tok, dg.SCOPE_READ)


def test_read_with_revoked_grant_refused(home, store):
    token_id, tok = _issue(dg.SCOPE_READ)
    TokenEngine().revoke(token_id)
    with pytest.raises(DemandGuardError):
        store.authorize(tok, dg.SCOPE_READ)


def test_read_with_expired_grant_refused(home, store, monkeypatch):
    _, tok = _issue(dg.SCOPE_READ, ttl=60)
    import levi.cybrus.tokens as tokens_mod

    real_now = tokens_mod._now
    monkeypatch.setattr(tokens_mod, "_now", lambda: real_now() + 3600)
    with pytest.raises(DemandGuardError):
        store.authorize(tok, dg.SCOPE_READ)


def test_session_token_cannot_hold_demand_grant(home, store):
    _, tok = _issue(dg.SCOPE_READ, kind="session")
    with pytest.raises(DemandGuardError):
        store.authorize(tok, dg.SCOPE_READ)


def test_read_with_valid_grant(home, store):
    _, tok = _issue(dg.SCOPE_READ)
    handle = store.authorize(tok, dg.SCOPE_READ)
    doc = handle.read()
    assert isinstance(doc, dict)
    events = [e for e in _audit_tail() if e["event"] == "demand.store.read"]
    assert events, "reads must be audit-logged"


# --- DG2: no write without a write grant receipt ----------------------------


def test_write_with_read_grant_refused(home, store):
    _, tok = _issue(dg.SCOPE_READ)
    handle = store.authorize(tok, dg.SCOPE_READ)
    with pytest.raises(DemandGuardError):
        handle.write({"signals": []})


def test_write_with_write_grant(home, store):
    _, tok = _issue(dg.SCOPE_WRITE)
    handle = store.authorize(tok, dg.SCOPE_WRITE)
    secret_text = "need-text-that-must-never-hit-the-audit-log-xyzzy"
    result = handle.write({"signals": [{"id": "s1", "need": secret_text}]})
    assert result["ok"] is True
    # Round-trip through a fresh read handle.
    _, rtok = _issue(dg.SCOPE_READ)
    doc = store.authorize(rtok, dg.SCOPE_READ).read()
    assert doc["signals"][0]["need"] == secret_text
    # L4: audit carries digests, never content.
    writes = [e for e in _audit_tail() if e["event"] == "demand.store.write"]
    assert writes and writes[-1]["details"]["doc_digest"] == result["doc_digest"][:16]
    blob = json.dumps(_audit_tail())
    assert secret_text not in blob


def test_append_signal_needs_write_grant(home, store):
    _, rtok = _issue(dg.SCOPE_READ)
    handle = store.authorize(rtok, dg.SCOPE_READ)
    with pytest.raises(DemandGuardError):
        handle.append_signal({"id": "x"})
    _, wtok = _issue(dg.SCOPE_WRITE)
    out = store.authorize(wtok, dg.SCOPE_WRITE).append_signal({"id": "x"})
    assert out["signal_count"] == 1


def test_scan_seed_items_needs_write_grant(home, store):
    _, rtok = _issue(dg.SCOPE_READ)
    with pytest.raises(DemandGuardError):
        store.authorize(rtok, dg.SCOPE_READ).scan_seed_items(
            [{"text": "need a plumber", "segment": "home", "source": "scan"}]
        )
    _, wtok = _issue(dg.SCOPE_WRITE)
    out = store.authorize(wtok, dg.SCOPE_WRITE).scan_seed_items(
        [{"text": "need a plumber", "segment": "home", "source": "scan"}]
    )
    assert out["ok"] and len(out["seeded"]) == 1
    # Watcher law L3 holds through the guard: everything stays HYPOTHESIS.
    _, rtok2 = _issue(dg.SCOPE_READ)
    doc = store.authorize(rtok2, dg.SCOPE_READ).read()
    assert doc["signals"][0]["kind"] == "HYPOTHESIS"


def test_admin_grant_covers_read_and_write(home, store):
    _, tok = _issue(dg.SCOPE_ADMIN)
    handle = store.authorize(tok, dg.SCOPE_READ)
    handle.read()
    handle2 = store.authorize(tok, dg.SCOPE_WRITE)
    handle2.write({"signals": []})


# --- DG3: alert emission needs an alert grant, and is always audit-logged --


def test_emit_alert_without_alert_grant_refused(home, store):
    _, wtok = _issue(dg.SCOPE_WRITE)
    handle = store.authorize(wtok, dg.SCOPE_WRITE)
    with pytest.raises(DemandGuardError):
        handle.emit_alert("test", "nope")


def test_emit_alert_audit_logged_metadata_only(home, store):
    _, tok = _issue(dg.SCOPE_ALERT)
    handle = store.authorize(tok, dg.SCOPE_ALERT)
    body = "alert-body-supersecret-must-not-hit-audit-xyzzy"
    out = handle.emit_alert("threshold", "price-spike", message=body)
    assert out["ok"] and out["alert_id"]
    emitted = [e for e in _audit_tail() if e["event"] == "demand.alert.emitted"]
    assert emitted, "every alert emission must be audit-logged"
    details = emitted[-1]["details"]
    assert details["kind"] == "threshold" and details["name"] == "price-spike"
    assert "message" not in details
    assert body not in json.dumps(_audit_tail())


# --- DG4: receipts re-validated per call ------------------------------------


def test_receipt_revalidated_every_call(home, store, monkeypatch):
    _, tok = _issue(dg.SCOPE_READ, ttl=60)
    handle = store.authorize(tok, dg.SCOPE_READ)
    handle.read()  # fine while valid
    import levi.cybrus.tokens as tokens_mod

    real_now = tokens_mod._now
    monkeypatch.setattr(tokens_mod, "_now", lambda: real_now() + 3600)
    with pytest.raises(DemandGuardError):
        handle.read()  # same handle, receipt now expired -> refused


# --- DG5: scope confinement — a compromised DemandPulse cannot command Cybrus


def test_demand_grant_cannot_route_service_calls(home):
    from levi.cybrus import enforce

    _, tok = _issue(dg.SCOPE_WRITE)
    with pytest.raises(enforce.NotAuthenticated):
        enforce.route_service_call(
            "demandpulse", "levi.knowledge", "search", credential=tok
        )


def test_demand_grant_cannot_request_egress(home):
    from levi.cybrus import enforce

    _, tok = _issue(dg.SCOPE_ADMIN)
    with pytest.raises(enforce.NotAuthenticated):
        enforce.request_egress(
            "demandpulse", "https://example.com", "exfiltrate", credential=tok
        )


def test_cybrus_routing_grant_refused_by_demand_guard(home, store):
    # The reverse direction: a Cybrus routing grant is meaningless here.
    _, tok = TokenEngine().issue(scopes=["route.external"], ttl_seconds=60)
    with pytest.raises(DemandGuardError):
        require_grant(tok, dg.SCOPE_READ)


# --- posture -----------------------------------------------------------------


def test_describe_posture(home):
    p = dg.describe_posture()
    assert p["mints_grants"] is False
    assert p["directs_demandpulse"] is False
    assert p["laws"] == ["DG1", "DG2", "DG3", "DG4", "DG5", "DG6"]

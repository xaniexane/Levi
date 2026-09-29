"""Proof for the bloodline metering laws (broker_meter.py).

M1 NO-SELF-MINT · M2 FOUNDER-FULFILL · M3 METERED · M4
ENTITLEMENT-BEFORE-USE · M5 AUDIT · M6 SINGLE-FULFILL.
"""

from __future__ import annotations

import json

import pytest

from levi.cybrus import BrokerApprovalRequired, CredentialBroker
from levi.cybrus import broker_meter as m
from levi.cybrus.approval import ApprovalEngine
from levi.cybrus.audit import AuditEngine
from levi.cybrus.broker_meter import MeterError


@pytest.fixture(autouse=True)
def _levi_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    from levi.cybrus import rate_limits

    rate_limits.set_tier("alice", "pro")
    rate_limits.set_tier("spawn1", "free")  # limited bloodline derivative
    yield tmp_path


def _run_gated(fn):
    try:
        return fn()
    except BrokerApprovalRequired as exc:
        ApprovalEngine().approve(exc.approval_id, by="tester")
        return fn()


def _make_session(name="chauncey-ops"):
    from levi.cybrus.factory import generate_password, hash_password
    from levi.cybrus.founder_gateway import FounderSession
    from levi.cybrus.gateway import CybrusGateway
    from levi.cybrus.identity import IdentityStore

    store = IdentityStore()
    if not store.exists(name):
        store.create(name, tier="pro")
    pw = generate_password(20)
    store.set_credential(name, hash_password(pw))
    gw = CybrusGateway()
    return FounderSession.authenticate(name, pw, gateway=gw), gw


def _audit_text():
    ok, _ = AuditEngine().verify()
    assert ok, "audit hash chain must verify"
    return "\n".join(
        json.dumps(rec.get("details", {}), sort_keys=True)
        for rec in AuditEngine().tail(500)
    )


# -- M1: a request is a ticket, never a mint ------------------------------------


def test_m1_request_files_ticket_and_mints_nothing():
    req = m.request_service("spawn1", "github", "https://github.com/signup")
    assert req["status"] == "pending"
    assert req["requestor"] == "spawn1"
    # Nothing minted: no accounts, no vault entries for the requestor.
    assert CredentialBroker("keeper-pw").list_accounts(identity="spawn1") == []
    # The ticket store carries metadata only.
    assert "keeper-pw" not in json.dumps(m.list_service_requests())
    # Founder names cannot request through themselves.
    with pytest.raises(MeterError, match="founder"):
        m.request_service("chauncey", "github", "https://github.com/signup")


# -- M2: fulfillment is founder-only ---------------------------------------------


def test_m2_fulfill_and_deny_require_live_session():
    req = m.request_service("spawn1", "github", "https://github.com/signup")
    with pytest.raises(MeterError, match="FounderSession"):
        m.fulfill_service_request(req["id"], session="not-a-session", vault_passphrase="x")
    with pytest.raises(MeterError, match="FounderSession"):
        m.fulfill_service_request(req["id"], session=None, vault_passphrase="x")
    with pytest.raises(MeterError, match="FounderSession"):
        m.deny_service_request(req["id"], session=None, reason="no")
    # Still pending — the refused attempts changed nothing.
    assert m.get_service_request(req["id"])["status"] == "pending"


# -- M3/M5/M6: the full service flow ----------------------------------------------


def test_m3_m5_m6_fulfill_mints_meters_audits_once():
    session, _gw = _make_session()
    req = m.request_service("spawn1", "github", "https://github.com/signup")
    # spawn1 is free tier: it can never mint directly ...
    br = CredentialBroker("keeper-pw")
    with pytest.raises(BrokerApprovalRequired):
        br.provision("github", "https://github.com/signup", identity="spawn1")
    # ... but the founder's service can provision for it.
    record, password = _run_gated(
        lambda: m.fulfill_service_request(req["id"], session, "keeper-pw")
    )
    assert record["identity"] == "spawn1"
    assert record["platform"] == "github"
    assert isinstance(password, str) and len(password) >= 16

    # M3: the requestor's meter is charged for the founder-fulfilled mint.
    reading = m.meter_reading("spawn1", "account_create")
    assert reading["used_lifetime"] >= 1
    assert reading["tier"] == "free"
    assert reading["unlimited"] is False

    # M6: a second terminal transition fails.
    with pytest.raises(MeterError):
        _run_gated(lambda: m.fulfill_service_request(req["id"], session, "keeper-pw"))
    with pytest.raises(MeterError, match="not pending"):
        m.deny_service_request(req["id"], session, "too late")

    # M5: request + fulfillment + provision are audit-logged, metadata only.
    events = [rec.get("event") for rec in AuditEngine().tail(500)]
    assert "broker.service.requested" in events
    assert "broker.service.fulfilled" in events
    assert "broker.account.provisioned" in events
    assert password not in _audit_text()


def test_m6_deny_is_terminal():
    session, _gw = _make_session()
    req = m.request_service("spawn1", "gitlab", "https://gitlab.com/signup")
    denied = m.deny_service_request(req["id"], session, "not a fit")
    assert denied["status"] == "denied"
    assert denied["decided_by"] == "chauncey-ops"
    with pytest.raises(MeterError, match="not pending"):
        _run_gated(lambda: m.fulfill_service_request(req["id"], session, "keeper-pw"))
    events = [rec.get("event") for rec in AuditEngine().tail(500)]
    assert "broker.service.denied" in events


# -- M4: entitlement is read-only -------------------------------------------------


def test_m4_entitlement_check_never_consumes():
    before = m.meter_reading("spawn1", "account_create")
    entitled, reason, remaining = m.entitlement_check("spawn1", "account_create")
    after = m.meter_reading("spawn1", "account_create")
    assert before == after, "entitlement_check must not consume quota"
    assert entitled is False  # free tier: zero account creation
    assert "quota-exhausted" in reason
    assert remaining == 0

    entitled_f, reason_f, remaining_f = m.entitlement_check("chauncey", "account_create")
    assert entitled_f is True
    assert remaining_f is None  # founder: unlimited
    assert "founder-unlimited" in reason_f

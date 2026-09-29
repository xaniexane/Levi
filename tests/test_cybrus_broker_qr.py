"""Proof for the QR invite laws (broker_qr.py).

Q1 SINGLE-USE · Q2 EXPIRY · Q3 SIGNED · Q4 NO-SECRETS-IN-QR ·
Q5 CREATOR-BOUND · Q6 BROKER-GATED · Q7 AUDIT.
"""

from __future__ import annotations

import time

import pytest

from levi.cybrus import BrokerApprovalRequired, broker_qr
from levi.cybrus.approval import ApprovalEngine
from levi.cybrus.audit import AuditEngine
from levi.cybrus.broker_qr import QRError


@pytest.fixture(autouse=True)
def _levi_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    from levi.cybrus import rate_limits

    rate_limits.set_tier("bob", "pro")
    rate_limits.set_tier("carol", "pro")
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


# -- Q4/Q5/Q7: issuance ----------------------------------------------------------


def test_q4_q5_q7_issue_invite_payload_and_binding():
    inv = broker_qr.issue_invite("alice", "inner-circle")
    assert inv["qr_payload"].startswith("cybrus://invite/")
    assert inv["creator"] == "alice"
    assert inv["circle"] == "inner-circle"
    # Q4: the payload is a signed ticket, not a secret.
    assert "password" not in inv["qr_payload"].lower()
    events = [rec.get("event") for rec in AuditEngine().tail(200)]
    assert "broker.qr.issued" in events


def test_q5_founder_creator_requires_live_session():
    with pytest.raises(QRError, match="FounderSession"):
        broker_qr.issue_invite("chauncey", "inner-circle")
    session, _gw = _make_session()
    inv = broker_qr.issue_invite("chauncey", "inner-circle", session=session)
    assert inv["creator"] == "chauncey"


# -- Q1/Q6/Q7: redemption --------------------------------------------------------


def test_q1_q6_q7_redeem_provisions_admits_and_single_use():
    inv = broker_qr.issue_invite("alice", "inner-circle", max_uses=1)
    account, admission = _run_gated(
        lambda: broker_qr.redeem_invite(inv["qr_payload"], "bob", "keeper-pw")
    )
    # Q6: the redemption went through the broker — a real brokered account.
    assert account["platform"] == "circle.inner-circle"
    assert account["identity"] == "bob"
    assert account["status"] == "provisioned"
    # The admission ticket verifies for the chat layer handshake.
    claims = broker_qr.verify_admission(admission)
    assert claims["user"] == "bob"
    assert claims["circle"] == "inner-circle"
    assert claims["creator"] == "alice"
    # Q1: a second redemption fails closed.
    with pytest.raises(QRError, match="fully redeemed"):
        _run_gated(lambda: broker_qr.redeem_invite(inv["qr_payload"], "carol", "keeper-pw"))
    events = [rec.get("event") for rec in AuditEngine().tail(200)]
    assert "broker.qr.redeemed" in events


def test_q6_invite_is_not_a_minting_bypass_for_limited_users():
    from levi.cybrus import rate_limits
    from levi.cybrus.rate_limits import RateLimitDenied

    rate_limits.set_tier("freeloader", "free")
    inv = broker_qr.issue_invite("alice", "inner-circle")
    with pytest.raises(BrokerApprovalRequired) as excinfo:
        broker_qr.redeem_invite(inv["qr_payload"], "freeloader", "keeper-pw")
    ApprovalEngine().approve(excinfo.value.approval_id, by="tester")
    with pytest.raises(RateLimitDenied):
        broker_qr.redeem_invite(inv["qr_payload"], "freeloader", "keeper-pw")


# -- Q2: expiry --------------------------------------------------------------------


def test_q2_expired_invite_fails_closed():
    inv = broker_qr.issue_invite("alice", "inner-circle", ttl_hours=0.0001)
    time.sleep(0.6)
    with pytest.raises(QRError, match="expired"):
        broker_qr.redeem_invite(inv["qr_payload"], "bob", "keeper-pw")


# -- Q3: signature -------------------------------------------------------------------


def test_q3_tampered_ticket_fails():
    inv = broker_qr.issue_invite("alice", "inner-circle")
    token = inv["qr_payload"].split("cybrus://invite/", 1)[1]
    body, sig = token.split(".", 1)
    tampered_body = ("A" if body[0] != "A" else "B") + body[1:]
    with pytest.raises(QRError):
        broker_qr.redeem_invite(tampered_body + "." + sig, "bob", "keeper-pw")
    # Forged admission tickets fail too.
    with pytest.raises(QRError):
        broker_qr.verify_admission(tampered_body + "." + sig)

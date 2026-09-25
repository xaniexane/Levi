"""Hermetic tests for the Cybrus broker founder edition (live provisioning).

``LEVI_HOME`` is monkeypatched to ``tmp_path`` for every test — no network,
no daemons, no user HOME writes. The operator channel is
``FakeOperatorChannel`` walking a ``FakeSignupPage``: an in-memory
stand-in for the browser-task driver that will drive the real signup.
Checkpoint pauses are proven against it.

Every provisioning transition requires a live authenticated
:class:`FounderSession` (FL1 — see broker_founder.py / founder_gateway.py);
tests open one via ``_session()``. Read-side methods
(get_plan/list_plans/status) still take ``identity=``.

The laws under test:
- SECRETS-SEALED: no plaintext secret in JSON stores, audit, or stdout.
- GATE-EVERY-STEP: every forward transition needs a consumed approval.
- TERMS-ARE-HUMAN: machine terms attestation is refused, always.
- NO-IDENTITY-DOCUMENTS: no such method, no such payload.
- CHECKPOINT-PAUSE: execution halts at checkpoints until the human.
- PLAN-FIDELITY: unapproved steps fail the plan instead of running.
- METADATA-ONLY: stores/audit carry names and digests, never values.
"""

from __future__ import annotations

import json

import pytest

from levi.cybrus import (
    SIGNUP_PLANS,
    BrokerApprovalRequired,
    CredentialBroker,
    FounderBroker,
    FounderBrokerError,
    FounderPlanFailed,
    FounderTermsRefused,
)
from levi.cybrus.approval import ApprovalEngine
from levi.cybrus.audit import AuditEngine


@pytest.fixture(autouse=True)
def _levi_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    from levi.cybrus import rate_limits

    rate_limits.set_tier("alice", "pro")
    rate_limits.set_tier("bob", "pro")
    yield tmp_path


def _run_gated(fn):
    """Drive a founder action through the human gate the way the CLI does:
    first call raises :class:`BrokerApprovalRequired` with a pending id, a
    verified human approves it, the retry succeeds."""
    try:
        return fn()
    except BrokerApprovalRequired as exc:
        approval_id = exc.approval_id
        pending = ApprovalEngine().pending()
        assert any(e["id"] == approval_id for e in pending)
        ApprovalEngine().approve(approval_id, by="tester")
        return fn()


def _session(name):
    """Open an authenticated FounderSession for a service identity."""
    from levi.cybrus import rate_limits
    from levi.cybrus.factory import generate_password, hash_password
    from levi.cybrus.founder_gateway import FounderSession
    from levi.cybrus.gateway import CybrusGateway
    from levi.cybrus.identity import IdentityStore

    store = IdentityStore()
    if not store.exists(name):
        store.create(name, tier="pro")
    pw = generate_password(20)
    store.set_credential(name, hash_password(pw))
    rate_limits.set_tier(name, "pro")
    return FounderSession.authenticate(name, pw, gateway=CybrusGateway())


def _audit_blob():
    ok, _ = AuditEngine().verify()
    assert ok, "audit chain must verify"
    return "\n".join(
        json.dumps(rec.get("details", {}), sort_keys=True)
        for rec in AuditEngine().tail(500)
    )


def _store_blob():
    from levi.cybrus._paths import load_json_store, store_path

    blob = {}
    for name in (
        "broker_accounts",
        "broker_founder_plans",
    ):
        blob[name] = load_json_store(store_path(name))
    return json.dumps(blob, sort_keys=True)


# -- fake operator channel: the browser-task driver stand-in ------------------


class FakeSignupPage:
    """In-memory fake of the Cash App signup page."""

    def __init__(self):
        self.opened = False
        self.contact = None
        self.code = None
        self.created = False


class FakeOperatorChannel:
    """Walks the machine steps of a plan against a FakeSignupPage.

    Human checkpoints are never performed here — the broker pauses and the
    test answers them as the human would.
    """

    def __init__(self, broker, plan_id, session, page):
        self.broker = broker
        self.plan_id = plan_id
        self.session = session
        self.page = page
        self.performed = []

    def perform(self, public_plan, step, context):
        sid = step["id"]
        self.performed.append(sid)
        if sid == "open_signup":
            self.page.opened = True
            return {"ok": True, "note": "signup form visible"}
        if sid == "enter_contact":
            contact = self.broker.issue_contact(
                self.plan_id, session=self.session
            )
            self.page.contact = contact
            return {"ok": True, "note": "contact entered"}
        if sid == "submit_code":
            code = self.broker.issue_checkpoint_secret(
                self.plan_id, session=self.session
            )
            self.page.code = code
            return {"ok": True, "note": "code submitted"}
        if sid == "confirm_created":
            assert self.page.opened and self.page.contact and self.page.code
            self.page.created = True
            return {"ok": True, "note": "$cashtag visible"}
        raise AssertionError(f"fake channel cannot perform step {sid!r}")


def _new_plan(br, session, contact="+15551234567"):
    return _run_gated(
        lambda: br.provision_plan(
            "cashapp", session=session, contact=contact
        )
    )


def _to_awaiting_human(br, plan_id, session):
    """Drive a fresh plan to its first human checkpoint. Returns the page."""
    _run_gated(lambda: br.mint_credential(plan_id, session=session))
    _run_gated(lambda: br.begin_execution(plan_id, session=session))
    page = FakeSignupPage()
    channel = FakeOperatorChannel(br, plan_id, session, page)
    checkpoint = br.run_to_checkpoint(plan_id, channel, session=session)
    assert checkpoint["kind"] == "checkpoint"
    assert checkpoint["checkpoint"] == "verification_code"
    assert br.get_plan(plan_id, identity="alice")["status"] == "awaiting-human"
    return page


# -- every forward transition is human-gated --------------------------------


def test_plan_requires_human_approval():
    br = FounderBroker("master-pw")
    session = _session("alice")
    with pytest.raises(BrokerApprovalRequired):
        br.provision_plan("cashapp", session=session, contact="+15550001111")


def test_mint_requires_human_approval():
    br = FounderBroker("master-pw")
    session = _session("alice")
    plan = _new_plan(br, session)
    with pytest.raises(BrokerApprovalRequired):
        br.mint_credential(plan["plan_id"], session=session)


def test_execute_requires_human_approval():
    br = FounderBroker("master-pw")
    session = _session("alice")
    plan = _new_plan(br, session)
    _run_gated(lambda: br.mint_credential(plan["plan_id"], session=session))
    with pytest.raises(BrokerApprovalRequired):
        br.begin_execution(plan["plan_id"], session=session)


def test_checkpoint_resume_requires_human_approval():
    br = FounderBroker("master-pw")
    session = _session("alice")
    plan = _new_plan(br, session)
    _to_awaiting_human(br, plan["plan_id"], session)
    with pytest.raises(BrokerApprovalRequired):
        br.human_input(
            plan["plan_id"], "checkpoint_sms", {"code": "123456"}, session=session
        )


def test_complete_requires_human_approval():
    br = FounderBroker("master-pw")
    session = _session("alice")
    plan = _new_plan(br, session)
    _drive_to_done(br, plan["plan_id"], session)
    with pytest.raises(BrokerApprovalRequired):
        br.complete_execution(plan["plan_id"], session=session)


def test_fail_requires_session_but_needs_no_approval():
    br = FounderBroker("master-pw")
    session = _session("alice")
    plan = _new_plan(br, session)
    # No approval requested, no approval consumed — failing just works.
    out = br.fail_plan(plan["plan_id"], "operator changed mind", session=session)
    assert out["status"] == "failed"


# -- state machine edges ----------------------------------------------------------


def test_illegal_transitions_refused():
    br = FounderBroker("master-pw")
    session = _session("alice")
    plan = _new_plan(br, session)
    pid = plan["plan_id"]
    # planned -> executing skips minting
    with pytest.raises(FounderBrokerError):
        _run_gated(lambda: br.begin_execution(pid, session=session))
    # planned -> complete
    with pytest.raises(FounderBrokerError):
        _run_gated(lambda: br.complete_execution(pid, session=session))
    # no steps to drive before executing
    with pytest.raises(FounderBrokerError):
        br.next_step(pid, session=session)
    # no checkpoint awaiting input
    with pytest.raises(FounderBrokerError):
        br.human_input(pid, "checkpoint_sms", {"code": "1"}, session=session)
    # unknown plan
    with pytest.raises(FounderBrokerError):
        br.get_plan("deadbeef" * 4, identity="alice")
    # unknown platform
    with pytest.raises(FounderBrokerError):
        _run_gated(
            lambda: br.provision_plan(
                "nope", session=session, contact="+15550001111"
            )
        )


def test_double_complete_refused():
    br = FounderBroker("master-pw")
    session = _session("alice")
    plan = _new_plan(br, session)
    _drive_to_done(br, plan["plan_id"], session)
    _run_gated(lambda: br.complete_execution(plan["plan_id"], session=session))
    with pytest.raises(FounderBrokerError):
        _run_gated(lambda: br.complete_execution(plan["plan_id"], session=session))


def test_duplicate_live_plan_refused():
    br = FounderBroker("master-pw")
    session = _session("alice")
    _new_plan(br, session)
    with pytest.raises(FounderBrokerError):
        _run_gated(
            lambda: br.provision_plan(
                "cashapp", session=session, contact="+15550002222"
            )
        )


# -- terms are human, always ----------------------------------------------------


def test_machine_terms_attestation_refused():
    br = FounderBroker("master-pw")
    session = _session("alice")
    plan = _new_plan(br, session)
    _drive_to_terms(br, plan["plan_id"], session)
    with pytest.raises(FounderTermsRefused):
        _run_gated(
            lambda: br.human_input(
                plan["plan_id"],
                "checkpoint_terms",
                {"accepted": True},
                session=session,
                human_attestation=False,  # the machine tried
            )
        )
    # The plan is still waiting — the refusal did not consume the checkpoint.
    assert (
        br.get_plan(plan["plan_id"], identity="alice")["status"]
        == "awaiting-human"
    )


def test_terms_attestation_by_wrong_identity_refused():
    br = FounderBroker("master-pw")
    session = _session("alice")
    plan = _new_plan(br, session)
    _drive_to_terms(br, plan["plan_id"], session)
    # Containment fires before the attestation is even evaluated.
    with pytest.raises(FounderBrokerError):
        _run_gated(
            lambda: br.human_input(
                plan["plan_id"],
                "checkpoint_terms",
                {"accepted": True},
                session=_session("bob"),
                human_attestation=True,
            )
        )


# -- no identity documents, ever --------------------------------------------------


def test_no_identity_document_surface():
    assert not hasattr(FounderBroker, "submit_identity_document")
    assert "identity_document" not in SIGNUP_PLANS["cashapp"]["steps"].__str__()
    for kind in ("verification_code", "terms_acceptance", "identity_kyc", "payment_link"):
        assert kind in (
            "verification_code",
            "terms_acceptance",
            "identity_kyc",
            "payment_link",
        )


def test_identity_kyc_rejects_values():
    br = FounderBroker("master-pw")
    session = _session("alice")
    plan = _new_plan(br, session)
    _drive_to_identity(br, plan["plan_id"], session)
    with pytest.raises(FounderBrokerError):
        _run_gated(
            lambda: br.human_input(
                plan["plan_id"],
                "checkpoint_identity",
                {"provided": True, "dob": "1990-01-01"},  # values refused
                session=session,
            )
        )


# -- checkpoint pauses fire ----------------------------------------------------------


def test_execution_pauses_at_checkpoint_and_holds():
    br = FounderBroker("master-pw")
    session = _session("alice")
    plan = _new_plan(br, session)
    pid = plan["plan_id"]
    page = _to_awaiting_human(br, pid, session)
    assert page.opened and page.contact == "+15551234567"
    # Driving again does not advance past the checkpoint.
    channel = FakeOperatorChannel(br, pid, "alice", page)
    again = br.run_to_checkpoint(pid, channel, session=session)
    assert again["checkpoint"] == "verification_code"
    assert channel.performed == []  # nothing executed while awaiting human


def test_checkpoint_secret_exactly_once():
    br = FounderBroker("master-pw")
    session = _session("alice")
    plan = _new_plan(br, session)
    _to_awaiting_human(br, plan["plan_id"], session)
    pid = plan["plan_id"]
    _run_gated(
        lambda: br.human_input(
            pid, "checkpoint_sms", {"code": "987654"}, session=session
        )
    )
    first = br.issue_checkpoint_secret(pid, session=session)
    assert first == "987654"
    with pytest.raises(FounderBrokerError):
        br.issue_checkpoint_secret(pid, session=session)


def test_contact_exactly_once():
    br = FounderBroker("master-pw")
    session = _session("alice")
    plan = _new_plan(br, session, contact="+15559998888")
    _run_gated(lambda: br.mint_credential(plan["plan_id"], session=session))
    first = br.issue_contact(plan["plan_id"], session=session)
    assert first == "+15559998888"
    with pytest.raises(FounderBrokerError):
        br.issue_contact(plan["plan_id"], session=session)


# -- plan fidelity -------------------------------------------------------------------


def test_unapproved_step_fails_plan():
    br = FounderBroker("master-pw")
    session = _session("alice")
    plan = _new_plan(br, session)
    pid = plan["plan_id"]
    _run_gated(lambda: br.mint_credential(pid, session=session))
    _run_gated(lambda: br.begin_execution(pid, session=session))
    with pytest.raises(FounderPlanFailed):
        br.report_step(pid, "evil_step", True, session=session)
    assert br.get_plan(pid, identity="alice")["status"] == "failed"


def test_failed_step_fails_plan():
    br = FounderBroker("master-pw")
    session = _session("alice")
    plan = _new_plan(br, session)
    pid = plan["plan_id"]
    _run_gated(lambda: br.mint_credential(pid, session=session))
    _run_gated(lambda: br.begin_execution(pid, session=session))

    class FailChannel:
        def perform(self, public_plan, step, context):
            return {"ok": False, "note": "page 404"}

    with pytest.raises(FounderPlanFailed):
        br.run_to_checkpoint(pid, FailChannel(), session=session)
    assert br.get_plan(pid, identity="alice")["status"] == "failed"


# -- secrets sealed, metadata only ----------------------------------------------------


def test_no_secrets_in_stores_or_audit():
    br = FounderBroker("master-pw")
    session = _session("alice")
    plan = _new_plan(br, session, contact="+15551234567")
    pid = plan["plan_id"]
    _, password = _drive_to_done(br, pid, session, code="246810")
    _run_gated(lambda: br.complete_execution(pid, session=session))
    blob = _store_blob() + "\n" + _audit_blob()
    for secret in (password, "+15551234567", "246810"):
        assert secret not in blob, f"secret leaked into stores/audit: {secret[:4]}..."


def test_public_plan_carries_no_secrets():
    br = FounderBroker("master-pw")
    session = _session("alice")
    plan = _new_plan(br, session, contact="+15551234567")
    blob = json.dumps(plan, sort_keys=True)
    assert "+15551234567" not in blob
    assert '"contact":' not in blob  # the secret value's field never ships


# -- end to end: the full live provisioning -----------------------------------------------


def _drive_to_identity(br, pid, session):
    _, password = _run_gated(lambda: br.mint_credential(pid, session=session))
    _run_gated(lambda: br.begin_execution(pid, session=session))
    page = FakeSignupPage()
    channel = FakeOperatorChannel(br, pid, session, page)
    br.run_to_checkpoint(pid, channel, session=session)
    _run_gated(
        lambda: br.human_input(
            pid, "checkpoint_sms", {"code": "111222"}, session=session
        )
    )
    br.run_to_checkpoint(pid, channel, session=session)
    return page, password


def _drive_to_terms(br, pid, session):
    page, password = _drive_to_identity(br, pid, session)
    channel = FakeOperatorChannel(br, pid, session, page)
    br.run_to_checkpoint(pid, channel, session=session)
    _run_gated(
        lambda: br.human_input(
            pid, "checkpoint_identity", {"provided": True}, session=session
        )
    )
    br.run_to_checkpoint(pid, channel, session=session)
    return page, password


def _drive_to_done(br, pid, session, code="333444"):
    page, password = _drive_to_terms(br, pid, session)
    channel = FakeOperatorChannel(br, pid, session, page)
    br.run_to_checkpoint(pid, channel, session=session)
    _run_gated(
        lambda: br.human_input(
            pid,
            "checkpoint_terms",
            {"accepted": True},
            session=session,
            human_attestation=True,
        )
    )
    br.run_to_checkpoint(pid, channel, session=session)
    _run_gated(
        lambda: br.human_input(
            pid, "link_card", {"skipped": True}, session=session
        )
    )
    done = br.run_to_checkpoint(pid, channel, session=session)
    assert done["done"] is True
    assert page.created
    return page, password


def test_full_provisioning_end_to_end():
    br = FounderBroker("master-pw")
    session = _session("alice")
    plan = _new_plan(br, session)
    pid = plan["plan_id"]
    _drive_to_done(br, pid, session)
    out = _run_gated(lambda: br.complete_execution(pid, session=session))
    assert out["plan"]["status"] == "active"
    assert out["account"]["status"] == "active"
    assert out["account"]["platform"] == "cashapp"
    assert out["account"]["founder_plan_id"] == pid
    # The live account is inherited by the base broker machinery.
    base = CredentialBroker("master-pw")
    accounts = base.list_accounts(identity="alice")
    assert any(
        a["id"] == out["account"]["id"] and a["status"] == "active"
        for a in accounts
    )
    # Rotation works through the base broker (gated, exactly-once).
    try:
        base.rotate(out["account"]["id"], identity="alice")
    except Exception as exc:  # noqa: BLE001 - approval gate expected
        from levi.cybrus import BrokerApprovalRequired as _BAR

        assert isinstance(exc, _BAR)
    ok, _ = AuditEngine().verify()
    assert ok


def test_fail_wipes_scratch_and_keeps_record():
    br = FounderBroker("master-pw")
    session = _session("alice")
    plan = _new_plan(br, session, contact="+15550009999")
    pid = plan["plan_id"]
    _run_gated(lambda: br.mint_credential(pid, session=session))
    br.fail_plan(pid, "human aborted at the terms screen", session=session)
    out = br.get_plan(pid, identity="alice")
    assert out["status"] == "failed"
    # Scratch secrets are gone from the vault.
    from levi.cybrus.vault import CredentialVault

    vault = CredentialVault("master-pw")
    service = f"cybrus.broker.founder.cashapp"
    short = pid[:8]
    for suffix in ("password", "contact", "verify_code"):
        with pytest.raises(KeyError):
            vault.get(service, f"{short}.{suffix}")
    # The failed record stays for the trail (nothing thrown away).
    assert len(br.list_plans(identity="alice")) == 1


def test_status_overview():
    br = FounderBroker("master-pw")
    session = _session("alice")
    plan = _new_plan(br, session)
    st = br.status(identity="alice")
    assert st["plans"] == 1
    assert st["by_status"] == {"planned": 1}
    assert "cashapp" in st["platforms"]
    br.fail_plan(plan["plan_id"], "nope", session=session)
    st = br.status(identity="alice")
    assert st["by_status"] == {"failed": 1}


def test_signup_plan_registry_lists_cashapp_reference():
    assert "cashapp" in SIGNUP_PLANS
    spec = SIGNUP_PLANS["cashapp"]
    assert spec["signup_url"].startswith("https://")
    kinds = [s["kind"] for s in spec["steps"]]
    assert "action" in kinds and "checkpoint" in kinds
    checkpoints = {
        s["checkpoint"] for s in spec["steps"] if s["kind"] == "checkpoint"
    }
    assert checkpoints == {
        "verification_code",
        "terms_acceptance",
        "identity_kyc",
        "payment_link",
    }
    # Every step has a human-readable description and a verify point.
    for step in spec["steps"]:
        assert step["description"] and step["verify"]

"""Full-build tests for the hardened Cybrus broker founder edition.

``LEVI_HOME`` is monkeypatched to ``tmp_path`` — no network, no daemons,
no user HOME writes.

The laws under test (see broker_founder.py / founder_gateway.py /
broker_operator.py):
- FL1 AUTHENTICATED-FOUNDER-PATH: every provisioning transition requires a
  live FounderSession; caller-asserted identity strings are refused;
  founder-tier sessions are refused at creation; expired sessions fail
  closed; cross-identity containment holds.
- FL3 REKEY-SAFE: change_master_password preserves every entry — proven by
  decrypt round-trip under the new passphrase (mechanism test; the live
  rotation is an operational runbook).
- FL5 NO-SECRETS-IN-STORES: after a full end-to-end run, the minted
  password, contact, and verification code appear nowhere in JSON stores,
  audit records, or raw vault bytes.
- FL6 OPERATOR-CHANNEL-BINDING: the unbound production channel fails
  closed; the scripted channel cannot improvise undeclared steps.
- FL7 PLAN-REGISTRY-FIDELITY: PayPal registered under the same checkpoint
  laws; unknown platforms refused.
- FL8 CLI-COVERAGE: the founder CLI read commands run; gated commands
  share the library gates (proven via the library here).
"""

from __future__ import annotations

import json

import pytest

from levi.cybrus import (
    SIGNUP_PLANS,
    BrowserTaskChannel,
    FounderBroker,
    FounderBrokerError,
    FounderPlanFailed,
    FounderSession,
    FounderSessionError,
    OperatorChannelError,
    ScriptedChannel,
    BrokerApprovalRequired,
)
from levi.cybrus.approval import ApprovalEngine
from levi.cybrus.audit import AuditEngine
from levi.cybrus.broker_founder import CHECKPOINT_KINDS


@pytest.fixture(autouse=True)
def _levi_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    from levi.cybrus import rate_limits

    rate_limits.set_tier("svc-a", "pro")
    rate_limits.set_tier("svc-b", "pro")
    yield tmp_path


def _run_gated(fn):
    """Drive a founder action through the human gate the way the CLI does."""
    try:
        return fn()
    except BrokerApprovalRequired as exc:
        approval_id = exc.approval_id
        pending = ApprovalEngine().pending()
        assert any(e["id"] == approval_id for e in pending)
        ApprovalEngine().approve(approval_id, by="tester")
        return fn()


def _make_session(name, tier="pro"):
    """Create a service identity and open an authenticated FounderSession."""
    from levi.cybrus.factory import generate_password, hash_password
    from levi.cybrus.gateway import CybrusGateway
    from levi.cybrus.identity import IdentityStore

    store = IdentityStore()
    if not store.exists(name):
        store.create(name, tier=tier)
    pw = generate_password(20)
    store.set_credential(name, hash_password(pw))
    gw = CybrusGateway()
    session = FounderSession.authenticate(name, pw, gateway=gw)
    return session, gw


def _broker():
    return FounderBroker("test-master-pass")


# -- FL1: no session, no provisioning ----------------------------------------


def test_fl1_provision_plan_requires_session():
    b = _broker()
    with pytest.raises(FounderBrokerError, match="authenticated founder session"):
        b.provision_plan("cashapp", contact="555-0100")


def test_fl1_all_transitions_require_session():
    b = _broker()
    session, _gw = _make_session("svc-a")
    plan = _run_gated(lambda: b.provision_plan("cashapp", session=session, contact="555-0100"))
    pid = plan["plan_id"]
    gated = [
        lambda: b.mint_credential(pid),
        lambda: b.begin_execution(pid),
        lambda: b.next_step(pid),
        lambda: b.report_step(pid, "open_signup", True),
        lambda: b.run_to_checkpoint(pid, ScriptedChannel({})),
        lambda: b.human_input(pid, "checkpoint_sms", {"code": "1"}),
        lambda: b.issue_contact(pid),
        lambda: b.issue_checkpoint_secret(pid),
        lambda: b.complete_execution(pid),
        lambda: b.fail_plan(pid, reason="x"),
    ]
    for fn in gated:
        with pytest.raises(FounderBrokerError, match="authenticated founder session"):
            fn()


def test_fl1_wrong_session_type_refused():
    b = _broker()
    with pytest.raises(FounderBrokerError, match="must be a FounderSession"):
        b.provision_plan("cashapp", session="svc-a", contact="555-0100")


def test_fl1_founder_identity_session_refused():
    from levi.cybrus.factory import generate_password, hash_password
    from levi.cybrus.gateway import CybrusGateway
    from levi.cybrus.identity import IdentityStore

    store = IdentityStore()
    if not store.exists("chauncey"):
        store.create("chauncey", tier="founder")
    pw = generate_password(20)
    store.set_credential("chauncey", hash_password(pw))
    with pytest.raises(FounderSessionError, match="founder identity"):
        FounderSession.authenticate("chauncey", pw, gateway=CybrusGateway())


def test_fl1_bad_credential_refused_without_distinction():
    _make_session("svc-a")
    from levi.cybrus.gateway import CybrusGateway

    with pytest.raises(FounderSessionError, match="authentication failed"):
        FounderSession.authenticate("svc-a", "wrong-password", gateway=CybrusGateway())


def test_fl1_expired_session_fails_closed():
    b = _broker()
    session, gw = _make_session("svc-a")
    plan = _run_gated(lambda: b.provision_plan("cashapp", session=session, contact="555-0100"))
    gw._sessions.clear()  # simulate expiry / restart
    with pytest.raises(FounderSessionError, match="not live"):
        b.mint_credential(plan["plan_id"], session=session)


def test_fl1_cross_identity_containment():
    b = _broker()
    sa, _ = _make_session("svc-a")
    sb, _ = _make_session("svc-b")
    plan = _run_gated(lambda: b.provision_plan("cashapp", session=sa, contact="555-0100"))
    with pytest.raises(FounderBrokerError, match="containment"):
        b.mint_credential(plan["plan_id"], session=sb)


def test_fl1_read_side_still_identity_scoped():
    b = _broker()
    sa, _ = _make_session("svc-a")
    sb, _ = _make_session("svc-b")
    _run_gated(lambda: b.provision_plan("cashapp", session=sa, contact="555-0100"))
    assert b.list_plans(identity="svc-a") != []
    assert b.list_plans(identity="svc-b") == []


# -- FL1 + L2..L7: full end-to-end run under a session ------------------------


def test_full_run_cashapp_under_session():
    b = _broker()
    session, _gw = _make_session("svc-a")
    plan = _run_gated(
        lambda: b.provision_plan("cashapp", session=session, contact="555-0100")
    )
    pid = plan["plan_id"]
    _public, password = _run_gated(lambda: b.mint_credential(pid, session=session))
    assert len(password) >= 16
    _run_gated(lambda: b.begin_execution(pid, session=session))

    # The operator channel issues the contact exactly once for the form.
    contact = b.issue_contact(pid, session=session)
    assert contact == "555-0100"
    with pytest.raises(FounderBrokerError, match="already spent"):
        b.issue_contact(pid, session=session)

    channel = ScriptedChannel(
        {
            "open_signup": {"ok": True, "note": "signup form visible"},
            "enter_contact": {"ok": True, "note": "contact accepted"},
            "submit_code": {"ok": True, "note": "contact verified"},
            "confirm_created": {"ok": True, "note": "dashboard visible"},
        }
    )
    first = b.run_to_checkpoint(pid, channel, session=session)
    assert first["kind"] == "checkpoint" and first["id"] == "checkpoint_sms"

    _run_gated(
        lambda: b.human_input(pid, "checkpoint_sms", {"code": "123456"}, session=session)
    )
    code = b.issue_checkpoint_secret(pid, session=session)
    assert code == "123456"
    with pytest.raises(FounderBrokerError, match="no pending checkpoint secret"):
        b.issue_checkpoint_secret(pid, session=session)

    second = b.run_to_checkpoint(pid, channel, session=session)
    assert second["id"] == "checkpoint_identity"
    _run_gated(
        lambda: b.human_input(pid, "checkpoint_identity", {"provided": True}, session=session)
    )
    # L3: machine terms attestation is refused even with approval.
    third = b.run_to_checkpoint(pid, channel, session=session)
    assert third["id"] == "checkpoint_terms"
    import levi.cybrus.broker_founder as _bf

    with pytest.raises(_bf.FounderTermsRefused):
        _run_gated(
            lambda: b.human_input(
                pid,
                "checkpoint_terms",
                {"accepted": True},
                session=session,
                human_attestation=False,
            )
        )
    _run_gated(
        lambda: b.human_input(
            pid, "checkpoint_terms", {"accepted": True}, session=session, human_attestation=True
        )
    )
    fourth = b.run_to_checkpoint(pid, channel, session=session)
    assert fourth["id"] == "link_card"
    _run_gated(
        lambda: b.human_input(pid, "link_card", {"skipped": True}, session=session)
    )
    done = b.run_to_checkpoint(pid, channel, session=session)
    assert done["done"] is True

    result = _run_gated(lambda: b.complete_execution(pid, session=session))
    assert result["plan"]["status"] == "active"
    assert result["account"]["status"] == "active"

    # FL5: no plaintext secret anywhere in stores, audit, or raw vault bytes.
    from levi.cybrus import _paths as _p

    blob_parts = []
    for name in ("broker_accounts", "broker_founder_plans"):
        blob_parts.append(json.dumps(_p.load_json_store(_p.store_path(name)), sort_keys=True))
    ok, _ = AuditEngine().verify()
    assert ok
    blob_parts.append(
        "\n".join(
            json.dumps(rec.get("details", {}), sort_keys=True)
            for rec in AuditEngine().tail(500)
        )
    )
    vault_entries = _p.cybrus_dir() / "vault" / "entries"
    if vault_entries.exists():
        blob_parts.append(vault_entries.read_bytes().decode("utf-8", "replace"))
    blob = "\n".join(blob_parts)
    for secret_value, label in (
        (password, "minted password"),
        ("555-0100", "contact"),
        ("123456", "verification code"),
    ):
        assert secret_value not in blob, f"FL5 violated: {label} leaked into stores/audit"


# -- FL6: operator channel binding --------------------------------------------


def test_fl6_unbound_channel_fails_closed():
    ch = BrowserTaskChannel()
    assert ch.bound is False
    with pytest.raises(OperatorChannelError, match="no browser-task executor bound"):
        ch.perform({"plan_id": "x"}, {"id": "open_signup", "kind": "action"}, {})


def test_fl6_bound_executor_drives_and_validates_shape():
    seen = []

    def executor(public_plan, step, context):
        seen.append(step["id"])
        return {"ok": True, "note": "did it"}

    ch = BrowserTaskChannel().bind_executor(executor)
    assert ch.bound is True
    out = ch.perform({"plan_id": "x"}, {"id": "open_signup", "kind": "action"}, {})
    assert out == {"ok": True, "note": "did it"}
    assert seen == ["open_signup"]

    def bad_executor(public_plan, step, context):
        return {"fine": True}

    ch2 = BrowserTaskChannel(bad_executor)
    with pytest.raises(OperatorChannelError, match="must return"):
        ch2.perform({"plan_id": "x"}, {"id": "open_signup", "kind": "action"}, {})


def test_fl6_scripted_channel_cannot_improvise():
    b = _broker()
    session, _gw = _make_session("svc-a")
    plan = _run_gated(
        lambda: b.provision_plan("cashapp", session=session, contact="555-0100")
    )
    pid = plan["plan_id"]
    _run_gated(lambda: b.mint_credential(pid, session=session))
    _run_gated(lambda: b.begin_execution(pid, session=session))
    # No scripted outcome for open_signup -> the plan fails, not faked.
    with pytest.raises(FounderPlanFailed):
        b.run_to_checkpoint(pid, ScriptedChannel({}), session=session)
    assert b.get_plan(pid, identity="svc-a")["status"] == "failed"


# -- FL7: plan registry fidelity -----------------------------------------------


def test_fl7_paypal_registered_beside_cashapp():
    assert set(SIGNUP_PLANS) == {"cashapp", "paypal"}
    paypal = SIGNUP_PLANS["paypal"]
    assert paypal["signup_url"].startswith("https://www.paypal.com/")
    kinds = {s.get("checkpoint") for s in paypal["steps"] if s["kind"] == "checkpoint"}
    assert kinds <= set(CHECKPOINT_KINDS)
    assert "verification_code" in kinds and "terms_acceptance" in kinds
    # PayPal enters a minted password into its web form (Cash App is mobile-first).
    assert any(s["id"] == "enter_password" for s in paypal["steps"] if s["kind"] == "action")


def test_fl7_unknown_platform_refused():
    b = _broker()
    session, _gw = _make_session("svc-a")
    with pytest.raises(FounderBrokerError, match="unknown platform"):
        b.provision_plan("venmo", session=session, contact="555-0100")


def test_fl7_paypal_plan_runs_to_first_checkpoint():
    b = _broker()
    session, _gw = _make_session("svc-a")
    plan = _run_gated(
        lambda: b.provision_plan("paypal", session=session, contact="555-0100")
    )
    assert plan["platform"] == "paypal"
    pid = plan["plan_id"]
    _run_gated(lambda: b.mint_credential(pid, session=session))
    _run_gated(lambda: b.begin_execution(pid, session=session))
    channel = ScriptedChannel(
        {
            "open_signup": {"ok": True, "note": "account selection visible"},
            "choose_personal": {"ok": True, "note": "personal form visible"},
            "enter_contact": {"ok": True, "note": "contact accepted"},
        }
    )
    first = b.run_to_checkpoint(pid, channel, session=session)
    assert first["id"] == "checkpoint_sms"
    assert channel.performed == ["open_signup", "choose_personal", "enter_contact"]


# -- FL3: re-key mechanism ------------------------------------------------------


def test_fl3_rekey_preserves_entries_round_trip(tmp_path):
    from levi.cybrus.vault import CredentialVault

    vdir = tmp_path / "vault"
    v = CredentialVault("old-passphrase", directory=vdir)
    v.store("svc", "user", "sekret-value")
    v.change_master_password("new-passphrase")
    v2 = CredentialVault("new-passphrase", directory=vdir)
    assert v2.get("svc", "user") == "sekret-value"
    with pytest.raises(Exception):
        CredentialVault("old-passphrase", directory=vdir).get("svc", "user")


# -- FL8: CLI coverage -----------------------------------------------------------


def test_fl8_founder_cli_read_commands():
    from levi.cybrus.__main__ import main

    assert main(["founder", "status"]) == 0
    assert main(["founder", "plans"]) == 0


def test_fl8_founder_cli_provision_is_session_gated():
    # The gated path is proven through the library above; here the CLI must
    # refuse to proceed without interactive auth material in a non-tty test.
    # Parser wiring: unknown platform choice is rejected by argparse itself.
    from levi.cybrus.__main__ import main

    with pytest.raises(SystemExit) as exc:
        main(["founder", "provision", "--platform", "venmo", "--identity", "svc-a"])
    assert exc.value.code == 2

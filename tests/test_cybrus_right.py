"""RIGHT-guard proof: accounts + money through the Cybrus gateway.

Law -> guard -> prove for Chauncey's four-directions mandate (RIGHT =
accounts + money): credential use and external account actions route
through ``levi.cybrus.accounts.AccountActionGateway`` with per-account
grants + human approval for sensitive scopes; every money path through
``levi.cybrus.money.MoneyGateway`` needs an approval receipt in the
hash-chained audit log; silent movement is denied and logged as a
violation, not warned.

Nothing here is formally proven — these are invariant tests, honestly
named (L8). Finance stays paper/simulated: no live broker is wired.

Hermetic: every test runs under tmp LEVI_HOME / LEVI_CYBRUS_DIR.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from levi.cybrus.accounts import (  # noqa: E402
    AccountActionGateway,
    AccountApprovalRequired,
    AccountError,
    AccountNotRegistered,
    AccountSuspended,
    CredentialRefused,
    GrantRefused,
)
from levi.cybrus.approval import ApprovalEngine  # noqa: E402
from levi.cybrus.audit import AuditEngine  # noqa: E402
from levi.cybrus.money import (  # noqa: E402
    ApprovalReceiptMissing,
    ApprovalReplayRefused,
    DoubleSpendRefused,
    MoneyApprovalRequired,
    MoneyAuthorization,
    MoneyGateway,
    MoneyOperation,
    MoneyRefused,
    NoRailConfigured,
    NotAuthorized,
)
from levi.cybrus.sentry import (  # noqa: E402
    ACCOUNT_ACTION_ALLOWLIST,
    RightSentry,
    SilentMovementDenied,
    scan_account_verbs,
)

CORE = Path(__file__).resolve().parent.parent / "core" / "levi"
PASSPHRASE = "right-guard-test-pass"


@pytest.fixture()
def iso(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "levi_home"))
    monkeypatch.setenv("LEVI_CYBRUS_DIR", str(tmp_path / "cybrus"))
    return tmp_path


@pytest.fixture()
def gw(iso):
    return AccountActionGateway(vault_passphrase=PASSPHRASE)


@pytest.fixture()
def gmail(gw):
    gw.register_account(
        "gmail-1", "gmail", ["email.read", "email.send"],
        registered_by="chauncey", username="chauncey.gmail",
        display_name="chauncey@gmail.com",
    )
    gw.store_credential(
        "gmail-1", "chauncey.gmail", "s3cr3t-smtp", by="chauncey"
    )
    return "gmail-1"


def _audit_text(iso) -> str:
    p = Path(str(iso / "levi_home")) / ".levi" / "cybrus" / "audit.jsonl"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _approve(approval_id: str) -> dict:
    return ApprovalEngine().approve(approval_id, by="chauncey")


# ---------------------------------------------------------------------------
# R1: no credential leaves the vault without a grant receipt
# ---------------------------------------------------------------------------


def test_credential_use_mints_grant_receipt(gw, gmail, iso):
    cred = gw.use_credential(gmail, "email.send", "oath-daemon")
    assert cred.secret == "s3cr3t-smtp"
    assert cred.receipt["account_id"] == gmail
    assert cred.receipt["grant_id"].startswith("ag_")
    text = _audit_text(iso)
    assert "account.credential_used" in text
    assert cred.receipt["grant_id"] in text
    # L4: the secret never lands in the audit log.
    assert "s3cr3t-smtp" not in text
    # The chain is intact.
    ok, bad = AuditEngine().verify()
    assert ok, f"audit chain broken at {bad}"


def test_credential_use_unknown_account_refused(gw, iso):
    with pytest.raises(AccountNotRegistered):
        gw.use_credential("nope", "email.send", "mallory")


def test_credential_use_unregistered_scope_refused(gw, gmail):
    with pytest.raises(CredentialRefused):
        gw.use_credential(gmail, "financial.write", "mallory")


def test_credential_use_requires_vault_passphrase(iso):
    bare = AccountActionGateway()
    bare.register_account("a1", "gmail", ["email.read"], registered_by="chauncey")
    with pytest.raises(CredentialRefused):
        bare.use_credential("a1", "email.read", "mallory")


def test_attest_credential_use_receipts_config_secret(gw, gmail, iso):
    # Migration cover: the secret lives outside the vault (mail.json).
    # The USE still goes through the gate — grant + metadata-only
    # receipt, source declared, secret never passed, never logged.
    receipt = gw.attest_credential_use(
        gmail, "email.send", "oath-daemon",
        purpose="smtp login", source="mail.json config",
    )
    assert receipt["account_id"] == gmail
    assert receipt["scope"] == "email.send"
    assert receipt["source"] == "mail.json config"
    assert receipt["grant_id"].startswith("ag_")
    text = _audit_text(iso)
    assert "account.credential_used" in text
    assert receipt["grant_id"] in text
    assert "mail.json config" in text
    ok, bad = AuditEngine().verify()
    assert ok, f"audit chain broken at {bad}"


def test_attest_unknown_scope_refused(gw, gmail):
    with pytest.raises(CredentialRefused):
        gw.attest_credential_use(gmail, "financial.write", "mallory")


def test_attest_unknown_account_refused(gw):
    with pytest.raises(AccountNotRegistered):
        gw.attest_credential_use("nope", "email.send", "mallory")


def test_attest_suspended_account_refused(gw, gmail):
    gw.suspend_account(gmail, by="chauncey")
    with pytest.raises(AccountSuspended):
        gw.attest_credential_use(gmail, "email.send", "oath-daemon")


def test_register_account_requires_keeper(gw, iso):
    with pytest.raises(AccountError):
        gw.register_account("evil", "gmail", ["email.send"], registered_by="mallory")
    assert "account.register_refused" in _audit_text(iso)


def test_suspended_account_credential_use_refused(gw, gmail):
    gw.suspend_account(gmail, by="chauncey")
    with pytest.raises(AccountSuspended):
        gw.use_credential(gmail, "email.read", "oath-daemon")


# ---------------------------------------------------------------------------
# R2/R5: per-account grants — bound, short-lived, single-use
# ---------------------------------------------------------------------------


def test_routine_scope_mints_grant_and_executes(gw, gmail, iso):
    grant = gw.request_account_action(
        gmail, "email.read", "list_inbox", "oath-daemon", "triage"
    )
    assert grant.account_id == gmail and grant.scope == "email.read"
    ran = []
    out = gw.execute_account_action(grant, lambda: ran.append(1) or "ok",
                                    actor="oath-daemon")
    assert out == "ok" and ran == [1]
    assert "account.action_executed" in _audit_text(iso)


def test_grant_single_use_replay_refused(gw, gmail):
    grant = gw.request_account_action(gmail, "email.read", "list", "a1")
    gw.execute_account_action(grant, lambda: None, actor="a1")
    with pytest.raises(GrantRefused):
        gw.execute_account_action(grant, lambda: None, actor="a1")


def test_grant_bound_to_actor(gw, gmail):
    grant = gw.request_account_action(gmail, "email.read", "list", "alice")
    with pytest.raises(GrantRefused):
        gw.execute_account_action(grant, lambda: None, actor="bob")


def test_grant_expiry_refused(gw, gmail, iso):
    grant = gw.request_account_action(gmail, "email.read", "list", "a1")
    # Age the grant past expiry in the store and re-sign it (white-box),
    # so the expiry branch — not the forgery branch — is exercised.
    from levi.cybrus.accounts import _sign_grant

    store = iso / "levi_home" / ".levi" / "cybrus" / "cybrus_account_grants.json"
    data = json.loads(store.read_text(encoding="utf-8"))
    rec = data[grant.grant_id]
    rec["expires_at"] = "2000-01-01T00:00:00+00:00"
    rec["sig"] = _sign_grant(rec["grant_id"], rec["account_id"],
                             rec["scope"], rec["actor"], rec["expires_at"])
    store.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(GrantRefused) as exc:
        gw.execute_account_action(grant, lambda: None, actor="a1")
    assert "expired" in str(exc.value)


def test_unknown_account_names_remedy(gw):
    with pytest.raises(AccountNotRegistered) as exc:
        gw.request_account_action("ghost", "email.read", "x", "a")
    assert "register_account" in str(exc.value)  # L6: remedy named


def test_unknown_scope_refused(gw, gmail):
    with pytest.raises(GrantRefused):
        gw.request_account_action(gmail, "nuke.everything", "x", "a")


# ---------------------------------------------------------------------------
# R3: sensitive scopes need a human approval (single-use, atomic)
# ---------------------------------------------------------------------------


def test_sensitive_scope_raises_approval_required(gw, gmail, iso):
    with pytest.raises(AccountApprovalRequired) as exc:
        gw.request_account_action(gmail, "email.send", "send_mail",
                                  "oath-daemon", "mission reply")
    assert exc.value.approval_id
    assert "levi cybrus approve" in str(exc.value)  # L6/L11: remedy named
    assert "account.approval_requested" in _audit_text(iso)


def test_approve_then_grant_minted(gw, gmail):
    try:
        gw.request_account_action(gmail, "email.send", "send_mail", "op")
        pytest.fail("should have raised")
    except AccountApprovalRequired as exc:
        approval_id = exc.approval_id
    _approve(approval_id)
    grant = gw.request_account_action(gmail, "email.send", "send_mail", "op",
                                      approval_id=approval_id)
    assert grant.approval_id == approval_id
    assert gw.execute_account_action(grant, lambda: "sent", actor="op") == "sent"


def test_approval_single_use(gw, gmail):
    try:
        gw.request_account_action(gmail, "email.send", "send_mail", "op")
    except AccountApprovalRequired as exc:
        approval_id = exc.approval_id
    _approve(approval_id)
    gw.request_account_action(gmail, "email.send", "send_mail", "op",
                              approval_id=approval_id)
    # Second mint with the same approval: refused (consumed).
    with pytest.raises(GrantRefused):
        gw.request_account_action(gmail, "email.send", "send_mail", "op",
                                  approval_id=approval_id)


def test_rebound_approval_refused(gw, gmail):
    # Approval minted for (gmail-1, email.read, list) ...
    grant_approval = ApprovalEngine().request_approval(
        action="account.action", subject="op", resource="account:gmail-1",
        risk="high",
        details={"account_id": "gmail-1", "scope": "email.read",
                 "action": "list", "actor": "op"},
    )
    _approve(grant_approval["id"])
    # ... presented for (gmail-1, email.send, send_mail): refused.
    with pytest.raises(GrantRefused):
        gw.request_account_action(gmail, "email.send", "send_mail", "op",
                                  approval_id=grant_approval["id"])


def test_denied_approval_refused(gw, gmail):
    try:
        gw.request_account_action(gmail, "email.send", "send_mail", "op")
    except AccountApprovalRequired as exc:
        approval_id = exc.approval_id
    ApprovalEngine().deny(approval_id, reason="nope", by="chauncey")
    with pytest.raises(GrantRefused):
        gw.request_account_action(gmail, "email.send", "send_mail", "op",
                                  approval_id=approval_id)


def test_suspended_account_denies_despite_approval(gw, gmail):
    # L3/R4: policy deny wins — even a live approval cannot mint a grant.
    try:
        gw.request_account_action(gmail, "email.send", "send_mail", "op")
    except AccountApprovalRequired as exc:
        approval_id = exc.approval_id
    _approve(approval_id)
    gw.suspend_account(gmail, by="chauncey")
    with pytest.raises(AccountSuspended):
        gw.request_account_action(gmail, "email.send", "send_mail", "op",
                                  approval_id=approval_id)


# ---------------------------------------------------------------------------
# R4: money movements need an approval receipt in the audit log
# ---------------------------------------------------------------------------


def _money_plan(gw_money):
    return gw_money.plan(MoneyOperation.CHARGE, 199, "USD", "nope",
                         "test charge", "tester")


def _approved_money_auth(gw_money, plan, by="chauncey"):
    entry = gw_money.request_execution_approval(plan, subject="tester")
    ApprovalEngine().approve(entry["id"], by=by)
    return MoneyAuthorization(authorized_by=by, plan_id=plan.plan_id,
                             operation="charge", approval_id=entry["id"])


def test_money_bare_authorization_refused(iso):
    gw_money = MoneyGateway()
    plan = _money_plan(gw_money)
    bare = MoneyAuthorization(authorized_by="chauncey", plan_id=plan.plan_id,
                              operation="charge")
    with pytest.raises(ApprovalReceiptMissing):
        gw_money.authorize(plan, bare)
    with pytest.raises(ApprovalReceiptMissing):
        gw_money.execute(plan, bare)


def test_money_unknown_approval_refused(iso):
    gw_money = MoneyGateway()
    plan = _money_plan(gw_money)
    auth = MoneyAuthorization(authorized_by="chauncey", plan_id=plan.plan_id,
                              operation="charge", approval_id="deadbeef")
    with pytest.raises(ApprovalReceiptMissing):
        gw_money.authorize(plan, auth)


def test_money_non_keeper_still_refused(iso):
    gw_money = MoneyGateway()
    plan = _money_plan(gw_money)
    auth = MoneyAuthorization(authorized_by="mallory", plan_id=plan.plan_id,
                              operation="charge", approval_id="x")
    with pytest.raises(NotAuthorized):
        gw_money.authorize(plan, auth)


def test_money_full_gate_receipt_in_chain(iso):
    gw_money = MoneyGateway()
    plan = _money_plan(gw_money)
    auth = _approved_money_auth(gw_money, plan)
    gw_money.authorize(plan, auth)  # writes the receipt to the hash chain
    # The receipt is in the hash-chained audit log (the requirement).
    found = [
        r for r in AuditEngine().tail(5000)
        if r["event"] == "money.approval_receipt"
        and r["details"].get("plan_id") == plan.plan_id
    ]
    assert len(found) == 1
    assert found[0]["details"]["approval_id"] == auth.approval_id
    ok, bad = AuditEngine().verify()
    assert ok, f"audit chain broken at {bad}"
    # Execute still refuses (no rails) — but the approval was consumed.
    with pytest.raises(NoRailConfigured):
        gw_money.execute(plan, auth)
    v = gw_money.verify(plan.plan_id)
    assert v["approval_receipt_in_chain"] is True
    assert v["complete"] is True
    receipt = gw_money.receipt(plan.plan_id)
    assert receipt["approval_id"] == auth.approval_id
    assert receipt["law"] == "Cybrus alone handles money."


def test_money_rebound_approval_refused(iso):
    gw_money = MoneyGateway()
    plan_a = _money_plan(gw_money)
    plan_b = _money_plan(gw_money)
    auth_b = _approved_money_auth(gw_money, plan_b)
    # Approval minted for plan B, presented for plan A: refused.
    rebound = MoneyAuthorization(authorized_by="chauncey",
                                 plan_id=plan_a.plan_id, operation="charge",
                                 approval_id=auth_b.approval_id)
    with pytest.raises(NotAuthorized):
        gw_money.authorize(plan_a, rebound)


def test_money_wrong_action_approval_refused(iso):
    gw_money = MoneyGateway()
    plan = _money_plan(gw_money)
    # An account.action approval is not a money.execute approval.
    entry = ApprovalEngine().request_approval(
        action="account.action", subject="tester", resource="x", risk="high",
        details={"plan_id": plan.plan_id},
    )
    ApprovalEngine().approve(entry["id"], by="chauncey")
    auth = MoneyAuthorization(authorized_by="chauncey", plan_id=plan.plan_id,
                              operation="charge", approval_id=entry["id"])
    with pytest.raises(NotAuthorized):
        gw_money.authorize(plan, auth)


def test_money_expired_approval_refused(iso):
    gw_money = MoneyGateway()
    plan = _money_plan(gw_money)
    entry = gw_money.request_execution_approval(plan, subject="tester",
                                               ttl_seconds=-1)
    auth = MoneyAuthorization(authorized_by="chauncey", plan_id=plan.plan_id,
                              operation="charge", approval_id=entry["id"])
    with pytest.raises(NotAuthorized):
        gw_money.authorize(plan, auth)


def test_money_approval_replay_refused(iso):
    # Two approvals for one plan; the authorization names the SECOND.
    # execute() consumes the first match atomically, notices the binding
    # mismatch, and refuses the replay instead of spending the wrong one.
    gw_money = MoneyGateway()
    plan = _money_plan(gw_money)
    first = gw_money.request_execution_approval(plan, subject="tester")
    second = gw_money.request_execution_approval(plan, subject="tester")
    ApprovalEngine().approve(first["id"], by="chauncey")
    ApprovalEngine().approve(second["id"], by="chauncey")
    auth = MoneyAuthorization(authorized_by="chauncey", plan_id=plan.plan_id,
                              operation="charge", approval_id=second["id"])
    gw_money.authorize(plan, auth)
    with pytest.raises(ApprovalReplayRefused):
        gw_money.execute(plan, auth)
    # The named approval was NOT spent by the refused attempt: a retry
    # with the same authorization now consumes it correctly.
    with pytest.raises(NoRailConfigured):  # fail-closed on rails, not replay
        gw_money.execute(plan, auth)


def test_money_double_spend_refused(iso):
    gw_money = MoneyGateway()
    plan = _money_plan(gw_money)
    auth = _approved_money_auth(gw_money, plan)
    # Simulate a rail having executed this plan in the past.
    audit_path = Path(str(iso / "cybrus")) / "money" / "money_audit.jsonl"
    with open(audit_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"event": "executed", "plan_id": plan.plan_id,
                             "ts": "2026-09-22T00:00:00+00:00"}) + "\n")
    with pytest.raises(DoubleSpendRefused):
        gw_money.execute(plan, auth)


def test_money_gateway_still_fail_closed_and_paper(iso):
    gw_money = MoneyGateway()
    assert gw_money.list_rails() == []
    from levi.cybrus.money import status

    assert status()["live_rails_exist"] is False
    plan = _money_plan(gw_money)
    auth = _approved_money_auth(gw_money, plan)
    with pytest.raises(NoRailConfigured):
        gw_money.execute(plan, auth)


# ---------------------------------------------------------------------------
# R5 (mandate): silent movement is denied and logged as a violation
# ---------------------------------------------------------------------------


def test_sentry_denies_and_logs_violation(iso):
    sentry = RightSentry()
    with pytest.raises(SilentMovementDenied) as exc:
        sentry.report_violation("mallory", "gmail.send",
                                evidence="direct smtplib call",
                                account_id="gmail-1")
    assert "violation" in str(exc.value).lower()
    text = _audit_text(iso)
    assert "right.violation" in text
    assert "gmail.send" in text
    ok, bad = AuditEngine().verify()
    assert ok, f"audit chain broken at {bad}"


def test_sentry_check_grant_none_denied(iso):
    with pytest.raises(SilentMovementDenied):
        RightSentry().check_grant("mallory", "vault.get", None)
    assert "right.violation" in _audit_text(iso)


def test_static_scan_no_silent_account_verbs():
    verb_hits, namespace_hits = scan_account_verbs(CORE)
    undeclared = [
        (rel, name) for rel, name in verb_hits
        if rel not in ACCOUNT_ACTION_ALLOWLIST
    ]
    assert undeclared == [], f"undeclared account-action verbs: {undeclared}"
    assert namespace_hits == [], (
        f"direct cybrus.accounts.* reads outside accounts.py: {namespace_hits}"
    )
    # The one allowlisted verb really is gateway-routed.
    assert "oath/daemon.py" in ACCOUNT_ACTION_ALLOWLIST


# ---------------------------------------------------------------------------
# R2/R3 end-to-end: oath send_mail through the gateway (fake SMTP)
# ---------------------------------------------------------------------------


class _FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.sent = []
        _FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def ehlo(self):
        pass

    def starttls(self):
        pass

    def login(self, user, password):
        self.user = user
        self.password = password

    def send_message(self, msg):
        self.sent.append(msg)


@pytest.fixture()
def mail_config():
    from levi.oath.inbox import MailConfig

    return MailConfig(
        smtp_host="smtp.example.com", smtp_port=587, smtp_from="bot@example.com",
        smtp_user="bot", smtp_password="pw", smtp_use_tls=True,
    )


def test_send_mail_gated_no_silent_send(iso, monkeypatch, mail_config):
    import smtplib
    from levi.oath import daemon as oath_daemon

    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    _FakeSMTP.instances.clear()
    # Unregistered account: refused before anything is sent.
    with pytest.raises(AccountNotRegistered):
        oath_daemon.send_mail(mail_config, "to@example.com", "hi", "body")
    assert _FakeSMTP.instances == []


def test_send_mail_full_gate(iso, monkeypatch, mail_config):
    import smtplib
    from levi.oath import daemon as oath_daemon

    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    _FakeSMTP.instances.clear()
    gw = AccountActionGateway()
    gw.register_account("smtp-primary", "smtp", ["email.send"],
                        registered_by="chauncey", username="bot")
    # Sensitive scope: approval first.
    with pytest.raises(AccountApprovalRequired) as exc_info:
        oath_daemon.send_mail(mail_config, "to@example.com", "hi", "body")
    assert _FakeSMTP.instances == []  # nothing sent while gated
    _approve(exc_info.value.approval_id)
    oath_daemon.send_mail(mail_config, "to@example.com", "hi", "body",
                          approval_id=exc_info.value.approval_id)
    assert len(_FakeSMTP.instances) == 1
    assert _FakeSMTP.instances[0].sent[0]["Subject"] == "hi"
    assert _FakeSMTP.instances[0].user == "bot"
    text = _audit_text(iso)
    assert "account.action_executed" in text
    assert "pw" not in text  # L4: credential never in the audit log


# ---------------------------------------------------------------------------
# RED-twin adversarial: forgery, tampering, cross-binding
# ---------------------------------------------------------------------------


def test_red_forged_grant_signature_refused(gw, gmail, iso):
    grant = gw.request_account_action(gmail, "email.read", "list", "alice")
    store = iso / "levi_home" / ".levi" / "cybrus" / "cybrus_account_grants.json"
    data = json.loads(store.read_text(encoding="utf-8"))
    data[grant.grant_id]["sig"] = "0" * 64  # forged signature
    store.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(GrantRefused):
        gw.execute_account_action(grant, lambda: None, actor="alice")
    assert "account.grant_refused" in _audit_text(iso)


def test_red_grant_scope_rebind_refused(gw, gmail, iso):
    # Grant minted for email.read; attacker edits the store to email.send.
    grant = gw.request_account_action(gmail, "email.read", "list", "alice")
    store = iso / "levi_home" / ".levi" / "cybrus" / "cybrus_account_grants.json"
    data = json.loads(store.read_text(encoding="utf-8"))
    data[grant.grant_id]["scope"] = "email.send"  # rebind attempt
    store.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(GrantRefused):  # signature no longer matches
        gw.execute_account_action(grant, lambda: None, actor="alice")


def test_red_consumed_grant_replay_refused(gw, gmail, iso):
    grant = gw.request_account_action(gmail, "email.read", "list", "alice")
    gw.execute_account_action(grant, lambda: None, actor="alice")
    # Attacker clears consumed_at in the store and replays.
    store = iso / "levi_home" / ".levi" / "cybrus" / "cybrus_account_grants.json"
    data = json.loads(store.read_text(encoding="utf-8"))
    data[grant.grant_id]["consumed_at"] = None
    data[grant.grant_id]["sig"] = "0" * 64  # must reforge — cannot
    store.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(GrantRefused):
        gw.execute_account_action(grant, lambda: None, actor="alice")


def test_red_cross_account_credential_isolation(gw, gmail, iso):
    gw.register_account("drive-1", "gdrive", ["drive.read"],
                        registered_by="chauncey", username="chauncey")
    gw.store_credential("drive-1", "chauncey", "drive-token", by="chauncey")
    # Each use_credential call re-resolves the account's OWN vault row:
    # a receipt for one account never unlocks another's secret.
    cred = gw.use_credential("drive-1", "drive.read", "agent")
    assert cred.secret == "drive-token"
    cred2 = gw.use_credential(gmail, "email.read", "agent")
    assert cred2.secret == "s3cr3t-smtp"
    assert cred.receipt["grant_id"] != cred2.receipt["grant_id"]


def test_accounts_module_exports():
    from levi import cybrus

    for name in ("AccountActionGateway", "AccountApprovalRequired",
                 "RightSentry", "SilentMovementDenied"):
        assert name in cybrus.__all__

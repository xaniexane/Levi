"""Shield service tests: the gate law, the loop, and the pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from levi.services.shield.assess import FindingsRegister, plan_assessment
from levi.services.shield.authorization import (
    CONFIRMATION_PHRASE,
    AuthorizationError,
    ScopeViolation,
    assert_in_scope,
    grant_authorization,
    require_authorization,
)
from levi.services.shield.harden import HardeningStore, build_hardening_plan
from levi.services.shield.report import build_report, verify_report


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


def _auth(home, **kw):
    args = dict(
        client="Acme Corp",
        authorized_contact="J. Rivera",
        contact_role="CISO",
        scope_assets=["acme.example.com"],
        testing_windows=["2026-10-01 02:00-05:00 UTC"],
        permitted_categories=["network", "configuration"],
        authorized_by="J. Rivera",
        expires_at="2027-01-01",
        confirmation=CONFIRMATION_PHRASE,
    )
    args.update(kw)
    return grant_authorization(home=home, **args)


def _plan(auth, home):
    return plan_assessment(
        auth.auth_id,
        assessment_type="network",
        targets=["acme.example.com"],
        objective="posture review",
        home=home,
    )


# --- the gate law ---------------------------------------------------------

def test_refuses_without_authorization(home):
    with pytest.raises(AuthorizationError):
        plan_assessment("", assessment_type="network", targets=["x.example.com"], home=home)


def test_wrong_confirmation_phrase_refused(home):
    with pytest.raises(AuthorizationError):
        _auth(home, confirmation="yes please")


def test_empty_scope_refused(home):
    with pytest.raises(AuthorizationError):
        _auth(home, scope_assets=[])


def test_past_expiry_refused(home):
    with pytest.raises(AuthorizationError):
        _auth(home, expires_at="2020-01-01")


def test_unknown_auth_refused(home):
    with pytest.raises(AuthorizationError):
        require_authorization("auth_nope", home)


def test_scope_violation_rejected(home):
    auth = _auth(home)
    with pytest.raises(ScopeViolation):
        assert_in_scope(auth, "evil.example.org")
    with pytest.raises(ScopeViolation):
        plan_assessment(
            auth.auth_id, assessment_type="network",
            targets=["acme.example.com", "other.example.net"], home=home,
        )


def test_subdomain_in_scope(home):
    auth = _auth(home)
    assert assert_in_scope(auth, "mail.acme.example.com") == "mail.acme.example.com"


def test_roe_category_rejected(home):
    auth = _auth(home)
    with pytest.raises(Exception):
        plan_assessment(
            auth.auth_id, assessment_type="wireless",
            targets=["acme.example.com"], home=home,
        )


# --- no offensive capability ----------------------------------------------

BANNED_TOKENS = [
    "exploit", "payload", "shellcode", "metasploit", "reverse_shell",
    "bind_shell", "ransomware", "sqlmap", "0day", "zero-day", "c2 server",
]


def test_no_offensive_capability():
    pkg = Path(__file__).resolve().parent.parent / "core" / "levi" / "services" / "shield"
    hits = []
    for path in sorted(pkg.glob("*.py")):
        text = path.read_text(encoding="utf-8").lower()
        for token in BANNED_TOKENS:
            if token in text:
                hits.append(f"{path.name}: {token}")
    assert not hits, f"offensive capability tokens found: {hits}"


# --- assessment -> hardening -> verify -------------------------------------

def test_plan_wires_real_playbooks(home):
    auth = _auth(home)
    plan = _plan(auth, home)
    assert plan["method"], "plan must resolve playbook method references"
    for m in plan["method"]:
        assert m["skill_id"].startswith("cyber_")
        assert m["name"]


def test_finding_requires_evidence(home):
    auth = _auth(home)
    plan = _plan(auth, home)
    reg = FindingsRegister(home)
    with pytest.raises(Exception):
        reg.record(
            auth.auth_id, plan_id=plan["plan_id"], target="acme.example.com",
            severity="high", title="t", evidence="  ",
            playbook_id="cyber_x", home=home,
        )


def test_hardening_prioritized_and_linked(home):
    auth = _auth(home)
    plan = _plan(auth, home)
    reg = FindingsRegister(home)
    crit = reg.record(
        auth.auth_id, plan_id=plan["plan_id"], target="acme.example.com",
        severity="critical", title="critical issue", evidence="observed",
        playbook_id=plan["method"][0]["skill_id"], home=home,
    )
    info = reg.record(
        auth.auth_id, plan_id=plan["plan_id"], target="acme.example.com",
        severity="info", title="info note", evidence="observed",
        playbook_id=plan["method"][0]["skill_id"], home=home,
    )
    actions = build_hardening_plan(auth.auth_id, [crit, info], home=home)
    assert actions
    prios = [a.priority for a in actions]
    assert prios == sorted(prios), "actions must be priority-ordered"
    crit_actions = [a for a in actions if a.finding_id == crit.finding_id]
    info_actions = [a for a in actions if a.finding_id == info.finding_id]
    assert min(a.priority for a in crit_actions) < min(a.priority for a in info_actions)
    assert all(a.playbook_id.startswith("cyber_") for a in actions)


def test_verification_closes_finding(home):
    auth = _auth(home)
    plan = _plan(auth, home)
    reg = FindingsRegister(home)
    finding = reg.record(
        auth.auth_id, plan_id=plan["plan_id"], target="acme.example.com",
        severity="high", title="open port", evidence="observed",
        playbook_id=plan["method"][0]["skill_id"], home=home,
    )
    store = HardeningStore(home)
    actions = build_hardening_plan(auth.auth_id, [finding], home=home)
    for action in actions:
        store.mark_applied(action.action_id)
        store.verify_action(auth.auth_id, action.action_id, "re-checked clean", home)
    updated = [f for f in reg.list(auth.auth_id) if f.finding_id == finding.finding_id][0]
    assert updated.status == "verified"


def test_verification_requires_note(home):
    auth = _auth(home)
    plan = _plan(auth, home)
    reg = FindingsRegister(home)
    finding = reg.record(
        auth.auth_id, plan_id=plan["plan_id"], target="acme.example.com",
        severity="low", title="t", evidence="observed",
        playbook_id=plan["method"][0]["skill_id"], home=home,
    )
    actions = build_hardening_plan(auth.auth_id, [finding], home=home)
    with pytest.raises(Exception):
        HardeningStore(home).verify_action(auth.auth_id, actions[0].action_id, "  ", home)


def test_cross_engagement_finding_refused(home):
    a1 = _auth(home)
    a2 = _auth(home, client="Other Inc")
    plan = _plan(a1, home)
    reg = FindingsRegister(home)
    finding = reg.record(
        a1.auth_id, plan_id=plan["plan_id"], target="acme.example.com",
        severity="medium", title="t", evidence="observed",
        playbook_id=plan["method"][0]["skill_id"], home=home,
    )
    with pytest.raises(Exception):
        build_hardening_plan(a2.auth_id, [finding], home=home)


# --- sealed report ----------------------------------------------------------

def test_report_sealed_and_tamper_evident(home):
    auth = _auth(home)
    plan = _plan(auth, home)
    reg = FindingsRegister(home)
    finding = reg.record(
        auth.auth_id, plan_id=plan["plan_id"], target="acme.example.com",
        severity="medium", title="t", evidence="observed",
        playbook_id=plan["method"][0]["skill_id"], home=home,
    )
    store = HardeningStore(home)
    for action in build_hardening_plan(auth.auth_id, [finding], home=home):
        store.verify_action(auth.auth_id, action.action_id, "clean", home)
    sealed = build_report(auth.auth_id, plan, home=home)
    assert verify_report(sealed)
    assert sealed["loop_closed"] is True
    tampered = dict(sealed)
    tampered["open_findings"] = 99
    assert not verify_report(tampered)


# --- legion pipeline --------------------------------------------------------

def test_pipeline_roundtrip_fail_closed_money(home):
    from levi.cybrus.money import MoneyRefused
    from levi.services.shield.service import (
        analyze_shield,
        deliver_shield,
        offer_shield,
        pay_shield,
        quote_shield,
        showcase_shield,
    )

    auth = _auth(home)
    plan = _plan(auth, home)
    offering = offer_shield(
        provider="levi", title="Acme network assessment",
        client="Acme Corp", auth_id=auth.auth_id, home=home,
    )
    assert offering.service_type == "cyber-audit"
    offering = analyze_shield(offering, auth.auth_id, plan, home=home)
    offering = quote_shield(offering, auth.auth_id, home=home)
    assert "quoted" in offering.stage

    reg = FindingsRegister(home)
    finding = reg.record(
        auth.auth_id, plan_id=plan["plan_id"], target="acme.example.com",
        severity="low", title="t", evidence="observed",
        playbook_id=plan["method"][0]["skill_id"], home=home,
    )
    store = HardeningStore(home)
    for action in build_hardening_plan(auth.auth_id, [finding], home=home):
        store.verify_action(auth.auth_id, action.action_id, "clean", home)
    sealed = build_report(auth.auth_id, plan, home=home)
    offering = deliver_shield(offering, auth.auth_id, sealed, home=home)
    assert "delivered" in offering.stage

    # money: fail-closed with no rail registered
    with pytest.raises(MoneyRefused):
        pay_shield(offering, auth.auth_id, authorized_by="Chauncey", home=home)

    # showcase: refuses without client consent
    with pytest.raises(Exception):
        showcase_shield(offering, auth.auth_id, client_consent=False, home=home)


def test_offer_requires_authorization(home):
    from levi.services.shield.service import offer_shield

    with pytest.raises(AuthorizationError):
        offer_shield(
            provider="levi", title="t", client="c",
            auth_id="auth_missing", home=home,
        )


def test_pipeline_stages_recheck_auth(home, tmp_path, monkeypatch):
    from levi.services.shield.service import offer_shield

    auth = _auth(home)
    # authorization granted, then the store is wiped: stages must refuse
    auth_file = home / "services" / "shield" / "authorizations.jsonl"
    auth_file.write_text("", encoding="utf-8")
    with pytest.raises(AuthorizationError):
        offer_shield(
            provider="levi", title="t", client="Acme Corp",
            auth_id=auth.auth_id, home=home,
        )

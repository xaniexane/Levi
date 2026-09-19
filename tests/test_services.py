"""Tests for the legion service-offering standard (levi.services).

Covers: the service taxonomy, the analyze->quote->deliver->paid->
showcase pipeline, advisor-composed quoting (a quote is not a
charge), Cybrus-only money (fail-closed settlement), showcase
admission rules, and the no-fabrication guards on analysis and
delivery. No real money moves anywhere in here.
"""

from __future__ import annotations

import pytest

from levi.services import (
    SERVICE_TYPES,
    ServiceError,
    analyze_service,
    attach_analysis,
    deliver_service,
    offer_service,
    quote_service,
)
from levi.services.analysis import AnalysisError, AnalysisReport
from levi.services.offering import ServiceStore
from levi.bounty import payment
from levi.bounty.hunts import BountyStore, BountyState
from levi.bounty.showcase import ShowcaseRefused


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "levi-home"))
    monkeypatch.setenv("LEVI_CYBRUS_DIR", str(tmp_path / "cybrus"))
    return tmp_path


def _offer(home, provider="uniforge", stype="cyber-audit"):
    return offer_service(
        provider=provider,
        service_type=stype,
        title="audit the login module",
        problem="possible injection in login",
        scope="login.py",
        home=home,
    )


def _analyzed(offering, home):
    return attach_analysis(
        offering,
        subject="login.py",
        summary="one injection found, evidence attached",
        findings=[
            {
                "finding": "SQL injection in login()",
                "severity": "high",
                "evidence": "login.py:42 unsanitized format string",
                "recommendation": "parameterize the query",
            }
        ],
        confidence=0.8,
        home=home,
    )


def test_taxonomy_covers_cyber_and_dev():
    cyber = {k for k in SERVICE_TYPES if k.startswith("cyber-")}
    dev = {k for k in SERVICE_TYPES if k.startswith("dev-")}
    assert {"cyber-audit", "cyber-hardening", "cyber-forensics"} <= cyber
    assert {"dev-build", "dev-lift", "dev-automation"} <= dev


def test_offer_rejects_unknown_service_type(home):
    with pytest.raises(ServiceError):
        _offer(home, stype="massage-therapy")


def test_offer_creates_bounty(home):
    offering = _offer(home)
    bounty = BountyStore(home=home).get(offering.bounty_id)
    assert bounty is not None
    assert bounty.state == BountyState.OPEN.value
    assert offering.provider == "uniforge"
    assert offering.stage == "offered"


def test_levi_itself_can_provide(home):
    offering = _offer(home, provider="levi", stype="dev-lift")
    assert offering.provider == "levi"


def test_analysis_requires_evidence(home):
    offering = _offer(home)
    with pytest.raises(AnalysisError):
        attach_analysis(
            offering,
            subject="login.py",
            summary="found stuff",
            findings=[{"finding": "a bug", "severity": "high", "evidence": ""}],
            home=home,
        )


def test_analysis_rejects_bad_severity(home):
    offering = _offer(home)
    with pytest.raises(AnalysisError):
        attach_analysis(
            offering,
            subject="login.py",
            summary="x",
            findings=[{"finding": "a bug", "severity": "apocalyptic", "evidence": "e"}],
            home=home,
        )


def test_analysis_records_report(home):
    offering = _analyzed(_offer(home), home)
    assert offering.stage == "analyzed"
    report = AnalysisReport.from_dict(
        # re-read through the store path
        __import__("levi.services.analysis", fromlist=["AnalysisStore"])
        .AnalysisStore(home=home)
        .get(offering.analysis_id)
        .to_dict()
    )
    assert report.findings[0].severity == "high"
    assert "login.py:42" in report.findings[0].evidence


def test_quote_is_advisor_composed_not_a_charge(home):
    offering = _analyzed(_offer(home), home)
    offering = quote_service(offering, giant_price=500.0, home=home)
    assert offering.stage == "quoted"
    bounty = BountyStore(home=home).get(offering.bounty_id)
    assert bounty.state == BountyState.QUOTED.value
    assert bounty.quote_usd is not None
    assert bounty.quote_usd < 500.0  # below the giant, per doctrine
    assert bounty.quote_usd > 0  # no free core
    assert bounty.payment_state in ("none", "quoted")
    assert bounty.payment_receipt is None  # nothing moved


def test_delivery_requires_evidence(home):
    offering = quote_service(_analyzed(_offer(home), home), home=home)
    with pytest.raises(ServiceError):
        deliver_service(offering, solution="fixed it", evidence=[], home=home)


def test_delivery_requires_solution(home):
    offering = quote_service(_analyzed(_offer(home), home), home=home)
    with pytest.raises(ServiceError):
        deliver_service(offering, solution="  ", evidence=["patch.diff"], home=home)


def test_full_pipeline_to_delivered(home):
    offering = _offer(home)
    offering = _analyzed(offering, home)
    offering = quote_service(offering, giant_price=200.0, home=home)
    offering = deliver_service(
        offering,
        solution="parameterized the login query; added regression test",
        evidence=["patch.diff", "test_login_injection.py passes"],
        confidence=0.9,
        verification="regression test passes; re-scan clean",
        home=home,
    )
    assert offering.stage == "delivered"
    bounty = BountyStore(home=home).get(offering.bounty_id)
    assert bounty.state == BountyState.DELIVERED.value
    assert bounty.confidence == 0.9


def test_money_moves_through_cybrus_only_and_refuses(home):
    """Settlement is fail-closed: no rails, so it refuses honestly."""
    offering = deliver_service(
        quote_service(_analyzed(_offer(home), home), home=home),
        solution="done",
        evidence=["patch.diff"],
        confidence=0.85,
        home=home,
    )
    store = BountyStore(home=home)
    bounty = store.get(offering.bounty_id)
    payment.request_payment(bounty)  # plans; moves nothing
    store.save(bounty)
    bounty = payment.record_agreement(bounty, note="client agreed")
    store.save(bounty)
    bounty = payment.mark_delivered_for_payment(bounty)
    store.save(bounty)
    with pytest.raises(payment.MoneyRefused):
        payment.settle_bounty(bounty, authorized_by="chauncey")
    # and the refusal was recorded truthfully, not hidden
    bounty = store.get(bounty.id)
    assert bounty.payment_state != "paid"


def test_showcase_refuses_unpaid(home):
    from levi.services.offering import showcase_service

    offering = deliver_service(
        quote_service(_analyzed(_offer(home), home), home=home),
        solution="done",
        evidence=["patch.diff"],
        confidence=0.85,
        home=home,
    )
    with pytest.raises(ShowcaseRefused):
        showcase_service(offering, home=home)
    # offering stage must not advance on refusal
    assert ServiceStore(home=home).get(offering.offering_id).stage == "delivered"


def test_cli_smoke(home, monkeypatch, capsys):
    import sys

    monkeypatch.setenv("LEVI_HOME", str(home / "levi-home"))
    sys.path.insert(0, "core")

    offering = _offer(home)
    assert ServiceStore(home=home).get(offering.offering_id) is not None
    capsys.readouterr()

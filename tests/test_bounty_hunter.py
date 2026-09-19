"""Tests for the service-bounty hunter (levi.bounty.hunts/payment/showcase).

Covers: the forward-only state machine, the no-fabrication delivery
guard, advisor-composed quoting (a quote is not a charge), Cybrus-only
money paths with fail-closed settlement, showcase admission rules, and
DemandPulse-composed sensing. No real money moves anywhere in here.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from levi.bounty import hunts
from levi.bounty.hunts import (
    Bounty,
    BountyError,
    BountyState,
    BountyStore,
    new_bounty,
    quote_bounty,
    sense_bounties,
    transition,
)
from levi.bounty import payment
from levi.bounty.payment import (
    MoneyRefused,
    mark_delivered_for_payment,
    payment_status,
    record_agreement,
    request_payment,
    settle_bounty,
)
from levi.bounty import showcase
from levi.bounty.showcase import ShowcaseRefused, ShowcaseStore, admit, render


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "levi-home"))
    monkeypatch.setenv("LEVI_CYBRUS_DIR", str(tmp_path / "cybrus"))
    return tmp_path


def _full_bounty(home, **kw):
    """Drive a bounty draft -> delivered (no money moved)."""
    store = BountyStore()
    b = new_bounty("Fix the login loop", "Users get bounced back to login.", **kw)
    store.add(b)
    transition(b, BountyState.OPEN)
    quote_bounty(b)
    transition(b, BountyState.AGREED, note="client accepted terms")
    transition(b, BountyState.HUNTING)
    b.solution = "Session cookie was set on the wrong domain; fixed + regression test."
    b.evidence = ["repro script output", "regression test green"]
    b.confidence = 0.92
    b.verification = "reproduced before fix, verified after, test suite green"
    transition(b, BountyState.DELIVERED)
    mark_delivered_for_payment(b)
    store.save(b)
    return b, store


# -- state machine ------------------------------------------------------


def test_forward_only(home):
    store = BountyStore()
    b = new_bounty("T", "P")
    store.add(b)
    with pytest.raises(BountyError):
        transition(b, BountyState.DELIVERED)  # skipping steps refuses
    with pytest.raises(BountyError):
        transition(b, BountyState.PAID)
    transition(b, BountyState.OPEN)
    with pytest.raises(BountyError):
        transition(b, BountyState.DRAFT)  # backward refuses
    assert b.state == "open"


def test_terminal_states(home):
    store = BountyStore()
    b = new_bounty("T", "P")
    store.add(b)
    transition(b, BountyState.CANCELLED, note="client withdrew")
    with pytest.raises(BountyError):
        transition(b, BountyState.OPEN)


def test_dispute_can_return_to_hunt(home):
    store = BountyStore()
    b, _ = _full_bounty(home)
    transition(b, BountyState.DISPUTED, note="client questions evidence")
    transition(b, BountyState.HUNTING)
    assert b.state == "hunting"


def test_empty_problem_refused():
    with pytest.raises(BountyError):
        new_bounty("T", "   ")


# -- no-fabrication guard ------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("solution", ""),
        ("evidence", []),
        ("confidence", None),
        ("verification", ""),
    ],
)
def test_deliver_requires_the_real_thing(home, field, value):
    store = BountyStore()
    b = new_bounty("T", "P")
    store.add(b)
    transition(b, BountyState.OPEN)
    quote_bounty(b)
    transition(b, BountyState.AGREED, note="ok")
    transition(b, BountyState.HUNTING)
    b.solution = "real solution"
    b.evidence = ["real evidence"]
    b.confidence = 0.8
    b.verification = "verified"
    setattr(b, field, value)
    with pytest.raises(BountyError):
        transition(b, BountyState.DELIVERED)


def test_paid_requires_cybrus_receipt(home):
    b, _ = _full_bounty(home)
    with pytest.raises(BountyError):
        transition(b, BountyState.PAID)


# -- quoting: advisor-composed, a quote is not a charge ------------------


def test_quote_uses_advisor_doctrine(home):
    store = BountyStore()
    b = new_bounty("T", "P")
    store.add(b)
    transition(b, BountyState.OPEN)
    quote_bounty(b, giant_price=100.0)
    assert b.state == "quoted"
    assert b.quote_usd and b.quote_usd > 0
    assert b.quote_usd < 100.0  # doctrine: below the giants
    assert b.price_rationale
    # a quote moves no money: the gateway audit shows no executed movement
    from levi.cybrus.money import MoneyGateway

    events = [e.get("event") for e in MoneyGateway().audit_log(limit=200)]
    assert "executed" not in events


# -- payment: Cybrus only, fail-closed -----------------------------------


def test_payment_plan_moves_nothing(home):
    b, _ = _full_bounty(home)
    res = request_payment(b)
    assert res["moved"] is False
    assert b.payment_state == "quoted"
    assert b.payment_plan_id
    st = payment_status(b)
    assert st["moved"] is False


def test_settlement_refuses_fail_closed(home):
    b, _ = _full_bounty(home)
    request_payment(b)  # re-plan is fine; records the quote-stage plan
    b.payment_state = "delivered"  # payment side already deliverable
    with pytest.raises(MoneyRefused):
        settle_bounty(b, authorized_by="chauncey")
    # the refusal is recorded truthfully; the bounty is NOT paid
    assert b.state == "delivered"
    assert b.payment_state == "delivered"
    assert any(e["event"] == "payment_refused" for e in b.history)


def test_settlement_needs_explicit_identity(home):
    b, _ = _full_bounty(home)
    request_payment(b)
    with pytest.raises(BountyError):
        settle_bounty(b, authorized_by="")  # never forged, never defaulted


def test_settlement_needs_delivery(home):
    store = BountyStore()
    b = new_bounty("T", "P")
    store.add(b)
    with pytest.raises(BountyError):
        settle_bounty(b, authorized_by="chauncey")


def test_no_direct_money_paths():
    """The bounty package may move money through levi.cybrus.money ONLY.
    No payment SDKs, no HTTP payment calls, no homegrown charge logic."""
    import ast

    pkg = Path(hunts.__file__).parent
    forbidden = re.compile(
        r"\bstripe\b|\bpaypal\b|\bsquare\b|\bbraintree\b|"
        r"requests\.(post|put)\b|urllib.*pay|"
        r"def\s+charge\s*\(|def\s+execute_payment\s*\(",
        re.IGNORECASE,
    )
    gateway_imports = 0
    for path in sorted(pkg.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert not forbidden.search(text), f"forbidden money path in {path.name}"
        if path.name == "payment.py":
            continue  # payment.py is the gateway adapter by design
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if "cybrus.money" in node.module or any(
                    a.name == "MoneyGateway" for a in node.names
                ):
                    gateway_imports += 1
            elif isinstance(node, ast.Import):
                if any("cybrus.money" in a.name for a in node.names):
                    gateway_imports += 1
    pay_text = (pkg / "payment.py").read_text(encoding="utf-8")
    assert "levi.cybrus.money" in pay_text
    assert not forbidden.search(pay_text), "forbidden money path in payment.py"
    # nothing outside payment.py imports the gateway at all
    assert gateway_imports == 0


# -- showcase: admission is structural ------------------------------------


def test_showcase_refuses_unpaid(home):
    b, _ = _full_bounty(home)  # delivered, not paid
    with pytest.raises(ShowcaseRefused):
        admit(b)


def test_showcase_refuses_without_receipt(home):
    b, _ = _full_bounty(home)
    b.state = BountyState.PAID.value  # forced, but no receipt
    with pytest.raises(ShowcaseRefused):
        admit(b)


def test_showcase_refuses_duplicates(home):
    store = ShowcaseStore()
    entry = showcase.ShowcaseEntry(
        entry_id="show_x", bounty_id="bnty_x", title="T",
        problem="P", solution_summary="S",
    )
    store.add(entry)
    with pytest.raises(ShowcaseRefused):
        store.add(entry)


def test_showcase_roundtrip_and_client_verify(home):
    store = ShowcaseStore()
    entry = showcase.ShowcaseEntry(
        entry_id="show_y", bounty_id="bnty_y", title="Hunt",
        problem="P", solution_summary="S", evidence=["e1"],
    )
    store.add(entry)
    store.verify_client("show_y", note="client confirms: fixed.")
    got = store.get("show_y")
    assert got.client_verified is True
    assert "fixed" in got.client_note
    text = render(store)
    assert "Hunt" in text and "client-verified" in text


def test_showcase_starts_empty_and_honest(home):
    store = ShowcaseStore()
    assert store.list() == []
    assert "No hunts showcased yet" in render(store)


# -- sensing: composes DemandPulse ----------------------------------------


def test_sense_composes_demandpulse():
    from levi.demand.pulse import Opportunity

    class StubPulse:
        opportunities = [
            Opportunity(
                id="opp_1", demand_id="d1", title="Need login help",
                demand_score=0.9, serviceability=0.9, startup_cost=0.1,
            ),
            Opportunity(
                id="opp_2", demand_id="d2", title="Vague idea",
                demand_score=0.1, serviceability=0.2, startup_cost=0.9,
            ),
        ]

    drafts = sense_bounties(min_worth=0.5, pulse=StubPulse())
    assert len(drafts) == 1
    assert drafts[0].sensed_from == "opp_1"
    assert drafts[0].state == "draft"


# -- store -----------------------------------------------------------------


def test_store_roundtrip(home):
    store = BountyStore()
    b = new_bounty("T", "P", client="acme")
    store.add(b)
    got = store.get(b.id)
    assert got.title == "T" and got.client == "acme"
    transition(got, BountyState.OPEN)
    store.save(got)
    assert store.get(b.id).state == "open"
    assert len(store.list()) == 1
    with pytest.raises(BountyError):
        store.get("bnty_nope")


def test_store_file_is_owner_only(home):
    store = BountyStore()
    mode = oct(store.path.stat().st_mode & 0o777)
    assert mode == "0o600", f"bounty case file must be owner-only, got {mode}"

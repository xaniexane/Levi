"""Regression pins for the 7 money-verb defs outside cybrus/ (BLUE-1, 2026-09-22).

test_money_verbs_declared_outside_cybrus (tests/test_money_law.py) names
7 money-verb function definitions outside core/levi/cybrus/. Each is
honestly accounting-only — NOT money movement — and each carries a
MONEY LAW comment at the def. These tests pin that behavior: if any of
the 7 ever gains a real money path, the pin fails loudly instead of
silently reclassifying.

Standing law: real money moves through levi.cybrus.money.MoneyGateway
only. None of these 7 touch it.
"""

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from levi.boards import squares  # noqa: E402
from levi.builders.economy import (  # noqa: E402
    OwnerGateRequired,
    collect_payment,
    marketplace_royalty,
)
from levi.demandpulse import payments  # noqa: E402
from levi.dispatch.checkcalls import DetentionPolicy  # noqa: E402
from levi.genex.ledger import GenexError, GenexLedger  # noqa: E402
from levi.methods.eniac import BlueprintAdoption  # noqa: E402
from levi.suprastreet.commerce import Settlement, SupraStreet  # noqa: E402

CORE = Path(__file__).resolve().parent.parent / "core" / "levi"

# path relative to core/levi -> the money-verb def it must carry
MONEY_LAW_SITES = {
    "boards/squares.py": "def withdraw_testimonial",
    "builders/economy.py": "def collect_payment",
    "demandpulse/payments.py": "def charge",
    "dispatch/checkcalls.py": "def charge_cents",
    "genex/ledger.py": "def transfer",
    "methods/eniac.py": "def transfer_ratio",
    "suprastreet/commerce.py": "def settlements",
}


@pytest.fixture()
def square_home(tmp_path, monkeypatch):
    monkeypatch.setattr(squares, "_home", lambda: tmp_path / "squares")
    (tmp_path / "squares").mkdir()
    yield


# ---------------------------------------------------------------- 1. boards/squares.py


def test_withdraw_testimonial_moves_no_money(square_home):
    """withdraw_testimonial retracts signed TEXT — no amounts, no funds."""
    squares.create_square("club", "d", "chauncey", join_mode="open")
    squares.request_join("club", "sam")
    t = squares.leave_testimonial("club", "chauncey", "sam", "solid builder")
    assert t["author"] == "chauncey"
    assert "amount" not in t and "cents" not in t  # the record is words, not money
    squares.withdraw_testimonial("club", t["id"], "chauncey")
    assert squares.testimonials("club") == []
    # only the author can withdraw — a retraction gate, not a payment gate
    t2 = squares.leave_testimonial("club", "chauncey", "sam", "still solid")
    with pytest.raises(squares.SquareError):
        squares.withdraw_testimonial("club", t2["id"], "sam")


# ---------------------------------------------------------------- 2. builders/economy.py


def test_collect_payment_is_fail_closed():
    """collect_payment never returns — it raises before anything could move."""
    with pytest.raises(OwnerGateRequired):
        collect_payment()
    with pytest.raises(OwnerGateRequired):
        collect_payment(amount=100, customer="mallory")
    # the honest money math beside it stays pure math
    assert marketplace_royalty(Decimal("100.00")) == Decimal("12.00")


# ---------------------------------------------------------------- 3. demandpulse/payments.py


def test_charge_is_fail_closed_and_no_processor():
    """charge() always refuses; the charge path is dark by construction."""
    assert payments.PAYMENT_PROCESSOR is None
    with pytest.raises(payments.PaymentNotAuthorized):
        payments.charge("cust-1")
    with pytest.raises(payments.PaymentNotAuthorized):
        payments.charge("cust-1", amount=6.00)
    with pytest.raises(payments.PaymentNotAuthorized):
        payments.create_entitlement("cust-1")
    # the informational check never blocks and never bills
    status = payments.check_entitlement("cust-1")
    assert status.active is False
    assert status.enforced is False
    assert status.tier == "ungated"


# ---------------------------------------------------------------- 4. dispatch/checkcalls.py


def test_charge_cents_is_pure_arithmetic():
    """charge_cents maps dwell hours -> an int. No funds, no side effects."""
    policy = DetentionPolicy(free_hours=2.0, rate_cents_per_hour=7500)
    assert policy.charge_cents(1.5) == 0      # inside free hours
    assert policy.charge_cents(2.5) == 7500   # 0.5h over -> 1 billable hour
    assert policy.charge_cents(4.0) == 15000  # 2h over -> 2 billable hours
    result = policy.charge_cents(2.5)
    assert isinstance(result, int)
    # pure: identical inputs, identical outputs, no state change
    assert policy.charge_cents(2.5) == result
    assert policy.free_hours == 2.0 and policy.rate_cents_per_hour == 7500


# ---------------------------------------------------------------- 5. genex/ledger.py


def test_genex_transfer_is_ledger_accounting():
    """transfer() moves integer unit counters in memory; no currency, no rails."""
    ledger = GenexLedger()
    ledger.issue("widget-credits", "alice", 100, memo="mint")
    ledger.transfer("widget-credits", "alice", "bob", 40, memo="handoff")
    assert ledger.balance("widget-credits", "alice") == 60
    assert ledger.balance("widget-credits", "bob") == 40
    assert all(isinstance(b, int) for b in
               ledger.holders("widget-credits").values())
    # conservation: issued minus retired anchors total supply
    assert ledger.total_supply("widget-credits") == 100
    assert ledger.verify_chain()["ok"] is True
    # refuses on insufficient balance — the ledger never overdrafts
    with pytest.raises(GenexError):
        ledger.transfer("widget-credits", "bob", "alice", 41)
    # no network / payment-rail surface on the module
    src = (CORE / "genex" / "ledger.py").read_text(encoding="utf-8")
    for token in ("import requests", "socket", "stripe", "http"):
        assert token not in src


# ---------------------------------------------------------------- 6. methods/eniac.py


def test_transfer_ratio_is_porting_metric():
    """transfer_ratio is a float about ENIAC procedure steps — not funds."""
    adoption = BlueprintAdoption()
    adoption.register_op("add", "tube adder")
    adoption.define_procedure("ballistics", ["load", "aim", "fire", "log"])
    adoption.map_step("ballistics", 0, "add")
    adoption.map_step("ballistics", 1, "add")
    adoption.map_step("ballistics", 2, "add")
    adoption.mark_rewrite("ballistics", 3, "no tube op for logging")
    report = adoption.finalize("ballistics")
    assert report.transfer_ratio == 0.75
    assert isinstance(report.transfer_ratio, float)
    summary = report.summary()
    assert summary["transferred"] == 3
    assert summary["rewrites"] == 1
    assert summary["transfer_ratio"] == 0.75


# ---------------------------------------------------------------- 7. suprastreet/commerce.py


def test_settlements_is_paper_read():
    """settlements() reads an in-memory paper trail; splits are paper records."""
    street = SupraStreet()
    street.register_product_with_founder_cut("p1", "Widget", 1000, "seller")
    s1 = street.record_sale("s1", "p1", quantity=2)
    assert isinstance(s1, Settlement)
    assert s1.gross == 2000
    assert s1.total_distributed() == 2000
    assert s1.payouts["founder"] == 300   # 15% founder cut, paper
    assert s1.payouts["seller"] == 1700  # 85% seller, paper
    trail = street.settlements()
    assert trail == [s1]
    # idempotent on sale_id — never double-settles
    assert street.record_sale("s1", "p1", quantity=2) is s1
    assert street.settlements() == [s1]
    assert street.earnings("founder") == 300
    # no network / payment-rail surface on the module
    src = (CORE / "suprastreet" / "commerce.py").read_text(encoding="utf-8")
    for token in ("import requests", "socket", "stripe", "http"):
        assert token not in src


# ---------------------------------------------------------------- convention pin


def test_money_law_comments_present_at_all_seven_defs():
    """Every one of the 7 defs carries its MONEY LAW honesty marker."""
    for rel, marker in MONEY_LAW_SITES.items():
        src = (CORE / rel).read_text(encoding="utf-8")
        idx = src.index(marker)
        window = src[idx: idx + 1200]
        assert "MONEY LAW" in window, f"{rel}: {marker} lost its MONEY LAW comment"

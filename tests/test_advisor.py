"""Tests for the founder-level feature/price advisor.

Doctrine compliance is tested as hard law: the price advisor can never
recommend free, and never prices at or above the giant. Verdict
thresholds and determinism are tested as arithmetic facts.
"""

import io
import sys

import pytest

from levi.advisor import (
    FeatureIdea,
    PricePlan,
    advise_feature,
    advise_price,
)
from levi.advisor.features import FeatureError
from levi.advisor.pricing import ROSTER_SEAT_CAPS, PriceError
from levi.advisor.pricing import (
    ENTERPRISE_ANNUAL_TOTALS_AT_FLOOR_DERIVED,
    ENTERPRISE_COMMITMENT_MONTHS,
    ENTERPRISE_PER_EMPLOYEE_MONTH_USD,
    ENTERPRISE_TERM,
    KEEPER_CONFIRMABLE_SEAT_DEFINITION,
    SEAT_PREMIUM_USD,
    SEAT_STANDARD_USD,
    SEAT_TERM,
    EnterpriseBelowFloorError,
    PriceError,
    quote_enterprise,
    quote_seat_price,
)


def _idea(**kw):
    base = dict(
        name="Test Feature",
        demand_composite=80.0,
        demand_basis="analyst test basis",
        strategic_fit=0.9,
        cost="small",
        doctrine_fit=0.9,
    )
    base.update(kw)
    return FeatureIdea(**base)


# --- feature advisor -------------------------------------------------


def test_build_verdict():
    v = advise_feature(_idea())
    assert v.verdict == "build"
    assert v.alignment >= 0.70
    assert v.demand_tier == "high"
    assert v.reasons


def test_kill_on_low_demand():
    v = advise_feature(_idea(demand_composite=30.0))
    assert v.verdict == "kill"
    assert any("low" in r for r in v.reasons)


def test_kill_on_doctrine_violation():
    v = advise_feature(_idea(doctrine_fit=0.2))
    assert v.verdict == "kill"


def test_hold_without_demand_evidence():
    v = advise_feature(_idea(demand_composite=None))
    assert v.verdict == "hold"
    assert v.demand_tier == "unassessed"
    assert any("HOLD" in r for r in v.reasons)


def test_hold_middle_ground():
    v = advise_feature(_idea(demand_composite=60.0, strategic_fit=0.5))
    assert v.verdict == "hold"


def test_determinism():
    a = advise_feature(_idea())
    b = advise_feature(_idea())
    assert a.verdict == b.verdict
    assert a.alignment == b.alignment
    assert a.reasons == b.reasons


def test_five_factor_demand_composition():
    idea = _idea(
        demand_composite=None,
        demand_factors={
            "demand": (80, "users ask weekly"),
            "market_size": (70, "niche but real"),
            "competition_gap": (60, "no local player"),
            "trend_velocity": (75, "rising searches"),
            "entry_feasibility": (90, "we can ship it"),
        },
    )
    v = advise_feature(idea)
    assert v.demand_composite == 73.75  # .3*80+.25*70+.2*60+.15*75+.1*90
    assert v.demand_tier == "watch"
    assert v.verdict == "hold"  # watch tier, not high -> hold


def test_fail_closed():
    with pytest.raises(FeatureError):
        advise_feature(FeatureIdea(name=""))
    with pytest.raises(FeatureError):
        advise_feature(_idea(cost="titanic"))
    with pytest.raises(FeatureError):
        advise_feature(_idea(strategic_fit=1.5))
    with pytest.raises(FeatureError):
        advise_feature(_idea(demand_composite=80.0, demand_basis=""))


# --- price advisor ---------------------------------------------------


def test_entry_dollar_scale():
    a = advise_price(PricePlan(tier="entry"))
    assert a.low == 1.0
    assert a.high == 5.0
    assert a.recommended == 1.0  # volume -> low end
    assert a.seat_cap == ROSTER_SEAT_CAPS["founder"] == 19


def test_giant_anchor_discount():
    a = advise_price(PricePlan(tier="standard", giant_price=20.0))
    assert a.low == 8.0  # 20 * 0.40
    assert a.high == 14.0  # 20 * 0.70
    assert a.high < 20.0  # never at or above the giant
    assert a.seat_cap == 122


def test_entry_held_to_dollar_scale_against_giant():
    a = advise_price(PricePlan(tier="entry", giant_price=100.0))
    assert a.high <= 5.0
    assert a.low <= a.high


def test_margin_strategy_high_end():
    a = advise_price(PricePlan(tier="standard", giant_price=20.0, strategy="margin"))
    assert a.recommended == a.high


def test_roster_law_seat_caps():
    assert advise_price(PricePlan(tier="entry")).seat_cap == 19
    assert advise_price(PricePlan(tier="standard")).seat_cap == 122
    assert advise_price(PricePlan(tier="flagship")).seat_cap == 490


def test_commission_labeled_separately():
    a = advise_price(PricePlan(tier="entry", founder_commission=0.1))
    assert a.commission_line == round(a.recommended * 0.1, 2)
    assert any("commission" in r for r in a.rationale)


def test_price_determinism():
    a = advise_price(PricePlan(tier="flagship", giant_price=50.0, strategy="margin"))
    b = advise_price(PricePlan(tier="flagship", giant_price=50.0, strategy="margin"))
    assert (a.low, a.high, a.recommended) == (b.low, b.high, b.recommended)


def test_fail_closed_price():
    with pytest.raises(PriceError):
        advise_price(PricePlan(tier="free"))
    with pytest.raises(PriceError):
        advise_price(PricePlan(giant_price=-5.0))
    with pytest.raises(PriceError):
        advise_price(PricePlan(strategy="chaos"))
    with pytest.raises(PriceError):
        advise_price(PricePlan(founder_commission=2.0))


# --- seat pricing (keeper's tiers, paper only) ------------------------------


def test_seat_tier_values():
    assert SEAT_STANDARD_USD == 300.0
    assert SEAT_PREMIUM_USD == 600.0  # counsel-backed


def test_seat_pack_math():
    standard = quote_seat_price("standard", 5)
    assert standard.per_seat == 300.0
    assert standard.total == 1500.0  # 5-agent pack at standard = $1,500
    premium = quote_seat_price("premium", 5)
    assert premium.per_seat == 600.0
    assert premium.total == 3000.0  # 5-agent pack at premium = $3,000


def test_seat_quote_paper_only():
    q = quote_seat_price("standard", 1)
    assert q.receipt["paper_only"] is True
    assert any("paper only" in r for r in q.rationale)


def test_seat_quote_fail_closed():
    with pytest.raises(PriceError):
        quote_seat_price("gold", 5)
    with pytest.raises(PriceError):
        quote_seat_price("standard", 0)
    with pytest.raises(PriceError):
        quote_seat_price("standard", -3)


def test_seat_definition_flag_present():
    # The definition is WORKING LAW, not canon — it must be visible on the flag.
    assert "AWAITING THE KEEPER" in KEEPER_CONFIRMABLE_SEAT_DEFINITION
    assert "seat = one agent seat in the purchased pack" in KEEPER_CONFIRMABLE_SEAT_DEFINITION
    q = quote_seat_price("premium", 2)
    assert KEEPER_CONFIRMABLE_SEAT_DEFINITION in q.rationale
    assert q.receipt["seat_definition_flag"] == KEEPER_CONFIRMABLE_SEAT_DEFINITION


# --- enterprise tier: $100/employee/month floor, 12-month commitment ---


def test_enterprise_floor_is_keeper_law():
    # His word: "no less than 100 per employee every month a year."
    # Floor $100/employee/month, 12-month commitment — the floor is law.
    assert ENTERPRISE_PER_EMPLOYEE_MONTH_USD == 100.0
    assert ENTERPRISE_COMMITMENT_MONTHS == 12
    assert ENTERPRISE_TERM == "12-month commitment, billed at the monthly floor"


def test_enterprise_floor_math_four_employees():
    # His math, verified: $100/employee/month x 12 = $1,200/employee/year;
    # a 4-person team = $4,800/year.
    q = quote_enterprise(4)
    assert q.per_employee_month == 100.0
    assert q.months == 12
    assert q.monthly_total == 400.0
    assert q.annual_total == 4800.0


def test_enterprise_floor_math_ten_employees():
    q = quote_enterprise(10)
    assert q.monthly_total == 1000.0
    assert q.annual_total == 12000.0


def test_enterprise_derived_band_reconciliation():
    # DERIVED observation, not a price: the old $2-$5k band was the annual
    # total a small team lands in at the floor — 4 people land at $4,800,
    # inside that band. The table below is orientation only; the floor is law.
    for size, annual in ENTERPRISE_ANNUAL_TOTALS_AT_FLOOR_DERIVED:
        assert quote_enterprise(size).annual_total == annual
    assert dict(ENTERPRISE_ANNUAL_TOTALS_AT_FLOOR_DERIVED)[4] == 4800.0
    assert 2000.0 <= 4800.0 <= 5000.0  # the small-team total sits in the old band


def test_enterprise_below_floor_refused_loud():
    # Any quote below the floor is refused — the floor is the floor.
    with pytest.raises(EnterpriseBelowFloorError) as exc:
        quote_enterprise(4, enterprise_rate=99.99)
    assert "below the keeper's floor" in str(exc.value)
    assert issubclass(EnterpriseBelowFloorError, PriceError)
    with pytest.raises(EnterpriseBelowFloorError):
        quote_enterprise(10, enterprise_rate=50.0)


def test_enterprise_higher_rate_override_rides():
    # A keeper-set HIGHER rate may ride as an explicit override — never below.
    q = quote_enterprise(4, enterprise_rate=150.0)
    assert q.per_employee_month == 150.0
    assert q.annual_total == 7200.0  # 150 x 4 x 12


def test_enterprise_quote_carries_twelve_month_term():
    q = quote_enterprise(4)
    assert q.receipt["kind"] == "enterprise_quote"
    assert q.receipt["term"] == "12-month commitment, billed at the monthly floor"
    assert q.receipt["paper_only"] is True
    assert any("12-month commitment" in r for r in q.rationale)
    assert any("paper only" in r for r in q.rationale)


def test_enterprise_fail_closed():
    with pytest.raises(PriceError):
        quote_enterprise(0)
    with pytest.raises(PriceError):
        quote_enterprise(-3)
    with pytest.raises(PriceError):
        quote_enterprise(4.5)
    with pytest.raises(PriceError):
        quote_enterprise(True)
    with pytest.raises(PriceError):
        quote_enterprise(4, enterprise_rate=-10.0)
    with pytest.raises(PriceError):
        quote_enterprise(4, enterprise_rate="one hundred")


def test_seat_tiers_are_lifetime_one_time():
    # Standard/premium: lifetime, one-time per-seat buys — unchanged math.
    assert SEAT_TERM == "lifetime, one-time"
    q = quote_seat_price("standard", 1)
    assert q.receipt["term"] == "lifetime, one-time"
    assert any("lifetime, one-time" in r for r in q.rationale)


# --- CLI round-trip --------------------------------------------------


def _run_cli(argv):
    from levi.advisor.cli import cmd_advise, register_advisor_parser
    import argparse

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="advise_cmd")
    register_advisor_parser(sub)
    # register_advisor_parser adds "advise" under sub; parse accordingly
    args = parser.parse_args(argv)
    if args.advise_cmd == "advise":
        inner = argparse.ArgumentParser()
        isub = inner.add_subparsers(dest="advise_cmd")
        from levi.advisor.cli import _register_commands

        _register_commands(isub)
        args = inner.parse_args(argv[1:])
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        cmd_advise(args)
    finally:
        sys.stdout = old
    return buf.getvalue()


def test_cli_feature_round_trip():
    out = _run_cli(
        [
            "advise",
            "feature",
            "Voice notes",
            "--demand",
            "80",
            "--demand-basis",
            "test basis",
            "--fit",
            "0.9",
            "--cost",
            "small",
            "--doctrine",
            "0.9",
        ]
    )
    assert "verdict: BUILD" in out


def test_cli_price_round_trip():
    out = _run_cli(["advise", "price", "--tier", "entry", "--giant-price", "20"])
    assert "band: $" in out
    assert "seat cap: 19" in out

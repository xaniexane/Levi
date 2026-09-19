"""Tests for the Legion product tiers (core/levi/legion/tiers.py).

Paper-only throughout: no test here touches a payment rail, and the
suite asserts the tiers module carries none.
"""

import pytest

from levi.legion.product import LegionError
from levi.legion import tiers
from levi.legion.tiers import (
    GRADE_NEPHILIM,
    GRADE_STANDARD,
    NEPHILIM_FUSED_OPERATOR,
    PaperPrice,
    assert_no_payment_rails,
    get_tier,
    seat_operator_for_grade,
    tier_names,
    with_grade,
)


def test_tier_names():
    assert tier_names() == ["nephilim", "standard"]


def test_get_tier_roundtrip():
    assert get_tier("standard").key == GRADE_STANDARD
    assert get_tier("nephilim").key == GRADE_NEPHILIM
    assert get_tier("NEPHILIM").key == GRADE_NEPHILIM  # case-insensitive


def test_unknown_tier_rejected():
    with pytest.raises(LegionError):
        get_tier("enterprise")
    with pytest.raises(LegionError):
        get_tier("")
    with pytest.raises(LegionError):
        get_tier(None)


def test_nephilim_is_superset_of_standard():
    standard = get_tier("standard")
    nephilim = get_tier("nephilim")
    missing = [f for f in standard.features if f not in nephilim.features]
    assert missing == [], f"superset law violated, missing: {missing}"
    extra = [f for f in nephilim.features if f not in standard.features]
    assert extra, "Nephilim grade must add features above standard"


def test_grade_label_verbatim():
    assert get_tier("nephilim").grade_label == "nephilim"
    assert get_tier("standard").grade_label == "standard"


def test_all_prices_paper_labeled():
    for key in tier_names():
        spec = get_tier(key)
        price = spec.price_lifetime
        assert price.paper is True
        assert price.currency == "USD"
        assert price.mode == "paper"
        assert "paper" in price.label.lower()
        assert price.amount_usd > 0


def test_paper_price_rejects_non_paper():
    with pytest.raises(LegionError):
        PaperPrice(amount_usd=10.0, label="PAPER test", paper=False)
    with pytest.raises(LegionError):
        PaperPrice(amount_usd=10.0, label="no label here")
    with pytest.raises(LegionError):
        PaperPrice(amount_usd=0.0, label="PAPER zero")


def test_nephilim_price_is_premium_multiple_of_standard():
    std = get_tier("standard").price_lifetime.amount_usd
    neph = get_tier("nephilim").price_lifetime.amount_usd
    assert neph > std
    spec = get_tier("nephilim")
    assert spec.price_multiplier > 1.0
    assert neph == pytest.approx(std * spec.price_multiplier, rel=1e-6)


def test_no_payment_rails_in_tiers_module():
    assert_no_payment_rails()  # raises AssertionError on any real rail ref


def test_no_stripe_like_imports_anywhere_in_module_source():
    import inspect

    src = inspect.getsource(tiers).lower()
    for token in ("import stripe", "from stripe", "import paypal",
                  "from paypal", "import square", "import braintree"):
        assert token not in src


def test_with_grade_stamps_descriptor():
    d = {"name": "restaurant"}
    stamped = with_grade(d, "nephilim")
    assert stamped["grade"] == "nephilim"
    assert stamped["name"] == "restaurant"
    assert "grade" not in d  # never mutates the caller's dict


def test_with_grade_rejects_unknown():
    with pytest.raises(LegionError):
        with_grade({"name": "x"}, "platinum")
    with pytest.raises(LegionError):
        with_grade({"name": "x"}, "")


def test_seat_operator_for_grade():
    assert seat_operator_for_grade("nephilim") == NEPHILIM_FUSED_OPERATOR
    standard_op = seat_operator_for_grade("standard")
    assert standard_op != NEPHILIM_FUSED_OPERATOR
    with pytest.raises(LegionError):
        seat_operator_for_grade("platinum")


def test_nephilim_wiring_names_fused_seat():
    wiring = get_tier("nephilim").operator_wiring
    assert wiring["seat_operator"] == NEPHILIM_FUSED_OPERATOR
    assert wiring["escalation"] == "priority"
    assert wiring["seat_type"] == "nephilim-fused"


def test_standard_wiring_is_hybrid_on_demand():
    wiring = get_tier("standard").operator_wiring
    assert wiring["seat_type"] == "hybrid"
    assert wiring["twin_pair"] == "on-demand"
    assert wiring["seat_shape"] == "single-operator"
    assert wiring["bulk_tier"] == "nano-bit"


def test_quote_legion_tier_line_item_paper():
    from levi.legion.sale import quote_legion

    std = quote_legion()
    assert std.tier == "standard"
    neph = quote_legion(tier="nephilim")
    assert neph.tier == "nephilim"
    assert neph.total_usd > std.total_usd
    assert any("PAPER tier line item" in r for r in neph.rationale)
    assert any("no money moves" in r for r in neph.rationale)


def test_quote_legion_rejects_unknown_tier():
    from levi.legion.sale import quote_legion

    with pytest.raises(LegionError):
        quote_legion(tier="platinum")

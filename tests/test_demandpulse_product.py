"""Tests for the DemandPulse customer product definition.

Honesty is the product: price anchor, 12% cut, every shipped feature citing
its module, planned features never claimed as shipped, competitor-price
caveat always present.
"""

from levi.demandpulse import product


def test_price_anchor():
    assert product.PRICE_MONTHLY == 6.0
    assert product.PRICE_CURRENCY == "USD"


def test_platform_cut_named_constant():
    assert product.PLATFORM_CUT == 0.12
    # no magic numbers: the sheet must reference the constant, not a literal
    line = product.monthly_price_line()
    assert "$6/month" in line


def test_no_free_tier():
    assert product.NO_FREE_TIER is True
    assert product.ENTRY_TIERS == ("monthly",)


def test_every_shipped_feature_cites_a_module():
    for f in product.shipped_features():
        assert f["module"].startswith("levi."), f["name"]
        assert f["status"] == "shipped"


def test_planned_features_are_not_claimed_shipped():
    shipped = {f["name"] for f in product.shipped_features()}
    for f in product.planned_features():
        assert f["status"] == "planned"
        assert f["name"] not in shipped


def test_growth_shape_not_claimed():
    names = [f["name"] for f in product.shipped_features()]
    assert not any("Growth-shape" in n for n in names)


def test_honest_limits_present():
    assert len(product.HONEST_LIMITS) >= 4
    joined = " ".join(product.HONEST_LIMITS)
    assert "not configured" in joined  # push/email
    assert "HYPOTHESIS" in joined


def test_product_sheet_is_hq_decision_5_verbatim():
    # HQ Decision 5, approved 2026-09-24 (Chauncey's word): product_sheet()
    # returns the decided copy verbatim — no paraphrase, no trimming.
    assert product.product_sheet() == product.PRODUCT_SHEET_HQ5


def test_product_sheet_has_honest_limits_and_terms_anchor():
    sheet = product.product_sheet()
    assert "**DemandPulse — $6/month**" in sheet
    assert "What $6/month buys" in sheet
    assert "Honest limits:" in sheet
    assert "quarantined, never published" in sheet
    assert "7-day refund: full $6 back, no questions" in sheet
    assert "$DirectDepositDaemon" in sheet
    # roadmap items are named as roadmap, never claimed
    assert "Growth-shape classification and meta-trend roll-ups are on the roadmap" in sheet


def test_exclusives_nonempty():
    assert len(product.EXCLUSIVES) >= 4
    joined = " ".join(product.EXCLUSIVES)
    assert "QUARANTINED" in joined
    assert "founder's" in joined

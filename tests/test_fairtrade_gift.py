"""Tests for the Gift Ledger (core/levi/fairtrade/gift.py)."""

import pytest

from levi.fairtrade.gift import (
    GIFT_CATALOG,
    GiftOffer,
    catalog_ids,
    get_gift,
    gift_receipt,
    price_of_free,
)


def _clean_gift(**kw):
    base = dict(
        giver="LEVI",
        name="Local Notebook",
        gift_pitch="a free local notebook that lives on your machine",
        extraction=[],
        declares_nothing_taken=True,
    )
    base.update(kw)
    return GiftOffer(**base)


def test_refuses_unnamed_gift():
    with pytest.raises(ValueError):
        GiftOffer(giver="X", name=" ", gift_pitch="free!", extraction=[])


def test_refuses_unnamed_giver():
    with pytest.raises(ValueError):
        GiftOffer(giver="", name="Thing", gift_pitch="free!", extraction=[])


def test_refuses_undeclared_extraction_without_flag():
    # The whole point of the ledger: a "free" gift that declares nothing
    # taken and won't admit the extraction is unknown gets refused.
    with pytest.raises(ValueError):
        GiftOffer(giver="X", name="Thing", gift_pitch="free!")


def test_clean_gift_scores_100():
    priced = price_of_free(_clean_gift())
    assert priced["honesty_score"] == 100
    assert priced["verdict"] == "honest gift"
    assert priced["takes"] == []


def test_unknown_extraction_capped_at_20():
    priced = price_of_free(_clean_gift(extraction_unknown=True))
    assert priced["honesty_score"] <= 20
    assert "not a gift" in priced["verdict"] or "extraction" in priced["verdict"]


def test_onavo_scores_near_zero():
    onavo = get_gift("Onavo Protect")
    priced = price_of_free(onavo)
    assert priced["honesty_score"] <= 40
    assert "trade" in priced["verdict"] or "not a gift" in priced["verdict"]


def test_gwx_penalized_for_irreversible_consent():
    gwx = get_gift("Windows 10 free upgrade (GWX campaign)")
    priced = price_of_free(gwx)
    assert any("one-way" in f for f in priced["findings"])
    assert priced["honesty_score"] <= 55


def test_receipt_names_what_it_takes():
    receipt = gift_receipt(get_gift("Google Assistant (contractor review era)"))
    assert "WHAT IT TAKES: voice recordings; training data." in receipt
    assert "GIFT RECEIPT" in receipt
    assert "a gift with no receipt is a bill" in receipt


def test_receipt_says_undeclared_plainly():
    receipt = gift_receipt(_clean_gift(extraction_unknown=True))
    assert "undeclared" in receipt


def test_score_scales_with_extraction_count():
    one = price_of_free(_clean_gift(extraction=["telemetry"]))
    two = price_of_free(_clean_gift(extraction=["telemetry", "browsing data"]))
    assert one["honesty_score"] > two["honesty_score"]


def test_catalog_covers_the_hunt():
    assert len(catalog_ids()) >= 3
    assert "Onavo Protect" in catalog_ids()


def test_price_of_free_rejects_non_offer():
    with pytest.raises(ValueError):
        price_of_free({"name": "not an offer"})

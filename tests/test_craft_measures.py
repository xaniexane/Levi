"""Hermetic tests for levi.craft.measures — the museum of dead measures."""

import pytest

from levi.craft import measures


def test_convert_chain_to_metres():
    # Gunter's chain: 22 yards = 20.1168 m
    assert measures.convert(1, "chain", "m") == pytest.approx(20.1168, rel=1e-6)


def test_convert_links_chain():
    assert measures.convert(100, "link", "chain") == pytest.approx(1.0)


def test_gunter_decimal_trick():
    # 10 square chains = 1 acre exactly; area math by decimal shift.
    assert measures.chain_area(47) == pytest.approx(4.7)
    sqm = measures.convert(4.7, "acre", "m")
    assert sqm == pytest.approx(4.7 * 4046.8564224, rel=1e-6)


def test_convert_furlong_mile():
    assert measures.convert(8, "furlong", "mile") == pytest.approx(1.0)


def test_seked_slope_as_ratio():
    # A 7-palm run per 1-cubit rise is a 45-degree seked of 7.
    assert measures.seked(1.0, 1.0) == pytest.approx(7.0)
    with pytest.raises(ValueError):
        measures.seked(0, 1.0)


def test_egyptian_subdivisions():
    assert measures.convert(1, "royal-cubit", "palm") == pytest.approx(7.0)
    assert measures.convert(1, "royal-cubit", "digit") == pytest.approx(28.0)


def test_roman_actus():
    assert measures.convert(1, "actus", "pes") == pytest.approx(120.0)
    assert measures.convert(1, "passus", "pes") == pytest.approx(5.0)


def test_barleycorn_inch():
    assert measures.convert(3, "barleycorn", "inch") == pytest.approx(1.0)


def test_talent_mina_shekel():
    assert measures.convert(1, "talent", "mina") == pytest.approx(60.0)
    assert measures.convert(1, "mina", "shekel") == pytest.approx(60.0)


def test_dimension_mismatch_refused():
    # The museum refuses to weigh a furlong.
    with pytest.raises(ValueError, match="dimension mismatch"):
        measures.convert(1, "furlong", "shekel")


def test_unknown_unit():
    with pytest.raises(KeyError):
        measures.convert(1, "smoot", "m")


def test_symbol_lookup():
    assert measures.get_unit("ch").name == "chain"
    assert measures.get_unit("RC").name == "royal-cubit"


def test_describe_carries_provenance():
    card = measures.describe("royal-cubit")
    assert card["master_standard"]
    assert card["si_unit"] == "m"
    assert card["regional_variant"] is False


def test_variant_flagged_honestly():
    assert measures.describe("braccio")["regional_variant"] is True
    assert measures.describe("shekel")["regional_variant"] is True


def test_master_chain():
    chain = measures.master_chain("chain")
    assert "Gunter" in chain


def test_list_units_filter():
    egyptian = measures.list_units("egyptian")
    assert {u.name for u in egyptian} == {"royal-cubit", "palm", "digit"}
    assert len(measures.list_units()) >= 20


def test_toise_replaced_by_metre():
    # Sanity: the toise is ~1.949 m, the unit the metre dethroned.
    assert measures.convert(1, "toise", "m") == pytest.approx(1.949, rel=1e-3)

"""Tests for revival wave 05 — crafts (c): treaties, convergence, containers,
pricing measures, reactive reserve, trace dopants, sacrificial models, ink."""

import pytest

from core.levi.revival import arshin_treaty as at
from core.levi.revival import weight_convergence as wc
from core.levi.revival import container_units as cu
from core.levi.revival import measure_pricing as mp
from core.levi.revival import reactive_reserve as rr
from core.levi.revival import trace_dopants as td
from core.levi.revival import sacrificial_model as sm
from core.levi.revival import biting_ink as bi


# ---------------------------------------------------------------------------
# arshin_treaty
# ---------------------------------------------------------------------------


def test_arshin_treaty_conversion_through_peg():
    reg = at.arshin_treaty_registry()
    value, pegged = reg.convert(2.0, "arshin", "english_inch")
    assert value == pytest.approx(56.0)
    assert pegged is True
    back, pegged = reg.convert(56.0, "english_inch", "arshin")
    assert back == pytest.approx(2.0)
    assert pegged is True


def test_arshin_treaty_ratify_is_immutable_and_verifiable():
    reg = at.arshin_treaty_registry()
    assert reg.verify_pegs() is True
    pegs = reg.pegs()
    assert len(pegs) == 1
    assert pegs[0].ratio_a_per_b == pytest.approx(28.0)
    # No audit violations while definitions match the treaty.
    assert reg.audit() == []


def test_arshin_treaty_drift_detected_as_violation():
    reg = at.arshin_treaty_registry()
    # A party quietly redefines its inch: the peg does not move.
    reg.define_unit("english_inch", "english", 1.1)
    violations = reg.audit()
    assert len(violations) == 1
    v = violations[0]
    assert v.unit_a == "arshin" and v.unit_b == "english_inch"
    assert v.drift > 0.05
    # But the peg chain itself is still intact.
    assert reg.verify_pegs() is True


def test_arshin_treaty_unpegged_conversion_falls_back():
    reg = at.arshin_treaty_registry()
    value, pegged = reg.convert(1.0, "verst", "arshin")
    assert value == pytest.approx(1500.0)
    assert pegged is False


# ---------------------------------------------------------------------------
# weight_convergence
# ---------------------------------------------------------------------------


def test_weight_convergence_spread_shrinks():
    standards = {
        "tyre": 11.2,
        "ur": 9.1,
        "gaza": 12.4,
        "byblos": 8.3,
        "sidon": 10.0,
        "ugarit": 13.1,
    }
    report = wc.cross_check(standards, rounds=80, seed=3)
    assert report.final_spread < report.initial_spread
    assert report.converged is True
    assert len(report.history) == 81


def test_weight_convergence_is_deterministic():
    standards = {"a": 9.0, "b": 12.0, "c": 10.5}
    r1 = wc.cross_check(standards, rounds=40, seed=11)
    r2 = wc.cross_check(standards, rounds=40, seed=11)
    assert r1.consensus == pytest.approx(r2.consensus)
    assert r1.history == r2.history


def test_weight_convergence_trust_rewards_agreement():
    standards = {"a": 10.0, "b": 10.05, "c": 10.1, "d": 9.95, "outlier": 12.5}
    report = wc.cross_check(standards, rounds=80, seed=5)
    row = report.final_trust["a"]
    peers = wc.trusted_peers(row, threshold=0.6)
    assert set(peers) == {"b", "c", "d"}
    assert row["outlier"] < row["b"]  # the outlier never earns trust


def test_weight_convergence_rejects_bad_input():
    with pytest.raises(ValueError):
        wc.cross_check({}, rounds=10)
    with pytest.raises(ValueError):
        wc.cross_check({"a": 10.0}, rounds=10, nudge=0.0)


# ---------------------------------------------------------------------------
# container_units
# ---------------------------------------------------------------------------


def test_container_ladder_doubling_and_volume():
    ladder = cu.beer_ladder()
    assert ladder.rungs() == ["firkin", "kilderkin", "barrel", "hogshead", "butt"]
    assert ladder.double_up("firkin") == "kilderkin"
    assert ladder.volume_gallons("hogshead") == pytest.approx(54.0)
    assert ladder.volume_cubic_inches("firkin") == pytest.approx(9 * 282.0)


def test_container_ladder_commodity_specific_gallon():
    beer = cu.beer_ladder()
    wine = cu.wine_ladder()
    # Same rung name, different gallons: the tax policy lives in the volume.
    assert beer.volume_gallons("hogshead") == pytest.approx(54.0)
    assert wine.volume_gallons("hogshead") == pytest.approx(63.0)
    assert wine.volume_cubic_inches("hogshead") == pytest.approx(63 * 231.0)


def test_container_ladder_excise_encoded_in_volume():
    ladder = cu.beer_ladder(excise_per_gallon=0.05)
    assert ladder.excise_due("barrel", 2) == pytest.approx(2 * 36 * 0.05)
    gallons, duty = ladder.shipment({"firkin": 4, "barrel": 1})
    assert gallons == pytest.approx(4 * 9 + 36)
    assert duty == pytest.approx(gallons * 0.05)


def test_container_ladder_custom_and_top_rung():
    ladder = cu.custom("mead", 250.0, {"cup": 1, "jug": 4}, 0.02)
    assert ladder.volume_gallons("jug", 3) == pytest.approx(12.0)
    with pytest.raises(ValueError):
        ladder.double_up("jug")


# ---------------------------------------------------------------------------
# measure_pricing
# ---------------------------------------------------------------------------


def test_measure_pricing_shorter_arm_costs_more():
    g = mp.cloth_market()
    quoted = 10.0  # same quoted price per braccio
    silk = g.price_per_meter(quoted, "silk_braccio")
    wool = g.price_per_meter(quoted, "wool_braccio")
    assert silk > wool  # shorter measure -> higher true price per meter


def test_measure_pricing_edge_quantifies_policy():
    g = mp.cloth_market()
    edge = g.pricing_edge("silk_braccio", "wool_braccio")
    assert edge["length_ratio_a_to_b"] == pytest.approx(0.583 / 0.680)
    assert edge["shorter_by_pct"] == pytest.approx((1 - 0.583 / 0.680) * 100)
    assert edge["price_premium_factor"] == pytest.approx(0.680 / 0.583)


def test_measure_pricing_compare_and_authority():
    g = mp.cloth_market()
    rows = g.compare("silk", quoted_per_measure=10.0)
    names = [r[0] for r in rows]
    assert "silk_braccio" in names and "generic_braccio" in names
    assert "wool_braccio" not in names  # wool measure doesn't apply to silk
    # Cheapest true price per meter first.
    assert rows[0][2] <= rows[-1][2]
    assert g.authority_of("silk_braccio") == "silk_guild"


# ---------------------------------------------------------------------------
# reactive_reserve
# ---------------------------------------------------------------------------


def test_reactive_reserve_heals_while_reserve_lasts():
    slab = rr.Slab(cracks=[2.0], clasts=[5.0])
    before = slab.damage()
    delta = slab.cycle(stress=1.0)
    assert delta < 0  # net healing
    assert slab.damage() < before
    assert slab.heal_reserve() < 5.0  # reserve was spent


def test_reactive_reserve_no_healing_when_spent():
    slab = rr.Slab(cracks=[3.0], clasts=[0.0])
    before = slab.damage()
    slab.cycle(stress=1.0)
    assert slab.damage() > before  # cracks grow unchecked
    assert slab.integrity() < 1.0


def test_reactive_reserve_integrity_and_stress_events():
    slab = rr.Slab()
    assert slab.integrity() == pytest.approx(1.0)
    slab.stress_event(4.0)
    assert slab.integrity() == pytest.approx(0.6)
    with pytest.raises(ValueError):
        slab.stress_event(-1.0)
    rep = slab.report()
    assert rep["damage_mm"] == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# trace_dopants
# ---------------------------------------------------------------------------


def test_trace_dopants_peak_near_optimum():
    peak = td.banding_index(td.OPTIMUM_PPM, cooling_rate=1.0)
    low = td.banding_index(10.0, cooling_rate=1.0)
    high = td.banding_index(5000.0, cooling_rate=1.0)
    assert peak == pytest.approx(1.0)
    assert low < peak and high < peak
    assert td.macrostructure(td.OPTIMUM_PPM) == "banded"
    assert td.macrostructure(1.0) == "dendritic"


def test_trace_dopants_cooling_amplifies():
    slow = td.banding_index(300.0, cooling_rate=0.2)
    fast = td.banding_index(300.0, cooling_rate=3.0)
    assert fast >= slow


def test_trace_dopants_recommend_minimum_effective_dose():
    plan = td.recommend(0.9, cooling_rate=1.0, max_ppm=1000.0)
    assert abs(plan.expected_index - 0.9) <= 0.05
    assert plan.headroom_ppm >= 0
    assert plan.dopant_ppm <= 1000.0
    # Smaller dose that also hits the target should not exist far below.
    smaller = td.banding_index(plan.dopant_ppm - 50.0, 1.0)
    assert abs(smaller - 0.9) >= abs(plan.expected_index - 0.9) - 1e-9


def test_trace_dopants_unreachable_target_raises():
    with pytest.raises(ValueError):
        td.recommend(0.99, cooling_rate=0.05, max_ppm=50.0)


# ---------------------------------------------------------------------------
# sacrificial_model
# ---------------------------------------------------------------------------


def test_sacrificial_model_lifecycle():
    m = sm.SacrificialModel.build("draft-1")
    m.write("a", 1)
    m.write("b", 2)
    m.transform("a", lambda x: x * 10)
    assert m.read("a") == 10
    assert m.operations == 3
    result = m.derive({"total": 12})
    assert result.model_name == "draft-1"
    receipt = m.burnout()
    assert receipt.operations == 3
    assert receipt.result_digest == result.digest
    assert receipt.verify() is True


def test_sacrificial_model_burn_blocks_access():
    m = sm.SacrificialModel.build("secret")
    m.write("k", "v")
    m.burnout()
    with pytest.raises(sm.BurnedOutError):
        m.read("k")
    with pytest.raises(sm.BurnedOutError):
        m.write("k2", "v2")
    with pytest.raises(sm.BurnedOutError):
        m.derive("x")
    # Burnout is idempotent: same receipt back.
    assert m.burnout() is m.receipt


def test_sacrificial_model_erase_and_burn_without_derive():
    m = sm.SacrificialModel.build("scratch")
    m.write("tmp", [1, 2, 3])
    m.erase("tmp")
    assert m.keys() == ()
    receipt = m.burnout()
    assert receipt.result_digest is None
    assert receipt.verify() is True


# ---------------------------------------------------------------------------
# biting_ink
# ---------------------------------------------------------------------------


def test_biting_ink_chain_verifies():
    ledger = bi.InkLedger()
    ledger.etch("first charter")
    ledger.etch("second charter")
    ledger.etch("third charter")
    ok, bad = ledger.verify()
    assert ok is True and bad is None
    assert len(ledger) == 3


def test_biting_ink_tamper_detected_at_right_link():
    ledger = bi.InkLedger()
    ledger.etch("alpha")
    ledger.etch("beta")
    ledger.etch("gamma")
    # Quietly rewrite the middle record's payload (same object layout).
    entries = ledger._entries
    tampered = bi.InkEntry(
        index=entries[1].index,
        payload="BETA (forged)",
        payload_digest=entries[1].payload_digest,  # stale digest
        prev_seal=entries[1].prev_seal,
        seal=entries[1].seal,
    )
    entries[1] = tampered
    ok, bad = ledger.verify()
    assert ok is False and bad == 1


def test_biting_ink_strength_grows_with_age():
    ledger = bi.InkLedger()
    ledger.etch("one")
    assert ledger.bite_strength(0) == 0
    ledger.etch("two")
    ledger.etch("three")
    assert ledger.bite_strength(0) == 2  # oldest bites deepest
    assert ledger.bite_strength(2) == 0
    report = ledger.etch_report()
    assert [r[2] for r in report] == [2, 1, 0]
    with pytest.raises(IndexError):
        ledger.bite_strength(9)

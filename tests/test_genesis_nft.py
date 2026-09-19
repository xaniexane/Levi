"""Tests for the genesis NFT economics + buyback treasury (levi.genesis.nft).

Keeper's canon (2026-09-18): the one-time lifetime copies ARE NFTs; each
year mints a capped number; any holder can opt out their weight through
the buyback treasury; the design must make value rise.

PAPER ONLY. Every figure here is paper; no chain, no funds.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from levi.genesis.nft import draw, economics, contract, simulate, treasury
from levi.genesis.nft.economics import (
    ANNUAL_SERIES_CAP_MIN,
    NftEconomicsError,
    build_master_token_metadata,
    build_token_metadata,
    check_white_label,
    framework_for_n,
    license_summary,
    master_token_id_for,
    reference_royalty,
    series_id_for,
    split_primary_revenue,
    token_id_for,
    usd,
)
from levi.genesis.nft.ledger import SeriesLedger
from levi.genesis.nft.treasury import Treasury


# ---------------------------------------------------------------------------
# economics — money math
# ---------------------------------------------------------------------------

class TestMoneyMath:
    def test_usd(self):
        assert usd(5_000) == "$50.00"
        assert usd(1) == "$0.01"
        assert usd(0) == "$0.00"

    def test_split_rates(self):
        split = split_primary_revenue(5_000, 1)
        assert split == {"keeper": 2_500, "pool": 1_500, "treasury": 1_000}

    @pytest.mark.parametrize("price,count", [(5_000, 1), (9_999, 3), (1, 7), (123_456, 11)])
    def test_split_always_sums_to_gross(self, price, count):
        split = split_primary_revenue(price, count)
        assert sum(split.values()) == price * count
        assert all(v >= 0 for v in split.values())

    def test_split_rejects_nonpositive(self):
        with pytest.raises(ValueError):
            split_primary_revenue(0, 1)

    def test_royalty_math(self):
        assert reference_royalty(10_000) == 750  # 7.5% of $100
        assert reference_royalty(999) == 75  # half-up: 74.925 -> 75
        assert reference_royalty(1) == 0
        assert reference_royalty(0) == 0

    def test_royalty_rejects_negative(self):
        with pytest.raises(ValueError):
            reference_royalty(-1)


# ---------------------------------------------------------------------------
# economics — white-label law
# ---------------------------------------------------------------------------

class TestWhiteLabel:
    def test_accepts_business_name(self):
        assert check_white_label("Acme Schools") == "Acme Schools"

    def test_rejects_empty(self):
        with pytest.raises(NftEconomicsError):
            check_white_label("   ")

    def test_rejects_levi_branding(self):
        with pytest.raises(NftEconomicsError):
            check_white_label("Levi Learning Co")

    def test_rejects_too_long(self):
        with pytest.raises(NftEconomicsError):
            check_white_label("x" * 121)


# ---------------------------------------------------------------------------
# economics — token design
# ---------------------------------------------------------------------------

PACK_ID = "gen-pack-abc123def456"
PACK_HASH = "f" * 64


class TestTokenDesign:
    def test_token_id_deterministic(self):
        assert token_id_for(PACK_ID, "GENESIS-2026") == token_id_for(PACK_ID, "GENESIS-2026")

    def test_token_id_unique_per_series(self):
        a = token_id_for(PACK_ID, "GENESIS-2026")
        b = token_id_for(PACK_ID, "GENESIS-2027")
        assert a != b

    def test_token_id_is_uint256(self):
        assert 0 <= token_id_for(PACK_ID, "GENESIS-2026") < 2**256

    def test_series_id_format(self):
        assert series_id_for(2026) == "GENESIS-2026"

    def test_series_id_rejects_bad_year(self):
        with pytest.raises(NftEconomicsError):
            series_id_for(1999)

    def test_metadata_anchors_pack_hash(self):
        md = build_token_metadata(
            pack_id=PACK_ID,
            pack_final_hash=PACK_HASH,
            series_id="GENESIS-2026",
            buyer_name="Acme Schools",
            agent_count=5,
        )
        assert md["pack_id"] == PACK_ID
        assert md["pack_final_hash"] == PACK_HASH
        assert md["token_id"] == token_id_for(PACK_ID, "GENESIS-2026")
        assert md["buyer_business"] == "Acme Schools"
        assert "LEVI" not in md["name"] or "Genesis" in md["name"]

    def test_metadata_enforces_odd_law(self):
        with pytest.raises(NftEconomicsError):
            build_token_metadata(
                pack_id=PACK_ID,
                pack_final_hash=PACK_HASH,
                series_id="GENESIS-2026",
                buyer_name="Acme Schools",
                agent_count=4,  # even — refused
            )

    def test_metadata_rejects_bad_hash(self):
        with pytest.raises(NftEconomicsError):
            build_token_metadata(
                pack_id=PACK_ID,
                pack_final_hash="not-a-hash",
                series_id="GENESIS-2026",
                buyer_name="Acme Schools",
                agent_count=3,
            )

    def test_metadata_rejects_missing_pack(self):
        with pytest.raises(NftEconomicsError):
            build_token_metadata(
                pack_id="",
                pack_final_hash=PACK_HASH,
                series_id="GENESIS-2026",
                buyer_name="Acme Schools",
                agent_count=3,
            )

    def test_metadata_carries_agent_roster(self):
        md = build_token_metadata(
            pack_id=PACK_ID,
            pack_final_hash=PACK_HASH,
            series_id="GENESIS-2026",
            buyer_name="Acme Schools",
            agent_count=3,
            agent_roster=[
                {"name": "Harbor", "theme": "tide-caller"},
                {"name": "Flint", "theme": "spark-keeper"},
                {"name": "Vesper", "theme": "dusk-runner"},
            ],
        )
        assert [a["name"] for a in md["agents"]] == ["Harbor", "Flint", "Vesper"]
        assert md["agents"][0]["theme"] == "tide-caller"

    def test_metadata_roster_must_match_count(self):
        with pytest.raises(NftEconomicsError):
            build_token_metadata(
                pack_id=PACK_ID,
                pack_final_hash=PACK_HASH,
                series_id="GENESIS-2026",
                buyer_name="Acme Schools",
                agent_count=3,
                agent_roster=[{"name": "Harbor"}],
            )

    def test_metadata_roster_agents_must_be_named(self):
        with pytest.raises(NftEconomicsError):
            build_token_metadata(
                pack_id=PACK_ID,
                pack_final_hash=PACK_HASH,
                series_id="GENESIS-2026",
                buyer_name="Acme Schools",
                agent_count=1,
                agent_roster=[{"theme": "nameless"}],
            )


# ---------------------------------------------------------------------------
# economics — the annual-N framework + license terms
# ---------------------------------------------------------------------------

class TestSeriesFramework:
    def test_framework_math(self):
        fw = framework_for_n(revenue_target_cents=1_000_000, mint_price_cents=5_000)
        assert fw["implied_n_rounded"] == 200
        assert fw["decision"].startswith("TBD")

    def test_framework_rejects_bad_inputs(self):
        with pytest.raises(NftEconomicsError):
            framework_for_n(revenue_target_cents=0, mint_price_cents=5_000)

    def test_license_terms_are_securities_safe(self):
        terms = license_summary()
        promises = " ".join(terms["no_profit_promises"]).lower()
        assert "no profit" in promises
        assert "no rising value" in promises
        assert "lawyer" in terms["legal"].lower()
        assert "raise a published cap" in " ".join(terms["forbidden"])


# ---------------------------------------------------------------------------
# contract — interface spec + conformance
# ---------------------------------------------------------------------------

def _good_ledger():
    return {
        "series": {
            "GENESIS-2026": {
                "cap": 100,
                "cap_history": [100],
                "minted": 60,
                "burned": 5,
                "treasury": "0xtreasury",
                "royalty_events": [(10_000, 750, "0xtreasury")],
            }
        }
    }


class TestContractSpec:
    def test_interface_covers_lifecycle(self):
        names = {f["name"] for f in contract.INTERFACE}
        for required in ("createSeries", "mint", "burn", "royaltyInfo",
                         "seriesOf", "seriesSupply", "seriesCap", "seriesFloor"):
            assert required in names

    def test_standards(self):
        assert contract.TOKEN_STANDARD == "ERC-721"
        assert contract.ROYALTY_STANDARD == "EIP-2981"

    def test_chain_choice_stays_keepers(self):
        rec = contract.CHAIN_RECOMMENDATION
        assert rec["recommended"]  # a recommendation exists...
        assert "keeper" in rec["decision"].lower()  # ...but he decides

    def test_conformance_passes_on_good_ledger(self):
        assert contract.check_conformance(_good_ledger())["ok"] is True

    def test_conformance_catches_raised_cap(self):
        ledger = _good_ledger()
        ledger["series"]["GENESIS-2026"]["cap_history"] = [100, 150]
        assert contract.check_conformance(ledger)["ok"] is False

    def test_conformance_catches_supply_over_cap(self):
        ledger = _good_ledger()
        ledger["series"]["GENESIS-2026"]["minted"] = 106  # 106 - 5 burned = 101 > cap 100
        result = contract.check_conformance(ledger)
        assert result["series"]["GENESIS-2026"]["supply-within-cap"] is False

    def test_conformance_catches_wrong_royalty_receiver(self):
        ledger = _good_ledger()
        ledger["series"]["GENESIS-2026"]["royalty_events"] = [(10_000, 750, "0xthief")]
        result = contract.check_conformance(ledger)
        assert result["series"]["GENESIS-2026"]["royalty-exact"] is False

    def test_conformance_catches_wrong_royalty_amount(self):
        ledger = _good_ledger()
        ledger["series"]["GENESIS-2026"]["royalty_events"] = [(10_000, 700, "0xtreasury")]
        result = contract.check_conformance(ledger)
        assert result["series"]["GENESIS-2026"]["royalty-exact"] is False

    def test_liquidity_bound(self):
        assert contract.invariant_floor_liquidity_bounded({}, "s", 4_000, 100_000, 5_000)
        assert not contract.invariant_floor_liquidity_bounded({}, "s", 6_000, 100_000, 5_000)
        # one-bid minimum: a thin treasury may still honor one floor bid
        assert contract.invariant_floor_liquidity_bounded({}, "s", 5_000, 1_000, 5_000)


# ---------------------------------------------------------------------------
# treasury — the floor, the queue, the burn
# ---------------------------------------------------------------------------

def _funded_series(cap=100, mint=5_000, primary=10):
    t = Treasury()
    t.create_series("GENESIS-2026", cap=cap, mint_price_cents=mint)
    t.fund_primary("GENESIS-2026", mint, primary)
    return t


class TestTreasury:
    def test_create_and_view(self):
        t = _funded_series()
        v = t.series_view("GENESIS-2026")
        assert v["cap"] == 100
        assert v["outstanding"] == 10
        assert v["balance_cents"] == 10_000  # 20% of 10 x $50
        assert v["floor_cents"] == 5_000  # backing $10 < mint $50

    def test_cap_never_raised(self):
        t = Treasury()
        t.create_series("GENESIS-2026", cap=100, mint_price_cents=5_000)
        with pytest.raises(NftEconomicsError):
            t.lower_cap("GENESIS-2026", 150)

    def test_cap_lower_before_mint_ok(self):
        t = Treasury()
        t.create_series("GENESIS-2026", cap=100, mint_price_cents=5_000)
        t.lower_cap("GENESIS-2026", 80)
        assert t.series_view("GENESIS-2026")["cap"] == 80

    def test_cap_frozen_after_mint(self):
        t = _funded_series()
        with pytest.raises(NftEconomicsError):
            t.lower_cap("GENESIS-2026", 80)

    def test_mint_beyond_cap_refused(self):
        t = _funded_series(cap=10, primary=10)
        with pytest.raises(NftEconomicsError):
            t.fund_primary("GENESIS-2026", 5_000, 1)

    def test_floor_is_max_of_mint_and_backing(self):
        t = _funded_series()
        # thin backing -> floor rests on mint price
        assert t.floor_price_cents("GENESIS-2026") == 5_000
        # royalties lift backing above mint -> floor follows backing
        t.fund_royalty("GENESIS-2026", 60_000)
        assert t.floor_price_cents("GENESIS-2026") == 7_000

    def test_backing_invariant_at_full_backing(self):
        """Buybacks at full backing leave backing-per-token unchanged."""
        t = _funded_series()
        t.fund_royalty("GENESIS-2026", 40_000)  # T=50k, S=10 -> backing $50 = mint
        before = t.backing_per_token("GENESIS-2026")
        assert before == Fraction(5_000, 1)
        t.request_buyback("GENESIS-2026", "alice", 1)
        t.settle_epoch("GENESIS-2026")
        after = t.backing_per_token("GENESIS-2026")
        assert abs(after - before) <= Fraction(1, 1)  # within a cent

    def test_buyback_burns(self):
        t = _funded_series()
        t.top_up("GENESIS-2026", 100_000)
        t.request_buyback("GENESIS-2026", "alice", 7)
        t.settle_epoch("GENESIS-2026")
        assert t.series_view("GENESIS-2026")["burned"] == 1
        assert t.outstanding("GENESIS-2026") == 9

    def test_epoch_budget_bounds_outflow(self):
        t = Treasury()
        t.create_series("GENESIS-2026", cap=1_000, mint_price_cents=5_000)
        t.fund_primary("GENESIS-2026", 5_000, 100)
        t.top_up("GENESIS-2026", 900_000)  # deep: T=$10k, backing $100 > mint
        # floor $100, budget = 5% of $10k = $500 -> 5 per epoch
        for i in range(8):
            t.request_buyback("GENESIS-2026", "holder-%d" % i, i)
        r = t.settle_epoch("GENESIS-2026")
        assert len(r["settled"]) == 5
        assert t.series_view("GENESIS-2026")["queued"] == 3

    def test_one_bid_minimum_on_thin_treasury(self):
        t = _funded_series(primary=20)  # T=$200, floor $50
        for i in range(3):
            t.request_buyback("GENESIS-2026", "holder-%d" % i, i)
        r = t.settle_epoch("GENESIS-2026")
        assert len(r["settled"]) == 1  # the door opens, once
        assert t.series_view("GENESIS-2026")["queued"] == 2

    def test_never_pays_what_it_does_not_hold(self):
        t = _funded_series(primary=1)  # T=$10 < floor $50
        t.request_buyback("GENESIS-2026", "alice", 1)
        r = t.settle_epoch("GENESIS-2026")
        assert r["settled"] == []
        assert t.series_view("GENESIS-2026")["balance_cents"] == 1_000
        assert t.check_solvency("GENESIS-2026")

    def test_receipts_verify(self):
        t = _funded_series()
        t.request_buyback("GENESIS-2026", "alice", 1)
        t.settle_epoch("GENESIS-2026")
        assert t.verify_receipts()

    def test_top_up(self):
        t = _funded_series()
        t.top_up("GENESIS-2026", 25_000, source="keeper")
        assert t.series_view("GENESIS-2026")["balance_cents"] == 35_000


# ---------------------------------------------------------------------------
# ledger — each year's N, in writing
# ---------------------------------------------------------------------------

class TestSeriesLedger:
    def test_floor_is_a_thousand(self):
        assert ANNUAL_SERIES_CAP_MIN == 1000

    def test_records_and_reads(self):
        led = SeriesLedger()
        led.record_year(2027, 1000, decided_by="keeper")
        assert led.get_n(2027) == 1000
        assert led.verify_ledger()

    def test_higher_n_allowed(self):
        led = SeriesLedger()
        led.record_year(2027, 2500, decided_by="keeper")
        assert led.get_n(2027) == 2500

    def test_sub_floor_refused_without_override(self):
        led = SeriesLedger()
        with pytest.raises(NftEconomicsError):
            led.record_year(2027, 500)
        assert led.get_n(2027) is None  # nothing banked — the refusal left no trace

    def test_sub_floor_allowed_with_explicit_override(self):
        led = SeriesLedger()
        led.record_year(2027, 500, override=True, decided_by="keeper")
        assert led.get_n(2027) == 500
        rec = led.year_record(2027)
        assert rec["sub_floor_override"] is True  # the override is on the record

    def test_double_record_refused(self):
        led = SeriesLedger()
        led.record_year(2027, 1000)
        with pytest.raises(NftEconomicsError):
            led.record_year(2027, 1200)  # a published N is never re-decided
        assert led.get_n(2027) == 1000

    def test_require_n_refuses_unbanked_year(self):
        led = SeriesLedger()
        with pytest.raises(NftEconomicsError):
            led.require_n(2028)

    def test_bad_year_refused(self):
        led = SeriesLedger()
        with pytest.raises(NftEconomicsError):
            led.record_year(1999, 1000)

    def test_decided_by_required(self):
        led = SeriesLedger()
        with pytest.raises(NftEconomicsError):
            led.record_year(2027, 1000, decided_by="")


# ---------------------------------------------------------------------------
# treasury gate — no ledgered N, no mint
# ---------------------------------------------------------------------------

def _ledgered(year=2027, n=1000):
    led = SeriesLedger()
    led.record_year(year, n, decided_by="keeper")
    return led


class TestMintGate:
    def test_series_without_ledger_record_refused(self):
        led = SeriesLedger()  # nothing banked
        t = Treasury()
        with pytest.raises(NftEconomicsError):
            t.create_series("GENESIS-2027", 1000, 5_000, ledger=led)

    def test_cap_must_match_banked_n(self):
        t = Treasury()
        with pytest.raises(NftEconomicsError):
            t.create_series("GENESIS-2027", 999, 5_000, ledger=_ledgered())

    def test_ledgered_series_opens(self):
        t = Treasury()
        t.create_series("GENESIS-2027", 1000, 5_000, ledger=_ledgered())
        assert t.series_view("GENESIS-2027")["cap"] == 1000

    def test_mint_1001_refused(self):
        t = Treasury()
        t.create_series("GENESIS-2027", 1000, 5_000, ledger=_ledgered())
        t.fund_primary("GENESIS-2027", 5_000, 1000)  # the full thousand mints
        assert t.outstanding("GENESIS-2027") == 1000
        with pytest.raises(NftEconomicsError):
            t.fund_primary("GENESIS-2027", 5_000, 1)  # #1001 refused

    def test_no_ledger_keeps_old_behavior(self):
        t = Treasury()  # no ledger passed: the old paper path still works
        t.create_series("GENESIS-2026", 100, 5_000)
        t.fund_primary("GENESIS-2026", 5_000, 10)
        assert t.outstanding("GENESIS-2026") == 10


# ---------------------------------------------------------------------------
# simulate — the thousand-cap scenario proves the floor at real scale
# ---------------------------------------------------------------------------

class TestThousandCap:
    def test_scenario_is_deterministic(self):
        a = simulate.scenario_thousand_cap()["floor_log"]
        b = simulate.scenario_thousand_cap()["floor_log"]
        assert a == b

    def test_floor_starts_at_mint_and_rises(self):
        r = simulate.scenario_thousand_cap()
        assert r["floor_after_primary"] == 5_000  # thin backing -> rests on mint
        assert r["floor_after_secondary"] == 5_500  # $55.00 — crosses mint
        assert r["floor_after_exits"] == 5_500  # buybacks leave backing unchanged
        assert r["final"]["floor_cents"] == 7_015  # $70.15 after the ratchet
        floors = [f for _, f in r["final"]["floor_log"]]
        assert floors == sorted(floors)  # never falls

    def test_exit_burns_and_backing_holds(self):
        r = simulate.scenario_thousand_cap()
        final = r["final"]
        assert final["burned"] == 10
        assert final["outstanding"] == 990
        assert r["receipts_ok"] and r["solvent"] and r["ledger_ok"]


# ---------------------------------------------------------------------------
# decided parameters — the keeper's word, in code
# ---------------------------------------------------------------------------

class TestDecidedParameters:
    def test_rates_confirmed(self):
        assert economics.KEEPER_SHARE == 0.50
        assert economics.POOL_SHARE == 0.30
        assert economics.TREASURY_CUT == 0.20
        assert economics.ROYALTY_BPS == 750

    def test_chain_decided_base(self):
        rec = contract.CHAIN_RECOMMENDATION
        assert rec["recommended"] == "Base"
        assert "decided" in rec["decision"].lower()
        assert "keeper" in rec["decision"].lower()

    def test_framework_applies_keeper_floor(self):
        fw = framework_for_n(revenue_target_cents=1_000_000, mint_price_cents=5_000)
        assert fw["implied_n_rounded"] == 200  # the raw math, unchanged
        assert fw["keeper_floor_n"] == 1000
        assert fw["effective_n"] == 1000  # the floor binds

class TestScenarios:
    def test_deterministic(self):
        first = [r["floor_log"] for r in simulate.run_all_scenarios()]
        second = [r["floor_log"] for r in simulate.run_all_scenarios()]
        assert first == second

    def test_first_light_floor_rises_above_mint(self):
        report = simulate.scenario_first_light()
        floors = [f for _, f in report["final"]["floor_log"]]
        assert floors == sorted(floors)  # never falls
        assert report["final"]["floor_cents"] > 5_000  # crosses mint
        assert report["receipts_ok"] and report["solvent"]

    def test_bank_run_stays_solvent_and_receipted(self):
        report = simulate.scenario_bank_run()
        assert report["solvent"]
        assert report["receipts_ok"]
        # the honest boundary: not every exit clears on a thin treasury
        assert report["final"]["queued"] >= 0

    def test_founder_parity(self):
        report = simulate.scenario_founder_parity()
        assert report["fifo_order"]
        assert report["identical_price"]
        assert report["solvent"] and report["receipts_ok"]


# ---------------------------------------------------------------------------
# custody law — the treasury belongs to the holders (decided 2026-09-18)
# ---------------------------------------------------------------------------

class TestCustodyLaw:
    def test_custody_law_in_data(self):
        law = contract.CUSTODY_LAW
        assert law["owner"] == "the holders, collectively"
        assert law["outflows"] == ["buyback-settlement"]
        assert "cannot withdraw" in law["principle"]
        assert "FIFO" in law["founder_exit"]

    def test_interface_has_no_drain(self):
        assert contract.invariant_interface_has_no_drain() is True
        names = contract.interface_function_names()
        assert not any(contract._looks_like_drain(n) for n in names)

    def test_drain_patterns_marked(self):
        assert contract._looks_like_drain("ownerSweep")
        assert contract._looks_like_drain("emergencyWithdraw")
        assert not contract._looks_like_drain("burn")

    def test_owner_withdrawal_attempt_refused(self):
        t = _funded_series()
        with pytest.raises(NftEconomicsError):
            t.withdraw("0xowner", 1_000)  # no such function — refused by law
        with pytest.raises(NftEconomicsError):
            t.ownerSweep()
        with pytest.raises(NftEconomicsError):
            t.drain_all_funds()

    def test_treasury_public_surface_has_no_drain_method(self):
        t = _funded_series()
        public = [n for n in dir(t) if not n.startswith("_")]
        assert not any(contract._looks_like_drain(n) for n in public)

    def test_conformance_passes_on_good_ledger(self):
        result = contract.check_conformance(_good_ledger())
        assert result["ok"] is True
        assert result["series"]["GENESIS-2026"]["no-owner-withdrawal"] is True

    def test_conformance_allows_clean_drain_fields(self):
        ledger = _good_ledger()
        ledger["series"]["GENESIS-2026"]["admin_drain_paths"] = []
        ledger["series"]["GENESIS-2026"]["interface_functions"] = (
            contract.interface_function_names()
        )
        ledger["series"]["GENESIS-2026"]["outflow_events"] = [
            {"kind": "buyback-settlement", "receiver": "0xalice"},
        ]
        assert contract.check_conformance(ledger)["ok"] is True

    def test_conformance_catches_admin_drain_path(self):
        ledger = _good_ledger()
        ledger["series"]["GENESIS-2026"]["admin_drain_paths"] = ["ownerSweep"]
        result = contract.check_conformance(ledger)
        assert result["ok"] is False
        assert result["series"]["GENESIS-2026"]["no-owner-withdrawal"] is False

    def test_conformance_catches_drain_in_declared_interface(self):
        ledger = _good_ledger()
        ledger["series"]["GENESIS-2026"]["interface_functions"] = (
            contract.interface_function_names() + ["emergencyWithdraw"]
        )
        result = contract.check_conformance(ledger)
        assert result["ok"] is False
        assert result["series"]["GENESIS-2026"]["no-owner-withdrawal"] is False

    def test_conformance_catches_owner_sweep_outflow(self):
        ledger = _good_ledger()
        ledger["series"]["GENESIS-2026"]["outflow_events"] = [
            {"kind": "owner-withdrawal", "receiver": "0xowner"},
        ]
        result = contract.check_conformance(ledger)
        assert result["ok"] is False
        assert result["series"]["GENESIS-2026"]["no-owner-withdrawal"] is False

    def test_keeper_exit_settles_via_queue_only(self):
        """Founder parity extended to custody: the keeper's exit is a queue
        request like any holder's — FIFO order, identical floor price, and
        no backdoor path exists to call."""
        t = _funded_series(cap=100, primary=10)  # floor $50, thin treasury
        t.request_buyback("GENESIS-2026", "alice", 1)  # ordinary holder first
        t.request_buyback("GENESIS-2026", "keeper", 2)  # keeper queues behind
        first = t.settle_epoch("GENESIS-2026")   # budget: one floor bid
        second = t.settle_epoch("GENESIS-2026")
        assert first["settled"][0]["holder"] == "alice"
        assert second["settled"][0]["holder"] == "keeper"  # FIFO order holds
        assert first["settled"][0]["paid_cents"] == second["settled"][0]["paid_cents"]  # identical price
        # and there is no keeper-only exit path to reach for instead
        with pytest.raises(NftEconomicsError):
            t.keeper_withdraw("GENESIS-2026", 2)


# ---------------------------------------------------------------------------
# the randomized draw — every agent gets form + avatar, not every pack mints
# ---------------------------------------------------------------------------

class TestMintDraw:
    def _pool(self, k=10):
        return ["pack-%02d" % i for i in range(k)]

    def _small_ledger(self, year, n):
        led = SeriesLedger()
        led.record_year(year, n, decided_by="keeper", override=True)
        return led

    def test_draw_is_deterministic_from_seed(self):
        a = draw.draw_mint(self._pool(), 4, seed="GENESIS-2026-draw")
        b = draw.draw_mint(self._pool(), 4, seed="GENESIS-2026-draw")
        assert a == b and len(a) == 4 and len(set(a)) == 4

    def test_draw_differs_by_seed(self):
        a = draw.draw_mint(self._pool(), 4, seed="seed-one")
        b = draw.draw_mint(self._pool(), 4, seed="seed-two")
        assert a != b

    def test_draw_verifies(self):
        drawn = draw.draw_mint(self._pool(), 4, seed="s")
        assert draw.verify_draw(self._pool(), 4, seed="s", drawn=drawn)
        # tampered order fails verification
        assert not draw.verify_draw(self._pool(), 4, seed="s",
                                    drawn=list(reversed(drawn)))
        # wrong seed fails verification
        assert not draw.verify_draw(self._pool(), 4, seed="other", drawn=drawn)

    def test_draw_rejects_bad_inputs(self):
        with pytest.raises(draw.DrawError):
            draw.draw_mint(self._pool(), 4, seed="  ")
        with pytest.raises(draw.DrawError):
            draw.draw_mint([], 1, seed="s")
        with pytest.raises(draw.DrawError):
            draw.draw_mint(self._pool(), 0, seed="s")
        with pytest.raises(draw.DrawError):
            draw.draw_mint(self._pool(), 11, seed="s")
        with pytest.raises(draw.DrawError):
            draw.draw_mint(["a", "a"], 1, seed="s")

    def test_seed_banked_before_draw(self):
        led = self._small_ledger(year=2028, n=3)
        led.record_draw_seed(2028, "GENESIS-2028-draw")
        drawn = draw.draw_mint(self._pool(), 3, seed="GENESIS-2028-draw")
        receipt = led.record_draw(2028, drawn)
        assert receipt["detail"]["drawn_count"] == 3
        assert draw.verify_draw(self._pool(), 3, seed="GENESIS-2028-draw",
                                drawn=receipt["detail"]["drawn_pack_ids"])
        assert led.verify_ledger()

    def test_draw_without_seed_refused(self):
        led = self._small_ledger(year=2029, n=2)
        with pytest.raises(NftEconomicsError):
            led.record_draw(2029, ["pack-01", "pack-02"])

    def test_draw_must_fill_n_exactly(self):
        led = self._small_ledger(year=2030, n=3)
        led.record_draw_seed(2030, "s")
        with pytest.raises(NftEconomicsError):
            led.record_draw(2030, ["pack-01", "pack-02"])  # short of N

    def test_one_draw_per_year(self):
        led = self._small_ledger(year=2031, n=2)
        led.record_draw_seed(2031, "s")
        led.record_draw(2031, ["pack-01", "pack-02"])
        with pytest.raises(NftEconomicsError):
            led.record_draw(2031, ["pack-03", "pack-04"])

    def test_seed_committed_once(self):
        led = self._small_ledger(year=2032, n=2)
        led.record_draw_seed(2032, "s")
        with pytest.raises(NftEconomicsError):
            led.record_draw_seed(2032, "other")


# ---------------------------------------------------------------------------
# keeper's reserve — one of each, out of N, never on top of it
# ---------------------------------------------------------------------------

class TestKeeperReserve:
    def _pool(self, k=10):
        return ["pack-%02d" % i for i in range(k)]

    def _small_ledger(self, year, n):
        led = SeriesLedger()
        led.record_year(year, n, decided_by="keeper", override=True)
        return led

    def test_reserve_draw_is_deterministic(self):
        a = draw.draw_mint_with_reserve(self._pool(), 4, seed="s",
                                        reserve_pack_id="pack-00")
        b = draw.draw_mint_with_reserve(self._pool(), 4, seed="s",
                                        reserve_pack_id="pack-00")
        assert a == b
        assert a["reserve"] == "pack-00"
        assert len(a["drawn"]) == 3
        assert "pack-00" not in a["drawn"]
        assert len(set(a["drawn"])) == 3

    def test_reserve_must_be_in_pool(self):
        with pytest.raises(draw.DrawError):
            draw.draw_mint_with_reserve(self._pool(), 4, seed="s",
                                        reserve_pack_id="pack-99")
        with pytest.raises(draw.DrawError):
            draw.draw_mint_with_reserve(self._pool(), 4, seed="s",
                                        reserve_pack_id="  ")

    def test_reserve_draw_verifies(self):
        r = draw.draw_mint_with_reserve(self._pool(), 4, seed="s",
                                        reserve_pack_id="pack-00")
        assert draw.verify_draw_with_reserve(self._pool(), 4, seed="s",
                                             reserve_pack_id="pack-00",
                                             drawn=r["drawn"])
        assert not draw.verify_draw_with_reserve(self._pool(), 4, seed="other",
                                                 reserve_pack_id="pack-00",
                                                 drawn=r["drawn"])

    def test_ledger_banks_reserve_draw(self):
        led = self._small_ledger(year=2040, n=4)
        led.record_draw_seed(2040, "s")
        r = draw.draw_mint_with_reserve(self._pool(), 4, seed="s",
                                        reserve_pack_id="pack-00")
        receipt = led.record_draw(2040, r["drawn"], keeper_reserve=r["reserve"])
        assert receipt["detail"]["keeper_reserve"] == "pack-00"
        assert receipt["detail"]["minted_total"] == 4
        assert led.verify_ledger()

    def test_ledger_reserve_needs_n_minus_one(self):
        led = self._small_ledger(year=2041, n=4)
        led.record_draw_seed(2041, "s")
        with pytest.raises(NftEconomicsError):
            led.record_draw(2041, ["pack-01", "pack-02", "pack-03", "pack-04"],
                            keeper_reserve="pack-00")  # 4 drawn + reserve = 5 > N

    def test_ledger_reserve_cannot_be_drawn(self):
        led = self._small_ledger(year=2042, n=4)
        led.record_draw_seed(2042, "s")
        with pytest.raises(NftEconomicsError):
            led.record_draw(2042, ["pack-00", "pack-01", "pack-02"],
                            keeper_reserve="pack-00")

    def test_treasury_mints_one_free_copy(self):
        t = Treasury()
        t.create_series("GENESIS-2026", 100, 5_000)
        before = t.series_view("GENESIS-2026")["balance_cents"]
        t.mint_keeper_reserve("GENESIS-2026", pack_id="pack-00")
        after = t.series_view("GENESIS-2026")
        assert after["balance_cents"] == before  # no revenue on a free copy
        assert t.outstanding("GENESIS-2026") == 1
        assert after["founder_reserve"] == 1

    def test_treasury_second_reserve_refused(self):
        t = Treasury()
        t.create_series("GENESIS-2026", 100, 5_000)
        t.mint_keeper_reserve("GENESIS-2026", pack_id="pack-00")
        with pytest.raises(NftEconomicsError):
            t.mint_keeper_reserve("GENESIS-2026", pack_id="pack-01")

    def test_reserve_counts_against_cap(self):
        t = Treasury()
        t.create_series("GENESIS-2026", 3, 5_000)
        t.mint_keeper_reserve("GENESIS-2026", pack_id="pack-00")
        t.fund_primary("GENESIS-2026", 5_000, 2)  # 1 + 2 = cap
        assert t.outstanding("GENESIS-2026") == 3
        with pytest.raises(NftEconomicsError):
            t.fund_primary("GENESIS-2026", 5_000, 1)  # cap is law


# ---------------------------------------------------------------------------
# NFT² — the series master token. The NFT of the NFTs.
# ---------------------------------------------------------------------------

class TestMasterToken:
    def _registry(self, series_id, pack_ids):
        return [token_id_for(p, series_id) for p in pack_ids]

    def _master_kwargs(self, n=4):
        series_id = "GENESIS-2026"
        packs = ["pack-%02d" % i for i in range(n)]
        return {
            "series_id": series_id,
            "year": 2026,
            "banked_n": n,
            "draw_seed": "GENESIS-2026-draw",
            "keeper_pack_id": packs[0],
            "keeper_pack_hash": "ab" * 32,
            "keeper_roster": [
                {"name": "Harbor", "theme": "tide-caller", "form": "inverse"},
            ],
            "mint_registry": self._registry(series_id, packs),
        }

    def test_master_id_is_domain_separated(self):
        mid = master_token_id_for("GENESIS-2026")
        pack_ids = [token_id_for("pack-%02d" % i, "GENESIS-2026") for i in range(50)]
        assert mid not in pack_ids
        assert master_token_id_for("GENESIS-2026") == mid
        assert master_token_id_for("GENESIS-2027") != mid

    def test_master_metadata_carries_the_registry(self):
        md = build_master_token_metadata(**self._master_kwargs(n=4))
        assert md["edition"] == "NFT2"
        assert md["mint_registry_count"] == 4
        assert len(md["mint_registry"]) == 4
        assert md["keeper_token_id"] in self._registry("GENESIS-2026",
                                                      ["pack-%02d" % i for i in range(4)])
        assert md["keeper_roster"][0]["form"] == "inverse"

    def test_master_requires_complete_registry(self):
        kw = self._master_kwargs(n=4)
        kw["mint_registry"] = kw["mint_registry"][:3]  # series not closed
        with pytest.raises(NftEconomicsError):
            build_master_token_metadata(**kw)

    def test_master_requires_keeper_in_registry(self):
        kw = self._master_kwargs(n=4)
        kw["mint_registry"] = self._registry("GENESIS-2026",
                                             ["pack-%02d" % i for i in range(1, 5)])
        with pytest.raises(NftEconomicsError):
            build_master_token_metadata(**kw)

    def test_master_rejects_bad_hash(self):
        kw = self._master_kwargs()
        kw["keeper_pack_hash"] = "not-a-hash"
        with pytest.raises(NftEconomicsError):
            build_master_token_metadata(**kw)

    def _drawn_ledger(self, year, n):
        led = SeriesLedger()
        led.record_year(year, n, decided_by="keeper", override=True)
        led.record_draw_seed(year, "s")
        pool = ["pack-%02d" % i for i in range(n)]
        r = draw.draw_mint_with_reserve(pool, n, seed="s", reserve_pack_id=pool[0])
        led.record_draw(year, r["drawn"], keeper_reserve=r["reserve"])
        return led

    def test_ledger_banks_master_last(self):
        led = self._drawn_ledger(2050, 4)
        receipt = led.record_master_token(2050, "0x" + "cd" * 32, "ef" * 32, 4)
        assert receipt["detail"]["token_count"] == 4
        assert led.verify_ledger()

    def test_ledger_master_needs_draw_first(self):
        led = SeriesLedger()
        led.record_year(2051, 4, decided_by="keeper", override=True)
        with pytest.raises(NftEconomicsError):
            led.record_master_token(2051, "0x" + "cd" * 32, "ef" * 32, 4)

    def test_ledger_master_needs_full_count(self):
        led = self._drawn_ledger(2052, 4)
        with pytest.raises(NftEconomicsError):
            led.record_master_token(2052, "0x" + "cd" * 32, "ef" * 32, 3)

    def test_ledger_one_master_per_year(self):
        led = self._drawn_ledger(2053, 4)
        led.record_master_token(2053, "0x" + "cd" * 32, "ef" * 32, 4)
        with pytest.raises(NftEconomicsError):
            led.record_master_token(2053, "0x" + "ab" * 32, "ef" * 32, 4)


# ---------------------------------------------------------------------------
# keeper's archive — the negatives, not the prints. Never tokens.
# ---------------------------------------------------------------------------

class TestKeeperArchive:
    def _drawn_ledger(self, year, n):
        led = SeriesLedger()
        led.record_year(year, n, decided_by="keeper", override=True)
        led.record_draw_seed(year, "s")
        pool = ["pack-%02d" % i for i in range(n)]
        r = draw.draw_mint_with_reserve(pool, n, seed="s", reserve_pack_id=pool[0])
        led.record_draw(year, r["drawn"], keeper_reserve=r["reserve"])
        return led

    def _hashes(self, n):
        return {"pack-%02d" % i: "%064x" % (i + 1) for i in range(n)}

    def test_archive_banks(self):
        led = self._drawn_ledger(2060, 4)
        receipt = led.record_archive(2060, self._hashes(4))
        assert receipt["detail"]["pack_count"] == 4
        assert receipt["detail"]["transferable"] is False
        assert receipt["detail"]["mintable"] is False
        assert led.verify_ledger()

    def test_archive_needs_draw_first(self):
        led = SeriesLedger()
        led.record_year(2061, 4, decided_by="keeper", override=True)
        with pytest.raises(NftEconomicsError):
            led.record_archive(2061, self._hashes(4))

    def test_archive_must_cover_n(self):
        led = self._drawn_ledger(2062, 4)
        with pytest.raises(NftEconomicsError):
            led.record_archive(2062, self._hashes(3))

    def test_archive_rejects_bad_hash(self):
        led = self._drawn_ledger(2063, 4)
        bad = self._hashes(4)
        bad["pack-00"] = "not-a-hash"
        with pytest.raises(NftEconomicsError):
            led.record_archive(2063, bad)

    def test_archive_one_per_year(self):
        led = self._drawn_ledger(2064, 4)
        led.record_archive(2064, self._hashes(4))
        with pytest.raises(NftEconomicsError):
            led.record_archive(2064, self._hashes(4))

"""BLUE regression tests: SupraStreet paper-ledger integrity (RED-1 batch A).

Fail-closed: read-side mutation either raises (sealed ledger entries)
or lands on a detached snapshot (never the ledger). The legitimate
paper path — conservation, the 15% founder's cut, idempotency, earnings —
keeps working exactly as before.
"""

import pytest

from levi.suprastreet.commerce import (
    FOUNDER_CUT_BP,
    RoyaltyShare,
    SupraStreet,
)


def _founder_product(street, price=2000):
    street.register_product_with_founder_cut("p1", "Widget", price, seller="seller")
    return street.record_sale("s1", "p1")


class TestSealedLedgerEntries:
    def test_record_sale_return_cannot_be_mutated(self):
        street = SupraStreet()
        s = _founder_product(street)
        # The ledger entry is sealed: item assignment raises, fail-closed.
        with pytest.raises(TypeError):
            s.payouts["founder"] = 999999
        with pytest.raises(TypeError):
            s.payouts["mallory"] = 500000
        # The ledger is untouched and the money laws hold.
        assert s.total_distributed() == s.gross == 2000
        assert street.earnings("founder") == 300
        assert street.earnings("mallory") == 0

    def test_idempotent_return_is_the_same_sealed_object(self):
        street = SupraStreet()
        first = _founder_product(street)
        again = street.record_sale("s1", "p1")
        assert again is first  # idempotency preserved
        with pytest.raises(TypeError):
            again.payouts["founder"] = 1


class TestDetachedSnapshots:
    def test_settlement_snapshot_mutation_never_reaches_ledger(self):
        street = SupraStreet()
        _founder_product(street)
        snap = street.settlements()
        # The snapshot is an ordinary detached copy: the attacker CAN
        # write into it, but the write goes nowhere.
        snap[0].payouts["founder"] = 999999
        snap[0].payouts["mallory"] = 500000
        for st in street.settlements():
            assert st.total_distributed() == st.gross == 2000
        assert street.earnings("founder") == 300
        assert street.earnings("mallory") == 0

    def test_product_snapshot_mutation_never_reaches_registry(self):
        street = SupraStreet()
        _founder_product(street)
        p = street.product("p1")
        p.shares.clear()
        p.shares.append(RoyaltyShare("mallory", 10000))
        # The registered split table is untouched: the next sale settles
        # exactly the registered splits.
        s2 = street.record_sale("s2", "p1")
        assert s2.total_distributed() == s2.gross == 2000
        assert s2.payouts.get("founder") == 300
        assert "mallory" not in s2.payouts

    def test_register_product_return_is_detached(self):
        street = SupraStreet()
        p = street.register_product_with_founder_cut(
            "p1", "Widget", 2000, seller="seller"
        )
        p.shares.clear()
        p.shares.append(RoyaltyShare("mallory", 10000))
        s = street.record_sale("s1", "p1")
        assert s.payouts.get("founder") == 300
        assert "mallory" not in s.payouts


class TestLegitimatePathUnchanged:
    def test_conservation_founder_cut_earnings(self):
        street = SupraStreet()
        s = _founder_product(street)
        assert s.total_distributed() == s.gross == 2000
        assert s.payouts["founder"] == 300  # 15% of 2000
        assert s.payouts["seller"] == 1700
        assert street.earnings("founder") == 300
        assert street.earnings("seller") == 1700
        assert street.earnings("nobody") == 0

    def test_snapshot_reads_equal_the_ledger(self):
        street = SupraStreet()
        s = _founder_product(street)
        trail = street.settlements()
        assert trail == [s]  # value-equal snapshots
        assert len(trail) == 1

    def test_split_table_reads_intact(self):
        street = SupraStreet()
        _founder_product(street)
        p = street.product("p1")
        assert sum(sh.basis_points for sh in p.shares) == 10_000
        assert p.shares[0] == RoyaltyShare("founder", FOUNDER_CUT_BP)

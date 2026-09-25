"""Proof for SupraStreet laws: splits sum to 100%, conservation, paper-only, idempotency."""

import pytest

from levi.suprastreet import RoyaltyError, SupraStreet
from levi.suprastreet.commerce import RoyaltyShare


def _street():
    return SupraStreet()


def _product(street, pid="song-1"):
    return street.register_product(
        pid, "Test Song", 1000,
        [RoyaltyShare("artist", 7000), RoyaltyShare("label", 2000),
         RoyaltyShare("platform", 1000)],
    )


def test_splits_must_sum_to_100_percent():
    street = _street()
    with pytest.raises(RoyaltyError):
        street.register_product("x", "X", 100,
                                [RoyaltyShare("a", 5000), RoyaltyShare("b", 4000)])
    with pytest.raises(RoyaltyError):
        street.register_product("x", "X", 100,
                                [RoyaltyShare("a", 6000), RoyaltyShare("b", 5000)])
    # Exactly 10_000 bps is accepted.
    p = _product(street)
    assert sum(s.basis_points for s in p.shares) == 10_000


def test_duplicate_product_refused():
    street = _street()
    _product(street)
    with pytest.raises(RoyaltyError):
        _product(street)


def test_sale_conservation_exact():
    street = _street()
    _product(street)
    s = street.record_sale("sale-1", "song-1", quantity=3)
    assert s.gross == 3000
    # Law 2: distributed == gross, exactly, integer math.
    assert s.total_distributed() == s.gross == 3000
    assert s.payouts == {"artist": 2100, "label": 600, "platform": 300}


def test_remainder_lands_deterministically():
    street = _street()
    street.register_product(
        "odd", "Odd", 100,
        [RoyaltyShare("a", 3333), RoyaltyShare("b", 3333), RoyaltyShare("c", 3334)],
    )
    s = street.record_sale("sale-odd", "odd")
    # 33 + 33 + 33 = 99, remainder 1 -> first recipient by registration order.
    assert s.total_distributed() == 100
    assert s.payouts["a"] == 34


def test_idempotent_sale_recording():
    street = _street()
    _product(street)
    first = street.record_sale("sale-1", "song-1")
    second = street.record_sale("sale-1", "song-1")
    assert first is second
    assert len(street.settlements()) == 1
    assert street.earnings("artist") == 700


def test_paper_only_ledger():
    street = _street()
    _product(street)
    street.record_sale("s1", "song-1")
    street.record_sale("s2", "song-1", quantity=2)
    # Law 3: settlements are plain data — no payout rails anywhere.
    assert street.earnings("artist") == 700 + 1400
    assert street.earnings("label") == 200 + 400
    assert street.earnings("nobody") == 0


def test_unknown_product_and_bad_quantity_refused():
    street = _street()
    with pytest.raises(RoyaltyError):
        street.record_sale("s", "missing")
    _product(street)
    with pytest.raises(RoyaltyError):
        street.record_sale("s", "song-1", quantity=0)


def test_founder_cut_is_fifteen_percent():
    # The original SER-18 mechanic: strict 15% to the founder wallet,
    # 85% to the seller, through the same guarded settle path.
    from levi.suprastreet import FOUNDER_CUT_BP, FOUNDER_WALLET
    assert FOUNDER_CUT_BP == 1500
    street = SupraStreet()
    street.register_product_with_founder_cut("beat-1", "Beat", 10_000,
                                             seller="producer")
    s = street.record_sale("s1", "beat-1")
    assert s.payouts[FOUNDER_WALLET] == 1_500
    assert s.payouts["producer"] == 8_500
    assert s.total_distributed() == s.gross == 10_000


def test_founder_cut_shares_sum_to_basis():
    shares = SupraStreet.founder_cut_shares("agent-7")
    assert sum(sh.basis_points for sh in shares) == 10_000
    assert shares[0].recipient == "founder"
    assert shares[0].basis_points == 1500


def test_founder_cut_idempotent_and_paper_only():
    street = SupraStreet()
    street.register_product_with_founder_cut("beat-2", "Beat 2", 1_000,
                                             seller="producer")
    first = street.record_sale("s9", "beat-2")
    again = street.record_sale("s9", "beat-2")
    assert again is first
    assert len(street.settlements()) == 1
    assert street.earnings("founder") == 150
    assert street.earnings("producer") == 850

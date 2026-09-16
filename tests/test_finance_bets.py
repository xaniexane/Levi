"""Paper-bet ledger tests — hermetic, no network, temp HOME files.

The hostile trader fixture is base64-encoded: no denylisted literal
appears in this file. It decodes in memory only, to exercise the guard.

Run:  python3 tests/test_finance_bets.py     (has a real __main__ runner)
      python3 -m pytest tests/test_finance_bets.py -q
"""

from __future__ import annotations

import base64
import json
import sys
import traceback
from pathlib import Path

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from levi.finance.bets import (  # noqa: E402
    Bet,
    BetAlreadySettled,
    BetLedger,
    BetNotFound,
    InvalidBet,
)

_TESTS = []


def finance_test(fn):
    _TESTS.append(fn)
    return fn


def _ledger() -> BetLedger:
    return BetLedger()


def _hostile(b64: str) -> str:
    """Decode a base64 hostile fixture (keeps literals out of source)."""
    return base64.b64decode(b64).decode("utf-8")


@finance_test
def test_place_and_ticket():
    ledger = _ledger()
    bet = ledger.place(
        trader="ape1",
        symbol="synth",
        side="buy",
        qty=10,
        entry_price=100.0,
        horizon_days=30,
        source="synth",
    )
    assert bet.id.startswith("bet-")
    assert bet.symbol == "SYNTH"
    assert bet.status == "open"
    ticket = BetLedger.ticket(bet)
    assert "PAPER YOLO TICKET" in ticket
    assert "SIMULATED" in ticket
    assert "ape1" in ticket
    assert "not financial advice" in ticket


@finance_test
def test_place_validates():
    ledger = _ledger()
    bad_kwargs = [
        {"trader": "", "symbol": "SYNTH", "side": "buy", "qty": 1, "entry_price": 1.0},
        {"trader": "x", "symbol": "", "side": "buy", "qty": 1, "entry_price": 1.0},
        {
            "trader": "x",
            "symbol": "SYNTH",
            "side": "hold",
            "qty": 1,
            "entry_price": 1.0,
        },
        {"trader": "x", "symbol": "SYNTH", "side": "buy", "qty": 0, "entry_price": 1.0},
        {"trader": "x", "symbol": "SYNTH", "side": "buy", "qty": 1, "entry_price": -5},
        {
            "trader": "x",
            "symbol": "SYNTH",
            "side": "buy",
            "qty": 1,
            "entry_price": 1.0,
            "horizon_days": 0,
        },
        {
            "trader": "x",
            "symbol": "SYNTH",
            "side": "buy",
            "qty": 1,
            "entry_price": 1.0,
            "source": "robinhood",
        },
    ]
    for kw in bad_kwargs:
        try:
            ledger.place(**kw)
        except InvalidBet:
            pass
        else:
            raise AssertionError(f"{kw} did not raise")


@finance_test
def test_trader_name_slur_rejected():
    ledger = _ledger()
    try:
        ledger.place(
            trader=_hostile("cmV0YXJkX2FwZQ=="),  # hostile name, encoded
            symbol="SYNTH",
            side="buy",
            qty=1,
            entry_price=1.0,
        )
    except InvalidBet as exc:
        assert "rejected" in str(exc)
    else:
        raise AssertionError("slur trader name was accepted")


@finance_test
def test_settle_long_win_and_short_win():
    ledger = _ledger()
    long_bet = ledger.place(
        trader="a", symbol="SYNTH", side="buy", qty=10, entry_price=100.0
    )
    settled = ledger.settle(long_bet.id, 110.0)
    assert settled.status == "settled"
    assert settled.pnl == 100.0
    assert settled.early_exit is False

    short_bet = ledger.place(
        trader="a", symbol="SYNTH", side="sell", qty=10, entry_price=100.0
    )
    settled_short = ledger.settle(short_bet.id, 90.0, early=True)
    assert settled_short.pnl == 100.0
    assert settled_short.early_exit is True


@finance_test
def test_settle_validates():
    ledger = _ledger()
    bet = ledger.place(trader="a", symbol="SYNTH", side="buy", qty=1, entry_price=10.0)
    try:
        ledger.settle("bet-nope", 12.0)
    except BetNotFound:
        pass
    else:
        raise AssertionError("unknown bet id did not raise")
    try:
        ledger.settle(bet.id, -3.0)
    except InvalidBet:
        pass
    else:
        raise AssertionError("negative exit price did not raise")
    ledger.settle(bet.id, 12.0)
    try:
        ledger.settle(bet.id, 13.0)
    except BetAlreadySettled:
        pass
    else:
        raise AssertionError("double settle did not raise")


@finance_test
def test_win_rate_and_hands_stats():
    ledger = _ledger()
    b1 = ledger.place(
        trader="diamond", symbol="SYNTH", side="buy", qty=10, entry_price=100.0
    )
    b2 = ledger.place(
        trader="diamond", symbol="SYNTH", side="buy", qty=10, entry_price=100.0
    )
    b3 = ledger.place(
        trader="paper", symbol="SYNTH", side="buy", qty=10, entry_price=100.0
    )
    ledger.settle(b1.id, 120.0)  # diamond win
    ledger.settle(b2.id, 80.0)  # diamond loss
    ledger.settle(b3.id, 105.0, early=True)  # paper win
    wr = ledger.win_rate()
    assert wr["bets"] == 3 and wr["wins"] == 2
    assert wr["win_rate"] == round(2 / 3, 4)
    assert wr["total_pnl"] == 50.0
    assert ledger.win_rate("diamond")["bets"] == 2
    assert ledger.win_rate("nobody")["win_rate"] is None
    hands = ledger.hands_stats()
    assert hands["diamond_hands"]["bets"] == 2
    assert hands["paper_hands"]["bets"] == 1
    assert hands["paper_hands"]["win_rate"] == 1.0


@finance_test
def test_persistence_roundtrip(tmp_path=None):
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bets.json"
        ledger = _ledger()
        bet = ledger.place(
            trader="a",
            symbol="SYNTHBTC",
            side="sell",
            qty=2,
            entry_price=60000.0,
            source="binance",
        )
        ledger.settle(bet.id, 59000.0)
        saved = ledger.save(path)
        assert saved == path
        loaded = BetLedger.load(path)
        assert len(loaded.bets) == 1
        assert loaded.bets[0].pnl == 2000.0
        assert loaded.bets[0].source == "binance"


@finance_test
def test_load_corrupt_warns_not_crashes(tmp_path=None):
    import tempfile
    import warnings

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bets.json"
        path.write_text("{corrupt")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            loaded = BetLedger.load(path)
        assert len(loaded.bets) == 0
        assert any("unreadable" in str(w.message) for w in caught)


@finance_test
def test_bet_serialization_roundtrip():
    bet = Bet(
        id="bet-abc123",
        trader="t",
        symbol="SYNTH",
        side="buy",
        qty=5,
        entry_price=10.0,
        horizon_days=7,
        source="synth",
    )
    clone = Bet.from_dict(json.loads(json.dumps(bet.to_dict())))
    assert clone.id == bet.id and clone.qty == bet.qty
    assert clone.entry_price == bet.entry_price


def main() -> int:
    failures = 0
    print(f"finance bets tests ({len(_TESTS)} tests)")
    for fn in _TESTS:
        name = fn.__name__
        try:
            fn()
        except AssertionError as e:
            failures += 1
            print(f"FAIL {name}: {e}")
        except Exception:
            failures += 1
            print(f"ERROR {name}:")
            traceback.print_exc()
        else:
            print(f"ok   {name}")
    print(f"\n{len(_TESTS) - failures}/{len(_TESTS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

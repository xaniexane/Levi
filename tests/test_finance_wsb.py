"""WSB skin tests — voice, honesty labels, and the slur guard.

Hostile fixtures are base64-encoded: no denylisted literal appears in
this file. They decode in memory only, to exercise the guard.

Run:  python3 tests/test_finance_wsb.py     (has a real __main__ runner)
      python3 -m pytest tests/test_finance_wsb.py -q
"""

from __future__ import annotations

import base64
import sys
import traceback
from pathlib import Path

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from levi.finance import signals as signals_mod  # noqa: E402
from levi.finance.wsb import (  # noqa: E402
    SlurDetected,
    assert_clean,
    dd_post,
    gain_loss_porn,
    hands_report,
    positions_or_ban,
    ticker_tape,
    wsb_quote,
)

_TESTS = []


def finance_test(fn):
    _TESTS.append(fn)
    return fn


def _hostile(b64: str) -> str:
    """Decode a base64 hostile fixture (keeps literals out of source)."""
    return base64.b64decode(b64).decode("utf-8")


def _bullish_signal():
    return signals_mod.Signal(
        symbol="SYNTH",
        direction="bullish",
        confidence=0.81,
        rationale=["RSI(14) 62.3 > 55: upside momentum", "Price above SMA20"],
        indicator_snapshot={"RSI14": 62.3, "SMA20": 101.2, "ADX14": 22.5},
    )


@finance_test
def test_slur_guard_blocks():
    nasties = (
        "eW91IHJldGFyZA==",
        "QVVUSVNUUyB0byB0aGUgbW9vbg==",
        "ZmFnZ290",
        "UmVUYVJkRWQ=",
    )
    for encoded in nasties:
        nasty = _hostile(encoded)
        try:
            assert_clean(nasty)
        except SlurDetected:
            pass
        else:
            raise AssertionError("a hostile fixture was not blocked")


@finance_test
def test_slur_guard_passes_clean():
    text = "Apes together strong! Diamond hands to the moon. Tendies secured."
    assert assert_clean(text) == text


@finance_test
def test_slur_guard_rejects_non_text():
    try:
        assert_clean(None)
    except SlurDetected:
        pass
    else:
        raise AssertionError("None was not rejected")


@finance_test
def test_dd_post_bullish():
    out = dd_post(_bullish_signal())
    assert "DD: SYNTH" in out
    assert "BULLISH" in out
    assert "81%" in out
    assert "heuristic agreement" in out
    assert "not a probability" in out
    assert "PAPER ONLY" in out
    assert "not financial advice" in out
    # numbers rendered verbatim
    assert "RSI14" in out and "62.3" in out


@finance_test
def test_dd_post_bearish_and_neutral():
    for direction, word in (("bearish", "BEARISH"), ("neutral", "NEUTRAL")):
        sig = signals_mod.Signal(symbol="SYNTHBTC", direction=direction, confidence=0.4)
        out = dd_post(sig)
        assert word in out
        assert "PAPER ONLY" in out


@finance_test
def test_positions_or_ban():
    summary = {
        "cash": 500.0,
        "positions": {
            "SYNTH": {
                "qty": 10,
                "avg_cost": 100.0,
                "unrealized_pnl": 250.0,
            },
            "DEAD": {"qty": 0, "avg_cost": 5.0},
        },
        "realized_pnl": -50.0,
        "unrealized_pnl": 250.0,
        "market_value": 1750.0,
        "total_pnl": 200.0,
    }
    out = positions_or_ban(summary)
    assert "POSITIONS OR BAN" in out
    assert "SYNTH" in out
    assert "DEAD" not in out  # flat positions hidden
    assert "+$200.00" in out
    assert "SIMULATED" in out


@finance_test
def test_gain_loss_porn_branches():
    gain = gain_loss_porn({"total_pnl": 1234.5})
    assert "GAIN PORN" in gain
    assert "+$1,234.50" in gain
    loss = gain_loss_porn({"total_pnl": -99.0})
    assert "LOSS PORN" in loss
    assert "-$99.00" in loss
    flat = gain_loss_porn({"total_pnl": 0.0})
    assert "CRAB" in flat
    for out in (gain, loss, flat):
        assert "not financial advice" in out


@finance_test
def test_hands_report():
    hands = {
        "diamond_hands": {
            "bets": 4,
            "wins": 3,
            "losses": 1,
            "win_rate": 0.75,
            "total_pnl": 250.0,
        },
        "paper_hands": {
            "bets": 2,
            "wins": 0,
            "losses": 2,
            "win_rate": 0.0,
            "total_pnl": -80.0,
        },
        "note": "x",
    }
    out = hands_report(hands)
    assert "DIAMOND HANDS vs PAPER HANDS" in out
    assert "+$250.00" in out and "-$80.00" in out
    assert "75%" in out
    assert "DIAMOND HANDS WIN" in out
    assert "not financial advice" in out
    assert "PAPER ONLY" in out


@finance_test
def test_hands_report_paper_wins_and_empty():
    hands = {
        "diamond_hands": {"bets": 1, "win_rate": 0.0, "total_pnl": -10.0},
        "paper_hands": {"bets": 1, "win_rate": 1.0, "total_pnl": 50.0},
    }
    assert "PAPER HANDS WIN" in hands_report(hands)
    empty = hands_report({"diamond_hands": {"bets": 0}, "paper_hands": {}})
    assert "no settled bets yet" in empty
    one_sided = hands_report(
        {"diamond_hands": {"bets": 2, "total_pnl": 5.0}, "paper_hands": {}}
    )
    assert "only diamond-hands exits" in one_sided


@finance_test
def test_ticker_tape():
    out = ticker_tape([("BTCUSDT", 67432.1, 2.4), ("SYNTH", 101.5, -1.2)])
    assert "BTCUSDT $67,432.10" in out
    assert "(+2.4%)" in out
    assert "(-1.2%)" in out
    assert "PAPER" in out
    assert "empty" in ticker_tape([])


@finance_test
def test_wsb_quote():
    out = wsb_quote("btcusdt", 67000.0, "2026-09-15", "Binance public klines")
    assert "BTCUSDT" in out
    assert "$67,000.00" in out
    assert "not financial advice" in out


@finance_test
def test_renderers_screen_hostile_input():
    # A slur smuggled in via rationale must blow up, not render.
    # (hostile fixture is base64-encoded; the literal stays out of source)
    sig = signals_mod.Signal(
        symbol="SYNTH",
        direction="bullish",
        confidence=0.5,
        rationale=[_hostile("dG8gdGhlIG1vb24gcmV0YXJk")],
    )
    try:
        dd_post(sig)
    except SlurDetected:
        pass
    else:
        raise AssertionError("hostile rationale was rendered")


def main() -> int:
    failures = 0
    print(f"finance wsb tests ({len(_TESTS)} tests)")
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

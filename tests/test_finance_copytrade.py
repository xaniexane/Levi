"""Copy-trade simulation tests — hermetic, synthetic bets only.

Run:  python3 tests/test_finance_copytrade.py     (has a real __main__ runner)
      python3 -m pytest tests/test_finance_copytrade.py -q
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from levi.finance.bets import BetLedger  # noqa: E402
from levi.finance.copytrade import (  # noqa: E402
    NoSettledBets,
    compare_traders,
    mirror_report,
    render_copy_report,
)

_TESTS = []


def finance_test(fn):
    _TESTS.append(fn)
    return fn


def _seeded_ledger() -> BetLedger:
    ledger = BetLedger()
    # guru: 4 settled bets, 3 wins
    for entry, exit_ in (
        (100.0, 110.0),
        (100.0, 120.0),
        (100.0, 90.0),
        (50.0, 60.0),
    ):
        b = ledger.place(
            trader="guru", symbol="SYNTH", side="buy", qty=10, entry_price=entry
        )
        ledger.settle(b.id, exit_)
    # shorter guru: 1 settled bet only
    b = ledger.place(
        trader="guru", symbol="SYNTH", side="sell", qty=4, entry_price=200.0
    )
    ledger.settle(b.id, 190.0)
    # rookie: 2 settled, both losses
    for entry, exit_ in ((100.0, 90.0), (100.0, 80.0)):
        b = ledger.place(
            trader="rookie", symbol="SYNTH", side="buy", qty=10, entry_price=entry
        )
        ledger.settle(b.id, exit_)
    # watcher: open bet only
    ledger.place(
        trader="watcher", symbol="SYNTH", side="buy", qty=10, entry_price=100.0
    )
    return ledger


@finance_test
def test_mirror_math():
    ledger = _seeded_ledger()
    report = mirror_report(ledger.bets, "guru", capital=10000.0)
    assert report["n_mirrored"] == 5
    assert report["capital"] == 10000.0
    assert report["notional_per_bet"] == 2000.0
    # legs: +2000*0.10, +2000*0.20, -2000*0.10, +2000*0.20, +2000*(10/200)
    expected = 200 + 400 - 200 + 400 + 100
    assert report["copier_pnl"] == float(expected), report["copier_pnl"]
    assert report["copier_win_rate"] == 0.8
    assert report["beat_baseline"] is True
    assert report["baseline_pnl"] == 0.0
    assert len(report["legs"]) == 5
    assert any("slippage" in note for note in report["assumptions"])


@finance_test
def test_mirror_short_side():
    ledger = BetLedger()
    b = ledger.place(trader="s", symbol="SYNTH", side="sell", qty=10, entry_price=100.0)
    ledger.settle(b.id, 80.0)
    report = mirror_report(ledger.bets, "s", capital=1000.0)
    assert report["copier_pnl"] == 200.0


@finance_test
def test_mirror_no_bets_raises():
    ledger = _seeded_ledger()
    for who in ("watcher", "nobody", ""):
        try:
            mirror_report(ledger.bets, who)
        except (NoSettledBets, ValueError):
            pass
        else:
            raise AssertionError(f"follow={who!r} did not raise")


@finance_test
def test_mirror_bad_capital():
    ledger = _seeded_ledger()
    for bad in (0, -100, "lots", True):
        try:
            mirror_report(ledger.bets, "guru", capital=bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"capital={bad!r} did not raise")


@finance_test
def test_compare_traders_ranking_and_threshold():
    ledger = _seeded_ledger()
    ranked = compare_traders(ledger.bets, capital=10000.0, min_bets=3)
    # guru (5 bets) qualifies; rookie (2) and watcher (0) do not
    assert [r["follow"] for r in ranked] == ["guru"]
    assert ranked[0]["copier_pnl"] == 900.0


@finance_test
def test_render_honest():
    report = mirror_report(_seeded_ledger().bets, "guru", capital=10000.0)
    out = render_copy_report(report)
    assert "COPY TRADE SIMULATION" in out
    assert "@guru" in out
    assert "PAPER ONLY" in out
    assert "not financial advice" in out
    assert "fine print" in out
    assert "slippage" in out


def main() -> int:
    failures = 0
    print(f"finance copytrade tests ({len(_TESTS)} tests)")
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

"""Leaderboard tests — hermetic, synthetic bets only.

Run:  python3 tests/test_finance_leaderboard.py     (has a real __main__ runner)
      python3 -m pytest tests/test_finance_leaderboard.py -q
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

from levi.finance.bets import BetLedger  # noqa: E402
from levi.finance.leaderboard import (  # noqa: E402
    MIN_BETS_RANKED,
    build_leaderboard,
    ranked_leaderboard,
    render_leaderboard,
)

_TESTS = []


def finance_test(fn):
    _TESTS.append(fn)
    return fn


def _seeded_ledger() -> BetLedger:
    ledger = BetLedger()
    # ape_pro: 3 settled (2 wins), 1 open
    for entry, exit_ in ((100.0, 120.0), (100.0, 80.0), (50.0, 75.0)):
        b = ledger.place(
            trader="ape_pro", symbol="SYNTH", side="buy", qty=10, entry_price=entry
        )
        ledger.settle(b.id, exit_)
    ledger.place(
        trader="ape_pro", symbol="SYNTH", side="buy", qty=10, entry_price=100.0
    )
    # quiet_ape: 1 settled win (below rank threshold)
    b = ledger.place(
        trader="quiet_ape", symbol="SYNTH", side="sell", qty=5, entry_price=100.0
    )
    ledger.settle(b.id, 90.0)
    # paper_hands_pete: 3 settled, all early exits, net loss
    for entry, exit_ in ((100.0, 101.0), (100.0, 99.0), (100.0, 95.0)):
        b = ledger.place(
            trader="paper_hands_pete",
            symbol="SYNTH",
            side="buy",
            qty=10,
            entry_price=entry,
        )
        ledger.settle(b.id, exit_, early=True)
    return ledger


@finance_test
def test_build_rows():
    rows = {r["trader"]: r for r in build_leaderboard(_seeded_ledger().bets)}
    pro = rows["ape_pro"]
    assert pro["bets"] == 3 and pro["wins"] == 2
    assert pro["win_rate"] == round(2 / 3, 4)
    assert pro["total_pnl"] == 250.0  # +200 -200 +250
    assert pro["diamond_rate"] == 1.0
    assert pro["open"] == 1
    pete = rows["paper_hands_pete"]
    assert pete["diamond_rate"] == 0.0
    assert pete["total_pnl"] == -50.0  # +10 -10 -50
    quiet = rows["quiet_ape"]
    assert quiet["bets"] == 1 and quiet["total_pnl"] == 50.0


@finance_test
def test_ranked_threshold():
    rows = ranked_leaderboard(build_leaderboard(_seeded_ledger().bets))
    by_trader = {r["trader"]: r for r in rows}
    # ordered by total_pnl desc: ape_pro (250) > quiet_ape (50) > pete (-40)
    assert [r["trader"] for r in rows] == ["ape_pro", "quiet_ape", "paper_hands_pete"]
    assert by_trader["ape_pro"]["rank"] == 1
    assert by_trader["paper_hands_pete"]["rank"] == 2
    # quiet_ape below MIN_BETS_RANKED: shown, unranked
    assert by_trader["quiet_ape"]["rank"] is None
    assert MIN_BETS_RANKED == 3


@finance_test
def test_render_paper_stamped():
    out = render_leaderboard(build_leaderboard(_seeded_ledger().bets))
    assert "LEADERBOARD" in out
    assert "ape_pro" in out
    assert "PAPER" in out
    assert "not financial advice" in out
    assert "🥇" in out  # top rank medal


@finance_test
def test_render_empty():
    out = render_leaderboard(build_leaderboard([]))
    assert "no paper traders yet" in out


@finance_test
def test_render_screens_hostile_trader():
    ledger = BetLedger()
    b = ledger.place(
        trader="clean_ape", symbol="SYNTH", side="buy", qty=1, entry_price=1.0
    )
    # mutate past validation to simulate a hostile stored name
    # (base64-encoded hostile fixture — the literal stays out of source)
    b.trader = base64.b64decode("ZXZpbCByZXRhcmQ=").decode("utf-8")
    try:
        render_leaderboard(build_leaderboard(ledger.bets))
    except Exception as exc:
        assert "blocked term" in str(exc), str(exc)
    else:
        raise AssertionError("hostile trader name was rendered")


def main() -> int:
    failures = 0
    print(f"finance leaderboard tests ({len(_TESTS)} tests)")
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

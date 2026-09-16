"""Synthetic provider tests — hermetic, no network.

Run:  python3 tests/test_finance_synth.py     (has a real __main__ runner)
      python3 -m pytest tests/test_finance_synth.py -q
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from levi.finance.market import MarketDataError  # noqa: E402
from levi.finance.synth import (  # noqa: E402
    SyntheticProvider,
    is_synth_symbol,
)

_TESTS = []


def finance_test(fn):
    _TESTS.append(fn)
    return fn


@finance_test
def test_synth_symbol_gate():
    assert is_synth_symbol("SYNTH")
    assert is_synth_symbol("synthbtc")
    assert is_synth_symbol("SYNTHETH")
    assert not is_synth_symbol("AAPL")
    assert not is_synth_symbol("BTCUSDT")
    assert not is_synth_symbol("")
    assert not is_synth_symbol(None)


@finance_test
def test_synth_rejects_real_symbols():
    provider = SyntheticProvider()
    for sym in ("AAPL", "BTCUSDT", "MSFT"):
        try:
            provider.daily_bars(sym, days=10)
        except MarketDataError as exc:
            assert "SYNTH" in str(exc), str(exc)
        else:
            raise AssertionError(f"{sym} did not raise")


@finance_test
def test_synth_deterministic():
    a = SyntheticProvider(seed=7).daily_bars("SYNTH", days=60)
    b = SyntheticProvider(seed=7).daily_bars("SYNTH", days=60)
    assert len(a) == 60
    assert [x.close for x in a] == [x.close for x in b]
    assert [x.date for x in a] == [x.date for x in b]


@finance_test
def test_synth_suffix_stable_across_days():
    # The trailing `days` bars of the master series: a 60-day request is
    # the suffix of the 120-day request for the same symbol+seed.
    long = SyntheticProvider().daily_bars("SYNTH", days=120)
    short = SyntheticProvider().daily_bars("SYNTH", days=60)
    assert [x.close for x in short] == [x.close for x in long[-60:]]


@finance_test
def test_synth_different_symbols_differ():
    a = SyntheticProvider().daily_bars("SYNTH", days=30)
    b = SyntheticProvider().daily_bars("SYNTHBTC", days=30)
    assert [x.close for x in a] != [x.close for x in b]
    # crypto-like profile swings around a much bigger base
    assert b[-1].close > 1000


@finance_test
def test_synth_bars_valid():
    bars = SyntheticProvider().daily_bars("SYNTHETH", days=90)
    assert len(bars) == 90
    dates = [b.date for b in bars]
    assert dates == sorted(dates)
    for bar in bars:
        assert bar.high >= bar.low
        assert bar.high >= bar.open and bar.high >= bar.close
        assert bar.low <= bar.open and bar.low <= bar.close
        assert bar.close > 0 and bar.volume >= 0


@finance_test
def test_synth_bad_days():
    provider = SyntheticProvider()
    for bad in (0, -5, "60", True):
        try:
            provider.daily_bars("SYNTH", days=bad)
        except MarketDataError:
            pass
        else:
            raise AssertionError(f"days={bad!r} did not raise")


@finance_test
def test_synth_bad_seed():
    try:
        SyntheticProvider(seed="nope")
    except MarketDataError:
        pass
    else:
        raise AssertionError("bad seed did not raise")


def main() -> int:
    failures = 0
    print(f"finance synth tests ({len(_TESTS)} tests)")
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

"""Crypto provider tests — hermetic, no network.

The raw HTTP seam is ``BinanceProvider._download``; every test that
would touch the network monkeypatches it with a canned klines payload.

Run:  python3 tests/test_finance_crypto.py     (has a real __main__ runner)
      python3 -m pytest tests/test_finance_crypto.py -q
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from levi.finance.crypto import (  # noqa: E402
    BinanceProvider,
    looks_like_crypto,
)
from levi.finance.market import MarketDataError  # noqa: E402

_TESTS = []


def finance_test(fn):
    _TESTS.append(fn)
    return fn


def _klines_payload(n=5, start=60000.0):
    from datetime import datetime, timezone

    rows = []
    # 2026-09-08T00:00:00Z, computed — never hand-rolled.
    base_ms = int(datetime(2026, 9, 8, tzinfo=timezone.utc).timestamp() * 1000)
    for i in range(n):
        close = start + i * 100.0
        rows.append(
            [
                base_ms + i * 86400000,
                f"{close - 50:.1f}",
                f"{close + 50:.1f}",
                f"{close - 80:.1f}",
                f"{close:.1f}",
                f"{1234.5 + i}",
                base_ms + (i + 1) * 86400000 - 1,
                "0",
                0,
                "0",
                "0",
                "0",
            ]
        )
    return json.dumps(rows)


def _patched(payload: str) -> BinanceProvider:
    provider = BinanceProvider()
    provider._download = lambda url: payload  # noqa: SLF001
    return provider


@finance_test
def test_crypto_parses_klines():
    bars = _patched(_klines_payload(5)).daily_bars("BTCUSDT", days=5)
    assert len(bars) == 5
    assert bars[0].date == "2026-09-08"
    assert bars[-1].close == 60400.0
    assert bars[0].high >= bars[0].low
    assert bars[0].volume == 1234.5


@finance_test
def test_crypto_symbol_validation():
    provider = _patched(_klines_payload(2))
    for bad in ("btc usdt", "BTC-USDT!", "", "a", "x" * 21, None):
        try:
            provider.daily_bars(bad, days=2)
        except MarketDataError:
            pass
        else:
            raise AssertionError(f"symbol {bad!r} did not raise")


@finance_test
def test_crypto_lowercase_normalized():
    bars = _patched(_klines_payload(2)).daily_bars("ethusdt", days=2)
    assert len(bars) == 2


@finance_test
def test_crypto_bad_days():
    provider = _patched(_klines_payload(2))
    for bad in (0, -1, "10", 1001):
        try:
            provider.daily_bars("BTCUSDT", days=bad)
        except MarketDataError:
            pass
        else:
            raise AssertionError(f"days={bad!r} did not raise")


@finance_test
def test_crypto_unparseable_payload():
    for payload in ("not json", '{"oops": 1}', "[]", "[[1,2]]"):
        try:
            _patched(payload).daily_bars("BTCUSDT", days=5)
        except MarketDataError:
            pass
        else:
            raise AssertionError(f"payload {payload!r} did not raise")


@finance_test
def test_crypto_download_failure_honest():
    provider = BinanceProvider()

    def boom(url):
        raise MarketDataError("market data download failed (URLError)")

    provider._download = boom  # noqa: SLF001
    try:
        provider.daily_bars("BTCUSDT", days=5)
    except MarketDataError as exc:
        assert "failed" in str(exc)
    else:
        raise AssertionError("download failure did not raise")


@finance_test
def test_looks_like_crypto_hint():
    assert looks_like_crypto("BTCUSDT")
    assert looks_like_crypto("ethusdc")
    assert not looks_like_crypto("AAPL")
    assert not looks_like_crypto("")
    assert not looks_like_crypto(None)


def main() -> int:
    failures = 0
    print(f"finance crypto tests ({len(_TESTS)} tests)")
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

"""Market data provider tests — hermetic, no network.

The raw HTTP seam is ``StooqProvider._download``; every test that would
touch the network monkeypatches it (or ``urllib.request.urlopen`` to
exercise the error-wrapping inside ``_download`` itself).

Run:  python3 tests/test_finance_market.py     (has a real __main__ runner)
      python3 -m pytest tests/test_finance_market.py -q
"""
from __future__ import annotations

import sys
import traceback
import urllib.error
import urllib.request
from pathlib import Path

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from levi.finance.market import (  # noqa: E402
    Bar,
    MarketDataError,
    MarketDataProvider,
    PROVIDERS,
    StooqProvider,
    get_provider,
)

_TESTS = []


def finance_test(fn):
    _TESTS.append(fn)
    return fn


# Hand-written 5-row Stooq daily CSV fixture (N/D row must be skipped).
FIXTURE_CSV = """Date,Open,High,Low,Close,Volume
2026-09-08,100.0,105.0,99.0,104.0,1000000
2026-09-09,104.0,106.0,102.0,N/D,0
2026-09-10,105.0,110.0,104.0,109.0,2000000
2026-09-11,109.0,112.0,107.0,111.5,1500000
2026-09-12,111.5,113.0,110.0,112.0,1200000
"""


def _patched_provider(csv_text):
    provider = StooqProvider()
    provider._download = lambda url: csv_text  # noqa: SLF001
    return provider


@finance_test
def test_csv_parsing_maps_fields():
    bars = _patched_provider(FIXTURE_CSV).daily_bars("AAPL")
    # 5 CSV rows minus 1 N/D row = 4 bars, oldest first.
    assert len(bars) == 4, f"expected 4 bars, got {len(bars)}"
    first = bars[0]
    assert isinstance(first, Bar)
    assert first.date == "2026-09-08"
    assert first.open == 100.0
    assert first.high == 105.0
    assert first.low == 99.0
    assert first.close == 104.0
    assert first.volume == 1000000.0
    # Field order check on a later row: 2026-09-11 close is 111.5.
    assert bars[2].date == "2026-09-11"
    assert bars[2].close == 111.5
    assert bars[3].date == "2026-09-12"
    print("  4 bars parsed, fields map correctly")


@finance_test
def test_nd_rows_skipped():
    bars = _patched_provider(FIXTURE_CSV).daily_bars("aapl")
    dates = [b.date for b in bars]
    assert "2026-09-09" not in dates, f"N/D row leaked through: {dates}"
    assert dates == ["2026-09-08", "2026-09-10", "2026-09-11", "2026-09-12"]


@finance_test
def test_symbol_validation_rejects_bad_input():
    provider = StooqProvider()
    for bad in ["", "AAPL!", "AAPL;DROP", "toolongsymbolname", "A A P L", "BRK/A"]:
        try:
            provider.daily_bars(bad)
        except MarketDataError:
            pass
        else:
            raise AssertionError(f"bad symbol accepted: {bad!r}")
    print("  6 malformed symbols rejected")


@finance_test
def test_symbol_lowercased_in_url():
    seen = {}
    orig_download = StooqProvider._download

    def fake_download(self, url):
        seen["url"] = url
        return FIXTURE_CSV

    StooqProvider._download = fake_download  # noqa: SLF001
    try:
        bars = StooqProvider().daily_bars("AAPL", days=10)
    finally:
        StooqProvider._download = orig_download  # restore the real seam
    assert len(bars) == 4
    assert "s=aapl.us" in seen["url"], seen["url"]
    assert "i=d" in seen["url"]
    print(f"  url ok: {seen['url']}")


@finance_test
def test_http_error_becomes_market_data_error():
    real_urlopen = urllib.request.urlopen

    def boom(request, timeout=None):
        raise urllib.error.URLError("connection refused (test)")

    urllib.request.urlopen = boom
    try:
        try:
            StooqProvider().daily_bars("AAPL")
        except MarketDataError as exc:
            # Plain message: no URL echoed, no traceback needed by callers.
            assert "stooq.com" not in str(exc), str(exc)
            print(f"  wrapped ok: {exc}")
        else:
            raise AssertionError("URLError did not become MarketDataError")
    finally:
        urllib.request.urlopen = real_urlopen


@finance_test
def test_empty_response_raises_not_silent():
    for text in ["", "Date,Open,High,Low,Close,Volume\n"]:
        try:
            _patched_provider(text).daily_bars("AAPL")
        except MarketDataError:
            pass
        else:
            raise AssertionError(
                f"empty feed did not raise (text={text!r})"
            )
    print("  empty/all-header feeds raise MarketDataError")


@finance_test
def test_registry_lookup():
    assert "stooq" in PROVIDERS
    provider = get_provider("stooq")
    assert isinstance(provider, StooqProvider)
    assert isinstance(provider, MarketDataProvider)
    # Case-insensitive lookup.
    assert isinstance(get_provider("STOOQ"), StooqProvider)
    try:
        get_provider("bloomberg")
    except MarketDataError:
        pass
    else:
        raise AssertionError("unknown provider name did not raise")
    print("  registry: stooq resolves, unknown names raise")


@finance_test
def test_provider_interface_sanity():
    assert issubclass(StooqProvider, MarketDataProvider)
    assert hasattr(MarketDataProvider, "daily_bars")
    assert getattr(MarketDataProvider.daily_bars, "__isabstractmethod__", False)
    # bad days value is a caller error, surfaced as MarketDataError
    try:
        _patched_provider(FIXTURE_CSV).daily_bars("AAPL", days=0)
    except MarketDataError:
        pass
    else:
        raise AssertionError("days=0 did not raise")


def main() -> int:
    failures = 0
    print(f"finance market tests ({len(_TESTS)} tests)")
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

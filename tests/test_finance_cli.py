"""Finance CLI tests — hermetic, no network, no real HOME writes.

Exercises ``levi.cli.main.cmd_finance`` (the ``levi finance`` surface)
through in-process calls with the market-data seam monkeypatched
(``StooqProvider._download``) and the portfolio ledger redirected to a
temporary directory via ``levi.finance.portfolio.DEFAULT_PATH``.

One subprocess test verifies the parser wiring (``levi finance --help``)
end-to-end; everything else calls ``cmd_finance`` directly for speed and
hermeticity.

Run:  python3 tests/test_finance_cli.py     (has a real __main__ runner)
      python3 -m pytest tests/test_finance_cli.py -q
"""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import traceback
from contextlib import redirect_stdout
from datetime import date, timedelta
from pathlib import Path

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

import levi.cli.main as cli_main  # noqa: E402
from levi.finance import market as market_mod  # noqa: E402
from levi.finance import portfolio as portfolio_mod  # noqa: E402
from levi.finance import signals as signals_mod  # noqa: E402
from levi.finance import indicators as indicators_mod  # noqa: E402

_TESTS = []


def finance_test(fn):
    _TESTS.append(fn)
    return fn


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _fixture_csv(n=60, start_close=100.0, step=0.5):
    """Deterministic N-bar daily ramp fixture (no weekends excluded —
    the parser doesn't care). Last close = start_close + step*(n-1)."""
    lines = ["Date,Open,High,Low,Close,Volume"]
    d0 = date(2026, 7, 1)
    for i in range(n):
        close = start_close + step * i
        day = (d0 + timedelta(days=i)).isoformat()
        lines.append(
            f"{day},{close - 0.1:.2f},{close + 0.3:.2f},"
            f"{close - 0.3:.2f},{close:.2f},1000000"
        )
    return "\n".join(lines) + "\n"


#: 60-bar ramp: last close 129.50; scores bullish with confidence 0.95
#: (weighted net +5.50: trend +1 x1.5, momentum abstains on a perfect ramp,
#: strength +1 x0.5, +DI over -DI +1 x1.5, VWAP +1, OBV +1; regime
#: 'trending'; ATR% 0.62 -> no volatility penalty; MTF agreement capped).
RAMP_CSV = _fixture_csv(60)


class _patch_download:
    """Swap ``StooqProvider._download`` for a canned payload."""

    def __init__(self, payload):
        self.payload = payload
        self._orig = market_mod.StooqProvider._download

    def __enter__(self):
        payload = self.payload

        def _fake(self_, url):
            if isinstance(payload, Exception):
                raise payload
            return payload

        market_mod.StooqProvider._download = _fake
        return self

    def __exit__(self, *exc):
        market_mod.StooqProvider._download = self._orig
        return False


class _patch_portfolio_home:
    """Redirect the paper ledger to a temp directory (no real HOME writes)."""

    def __init__(self, tmp_path):
        self.tmp_path = Path(tmp_path)
        self._orig = portfolio_mod.DEFAULT_PATH

    def __enter__(self):
        portfolio_mod.DEFAULT_PATH = self.tmp_path / "portfolio.json"
        return self

    def __exit__(self, *exc):
        portfolio_mod.DEFAULT_PATH = self._orig
        return False


class _patch_narrate:
    """Keep narration deterministic and offline in tests."""

    def __init__(self, text="TEST NARRATIVE"):
        self.text = text
        self._orig = signals_mod.narrate

    def __enter__(self):
        text = self.text
        signals_mod.narrate = lambda signal: text
        return self

    def __exit__(self, *exc):
        signals_mod.narrate = self._orig
        return False


def _run_finance(tmpdir, action, **kwargs):
    """Run ``cmd_finance`` in-process; return (exit_code, stdout).

    ``tmpdir``: a fresh empty dir used as the portfolio home.
    """
    args = argparse.Namespace(
        finance_action=action,
        sym=None,
        qty=None,
        side=None,
        yes=False,
        live=False,
        amount=None,
        json=False,
    )
    for key, value in kwargs.items():
        setattr(args, key, value)
    buf = io.StringIO()
    with _patch_portfolio_home(tmpdir):
        try:
            with redirect_stdout(buf):
                cli_main.cmd_finance(args)
        except SystemExit as exc:
            return exc.code, buf.getvalue()
    return 0, buf.getvalue()


def _tmpdir():
    import tempfile

    return tempfile.mkdtemp(prefix="levi_finance_cli_test_")


# ---------------------------------------------------------------------------
# Parser wiring
# ---------------------------------------------------------------------------


@finance_test
def test_finance_help_lists_subcommands():
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "core"), *sys.path])
    proc = subprocess.run(
        [sys.executable, "-m", "levi.cli.main", "finance", "--help"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    for sub in ("quote", "indicators", "signal", "portfolio", "order", "deposit"):
        assert sub in proc.stdout, f"finance subcommand {sub!r} missing"


@finance_test
def test_finance_no_action_prints_usage():
    code, out = _run_finance(_tmpdir(), None)
    assert code == 0, out
    assert "levi finance" in out
    assert "quote" in out


# ---------------------------------------------------------------------------
# quote
# ---------------------------------------------------------------------------


@finance_test
def test_quote_prints_close():
    with _patch_download(RAMP_CSV):
        code, out = _run_finance(_tmpdir(), "quote", sym="TEST")
    assert code == 0, out
    assert "TEST" in out
    assert "129.50" in out  # last close of the ramp fixture
    assert "2026-08-29" in out  # date of the last bar


@finance_test
def test_quote_json():
    with _patch_download(RAMP_CSV):
        code, out = _run_finance(_tmpdir(), "quote", sym="test", json=True)
    assert code == 0, out
    payload = json.loads(out)
    assert payload["symbol"] == "TEST"
    assert payload["close"] == 129.5
    assert payload["date"] == "2026-08-29"


@finance_test
def test_quote_market_data_error_exits_1_honest():
    boom = market_mod.MarketDataError("market data download failed (Timeout)")
    with _patch_download(boom):
        code, out = _run_finance(_tmpdir(), "quote", sym="TEST")
    assert code == 1, out
    assert "Market data unavailable" in out
    # Never fake numbers: no price digits in the failure message.
    assert "129.50" not in out


# ---------------------------------------------------------------------------
# indicators
# ---------------------------------------------------------------------------


@finance_test
def test_indicators_prints_expected_values():
    with _patch_download(RAMP_CSV):
        code, out = _run_finance(_tmpdir(), "indicators", sym="TEST")
    assert code == 0, out
    closes = [100.0 + 0.5 * i for i in range(60)]
    assert f"{indicators_mod.sma(closes, 20)[-1]:.4f}" in out  # 124.7500
    assert f"{indicators_mod.ema(closes, 12)[-1]:.4f}" in out
    assert f"{indicators_mod.ema(closes, 26)[-1]:.4f}" in out
    assert f"{indicators_mod.rsi(closes, 14)[-1]:.1f}" in out  # 100.0
    macd_res = indicators_mod.macd(closes)
    assert f"{macd_res['macd_line'][-1]:.4f}" in out
    assert f"{macd_res['signal_line'][-1]:.4f}" in out
    assert f"{macd_res['histogram'][-1]:.4f}" in out
    bands = indicators_mod.bollinger(closes, 20, 2.0)
    assert f"{bands['upper'][-1]:.4f}" in out
    provider = market_mod.StooqProvider()
    provider._download = lambda url: RAMP_CSV  # noqa: SLF001
    bars = provider.daily_bars("TEST")
    assert f"{indicators_mod.atr(bars, 14)[-1]:.4f}" in out
    stoch = indicators_mod.stochastic(bars)
    assert f"{stoch['k'][-1]:.1f}" in out  # %K on the ramp
    assert f"{stoch['d'][-1]:.1f}" in out  # %D on the ramp
    assert f"{indicators_mod.obv(bars)[-1]:,.0f}" in out  # OBV
    adx_res = indicators_mod.adx(bars)
    assert f"{adx_res['adx'][-1]:.1f}" in out  # ADX14 = 100.0 on the ramp
    assert f"{adx_res['plus_di'][-1]:.1f}" in out
    assert f"{adx_res['minus_di'][-1]:.1f}" in out
    assert f"{indicators_mod.vwap(bars)[-1]:.4f}" in out  # VWAP
    regime = indicators_mod.classify_regime(bars)
    assert regime["regime"] == "trending"
    assert f"Regime           trending (ADX14 {regime['adx']:.1f}" in out


# ---------------------------------------------------------------------------
# signal
# ---------------------------------------------------------------------------


@finance_test
def test_signal_prints_direction_and_banner():
    with _patch_download(RAMP_CSV), _patch_narrate():
        code, out = _run_finance(_tmpdir(), "signal", sym="TEST")
    assert code == 0, out
    assert "ADVISORY ONLY — paper only, not financial advice" in out
    assert "BULLISH" in out  # ramp fixture scores bullish
    assert "0.95" in out  # confidence = min(0.95, 0.5 + 0.12*5.5), no vol penalty
    assert "•" in out  # rationale bullets
    assert "sma20" in out  # indicator snapshot
    assert "TEST NARRATIVE" in out


@finance_test
def test_signal_json():
    with _patch_download(RAMP_CSV), _patch_narrate("N"):
        code, out = _run_finance(_tmpdir(), "signal", sym="TEST", json=True)
    assert code == 0, out
    payload = json.loads(out)
    assert payload["direction"] == "bullish"
    assert payload["confidence"] == 0.95
    assert payload["advisory"] is True
    assert payload["narrative"] == "N"
    assert payload["indicator_snapshot"]["regime"] == "trending"


@finance_test
def test_signal_market_data_error_exits_1():
    boom = market_mod.MarketDataError("market data download failed (Timeout)")
    with _patch_download(boom):
        code, out = _run_finance(_tmpdir(), "signal", sym="TEST")
    assert code == 1, out
    assert "Market data unavailable" in out


# ---------------------------------------------------------------------------
# deposit
# ---------------------------------------------------------------------------


@finance_test
def test_deposit_funds_paper_portfolio():
    tmp = _tmpdir()
    code, out = _run_finance(tmp, "deposit", amount=1000.0)
    assert code == 0, out
    assert "1,000.00" in out
    assert "SIMULATED" in out
    ledger = json.loads((Path(tmp) / "portfolio.json").read_text())
    assert ledger["cash"] == 1000.0


@finance_test
def test_deposit_nonpositive_refuses():
    tmp = _tmpdir()
    for amount in (-5.0, 0.0):
        code, out = _run_finance(tmp, "deposit", amount=amount)
        assert code == 2, out
        assert "refused" in out.lower()
    assert not (Path(tmp) / "portfolio.json").exists()


# ---------------------------------------------------------------------------
# order (HITL gate)
# ---------------------------------------------------------------------------


@finance_test
def test_order_without_yes_exits_2_no_mutation():
    tmp = _tmpdir()
    _run_finance(tmp, "deposit", amount=1000.0)
    with _patch_download(RAMP_CSV):
        code, out = _run_finance(tmp, "order", sym="TEST", qty=10.0, side="buy")
    assert code == 2, out
    assert "--yes" in out
    assert "HITL" in out
    # Ledger untouched: cash still 1000, no positions.
    ledger = json.loads((Path(tmp) / "portfolio.json").read_text())
    assert ledger["cash"] == 1000.0
    assert ledger["positions"] == {}


@finance_test
def test_order_with_yes_mutates_and_says_simulated():
    tmp = _tmpdir()
    _run_finance(tmp, "deposit", amount=10000.0)
    with _patch_download(RAMP_CSV):
        code, out = _run_finance(
            tmp, "order", sym="TEST", qty=10.0, side="buy", yes=True
        )
    assert code == 0, out
    assert "SIMULATED" in out
    assert "TEST" in out
    ledger = json.loads((Path(tmp) / "portfolio.json").read_text())
    # 10 shares @ last close 129.50 → cash 10000 - 1295 = 8705.
    assert ledger["cash"] == 8705.0, ledger
    pos = ledger["positions"]["TEST"]
    assert pos["qty"] == 10.0
    assert pos["avg_cost"] == 129.5


@finance_test
def test_order_live_flag_refuses():
    tmp = _tmpdir()
    _run_finance(tmp, "deposit", amount=1000.0)
    with _patch_download(RAMP_CSV):
        code, out = _run_finance(
            tmp, "order", sym="TEST", qty=10.0, side="buy", yes=True, live=True
        )
    assert code == 2, out
    assert "NOT enabled" in out
    assert "LEVI_ALPACA_KEY" in out
    assert "transport_not_wired" in out
    ledger = json.loads((Path(tmp) / "portfolio.json").read_text())
    assert ledger["positions"] == {}  # nothing placed


@finance_test
def test_order_live_env_var_refuses():
    tmp = _tmpdir()
    _run_finance(tmp, "deposit", amount=1000.0)
    old = os.environ.get("LEVI_BROKER_LIVE")
    os.environ["LEVI_BROKER_LIVE"] = "1"
    try:
        with _patch_download(RAMP_CSV):
            code, out = _run_finance(
                tmp, "order", sym="TEST", qty=10.0, side="buy", yes=True
            )
    finally:
        if old is None:
            del os.environ["LEVI_BROKER_LIVE"]
        else:
            os.environ["LEVI_BROKER_LIVE"] = old
    assert code == 2, out
    assert "NOT enabled" in out
    ledger = json.loads((Path(tmp) / "portfolio.json").read_text())
    assert ledger["positions"] == {}


@finance_test
def test_order_invalid_qty_refuses():
    tmp = _tmpdir()
    _run_finance(tmp, "deposit", amount=1000.0)
    with _patch_download(RAMP_CSV):
        code, out = _run_finance(
            tmp, "order", sym="TEST", qty=0.0, side="buy", yes=True
        )
    assert code == 2, out
    assert "NOT placed" in out
    ledger = json.loads((Path(tmp) / "portfolio.json").read_text())
    assert ledger["positions"] == {}


@finance_test
def test_order_sell_more_than_held_refuses():
    tmp = _tmpdir()
    _run_finance(tmp, "deposit", amount=10000.0)
    with _patch_download(RAMP_CSV):
        code, out = _run_finance(
            tmp, "order", sym="TEST", qty=1.0, side="sell", yes=True
        )
    assert code == 2, out
    assert "rejected" in out.lower()


# ---------------------------------------------------------------------------
# portfolio
# ---------------------------------------------------------------------------


@finance_test
def test_portfolio_prints_cash_positions_and_pnl():
    tmp = _tmpdir()
    _run_finance(tmp, "deposit", amount=10000.0)
    with _patch_download(RAMP_CSV):
        _run_finance(tmp, "order", sym="TEST", qty=10.0, side="buy", yes=True)
        code, out = _run_finance(tmp, "portfolio")
    assert code == 0, out
    assert "SIMULATED" in out
    assert "8,705.00" in out  # cash
    assert "TEST" in out
    assert "realized P&L" in out
    assert "unrealized P&L" in out
    assert "market value" in out
    assert "total P&L" in out
    # Valued at the fetched close (129.50): 8705 + 1295 = 10000.
    assert "10,000.00" in out


@finance_test
def test_portfolio_warns_on_fetch_failure_not_zeroed():
    tmp = _tmpdir()
    _run_finance(tmp, "deposit", amount=10000.0)
    with _patch_download(RAMP_CSV):
        _run_finance(tmp, "order", sym="TEST", qty=10.0, side="buy", yes=True)
    boom = market_mod.MarketDataError("market data download failed (Timeout)")
    with _patch_download(boom):
        code, out = _run_finance(tmp, "portfolio")
    assert code == 0, out  # honest warning, not a crash
    assert "TEST" in out
    assert "warnings" in out.lower()
    # Position valued at average cost (129.50), never zeroed:
    # market value still 10000.00 even though the fetch failed.
    assert "10,000.00" in out


@finance_test
def test_portfolio_json():
    tmp = _tmpdir()
    _run_finance(tmp, "deposit", amount=500.0)
    code, out = _run_finance(tmp, "portfolio", json=True)
    assert code == 0, out
    payload = json.loads(out)
    assert payload["cash"] == 500.0
    assert payload["positions"] == {}


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------


def main():
    failures = 0
    for fn in _TESTS:
        name = fn.__name__
        try:
            fn()
        except AssertionError as e:
            failures += 1
            print(f"FAIL {name}: {e}")
        except SystemExit as e:
            failures += 1
            print(f"FAIL {name}: unexpected SystemExit({e.code})")
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

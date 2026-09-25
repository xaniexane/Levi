"""Signal engine tests — hermetic, hand-built bars, no network.

Bars are constructed by hand from synthetic close series, so every
expected direction/confidence value is derived from the documented
scoring rules, not copied from the implementation under test.

Run:  python3 tests/test_finance_signals.py     (has a real __main__ runner)
      python3 -m pytest tests/test_finance_signals.py -q
"""

from __future__ import annotations

import dataclasses
import sys
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from levi.finance.market import Bar, MarketDataError, MarketDataProvider, StooqProvider  # noqa: E402
from levi.finance.signals import (  # noqa: E402
    REGIME_WEIGHTS,
    _weighted_net,
    fallback_narrative,
    generate_signal,
    narrate,
    score_bars,
)
from levi.model.abstraction import ModelRouter  # noqa: E402

_TESTS = []


def finance_test(fn):
    _TESTS.append(fn)
    return fn


def _bars(closes):
    """Build daily bars from a close series (valid dates, sane OHLCV)."""
    out = []
    for i, close in enumerate(closes):
        day = (date(2026, 1, 5) + timedelta(days=i)).isoformat()
        out.append(
            Bar(
                date=day,
                open=close - 0.10,
                high=close + 0.50,
                low=close - 0.50,
                close=close,
                volume=1000.0,
            )
        )
    return out


def _rising(n=40):
    return _bars([100.0 + i for i in range(n)])


def _falling(n=40):
    return _bars([140.0 - i for i in range(n)])


def _flat(n=40):
    return _bars([100.0] * n)


def _dead_flat(n=40):
    """Truly motionless bars: high == low == open == close (ATR = 0)."""
    out = []
    for i in range(n):
        day = (date(2026, 1, 5) + timedelta(days=i)).isoformat()
        out.append(
            Bar(
                date=day,
                open=100.0,
                high=100.0,
                low=100.0,
                close=100.0,
                volume=1000.0,
            )
        )
    return out


@finance_test
def test_deterministic_same_bars_same_signal():
    # Scoring is deterministic: identical bars -> identical signal.
    # generated_at records wall-clock time, so it is excluded from the
    # comparison and validated separately as ISO-8601.
    s1 = score_bars("AAPL", _rising())
    s2 = score_bars("AAPL", _rising())
    assert s1.generated_at and s2.generated_at
    datetime.fromisoformat(s1.generated_at)  # raises if not ISO-8601
    assert dataclasses.replace(s1, generated_at="") == dataclasses.replace(
        s2, generated_at=""
    )


@finance_test
def test_rising_series_is_bullish():
    # 40 bars rising 1/day, regime 'trending' (ADX=100, ATR%=1.08):
    #   trend +1 x1.5, momentum abstains (float noise), strength +1 x0.5,
    #   +DI over -DI +1 x1.5, stochastic abstains (%K == %D on the ramp),
    #   VWAP +1 x1.0, OBV rising +1 x1.0.
    # weighted net = +5.50 -> bullish; base = min(0.95, 0.5+0.12*5.5) = 0.95;
    # ATR% 1.08 <= 2 -> no volatility penalty; MTF unavailable (40 < 60 bars).
    # Final confidence 0.95.
    sig = score_bars("AAPL", _rising())
    assert sig.direction == "bullish", sig.direction
    assert sig.confidence == 0.95, sig.confidence
    assert sig.advisory is True
    rationale = " ".join(sig.rationale)
    for expected in (
        "20-day SMA",
        "MACD",
        "RSI(14)",
        "overbought",
        "Bollinger",
        "Directional movement",
        "Stochastic",
        "VWAP",
        "OBV",
        "Regime: 'trending'",
        "weighted net +5.50",
        "direction 'bullish'",
    ):
        assert expected in rationale, f"missing from rationale: {expected!r}"
    snap = sig.indicator_snapshot
    assert snap["bars_used"] == 40
    assert snap["close"] > snap["sma20"]
    assert snap["rsi14"] == 100.0
    assert snap["atr_pct_of_close"] > 0
    assert snap["regime"] == "trending"
    assert snap["stochastic_k"] is not None
    assert snap["adx14"] is not None
    assert snap["plus_di14"] > snap["minus_di14"]
    assert snap["vwap"] is not None
    assert snap["obv"] is not None


@finance_test
def test_falling_series_is_bearish():
    # Mirror image of the rising series: every vote flips sign.
    # weighted net = -5.50 -> bearish, confidence 0.95, oversold notes.
    sig = score_bars("AAPL", _falling())
    assert sig.direction == "bearish", sig.direction
    assert sig.confidence == 0.95, sig.confidence
    assert sig.advisory is True
    rationale = " ".join(sig.rationale)
    for expected in (
        "20-day SMA",
        "MACD",
        "RSI(14)",
        "oversold",
        "-DI(14)",
        "weighted net -5.50",
        "direction 'bearish'",
    ):
        assert expected in rationale, f"missing from rationale: {expected!r}"
    assert sig.indicator_snapshot["rsi14"] == 0.0
    assert sig.indicator_snapshot["regime"] == "trending"


@finance_test
def test_momentum_abstains_on_float_noise():
    # On a perfect straight-line ramp, MACD and its signal line converge
    # to the same constant; their raw difference is ~1e-15 of float
    # noise. The momentum rule must abstain rather than cast a vote on
    # that noise — and the rationale must say so.
    sig = score_bars("AAPL", _rising())
    rationale = " ".join(sig.rationale)
    assert "abstains" in rationale
    assert "effectively equal" in rationale


@finance_test
def test_flat_series_is_neutral():
    # Truly motionless bars (ATR(14) = 0): the RSI(14) = 100.0 value is a
    # Wilder formula artifact, so the strength vote is withheld; trend,
    # momentum, DI, stochastic (%K == %D == 50.0), VWAP and OBV all
    # abstain on exact equality. weighted net = 0 -> neutral, conf 0.50.
    sig = score_bars("AAPL", _dead_flat())
    assert sig.direction == "neutral", sig.direction
    assert sig.confidence == 0.50, sig.confidence
    assert sig.advisory is True
    rationale = " ".join(sig.rationale)
    assert "weighted net +0.00" in rationale
    assert "formula artifact" in rationale
    assert sig.indicator_snapshot["atr14"] == 0.0


@finance_test
def test_constant_close_with_range_is_neutral():
    # Constant closes but a nonzero intraday range: ATR > 0, so RSI(14)
    # reads a genuine 100.0 (no down moves) and votes +1 bullish; regime
    # is 'ranging' (ADX = 0), so the mean-reversion class gets x1.5.
    # Trend, momentum, DI, stochastic, VWAP, OBV abstain.
    # weighted net = +1.50 -> still neutral, conf = 0.5 + 0.12*1.5 = 0.68.
    sig = score_bars("AAPL", _flat())
    assert sig.direction == "neutral", sig.direction
    assert sig.confidence == 0.68, sig.confidence
    assert "weighted net +1.50" in " ".join(sig.rationale)
    assert sig.indicator_snapshot["regime"] == "ranging"


@finance_test
def test_insufficient_data_is_neutral_zero_confidence():
    # 20 bars < MIN_BARS(30): never guessed, never scored.
    sig = score_bars("AAPL", _bars([100.0] * 20))
    assert sig.direction == "neutral"
    assert sig.confidence == 0.0
    rationale = " ".join(sig.rationale)
    assert "20" in rationale and "30" in rationale, rationale
    assert "never scored" in rationale or "never guessed" in rationale
    assert sig.indicator_snapshot["bars_used"] == 20


@finance_test
def test_weighted_net_applies_documented_weights():
    # Unit test of the weighting mechanism: one trend-following vote.
    # Trending up-weights it x1.5, ranging down-weights it x0.5.
    votes = [("trend_follow", 1)]
    net_t, bull_t, _ = _weighted_net(votes, REGIME_WEIGHTS["trending"])
    net_r, bull_r, _ = _weighted_net(votes, REGIME_WEIGHTS["ranging"])
    assert net_t == 1.5 and bull_t == 1.5
    assert net_r == 0.5 and bull_r == 0.5
    # A mean-reversion vote mirrors: x0.5 trending, x1.5 ranging.
    net_t, _, _ = _weighted_net([("mean_revert", -1)], REGIME_WEIGHTS["trending"])
    net_r, _, bear_r = _weighted_net([("mean_revert", -1)], REGIME_WEIGHTS["ranging"])
    assert net_t == -0.5 and net_r == -1.5 and bear_r == 1.5
    # Value/flow are regime-neutral; volatile privileges no class.
    for regime in ("trending", "ranging", "volatile", "unknown"):
        net, _, _ = _weighted_net([("value", 1), ("flow", -1)], REGIME_WEIGHTS[regime])
        assert net == 0.0, regime


@finance_test
def test_regime_weights_table_matches_documentation():
    # The exact table shipped in FINANCE.md §6.4 — the test pins the code
    # to the documented numbers.
    assert REGIME_WEIGHTS["trending"] == {
        "trend_follow": 1.5,
        "mean_revert": 0.5,
        "value": 1.0,
        "flow": 1.0,
    }
    assert REGIME_WEIGHTS["ranging"] == {
        "trend_follow": 0.5,
        "mean_revert": 1.5,
        "value": 1.0,
        "flow": 1.0,
    }
    assert REGIME_WEIGHTS["volatile"] == {
        "trend_follow": 1.0,
        "mean_revert": 1.0,
        "value": 1.0,
        "flow": 1.0,
    }


@finance_test
def test_volatility_penalty_lowers_confidence_for_identical_votes():
    # Same closes (same votes, same direction), wider daily ranges ->
    # higher ATR% -> strictly lower confidence.
    def _wide(closes):
        out = []
        for i, close in enumerate(closes):
            day = (date(2026, 1, 5) + timedelta(days=i)).isoformat()
            out.append(
                Bar(
                    date=day,
                    open=close - 0.1,
                    high=close + 5.0,
                    low=close - 5.0,
                    close=close,
                    volume=1000.0,
                )
            )
        return out

    closes = [100.0 + i for i in range(40)]
    narrow = score_bars("AAPL", _bars(closes))
    wide = score_bars("AAPL", _wide(closes))
    assert narrow.direction == wide.direction == "bullish"
    assert wide.confidence < narrow.confidence, (narrow.confidence, wide.confidence)
    assert narrow.indicator_snapshot["atr_pct_of_close"] < 2.0
    assert wide.indicator_snapshot["atr_pct_of_close"] > 4.0


@finance_test
def test_confidence_stays_within_bounds():
    # Property check across tapes: confidence is always in [0, 1].
    series = [
        _rising(),
        _falling(),
        _flat(),
        _dead_flat(),
        _bars([100.0 + i for i in range(70)]),  # 70-bar ramp (MTF on)
        _bars(
            [200.0 - i for i in range(60)]  # decline-then-bounce
            + [140.0 + i for i in range(10)]
        ),
    ]
    for bars in series:
        sig = score_bars("AAPL", bars)
        assert 0.0 <= sig.confidence <= 1.0, (sig.direction, sig.confidence)
        assert sig.confidence != 1.0  # the 0.95 honesty cap


@finance_test
def test_regime_note_names_weights_in_rationale():
    # The trending ramp names its regime and the exact multipliers.
    rationale = " ".join(score_bars("AAPL", _rising()).rationale)
    assert "Regime: 'trending'" in rationale
    assert "trend-following rules x1.5" in rationale
    assert "mean-reversion rules x0.5" in rationale


@finance_test
def test_mtf_confluence_unavailable_below_60_bars():
    sig = score_bars("AAPL", _rising())  # 40 bars
    rationale = " ".join(sig.rationale)
    assert "Multi-timeframe confluence unavailable" in rationale
    assert "at least 60" in rationale
    assert sig.indicator_snapshot["mtf_weekly_bars"] is None


@finance_test
def test_mtf_confluence_agreement_adds_delta():
    # 70-bar ramp: weekly close above weekly SMA(10) -> agreement (+0.05),
    # capped at the 0.95 honesty ceiling.
    sig = score_bars("AAPL", _bars([100.0 + i for i in range(70)]))
    rationale = " ".join(sig.rationale)
    assert "Multi-timeframe confluence:" in rationale
    assert "agreeing" in rationale
    assert "(+0.05 confidence)" in rationale
    assert sig.indicator_snapshot["mtf_weekly_bars"] == 14
    assert sig.indicator_snapshot["mtf_weekly_trend"] == "above"


@finance_test
def test_mtf_divergence_subtracts_delta():
    # Long decline then a sharp bounce: daily signal bullish, but the
    # weekly close sits below the weekly SMA(10) -> divergence (-0.05).
    closes = [200.0 - i for i in range(60)] + [140.0 + i for i in range(10)]
    sig = score_bars("AAPL", _bars(closes))
    rationale = " ".join(sig.rationale)
    assert "Multi-timeframe divergence:" in rationale
    assert "disagreeing" in rationale
    assert "(-0.05 confidence)" in rationale
    assert sig.direction == "bullish"
    assert sig.indicator_snapshot["mtf_weekly_trend"] == "below"


@finance_test
def test_new_indicator_snapshot_keys_present():
    snap = score_bars("AAPL", _rising()).indicator_snapshot
    for key in (
        "stochastic_k",
        "stochastic_d",
        "adx14",
        "plus_di14",
        "minus_di14",
        "vwap",
        "obv",
        "regime",
        "mtf_weekly_bars",
        "mtf_weekly_trend",
    ):
        assert key in snap, f"missing snapshot key: {key}"
    # Old keys still present — the snapshot only grew.
    for key in (
        "sma20",
        "macd_line",
        "macd_signal",
        "rsi14",
        "bollinger_upper",
        "atr14",
        "atr_pct_of_close",
    ):
        assert key in snap, f"missing snapshot key: {key}"


@finance_test
def test_architectural_rule_no_execution_path():
    # signals.py must have no import path to execution code. Grep-style:
    # parse the source and reject every forbidden token.
    path = ROOT / "core" / "levi" / "finance" / "signals.py"
    source = path.read_text(encoding="utf-8")
    for token in ("broker", "place_order", "PaperBroker", "Alpaca", "Order("):
        assert token not in source, f"forbidden token {token!r} in signals.py"


@finance_test
def test_fallback_narrative_is_advisory_and_paper_only():
    text = fallback_narrative(score_bars("AAPL", _rising()))
    lowered = text.lower()
    assert "advisory" in lowered
    assert "paper-only" in lowered
    assert "AAPL" in text
    assert "bullish" in text
    assert len(text) > 100


@finance_test
def test_narrate_with_model_router_present():
    # Real ModelRouter, no Ollama running: offline fallback inside the
    # router still yields non-empty narration. Never raises.
    text = narrate(score_bars("AAPL", _rising()))
    assert isinstance(text, str) and text.strip(), "narrate returned empty"


@finance_test
def test_narrate_degrades_gracefully(monkeypatch=None):
    # If the model path fails in any way, narrate() must return the
    # deterministic fallback instead of raising.
    sig = score_bars("AAPL", _rising())

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated model failure")

    original = ModelRouter.generate
    ModelRouter.generate = _raise
    try:
        text = narrate(sig)
    finally:
        ModelRouter.generate = original
    assert text == fallback_narrative(sig), text
    assert "advisory" in text


@finance_test
def test_narrate_without_local_model_uses_domain_fallback():
    # With no real model behind the router (the usual offline case),
    # narrate() must use the domain-specific fallback narrative — never
    # the router's generic offline template (which echoes prompts and
    # carries placeholder variables like "x, y, z").
    from levi.model.abstraction import ModelRouter as _MR

    status = _MR().status()
    if status.get("local_available") or status.get("cloud_enabled"):
        return  # a real model is present; nothing to assert here
    sig = score_bars("AAPL", _rising())
    text = narrate(sig)
    assert text == fallback_narrative(sig), text
    assert "advisory" in text
    assert "paper" in text.lower()
    assert "You said:" not in text


class _StubProvider(MarketDataProvider):
    def __init__(self, bars):
        self._bars = bars

    def daily_bars(self, symbol, days=120):
        return list(self._bars)


class _FailingProvider(MarketDataProvider):
    def daily_bars(self, symbol, days=120):
        raise MarketDataError("simulated outage")


@finance_test
def test_generate_signal_uses_provider():
    sig = generate_signal("AAPL", provider=_StubProvider(_rising()))
    assert sig.direction == "bullish"
    assert sig.symbol == "AAPL"
    # A provider failure propagates honestly — never fabricated.
    try:
        generate_signal("AAPL", provider=_FailingProvider())
    except MarketDataError:
        pass
    else:
        raise AssertionError("MarketDataError did not propagate")


@finance_test
def test_generate_signal_defaults_to_stooq():
    # Default provider is the keyless Stooq provider (no network touched
    # here — instantiation only).
    provider = StooqProvider()
    assert isinstance(provider, MarketDataProvider)


def main() -> int:
    failures = 0
    print(f"finance signal tests ({len(_TESTS)} tests)")
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

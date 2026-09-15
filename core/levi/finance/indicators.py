"""LEVI finance domain — pure-stdlib technical indicators.

All functions are deterministic, take plain lists of floats (``atr``
takes a list of :class:`~levi.finance.market.Bar`), and use ``math``
only. No pandas, no numpy (blueprint §1.1).

Insufficient data yields ``None`` (or ``None``-padded lists) — indicators
never fabricate values before their warmup window completes. Every
output list is aligned to its input list: ``out[i]`` describes
``values[i]``.
"""

from __future__ import annotations

import math

__all__ = [
    "sma",
    "ema",
    "rsi",
    "macd",
    "bollinger",
    "atr",
    "stochastic",
    "obv",
    "adx",
    "vwap",
    "classify_regime",
    "REGIME_TREND_ADX",
    "REGIME_VOLATILE_ATR_PCT",
]


def _require_period(period: int) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period < 1:
        raise ValueError(f"period must be a positive int, got {period!r}")


def sma(values: list[float], period: int) -> list[float | None]:
    """Simple moving average, ``None``-padded before the first window."""
    _require_period(period)
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    window_sum = sum(values[:period])
    out[period - 1] = window_sum / period
    for i in range(period, len(values)):
        window_sum += values[i] - values[i - period]
        out[i] = window_sum / period
    return out


def ema(values: list[float], period: int) -> list[float | None]:
    """Exponential moving average, seeded with the SMA of the first window.

    ``ema[period - 1]`` equals ``sma(values, period)[period - 1]``;
    earlier entries are ``None``.
    """
    _require_period(period)
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    k = 2.0 / (period + 1)
    prev = sum(values[:period]) / period
    out[period - 1] = prev
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1.0 - k)
        out[i] = prev
    return out


def rsi(values: list[float], period: int = 14) -> list[float | None]:
    """Relative Strength Index with Wilder smoothing.

    All-gains → 100.0, all-losses → 0.0, fewer than ``period + 1``
    values → all ``None``.
    """
    _require_period(period)
    out: list[float | None] = [None] * len(values)
    if len(values) < period + 1:
        return out
    gains = [max(0.0, values[i] - values[i - 1]) for i in range(1, period + 1)]
    losses = [max(0.0, values[i - 1] - values[i]) for i in range(1, period + 1)]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0.0:
        out[period] = 100.0
    else:
        out[period] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    for i in range(period + 1, len(values)):
        change = values[i] - values[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(0.0, change)) / period
        avg_loss = (avg_loss * (period - 1) + max(0.0, -change)) / period
        if avg_loss == 0.0:
            out[i] = 100.0
        else:
            out[i] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return out


def macd(
    values: list[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> dict[str, list[float | None]]:
    """MACD: fast EMA − slow EMA, plus signal line and histogram.

    Returns ``{"macd_line", "signal_line", "histogram"}``, each a list
    aligned to ``values`` with ``None`` padding. Histogram is
    ``macd_line − signal_line`` (positive when MACD sits above signal).
    """
    for p in (fast, slow, signal):
        _require_period(p)
    n = len(values)
    fast_line = ema(values, fast)
    slow_line = ema(values, slow)
    macd_line: list[float | None] = [None] * n
    for i in range(n):
        if fast_line[i] is not None and slow_line[i] is not None:
            macd_line[i] = fast_line[i] - slow_line[i]  # type: ignore[operator]
    # Signal line: EMA of the MACD line over its non-None span.
    first = next((i for i, v in enumerate(macd_line) if v is not None), None)
    signal_line: list[float | None] = [None] * n
    histogram: list[float | None] = [None] * n
    if first is not None:
        span = [v for v in macd_line[first:] if v is not None]
        sig_vals = ema(span, signal)
        for j, v in enumerate(sig_vals):
            signal_line[first + j] = v
        for i in range(n):
            if macd_line[i] is not None and signal_line[i] is not None:
                histogram[i] = macd_line[i] - signal_line[i]  # type: ignore[operator]
    return {
        "macd_line": macd_line,
        "signal_line": signal_line,
        "histogram": histogram,
    }


def bollinger(
    values: list[float], period: int = 20, mult: float = 2.0
) -> dict[str, list[float | None]]:
    """Bollinger bands: SMA ± ``mult`` × population stdev of the window.

    A constant series has stdev 0, so upper == middle == lower there.
    """
    _require_period(period)
    if mult < 0:
        raise ValueError(f"mult must be non-negative, got {mult!r}")
    n = len(values)
    middle = sma(values, period)
    upper: list[float | None] = [None] * n
    lower: list[float | None] = [None] * n
    for i in range(period - 1, n):
        if len(values) < period:
            break
        window = values[i - period + 1 : i + 1]
        mean = middle[i]
        assert mean is not None
        variance = sum((x - mean) ** 2 for x in window) / period
        band = mult * math.sqrt(variance)
        upper[i] = mean + band
        lower[i] = mean - band
    return {"middle": middle, "upper": upper, "lower": lower}


def atr(bars: list, period: int = 14) -> list[float | None]:
    """Average True Range with Wilder smoothing over :class:`Bar` rows.

    True Range of bar ``i`` is ``max(high − low, |high − prev_close|,
    |low − prev_close|)``; the first bar's is ``high − low``. The first
    ATR value is the mean of the first ``period`` true ranges. Flat bars
    yield 0.0 (never ``None``) once warmed up.
    """
    from levi.finance.market import Bar  # local import: avoids a cycle

    _require_period(period)
    out: list[float | None] = [None] * len(bars)
    if len(bars) < period:
        return out
    for bar in bars:
        if not isinstance(bar, Bar):
            raise ValueError(f"atr() expects Bar rows, got {type(bar).__name__}")
    true_ranges: list[float] = []
    for i, bar in enumerate(bars):
        if i == 0:
            true_ranges.append(bar.high - bar.low)
        else:
            prev_close = bars[i - 1].close
            true_ranges.append(
                max(
                    bar.high - bar.low,
                    abs(bar.high - prev_close),
                    abs(bar.low - prev_close),
                )
            )
    prev = sum(true_ranges[:period]) / period
    out[period - 1] = prev
    for i in range(period, len(bars)):
        prev = (prev * (period - 1) + true_ranges[i]) / period
        out[i] = prev
    return out


def stochastic(bars: list, k_period: int = 14, d_period: int = 3) -> dict[str, list[float | None]]:
    """Stochastic oscillator: %K and %D, aligned to ``bars``.

    Formula (standard, per Wilder/Lane convention)::

        %K(i) = 100 * (close_i - lowest_low(i-k+1..i))
                      / (highest_high(i-k+1..i) - lowest_low(i-k+1..i))
        %D(i) = SMA of %K over the last ``d_period`` values

    Warmup: %K needs ``k_period`` bars (``None`` before index
    ``k_period - 1``); %D needs ``k_period + d_period - 1`` bars.
    Zero-range window (highest high == lowest low, e.g. a flat tape):
    %K is defined as 50.0 — a documented midpoint choice, since the
    close sits exactly in the middle of a degenerate range.
    %K above %D is bullish momentum; below is bearish. Readings above
    80 / below 20 are the conventional overbought / oversold zones.
    """
    from levi.finance.market import Bar  # local import: avoids a cycle

    _require_period(k_period)
    _require_period(d_period)
    n = len(bars)
    for bar in bars:
        if not isinstance(bar, Bar):
            raise ValueError(
                f"stochastic() expects Bar rows, got {type(bar).__name__}"
            )
    k: list[float | None] = [None] * n
    for i in range(k_period - 1, n):
        window = bars[i - k_period + 1 : i + 1]
        lowest = min(b.low for b in window)
        highest = max(b.high for b in window)
        span = highest - lowest
        if span == 0.0:
            k[i] = 50.0
        else:
            k[i] = 100.0 * (bars[i].close - lowest) / span
    d: list[float | None] = [None] * n
    for i in range(k_period - 1 + d_period - 1, n):
        vals = k[i - d_period + 1 : i + 1]
        if all(v is not None for v in vals):
            d[i] = sum(vals) / d_period  # type: ignore[arg-type]
    return {"k": k, "d": d}


def obv(bars: list) -> list[float]:
    """On-Balance Volume (Granville).

    ``obv[0] = 0.0`` (no previous close to compare); then
    ``obv[i] = obv[i-1] + volume_i`` when ``close_i > close_{i-1}``,
    ``obv[i] = obv[i-1] - volume_i`` when ``close_i < close_{i-1}``,
    unchanged when the close is unchanged. The absolute level is
    arbitrary — the slope (accumulation vs distribution) is the signal.
    Never ``None``: defined for every bar once data exists.
    """
    from levi.finance.market import Bar  # local import: avoids a cycle

    out: list[float] = [0.0] * len(bars)
    for i, bar in enumerate(bars):
        if not isinstance(bar, Bar):
            raise ValueError(f"obv() expects Bar rows, got {type(bar).__name__}")
        if i == 0:
            continue
        prev = bars[i - 1].close
        if bar.close > prev:
            out[i] = out[i - 1] + bar.volume
        elif bar.close < prev:
            out[i] = out[i - 1] - bar.volume
        else:
            out[i] = out[i - 1]
    return out


def adx(bars: list, period: int = 14) -> dict[str, list[float | None]]:
    """Wilder's Average Directional Index, with +DI / -DI.

    Returns ``{"adx", "plus_di", "minus_di"}``, each aligned to ``bars``
    with ``None`` padding. Formulas (Wilder, 1978)::

        up_i   = high_i - high_{i-1} ; down_i = low_{i-1} - low_i
        +DM_i  = up_i   if up_i > down_i and up_i > 0 else 0
        -DM_i  = down_i if down_i > up_i and down_i > 0 else 0
        TR_i   = max(high_i - low_i, |high_i - close_{i-1}|,
                     |low_i - close_{i-1}|)

    At index ``period`` the three series are seeded with the plain sums
    of the first ``period`` values, then smoothed with Wilder recursion
    ``s(i) = s(i-1) - s(i-1)/period + x_i``. From there::

        +DI_i = 100 * smoothed(+DM)_i / smoothed(TR)_i
        -DI_i = 100 * smoothed(-DM)_i / smoothed(TR)_i
        DX_i  = 100 * |+DI_i - -DI_i| / (+DI_i + -DI_i)
                (0.0 when both directional indicators are zero)
        ADX   = mean of the first ``period`` DX values at index
                ``2*period - 1``, then Wilder-smoothed afterwards.

    Warmup: ``plus_di``/``minus_di`` need ``period + 1`` bars (first
    value at index ``period``); ``adx`` needs ``2 * period`` bars
    (first value at index ``2*period - 1``). ADX is directionless: high
    ADX means a strong trend (up or down), low ADX means no trend —
    direction comes from comparing +DI and -DI.
    """
    from levi.finance.market import Bar  # local import: avoids a cycle

    _require_period(period)
    n = len(bars)
    for bar in bars:
        if not isinstance(bar, Bar):
            raise ValueError(f"adx() expects Bar rows, got {type(bar).__name__}")
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    tr = [0.0] * n
    for i in range(1, n):
        up = bars[i].high - bars[i - 1].high
        down = bars[i - 1].low - bars[i].low
        if up > down and up > 0:
            plus_dm[i] = up
        if down > up and down > 0:
            minus_dm[i] = down
        prev_close = bars[i - 1].close
        tr[i] = max(
            bars[i].high - bars[i].low,
            abs(bars[i].high - prev_close),
            abs(bars[i].low - prev_close),
        )
    plus_di: list[float | None] = [None] * n
    minus_di: list[float | None] = [None] * n
    dx: list[float | None] = [None] * n
    adx_out: list[float | None] = [None] * n
    if n < period + 1:
        return {"adx": adx_out, "plus_di": plus_di, "minus_di": minus_di}
    s_tr = sum(tr[1 : period + 1])
    s_plus = sum(plus_dm[1 : period + 1])
    s_minus = sum(minus_dm[1 : period + 1])
    for i in range(period, n):
        if i > period:
            s_tr = s_tr - s_tr / period + tr[i]
            s_plus = s_plus - s_plus / period + plus_dm[i]
            s_minus = s_minus - s_minus / period + minus_dm[i]
        if s_tr == 0.0:
            plus_di[i] = 0.0
            minus_di[i] = 0.0
            dx[i] = 0.0
        else:
            pdi = 100.0 * s_plus / s_tr
            mdi = 100.0 * s_minus / s_tr
            plus_di[i] = pdi
            minus_di[i] = mdi
            dx[i] = 0.0 if (pdi + mdi) == 0.0 else 100.0 * abs(pdi - mdi) / (pdi + mdi)
    first_adx = 2 * period - 1
    if n > first_adx:
        seed = [v for v in dx[period : first_adx + 1] if v is not None]
        assert len(seed) == period  # i in [period, 2*period-1] all warm
        adx_out[first_adx] = sum(seed) / period
        for i in range(first_adx + 1, n):
            prev = adx_out[i - 1]
            assert prev is not None and dx[i] is not None
            adx_out[i] = (prev * (period - 1) + dx[i]) / period
    return {"adx": adx_out, "plus_di": plus_di, "minus_di": minus_di}


def vwap(bars: list) -> list[float]:
    """Volume-Weighted Average Price, anchored at the first bar.

    ``typical_i = (high_i + low_i + close_i) / 3``;
    ``vwap_i = sum(typical_j * volume_j for j <= i)
               / sum(volume_j for j <= i)``.
    On daily bars this is anchored to the first bar of the supplied
    series (not reset intraday) — the documented meaning here is "the
    average price actually paid over the window shown". A zero-volume
    prefix falls back to the typical price of the bar (documented
    choice, never a division by zero). Always defined for >= 1 bar.
    Price above VWAP means the market is paying up versus the average
    traded price; below means it is paying down.
    """
    from levi.finance.market import Bar  # local import: avoids a cycle

    out: list[float] = []
    cum_pv = 0.0
    cum_v = 0.0
    for bar in bars:
        if not isinstance(bar, Bar):
            raise ValueError(f"vwap() expects Bar rows, got {type(bar).__name__}")
        typical = (bar.high + bar.low + bar.close) / 3.0
        cum_pv += typical * bar.volume
        cum_v += bar.volume
        out.append(cum_pv / cum_v if cum_v > 0 else typical)
    return out


#: ADX threshold for "trending": Wilder's classic 25 — ADX >= 25 means a
#: trend strong enough to be worth following. The 20-25 "weak trend"
#: band is deliberately folded into "ranging" (conservative: do not
#: assume a trend without clear evidence).
REGIME_TREND_ADX = 25.0

#: ATR-as-%-of-close threshold for "volatile": >= 4.0% marks a tape
#: with unusually wide daily swings for large-cap daily bars. A
#: judgmental heuristic, not a researched universal constant — its job
#: is to flag tapes where the confidence penalty (not rule weighting)
#: should do the substantive work.
REGIME_VOLATILE_ATR_PCT = 4.0


def classify_regime(
    bars: list, adx_period: int = 14, atr_period: int = 14
) -> dict:
    """Classify the tape into trending / ranging / volatile from ADX + ATR%.

    Returns ``{"regime", "adx", "atr_pct"}``. Decision order:

    1. ``atr_pct = ATR(atr_period) / close * 100``; if
       ``atr_pct >= REGIME_VOLATILE_ATR_PCT`` (4.0) -> ``"volatile"``.
       Volatility is checked first because on a high-ATR% tape the
       volatility penalty on confidence — not per-regime rule
       weighting — does the substantive work.
    2. Else ``adx = ADX(adx_period)``; if ``adx >= REGIME_TREND_ADX``
       (25.0) -> ``"trending"`` (Wilder's trend-presence threshold).
    3. Else -> ``"ranging"`` (includes the 20-25 weak-trend band, by
       the conservative choice documented above).

    Needs ``max(2 * adx_period, atr_period)`` bars; with fewer, returns
    ``{"regime": "unknown", "adx": None, "atr_pct": None}`` — the
    caller never guesses a regime from insufficient data.
    """
    need = max(2 * adx_period, atr_period)
    if len(bars) < need:
        return {"regime": "unknown", "adx": None, "atr_pct": None}
    adx_val = adx(bars, adx_period)["adx"][-1]
    atr_val = atr(bars, atr_period)[-1]
    close = bars[-1].close
    atr_pct = (atr_val / close * 100.0) if close > 0 else 0.0
    if atr_pct >= REGIME_VOLATILE_ATR_PCT:
        regime = "volatile"
    elif adx_val is not None and adx_val >= REGIME_TREND_ADX:
        regime = "trending"
    else:
        regime = "ranging"
    return {"regime": regime, "adx": adx_val, "atr_pct": atr_pct}

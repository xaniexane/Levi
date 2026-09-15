"""LEVI finance domain — deterministic AI signal scoring engine.

This module turns OHLCV bars into a scored, human-readable ``Signal``.
The scoring is *deterministic* (fixed rules, no model, no randomness), so
the same bars always produce the same signal; a local model may
optionally *narrate* the result via :func:`narrate`, following the
model-preferred, offline-graceful pattern (blueprint §1.4).

Advisory-only by construction: signals describe what the indicators say.
This module has NO import path to any trade-execution code — a signal
cannot reach a live account, cannot move money, and cannot act. The
``Signal.advisory`` flag is always ``True`` (enforced in
``__post_init__``).

Scoring rules (this exact rule set ships in the code; the docstring of
:func:`score_bars` repeats it in review-brief form):

    1. TREND — close vs SMA(20): close above → +1 bullish point;
       close below → +1 bearish point; equal → abstain (no vote).
       Rule class: trend-following.
    2. MOMENTUM — MACD line vs signal line: above → +1 bullish;
       below → +1 bearish; equal → abstain. Compared with an epsilon
       tolerance (1e-9): converged EMA values can differ by floating-
       point noise (~1e-15), which must never cast a vote, so values
       within epsilon count as equal. Needs 34 bars for a warmed-up
       final signal-line value (slow 26 + signal 9); with 30–33 bars the
       rule abstains and says so in the rationale. Rule class:
       trend-following.
    3. STRENGTH — RSI(14): > 55 → +1 bullish; < 45 → +1 bearish.
       RSI > 70 or < 30 adds an overbought/oversold NOTE to the rationale
       (no point — extremes are context, not votes).
       Zero-movement guard: if ATR(14) is 0.0 the series did not move at
       all, and RSI collapses to a formula artifact (100.0); the strength
       vote is withheld and the rationale says so. Rule class:
       mean-reversion.
    4. VOLATILITY CONTEXT — Bollinger(20, 2) position: close in the upper
       third of the band → mild bullish note; lower third → mild bearish
       note; middle third or zero width → neutral note. Never a point.
       ATR(14) as % of close is reported in the snapshot as regime
       context, never as a vote.
    5. DIRECTIONAL MOVEMENT — +DI(14) vs -DI(14): +DI above → +1
       bullish; -DI above → +1 bearish; within epsilon (1e-9) → abstain.
       ADX itself is directionless; the +DI/-DI cross gives the
       direction. Rule class: trend-following.
    6. STOCHASTIC — %K(14) vs %D(3): %K above %D → +1 bullish; %K
       below %D → +1 bearish; within epsilon (1e-9) → abstain.
       %K > 80 or < 20 adds an overbought/oversold NOTE (no point).
       Rule class: mean-reversion.
    7. VALUE — close vs VWAP (anchored at the first bar): close above
       → +1 bullish; below → +1 bearish; equal → abstain. Rule class:
       value.
    8. MONEY FLOW — OBV slope over the last 5 bars: rising → +1
       bullish (accumulation); falling → +1 bearish (distribution);
       flat → abstain. Rule class: flow.
    9. REGIME WEIGHTING — the tape is classified by
       ``indicators.classify_regime`` into trending (ADX ≥ 25),
       ranging (ADX < 25), or volatile (ATR% ≥ 4.0). Per-regime
       weights multiply each rule's vote by its class weight
       (see ``REGIME_WEIGHTS``): trend-following rules ×1.5 when
       trending (×0.5 when ranging), mean-reversion rules ×1.5 when
       ranging (×0.5 when trending); value and flow rules ×1.0 in
       every regime; all classes ×1.0 when volatile. The weights are
       documented judgmental heuristics, not backtest-fitted numbers.
    10. SCORE — weighted_net = Σ weight × vote. Direction:
        weighted_net >= 2 → "bullish"; <= −2 → "bearish"; otherwise
        "neutral". Base confidence = min(0.95, 0.5 + 0.12 × |net|).
        Volatility adjustment: confidence is divided by
        ``1 + max(0, atr_pct − 2.0) / 4.0`` — no penalty while ATR% is
        at or below 2%, then each extra 4 points of ATR% halves the
        remaining confidence. Multi-timeframe confluence: when ≥ 60
        daily bars exist, they are resampled into 5-bar "weeks" and the
        weekly close is compared to the weekly SMA(10); agreement adds
        +0.05 confidence, disagreement subtracts 0.05, and with fewer
        than 60 bars the rationale says confluence is unavailable.
        Final confidence = clamp(base × vol_factor + mtf_delta, 0, 0.95),
        rounded to 2 decimals — never 1.00, never negative.
    11. INSUFFICIENT DATA — fewer than 30 bars → direction "neutral",
        confidence 0.0, and the rationale states exactly what is missing.
        Partial data is never scored; a signal is never guessed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from levi.finance.indicators import (
    adx,
    atr,
    bollinger,
    classify_regime,
    macd,
    obv,
    rsi,
    sma,
    stochastic,
    vwap,
)
from levi.finance.market import (
    Bar,
    MarketDataError,
    MarketDataProvider,
    StooqProvider,
)
from levi.model.abstraction import GenerationRequest, ModelRouter

__all__ = [
    "MIN_BARS",
    "MOMENTUM_EPS",
    "REGIME_WEIGHTS",
    "Signal",
    "score_bars",
    "generate_signal",
    "narrate",
    "fallback_narrative",
]

#: Minimum bars required before any scoring. Warmup math: SMA(20) and
#: Bollinger(20) need 20, RSI(14) needs 15, ATR(14) needs 14, +DI/-DI
#: need 15, stochastic %D needs 16, ADX(14) needs 28, and MACD(12, 26, 9)
#: needs 34 for a warmed-up *final* signal-line value. 30 is the
#: documented floor; with 30–33 bars the momentum rule abstains (see
#: score_bars) rather than guessing.
MIN_BARS = 30

#: Tolerance for the MACD momentum comparison. Converged EMA values can
#: differ by ~1e-15 of pure floating-point noise (verified on a perfect
#: straight-line price ramp); such noise must never cast a vote, so
#: differences at or below this epsilon count as equal and the momentum
#: rule abstains.
MOMENTUM_EPS = 1e-9

#: Tolerance for the stochastic %K vs %D comparison. Same rationale as
#: MOMENTUM_EPS: near-ties from converged smoothing must abstain.
STOCH_EPS = 1e-9

#: Tolerance for the +DI vs -DI comparison. Same rationale as
#: MOMENTUM_EPS.
DI_EPS = 1e-9

#: Lookback (in bars) for the OBV slope rule: OBV[-1] vs OBV[-6].
OBV_LOOKBACK = 5

#: Minimum daily bars before the multi-timeframe weekly resample runs.
#: 60 daily bars -> 12 "weekly" bars, enough to warm a weekly SMA(10).
MTF_MIN_DAILY_BARS = 60

#: Weekly SMA period used for the multi-timeframe trend comparison.
MTF_WEEKLY_SMA = 10

#: Confidence nudge for multi-timeframe agreement (+0.05) or
#: disagreement (-0.05). Small and bounded by design.
MTF_DELTA = 0.05

#: ATR-as-%-of-close at or below this baseline draws no volatility
#: penalty (~typical large-cap daily true range; a judgmental
#: heuristic).
VOL_BASE_PCT = 2.0

#: Each extra VOL_SCALE_PCT points of ATR% above the baseline halves
#: the remaining confidence: factor = 1 / (1 + max(0, atr_pct -
#: VOL_BASE_PCT) / VOL_SCALE_PCT).
VOL_SCALE_PCT = 4.0

#: Confidence never claims certainty from heuristics.
MAX_CONFIDENCE = 0.95

#: Per-regime weights by rule class. Documented rationale:
#: trend-following indicators whipsaw in ranges (false signals), and
#: mean-reversion indicators fade strong trends (painful) — so each
#: class is up-weighted ×1.5 where it belongs and down-weighted ×0.5
#: where it does not. Value (VWAP position) and flow (OBV slope) are
#: regime-neutral references, ×1.0 everywhere. In volatile tapes no
#: class is privileged (all ×1.0): the volatility penalty on
#: confidence does the substantive work there. These multipliers are
#: judgmental heuristics, not backtest-fitted constants.
REGIME_WEIGHTS = {
    "trending": {
        "trend_follow": 1.5,
        "mean_revert": 0.5,
        "value": 1.0,
        "flow": 1.0,
    },
    "ranging": {
        "trend_follow": 0.5,
        "mean_revert": 1.5,
        "value": 1.0,
        "flow": 1.0,
    },
    "volatile": {
        "trend_follow": 1.0,
        "mean_revert": 1.0,
        "value": 1.0,
        "flow": 1.0,
    },
    "unknown": {
        "trend_follow": 1.0,
        "mean_revert": 1.0,
        "value": 1.0,
        "flow": 1.0,
    },
}


@dataclass
class Signal:
    """One scored advisory signal for a symbol.

    ``advisory`` is always ``True``: a Signal is research output, never
    an instruction to act. ``__post_init__`` enforces this so the
    advisory-only property survives construction from any caller.
    """

    symbol: str
    direction: str  # "bullish" | "bearish" | "neutral"
    confidence: float  # 0.0–1.0
    rationale: list[str] = field(default_factory=list)
    indicator_snapshot: dict = field(default_factory=dict)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    advisory: bool = True

    def __post_init__(self) -> None:
        if self.direction not in ("bullish", "bearish", "neutral"):
            raise ValueError(
                f"direction must be bullish/bearish/neutral, got {self.direction!r}"
            )
        if not isinstance(self.confidence, (int, float)) or not (
            0.0 <= self.confidence <= 1.0
        ):
            raise ValueError(
                f"confidence must be in [0.0, 1.0], got {self.confidence!r}"
            )
        if self.advisory is not True:
            raise ValueError("Signal is advisory-only; advisory must be True")
        if not all(isinstance(line, str) for line in self.rationale):
            raise ValueError("rationale must be a list of strings")


def _round4(value: float | None) -> float | None:
    """Round a snapshot value for readability; pass ``None`` through."""
    return None if value is None else round(float(value), 4)


def _atr_pct(atr14: float, last_close: float) -> float:
    """ATR(14) as a percentage of the close (0.0 when the close <= 0)."""
    return (atr14 / last_close * 100.0) if last_close > 0 else 0.0


def _insufficient_rationale(n: int) -> list[str]:
    return [
        f"Only {n} daily bar(s) available; at least {MIN_BARS} are required "
        "to warm up the indicators — SMA(20)/Bollinger(20) need 20 bars, "
        "RSI(14) needs 15, ATR(14) needs 14, +DI/-DI need 15, stochastic "
        "%D needs 16, ADX(14) needs 28, and MACD(12, 26, 9) needs 34 "
        "for a fully warmed-up signal line.",
        "Direction forced to 'neutral' with confidence 0.0: partial data "
        "is never scored, and a signal is never guessed from what is missing.",
    ]


def _weighted_net(
    votes: list[tuple[str, int]], weights: dict[str, float]
) -> tuple[float, float, float]:
    """Apply per-regime class weights to rule votes.

    ``votes`` is a list of ``(rule_class, vote)`` with vote in
    ``(+1, -1, 0)``; ``weights`` maps rule class to multiplier.
    Returns ``(weighted_net, bullish_weight, bearish_weight)``.
    Pure function — unit-tested separately from the bar plumbing.
    """
    net = 0.0
    bull_w = 0.0
    bear_w = 0.0
    for rule_class, vote in votes:
        w = weights[rule_class]
        net += w * vote
        if vote > 0:
            bull_w += w
        elif vote < 0:
            bear_w += w
    return net, bull_w, bear_w


def _weekly_bars(bars: list[Bar]) -> list[Bar]:
    """Resample daily bars into fixed 5-trading-day "weekly" groups.

    These are consecutive 5-bar groups, oldest first — not calendar
    weeks (no calendar logic is used, keeping the resample deterministic
    and stdlib-trivial). The trailing group may cover fewer than 5 days
    (a partial week); it is kept as its own week. Open is the first
    bar's open, close the last bar's close, high/low the extremes,
    volume the sum.
    """
    out: list[Bar] = []
    for g in range(0, len(bars), 5):
        chunk = bars[g : g + 5]
        out.append(
            Bar(
                date=chunk[-1].date,
                open=chunk[0].open,
                high=max(b.high for b in chunk),
                low=min(b.low for b in chunk),
                close=chunk[-1].close,
                volume=sum(b.volume for b in chunk),
            )
        )
    return out


def _mtf_confluence(
    bars: list[Bar], direction: str
) -> tuple[str, float, int | None, str | None]:
    """Multi-timeframe confluence: weekly trend vs the daily signal.

    Returns ``(note, delta, weekly_bars_used, weekly_trend)`` where
    ``weekly_trend`` is "above" / "below" / "equal" / None.

    Precise meaning here: when at least ``MTF_MIN_DAILY_BARS`` (60)
    daily bars exist, they are resampled into 5-bar "weeks" (see
    :func:`_weekly_bars`) and the weekly close is compared to the
    weekly SMA(``MTF_WEEKLY_SMA``) (10). If the weekly trend agrees
    with a non-neutral daily direction, ``delta`` is ``+MTF_DELTA``
    (+0.05); if it disagrees, ``-MTF_DELTA``; if the weekly close
    equals the SMA, the daily signal is neutral, or the weekly SMA is
    unwarm, ``delta`` is 0.0 with a note saying so.

    Honest limits: with fewer than 60 daily bars there are not enough
    weekly bars to warm a weekly SMA(10), so confluence is unavailable
    and the note says exactly that — it is never estimated from what
    is missing. Even at 60+ bars, the weekly view is a coarse 5-bar
    grouping, not calendar weeks, and the nudge is deliberately small.
    """
    n = len(bars)
    if n < MTF_MIN_DAILY_BARS:
        return (
            f"Multi-timeframe confluence unavailable: {n} daily bars, but "
            f"the weekly resample needs at least {MTF_MIN_DAILY_BARS} to "
            "warm a weekly SMA(10) — no adjustment.",
            0.0,
            None,
            None,
        )
    weekly = _weekly_bars(bars)
    wcloses = [b.close for b in weekly]
    wcount = len(weekly)
    wclose = wcloses[-1]
    wsma = sma(wcloses, MTF_WEEKLY_SMA)[-1]
    if wsma is None or direction == "neutral":
        reason = (
            "the weekly SMA(10) is not warmed up"
            if wsma is None
            else "the daily signal is neutral"
        )
        return (
            f"Multi-timeframe: {wcount} weekly bars, weekly close "
            f"{wclose:.2f} vs weekly SMA({MTF_WEEKLY_SMA}) "
            f"{'n/a' if wsma is None else f'{wsma:.2f}'} — no confluence "
            f"check because {reason} (no adjustment).",
            0.0,
            wcount,
            None,
        )
    if wclose > wsma:
        wtrend = "above"
    elif wclose < wsma:
        wtrend = "below"
    else:
        wtrend = "equal"
    if wtrend == "equal":
        return (
            f"Multi-timeframe: weekly close {wclose:.2f} equals the weekly "
            f"SMA({MTF_WEEKLY_SMA}) — no confluence either way (no adjustment).",
            0.0,
            wcount,
            wtrend,
        )
    agrees = (direction == "bullish" and wtrend == "above") or (
        direction == "bearish" and wtrend == "below"
    )
    if agrees:
        return (
            f"Multi-timeframe confluence: weekly close {wclose:.2f} is "
            f"{wtrend} the weekly SMA({MTF_WEEKLY_SMA}) {wsma:.2f}, agreeing "
            f"with the daily '{direction}' signal (+{MTF_DELTA:.2f} confidence).",
            MTF_DELTA,
            wcount,
            wtrend,
        )
    return (
        f"Multi-timeframe divergence: weekly close {wclose:.2f} is "
        f"{wtrend} the weekly SMA({MTF_WEEKLY_SMA}) {wsma:.2f}, disagreeing "
        f"with the daily '{direction}' signal (-{MTF_DELTA:.2f} confidence).",
        -MTF_DELTA,
        wcount,
        wtrend,
    )


def score_bars(symbol: str, bars: list[Bar]) -> Signal:
    """Score daily bars into a deterministic advisory ``Signal``.

    Review-brief rule set (exactly what the code below implements):

    1. **Trend** (trend-following) — close vs SMA(20): close above → +1
       bullish point; close below → +1 bearish point; exactly equal →
       abstain (no vote).
    2. **Momentum** (trend-following) — MACD line vs signal line at the
       final bar: MACD above → +1 bullish; below → +1 bearish; equal →
       abstain. The comparison uses an epsilon tolerance of 1e-9:
       converged EMA values can differ by pure floating-point noise
       (~1e-15, observed on a perfect straight-line ramp), and such
       noise must never cast a vote — values within epsilon count as
       equal. The signal line needs 34 bars to warm up (slow 26 +
       signal 9), so with 30–33 bars this rule abstains and records why
       in the rationale.
    3. **Strength** (mean-reversion) — RSI(14) at the final bar: > 55 →
       +1 bullish; < 45 → +1 bearish. RSI > 70 or < 30 additionally
       appends an overbought/oversold NOTE to the rationale (context,
       not a vote). Zero-movement guard: when ATR(14) is 0.0 the series
       did not move at all and RSI collapses to the Wilder formula
       artifact 100.0; the strength vote is then withheld and the
       rationale says so.
    4. **Volatility context** — position of the close inside
       Bollinger(20, 2): upper third → mild bullish note, lower third →
       mild bearish note, middle third or zero band width → neutral
       note. Never scores a point. ATR(14) as a percentage of the close
       is reported in the snapshot as regime context, never as a vote.
    5. **Directional movement** (trend-following) — +DI(14) vs -DI(14)
       at the final bar: +DI above → +1 bullish (buying pressure
       dominates); -DI above → +1 bearish; within 1e-9 → abstain. ADX
       itself is directionless, so the +DI/-DI cross carries the
       directional vote.
    6. **Stochastic** (mean-reversion) — %K(14) vs %D(3) at the final
       bar: %K above %D → +1 bullish; %K below %D → +1 bearish; within
       1e-9 → abstain. %K > 80 or < 20 appends an overbought/oversold
       NOTE (context, not a vote).
    7. **Value** (value class) — close vs VWAP anchored at the first
       bar: close above → +1 bullish (market paying up versus the
       average traded price); close below → +1 bearish; equal → abstain.
    8. **Money flow** (flow class) — OBV slope over the last 5 bars:
       rising → +1 bullish (accumulation); falling → +1 bearish
       (distribution); flat → abstain.
    9. **Regime weighting** — ``classify_regime`` labels the tape
       trending (ADX ≥ 25), ranging (ADX < 25), or volatile (ATR% ≥
       4.0). Each rule's vote is multiplied by its class weight from
       ``REGIME_WEIGHTS``: trend-following ×1.5 when trending (×0.5
       when ranging), mean-reversion ×1.5 when ranging (×0.5 when
       trending), value and flow ×1.0 in every regime, every class
       ×1.0 when volatile. The multipliers are documented judgmental
       heuristics, not backtest-fitted constants.
    10. **Score** — weighted_net = Σ (weight × vote). Direction is
        "bullish" when weighted_net >= 2, "bearish" when <= −2, else
        "neutral". Base confidence = min(0.95, 0.5 + 0.12 × |net|).
        Volatility adjustment: the base is divided by
        ``1 + max(0, atr_pct − 2.0) / 4.0`` — no penalty at or below 2%
        ATR, then each extra 4 points of ATR% halves what remains.
        Multi-timeframe: with ≥ 60 daily bars the weekly resample adds
        +0.05 (agreement) or −0.05 (divergence); below 60 bars the
        rationale says it is unavailable. Final confidence =
        clamp(base × vol_factor + mtf_delta, 0, 0.95), rounded to 2
        decimals — never 1.00, never negative.
    11. **Insufficient data** — fewer than 30 bars → direction
        "neutral", confidence 0.0, rationale states exactly what is
        missing. The function never estimates a signal from partial
        data.

    The same ``bars`` always produce the same ``Signal`` (no model, no
    randomness). ``generated_at`` is the only field that varies, because
    it records when scoring ran.
    """
    n = len(bars)
    if n < MIN_BARS:
        return Signal(
            symbol=symbol,
            direction="neutral",
            confidence=0.0,
            rationale=_insufficient_rationale(n),
            indicator_snapshot={"bars_used": n},
        )

    closes = [bar.close for bar in bars]
    last_close = closes[-1]

    sma20 = sma(closes, 20)[-1]
    macd_res = macd(closes, fast=12, slow=26, signal=9)
    macd_line = macd_res["macd_line"][-1]
    macd_signal = macd_res["signal_line"][-1]
    rsi14 = rsi(closes, 14)[-1]
    bands = bollinger(closes, 20, 2.0)
    bb_upper = bands["upper"][-1]
    bb_middle = bands["middle"][-1]
    bb_lower = bands["lower"][-1]
    atr14 = atr(bars, 14)[-1]
    stoch = stochastic(bars, k_period=14, d_period=3)
    stoch_k = stoch["k"][-1]
    stoch_d = stoch["d"][-1]
    obv_vals = obv(bars)
    adx_res = adx(bars, 14)
    adx14 = adx_res["adx"][-1]
    plus_di14 = adx_res["plus_di"][-1]
    minus_di14 = adx_res["minus_di"][-1]
    vwap_val = vwap(bars)[-1]
    regime_info = classify_regime(bars, adx_period=14, atr_period=14)
    regime = regime_info["regime"]
    weights = REGIME_WEIGHTS[regime]
    atr_pct = _atr_pct(atr14, last_close)

    votes: list[tuple[str, int]] = []
    rationale: list[str] = []

    # --- Rule 1: trend (close vs SMA(20)) --------------------------------
    assert sma20 is not None  # n >= 30 >= 20, so the SMA is warmed up
    if last_close > sma20:
        votes.append(("trend_follow", 1))
        rationale.append(
            f"Trend: close {last_close:.2f} is above the 20-day SMA "
            f"{sma20:.2f} — price is trending higher (+1 bullish point, "
            "trend-following)."
        )
    elif last_close < sma20:
        votes.append(("trend_follow", -1))
        rationale.append(
            f"Trend: close {last_close:.2f} is below the 20-day SMA "
            f"{sma20:.2f} — price is trending lower (+1 bearish point, "
            "trend-following)."
        )
    else:
        rationale.append(
            f"Trend: close {last_close:.2f} equals the 20-day SMA — "
            "the trend rule abstains (no vote)."
        )

    # --- Rule 2: momentum (MACD line vs signal line) ----------------------
    if macd_line is not None and macd_signal is not None:
        if macd_line > macd_signal + MOMENTUM_EPS:
            votes.append(("trend_follow", 1))
            rationale.append(
                f"Momentum: MACD line {macd_line:.4f} is above its signal line "
                f"{macd_signal:.4f} — bullish momentum (+1 bullish point, "
                "trend-following)."
            )
        elif macd_line < macd_signal - MOMENTUM_EPS:
            votes.append(("trend_follow", -1))
            rationale.append(
                f"Momentum: MACD line {macd_line:.4f} is below its signal line "
                f"{macd_signal:.4f} — bearish momentum (+1 bearish point, "
                "trend-following)."
            )
        else:
            rationale.append(
                f"Momentum: MACD line {macd_line:.4f} and signal line "
                f"{macd_signal:.4f} differ by less than {MOMENTUM_EPS:g} — "
                "effectively equal, so the momentum rule abstains (no vote)."
            )
    else:
        # Only reachable with 30–33 bars: the MACD signal line needs 34.
        rationale.append(
            f"Momentum: MACD signal line is not warmed up with only {n} bars "
            "(needs 34: slow 26 + signal 9) — the momentum rule abstains "
            "(no vote)."
        )

    # --- Rule 3: strength (RSI(14)) ---------------------------------------
    assert rsi14 is not None  # n >= 30 >= 15, so RSI is warmed up
    assert atr14 is not None  # n >= 30 >= 14, so ATR is warmed up
    if atr14 == 0.0:
        # Degenerate flat series: RSI's Wilder smoothing divides by zero
        # average loss and yields 100.0 — a formula artifact, not strength.
        rationale.append(
            f"Strength: RSI(14) reads {rsi14:.1f}, but ATR(14) is 0.00 — the "
            "series did not move at all over the window, so the RSI value is "
            "a formula artifact and the strength vote is withheld (no vote)."
        )
    else:
        if rsi14 > 55:
            votes.append(("mean_revert", 1))
            rationale.append(
                f"Strength: RSI(14) is {rsi14:.1f}, above 55 — buying strength "
                "(+1 bullish point, mean-reversion)."
            )
        elif rsi14 < 45:
            votes.append(("mean_revert", -1))
            rationale.append(
                f"Strength: RSI(14) is {rsi14:.1f}, below 45 — selling "
                "weakness (+1 bearish point, mean-reversion)."
            )
        else:
            rationale.append(
                f"Strength: RSI(14) is {rsi14:.1f}, between 45 and 55 — "
                "no clear strength either way (no vote)."
            )
        if rsi14 > 70:
            rationale.append(
                f"Note: RSI(14) at {rsi14:.1f} is overbought (> 70) — "
                "upside may be stretched (context only, not a point)."
            )
        elif rsi14 < 30:
            rationale.append(
                f"Note: RSI(14) at {rsi14:.1f} is oversold (< 30) — "
                "downside may be stretched (context only, not a point)."
            )

    # --- Rule 4: volatility context (Bollinger position) -------------------
    band_position: float | None = None
    assert bb_upper is not None and bb_lower is not None  # n >= 20
    width = bb_upper - bb_lower
    if width > 0:
        band_position = (last_close - bb_lower) / width
        if band_position >= 2 / 3:
            rationale.append(
                f"Volatility context: close sits in the upper third of the "
                f"Bollinger band (position {band_position:.2f}) — buyers are "
                "pressing the top of the range (mild bullish note, no point)."
            )
        elif band_position <= 1 / 3:
            rationale.append(
                f"Volatility context: close sits in the lower third of the "
                f"Bollinger band (position {band_position:.2f}) — sellers are "
                "pressing the bottom of the range (mild bearish note, no point)."
            )
        else:
            rationale.append(
                f"Volatility context: close sits in the middle third of the "
                f"Bollinger band (position {band_position:.2f}) — price inside "
                "the range (neutral context, no point)."
            )
    else:
        rationale.append(
            "Volatility context: Bollinger band width is zero — the series is "
            "flat over the window, so there is no volatility context (no point)."
        )

    # --- Rule 5: directional movement (+DI vs -DI) -------------------------
    assert plus_di14 is not None and minus_di14 is not None  # n >= 30 >= 15
    if plus_di14 > minus_di14 + DI_EPS:
        votes.append(("trend_follow", 1))
        rationale.append(
            f"Directional movement: +DI(14) {plus_di14:.1f} is above -DI(14) "
            f"{minus_di14:.1f} — buying pressure dominates (+1 bullish point, "
            "trend-following)."
        )
    elif minus_di14 > plus_di14 + DI_EPS:
        votes.append(("trend_follow", -1))
        rationale.append(
            f"Directional movement: -DI(14) {minus_di14:.1f} is above +DI(14) "
            f"{plus_di14:.1f} — selling pressure dominates (+1 bearish point, "
            "trend-following)."
        )
    else:
        rationale.append(
            f"Directional movement: +DI(14) {plus_di14:.1f} and -DI(14) "
            f"{minus_di14:.1f} differ by less than {DI_EPS:g} — effectively "
            "equal, so the directional-movement rule abstains (no vote)."
        )

    # --- Rule 6: stochastic (%K vs %D) -------------------------------------
    assert stoch_k is not None and stoch_d is not None  # n >= 30 >= 16
    if stoch_k > stoch_d + STOCH_EPS:
        votes.append(("mean_revert", 1))
        rationale.append(
            f"Stochastic: %K(14) {stoch_k:.1f} is above %D(3) {stoch_d:.1f} — "
            "short-term momentum turning up (+1 bullish point, mean-reversion)."
        )
    elif stoch_k < stoch_d - STOCH_EPS:
        votes.append(("mean_revert", -1))
        rationale.append(
            f"Stochastic: %K(14) {stoch_k:.1f} is below %D(3) {stoch_d:.1f} — "
            "short-term momentum turning down (+1 bearish point, mean-reversion)."
        )
    else:
        rationale.append(
            f"Stochastic: %K(14) {stoch_k:.1f} and %D(3) {stoch_d:.1f} differ "
            f"by less than {STOCH_EPS:g} — effectively equal, so the "
            "stochastic rule abstains (no vote)."
        )
    if stoch_k > 80:
        rationale.append(
            f"Note: stochastic %K at {stoch_k:.1f} is overbought (> 80) — "
            "upside may be stretched (context only, not a point)."
        )
    elif stoch_k < 20:
        rationale.append(
            f"Note: stochastic %K at {stoch_k:.1f} is oversold (< 20) — "
            "downside may be stretched (context only, not a point)."
        )

    # --- Rule 7: value (close vs VWAP) -------------------------------------
    if last_close > vwap_val:
        votes.append(("value", 1))
        rationale.append(
            f"Value: close {last_close:.2f} is above VWAP {vwap_val:.2f} — the "
            "market is paying up versus the average traded price over the "
            "window (+1 bullish point, value)."
        )
    elif last_close < vwap_val:
        votes.append(("value", -1))
        rationale.append(
            f"Value: close {last_close:.2f} is below VWAP {vwap_val:.2f} — the "
            "market is paying down versus the average traded price over the "
            "window (+1 bearish point, value)."
        )
    else:
        rationale.append(
            f"Value: close {last_close:.2f} equals VWAP — price sits on the "
            "average traded price (no vote)."
        )

    # --- Rule 8: money flow (OBV slope) ------------------------------------
    obv_slope = obv_vals[-1] - obv_vals[-OBV_LOOKBACK - 1]  # n >= 30 >= 6
    if obv_slope > 0:
        votes.append(("flow", 1))
        rationale.append(
            f"Money flow: OBV rising over the last {OBV_LOOKBACK} bars "
            f"({obv_slope:+,.0f}) — accumulation (+1 bullish point, flow)."
        )
    elif obv_slope < 0:
        votes.append(("flow", -1))
        rationale.append(
            f"Money flow: OBV falling over the last {OBV_LOOKBACK} bars "
            f"({obv_slope:+,.0f}) — distribution (+1 bearish point, flow)."
        )
    else:
        rationale.append(
            f"Money flow: OBV unchanged over the last {OBV_LOOKBACK} bars — "
            "no accumulation or distribution signal (no vote)."
        )

    # --- Rule 9: regime weighting ------------------------------------------
    net, bull_w, bear_w = _weighted_net(votes, weights)
    rationale.append(
        f"Regime: '{regime}' (ADX(14) {adx14:.1f}, ATR {atr_pct:.2f}% "
        f"of close) — trend-following rules x{weights['trend_follow']:g}, "
        f"mean-reversion rules x{weights['mean_revert']:g}, value and flow "
        f"rules x{weights['value']:g}. Rationale: trend-following whipsaws "
        "in ranges and mean-reversion fades strong trends, so each class "
        "is up-weighted where it belongs and down-weighted where it does "
        "not; value/flow are regime-neutral; volatile tapes privilege no "
        "class and let the volatility penalty do the work."
    )

    # --- Rule 10: score -----------------------------------------------------
    if net >= 2:
        direction = "bullish"
    elif net <= -2:
        direction = "bearish"
    else:
        direction = "neutral"
    # Base confidence: min(0.95, 0.5 + 0.12 x |net|), 2-decimal rounding.
    base_conf = min(MAX_CONFIDENCE, 0.5 + 0.12 * abs(net))
    vol_factor = 1.0 / (1.0 + max(0.0, atr_pct - VOL_BASE_PCT) / VOL_SCALE_PCT)
    mtf_note, mtf_delta, mtf_weekly_bars, mtf_weekly_trend = _mtf_confluence(
        bars, direction
    )
    rationale.append(mtf_note)
    confidence = round(
        min(MAX_CONFIDENCE, max(0.0, base_conf * vol_factor + mtf_delta)), 2
    )
    rationale.insert(
        0,
        f"Score: weighted net {net:+.2f} ({bull_w:.2f} bullish vs {bear_w:.2f} "
        f"bearish) -> direction '{direction}'. Base confidence {base_conf:.2f}; "
        f"volatility factor {vol_factor:.3f} (ATR% {atr_pct:.2f}); "
        f"multi-timeframe {mtf_delta:+.2f} -> final confidence {confidence:.2f}.",
    )

    snapshot = {
        "bars_used": n,
        "close": _round4(last_close),
        "sma20": _round4(sma20),
        "macd_line": _round4(macd_line),
        "macd_signal": _round4(macd_signal),
        "rsi14": _round4(rsi14),
        "bollinger_upper": _round4(bb_upper),
        "bollinger_middle": _round4(bb_middle),
        "bollinger_lower": _round4(bb_lower),
        "bollinger_position": _round4(band_position),
        "atr14": _round4(atr14),
        "atr_pct_of_close": _round4(atr_pct),
        "stochastic_k": _round4(stoch_k),
        "stochastic_d": _round4(stoch_d),
        "adx14": _round4(adx14),
        "plus_di14": _round4(plus_di14),
        "minus_di14": _round4(minus_di14),
        "vwap": _round4(vwap_val),
        "obv": _round4(obv_vals[-1]),
        "regime": regime,
        "mtf_weekly_bars": mtf_weekly_bars,
        "mtf_weekly_trend": mtf_weekly_trend,
    }

    return Signal(
        symbol=symbol,
        direction=direction,
        confidence=confidence,
        rationale=rationale,
        indicator_snapshot=snapshot,
    )


def generate_signal(
    symbol: str,
    provider: MarketDataProvider | None = None,
    days: int = 120,
) -> Signal:
    """Fetch daily bars and score them into an advisory ``Signal``.

    ``provider`` defaults to :class:`~levi.finance.market.StooqProvider`
    (keyless). A ``MarketDataError`` from the provider propagates
    honestly — this function never fabricates bars or a signal from a
    failed fetch.
    """
    if provider is None:
        provider = StooqProvider()
    bars = provider.daily_bars(symbol, days=days)
    return score_bars(symbol, bars)


def _signal_facts_block(signal: Signal) -> str:
    """Deterministic plain-text summary of a signal for narration."""
    lines = [
        f"Symbol: {signal.symbol}",
        f"Direction: {signal.direction}",
        f"Confidence: {signal.confidence:.2f}",
        "Reasons:",
    ]
    lines.extend(f"- {line}" for line in signal.rationale)
    snapshot = ", ".join(
        f"{key}={value}" for key, value in signal.indicator_snapshot.items()
    )
    lines.append(f"Indicator snapshot: {snapshot}")
    return "\n".join(lines)


def narrate(signal: Signal) -> str:
    """Narrate a signal as plain-language advice (model-preferred).

    Tries :class:`~levi.model.abstraction.ModelRouter` first when a real
    local or cloud model is available; on ANY failure — no model
    available, generation error, empty text — falls back to
    :func:`fallback_narrative`, which is deterministic and
    domain-specific (the router's own generic offline template is never
    used for signal commentary). Never raises for narration reasons:
    narration is commentary, not data.
    """
    prompt = (
        "Rewrite these deterministic market-signal facts as 2-4 sentences of "
        "plain-language commentary for a paper-trading research notebook. "
        "Keep every number unchanged. Do not invent new facts. Do not "
        "recommend real trades. End with a clear statement that this is "
        "advisory-only and paper-only, never a real position.\n\n"
        + _signal_facts_block(signal)
    )
    system = (
        "You are LEVI's finance signal narrator. Plain language, no jargon "
        "overload, no invented facts."
    )
    try:
        router = ModelRouter()
        status = router.status()
        if not (status.get("local_available") or status.get("cloud_enabled")):
            # No real model behind the router — its generic offline
            # template is not suitable signal commentary; use the
            # domain-specific deterministic narrative instead.
            return fallback_narrative(signal)
        result = router.generate(
            GenerationRequest(
                prompt=prompt,
                system=system,
                max_tokens=220,
                temperature=0.3,
            )
        )
        text = (result.text or "").strip()
        if not text or result.model_id == "fallback-deterministic":
            return fallback_narrative(signal)
        return text
    except Exception:
        return fallback_narrative(signal)


def fallback_narrative(signal: Signal) -> str:
    """Deterministic plain-language narrative for a signal (pure function).

    Used directly when no model is available and as the guaranteed
    fallback inside :func:`narrate`. Reads as plain-language advice and
    always carries the advisory wording and the paper-only disclaimer.
    """
    confidence_pct = f"{signal.confidence:.0%}"
    if signal.rationale:
        reasons = " ".join(signal.rationale)
    else:
        reasons = "No supporting reasons were recorded."
    return (
        f"Advisory signal for {signal.symbol}: {signal.direction} "
        f"(confidence {confidence_pct}).\n"
        f"Why: {reasons}\n"
        "This is an advisory, not financial advice — LEVI scores these "
        "signals deterministically from price data and cannot act on them.\n"
        "Paper-only disclaimer: this signal is for paper-trading research "
        "only. No real money is involved, and nothing here is a "
        "recommendation to trade."
    )

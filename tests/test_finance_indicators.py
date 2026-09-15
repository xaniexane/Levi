"""Indicator math tests — hand-computed expectations, no network.

Every expected number below is computed by hand in the comments, not
copied from the implementation under test.

Run:  python3 tests/test_finance_indicators.py     (has a real __main__ runner)
      python3 -m pytest tests/test_finance_indicators.py -q
"""
from __future__ import annotations

import math
import sys
import traceback
from pathlib import Path

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from levi.finance.indicators import (  # noqa: E402
    adx,
    atr,
    bollinger,
    classify_regime,
    ema,
    macd,
    obv,
    rsi,
    sma,
    stochastic,
    vwap,
)
from levi.finance.market import Bar  # noqa: E402

_TESTS = []


def finance_test(fn):
    _TESTS.append(fn)
    return fn


def close(a, b, tol=1e-9):
    assert math.isclose(a, b, rel_tol=tol, abs_tol=tol), f"{a} != {b}"


@finance_test
def test_sma_hand_computed():
    # values [1,2,3,4,5], period 3:
    #   i=2: (1+2+3)/3 = 2.0 ; i=3: (2+3+4)/3 = 3.0 ; i=4: (3+4+5)/3 = 4.0
    out = sma([1, 2, 3, 4, 5], 3)
    assert out == [None, None, 2.0, 3.0, 4.0], out
    assert out[3] == 3.0  # the headline check
    # insufficient data -> all None, same length
    assert sma([1, 2], 3) == [None, None]


@finance_test
def test_ema_seeds_from_sma():
    # values [1,2,3,4,5], period 3, k = 2/(3+1) = 0.5
    #   seed ema[2] = (1+2+3)/3 = 2.0
    #   ema[3] = 4*0.5 + 2.0*0.5 = 3.0
    #   ema[4] = 5*0.5 + 3.0*0.5 = 4.0
    out = ema([1, 2, 3, 4, 5], 3)
    assert out[0] is None and out[1] is None
    close(out[2], 2.0)  # == sma seed
    close(out[3], 3.0)
    close(out[4], 4.0)
    assert len(out) == 5


@finance_test
def test_rsi_all_up_is_100():
    # every change +1 -> avg_loss == 0 -> 100.0; needs period+1 values
    out = rsi([1, 2, 3, 4, 5], period=2)
    assert out == [None, None, 100.0, 100.0, 100.0], out


@finance_test
def test_rsi_all_down_is_0():
    out = rsi([5, 4, 3, 2, 1], period=2)
    assert out == [None, None, 0.0, 0.0, 0.0], out


@finance_test
def test_rsi_wilder_smoothing_hand_computed():
    # values [10,12,11,13], period 2. Changes: +2, -1, +2.
    # First window (changes +2, -1):
    #   avg_gain = (2+0)/2 = 1.0 ; avg_loss = (0+1)/2 = 0.5
    #   RS = 2 -> RSI = 100 - 100/3 = 66.666...   (at index 2)
    # Next (change +2, Wilder):
    #   avg_gain = (1.0*1 + 2)/2 = 1.5 ; avg_loss = (0.5*1 + 0)/2 = 0.25
    #   RS = 6 -> RSI = 100 - 100/7 = 85.714285... (at index 3)
    out = rsi([10, 12, 11, 13], period=2)
    assert out[0] is None and out[1] is None
    close(out[2], 100 - 100 / 3)
    close(out[3], 100 - 100 / 7)
    print(f"  rsi: {out[2]:.6f}, {out[3]:.6f}")


@finance_test
def test_rsi_insufficient_data_is_none():
    assert rsi([1, 2, 3], period=14) == [None, None, None]
    assert rsi([], period=14) == []


@finance_test
def test_bollinger_constant_series_collapses():
    # stdev of a constant window is 0 -> upper == middle == lower
    bands = bollinger([7, 7, 7, 7, 7], period=3, mult=2.0)
    for key in ("middle", "upper", "lower"):
        assert bands[key] == [None, None, 7.0, 7.0, 7.0], (key, bands[key])


@finance_test
def test_bollinger_hand_computed():
    # values [1,2,3,4,5], period 3, mult 2.0. Each window has the same
    # spread: population stdev = sqrt(((1+0+1)/3)) = sqrt(2/3) = 0.8164965809
    #   i=2: middle 2.0 -> upper 2+2*0.8164965809 = 3.6329931619
    #                     -> lower 2-2*0.8164965809 = 0.3670068381
    #   i=3: middle 3.0 -> upper 4.6329931619, lower 1.3670068381
    #   i=4: middle 4.0 -> upper 5.6329931619, lower 2.3670068381
    bands = bollinger([1, 2, 3, 4, 5], period=3, mult=2.0)
    sd = math.sqrt(2 / 3)
    for i, mean in ((2, 2.0), (3, 3.0), (4, 4.0)):
        close(bands["middle"][i], mean)
        close(bands["upper"][i], mean + 2 * sd)
        close(bands["lower"][i], mean - 2 * sd)
    assert bands["upper"][0] is None and bands["upper"][1] is None
    print(f"  band[2]: {bands['lower'][2]:.6f} {bands['middle'][2]} {bands['upper'][2]:.6f}")


@finance_test
def test_atr_flat_bars_is_zero():
    bars = [Bar(date=f"2026-09-{d:02d}", open=100, high=100, low=100,
                close=100, volume=0) for d in range(1, 6)]
    out = atr(bars, period=3)
    # True Range of a flat bar is 0; after warmup ATR is 0.0 (not None)
    assert out == [None, None, 0.0, 0.0, 0.0], out


@finance_test
def test_atr_hand_computed():
    # b1: h=110 l=100 c=105 -> TR1 = 110-100 = 10
    # b2: h=115 l=102 c=110, prev c=105 -> TR2 = max(13, |115-105|=10, |102-105|=3) = 13
    # b3: h=118 l=112 c=117, prev c=110 -> TR3 = max(6, |118-110|=8, |112-110|=2) = 8
    # ATR(3) at i=2 = (10+13+8)/3 = 31/3 = 10.333...
    bars = [
        Bar(date="2026-09-01", open=100, high=110, low=100, close=105, volume=1),
        Bar(date="2026-09-02", open=105, high=115, low=102, close=110, volume=1),
        Bar(date="2026-09-03", open=110, high=118, low=112, close=117, volume=1),
    ]
    out = atr(bars, period=3)
    assert out[0] is None and out[1] is None
    close(out[2], 31 / 3)
    # Wilder smoothing continues: TR4 = max(5,|120-117|=3,|115-117|=2)=5
    # ATR = (10.333...*2 + 5)/3 = 25.666.../3 = 8.555...
    bars.append(Bar(date="2026-09-04", open=117, high=120, low=115,
                    close=119, volume=1))
    out = atr(bars, period=3)
    close(out[3], ((31 / 3) * 2 + 5) / 3)
    print(f"  atr: {out[2]:.6f}, {out[3]:.6f}")


@finance_test
def test_macd_crossover_sign_convention():
    # An accelerating (quadratic) rising series: the fast EMA stays above
    # the slow EMA by a widening gap, so macd_line > signal_line and the
    # histogram is positive at the end. (A perfectly *linear* series would
    # not work: MACD(12,26) converges to exactly 7.0 there and the signal
    # line converges to the same value, leaving only float noise.)
    values = [float(i * i) for i in range(1, 61)]
    res = macd(values, fast=12, slow=26, signal=9)
    for key in ("macd_line", "signal_line", "histogram"):
        assert len(res[key]) == 60, key
    # Warmup: macd_line starts at index 25 (slow EMA seed), signal/hist
    # start at index 33 (25 + signal period 9 - 1).
    assert res["macd_line"][24] is None
    assert res["macd_line"][25] is not None
    assert res["histogram"][32] is None
    assert res["histogram"][33] is not None
    assert res["macd_line"][-1] > res["signal_line"][-1]
    assert res["histogram"][-1] > 0
    close(res["histogram"][-1],
          res["macd_line"][-1] - res["signal_line"][-1])
    print(f"  macd[-1]={res['macd_line'][-1]:.4f} "
          f"signal[-1]={res['signal_line'][-1]:.4f} "
          f"hist[-1]={res['histogram'][-1]:.4f}")


@finance_test
def test_macd_insufficient_data_all_none():
    res = macd([1.0, 2.0, 3.0])
    for key in ("macd_line", "signal_line", "histogram"):
        assert res[key] == [None, None, None], key


@finance_test
def test_period_validation():
    for fn in (lambda: sma([1.0], 0), lambda: ema([1.0], -2),
               lambda: rsi([1.0], 0), lambda: macd([1.0], fast=0),
               lambda: bollinger([1.0], 0),
               lambda: atr([], 0)):
        try:
            fn()
        except ValueError:
            pass
        else:
            raise AssertionError("period < 1 did not raise ValueError")


def _mkbars(rows):
    """Build Bar rows from (high, low, close, volume) tuples."""
    return [
        Bar(
            date=f"2026-09-{i + 1:02d}",
            open=c - 0.1,
            high=h,
            low=low,
            close=c,
            volume=v,
        )
        for i, (h, low, c, v) in enumerate(rows)
    ]


@finance_test
def test_stochastic_hand_computed():
    # k_period=3. Bars (h, l, c):
    #   b0: 10/8/9, b1: 11/9/10, b2: 12/10/11, b3: 11/9/9.5, b4: 13/11/12.5
    # K[2] = 100*(11-8)/(12-8)   = 75.0
    # K[3] = 100*(9.5-9)/(12-9)  = 100*0.5/3  = 16.666...
    # K[4] = 100*(12.5-9)/(13-9) = 100*3.5/4  = 87.5
    # D = SMA(K, 3): D[4] = (75 + 50/3 + 87.5)/3 = 59.722...
    bars = _mkbars(
        [(10, 8, 9, 100), (11, 9, 10, 100), (12, 10, 11, 100),
         (11, 9, 9.5, 100), (13, 11, 12.5, 100)]
    )
    out = stochastic(bars, k_period=3, d_period=3)
    k, d = out["k"], out["d"]
    assert k[0] is None and k[1] is None
    close(k[2], 75.0)
    close(k[3], 50.0 / 3.0)
    close(k[4], 87.5)
    assert d[0] is None and d[1] is None and d[2] is None and d[3] is None
    close(d[4], (75.0 + 50.0 / 3.0 + 87.5) / 3.0)


@finance_test
def test_stochastic_zero_range_is_fifty():
    # Degenerate flat tape: highest high == lowest low -> %K defined as
    # 50.0 (documented midpoint), never a ZeroDivisionError.
    bars = _mkbars([(100, 100, 100, 1000)] * 5)
    out = stochastic(bars, k_period=3, d_period=2)
    assert out["k"][2:] == [50.0, 50.0, 50.0], out["k"]
    assert out["d"][3:] == [50.0, 50.0], out["d"]


@finance_test
def test_obv_hand_computed():
    # closes 10, 11, 11, 9 with volumes 100, 200, 300, 400:
    # obv[0] = 0.0 (no previous close)
    # i=1: up   -> 0 + 200 = 200
    # i=2: flat -> 200
    # i=3: down -> 200 - 400 = -200
    bars = _mkbars(
        [(10, 9, 10, 100), (11, 10, 11, 200),
         (11, 10, 11, 300), (10, 9, 9, 400)]
    )
    assert obv(bars) == [0.0, 200.0, 200.0, -200.0], obv(bars)


@finance_test
def test_vwap_hand_computed():
    # typical prices: (10+8+9)/3 = 9, (12+10+11)/3 = 11, (14+12+13)/3 = 13
    # vwap[0] = 9*100/100 = 9.0
    # vwap[1] = (900 + 2200)/300 = 3100/300 = 31/3
    # vwap[2] = (3100 + 3900)/600 = 7000/600 = 35/3
    bars = _mkbars(
        [(10, 8, 9, 100), (12, 10, 11, 200), (14, 12, 13, 300)]
    )
    out = vwap(bars)
    close(out[0], 9.0)
    close(out[1], 31.0 / 3.0)
    close(out[2], 35.0 / 3.0)
    assert len(out) == 3


@finance_test
def test_vwap_zero_volume_prefix_falls_back():
    # Zero cumulative volume -> typical price of the bar, never div-by-0.
    bars = _mkbars([(10, 8, 9, 0), (12, 10, 11, 200)])
    out = vwap(bars)
    close(out[0], 9.0)
    close(out[1], 11.0)  # (9*0 + 11*200)/200


@finance_test
def test_adx_perfect_uptrend_is_100():
    # Steady uptrend: +DM > 0 every bar, -DM = 0 -> +DI >> -DI, DX = 100,
    # ADX(3) = 100 at the first valid index (2*3-1 = 5).
    bars = _mkbars(
        [(1000, 998, 999, 100), (1002, 999, 1001, 100),
         (1004, 1000, 1003, 100), (1006, 1002, 1005, 100),
         (1008, 1004, 1007, 100), (1010, 1006, 1009, 100),
         (1012, 1008, 1011, 100)]
    )
    out = adx(bars, period=3)
    assert out["adx"][:5] == [None] * 5, out["adx"]
    close(out["adx"][5], 100.0)
    close(out["adx"][6], 100.0)
    assert out["plus_di"][3] > out["minus_di"][3]
    close(out["minus_di"][5], 0.0)


@finance_test
def test_adx_ranging_hand_computed():
    # Balanced +DM/-DM (alternating up/down extensions), period=3.
    # Hand-computed (Wilder smoothing from index 3):
    #   DX[3] = 100/3, DX[4] = 100/9, DX[5] = 700/27, DX[6] = 1300/81
    #   ADX[5] = (DX[3]+DX[4]+DX[5])/3 = 1900/81 = 23.4568
    #   ADX[6] = (ADX[5]*2 + DX[6])/3 = 5100/243 = 20.9877
    #   +DI[6] = 100*(17/27)/(197/18) = 5.7522
    #   -DI[6] = 100*(47/54)/(197/18) = 7.9534
    bars = _mkbars(
        [(100.5, 99.0, 99.8, 100), (101.0, 99.0, 100.2, 100),
         (101.0, 98.5, 99.6, 100), (101.5, 98.5, 100.4, 100),
         (101.5, 98.0, 99.8, 100), (102.0, 98.0, 100.6, 100),
         (102.0, 97.5, 100.0, 100)]
    )
    out = adx(bars, period=3)
    assert out["adx"][:5] == [None] * 5, out["adx"]
    close(out["adx"][5], 1900.0 / 81.0, tol=1e-6)
    close(out["adx"][6], 5100.0 / 243.0, tol=1e-6)
    close(out["plus_di"][6], 5.7522, tol=1e-3)
    close(out["minus_di"][6], 7.9534, tol=1e-3)


@finance_test
def test_adx_insufficient_data_all_none():
    # period=3: +DI/-DI need 4 bars (valid from index 3), ADX needs 6
    # (first value at index 5). With 5 bars, ADX is all None while the
    # directional indicators are warmed up (0.0 on this flat series).
    bars = _mkbars([(10, 9, 9.5, 100)] * 5)
    out = adx(bars, period=3)
    assert all(v is None for v in out["adx"]), out["adx"]
    assert out["plus_di"][:3] == [None] * 3, out["plus_di"]
    assert out["plus_di"][3:] == [0.0, 0.0], out["plus_di"]
    assert len(out["adx"]) == 5  # still aligned to input length


@finance_test
def test_classify_regime_trending():
    # Perfect uptrend, tiny ATR% (0.39% < 4.0): ADX(3) = 100 >= 25.
    bars = _mkbars(
        [(1000, 998, 999, 100), (1002, 999, 1001, 100),
         (1004, 1000, 1003, 100), (1006, 1002, 1005, 100),
         (1008, 1004, 1007, 100), (1010, 1006, 1009, 100),
         (1012, 1008, 1011, 100)]
    )
    res = classify_regime(bars, adx_period=3, atr_period=3)
    assert res["regime"] == "trending", res
    close(res["adx"], 100.0)
    assert res["atr_pct"] < 4.0


@finance_test
def test_classify_regime_ranging():
    # Balanced +DM/-DM fixture: ADX(3) = 20.99 < 25, ATR% = 3.60 < 4.0.
    bars = _mkbars(
        [(100.5, 99.0, 99.8, 100), (101.0, 99.0, 100.2, 100),
         (101.0, 98.5, 99.6, 100), (101.5, 98.5, 100.4, 100),
         (101.5, 98.0, 99.8, 100), (102.0, 98.0, 100.6, 100),
         (102.0, 97.5, 100.0, 100)]
    )
    res = classify_regime(bars, adx_period=3, atr_period=3)
    assert res["regime"] == "ranging", res
    assert res["adx"] < 25.0
    assert res["atr_pct"] < 4.0


@finance_test
def test_classify_regime_volatile_takes_priority():
    # Strong uptrend (ADX(3) = 100) but ATR% ~ 14.8 >= 4.0 -> "volatile":
    # the volatility check runs first by design.
    bars = _mkbars(
        [(110, 90, 100, 100), (115, 95, 108, 100), (120, 100, 115, 100),
         (125, 105, 120, 100), (130, 110, 125, 100), (135, 115, 130, 100),
         (140, 120, 135, 100)]
    )
    res = classify_regime(bars, adx_period=3, atr_period=3)
    assert res["regime"] == "volatile", res
    assert res["atr_pct"] >= 4.0


@finance_test
def test_classify_regime_unknown_on_short_data():
    # 5 bars < 2*3 = 6 needed: unknown, never guessed.
    bars = _mkbars([(1000, 998, 999, 100)] * 5)
    res = classify_regime(bars, adx_period=3, atr_period=3)
    assert res == {"regime": "unknown", "adx": None, "atr_pct": None}, res


def main() -> int:
    failures = 0
    print(f"finance indicator tests ({len(_TESTS)} tests)")
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

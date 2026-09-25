"""Seeded synthetic market data for the LEVI finance domain.

The :class:`SyntheticProvider` serves deterministic, seeded OHLCV bars for
``SYNTH*`` symbols only. It never returns real market data and never
claims to: every bar it produces is synthetic by construction, and the
symbol gate (``^SYNTH[A-Z]{0,8}$``) makes a synthetic symbol unmistakable
next to a real one.

Use it for offline demos, WSB-mode paper bets, and hermetic tests —
anywhere a network fetch is unavailable or undesirable. Anything built
on these bars (signals, forecasts, P&L) is labeled synthetic end to end.

Stdlib-only: ``hashlib``, ``random``, ``re``, ``datetime``.
"""

from __future__ import annotations

import hashlib
import random
import re
from datetime import date, timedelta

from levi.finance.market import Bar, MarketDataError, MarketDataProvider

__all__ = [
    "SyntheticProvider",
    "SYNTH_SYMBOL_RE",
    "SYNTH_UNIVERSE",
    "is_synth_symbol",
]

#: Synthetic symbols are unmistakable: they all start with SYNTH.
SYNTH_SYMBOL_RE = re.compile(r"^SYNTH[A-Z]{0,8}$")

#: base price + per-regime personality per known synthetic symbol.
#: Unknown SYNTH* symbols fall back to the generic equity-like profile.
SYNTH_UNIVERSE: dict[str, dict] = {
    "SYNTH": {"base": 100.0, "kind": "equity-like"},
    "SYNTHBTC": {"base": 60000.0, "kind": "crypto-like"},
    "SYNTHETH": {"base": 3000.0, "kind": "crypto-like"},
}

#: (drift, daily volatility) per regime. The master series cycles through
#: these in 30-bar blocks: trend up, range, high volatility, trend down.
_REGIMES = (
    ("trend_up", 0.004, 0.012),
    ("range", 0.0, 0.008),
    ("volatile", 0.0, 0.045),
    ("trend_down", -0.004, 0.014),
)
_BLOCK = 30
_MASTER_BARS = 2000


def is_synth_symbol(symbol: object) -> bool:
    """True for symbols the synthetic provider serves (``SYNTH*``)."""
    return isinstance(symbol, str) and bool(
        SYNTH_SYMBOL_RE.match(symbol.strip().upper())
    )


def _seed_for(symbol: str, seed: int) -> int:
    digest = hashlib.sha256(f"{symbol}:{seed}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


class SyntheticProvider(MarketDataProvider):
    """Deterministic seeded synthetic bars for ``SYNTH*`` symbols.

    A 2000-bar master series is generated per (symbol, seed); requests
    return the trailing ``days`` bars, so results are stable across
    different ``days`` values. Same symbol + seed ⇒ same prices, always;
    calendar dates anchor to ``as_of`` (default: today), so pass an
    explicit ``as_of`` when dates must be reproducible across sessions.

    Raises :class:`MarketDataError` for non-SYNTH symbols — this provider
    never serves (or fabricates) real market data.
    """

    #: Default seed. Override per-instance for alternate histories.
    seed: int = 20260915

    def __init__(self, seed: int = 20260915, as_of: date | None = None) -> None:
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise MarketDataError(f"seed must be an int, got {seed!r}")
        if as_of is not None and not isinstance(as_of, date):
            raise MarketDataError(f"as_of must be a date, got {as_of!r}")
        self.seed = seed
        # Date anchor for the generated calendar: defaults to today so a
        # fresh provider always ends "now"; pin it for reproducibility.
        self.as_of: date = as_of or date.today()

    def _master_series(self, symbol: str) -> list[Bar]:
        profile = SYNTH_UNIVERSE.get(symbol, {"base": 50.0, "kind": "equity-like"})
        base = float(profile["base"])
        crypto_like = profile["kind"] == "crypto-like"
        rng = random.Random(_seed_for(symbol, self.seed))
        end = self.as_of
        start = end - timedelta(days=_MASTER_BARS - 1)
        price = base
        bars: list[Bar] = []
        for i in range(_MASTER_BARS):
            _name, drift, vol = _REGIMES[(i // _BLOCK) % len(_REGIMES)]
            if crypto_like:
                vol *= 1.6  # crypto-like symbols swing harder
            shock = rng.gauss(0.0, vol)
            open_ = price
            close = open_ * (1.0 + drift + shock)
            # Keep the walk positive-definite; a zero/negative print is a
            # generator bug, never a market event.
            close = max(close, base * 0.01)
            wick = abs(rng.gauss(0.0, vol * 0.6))
            high = max(open_, close) * (1.0 + wick)
            low = min(open_, close) * (1.0 - wick)
            low = max(low, base * 0.005)
            volume = base * (2000.0 if crypto_like else 1000.0) * (0.5 + rng.random())
            bars.append(
                Bar(
                    date=(start + timedelta(days=i)).isoformat(),
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
            )
            price = close
        return bars

    def daily_bars(self, symbol: str, days: int = 120) -> list[Bar]:
        """Return the last ``days`` synthetic bars for a ``SYNTH*`` symbol.

        Raises ``MarketDataError`` for anything that is not a SYNTH
        symbol — real symbols are never served here.
        """
        if not isinstance(symbol, str):
            raise MarketDataError(f"invalid symbol: {symbol!r}")
        clean = symbol.strip().upper()
        if not SYNTH_SYMBOL_RE.match(clean):
            raise MarketDataError(
                f"synthetic provider only serves SYNTH* symbols "
                f"(got {symbol!r}) — it never returns real market data."
            )
        if isinstance(days, bool) or not isinstance(days, int) or days < 1:
            raise MarketDataError(f"days must be a positive int, got {days!r}")
        if days > _MASTER_BARS:
            raise MarketDataError(
                f"synthetic history holds {_MASTER_BARS} bars; asked for {days}."
            )
        return self._master_series(clean)[-days:]

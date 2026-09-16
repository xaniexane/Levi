"""Crypto market data for the LEVI finance domain — keyless and honest.

:class:`BinanceProvider` fetches daily klines from Binance's public,
keyless REST endpoint over stdlib ``urllib``. No API keys, no account,
no SDK. Any failure — network, HTTP error, bad JSON, empty klines —
raises :class:`MarketDataError`; prices are never fabricated.

Crypto symbols (``BTCUSDT``, ``ETHUSDT``, …) are validated as uppercase
alphanumerics; anything else is rejected before any request is made.

Stdlib-only: ``json``, ``re``, ``urllib``, ``datetime``.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

from levi.finance.market import Bar, MarketDataError, MarketDataProvider

__all__ = [
    "BinanceProvider",
    "CRYPTO_SYMBOL_RE",
    "CRYPTO_QUOTE_ASSETS",
    "looks_like_crypto",
]

#: Binance spot symbols: uppercase alphanumerics, e.g. BTCUSDT, ETHBTC.
CRYPTO_SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,20}$")

#: Common quote assets — used only for the CLI's "did you mean --source
#: binance?" hint, never for validation.
CRYPTO_QUOTE_ASSETS = ("USDT", "USDC", "BTC", "ETH", "BNB", "USD", "EUR")


def looks_like_crypto(symbol: object) -> bool:
    """Heuristic: does ``symbol`` look like a crypto pair?

    Used for helpful CLI hints only — never for validation or routing.
    """
    if not isinstance(symbol, str):
        return False
    text = symbol.strip().upper()
    return text.endswith(CRYPTO_QUOTE_ASSETS) and bool(CRYPTO_SYMBOL_RE.match(text))


_KLINES_URL = (
    "https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit={limit}"
)
_MAX_KLINES = 1000  # Binance's per-request cap for klines


class BinanceProvider(MarketDataProvider):
    """Keyless daily-bar provider backed by Binance public klines.

    The raw HTTP fetch lives in :meth:`_download` alone — a small seam
    tests can monkeypatch so the suite never touches the network.
    """

    #: HTTP timeout in seconds.
    timeout: float = 15.0

    def _download(self, url: str) -> str:
        """Fetch a URL body as text. Raises ``MarketDataError`` on failure.

        The error message names the failure class but never echoes the
        URL or a traceback into callers.
        """
        request = urllib.request.Request(
            url, headers={"User-Agent": "levi-finance/1.0 (+local-only)"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                return resp.read().decode("utf-8")
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise MarketDataError(
                f"market data download failed ({type(exc).__name__})"
            ) from None

    @staticmethod
    def _parse_klines(text: str) -> list[Bar]:
        """Parse Binance klines JSON into bars.

        A kline row is ``[open_time_ms, open, high, low, close, volume,
        …]`` with prices as strings. Malformed rows are skipped; an
        all-malformed payload raises rather than returning silently
        empty.
        """
        try:
            rows = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            raise MarketDataError("unparseable klines response") from None
        if not isinstance(rows, list):
            raise MarketDataError("unexpected klines response shape")
        bars: list[Bar] = []
        for row in rows:
            try:
                if not isinstance(row, (list, tuple)) or len(row) < 6:
                    continue
                day = datetime.fromtimestamp(
                    int(row[0]) / 1000, tz=timezone.utc
                ).strftime("%Y-%m-%d")
                bars.append(
                    Bar(
                        date=day,
                        open=float(row[1]),
                        high=float(row[2]),
                        low=float(row[3]),
                        close=float(row[4]),
                        volume=float(row[5]),
                    )
                )
            except (ValueError, TypeError, OverflowError, OSError):
                continue
        if not bars:
            raise MarketDataError("no usable klines in market data response")
        return bars

    def daily_bars(self, symbol: str, days: int = 120) -> list[Bar]:
        """Fetch the last ``days`` daily klines for a crypto pair symbol.

        Raises ``MarketDataError`` for invalid symbols, impossible day
        counts, and any fetch/parse failure — never an empty list.
        """
        if not isinstance(symbol, str):
            raise MarketDataError(f"invalid symbol: {symbol!r}")
        clean = symbol.strip().upper()
        if not CRYPTO_SYMBOL_RE.match(clean):
            raise MarketDataError(f"invalid crypto symbol: {symbol!r}")
        if isinstance(days, bool) or not isinstance(days, int) or days < 1:
            raise MarketDataError(f"days must be a positive int, got {days!r}")
        if days > _MAX_KLINES:
            raise MarketDataError(
                f"binance serves at most {_MAX_KLINES} daily klines per "
                f"request; asked for {days}."
            )
        url = _KLINES_URL.format(symbol=clean, limit=days)
        return self._parse_klines(self._download(url))

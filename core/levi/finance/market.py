"""LEVI finance domain — market data providers.

Data + math layer for the finance domain. Stdlib-only by kernel rule
(blueprint §1.1): ``urllib``, ``csv``, ``dataclasses``, ``math``, ``re``,
``datetime``, ``abc`` — no pandas, no numpy, no requests, no SDKs.

This module defines the provider abstraction (``MarketDataProvider``) and
one keyless provider (``StooqProvider``) that fetches daily bars as CSV
over plain ``urllib``. Providers raise ``MarketDataError`` for missing or
unusable data — they never return silent empty results.

Nothing here executes trades or moves money; it is a data feed for the
paper-only signal/ledger layers. Live trading is structurally disabled
elsewhere in the package.
"""

from __future__ import annotations

import csv
import io
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, timedelta

__all__ = [
    "Bar",
    "MarketDataError",
    "MarketDataProvider",
    "StooqProvider",
    "PROVIDERS",
    "get_provider",
]


class MarketDataError(Exception):
    """Raised when market data is missing, invalid, or unusable.

    Providers raise this instead of returning empty results, so callers
    can never mistake "no data" for "zero data".
    """


@dataclass
class Bar:
    """One daily OHLCV bar."""

    date: str  # YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        try:
            year, month, day = (int(part) for part in self.date.split("-"))
            date(year, month, day)  # validates calendar correctness
        except (ValueError, AttributeError):
            raise ValueError(
                f"Bar.date must be YYYY-MM-DD, got {self.date!r}"
            ) from None
        for field in ("open", "high", "low", "close", "volume"):
            setattr(self, field, float(getattr(self, field)))


class MarketDataProvider(ABC):
    """Abstract market-data source."""

    @abstractmethod
    def daily_bars(self, symbol: str, days: int = 120) -> list[Bar]:
        """Return daily bars for ``symbol``, oldest first.

        Raises ``MarketDataError`` for missing/unusable data — never
        returns an empty list.
        """
        raise NotImplementedError


_SYMBOL_RE = re.compile(r"^[A-Za-z.\-]{1,12}$")
_STOOQ_URL = (
    "https://stooq.com/q/d/l/?s={symbol}.us"
    "&d1={d1}&d2={d2}&i=d"
)


class StooqProvider(MarketDataProvider):
    """Keyless daily-bar provider backed by Stooq's public CSV endpoint.

    The raw HTTP fetch lives in :meth:`_download` alone — a small seam
    tests can monkeypatch so the suite never touches the network.
    """

    #: HTTP timeout in seconds.
    timeout: float = 15.0

    def _download(self, url: str) -> str:
        """Fetch a URL body as text. Raises ``MarketDataError`` on failure.

        The error message is deliberately plain: it names the failure
        class but never echoes the URL or a traceback into callers.
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
    def _parse_csv(text: str) -> list[Bar]:
        """Parse Stooq daily CSV text into bars, skipping N/D rows."""
        rows = csv.reader(io.StringIO(text))
        header = next(rows, None)
        if header is None:
            raise MarketDataError("empty market data response")
        bars: list[Bar] = []
        for row in rows:
            if len(row) < 6:
                continue
            day, open_, high, low, close, volume = (
                cell.strip() for cell in row[:6]
            )
            if close.upper() == "N/D":
                # Stooq marks unavailable closes as N/D; skip, don't fake.
                continue
            try:
                bars.append(
                    Bar(
                        date=day,
                        open=float(open_),
                        high=float(high),
                        low=float(low),
                        close=float(close),
                        volume=float(volume),
                    )
                )
            except ValueError:
                # Malformed row: skip it; an all-malformed feed still
                # raises below rather than returning silently empty.
                continue
        if not bars:
            raise MarketDataError("no usable bars in market data response")
        return bars

    def daily_bars(self, symbol: str, days: int = 120) -> list[Bar]:
        """Fetch the last ``days`` daily bars for a US symbol."""
        if not isinstance(symbol, str) or not _SYMBOL_RE.match(symbol):
            raise MarketDataError(f"invalid symbol: {symbol!r}")
        if not isinstance(days, int) or days < 1:
            raise MarketDataError(f"days must be a positive int, got {days!r}")
        end = date.today()
        start = end - timedelta(days=days)
        url = _STOOQ_URL.format(
            symbol=symbol.lower(),
            d1=start.strftime("%Y%m%d"),
            d2=end.strftime("%Y%m%d"),
        )
        return self._parse_csv(self._download(url))


#: Registry of available providers; new sources plug in by adding an entry.
PROVIDERS: dict[str, type[MarketDataProvider]] = {
    "stooq": StooqProvider,
}


def get_provider(name: str = "stooq") -> MarketDataProvider:
    """Return an instance of the named provider.

    Raises ``MarketDataError`` for unknown names.
    """
    try:
        cls = PROVIDERS[name.lower()]
    except (KeyError, AttributeError):
        raise MarketDataError(
            f"unknown market data provider: {name!r}"
        ) from None
    return cls()

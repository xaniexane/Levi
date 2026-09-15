"""LEVI finance domain — paper-trading primitives (stdlib-only).

Kernel rule (blueprint §1.1): this package is stdlib-only — ``urllib``,
``csv``, ``dataclasses``, ``math``, ``re``, ``datetime``, ``abc``.
No pandas, no numpy, no network SDKs. Anything needing a real dependency
is a sign-off decision, not a silent import.

Modules:
    market:     provider abstraction (``MarketDataProvider``) + keyless
                Stooq daily-bar provider. Raises ``MarketDataError``
                for missing/unusable data — never silent empty results.
    indicators: pure-stdlib technical indicators (sma/ema/rsi/macd/
                bollinger/atr). ``None``-padded on insufficient data.
    signals:    advisory-only signal scoring engine. Deterministic rules
                over indicators; NO import path to any execution code —
                a Signal can describe but never act. ``narrate()`` is
                model-preferred with an offline-graceful fallback.
    portfolio:  cash + position ledger for paper trading. Live trading is
                structurally disabled — there is no broker wiring here.

Exports are lazy (PEP 562): importing this package never imports a
submodule, and a name resolves from its owning module on first access.
This keeps the package importable even while sibling modules are still
landing in a parallel build.
"""

from __future__ import annotations

_LAZY_EXPORTS = {
    # market.py — data feed
    "Bar": "market",
    "MarketDataError": "market",
    "MarketDataProvider": "market",
    "StooqProvider": "market",
    "PROVIDERS": "market",
    "get_provider": "market",
    # indicators.py — math layer
    "sma": "indicators",
    "ema": "indicators",
    "rsi": "indicators",
    "macd": "indicators",
    "bollinger": "indicators",
    "atr": "indicators",
    # signals.py — advisory scoring engine (sibling module; no execution path)
    "MIN_BARS": "signals",
    "MOMENTUM_EPS": "signals",
    "Signal": "signals",
    "score_bars": "signals",
    "generate_signal": "signals",
    "narrate": "signals",
    "fallback_narrative": "signals",
    # portfolio.py — paper ledger (sibling module)
    "DEFAULT_PATH": "portfolio",
    "Position": "portfolio",
    "Portfolio": "portfolio",
    "load": "portfolio",
}

__all__ = sorted(_LAZY_EXPORTS)


def __getattr__(name: str):
    if name in _LAZY_EXPORTS:
        import importlib

        module = importlib.import_module(
            f"levi.finance.{_LAZY_EXPORTS[name]}"
        )
        return getattr(module, name)
    raise AttributeError(f"module 'levi.finance' has no attribute {name!r}")


def __dir__():
    return sorted(list(globals().keys()) + __all__)

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
    # synth.py — seeded synthetic market data
    "SyntheticProvider": "synth",
    "SYNTH_SYMBOL_RE": "synth",
    "SYNTH_UNIVERSE": "synth",
    "is_synth_symbol": "synth",
    # crypto.py — keyless crypto market data
    "BinanceProvider": "crypto",
    "CRYPTO_SYMBOL_RE": "crypto",
    "CRYPTO_QUOTE_ASSETS": "crypto",
    "looks_like_crypto": "crypto",
    # wsb.py — WSB presentation skin
    "BANNED_DIGEST_COUNT": "wsb",
    "SlurDetected": "wsb",
    "assert_clean": "wsb",
    "dd_post": "wsb",
    "positions_or_ban": "wsb",
    "gain_loss_porn": "wsb",
    "hands_report": "wsb",
    "ticker_tape": "wsb",
    "wsb_quote": "wsb",
    "ADVISORY_FOOTER": "wsb",
    "PAPER_STAMP": "wsb",
    # bets.py — paper YOLO bet ledger
    "Bet": "bets",
    "BetLedger": "bets",
    "DEFAULT_BETS_PATH": "bets",
    "InvalidBet": "bets",
    "BetNotFound": "bets",
    "BetAlreadySettled": "bets",
    # leaderboard.py — paper-trader rankings
    "MIN_BETS_RANKED": "leaderboard",
    "build_leaderboard": "leaderboard",
    "ranked_leaderboard": "leaderboard",
    "render_leaderboard": "leaderboard",
    # copytrade.py — simulated copy trading
    "NoSettledBets": "copytrade",
    "mirror_report": "copytrade",
    "compare_traders": "copytrade",
    "render_copy_report": "copytrade",
    # brokerlink.py — draft-only broker-link option
    "BrokerLinkConfig": "brokerlink",
    "DraftOrder": "brokerlink",
    "LiveExecutionRefused": "brokerlink",
    "InvalidDraft": "brokerlink",
    "SUPPORTED_PLATFORMS": "brokerlink",
    "DEFAULT_LINK_PATH": "brokerlink",
    "DEFAULT_DRAFTS_PATH": "brokerlink",
    "configure_broker_link": "brokerlink",
    "broker_link_status": "brokerlink",
    "prepare_drafts": "brokerlink",
    "execute_draft": "brokerlink",
    "load_drafts": "brokerlink",
}

__all__ = sorted(_LAZY_EXPORTS)


def __getattr__(name: str):
    if name in _LAZY_EXPORTS:
        import importlib

        module = importlib.import_module(f"levi.finance.{_LAZY_EXPORTS[name]}")
        return getattr(module, name)
    raise AttributeError(f"module 'levi.finance' has no attribute {name!r}")


def __dir__():
    return sorted(list(globals().keys()) + __all__)

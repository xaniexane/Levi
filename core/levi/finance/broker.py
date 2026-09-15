"""Brokerage layer for the LEVI finance domain (blueprint §1, §1.5).

STDLIB-ONLY. This module imports nothing beyond the standard library.
There is intentionally no alpaca SDK (or any broker SDK) anywhere in the
kernel — see blueprint §1.1: a real broker dependency is a deliberate,
sign-off'd decision, never a silent import.

Two paths:

* ``PaperBroker`` (the default) — a plain class, NOT a plugin
  ``Connector``. It is not a third-party account; it moves no money and
  touches no network. Every ``Fill`` it returns carries
  ``simulated=True``, ``broker="paper"``, and ``str(fill)`` always
  contains the word "SIMULATED". A paper fill cannot be mistaken for a
  real one.

* ``AlpacaConnector`` — the honest connector contract for a real
  equities broker, reusing ``levi.plugins.registry.Connector``. Its
  transport is NOT wired: no SDK, no ``urllib`` call, nothing. Any
  attempt to use it without a wired transport surfaces the registry's
  honest ``transport_not_wired`` status — success is never simulated
  (blueprint §1.7 / "never simulate success").

WHAT ENABLING LIVE TRADING WOULD REQUIRE (structural checklist, none of
this is implemented here):

1. A deliberate dependency decision with sign-off (blueprint §1.1) to
   add a real broker transport — either stdlib ``urllib`` against the
   Alpaca REST API or an approved SDK — and a wired ``_call_api``
   implementation in ``AlpacaConnector``.
2. Credentials present: ``LEVI_ALPACA_KEY`` and ``LEVI_ALPACA_SECRET``
   both set (read from the environment, never logged, never printed,
   never written to disk).
3. The explicit opt-in flag: ``LEVI_BROKER_LIVE=1`` in the environment.
4. Per-order human confirmation, every time: ``PaperBroker.place_order``
   raises ``OrderNotConfirmed`` without ``confirm=True``, and the
   registry forces ``requires_confirmation=True`` on ``AlpacaConnector``
   with no per-feature override (blueprint §1.5).
5. ``get_broker("alpaca")`` returning a live instance only when all of
   the above hold; otherwise it raises ``LiveBrokerUnavailable`` naming
   exactly what is missing.

Until every item above is true, ``live_enabled()`` is ``False`` and the
only broker that exists is paper.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from levi.plugins.registry import (
    Capability,
    Connector,
    InvalidParams,
    Operation,
    Transport,
)

__all__ = [
    "Order",
    "Fill",
    "OrderNotConfirmed",
    "InvalidOrder",
    "NoReferencePrice",
    "LiveBrokerUnavailable",
    "PaperBroker",
    "AlpacaConnector",
    "live_enabled",
    "get_broker",
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class OrderNotConfirmed(Exception):
    """Raised when ``place_order`` is called without explicit human
    confirmation. Blueprint §1.5: consequential actions always need an
    explicit confirm step — never a default-yes."""


class InvalidOrder(Exception):
    """Raised when an order fails validation. Nothing was executed."""


class NoReferencePrice(Exception):
    """Raised when a paper order has no reference price. A price is never
    invented — the caller must supply one."""


class LiveBrokerUnavailable(Exception):
    """Raised when the live broker path is requested but not enabled."""


# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_qty(qty: Any) -> float:
    try:
        value = float(qty)
    except (TypeError, ValueError):
        raise InvalidOrder(
            f"invalid qty {qty!r}: expected a number greater than 0 — "
            "nothing was executed."
        ) from None
    if not math.isfinite(value) or value <= 0:
        raise InvalidOrder(
            f"invalid qty {qty!r}: expected a number greater than 0 — "
            "nothing was executed."
        )
    return value


def _validate_side(side: Any) -> str:
    text = str(side or "").strip().lower()
    if text not in ("buy", "sell"):
        raise InvalidOrder(
            f"invalid side {side!r}: expected 'buy' or 'sell' — "
            "nothing was executed."
        )
    return text


def _validate_symbol(symbol: Any) -> str:
    text = str(symbol or "").strip().upper()
    if not text:
        raise InvalidOrder(
            f"invalid symbol {symbol!r}: expected a non-empty symbol — "
            "nothing was executed."
        )
    return text


@dataclass
class Order:
    """A request to trade. Construction validates; an invalid order can
    never exist, let alone be "executed"."""

    symbol: str
    qty: float
    side: str  # "buy" | "sell"
    order_type: str = "market"  # "market" only for now
    created_at: str = field(default_factory=_now_iso)

    def __post_init__(self) -> None:
        self.symbol = _validate_symbol(self.symbol)
        self.qty = _validate_qty(self.qty)
        self.side = _validate_side(self.side)
        if self.order_type != "market":
            raise InvalidOrder(
                f"invalid order_type {self.order_type!r}: only 'market' "
                "orders are supported — nothing was executed."
            )


@dataclass
class Fill:
    """The outcome of an order. ``simulated=True`` marks a paper fill;
    ``simulated=False`` marks a fill that came back from a real broker
    transport. ``str(fill)`` always labels which it is."""

    symbol: str
    qty: float
    side: str
    order_type: str
    created_at: str
    fill_price: float
    filled_at: str
    simulated: bool
    broker: str

    def __str__(self) -> str:
        label = "SIMULATED" if self.simulated else "REAL"
        return (
            f"[{label}] {self.broker} {self.side} {self.qty:g} "
            f"{self.symbol} @ {self.fill_price:g} ({self.order_type}, "
            f"filled {self.filled_at})"
        )


# ---------------------------------------------------------------------------
# Paper broker (default) — plain class, not a plugin Connector
# ---------------------------------------------------------------------------


class PaperBroker:
    """Paper trading broker.

    Deliberately NOT a ``levi.plugins.registry.Connector``: it is not a
    third-party account, it holds no credentials, it moves no money, and
    it touches no network. Fills are computed deterministically from the
    caller-supplied reference price and are unmistakably labeled as
    simulated.
    """

    id = "paper"

    def place_order(
        self,
        order: Order,
        *,
        confirm: bool = False,
        reference_price: float | None = None,
    ) -> Fill:
        """Fill ``order`` against the paper book.

        * No ``confirm=True`` → ``OrderNotConfirmed`` (HITL gate,
          blueprint §1.5).
        * Bad qty/side → ``InvalidOrder`` (nothing "executed").
        * No ``reference_price`` → ``NoReferencePrice``. A price is never
          invented.
        """
        if not confirm:
            raise OrderNotConfirmed(
                "order was NOT placed: explicit confirmation is required "
                "for every order (pass confirm=True) — nothing was "
                "executed."
            )
        if not isinstance(order, Order):
            raise InvalidOrder(
                f"invalid order {order!r}: expected an Order — nothing "
                "was executed."
            )
        # Re-validate defensively: Order.__post_init__ already guarantees
        # these, but a fill must never be built from unchecked values.
        symbol = _validate_symbol(order.symbol)
        qty = _validate_qty(order.qty)
        side = _validate_side(order.side)
        if order.order_type != "market":
            raise InvalidOrder(
                f"invalid order_type {order.order_type!r}: only 'market' "
                "orders are supported — nothing was executed."
            )
        if reference_price is None:
            raise NoReferencePrice(
                "no reference price supplied: a fill price is never "
                "invented — pass reference_price=<price> to price this "
                "paper fill. Nothing was executed."
            )
        try:
            price = float(reference_price)
        except (TypeError, ValueError):
            raise NoReferencePrice(
                f"invalid reference_price {reference_price!r}: supply a "
                "positive number as reference_price. Nothing was "
                "executed."
            ) from None
        if not math.isfinite(price) or price <= 0:
            raise NoReferencePrice(
                f"invalid reference_price {reference_price!r}: supply a "
                "positive number as reference_price. Nothing was "
                "executed."
            )
        return Fill(
            symbol=symbol,
            qty=qty,
            side=side,
            order_type=order.order_type,
            created_at=order.created_at,
            fill_price=price,
            filled_at=_now_iso(),
            simulated=True,
            broker="paper",
        )


# ---------------------------------------------------------------------------
# Alpaca connector — honest, unwired
# ---------------------------------------------------------------------------


#: Env vars for the Alpaca live path. Both are required before
#: ``live_enabled()`` can be true; both are read from the environment and
#: neither is ever logged, printed, or written to disk.
ALPACA_KEY_ENV = "LEVI_ALPACA_KEY"
ALPACA_SECRET_ENV = "LEVI_ALPACA_SECRET"
BROKER_LIVE_FLAG = "LEVI_BROKER_LIVE"


class AlpacaConnector(Connector):
    """Alpaca brokerage connector — declared but NOT wired.

    Auth: ``LEVI_ALPACA_KEY`` and ``LEVI_ALPACA_SECRET``, read ONLY from
    the environment. A real deployment needs BOTH; the key alone is not
    enough. Neither value is ever logged, printed, or written to disk.

    The transport is intentionally unwired: the base class's
    ``_call_api`` raises ``TransportNotWired``, which ``execute()``
    converts to an honest ``transport_not_wired`` result. Wiring it would
    require the dependency decision, the live flag, and per-order
    confirmation documented in this module's docstring.
    """

    id = "alpaca"
    display_name = "Alpaca (equities broker)"
    credential_env_var = ALPACA_KEY_ENV
    #: The second credential a real deployment needs. Declared and read
    #: here, never logged or printed.
    credential_secret_env_var = ALPACA_SECRET_ENV

    capabilities = (
        Capability("read.quote", "Read the latest quote for a symbol"),
        Capability(
            "write.place_order",
            "Place a market order on the Alpaca account",
            write=True,
        ),
    )

    operations = (
        Operation(
            "quote", "Return the latest quote for symbol", params=("symbol",)
        ),
        Operation(
            "place_order",
            "Place a market order for symbol/qty/side",
            write=True,
            params=("symbol", "qty", "side"),
        ),
    )

    # requires_confirmation is forced to True by the registry's
    # __init_subclass__ because this connector exposes a write
    # capability — no per-feature override, no exceptions. Stated
    # explicitly here so the rule is visible at the call site that needs
    # it most.
    requires_confirmation = True

    # -- credential handling ----------------------------------------------

    def credential(self) -> str | None:
        """Both ``LEVI_ALPACA_KEY`` and ``LEVI_ALPACA_SECRET`` must be
        present and non-blank. Returns the key for the transport to use;
        never logs or prints either value."""
        key = os.environ.get(ALPACA_KEY_ENV, "").strip()
        secret = os.environ.get(ALPACA_SECRET_ENV, "").strip()
        if not key or not secret:
            return None
        return key

    def missing_credential_message(self) -> str:
        # Names the env vars the caller must set, never their values.
        return (
            f"missing credential: set {ALPACA_KEY_ENV} and "
            f"{ALPACA_SECRET_ENV} — nothing was sent."
        )

    # -- operations --------------------------------------------------------

    def perform(
        self,
        operation: str,
        params: dict[str, Any],
        token: str,
        transport: Transport | None,
    ) -> Any:
        missing = [
            name
            for name in next(
                o for o in self.operations if o.name == operation
            ).params
            if not str(params.get(name, "")).strip()
        ]
        if missing:
            raise InvalidParams(
                f"missing required params for {operation!r}: "
                f"{', '.join(missing)} — nothing was sent."
            )

        if operation == "quote":
            symbol = _validate_symbol(params["symbol"])
            return self._request(
                "GET",
                f"/v2/stocks/{symbol}/quotes/latest",
                token,
                None,
                transport,
            )

        if operation == "place_order":
            symbol = _validate_symbol(params["symbol"])
            qty = _validate_qty(params["qty"])
            side = _validate_side(params["side"])
            body = {
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "type": "market",
                "time_in_force": "day",
            }
            return self._request(
                "POST", "/v2/orders", token, body, transport
            )

        # Unreachable via execute() (unknown ops are rejected there), but
        # stay honest rather than returning a fabricated payload.
        raise InvalidParams(
            f"operation {operation!r} has no implementation — "
            "nothing was sent."
        )

    def _request(
        self,
        method: str,
        path: str,
        token: str,
        body: Any,
        transport: Transport | None,
    ) -> Any:
        if transport is not None:
            return transport(method, path, token, body)
        # No transport wired in the kernel: the base implementation
        # raises TransportNotWired, which execute() reports honestly.
        return self._call_api(method, path, token, body)


# Deliberately NOT registered in the connector registry: the live path is
# structurally gated by live_enabled() / get_broker("alpaca"), so the
# connector only exists when the deployment has opted in explicitly.


# ---------------------------------------------------------------------------
# Live gate + factory
# ---------------------------------------------------------------------------


def live_enabled() -> bool:
    """True ONLY when the operator has explicitly enabled live trading:

    * ``LEVI_BROKER_LIVE=1`` is set, AND
    * ``LEVI_ALPACA_KEY`` is set and non-blank, AND
    * ``LEVI_ALPACA_SECRET`` is set and non-blank.

    Anything else → False. No partial enablement, no fallback.
    """
    if os.environ.get(BROKER_LIVE_FLAG) != "1":
        return False
    key = os.environ.get(ALPACA_KEY_ENV, "").strip()
    secret = os.environ.get(ALPACA_SECRET_ENV, "").strip()
    return bool(key and secret)


def get_broker(name: str = "paper") -> PaperBroker | AlpacaConnector:
    """Return a broker by name.

    ``"paper"`` → ``PaperBroker`` (always available, simulated fills).
    ``"alpaca"`` → ``AlpacaConnector`` ONLY if ``live_enabled()``;
    otherwise raises ``LiveBrokerUnavailable`` naming exactly what is
    missing.
    """
    key = str(name or "").strip().lower()
    if key == "paper":
        return PaperBroker()
    if key == "alpaca":
        missing: list[str] = []
        if os.environ.get(BROKER_LIVE_FLAG) != "1":
            missing.append(
                f"{BROKER_LIVE_FLAG}=1 (explicit live-trading opt-in flag)"
            )
        if not os.environ.get(ALPACA_KEY_ENV, "").strip():
            missing.append(f"{ALPACA_KEY_ENV} (Alpaca API key)")
        if not os.environ.get(ALPACA_SECRET_ENV, "").strip():
            missing.append(f"{ALPACA_SECRET_ENV} (Alpaca API secret)")
        if missing:
            raise LiveBrokerUnavailable(
                "live broker 'alpaca' is unavailable — missing: "
                + "; ".join(missing)
                + ". Set all of these to enable live trading. "
                "Nothing was sent and nothing was traded."
            )
        return AlpacaConnector()
    raise ValueError(
        f"unknown broker {name!r}: expected 'paper' or 'alpaca'."
    )

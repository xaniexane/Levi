"""Carrier billing — the carrier as payment processor and revenue partner.

Studied from: dead-networks-20260916, report.md [Bildschirmtext / BTX
(Germany)] — BTX, where whole pages were transferred with per-received-
page billing settled by the Bundespost: the carrier acting as payment
processor, revenue-share partner, and terminal monopoly.

This module models that pattern: ``Subscriber`` records are bound to a
single registered ``Terminal`` (the monopoly); every page delivered is
billed at receipt; the ``Carrier`` keeps a declared revenue share and
passes the rest to the ``ContentProvider``. Billing is integer minor
units on a local ledger — no real payments, no network.

Honesty: toy accounting. No fraud detection, no chargebacks, no
interconnect disputes; the terminal monopoly is modeled as a
one-terminal-per-subscriber constraint, which is the historical shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/carrier-billing"


@dataclass(frozen=True)
class Terminal:
    """A carrier-issued terminal: exactly one per subscriber."""

    terminal_id: str


@dataclass
class Subscriber:
    """A billed party bound to one registered terminal."""

    subscriber_id: str
    terminal: Terminal
    balance_units: int = 0  # amount billed, awaiting settlement


@dataclass(frozen=True)
class ContentProvider:
    """An information provider paid through the carrier."""

    provider_id: str
    name: str


@dataclass(frozen=True)
class PageReceipt:
    """Proof a page was received by a terminal: the billable event."""

    page_id: str
    provider_id: str
    price_units: int
    subscriber_id: str

    def __post_init__(self) -> None:
        if self.price_units < 0:
            raise ValueError("price_units must be >= 0")


class Carrier:
    """The carrier: bills per received page, keeps a declared share."""

    def __init__(self, revenue_share: float = 0.30) -> None:
        if not 0.0 <= revenue_share < 1.0:
            raise ValueError("revenue_share must be in [0, 1)")
        self.revenue_share = revenue_share
        self.subscribers: Dict[str, Subscriber] = {}
        self.providers: Dict[str, ContentProvider] = {}
        self.receipts: List[PageReceipt] = []
        self.carrier_ledger_units: int = 0
        self.provider_ledger: Dict[str, int] = {}

    def register_subscriber(self, subscriber: Subscriber) -> None:
        if subscriber.subscriber_id in self.subscribers:
            raise ValueError(f"duplicate subscriber {subscriber.subscriber_id!r}")
        used = {s.terminal.terminal_id for s in self.subscribers.values()}
        if subscriber.terminal.terminal_id in used:
            raise ValueError("terminal already registered to another subscriber")
        self.subscribers[subscriber.subscriber_id] = subscriber

    def register_provider(self, provider: ContentProvider) -> None:
        if provider.provider_id in self.providers:
            raise ValueError(f"duplicate provider {provider.provider_id!r}")
        self.providers[provider.provider_id] = provider

    def deliver_page(
        self, page_id: str, price_units: int, provider_id: str, subscriber_id: str
    ) -> PageReceipt:
        """Deliver a whole page and bill it at receipt."""
        if price_units < 0:
            raise ValueError("price_units must be >= 0")
        if provider_id not in self.providers:
            raise ValueError(f"unknown provider {provider_id!r}")
        subscriber = self.subscribers.get(subscriber_id)
        if subscriber is None:
            raise ValueError(f"unknown subscriber {subscriber_id!r}")
        receipt = PageReceipt(page_id, provider_id, price_units, subscriber_id)
        self.receipts.append(receipt)
        subscriber.balance_units += price_units
        carrier_cut = int(round(price_units * self.revenue_share))
        self.carrier_ledger_units += carrier_cut
        self.provider_ledger[provider_id] = self.provider_ledger.get(provider_id, 0) + (
            price_units - carrier_cut
        )
        return receipt

    def settle_provider(self, provider_id: str) -> int:
        """Pay out a provider's accumulated share; returns units paid."""
        amount = self.provider_ledger.get(provider_id, 0)
        self.provider_ledger[provider_id] = 0
        return amount

    def statement(self, subscriber_id: str) -> Dict[str, object]:
        """A subscriber's bill: line items plus total."""
        sub = self.subscribers.get(subscriber_id)
        if sub is None:
            raise ValueError(f"unknown subscriber {subscriber_id!r}")
        items: List[Tuple[str, int]] = [
            (r.page_id, r.price_units)
            for r in self.receipts
            if r.subscriber_id == subscriber_id
        ]
        return {
            "subscriber_id": subscriber_id,
            "terminal_id": sub.terminal.terminal_id,
            "items": items,
            "total_units": sub.balance_units,
        }

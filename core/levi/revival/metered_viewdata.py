"""Metered viewdata — per-page billing settled to information providers.

Studied from: dead-networks-20260916, report.md [Prestel (UK)] — Prestel,
the interactive two-way viewdata system with per-session billing built
into the network: pages are metered and revenue is settled out to the
information providers who published them.

This module models that pattern as a local accounting mechanism:
a ``Session`` visits ``Page`` records owned by ``InformationProvider``
records; every visit is metered (page id, duration seconds, price tier);
``Gateway.settle(session)`` turns the metered visits into a
``Settlement``: what the subscriber owes, what each provider earns after
the network's carriage cut, and a per-provider breakdown. Prices are
integer minor units; nothing here touches money or networks.

Honesty: toy ledger arithmetic, not a billing system — no proration
disputes, no credit, no real settlement rails. The pattern preserved is
the honest-metering split: the subscriber pays for what they read, the
provider is paid for what was read, the network takes a declared cut.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

ORIGIN = "levi-revival/metered-viewdata"


@dataclass(frozen=True)
class InformationProvider:
    """A publisher whose pages can be metered."""

    provider_id: str
    name: str


@dataclass(frozen=True)
class Page:
    """One viewdata page: owner, price tier in minor units per visit."""

    page_id: str
    provider_id: str
    price_units: int = 0  # 0 == free frame

    def __post_init__(self) -> None:
        if self.price_units < 0:
            raise ValueError("price_units must be >= 0")


@dataclass
class Visit:
    """One metered page view inside a session."""

    page_id: str
    duration_s: float


@dataclass
class Settlement:
    """Result of settling one session: who owes what."""

    session_id: str
    subscriber_charge: int
    network_cut: int
    provider_payouts: Dict[str, int]  # provider_id -> units


class Session:
    """A subscriber's viewdata session: records metered page visits."""

    def __init__(self, session_id: str, subscriber_id: str) -> None:
        self.session_id = session_id
        self.subscriber_id = subscriber_id
        self.visits: List[Visit] = []

    def visit(self, page: Page, duration_s: float = 0.0) -> None:
        """Record a metered visit to a page."""
        if duration_s < 0:
            raise ValueError("duration_s must be >= 0")
        self.visits.append(Visit(page.page_id, duration_s))


class Gateway:
    """The network: holds the page registry and settles sessions."""

    def __init__(self, network_cut_rate: float = 0.10) -> None:
        if not 0.0 <= network_cut_rate < 1.0:
            raise ValueError("network_cut_rate must be in [0, 1)")
        self.network_cut_rate = network_cut_rate
        self.providers: Dict[str, InformationProvider] = {}
        self.pages: Dict[str, Page] = {}
        self.settlements: List[Settlement] = []

    def register_provider(self, provider: InformationProvider) -> None:
        if provider.provider_id in self.providers:
            raise ValueError(f"duplicate provider {provider.provider_id!r}")
        self.providers[provider.provider_id] = provider

    def publish_page(self, page: Page) -> None:
        if page.page_id in self.pages:
            raise ValueError(f"duplicate page {page.page_id!r}")
        if page.provider_id not in self.providers:
            raise ValueError(f"unknown provider {page.provider_id!r}")
        self.pages[page.page_id] = page

    def settle(self, session: Session) -> Settlement:
        """Meter the session and settle revenue to providers."""
        payouts: Dict[str, int] = {}
        gross = 0
        for visit in session.visits:
            page = self.pages.get(visit.page_id)
            if page is None:
                raise ValueError(f"unregistered page {visit.page_id!r}")
            gross += page.price_units
            if page.price_units:
                payouts[page.provider_id] = (
                    payouts.get(page.provider_id, 0) + page.price_units
                )
        network_cut = int(round(gross * self.network_cut_rate))
        # Payouts come out of the provider pool (gross minus network cut).
        pool = gross - network_cut
        scaled: Dict[str, int] = {}
        if payouts and gross:
            for pid, amt in payouts.items():
                scaled[pid] = int(round(amt * pool / gross))
            # Fix rounding drift so totals balance.
            drift = pool - sum(scaled.values())
            if drift:
                first = next(iter(scaled))
                scaled[first] += drift
        settlement = Settlement(
            session_id=session.session_id,
            subscriber_charge=gross,
            network_cut=network_cut,
            provider_payouts=scaled,
        )
        self.settlements.append(settlement)
        return settlement

    def provider_ledger(self, provider_id: str) -> Dict[str, int]:
        """Total earned by one provider across all settled sessions."""
        total = sum(s.provider_payouts.get(provider_id, 0) for s in self.settlements)
        sessions = sum(1 for s in self.settlements if provider_id in s.provider_payouts)
        return {
            "provider_id": provider_id,
            "total_units": total,
            "settlements": sessions,
        }

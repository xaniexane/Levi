"""Apogee episode model — the honest free slice funds the rest.

Studied from: honest-markets-20260916, findings.jsonl
[arch-honest-shareware-apogee-model] — the Apogee shareware episode
model: episode 1 free and freely redistributable by anyone, paid
episodes 2 and 3 by mail order; the fans' own distribution labor became
the trial channel.

This module models that pattern: a ``Series`` of ``Episode`` records
where episode 1 is the free slice (anyone may ``redistribute`` it);
later episodes are sold via ``MailOrder`` records; every redistribution
is logged so the trial channel is visible as real counts. Integer minor
units on a local ledger — no payments, no mail.

Honesty: the model tracks orders and redistribution counts; it does not
fulfill anything, prevent copying, or verify addresses. The preserved
pattern is the economics of trust: give away the honest slice, let the
audience do the marketing, charge for the rest.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

ORIGIN = "levi-revival/apogee-model"


@dataclass(frozen=True)
class Episode:
    """One episode: free slice or paid installment."""

    number: int
    title: str
    free: bool = False
    price_units: int = 0

    def __post_init__(self) -> None:
        if self.number < 1:
            raise ValueError("episode number must be >= 1")
        if self.free and self.price_units != 0:
            raise ValueError("a free episode must cost 0")
        if not self.free and self.price_units <= 0:
            raise ValueError("a paid episode must have a price > 0")


@dataclass(frozen=True)
class MailOrder:
    """A mail-order purchase of a paid episode."""

    order_id: str
    episode_number: int
    buyer: str
    price_units: int


@dataclass(frozen=True)
class Redistribution:
    """One fan redistribution of the free slice."""

    episode_number: int
    distributor: str


class Series:
    """A game series sold on the episode model."""

    def __init__(self, name: str) -> None:
        if not name.strip():
            raise ValueError("series name must not be empty")
        self.name = name
        self.episodes: Dict[int, Episode] = {}
        self.orders: List[MailOrder] = []
        self.redistributions: List[Redistribution] = []
        self._order_seq = 0

    def add_episode(self, episode: Episode) -> None:
        if episode.number in self.episodes:
            raise ValueError(f"duplicate episode {episode.number}")
        self.episodes[episode.number] = episode

    def free_slice(self) -> Episode:
        """The honest free slice: episode 1, freely redistributable."""
        episode = self.episodes.get(1)
        if episode is None or not episode.free:
            raise ValueError("series has no free episode 1")
        return episode

    def redistribute(self, distributor: str, episode_number: int = 1) -> Redistribution:
        """Log a fan redistribution; only the free slice may be shared."""
        episode = self.episodes.get(episode_number)
        if episode is None:
            raise ValueError(f"unknown episode {episode_number}")
        if not episode.free:
            raise ValueError(f"episode {episode_number} is not freely redistributable")
        event = Redistribution(episode_number, distributor)
        self.redistributions.append(event)
        return event

    def order(self, episode_number: int, buyer: str) -> MailOrder:
        """Place a mail order for a paid episode."""
        episode = self.episodes.get(episode_number)
        if episode is None:
            raise ValueError(f"unknown episode {episode_number}")
        if episode.free:
            raise ValueError("the free slice needs no order")
        self._order_seq += 1
        mail_order = MailOrder(
            order_id=f"{self.name}-order-{self._order_seq:04d}",
            episode_number=episode_number,
            buyer=buyer,
            price_units=episode.price_units,
        )
        self.orders.append(mail_order)
        return mail_order

    def funnel(self) -> Dict[str, object]:
        """Trial-channel stats: redistributions vs paid orders."""
        paid_units = sum(o.price_units for o in self.orders)
        per_episode: Dict[int, int] = {}
        for order in self.orders:
            per_episode[order.episode_number] = (
                per_episode.get(order.episode_number, 0) + 1
            )
        return {
            "series": self.name,
            "redistributions": len(self.redistributions),
            "distributors": len({r.distributor for r in self.redistributions}),
            "orders": len(self.orders),
            "orders_per_episode": per_episode,
            "revenue_units": paid_units,
        }

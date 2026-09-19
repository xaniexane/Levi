"""Self-publishing game channel: cheap tools, peer review, tiny price points.

Studied from: dead-game-genres-2026-09-16/report.md [Entries - Xbox Live
Indie Games (XNA)] (the channel's shape: a flat yearly creator fee, cheap
tools, community peer review standing in for formal certification, and
rock-bottom price points that let hobbyists sell real games).

This is an original, from-scratch implementation for LEVI. A ``Channel``
runs the whole loop: creators pay the yearly fee to join, submit ``Game``
builds, and each submission enters a ``PeerReview`` queue where other
creators rate it on content-safety, playability, and honesty-of-description.
A game ships when it collects enough passing reviews; it is rejected when
rejections outnumber passes. Shipped games list in the ``Storefront`` at
their chosen price point, players buy them and leave star ratings, and the
channel pays creators their revenue share. Fees, splits, and thresholds are
constructor parameters, not hardcoded lore.

Honest limits: "players" are simulated purchase/rate events rather than real
accounts; review scores are recorded as given (no fraud detection); there is
no real money movement - revenue is ledgered, not settled.

Public surface:
- ``Channel(yearly_fee, revenue_share, price_points)``.
- ``register_creator(name)`` / ``submit(title, creator, price, blurb)`` -> game id.
- ``review(game_id, reviewer, verdict, notes)`` -> review state.
- ``buy(game_id)`` / ``rate(game_id, stars)``.
- ``storefront()`` / ``payout(creator)`` / ``channel_report()``.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

ORIGIN = "levi-revival/indie-channel"

PASS, REJECT, NEEDS_WORK = "pass", "reject", "needs_work"
DEFAULT_PRICE_POINTS = (1, 3, 5, 10)


@dataclass
class Review:
    reviewer: str
    verdict: str  # pass | reject | needs_work
    notes: str = ""


@dataclass
class Game:
    id: int
    title: str
    creator: str
    price: int
    blurb: str
    status: str = "in_review"  # in_review | shipped | rejected
    reviews: List[Review] = field(default_factory=list)
    sales: int = 0
    ratings: List[int] = field(default_factory=list)

    @property
    def avg_rating(self) -> Optional[float]:
        if not self.ratings:
            return None
        return round(sum(self.ratings) / len(self.ratings), 2)


@dataclass
class Channel:
    yearly_fee: int = 99
    revenue_share: float = 0.70  # creator keeps 70%
    price_points: tuple = DEFAULT_PRICE_POINTS
    reviews_to_ship: int = 3
    rejects_to_kill: int = 2

    def __post_init__(self) -> None:
        self.creators: Dict[str, Dict[str, object]] = {}
        self.games: Dict[int, Game] = {}
        self._next_id = 1
        self.fees_collected = 0

    # -- creators -------------------------------------------------------------------
    def register_creator(self, name: str) -> str:
        if name in self.creators:
            return f"{name} is already registered."
        self.creators[name] = {"fee_paid": self.yearly_fee, "earned": 0.0}
        self.fees_collected += self.yearly_fee
        return f"{name} joined the channel (${self.yearly_fee}/yr)."

    # -- submission -------------------------------------------------------------------
    def submit(self, title: str, creator: str, price: int, blurb: str = "") -> int:
        if creator not in self.creators:
            raise ValueError(f"{creator!r} is not a registered creator")
        if price not in self.price_points:
            raise ValueError(f"price must be one of {self.price_points}")
        gid = self._next_id
        self._next_id += 1
        self.games[gid] = Game(
            id=gid, title=title, creator=creator, price=price, blurb=blurb
        )
        return gid

    # -- peer review (instead of certification) ------------------------------------------
    def review(self, game_id: int, reviewer: str, verdict: str, notes: str = "") -> str:
        game = self._game(game_id)
        if game.status != "in_review":
            return f"'{game.title}' is already {game.status}."
        if reviewer == game.creator:
            return "Creators cannot review their own game."
        if reviewer not in self.creators:
            return f"{reviewer!r} is not a registered creator."
        if verdict not in (PASS, REJECT, NEEDS_WORK):
            raise ValueError(f"verdict must be pass/reject/needs_work, got {verdict!r}")
        if any(r.reviewer == reviewer for r in game.reviews):
            return f"{reviewer} already reviewed '{game.title}'."
        game.reviews.append(Review(reviewer, verdict, notes))
        passes = sum(1 for r in game.reviews if r.verdict == PASS)
        rejects = sum(1 for r in game.reviews if r.verdict == REJECT)
        if rejects >= self.rejects_to_kill:
            game.status = "rejected"
            return f"'{game.title}' rejected by peer review ({rejects} rejects)."
        if passes >= self.reviews_to_ship:
            game.status = "shipped"
            return f"'{game.title}' passes peer review and ships at ${game.price}!"
        return (
            f"Review recorded ({passes}/{self.reviews_to_ship} passes, "
            f"{rejects} rejects). Still in review."
        )

    # -- storefront -----------------------------------------------------------------------
    def storefront(self) -> List[Game]:
        return [g for g in self.games.values() if g.status == "shipped"]

    def buy(self, game_id: int) -> str:
        game = self._game(game_id)
        if game.status != "shipped":
            return f"'{game.title}' is not for sale ({game.status})."
        game.sales += 1
        earned = game.price * self.revenue_share
        self.creators[game.creator]["earned"] = (
            float(self.creators[game.creator]["earned"]) + earned
        )
        return f"Sold '{game.title}' for ${game.price} ({game.creator} earned ${earned:.2f})."

    def rate(self, game_id: int, stars: int) -> str:
        game = self._game(game_id)
        if game.status != "shipped":
            return "Only shipped games can be rated."
        if not 1 <= stars <= 5:
            raise ValueError("stars must be 1-5")
        game.ratings.append(stars)
        return f"Rated '{game.title}' {stars}/5 (avg {game.avg_rating})."

    # -- money ------------------------------------------------------------------------------
    def payout(self, creator: str) -> float:
        if creator not in self.creators:
            raise ValueError(f"unknown creator {creator!r}")
        earned = float(self.creators[creator]["earned"])
        self.creators[creator]["earned"] = 0.0
        return round(earned, 2)

    def channel_report(self) -> Dict[str, object]:
        shipped = self.storefront()
        return {
            "creators": len(self.creators),
            "fees_collected": self.fees_collected,
            "games_submitted": len(self.games),
            "games_shipped": len(shipped),
            "games_rejected": sum(
                1 for g in self.games.values() if g.status == "rejected"
            ),
            "total_sales": sum(g.sales for g in shipped),
            "top_rated": sorted(
                [g for g in shipped if g.avg_rating is not None],
                key=lambda g: g.avg_rating or 0,
                reverse=True,
            )[:3],
        }

    def _game(self, game_id: int) -> Game:
        if game_id not in self.games:
            raise ValueError(f"no game #{game_id}")
        return self.games[game_id]

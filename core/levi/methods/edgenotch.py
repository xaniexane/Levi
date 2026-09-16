"""Edge-notched (McBee) cards: needle-sort boolean retrieval.

History: mid-20th-century mechanical databases — index cards with holes
punched around the edges, each hole position encoding a feature. Stack the
deck, push needle-rods through the holes for your terms, shake: cards with
those positions *notched out* fall. Multiple needles = Boolean AND; pooled
selections = OR. Zatocoding compressed many features into overlapping hole
combinations at the price of occasional false drops. Died of capacity limits
and the labor of notching; computers absorbed it by ~1980.

In LEVI: the *logic* as a tagging discipline — no folders, only feature
tags; every query is a Boolean combination executed at search time.
:class:`Deck` maps each feature to a hole position; a card's notches are a
bitmask, and a query is a needle pass. Shared hole positions (Zatocoding)
are allowed but honestly flagged: they may produce false drops, and the
deck tells you so.

Honesty: USEFUL PATTERN — post-coordinate retrieval without the knitting
needles; LEVI does the notching (tagging) and the shaking (intersection).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Card:
    item_id: str
    title: str = ""
    notches: int = 0  # bitmask: bit p set = hole position p notched out

    def validate(self) -> None:
        if not self.item_id or not self.item_id.strip():
            raise ValueError("item_id must be non-empty")


class Deck:
    """A needle-sortable deck: features -> hole positions -> bitmasks."""

    MAX_POSITIONS = 64  # one bitmask word; more features than this = get a bigger deck

    def __init__(self):
        self.features: dict[str, int] = {}  # feature -> hole position
        self.cards: dict[str, Card] = {}
        self.shared: dict[
            int, list[str]
        ] = {}  # position -> features sharing it (zatocoding)

    # ---- notching --------------------------------------------------------
    def register_feature(self, feature: str, share_with: str | None = None) -> int:
        """Assign a hole position to a feature. ``share_with`` reuses another
        feature's position (Zatocoding compression) — flagged as possibly
        producing false drops."""
        feature = feature.strip()
        if not feature:
            raise ValueError("feature must be non-empty")
        if feature in self.features:
            return self.features[feature]
        if share_with is not None:
            if share_with not in self.features:
                raise KeyError(f"cannot share with unknown feature {share_with!r}")
            pos = self.features[share_with]
            self.features[feature] = pos
            sharers = self.shared.setdefault(pos, [])
            for f in (share_with, feature):
                if f not in sharers:
                    sharers.append(f)
            return pos
        if len({p for p in self.features.values()}) >= self.MAX_POSITIONS:
            raise OverflowError("deck is full: no free hole positions")
        used = set(self.features.values())
        pos = next(p for p in range(self.MAX_POSITIONS) if p not in used)
        self.features[feature] = pos
        return pos

    def add_card(
        self, item_id: str, title: str = "", features: list[str] | None = None
    ) -> Card:
        card = Card(item_id.strip(), title)
        card.validate()
        if card.item_id in self.cards:
            raise ValueError(f"card {card.item_id!r} already in deck")
        for feat in features or []:
            pos = self.register_feature(feat)
            card.notches |= 1 << pos
        self.cards[card.item_id] = card
        return card

    def notch(self, item_id: str, feature: str) -> None:
        """Notch an additional feature onto an existing card."""
        if item_id not in self.cards:
            raise KeyError(f"no card {item_id!r}")
        pos = self.register_feature(feature)
        self.cards[item_id].notches |= 1 << pos

    # ---- needle passes ---------------------------------------------------
    def _mask(self, features: list[str]) -> int:
        mask = 0
        for feat in features:
            if feat not in self.features:
                raise KeyError(f"feature {feat!r} was never notched into this deck")
            mask |= 1 << self.features[feat]
        return mask

    def query(self, features: list[str], op: str = "AND") -> list[Card]:
        """Push the needles through: AND = cards with all holes notched;
        OR = cards with any; NOT = cards with none of the given features."""
        if not features:
            raise ValueError("query needs at least one feature")
        op = op.upper()
        if op not in ("AND", "OR", "NOT"):
            raise ValueError("op must be AND, OR, or NOT")
        mask = self._mask(features)
        if op == "AND":
            hits = [c for c in self.cards.values() if c.notches & mask == mask]
        elif op == "OR":
            hits = [c for c in self.cards.values() if c.notches & mask]
        else:
            hits = [c for c in self.cards.values() if not (c.notches & mask)]
        return sorted(hits, key=lambda c: c.item_id)

    def may_false_drop(self, features: list[str]) -> list[str]:
        """Zatocoding honesty: which queried features share hole positions
        with other features (hits may include cards notched for the sharer)?"""
        flagged = []
        for feat in features:
            pos = self.features.get(feat)
            if pos is not None and pos in self.shared:
                sharers = [f for f in self.shared[pos] if f != feat]
                if sharers:
                    flagged.append(f"{feat!r} shares hole {pos} with {sharers}")
        return flagged

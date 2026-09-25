"""LEVI's honest piles: spatial triage with deterministic layout, no physics engine.

Studied from: revival-50-more-20260916-0009/report-part2.md (§32).

The load-bearing pattern of BumpTop: *piles as informal grouping* —
things tossed in a pile for "I'll deal with this later", item size
expressing importance, piles you can fan out to see inside. ``physpiles``
keeps the pile and drops the physics: no engine, no simulation, just
deterministic layout rules that put every item in exactly the same place
every time. ``pile`` stacks, ``fan`` spreads, ``sort_by_importance`` puts
the heaviest thinking on top — and LEVI says plainly that the "physics"
is choreography, not simulation.

This is an original, from-scratch reimplementation — no recovered code.
Local-first, stdlib only, no network. LEVI's own synthetic intelligence,
never a mask of anyone else's.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Literal, Optional


ORIGIN = "levi-revival/physpiles"


Layout = Literal["stack", "fan"]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PhyspilesError(Exception):
    """Base class for physpiles failures."""


class UnknownItem(PhyspilesError):
    """A pile operation named an item that isn't in the pile."""

    def __init__(self, item_id: str):
        super().__init__(f"no item {item_id!r} in this pile")
        self.item_id = item_id


# ---------------------------------------------------------------------------
# Items and piles
# ---------------------------------------------------------------------------


@dataclass
class PileItem:
    """One thing in the pile. ``importance`` is 0..1 and drives size:
    bigger means "deal with me sooner". Honest and visible."""

    item_id: str
    label: str
    importance: float = 0.5
    note: str = ""

    def __post_init__(self):
        if not 0.0 <= self.importance <= 1.0:
            raise PhyspilesError(
                f"importance of {self.item_id!r} must be 0..1, got {self.importance}"
            )

    def size_class(self) -> str:
        """Size as a word, because the pile shows its reasoning."""
        if self.importance >= 0.8:
            return "large"
        if self.importance >= 0.5:
            return "medium"
        return "small"


@dataclass
class PlacedItem:
    """An item plus its deterministic slot in the layout."""

    item: PileItem
    x: int
    y: int
    rotation: int  # degrees, -8..8 — the casual tilt of a real pile
    order: int  # stacking order: 0 is the bottom of the pile


class Pile:
    """A spatial pile of items. Layout is a pure function of the items
    and the mode — deterministic choreography, openly not physics.

    - ``stack``: items cascade with a fixed offset, like papers dropped
      one on another. The last item added sits on top.
    - ``fan``: items spread in reading order so every label shows.
    Size always expresses importance, in either mode.
    """

    STACK_DX = 3
    STACK_DY = 2
    FAN_DX = 14

    def __init__(self, name: str = "pile", layout: Layout = "stack"):
        self.name = name
        self.layout: Layout = layout
        self._items: list[PileItem] = []

    # -- filling the pile ---------------------------------------------------
    def toss(
        self, item_id: str, label: str, importance: float = 0.5, note: str = ""
    ) -> PileItem:
        """Toss something onto the pile — the triage gesture itself."""
        if any(i.item_id == item_id for i in self._items):
            raise PhyspilesError(f"item {item_id!r} is already in the pile")
        item = PileItem(item_id=item_id, label=label, importance=importance, note=note)
        self._items.append(item)
        return item

    def pull(self, item_id: str) -> PileItem:
        """Take an item out of the pile (dealt with, filed, gone)."""
        for i, item in enumerate(self._items):
            if item.item_id == item_id:
                return self._items.pop(i)
        raise UnknownItem(item_id)

    def item(self, item_id: str) -> PileItem:
        for item in self._items:
            if item.item_id == item_id:
                return item
        raise UnknownItem(item_id)

    def reweigh(self, item_id: str, importance: float) -> PileItem:
        """Change how much an item matters; the pile re-lays itself out."""
        item = self.item(item_id)
        if not 0.0 <= importance <= 1.0:
            raise PhyspilesError("importance must be 0..1")
        item.importance = importance
        return item

    # -- arranging ------------------------------------------------------------
    def pile(self) -> "Pile":
        """Stack it: the dropped-papers cascade."""
        self.layout = "stack"
        return self

    def fan(self) -> "Pile":
        """Fan it out: every label visible, importance still sized."""
        self.layout = "fan"
        return self

    def sort_by_importance(self) -> "Pile":
        """Heaviest thinking on top (the end of the list is the top of
        the pile). Stable: ties keep toss order."""
        self._items.sort(key=lambda i: i.importance)
        return self

    def peek(self) -> Optional[PileItem]:
        """What's on top right now."""
        return self._items[-1] if self._items else None

    # -- deterministic layout ---------------------------------------------------
    def layout_items(self) -> list[PlacedItem]:
        """Compute every item's slot. Same items, same mode → same slots,
        every time. No randomness, no engine, no surprises."""
        placed: list[PlacedItem] = []
        for order, item in enumerate(self._items):
            tilt = ((order * 5 + len(item.item_id) * 3) % 17) - 8
            if self.layout == "stack":
                x, y = order * self.STACK_DX, order * self.STACK_DY
            else:  # fan
                x, y = order * self.FAN_DX, (order % 2) * 4
            placed.append(PlacedItem(item=item, x=x, y=y, rotation=tilt, order=order))
        return placed

    def render(self) -> str:
        """The pile as text: top item last, size words showing importance."""
        lines = [f"⌁ {self.name} ({self.layout}, {len(self._items)} items)"]
        for placed in self.layout_items():
            item = placed.item
            bar = "█" * max(1, round(item.importance * 8))
            lines.append(
                f"  [{placed.order}] ({item.size_class():6}) {bar} {item.label} "
                f"@({placed.x},{placed.y}) ∠{placed.rotation}°"
            )
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[PileItem]:
        return iter(self._items)


def demo_pile() -> Pile:
    """An inbox triage pile: three things tossed in, heaviest on top."""
    pile = Pile("inbox")
    pile.toss("visa", "visa application", importance=0.9)
    pile.toss("receipt", "lunch receipt", importance=0.2)
    pile.toss("draft", "draft reply to Sam", importance=0.65)
    pile.sort_by_importance()
    return pile


__all__ = [
    "Layout",
    "PhyspilesError",
    "UnknownItem",
    "PileItem",
    "PlacedItem",
    "Pile",
    "demo_pile",
]

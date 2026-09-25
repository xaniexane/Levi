"""An explicit, user-curated top-N list of who matters.

Studied from: fallen-platforms-hunt-20260916/report.md [4. MySpace's handmade page]

The studied shape: the Top 8 — a social hierarchy the user declares
out loud, ranked and public, instead of one hidden in a feed
algorithm. The meaning is the *curation itself*: who you name, what
order, what changes.

LEVI-native re-expression: a ranked list of named slots with a fixed
capacity, explicit moves (rank up/down, pin, swap), a change journal
so the history of who moved where is legible, and an export that
reads like a declaration, not a metric.

Honest limits: it's a list with ranks and a journal — no implied
reciprocity, no social graph, no sentiment analysis. The list is the
whole mechanism.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

ORIGIN = "levi-revival/top8-list"

#: The canonical capacity. Any N works, but the shape is a short list.
DEFAULT_CAPACITY = 8


class TopListError(Exception):
    """Raised for bad names, duplicate slots, or illegal moves."""


@dataclass
class Slot:
    """One ranked entry."""

    name: str
    note: str = ""
    pinned: bool = False


@dataclass
class Change:
    """One journal entry recording a re-ranking."""

    seq: int
    action: str
    detail: str


class TopList:
    """A public, user-ranked list of who matters."""

    def __init__(self, owner: str, capacity: int = DEFAULT_CAPACITY) -> None:
        if capacity < 1:
            raise TopListError("capacity must be at least 1")
        self.owner = owner
        self.capacity = capacity
        self._slots: List[Slot] = []
        self._journal: List[Change] = []
        self._seq = 0

    # -- internals ---------------------------------------------------------
    def _log(self, action: str, detail: str) -> None:
        self._seq += 1
        self._journal.append(Change(seq=self._seq, action=action, detail=detail))

    def _find(self, name: str) -> Slot:
        for slot in self._slots:
            if slot.name.lower() == name.lower():
                return slot
        raise TopListError(f"not on the list: {name!r}")

    # -- membership ----------------------------------------------------------
    def add(self, name: str, note: str = "") -> int:
        """Add to the end of the list; returns the rank (1-based)."""
        name = name.strip()
        if not name:
            raise TopListError("name may not be blank")
        if any(s.name.lower() == name.lower() for s in self._slots):
            raise TopListError(f"already on the list: {name!r}")
        if len(self._slots) >= self.capacity:
            raise TopListError(f"list is full at {self.capacity}")
        self._slots.append(Slot(name=name, note=note))
        self._log("add", f"{name} entered at rank {len(self._slots)}")
        return len(self._slots)

    def remove(self, name: str) -> None:
        slot = self._find(name)
        self._slots.remove(slot)
        self._log("remove", f"{slot.name} left the list")

    # -- ranking ---------------------------------------------------------------
    def rank(self, name: str) -> int:
        """Current 1-based rank of a name."""
        return self._slots.index(self._find(name)) + 1

    def move(self, name: str, new_rank: int) -> None:
        """Move to an exact rank; pinned slots refuse to move."""
        slot = self._find(name)
        if slot.pinned:
            raise TopListError(f"{slot.name} is pinned and cannot move")
        if not 1 <= new_rank <= len(self._slots):
            raise TopListError(f"rank out of range: {new_rank}")
        old = self.rank(name)
        self._slots.remove(slot)
        self._slots.insert(new_rank - 1, slot)
        if old != new_rank:
            self._log("move", f"{slot.name}: rank {old} -> {new_rank}")

    def promote(self, name: str) -> None:
        """Bump one rank toward the top."""
        self._find(name)  # raises if unknown; pin/move checks live in move()
        self.move(name, max(1, self.rank(name) - 1))

    def swap(self, first: str, second: str) -> None:
        a, b = self._find(first), self._find(second)
        if a.pinned or b.pinned:
            raise TopListError("pinned slots cannot be swapped")
        ia, ib = self._slots.index(a), self._slots.index(b)
        self._slots[ia], self._slots[ib] = self._slots[ib], self._slots[ia]
        self._log("swap", f"{a.name} <-> {b.name}")

    def pin(self, name: str) -> None:
        slot = self._find(name)
        slot.pinned = True
        self._log("pin", f"{slot.name} pinned at rank {self.rank(name)}")

    def unpin(self, name: str) -> None:
        slot = self._find(name)
        slot.pinned = False
        self._log("unpin", f"{slot.name} unpinned")

    # -- reads -------------------------------------------------------------------
    def as_list(self) -> List[str]:
        return [s.name for s in self._slots]

    def detail(self, name: str) -> Slot:
        return self._find(name)

    def history(self) -> List[Change]:
        return list(self._journal)

    def declaration(self) -> str:
        """The list as a public statement, not a metric."""
        lines = [f"{self.owner}'s top {self.capacity}:"]
        for i, slot in enumerate(self._slots, 1):
            mark = " *" if slot.pinned else ""
            note = f" — {slot.note}" if slot.note else ""
            lines.append(f"  {i}. {slot.name}{mark}{note}")
        return "\n".join(lines)

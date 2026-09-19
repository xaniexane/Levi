"""New-tab launchpad of visual dials: intentions, not a feed.

Studied from: desktop-casualties-20260916/report.md [1. Opera]

Functional description: a grid of "dials" — one glanceable tile per
intention, each pointing at a target the user chose. Dials are created,
renamed, re-slotted, and removed; the launchpad renders as a fixed grid of
rows so the user builds spatial memory ("morning news is top-left"). Visit
counts and last-visit stamps are recorded so the pad can sort by habit
without becoming a recommendation feed — the user owns every dial.

Pure Python, stdlib only. No provider branding. Not artificial — synthetic.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional

ORIGIN = "levi-revival/speed-dial"


@dataclass
class Dial:
    """One intention tile on the launchpad."""

    id: int
    title: str
    target: str
    slot: int
    visits: int = 0
    last_visited: Optional[float] = None
    note: str = ""

    def visit(self) -> None:
        self.visits += 1
        self.last_visited = time.time()


class SpeedDial:
    """The launchpad: an ordered grid of user-owned dials."""

    def __init__(self, columns: int = 4) -> None:
        if columns < 1:
            raise ValueError("columns must be >= 1")
        self.columns = columns
        self._dials: Dict[int, Dial] = {}
        self._next_id = 1

    # -- management ----------------------------------------------------
    def add(self, title: str, target: str, note: str = "") -> Dial:
        if not title.strip() or not target.strip():
            raise ValueError("title and target must be non-empty")
        slot = self._next_free_slot()
        dial = Dial(self._next_id, title.strip(), target.strip(), slot, note=note)
        self._dials[dial.id] = dial
        self._next_id += 1
        return dial

    def _next_free_slot(self) -> int:
        taken = {d.slot for d in self._dials.values()}
        slot = 0
        while slot in taken:
            slot += 1
        return slot

    def remove(self, dial_id: int) -> bool:
        return self._dials.pop(dial_id, None) is not None

    def rename(self, dial_id: int, title: str) -> None:
        if not title.strip():
            raise ValueError("title must be non-empty")
        self._dials[dial_id].title = title.strip()

    def retarget(self, dial_id: int, target: str) -> None:
        if not target.strip():
            raise ValueError("target must be non-empty")
        self._dials[dial_id].target = target.strip()

    def move(self, dial_id: int, slot: int) -> None:
        """Move a dial to an absolute slot, swapping with any occupant."""
        if slot < 0:
            raise ValueError("slot must be >= 0")
        dial = self._dials[dial_id]
        for other in self._dials.values():
            if other.id != dial_id and other.slot == slot:
                other.slot = dial.slot
        dial.slot = slot

    # -- use ------------------------------------------------------------
    def launch(self, dial_id: int) -> str:
        """'Open' a dial: records the visit and returns its target."""
        dial = self._dials[dial_id]
        dial.visit()
        return dial.target

    def by_slot(self) -> List[Dial]:
        return sorted(self._dials.values(), key=lambda d: d.slot)

    def by_habit(self) -> List[Dial]:
        """Dials ordered by use, most-visited first — the user's own habit,
        computed locally, never a recommendation feed."""
        return sorted(
            self._dials.values(),
            key=lambda d: (-d.visits, d.slot),
        )

    def find(self, query: str) -> List[Dial]:
        q = query.lower()
        return [
            d
            for d in self._dials.values()
            if q in d.title.lower() or q in d.target.lower()
        ]

    # -- rendering ------------------------------------------------------
    def render(self) -> str:
        """Render the grid as fixed rows of ``[slot] title`` cells."""
        dials = self.by_slot()
        if not dials:
            return "(empty launchpad)"
        cells = [f"[{d.slot}] {d.title}" for d in dials]
        width = max(len(c) for c in cells) + 2
        rows = []
        for i in range(0, len(cells), self.columns):
            chunk = cells[i : i + self.columns]
            rows.append(" | ".join(c.ljust(width) for c in chunk))
        return "\n".join(rows)

    def to_dict(self) -> Dict[str, object]:
        return {
            "columns": self.columns,
            "dials": [
                {
                    "id": d.id,
                    "title": d.title,
                    "target": d.target,
                    "slot": d.slot,
                    "visits": d.visits,
                    "note": d.note,
                }
                for d in self.by_slot()
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "SpeedDial":
        pad = cls(columns=int(data.get("columns", 4)))
        for raw in data.get("dials", []):  # type: ignore[union-attr]
            dial = Dial(
                id=int(raw["id"]),
                title=str(raw["title"]),
                target=str(raw["target"]),
                slot=int(raw["slot"]),
                visits=int(raw.get("visits", 0)),
                note=str(raw.get("note", "")),
            )
            pad._dials[dial.id] = dial
            pad._next_id = max(pad._next_id, dial.id + 1)
        return pad


def demo_dial() -> Dict[str, object]:
    pad = SpeedDial(columns=3)
    pad.add("Morning brief", "levi://news/morning")
    pad.add("Build status", "levi://build/status")
    pad.add("Garden notes", "levi://notes/garden")
    pad.launch(1)
    pad.launch(1)
    pad.launch(3)
    return {"grid": pad.render(), "habit": [d.title for d in pad.by_habit()]}


if __name__ == "__main__":  # pragma: no cover
    import json

    print(json.dumps(demo_dial(), indent=2))

"""Comptometer: key-driven direct actuation with chorded entry.

Studied from: pre-digital-computation-20260916 report.md [Beat A #2,
LOAD-BEARING] (functional shape only: each key directly actuates its
column with no crank; multi-finger chorded entry; controlled-key
mechanical debounce).

The mechanism, faithfully simulated:

- **Key-driven direct actuation.** Each column (decimal position)
  carries keys 1..9. Pressing a key adds its digit straight into
  that column — no crank turn, no separate add stroke. Carry
  propagates through the register immediately.
- **Chorded multi-finger entry.** Several keys in different columns
  may be pressed at once; the whole chord lands atomically in one
  machine cycle. A fast operator enters a whole number with one
  hand motion.
- **Controlled-key debounce.** Every key has travel. A full stroke
  (travel >= 1.0) registers. A short bounce (travel < 0.5) is
  ignored as flutter. A *partial* stroke (0.5 <= travel < 1.0) trips
  the controlled-key lock: the machine refuses the whole chord and
  the key stays locked until it returns fully to rest — no phantom
  half-adds. ``release()`` clears locks.

The register is a fixed-width decimal accumulator (default 8
columns); overflow wraps with a flag. This simulates the actuation
protocol, not the levers. stdlib-only, no network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Mapping, Tuple


ORIGIN = "levi-revival/comptometer"

COLUMNS = 8
FULL_STROKE = 1.0
FLUTTER_LIMIT = 0.5


@dataclass
class KeyEvent:
    """What one key press did."""

    column: int
    key: int
    travel: float
    outcome: str  # "added" | "flutter" | "locked" | "rejected-locked"


@dataclass
class ChordResult:
    """What one machine cycle did with a chord."""

    events: List[KeyEvent]
    added: int
    total: int
    locked: bool


class Comptometer:
    """A key-driven adding machine with controlled-key debounce."""

    def __init__(self, columns: int = COLUMNS) -> None:
        if columns < 1:
            raise ValueError("need at least one column")
        self.columns = columns
        self.modulus = 10**columns
        self.total_value = 0
        self.overflow = False
        self.locked_keys: List[Tuple[int, int]] = []  # (column, key)
        self.cycles = 0

    # -- internals ------------------------------------------------------
    def _add(self, amount: int) -> None:
        new = self.total_value + amount
        if new >= self.modulus:
            self.overflow = True
        self.total_value = new % self.modulus

    def _press_one(self, column: int, key: int, travel: float) -> KeyEvent:
        if not (0 <= column < self.columns):
            raise ValueError(f"column {column} out of range")
        if not (1 <= key <= 9):
            raise ValueError(f"key {key} out of range (1-9)")
        if (column, key) in self.locked_keys:
            return KeyEvent(column, key, travel, "rejected-locked")
        if travel < FLUTTER_LIMIT:
            return KeyEvent(column, key, travel, "flutter")
        if travel < FULL_STROKE:
            self.locked_keys.append((column, key))
            return KeyEvent(column, key, travel, "locked")
        self._add(key * (10**column))
        return KeyEvent(column, key, travel, "added")

    # -- the keyboard ----------------------------------------------------
    def press(self, column: int, key: int, travel: float = FULL_STROKE) -> KeyEvent:
        """Press one key (a one-key chord)."""
        return self.chord({column: (key, travel)}).events[0]

    def chord(self, keys: Mapping[int, Tuple[int, float]]) -> ChordResult:
        """Press several keys at once; the chord lands atomically.

        ``keys`` maps column -> (key, travel). If any key makes only a
        partial stroke, the controlled-key lock trips: *nothing* in
        the chord is added and the partial keys lock until released.
        """
        overflow_before = self.overflow
        events = [self._press_one(col, k, t) for col, (k, t) in keys.items()]
        locked = any(e.outcome == "locked" for e in events)
        if locked:
            # Controlled-key rule: a partial stroke voids the cycle.
            # Roll back anything the full-stroke keys already added.
            rolled_back = sum(
                e.key * (10**e.column) for e in events if e.outcome == "added"
            )
            self.total_value = (self.total_value - rolled_back) % self.modulus
            self.overflow = overflow_before
            for e in events:
                if e.outcome == "added":
                    e.outcome = "voided-by-lock"
            added = 0
        else:
            added = sum(e.key * (10**e.column) for e in events if e.outcome == "added")
        self.cycles += 1
        return ChordResult(
            events=events, added=added, total=self.total_value, locked=locked
        )

    def release(self) -> List[Tuple[int, int]]:
        """Return all locked keys fully to rest; report what unlocked."""
        freed = list(self.locked_keys)
        self.locked_keys.clear()
        return freed

    def clear(self) -> None:
        """Clear the total (locks are kept; release them explicitly)."""
        self.total_value = 0
        self.overflow = False

    def total(self) -> int:
        return self.total_value

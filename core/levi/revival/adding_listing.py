"""The adding-listing machine: computation that produces evidence.

Studied from: pre-digital-computation-20260916 / report.md (Beat A #9)

The mechanism: a key-driven adding machine that prints every entry on a
paper tape as it computes. The tape is the point — each keystroke leaves
a printed line, so the computation is auditable after the fact without
re-running it. Input validation happens in hardware: malformed keys
jam the machine into an error state that only an explicit clear can
release, so a bad entry can never silently enter the total.

What this module models:
- ``ListingMachine``: digit keys with column-width validation, add and
  subtract keys, subtotal and total keys, and an error lock.
- ``TapeLine``: one printed line — the entered value, the operation
  symbol, and the running total after the entry.
- ``print_tape``: the paper record as text, including subtotal/total
  lines and error-lock notices.

Honest limits: amounts are integers of plain decimal digits (the machine
predates stored-program arithmetic, and cents are the operator's
convention, not the machine's); there is no multiplication or division —
those lived in the operator's procedure, not the mechanism. No network,
stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal


ORIGIN = "levi-revival/adding-listing"

Operation = Literal["add", "subtract"]


class ErrorLock(Exception):
    """The machine has jammed on invalid input; clear it to continue."""


@dataclass(frozen=True)
class TapeLine:
    """One printed line on the paper tape."""

    entry: str  # the digits as keyed, or a control symbol
    operation: str  # "+", "-", "S" (subtotal), "T" (total), "!" (error)
    running_total: int


@dataclass
class ListingMachine:
    """A key-driven adder with a printed audit tape.

    ``columns`` is the hardware digit width: any keyed entry longer than
    this, or containing anything but decimal digits, jams the machine.
    """

    columns: int = 13
    _total: int = field(default=0, init=False, repr=False)
    _locked: bool = field(default=False, init=False, repr=False)
    _tape: List[TapeLine] = field(default_factory=list, init=False, repr=False)

    # -- keys -----------------------------------------------------------
    def enter(self, digits: str, operation: Operation = "add") -> int:
        """Press the digit keys and pull the operation lever.

        Returns the running total after the entry. Raises ``ErrorLock``
        (and jams the machine) on any input the hardware would reject:
        empty keys, non-digit characters, or more digits than columns.
        """
        if self._locked:
            raise ErrorLock("machine jammed: call clear_error() first")
        if not digits or not digits.isdigit() or len(digits) > self.columns:
            self._locked = True
            self._tape.append(
                TapeLine(entry=digits, operation="!", running_total=self._total)
            )
            raise ErrorLock(f"invalid keying rejected: {digits!r}")
        value = int(digits)
        if operation == "add":
            self._total += value
            symbol = "+"
        else:
            self._total -= value
            symbol = "-"
        self._tape.append(
            TapeLine(entry=digits, operation=symbol, running_total=self._total)
        )
        return self._total

    def subtotal(self) -> int:
        """Print the running total without clearing it."""
        if self._locked:
            raise ErrorLock("machine jammed: call clear_error() first")
        self._tape.append(TapeLine(entry="", operation="S", running_total=self._total))
        return self._total

    def total(self) -> int:
        """Print the grand total and clear the accumulator."""
        if self._locked:
            raise ErrorLock("machine jammed: call clear_error() first")
        result = self._total
        self._tape.append(TapeLine(entry="", operation="T", running_total=result))
        self._total = 0
        return result

    def clear_error(self) -> None:
        """Release the error lock. The rejected entry stays on the tape."""
        self._locked = False

    # -- reading the evidence --------------------------------------------
    @property
    def locked(self) -> bool:
        return self._locked

    @property
    def running_total(self) -> int:
        return self._total

    def tape(self) -> List[TapeLine]:
        """The printed tape as data, oldest line first."""
        return list(self._tape)

    def print_tape(self) -> str:
        """The printed tape as text, in the machine's own terse voice."""
        lines = []
        for line in self._tape:
            if line.operation == "!":
                lines.append(
                    f"! ERROR rejected {line.entry!r} (total {line.running_total})"
                )
            elif line.operation in ("S", "T"):
                label = "SUBTOTAL" if line.operation == "S" else "TOTAL"
                lines.append(f"* {label}: {line.running_total}")
            else:
                lines.append(
                    f"  {line.entry} {line.operation}  -> {line.running_total}"
                )
        return "\n".join(lines)

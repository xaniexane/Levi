"""Millionaire: direct multiplication as memoization.

Studied from: pre-digital-computation-20260916 report.md [Beat A #3,
USEFUL PATTERN] (functional shape only: the 9x9 product table
precomputed in brass pin heights, so one crank turn per multiplier
digit suffices — multiplication by table lookup, not repeated
addition).

The mechanism, faithfully simulated:

- **The brass table.** All 81 single-digit products are precomputed
  once, at build time, into ``TABLE`` — the analog of the pin plate.
  ``verify_table()`` re-checks every cell against plain arithmetic;
  a corrupted plate is refused, not silently used.
- **Direct multiplication.** To multiply, each *nonzero* multiplier
  digit costs exactly one crank turn: the machine looks up
  ``multiplicand_digit x digit`` for every multiplicand digit and
  engages the whole direct product at the carriage position in that
  one turn. Cost is counted in turns, not in additions — a multiplier
  digit of 9 costs one turn here, nine on a repeated-addition
  machine.
- **Carriage.** The direct product is added at ``10**position`` for
  the digit's decimal place.

The result register is fixed-width (default 12 digits); overflow
wraps with a flag. Addition and subtraction ride the same register.
This simulates the lookup procedure, not the pins. stdlib-only, no
network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


ORIGIN = "levi-revival/millionaire_mult"

WIDTH = 12


def _build_table() -> Dict[Tuple[int, int], int]:
    """Precompute the 9x9 brass plate: every single-digit product."""
    return {(a, b): a * b for a in range(10) for b in range(10)}


TABLE: Dict[Tuple[int, int], int] = _build_table()


def verify_table() -> bool:
    """Re-check every brass cell against plain arithmetic."""
    return all(TABLE[(a, b)] == a * b for a in range(10) for b in range(10))


@dataclass
class MultiplyResult:
    product: int
    turns: int  # crank turns used == nonzero multiplier digits
    lookups: int  # individual brass-plate lookups performed
    overflow: bool


class Millionaire:
    """A direct-multiplication machine backed by a memoized table."""

    def __init__(self, width: int = WIDTH) -> None:
        if width < 1:
            raise ValueError("width must be positive")
        if not verify_table():
            raise RuntimeError("brass plate failed verification")
        self.width = width
        self.modulus = 10**width
        self.result = 0
        self.overflow = False
        self.turns = 0
        self.lookups = 0

    # -- register -------------------------------------------------------
    def _accumulate(self, amount: int) -> None:
        new = self.result + amount
        if not (0 <= new < self.modulus):
            self.overflow = True
        self.result = new % self.modulus

    def clear(self) -> None:
        self.result = 0
        self.overflow = False

    def add(self, value: int) -> None:
        if value < 0:
            raise ValueError("use subtract for negative amounts")
        self._accumulate(value)

    def subtract(self, value: int) -> None:
        if value < 0:
            raise ValueError("value must be non-negative")
        self._accumulate(-value)

    # -- the brass plate -------------------------------------------------
    @staticmethod
    def _digits(value: int) -> List[int]:
        return [int(ch) for ch in reversed(str(value))] if value else [0]

    def _direct_product(self, multiplicand: int, digit: int) -> int:
        """One turn's worth: multiplicand x single digit, via the plate."""
        if not (0 <= digit <= 9):
            raise ValueError("multiplier digit must be 0-9")
        total = 0
        for pos, m_digit in enumerate(self._digits(multiplicand)):
            total += TABLE[(m_digit, digit)] * (10**pos)
            self.lookups += 1
        return total

    def multiply(self, multiplicand: int, multiplier: int) -> MultiplyResult:
        """Direct multiplication: one crank turn per nonzero digit."""
        if multiplicand < 0 or multiplier < 0:
            raise ValueError("operands must be non-negative")
        if multiplicand >= self.modulus:
            raise OverflowError("multiplicand exceeds register width")
        self.clear()
        self.turns = 0
        self.lookups = 0
        turns = 0
        for pos, digit in enumerate(self._digits(multiplier)):
            if digit == 0:
                continue  # zero digits cost no turn at all
            direct = self._direct_product(multiplicand, digit)
            self._accumulate(direct * (10**pos))
            turns += 1
        self.turns = turns
        return MultiplyResult(
            product=self.result,
            turns=turns,
            lookups=self.lookups,
            overflow=self.overflow,
        )

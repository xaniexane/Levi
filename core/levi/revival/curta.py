"""Curta: one stepped drum on a segmented shaft, serial digits.

Studied from: pre-digital-computation-20260916 report.md [Beat A #4,
USEFUL PATTERN] (functional shape only: a single stepped drum serves
every digit position through a segmented shaft; the carriage selects
which digit column the drum engages — a mechanical ALU with
time-multiplexed serial digits).

The mechanism, faithfully simulated:

- **One drum, segmented shaft.** There is a single stepped drum, not
  one per column. The setting register's digits sit on a segmented
  shaft; each segment presents its digit's tooth count to the one
  drum in turn — time-multiplexed serial engagement.
- **Setting sliders.** The multiplicand is set once on the input
  sliders (8 digits). It stays put for the whole computation.
- **Carriage-selected position.** The carriage chooses which decimal
  position the drum engages. One crank turn adds the *entire* set
  value times ``10**carriage`` — every set digit contributes in that
  single turn, each through the same drum in sequence.
- **Revolution counter per position.** The counter records how many
  turns were cranked at each carriage position; its digits are the
  multiplier. Lifting the crank reverses the drum for subtraction,
  and the counter counts back down.
- **Result register.** 11 digits; overflow wraps with a flag.

Operations: ``crank`` (add turns at the carriage),
``crank_back`` (subtract), ``multiply`` (turns per multiplier digit
at successive positions), ``divide`` (repeated subtraction from the
top position down; quotient lands in the counter). Division by zero
raises; each quotient digit is capped at 9 per position like the
brass.

This simulates the register protocol of the serial drum, not the
drum's teeth. stdlib-only, no network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


ORIGIN = "levi-revival/curta"

SETTING_WIDTH = 8
RESULT_WIDTH = 11
CARRIAGE_POSITIONS = 6  # positions 0..5


@dataclass
class CrankResult:
    added: int
    carriage: int
    result: int
    counter: Dict[int, int]
    overflow: bool


@dataclass
class MultiplyResult:
    product: int
    turns: int
    counter_value: int
    multiplier: int
    self_check_ok: bool
    overflow: bool


@dataclass
class DivideResult:
    quotient: int
    remainder: int
    turns: int
    overflow: bool


class Curta:
    """A single-drum serial-digit calculator."""

    def __init__(
        self,
        setting_width: int = SETTING_WIDTH,
        result_width: int = RESULT_WIDTH,
        carriage_positions: int = CARRIAGE_POSITIONS,
    ) -> None:
        if setting_width < 1 or result_width < 1 or carriage_positions < 1:
            raise ValueError("widths and carriage count must be positive")
        self.setting_width = setting_width
        self.setting_modulus = 10**setting_width
        self.result_width = result_width
        self.result_modulus = 10**result_width
        self.carriage_positions = list(range(carriage_positions))
        self.setting = 0
        self.result = 0
        self.carriage = 0
        self.counter: Dict[int, int] = {p: 0 for p in self.carriage_positions}
        self.overflow = False
        self.turns = 0

    # -- setup ----------------------------------------------------------
    def set(self, value: int) -> None:
        """Set the multiplicand on the input sliders."""
        if not (0 <= value < self.setting_modulus):
            raise ValueError("setting out of slider range")
        self.setting = value

    def move_carriage(self, position: int) -> None:
        """Slide the carriage to select the engaged digit position."""
        if position not in self.carriage_positions:
            raise ValueError(f"carriage position {position} out of range")
        self.carriage = position

    def clear(self) -> None:
        """Clear result and revolution counter (setting kept)."""
        self.result = 0
        self.counter = {p: 0 for p in self.carriage_positions}
        self.overflow = False

    def counter_value(self) -> int:
        return sum(d * (10**p) for p, d in self.counter.items())

    # -- the single drum -------------------------------------------------
    def _engage(self, signed_turns: int) -> CrankResult:
        """One drum engagement: the whole setting, serially, at carriage.

        Every set digit passes the single drum in sequence within the
        one turn — the shaft's segments time-multiplex the digits.
        """
        if self.carriage not in self.carriage_positions:
            raise ValueError("carriage out of range")
        added = signed_turns * self.setting * (10**self.carriage)
        new = self.result + added
        overflow = not (0 <= new < self.result_modulus)
        self.result = new % self.result_modulus
        self.overflow = self.overflow or overflow
        self.counter[self.carriage] += signed_turns
        self.turns += abs(signed_turns)
        return CrankResult(
            added=added,
            carriage=self.carriage,
            result=self.result,
            counter=dict(self.counter),
            overflow=overflow,
        )

    def crank(self, turns: int = 1) -> CrankResult:
        """Crank forward: add the set value at the carriage, serially."""
        if turns < 0:
            raise ValueError("turns must be non-negative")
        return self._engage(turns)

    def crank_back(self, turns: int = 1) -> CrankResult:
        """Lift the crank and turn back: subtract at the carriage."""
        if turns < 0:
            raise ValueError("turns must be non-negative")
        return self._engage(-turns)

    # -- compound operations ---------------------------------------------
    def multiply(self, multiplicand: int, multiplier: int) -> MultiplyResult:
        """Turns per multiplier digit at successive carriage positions."""
        if multiplicand < 0 or multiplier < 0:
            raise ValueError("operands must be non-negative")
        self.clear()
        self.set(multiplicand)
        self.turns = 0
        digits = [int(ch) for ch in reversed(str(multiplier))] if multiplier else [0]
        turns = 0
        for pos, digit in enumerate(digits):
            if pos not in self.carriage_positions:
                raise OverflowError("multiplier wider than carriage range")
            if digit:
                self.move_carriage(pos)
                self.crank(digit)
                turns += digit
        cv = self.counter_value()
        return MultiplyResult(
            product=self.result,
            turns=turns,
            counter_value=cv,
            multiplier=multiplier,
            self_check_ok=(
                cv == multiplier
                and self.result == (multiplicand * multiplier) % self.result_modulus
            ),
            overflow=self.overflow,
        )

    def divide(self, dividend: int, divisor: int) -> DivideResult:
        """Repeated subtraction from the top carriage position down.

        The revolution counter tallies subtraction turns per position;
        its digits are the quotient, the register keeps the remainder.
        """
        if divisor <= 0:
            raise ValueError("divisor must be positive")
        if dividend < 0:
            raise ValueError("dividend must be non-negative")
        self.clear()
        self.set(divisor)
        self.result = dividend % self.result_modulus
        self.turns = 0
        turns = 0
        for pos in sorted(self.carriage_positions, reverse=True):
            self.move_carriage(pos)
            step = divisor * (10**pos)
            digit = 0
            while self.result >= step and digit < 9:
                self.crank_back(1)
                digit += 1
                turns += 1
            # crank_back counted down; the counter digit is the tally.
            self.counter[pos] = -self.counter[pos]
        return DivideResult(
            quotient=self.counter_value(),
            remainder=self.result,
            turns=turns,
            overflow=self.overflow,
        )

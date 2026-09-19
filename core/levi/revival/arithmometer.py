"""Arithmometer: stepped drum + sliding carriage + revolution counter.

Studied from: pre-digital-computation-20260916 report.md [Beat A #1,
LOAD-BEARING] (functional shape only: stepped drum engages a number
of teeth per digit; a sliding carriage shifts decimal position; a
revolution counter records crank turns per position so the multiplier
is self-verifying).

The mechanism, faithfully simulated:

- **Stepped drum.** A brass drum carries 9 steps of increasing tooth
  count. Setting input digit ``d`` exposes exactly ``d`` teeth, so one
  crank turn adds ``input_digit * d`` worth of teeth into the result
  gears — no per-tooth iteration, the digit acts in one turn.
- **Sliding carriage.** The carriage shifts the result register left
  or right so the drum engages at a chosen decimal position; each
  crank turn adds ``input * 10**carriage``.
- **Revolution counter.** Every turn is counted at the current
  carriage position. After a multiplication the counter's digits must
  spell the multiplier — the machine checks its own work.
- **Result register.** Fixed width (default 13 digits, like the
  brass). Overflow wraps modulo 10**width and raises a flag; the
  brass did exactly this, silently.

Operations: ``add`` / ``subtract`` (one crank turn at the carriage),
``multiply`` (digit-by-digit shift-and-add with counter self-check),
``divide`` (repeated subtraction per carriage position, quotient
built from the counter). Division by zero raises; quotient width is
bounded by the carriage range.

This is a faithful register-level simulation of the shift-and-add
procedure, not a physical model of the drums. stdlib-only, no
network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


ORIGIN = "levi-revival/arithmometer"

DEFAULT_WIDTH = 13
DEFAULT_CARRIAGE_RANGE = range(0, 8)  # positions 0..7


@dataclass
class CrankResult:
    """Outcome of one crank turn."""

    added: int
    carriage: int
    result: int
    counter_digit: int
    overflow: bool


@dataclass
class MultiplyResult:
    """Outcome of a full multiplication."""

    product: int
    turns: int
    counter_value: int
    multiplier: int
    self_check_ok: bool
    overflow: bool


@dataclass
class DivideResult:
    """Outcome of a full division."""

    quotient: int
    remainder: int
    turns: int
    overflow: bool


class Arithmometer:
    """A stepped-drum calculator with carriage and revolution counter."""

    def __init__(
        self,
        width: int = DEFAULT_WIDTH,
        carriage_positions: range = DEFAULT_CARRIAGE_RANGE,
    ) -> None:
        if width < 1:
            raise ValueError("width must be positive")
        self.width = width
        self.modulus = 10**width
        self.carriage_positions = list(carriage_positions)
        self.result = 0
        self.input_value = 0
        self.carriage = 0
        self.counter: Dict[int, int] = {p: 0 for p in self.carriage_positions}
        self.overflow = False
        self.turns = 0

    # -- setup ---------------------------------------------------------
    def enter(self, value: int) -> None:
        """Set the input (multiplicand) register."""
        if value < 0:
            raise ValueError("input must be non-negative")
        if value >= self.modulus:
            raise OverflowError("input exceeds register width")
        self.input_value = value

    def move_carriage(self, position: int) -> None:
        """Slide the carriage to a decimal position."""
        if position not in self.carriage_positions:
            raise ValueError(f"carriage position {position} out of range")
        self.carriage = position

    def clear(self) -> None:
        """Clear result, counter, overflow flag (input register kept)."""
        self.result = 0
        self.counter = {p: 0 for p in self.carriage_positions}
        self.overflow = False

    # -- the crank ------------------------------------------------------
    def _accumulate(self, amount: int) -> bool:
        new = self.result + amount
        wrapped = new % self.modulus
        overflow = not (0 <= new < self.modulus)
        self.result = wrapped
        self.overflow = self.overflow or overflow
        return overflow

    def crank(self, turns: int = 1, direction: int = 1) -> CrankResult:
        """Turn the crank: engage the stepped drum ``turns`` times.

        ``direction`` +1 adds, -1 subtracts (Thomas's machine
        subtracted directly; no complement tricks needed here).
        """
        if turns < 0:
            raise ValueError("turns must be non-negative")
        if direction not in (1, -1):
            raise ValueError("direction must be +1 or -1")
        if self.carriage not in self.carriage_positions:
            raise ValueError("carriage out of range")
        # The stepped drum: digit d exposes d teeth; one turn moves the
        # result gears by input_value * 10**carriage in a single motion.
        added = direction * turns * self.input_value * (10**self.carriage)
        overflow = self._accumulate(added)
        self.counter[self.carriage] += direction * turns
        self.turns += turns
        return CrankResult(
            added=added,
            carriage=self.carriage,
            result=self.result,
            counter_digit=self.counter[self.carriage],
            overflow=overflow,
        )

    def add(self) -> CrankResult:
        """One turn: result += input * 10**carriage."""
        return self.crank(1, 1)

    def subtract(self) -> CrankResult:
        """One turn: result -= input * 10**carriage."""
        return self.crank(1, -1)

    # -- compound operations --------------------------------------------
    def _digits(self, value: int) -> List[int]:
        return [int(ch) for ch in str(value)] if value else [0]

    def multiply(self, multiplicand: int, multiplier: int) -> MultiplyResult:
        """Shift-and-add multiplication with counter self-verification."""
        if multiplicand < 0 or multiplier < 0:
            raise ValueError("operands must be non-negative")
        self.clear()
        self.enter(multiplicand)
        self.turns = 0
        digits = self._digits(multiplier)
        turns = 0
        for pos, digit in enumerate(reversed(digits)):
            if pos not in self.carriage_positions:
                raise OverflowError("multiplier wider than carriage range")
            if digit:
                self.move_carriage(pos)
                self.crank(digit, 1)
                turns += digit
        counter_value = sum(d * (10**p) for p, d in self.counter.items())
        return MultiplyResult(
            product=self.result,
            turns=turns,
            counter_value=counter_value,
            multiplier=multiplier,
            self_check_ok=(
                counter_value == multiplier
                and self.result == (multiplicand * multiplier) % self.modulus
            ),
            overflow=self.overflow,
        )

    def divide(self, dividend: int, divisor: int) -> DivideResult:
        """Repeated-subtraction division, high carriage position first.

        Quotient digits accumulate in the revolution counter as
        subtraction turns; the remainder is left in the result
        register.
        """
        if divisor <= 0:
            raise ValueError("divisor must be positive")
        if dividend < 0:
            raise ValueError("dividend must be non-negative")
        self.clear()
        self.enter(divisor)
        self.result = dividend % self.modulus
        self.turns = 0
        turns = 0
        for pos in sorted(self.carriage_positions, reverse=True):
            self.move_carriage(pos)
            step = divisor * (10**pos)
            digit = 0
            while self.result >= step and digit < 9:
                self.subtract()
                digit += 1
                turns += 1
            # counter[pos] went negative by `digit`; flip to quotient.
            self.counter[pos] = -self.counter[pos]
        quotient = sum(d * (10**p) for p, d in self.counter.items())
        # Undo the counter negation bookkeeping: counter already holds
        # positive quotient digits after the flip above.
        return DivideResult(
            quotient=quotient,
            remainder=self.result,
            turns=turns,
            overflow=self.overflow,
        )

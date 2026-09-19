"""Odhner pinwheel: variable-tooth pins as a sparse digit encoding.

Studied from: pre-digital-computation-20260916 report.md [Beat A #5,
USEFUL PATTERN] (functional shape only: each digit is a set of
retractable pins — a sparse, physical encoding of the digit — and the
engaged pins drive the result gears as the wheel turns).

The mechanism, faithfully simulated:

- **The pinwheel.** Each digit wheel carries 9 radial slots. Setting
  digit ``d`` extends exactly ``d`` pins out of the wheel's rim — the
  digit ``7`` is pins 0..6 extended, the rest retracted. The digit is
  a sparse mask: ``mask(d) = (1 << d) - 1``, and the machine
  self-verifies with ``popcount(mask) == d`` on every engagement.
- **Rotation engagement.** One full turn of a pinwheel set to ``d``
  drives its result gear forward by exactly ``d`` teeth — one per
  extended pin. Retracted pins pass through the mesh untouched.
- **Carriage shift.** The pinwheel row slides so the wheels engage
  the result register at a chosen decimal position; one turn adds
  ``input * 10**carriage`` via pin engagement, not tooth counting.
- **Clear by retract.** Clearing the input retracts every pin
  (masks to zero) — the wheels spin free and engage nothing.

The result register is fixed-width (default 10 digits); overflow
wraps with a flag. Division runs repeated pinwheel subtraction from
the top position down, quotient tallied per position.

This simulates the pin engagement protocol, not the pins' springs.
stdlib-only, no network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


ORIGIN = "levi-revival/pinwheel"

WIDTH = 10
PINS_PER_WHEEL = 9


def pin_mask(digit: int) -> int:
    """Sparse encoding: digit ``d`` extends the first ``d`` of 9 pins."""
    if not (0 <= digit <= 9):
        raise ValueError("pinwheel digit must be 0-9")
    return (1 << digit) - 1


def popcount(mask: int) -> int:
    """Teeth a wheel will engage this turn: extended pins."""
    return bin(mask).count("1")


@dataclass
class TurnResult:
    engaged_teeth: int
    carriage: int
    result: int
    overflow: bool


@dataclass
class MultiplyResult:
    product: int
    turns: int
    overflow: bool


@dataclass
class DivideResult:
    quotient: int
    remainder: int
    turns: int
    overflow: bool


class Pinwheel:
    """An Odhner-style pinwheel calculator."""

    def __init__(self, width: int = WIDTH, carriage_positions: int = 8) -> None:
        if width < 1 or carriage_positions < 1:
            raise ValueError("width and carriage count must be positive")
        self.width = width
        self.modulus = 10**width
        self.carriage_positions = list(range(carriage_positions))
        # One pinwheel per input digit position; value = extended pins.
        self.wheels: Dict[int, int] = {p: 0 for p in range(width)}
        self.result = 0
        self.carriage = 0
        self.overflow = False
        self.turns = 0

    # -- the pins --------------------------------------------------------
    def set_input(self, value: int) -> None:
        """Extend pins across the wheels to encode ``value``."""
        if not (0 <= value < self.modulus):
            raise ValueError("input out of pinwheel range")
        for pos in range(self.width):
            digit = (value // (10**pos)) % 10
            self.wheels[pos] = pin_mask(digit)

    def retract_all(self) -> None:
        """Clear the input: retract every pin."""
        for pos in self.wheels:
            self.wheels[pos] = 0

    def input_value(self) -> int:
        """Read back the encoded input, verifying each wheel."""
        total = 0
        for pos, mask in self.wheels.items():
            digit = popcount(mask)
            if mask != pin_mask(digit):
                raise RuntimeError(f"pinwheel {pos} has a non-prefix mask: corrupted")
            total += digit * (10**pos)
        return total

    def move_carriage(self, position: int) -> None:
        if position not in self.carriage_positions:
            raise ValueError(f"carriage position {position} out of range")
        self.carriage = position

    def clear_result(self) -> None:
        self.result = 0
        self.overflow = False

    # -- rotation ----------------------------------------------------------
    def _accumulate(self, amount: int) -> bool:
        new = self.result + amount
        overflow = not (0 <= new < self.modulus)
        self.result = new % self.modulus
        self.overflow = self.overflow or overflow
        return overflow

    def rotate(self, turns: int = 1, direction: int = 1) -> TurnResult:
        """Turn the pinwheels: each extended pin engages one tooth.

        ``direction`` +1 adds, -1 subtracts. Engagement is verified:
        the teeth moved must equal the popcount of every wheel's mask
        times the positional shift — a wheel that lies about its pins
        is caught here.
        """
        if turns < 0:
            raise ValueError("turns must be non-negative")
        if direction not in (1, -1):
            raise ValueError("direction must be +1 or -1")
        engaged = 0
        for _ in range(turns):
            per_turn = 0
            for pos, mask in self.wheels.items():
                teeth = popcount(mask)
                per_turn += teeth * (10 ** (pos + self.carriage))
            # Self-verification: engagement == encoded input shifted.
            assert per_turn == self.input_value() * (10**self.carriage)
            engaged += per_turn
            self._accumulate(direction * per_turn)
        self.turns += turns
        return TurnResult(
            engaged_teeth=engaged,
            carriage=self.carriage,
            result=self.result,
            overflow=self.overflow,
        )

    # -- compound operations -----------------------------------------------
    def multiply(self, multiplicand: int, multiplier: int) -> MultiplyResult:
        """Shift-and-add: pinwheel turns per multiplier digit."""
        if multiplicand < 0 or multiplier < 0:
            raise ValueError("operands must be non-negative")
        if multiplicand >= self.modulus:
            raise OverflowError("multiplicand exceeds pinwheel width")
        self.clear_result()
        self.retract_all()
        self.set_input(multiplicand)
        self.turns = 0
        turns = 0
        digits = [int(ch) for ch in reversed(str(multiplier))] if multiplier else [0]
        for pos, digit in enumerate(digits):
            if pos not in self.carriage_positions:
                raise OverflowError("multiplier wider than carriage range")
            if digit:
                self.move_carriage(pos)
                self.rotate(digit, 1)
                turns += digit
        return MultiplyResult(product=self.result, turns=turns, overflow=self.overflow)

    def divide(self, dividend: int, divisor: int) -> DivideResult:
        """Repeated pinwheel subtraction, top carriage position first."""
        if divisor <= 0:
            raise ValueError("divisor must be positive")
        if dividend < 0:
            raise ValueError("dividend must be non-negative")
        self.clear_result()
        self.retract_all()
        self.set_input(divisor)
        self.result = dividend % self.modulus
        self.turns = 0
        turns = 0
        quotient_digits: Dict[int, int] = {}
        for pos in sorted(self.carriage_positions, reverse=True):
            self.move_carriage(pos)
            step = divisor * (10**pos)
            digit = 0
            while self.result >= step and digit < 9:
                self.rotate(1, -1)
                digit += 1
                turns += 1
            quotient_digits[pos] = digit
        quotient = sum(d * (10**p) for p, d in quotient_digits.items())
        return DivideResult(
            quotient=quotient,
            remainder=self.result,
            turns=turns,
            overflow=self.overflow,
        )

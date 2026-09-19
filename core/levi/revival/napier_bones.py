"""Napier's bones: the algorithm factored into the object.

Studied from: pre-digital-computation-20260916 / report.md (Beat A #12)

The mechanism: a set of rods, one per digit 0-9. Rod ``d`` carries the
multiples of ``d`` — row ``r`` shows ``d*r`` split across a diagonal
into tens and units. To multiply, you lay out the rods for the
multiplicand's digits, read one row per multiplier digit, and add along
the diagonals, letting carries ripple left. The hard part of
multiplication (all the single-digit products) is precomputed in the
object; what remains is addition along diagonals.

The same idea extends to "location arithmetic": binary counting done as
board positions, where two counters on one square are replaced by one
counter on the next — carrying as a physical rule rather than a
memorized one.

What this module models:
- ``Bone``: one rod; ``row(r)`` returns the (tens, units) diagonal
  pair for ``d * r``.
- ``multiply``: genuine bone multiplication — rods are laid out, rows
  read, diagonals summed with carries; never a shortcut ``a * b`` on
  the critical path.
- ``divide``: bone-assisted long division — each quotient digit is
  found by reading the bone rows of the divisor.
- ``LocationBoard``: binary addition/subtraction by the doubling rule
  (two counters on a square become one on the next).

Honest limits: inputs are non-negative integers (the bones know
nothing of fractions or signs — those were the operator's business);
division returns (quotient, remainder). No network, stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


ORIGIN = "levi-revival/napier-bones"


@dataclass(frozen=True)
class Bone:
    """One Napier rod for a single digit: the multiples, precomputed."""

    digit: int

    def __post_init__(self) -> None:
        if not 0 <= self.digit <= 9:
            raise ValueError("a bone carries a single decimal digit")

    def row(self, multiplier_digit: int) -> Tuple[int, int]:
        """The (tens, units) diagonal pair for digit * multiplier_digit."""
        if not 0 <= multiplier_digit <= 9:
            raise ValueError("multiplier digit must be 0..9")
        product = self.digit * multiplier_digit
        return product // 10, product % 10


def _single_digit_product(digits: List[int], m: int) -> int:
    """Multiply a digit list (most-significant first) by one digit, via bones.

    Lays out one bone per digit, reads row ``m`` from each, and sums
    along the diagonals from right to left with carries — the actual
    bone procedure.
    """
    if m == 0 or not digits:
        return 0
    bones = [Bone(d) for d in digits]
    pairs = [bone.row(m) for bone in bones]  # (tens, units) per bone
    n = len(pairs)
    result_digits: List[int] = []
    carry = 0
    # Rightmost diagonal: units of the last bone.
    total = pairs[n - 1][1] + carry
    result_digits.append(total % 10)
    carry = total // 10
    # Middle diagonals: tens of bone i + units of bone i-1.
    for i in range(n - 1, 0, -1):
        total = pairs[i][0] + pairs[i - 1][1] + carry
        result_digits.append(total % 10)
        carry = total // 10
    # Leftmost diagonal: tens of the first bone, plus final carry.
    total = pairs[0][0] + carry
    while total > 0:
        result_digits.append(total % 10)
        total //= 10
    value = 0
    for d in reversed(result_digits):
        value = value * 10 + d
    return value


def multiply(multiplicand: int, multiplier: int) -> int:
    """Multiply via Napier's bones: rods, rows, diagonal sums.

    Each digit of the multiplier selects one bone-row read of the
    multiplicand; the partial products are shifted and added, exactly
    as the rods prescribe.
    """
    if multiplicand < 0 or multiplier < 0:
        raise ValueError("bones multiply non-negative integers")
    digits = [int(c) for c in str(multiplicand)]
    total = 0
    for shift, ch in enumerate(reversed(str(multiplier))):
        partial = _single_digit_product(digits, int(ch))
        total += partial * (10**shift)
    return total


def divide(dividend: int, divisor: int) -> Tuple[int, int]:
    """Bone-assisted long division: (quotient, remainder).

    Each quotient digit is chosen by reading the divisor's bone rows —
    the largest row multiple that fits the current remainder segment.
    """
    if divisor <= 0:
        raise ValueError("divisor must be positive")
    if dividend < 0:
        raise ValueError("dividend must be non-negative")
    divisor_digits = [int(c) for c in str(divisor)]
    quotient_digits: List[int] = []
    remainder = 0
    for ch in str(dividend):
        remainder = remainder * 10 + int(ch)
        # Read the divisor's bone rows to find the largest fitting digit.
        q = 0
        for candidate in range(1, 10):
            if _single_digit_product(divisor_digits, candidate) <= remainder:
                q = candidate
            else:
                break
        quotient_digits.append(q)
        remainder -= _single_digit_product(divisor_digits, q)
    quotient = int("".join(str(d) for d in quotient_digits)) if quotient_digits else 0
    return quotient, remainder


class LocationBoard:
    """Binary arithmetic as board positions (location arithmetic).

    A number is a multiset of counters on numbered squares; square ``p``
    is worth 2**p. The single rule of the board: two counters on one
    square are replaced by one counter on the next square up. Addition
    is placing both sets of counters and reducing; subtraction is
    borrowing down the board.
    """

    @staticmethod
    def to_counters(n: int) -> List[int]:
        """Bit positions holding counters for ``n``."""
        if n < 0:
            raise ValueError("board holds non-negative integers")
        return [p for p in range(n.bit_length()) if (n >> p) & 1]

    @staticmethod
    def from_counters(counters: List[int]) -> int:
        value = 0
        for p in counters:
            if p < 0:
                raise ValueError("board squares are non-negative")
            value += 1 << p
        return value

    @classmethod
    def _reduce(cls, counters: List[int]) -> List[int]:
        """Apply the doubling rule until no square holds two counters."""
        counts: dict[int, int] = {}
        for p in counters:
            counts[p] = counts.get(p, 0) + 1
        changed = True
        while changed:
            changed = False
            for p in sorted(counts):
                while counts[p] >= 2:
                    counts[p] -= 2
                    counts[p + 1] = counts.get(p + 1, 0) + 1
                    changed = True
        return [p for p, c in counts.items() if c]

    @classmethod
    def add(cls, a: int, b: int) -> int:
        """Add by placing both counter sets on the board and reducing."""
        return cls.from_counters(cls._reduce(cls.to_counters(a) + cls.to_counters(b)))

    @classmethod
    def subtract(cls, a: int, b: int) -> int:
        """Subtract by borrowing: a counter breaks into two below."""
        if b > a:
            raise ValueError("board subtraction needs a >= b")
        counts: dict[int, int] = {}
        for p in cls.to_counters(a):
            counts[p] = counts.get(p, 0) + 1
        for p in cls.to_counters(b):
            if counts.get(p, 0) == 0:
                # Borrow: one counter at q becomes one counter at each
                # square p..q-1 (2**q = sum(p..q-1 of 2**r) + 2**p, and
                # the created p-counter is the change) — net exactly -2**p.
                q = p + 1
                while counts.get(q, 0) == 0:
                    q += 1
                counts[q] -= 1
                for r in range(p, q):
                    counts[r] = counts.get(r, 0) + 1
            else:
                counts[p] -= 1
        return cls.from_counters([p for p, c in counts.items() for _ in range(c)])

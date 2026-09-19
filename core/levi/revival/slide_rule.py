"""The slide rule: multiplication by adding logarithms on a stick.

Studied from: pre-digital-computation-20260916 / report.md (Beat A #6)

The mechanism: a value's position on the rule is proportional to the
logarithm of its mantissa. Sliding one logarithmic scale against another
adds positions, which multiplies values; the cursor reads the mantissa
of the result. The rule has no notion of magnitude — the operator must
track the exponent (the power of ten) separately, in their head.

That limitation is the discipline: every slide-rule computation ends
with an explicit human estimate of scale, which makes order-of-magnitude
errors nearly impossible to commit blindly.

What this module models:
- ``mantissa_exponent``: split any nonzero value into mantissa in
  [1, 10) and an integer exponent.
- ``SlideRule``: position arithmetic on the C/D scales (multiply,
  divide), the A/B scales (square, square root via halved/doubled
  positions), and the "off the end" wrap flag — when the log sum runs
  past 1.0 the cursor leaves the scale and the operator must add one to
  their exponent estimate (real slide-rule behavior).
- ``Reading``: mantissa + operator-supplied exponent assembled into a
  value, with a cursor-resolution error bound.

Honest limits: this is exact floating-point arithmetic dressed in the
rule's geometry, not a physical simulation — a real stick reads to about
3 significant figures and the error bound below is a stated model of
cursor resolution, not a measured property. No network, stdlib only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple


ORIGIN = "levi-revival/slide-rule"

# A real cursor reads a 25 cm scale to roughly half a millimeter, which
# is about 1 part in 500 of the log range — modelled here as a relative
# error bound on the mantissa reading.
CURSOR_RELATIVE_ERROR = 0.002


def mantissa_exponent(value: float) -> Tuple[float, int]:
    """Split ``value`` into (mantissa in [1, 10), integer exponent)."""
    if value == 0.0:
        raise ValueError("zero has no mantissa/exponent split")
    if not math.isfinite(value):
        raise ValueError("value must be finite")
    exponent = math.floor(math.log10(abs(value)))
    mantissa = abs(value) / (10.0**exponent)
    # Guard the floating-point edge where mantissa lands exactly on 10.
    if mantissa >= 10.0:
        mantissa /= 10.0
        exponent += 1
    return mantissa, exponent


@dataclass(frozen=True)
class MantissaProduct:
    """Result of position arithmetic: a mantissa plus a wrap flag.

    ``wrap`` is True when the summed log position ran past the end of
    the scale (product of mantissas >= 10): on a real rule the cursor
    falls off the right end and the operator adds 1 to the exponent
    estimate. For division, wrap means the difference went negative and
    the operator subtracts 1.
    """

    mantissa: float
    wrap: bool


@dataclass(frozen=True)
class Reading:
    """A finished reading: mantissa from the rule, exponent from the human."""

    mantissa: float
    exponent: int

    def value(self) -> float:
        """Assemble the number. The exponent is the operator's estimate."""
        return self.mantissa * (10.0**self.exponent)

    def error_bound(self) -> float:
        """Half-width of the cursor-resolution error band on value()."""
        return abs(self.value()) * CURSOR_RELATIVE_ERROR


class SlideRule:
    """C/D scales for multiply/divide, A/B scales for square/root."""

    # -- scale geometry -------------------------------------------------
    @staticmethod
    def position(mantissa: float) -> float:
        """Position of a mantissa on the scale, in [0, 1)."""
        if not 1.0 <= mantissa < 10.0:
            raise ValueError("mantissa must lie in [1, 10)")
        return math.log10(mantissa)

    @staticmethod
    def value_at(position: float) -> float:
        """Mantissa read at a scale position."""
        if not 0.0 <= position < 1.0:
            raise ValueError("position must lie in [0, 1)")
        return 10.0**position

    # -- C/D: multiply and divide ---------------------------------------
    def multiply(self, a: float, b: float) -> MantissaProduct:
        """Mantissa of a*b via added log positions.

        Operands are reduced to mantissas (the rule never sees the
        exponent); ``wrap`` tells the operator to adjust the exponent
        estimate by +1.
        """
        ma, _ = mantissa_exponent(a)
        mb, _ = mantissa_exponent(b)
        total = self.position(ma) + self.position(mb)
        wrap = total >= 1.0
        if wrap:
            total -= 1.0
        return MantissaProduct(mantissa=self.value_at(total), wrap=wrap)

    def divide(self, a: float, b: float) -> MantissaProduct:
        """Mantissa of a/b via subtracted log positions.

        ``wrap`` here means the position difference went below 0 and the
        operator must subtract 1 from the exponent estimate.
        """
        ma, _ = mantissa_exponent(a)
        mb, _ = mantissa_exponent(b)
        diff = self.position(ma) - self.position(mb)
        wrap = diff < 0.0
        if wrap:
            diff += 1.0
        return MantissaProduct(mantissa=self.value_at(diff), wrap=wrap)

    # -- A/B: square and square root ------------------------------------
    def square(self, a: float) -> MantissaProduct:
        """Mantissa of a**2: doubled log position, wrapped into [0, 1)."""
        ma, _ = mantissa_exponent(a)
        total = 2.0 * self.position(ma)
        wrap = total >= 1.0
        if wrap:
            total -= 1.0
        return MantissaProduct(mantissa=self.value_at(total), wrap=wrap)

    def sqrt(self, a: float) -> float:
        """Mantissa of sqrt(a): halved log position.

        No wrap flag is needed: the halved position always lands on the
        scale, which is exactly why root extraction is pleasant on a
        rule — the operator only adjusts the exponent estimate by hand.
        """
        ma, _ = mantissa_exponent(a)
        return self.value_at(self.position(ma) / 2.0)

    # -- assembling a finished reading ----------------------------------
    @staticmethod
    def read(mantissa_product: MantissaProduct, exponent: int) -> Reading:
        """Combine a rule result with the operator's exponent estimate.

        ``exponent`` is the human's magnitude estimate for the true
        result; add +1 when ``mantissa_product.wrap`` is True (multiply /
        square) or -1 for a wrapped division.
        """
        return Reading(mantissa=mantissa_product.mantissa, exponent=exponent)

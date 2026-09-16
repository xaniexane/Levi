"""Honest precision: the slide-rule discipline.

Slide-rule operators knew their answers carried about three honest digits
and never claimed a fourth. The spreadsheet era prints fifteen false digits
from a float that earned two. This module refuses false precision:

- ``to_sigfigs(value, sig)`` rounds to n significant figures (ROUND_HALF_EVEN).
- ``format_sigfigs(value, sig)`` renders exactly n significant figures.
- ``sigfigs_in(text)`` counts the significant figures of a decimal literal,
  with the documented ambiguity rule: trailing zeros in an integer with no
  decimal point are NOT counted (e.g. "1200" -> 2); add a decimal point to
  claim them ("1200." -> 4).

Rule for LEVI: any number reported to a human passes through to_sigfigs
with the sig count its computation actually earned. Exact integer counts
(inventory, test tallies) are exact and need no rounding.
"""

from __future__ import annotations

from decimal import Decimal, localcontext, ROUND_HALF_EVEN


def _require_sig(sig: int) -> int:
    if isinstance(sig, bool) or not isinstance(sig, int) or sig < 1:
        raise ValueError("sig must be a positive int, got %r" % (sig,))
    return sig


def to_sigfigs(value: float, sig: int) -> float:
    """Round value to sig significant figures. 0 stays 0."""
    _require_sig(sig)
    if value == 0:
        return 0.0
    with localcontext() as ctx:
        ctx.prec = sig
        ctx.rounding = ROUND_HALF_EVEN
        return float(+Decimal(str(value)))


def format_sigfigs(value: float, sig: int) -> str:
    """Render value with exactly sig significant figures."""
    _require_sig(sig)
    if value == 0:
        return "0." + "0" * (sig - 1) if sig > 1 else "0"
    with localcontext() as ctx:
        ctx.prec = sig
        ctx.rounding = ROUND_HALF_EVEN
        d = +Decimal(str(value))
        # Quantum for sig significant figures: 10**(adj - sig + 1),
        # where adj is the exponent of the most significant digit.
        # (Single-digit-coefficient quantum: "1.0E+n" trips InvalidOperation.)
        quantum = Decimal("1E%d" % (d.adjusted() - sig + 1))
        d = d.quantize(quantum)
    return format(d, "f")


def sigfigs_in(text: str) -> int:
    """Count significant figures in a decimal literal string.

    Ambiguity rule: trailing zeros in an integer without a decimal point
    are not counted ("1200" -> 2; "1200." -> 4; "0.00300" -> 3).
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("sigfigs_in needs a non-empty decimal literal string")
    s = text.strip().lower().lstrip("+-")
    if "e" in s:
        s = s.split("e", 1)[0]
    if not s or any(c not in "0123456789." for c in s) or s.count(".") > 1:
        raise ValueError("not a decimal literal: %r" % (text,))
    s = s.lstrip("0")
    if s.startswith("."):
        s = "0" + s
    if s == "" or s == "." or set(s) <= {".", "0"}:
        return 1  # "0", "0.0", "000" — one significant zero by convention
    if "." in s:
        int_part, frac_part = s.split(".", 1)
        int_part = int_part.lstrip("0")
        if int_part:
            return len(int_part) + len(frac_part)
        # 0.xxx: leading fractional zeros are placeholders
        frac_stripped = frac_part.lstrip("0")
        return len(frac_stripped)
    # integer with no decimal point: trailing zeros are ambiguous -> not counted
    return len(s.rstrip("0")) or 1


def honest_report(value: float, sig: int) -> str:
    """One call for reports: format_sigfigs plus the earned-precision note."""
    return "%s  (%d significant figures)" % (format_sigfigs(value, sig), sig)

"""Casting out nines and elevens: the desk-machine digit rituals.

Every consequential integer computation gets a second, nearly-free,
independent proof: the digit-sum of the operands must agree (mod 9, or mod 11
with alternating sums) with the digit-sum of the claimed result.

Honest limits, stated up front (the ritual is a net, not a proof):
- cast-out-nines catches ~8/9 of random errors but NEVER catches digit
  transpositions (12 and 21 have the same digit sum).
- cast-out-elevens catches all single adjacent transpositions and most
  shifted partial products, but it is only slightly harder, not infallible.
- a passing check never proves correctness; a failing check proves an error.
"""

from __future__ import annotations

from typing import Iterable, List

from .receipts import VerificationReceipt


def _require_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("%s must be an int, got %r" % (name, type(value).__name__))
    return value


def nines(n: int) -> int:
    """Cast out nines: repeated digit sum of |n|, 9 mapped to 0. Range 0..8."""
    _require_int(n, "n")
    total = 0
    for ch in str(abs(n)):
        total += ord(ch) - 48
    return total % 9


def elevens(n: int) -> int:
    """Cast out elevens: alternating digit sum of |n|, mod 11. Range 0..10.

    Transposition-proof: swapping two adjacent digits always changes this
    value (unless the swapped digits are equal).
    """
    _require_int(n, "n")
    digits = [ord(ch) - 48 for ch in str(abs(n))]
    alt = sum(d if i % 2 == 0 else -d for i, d in enumerate(reversed(digits)))
    return alt % 11


def check_sum(terms: Iterable[int], claimed: int) -> VerificationReceipt:
    """Verify sum(terms) == claimed by cast-out-nines."""
    terms = [_require_int(t, "term") for t in terms]
    _require_int(claimed, "claimed")
    expected = sum(nines(t) for t in terms) % 9
    got = nines(claimed)
    ok = expected == got
    return VerificationReceipt(
        ok=ok,
        method="cast-out-nines",
        detail=(
            "digit-root of %d terms is %d; digit-root of claimed %d is %d"
            % (len(terms), expected, claimed, got)
        ),
        expected=str(expected),
        got=str(got),
    )


def check_product_nines(a: int, b: int, claimed: int) -> VerificationReceipt:
    """Verify a * b == claimed by cast-out-nines."""
    _require_int(a, "a")
    _require_int(b, "b")
    _require_int(claimed, "claimed")
    expected = (nines(a) * nines(b)) % 9
    got = nines(claimed)
    ok = expected == got
    return VerificationReceipt(
        ok=ok,
        method="cast-out-nines",
        detail=(
            "digit-root(%d)*digit-root(%d) mod 9 is %d; "
            "digit-root of claimed %d is %d" % (a, b, expected, claimed, got)
        ),
        expected=str(expected),
        got=str(got),
    )


def check_product_elevens(a: int, b: int, claimed: int) -> VerificationReceipt:
    """Verify a * b == claimed by cast-out-elevens (transposition-aware)."""
    _require_int(a, "a")
    _require_int(b, "b")
    _require_int(claimed, "claimed")
    expected = (elevens(a) * elevens(b)) % 11
    got = elevens(claimed)
    ok = expected == got
    return VerificationReceipt(
        ok=ok,
        method="cast-out-elevens",
        detail=(
            "alt-sum(%d)*alt-sum(%d) mod 11 is %d; "
            "alt-sum of claimed %d is %d" % (a, b, expected, claimed, got)
        ),
        expected=str(expected),
        got=str(got),
    )


def check_product(a: int, b: int, claimed: int) -> List[VerificationReceipt]:
    """Both rituals at once: nines first (cheap), elevens second (strict)."""
    return [check_product_nines(a, b, claimed), check_product_elevens(a, b, claimed)]

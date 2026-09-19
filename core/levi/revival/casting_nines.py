"""Human-operable checksums: casting out nines (and elevens).

Studied from: precompute-hunt-20260915, report.md [Find 1, LOAD-BEARING].

Inspired by the *shape* of casting out nines: sum the digits of a number
repeatedly and require both sides of a computation to agree modulo 9 — a
second, nearly-free, independent computation path a human can run with
pencil and paper. Casting out elevens (alternating digit sum) additionally
catches adjacent transpositions, which nines misses. This is an original,
from-scratch implementation for LEVI.

The core is :func:`check`, which verifies ``a op b = claimed`` by
comparing modular residues instead of recomputing the full arithmetic.
:func:`cast_out` exposes the raw residue computation for either modulus.

Honest limits: a passing check is *evidence*, not proof — mod 9 misses
transpositions and any error that is a multiple of 9; mod 11 misses
errors that are multiples of 11. A failed check is conclusive (the
claimed result is wrong); a passed check is merely consistent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict

ORIGIN = "levi-revival/casting-nines"


class CheckError(Exception):
    """Base class for checksum failures."""


def cast_out(value: int, modulus: int = 9) -> int:
    """Reduce ``value`` to its casting residue.

    ``modulus=9`` sums decimal digits repeatedly (digital root mod 9).
    ``modulus=11`` uses the alternating digit sum, which is what catches
    adjacent transpositions.
    """
    if modulus not in (9, 11):
        raise CheckError("casting supports modulus 9 and 11 only")
    n = abs(int(value))
    if modulus == 9:
        while n >= 9:
            n = sum(int(d) for d in str(n))
        return n % 9
    # alternating sum of digits, units place positive
    digits = [int(d) for d in str(n)][::-1]
    return sum(d if i % 2 == 0 else -d for i, d in enumerate(digits)) % 11


def digital_root(value: int) -> int:
    """Classic digital root: repeated digit sum down to a single digit."""
    n = abs(int(value))
    while n >= 10:
        n = sum(int(d) for d in str(n))
    return n or 0


@dataclass(frozen=True)
class Receipt:
    """The evidence trail for one checked computation."""

    operation: str
    operands: tuple
    claimed: int
    modulus: int
    left_residue: int
    right_residue: int
    agrees: bool

    def explain(self) -> str:
        verdict = "AGREES" if self.agrees else "DISAGREES"
        return (
            f"cast out {self.modulus}: {self.operation}{self.operands} "
            f"claimed {self.claimed} -> residues "
            f"{self.left_residue} vs {self.right_residue} [{verdict}]"
        )


_OPERATIONS: Dict[str, Callable[[int, int], int]] = {
    "add": lambda a, b: a + b,
    "sub": lambda a, b: a - b,
    "mul": lambda a, b: a * b,
    "pow": lambda a, b: a**b,
}


def check(operation: str, a: int, b: int, claimed: int, modulus: int = 9) -> Receipt:
    """Verify ``a <operation> b = claimed`` via modular residues.

    Both operand residues are combined with the same operation under the
    modulus and compared against the residue of the claimed result.
    """
    if operation not in _OPERATIONS:
        raise CheckError(
            f"unsupported operation {operation!r}; use one of {sorted(_OPERATIONS)}"
        )
    op = _OPERATIONS[operation]
    left = op(cast_out(a, modulus), cast_out(b, modulus)) % modulus
    right = cast_out(claimed, modulus)
    return Receipt(
        operation=operation,
        operands=(a, b),
        claimed=claimed,
        modulus=modulus,
        left_residue=left,
        right_residue=right,
        agrees=left == right,
    )


def check_both(operation: str, a: int, b: int, claimed: int) -> Dict[int, Receipt]:
    """Run the check under mod 9 *and* mod 11; returns both receipts.

    The mod-11 receipt is the transposition catcher: a claimed result
    whose digits were merely swapped will still agree mod 9 but fail
    mod 11.
    """
    return {m: check(operation, a, b, claimed, modulus=m) for m in (9, 11)}


def transposition_pairs(value: int) -> list:
    """All numbers formed by swapping one adjacent digit pair of ``value``.

    Useful for demonstrating which modulus catches the swap.
    """
    digits = list(str(abs(int(value))))
    out = []
    for i in range(len(digits) - 1):
        swapped = digits.copy()
        swapped[i], swapped[i + 1] = swapped[i + 1], swapped[i]
        if swapped != digits:
            out.append(int("".join(swapped)))
    return out

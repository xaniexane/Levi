"""Cotes quadrature tables — the table is the program.

Studied from: pre-digital-computation-20260916, report.md [Beat B #17,
USEFUL PATTERN] — Cotes quadrature tables.

The mechanism, functionally: pick ``n`` equally spaced nodes on the
integration interval, and precompute — once, exactly, in rationals —
the integral of each Lagrange basis polynomial. From then on,
integrating *any* function is just a weighted sum of its samples:
``integral ≈ (b-a) * sum(w_i * f(x_i))``. The "program" is the weight
table; evaluation is a dot product. This module builds the tables from
scratch by solving the moment equations (integrate x^k for
k = 0..n-1, match against node sums) with exact rational arithmetic,
so the tables it emits are the true closed Newton–Cotes weights, not
hard-coded folklore.

Key operations: ``cotes_table(n)`` builds the ``n``-point table on
[0, 1] (weights as Fractions, exact); ``integrate(f, a, b, n)`` maps
the table onto any interval and returns a float; ``table_text(n)``
renders the table for inspection; known rules surface as the tables
themselves (n=2 trapezoid, n=3 Simpson, n=5 Boole).

Honesty: equally spaced nodes only — high-order Newton–Cotes weights
go negative past n=7 and can be unstable, so tables are offered for
n=1..8 with a documented warning above n=7. Exact only for polynomials
of degree ≤ n-1 (n even) or ≤ n (n odd); everything else is an
approximation, reported as such.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Callable, List, Tuple

ORIGIN = "levi-revival/quadrature-tables"

MAX_TABLE = 8  # Newton–Cotes goes oscillatory past n=7; cap at 8.


def _solve_rational(a: List[List[Fraction]], b: List[Fraction]) -> List[Fraction]:
    """Gaussian elimination over Fractions (small systems only)."""
    n = len(a)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = next(i for i in range(col, n) if m[i][col] != 0)
        m[col], m[piv] = m[piv], m[col]
        for i in range(n):
            if i != col and m[i][col] != 0:
                factor = m[i][col] / m[col][col]
                for j in range(col, n + 1):
                    m[i][j] -= factor * m[col][j]
    return [m[i][n] / m[i][i] for i in range(n)]


class CotesTable:
    """A precomputed n-point Newton–Cotes weight table on [0, 1]."""

    def __init__(self, n: int):
        if not 1 <= n <= MAX_TABLE:
            raise ValueError(f"n must be in 1..{MAX_TABLE}")
        self.n = n
        # Nodes x_i = i/(n-1) (n=1 is the midpoint rule: node at 1/2).
        self.nodes: List[Fraction] = (
            [Fraction(1, 2)] if n == 1 else [Fraction(i, n - 1) for i in range(n)]
        )
        self.weights: List[Fraction] = self._build()

    def _build(self) -> List[Fraction]:
        if self.n == 1:
            return [Fraction(1)]
        n = self.n
        # Moment equations: sum_i w_i * x_i^k = 1/(k+1) for k < n.
        a = [[self.nodes[i] ** k for i in range(n)] for k in range(n)]
        b = [Fraction(1, k + 1) for k in range(n)]
        return _solve_rational(a, b)

    def weight_sum(self) -> Fraction:
        """Weights must sum to exactly 1 on [0, 1]."""
        return sum(self.weights, Fraction(0))

    def __repr__(self) -> str:  # pragma: no cover - display helper
        return f"CotesTable(n={self.n})"


_tables: dict = {}


def cotes_table(n: int) -> CotesTable:
    """Fetch (building once) the n-point table."""
    if n not in _tables:
        _tables[n] = CotesTable(n)
    return _tables[n]


def integrate(
    f: Callable[[float], float], a: float, b: float, n: int = 5
) -> Tuple[float, str]:
    """Integrate f over [a, b] with the n-point table.

    Returns ``(value, note)`` where note names the rule degree the
    result is exact for — an honest statement of what the number is.
    """
    if a == b:
        return 0.0, "empty interval"
    table = cotes_table(n)
    width = b - a
    total = sum(
        w * f(a + float(x) * width)
        for w, x in zip(table.weights, table.nodes, strict=True)
    )
    value = float(width * total)
    deg = n if n % 2 == 1 else n - 1
    note = f"exact for polynomials of degree <= {deg}; approximation otherwise"
    if n > 7:
        note += " (warning: high-order Newton-Cotes can be unstable)"
    return value, note


def table_text(n: int) -> str:
    """Render the weight table for inspection."""
    t = cotes_table(n)
    lines = [f"Newton-Cotes n={n} on [0,1]:"]
    for x, w in zip(t.nodes, t.weights, strict=True):
        lines.append(f"  x={float(x):.4f}  w={w}  (~{float(w):.6f})")
    lines.append(f"  sum(w)={t.weight_sum()}")
    return "\n".join(lines)


def demo() -> Tuple[str, float]:
    """Show the Simpson table (n=3) and integrate x^2 over [0, 1]."""
    val, _ = integrate(lambda x: x * x, 0.0, 1.0, n=3)
    return table_text(3), val

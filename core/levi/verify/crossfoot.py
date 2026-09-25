"""Ledger crossfooting: the bookkeeper's two-directional proof.

A crossfoot table is a matrix of ints whose last row holds the column totals,
whose last column holds the row totals, and whose bottom-right cell is the
grand total. Three independent tallies must all agree:

1. every data row sums to its stated row total,
2. every data column sums to its stated column total,
3. the grand total equals the sum of row totals and the sum of column totals.

Any disagreement names the exact row or column — the ritual points at the
offending line, it does not just say "wrong".
"""

from __future__ import annotations

from typing import List, Sequence

from .receipts import VerificationReceipt


def _require_int_cell(value: object, row: int, col: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(
            "crossfoot cell [%d][%d] must be an int, got %r"
            % (row, col, type(value).__name__)
        )
    return value


def crossfoot(table: Sequence[Sequence[int]]) -> VerificationReceipt:
    """Verify a crossfoot table. Returns a receipt naming every discrepancy."""
    rows: List[List[int]] = [
        [_require_int_cell(v, r, c) for c, v in enumerate(row)]
        for r, row in enumerate(table)
    ]
    if len(rows) < 2 or any(len(r) < 2 for r in rows):
        raise ValueError("crossfoot needs at least a 2x2 table (data + totals row/col)")
    width = len(rows[0])
    if any(len(r) != width for r in rows):
        raise ValueError("crossfoot table is ragged: rows have unequal lengths")

    n_data_rows = len(rows) - 1
    n_data_cols = width - 1
    problems: List[str] = []

    # 1. row checks: data row sums must equal the stated row total.
    for r in range(n_data_rows):
        actual = sum(rows[r][:n_data_cols])
        stated = rows[r][n_data_cols]
        if actual != stated:
            problems.append("row %d sums to %d but states %d" % (r, actual, stated))

    # 2. column checks: data column sums must equal the stated column total.
    for c in range(n_data_cols):
        actual = sum(rows[r][c] for r in range(n_data_rows))
        stated = rows[n_data_rows][c]
        if actual != stated:
            problems.append("column %d sums to %d but states %d" % (c, actual, stated))

    # 3. grand total must agree from both directions.
    grand = rows[n_data_rows][n_data_cols]
    by_rows = sum(rows[r][n_data_cols] for r in range(n_data_rows))
    by_cols = sum(rows[n_data_rows][c] for c in range(n_data_cols))
    if grand != by_rows:
        problems.append(
            "grand total %d disagrees with row totals %d" % (grand, by_rows)
        )
    if grand != by_cols:
        problems.append(
            "grand total %d disagrees with column totals %d" % (grand, by_cols)
        )

    ok = not problems
    return VerificationReceipt(
        ok=ok,
        method="crossfoot",
        detail=(
            "all %d row totals, %d column totals, and the grand total agree"
            % (n_data_rows, n_data_cols)
            if ok
            else "; ".join(problems)
        ),
        expected=None,
        got=None,
    )

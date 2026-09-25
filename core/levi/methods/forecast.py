"""Richardson's forecast factory: cellular computation with barrier sync.

Origin: 1922, *Weather Prediction by Numerical Process*. Lewis Fry
Richardson — after spending ~1,000 hours hand-computing a 6-hour forecast
(for Munich, May 20 1910, and getting it wrong) — proposed a "forecast
factory": a vast hall where 64,000 human computers, each solving one cell
of the atmosphere's equations with slide rules, would be coordinated by a
conductor. Each computer handled one map sector; pressure (red cells) and
winds/momenta (white cells) were signaled to neighbors racing ahead or
lagging behind via "night signs" (message passing); a director in a central
pulpit broadcast tempo with blue and rosy beams (a broadcast channel /
barrier synchronization). Lynch's analysis notes the estimate was short —
~204,800 would have been needed globally, and even that computed weather
only as fast as it happened. The architecture is what matters: Richardson
specified an MPP programming model before the machine.

What it is in LEVI: a cellular computer. A grid of cells; each step every
cell computes from its own value plus its neighbors' messages, exchanges
with its neighbors, then a broadcast barrier sync advances the epoch for
all cells at once — nobody races ahead, nobody lags. The director's tempo
beam is ``broadcast()``: one message delivered to every cell in the same
epoch. A diffusion computation converges over steps: variance collapses
while the total is conserved.

Honesty label: LOAD-BEARING — domain decomposition + neighbor exchange +
broadcast barrier sync is a concrete parallel-computing primitive.

Deny-closed inputs: non-positive or non-integer grid dimensions,
out-of-range cell coordinates, non-numeric seed values, non-positive or
non-integer step counts, and empty broadcast messages are all rejected with
ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["CellularComputer", "ConvergenceReport"]


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _clean(value: str, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{what} must be a non-empty string")
    return value.strip()


@dataclass
class ConvergenceReport:
    steps: int
    initial_variance: float
    final_variance: float
    total: float  # conserved sum of all cells
    converged: bool
    broadcasts: list = field(default_factory=list)


class CellularComputer:
    """Richardson's hall: a grid of cells, neighbor messages, tempo beams.

    Each ``step()`` is: every cell computes from its own value plus its
    four neighbors' messages (missing neighbors at the edge count as the
    cell itself, so the total is conserved), all cells exchange at once,
    then the broadcast barrier advances the epoch for everyone together.
    """

    def __init__(self, rows: int, cols: int) -> None:
        for name, dim in (("rows", rows), ("cols", cols)):
            if not isinstance(dim, int) or isinstance(dim, bool) or dim < 1:
                raise ValueError(f"{name} must be a positive integer, got {dim!r}")
        self._rows = rows
        self._cols = cols
        self._grid = [[0.0 for _ in range(cols)] for _ in range(rows)]
        self._epoch = 0
        self._mailbox: dict[tuple[int, int], list[str]] = {
            (r, c): [] for r in range(rows) for c in range(cols)
        }
        self._broadcasts: list[str] = []

    def seed(self, row: int, col: int, value: float) -> None:
        """Set a cell's initial value before the factory starts."""
        self._require_cell(row, col)
        if not _is_number(value):
            raise ValueError(f"seed value must be a number, got {value!r}")
        self._grid[row][col] = float(value)

    def value(self, row: int, col: int) -> float:
        self._require_cell(row, col)
        return self._grid[row][col]

    def epoch(self) -> int:
        return self._epoch

    def broadcast(self, message: str) -> int:
        """The director's tempo beam: one message to every cell at once."""
        message = _clean(message, "broadcast message")
        for cell in self._mailbox:
            self._mailbox[cell].append(f"epoch-{self._epoch}: {message}")
        self._broadcasts.append(message)
        return len(self._mailbox)

    def step(self) -> int:
        """One factory beat: compute, exchange, barrier sync."""
        new = [[0.0 for _ in range(self._cols)] for _ in range(self._rows)]
        for r in range(self._rows):
            for c in range(self._cols):
                own = self._grid[r][c]
                neighbors = [
                    self._grid[nr][nc]
                    for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1))
                    if 0 <= nr < self._rows and 0 <= nc < self._cols
                ]
                # Missing neighbors count as the cell itself: nobody races
                # ahead, nobody lags — the total is conserved exactly.
                vals = [own] * (5 - len(neighbors)) + neighbors
                new[r][c] = sum(vals) / 5.0
        self._grid = new
        # Barrier sync: the epoch advances for all cells at once.
        self._epoch += 1
        return self._epoch

    def run(self, steps: int, tolerance: float = 1e-6) -> ConvergenceReport:
        """Run the factory and report convergence."""
        if not isinstance(steps, int) or isinstance(steps, bool) or steps < 1:
            raise ValueError(f"steps must be a positive integer, got {steps!r}")
        if not _is_number(tolerance) or tolerance < 0:
            raise ValueError("tolerance must be a non-negative number")
        initial = self._variance()
        for _ in range(steps):
            self.step()
        final = self._variance()
        return ConvergenceReport(
            steps=steps,
            initial_variance=initial,
            final_variance=final,
            total=self._total(),
            converged=final < tolerance,
            broadcasts=list(self._broadcasts),
        )

    def inbox(self, row: int, col: int) -> list[str]:
        """The tempo messages a cell has received."""
        self._require_cell(row, col)
        return list(self._mailbox[(row, col)])

    # -- internals -------------------------------------------------------------
    def _require_cell(self, row: int, col: int) -> None:
        for name, idx, dim in (("row", row, self._rows), ("col", col, self._cols)):
            if not isinstance(idx, int) or isinstance(idx, bool) or not 0 <= idx < dim:
                raise ValueError(
                    f"{name} {idx!r} out of range for a {self._rows}x{self._cols} grid"
                )

    def _variance(self) -> float:
        flat = [v for row in self._grid for v in row]
        mean = sum(flat) / len(flat)
        return sum((v - mean) ** 2 for v in flat) / len(flat)

    def _total(self) -> float:
        return sum(v for row in self._grid for v in row)

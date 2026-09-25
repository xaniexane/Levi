"""Michelson-style harmonic analyzer: weighted sums of sinusoids, both ways.

Studied from: pre-digital-computation-20260916 report.md
[Beat B #5, USEFUL PATTERN] — cone-pulley gears at 1..20x speed with a
summing lever adding weighted sinusoids.

The machine is a bank of geared oscillators. Each harmonic ``n`` has a
cone-pulley gear spinning at ``n`` times the base speed; the amplitude
weight and phase offset are set like stops on a lever, and a summing
lever adds every contribution into one output shaft. Two operations:

* **synthesize** — set harmonic weights and read the summed waveform.
* **analyze** — trace a sampled curve and recover the weights that
  best explain it (the analyzer run in reverse), by least-squares
  projection onto the cosine/sine basis.

stdlib-only. No network. Honest limits: the analysis step is a
numerical least-squares fit over discrete samples, so content above
the sampling Nyquist rate aliases, and the fit residual is reported
rather than hidden.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple


ORIGIN = "levi-revival/harmonic-analyzer"

MAX_HARMONIC = 20


@dataclass
class HarmonicBank:
    """One geared oscillator per harmonic, feeding one summing lever.

    ``weights[n]`` is ``(amplitude, phase)`` for harmonic ``n`` in
    ``1..MAX_HARMONIC``; the ``n = 0`` entry holds the DC offset as
    ``(offset, 0.0)``.
    """

    weights: Dict[int, Tuple[float, float]] = field(default_factory=dict)

    def set_harmonic(self, n: int, amplitude: float, phase: float = 0.0) -> None:
        """Set the cone-pulley stop for harmonic ``n`` (like engaging a gear)."""
        if not 1 <= n <= MAX_HARMONIC:
            raise ValueError(f"harmonic must be 1..{MAX_HARMONIC}, got {n}")
        if amplitude < 0:
            raise ValueError("amplitude is a gear throw and cannot be negative")
        self.weights[n] = (amplitude, phase)

    def set_offset(self, value: float) -> None:
        """DC offset — the lever's rest position."""
        self.weights[0] = (value, 0.0)

    def output(self, t: float) -> float:
        """Read the summing lever at shaft angle ``t`` (radians)."""
        total = self.weights.get(0, (0.0, 0.0))[0]
        for n, (amp, phase) in self.weights.items():
            if n == 0:
                continue
            total += amp * math.cos(n * t + phase)
        return total

    def harmonics(self) -> List[int]:
        """Which gears are currently engaged."""
        return sorted(n for n in self.weights if n != 0)

    @staticmethod
    def analyze(
        samples: Sequence[Tuple[float, float]], max_harmonic: int = MAX_HARMONIC
    ) -> Tuple["HarmonicBank", Dict[str, float]]:
        """Recover harmonic weights from traced ``(t, y)`` samples.

        Least-squares projection onto ``{1, cos(nt), sin(nt)}`` solved
        through the normal equations. Returns the fitted bank plus a
        report with ``rms_residual`` and ``samples_used``. Content
        above the sample Nyquist rate aliases — the residual carries
        that warning honestly.
        """
        if not 1 <= max_harmonic <= MAX_HARMONIC:
            raise ValueError(f"max_harmonic must be 1..{MAX_HARMONIC}")
        if len(samples) < 2 * max_harmonic + 1:
            raise ValueError(
                f"need at least {2 * max_harmonic + 1} samples for "
                f"{max_harmonic} harmonics, got {len(samples)}"
            )

        # Design matrix columns: 1, cos(t), sin(t), cos(2t), sin(2t), ...
        cols: List[List[float]] = []
        cols.append([1.0 for _ in samples])
        for n in range(1, max_harmonic + 1):
            cols.append([math.cos(n * t) for t, _ in samples])
            cols.append([math.sin(n * t) for t, _ in samples])
        n_cols = len(cols)
        n_rows = len(samples)

        # Normal equations: (A^T A) x = A^T y
        ata = [[0.0] * n_cols for _ in range(n_cols)]
        aty = [0.0] * n_cols
        ys = [y for _, y in samples]
        for i in range(n_cols):
            ci = cols[i]
            aty[i] = sum(ci[k] * ys[k] for k in range(n_rows))
            for j in range(i, n_cols):
                s = sum(ci[k] * cols[j][k] for k in range(n_rows))
                ata[i][j] = s
                ata[j][i] = s

        coeffs = _solve(ata, aty)

        bank = HarmonicBank()
        bank.set_offset(coeffs[0])
        for n in range(1, max_harmonic + 1):
            a = coeffs[2 * n - 1]  # cos coefficient
            b = coeffs[2 * n]  # sin coefficient
            amp = math.hypot(a, b)
            phase = math.atan2(-b, a)  # a cos + b sin = amp cos(nt + phase)
            if amp > 1e-12:
                bank.set_harmonic(n, amp, phase)

        resid = sum((bank.output(t) - y) ** 2 for t, y in samples)
        report = {
            "rms_residual": math.sqrt(resid / n_rows),
            "samples_used": float(n_rows),
            "harmonics_fitted": float(max_harmonic),
        }
        return bank, report


def _solve(a: List[List[float]], b: List[float]) -> List[float]:
    """Gaussian elimination with partial pivoting (small, dense, local)."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-14:
            raise ValueError("singular normal equations: samples too sparse")
        m[col], m[piv] = m[piv], m[col]
        inv = 1.0 / m[col][col]
        for r in range(col + 1, n):
            factor = m[r][col] * inv
            for c in range(col, n + 1):
                m[r][c] -= factor * m[col][c]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (m[i][n] - sum(m[i][j] * x[j] for j in range(i + 1, n))) / m[i][i]
    return x

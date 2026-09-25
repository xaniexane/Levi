"""Terminal Fourier playground — Michelson's harmonic analyzer, LEVI-native.

Michelson's 1890s harmonic analyzer added sine waves with springs and
gears and *showed* Fourier synthesis happening. This module does the same
in a terminal: stack harmonic bars, watch the waveform, then decompose it
back with a pure-Python DFT (no numpy — stdlib only, offline always).

Convention: bars are (n, amp, phase) with the wave

    x(t) = sum(amp * cos(2*pi*n*t + phase)),  t in [0, 1)

and analyze() inverts exactly that convention.
"""

from __future__ import annotations

import math
from typing import List, Tuple

Bar = Tuple[int, float, float]  # (harmonic n, amplitude, phase in radians)


def bars_to_wave(bars: List[Bar], points: int = 61) -> List[float]:
    """Synthesize one period from harmonic bars: sum of amp*cos(2*pi*n*t+phase)."""
    if points <= 0:
        raise ValueError("points must be positive")
    wave = []
    for i in range(points):
        t = i / points
        x = 0.0
        for n, amp, phase in bars:
            if n < 0:
                raise ValueError("harmonic n must be non-negative")
            x += amp * math.cos(2.0 * math.pi * n * t + phase)
        wave.append(x)
    return wave


def analyze(samples: List[float], top_k: int = 5) -> List[Bar]:
    """Recover harmonic bars from one period of samples via pure-Python DFT.

    Returns the top_k harmonics sorted by amplitude, descending.
    Inverts bars_to_wave exactly: a wave built from bars round-trips.
    """
    n = len(samples)
    if n == 0:
        raise ValueError("need at least one sample")
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    found: List[Bar] = []
    for k in range(n // 2 + 1):
        re = 0.0
        im = 0.0
        for i, x in enumerate(samples):
            theta = 2.0 * math.pi * k * i / n
            re += x * math.cos(theta)
            im -= x * math.sin(theta)
        if k == 0:
            amp = abs(re) / n
            phase = 0.0
        else:
            amp = 2.0 * math.hypot(re, im) / n
            phase = math.atan2(im, re)
        found.append((k, amp, phase))
    found.sort(key=lambda b: b[1], reverse=True)
    return found[:top_k]


def plot_ascii(values: List[float], height: int = 11) -> str:
    """Waveform plot as ASCII art, height rows tall.

    A flat signal draws a midline instead of dividing by zero; the
    waveform is sampled to one column per value.
    """
    if height <= 0:
        raise ValueError("height must be positive")
    if not values:
        return ""
    lo, hi = min(values), max(values)
    span = hi - lo
    rows = []
    for r in range(height):
        line = []
        for v in values:
            if span == 0:
                row_of_v = height // 2
            else:
                row_of_v = int(round((hi - v) / span * (height - 1)))
            line.append("*" if row_of_v == r else " ")
        rows.append("".join(line).rstrip())
    return "\n".join(rows)

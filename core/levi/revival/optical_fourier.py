"""Optical Fourier processor — the lens as a 2-D Fourier transform.

Studied from: pre-digital-computation-20260916, report.md [Beat B #16,
USEFUL PATTERN] — optical Fourier processors.

The mechanism, functionally: a converging lens performs a two-dimensional
Fourier transform of the light field at its focal plane — instantly,
in parallel, for the whole image. Coherent-optical processors exploited
this for two decades to do SAR image formation and matched filtering:
put a filter (the Fourier transform of the template) at the focal
plane and the output plane shows the correlation of the scene with the
template, the brightest spot marking the match. The math identity is
the convolution theorem: correlation in the image domain is pointwise
multiplication in the Fourier domain.

This module is a small numerical analog of that pipeline, stdlib-only:
a radix-2 1-D FFT (pure Python, complex) lifted to 2-D transforms
(``dft2``/``idft2``); ``power_spectrum`` as the focal-plane intensity;
and ``matched_filter`` implementing the optical correlator — transform
scene and template, multiply by the conjugated template spectrum (the
"filter at the focal plane"), inverse-transform, and report the peak
location and strength. A naive ``direct_correlate`` is kept as the
ground-truth cross-check for tests.

Honesty: a discrete FFT on small grids, not optics and not a lens.
Pure-Python radix-2 means sizes are powers of two and modest grids
run in the tens of milliseconds — stated openly as a performance
limit, not a feature. No claim of SAR image formation; the pipeline
is correlation, the documented workhorse use.
"""

from __future__ import annotations

import cmath
import math
from typing import List, Sequence, Tuple

ORIGIN = "levi-revival/optical-fourier"

Grid = List[List[complex]]


def _is_pow2(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def fft1d(xs: Sequence[complex]) -> List[complex]:
    """Radix-2 Cooley–Tukey FFT. Length must be a power of two."""
    xs = list(xs)
    n = len(xs)
    if not _is_pow2(n):
        raise ValueError("fft1d length must be a power of two")
    if n == 1:
        return xs
    even = fft1d(xs[0::2])
    odd = fft1d(xs[1::2])
    out: List[complex] = [0j] * n
    for k in range(n // 2):
        tw = cmath.exp(-2j * math.pi * k / n) * odd[k]
        out[k] = even[k] + tw
        out[k + n // 2] = even[k] - tw
    return out


def ifft1d(xs: Sequence[complex]) -> List[complex]:
    """Inverse FFT via the conjugate trick."""
    xs = list(xs)
    n = len(xs)
    conj = fft1d([x.conjugate() for x in xs])
    return [x.conjugate() / n for x in conj]


def _check_grid(g: Grid) -> Tuple[int, int]:
    if not g or not g[0]:
        raise ValueError("grid must be non-empty")
    rows, cols = len(g), len(g[0])
    if any(len(r) != cols for r in g):
        raise ValueError("grid rows must be uniform")
    if not _is_pow2(rows) or not _is_pow2(cols):
        raise ValueError("grid dimensions must be powers of two")
    return rows, cols


def dft2(grid: Sequence[Sequence[float]]) -> Grid:
    """2-D Fourier transform — the "lens" of this module."""
    g = [[complex(v) for v in row] for row in grid]
    rows, cols = _check_grid(g)
    row_t = [fft1d(r) for r in g]
    out: Grid = [[0j] * cols for _ in range(rows)]
    for c in range(cols):
        col_t = fft1d([row_t[r][c] for r in range(rows)])
        for r in range(rows):
            out[r][c] = col_t[r]
    return out


def idft2(spec: Grid) -> Grid:
    """Inverse 2-D transform — the "second lens" back to image space."""
    rows, cols = _check_grid(spec)
    row_t = [ifft1d(r) for r in spec]
    out: Grid = [[0j] * cols for _ in range(rows)]
    for c in range(cols):
        col_t = ifft1d([row_t[r][c] for r in range(rows)])
        for r in range(rows):
            out[r][c] = col_t[r]
    return out


def power_spectrum(grid: Sequence[Sequence[float]]) -> List[List[float]]:
    """Focal-plane intensity: |F(u,v)|^2 of the input."""
    return [[abs(v) ** 2 for v in row] for row in dft2(grid)]


def direct_correlate(
    scene: Sequence[Sequence[float]], templ: Sequence[Sequence[float]]
) -> List[List[float]]:
    """Ground-truth cyclic cross-correlation (O(n^4) — for testing)."""
    rs, cs = len(scene), len(scene[0])
    rt, ct = len(templ), len(templ[0])
    out = [[0.0] * cs for _ in range(rs)]
    for r in range(rs):
        for c in range(cs):
            acc = 0.0
            for tr in range(rt):
                for tc in range(ct):
                    acc += scene[(r + tr) % rs][(c + tc) % cs] * templ[tr][tc]
            out[r][c] = acc
    return out


def matched_filter(
    scene: Sequence[Sequence[float]], templ: Sequence[Sequence[float]]
) -> Tuple[Tuple[int, int], float, List[List[float]]]:
    """Optical correlator: focal-plane filter then peak detection.

    Pads the template to the scene size, multiplies the scene spectrum
    by the conjugated template spectrum (the filter at the focal
    plane), inverse-transforms, and returns ``((row, col), strength,
    correlation_plane)`` — the brightest spot is where the template
    matches best.
    """
    rows, cols = len(scene), len(scene[0])
    if rows < len(templ) or cols < len(templ[0]):
        raise ValueError("template must fit inside the scene")
    padded = [[0.0] * cols for _ in range(rows)]
    for r, row in enumerate(templ):
        for c, v in enumerate(row):
            padded[r][c] = v
    fs = dft2(scene)
    ft = dft2(padded)
    prod = [
        [a * b.conjugate() for a, b in zip(r1, r2, strict=True)]
        for r1, r2 in zip(fs, ft, strict=True)
    ]
    plane = [[v.real for v in row] for row in idft2(prod)]
    best = (0, 0)
    for r in range(rows):
        for c in range(cols):
            if plane[r][c] > plane[best[0]][best[1]]:
                best = (r, c)
    return best, plane[best[0]][best[1]], plane


def demo() -> Tuple[Tuple[int, int], float]:
    """Find a 4x4 bright block hidden in an 8x8 scene."""
    scene = [[0.0] * 8 for _ in range(8)]
    for r in range(2, 6):
        for c in range(3, 7):
            scene[r][c] = 1.0
    templ = [[1.0] * 4 for _ in range(4)]
    loc, strength, _ = matched_filter(scene, templ)
    return loc, strength

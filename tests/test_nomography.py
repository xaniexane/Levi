"""Tests for levi.nomography — the SVG alignment-chart emitter.

Law->guard->prove: the collinearity invariant (L1) is checked as a property
over random triples, not just one example.
"""

from __future__ import annotations

import math
import random
import xml.etree.ElementTree as ET

import pytest

from levi.nomography import (
    Scale,
    addition_nomogram,
    isopleth_points,
    parallel_nomogram,
    solve_w,
)


def _addition_scales(f1, f2, f3, r1, r2, r3):
    return [
        Scale(0.0, f1, r1[0], r1[1], "u"),
        Scale(0.5, lambda w: f3(w) / 2.0, r3[0], r3[1], "w"),
        Scale(1.0, f2, r2[0], r2[1], "v"),
    ]


def _crosses_at_mid(p1, p2):
    # x=0.5 crossing of the line through p1 (x=0) and p2 (x=1)
    (x1, y1), (x2, y2) = p1, p2
    return y1 + (y2 - y1) * (0.5 - x1) / (x2 - x1)


def test_collinearity_identity_L1():
    rng = random.Random(20260927)
    scales = _addition_scales(lambda v: v, lambda v: v, lambda v: v,
                              (0, 10), (0, 10), (0, 20))
    for _ in range(50):
        u, v = rng.uniform(0, 10), rng.uniform(0, 10)
        w = u + v  # solves w = u + v
        pts = isopleth_points(scales, [u, w, v])
        assert _crosses_at_mid(pts[0], pts[2]) == pytest.approx(pts[1][1], abs=1e-9)


def test_collinearity_log_product_L1():
    # log a + log b = log c  <=>  a * b = c  (the slide-rule nomogram)
    rng = random.Random(7)
    scales = _addition_scales(math.log10, math.log10, math.log10,
                              (1, 100), (1, 100), (1, 10000))
    for _ in range(50):
        a, b = rng.uniform(1, 100), rng.uniform(1, 100)
        c = a * b
        pts = isopleth_points(scales, [a, c, b])
        assert _crosses_at_mid(pts[0], pts[2]) == pytest.approx(pts[1][1], abs=1e-9)


def test_solve_w_recovers_and_refuses_L2():
    assert solve_w(lambda x: x, 3.5, 0, 10) == pytest.approx(3.5)
    assert solve_w(lambda x: 2 * x + 1, 7.0, 0, 10) == pytest.approx(3.0)
    assert solve_w(lambda x: -x, -4.0, 0, 10) == pytest.approx(4.0)  # decreasing
    assert solve_w(lambda x: x, 99.0, 0, 10) is None  # out of range: no guess
    assert solve_w(lambda x: x, -1.0, 0, 10) is None


def test_ticks_span_range_L3():
    scales = [Scale(0.0, lambda v: v, 5, 15, "u", ticks=6),
              Scale(1.0, lambda v: v, 5, 15, "v", ticks=6)]
    svg = parallel_nomogram(scales)
    assert ">5<" in svg and ">15<" in svg
    # 2 axes + 12 tick marks
    assert svg.count("<line") == 2 + 12


def test_svg_wellformed_and_titled():
    svg = addition_nomogram(
        lambda v: v, lambda v: v, lambda v: v,
        (0, 10), (0, 10), (0, 20), ("u", "v", "w"),
        title="u + v = w", isopleth_uv=(3, 4),
    )
    ET.fromstring(svg)  # raises if malformed
    assert "u + v = w" in svg
    assert "crimson" in svg  # the isopleth line


def test_unsolvable_isopleth_draws_no_line():
    svg = addition_nomogram(
        lambda v: v, lambda v: v, lambda v: v,
        (0, 10), (0, 10), (0, 20), ("u", "v", "w"),
        isopleth_uv=(30, 40),  # w = 70, off the chart: honest omission
    )
    ET.fromstring(svg)
    assert "crimson" not in svg


def test_labels_escaped():
    scales = [Scale(0.0, lambda v: v, 0, 1, "a<b>&\"c\""), Scale(1.0, lambda v: v, 0, 1, "v")]
    svg = parallel_nomogram(scales, title="x < y")
    ET.fromstring(svg)
    assert "a&lt;b&gt;" in svg


def test_degenerate_scale_refused():
    with pytest.raises(ValueError):
        parallel_nomogram([Scale(0.0, lambda v: 1.0, 0, 1, "u"),
                           Scale(1.0, lambda v: 1.0, 0, 1, "v")])


def test_isopleth_length_mismatch_refused():
    scales = [Scale(0.0, lambda v: v, 0, 1, "u"), Scale(1.0, lambda v: v, 0, 1, "v")]
    with pytest.raises(ValueError):
        parallel_nomogram(scales, isopleth=[1.0])

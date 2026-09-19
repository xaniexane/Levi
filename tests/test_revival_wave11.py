"""Tests for revival wave 11 — analog-compute (d).

coincidence_rangefinder, argo_clock, optical_fourier, quadrature_tables,
patch_grammar, geared_cycles: each an original, from-scratch LEVI
mechanism. At least three meaningful tests per module: construct,
exercise the core mechanism, cover an edge.
"""

import math
from fractions import Fraction

import pytest

from core.levi.revival import coincidence_rangefinder as cr
from core.levi.revival import argo_clock as ac
from core.levi.revival import optical_fourier as of_
from core.levi.revival import quadrature_tables as qt
from core.levi.revival import patch_grammar as pg
from core.levi.revival import geared_cycles as gc


# ---------------------------------------------------------------------------
# coincidence_rangefinder — null-matching range measurement
# ---------------------------------------------------------------------------


def _sine(x: float) -> float:
    return math.sin(3.0 * x)


def test_rangefinder_geometry_roundtrip():
    assert cr.range_from_knob(
        cr.knob_from_range(500.0, 2.0, 32.0), 2.0, 32.0
    ) == pytest.approx(500.0)


def test_rangefinder_null_measures_smooth_target_near_exact():
    rf = cr.Rangefinder(baseline=2.0)
    est, residual, steps = rf.measure(_sine, 500.0)
    assert est == pytest.approx(500.0, rel=1e-3)
    assert residual >= 0.0
    assert steps > 0


def test_rangefinder_step_edge_within_instrument_class():
    rf = cr.Rangefinder(baseline=2.0)
    est, _, _ = rf.measure(lambda x: 1.0 if x > 0.1 else 0.0, 500.0)
    assert est == pytest.approx(500.0, rel=0.02)


def test_rangefinder_rejects_bad_inputs():
    with pytest.raises(ValueError):
        cr.Rangefinder(baseline=0.0)
    with pytest.raises(ValueError):
        cr.range_from_knob(-1.0, 2.0, 32.0)
    with pytest.raises(ValueError):
        cr.mismatch([1.0, 2.0], [1.0])


# ---------------------------------------------------------------------------
# argo_clock — continuously integrated relative-motion plot
# ---------------------------------------------------------------------------


def _crossing_plot() -> "ac.Plot":
    return ac.Plot(
        initial_range=8000.0,
        initial_bearing_deg=45.0,
        target_course_deg=270.0,
        target_speed=15.0,
        own_course_deg=0.0,
        own_speed=20.0,
    )


def test_argo_clock_integrates_relative_motion():
    p = _crossing_plot()
    r0, b0 = p.range, p.bearing_deg
    p.tick(60.0)
    assert p.elapsed == pytest.approx(60.0)
    assert (p.range, p.bearing_deg) != (r0, b0)


def test_argo_clock_static_geometry_stays_put():
    p = ac.Plot(1000.0, 90.0, 0.0, 0.0, 0.0, 0.0)
    p.tick(3600.0)
    assert p.range == pytest.approx(1000.0)
    assert p.bearing_deg == pytest.approx(90.0)


def test_argo_clock_rates_match_finite_difference():
    p = _crossing_plot()
    rr, br = p.rates()
    r0, b0 = p.range, p.bearing_deg
    p2 = _crossing_plot()
    dt = 1e-3  # tiny step: curvature is second-order, rate is first-order
    p2.tick(dt)
    assert (p2.range - r0) / dt == pytest.approx(rr, abs=1e-4)
    db = (p2.bearing_deg - b0 + 540.0) % 360.0 - 180.0
    assert db / dt == pytest.approx(br, abs=1e-4)


def test_argo_clock_corrections_nudge_model():
    p = _crossing_plot()
    p.correct_range(9000.0, gain=1.0)
    assert p.range == pytest.approx(9000.0)
    assert p.corrections == 1
    p.correct_bearing(50.0, gain=1.0)
    assert p.bearing_deg == pytest.approx(50.0)
    with pytest.raises(ValueError):
        p.correct_range(9000.0, gain=1.5)


def test_argo_clock_gun_orders_lead_the_target():
    p = _crossing_plot()
    train, elev = p.gun_orders(30.0)
    pr, pb = p.project(30.0)
    expect_train = (pb - p.bearing_deg + 540.0) % 360.0 - 180.0
    assert train == pytest.approx(expect_train)
    assert elev == pytest.approx(pr * 0.01)
    assert train != pytest.approx(0.0)  # crossing target needs lead


def test_argo_clock_rejects_bad_inputs():
    with pytest.raises(ValueError):
        ac.Plot(0.0, 0.0, 0.0, 1.0, 0.0, 1.0)
    with pytest.raises(ValueError):
        _crossing_plot().tick(-1.0)


# ---------------------------------------------------------------------------
# optical_fourier — the lens as a 2-D Fourier transform
# ---------------------------------------------------------------------------


def test_fft1d_roundtrip_and_known_value():
    xs = [1.0, 2.0, 3.0, 4.0]
    back = of_.ifft1d(of_.fft1d(xs))
    assert [v.real for v in back] == pytest.approx(xs)
    spec = of_.fft1d([1.0, 0.0, 0.0, 0.0])
    assert [v.real for v in spec] == pytest.approx([1.0, 1.0, 1.0, 1.0])
    with pytest.raises(ValueError):
        of_.fft1d([1.0, 2.0, 3.0])


def test_dft2_idft2_roundtrip():
    grid = [[float(r * 4 + c) for c in range(4)] for r in range(4)]
    back = of_.idft2(of_.dft2(grid))
    for r in range(4):
        for c in range(4):
            assert back[r][c].real == pytest.approx(grid[r][c], abs=1e-9)
            assert back[r][c].imag == pytest.approx(0.0, abs=1e-9)


def test_matched_filter_finds_template_and_matches_direct():
    scene = [[0.0] * 8 for _ in range(8)]
    for r in range(2, 6):
        for c in range(3, 7):
            scene[r][c] = 1.0
    templ = [[1.0] * 4 for _ in range(4)]
    loc, strength, plane = of_.matched_filter(scene, templ)
    direct = of_.direct_correlate(scene, templ)
    for r in range(8):
        for c in range(8):
            assert plane[r][c] == pytest.approx(direct[r][c], abs=1e-6)
    assert loc == (2, 3)
    assert strength == pytest.approx(16.0)
    with pytest.raises(ValueError):
        of_.matched_filter([[1.0]], [[1.0, 2.0], [3.0, 4.0]])


def test_power_spectrum_shape_and_nonnegativity():
    grid = [[1.0 if (r + c) % 2 == 0 else 0.0 for c in range(4)] for r in range(4)]
    ps = of_.power_spectrum(grid)
    assert len(ps) == 4 and all(len(row) == 4 for row in ps)
    assert all(v >= 0.0 for row in ps for v in row)


# ---------------------------------------------------------------------------
# quadrature_tables — the table is the program
# ---------------------------------------------------------------------------


def test_cotes_simpson_table_is_exact_rationals():
    t = qt.cotes_table(3)
    assert t.weights == [Fraction(1, 6), Fraction(4, 6), Fraction(1, 6)]
    assert t.weight_sum() == Fraction(1)


def test_cotes_integrates_polynomials_exactly():
    val, note = qt.integrate(lambda x: x**2, 0.0, 1.0, n=3)
    assert val == pytest.approx(1 / 3, abs=1e-12)
    val5, _ = qt.integrate(lambda x: x**4 - 2 * x, 1.0, 3.0, n=5)
    exact = (3**5 / 5 - 3**2) - (1 / 5 - 1)
    assert val5 == pytest.approx(exact, abs=1e-9)
    assert "exact for polynomials" in note


def test_cotes_approximates_transcendental():
    val, _ = qt.integrate(math.sin, 0.0, math.pi, n=7)
    assert val == pytest.approx(2.0, rel=1e-4)  # honest approximation error


def test_cotes_edges():
    assert qt.integrate(math.sin, 2.0, 2.0)[0] == 0.0
    assert qt.cotes_table(2).weights[0] == Fraction(1, 2)
    with pytest.raises(ValueError):
        qt.cotes_table(0)
    with pytest.raises(ValueError):
        qt.cotes_table(9)
    assert "Newton-Cotes n=3" in qt.table_text(3)


# ---------------------------------------------------------------------------
# patch_grammar — computation as inspectable arrangement
# ---------------------------------------------------------------------------


def _wired_panel() -> "pg.PatchPanel":
    p = pg.PatchPanel("t")
    p.place("src", "const", value=3.0)
    p.place("amp", "gain", k=4.0)
    p.place("sum", "add")
    p.cord("src", "v", "amp", "x")
    p.cord("src", "v", "sum", "a")
    p.cord("amp", "y", "sum", "b")
    return p


def test_patch_panel_wires_and_evaluates():
    out = _wired_panel().run()
    assert out["amp"]["y"] == pytest.approx(12.0)
    assert out["sum"]["s"] == pytest.approx(15.0)
    assert "cord: src.v -> amp.x" in _wired_panel().wiring_diagram()


def test_patch_panel_integrator_holds_state():
    p = pg.PatchPanel("i")
    p.place("acc", "integrator", dt=0.5)
    assert p.run({"acc": {"x": 2.0}})["acc"]["y"] == pytest.approx(1.0)
    assert p.run({"acc": {"x": 2.0}})["acc"]["y"] == pytest.approx(2.0)


def test_patch_panel_rejects_bad_wiring():
    p = pg.PatchPanel("b")
    p.place("a", "const", value=1.0)
    p.place("b", "gain", k=2.0)
    with pytest.raises(pg.PatchError):
        p.cord("a", "v", "b", "nope")
    p.cord("a", "v", "b", "x")
    with pytest.raises(pg.PatchError):
        p.cord("a", "v", "b", "x")  # fan-in collision
    cyc = pg.PatchPanel("c")
    cyc.place("u1", "gain", k=1.0).place("u2", "gain", k=1.0)
    cyc.cord("u1", "y", "u2", "x").cord("u2", "y", "u1", "x")
    with pytest.raises(pg.PatchError):
        cyc.run()


def test_cam_barrel_reads_cut_pegs():
    cam = pg.CamBarrel().cut(0.0, 0.0).cut(90.0, 1.0).cut(180.0, 0.0)
    assert cam.read(90.0) == pytest.approx(1.0)
    assert cam.read(45.0) == pytest.approx(0.5)
    assert cam.read(360.0) == pytest.approx(cam.read(0.0))
    with pytest.raises(pg.PatchError):
        pg.CamBarrel().read(10.0)


def test_nomograph_aligns_off_the_table():
    xs = [0.0, 10.0]
    ys = [0.0, 5.0]
    table = [[0.0, 5.0], [10.0, 15.0]]  # z = x + y
    n = pg.Nomograph(xs, ys, table)
    assert n.align(5.0, 2.5) == pytest.approx(7.5)
    assert n.align(10.0, 5.0) == pytest.approx(15.0)
    with pytest.raises(ValueError):
        pg.Nomograph([0.0], [0.0, 1.0], [[0.0, 1.0]])


def test_quipu_encodes_and_combines_channels():
    q = pg.Quipu().encode("a", 27).encode("b", 15)
    assert q.decode("a") == 27
    assert q.channels() == ["a", "b"]
    q.combine("total", lambda x, y: x + y, "a", "b")
    assert q.decode("total") == 42
    with pytest.raises(pg.PatchError):
        q.decode("missing")
    with pytest.raises(ValueError):
        pg.Quipu().encode("neg", -3)


# ---------------------------------------------------------------------------
# geared_cycles — astronomical prediction as gear ratios
# ---------------------------------------------------------------------------


def _demo_train() -> "gc.GearTrain":
    return gc.GearTrain([gc.Gear("crank", 60), gc.Gear("wheel", 1772)])


def test_gear_train_compounds_ratios_with_sign_flip():
    train = gc.GearTrain([gc.Gear("a", 20), gc.Gear("b", 40), gc.Gear("c", 10)])
    assert train.ratios() == pytest.approx([1.0, -0.5, 2.0])
    out = train.drive(4.0)
    assert out["c"] == pytest.approx(8.0)
    with pytest.raises(gc.GearError):
        gc.Gear("flat", 0)
    with pytest.raises(gc.GearError):
        gc.GearTrain([gc.Gear("solo", 10)])


def test_cycle_dial_tracks_phase_and_zero():
    dial = gc.CycleDial("m", 1.0, "wheel", -60 / 1772).advance(29.53 / 2)
    assert dial.phase() == pytest.approx(0.5, abs=1e-3)
    assert dial.angle_deg() == pytest.approx(180.0, abs=0.5)
    zero = gc.CycleDial("m", 1.0, "wheel", -60 / 1772)
    assert zero.near_zero()


def test_eclipse_window_opens_on_coincidence():
    month = gc.CycleDial("month", 1.0, "w1", 1 / 29.53)
    node = gc.CycleDial("node", 1.0, "w2", 1 / 27.21)
    w = gc.EclipseWindow(month, node)
    assert w.open()  # both at zero on the bench
    nxt = w.next_open(step=0.5)
    assert nxt == pytest.approx(0.0)
    month.advance(29.53 / 2)  # full moon, off the node
    assert not w.open()
    later = w.next_open(step=0.5, limit=5000.0)
    assert later is not None and later > 0.0


def test_eclipse_next_open_returns_none_past_limit():
    month = gc.CycleDial("month", 1.0, "w1", 1 / 29.53).advance(7.0)
    node = gc.CycleDial("node", 1.0, "w2", 1 / 27.21).advance(7.0)
    w = gc.EclipseWindow(month, node, tolerance=1e-9)
    assert not w.open()
    assert w.next_open(step=1.0, limit=10.0) is None
    with pytest.raises(gc.GearError):
        gc.EclipseWindow(month, node, tolerance=0.5)

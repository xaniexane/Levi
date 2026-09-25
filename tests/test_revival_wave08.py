"""Wave 08 tests: analog-compute (a) — machines, integrators, fire control."""

import pytest

from levi.revival import arithmometer as am
from levi.revival import comptometer as cm
from levi.revival import curta as cu
from levi.revival import millionaire_mult as mm
from levi.revival import moniac_flow as mf
from levi.revival import nomography as ng
from levi.revival import pinwheel as pw
from levi.revival import planimeter as pl


# ---------------------------------------------------------------- nomography
def test_nomography_addition_exact():
    chart = ng.addition_chart()
    r = chart.solve({"u": 30.0, "v": 45.0}, "w", divisions=10000)
    assert r.exact == pytest.approx(75.0)
    assert r.read_value == pytest.approx(75.0, abs=0.01)


def test_nomography_product_log_scales():
    chart = ng.product_chart()
    r = chart.solve({"u": 6.0, "v": 7.0}, "w", divisions=10000)
    assert r.exact == pytest.approx(42.0)
    assert r.read_value == pytest.approx(42.0, rel=0.001)


def test_nomography_harmonic_parallel_resistors():
    chart = ng.harmonic_chart()
    r = chart.solve({"u": 20.0, "v": 30.0}, "w", divisions=10000)
    assert r.exact == pytest.approx(12.0)
    assert r.read_value == pytest.approx(12.0, rel=0.001)


def test_nomography_tick_quantization_is_honest():
    chart = ng.addition_chart()
    coarse = chart.solve({"u": 30.0, "v": 45.0}, "w", divisions=10)
    fine = chart.solve({"u": 30.0, "v": 45.0}, "w", divisions=10000)
    # Coarse ticks cannot read exactly; fine ticks nearly can.
    assert coarse.read_error > 0
    assert fine.read_error <= coarse.read_error
    # The quantized read is always within one tick of the exact value.
    assert abs(coarse.read_value - coarse.exact) <= 100.0 / 10


# --------------------------------------------------------------- moniac_flow
def test_moniac_conserves_water():
    c = mf.Circuit()
    c.add_tank("X", 100.0, level=60.0)
    c.add_tank("Y", 100.0, level=10.0)
    c.add_pipe("p", "X", "Y", conductance=0.1)
    before = c.total_water()
    c.run(50)
    assert c.total_water() == pytest.approx(before)


def test_moniac_closed_valve_holds_levels():
    c = mf.Circuit()
    c.add_tank("X", 100.0, level=60.0)
    c.add_tank("Y", 100.0, level=10.0)
    c.add_pipe("p", "X", "Y", conductance=0.5, opening=0.0)
    step = c.step()
    assert step.flows["p"] == pytest.approx(0.0)
    assert step.levels["X"] == pytest.approx(60.0)
    assert step.levels["Y"] == pytest.approx(10.0)


def test_moniac_float_valve_holds_level_near_target():
    c = mf.Circuit()
    c.add_tank("A", 1000.0, level=50.0)
    c.add_tank("B", 1000.0, level=0.0)
    c.add_pipe("spend", "A", "B", conductance=0.2, opening=0.0)
    c.add_source("A", 5.0)
    c.add_sink("B", 100.0)
    c.add_float_valve("A", "spend", target=50.0, gain=0.05, smoothing=0.3)
    c.run(2000)
    tail = [s.levels["A"] for s in c.history[-50:]]
    assert max(tail) - min(tail) < 1e-9  # settled, no hunting
    assert 50.0 < sum(tail) / len(tail) < 65.0  # near target w/ honest offset
    assert 0.0 < c.pipes["spend"].opening < 1.0


def test_moniac_overflow_is_spilled_and_counted():
    c = mf.Circuit()
    c.add_tank("T", 10.0, level=10.0)
    c.add_source("T", 5.0)
    c.step()
    assert c.tanks["T"].level == pytest.approx(10.0)
    assert c.tanks["T"].spilled == pytest.approx(5.0)


# ---------------------------------------------------------------- planimeter
SQUARE = [(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)]
TRIANGLE = [(0.0, 0.0), (3.0, 0.0), (0.0, 2.0)]


def _planimeter():
    return pl.PolarPlanimeter(
        pivot=(-5.0, 0.0), pole=6.0, arm=4.0, wheel_d=2.0, subdivisions=400
    )


def test_planimeter_square_area():
    m = _planimeter().trace(SQUARE)
    assert m.measured_area == pytest.approx(4.0, rel=0.01)
    assert m.reference_area == pytest.approx(4.0)
    assert m.relative_error < 0.01


def test_planimeter_triangle_area():
    m = _planimeter().trace(TRIANGLE)
    assert m.measured_area == pytest.approx(3.0, rel=0.01)


def test_planimeter_clockwise_reads_negative():
    cw = list(reversed(SQUARE))
    m = _planimeter().trace(cw)
    assert m.measured_area == pytest.approx(-4.0, rel=0.01)


def test_planimeter_rejects_pivot_inside_and_unreachable():
    inside = pl.PolarPlanimeter(pivot=(0.5, 0.5), pole=6.0, arm=4.0)
    with pytest.raises(pl.GeometryError):
        inside.trace(SQUARE)
    far = _planimeter()
    with pytest.raises(pl.GeometryError):
        far.trace([(50.0, 0.0), (51.0, 0.0), (50.0, 1.0)])


# -------------------------------------------------------------- arithmometer
def test_arithmometer_multiply_with_self_check():
    m = am.Arithmometer()
    r = m.multiply(123, 456)
    assert r.product == 56088
    assert r.turns == 4 + 5 + 6
    assert r.counter_value == 456
    assert r.self_check_ok
    assert not r.overflow


def test_arithmometer_crank_add_subtract_at_carriage():
    m = am.Arithmometer()
    m.enter(7)
    m.move_carriage(2)
    m.add()
    assert m.result == 700
    m.subtract()
    assert m.result == 0


def test_arithmometer_divide():
    m = am.Arithmometer()
    r = m.divide(56088, 123)
    assert r.quotient == 456
    assert r.remainder == 0
    with pytest.raises(ValueError):
        m.divide(10, 0)


def test_arithmometer_overflow_wraps_with_flag():
    m = am.Arithmometer(width=4)
    m.enter(9999)
    m.add()
    assert m.result == 9999
    assert not m.overflow
    m.add()
    assert m.overflow
    assert m.result == 9998  # 19998 mod 10000


# -------------------------------------------------------------- comptometer
def test_comptometer_chord_entry():
    m = cm.Comptometer()
    r = m.chord({0: (5, 1.0), 1: (2, 1.0), 2: (4, 1.0)})
    assert r.added == 425
    assert m.total() == 425
    assert not r.locked


def test_comptometer_flutter_ignored():
    m = cm.Comptometer()
    e = m.press(0, 9, travel=0.2)
    assert e.outcome == "flutter"
    assert m.total() == 0


def test_comptometer_partial_stroke_locks_and_voids_chord():
    m = cm.Comptometer()
    r = m.chord({0: (5, 1.0), 1: (3, 0.7)})
    assert r.locked
    assert r.added == 0
    assert m.total() == 0  # full-stroke key rolled back
    assert any(e.outcome == "locked" for e in r.events)
    # Locked key is rejected until released to rest.
    e2 = m.press(1, 3, travel=1.0)
    assert e2.outcome == "rejected-locked"
    freed = m.release()
    assert (1, 3) in freed
    e3 = m.press(1, 3, travel=1.0)
    assert e3.outcome == "added"
    assert m.total() == 30


def test_comptometer_carry_and_overflow():
    m = cm.Comptometer(columns=3)
    m.chord({0: (9, 1.0), 1: (9, 1.0), 2: (9, 1.0)})
    assert m.total() == 999
    m.press(0, 1)
    assert m.total() == 0  # 1000 mod 1000
    assert m.overflow


# ----------------------------------------------------------------- millionaire
def test_millionaire_table_verifies():
    assert mm.verify_table()
    assert mm.TABLE[(7, 8)] == 56
    assert len(mm.TABLE) == 100


def test_millionaire_multiply_one_turn_per_nonzero_digit():
    m = mm.Millionaire()
    r = m.multiply(123, 456)
    assert r.product == 56088
    assert r.turns == 3  # digits 4,5,6 — not 4+5+6
    assert r.lookups == 3 * 3
    assert not r.overflow


def test_millionaire_zero_digits_cost_no_turns():
    m = mm.Millionaire()
    r = m.multiply(7, 1001)
    assert r.product == 7007
    assert r.turns == 2


def test_millionaire_overflow_wraps_with_flag():
    m = mm.Millionaire(width=4)
    r = m.multiply(9999, 9999)
    assert r.overflow
    assert r.product == 9999 * 9999 % 10000


# --------------------------------------------------------------------- curta
def test_curta_multiply_serial_drum():
    m = cu.Curta()
    r = m.multiply(123, 456)
    assert r.product == 56088
    assert r.counter_value == 456
    assert r.self_check_ok
    assert not r.overflow


def test_curta_crank_back_subtracts_and_counter_rewinds():
    m = cu.Curta()
    m.set(100)
    m.move_carriage(0)
    m.crank(3)
    assert m.result == 300
    assert m.counter_value() == 3
    m.crank_back(1)
    assert m.result == 200
    assert m.counter_value() == 2


def test_curta_divide():
    m = cu.Curta()
    r = m.divide(56088, 123)
    assert r.quotient == 456
    assert r.remainder == 0
    r2 = m.divide(100, 7)
    assert r2.quotient == 14
    assert r2.remainder == 2


def test_curta_overflow_wraps_result_register():
    m = cu.Curta(result_width=3)
    m.set(999)
    m.crank(2)
    assert m.overflow
    assert m.result == 1998 % 1000


# ------------------------------------------------------------------ pinwheel
def test_pinwheel_sparse_digit_encoding():
    assert pw.pin_mask(0) == 0
    assert pw.pin_mask(7) == 0b1111111
    assert pw.pin_mask(9) == 0b111111111
    assert pw.popcount(pw.pin_mask(5)) == 5
    with pytest.raises(ValueError):
        pw.pin_mask(10)


def test_pinwheel_input_roundtrip_and_corruption_caught():
    m = pw.Pinwheel()
    m.set_input(4821)
    assert m.input_value() == 4821
    m.wheels[0] = 0b101  # non-prefix mask: not a real digit setting
    with pytest.raises(RuntimeError):
        m.input_value()


def test_pinwheel_multiply():
    m = pw.Pinwheel()
    r = m.multiply(123, 45)
    assert r.product == 5535
    assert r.turns == 4 + 5
    assert not r.overflow


def test_pinwheel_divide_and_retract():
    m = pw.Pinwheel()
    r = m.divide(100, 7)
    assert r.quotient == 14
    assert r.remainder == 2
    m.retract_all()
    assert m.input_value() == 0
    before = m.result
    m.rotate(3)
    assert m.result == before  # retracted pins engage nothing

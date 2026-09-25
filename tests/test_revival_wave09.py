"""Tests for revival wave 09: analog-compute (b) — machines, integrators."""

import dataclasses
import math

import pytest

from core.levi.revival import slide_rule, sector_scale, adding_listing, cam_programming
from core.levi.revival import napier_bones, soroban_suanpan, tide_predictor
from core.levi.revival import ball_disc_integrator


# -- slide_rule: logarithmic position arithmetic ---------------------------


def test_slide_rule_multiply_mantissa_and_wrap():
    r = slide_rule.SlideRule()
    prod = r.multiply(2.0, 3.0)
    assert prod.mantissa == pytest.approx(6.0, rel=1e-9)
    assert prod.wrap is False
    prod = r.multiply(4.0, 5.0)  # 20 -> mantissa 2.0, cursor off the end
    assert prod.mantissa == pytest.approx(2.0, rel=1e-9)
    assert prod.wrap is True


def test_slide_rule_divide_wrap_adjusts_exponent_down():
    r = slide_rule.SlideRule()
    q = r.divide(8.0, 4.0)
    assert q.mantissa == pytest.approx(2.0, rel=1e-9)
    assert q.wrap is False
    q = r.divide(2.0, 8.0)  # 0.25 -> mantissa 2.5, position went negative
    assert q.mantissa == pytest.approx(2.5, rel=1e-9)
    assert q.wrap is True


def test_slide_rule_square_sqrt_and_reading_assembly():
    r = slide_rule.SlideRule()
    sq = r.square(3.0)
    assert sq.mantissa == pytest.approx(9.0, rel=1e-9)
    assert r.sqrt(2.0) == pytest.approx(math.sqrt(2.0), rel=1e-9)
    reading = r.read(r.multiply(250.0, 4.0), exponent=3)  # wrap: 1000
    assert reading.mantissa == pytest.approx(1.0, rel=1e-9)
    assert reading.value() == pytest.approx(1000.0, rel=1e-9)
    assert reading.error_bound() > 0.0


def test_slide_rule_mantissa_exponent_split_rejects_zero():
    m, e = slide_rule.mantissa_exponent(0.025)
    assert m == pytest.approx(2.5, rel=1e-12) and e == -2
    with pytest.raises(ValueError):
        slide_rule.mantissa_exponent(0.0)


# -- sector_scale: similar triangles in engraved spacing --------------------


def test_sector_proportion_fourth_proportional():
    s = sector_scale.Sector()
    assert s.proportion(6.0, 2.0, 9.0) == pytest.approx(3.0, rel=1e-9)
    assert s.proportion(3.0, 5.0, 9.0) == pytest.approx(15.0, rel=1e-9)


def test_sector_opening_limit_is_honest_hardware():
    s = sector_scale.Sector()
    with pytest.raises(ValueError):
        s.open_for(1.0, 3.0)  # wider than flat-open legs allow
    angle = s.open_for(2.0, 2.0)
    assert 0.0 < angle <= math.pi


def test_sector_square_scale_spacing():
    sq = sector_scale.Scale("square")
    assert sq.mark(4.0) == pytest.approx(2.0 * sq.mark(1.0), rel=1e-9)
    s = sector_scale.Sector()
    assert s.double_area_side(1.0) == pytest.approx(math.sqrt(2.0), rel=1e-9)
    with pytest.raises(ValueError):
        sector_scale.Sector().transverse(5.0)  # opening never set


# -- adding_listing: computation that produces evidence ----------------------


def test_adding_listing_tape_and_totals():
    m = adding_listing.ListingMachine()
    assert m.enter("100") == 100
    assert m.enter("25", operation="subtract") == 75
    assert m.subtotal() == 75
    assert m.running_total == 75  # subtotal does not clear
    assert m.total() == 75
    assert m.running_total == 0  # total clears
    tape = m.tape()
    assert [line.operation for line in tape] == ["+", "-", "S", "T"]
    text = m.print_tape()
    assert "TOTAL: 75" in text


def test_adding_listing_rejects_bad_keying_and_locks():
    m = adding_listing.ListingMachine(columns=4)
    with pytest.raises(adding_listing.ErrorLock):
        m.enter("12a4")
    assert m.locked is True
    with pytest.raises(adding_listing.ErrorLock):
        m.enter("1")  # jammed machines stay jammed
    m.clear_error()
    with pytest.raises(adding_listing.ErrorLock):
        m.enter("12345")  # wider than the hardware columns
    assert m.tape()[-1].operation == "!"  # the rejection is on the tape
    m.clear_error()
    assert m.enter("7") == 7


def test_adding_listing_empty_keying_rejected():
    m = adding_listing.ListingMachine()
    with pytest.raises(adding_listing.ErrorLock):
        m.enter("")


# -- cam_programming: pinned-barrel declarative automation -------------------


def test_cam_barrel_fires_pins_in_order_across_revolutions():
    b = cam_programming.PinBarrel(tracks=2, steps=4)
    b.pin(0, 1)
    b.pin(1, 1)
    b.pin(0, 3)
    strikes = b.run(revolutions=2)
    assert [(s.track, s.step, s.revolution) for s in strikes] == [
        (0, 1, 0),
        (1, 1, 0),
        (0, 3, 0),
        (0, 1, 1),
        (1, 1, 1),
        (0, 3, 1),
    ]


def test_cam_barrel_actuators_and_inspection():
    b = cam_programming.PinBarrel(tracks=1, steps=3)
    b.pin(0, 2)
    fired = []
    b.run(actuators={0: fired.append})
    assert len(fired) == 1 and fired[0].step == 2
    assert "t0: ..*" in b.inspect()
    b.unpin(0, 2)
    assert b.run() == []


def test_cam_barrel_freeze_is_read_only():
    b = cam_programming.PinBarrel(tracks=1, steps=2)
    b.pin(0, 0)
    frozen = b.freeze()
    assert frozen.is_pinned(0, 0) is True
    with pytest.raises(dataclasses.FrozenInstanceError):
        frozen.pins = ()  # frozen dataclass: cannot re-pin the barrel
    with pytest.raises(IndexError):
        b.pin(5, 0)


def test_cam_profile_lift_and_dwell():
    cam = cam_programming.Cam(lambda th: 1.0 + (0.5 if th < math.pi else 0.0))
    assert cam.max_lift() == pytest.approx(0.5, rel=1e-9)
    assert cam.lift_at(0) == pytest.approx(0.5, rel=1e-9)
    assert cam.dwell_steps() == cam.samples // 2


# -- napier_bones: the algorithm factored into the object --------------------


def test_napier_bone_rows_are_diagonal_pairs():
    bone = napier_bones.Bone(7)
    assert bone.row(8) == (5, 6)  # 7*8 = 56, tens|units across the diagonal
    assert bone.row(0) == (0, 0)
    with pytest.raises(ValueError):
        napier_bones.Bone(10)


def test_napier_multiply_via_diagonal_sums():
    assert napier_bones.multiply(738, 59) == 43542
    assert napier_bones.multiply(0, 999) == 0
    assert napier_bones.multiply(123456789, 987654321) == 123456789 * 987654321
    with pytest.raises(ValueError):
        napier_bones.multiply(-2, 3)


def test_napier_divide_via_bone_rows():
    q, r = napier_bones.divide(43542, 59)
    assert (q, r) == (738, 0)
    q, r = napier_bones.divide(100, 7)
    assert (q, r) == (14, 2)
    with pytest.raises(ValueError):
        napier_bones.divide(10, 0)


def test_location_board_add_and_subtract():
    board = napier_bones.LocationBoard
    assert board.add(13, 29) == 42
    assert board.add(255, 1) == 256  # carry ripples the whole board
    assert board.subtract(42, 29) == 13
    assert board.subtract(100, 100) == 0
    with pytest.raises(ValueError):
        board.subtract(5, 9)


# -- soroban_suanpan: bi-quinary bead reckoning -------------------------------


def test_abacus_set_and_read_roundtrip():
    ab = soroban_suanpan.Abacus(rods=5)
    ab.set_value(9876)
    assert ab.read() == 9876
    ab.set_rod(4, 3)
    assert ab.read_rod(4) == 3
    with pytest.raises(ValueError):
        ab.set_rod(0, 10)
    with pytest.raises(OverflowError):
        ab.set_value(100000)


def test_abacus_add_uses_complements():
    ab = soroban_suanpan.Abacus(rods=4)
    ab.set_value(7)
    assert ab.add(8) == 15  # 7 + 8 needs the ten-complement on the units rod
    techniques = dict(ab.last_techniques)
    assert techniques[3] == "ten-complement"
    ab.set_value(1)
    assert ab.add(4) == 5  # five-complement: +5 heaven, -1 earth
    assert dict(ab.last_techniques)[3] == "five-complement"


def test_abacus_subtract_and_borrow():
    ab = soroban_suanpan.Abacus(rods=4)
    ab.set_value(100)
    assert ab.subtract(1) == 99
    ab.set_value(50)
    assert ab.subtract(50) == 0
    with pytest.raises(ValueError):
        ab.subtract(1)  # frame cannot show negatives


def test_suanpan_spares_normalize_and_anzan():
    ab = soroban_suanpan.Abacus(rods=3, heaven=2, earth=5)
    assert ab.frame == "suanpan"
    ab._rods[2] = soroban_suanpan.RodState(heaven=2, earth=5)  # spare-laden
    ab.normalize()
    assert ab.read_rod(2) == 5 and ab.read_rod(1) == 1  # 15 carried
    drill = soroban_suanpan.AnzanDrill([7, 8, 15, 20])
    assert drill.check(50) is True
    assert drill.check(49) is False
    assert drill.sequence() == [7, 8, 15, 20]


def test_abacus_bead_diagram_shows_beads_at_bar():
    ab = soroban_suanpan.Abacus(rods=1)
    ab.set_value(7)
    diagram = ab.bead_diagram()
    assert "#|oo.." in diagram  # heaven engaged, two earth engaged


# -- tide_predictor: mechanical Fourier synthesis ------------------------------


def test_tide_single_constituent_period():
    tp = tide_predictor.TidePredictor()
    tp.add_classic("M2", amplitude=2.0)
    t2 = tide_predictor.CLASSIC_CONSTITUENTS["M2"]
    assert tp.predict(3.0) == pytest.approx(tp.predict(3.0 + t2), rel=1e-9)
    assert tp.predict(0.0) == pytest.approx(2.0, rel=1e-9)


def test_tide_synthesis_is_linear_superposition():
    tp = tide_predictor.TidePredictor()
    tp.add_classic("M2", amplitude=1.0)
    tp.add_classic("S2", amplitude=0.5)
    single = tide_predictor.TidePredictor()
    single.add_classic("M2", amplitude=1.0)
    assert tp.predict(5.0) == pytest.approx(
        single.predict(5.0) + 0.5 * math.cos(2.0 * math.pi * 5.0 / 12.0),
        rel=1e-9,
    )
    with pytest.raises(ValueError):
        tp.add_classic("M2")  # shaft already mounted
    with pytest.raises(ValueError):
        tp.add_classic("NOPE")


def test_tide_high_low_waters_found():
    tp = tide_predictor.TidePredictor()
    tp.add_classic("M2", amplitude=1.0)
    events = tp.high_low_waters(0.0, 30.0, step=0.05)
    kinds = [k for _, _, k in events]
    assert kinds == ["low", "high", "low", "high"]  # two semidiurnal cycles
    assert events[1][0] == pytest.approx(12.4206, abs=0.1)
    series = tp.series(0.0, 1.0, 0.5)
    assert [t for t, _ in series] == [0.0, 0.5, 1.0]


# -- ball_disc_integrator: integration in rolling contact -----------------------


def test_integrator_measures_integral_of_y_dx():
    ig = ball_disc_integrator.BallDiscIntegrator()
    assert ig.integrate(lambda x: x, 0.0, 1.0, steps=2000) == pytest.approx(
        0.5, rel=1e-3
    )
    ig = ball_disc_integrator.BallDiscIntegrator(disc_radius=4.0)
    assert ig.integrate(lambda x: 3.0, 0.0, 2.0, steps=100) == pytest.approx(
        6.0, rel=1e-9
    )


def test_integrator_revolutions_follow_ball_geometry():
    ig = ball_disc_integrator.BallDiscIntegrator(disc_radius=2.0, ball_radius=0.25)
    ig.step(1.0, 2.0)
    assert ig.integral == pytest.approx(2.0, rel=1e-12)
    assert ig.revolutions == pytest.approx(2.0 / (2.0 * math.pi * 0.25), rel=1e-12)


def test_integrator_clamps_ball_at_disc_edge():
    ig = ball_disc_integrator.BallDiscIntegrator(disc_radius=1.0)
    ig.step(1.0, 5.0)  # ball cannot ride past the edge
    assert ig.clamped_steps == 1
    assert ig.integral == pytest.approx(1.0, rel=1e-12)


def test_integrator_slip_reduces_output_and_reset_zeroes():
    ideal = ball_disc_integrator.BallDiscIntegrator(slip=0.0)
    lossy = ball_disc_integrator.BallDiscIntegrator(slip=0.2)
    ideal.step(1.0, 1.0)
    lossy.step(1.0, 1.0)
    assert ideal.integral == lossy.integral == pytest.approx(1.0, rel=1e-12)
    assert lossy.revolutions == pytest.approx(0.8 * ideal.revolutions, rel=1e-12)
    lossy.reset()
    assert lossy.integral == 0.0 and lossy.clamped_steps == 0

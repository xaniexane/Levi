"""Tests for wave 10 — analog-compute (c): machines, integrators,
fire control, patch grammar."""

import math

import pytest

from core.levi.revival import harmonic_analyzer as ha
from core.levi.revival import rolling_sphere_integrator as rsi
from core.levi.revival import diff_analyzer as da
from core.levi.revival import reac_analog as reac
from core.levi.revival import pace_analog as pace
from core.levi.revival import suitcase_analog as suit
from core.levi.revival import fire_control as fc
from core.levi.revival import gyro_sight as gs


# --- harmonic_analyzer -------------------------------------------------


def test_synthesize_weighted_sinusoids():
    bank = ha.HarmonicBank()
    bank.set_offset(1.0)
    bank.set_harmonic(1, 2.0, 0.0)
    bank.set_harmonic(2, 1.0, math.pi)  # cos(2t + pi) = -cos(2t)
    assert bank.output(0.0) == pytest.approx(1.0 + 2.0 - 1.0)
    assert bank.output(math.pi) == pytest.approx(1.0 - 2.0 - 1.0)
    assert bank.harmonics() == [1, 2]


def test_analyze_recovers_weights():
    truth = ha.HarmonicBank()
    truth.set_offset(1.0)
    truth.set_harmonic(2, 3.0, 0.5)
    samples = [(t, truth.output(t)) for t in [i * 2 * math.pi / 64 for i in range(64)]]
    bank, report = ha.HarmonicBank.analyze(samples, max_harmonic=4)
    assert bank.weights[0][0] == pytest.approx(1.0, abs=1e-6)
    amp, phase = bank.weights[2]
    assert amp == pytest.approx(3.0, abs=1e-6)
    assert phase == pytest.approx(0.5, abs=1e-6)
    assert report["rms_residual"] < 1e-6
    assert 1 not in bank.harmonics()


def test_analyze_rejects_bad_input():
    bank = ha.HarmonicBank()
    with pytest.raises(ValueError):
        bank.set_harmonic(0, 1.0)
    with pytest.raises(ValueError):
        bank.set_harmonic(21, 1.0)
    with pytest.raises(ValueError):
        bank.set_harmonic(3, -1.0)
    with pytest.raises(ValueError):
        ha.HarmonicBank.analyze([(0.0, 1.0), (1.0, 2.0)], max_harmonic=4)


# --- rolling_sphere_integrator -----------------------------------------


def test_sphere_rolls_area_into_rotation():
    s = rsi.SphereIntegrator(radius=2.0)
    assert s.step(4.0, 0.5) == pytest.approx(1.0)  # 4*0.5/2
    assert s.steps == 1
    slippery = rsi.SphereIntegrator(radius=2.0, slip=0.5)
    assert slippery.step(4.0, 0.5) == pytest.approx(0.5)
    with pytest.raises(ValueError):
        rsi.SphereIntegrator(radius=0.0)
    with pytest.raises(ValueError):
        rsi.SphereIntegrator(slip=1.0)


def test_tracing_pass_yields_fourier_coefficients():
    period = 2.0 * math.pi
    tracer = rsi.TracingPass(curve=math.cos, period=period, n_spheres=3)
    coeffs = tracer.trace()
    assert rsi.coefficient_count(3) == 7
    assert coeffs["a1"] == pytest.approx(1.0, abs=1e-3)
    assert coeffs["b1"] == pytest.approx(0.0, abs=1e-3)
    assert coeffs["a2"] == pytest.approx(0.0, abs=1e-3)
    assert coeffs["a0"] == pytest.approx(0.0, abs=1e-3)


def test_reconstruct_matches_curve():
    period = 2.0 * math.pi
    tracer = rsi.TracingPass(
        curve=lambda x: 2.0 + math.sin(2 * x), period=period, n_spheres=3
    )
    coeffs = tracer.trace()
    for x in (0.3, 1.1, 2.7, 5.0):
        assert tracer.reconstruct(coeffs, x) == pytest.approx(
            2.0 + math.sin(2 * x), abs=1e-2
        )


# --- diff_analyzer -----------------------------------------------------


def test_decay_wiring_solves_exponential():
    trace = da.solve_decay(y0=1.0, rate=1.0, dx=0.001, cycles=1000)
    assert trace[-1] == pytest.approx(math.exp(-1.0), rel=0.01)
    assert all(b <= a for a, b in zip(trace, trace[1:], strict=False))  # monotone


def test_chained_integrators_solve_harmonic():
    trace = da.solve_harmonic(x0=1.0, v0=0.0, omega=1.0, dx=0.001, cycles=1000)
    assert trace[-1] == pytest.approx(math.cos(1.0), rel=0.03)
    # quarter period: cos(pi/2) ~ 0
    quarter = da.solve_harmonic(x0=1.0, v0=0.0, omega=1.0, dx=0.001, cycles=1571)
    assert abs(quarter[-1]) < 0.05


def test_unwired_units_and_diagram():
    machine = da.DifferentialAnalyzer()
    machine.set_dx(0.01)
    machine.add_integrator("loose")
    with pytest.raises(RuntimeError):
        machine.cycle()
    amp = da.TorqueAmplifier("servo")
    src = da.Shaft("src", 3.0)
    followers = amp.drive(src, 3)
    assert len(followers) == 3 and all(f.value == 3.0 for f in followers)
    diagram = machine.wiring_diagram()
    assert "loose" in diagram and "d(loose.z)" in diagram["loose"]


# --- reac_analog -------------------------------------------------------


def test_spring_mass_damper_decays():
    rack = reac.spring_mass_damper(mass=1.0, damping=0.2, stiffness=1.0, x0=1.0, v0=0.0)
    rack.reset()
    assert rack.modules["int_x"].output.value == pytest.approx(1.0)
    trace = rack.operate(problem_dt=0.01, steps=1000)
    assert not rack.overload
    assert rack.mode == "OPERATE"
    first = abs(trace[0]["int_x"])
    last = abs(trace[-1]["int_x"])
    assert last < 0.5 * first  # visibly damped: e^-1 envelope over 10 s
    assert len(trace) == 1000


def test_overload_freezes_and_flags():
    rack = reac.Rack()
    const = rack.add(reac.Pot("const", 1.0))
    const.jacks["in"].value = 50.0  # 50 V standing on the pot input
    integ = rack.add(reac.Integrator("runaway", [1.0], initial=0.0))
    rack.panel.patch(const.output, integ.jacks["in0"])
    rack.reset()
    rack.operate(problem_dt=0.01, steps=500)
    assert rack.overload  # |out| exceeded 100 V
    assert rack.mode == "HOLD"


def test_pot_summer_multiplier_transfer():
    rack = reac.Rack()
    half = rack.add(reac.Pot("half", 0.5))
    half.jacks["in"].value = 80.0
    inv = rack.add(reac.Inverter("inv"))
    rack.panel.patch(half.output, inv.jacks["in"])
    total = rack.add(reac.Summer("total", [1.0, 2.0]))
    rack.panel.patch(half.output, total.jacks["in0"])
    rack.panel.patch(inv.output, total.jacks["in1"])
    mult = rack.add(reac.Multiplier("mult"))
    rack.panel.patch(half.output, mult.jacks["x"])
    rack.panel.patch(inv.output, mult.jacks["y"])
    rack.reset()
    # half.out = 40; inv.out = -40; total = -(40 + 2*(-40)) = 40
    assert total.output.value == pytest.approx(40.0)
    # mult = (40 * -40)/100 = -16
    assert mult.output.value == pytest.approx(-16.0)
    with pytest.raises(ValueError):
        reac.Pot("bad", 1.5)


# --- pace_analog -------------------------------------------------------


def test_dfg_card_approximates_sine():
    dfg = pace.fit_breakpoints(math.sin, -math.pi, math.pi, 32, name="sin")
    assert dfg.segments() == 32
    assert dfg.evaluate(0.0) == pytest.approx(0.0, abs=1e-9)
    assert dfg.evaluate(math.pi / 2) == pytest.approx(1.0, abs=0.01)
    assert not dfg.saturated
    assert dfg.evaluate(10.0) == pytest.approx(0.0, abs=1e-9)  # clips
    assert dfg.saturated
    with pytest.raises(ValueError):
        pace.DiodeFunctionGenerator(name="bad", breakpoints=[(0.0, 0.0)])


def test_realtime_pendulum_oscillates():
    rack = pace.RealtimeRack(time_scale=1.0)
    dfg = pace.fit_breakpoints(math.sin, -1.0, 1.0, 40, name="sin")
    rack.plug_dfg(dfg)
    rack.add_op_amps(12)
    rhs = pace.pendulum_rhs(length=1.0, dfg=dfg)
    trace = rack.simulate(rhs, [0.2, 0.0], t_end=6.5, dt=0.01)
    thetas = [y[0] for _, y in trace]
    assert min(thetas) < -0.1 and max(thetas) > 0.1  # swings both ways
    report = rack.module_report()
    assert report["realtime"] is True
    assert report["dfg_cards"]["sin"]["segments"] == 40
    assert report["op_amps"] == 12


def test_rack_rejects_bad_config():
    with pytest.raises(ValueError):
        pace.RealtimeRack(time_scale=0.0)
    rack = pace.RealtimeRack()
    dfg = pace.fit_breakpoints(math.sin, -1.0, 1.0, 8, name="s")
    rack.plug_dfg(dfg)
    with pytest.raises(ValueError):
        rack.plug_dfg(dfg)  # slot occupied
    with pytest.raises(ValueError):
        rack.simulate(lambda t, y: [0.0], [0.0], t_end=-1.0, dt=0.01)


# --- suitcase_analog ---------------------------------------------------


def test_decay_lesson_reports_accuracy():
    box = suit.SuitcaseComputer()
    box.turn_knob("rate", 1.0)
    result = box.lesson_decay()
    assert result["lesson"] == "decay"
    assert result["accuracy_check"] < 0.2  # coarse Euler, honestly measured
    assert "±5%" in result["meter"]
    assert "rate knob" in result["teaching_note"]


def test_oscillator_lesson_and_what_if():
    box = suit.SuitcaseComputer()
    result = box.lesson_oscillator(omega=1.0, t_end=6.2832)
    assert result["trace"][-1][0] == pytest.approx(6.2832)
    sweep = box.what_if("decay", "rate", [0.5, 1.0, 2.0])
    assert len(sweep) == 3
    finals = [r["final"] for r in sweep]
    assert finals[0] > finals[1] > finals[2]  # faster rate, lower remainder
    with pytest.raises(ValueError):
        box.what_if("fission", "rate", [1.0])


def test_knobs_and_inventory():
    box = suit.SuitcaseComputer()
    with pytest.raises(ValueError):
        box.turn_knob("rate", math.inf)
    card = box.inventory_card()
    assert card["op_amps"] == 6
    assert card["pots"] == 4
    assert card["philosophy"] == "immediacy beats precision"
    reading = box.read_meter("test", 1.23456, unit="V")
    assert "1.2346 V" in reading.card()


# --- fire_control ------------------------------------------------------


def test_tracker_converges_on_straight_track():
    truth = [(float(i), 0.0) for i in range(101)]
    result = fc.run_engagement(truth, dt=1.0, gain=0.35)
    final = result["final"]
    assert final.x == pytest.approx(100.0, abs=2.0)
    assert final.vx == pytest.approx(1.0, abs=0.2)
    assert result["quality"]["mean_residual"] < 2.0


def test_feedback_beats_pure_prediction():
    truth = [(float(i), 0.05 * i * i) for i in range(51)]  # accelerating
    corrected = fc.run_engagement(truth, dt=1.0, gain=0.5)
    # pure prediction from the first two points, no feedback
    pred = fc.TrackState(truth[0][0], truth[0][1], 1.0, 0.05)
    for _ in range(50):
        pred = pred.predict(1.0)
    corr_err = math.hypot(
        corrected["final"].x - truth[-1][0], corrected["final"].y - truth[-1][1]
    )
    pred_err = math.hypot(pred.x - truth[-1][0], pred.y - truth[-1][1])
    assert corr_err < pred_err


def test_gun_orders_lead_a_crossing_target():
    director = fc.GunDirector(shell_speed=800.0)
    track = fc.TrackState(x=1000.0, y=0.0, vx=0.0, vy=100.0)
    orders = director.orders(track)
    assert orders["time_of_flight_s"] == pytest.approx(1.25)
    assert orders["lead_distance_m"] == pytest.approx(125.0, rel=0.01)
    assert orders["deflection_mils"] > 0  # lead is off the line of sight
    assert orders["ballistic_drop_m"] == pytest.approx(0.5 * 9.80665 * 1.25**2)
    with pytest.raises(ValueError):
        fc.TachymetricTracker(gain=0.0)
    with pytest.raises(ValueError):
        fc.GunDirector(shell_speed=-10.0)


# --- gyro_sight --------------------------------------------------------


def test_release_triangle_geometry():
    run = gs.BombRun(altitude_m=3000.0, true_airspeed_ms=150.0)
    point = run.release_point()
    assert point["time_of_fall_s"] == pytest.approx(math.sqrt(2 * 3000.0 / 9.80665))
    assert (
        point["bomb_range_m"] < point["ground_speed_ms"] * point["time_of_fall_s"]
    )  # trail steals range
    assert point["trail_m"] > 0
    assert point["sighting_angle_deg"] == pytest.approx(
        math.degrees(math.atan2(point["bomb_range_m"], 3000.0))
    )
    windy = gs.BombRun(altitude_m=3000.0, true_airspeed_ms=150.0, crosswind_ms=10.0)
    assert windy.drift_angle_deg() == pytest.approx(
        math.degrees(math.atan2(10.0, 150.0))
    )
    with pytest.raises(ValueError):
        gs.BombRun(altitude_m=0.0, true_airspeed_ms=150.0)


def test_cep_and_stabilizer():
    assert gs.cep([10.0, 10.0, 10.0, 10.0]) == pytest.approx(
        1.1774 * 10.0 / math.sqrt(2.0)
    )
    with pytest.raises(ValueError):
        gs.cep([5.0, 6.0])
    stab = gs.GyroStabilizer(drift_rate_dps=0.01)
    err = stab.correct(base_rate_dps=0.5, compensation_dps=0.5, dt=10.0)
    assert err == pytest.approx(0.1)  # only the uncorrected drift remains
    stab.re_cage()
    assert stab.pointing_error == 0.0


def test_lab_vs_field_gap():
    report = gs.lab_vs_field(23.0)
    assert report["test_cep_m"] == 23.0
    assert report["field_cep_m"] > report["test_cep_m"]
    assert report["degradation_ratio"] == pytest.approx(3.0 * 2.5 * 2.0 * 1.5)
    assert "field" in report["lesson"]
    custom = gs.lab_vs_field(10.0, factors={"dust": 2.0})
    assert custom["field_cep_m"] == pytest.approx(20.0)
    with pytest.raises(ValueError):
        gs.lab_vs_field(10.0, factors={"miracle": 0.5})

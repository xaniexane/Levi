"""Hermetic tests for levi.analog — stdlib only, no I/O, no network."""

from __future__ import annotations

import math

import pytest

from levi.analog.bench import (
    Const,
    Gain,
    Integrator,
    Mul,
    Netlist,
    Sine,
    StepBudgetExceeded,
    Summer,
    damped_spring,
    parts_list,
    simulate,
)
from levi.analog.fourier import analyze, bars_to_wave, plot_ascii
from levi.analog.nomo import Nomograph, multiply_nomograph


# ---------------------------------------------------------------------------
# bench
# ---------------------------------------------------------------------------


def test_integrator_of_constant_is_linear_ramp():
    net = Netlist(
        blocks={"src": Const(c=2.0), "ramp": Integrator(ic=0.0)},
        wires=[("src", "ramp", 0)],
    )
    trace, receipt = simulate(net, t_end=1.0, dt=0.01)
    assert trace.signals["ramp"][-1] == pytest.approx(2.0, abs=1e-6)
    assert trace.signals["ramp"][0] == pytest.approx(0.0, abs=1e-12)
    assert receipt.ok


def test_summer_adds_weighted_inputs():
    net = Netlist(
        blocks={
            "a": Const(c=1.0),
            "b": Const(c=2.0),
            "s": Summer(signs=(1.0, 1.0)),
        },
        wires=[("a", "s", 0), ("b", "s", 1)],
    )
    trace, _ = simulate(net, t_end=0.1, dt=0.1)
    assert all(v == pytest.approx(3.0) for v in trace.signals["s"])


def test_summer_subtraction_signs():
    net = Netlist(
        blocks={
            "a": Const(c=5.0),
            "b": Const(c=2.0),
            "s": Summer(signs=(1.0, -1.0)),
        },
        wires=[("a", "s", 0), ("b", "s", 1)],
    )
    trace, _ = simulate(net, t_end=0.1, dt=0.1)
    assert trace.signals["s"][-1] == pytest.approx(3.0)


def test_gain_scales_input():
    net = Netlist(
        blocks={"c": Const(c=3.0), "g": Gain(k=2.0)},
        wires=[("c", "g", 0)],
    )
    trace, _ = simulate(net, t_end=0.1, dt=0.1)
    assert trace.signals["g"][-1] == pytest.approx(6.0)


def test_multiplier():
    net = Netlist(
        blocks={"a": Const(c=3.0), "b": Const(c=4.0), "m": Mul()},
        wires=[("a", "m", 0), ("b", "m", 1)],
    )
    trace, _ = simulate(net, t_end=0.1, dt=0.1)
    assert trace.signals["m"][-1] == pytest.approx(12.0)


def test_sine_source_integrated():
    # integral of 2*sin(2*pi*t) from 0 to 0.5 is 2/pi
    net = Netlist(
        blocks={"gen": Sine(freq=1.0, amp=2.0), "i": Integrator(ic=0.0)},
        wires=[("gen", "i", 0)],
    )
    trace, _ = simulate(net, t_end=0.5, dt=0.01)
    assert trace.signals["i"][-1] == pytest.approx(2.0 / math.pi, abs=1e-4)


def test_wire_to_unknown_block_raises():
    with pytest.raises(ValueError):
        Netlist(
            blocks={"a": Const(c=1.0)},
            wires=[("a", "nope", 0)],
        )


def test_wire_from_unknown_block_raises():
    with pytest.raises(ValueError):
        Netlist(
            blocks={"a": Const(c=1.0)},
            wires=[("ghost", "a", 0)],
        )


def test_wire_input_index_outside_arity_raises():
    with pytest.raises(ValueError):
        Netlist(
            blocks={"a": Const(c=1.0), "g": Gain(k=1.0)},
            wires=[("a", "g", 3)],
        )


def test_fan_in_conflict_raises():
    with pytest.raises(ValueError):
        Netlist(
            blocks={"a": Const(c=1.0), "b": Const(c=2.0), "g": Gain(k=1.0)},
            wires=[("a", "g", 0), ("b", "g", 0)],
        )


def test_algebraic_loop_refused():
    with pytest.raises(ValueError, match="algebraic loop"):
        Netlist(
            blocks={"a": Gain(k=1.0), "b": Gain(k=1.0)},
            wires=[("a", "b", 0), ("b", "a", 0)],
        )


def test_step_budget_exceeded_raises_before_work():
    net = Netlist(
        blocks={"src": Const(c=1.0), "i": Integrator(ic=0.0)},
        wires=[("src", "i", 0)],
    )
    with pytest.raises(StepBudgetExceeded):
        simulate(net, t_end=1.0, dt=0.01, max_steps=10)


def test_step_budget_exactly_allowed():
    net = Netlist(
        blocks={"src": Const(c=1.0), "i": Integrator(ic=0.0)},
        wires=[("src", "i", 0)],
    )
    _trace, receipt = simulate(net, t_end=1.0, dt=0.01, max_steps=100)
    assert receipt.steps_used == 100
    assert receipt.blocks_evaluated == 100 * 4 * 2


def test_unpatched_input_is_explicit_zero():
    net = Netlist(
        blocks={"g": Gain(k=5.0)},
        wires=[],
    )
    trace, _ = simulate(net, t_end=0.1, dt=0.1)
    assert trace.signals["g"][-1] == pytest.approx(0.0)


def test_damped_spring_converges_toward_zero():
    net = damped_spring(m=1.0, c=0.5, k=4.0, x0=1.0, v0=0.0)
    trace, receipt = simulate(net, t_end=20.0, dt=0.01)
    assert trace.signals["pos"][0] == pytest.approx(1.0)
    assert abs(trace.signals["pos"][-1]) < 0.01
    assert receipt.peak_dy_dt > 0.0


def test_damped_spring_receipt_fields():
    net = damped_spring()
    _trace, receipt = simulate(net, t_end=2.0, dt=0.01)
    assert receipt.steps_used == 200
    assert receipt.dt == pytest.approx(0.01)
    assert receipt.ok is True


def test_parts_list_demystifies_integrator():
    net = damped_spring()
    lines = parts_list(net)
    joined = "\n".join(lines)
    assert "torque amplifier" in joined
    assert "Integrator 'pos'" in joined
    assert len(lines) == len(net.blocks)


# ---------------------------------------------------------------------------
# nomo
# ---------------------------------------------------------------------------


def test_nomo_solve_roundtrip_log_scales():
    chart = multiply_nomograph()
    assert chart.solve(2.0, 3.0) == pytest.approx(6.0, abs=1e-9)
    assert chart.solve(0.5, 4.0) == pytest.approx(2.0, abs=1e-9)


def test_nomo_unbracketed_target_raises():
    log = math.log10
    chart = Nomograph(
        X=log,
        Y=log,
        Z=log,
        u_range=(1.0, 10.0),
        v_range=(1.0, 10.0),
        w_range=(1.0, 10.0),
    )
    with pytest.raises(ValueError, match="not bracketed"):
        chart.solve(10.0, 10.0)  # target 2.0, Z range is (0, 1)


def test_chart_ascii_has_scale_labels():
    chart = multiply_nomograph()
    art = chart.chart_ascii()
    assert "u" in art and "v" in art and "w" in art
    assert "|" in art  # the scale lines


def test_chart_ascii_carries_accuracy_note():
    chart = multiply_nomograph()
    art = chart.chart_ascii()
    assert "residual" in art


def test_svg_starts_with_svg_tag_and_closes():
    chart = multiply_nomograph()
    s = chart.svg()
    assert s.startswith("<svg")
    assert s.rstrip().endswith("</svg>")


def test_svg_contains_sample_solution():
    chart = multiply_nomograph()
    s = chart.svg()
    assert "X(u) + Y(v) = Z(" in s
    assert "solved" in s


# ---------------------------------------------------------------------------
# fourier
# ---------------------------------------------------------------------------


def test_bars_to_wave_matches_manual_sum():
    bars = [(1, 1.0, 0.0), (2, 0.5, 0.25)]
    wave = bars_to_wave(bars, points=61)
    for i, v in enumerate(wave):
        t = i / 61
        manual = 1.0 * math.cos(2 * math.pi * 1 * t) + 0.5 * math.cos(
            2 * math.pi * 2 * t + 0.25
        )
        assert v == pytest.approx(manual, abs=1e-12)


def test_analyze_recovers_dominant_harmonic():
    bars = [(1, 1.0, 0.0), (2, 0.5, 0.0)]
    wave = bars_to_wave(bars, points=61)
    top = analyze(wave, top_k=2)
    assert top[0][0] == 1
    assert top[0][1] == pytest.approx(1.0, abs=1e-9)
    assert top[1][0] == 2
    assert top[1][1] == pytest.approx(0.5, abs=1e-9)


def test_analyze_recovers_phase():
    bars = [(3, 0.7, 0.9)]
    wave = bars_to_wave(bars, points=61)
    top = analyze(wave, top_k=1)
    assert top[0][0] == 3
    assert top[0][1] == pytest.approx(0.7, abs=1e-9)
    assert top[0][2] == pytest.approx(0.9, abs=1e-9)


def test_analyze_empty_samples_raises():
    with pytest.raises(ValueError):
        analyze([])


def test_plot_ascii_height():
    wave = bars_to_wave([(1, 1.0, 0.0)], points=40)
    art = plot_ascii(wave, height=11)
    assert len(art.split("\n")) == 11
    assert "*" in art


def test_plot_ascii_flat_signal_draws_midline():
    art = plot_ascii([2.0, 2.0, 2.0], height=7)
    rows = art.split("\n")
    assert len(rows) == 7
    assert any("*" in r for r in rows)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_run_returns_zero(capsys):
    from levi.analog.__main__ import main

    assert main(["run", "--t-end", "0.5"]) == 0
    out = capsys.readouterr().out
    assert "receipt:" in out
    assert "x(t):" in out


def test_cli_parts_returns_zero(capsys):
    from levi.analog.__main__ import main

    assert main(["parts"]) == 0
    out = capsys.readouterr().out
    assert "torque amplifier" in out


def test_cli_nomo_returns_zero(capsys):
    from levi.analog.__main__ import main

    assert main(["nomo", "--u", "2", "--v", "3"]) == 0
    out = capsys.readouterr().out
    assert "<svg" in out
    assert "6" in out


def test_cli_fourier_returns_zero(capsys):
    from levi.analog.__main__ import main

    assert main(["fourier", "1,1.0,0 2,0.5,0"]) == 0
    out = capsys.readouterr().out
    assert "*" in out
    assert "recovered" in out

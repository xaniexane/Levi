"""Entrypoint tests: python -m levi.demand (hermetic, no network)."""

import pytest

from levi.demand.__main__ import main


def _herm(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    # DemandPulse freezes its store path at import time (pulse.DEFAULT);
    # HOME alone does not redirect it, so CLI tests would otherwise write
    # to the real ~/.levi/demand_pulse.json (seen live 2026-09-22: a test
    # run appended a real "Shift planner" score card and bumped real
    # signal seen_counts). Redirect it too.
    import levi.demand.pulse as _pulse

    monkeypatch.setattr(_pulse, "DEFAULT", tmp_path / "demand_pulse.json")


def test_help_exits_zero():
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0


def test_scan_and_five_factor(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    rc = main(
        [
            "--scan",
            "I need help scheduling shifts",
            "--title",
            "Shift planner",
            "--five-factor",
            "--ff-demand",
            "70",
            "--ff-market",
            "60",
            "--ff-gap",
            "80",
            "--ff-velocity",
            "50",
            "--ff-feasibility",
            "90",
            "--ff-basis",
            "test estimates",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Shift planner" in out
    assert "composite=" in out


def test_five_factor_without_basis_fails_closed(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    rc = main(
        [
            "--scan",
            "need shifts help",
            "--title",
            "X",
            "--five-factor",
            "--ff-demand",
            "70",
            "--ff-market",
            "60",
            "--ff-gap",
            "80",
            "--ff-velocity",
            "50",
            "--ff-feasibility",
            "90",
        ]
    )
    assert rc == 2
    assert "ff-basis" in capsys.readouterr().err


def test_five_factor_missing_value_fails_closed(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    rc = main(
        [
            "--scan",
            "need shifts help",
            "--title",
            "X",
            "--five-factor",
            "--ff-demand",
            "70",
            "--ff-basis",
            "test",
        ]
    )
    assert rc == 2


def test_status_only(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main([]) == 0
    assert "DemandPulse" in capsys.readouterr().out

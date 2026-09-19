"""Tests for levi.academy.ladder — BuildLadder (hermetic)."""

import json

import pytest

from levi.academy.ladder import BuildLadder, default_ladder


def _ok():
    return True, "fine"


def _fail():
    return False, "broken"


def _boom():
    raise RuntimeError("kaput")


@pytest.fixture()
def ladder():
    l = BuildLadder()
    l.register_step("alpha", "First step", [("one", _ok), ("two", _fail)])
    l.register_step("beta", "Second step", [("three", _boom)])
    return l


def test_run_step_reports_failure_not_exception(ladder):
    r = ladder.run_step("beta")
    assert r["pass"] is False
    assert r["checks"][0]["ok"] is False
    assert "kaput" in r["checks"][0]["detail"]


def test_run_step_counts(ladder):
    r = ladder.run_step("alpha")
    assert r["passed"] == 1 and r["total"] == 2
    assert r["pass"] is False


def test_unknown_step_raises(ladder):
    with pytest.raises(KeyError):
        ladder.run_step("nope")


def test_run_all_preserves_order(ladder):
    assert [r["step"] for r in ladder.run_all()] == ["alpha", "beta"]


def test_readiness_pct(ladder):
    r = ladder.readiness_pct()
    assert r["passed"] == 1 and r["total"] == 3
    assert r["pass_rate"] == pytest.approx(round(1 / 3, 3))
    assert r["all_pass"] is False


def test_format_ladder_readable(ladder):
    text = ladder.format_ladder()
    assert "=== LEVI Build Ladder ===" in text
    assert "alpha  [1/2]  FAIL" in text
    assert "NOT READY" in text


def test_ladder_json_machine_readable(ladder):
    data = json.loads(ladder.ladder_json())
    assert len(data["steps"]) == 2
    assert data["readiness"]["total"] == 3


def test_empty_ladder_not_ready():
    l = BuildLadder()
    assert l.readiness_pct()["all_pass"] is False
    assert "NOT READY" in l.format_ladder()


def test_default_kernel_boot_step_passes():
    ladder = default_ladder()
    assert ladder.step_names() == ["kernel_boot"]
    r = ladder.run_step("kernel_boot")
    assert r["pass"] is True, json.dumps(r["checks"], indent=2)

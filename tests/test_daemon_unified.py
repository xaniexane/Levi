"""Unified daemon hardening tests (hermetic, stdlib-only)."""

from __future__ import annotations

import pytest

from levi.daemon.unified import UnifiedDaemon


@pytest.fixture()
def daemon(tmp_path):
    return UnifiedDaemon(path=tmp_path / "levi")


def test_compose_validates_task(daemon):
    with pytest.raises(ValueError, match="non-empty string"):
        daemon.compose("")
    with pytest.raises(ValueError, match="non-empty string"):
        daemon.compose(None)  # type: ignore[arg-type]
    comp = daemon.compose("scan market demand gaps")
    assert "demand_pulse" in comp.capabilities
    assert comp.requires_hitl is False
    comp2 = daemon.compose("sell my service, handle payment")
    assert comp2.requires_hitl is True


def test_run_cycle_validates_inputs(daemon):
    with pytest.raises(ValueError, match="non-empty string"):
        daemon.run_cycle("")
    with pytest.raises(ValueError, match="execute"):
        daemon.run_cycle("hello", execute="yes")  # type: ignore[arg-type]


def test_run_cycle_plan_only_is_safe(daemon):
    out = daemon.run_cycle("check status", execute=False)
    assert "HELD (plan-only)" in out
    assert "cycle_start" not in out  # events go to the kernel, not stdout

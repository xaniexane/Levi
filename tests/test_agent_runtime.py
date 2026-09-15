"""AgentRuntime hardening tests (hermetic, stdlib-only)."""

from __future__ import annotations

import pytest

from levi.agent.runtime import AgentRuntime


def test_run_validates_intent_and_max_steps():
    rt = AgentRuntime()
    with pytest.raises(ValueError, match="non-empty string"):
        rt.run("")
    with pytest.raises(ValueError, match="non-empty string"):
        rt.run(None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="max_steps"):
        rt.run("status", max_steps=0)
    with pytest.raises(ValueError, match="max_steps"):
        rt.run("status", max_steps=101)
    with pytest.raises(ValueError, match="max_steps"):
        rt.run("status", max_steps=2.5)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="max_steps"):
        rt.run("status", max_steps=True)  # type: ignore[arg-type]


def test_init_validates_budget():
    with pytest.raises(ValueError, match="budget"):
        AgentRuntime(budget=float("nan"))
    with pytest.raises(ValueError, match="budget"):
        AgentRuntime(budget=-1)
    with pytest.raises(ValueError, match="budget"):
        AgentRuntime(budget="lots")  # type: ignore[arg-type]


def test_run_happy_path():
    rt = AgentRuntime()
    run = rt.run("status")
    assert run.id.startswith("run.")
    assert isinstance(run.final, str)

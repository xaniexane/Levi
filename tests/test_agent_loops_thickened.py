"""Tests for thickened + solidified agentic loops.

- ``delegate`` recursion depth cap (hermetic).
- Runtime policy enforcement: the policy engine is consulted BEFORE each
  specialist action, and anything above the auto-approve threshold halts
  the run honestly without executing.
- Runtime plan / verify / receipt are real, not stubs.
- Deep mode routes specialist work through the step-level tool loop.
"""

from __future__ import annotations

import pytest

from levi.agent import tools as tools_mod
from levi.agent.runtime import AgentRuntime
from levi.agent.tools import ExecContext, build_default_registry
from levi.policy.gates import RiskLevel


# -- delegate depth cap -------------------------------------------------


def test_exec_context_depth_validation():
    ExecContext(depth=0)
    ExecContext(depth=5)
    with pytest.raises(ValueError, match="depth"):
        ExecContext(depth=-1)
    with pytest.raises(ValueError, match="depth"):
        ExecContext(depth=True)
    with pytest.raises(ValueError, match="depth"):
        ExecContext(depth="1")  # type: ignore[arg-type]


def test_delegate_refuses_at_max_depth():
    reg = build_default_registry()
    res = reg.execute(
        "delegate",
        {"task": "recurse forever"},
        ExecContext(depth=tools_mod.MAX_DELEGATE_DEPTH),
    )
    assert res.ok is False
    assert "max delegation depth" in res.error


def test_delegate_increments_depth(monkeypatch):
    captured = {}

    class FakeTranscript:
        ok = True

        def __str__(self):
            return "fake subtask done"

    def fake_run_subtask(task, **kwargs):
        captured["ctx"] = kwargs.get("ctx")
        captured["task"] = task
        return FakeTranscript()

    import levi.agent.loop as loop_mod

    monkeypatch.setattr(loop_mod, "run_subtask", fake_run_subtask)
    reg = build_default_registry()
    res = reg.execute("delegate", {"task": "shallow"}, ExecContext(depth=1))
    assert res.ok is True
    assert captured["ctx"].depth == 2
    assert captured["task"] == "shallow"


# -- runtime policy enforcement -----------------------------------------


def test_runtime_policy_halts_above_threshold_without_executing():
    rt = AgentRuntime(auto_approve_up_to=RiskLevel.INFO)
    run = rt.run("build me an app")
    # coding specialist wants factory_create (MODERATE) > INFO threshold
    assert run.ok is False
    denied = [s for s in run.steps if s.policy == "denied"]
    assert denied, "expected a policy-denied step"
    assert "approval" in denied[0].result.lower()
    # the gated action never executed
    assert not any(
        s.action == "factory_create" and s.policy == "approved" for s in run.steps
    )
    assert any(d["policy"] == "awaiting_permission" for d in run.policy_decisions)


def test_runtime_policy_auto_approves_low_risk():
    rt = AgentRuntime()  # default: auto-approve up to LOW
    run = rt.run("status")
    assert run.ok is True
    assert all(s.policy == "approved" for s in run.steps)
    assert all(s.verified for s in run.steps)


# -- plan / verify / receipt --------------------------------------------


def test_runtime_plan_is_real():
    rt = AgentRuntime()
    run = rt.run("status")
    assert len(run.plan) >= 3  # specialists + verification line
    assert any("supervisor" in line for line in run.plan)
    assert run.plan[-1].startswith(f"{len(run.plan)}.")


def test_runtime_receipt_structure():
    rt = AgentRuntime()
    run = rt.run("remember the sky is blue")
    receipt = run.receipt()
    assert receipt["run_id"] == run.id
    assert receipt["intent"] == "remember the sky is blue"
    assert receipt["ok"] is True
    assert receipt["plan"]
    assert len(receipt["steps"]) == len(run.steps)
    for step in receipt["steps"]:
        assert step["verified"] is True
        assert step["policy"] == "approved"
    assert receipt["policy_decisions"]
    assert receipt["policy_receipts"]  # mark_completed receipts kept


def test_runtime_run_validates_deep_flag():
    rt = AgentRuntime()
    with pytest.raises(ValueError, match="deep"):
        rt.run("status", deep="yes")  # type: ignore[arg-type]


# -- deep mode -----------------------------------------------------------


def test_runtime_deep_mode_routes_through_subloop(monkeypatch):
    class FakeTranscript:
        ok = True

        def __str__(self):
            return "deep work complete"

    seen = {}

    def fake_run_subtask(task, **kwargs):
        seen["task"] = task
        seen["max_steps"] = kwargs.get("max_steps")
        return FakeTranscript()

    import levi.agent.loop as loop_mod

    monkeypatch.setattr(loop_mod, "run_subtask", fake_run_subtask)
    # deep mode runs a whole sub-loop: MODERATE risk, needs approval
    rt = AgentRuntime(auto_approve_up_to=RiskLevel.MODERATE)
    run = rt.run("remember the sky is blue", deep=True)
    assert run.ok is True
    deep_steps = [s for s in run.steps if s.action == "delegate_loop"]
    assert deep_steps, "expected delegate_loop steps in deep mode"
    assert "memory specialist" in seen["task"].lower()
    assert all(s.verified for s in deep_steps)
    assert any("step-level tool loop" in line for line in run.plan)


def test_runtime_deep_mode_honest_when_loop_missing(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        # `from levi.agent import loop` compiles to
        # __import__('levi.agent', ..., fromlist=('loop',), ...).
        if name == "levi.agent" and "loop" in (fromlist or ()):
            raise ImportError("no loop here")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    rt = AgentRuntime(auto_approve_up_to=RiskLevel.MODERATE)
    run = rt.run("remember the sky is blue", deep=True)
    deep_steps = [s for s in run.steps if s.action == "delegate_loop"]
    assert deep_steps
    assert run.ok is False  # honest failure recorded, not swallowed
    assert "unavailable" in deep_steps[0].result.lower()

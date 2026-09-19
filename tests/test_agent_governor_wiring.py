"""Hermetic tests for the usage-governor wiring in ``run_subtask()``
(docs/USAGE_GOVERNOR.md "Integration seam").

The loop must route every model call through a ``GovernedProvider``
(task_id=the task, agent_id="agent-loop"), keep the inner provider's
name for ``provider_name``, and end the run honestly (not crash) when
the governor refuses a call. No network, no user HOME writes.
"""

import json

from levi.agent.loop import run_subtask
from levi.agent.providers import ChatProvider, ChatResponse
from levi.agent.tools import build_default_registry


class _FakeProvider(ChatProvider):
    name = "fake"

    def __init__(self, script):
        self._script = list(script)

    def is_available(self):
        return True

    def chat(self, messages, tools):
        if not self._script:
            return ChatResponse(text="done", model="fake", provider="fake")
        return self._script.pop(0)


def _reg(tmp_path):
    return build_default_registry(
        workspace_root=tmp_path / "ws",
        memory_dir=tmp_path / "mem",
        skills_dir=tmp_path / "skills",
    )


def _ledger(tmp_path):
    ledger = tmp_path / ".levi" / "governor" / "usage.jsonl"
    assert ledger.exists(), "governor must have metered the run"
    return [
        json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()
    ]


def test_governor_meters_run_subtask_calls(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    prov = _FakeProvider(
        [ChatResponse(text="all done", model="fake", provider="fake", prompt_tokens=7)]
    )
    t = run_subtask("do a tiny thing", provider=prov, registry=_reg(tmp_path))
    assert t.ok is True
    records = _ledger(tmp_path)
    assert len(records) >= 1
    assert all(r["agent_id"] == "agent-loop" for r in records)
    assert all(r["task_id"] == "do a tiny thing" for r in records)


def test_governor_keeps_inner_provider_name(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    prov = _FakeProvider([ChatResponse(text="done", model="fake", provider="fake")])
    t = run_subtask("name check", provider=prov, registry=_reg(tmp_path))
    assert t.provider_name == "fake"


def test_governor_refusal_ends_run_honestly(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import sys

    from levi.governor import GovernedProvider as RealGoverned

    class _Refusing(RealGoverned):
        def chat(self, messages, tools):
            return ChatResponse(error="[governor] call refused: cool-down — test")

    monkeypatch.setitem(
        sys.modules["levi.governor"].__dict__, "GovernedProvider", _Refusing
    )
    prov = _FakeProvider([])
    t = run_subtask("refused task", provider=prov, registry=_reg(tmp_path))
    assert t.ok is False
    assert "cool-down" in t.final

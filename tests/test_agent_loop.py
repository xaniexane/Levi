"""Hermetic tests for levi.agent.loop (the step-level tool-using loop).

No network, no user HOME writes: HOME is monkeypatched to a tmp dir by the
root conftest conventions used here, and all providers are scripted fakes.
"""

import json

from levi.agent.loop import run_subtask
from levi.agent.providers import ChatProvider, ChatResponse, ProviderToolCall
from levi.agent.tools import build_default_registry


def _reg(tmp_path):
    return build_default_registry(
        workspace_root=tmp_path / "ws",
        memory_dir=tmp_path / "mem",
        skills_dir=tmp_path / "skills",
    )


class FakeProvider(ChatProvider):
    """Scripted provider: pops one ChatResponse per chat() call."""

    name = "fake"

    def __init__(self, script):
        self._script = list(script)
        self.calls = 0
        self.last_tools = None

    def is_available(self):
        return True

    def chat(self, messages, tools):
        self.calls += 1
        self.last_tools = tools
        if not self._script:
            return ChatResponse(text="done", model="fake", provider="fake")
        return self._script.pop(0)


def _call(name, **args):
    return ProviderToolCall(id="call-1", name=name, arguments=args)


def _resp(text="", calls=None, error=None):
    return ChatResponse(
        text=text,
        tool_calls=calls or [],
        model="fake",
        provider="fake",
        error=error,
    )


# -- (a) the loop executes tool calls and feeds results back -----------------


def test_loop_executes_tools_and_feeds_results_back(tmp_path):
    prov = FakeProvider(
        [
            _resp(calls=[_call("file_write", path="hello.txt", content="line one")]),
            _resp(calls=[_call("file_read", path="hello.txt")]),
            _resp(text="Done; the file contained: line one"),
        ]
    )
    reg = _reg(tmp_path)
    t = run_subtask(
        "write hello.txt then read it back",
        provider=prov,
        registry=reg,
        consent=True,
    )
    assert t.ok is True
    target = tmp_path / "ws" / "hello.txt"
    assert target.is_file()
    assert target.read_text(encoding="utf-8") == "line one"
    assert len(t.steps) == 2
    # the file_read step saw the tool result of the file_write step
    assert t.steps[1].results[0]["tool"] == "file_read"
    assert t.steps[1].results[0]["ok"] is True
    assert "line one" in t.steps[1].results[0]["output"]
    # the final summary honestly mentions what the tool reported
    assert "line one" in t.final


def test_unknown_tool_is_honest_not_fatal(tmp_path):
    prov = FakeProvider(
        [
            _resp(calls=[_call("no_such_tool", x=1)]),
            _resp(text="the tool did not exist, so I did nothing"),
        ]
    )
    reg = _reg(tmp_path)
    t = run_subtask("call a bogus tool", provider=prov, registry=reg, consent=True)
    assert t.ok is True
    assert t.steps[0].results[0]["ok"] is False
    assert "unknown tool" in t.steps[0].results[0]["error"]


# -- (b) max_steps -------------------------------------------------------------


def test_loop_respects_max_steps(tmp_path):
    class AlwaysCalls(FakeProvider):
        def chat(self, messages, tools):
            self.calls += 1
            return _resp(calls=[_call("memory_write", text="note %d" % self.calls)])

    prov = AlwaysCalls([])
    reg = _reg(tmp_path)
    t = run_subtask("anything", provider=prov, registry=reg, consent=True, max_steps=3)
    assert t.ok is False
    assert t.error == "max_steps_exceeded"
    assert len(t.steps) == 3
    assert prov.calls == 3
    assert "step limit" in t.final


# -- (c) the confirmation gate trips honestly --------------------------------


def test_loop_gate_trips_without_consent(tmp_path):
    prov = FakeProvider(
        [
            _resp(calls=[_call("file_write", path="secret.txt", content="x")]),
            _resp(text="this must never be reached"),
        ]
    )
    reg = _reg(tmp_path)
    t = run_subtask(
        "write secret.txt",
        provider=prov,
        registry=reg,
        consent=False,
        confirm=None,
    )
    assert t.ok is False
    assert t.error == "confirmation_required"
    assert "gate tripped" in t.final
    # the gated tool never ran: no file on disk
    assert not (tmp_path / "ws" / "secret.txt").exists()


# -- (d) provider errors -------------------------------------------------------


def test_loop_surfaces_provider_error(tmp_path):
    prov = FakeProvider([_resp(error="upstream exploded")])
    reg = _reg(tmp_path)
    t = run_subtask("anything", provider=prov, registry=reg, consent=True)
    assert t.ok is False
    assert t.error == "upstream exploded"
    assert "upstream exploded" in t.final
    assert t.steps == []


# -- (e) transcript serialization ----------------------------------------------


def test_transcript_to_dict_json_round_trip(tmp_path):
    prov = FakeProvider(
        [
            _resp(calls=[_call("memory_write", text="a note")]),
            _resp(text="noted"),
        ]
    )
    reg = _reg(tmp_path)
    t = run_subtask("remember a note", provider=prov, registry=reg, consent=True)
    d = t.to_dict()
    assert set(d) == {
        "task",
        "provider_name",
        "steps",
        "final",
        "ok",
        "error",
        "prompt_tokens",
        "completion_tokens",
    }
    rt = json.loads(json.dumps(d))
    assert rt == d
    assert rt["task"] == "remember a note"
    assert rt["provider_name"] == "fake"
    assert rt["ok"] is True
    assert isinstance(rt["steps"], list) and len(rt["steps"]) == 1
    assert set(rt["steps"][0]) == {
        "index",
        "provider_text",
        "tool_calls",
        "results",
        "prompt_tokens",
        "completion_tokens",
    }


# -- provider argument forms ---------------------------------------------------


def test_provider_as_instance_uses_that_provider(tmp_path):
    prov = FakeProvider([_resp(text="hello from fake")])
    reg = _reg(tmp_path)
    t = run_subtask("hi", provider=prov, registry=reg, consent=True)
    assert t.provider_name == "fake"
    assert t.ok is True


def test_provider_as_name_string(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_PROVIDER", "local")
    reg = _reg(tmp_path)
    t = run_subtask(
        "remember that the sky is blue", provider="local", registry=reg, consent=True
    )
    assert t.provider_name == "local"
    assert t.ok is True


def test_provider_none_falls_back_to_select_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_PROVIDER", "local")
    reg = _reg(tmp_path)
    t = run_subtask(
        "remember that the sky is blue", provider=None, registry=reg, consent=True
    )
    assert t.provider_name == "local"
    assert t.ok is True


def test_local_provider_end_to_end_through_name_string(tmp_path, monkeypatch):
    """LocalProvider drives a real multi-step file task through the loop."""
    monkeypatch.setenv("LEVI_PROVIDER", "local")
    reg = _reg(tmp_path)
    t = run_subtask(
        "create notes.txt with three lines, read it back",
        provider="local",
        registry=reg,
        consent=True,
    )
    assert t.ok is True
    assert (tmp_path / "ws" / "notes.txt").is_file()
    assert "Contents read" in t.final


# -- (c) input validation ----------------------------------------------------


def test_run_subtask_rejects_blank_task():
    import pytest

    for bad in ("", "   ", None, 123):
        with pytest.raises(ValueError, match="non-empty string"):
            run_subtask(bad)  # type: ignore[arg-type]


def test_run_subtask_rejects_bad_max_steps():
    import pytest

    for bad in (0, -3, 101, "many", None):
        with pytest.raises(ValueError, match="max_steps"):
            run_subtask("do a thing", max_steps=bad)  # type: ignore[arg-type]


def test_run_subtask_rejects_bad_provider_type():
    import pytest

    with pytest.raises(ValueError, match="provider"):
        run_subtask("do a thing", provider=123)  # type: ignore[arg-type]

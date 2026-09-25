"""Hermetic tests for F2: ``agent/chat.py`` adopts ``load_user_context_retrieved``.

Per turn, the chat manager must fetch the query-relevant "what I know
about you" block from the interop retrieval adapter and inject it into
the turn's system prompt — never breaking the turn when retrieval
degrades. No network, no user HOME writes.
"""

import pytest

from levi.agent import chat as chat_mod
from levi.agent.chat import ConversationManager
from levi.agent.providers import ChatProvider, ChatResponse


class _FakeProvider(ChatProvider):
    name = "fake"

    def __init__(self):
        self.chats = []

    def is_available(self):
        return True

    def chat(self, messages, tools):
        self.chats.append((list(messages), list(tools)))
        return ChatResponse(text="fake answer", prompt_tokens=10)


class _Step:
    provider_text = "fake answer"
    tool_calls = []
    results = []


class _Transcript:
    steps = [_Step()]
    final = "fake answer"
    ok = True
    prompt_tokens = 0


@pytest.fixture()
def mgr(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_AGENT_SESSIONS_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("LEVI_MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.delenv("LEVI_CHAT_USER_CONTEXT", raising=False)
    from levi.agent.tools import build_default_registry

    reg = build_default_registry(memory_dir=tmp_path / "mem")
    return ConversationManager("f2", provider=_FakeProvider(), registry=reg)


def _capture_run_subtask(monkeypatch, captured):
    def _fake(task, **kwargs):
        captured.update(kwargs)
        captured["task"] = task
        return _Transcript()

    monkeypatch.setattr(chat_mod, "run_subtask", _fake)


def _patch_adapter(monkeypatch, block):
    import levi.interop.adapters.assistant_retrieval as ar

    calls = {}

    def _fake(store, query, limit=8):
        calls["store"] = store
        calls["query"] = query
        calls["limit"] = limit
        return {"block": block, "method": "hybrid", "entry_ids": [], "note": ""}

    monkeypatch.setattr(ar, "load_user_context_retrieved", _fake)
    return calls


def test_f2_block_injected_into_system_prompt(mgr, monkeypatch):
    captured = {}
    _capture_run_subtask(monkeypatch, captured)
    calls = _patch_adapter(monkeypatch, "- user likes tea\n- user is Chauncey")
    mgr.turn("what should I drink?")
    assert calls["query"] == "what should I drink?"
    assert calls["limit"] == 8
    prompt = captured["system_prompt"]
    assert "user likes tea" in prompt
    assert "user is Chauncey" in prompt
    assert "What LEVI remembers about the user" in prompt


def test_f2_empty_block_leaves_system_prompt_alone(mgr, monkeypatch):
    captured = {}
    _capture_run_subtask(monkeypatch, captured)
    _patch_adapter(monkeypatch, "")
    mgr.turn("hello")
    assert captured["system_prompt"] is None


def test_f2_adapter_raises_still_turns_ok(mgr, monkeypatch):
    import levi.interop.adapters.assistant_retrieval as ar

    monkeypatch.setattr(
        ar,
        "load_user_context_retrieved",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    captured = {}
    _capture_run_subtask(monkeypatch, captured)
    result = mgr.turn("hello")
    assert result.transcript.ok is True
    assert captured["system_prompt"] is None


def test_f2_kill_switch_disables(monkeypatch, tmp_path):
    monkeypatch.setenv("LEVI_AGENT_SESSIONS_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("LEVI_MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("LEVI_CHAT_USER_CONTEXT", "0")
    from levi.agent.tools import build_default_registry

    reg = build_default_registry(memory_dir=tmp_path / "mem")
    m = ConversationManager("f2off", provider=_FakeProvider(), registry=reg)
    captured = {}
    _capture_run_subtask(monkeypatch, captured)

    import levi.interop.adapters.assistant_retrieval as ar

    def _boom(store, query, limit=8):
        raise AssertionError("adapter must not be called with kill switch on")

    monkeypatch.setattr(ar, "load_user_context_retrieved", _boom)
    m.turn("hello")
    assert captured["system_prompt"] is None


def test_f2_existing_system_prompt_preserved(mgr, monkeypatch, tmp_path):
    monkeypatch.setenv("LEVI_AGENT_SESSIONS_DIR", str(tmp_path / "sessions"))
    from levi.agent.tools import build_default_registry

    reg = build_default_registry(memory_dir=tmp_path / "mem")
    m = ConversationManager(
        "f2sp", provider=_FakeProvider(), registry=reg, system_prompt="Be brief."
    )
    captured = {}
    _capture_run_subtask(monkeypatch, captured)
    _patch_adapter(monkeypatch, "- user likes tea")
    m.turn("hello")
    prompt = captured["system_prompt"]
    assert "Be brief." in prompt
    assert "user likes tea" in prompt

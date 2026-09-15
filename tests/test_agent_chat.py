"""Tests for levi.agent.chat: sessions, compression, durable facts."""


import pytest

from levi.agent.chat import (
    COMPRESSION_THRESHOLD,
    ChatSession,
    ConversationManager,
    sanitize_session_name,
)
from levi.agent.providers import ChatProvider, ChatResponse


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def sessions_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_AGENT_SESSIONS_DIR", str(tmp_path))
    return tmp_path


class FakeProvider(ChatProvider):
    """Deterministic stand-in: answers turns, summarizes in the required
    format, and reports token usage."""
    name = "fake"

    def __init__(self, summary_text="SUMMARY: old stuff happened\nFACTS:\n- user likes tea\n",
                 prompt_tokens=100):
        self.summary_text = summary_text
        self.prompt_tokens = prompt_tokens
        self.chats = []

    def is_available(self):
        return True

    def chat(self, messages, tools):
        self.chats.append((list(messages), list(tools)))
        text = messages[-1].content if messages else ""
        if text.startswith("You are compressing"):
            return ChatResponse(text=self.summary_text,
                                prompt_tokens=self.prompt_tokens)
        return ChatResponse(text="fake answer", prompt_tokens=self.prompt_tokens)


# ---------------------------------------------------------------------------
# session names + persistence
# ---------------------------------------------------------------------------


def test_sanitize_session_name_ok():
    assert sanitize_session_name("default") == "default"
    assert sanitize_session_name(" my-chat_2 ") == "my-chat_2"


@pytest.mark.parametrize("bad", ["", "../x", "a/b", "x" * 65, ".hidden", "-x" * 40])
def test_sanitize_session_name_rejects(bad):
    with pytest.raises(ValueError):
        sanitize_session_name(bad)


def test_session_persistence_and_resume(sessions_dir):
    s = ChatSession("persist")
    s.append_message("user", "hello")
    s.append_message("assistant", "hi there")
    s.append_note("a note")
    assert (sessions_dir / "persist.jsonl").exists()

    again = ChatSession("persist")
    msgs = again.messages()
    assert [(m.role, m.content) for m in msgs] == [
        ("user", "hello"), ("assistant", "hi there")]
    assert again.notes() == ["a note"]
    assert again.summary() == (None, 0)


def test_session_summary_records(sessions_dir):
    s = ChatSession("summ")
    s.append_message("user", "one")
    s.append_summary("summary text", covers_messages=1)
    text, covers = s.summary()
    assert text == "summary text"
    assert covers == 1


# ---------------------------------------------------------------------------
# turns: history, persistence, context reporting
# ---------------------------------------------------------------------------


def test_turn_persists_and_uses_history(sessions_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_MODEL_DIR", str(tmp_path / "models"))
    from levi.agent.tools import build_default_registry
    reg = build_default_registry(memory_dir=tmp_path / "mem")
    fake = FakeProvider()
    mgr = ConversationManager("t1", provider=fake, registry=reg)
    r1 = mgr.turn("first message")
    assert r1.transcript.final
    assert r1.context_pct == pytest.approx(100 / mgr.ctx_size)
    # Second turn must receive the earlier exchange as history.
    mgr.turn("second message")
    turn2_msgs = fake.chats[-1][0]
    roles_contents = [(m.role, m.content) for m in turn2_msgs]
    assert ("user", "first message") in roles_contents
    assert ("user", "second message") in roles_contents
    # The session file holds the whole dialogue.
    roles = [r["role"] for r in ChatSession("t1").message_records()]
    assert roles.count("user") == 2


def test_turn_does_not_duplicate_user_message(sessions_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_MODEL_DIR", str(tmp_path / "models"))
    from levi.agent.tools import build_default_registry
    reg = build_default_registry(memory_dir=tmp_path / "mem")
    fake = FakeProvider()
    mgr = ConversationManager("dup", provider=fake, registry=reg)
    mgr.turn("hello world")
    msgs = fake.chats[0][0]
    user_texts = [m.content for m in msgs if m.role == "user"]
    assert user_texts.count("hello world") == 1


# ---------------------------------------------------------------------------
# compression
# ---------------------------------------------------------------------------


def _many_turn_manager(sessions_dir, tmp_path, monkeypatch, provider,
                       ctx_size=600, turns=8):
    monkeypatch.setenv("LEVI_MODEL_DIR", str(tmp_path / "models"))
    from levi.agent.tools import build_default_registry
    reg = build_default_registry(memory_dir=tmp_path / "mem")
    mgr = ConversationManager("cmp", provider=provider, registry=reg,
                              ctx_size=ctx_size)
    results = [mgr.turn("note %d about topic alpha" % i) for i in range(turns)]
    return mgr, results


def test_compression_triggers_and_never_deletes(sessions_dir, tmp_path, monkeypatch):
    from levi.agent.providers import LocalProvider
    mgr, results = _many_turn_manager(
        sessions_dir, tmp_path, monkeypatch, LocalProvider())
    assert any(r.compressed for r in results), "compression should trigger"
    summary, covers = mgr.session.summary()
    assert summary and covers > 0
    # Original messages are all still in the log.
    assert len(mgr.session.message_records()) > covers
    # Working context starts after the covered prefix.
    ctx = mgr._context_messages()
    assert ctx[0].content.startswith("[Rolling summary")
    assert len(ctx) < len(mgr.session.messages())
    # A note explains what happened.
    assert any("compressed" in n for n in mgr.session.notes())


def test_compression_summarizes_with_model_and_stores_facts(
        sessions_dir, tmp_path, monkeypatch):
    fake = FakeProvider()
    mgr, results = _many_turn_manager(
        sessions_dir, tmp_path, monkeypatch, fake)
    assert any(r.compressed for r in results)
    summary, _ = mgr.session.summary()
    assert "old stuff happened" in summary
    # Durable facts persisted via memory_write into the session facts file.
    assert "user likes tea" in mgr.read_facts()
    # The summary request went to the model in the required format.
    summary_calls = [c for c in fake.chats if c[0][-1].content.startswith("You are compressing")]
    assert summary_calls
    assert "SUMMARY:" in summary_calls[0][0][-1].content
    assert "FACTS:" in summary_calls[0][0][-1].content


def test_compression_failure_keeps_history(sessions_dir, tmp_path, monkeypatch):
    fake = FakeProvider(summary_text="")  # model returns nothing usable
    mgr, results = _many_turn_manager(
        sessions_dir, tmp_path, monkeypatch, fake)
    assert any(r.compressed for r in results)
    summary, covers = mgr.session.summary()
    assert "summarization failed" in summary
    # Nothing was dropped: records still complete, context keeps everything.
    assert len(mgr.session.message_records()) > covers


def test_parse_summary_response_tolerant():
    parse = ConversationManager._parse_summary_response
    s, facts = parse("SUMMARY: hello world\nFACTS:\n- likes tea\n- works late\n")
    assert s == "hello world"
    assert facts == ["likes tea", "works late"]
    s2, facts2 = parse("just some text")
    assert s2 == "just some text" and facts2 == []


def test_threshold_constant_sane():
    assert 0.5 < COMPRESSION_THRESHOLD < 1.0

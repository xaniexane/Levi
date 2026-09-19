"""Hermetic tests for F1: bot ``research-brief`` adopts ``research_brief_rag``.

``_handle_research_brief`` must prefer the cited RAG path and fall through
to the agent-runtime path only when RAG has nothing to cite. No network,
no user HOME writes.
"""

import pytest

from levi.bot.services import ServiceResult, _handle_research_brief


@pytest.fixture()
def online_hermetic(tmp_path, monkeypatch):
    """Hermetic but *not* offline: the RAG/runtime paths are exercised."""
    monkeypatch.setenv("LEVI_BOT_HOME", str(tmp_path / "bothome"))
    monkeypatch.delenv("LEVI_BOT_OFFLINE", raising=False)
    monkeypatch.delenv("LEVI_BOT_PROVIDER", raising=False)
    monkeypatch.delenv("LEVI_PROVIDER", raising=False)
    return tmp_path


class _FakeStore:
    def list(self, **kwargs):
        return []


def _patch_rag(monkeypatch, result=None, exc=None):
    import levi.interop.adapters.bot_rag as bot_rag
    import levi.memory.store as mem_store

    monkeypatch.setattr(mem_store, "MemoryStore", lambda: _FakeStore())

    calls = {}

    def _fake(topic, store):
        calls["topic"] = topic
        calls["store"] = store
        if exc is not None:
            raise exc
        return result

    monkeypatch.setattr(bot_rag, "research_brief_rag", _fake)
    return calls


def _patch_runtime(monkeypatch, final="RUNTIME BRIEF BODY"):
    import levi.agent.loop as loop

    class _Transcript:
        def __init__(self):
            self.final = final

    monkeypatch.setattr(loop, "run_subtask", lambda *a, **k: _Transcript())


def test_f1_rag_ok_short_circuits_runtime(online_hermetic, monkeypatch):
    calls = _patch_rag(
        monkeypatch,
        result={
            "ok": True,
            "report": "RESEARCH BRIEF on 'x' (cited)",
            "citations": ["mem-1", "mem-2"],
            "notice": "",
            "method": "rag",
        },
    )
    res = _handle_research_brief({"topic": "post-quantum TLS"})
    assert isinstance(res, ServiceResult)
    assert res.ok is True
    assert "RESEARCH BRIEF on 'x' (cited)" in res.report
    assert res.notes == ["mem-1", "mem-2"]
    assert calls["topic"] == "post-quantum TLS"
    assert isinstance(calls["store"], _FakeStore)
    assert res.files == []  # RAG path writes no brief file


def test_f1_rag_not_ok_falls_through_to_runtime(online_hermetic, monkeypatch):
    _patch_rag(monkeypatch, result={"ok": False, "report": "nothing", "citations": []})
    _patch_runtime(monkeypatch, final="RUNTIME BRIEF BODY")
    res = _handle_research_brief({"topic": "post-quantum TLS"})
    assert res.ok is True
    assert "RUNTIME BRIEF BODY" in res.report
    assert len(res.files) == 1  # runtime path still writes the dated brief file


def test_f1_rag_raises_still_falls_through(online_hermetic, monkeypatch):
    _patch_rag(monkeypatch, exc=RuntimeError("pipeline exploded"))
    _patch_runtime(monkeypatch, final="RUNTIME BRIEF BODY")
    res = _handle_research_brief({"topic": "post-quantum TLS"})
    assert res.ok is True
    assert "RUNTIME BRIEF BODY" in res.report


def test_f1_blank_topic_still_raises(online_hermetic, monkeypatch):
    from levi.bot.services import ServiceError

    _patch_rag(monkeypatch, result={"ok": True, "report": "x", "citations": []})
    with pytest.raises(ServiceError):
        _handle_research_brief({"topic": "   "})

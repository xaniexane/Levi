"""Hermetic tests for levi.agent.growth_context.

Read-only retrieval of growth-loop learnings for the agent runtime.
Synthetic MemoryStore only — never the real ~/.levi.
"""

from __future__ import annotations

from pathlib import Path

from levi.agent import growth_context as gc
from levi.memory.store import MemoryStore
from levi.memory.types import MemoryType


def _store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(data_dir=tmp_path / "memory")


def _learning(store: MemoryStore, content: str, tags, **md) -> None:
    metadata = {"kind": "procedural", "confidence": 0.8, "status": "provisional"}
    metadata.update(md)
    store.add(
        memory_type=MemoryType("semantic"),
        content=content,
        importance=0.7,
        source="growth",
        tags=list(tags),
        metadata=metadata,
    )


def _seed(store: MemoryStore) -> None:
    _learning(
        store,
        "Growth distribution: learning routed to subsystem(s): agent.\n"
        "Learning [procedural · conf 0.80]: when the user asks to create a "
        "file, always confirm the target path before writing.",
        ["growth", "levi-learned", "distribution", "agent"],
        cycle_id="c1",
    )
    _learning(
        store,
        "Growth distribution: learning routed to subsystem(s): finance.\n"
        "Learning [fact · conf 0.60]: paper trading fills are simulated.",
        ["growth", "levi-learned", "distribution", "finance"],
        kind="fact",
        confidence=0.6,
        cycle_id="c1",
    )
    # Not growth-tagged: must never surface.
    store.add(
        memory_type=MemoryType("semantic"),
        content="the user likes dark mode",
        importance=0.9,
        source="user",
        tags=["preference"],
        metadata={},
    )


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


def test_returns_relevant_growth_learnings(tmp_path):
    store = _store(tmp_path)
    _seed(store)
    out = gc.recent_learnings("create a file for me", store=store)
    assert out, "expected the agent learning to be returned"
    assert any("confirm the target path" in item["content"] for item in out)
    for item in out:
        assert set(item) >= {"content", "kind", "confidence", "subsystems", "cycle_id"}


def test_non_growth_entries_never_surface(tmp_path):
    store = _store(tmp_path)
    _seed(store)
    out = gc.recent_learnings("dark mode", store=store)
    assert not any("dark mode" in item["content"] for item in out)


def test_agent_subsystem_preferred_for_agent_tasks(tmp_path):
    store = _store(tmp_path)
    _seed(store)
    out = gc.recent_learnings("run the agent tool loop", store=store, limit=5)
    assert out[0]["subsystems"] and "agent" in out[0]["subsystems"]


def test_empty_store_returns_empty(tmp_path):
    store = _store(tmp_path)
    assert gc.recent_learnings("anything", store=store) == []


def test_broken_store_returns_empty_not_raise(tmp_path):
    class Broken:
        def list(self, **kwargs):
            raise RuntimeError("disk on fire")

    assert gc.recent_learnings("anything", store=Broken()) == []


def test_limit_is_clamped(tmp_path):
    store = _store(tmp_path)
    for i in range(15):
        _learning(
            store,
            f"Growth distribution: learning routed to subsystem(s): general. "
            f"Learning [fact · conf 0.50]: synthetic learning number {i}.",
            ["growth", "levi-learned", "distribution", "general"],
            kind="fact",
            confidence=0.5,
        )
    out = gc.recent_learnings("synthetic", store=store, limit=999)
    assert 1 <= len(out) <= gc.MAX_LIMIT


def test_disabled_via_env(tmp_path, monkeypatch):
    store = _store(tmp_path)
    _seed(store)
    monkeypatch.setenv("LEVI_GROWTH_CONTEXT", "0")
    assert gc.recent_learnings("create a file", store=store) == []
    assert not gc.enabled()


# ---------------------------------------------------------------------------
# Read-only guarantee
# ---------------------------------------------------------------------------


def test_retrieval_writes_nothing(tmp_path):
    store = _store(tmp_path)
    _seed(store)
    before = store.list(tags=["growth"], limit=5000)
    gc.recent_learnings("create a file", store=store)
    after = store.list(tags=["growth"], limit=5000)
    assert [e.id for e in before] == [e.id for e in after]
    assert len(after) == 2


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def test_format_block_empty():
    assert gc.format_block([]) == ""


def test_format_block_labels_advisory(tmp_path):
    store = _store(tmp_path)
    _seed(store)
    out = gc.recent_learnings("create a file", store=store)
    block = gc.format_block(out)
    assert "growth loop" in block
    assert "advisory" in block.lower()
    assert "provisional" in block


def test_context_addendum_empty_when_nothing_relevant(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert gc.context_addendum("anything at all", home=tmp_path) == ""


def test_unrelated_task_gets_no_learnings_despite_high_importance(tmp_path):
    # Relevance requires evidence (term hit or subsystem match):
    # importance alone must not leak unrelated learnings into a turn.
    store = _store(tmp_path)
    _learning(
        store,
        "Learning [fact · conf 0.99]: rebalance the paper portfolio quarterly.",
        ["growth", "levi-learned", "distribution", "finance"],
        importance=1.0,
        kind="fact",
        confidence=0.99,
        cycle_id="c2",
    )
    out = gc.recent_learnings("fix the garden sprinkler", store=store)
    assert out == []


def test_only_matching_learnings_returned_for_task(tmp_path):
    store = _store(tmp_path)
    _seed(store)
    out = gc.recent_learnings("create a file for me", store=store, limit=5)
    assert any("confirm the target path" in item["content"] for item in out)
    assert not any("paper trading" in item["content"] for item in out)


def test_context_addendum_reads_home_store(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    store = MemoryStore(data_dir=tmp_path / ".levi" / "memory")
    _learning(
        store,
        "Growth distribution: learning routed to subsystem(s): agent.\n"
        "Learning [procedural · conf 0.90]: summarize tool output before "
        "the final answer.",
        ["growth", "levi-learned", "distribution", "agent"],
        confidence=0.9,
        cycle_id="c9",
    )
    add = gc.context_addendum("summarize the agent run")
    assert "summarize tool output" in add


# ---------------------------------------------------------------------------
# Tool wiring (levi.agent.tools :: growth_context)
# ---------------------------------------------------------------------------


def test_growth_context_tool_in_default_registry(tmp_path):
    from levi.agent.tools import build_default_registry

    reg = build_default_registry(
        workspace_root=tmp_path / "ws",
        memory_dir=tmp_path / "mem",
        skills_dir=tmp_path / "skills",
    )
    tool = reg.get("growth_context")
    assert tool is not None
    assert "Read-only" in tool.description


def test_growth_context_tool_returns_learnings(tmp_path, monkeypatch):
    from levi.agent.tools import build_default_registry

    monkeypatch.setenv("HOME", str(tmp_path))
    store = MemoryStore(data_dir=tmp_path / ".levi" / "memory")
    _seed(store)
    reg = build_default_registry(
        workspace_root=tmp_path / "ws",
        memory_dir=tmp_path / "mem",
        skills_dir=tmp_path / "skills",
    )
    res = reg.execute("growth_context", {"query": "create a file with the agent"}, None)
    assert res.ok
    assert "confirm the target path" in res.output


def test_growth_context_tool_requires_query(tmp_path):
    from levi.agent.tools import build_default_registry

    reg = build_default_registry(
        workspace_root=tmp_path / "ws",
        memory_dir=tmp_path / "mem",
        skills_dir=tmp_path / "skills",
    )
    res = reg.execute("growth_context", {"query": "  "}, None)
    assert not res.ok


def test_growth_context_tool_honest_when_empty(tmp_path, monkeypatch):
    from levi.agent.tools import build_default_registry

    monkeypatch.setenv("HOME", str(tmp_path))
    reg = build_default_registry(
        workspace_root=tmp_path / "ws",
        memory_dir=tmp_path / "mem",
        skills_dir=tmp_path / "skills",
    )
    res = reg.execute("growth_context", {"query": "nothing matches this"}, None)
    assert res.ok
    assert "No relevant growth learnings" in res.output

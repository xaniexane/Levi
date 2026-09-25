"""Behavior-change integration test: growth learnings reach the agent.

``run_subtask(..., growth=True)`` must inject relevant growth-tagged memory
entries into the provider's system prompt; ``growth=False`` (or no memory)
must leave it out. The stub provider captures what it was sent, so this
proves the behavior change end to end rather than only testing
``growth_context`` in isolation.

Synthetic fixtures only — a throwaway ``LEVI_HOME``; no real user memory
is touched.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from levi.agent import loop as loop_mod
from levi.agent.providers import ChatMessage, ChatProvider, ChatResponse
from levi.memory.store import MemoryStore
from levi.memory.types import MemoryType


class _CaptureProvider(ChatProvider):
    name = "capture"

    def __init__(self) -> None:
        self.systems: list[str] = []

    def is_available(self) -> bool:
        return True

    def chat(self, messages: list[ChatMessage], tools: list[dict]) -> ChatResponse:
        system = "\n".join(m.content for m in messages if m.role == "system")
        self.systems.append(system)
        return ChatResponse(text="done", tool_calls=[])


def _seed_learning(
    home: Path, content: str, tags: list[str], importance: float = 0.9
) -> None:
    store = MemoryStore(data_dir=home / "memory")
    store.add(
        memory_type=MemoryType("semantic"),
        content=content,
        importance=importance,
        source="growth",
        tags=tags,
        metadata={"kind": "fact", "status": "provisional"},
    )


@pytest.fixture()
def home_with_learning(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    _seed_learning(
        tmp_path,
        "Learning [fact]: the user prefers concise summaries for weekly reports.",
        ["growth", "levi-learned", "weekly-reports"],
    )
    return tmp_path


def test_growth_true_injects_learning_into_system_prompt(
    home_with_learning: Path,
) -> None:
    prov = _CaptureProvider()
    loop_mod.run_subtask(
        "draft the weekly report",
        provider=prov,
        registry=loop_mod.ToolRegistry(),
        growth=True,
        max_steps=1,
    )
    assert prov.systems, "provider never received a system prompt"
    assert "concise summaries" in prov.systems[0]
    assert "provisional" in prov.systems[0].lower()


def test_growth_false_omits_learning(home_with_learning: Path) -> None:
    prov = _CaptureProvider()
    loop_mod.run_subtask(
        "draft the weekly report",
        provider=prov,
        registry=loop_mod.ToolRegistry(),
        growth=False,
        max_steps=1,
    )
    assert prov.systems
    assert "concise summaries" not in prov.systems[0]


def test_empty_memory_store_still_runs_without_growth_section(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    prov = _CaptureProvider()
    loop_mod.run_subtask(
        "draft the weekly report",
        provider=prov,
        registry=loop_mod.ToolRegistry(),
        growth=True,
        max_steps=1,
    )
    assert prov.systems
    assert "Growth learnings" not in prov.systems[0]


def test_non_growth_entries_never_leak(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    _seed_learning(
        tmp_path,
        "secret project codename midnight",
        ["personal"],
        importance=1.0,
    )
    prov = _CaptureProvider()
    loop_mod.run_subtask(
        "summarize my notes",
        provider=prov,
        registry=loop_mod.ToolRegistry(),
        growth=True,
        max_steps=1,
    )
    assert prov.systems
    assert "midnight" not in prov.systems[0]

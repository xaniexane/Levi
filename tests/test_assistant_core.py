"""Hermetic tests for core/levi/agent/assistant.py.

No network, isolated memory store (MemoryStore pointed at a tmp dir),
no dependency on the rest of the agent runtime.
"""

import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "core"))

from levi.agent.assistant import (  # noqa: E402
    assistant_system_prompt,
    build_agent_prompt,
    candidate_learnings,
    load_user_context,
)
from levi.memory.store import MemoryStore  # noqa: E402
from levi.memory.types import MemoryType  # noqa: E402

# ---------------------------------------------------------------------------
# Prompt content: behavior + identity
# ---------------------------------------------------------------------------

_SYCOPHANCY_MARKERS = (
    "great question",
    "i'd be happy to help",
    "excellent question",
    "thanks for asking",
)

_IDENTITY_CLAIM_PATTERNS = (
    re.compile(r"\bi am muse\b", re.I),
    re.compile(r"\bi'm muse\b", re.I),
    re.compile(r"\bi am grok\b", re.I),
    re.compile(r"\byou are muse\b", re.I),
    re.compile(r"\byou are grok\b", re.I),
    re.compile(r"\ban (anthropic|xai|openai|google|meta) (product|assistant|model)\b", re.I),
)

_PROVIDER_AS_IDENTITY = re.compile(
    r"\b(i am|i'm|you are)\s+(Muse|Grok|ChatGPT|Gemini|Copilot)\b"
)


def test_prompt_names_levi_identity():
    prompt = assistant_system_prompt()
    assert "LEVI" in prompt


def test_prompt_has_no_sycophancy_markers():
    # Markers may only appear as *negated* examples ("no 'Great
    # question!' filler") — never as affirmative praise.
    prompt = assistant_system_prompt()
    for marker in _SYCOPHANCY_MARKERS:
        for match in re.finditer(marker, prompt, re.I):
            before = prompt[max(0, match.start() - 8):match.start()].lower()
            assert "no" in before, (
                "unaffirmed sycophancy marker found: %r" % marker
            )


def test_prompt_makes_no_identity_claims():
    prompt = assistant_system_prompt()
    for pat in _IDENTITY_CLAIM_PATTERNS:
        assert not pat.search(prompt), "identity claim pattern matched: %s" % pat.pattern
    assert not _PROVIDER_AS_IDENTITY.search(prompt)


def test_prompt_mentions_muse_only_as_reference():
    prompt = assistant_system_prompt().lower()
    assert "muse" in prompt  # the reference paragraph exists
    assert "not a claim of" in prompt or "reference" in prompt


def test_prompt_custom_identity():
    prompt = assistant_system_prompt(identity="TESTBOT")
    assert "TESTBOT" in prompt
    assert "LEVI" not in prompt


def test_prompt_is_composable_plain_text():
    prompt = assistant_system_prompt()
    assert isinstance(prompt, str) and len(prompt) > 200


# ---------------------------------------------------------------------------
# load_user_context
# ---------------------------------------------------------------------------


def _seeded_store(tmp_path):
    store = MemoryStore(data_dir=tmp_path / "memory")
    store.add(MemoryType.PREFERENCE, "Chauncey prefers concise answers", importance=0.9)
    store.add(MemoryType.PREFERENCE, "Chauncey likes dark mode", importance=0.5)
    store.add(MemoryType.SEMANTIC, "LEVI is a local-first assistant", importance=0.8)
    store.add(MemoryType.RELATIONSHIP, "Chauncey is the owner", importance=0.7)
    store.add(MemoryType.WORKING, "current task: testing", importance=0.9)
    return store


def test_load_user_context_empty_store_returns_empty(tmp_path):
    store = MemoryStore(data_dir=tmp_path / "memory")
    assert load_user_context(store=store) == ""


def test_load_user_context_preferences_first_and_capped(tmp_path):
    store = _seeded_store(tmp_path)
    block = load_user_context(store=store, limit=3)
    assert block.startswith("What I know about you")
    lines = [ln for ln in block.splitlines() if ln.startswith("- [")]
    assert len(lines) == 3
    # preferences come before semantic/relationship entries
    assert lines[0].startswith("- [preference]")
    assert lines[1].startswith("- [preference]")


def test_load_user_context_includes_facts_and_relationships(tmp_path):
    store = _seeded_store(tmp_path)
    block = load_user_context(store=store, limit=12)
    assert "concise answers" in block
    assert "local-first assistant" in block
    assert "owner" in block


def test_load_user_context_fail_soft_on_broken_store():
    class Broken:
        def list(self, *a, **k):
            raise RuntimeError("boom")

    assert load_user_context(store=Broken()) == ""


def test_load_user_context_never_raises_on_garbage():
    assert load_user_context(store=object()) == ""
    assert load_user_context(store=None, limit=5) in ("", load_user_context(store=None, limit=5))


# ---------------------------------------------------------------------------
# candidate_learnings
# ---------------------------------------------------------------------------


def test_candidate_learnings_remember_that():
    cands = candidate_learnings("Please remember that my dog is named Biscuit.")
    assert len(cands) == 1
    cand = cands[0]
    assert cand["kind"] == "fact"
    assert "Biscuit" in cand["content"]
    assert cand["confidence"] == "heuristic"
    assert cand["source"] == "assistant-core"


def test_candidate_learnings_i_prefer():
    cands = candidate_learnings("I prefer short answers with no fluff.")
    assert any(
        c["kind"] == "preference" and "short answers" in c["content"]
        for c in cands
    )
    assert all(c["confidence"] == "heuristic" for c in cands)


def test_candidate_learnings_call_me_and_correction():
    cands = candidate_learnings("Call me Chauncey. Actually, my timezone is America/Chicago.")
    kinds = {c["kind"] for c in cands}
    assert "preference" in kinds
    assert "fact" in kinds


def test_candidate_learnings_ignores_smalltalk():
    assert candidate_learnings("hey, how's it going?") == []
    assert candidate_learnings("") == []
    assert candidate_learnings(None) == []
    assert candidate_learnings(123) == []


def test_candidate_learnings_deduplicates():
    cands = candidate_learnings("Remember that x is y. Remember that x is y.")
    assert len(cands) == 1


def test_candidate_learnings_record_shape():
    cands = candidate_learnings("I love dark mode.")
    assert cands
    for cand in cands:
        assert set(cand.keys()) == {"content", "kind", "confidence", "source"}


# ---------------------------------------------------------------------------
# build_agent_prompt
# ---------------------------------------------------------------------------


def test_build_agent_prompt_composes_core_then_context(tmp_path):
    store = _seeded_store(tmp_path)
    prompt = build_agent_prompt("hello", store=store)
    core_idx = prompt.index("Genuinely helpful")
    ctx_idx = prompt.index("What I know about you")
    assert core_idx < ctx_idx  # core first, context second


def test_build_agent_prompt_without_context_is_core_only(tmp_path):
    store = MemoryStore(data_dir=tmp_path / "memory")
    prompt = build_agent_prompt("hello", store=store)
    assert "What I know about you" not in prompt
    assert "LEVI" in prompt


def test_build_agent_prompt_never_raises():
    assert isinstance(build_agent_prompt("", store=object()), str)

"""Tests for levi.growth — raising baby Levi.

Covers: experience harvesting (sessions + watermark idempotency),
rule-based reflection, consolidation (dedup/corroboration), the journal,
a full dry-run cycle, and the forget path. All hermetic: sessions,
growth dir, and memory store are pointed at tmp_path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from levi.growth import cycle as growth_cycle
from levi.growth import journal as growth_journal
from levi.growth.consolidate import consolidate
from levi.growth.experience import Experience, harvest_sessions
from levi.growth.reflect import Learning, reflect_rules
from levi.memory.store import MemoryStore
from levi.memory.types import MemoryType


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def env(tmp_path, monkeypatch):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    growth = tmp_path / "growth"
    mem = tmp_path / "memory"
    monkeypatch.setenv("LEVI_AGENT_SESSIONS_DIR", str(sessions))
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(growth))
    return {"sessions": sessions, "growth": growth, "mem": mem}


def _write_session(sessions: Path, name: str, records: list[dict]) -> None:
    p = sessions / f"{name}.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _sample_records() -> list[dict]:
    return [
        {
            "kind": "message",
            "role": "user",
            "ts": "2026-09-15T10:00:00Z",
            "content": "Please remember that I prefer dark mode in every app.",
        },
        {
            "kind": "message",
            "role": "assistant",
            "ts": "2026-09-15T10:00:05Z",
            "content": "Got it, I'll remember you prefer dark mode.",
        },
        {
            "kind": "message",
            "role": "user",
            "ts": "2026-09-15T10:01:00Z",
            "content": "No, that's wrong — I meant dark mode only for the terminal.",
        },
        {
            "kind": "message",
            "role": "user",
            "ts": "2026-09-15T10:02:00Z",
            "content": "Remember that my backup drive is mounted at /mnt/backup.",
        },
        {
            "kind": "summary",
            "ts": "2026-09-15T10:03:00Z",
            "content": "User set a dark-mode preference and corrected its scope to terminal only.",
            "covers_messages": 4,
        },
    ]


# ---------------------------------------------------------------------------
# harvesting
# ---------------------------------------------------------------------------


def test_harvest_sessions_kinds(env):
    _write_session(env["sessions"], "chat1", _sample_records())
    exps, marks = harvest_sessions()
    kinds = [e.kind for e in exps]
    assert "user-said" in kinds
    assert "levi-did" in kinds
    assert "distilled" in kinds
    assert marks["chat1"] == "2026-09-15T10:03:00Z"
    assert all(e.source == "chat1" for e in exps)


def test_harvest_watermark_idempotent(env):
    _write_session(env["sessions"], "chat1", _sample_records())
    exps1, marks = harvest_sessions()
    assert exps1
    exps2, _ = harvest_sessions(since=marks)
    assert exps2 == []


def test_harvest_skips_tiny_and_malformed(env):
    _write_session(
        env["sessions"],
        "chat2",
        [
            {
                "kind": "message",
                "role": "user",
                "ts": "2026-09-15T11:00:00Z",
                "content": "ok",
            },
            {
                "kind": "message",
                "role": "user",
                "ts": "2026-09-15T11:01:00Z",
                "content": "",
            },
            {"no-kind": True},
            "not json at all",
        ],
    )
    exps, _ = harvest_sessions()
    assert exps == []


# ---------------------------------------------------------------------------
# reflection (rules)
# ---------------------------------------------------------------------------


def test_reflect_rules_preference_and_fact():
    exps = [
        Experience(
            id="1",
            kind="user-said",
            source="s",
            ts="t",
            content="I prefer concise answers, please always keep them short.",
        ),
        Experience(
            id="2",
            kind="user-said",
            source="s",
            ts="t",
            content="Remember that the staging URL is https://staging.example.com.",
        ),
    ]
    learnings = reflect_rules(exps)
    kinds = {learning.kind for learning in learnings}
    assert "preference" in kinds
    assert "fact" in kinds
    assert all(learning.confidence > 0 for learning in learnings)
    assert all(learning.provenance.get("mode") == "rules" for learning in learnings)


def test_reflect_rules_correction():
    exps = [
        Experience(
            id="1",
            kind="user-said",
            source="s",
            ts="t",
            content="No, that's wrong — I meant the blue one, not the red one.",
        ),
    ]
    learnings = reflect_rules(exps)
    assert any(learning.kind == "correction" for learning in learnings)


def test_reflect_rules_tool_trouble():
    exps = [
        Experience(
            id=f"t{i}",
            kind="levi-did",
            source="s",
            ts="t",
            content=f"[tool web_fetch] error: connection failed ({i})",
        )
        for i in range(3)
    ]
    learnings = reflect_rules(exps)
    proc = [learning for learning in learnings if learning.kind == "procedural"]
    assert proc and "web_fetch" in proc[0].content


def test_reflect_rules_empty():
    assert reflect_rules([]) == []


def test_reflect_never_claims_sentience():
    exps = [
        Experience(
            id="1",
            kind="user-said",
            source="s",
            ts="t",
            content="Remember that I prefer dark mode.",
        ),
        Experience(id="2", kind="levi-did", source="s", ts="t", content="Understood."),
    ]
    for learning in reflect_rules(exps):
        low = learning.content.lower()
        assert "i feel" not in low and "conscious" not in low and "sentient" not in low


# ---------------------------------------------------------------------------
# consolidation
# ---------------------------------------------------------------------------


def _learning(kind, content, conf=0.8):
    return Learning(
        kind=kind, content=content, confidence=conf, provenance={"mode": "rules"}
    )


def test_consolidate_writes_typed_memories(env):
    store = MemoryStore(data_dir=env["mem"])
    rep = consolidate(
        [
            _learning("preference", "The user prefers concise answers in every app."),
            _learning("fact", "The staging URL is https://staging.example.com."),
            _learning(
                "procedural", "When web_fetch fails twice, re-check arguments first."
            ),
        ],
        cycle_id="cyc-test",
        store=store,
    )
    assert rep["accepted"] == 3 and rep["corroborated"] == 0
    assert len(rep["writes"]) == 3
    entries = store.list(limit=100)
    types = {e.memory_type for e in entries}
    assert MemoryType.PREFERENCE in types
    assert MemoryType.SEMANTIC in types
    assert MemoryType.PROCEDURAL in types
    assert all("growth" in e.tags and e.source == "growth" for e in entries)
    assert all(e.metadata.get("status") == "provisional" for e in entries)


def test_consolidate_dedup_corroborates(env):
    store = MemoryStore(data_dir=env["mem"])
    l1 = _learning("preference", "The user prefers concise answers in every app.")
    consolidate([l1], cycle_id="cyc-1", store=store)
    l2 = _learning("preference", "User prefers concise answers in all applications.")
    rep = consolidate([l2], cycle_id="cyc-2", store=store)
    assert rep["accepted"] == 0 and rep["corroborated"] == 1
    entries = [e for e in store.list(limit=100) if "growth" in e.tags]
    assert len(entries) == 1
    assert entries[0].metadata["corroborated_count"] == 1
    assert entries[0].importance > 0.8  # bumped


def test_consolidate_dry_run_writes_nothing(env):
    store = MemoryStore(data_dir=env["mem"])
    rep = consolidate(
        [_learning("fact", "The sky is blue on clear days.")],
        cycle_id="cyc-dry",
        store=store,
        dry_run=True,
    )
    assert rep["accepted"] == 1 and rep["writes"] == []
    assert store.stats()["total"] == 0


# ---------------------------------------------------------------------------
# journal + cycle
# ---------------------------------------------------------------------------


def test_journal_append_and_read(env):
    rec = growth_journal.append_entry({"kind": "cycle", "experiences": 5})
    assert rec["id"] and rec["ts"]
    entries = growth_journal.read_entries()
    assert entries and entries[0]["id"] == rec["id"]


def test_developmental_stages():
    # compatibility shim: cycles stand in for days_active under the
    # nightly cadence; corroborations/curriculum_units are unavailable
    # here and count as 0, which can only under-advance the stage
    assert growth_journal.developmental_stage(0, 0)[0] == "newborn"
    assert growth_journal.developmental_stage(1, 1)[0] == "sprouting"
    assert growth_journal.developmental_stage(10, 3)[0] == "curious"
    assert growth_journal.developmental_stage(30, 8)[0] == "curious"
    assert growth_journal.developmental_stage(120, 40)[0] == "curious"


def test_full_cycle_dry_run(env):
    _write_session(env["sessions"], "chat1", _sample_records())
    report = growth_cycle.run_cycle(use_model=False, dry_run=True)
    assert report["experiences"] > 0
    assert report["mode"] == "rules"
    assert report["learnings_proposed"] > 0
    assert report["consolidation"]["accepted"] > 0
    # dry run: no watermark advance, no journal
    assert growth_journal.load_state().get("cycles", 0) == 0
    assert growth_journal.read_entries() == []


def test_full_cycle_writes_and_idempotent(env):
    _write_session(env["sessions"], "chat1", _sample_records())
    store = MemoryStore(data_dir=env["mem"])
    r1 = growth_cycle.run_cycle(use_model=False, store=store)
    assert r1["consolidation"]["accepted"] > 0
    assert not r1["quiet"]
    # second run: nothing new → quiet, no new learnings
    r2 = growth_cycle.run_cycle(use_model=False, store=store)
    assert r2["quiet"] and r2["experiences"] == 0
    assert r2["learnings_proposed"] == 0
    state = growth_journal.load_state()
    assert state["cycles"] == 2
    entries = growth_journal.read_entries(limit=5)
    assert len(entries) == 2 and entries[0]["quiet"]


def test_cycle_quiet_when_no_sessions(env):
    report = growth_cycle.run_cycle(use_model=False, dry_run=True)
    assert report["quiet"] and report["experiences"] == 0


def test_status_dashboard(env):
    _write_session(env["sessions"], "chat1", _sample_records())
    store = MemoryStore(data_dir=env["mem"])
    growth_cycle.run_cycle(use_model=False, store=store)
    s = growth_cycle.status(store=store)
    assert s["stage"] in ("sprouting", "curious", "growing")
    assert s["cycles_completed"] == 1
    assert s["learnings_consolidated"] > 0
    assert s["experiences_pending"] == 0
    assert s["last_cycle"]["accepted"] > 0


def test_forget_path_removes_learnings(env):
    store = MemoryStore(data_dir=env["mem"])
    rep = consolidate(
        [_learning("fact", "Levi learned the staging URL today.")],
        cycle_id="cyc-f",
        store=store,
    )
    eid = rep["writes"][0]
    assert store.delete(eid)
    assert store.get(eid) is None

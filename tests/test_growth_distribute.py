"""Tests for levi.growth.distribute (MEGAZORD AXIS 9 — growth feeds all).

Hermetic: tmp HOME, patched import-time DEFAULT_DATA_DIR (see
tests/test_entrypoints_finance.py::_herm), explicit LEVI_HOME/LEVI_GROWTH_DIR.
"""

from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path

import pytest

from levi.growth import cycle as growth_cycle
from levi.growth.distribute import distribute_learnings, infer_subsystems
from levi.growth.reflect import Learning
import levi.memory.store as _mem_store
from levi.memory.store import MemoryStore


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def env(tmp_path, monkeypatch):
    levi_home = tmp_path / ".levi"
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LEVI_HOME", str(levi_home))
    # Growth journal: keep the cycle journal and the distribution journal in
    # the same file (distribute resolves <home>/growth when home is given).
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(levi_home / "growth"))
    monkeypatch.setenv("LEVI_AGENT_SESSIONS_DIR", str(tmp_path / "sessions"))
    (tmp_path / "sessions").mkdir()
    # MemoryStore.DEFAULT_DATA_DIR is bound at import time from Path.home();
    # patching HOME alone does not move it.
    monkeypatch.setattr(
        _mem_store, "DEFAULT_DATA_DIR", levi_home / "memory"
    )
    return {"home": levi_home, "tmp": tmp_path}


def _learning(content, kind="fact", confidence=0.8):
    return Learning(
        kind=kind,
        content=content,
        confidence=confidence,
        provenance={"mode": "rules", "source": "test"},
    )


def _journal_lines(env):
    p = env["home"] / "growth" / "journal.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()]


# ---------------------------------------------------------------------------
# subsystem inference
# ---------------------------------------------------------------------------


def test_infer_subsystems_keyword_map():
    subs = infer_subsystems(
        "The user prefers their stock portfolio rebalanced when market signals fire."
    )
    assert "finance" in subs
    assert infer_subsystems("Remember to backup the vault keys nightly.") == [
        "backup",
        "vault",
    ]
    multi = infer_subsystems("Galaxy package install failed during agent tool delegation")
    assert "galaxy" in multi and "agent" in multi


def test_infer_subsystems_fallback_general():
    assert infer_subsystems("The sky is blue on Tuesdays apparently.") == ["general"]


# ---------------------------------------------------------------------------
# distribution writes
# ---------------------------------------------------------------------------


def test_distribute_writes_memory_with_subsystem_tags(env):
    learnings = [
        _learning("When the market dips 5%, the user wants their portfolio checked."),
        _learning("The agent should always confirm before delegating tool calls."),
    ]
    report = distribute_learnings(learnings, env["home"])
    assert report["distributed"] == 2
    assert report["skipped"] == 0
    assert report["subsystems"].get("finance", 0) >= 1
    assert report["subsystems"].get("agent", 0) >= 1

    store = MemoryStore(data_dir=env["home"] / "memory")
    entries = [e for e in store.list(limit=5000) if "distribution" in e.tags]
    assert len(entries) == 2
    by_sub = {}
    for e in entries:
        # binding rails: growth-tagged, source=growth, never anything else
        assert "growth" in e.tags
        assert e.source == "growth"
        assert e.metadata["shareable"] is False
        assert e.metadata["status"] == "provisional"
        for tag in e.tags:
            if tag not in ("growth", "levi-learned", "distribution"):
                by_sub.setdefault(tag, 0)
                by_sub[tag] += 1
    assert by_sub.get("finance", 0) >= 1
    assert by_sub.get("agent", 0) >= 1


def test_distribute_accepts_dict_learnings(env):
    d = _learning("The forge repo needs signed commits on main.").to_dict()
    report = distribute_learnings([d], env["home"])
    assert report["distributed"] == 1
    assert report["subsystems"].get("forge", 0) == 1


def test_distribute_journal_records(env):
    learning = _learning("Archive ingested 12 research reports about forgotten software.")
    report = distribute_learnings([learning], env["home"], cycle_id="cyc-test")
    lines = _journal_lines(env)
    dist = [r for r in lines if r.get("kind") == "distribution"]
    assert len(dist) == 1
    rec = dist[0]
    assert rec["cycle_id"] == "cyc-test"
    assert "archive" in rec["subsystems"]
    assert rec["memory_entry_id"] == report["entries"][0]
    assert rec["bus_published"] is True  # real bloodstream.bus now exists
    assert report["bus_published"] == 1


def test_distribute_bus_end_to_end(env):
    """The real bloodstream bus delivers levi.growth.learning events."""
    from levi.bloodstream import bus as blood_bus

    received = []
    token = blood_bus.subscribe("levi.growth.learning", lambda t, p: received.append((t, p)))
    try:
        report = distribute_learnings(
            [_learning("The daemon heartbeat interval should be 15 minutes.")],
            env["home"],
        )
    finally:
        blood_bus.unsubscribe(token)
    assert report["bus_published"] == 1
    assert len(received) == 1
    topic, payload = received[0]
    assert topic == "levi.growth.learning"
    assert "daemon" in payload["subsystems"]
    assert payload["learning_key"]


def test_distribute_bus_failure_is_silent(env, monkeypatch):
    """A bus whose publish raises must not break distribution."""
    import levi.bloodstream as _blood_pkg

    fake_bus = types.ModuleType("levi.bloodstream.bus")

    def publish(topic, payload):
        raise RuntimeError("bus exploded")

    fake_bus.publish = publish
    monkeypatch.setitem(sys.modules, "levi.bloodstream.bus", fake_bus)
    monkeypatch.setattr(_blood_pkg, "bus", fake_bus)

    report = distribute_learnings(
        [_learning("Galaxy trust pins must be verified before install.")], env["home"]
    )
    assert report["distributed"] == 1  # memory + journal still landed
    assert report["bus_published"] == 0
    lines = _journal_lines(env)
    dist = [r for r in lines if r.get("kind") == "distribution"]
    assert dist and dist[0]["bus_published"] is False


def test_distribute_idempotent(env):
    learnings = [_learning("The user prefers dark mode in every app, always.")]
    first = distribute_learnings(learnings, env["home"])
    second = distribute_learnings(learnings, env["home"])
    assert first["distributed"] == 1
    assert second["distributed"] == 0
    assert second["duplicates"] == 1
    store = MemoryStore(data_dir=env["home"] / "memory")
    dist = [e for e in store.list(limit=5000) if "distribution" in e.tags]
    assert len(dist) == 1


def test_distribute_rejects_non_list(env):
    with pytest.raises(ValueError):
        distribute_learnings("not-a-list", env["home"])


def test_distribute_skips_bad_items(env):
    report = distribute_learnings(
        [
            _learning("short"),  # too short
            {"kind": "nonsense", "content": "long enough but bad kind here"},  # bad kind
            42,  # not a learning
            _learning("The user asked to remember the backup schedule nightly."),
        ],
        env["home"],
    )
    assert report["distributed"] == 1
    assert report["skipped"] == 3


def test_distribute_dry_run_no_writes(env):
    report = distribute_learnings(
        [_learning("The user prefers concise answers without fluff.")],
        env["home"],
        dry_run=True,
    )
    assert report["distributed"] == 1  # counted, not written
    store = MemoryStore(data_dir=env["home"] / "memory")
    assert [e for e in store.list(limit=5000) if "distribution" in e.tags] == []
    assert _journal_lines(env) == []


def test_distribute_respects_rails_no_sentience(env):
    report = distribute_learnings(
        [_learning("When X happens, do Y — a functional workflow pattern.")], env["home"]
    )
    assert report["distributed"] == 1
    store = MemoryStore(data_dir=env["home"] / "memory")
    entries = [e for e in store.list(limit=5000) if "distribution" in e.tags]
    assert len(entries) == 1
    content = entries[0].content.lower()
    for claim in ("i feel", "i am conscious", "sentience", "subjective experience"):
        assert claim not in content
    # every write is growth-tagged, source=growth — never tools/policy/identity
    assert "growth" in entries[0].tags
    assert entries[0].source == "growth"


# ---------------------------------------------------------------------------
# cycle hook
# ---------------------------------------------------------------------------


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
            "content": "Please remember that my finance broker statements arrive monthly.",
        },
        {
            "kind": "message",
            "role": "assistant",
            "ts": "2026-09-15T10:00:05Z",
            "content": "Noted — monthly broker statements.",
        },
    ]


def test_cycle_calls_distribution(env, monkeypatch):
    _write_session(Path(os.environ["LEVI_AGENT_SESSIONS_DIR"]), "c1", _sample_records())
    calls = []

    def spy(learnings, home, **kwargs):
        calls.append({"learnings": learnings, "home": home, "kwargs": kwargs})
        return {
            "distributed": len(learnings),
            "skipped": 0,
            "duplicates": 0,
            "entries": [],
            "subsystems": {"finance": 1},
            "bus_published": 0,
            "journal_records": [],
        }

    monkeypatch.setattr(growth_cycle, "distribute_learnings", spy)
    report = growth_cycle.run_cycle(use_model=False)
    assert report["learnings_proposed"] > 0
    assert len(calls) == 1
    assert calls[0]["kwargs"]["cycle_id"] == report["cycle_id"]
    assert report["distribution"]["distributed"] == report["learnings_proposed"]

    # cycle journal entry carries the distribution summary
    lines = _journal_lines(env)
    cycles = [r for r in lines if r.get("kind") == "cycle"]
    assert cycles and cycles[0]["distributed"] == report["learnings_proposed"]


def test_cycle_distribution_disabled_by_env(env, monkeypatch):
    _write_session(Path(os.environ["LEVI_AGENT_SESSIONS_DIR"]), "c2", _sample_records())
    monkeypatch.setenv("LEVI_GROWTH_DISTRIBUTE", "0")

    def spy(*a, **k):  # pragma: no cover — must not be called
        raise AssertionError("distribute_learnings must not run when disabled")

    monkeypatch.setattr(growth_cycle, "distribute_learnings", spy)
    report = growth_cycle.run_cycle(use_model=False)
    assert report["distribution"]["distributed"] == 0


def test_cycle_distribution_failure_does_not_break_cycle(env, monkeypatch):
    _write_session(Path(os.environ["LEVI_AGENT_SESSIONS_DIR"]), "c3", _sample_records())

    def boom(*a, **k):
        raise RuntimeError("bus exploded")

    monkeypatch.setattr(growth_cycle, "distribute_learnings", boom)
    report = growth_cycle.run_cycle(use_model=False)  # must not raise
    assert "error" in report["distribution"]
    assert "bus exploded" in report["distribution"]["error"]
    # consolidation still landed
    assert report["consolidation"]["accepted"] > 0


def test_cycle_real_distribution_end_to_end(env):
    _write_session(Path(os.environ["LEVI_AGENT_SESSIONS_DIR"]), "c4", _sample_records())
    report = growth_cycle.run_cycle(use_model=False)
    assert report["distribution"]["distributed"] >= 1
    store = MemoryStore(data_dir=env["home"] / "memory")
    dist = [e for e in store.list(limit=5000) if "distribution" in e.tags]
    assert len(dist) == report["distribution"]["distributed"]
    # dashboard stays honest: learnings exclude routing slips
    status = growth_cycle.status(store)
    assert status["learnings_consolidated"] == report["consolidation"]["accepted"]
    assert status["learnings_distributed"] == report["distribution"]["distributed"]

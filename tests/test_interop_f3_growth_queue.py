"""Hermetic tests for F3: growth ``cycle.py`` consumes the pending-learnings
queue at the start of the harvest phase.

A cycle must journal valid bot-pending learnings, reject malformed lines
honestly, and never double-consume a queue (the adapter renames it to
``.consumed-<ts>`` first). Dry runs must not touch the queue. No network,
no user HOME writes.
"""

import json

import pytest

from levi.growth import cycle as growth_cycle
from levi.growth import journal as growth_journal
from levi.memory.store import MemoryStore


@pytest.fixture()
def env(tmp_path, monkeypatch):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    growth = tmp_path / "growth"
    monkeypatch.setenv("LEVI_AGENT_SESSIONS_DIR", str(sessions))
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(growth))
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "levihome"))
    monkeypatch.setenv("LEVI_WORKSPACE", str(tmp_path / "workspace"))
    monkeypatch.setenv("LEVI_MEMORY_DIR", str(tmp_path / "memlog"))
    monkeypatch.setenv("LEVI_BOT_DIR", str(tmp_path / "bot"))
    return tmp_path


def _write_queue(tmp_path, lines):
    bot_dir = tmp_path / "bot"
    bot_dir.mkdir(exist_ok=True)
    q = bot_dir / "pending_learnings.jsonl"
    q.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return q


def _journal_learning_texts():
    return [
        e.get("text")
        for e in growth_journal.read_entries(limit=1000)
        if e.get("kind") == "learning"
    ]


def test_f3_queue_consumed_at_harvest_start(env):
    q = _write_queue(
        env,
        [
            json.dumps({"text": "bot learning one", "source": "bot-test"}),
            json.dumps({"learning": "bot learning two"}),
            "not json at all",
        ],
    )
    store = MemoryStore(data_dir=env / "memory")
    report = growth_cycle.run_cycle(use_model=False, store=store)
    consumed = report["pending_learnings"]
    assert consumed["accepted"] == 2
    assert consumed["rejected"] == 1
    assert consumed["backup"] is not None
    # queue renamed away: exactly-once even across reruns
    assert not q.exists()
    leftovers = list(q.parent.glob("pending_learnings.jsonl.consumed-*"))
    assert len(leftovers) == 1
    # journaled as provisional growth learnings
    texts = _journal_learning_texts()
    assert "bot learning one" in texts
    assert "bot learning two" in texts


def test_f3_no_double_consume(env):
    q = _write_queue(env, [json.dumps({"text": "only once"})])
    store = MemoryStore(data_dir=env / "memory")
    growth_cycle.run_cycle(use_model=False, store=store)
    assert not q.exists()
    r2 = growth_cycle.run_cycle(use_model=False, store=store)
    assert r2["pending_learnings"]["accepted"] == 0
    assert r2["pending_learnings"]["backup"] is None
    assert _journal_learning_texts().count("only once") == 1


def test_f3_dry_run_does_not_touch_queue(env):
    q = _write_queue(env, [json.dumps({"text": "stays put"})])
    report = growth_cycle.run_cycle(use_model=False, dry_run=True)
    assert report["pending_learnings"]["skipped"] is True
    assert report["pending_learnings"]["accepted"] == 0
    assert q.exists()  # untouched
    assert "stays put" not in _journal_learning_texts()


def test_f3_missing_queue_is_idle_not_error(env):
    store = MemoryStore(data_dir=env / "memory")
    report = growth_cycle.run_cycle(use_model=False, store=store)
    consumed = report["pending_learnings"]
    assert consumed["accepted"] == 0
    assert consumed["rejected"] == 0
    assert consumed["backup"] is None

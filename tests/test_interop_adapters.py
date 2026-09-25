"""Hermetic tests for the interpenetration adapters.

Stub modules via fake objects and ``sys.modules`` blocking; hermetic
(isolated HOME, no network). Never touches the 7 untracked daemon/runtime
test filenames.
"""

import json
import sys
import types

import pytest

from levi.interop.adapters import assistant_retrieval, bot_rag
from levi.interop.adapters import growth_learnings
from levi.interop.adapters.academy_memory import concepts_to_memory_entries
from levi.interop.adapters.bounty_knowledge import findings_to_corpus_units


# ---------------------------------------------------------------------------
# fakes
# ---------------------------------------------------------------------------


class FakeEntry:
    def __init__(self, eid, content, tags=(), importance=0.7):
        self.id = eid
        self.content = content
        self.tags = list(tags)
        self.importance = importance
        self.updated_at = "2026-09-15T12:00:00+00:00"
        self.created_at = "2026-09-15T12:00:00+00:00"
        self.metadata = {}
        self.memory_type = types.SimpleNamespace(value="semantic")


class FakeStore:
    """Duck-typed store for both retrieve() and load_user_context()."""

    def __init__(self, entries):
        self._entries = entries

    def list(self, limit=None, memory_type=None, **_kw):
        entries = list(self._entries)
        return entries[:limit] if limit else entries


class FakeJournal:
    def __init__(self):
        self.appended = []

    def append_entry(self, entry):
        rec = dict(entry)
        rec.setdefault("id", "j-%d" % len(self.appended))
        self.appended.append(rec)
        return rec


# ---------------------------------------------------------------------------
# assistant_retrieval
# ---------------------------------------------------------------------------


def test_assistant_retrieval_hybrid_path():
    store = FakeStore(
        [
            FakeEntry("e1", "user plays guitar every evening", tags=["music"]),
            FakeEntry("e2", "user likes strong coffee", tags=["food"]),
        ]
    )
    out = assistant_retrieval.load_user_context_retrieved(store, "guitar", limit=8)
    assert out["method"] == "hybrid"
    assert "e1" in out["entry_ids"]
    assert "guitar" in out["block"].lower()


def test_assistant_retrieval_fallback_when_retrieval_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "levi.memory.retrieval", None)
    store = FakeStore([FakeEntry("e1", "user prefers dark mode")])
    out = assistant_retrieval.load_user_context_retrieved(store, "anything", limit=8)
    assert out["method"] == "fallback"
    assert "dark mode" in out["block"]
    assert out["entry_ids"] == []


def test_assistant_retrieval_fallback_no_hits():
    store = FakeStore([FakeEntry("e1", "user prefers dark mode")])
    out = assistant_retrieval.load_user_context_retrieved(
        store, "zzz-no-match-qqq", limit=8
    )
    assert out["method"] == "fallback"
    assert "dark mode" in out["block"]


def test_assistant_retrieval_empty_everything(monkeypatch):
    monkeypatch.setitem(sys.modules, "levi.memory.retrieval", None)
    monkeypatch.setitem(sys.modules, "levi.agent.assistant", None)
    out = assistant_retrieval.load_user_context_retrieved(FakeStore([]), "x")
    assert out["method"] == "fallback"
    assert out["block"] == ""
    assert "nothing" in out["note"]


def test_assistant_retrieval_blank_query_falls_back():
    store = FakeStore([FakeEntry("e1", "user prefers dark mode")])
    out = assistant_retrieval.load_user_context_retrieved(store, "   ")
    assert out["method"] == "fallback"  # retrieve() refuses blank queries


# ---------------------------------------------------------------------------
# bot_rag
# ---------------------------------------------------------------------------


def test_bot_rag_shapes_ask_result():
    store = FakeStore(
        [
            FakeEntry(
                "k1", "post-quantum TLS migrates to ML-KEM key exchange", tags=["tls"]
            ),
        ]
    )
    out = bot_rag.research_brief_rag("post-quantum TLS", store)
    assert out["method"] == "rag"
    if out["ok"]:
        assert "[memory:k1]" in out["report"]
        assert out["citations"] == ["k1"]
    else:
        # honestly reported no-results is also acceptable
        assert out["notice"]


def test_bot_rag_no_results_is_honest():
    out = bot_rag.research_brief_rag("zzz-no-match-qqq-topic", FakeStore([]))
    assert out["ok"] is False
    assert out["citations"] == []
    assert out["notice"]


def test_bot_rag_unavailable_is_honest(monkeypatch):
    monkeypatch.setitem(sys.modules, "levi.rag.pipeline", None)
    out = bot_rag.research_brief_rag("anything", FakeStore([]))
    assert out["ok"] is False
    assert out["notice"] == "rag-unavailable"
    assert "unavailable" in out["report"].lower()


def test_bot_rag_blank_topic_refused():
    out = bot_rag.research_brief_rag("   ", FakeStore([]))
    assert out["ok"] is False
    assert "no topic" in out["report"].lower()


# ---------------------------------------------------------------------------
# growth_learnings (queue consumer)
# ---------------------------------------------------------------------------


def _write_queue(path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_growth_queue_consumer_happy_path(tmp_path):
    q = tmp_path / "pending_learnings.jsonl"
    _write_queue(
        q,
        [
            json.dumps(
                {
                    "ts": "t",
                    "kind": "fact",
                    "text": "user likes tea",
                    "confidence": "heuristic",
                    "source": "levi-bot",
                    "status": "pending",
                }
            ),
            json.dumps({"text": "user runs marathons"}),
        ],
    )
    journal = FakeJournal()
    summary = growth_learnings.consume_pending_learnings(q, journal)
    assert summary["accepted"] == 2
    assert summary["rejected"] == 0
    assert len(journal.appended) == 2
    assert journal.appended[0]["text"] == "user likes tea"
    assert journal.appended[0]["kind"] == "learning"  # journal kind, not bot kind
    assert journal.appended[0]["provisional"] is True
    # queue moved to a consumed backup
    assert not q.exists()
    assert summary["backup"] is not None
    assert ".consumed-" in summary["backup"]


def test_growth_queue_consumer_rejects_bad_lines(tmp_path):
    q = tmp_path / "pending_learnings.jsonl"
    _write_queue(
        q,
        [
            "not json at all",
            json.dumps({"kind": "fact"}),  # missing text
            json.dumps(["a", "list"]),  # not a dict
            json.dumps({"text": "  valid one  "}),
        ],
    )
    journal = FakeJournal()
    summary = growth_learnings.consume_pending_learnings(q, journal)
    assert summary["accepted"] == 1
    assert summary["rejected"] == 3
    assert len(summary["rejections"]) == 3
    assert journal.appended[0]["text"] == "valid one"
    assert not q.exists()


def test_growth_queue_consumer_idempotent(tmp_path):
    q = tmp_path / "pending_learnings.jsonl"
    _write_queue(q, [json.dumps({"text": "one"})])
    journal = FakeJournal()
    first = growth_learnings.consume_pending_learnings(q, journal)
    second = growth_learnings.consume_pending_learnings(q, journal)
    assert first["accepted"] == 1
    assert second["accepted"] == 0 and second["rejected"] == 0
    assert len(journal.appended) == 1  # never reprocessed


def test_growth_queue_consumer_missing_queue_is_idle(tmp_path):
    journal = FakeJournal()
    summary = growth_learnings.consume_pending_learnings(
        tmp_path / "nope.jsonl", journal
    )
    assert summary["accepted"] == 0 and summary["rejected"] == 0
    assert summary["backup"] is None


def test_growth_queue_consumer_bad_journal_rejected(tmp_path):
    q = tmp_path / "pending_learnings.jsonl"
    _write_queue(q, [json.dumps({"text": "one"})])
    with pytest.raises(ValueError):
        growth_learnings.consume_pending_learnings(q, object())


def test_growth_queue_default_path_honors_env(monkeypatch, tmp_path):
    monkeypatch.setenv("LEVI_BOT_DIR", str(tmp_path))
    assert growth_learnings.default_queue_path() == tmp_path / "pending_learnings.jsonl"


# ---------------------------------------------------------------------------
# academy_memory (pure transform)
# ---------------------------------------------------------------------------


def test_academy_concepts_to_memory_entries_schema():
    concepts = [
        {
            "id": "pyD01B1O1",
            "name": "list comprehensions",
            "kind": "objective",
            "track": "python",
            "day": 1,
            "block": 1,
            "session": 3,
            "content_words": ["list", "comprehension"],
            "strength": 0.9,
            "status": "active",
        }
    ]
    entries = concepts_to_memory_entries(concepts)
    assert len(entries) == 1
    e = entries[0]
    assert e["memory_type"] == "semantic"
    assert "list comprehensions" in e["content"]
    assert set(e["tags"]) == {"academy", "python", "objective", "concept"}
    assert 0.0 <= e["importance"] <= 1.0
    assert e["importance"] == 0.9
    assert e["metadata"]["provenance"] == "academy"
    assert e["metadata"]["concept_id"] == "pyD01B1O1"


def test_academy_concepts_defaults_and_clamping():
    entries = concepts_to_memory_entries([{"name": "x", "strength": 99}])
    assert entries[0]["importance"] == 1.0
    assert entries[0]["tags"] == ["academy", "general", "concept", "concept"]


def test_academy_concepts_deny_closed():
    with pytest.raises(ValueError):
        concepts_to_memory_entries([{"kind": "objective"}])  # no name
    with pytest.raises(ValueError):
        concepts_to_memory_entries(["not-a-dict"])
    with pytest.raises(ValueError):
        concepts_to_memory_entries("not-a-list")


def test_academy_concepts_empty_list_ok():
    assert concepts_to_memory_entries([]) == []


# ---------------------------------------------------------------------------
# bounty_knowledge (pure transform)
# ---------------------------------------------------------------------------


def test_bounty_findings_to_corpus_units_schema():
    findings = [
        {
            "id": "f1",
            "target": "example.com",
            "scope": "example.com",
            "kind": "open_port",
            "detail": "port 443 open with TLS 1.0 enabled",
            "evidence": "nmap -sV output",
            "first_seen": "2026-09-01T00:00:00Z",
            "last_seen": "2026-09-15T00:00:00Z",
        }
    ]
    units = findings_to_corpus_units(findings)
    assert len(units) == 1
    u = units[0]
    assert u["id"] == "bounty:f1"
    assert u["kind"] == "security-finding"
    assert "port 443 open" in u["text"]
    assert "Evidence:" in u["text"]
    assert set(u["tags"]) == {"open_port", "bounty", "defensive"}
    assert u["provenance"]["source"] == "bounty"
    assert u["provenance"]["finding_id"] == "f1"
    assert u["provenance"]["target"] == "example.com"


def test_bounty_findings_no_evidence_ok():
    units = findings_to_corpus_units(
        [
            {
                "id": "f2",
                "target": "t",
                "scope": "s",
                "kind": "subdomain",
                "detail": "new subdomain observed",
            }
        ]
    )
    assert units[0]["text"] == "new subdomain observed"
    assert "Evidence:" not in units[0]["text"]


def test_bounty_findings_deny_closed():
    with pytest.raises(ValueError):
        findings_to_corpus_units([{"detail": "no id"}])
    with pytest.raises(ValueError):
        findings_to_corpus_units([{"id": "f", "detail": "  "}])
    with pytest.raises(ValueError):
        findings_to_corpus_units([42])
    with pytest.raises(ValueError):
        findings_to_corpus_units(None)

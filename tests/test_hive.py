"""The Hive: index/hive consistency, pickup, orchestration, synthesis, guards.

All tests run against a throwaway LEVI_GROWTH_DIR so the real
``~/.levi/growth`` (and the real hive index) is never touched.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if os.path.join(REPO, "core") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "core"))

from levi.founders import roster  # noqa: E402
from levi.growth import guards  # noqa: E402
from levi.hive import index as hive_index  # noqa: E402
from levi.hive import orchestrate  # noqa: E402
import sys as _sys

_hive_recall = _sys.modules["levi.hive.recall"]


def _recall(*args, **kwargs):
    return _hive_recall.recall(*args, **kwargs)


from levi.hive import synthesize  # noqa: E402


class FakeStore:
    def __init__(self):
        self.entries = []
        self._n = 0

    def add(
        self,
        memory_type,
        content,
        importance=0.5,
        source="user",
        tags=None,
        project_id=None,
        metadata=None,
    ):
        self._n += 1
        e = _FakeEntry(
            self._n,
            memory_type,
            content,
            importance,
            source,
            list(tags or []),
            dict(metadata or {}),
        )
        self.entries.append(e)
        return e

    def list(self, limit=5000):
        return self.entries[:limit]

    def update(self, entry_id, **fields):
        for e in self.entries:
            if e.id == entry_id:
                for k, v in fields.items():
                    setattr(e, k, v)
                return e
        raise KeyError(entry_id)


class _FakeEntry:
    def __init__(self, n, memory_type, content, importance, source, tags, metadata):
        self.id = "fake-%d" % n
        self.memory_type = memory_type
        self.content = content
        self.importance = importance
        self.source = source
        self.tags = tags
        self.metadata = metadata
        self.created_at = "2026-09-17T00:00:00Z"


@pytest.fixture()
def growth_dir(tmp_path, monkeypatch):
    d = tmp_path / "growth"
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(d))
    return d


def _register(seat, rid, content="a functional learning about trigger timing"):
    return hive_index.register_record(
        {
            "id": rid,
            "kind": "learned",
            "seat": seat,
            "content": content,
            "tags": ["fact"],
            "provenance": {"seat": seat},
        }
    )


# ---------------------------------------------------------------------------
# 1. index/hive consistency
# ---------------------------------------------------------------------------


def test_register_is_append_only_and_idempotent(growth_dir):
    out1 = _register("echo", "learn:1")
    out2 = _register("echo", "learn:1")  # same id: no-op
    assert out1["registered"] is True
    assert out2["registered"] is False
    recs = hive_index.read_index()
    assert len(recs) == 1 and recs[0]["id"] == "learn:1"


def test_index_entry_carries_provenance(growth_dir):
    _register("cybrus", "learn:2", "gate decisions must stay reviewable")
    rec = hive_index.query_index("learn:2")[0]
    assert rec["seat"] == "cybrus"
    assert rec["provenance"]["seat"] == "cybrus"
    assert "hive" in rec["tags"]


def test_consistency_ok_after_sync(growth_dir):
    from levi.growth.tracks import append_seat_entry

    append_seat_entry(
        "echo",
        {
            "id": "cyc-1",
            "kind": "raise",
            "experiences": 2,
            "learnings_proposed": 1,
            "accepted": 1,
            "mode": "rules",
        },
    )
    store = FakeStore()
    store.add(
        "semantic",
        "trigger timing learning, functional and plain",
        source="growth",
        tags=["growth", "fact", "seat:echo"],
        metadata={"provenance": {"seat": "echo"}},
    )
    hive_index.sync_from_journals()
    hive_index.sync_from_store(store)
    result = hive_index.verify_consistency(store)
    assert result["ok"], result["problems"]


def test_consistency_catches_missing_index_entry(growth_dir):
    from levi.growth.tracks import append_seat_entry

    append_seat_entry("echo", {"id": "cyc-9", "kind": "raise"})
    result = hive_index.verify_consistency(FakeStore())
    assert result["ok"] is False
    assert any("cyc-9" in p for p in result["problems"])


def test_reim_riem_register_through_public_data(growth_dir):
    from levi.identity.reim import REIM
    from levi.identity.riem import RIEM

    lessons = REIM().compost(
        {
            "identity": "test-seat",
            "success": False,
            "failures": ["gate misfired once"],
            "notes": "gate misfired once",
        }
    )
    assert isinstance(lessons, list)
    compressed = RIEM().compress(lessons, {})
    deltas = compressed.get("deltas", []) if isinstance(compressed, dict) else []
    r1 = hive_index.register_compost(lessons)
    r2 = hive_index.register_genome_deltas(deltas if isinstance(deltas, list) else [])
    assert r1["registered"] == r1["lessons"] > 0
    kinds = {r["kind"] for r in hive_index.read_index()}
    assert "composted" in kinds
    if deltas:
        assert "genome-delta" in kinds


# ---------------------------------------------------------------------------
# 2. pickup protocol: hit / miss / recovery records
# ---------------------------------------------------------------------------


def test_pickup_hit_supplies_with_recovery_records(growth_dir):
    _register("echo", "learn:7", "intent capture must stay faithful")
    result = _recall("cybrus", "learn:7", store=FakeStore())
    assert result["status"] == "supplied"
    assert result["entry"]["id"] == "learn:7"
    # seat-side recovery note: the mind knows it was supplied
    from levi.growth.tracks import read_seat_entries

    notes = [
        r for r in read_seat_entries("cybrus") if r.get("kind") == "recovered-via-hive"
    ]
    assert len(notes) == 1
    assert notes[0]["from_seat"] == "echo"
    # hive-side supply record: who failed, what was supplied, from whom
    supplied = hive_index.query_index(kind="supplied")
    assert len(supplied) == 1
    assert supplied[0]["provenance"]["to_seat"] == "cybrus"
    assert supplied[0]["provenance"]["from_seat"] == "echo"


def test_pickup_recalled_when_seat_holds_it(growth_dir):
    from levi.growth.tracks import append_seat_entry

    append_seat_entry("echo", {"id": "mine-1", "kind": "raise"})
    result = _recall("echo", "mine-1", store=FakeStore())
    assert result["status"] == "recalled"
    assert result["source"] == "journal"


def test_pickup_miss_is_honest(growth_dir):
    result = _recall("echo", "no-such-memory", store=FakeStore())
    assert result["status"] == "miss"
    assert result["entry"] is None
    misses = hive_index.query_index(kind="miss")
    assert len(misses) == 1
    assert (
        "Nothing was invented" in misses[0]["content"]
        or "never invented" in misses[0]["content"]
    )


def test_pickup_unknown_seat_raises(growth_dir):
    with pytest.raises(KeyError):
        _recall("not-a-seat", "whatever", store=FakeStore())


# ---------------------------------------------------------------------------
# 3. orchestration: fan-out, receipts, failure attribution
# ---------------------------------------------------------------------------


def test_broadcast_gathers_per_seat_receipts():
    def handler(seat, task):
        if seat == "echo":
            raise RuntimeError("boom")
        return "ok:%s" % seat

    report = orchestrate.broadcast(["echo", "mandella"], {"q": 1}, handler)
    assert report["mode"] == "rules:fan-out"
    assert report["seats"] == 2 and report["ok"] == 1 and report["failed"] == 1
    by_seat = {r["seat"]: r for r in report["receipts"]}
    assert by_seat["echo"]["ok"] is False
    assert "boom" in by_seat["echo"]["error"]  # failure attributed, never swallowed
    assert by_seat["mandella"]["result"] == "ok:mandella"


def test_seats_for_wave_and_category():
    a = orchestrate.seats_for(wave="A")
    assert len(a) == 122
    founders = orchestrate.seats_for(wave="founders")
    assert len(founders) == 19
    comms = orchestrate.seats_for(category="Communication")
    assert len(comms) == 39
    with pytest.raises(ValueError):
        orchestrate.seats_for(wave="Z")
    with pytest.raises(KeyError):  # deny-open, never guess
        orchestrate.seats_for(keys=["echo", "not-a-seat"])


def test_pulse_over_founders():
    report = orchestrate.pulse(wave="founders")
    assert report["seats"] == 19
    assert report["failed"] == 0
    for r in report["receipts"]:
        assert set(
            ("seat", "track", "stage", "learnings", "seasoned", "nature")
        ) <= set(r["result"])


# ---------------------------------------------------------------------------
# 4. synthesis: corroboration, conflict, no smoothing
# ---------------------------------------------------------------------------


def test_synthesis_counts_corroboration():
    seats = ["echo", "mandella", "reim"]
    contributions = {
        "echo": ["Trigger timing improved after the third run of the automation."],
        "mandella": ["Trigger timing improved after the third run of the automation."],
        "reim": ["Compost every failure into a lesson."],
    }
    out = synthesize.reasoning_round(seats, "trigger timing", contributions)
    assert out["mode"] == "rules"
    assert len(out["consensus"]) == 1
    assert out["consensus"][0]["supporters"] == ["echo", "mandella"]
    assert out["consensus"][0]["count"] == 2
    assert len(out["positions"]) == 1 and out["positions"][0]["seat"] == "reim"
    assert out["conflicts"] == []


def test_synthesis_surfaces_conflict_with_provenance():
    seats = ["echo", "mandella"]
    contributions = {
        "echo": ["Trigger timing has improved after the third automation run."],
        "mandella": ["Trigger timing has not improved after the third automation run."],
    }
    out = synthesize.reasoning_round(seats, "gate behavior", contributions)
    assert len(out["conflicts"]) == 1
    c = out["conflicts"][0]
    assert c["asserted_by"] == ["echo"] and c["negated_by"] == ["mandella"]
    assert out["consensus"] == []  # disagreement is shown, not smoothed


def test_synthesis_rejects_sentience_claims():
    with pytest.raises(ValueError):
        synthesize.reasoning_round(
            ["echo"], "x", {"echo": ["I feel conscious and alive"]}
        )


def test_synthesis_deny_open_and_shape():
    with pytest.raises(KeyError):
        synthesize.reasoning_round(["nope"], "x", {"nope": ["a"]})
    with pytest.raises(ValueError):
        synthesize.reasoning_round(["echo"], "x", {})


# ---------------------------------------------------------------------------
# 5. guards hold + MSSI reservation untouched
# ---------------------------------------------------------------------------


def test_hive_rejects_sentience_content(growth_dir):
    with pytest.raises(ValueError):
        hive_index.register_record(
            {
                "id": "bad:1",
                "kind": "learned",
                "seat": "echo",
                "content": "I am conscious and I feel things",
            }
        )
    assert hive_index.read_index() == []


def test_hive_rejects_unknown_seat_provenance(growth_dir):
    with pytest.raises(KeyError):
        hive_index.register_record(
            {
                "id": "bad:2",
                "kind": "learned",
                "seat": "not-a-seat",
                "content": "plain functional content",
            }
        )


def test_mssi_reservation_untouched():
    assert roster.current_nature("levi") == "mssi"
    with pytest.raises(ValueError):
        roster.switch_nature("echo", "mssi")
    # synthesis output never claims multi-substrate for anyone
    out = synthesize.reasoning_round(
        ["echo", "mandella"],
        "t",
        {"echo": ["a"], "mandella": ["b"]},
    )
    blob = json.dumps(out).lower()
    assert "mssi" not in blob and "multi-substrate" not in blob.replace(
        "no seat is made multi-substrate", ""
    )

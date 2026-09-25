"""Tests for explicit developmental stages (levi.growth.stages).

The stage ladder is a pure function of observable counters —
learnings, corroborations, days_active, curriculum_units, cycles —
never vibes. Tests cover: every rung of the ladder, boundary
thresholds, next-stage requirements with explicit numbers, input
validation, and gather_stats over synthetic memory/journal data.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from levi.growth.stages import STAGE_LADDER, gather_stats, stage_for
from levi.memory.store import MemoryStore
from levi.memory.types import MemoryEntry, MemoryType


# ---------------------------------------------------------------------------
# stage_for: the ladder
# ---------------------------------------------------------------------------


def test_stage_names_in_order():
    names = [name for name, _blurb, _crit in STAGE_LADDER]
    assert names == ["newborn", "sprouting", "curious", "growing", "maturing"]


def test_newborn_with_empty_stats():
    res = stage_for({})
    assert res["name"] == "newborn"
    assert res["criteria"] == {}
    assert res["next"]["name"] == "sprouting"


def test_sprouting_at_one_learning():
    res = stage_for({"learnings": 1})
    assert res["name"] == "sprouting"
    nxt = res["next"]
    assert nxt["name"] == "curious"
    assert nxt["requirements"]["learnings"] == {
        "current": 1.0,
        "threshold": 5,
        "met": False,
    }
    assert nxt["requirements"]["days_active"] == {
        "current": 0.0,
        "threshold": 1,
        "met": False,
    }


def test_curious_boundary():
    assert stage_for({"learnings": 4, "days_active": 30})["name"] == "sprouting"
    assert stage_for({"learnings": 5, "days_active": 1})["name"] == "curious"
    # days_active alone doesn't advance without learnings
    assert stage_for({"learnings": 0, "days_active": 100})["name"] == "newborn"


def test_growing_needs_all_criteria():
    base = {"learnings": 25, "corroborations": 10, "days_active": 7}
    assert stage_for(base)["name"] == "growing"
    assert stage_for({**base, "corroborations": 9})["name"] == "curious"
    assert stage_for({**base, "days_active": 6})["name"] == "curious"
    assert stage_for({**base, "learnings": 24})["name"] == "curious"


def test_maturing_and_top_stage_has_no_next():
    res = stage_for(
        {
            "learnings": 100,
            "corroborations": 50,
            "days_active": 30,
            "curriculum_units": 20,
        }
    )
    assert res["name"] == "maturing"
    assert res["next"] is None
    # curriculum_units gates the top stage
    res2 = stage_for(
        {
            "learnings": 500,
            "corroborations": 500,
            "days_active": 365,
            "curriculum_units": 19,
        }
    )
    assert res2["name"] == "growing"


def test_next_requirements_are_explicit_numbers():
    res = stage_for({"learnings": 12, "corroborations": 4, "days_active": 5})
    assert res["name"] == "curious"
    req = res["next"]["requirements"]
    assert req["learnings"]["current"] == 12.0
    assert req["learnings"]["threshold"] == 25
    assert req["learnings"]["met"] is False
    assert req["corroborations"]["current"] == 4.0
    assert req["days_active"]["current"] == 5.0


def test_stage_for_validates_input():
    with pytest.raises(ValueError):
        stage_for("not-a-mapping")
    with pytest.raises(ValueError):
        stage_for({"learnings": -1})
    with pytest.raises(ValueError):
        stage_for({"learnings": "many"})


# ---------------------------------------------------------------------------
# gather_stats: observable counters
# ---------------------------------------------------------------------------


def _entry(tags, corroborated=0, created_at=None):
    return MemoryEntry(
        id="e",
        memory_type=MemoryType.SEMANTIC,
        content="a durable learned statement about the world",
        tags=tags,
        metadata={"corroborated_count": corroborated},
        created_at=created_at or "2026-09-15T00:00:00Z",
    )


class _Store:
    def __init__(self, entries):
        self._entries = entries

    def list(self, limit=5000):
        return self._entries[:limit]


def test_gather_stats_counts():
    now = datetime(2026, 9, 16, tzinfo=timezone.utc)
    entries = [
        _entry(["growth", "levi-learned", "fact"], corroborated=3),
        _entry(["growth", "levi-learned", "procedural"], corroborated=7),
        _entry(["growth", "levi-learned", "preference"]),
        _entry(["growth", "levi-learned", "correction"]),
        _entry(["growth", "levi-learned", "fact"]),
        _entry(["growth", "curriculum", "fact"], corroborated=20),  # seed: not counted
        _entry(["growth", "distribution", "fact"]),  # slip: not counted
        _entry(["user", "fact"]),  # not growth
    ]
    journal = [
        {
            "kind": "cycle",
            "ts": (now - timedelta(days=9, hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        {"kind": "cycle", "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ")},
        {"kind": "distribution", "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ")},
    ]
    stats = gather_stats(_Store(entries), {"cycles": 9}, journal, now=now)
    assert stats["learnings"] == 5.0
    assert stats["curriculum_units"] == 1.0
    assert stats["corroborations"] == 10.0  # seed's 20 excluded
    assert stats["days_active"] == 9.0
    assert stats["cycles"] == 9.0
    assert stage_for(stats)["name"] == "curious"


def test_gather_stats_empty_world():
    stats = gather_stats(_Store([]), {}, [])
    assert stats == {
        "learnings": 0.0,
        "corroborations": 0.0,
        "days_active": 0.0,
        "curriculum_units": 0.0,
        "cycles": 0.0,
    }
    assert stage_for(stats)["name"] == "newborn"


def test_gather_stats_validates_input():
    with pytest.raises(ValueError):
        gather_stats(object(), {}, [])
    with pytest.raises(ValueError):
        gather_stats(_Store([]), "nope", [])
    with pytest.raises(ValueError):
        gather_stats(_Store([]), {}, "nope")


def test_gather_stats_against_real_store(tmp_path):
    # sanity: works against the real MemoryStore shape
    store = MemoryStore(data_dir=tmp_path / "memory")
    store.add(
        memory_type=MemoryType.SEMANTIC,
        content="The user prefers concise answers in every app.",
        source="growth",
        tags=["growth", "levi-learned", "preference"],
        metadata={"corroborated_count": 2},
    )
    stats = gather_stats(store, {"cycles": 1}, [])
    assert stats["learnings"] == 1.0
    assert stats["corroborations"] == 2.0

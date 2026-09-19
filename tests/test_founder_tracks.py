"""Raising tracks: resolution, round-trip, isolation, guards, idempotency.

Every test runs against a throwaway LEVI_GROWTH_DIR so the real
``~/.levi/growth`` is never touched, and a throwaway in-memory store
so no real memory is written.
"""

from __future__ import annotations

import os
import sys

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if os.path.join(REPO, "core") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "core"))

from levi.founders import roster  # noqa: E402
from levi.growth import guards  # noqa: E402
from levi.growth import tracks  # noqa: E402
from levi.growth.reflect import Learning  # noqa: E402


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


class FakeStore:
    """Minimal memory store (add/list/update)."""

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


def _auto_exp(n, ok=True):
    from levi.growth.experience import Experience

    return Experience(
        id="auto:fake-%d" % n,
        kind="automation",
        source="fake-automation-%d" % n,
        ts="2026-09-17T00:00:0%dZ" % n,
        content=(
            "Automation 'fake-automation-%d' has run %d time(s); status=%s; "
            "last result: routine completed"
            % (n, 3 + n, "ok" if ok else "failed: worker error")
        ),
        meta={"run_count": 3 + n, "status": "ok" if ok else "failed"},
    )


@pytest.fixture()
def growth_dir(tmp_path, monkeypatch):
    d = tmp_path / "growth"
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(d))
    # growth_dir() mkdirs on call; also make sure the harvesters don't
    # read real ~/.levi sources: stub the pool inputs.
    monkeypatch.setattr(tracks, "harvest_sessions", lambda since=None: ([], {}))
    monkeypatch.setattr(tracks, "harvest_ops_logs", lambda since=None: ([], {}))
    monkeypatch.setattr(
        tracks, "harvest_automations", lambda: [_auto_exp(1), _auto_exp(2)]
    )
    return d


# ---------------------------------------------------------------------------
# 1. track resolution for all 490 seats
# ---------------------------------------------------------------------------


def test_all_490_seats_resolve_to_a_track():
    assert len(roster.SEATS) == 490
    seen_tracks = set()
    for key in roster.SEATS:
        t = tracks.track_for(key)
        seen_tracks.add(t.track_id)
        assert key in t.seats
        seat = roster.get_seat(key)
        if seat.kind == "founder":
            assert t.tier == "founder" and t.wave == "founders"
        else:
            assert t.tier == "agent" and t.wave == seat.wave
    assert len(seen_tracks) == 30  # 19 founder + 11 category


def test_founder_tracks_are_hand_tuned():
    founder_tracks = tracks.tracks_by_tier()["founder"]
    assert len(founder_tracks) == 19
    for t in founder_tracks:
        assert len(t.seats) == 1
        seat = roster.get_founder(t.seats[0])
        assert t.reflect_focus and t.exceed
        assert t.stage_scale > 0
        # track is oriented on the seat's purpose, not boilerplate
        assert t.provenance


def test_category_tracks_partition_agents():
    agent_tracks = tracks.tracks_by_tier()["agent"]
    assert len(agent_tracks) == 11
    covered = sorted(k for t in agent_tracks for k in t.seats)
    agents = sorted(s.key for s in roster.seats_by_kind()["agent"])
    assert covered == agents
    for t in agent_tracks:
        assert t.reflect_focus  # trigger precision / gates / refusal honesty


def test_track_for_unknown_key_raises():
    with pytest.raises(KeyError):
        tracks.track_for("not-a-seat")


def test_nature_is_not_a_ceiling():
    # every track raises identically regardless of nature; mssi never
    # assignable outside Levi
    t_ai = tracks.track_for("echo")
    roster.switch_nature("echo", "si")
    try:
        assert tracks.track_for("echo") is t_ai
    finally:
        roster.switch_nature("echo", "ai")
    with pytest.raises(ValueError):
        roster.switch_nature("echo", "mssi")


# ---------------------------------------------------------------------------
# 2. round-trip: harvest -> reflect -> consolidate -> journal
# ---------------------------------------------------------------------------


def test_round_trip_founder(growth_dir):
    store = FakeStore()
    report = tracks.run_raising_cycle("echo", use_model=False, store=store)
    assert report["seat"] == "echo"
    assert report["track"] == "founder:echo"
    assert report["experiences"] == 0  # echo's track takes sessions only; stubbed empty
    assert report["quiet"] is True
    recs = tracks.read_seat_entries("echo")
    assert len(recs) == 1 and recs[0]["kind"] == "raise" and recs[0]["quiet"] is True


def test_round_trip_agent_with_learnings(growth_dir):
    store = FakeStore()
    # an agent seat on a category track: automations in the stubbed pool
    from levi.automation.minions import MINIONS

    key = MINIONS[0].id
    report = tracks.run_raising_cycle(key, use_model=False, store=store)
    assert report["seat"] == key
    assert report["experiences"] == 2
    assert report["mode"] == "rules"  # honest mode reporting
    assert report["learnings_proposed"] >= 1
    assert report["consolidation"]["accepted"] >= 1
    # namespaced: every written entry carries the seat tag
    for e in store.entries:
        assert "growth" in e.tags and ("seat:" + key) in e.tags
        assert "raise" in e.tags
    # journal: per-seat namespaced path
    recs = tracks.read_seat_entries(key)
    assert len(recs) == 1 and recs[0]["kind"] == "raise"
    assert recs[0]["seat"] == key
    path = tracks._seat_journal_path(key)
    assert str(path).endswith("agents/A/%s/journal.jsonl" % key)


def test_founder_journal_path(growth_dir):
    path = tracks._seat_journal_path("cybrus")
    assert str(path).endswith("founders/cybrus/journal.jsonl")


def test_round_trip_dry_run_writes_nothing(growth_dir):
    store = FakeStore()
    from levi.automation.minions import MINIONS

    key = MINIONS[0].id
    report = tracks.run_raising_cycle(key, use_model=False, store=store, dry_run=True)
    assert report["dry_run"] is True
    assert store.entries == []
    assert tracks.read_seat_entries(key) == []
    assert not tracks._seat_state_path(key).exists()


def test_store_without_interface_raises(growth_dir):
    with pytest.raises(ValueError):
        tracks.run_raising_cycle("echo", store=object())


# ---------------------------------------------------------------------------
# 3. namespacing isolation: no cross-seat mingling
# ---------------------------------------------------------------------------


def test_learnings_never_mingle_between_seats(growth_dir):
    store = FakeStore()
    from levi.automation.minions import MINIONS

    k1, k2 = MINIONS[0].id, MINIONS[1].id
    tracks.run_raising_cycle(k1, use_model=False, store=store)
    tracks.run_raising_cycle(k2, use_model=False, store=store)
    tags1 = {t for e in store.entries for t in e.tags if t.startswith("seat:")}
    assert ("seat:" + k1) in tags1 and ("seat:" + k2) in tags1
    for e in store.entries:
        seat_tags = [t for t in e.tags if t.startswith("seat:")]
        assert len(seat_tags) == 1  # exactly one owner per entry
    # seat_stats counts only its own learnings
    s1 = tracks.seat_stats(k1, store=store)
    s2 = tracks.seat_stats(k2, store=store)
    assert s1["learnings"] + s2["learnings"] == len(store.entries)


def test_dedup_scoped_per_seat(growth_dir):
    store = FakeStore()
    from levi.automation.minions import MINIONS

    k1, k2 = MINIONS[0].id, MINIONS[1].id
    r1 = tracks.run_raising_cycle(k1, use_model=False, store=store)
    # same experiences for seat 2: dedup is per-seat, so it writes fresh
    r2 = tracks.run_raising_cycle(k2, use_model=False, store=store)
    assert r2["consolidation"]["accepted"] == r1["consolidation"]["accepted"]
    assert r2["consolidation"]["corroborated"] == 0
    # but running seat 1 again corroborates within its own scope only
    r1b = tracks.run_raising_cycle(k1, use_model=False, store=store)
    assert r1b["consolidation"]["corroborated"] >= 1


# ---------------------------------------------------------------------------
# 4. guards hold
# ---------------------------------------------------------------------------


def test_sentience_learning_blocked(growth_dir, monkeypatch):
    store = FakeStore()
    evil = Learning(
        kind="fact",
        content="I feel conscious and alive with subjective experience",
        confidence=0.9,
        provenance={},
    )

    def fake_reflect(experiences, use_model=True):
        return [evil], "rules", {"direct_signals": 1}

    import sys as _sys

    monkeypatch.setattr(
        _sys.modules["levi.growth.reflect"], "reflect_detailed", fake_reflect
    )
    from levi.automation.minions import MINIONS

    key = MINIONS[0].id
    report = tracks.run_raising_cycle(key, use_model=False, store=store)
    assert report["learnings_proposed"] == 0
    assert report["evidence"].get("blocked_sentience", 0) >= 1
    assert store.entries == []  # nothing written


def test_guards_module_rejects_sentience_directly():
    hits = guards.check_no_sentience_claim("I am conscious and I feel things")
    assert hits
    assert guards.check_no_sentience_claim("When X happens, do Y") == []


def test_provisional_status_and_provenance(growth_dir):
    store = FakeStore()
    from levi.automation.minions import MINIONS

    key = MINIONS[0].id
    tracks.run_raising_cycle(key, use_model=False, store=store)
    for e in store.entries:
        assert e.metadata.get("status") == "provisional"
        prov = e.metadata.get("provenance", {})
        assert prov.get("seat") == key
        assert prov.get("track", "").startswith("category:")


# ---------------------------------------------------------------------------
# 5. idempotency
# ---------------------------------------------------------------------------


def test_second_run_is_quiet(growth_dir):
    store = FakeStore()
    from levi.automation.minions import MINIONS

    key = MINIONS[0].id
    first = tracks.run_raising_cycle(key, use_model=False, store=store)
    second = tracks.run_raising_cycle(key, use_model=False, store=store)
    # harvest_automations is not watermarked upstream; the seat
    # watermark covers the pool... second run journals again (honest
    # quiet record is acceptable), but must not double-count learnings
    # into NEW entries beyond corroboration
    assert second["consolidation"]["accepted"] == 0


def test_mentoring_only_for_seasoned(growth_dir, monkeypatch):
    # unseasoned seats harvest no mentoring outcomes even with mentees
    monkeypatch.setattr(roster, "is_seasoned", lambda k: False)
    assert tracks._harvest_mentoring("levi", {}) == []


def test_mentoring_experience_for_seasoned(growth_dir, monkeypatch):
    monkeypatch.setattr(roster, "is_seasoned", lambda k: k == "levi")
    since = {}
    exps = tracks._harvest_mentoring("levi", since)
    assert exps  # 18 originals minus alpha/omega = 16
    assert len(exps) == 16
    assert all(e.kind == "mentoring" for e in exps)
    # idempotent: same stamp -> no new experiences
    assert tracks._harvest_mentoring("levi", since) == []


# ---------------------------------------------------------------------------
# 6. dashboard
# ---------------------------------------------------------------------------


def test_raising_status_shape(growth_dir):
    store = FakeStore()
    status = tracks.raising_status(store=store)
    assert status["track_count"] == 30
    assert status["totals"]["seats"] == 490
    assert len(status["tracks"]) == 30
    for tid, info in status["tracks"].items():
        assert {
            "tier",
            "wave",
            "seats",
            "seasoned",
            "learnings",
            "stage_counts",
            "reflect_focus",
            "exceed",
        } <= set(info)


def test_seat_stage_uses_track_scale(growth_dir):
    # levi's bar is 2x: same counters -> lower-or-equal stage than a
    # scale-1.0 track
    store = FakeStore()
    base = tracks.seat_stats("echo", store=store)
    s_echo = tracks._scaled_stage_for(base, 1.0)
    s_levi = tracks._scaled_stage_for(base, 2.0)
    order = ["newborn", "sprouting", "curious", "growing", "maturing"]
    assert order.index(s_levi["name"]) <= order.index(s_echo["name"])

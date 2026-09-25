"""Tests for the metronome pacing daemon.

Pure scheduling: every test injects ``now`` and a LEVI_HOME under tmp_path.
"""

from __future__ import annotations

import pytest

from levi.daemon.metronome import (
    JobSpec,
    Metronome,
    _grid_index,
    _slot_time,
    default_jobs,
    phase_for,
    slot_offset,
    spread_report,
)


def _safe_now(name: str, interval: float) -> float:
    k = _grid_index(name, interval, 10_000_000.0)
    return _slot_time(name, interval, k) + interval / 2


@pytest.fixture()
def home(tmp_path, monkeypatch):
    h = tmp_path / "levi-home"
    h.mkdir()
    monkeypatch.setenv("LEVI_HOME", str(h))
    return h


def test_phase_deterministic_and_bounded():
    assert phase_for("levi-heartbeat") == phase_for("levi-heartbeat")
    assert 0.0 <= phase_for("anything") < 1.0
    assert slot_offset("x", 3600.0) == phase_for("x") * 3600.0


def test_fresh_job_is_due_immediately():
    m = Metronome([JobSpec("fresh", 3600.0)])
    assert m.due_in(m.jobs["fresh"], 1_000_000.0, {}) <= 0


def test_tick_claims_then_waits(home):
    m = Metronome([JobSpec("steady", 3600.0)])
    now = _safe_now("steady", 3600.0)
    claimed = m.tick(now)
    assert [t.job for t in claimed] == ["steady"]
    # Same instant: nothing more due.
    assert m.tick(now) == []
    # A minute later: still waiting for the slot.
    assert m.tick(now + 60.0) == []
    # Two intervals later the grid advanced -> due again.
    assert [t.job for t in m.tick(now + 7200.0)] == ["steady"]


def test_ticks_persist_across_instances(home):
    now = _safe_now("persist", 3600.0)
    Metronome([JobSpec("persist", 3600.0)]).tick(now)
    m2 = Metronome([JobSpec("persist", 3600.0)])
    assert m2.due(now + 10.0, m2.load_ticks()) == []


def test_disabled_job_never_due():
    m = Metronome([JobSpec("off", 60.0, enabled=False)])
    assert m.due(9_999_999.0, {}) == []


def test_same_interval_jobs_get_distinct_slots():
    jobs = [JobSpec(f"job-{i}", 300.0) for i in range(8)]
    report = spread_report(jobs)
    assert report["intervals"]["300.0"] > 0.0


def test_duplicate_registration_rejected():
    m = Metronome([])
    m.register(JobSpec("once", 60.0))
    with pytest.raises(ValueError):
        m.register(JobSpec("once", 60.0))


def test_bad_jobspec_rejected():
    with pytest.raises(ValueError):
        JobSpec("", 60.0)
    with pytest.raises(ValueError):
        JobSpec("x", 0.0)


def test_default_jobs_are_the_perpetual_trio():
    names = {j.name for j in default_jobs()}
    assert names == {"levi-heartbeat", "levi-growth", "levi-automation"}


def test_status_rows(home):
    rows = Metronome([JobSpec("s", 600.0)]).status(1_000_000.0)
    assert rows[0]["job"] == "s"
    assert rows[0]["state"] == "due"
    assert "slot_phase" in rows[0]

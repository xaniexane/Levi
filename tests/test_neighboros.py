"""Hermetic tests for the NeighborOS dispatch OS (product line 01).

No HOME writes unless a test explicitly monkeypatches the default path;
trackers are otherwise constructed with a tmp_path. No network, no
randomness: every assertion is deterministic, and "now" is injected
into the brief functions. All example data is synthetic.
"""

from datetime import datetime, timedelta, timezone

import pytest

from levi.neighboros import brief as brief_mod
from levi.neighboros.tracker import (
    OPEN_STATUSES,
    NeighborTracker,
    ServiceJob,
    Worker,
)


def _tracker(tmp_path):
    return NeighborTracker(
        jobs_path=tmp_path / "neighboros" / "jobs.json",
        workers_path=tmp_path / "neighboros" / "workers.json",
    )


NOW = datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc)


def _old(ts_days_ago: float) -> str:
    return (NOW - timedelta(days=ts_days_ago)).isoformat(timespec="seconds")


# -- jobs: records & validation ------------------------------------------


def test_add_job_defaults(tmp_path):
    t = _tracker(tmp_path)
    job = t.add_job("Fix leaky faucet", category="plumbing", customer="R. Diaz")
    assert job.id == 1
    assert job.status == "requested"
    assert job.priority == "normal"
    assert job.worker == ""
    assert job.due == ""
    assert (tmp_path / "neighboros" / "jobs.json").exists()


def test_add_job_rejects_empty_title(tmp_path):
    t = _tracker(tmp_path)
    with pytest.raises(ValueError, match="title"):
        t.add_job("   ")


def test_add_job_rejects_bad_priority(tmp_path):
    t = _tracker(tmp_path)
    with pytest.raises(ValueError, match="priority"):
        t.add_job("Mow lawn", priority="urgent-ish")


def test_add_job_rejects_bad_due(tmp_path):
    t = _tracker(tmp_path)
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        t.add_job("Mow lawn", due="not-a-date")


def test_add_job_accepts_due(tmp_path):
    t = _tracker(tmp_path)
    job = t.add_job("Mow lawn", due="2026-09-20")
    assert job.due == "2026-09-20"


# -- jobs: pipeline -------------------------------------------------------


def test_pipeline_happy_path(tmp_path):
    t = _tracker(tmp_path)
    job = t.add_job("Patch drywall")
    t.assign_job(job.id, "Sam K")
    assert t.get_job(job.id).status == "dispatched"
    assert t.get_job(job.id).worker == "Sam K"
    t.move_job(job.id, "in_progress")
    t.move_job(job.id, "completed")
    assert t.get_job(job.id).status == "completed"


def test_invalid_transition_rejected(tmp_path):
    t = _tracker(tmp_path)
    job = t.add_job("Patch drywall")
    with pytest.raises(ValueError, match="invalid transition"):
        t.move_job(job.id, "completed")  # requested → completed is not allowed


def test_terminal_states_are_terminal(tmp_path):
    t = _tracker(tmp_path)
    job = t.add_job("Patch drywall")
    t.assign_job(job.id, "Sam K")
    t.move_job(job.id, "in_progress")
    t.move_job(job.id, "completed")
    with pytest.raises(ValueError, match="invalid transition"):
        t.move_job(job.id, "requested")


def test_assign_requires_worker_name(tmp_path):
    t = _tracker(tmp_path)
    job = t.add_job("Patch drywall")
    with pytest.raises(ValueError, match="worker"):
        t.assign_job(job.id, "   ")


def test_assign_unknown_job(tmp_path):
    t = _tracker(tmp_path)
    with pytest.raises(KeyError):
        t.assign_job(999, "Sam K")


def test_upsert_is_idempotent(tmp_path):
    t = _tracker(tmp_path)
    job, created = t.upsert_job("Fix sink", customer="A. Rao", category="plumbing")
    assert created is True
    same, created2 = t.upsert_job(
        "Fix sink", customer="A. Rao", category="plumbing", note="called back"
    )
    assert created2 is False
    assert same.id == job.id
    assert len(t.list_jobs()) == 1
    assert any("called back" in n.text for n in same.notes)


def test_list_filters(tmp_path):
    t = _tracker(tmp_path)
    t.add_job("Job A", category="plumbing")
    b = t.add_job("Job B", category="electrical")
    t.assign_job(b.id, "Lee")
    assert len(t.list_jobs(status="requested")) == 1
    assert len(t.list_jobs(category="electrical")) == 1
    assert len(t.list_jobs(status="dispatched", category="electrical")) == 1


def test_note_job(tmp_path):
    t = _tracker(tmp_path)
    job = t.add_job("Fix sink")
    note = t.note_job(job.id, "customer prefers mornings")
    assert note.text == "customer prefers mornings"
    assert note.ts
    assert len(t.get_job(job.id).notes) == 1


def test_persistence_round_trip(tmp_path):
    t = _tracker(tmp_path)
    t.add_job("Fix sink", category="plumbing", priority="high")
    t.add_worker("Sam K", ["plumbing"])
    t2 = NeighborTracker(
        jobs_path=tmp_path / "neighboros" / "jobs.json",
        workers_path=tmp_path / "neighboros" / "workers.json",
    )
    jobs = t2.list_jobs()
    assert len(jobs) == 1
    assert jobs[0].title == "Fix sink"
    assert jobs[0].priority == "high"
    assert len(t2.list_workers()) == 1
    # next ids continue
    assert t2.add_job("Second job").id == 2


def test_corrupt_store_starts_empty(tmp_path):
    d = tmp_path / "neighboros"
    d.mkdir()
    (d / "jobs.json").write_text("{not json", encoding="utf-8")
    t = NeighborTracker(
        jobs_path=d / "jobs.json", workers_path=d / "workers.json"
    )
    assert t.list_jobs() == []


# -- workers --------------------------------------------------------------


def test_add_worker(tmp_path):
    t = _tracker(tmp_path)
    w = t.add_worker("Sam K", ["plumbing", "handyman"])
    assert w.id == 1
    assert w.status == "active"
    assert w.categories == ["plumbing", "handyman"]
    assert (tmp_path / "neighboros" / "workers.json").exists()


def test_add_worker_rejects_empty_name(tmp_path):
    t = _tracker(tmp_path)
    with pytest.raises(ValueError, match="name"):
        t.add_worker("  ", ["plumbing"])


def test_active_workers_for_category(tmp_path):
    t = _tracker(tmp_path)
    t.add_worker("Sam K", ["Plumbing"])
    t.add_worker("Lee M", ["electrical"])
    assert [w.name for w in t.active_workers_for("plumbing")] == ["Sam K"]
    assert t.active_workers_for("hvac") == []


def test_deactivate_worker_removes_coverage(tmp_path):
    t = _tracker(tmp_path)
    w = t.add_worker("Sam K", ["plumbing"])
    assert len(t.active_workers_for("plumbing")) == 1
    t.set_worker_status(w.id, "inactive")
    assert t.active_workers_for("plumbing") == []
    assert t.list_workers(status="inactive")[0].name == "Sam K"


def test_stats(tmp_path):
    t = _tracker(tmp_path)
    t.add_job("A")
    b = t.add_job("B")
    t.assign_job(b.id, "Sam K")
    t.add_worker("Sam K", ["handyman"])
    s = t.stats()
    assert s["jobs_total"] == 2
    assert s["jobs_open"] == 2
    assert s["jobs_by_status"]["requested"] == 1
    assert s["jobs_by_status"]["dispatched"] == 1
    assert s["workers_total"] == 1
    assert s["workers_active"] == 1


# -- brief: bottlenecks ----------------------------------------------------


def test_bottleneck_unassigned_and_aging(tmp_path):
    t = _tracker(tmp_path)
    fresh = t.add_job("Fresh request", category="cleaning")
    old = t.add_job("Old request", category="cleaning")
    t._jobs[old.id].created_at = _old(2.0)
    t._jobs[old.id].updated_at = _old(2.0)
    found = brief_mod.dispatch_bottlenecks(t, now=NOW)
    assert [b["job"].id for b in found] == [old.id, fresh.id]
    assert "aging" in found[0]["reason"]
    assert "aging" not in found[1]["reason"]


def test_bottleneck_stalled_dispatched(tmp_path):
    t = _tracker(tmp_path)
    job = t.add_job("Stalled job", category="plumbing")
    t.assign_job(job.id, "Sam K")
    t._jobs[job.id].updated_at = _old(3.0)
    found = brief_mod.dispatch_bottlenecks(t, now=NOW)
    assert len(found) == 1
    assert "stalled" in found[0]["reason"]
    assert "Sam K" in found[0]["reason"]


def test_no_bottlenecks_when_flowing(tmp_path):
    t = _tracker(tmp_path)
    job = t.add_job("Flowing job", category="plumbing")
    t.assign_job(job.id, "Sam K")
    assert brief_mod.dispatch_bottlenecks(t, now=NOW) == []


# -- brief: urgent ---------------------------------------------------------


def test_urgent_emergency_and_overdue(tmp_path):
    t = _tracker(tmp_path)
    t.add_job("Burst pipe", category="plumbing", priority="emergency")
    t.add_job("Late gutter job", category="handyman", due="2026-09-10")
    t.add_job("Routine mow", category="lawn care", due="2026-09-16")
    t.add_job("Far future", category="lawn care", due="2026-10-30")
    urgent = brief_mod.urgent_work(t, now=NOW)
    titles = [u["job"].title for u in urgent]
    assert titles == ["Burst pipe", "Late gutter job", "Routine mow"]
    assert "emergency" in urgent[0]["reason"]
    assert "overdue" in urgent[1]["reason"]
    assert "due 2026-09-16" in urgent[2]["reason"]


def test_urgent_ignores_completed(tmp_path):
    t = _tracker(tmp_path)
    job = t.add_job("Burst pipe", priority="emergency")
    t.assign_job(job.id, "Sam K")
    t.move_job(job.id, "in_progress")
    t.move_job(job.id, "completed")
    assert brief_mod.urgent_work(t, now=NOW) == []


# -- brief: supply gaps -----------------------------------------------------


def test_supply_gaps(tmp_path):
    t = _tracker(tmp_path)
    t.add_job("Fix sink", category="plumbing")
    t.add_job("Fix toilet", category="plumbing")
    t.add_job("Rewire outlet", category="electrical")
    t.add_worker("Lee M", ["electrical"])
    gaps = brief_mod.supply_gaps(t)
    assert len(gaps) == 1
    assert gaps[0]["category"] == "plumbing"
    assert gaps[0]["open_jobs"] == 2


def test_no_supply_gap_when_covered(tmp_path):
    t = _tracker(tmp_path)
    t.add_job("Fix sink", category="plumbing")
    t.add_worker("Sam K", ["plumbing"])
    assert brief_mod.supply_gaps(t) == []


# -- brief: highest-leverage action -----------------------------------------


def test_leverage_prefers_emergency(tmp_path):
    t = _tracker(tmp_path)
    t.add_job("Old unassigned", category="cleaning")
    t.add_job("Burst pipe", category="plumbing", priority="emergency")
    action = brief_mod.highest_leverage_action(t, now=NOW)
    assert "Burst pipe" in action


def test_leverage_then_unassigned(tmp_path):
    t = _tracker(tmp_path)
    t.add_job("Unassigned request", category="cleaning")
    action = brief_mod.highest_leverage_action(t, now=NOW)
    assert "Dispatch job" in action
    assert "Unassigned request" in action


def test_leverage_then_supply_gap(tmp_path):
    t = _tracker(tmp_path)
    job = t.add_job("Assigned job", category="plumbing")
    t.assign_job(job.id, "Sam K")  # no unassigned left, but no plumber rostered
    action = brief_mod.highest_leverage_action(t, now=NOW)
    assert "Recruit workers for 'plumbing'" in action


def test_leverage_empty_queue_is_recruiting_day(tmp_path):
    t = _tracker(tmp_path)
    action = brief_mod.highest_leverage_action(t, now=NOW)
    assert "recruiting day" in action


def test_leverage_flowing_queue(tmp_path):
    t = _tracker(tmp_path)
    job = t.add_job("Steady job", category="plumbing")
    t.assign_job(job.id, "Sam K")
    t.add_worker("Sam K", ["plumbing"])
    action = brief_mod.highest_leverage_action(t, now=NOW)
    assert "Queue is flowing" in action
    assert "Steady job" in action


# -- brief: render + persist --------------------------------------------------


def test_render_brief_sections(tmp_path):
    t = _tracker(tmp_path)
    t.add_job("Burst pipe", category="plumbing", priority="emergency")
    text = brief_mod.render_brief(t, brief_date="2026-09-16", now=NOW)
    assert text.startswith("# NeighborOS Daily Operations Brief — 2026-09-16")
    for section in (
        "## Pipeline snapshot",
        "## Dispatch bottlenecks",
        "## Urgent work",
        "## Supply gaps",
        "## Highest-leverage action",
    ):
        assert section in text
    assert "Burst pipe" in text


def test_render_brief_empty_queue(tmp_path):
    t = _tracker(tmp_path)
    text = brief_mod.render_brief(t, brief_date="2026-09-16", now=NOW)
    assert "Open jobs: 0 of 0 tracked" in text
    assert "recruiting day" in text


def test_write_brief_idempotent(tmp_path):
    t = _tracker(tmp_path)
    t.add_job("Fix sink", category="plumbing")
    briefs = tmp_path / "briefs"
    p1 = brief_mod.write_brief(t, brief_date="2026-09-16", now=NOW, briefs_dir=briefs)
    p2 = brief_mod.write_brief(t, brief_date="2026-09-16", now=NOW, briefs_dir=briefs)
    assert p1 == p2 == briefs / "brief-2026-09-16.md"
    assert p1.read_text(encoding="utf-8").count("Daily Operations Brief") == 1


def test_generate_brief_returns_text_and_path(tmp_path):
    t = _tracker(tmp_path)
    t.add_job("Fix sink", category="plumbing")
    briefs = tmp_path / "briefs"
    text, path = brief_mod.generate_brief(
        t, brief_date="2026-09-16", now=NOW, briefs_dir=briefs
    )
    assert "Fix sink" in text
    assert path.exists()


# -- cli smoke -----------------------------------------------------------------


def _ns(**kwargs):
    import argparse

    return argparse.Namespace(**kwargs)


def test_cli_brief_writes_file(tmp_path, monkeypatch, capsys):
    import levi.neighboros.cli as ncli

    monkeypatch.setattr(
        ncli,
        "NeighborTracker",
        lambda: NeighborTracker(
            jobs_path=tmp_path / "n" / "jobs.json",
            workers_path=tmp_path / "n" / "workers.json",
        ),
    )
    real_generate = brief_mod.generate_brief
    monkeypatch.setattr(
        ncli,
        "generate_brief",
        lambda tracker, brief_date=None, now=None, briefs_dir=None: real_generate(
            tracker,
            brief_date=brief_date,
            now=now,
            briefs_dir=tmp_path / "briefs",
        ),
    )
    # seed one job through the CLI itself
    rc = ncli.cmd_neighboros(
        _ns(
            neighboros_cmd="jobs",
            neighboros_jobs_cmd="add",
            title="CLI sink",
            category="plumbing",
            priority="normal",
            customer="",
            due="",
        )
    )
    assert rc == 0
    rc = ncli.cmd_neighboros(
        _ns(neighboros_cmd="brief", date="2026-09-16")
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "CLI sink" in out
    assert "brief written to" in out


def test_cli_jobs_add_validation(tmp_path, monkeypatch, capsys):
    import levi.neighboros.cli as ncli

    monkeypatch.setattr(
        ncli,
        "NeighborTracker",
        lambda: NeighborTracker(
            jobs_path=tmp_path / "n" / "jobs.json",
            workers_path=tmp_path / "n" / "workers.json",
        ),
    )
    rc = ncli.cmd_neighboros(
        _ns(
            neighboros_cmd="jobs",
            neighboros_jobs_cmd="add",
            title="   ",
            category="",
            priority="normal",
            customer="",
            due="",
        )
    )
    assert rc == 2
    assert "failed" in capsys.readouterr().out


def test_open_statuses_constant():
    assert set(OPEN_STATUSES) == {"requested", "dispatched", "in_progress"}
    assert isinstance(ServiceJob(id=1, title="x"), ServiceJob)
    assert isinstance(Worker(id=1, name="y"), Worker)

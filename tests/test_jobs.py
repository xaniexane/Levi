"""Hermetic tests for the LEVI jobs tracker (opportunity / deal pipeline).

No HOME writes unless a test explicitly monkeypatches the default path;
trackers are otherwise constructed with a tmp_path. No network, no
randomness: every assertion is deterministic. All example data is
synthetic.
"""

import argparse
import json
import os
import stat

import pytest

import levi.jobs.tracker as jobs_tracker
from levi.jobs.tracker import STATUSES, Job, JobTracker, import_demand


def _tracker(tmp_path):
    return JobTracker(path=tmp_path / "jobs" / "jobs.json")


# -- records & validation -------------------------------------------------


def test_add_defaults_to_new_manual(tmp_path):
    t = _tracker(tmp_path)
    job = t.add("Neighborhood compost pickup", company="Green Block Co")
    assert job.id == 1
    assert job.status == "new"
    assert job.source == "manual"
    assert job.title == "Neighborhood compost pickup"
    assert job.created_at and job.updated_at
    assert (tmp_path / "jobs" / "jobs.json").exists()


def test_add_rejects_empty_title(tmp_path):
    t = _tracker(tmp_path)
    with pytest.raises(ValueError, match="title"):
        t.add("   ", company="Acme")


def test_add_rejects_unknown_status(tmp_path):
    t = _tracker(tmp_path)
    with pytest.raises(ValueError, match="unknown status"):
        t.add("Role", status="dreaming")


def test_add_rejects_long_title(tmp_path):
    t = _tracker(tmp_path)
    with pytest.raises(ValueError, match="exceeds"):
        t.add("x" * 201)


def test_ids_increment(tmp_path):
    t = _tracker(tmp_path)
    a = t.add("Job A")
    b = t.add("Job B", source="demand-pipeline")
    assert (a.id, b.id) == (1, 2)
    assert b.source == "demand-pipeline"


def test_get_and_missing(tmp_path):
    t = _tracker(tmp_path)
    t.add("Job A")
    assert t.get(1).title == "Job A"
    with pytest.raises(KeyError):
        t.get(999)
    with pytest.raises(ValueError):
        t.get("abc")


# -- status pipeline & transitions ----------------------------------------


def test_statuses_cover_expected_pipeline():
    assert STATUSES == ("new", "active", "won", "lost", "dropped")


def test_happy_path_new_to_won(tmp_path):
    t = _tracker(tmp_path)
    t.add("Job A")
    assert t.move(1, "active").status == "active"
    assert t.move(1, "won").status == "won"


def test_active_to_lost_and_dropped(tmp_path):
    t = _tracker(tmp_path)
    t.add("Job A")
    t.move(1, "active")
    assert t.move(1, "lost").status == "lost"
    t.add("Job B")
    t.move(2, "dropped")
    assert t.get(2).status == "dropped"


def test_terminal_can_reopen(tmp_path):
    t = _tracker(tmp_path)
    t.add("Job A")
    t.move(1, "active")
    t.move(1, "won")
    assert t.move(1, "active").status == "active"
    t.move(1, "lost")
    assert t.move(1, "new").status == "new"


def test_same_status_move_is_noop(tmp_path):
    t = _tracker(tmp_path)
    t.add("Job A")
    assert t.move(1, "new").status == "new"


@pytest.mark.parametrize(
    "from_status,to_status",
    [
        ("new", "won"),
        ("new", "lost"),
        ("won", "lost"),
        ("won", "dropped"),
        ("lost", "won"),
        ("dropped", "won"),
        ("active", "bogus"),
    ],
)
def test_invalid_transitions_rejected(tmp_path, from_status, to_status):
    t = _tracker(tmp_path)
    t.add("Job A")
    # walk to from_status through valid moves
    walk = {
        "new": [],
        "active": ["active"],
        "won": ["active", "won"],
        "lost": ["active", "lost"],
        "dropped": ["dropped"],
    }[from_status]
    for step in walk:
        t.move(1, step)
    with pytest.raises(ValueError, match="invalid transition|unknown status"):
        t.move(1, to_status)


def test_move_rejects_unknown_status(tmp_path):
    t = _tracker(tmp_path)
    t.add("Job A")
    with pytest.raises(ValueError, match="unknown status"):
        t.move(1, "hired")


def test_move_missing_job(tmp_path):
    t = _tracker(tmp_path)
    with pytest.raises(KeyError):
        t.move(42, "active")


# -- update ---------------------------------------------------------------


def test_update_fields(tmp_path):
    t = _tracker(tmp_path)
    t.add("Job A")
    job = t.update(1, title="Job A+", company="Acme", source="referral")
    assert (job.title, job.company, job.source) == ("Job A+", "Acme", "referral")


def test_update_status_uses_transition_rules(tmp_path):
    t = _tracker(tmp_path)
    t.add("Job A")
    assert t.update(1, status="active").status == "active"
    assert t.update(1, status="lost").status == "lost"  # active -> lost valid
    with pytest.raises(ValueError, match="invalid transition"):
        t.update(1, status="won")  # lost -> won is invalid


def test_update_missing_job(tmp_path):
    t = _tracker(tmp_path)
    with pytest.raises(KeyError):
        t.update(99, title="x")


# -- idempotent upsert ----------------------------------------------------


def test_upsert_is_idempotent(tmp_path):
    t = _tracker(tmp_path)
    job_a, created_a = t.upsert(
        "Compost route",
        company="Green Block",
        source="demand-pipeline",
        note="worth=0.81 (HYPOTHESIS)",
    )
    assert created_a is True
    job_b, created_b = t.upsert(
        "Compost route",
        company="Green Block",
        source="demand-pipeline",
        note="worth=0.81 (HYPOTHESIS)",
    )
    assert created_b is False
    assert job_a.id == job_b.id
    assert t.stats()["total"] == 1
    # same note text is not duplicated
    assert len(t.get(job_a.id).notes) == 1


def test_upsert_case_insensitive_match(tmp_path):
    t = _tracker(tmp_path)
    a, _ = t.upsert("Compost Route", source="MANUAL")
    b, created = t.upsert("compost route", source="manual")
    assert created is False
    assert a.id == b.id


def test_upsert_appends_new_evidence(tmp_path):
    t = _tracker(tmp_path)
    job, _ = t.upsert("Compost route", note="first sighting")
    job2, created = t.upsert("Compost route", note="second sighting")
    assert created is False
    assert [n.text for n in t.get(job.id).notes] == [
        "first sighting",
        "second sighting",
    ]
    assert job2.updated_at >= job.updated_at


def test_upsert_different_source_is_different_job(tmp_path):
    t = _tracker(tmp_path)
    t.upsert("Compost route", source="manual")
    t.upsert("Compost route", source="demand-pipeline")
    assert t.stats()["total"] == 2


# -- notes ----------------------------------------------------------------


def test_note_appends_timestamped(tmp_path):
    t = _tracker(tmp_path)
    t.add("Job A")
    note = t.note(1, "Called the contact Thursday")
    assert note.text == "Called the contact Thursday"
    assert note.ts
    assert len(t.get(1).notes) == 1


def test_note_rejects_empty(tmp_path):
    t = _tracker(tmp_path)
    t.add("Job A")
    with pytest.raises(ValueError, match="note"):
        t.note(1, "   ")


# -- list / restrictions / stats ------------------------------------------


def test_list_filter_by_status(tmp_path):
    t = _tracker(tmp_path)
    t.add("Job A")
    t.add("Job B")
    t.move(2, "active")
    assert [j.id for j in t.list()] == [1, 2]
    assert [j.id for j in t.list(status="active")] == [2]
    assert t.list(status="won") == []
    with pytest.raises(ValueError, match="unknown status"):
        t.list(status="nope")


def test_restrictions_add_remove_list(tmp_path):
    t = _tracker(tmp_path)
    assert t.restrictions() == []
    t.add_restriction("local-first only")
    t.add_restriction("local-first only")  # idempotent
    t.add_restriction("no paid APIs")
    assert t.restrictions() == ["local-first only", "no paid APIs"]
    t.remove_restriction("local-first only")
    assert t.restrictions() == ["no paid APIs"]
    with pytest.raises(ValueError, match="restriction"):
        t.add_restriction("  ")


def test_stats(tmp_path):
    t = _tracker(tmp_path)
    t.add("Job A")
    t.add("Job B")
    t.move(1, "active")
    t.move(2, "active")
    t.move(2, "lost")
    t.add_restriction("local-first only")
    s = t.stats()
    assert s["total"] == 2
    assert s["active"] == 1  # new + active only
    assert s["by_status"]["active"] == 1
    assert s["by_status"]["lost"] == 1
    assert s["restrictions"] == 1


# -- persistence ----------------------------------------------------------


def test_persistence_round_trip(tmp_path):
    t = _tracker(tmp_path)
    t.add("Job A", company="Acme", source="demand-pipeline")
    t.note(1, "first note")
    t.move(1, "active")
    t.add_restriction("local-first only")

    t2 = _tracker(tmp_path)  # same path -> reloads
    job = t2.get(1)
    assert job.title == "Job A"
    assert job.company == "Acme"
    assert job.source == "demand-pipeline"
    assert job.status == "active"
    assert job.notes[0].text == "first note"
    assert t2.restrictions() == ["local-first only"]
    assert t2.add("Job B").id == 2  # next_id continues


def test_isolated_home_default_path(tmp_path, monkeypatch):
    home = tmp_path / "fakehome"
    monkeypatch.setattr(
        jobs_tracker, "default_path", lambda: home / ".levi" / "jobs" / "jobs.json"
    )
    t = JobTracker()  # no explicit path -> default resolution
    t.add("Job A")
    state_file = home / ".levi" / "jobs" / "jobs.json"
    assert state_file.exists()
    assert json.loads(state_file.read_text())["jobs"][0]["title"] == "Job A"


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions only")
def test_owner_only_permissions(tmp_path, monkeypatch):
    home = tmp_path / "fakehome"
    monkeypatch.setattr(
        jobs_tracker, "default_path", lambda: home / ".levi" / "jobs" / "jobs.json"
    )
    t = JobTracker()
    t.add("Job A")
    assert t.permissions_ok()
    d = stat.S_IMODE(os.stat(home / ".levi" / "jobs").st_mode)
    f = stat.S_IMODE(os.stat(home / ".levi" / "jobs" / "jobs.json").st_mode)
    assert (d, f) == (0o700, 0o600)


def test_corrupt_state_starts_empty(tmp_path):
    p = tmp_path / "jobs.json"
    p.write_text("{not valid json", encoding="utf-8")
    t = JobTracker(path=p)
    assert t.list() == []
    t.add("Job A")  # recovers by overwriting on next write
    assert json.loads(p.read_text(encoding="utf-8"))["jobs"][0]["title"] == "Job A"


def test_legacy_store_migrates(tmp_path, monkeypatch):
    """Old single-file store (~/.levi/jobs.json) with legacy stages migrates."""
    home = tmp_path / "fakehome"
    monkeypatch.setattr(
        jobs_tracker, "default_path", lambda: home / ".levi" / "jobs" / "jobs.json"
    )
    monkeypatch.setattr(jobs_tracker, "LEGACY_PATH", home / ".levi" / "jobs.json")
    legacy = {
        "next_id": 4,
        "jobs": [
            {
                "id": 1,
                "title": "Old A",
                "company": "Acme",
                "stage": "review_buffer",
                "source": "",
                "notes": [],
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "id": 2,
                "title": "Old B",
                "company": "Beta",
                "stage": "interview",
                "source": "board",
                "notes": [],
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "id": 3,
                "title": "Old C",
                "company": "Gamma",
                "stage": "offer",
                "source": "",
                "notes": [],
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            },
        ],
        "restrictions": ["remote only"],
    }
    (home / ".levi").mkdir(parents=True)
    (home / ".levi" / "jobs.json").write_text(json.dumps(legacy))
    t = JobTracker()
    assert t.get(1).status == "new"
    assert t.get(2).status == "active"
    assert t.get(3).status == "won"
    assert t.get(2).source == "board"
    assert t.restrictions() == ["remote only"]
    assert t.add("Job D").id == 4  # next_id preserved


def test_job_from_dict_skips_garbage_notes(tmp_path):
    t = _tracker(tmp_path)
    job = t.add("Job A")
    job.notes.append("not-a-note")  # type: ignore[arg-type]
    d = job.to_dict()
    restored = Job.from_dict(d)
    assert restored.notes == []


# -- skills -----------------------------------------------------------------


def test_job_skills_registered():
    from levi.skill.registry import SkillRegistry, SkillRisk

    reg = SkillRegistry()
    add = reg.get("jobs_add")
    assert add is not None
    assert add.category == "productivity"
    assert add.risk_level == SkillRisk.INFO
    move = reg.get("jobs_move")
    assert move is not None
    assert move.risk_level == SkillRisk.LOW
    assert "won/lost/dropped" in move.description


# -- demand import ------------------------------------------------------------


def _make_pulse(tmp_path):
    from levi.demand.pulse import DemandPulse

    dp = DemandPulse(path=tmp_path / "dp.json")
    s = dp.scan_seed("neighbors want compost pickup", segment="local")
    dp.score_opportunity(
        s.id,
        "Neighborhood compost pickup",
        demand_score=0.8,
        serviceability=0.7,
        startup_cost=0.2,
        notes="pilot block",
    )
    dp.score_opportunity(
        s.id,
        "Tiny errand service",
        demand_score=0.3,
        serviceability=0.4,
        startup_cost=0.5,
    )
    return dp


def test_import_demand_creates_jobs(tmp_path):
    t = _tracker(tmp_path)
    dp = _make_pulse(tmp_path)
    res = import_demand(t, _pulse_factory=lambda _p: dp)
    assert res["created"] == 2
    assert res["refreshed"] == 0
    jobs = t.list()
    assert {j.source for j in jobs} == {"demand-pipeline"}
    assert all(j.status == "new" for j in jobs)
    first = next(j for j in jobs if j.title == "Neighborhood compost pickup")
    assert "HYPOTHESIS" in first.notes[0].text
    assert "worth=" in first.notes[0].text


def test_import_demand_is_idempotent(tmp_path):
    t = _tracker(tmp_path)
    dp = _make_pulse(tmp_path)
    import_demand(t, _pulse_factory=lambda _p: dp)
    res = import_demand(t, _pulse_factory=lambda _p: dp)
    assert res["created"] == 0
    assert res["refreshed"] == 2
    assert t.stats()["total"] == 2


def test_import_demand_min_worth_filter(tmp_path):
    t = _tracker(tmp_path)
    dp = _make_pulse(tmp_path)
    res = import_demand(t, min_worth=0.7, _pulse_factory=lambda _p: dp)
    assert res["created"] == 1
    assert res["skipped"] == 1
    assert t.list()[0].title == "Neighborhood compost pickup"


def test_import_demand_dry_run_writes_nothing(tmp_path):
    t = _tracker(tmp_path)
    dp = _make_pulse(tmp_path)
    res = import_demand(t, dry_run=True, _pulse_factory=lambda _p: dp)
    assert res["dry_run"] is True
    assert len(res["imported"]) == 2
    assert t.stats()["total"] == 0


def test_import_demand_rejects_bad_thresholds(tmp_path):
    t = _tracker(tmp_path)
    with pytest.raises(ValueError, match="min_worth"):
        import_demand(t, min_worth=1.5)
    with pytest.raises(ValueError, match="min_score"):
        import_demand(t, min_score=101.0)


def test_import_demand_score_cards(tmp_path):
    t = _tracker(tmp_path)
    dp = _make_pulse(tmp_path)
    sig = dp.signals[0]
    dp.score_five_factor(
        sig.id,
        "Neighborhood compost pickup",
        factors={
            "demand": (80, "survey of 40 neighbors"),
            "market_size": (70, "2000-home service area"),
            "competition_gap": (85, "no local provider found"),
            "trend_velocity": (60, "steady HOA requests"),
            "entry_feasibility": (90, "bike trailer suffices"),
        },
        notes="pilot",
    )
    res = import_demand(t, _pulse_factory=lambda _p: dp)
    # same title as the opportunity -> evidence merged into one job
    assert t.stats()["total"] == 2
    job = next(j for j in t.list() if j.title == "Neighborhood compost pickup")
    assert any("five-factor" in n.text for n in job.notes)
    assert res["created"] == 2


# -- CLI ----------------------------------------------------------------------


def _ns(**kwargs):
    return argparse.Namespace(**kwargs)


def test_cli_end_to_end(tmp_path, monkeypatch, capsys):
    from levi.jobs import cli as jobs_cli

    monkeypatch.setattr(
        jobs_cli, "JobTracker", lambda: JobTracker(path=tmp_path / "j.json")
    )

    assert (
        jobs_cli.cmd_jobs(
            _ns(
                jobs_cmd="add",
                title="QA Engineer",
                company="Beta Inc",
                source="board",
                status="new",
            )
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "QA Engineer" in out and "Beta Inc" in out

    assert jobs_cli.cmd_jobs(_ns(jobs_cmd="move", id=1, status="active")) == 0
    assert "active" in capsys.readouterr().out

    assert jobs_cli.cmd_jobs(_ns(jobs_cmd="note", id=1, text="sent resume")) == 0

    assert (
        jobs_cli.cmd_jobs(
            _ns(
                jobs_cmd="update",
                id=1,
                title="QA Engineer II",
                company=None,
                source=None,
                status=None,
            )
        )
        == 0
    )
    assert "QA Engineer II" in capsys.readouterr().out

    assert jobs_cli.cmd_jobs(_ns(jobs_cmd="show", id=1)) == 0
    out = capsys.readouterr().out
    assert "sent resume" in out

    assert jobs_cli.cmd_jobs(_ns(jobs_cmd="list", status=None)) == 0
    assert "QA Engineer II" in capsys.readouterr().out

    assert jobs_cli.cmd_jobs(_ns(jobs_cmd="stats")) == 0
    assert "total: 1" in capsys.readouterr().out

    assert (
        jobs_cli.cmd_jobs(
            _ns(jobs_cmd="restrict", action="add", text="local-first only")
        )
        == 0
    )

    # invalid transition via CLI -> return code 2, no exception
    assert jobs_cli.cmd_jobs(_ns(jobs_cmd="move", id=1, status="won")) == 0
    assert jobs_cli.cmd_jobs(_ns(jobs_cmd="move", id=1, status="lost")) == 2

    # bad id -> return code 2, no exception
    assert jobs_cli.cmd_jobs(_ns(jobs_cmd="move", id=999, status="active")) == 2


def test_cli_import_demand(tmp_path, monkeypatch, capsys):
    from levi.jobs import cli as jobs_cli

    monkeypatch.setattr(
        jobs_cli, "JobTracker", lambda: JobTracker(path=tmp_path / "j.json")
    )
    dp = _make_pulse(tmp_path)
    monkeypatch.setattr(jobs_tracker, "DemandPulse", lambda *a, **k: dp)

    ns = _ns(
        jobs_cmd="import-demand", min_worth=0.0, min_score=0.0, limit=0, dry_run=False
    )
    assert jobs_cli.cmd_jobs(ns) == 0
    out = capsys.readouterr().out
    assert "created=2" in out
    assert "Neighborhood compost pickup" in out

    # second run refreshes instead of duplicating
    assert jobs_cli.cmd_jobs(ns) == 0
    out = capsys.readouterr().out
    assert "created=0" in out
    assert "refreshed=2" in out

    # dry run
    ns = _ns(
        jobs_cmd="import-demand", min_worth=0.0, min_score=0.0, limit=0, dry_run=True
    )
    assert jobs_cli.cmd_jobs(ns) == 0
    assert "would import" in capsys.readouterr().out

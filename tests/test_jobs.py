"""Hermetic tests for the Hybrid Search & Apply job tracker.

No HOME writes (JobTracker is constructed with a tmp_path), no network,
no randomness: every assertion is deterministic. All example data is
synthetic.
"""

import json

import pytest

from levi.jobs.tracker import STAGES, Job, JobTracker


def _tracker(tmp_path):
    return JobTracker(path=tmp_path / "jobs.json")


def test_add_starts_in_review_buffer(tmp_path):
    t = _tracker(tmp_path)
    job = t.add("Backend Engineer", "Acme Corp", source="referral")
    assert job.id == 1
    assert job.stage == "review_buffer"
    assert job.title == "Backend Engineer"
    assert job.company == "Acme Corp"
    assert (tmp_path / "jobs.json").exists()


def test_add_rejects_empty_title(tmp_path):
    t = _tracker(tmp_path)
    with pytest.raises(ValueError, match="title"):
        t.add("   ", "Acme Corp")


def test_add_rejects_unknown_stage(tmp_path):
    t = _tracker(tmp_path)
    with pytest.raises(ValueError, match="unknown stage"):
        t.add("Engineer", "Acme", stage="dreaming")


def test_ids_increment(tmp_path):
    t = _tracker(tmp_path)
    a = t.add("Role A", "Co A")
    b = t.add("Role B", "Co B")
    assert (a.id, b.id) == (1, 2)


def test_get_and_missing(tmp_path):
    t = _tracker(tmp_path)
    t.add("Role A", "Co A")
    assert t.get(1).title == "Role A"
    with pytest.raises(KeyError):
        t.get(999)
    with pytest.raises(ValueError):
        t.get("abc")


def test_move_through_pipeline(tmp_path):
    t = _tracker(tmp_path)
    t.add("Role A", "Co A")
    for stage in ("applied", "interview", "prep", "offer"):
        job = t.move(1, stage)
        assert job.stage == stage
    assert t.get(1).stage == "offer"


def test_move_rejects_unknown_stage(tmp_path):
    t = _tracker(tmp_path)
    t.add("Role A", "Co A")
    with pytest.raises(ValueError, match="unknown stage"):
        t.move(1, "hired")


def test_move_missing_job(tmp_path):
    t = _tracker(tmp_path)
    with pytest.raises(KeyError):
        t.move(42, "applied")


def test_note_appends_timestamped(tmp_path):
    t = _tracker(tmp_path)
    t.add("Role A", "Co A")
    note = t.note(1, "Recruiter call Thursday")
    assert note.text == "Recruiter call Thursday"
    assert note.ts
    assert len(t.get(1).notes) == 1


def test_note_rejects_empty(tmp_path):
    t = _tracker(tmp_path)
    t.add("Role A", "Co A")
    with pytest.raises(ValueError, match="note"):
        t.note(1, "   ")


def test_list_filter_by_stage(tmp_path):
    t = _tracker(tmp_path)
    t.add("Role A", "Co A")
    t.add("Role B", "Co B")
    t.move(2, "applied")
    assert [j.id for j in t.list()] == [1, 2]
    assert [j.id for j in t.list(stage="applied")] == [2]
    assert t.list(stage="offer") == []
    with pytest.raises(ValueError, match="unknown stage"):
        t.list(stage="nope")


def test_restrictions_add_remove_list(tmp_path):
    t = _tracker(tmp_path)
    assert t.restrictions() == []
    t.add_restriction("remote only")
    t.add_restriction("remote only")  # idempotent
    t.add_restriction("no relocation")
    assert t.restrictions() == ["remote only", "no relocation"]
    t.remove_restriction("remote only")
    assert t.restrictions() == ["no relocation"]
    with pytest.raises(ValueError, match="restriction"):
        t.add_restriction("  ")


def test_stats(tmp_path):
    t = _tracker(tmp_path)
    t.add("Role A", "Co A")
    t.add("Role B", "Co B")
    t.move(1, "applied")
    t.move(2, "rejected")
    t.add_restriction("remote only")
    s = t.stats()
    assert s["total"] == 2
    assert s["active"] == 1
    assert s["by_stage"]["review_buffer"] == 0
    assert s["by_stage"]["applied"] == 1
    assert s["by_stage"]["rejected"] == 1
    assert s["restrictions"] == 1


def test_persistence_round_trip(tmp_path):
    t = _tracker(tmp_path)
    t.add("Role A", "Co A", source="board")
    t.note(1, "first note")
    t.move(1, "interview")
    t.add_restriction("remote only")

    t2 = _tracker(tmp_path)  # same path -> reloads
    job = t2.get(1)
    assert job.title == "Role A"
    assert job.stage == "interview"
    assert job.notes[0].text == "first note"
    assert t2.restrictions() == ["remote only"]
    # next_id continues
    assert t2.add("Role B", "Co B").id == 2


def test_corrupt_state_starts_empty(tmp_path):
    p = tmp_path / "jobs.json"
    p.write_text("{not valid json", encoding="utf-8")
    t = JobTracker(path=p)
    assert t.list() == []
    # and recovers by overwriting on next write
    t.add("Role A", "Co A")
    assert json.loads(p.read_text(encoding="utf-8"))["jobs"][0]["title"] == "Role A"


def test_stages_cover_expected_pipeline():
    assert STAGES[:5] == (
        "review_buffer",
        "applied",
        "interview",
        "prep",
        "offer",
    )
    assert "rejected" in STAGES and "withdrawn" in STAGES


def test_job_from_dict_skips_garbage_notes(tmp_path):
    t = _tracker(tmp_path)
    job = t.add("Role A", "Co A")
    job.notes.append("not-a-note")  # type: ignore[arg-type]
    d = job.to_dict()
    restored = Job.from_dict(d)
    assert restored.notes == []


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


def test_cli_end_to_end(tmp_path, monkeypatch, capsys):
    import argparse

    from levi.jobs import cli as jobs_cli
    from levi.jobs.tracker import DEFAULT_PATH

    # Point the CLI's default state at tmp (isolated HOME)
    monkeypatch.setattr(
        jobs_cli, "JobTracker", lambda: JobTracker(path=tmp_path / "j.json")
    )
    assert DEFAULT_PATH  # default exists for real use; tests override it

    ns = argparse.Namespace(
        jobs_cmd="add",
        title="QA Engineer",
        company="Beta Inc",
        source="board",
        stage="review_buffer",
    )
    assert jobs_cli.cmd_jobs(ns) == 0
    out = capsys.readouterr().out
    assert "QA Engineer" in out and "Beta Inc" in out

    ns = argparse.Namespace(jobs_cmd="move", id=1, stage="applied")
    assert jobs_cli.cmd_jobs(ns) == 0
    assert "applied" in capsys.readouterr().out

    ns = argparse.Namespace(jobs_cmd="note", id=1, text="sent resume")
    assert jobs_cli.cmd_jobs(ns) == 0

    ns = argparse.Namespace(jobs_cmd="show", id=1)
    assert jobs_cli.cmd_jobs(ns) == 0
    out = capsys.readouterr().out
    assert "sent resume" in out

    ns = argparse.Namespace(jobs_cmd="list", stage=None)
    assert jobs_cli.cmd_jobs(ns) == 0
    assert "QA Engineer" in capsys.readouterr().out

    ns = argparse.Namespace(jobs_cmd="stats")
    assert jobs_cli.cmd_jobs(ns) == 0
    assert "total: 1" in capsys.readouterr().out

    ns = argparse.Namespace(jobs_cmd="restrict", action="add", text="remote only")
    assert jobs_cli.cmd_jobs(ns) == 0

    # bad id -> return code 2, no exception
    ns = argparse.Namespace(jobs_cmd="move", id=999, stage="applied")
    assert jobs_cli.cmd_jobs(ns) == 2

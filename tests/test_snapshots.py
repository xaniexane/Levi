"""Hermetic tests for ``levi.snapshots`` — capture/resume/list/drop.

Uses a tmp LEVI_HOME and a real throwaway git repo in tmp. No network,
no real ``~/.levi``.

Run:  python3 -m pytest tests/test_snapshots.py -q
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from levi.snapshots import (  # noqa: E402
    SnapshotStore,
    capture,
    drop,
    list_snapshots,
    resume,
    resume_brief,
)


@pytest.fixture()
def home(tmp_path, monkeypatch):
    h = tmp_path / "levi_home"
    h.mkdir()
    monkeypatch.setenv("LEVI_HOME", str(h))
    return h


@pytest.fixture()
def git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "a.txt").write_text("one")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    (repo / "a.txt").write_text("one-modified")  # unstaged change
    (repo / "new.txt").write_text("untracked")
    return repo


def _seed_home(home: Path) -> None:
    (home / "commitments").mkdir(exist_ok=True)
    (home / "commitments" / "commitments.json").write_text(
        json.dumps(
            [
                {
                    "name": "morning-run",
                    "target_per": "day",
                    "checkins": [{"date": "2026-09-14", "value": 1}],
                    "state": "active",
                }
            ]
        )
    )
    (home / "growth").mkdir(exist_ok=True)
    with (home / "growth" / "journal.jsonl").open("a") as fh:
        fh.write(json.dumps({"entry": "learned X"}) + "\n")
        fh.write(json.dumps({"entry": "decided Y"}) + "\n")


def test_capture_resume_round_trip(home, git_repo):
    _seed_home(home)
    snap = capture(
        "before-lunch",
        repo_dir=git_repo,
        focus="snapshots package",
        mode="build",
        notes=["mid wave, nothing else open"],
    )
    assert snap["name"] == "before-lunch"
    assert snap["focus"] == "snapshots package"
    assert snap["mode"] == "build"
    assert snap["commitments"] != "none"
    assert snap["commitments"][0]["name"] == "morning-run"
    assert snap["repo"]["branch"]  # real git repo summary
    assert snap["repo"]["changed"] == 1
    assert snap["repo"]["untracked"] == 1
    assert snap["journal_tail"] != "none"
    assert len(snap["journal_tail"]) == 2

    loaded = resume("before-lunch")
    assert loaded == snap

    brief = resume_brief(loaded)
    assert "before-lunch" in brief
    assert "morning-run" in brief
    assert "changed, 1 untracked" in brief
    assert "learned X" in brief


def test_empty_state_is_honest(home, git_repo, tmp_path):
    # No commitments, no journal, non-git dir -> all recorded as "none".
    plain = tmp_path / "plain"
    plain.mkdir()
    snap = SnapshotStore().capture("empty", repo_dir=plain)
    assert snap["commitments"] == "none"
    assert snap["journal_tail"] == "none"
    assert snap["repo"] == "none"
    brief = resume_brief(snap)
    assert "none recorded" in brief
    assert "no recent entries" in brief


def test_list_and_drop(home):
    assert list_snapshots() == []
    capture("one")
    capture("two")
    names = [r["name"] for r in list_snapshots()]
    assert names == ["one", "two"]
    assert drop("one") is True
    assert [r["name"] for r in list_snapshots()] == ["two"]
    assert drop("one") is False  # already gone
    with pytest.raises(KeyError):
        resume("one")


def test_module_level_functions_resolve_home_at_call_time(home, tmp_path, monkeypatch):
    capture("a")
    other = tmp_path / "other_home"
    other.mkdir()
    monkeypatch.setenv("LEVI_HOME", str(other))
    assert list_snapshots() == []  # fresh home: nothing there
    capture("b")
    assert [r["name"] for r in list_snapshots()] == ["b"]


def test_persisted_focus_picked_up(home):
    store = SnapshotStore()
    store.set_focus("teachback package")
    snap = store.capture("f1")
    assert snap["focus"] == "teachback package"

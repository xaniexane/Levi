"""Tests for the Park Sentry bot.

Proofs for the laws in ``levi/bot/parksentry.py``: park-don't-delete,
report-don't-resolve, dry-by-default, honest failure, and the
deny-closed gates (only staged deletions are parked; renames and
unstaged deletions are left as found).
"""

import json
import subprocess

import pytest

from levi.bot import parksentry
from levi.bot.parksentry import NotARepoError, ParkReport


def _git(repo, *args):
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )


@pytest.fixture()
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    _git(path, "init", "-q")
    _git(
        path, "-c", "user.email=t@t", "-c", "user.name=t", "config", "user.email", "t@t"
    )
    _git(path, "-c", "user.email=t@t", "-c", "user.name=t", "config", "user.name", "t")
    (path / "keep.txt").write_text("keep\n")
    (path / "doomed.txt").write_text("doomed\n")
    _git(path, "add", "-A")
    _git(
        path,
        "-c",
        "user.email=t@t",
        "-c",
        "user.name=t",
        "commit",
        "-qm",
        "seed",
    )
    return path


def _stage_deletion(repo):
    _git(repo, "rm", "-q", "doomed.txt")


def _staged_paths(repo):
    out = _git(repo, "status", "--porcelain=v1", "-z").stdout
    return out


def test_scan_reports_staged_deletions_and_changes_nothing(repo):
    _stage_deletion(repo)
    before = _staged_paths(repo)
    report = parksentry.scan(str(repo))
    assert isinstance(report, ParkReport)
    assert report.staged_deletions == ["doomed.txt"]
    assert report.clean is False
    assert _staged_paths(repo) == before


def test_scan_clean_repo(repo):
    report = parksentry.scan(str(repo))
    assert report.clean is True
    assert report.staged_deletions == []


def test_dry_run_park_leaves_index_intact(repo, tmp_path):
    _stage_deletion(repo)
    report = parksentry.park(str(repo), ledger_dir=str(tmp_path))
    assert report.applied is False
    assert report.parked == []
    # index untouched: still staged for deletion
    assert "D  doomed.txt" in _staged_paths(repo).replace("\0", "\n")


def test_apply_park_unstages_and_records_ledger(repo, tmp_path):
    _stage_deletion(repo)
    report = parksentry.park(str(repo), apply=True, ledger_dir=str(tmp_path))
    assert report.applied is True
    assert report.parked == ["doomed.txt"]
    # parked, not deleted: the deletion is now unstaged, worktree untouched
    status = _staged_paths(repo).replace("\0", "\n")
    assert "D  doomed.txt" not in status
    assert " D doomed.txt" in status
    ledger = tmp_path / "parked.jsonl"
    records = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert len(records) == 1
    assert records[0]["path"] == "doomed.txt"
    assert records[0]["action"] == "parked"


def test_rename_is_reported_but_not_parked(repo, tmp_path):
    _git(repo, "mv", "keep.txt", "kept.txt")
    report = parksentry.park(str(repo), apply=True, ledger_dir=str(tmp_path))
    assert report.staged_deletions == []
    assert report.parked == []
    # the rename survived the pass untouched
    plain = _git(repo, "status", "--porcelain=v1").stdout
    assert "R  keep.txt -> kept.txt" in plain


def test_unstaged_deletion_is_reported_but_not_parked(repo, tmp_path):
    (repo / "doomed.txt").unlink()
    report = parksentry.park(str(repo), apply=True, ledger_dir=str(tmp_path))
    assert report.staged_deletions == []
    assert report.parked == []
    assert report.unstaged_deletions == ["doomed.txt"]


def test_render_names_every_path(repo):
    _stage_deletion(repo)
    report = parksentry.scan(str(repo))
    text = parksentry.render(report)
    assert "doomed.txt" in text
    assert "Park Sentry" in text


def test_not_a_repo_is_refused(tmp_path):
    with pytest.raises(NotARepoError):
        parksentry.scan(str(tmp_path))
    with pytest.raises(NotARepoError):
        parksentry.park(str(tmp_path / "missing"), apply=True)


def test_cli_dry_run_returns_zero_and_reports(repo, capsys):
    _stage_deletion(repo)
    code = parksentry.cli(["--repo", str(repo)])
    assert code == 0
    out = capsys.readouterr().out
    assert "doomed.txt" in out
    assert "dry run" in out


def test_cli_bad_repo_returns_two(capsys, tmp_path):
    code = parksentry.cli(["--repo", str(tmp_path)])
    assert code == 2

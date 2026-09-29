"""Tests for the index-integrity watch daemon (law -> guard -> prove).

Hermetic: every test builds its own throwaway git fixture repo under
tmp_path. The real ~/workspace/levi index is never touched.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from levi.daemon.index_watch import (
    READ_ONLY_GIT,
    IndexWatch,
    IndexWatchConfig,
)

MODULE_PATH = (
    Path(__file__).resolve().parent.parent
    / "core"
    / "levi"
    / "daemon"
    / "index_watch.py"
)

FORBIDDEN_SUBCOMMANDS = {
    "add",
    "stash",
    "reset",
    "commit",
    "checkout",
    "rm",
    "mv",
    "clean",
}


def _git_fixture_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    (root / "a.txt").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=root, check=True)
    return root


def _make_watch(tmp_path: Path, repo: Path, procs=None) -> IndexWatch:
    cfg = IndexWatchConfig(
        repo=repo,
        log_path=tmp_path / "watch.log",
        inbox_dir=tmp_path / "inbox",
        state_dir=tmp_path / "state",
        poll_sec=0.01,
        process_lister=(lambda: list(procs) if procs is not None else []),
    )
    return IndexWatch(cfg)


def _alert_files(inbox: Path):
    return sorted(inbox.glob("INDEX-WATCH-ALERT-*.md"))


# -- law 5/1: change detection -------------------------------------------


def test_change_detection_fires_on_fixture_index_modification(tmp_path):
    repo = _git_fixture_repo(tmp_path / "repo")
    watch = _make_watch(tmp_path, repo)
    first = watch.tick()
    assert first["baselined"] is True
    assert first["alert_written"] is None
    # Modify the fixture index (test's own repo — allowed).
    (repo / "b.txt").write_text("two\n", encoding="utf-8")
    subprocess.run(["git", "add", "b.txt"], cwd=repo, check=True)
    second = watch.tick()
    assert second["changed"] is True
    assert second["alert_written"] is None  # no deletions staged
    log = (tmp_path / "watch.log").read_text(encoding="utf-8")
    assert "index changed" in log
    assert "b.txt" in log


# -- law 2: alert on staged deletions -------------------------------------


def test_alert_written_on_staged_deletion_fixture(tmp_path):
    repo = _git_fixture_repo(tmp_path / "repo")
    procs = ["12345 2026-09-25 git add sneaky.py"]
    watch = _make_watch(tmp_path, repo, procs=procs)
    watch.tick()  # baseline: clean index, no alert
    assert _alert_files(tmp_path / "inbox") == []
    # Stage a deletion in the fixture.
    subprocess.run(["git", "rm", "--cached", "-q", "a.txt"], cwd=repo, check=True)
    result = watch.tick()
    assert result["changed"] is True
    alerts = _alert_files(tmp_path / "inbox")
    assert len(alerts) == 1
    body = alerts[0].read_text(encoding="utf-8")
    assert "STAGED DELETIONS" in body
    assert "a.txt" in body
    assert "PARKED awaiting your ruling" in body
    assert "12345" in body  # process snapshot recorded
    assert "Index lock present" in body


def test_no_realert_on_unchanged_deletion_set(tmp_path):
    repo = _git_fixture_repo(tmp_path / "repo")
    watch = _make_watch(tmp_path, repo)
    watch.tick()
    subprocess.run(["git", "rm", "--cached", "-q", "a.txt"], cwd=repo, check=True)
    watch.tick()
    assert len(_alert_files(tmp_path / "inbox")) == 1
    # Tick again with no index change: no new alert.
    again = watch.tick()
    assert again["changed"] is False
    assert len(_alert_files(tmp_path / "inbox")) == 1
    # A NEW deletion set -> new alert.
    (repo / "c.txt").write_text("three\n", encoding="utf-8")
    subprocess.run(["git", "add", "c.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "c"], cwd=repo, check=True)
    subprocess.run(["git", "rm", "--cached", "-q", "c.txt"], cwd=repo, check=True)
    watch.tick()
    assert len(_alert_files(tmp_path / "inbox")) == 2


def test_baseline_does_not_alert_on_preexisting_deletions(tmp_path):
    repo = _git_fixture_repo(tmp_path / "repo")
    subprocess.run(["git", "rm", "--cached", "-q", "a.txt"], cwd=repo, check=True)
    watch = _make_watch(tmp_path, repo)
    result = watch.tick()
    assert result["baselined"] is True
    assert result["alert_written"] is None
    assert _alert_files(tmp_path / "inbox") == []
    assert "pre-existing staged deletions" in " ".join(result["notes"])


# -- law 4: never crash ----------------------------------------------------


def test_tick_never_crashes_on_missing_repo(tmp_path):
    watch = _make_watch(tmp_path, tmp_path / "no-such-repo")
    result = watch.tick()  # must not raise
    assert result["changed"] is False
    assert any("not readable" in n for n in result["notes"])


def test_git_refuses_non_readonly_subcommand(tmp_path):
    repo = _git_fixture_repo(tmp_path / "repo")
    watch = _make_watch(tmp_path, repo)
    with pytest.raises(ValueError, match="refusing non-read-only"):
        watch._git("add", ".")
    with pytest.raises(ValueError, match="refusing non-read-only"):
        watch._git("reset", "--hard")


# -- law 1+2: static proof of read-only ------------------------------------


def _code_lines(path: Path):
    """Module source with docstrings and comments stripped."""
    src = path.read_text(encoding="utf-8")
    # Strip triple-quoted docstrings.
    src = re.sub(r'"""[\s\S]*?"""', "", src)
    src = re.sub(r"'''[\s\S]*?'''", "", src)
    lines = []
    for line in src.splitlines():
        stripped = line.split("#", 1)[0]
        if stripped.strip():
            lines.append(stripped)
    return "\n".join(lines)


def test_static_scan_no_index_mutating_git_commands():
    code = _code_lines(MODULE_PATH)
    hits = re.findall(r"\bgit\s+(add|stash|reset|commit|checkout|rm|mv|clean)\b", code)
    assert hits == [], f"index-mutating git tokens found: {hits}"


def test_read_only_allowlist_has_no_forbidden_subcommands():
    assert not (set(READ_ONLY_GIT) & FORBIDDEN_SUBCOMMANDS)


def test_no_unstage_or_lock_touch_tokens():
    code = _code_lines(MODULE_PATH)
    # The daemon may OBSERVE lock_path via .exists(); it must never
    # write, remove, or move the lock file or the index.
    assert "lock_path.exists()" in code or ".exists()" in code
    assert not re.search(
        r"lock_path\s*\.\s*(unlink|write_text|write_bytes|rename|replace)", code
    )
    assert not re.search(
        r"index_path\s*\.\s*(unlink|write_text|write_bytes|rename|replace)", code
    )
    # os.replace is used only for the atomic state-file write: its
    # arguments must never reference the index or the lock.
    for m in re.finditer(r"os\.replace\(([^)]+)\)", code):
        args = m.group(1).lower()
        assert "index" not in args and "lock" not in args, (
            f"os.replace touches index/lock: {m.group(0)}"
        )


# -- wiring -----------------------------------------------------------------


def test_registered_in_perpetual_adapters():
    from levi.perpetual import supervise

    assert "levi-index-watch" in supervise.SERVICE_ADAPTERS


def test_registered_in_daemon_supervisor_catalog():
    from levi.daemon.supervisor import Supervisor

    names = [e["name"] for e in Supervisor().list_services()]
    assert "index-watch" in names


def test_health_check_reports_without_running(tmp_path):
    from levi.daemon.index_watch import _check_index_watch, _status_detail

    # The not-yet-run branch, via the pure status helper.
    ok, detail = _status_detail({})
    assert ok is True
    assert "not yet run" in detail
    # The live path ticks the (hermetic-state) check and reports alive.
    ok, detail = _check_index_watch(home=tmp_path)
    assert ok is True
    assert "alive" in detail

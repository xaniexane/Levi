"""Tests for the Roost daemon.

Proofs for the laws in ``levi/daemon/roost.py``: honest snapshots
(failed reads recorded, never zero-filled), atomic writes, the caged
prune (only under ``<home>/roost/tmp``), dry-by-default, and the
deny-closed gates on ``home`` and ``max_age_days``.
"""

import json
import os
import time

import pytest

from levi.daemon import roost


def test_tick_writes_atomic_snapshot(tmp_path):
    snapshot = roost.tick(home=str(tmp_path))
    snap_path = tmp_path / "roost" / "snapshot.json"
    assert snap_path.is_file()
    on_disk = json.loads(snap_path.read_text())
    assert on_disk["ts"] == snapshot["ts"]
    assert snapshot["tmp"]["band"] in ("ok", "warn", "crit")
    assert isinstance(snapshot["tmp"]["free_bytes"], int)
    assert isinstance(snapshot["levi_home"]["free_bytes"], int)
    assert snapshot["snapshot"] == str(snap_path)


def test_tick_twice_overwrites_honestly(tmp_path):
    first = roost.tick(home=str(tmp_path))
    second = roost.tick(home=str(tmp_path))
    assert first["ts"] <= second["ts"]
    on_disk = json.loads((tmp_path / "roost" / "snapshot.json").read_text())
    assert on_disk["ts"] == second["ts"]


def test_tick_counts_stale_scratch(tmp_path):
    scratch = tmp_path / "roost" / "tmp"
    scratch.mkdir(parents=True)
    stale = scratch / "old.log"
    stale.write_text("old")
    old = time.time() - 8 * 86400
    os.utime(stale, (old, old))
    snapshot = roost.tick(home=str(tmp_path))
    assert snapshot["stale_scratch_files"] == 1


def _make_stale_and_fresh(tmp_path):
    scratch = tmp_path / "roost" / "tmp"
    scratch.mkdir(parents=True)
    stale = scratch / "old.log"
    stale.write_text("old")
    old = time.time() - 10 * 86400
    os.utime(stale, (old, old))
    fresh = scratch / "new.log"
    fresh.write_text("new")
    return stale, fresh


def test_prune_dry_run_lists_without_deleting(tmp_path):
    stale, fresh = _make_stale_and_fresh(tmp_path)
    result = roost.prune(home=str(tmp_path), max_age_days=7)
    assert result["dry_run"] is True
    assert result["candidates"] == 1
    assert result["removed"] == [str(stale)]
    assert stale.exists() and fresh.exists()


def test_prune_apply_removes_only_stale(tmp_path):
    stale, fresh = _make_stale_and_fresh(tmp_path)
    result = roost.prune(home=str(tmp_path), max_age_days=7, dry_run=False)
    assert result["dry_run"] is False
    assert not stale.exists()
    assert fresh.exists()


def test_prune_refuses_negative_age(tmp_path):
    with pytest.raises(ValueError):
        roost.prune(home=str(tmp_path), max_age_days=-1)


def test_prune_refuses_non_numeric_age(tmp_path):
    with pytest.raises(ValueError):
        roost.prune(home=str(tmp_path), max_age_days="soon")


def test_tick_refuses_non_directory_home(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    with pytest.raises(ValueError):
        roost.tick(home=str(blocker))


def test_cmd_roost_tick(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    code = roost.cmd_roost(["tick"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert "tmp" in payload and "levi_home" in payload


def test_cmd_roost_prune_dry_run(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    stale, _fresh = _make_stale_and_fresh(tmp_path)
    code = roost.cmd_roost(["prune", "--days", "7"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert stale.exists()

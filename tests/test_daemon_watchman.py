"""Tests for levi.daemon.watchman — polling directory watcher."""

from __future__ import annotations

import json
import time
from pathlib import Path

from levi.daemon.watchman import WatchEvent, Watchman, WatchmanConfig


def _cfg(tmp_path, **kw):
    roots = kw.pop("roots", [])
    return WatchmanConfig(
        roots=roots,
        interval_sec=0.05,
        state_path=str(tmp_path / "state.json"),
        journal_path=str(tmp_path / "events.jsonl"),
        **kw,
    )


def test_first_tick_baselines_silently(tmp_path):
    root = tmp_path / "watched"
    root.mkdir()
    (root / "a.txt").write_text("hello")
    wm = Watchman(_cfg(tmp_path, roots=[str(root)]))
    assert wm.watch_once() == []
    # Journal file must not even exist (nothing journaled).
    assert not (tmp_path / "events.jsonl").exists()


def test_created_modified_deleted(tmp_path):
    root = tmp_path / "watched"
    root.mkdir()
    wm = Watchman(_cfg(tmp_path, roots=[str(root)]))
    wm.watch_once()  # baseline

    (root / "new.txt").write_text("x")
    events = wm.watch_once()
    kinds = {(e.kind, Path(e.path).name) for e in events}
    assert ("created", "new.txt") in kinds

    time.sleep(0.01)
    (root / "new.txt").write_text("changed!")
    events = wm.watch_once()
    assert any(e.kind == "modified" and e.path.endswith("new.txt") for e in events)

    (root / "new.txt").unlink()
    events = wm.watch_once()
    assert any(e.kind == "deleted" and e.path.endswith("new.txt") for e in events)


def test_ignore_patterns(tmp_path):
    root = tmp_path / "watched"
    (root / ".git").mkdir(parents=True)
    wm = Watchman(_cfg(tmp_path, roots=[str(root)]))
    wm.watch_once()
    (root / ".git" / "config").write_text("x")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "mod.pyc").write_text("x")
    assert wm.watch_once() == []


def test_journal_is_jsonl_and_state_persists(tmp_path):
    root = tmp_path / "watched"
    root.mkdir()
    cfg = _cfg(tmp_path, roots=[str(root)])
    wm = Watchman(cfg)
    wm.watch_once()
    (root / "f.txt").write_text("1")
    wm.watch_once()

    lines = (tmp_path / "events.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["kind"] == "created" and row["path"].endswith("f.txt")

    # A fresh watchman with the same state file sees no changes.
    wm2 = Watchman(cfg)
    assert wm2.watch_once() == []


def test_stop_file_and_event_stops_run(tmp_path):
    root = tmp_path / "watched"
    root.mkdir()
    stop = tmp_path / "stop"
    wm = Watchman(_cfg(tmp_path, roots=[str(root)], stop_file=str(stop)))
    stop.write_text("")
    assert wm.run() == 0

    wm2 = Watchman(_cfg(tmp_path, roots=[str(root)]))
    t = wm2.run_in_thread()
    time.sleep(0.15)
    wm2.stop()
    t.join(timeout=5)
    assert not t.is_alive()


def test_missing_root_is_not_an_error(tmp_path):
    wm = Watchman(_cfg(tmp_path, roots=[str(tmp_path / "nope")]))
    assert wm.watch_once() == []


def test_watch_event_serializes():
    ev = WatchEvent("modified", "/x/y", detail={"size": 3})
    d = ev.to_dict()
    assert d["kind"] == "modified" and d["detail"]["size"] == 3 and d["at"]

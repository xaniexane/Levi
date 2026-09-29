"""Tests for the DemandPulse Watch — levi.demandpulse.watch + cli.

Laws under test:
  W1 illegal statuses/waiters rejected at the boundary
  W2 history is append-only, one event per status change
  W3 snapshot equals replay of the history log (check_laws)
  W4 nothing deleted — completed items stay as record
  W5 waiting_on restricted to {him, me, none}
Plus: registry round-trip, alert-pipeline hook, seed idempotence, CLI.
"""

from __future__ import annotations

import argparse
import json

import pytest

from levi.demandpulse import watch as W
from levi.demandpulse.cli import cmd_demandpulse, register_demandpulse_parser


@pytest.fixture()
def reg(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMANDPULSE_WATCH_DIR", str(tmp_path / "watch"))
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    return W.WatchRegistry()


def _outbox(tmp_path):
    return tmp_path / "home" / ".levi" / "demand_alerts_outbox.jsonl"


# ---- W1: fixed statuses ----------------------------------------------------


def test_add_rejects_illegal_status(reg):
    with pytest.raises(W.InvalidStatusError):
        reg.add("X", "build", status="done-ish")


def test_set_rejects_illegal_status(reg):
    item = reg.add("X", "build")
    with pytest.raises(W.InvalidStatusError):
        reg.set_status(item["id"], "almost-done")
    assert reg.get(item["id"])["status"] == "queued"  # unchanged


def test_unknown_item_rejected(reg):
    with pytest.raises(W.UnknownItemError):
        reg.set_status("nope", "complete")
    with pytest.raises(W.UnknownItemError):
        reg.history_for("nope")


# ---- W5: honest waiters -----------------------------------------------------


def test_waiter_rejected(reg):
    item = reg.add("X", "build")
    with pytest.raises(W.InvalidWaiterError):
        reg.set_waiter(item["id"], "someone-else")
    with pytest.raises(W.InvalidWaiterError):
        reg.add("Y", "build", waiting_on="the-void")


def test_waiter_change_logged(reg):
    item = reg.add("X", "build", waiting_on="none")
    reg.set_waiter(item["id"], "him")
    assert reg.get(item["id"])["waiting_on"] == "him"
    kinds = [e["event"] for e in reg.history_for(item["id"])]
    assert kinds == ["created", "waiter"]


# ---- W2: append-only history -------------------------------------------------


def test_status_changes_append_history(reg):
    item = reg.add("X", "build")
    reg.set_status(item["id"], "in_progress", note="started")
    reg.set_status(item["id"], "blocked", note="waiting on him")
    evs = reg.history_for(item["id"])
    assert [e["event"] for e in evs] == ["created", "status", "status"]
    assert [e["seq"] for e in evs] == [1, 2, 3]
    assert evs[1]["from"] == "queued" and evs[1]["to"] == "in_progress"
    assert evs[2]["to"] == "blocked"
    assert reg.get(item["id"])["status"] == "blocked"


def test_same_status_is_not_a_change(reg):
    item = reg.add("X", "build")
    reg.set_status(item["id"], "queued")
    assert len(reg.history_for(item["id"])) == 1  # created only


# ---- W4: nothing deleted ------------------------------------------------------


def test_complete_keeps_record(reg):
    item = reg.add("X", "build")
    reg.set_status(item["id"], "complete")
    assert reg.get(item["id"])["status"] == "complete"
    assert any(i["id"] == item["id"] for i in reg.items())


# ---- W3: snapshot + log consistency --------------------------------------------


def test_check_laws_ok(reg):
    a = reg.add("A", "system", status="complete")
    b = reg.add("B", "thread", status="held", waiting_on="him")
    reg.set_status(b["id"], "blocked", note="stuck")
    report = reg.check_laws()
    assert report["ok"], report["problems"]
    assert len(report["laws"]) == 6


def test_check_laws_catches_tampered_snapshot(reg, tmp_path):
    reg.add("A", "system", status="complete")
    p = tmp_path / "watch" / "registry.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    (iid,) = data["items"]
    data["items"][iid]["status"] = "bogus"
    p.write_text(json.dumps(data), encoding="utf-8")
    # tampered snapshot is rejected at the load boundary (W1), before
    # any operation can run on it — check_laws never sees it
    with pytest.raises(W.WatchError, match="W1"):
        W.WatchRegistry(root=tmp_path / "watch")


def test_registry_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMANDPULSE_WATCH_DIR", str(tmp_path / "watch"))
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    r1 = W.WatchRegistry()
    item = r1.add("Round", "build", note="trip")
    r1.set_status(item["id"], "in_progress")
    r2 = W.WatchRegistry()
    assert r2.get(item["id"])["status"] == "in_progress"
    assert r2.get(item["id"])["note"] == "trip"
    assert len(r2.history_for(item["id"])) == 2


# ---- alert pipeline hook -------------------------------------------------------


def test_complete_queues_alert_line(reg, tmp_path):
    item = reg.add("Build X", "build")
    reg.set_status(item["id"], "complete", note="shipped")
    p = _outbox(tmp_path)
    assert p.exists()
    recs = [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines()]
    assert len(recs) == 1
    rec = recs[0]
    assert rec["dedup_key"].startswith(f"watch:{item['id']}:complete:")
    assert rec["kind"] == "watch:complete"
    assert "Build X" in rec["title"]
    assert len(rec["body"]) <= 160  # SMS-safe


def test_blocked_queues_alert_line(reg, tmp_path):
    item = reg.add("Build Y", "build")
    reg.set_status(item["id"], "blocked", note="needs him")
    recs = [json.loads(ln) for ln in
            _outbox(tmp_path).read_text(encoding="utf-8").splitlines()]
    assert recs[0]["kind"] == "watch:blocked"


def test_non_alert_status_queues_nothing(reg, tmp_path):
    item = reg.add("Build Z", "build")
    reg.set_status(item["id"], "in_progress")
    assert not _outbox(tmp_path).exists()


# ---- seed ----------------------------------------------------------------------


def test_seed_matches_standing_list(reg):
    W.seed(reg)
    assert len(reg.items()) == len(W.STANDING_SEED)
    assert reg.check_laws()["ok"]
    counts = reg.board()["counts"]
    assert counts["held"] >= 5  # threads waiting on him
    assert counts["blocked"] >= 3


def test_seed_idempotent(reg):
    W.seed(reg)
    n = len(reg.items())
    W.seed(reg)
    assert len(reg.items()) == n
    assert len(reg.history()) == n  # created events only, no dupes


# ---- board -----------------------------------------------------------------------


def test_board_groups_and_counts(reg):
    W.seed(reg)
    b = reg.board()
    assert b["total"] == len(W.STANDING_SEED)
    assert sum(b["counts"].values()) == b["total"]
    text = W.render_board(b)
    assert "DemandPulse Watch" in text
    for s in W.STATUSES:
        assert f"[{s}]" in text or b["counts"][s] == 0


# ---- CLI ---------------------------------------------------------------------------


def _parse(argv):
    p = argparse.ArgumentParser(prog="levi")
    sub = p.add_subparsers(dest="command")
    register_demandpulse_parser(sub)
    return p.parse_args(argv)


def test_cli_watch_board(reg, capsys):
    W.seed(reg)
    rc = cmd_demandpulse(_parse(["demandpulse", "watch", "board"]))
    assert rc == 0
    out = capsys.readouterr().out
    assert "DemandPulse Watch" in out
    assert "complete=" in out


def test_cli_watch_add_set_history(reg, capsys):
    rc = cmd_demandpulse(_parse(
        ["demandpulse", "watch", "add", "New thing", "--area", "build"]))
    assert rc == 0
    out = capsys.readouterr().out
    item_id = out.split()[1].rstrip(":")
    rc = cmd_demandpulse(_parse(
        ["demandpulse", "watch", "set", item_id, "in_progress",
         "--note", "going"]))
    assert rc == 0
    assert "in_progress" in capsys.readouterr().out
    rc = cmd_demandpulse(_parse(["demandpulse", "watch", "history", item_id]))
    assert rc == 0
    hist = capsys.readouterr().out
    assert "created" in hist and "status" in hist


def test_cli_watch_set_bad_status(reg, capsys):
    item = reg.add("X", "build")
    rc = cmd_demandpulse(_parse(["demandpulse", "watch", "set",
                                 item["id"], "done-ish"]))
    assert rc == 2
    assert "failed" in capsys.readouterr().out


def test_cli_watch_defaults_to_board(reg, capsys):
    W.seed(reg)
    rc = cmd_demandpulse(_parse(["demandpulse", "watch"]))
    assert rc == 0
    assert "DemandPulse Watch" in capsys.readouterr().out

# ------------------------------------------------- wave 5: watch hardening
def test_add_rejects_non_string_fields(reg):
    with pytest.raises(ValueError, match="name"):
        reg.add(123, "area")
    with pytest.raises(ValueError, match="area"):
        reg.add("name", None)
    with pytest.raises(ValueError, match="note"):
        reg.add("name", "area", note=42)
    with pytest.raises(ValueError, match="non-empty"):
        reg.add("   ", "area")


def test_set_status_rejects_non_string_note(reg):
    item = reg.add("n", "a")
    with pytest.raises(ValueError, match="note"):
        reg.set_status(item["id"], "in_progress", note=42)


def test_created_event_carries_waiting_on(reg):
    item = reg.add("n", "a", waiting_on="him")
    created = [e for e in reg.history() if e["event"] == "created"][0]
    assert created["waiting_on"] == "him"
    assert reg.check_laws()["ok"] is True
    assert item["waiting_on"] == "him"


def test_check_laws_catches_waiter_mismatch(tmp_path):
    root = tmp_path / "w"
    reg = W.WatchRegistry(root=root)
    item = reg.add("n", "a", waiting_on="him")
    # hand-edit the snapshot out from under the log
    p = root / "registry.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    data["items"][item["id"]]["waiting_on"] = "me"
    p.write_text(json.dumps(data), encoding="utf-8")
    reg2 = W.WatchRegistry(root=root)
    verdict = reg2.check_laws()
    assert verdict["ok"] is False
    assert any("waiter mismatch" in pr for pr in verdict["problems"])


def test_corrupt_registry_raises_named_error(tmp_path):
    root = tmp_path / "w"
    root.mkdir()
    (root / "registry.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(W.WatchError, match="registry corrupt"):
        W.WatchRegistry(root=root)


def test_illegal_status_in_snapshot_rejected_at_load(tmp_path):
    root = tmp_path / "w"
    root.mkdir()
    (root / "registry.json").write_text(
        json.dumps({"items": {"x": {"id": "x", "name": "x", "area": "a",
                                   "status": "bogus", "waiting_on": "none"}}}),
        encoding="utf-8",
    )
    with pytest.raises(W.WatchError, match="W1"):
        W.WatchRegistry(root=root)


def test_corrupt_history_line_raises_named_error(tmp_path):
    root = tmp_path / "w"
    reg = W.WatchRegistry(root=root)
    reg.add("n", "a")
    with (root / "history.jsonl").open("a", encoding="utf-8") as fh:
        fh.write("{broken\n")
    with pytest.raises(W.WatchError, match="history corrupt"):
        reg.history()


def test_render_board_tolerates_partial_dict():
    text = W.render_board({"counts": {"complete": 1}, "total": 1, "groups": {}})
    assert "DemandPulse Watch" in text
    assert W.render_board({})  # empty dict renders, never raises


def test_watch_dir_blank_env_falls_back(monkeypatch):
    from pathlib import Path

    monkeypatch.setenv("DEMANDPULSE_WATCH_DIR", "   ")
    assert W.watch_dir() == Path.home() / "workspace" / "demandpulse-watch"

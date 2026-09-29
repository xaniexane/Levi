"""Hermetic tests for levi.tasklist: tmp HOME, owner-only perms, law guards."""

import json
import os
from datetime import date, timedelta
from pathlib import Path

import pytest

from levi.tasklist import PRIORITIES, TaskError, TaskLists


@pytest.fixture()
def tl(monkeypatch, tmp_path):
    monkeypatch.setenv("LEVI_TASKLIST_DIR", str(tmp_path / "tasklist"))
    return TaskLists()


def _mode(p: Path) -> int:
    return os.stat(p).st_mode & 0o777


def test_create_and_list_names(tl):
    tl.create_list("Errands")
    assert tl.lists() == ["Errands"]
    with pytest.raises(TaskError):  # L4: duplicate refused
        tl.create_list("Errands")


def test_store_is_owner_only(tl):
    assert _mode(tl.home) == 0o700
    assert _mode(tl.lists_dir) == 0o700
    tl.create_list("X")
    assert _mode(tl._path("X")) == 0o600


def test_add_task_fields(tl):
    tl.create_list("Work")
    t = tl.add_task("Work", "Ship report", priority="high", due="2026-09-30",
                    notes="numbers", tags=["q3"])
    assert t["priority"] == "high" and t["due"] == "2026-09-30"
    assert t["status"] == "open" and t["steps"] == []
    got = tl.get_task("Work", t["id"])
    assert got["title"] == "Ship report" and got["tags"] == ["q3"]


def test_add_task_refusals(tl):
    tl.create_list("Work")
    with pytest.raises(TaskError):
        tl.add_task("Work", "   ")  # empty title
    with pytest.raises(TaskError):
        tl.add_task("Work", "x", priority="someday")  # bad priority
    with pytest.raises(TaskError):
        tl.add_task("Work", "x", due="not-a-date")  # bad date
    with pytest.raises(TaskError):
        tl.add_task("Nope", "x")  # unknown list


def test_explicit_task_id_collision_refused(tl):  # L4
    tl.create_list("Work")
    tl.add_task("Work", "one", id="t-fixed")
    with pytest.raises(TaskError):
        tl.add_task("Work", "two", id="t-fixed")


def test_complete_and_reopen_keep_receipts(tl):  # L1
    tl.create_list("Work")
    t = tl.add_task("Work", "Call Erica")
    tl.complete_task("Work", t["id"])
    assert tl.get_task("Work", t["id"])["status"] == "done"
    receipts = tl.receipts()
    assert receipts[-1]["action"] == "completed"
    assert receipts[-1]["task"]["title"] == "Call Erica"
    assert _mode(tl.receipts_path) == 0o600
    tl.reopen_task("Work", t["id"])
    assert tl.get_task("Work", t["id"])["status"] == "open"
    assert tl.receipts()[-1]["action"] == "reopened"
    with pytest.raises(TaskError):
        tl.reopen_task("Work", t["id"])  # not done


def test_remove_task_keeps_full_record(tl):  # L1: restorable from receipt
    tl.create_list("Work")
    t = tl.add_task("Work", "Old thing", notes="keep me")
    tl.remove_task("Work", t["id"])
    assert tl.open_tasks("Work") == []
    rec = tl.receipts()[-1]
    assert rec["action"] == "removed" and rec["task"]["notes"] == "keep me"
    assert rec["task"]["id"] == t["id"]


def test_steps(tl):
    tl.create_list("Home")
    t = tl.add_task("Home", "Fix sink")
    s1 = tl.add_step("Home", t["id"], "Buy washer")
    s2 = tl.add_step("Home", t["id"], "Shut off water")
    tl.set_step("Home", t["id"], s1["id"], True)
    got = tl.get_task("Home", t["id"])
    steps = {s["id"]: s for s in got["steps"]}
    assert steps[s1["id"]]["done"] is True and steps[s2["id"]]["done"] is False
    tl.set_step("Home", t["id"], s1["id"], False)
    assert tl.get_task("Home", t["id"])["steps"][0]["done"] is False
    with pytest.raises(TaskError):
        tl.set_step("Home", t["id"], "s-nope", True)
    with pytest.raises(TaskError):
        tl.add_step("Home", t["id"], "  ")


def test_due_today_and_overdue(tl):
    tl.create_list("D")
    today = date.today().isoformat()
    past = (date.today() - timedelta(days=2)).isoformat()
    tl.add_task("D", "today task", due=today)
    tl.add_task("D", "late task", due=past)
    tl.add_task("D", "done late", due=past)
    done_id = tl.open_tasks("D")[2]["id"]
    tl.complete_task("D", done_id)  # completed tasks excluded
    assert [t["title"] for t in tl.due_today("D")] == ["today task"]
    assert [t["title"] for t in tl.overdue("D")] == ["late task"]


def test_by_priority_orders_urgent_first(tl):
    tl.create_list("P")
    tl.add_task("P", "low one", priority="low")
    tl.add_task("P", "urgent one", priority="urgent")
    tl.add_task("P", "high one", priority="high")
    titles = [t["title"] for t in tl.by_priority("P")]
    assert titles == ["urgent one", "high one", "low one"]


def test_search_hits_titles_notes_steps(tl):
    tl.create_list("S")
    t = tl.add_task("S", "Buy brass", notes="for candlestick")
    tl.add_step("S", t["id"], "Polish with wax")
    assert [x["title"] for x in tl.search("S", "brass")] == ["Buy brass"]
    assert [x["title"] for x in tl.search("S", "candlestick")] == ["Buy brass"]
    assert [x["title"] for x in tl.search("S", "wax")] == ["Buy brass"]
    assert tl.search("S", "zzz") == []


def test_update_task(tl):
    tl.create_list("U")
    t = tl.add_task("U", "Draft")
    u = tl.update_task("U", t["id"], title="Draft v2", priority="urgent",
                       due="2026-10-01", tags=["x"])
    assert (u["title"], u["priority"], u["due"], u["tags"]) == \
        ("Draft v2", "urgent", "2026-10-01", ["x"])
    with pytest.raises(TaskError):
        tl.update_task("U", t["id"], priority="bogus")


def test_export_import_roundtrip_is_lossless(tl, tmp_path):  # L3
    tl.create_list("Shared")
    t = tl.add_task("Shared", "Plan potluck", priority="high", due="2026-10-05")
    tl.add_step("Shared", t["id"], "Buy plates")
    tl.complete_task("Shared", t["id"])
    src_data = json.loads(tl._path("Shared").read_text())
    share = tmp_path / "shared.tasklist.json"
    tl.export_list("Shared", share)
    assert _mode(share) == 0o600
    payload = json.loads(share.read_text())
    assert payload["levi_tasklist_share"] == 1

    # import into a fresh home: lossless
    tl2_home = tmp_path / "tasklist2"
    tl2 = TaskLists(home=tl2_home)
    imported = tl2.import_list(share)
    assert imported["tasks"] == src_data["tasks"]
    assert imported["name"] == src_data["name"]
    with pytest.raises(TaskError):  # L4: re-import refused, never merged
        tl2.import_list(share)
    assert tl2.receipts()[-1]["action"] == "completed"


def test_import_rejects_non_share_files(tl, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"nope": true}')
    with pytest.raises(TaskError):
        tl.import_list(bad)


def test_rename_list(tl):
    tl.create_list("Old")
    tl.create_list("Other")
    tl.rename_list("Old", "New")
    assert tl.lists() == ["New", "Other"]
    with pytest.raises(TaskError):
        tl.rename_list("New", "Other")  # L4
    with pytest.raises(TaskError):
        tl.rename_list("Ghost", "X")  # unknown


def test_receipts_limit_and_empty(tl):
    assert tl.receipts() == []
    tl.create_list("R")
    t = tl.add_task("R", "one")
    tl.complete_task("R", t["id"])
    assert len(tl.receipts(limit=5)) == 1


def test_priorities_constant_is_ordered(tl):
    assert PRIORITIES == ("low", "normal", "high", "urgent")

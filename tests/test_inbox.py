"""Tests for the companion inbox: analytics + request box (all local)."""

import json
import os

import pytest

from levi.inbox.analytics import Analytics, record, render_daily, render_weekly
from levi.inbox.requests import RequestBox, RequestError, render_list


@pytest.fixture()
def inbox_dir(tmp_path, monkeypatch):
    d = tmp_path / "inbox"
    monkeypatch.setenv("LEVI_INBOX_DIR", str(d))
    monkeypatch.delenv("LEVI_ANALYTICS_OFF", raising=False)
    return d


def test_record_and_daily_aggregation(inbox_dir):
    assert record("chat.turn", "default")
    assert record("chat.turn", "default")
    assert record("chat.request", "default")
    agg = Analytics().daily()
    assert agg["total"] == 3
    assert agg["by_capability"] == {"chat.turn": 2, "chat.request": 1}
    text = render_daily(agg)
    assert "chat.turn: 2" in text


def test_record_rejects_bad_capability(inbox_dir):
    assert record("") is False
    assert record("../../evil") is False
    assert Analytics().daily()["total"] == 0


def test_analytics_opt_out(monkeypatch, tmp_path):
    monkeypatch.setenv("LEVI_INBOX_DIR", str(tmp_path / "inbox"))
    monkeypatch.setenv("LEVI_ANALYTICS_OFF", "1")
    assert record("chat.turn") is True
    assert Analytics().daily()["total"] == 0


def test_analytics_never_records_content(inbox_dir):
    record("chat.turn", "session-name")
    path = next(inbox_dir.glob("usage-*.jsonl"))
    data = json.loads(path.read_text().strip().splitlines()[0])
    assert set(data.keys()) == {"ts", "capability", "detail"}
    assert "content" not in data


def test_weekly_aggregation(inbox_dir):
    record("chat.turn")
    record("chat.turn")
    summary = Analytics().weekly()
    assert summary["total"] == 2
    assert summary["by_capability"]["chat.turn"] == 2
    assert "per day" in render_weekly(summary)


def test_top_capabilities(inbox_dir):
    for _ in range(5):
        record("a")
    for _ in range(2):
        record("b")
    top = Analytics().top(n=1)
    assert top == [{"capability": "a", "count": 5}]


def test_request_round_trip(inbox_dir):
    box = RequestBox()
    r1 = box.add("dark mode for the chat box")
    r2 = box.add("voice input")
    assert (r1.id, r2.id) == (1, 2)
    assert [r.id for r in box.list()] == [1, 2]
    assert "dark mode" in render_list(box.list())


def test_request_status_moves_forward_only(inbox_dir):
    box = RequestBox()
    r = box.add("x")
    box.set_status(r.id, "considered")
    box.set_status(r.id, "building")
    box.set_status(r.id, "done")
    assert box.get(r.id).status == "done"
    with pytest.raises(RequestError):
        box.set_status(r.id, "open")  # backward move refused


def test_request_status_unknown_rejected(inbox_dir):
    box = RequestBox()
    r = box.add("x")
    with pytest.raises(RequestError):
        box.set_status(r.id, "shipped")
    with pytest.raises(RequestError):
        box.set_status(999, "done")
    with pytest.raises(RequestError):
        box.list(status="nope")


def test_request_empty_text_rejected(inbox_dir):
    with pytest.raises(RequestError):
        RequestBox().add("   ")


def test_request_list_filter(inbox_dir):
    box = RequestBox()
    a = box.add("one")
    box.add("two")
    box.set_status(a.id, "considered")
    assert [r.id for r in box.list(status="open")] == [2]
    assert [r.id for r in box.list(status="considered")] == [1]


def test_files_are_owner_only(inbox_dir):
    record("chat.turn")
    RequestBox().add("x")
    for p in inbox_dir.iterdir():
        if p.is_file():
            assert oct(p.stat().st_mode & 0o777) == "0o600"
    assert oct(inbox_dir.stat().st_mode & 0o777) == "0o700"


def test_corrupt_lines_skipped(inbox_dir):
    box = RequestBox()
    box.add("good one")
    with open(box.path, "a", encoding="utf-8") as fh:
        fh.write("this is not json\n")
    assert len(box.list()) == 1
    # analytics side too
    record("chat.turn")
    path = next(inbox_dir.glob("usage-*.jsonl"))
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("{bad json\n")
    assert Analytics().daily()["total"] == 1


def test_cli_round_trip(inbox_dir, capsys):
    from levi.inbox.cli import cmd_inbox

    class A:
        pass

    a = A()
    a.inbox_cmd = "request"
    a.text = ["make", "it", "faster"]
    cmd_inbox(a)
    out = capsys.readouterr().out
    assert "request #1 saved" in out

    a2 = A()
    a2.inbox_cmd = "requests"
    cmd_inbox(a2)
    assert "#1 [open] make it faster" in capsys.readouterr().out

    a3 = A()
    a3.inbox_cmd = "request-status"
    a3.id = 1
    a3.status = "done"
    cmd_inbox(a3)
    assert "→ done" in capsys.readouterr().out

    a4 = A()
    a4.inbox_cmd = "analytics"
    a4.view = "today"
    cmd_inbox(a4)
    assert "analytics" in capsys.readouterr().out

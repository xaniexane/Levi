"""Tests for levi.daemon.herald — the notification dispatcher."""

from __future__ import annotations

import os
import stat

import pytest

from levi.daemon.herald import (
    HeraldQueue,
    LogSink,
    Notice,
    StdoutSink,
    TermuxSink,
    dispatch_once,
    notify,
)


def _queue(tmp_path) -> HeraldQueue:
    return HeraldQueue(tmp_path / "queue.jsonl")


def test_notice_validation():
    with pytest.raises(ValueError):
        Notice(title="   ")
    with pytest.raises(ValueError):
        Notice(title="ok", level="screaming")
    n = Notice(title="hi", body="there", level="urgent", source="watchers")
    assert n.level == "urgent"
    assert Notice.from_dict(n.to_dict()).title == "hi"


def test_enqueue_pending_mark_delivered(tmp_path):
    q = _queue(tmp_path)
    assert q.pending() == []
    nid = q.enqueue(Notice(title="hello", body="world", source="test"))
    pending = q.pending()
    assert len(pending) == 1
    assert pending[0].id == nid
    # queue file is owner-only
    mode = stat.S_IMODE(os.stat(q.queue_path).st_mode)
    assert mode == 0o600

    from levi.daemon.herald import NoticeReceipt

    assert q.mark_delivered(nid, NoticeReceipt(nid, True, "log")) is True
    assert q.pending() == []
    assert q.mark_delivered("nope", NoticeReceipt("nope", True, "log")) is False


def test_notify_helper(tmp_path, monkeypatch):
    monkeypatch.setattr("levi.daemon.herald.DEFAULT_QUEUE_PATH", tmp_path / "q.jsonl")
    # notify() uses the module-level default path; point a queue at it instead
    q = HeraldQueue(tmp_path / "q.jsonl")
    nid = notify("ping", "pong", level="warn", source="t", queue=q)
    assert q.pending()[0].id == nid


def test_dispatch_once_log_sink(tmp_path):
    q = _queue(tmp_path)
    log = tmp_path / "notices.log"
    q.enqueue(Notice(title="morning", body="all quiet", source="pulse"))
    receipts = dispatch_once(sinks=[LogSink(log)], queue=q)
    assert len(receipts) == 1
    r = receipts[0]
    assert r.delivered is True
    assert r.channel == "log"
    assert "morning" in log.read_text()
    assert "all quiet" in log.read_text()
    assert q.pending() == []  # delivered → removed from pending


def test_dispatch_once_first_ok_sink_wins(tmp_path):
    q = _queue(tmp_path)
    q.enqueue(Notice(title="x"))
    receipts = dispatch_once(sinks=[StdoutSink(), LogSink(tmp_path / "l.log")], queue=q)
    assert receipts[0].delivered is True
    assert receipts[0].channel == "stdout"


def test_dispatch_once_no_sink_available_keeps_pending(tmp_path):
    class DeadSink:
        channel = "dead"

        @property
        def available(self) -> bool:
            return False

    q = _queue(tmp_path)
    q.enqueue(Notice(title="stuck"))
    receipts = dispatch_once(sinks=[DeadSink()], queue=q)
    assert receipts[0].delivered is False
    assert receipts[0].channel == "none"
    assert "unavailable" in receipts[0].detail
    assert len(q.pending()) == 1  # never silently dropped


def test_dispatch_once_broken_sink_does_not_kill_dispatch(tmp_path):
    class BoomSink:
        channel = "boom"

        @property
        def available(self) -> bool:
            return True

        def send(self, notice):
            raise RuntimeError("kaput")

    q = _queue(tmp_path)
    q.enqueue(Notice(title="survives"))
    receipts = dispatch_once(sinks=[BoomSink(), LogSink(tmp_path / "l.log")], queue=q)
    assert receipts[0].delivered is True
    assert receipts[0].channel == "log"
    assert "error RuntimeError" in receipts[0].detail


def test_termux_sink_honest_when_missing(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    sink = TermuxSink()
    assert sink.available is False
    result = sink.send(Notice(title="t"))
    assert result.ok is False
    assert "not installed" in result.detail


def test_termux_sink_success_path(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/bin/termux-notification")
    calls = []

    class Proc:
        returncode = 0
        stderr = b""

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return Proc()

    sink = TermuxSink(runner=fake_run)
    result = sink.send(Notice(title="hi", body="yo", level="urgent"))
    assert result.ok is True
    assert "--priority" in calls[0]
    assert "high" in calls[0]

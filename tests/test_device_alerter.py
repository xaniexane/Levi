"""Tests for the on-device alerter (laws L1-L8). SMS send is mocked."""

import json
import os
from datetime import datetime, timezone

import pytest

import levi.device.alerter as alerter
from levi.device.alerter import (
    NoNumberError,
    check_laws,
    collect_new,
    drain,
    in_quiet_hours,
    main,
    mark_sent,
    parse_quiet,
    read_sent,
    register_source,
    shape_sms,
)


@pytest.fixture()
def iso(tmp_path, monkeypatch):
    """Isolated LEVI_HOME + device dir, quiet hours off, fake source."""
    home = tmp_path / "home"
    monkeypatch.setenv("LEVI_HOME", str(home))
    monkeypatch.setenv("LEVI_DEVICE_DIR", str(tmp_path / "device"))
    monkeypatch.setenv("LEVI_ALERT_QUIET", "off")
    monkeypatch.setenv("LEVI_ALERT_NUMBER", "555-010-0199")
    monkeypatch.delenv("LEVI_ALERT_TZ", raising=False)
    alerter.SOURCES.clear()

    def reader():
        return [
            {"uid": "t:1", "title": "Test alert", "body": "something happened"},
            {"uid": "t:2", "title": "Second", "body": ""},
        ]

    register_source("test", tmp_path / "alerts.jsonl", reader)
    return tmp_path


class FakeSms:
    def __init__(self):
        self.calls = []

    def __call__(self, number, text):
        self.calls.append((number, text))


def test_exact_argv_via_subprocess(iso, monkeypatch):
    """L8: the real sender runs exactly termux-sms-send -n <number> <text>."""
    import subprocess

    seen = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        seen["kwargs"] = kwargs

        class R:
            returncode = 0

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    alerter.send_sms("555-010-0199", "hello")
    assert seen["argv"] == ["termux-sms-send", "-n", "555-010-0199", "hello"]


def test_drain_sends_each_once(iso):
    """L2: second drain sends nothing — dedupe via sent-log."""
    fake = FakeSms()
    r1 = drain(sms_sender=fake, binary_present=True)
    assert sorted(r1.sent) == ["t:1", "t:2"]
    assert len(fake.calls) == 2
    assert read_sent() == {"t:1", "t:2"}
    r2 = drain(sms_sender=fake, binary_present=True)
    assert r2.sent == [] and len(fake.calls) == 2


def test_fail_closed_without_number(iso, monkeypatch):
    """L1: no number -> NoNumberError, nothing attempted."""
    monkeypatch.delenv("LEVI_ALERT_NUMBER")
    fake = FakeSms()
    with pytest.raises(NoNumberError, match="number not configured"):
        drain(sms_sender=fake, binary_present=True)
    assert fake.calls == []
    assert read_sent() == set()
    assert main([]) == 2  # exit code path, message on stderr


def test_number_never_in_logs(iso, capsys):
    """L3: destination number appears nowhere in output."""
    fake = FakeSms()
    drain(sms_sender=fake, binary_present=True)
    out, err = capsys.readouterr()
    assert "555-010-0199" not in out and "555-010-0199" not in err
    # but the sms itself got the real number
    assert all(n == "555-010-0199" for n, _ in fake.calls)


def test_quiet_hours_hold_and_flush(iso, monkeypatch):
    """L4: held overnight, flushed on the next pass."""
    monkeypatch.setenv("LEVI_ALERT_QUIET", "00:00-23:59")  # always quiet
    fake = FakeSms()
    r = drain(sms_sender=fake, binary_present=True)
    assert sorted(r.held) == ["t:1", "t:2"]
    assert fake.calls == [] and read_sent() == set()
    monkeypatch.setenv("LEVI_ALERT_QUIET", "off")  # morning
    r2 = drain(sms_sender=fake, binary_present=True)
    assert sorted(r2.sent) == ["t:1", "t:2"]


def test_in_quiet_hours_windows():
    assert parse_quiet("22:00-07:00") is not None
    assert parse_quiet("off") is None
    assert parse_quiet("bogus") is None
    assert in_quiet_hours(datetime(2026, 9, 23, 3, 0, tzinfo=timezone.utc)) in (True, False)


def test_termux_absent_fallback(iso, capsys):
    """L5: no binary -> console print, exit 0, nothing marked sent."""
    fake = FakeSms()
    r = drain(sms_sender=fake, binary_present=False)
    assert r.sent == [] and fake.calls == []
    out, _ = capsys.readouterr()
    assert "[alerter:console]" in out
    assert read_sent() == set()
    assert main([]) == 0


def test_registry_open(iso):
    """L6: adding a source is one call; drain loop untouched."""
    n_before = len(alerter.SOURCES)
    register_source("future", iso / "x.jsonl", lambda: [])
    assert len(alerter.SOURCES) == n_before + 1
    assert alerter.SOURCES["future"].reader() == []


def test_readers_do_not_invent(iso, monkeypatch):
    """Missing stores -> empty lists, never fabricated items."""
    assert alerter._read_demandpulse() == []
    assert alerter._read_neighbor() == []
    assert alerter._read_cybrus() == []


def test_neighbor_reader_latest_wins(iso, monkeypatch):
    home = iso / "home"
    p = home / ".levi" / "neighbor" / "nudges.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "\n".join(
            json.dumps(r)
            for r in [
                {"id": "nudge-1", "kind": "gig", "message": "hi", "status": "queued"},
                {"id": "nudge-1", "kind": "gig", "message": "hi", "status": "pulled"},
                {"id": "nudge-2", "kind": "pay", "message": "owed", "status": "queued"},
            ]
        )
    )
    items = {i["uid"]: i for i in alerter._read_neighbor()}
    assert set(items) == {"neighbor:nudge-2"}


def test_cybrus_reader_filters_barks(iso):
    home = iso / "home"
    p = home / ".levi" / "cybrus" / "audit.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "\n".join(
            json.dumps(r)
            for r in [
                {"event": "cybrus.watchdog.bark", "seq": 7,
                 "details": {"direction": "in", "signal": "x", "remedy": "fix it"}},
                {"event": "cybrus.watchdog.screen", "seq": 8, "details": {}},
            ]
        )
    )
    items = alerter._read_cybrus()
    assert [i["uid"] for i in items] == ["cybrus:7"]
    assert "fix it" in items[0]["body"]


def test_shape_sms_short_plain():
    text = shape_sms("herald", "Watchdog bark", "line one\nline two")
    assert text == "[herald] Watchdog bark — line one"
    long_text = shape_sms("x", "t", "b" * 500)
    assert len(long_text) <= alerter.MAX_BODY_CHARS


def test_check_laws_ok(iso):
    report = check_laws()
    assert report["ok"], report["problems"]
    assert len(report["laws"]) == 8


def test_mark_sent_is_append_only(iso):
    mark_sent("a")
    mark_sent("b")
    assert read_sent() == {"a", "b"}

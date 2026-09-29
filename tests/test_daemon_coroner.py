"""Tests for the coroner crash-digest daemon."""

import json

import pytest

from levi.daemon.coroner import (
    CoronerError,
    digest_reports,
    load_reports,
    render_digest,
    run_once,
)


def _write_report(d, name, child, exc, at, restart_count=0):
    payload = {
        "child": child,
        "exc_type": exc,
        "message": "boom",
        "traceback": "tb",
        "at": at,
        "at_iso": "2026-09-25T12:00:00+00:00",
        "restart_count": restart_count,
    }
    (d / name).write_text(json.dumps(payload))
    return payload


def test_load_reports_skips_corrupt(tmp_path):
    _write_report(
        tmp_path, "crash-a.json", "levi-heartbeat", "ValueError", 1_700_000_000
    )
    (tmp_path / "crash-bad.json").write_text("{not json")
    (tmp_path / "crash-wrong.json").write_text(json.dumps({"nope": True}))
    (tmp_path / "notes.txt").write_text("ignored: not json")
    reports, skipped = load_reports(tmp_path)
    assert len(reports) == 1
    assert skipped == 2  # corrupt + misshapen; .txt not counted


def test_missing_dir_refused(tmp_path):
    with pytest.raises(CoronerError):
        load_reports(tmp_path / "nope")


def test_digest_counts_and_last(tmp_path):
    _write_report(tmp_path, "c1.json", "levi-heartbeat", "ValueError", 1_700_000_001)
    _write_report(tmp_path, "c2.json", "levi-heartbeat", "KeyError", 1_700_000_002)
    _write_report(tmp_path, "c3.json", "levi-growth", "RuntimeError", 1_700_000_003)
    reports, skipped = load_reports(tmp_path)
    digest = digest_reports(reports, skipped)
    assert digest.total_reports == 3
    assert digest.services["levi-heartbeat"].crashes == 2
    assert digest.services["levi-heartbeat"].last_exc == "KeyError"
    assert digest.services["levi-growth"].crashes == 1


def test_repeat_offender_and_restart_limit():
    base = 1_700_000_000
    reports = [
        {
            "child": "levi-heartbeat",
            "exc_type": "ValueError",
            "at": base + i * 3600,
            "at_iso": "2026-09-25T12:00:00+00:00",
            "restart_count": 5,
        }
        for i in range(3)
    ]
    reports.append(
        {
            "child": "levi-growth",
            "exc_type": "KeyError",
            "at": base,
            "at_iso": "2026-09-25T12:00:00+00:00",
            "restart_count": 1,
        }
    )
    from datetime import datetime, timezone

    now = datetime.fromtimestamp(base + 3 * 3600 + 1, timezone.utc)
    digest = digest_reports(reports, now=now)
    assert digest.repeat_offenders == ["levi-heartbeat"]
    assert digest.services["levi-heartbeat"].at_restart_limit is True
    assert digest.services["levi-growth"].at_restart_limit is False


def test_render_digest_quiet_and_loud(tmp_path):
    quiet = render_digest(digest_reports([]))
    assert "quiet" in quiet
    _write_report(
        tmp_path,
        "c.json",
        "levi-heartbeat",
        "ValueError",
        1_700_000_000,
        restart_count=5,
    )
    reports, skipped = load_reports(tmp_path)
    loud = render_digest(digest_reports(reports, skipped))
    assert "levi-heartbeat" in loud
    assert "AT RESTART LIMIT" in loud


def test_run_once_prints(tmp_path, capsys):
    _write_report(tmp_path, "c.json", "levi-heartbeat", "ValueError", 1_700_000_000)
    assert run_once(tmp_path) == 0
    assert "Crash digest" in capsys.readouterr().out

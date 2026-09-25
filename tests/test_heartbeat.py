"""Hermetic tests for the autonomous heartbeat (core/levi/daemon/heartbeat.py).

Everything runs against a tmp home dir: Path.home is monkeypatched so the
real ~/.levi is never touched.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from levi.daemon.heartbeat import (
    HeartbeatResult,
    cmd_heartbeat,
    run_heartbeat,
)


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


def _at(day: int, hour: int) -> datetime:
    """Naive local datetime on 2026-09-{day} at hour:00 (tests treat as local)."""
    return datetime(2026, 9, day, hour, 0, 0)


def _write_memory_index(home: Path, entries) -> None:
    mem_dir = home / ".levi" / "memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    (mem_dir / "index.json").write_text(
        json.dumps({"version": 1, "entries": entries}), encoding="utf-8"
    )


def _growth_entry(created_at: str, content: str = "learned a thing"):
    return {
        "id": "test-1",
        "memory_type": "semantic",
        "content": content,
        "metadata": {"status": "provisional", "confidence": 0.8},
        "importance": 0.7,
        "created_at": created_at,
        "updated_at": created_at,
        "source": "growth",
        "tags": ["growth", "levi-learned", "fact"],
        "project_id": None,
        "embedding_ref": None,
        "version": 1,
    }


class Args:
    """Minimal argparse namespace stand-in."""

    def __init__(self, **kwargs):
        self.heartbeat_action = kwargs.pop("heartbeat_action", "run")
        for k, v in kwargs.items():
            setattr(self, k, v)


# --------------------------------------------------------------------------
# seeded attention item → digest, silent=False
# --------------------------------------------------------------------------


def test_provisional_learning_seed_produces_digest(home, capsys):
    _write_memory_index(home, [_growth_entry("2026-09-15T19:00:00+00:00")])
    result = run_heartbeat(home=home, now=_at(15, 14), force=True)
    assert isinstance(result, HeartbeatResult)
    assert result.silent is False
    assert "attention" in result.reason
    assert any("provisional learning" in item for item in result.attention)

    digest = home / ".levi" / "heartbeat" / "last_digest.md"
    assert digest.exists()
    text = digest.read_text(encoding="utf-8")
    assert "provisional learning" in text

    cmd_heartbeat(Args(heartbeat_action="run", force=True))
    out = capsys.readouterr().out
    assert "provisional learning" in out


# --------------------------------------------------------------------------
# clean home → silent
# --------------------------------------------------------------------------


def test_clean_home_is_silent(home, capsys):
    result = run_heartbeat(home=home, now=_at(15, 14), force=True)
    assert result.silent is True
    assert result.reason == "nothing needs attention"
    assert result.attention == []

    cmd_heartbeat(Args(heartbeat_action="run", force=True))
    out = capsys.readouterr().out
    assert "quiet" in out
    assert "nothing needs attention" in out


# --------------------------------------------------------------------------
# active-hours gating
# --------------------------------------------------------------------------


def test_outside_active_hours_is_silent(home):
    result = run_heartbeat(home=home, now=_at(15, 3))
    assert result.silent is True
    assert result.reason == "outside active hours"
    assert result.attention == []


def test_force_bypasses_active_hours_gate(home):
    # Documented contract (run_heartbeat docstring): force=True bypasses
    # both the active-hours gate and the interval gate.
    result = run_heartbeat(home=home, now=_at(15, 3), force=True)
    assert result.reason != "outside active hours"


def test_inside_active_hours_proceeds(home):
    result = run_heartbeat(home=home, now=_at(15, 14), force=True)
    assert result.reason != "outside active hours"


# --------------------------------------------------------------------------
# interval: second run inside interval is a no-op
# --------------------------------------------------------------------------


def test_interval_second_run_is_noop(home):
    first = run_heartbeat(home=home, now=_at(15, 14), force=True)
    assert first.reason != "interval not elapsed"
    second = run_heartbeat(home=home, now=datetime(2026, 9, 15, 14, 10))
    assert second.silent is True
    assert second.reason == "interval not elapsed"


def test_interval_force_reruns(home):
    run_heartbeat(home=home, now=_at(15, 14), force=True)
    rerun = run_heartbeat(home=home, now=_at(15, 14), force=True)
    assert rerun.reason != "interval not elapsed"


def test_interval_env_override(home, monkeypatch):
    monkeypatch.setenv("LEVI_HEARTBEAT_INTERVAL_MIN", "60")
    run_heartbeat(home=home, now=_at(15, 14), force=True)
    # 40 minutes later is still inside the 60-min interval
    second = run_heartbeat(home=home, now=datetime(2026, 9, 15, 14, 40))
    assert second.reason == "interval not elapsed"


# --------------------------------------------------------------------------
# status action
# --------------------------------------------------------------------------


def test_status_action_prints_state(home, capsys):
    run_heartbeat(home=home, now=_at(15, 14), force=True)
    cmd_heartbeat(Args(heartbeat_action="status"))
    out = capsys.readouterr().out
    assert "last run" in out
    assert "interval" in out
    assert "active hours" in out
    assert "attention items" in out


# --------------------------------------------------------------------------
# resilience: a broken source must not crash the run
# --------------------------------------------------------------------------


def test_broken_source_does_not_crash(home):
    mem_dir = home / ".levi" / "memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    (mem_dir / "index.json").write_text("not json {{{", encoding="utf-8")
    result = run_heartbeat(home=home, now=_at(15, 14), force=True)
    assert result.silent is False
    assert any("heartbeat check" in item for item in result.attention)


# ---------------------------------------------------------------------------
# Interval validation hardening
# ---------------------------------------------------------------------------


def test_resolve_interval_rejects_bad_explicit_values():
    from levi.daemon.heartbeat import _resolve_interval

    assert _resolve_interval(30) == 30
    assert _resolve_interval(None) == 30  # default when env unset
    for bad in (0, -5, 1.5, True, "30", float("nan")):
        with pytest.raises(ValueError, match="integer >= 1"):
            _resolve_interval(bad)


def test_resolve_interval_env_degrades_to_default(monkeypatch):
    from levi.daemon.heartbeat import _resolve_interval, ENV_INTERVAL

    monkeypatch.setenv(ENV_INTERVAL, "not-a-number")
    assert _resolve_interval() == 30
    monkeypatch.setenv(ENV_INTERVAL, "-10")
    assert _resolve_interval() == 30
    monkeypatch.setenv(ENV_INTERVAL, "0")
    assert _resolve_interval() == 30
    monkeypatch.setenv(ENV_INTERVAL, "45")
    assert _resolve_interval() == 45


def test_study_interval_hours_rejects_bad_env(monkeypatch):
    from levi.daemon.heartbeat import (
        _study_interval_hours,
        STUDY_ENV_INTERVAL,
        STUDY_DEFAULT_INTERVAL_HOURS,
    )

    for bad in ("garbage", "nan", "inf", "-2", "0"):
        monkeypatch.setenv(STUDY_ENV_INTERVAL, bad)
        assert _study_interval_hours() == float(STUDY_DEFAULT_INTERVAL_HOURS)
    monkeypatch.setenv(STUDY_ENV_INTERVAL, "6")
    assert _study_interval_hours() == 6.0
    monkeypatch.delenv(STUDY_ENV_INTERVAL, raising=False)
    assert _study_interval_hours() == float(STUDY_DEFAULT_INTERVAL_HOURS)

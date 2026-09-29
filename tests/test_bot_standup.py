"""Tests for the bot standup composer."""

import pytest

from levi.bot.standup import (
    StandupError,
    compose_standup,
    crash_provider,
    default_providers,
    disk_provider,
)


def test_compose_basic_card():
    card = compose_standup(
        "Morning standup",
        {"alpha": lambda: ["line one", "line two"], "beta": lambda: ["solo"]},
    )
    assert "Morning standup" in card.text
    assert "alpha" in card.text
    assert "line one" in card.text
    assert "solo" in card.text


def test_raising_provider_becomes_silent():
    def bad():
        raise RuntimeError("nope")

    card = compose_standup("T", {"bad": bad, "good": lambda: ["ok"]})
    assert "SILENT (RuntimeError)" in card.text
    assert "ok" in card.text


def test_bad_provider_shape_becomes_silent():
    card = compose_standup("T", {"weird": lambda: "not a list"})
    assert "SILENT (bad provider shape)" in card.text


def test_malformed_tables_refused():
    with pytest.raises(StandupError):
        compose_standup("T", {})
    with pytest.raises(StandupError):
        compose_standup("T", {"x": "not callable"})
    with pytest.raises(StandupError):
        compose_standup("   ", {"x": lambda: []})
    with pytest.raises(StandupError):
        compose_standup("T", {"": lambda: []})


def test_deterministic():
    providers = {"a": lambda: ["1", "2"], "b": lambda: ["3"]}
    one = compose_standup("T", providers).text
    two = compose_standup("T", providers).text
    assert one == two


def test_disk_provider_band_line():
    lines = disk_provider()
    assert len(lines) == 1
    assert lines[0].startswith("disk ")
    assert any(band in lines[0] for band in ("ok", "warn", "crit"))


def test_crash_provider_no_dir(monkeypatch, tmp_path):
    import levi.daemon.coroner as coroner

    monkeypatch.setattr(coroner, "DEFAULT_CRASH_DIR", tmp_path / "nope")
    assert crash_provider() == ["no crash directory yet"]


def test_crash_provider_with_reports(tmp_path, monkeypatch):
    import json

    import levi.daemon.coroner as coroner

    d = tmp_path / "crashes"
    d.mkdir()
    (d / "crash-x.json").write_text(
        json.dumps(
            {
                "child": "levi-heartbeat",
                "exc_type": "ValueError",
                "at": 1_700_000_000,
                "at_iso": "2026-09-25T12:00:00+00:00",
                "restart_count": 1,
            }
        )
    )
    monkeypatch.setattr(coroner, "DEFAULT_CRASH_DIR", d)
    lines = crash_provider()
    assert any("levi-heartbeat" in line for line in lines)


def test_default_providers_table():
    providers = default_providers()
    assert set(providers) == {"crashes", "disk"}
    card = compose_standup("Morning standup", providers)
    assert "Morning standup" in card.text

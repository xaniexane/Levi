"""Tests for the briefing renderer (file outbox only — never sends)."""

import pytest

from levi.demandpulse import briefing
from levi.demandpulse.ternary import classify


def _digest(**kw):
    base = {
        "digest_id": "d1",
        "generated_at": "2026-09-29T00:00:00Z",
        "items": [],
        "quarantined": [],
    }
    base.update(kw)
    return base


def test_render_sections_present():
    text = briefing.render_briefing(
        _digest(), ternary_states=[classify("widgets", [0, 1, 9])]
    )
    for section in ("BREAKING", "GATHERING", "WATCHING", "QUIET",
                    "QUARANTINED", "LABEL LEGEND"):
        assert section in text
    assert "FILE OUTBOX ONLY" in text
    assert "widgets" in text


def test_render_rejects_garbage_digest():
    with pytest.raises(ValueError, match="digest must be"):
        briefing.render_briefing(None)
    with pytest.raises(ValueError, match="digest must be"):
        briefing.render_briefing(42)


def test_render_tolerates_non_mapping_items():
    text = briefing.render_briefing(
        _digest(items=["just a string", {"title": "real"}],
                quarantined=["held raw"]))
    assert "just a string" in text
    assert "real" in text
    assert "held raw" in text


def test_write_briefing_rejects_hostile_stamp(tmp_path):
    with pytest.raises(ValueError, match="stamp"):
        briefing.write_briefing("x", home=tmp_path, stamp="../../escape")
    assert not (tmp_path.parent / "escape").exists()


def test_write_briefing_never_overwrites(tmp_path):
    p1 = briefing.write_briefing("a", home=tmp_path, stamp="s1")
    p2 = briefing.write_briefing("b", home=tmp_path, stamp="s1")
    assert p1 != p2
    assert p1.read_text() == "a" and p2.read_text() == "b"

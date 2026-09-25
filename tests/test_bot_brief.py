"""Tests for levi.bot.brief: plain-text briefing cards with a line budget."""

import pytest

from levi.bot.brief import BriefError, render_brief


def _sections():
    return [
        ("Pulse", ["3 services up", "growth tick at 06:00"]),
        ("Watch", ["disk at 71%"]),
    ]


def test_brief_renders_title_and_headings():
    card = render_brief("Morning brief", _sections())
    assert card.text.startswith("Morning brief\n=============")
    assert "Pulse" in card.text
    assert "Watch" in card.text
    assert card.dropped == 0
    assert card.sections == 2


def test_brief_respects_the_budget():
    card = render_brief("Brief", _sections(), max_lines=9)
    assert card.lines <= 9
    # title(2) + 2 headings(4) + 3 body lines fit exactly: no drops
    assert card.dropped == 0


def test_brief_holds_back_body_with_a_counted_note():
    card = render_brief("Brief", _sections(), max_lines=7)
    assert card.lines <= 7
    assert card.dropped == 2
    assert "[2 line(s) held back" in card.text
    # headings are never dropped
    assert "Pulse" in card.text and "Watch" in card.text


def test_brief_fills_sections_in_order():
    sections = [("First", ["a1", "a2"]), ("Second", ["b1", "b2"])]
    card = render_brief("Brief", sections, max_lines=8)
    # min 2 + 4 = 6, body budget 2, 4 body lines -> 2 dropped, note takes a slot
    assert card.dropped == 2
    assert "a1" in card.text
    assert "b1" not in card.text  # second section's body didn't fit


def test_brief_deterministic():
    first = render_brief("B", _sections(), max_lines=10)
    second = render_brief("B", _sections(), max_lines=10)
    assert first == second


def test_brief_accepts_dict_sections():
    card = render_brief("Brief", [{"heading": "H", "lines": ["one"]}], max_lines=10)
    assert "H" in card.text
    assert "one" in card.text


def test_brief_rejects_budget_too_small_for_headings():
    with pytest.raises(BriefError):
        render_brief("Brief", [("A", []), ("B", [])], max_lines=4)
    # 2 (title) + 4 (two headings) = 6 minimum; 6 fits
    card = render_brief("Brief", [("A", []), ("B", [])], max_lines=6)
    assert card.lines == 6


def test_brief_rejects_bad_title():
    with pytest.raises(BriefError):
        render_brief("", _sections())
    with pytest.raises(BriefError):
        render_brief("   ", _sections())


def test_brief_rejects_bad_sections():
    with pytest.raises(BriefError):
        render_brief("Brief", [])
    with pytest.raises(BriefError):
        render_brief("Brief", [("", ["x"])])
    with pytest.raises(BriefError):
        render_brief("Brief", [("H", ["x", 3])])


def test_brief_rejects_bad_budget():
    with pytest.raises(BriefError):
        render_brief("Brief", _sections(), max_lines=3)
    with pytest.raises(BriefError):
        render_brief("Brief", _sections(), max_lines="many")

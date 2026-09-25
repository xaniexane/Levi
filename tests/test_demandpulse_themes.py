"""Tests for the structured theme packs (Myspace-style customization, safe).

Safety is the test: no theme can inject HTML/JS or arbitrary escapes —
values are whitelisted before they ever reach the terminal.
"""

import pytest

from levi.demandpulse import themes


def test_bundled_themes_validate():
    for name in themes.list_themes():
        assert themes.get_theme(name)  # raises on invalid


def test_default_theme_is_void():
    th = themes.get_theme("void")
    assert set(th) == set(themes.THEME_SCHEMA_KEYS)


def test_unknown_theme_raises():
    with pytest.raises(themes.ThemeError):
        themes.get_theme("midnight-hacker")


@pytest.mark.parametrize(
    "bad",
    [
        {
            "fg": "white",
            "accent": "cyan",
            "dim": "gray",
            "rule": "=",
            "bullet": ">",
            "extra": "x",
        },  # unknown key
        {"fg": "white", "accent": "cyan", "dim": "gray", "rule": "="},  # missing key
        {
            "fg": "white",
            "accent": "not-a-color",
            "dim": "gray",
            "rule": "=",
            "bullet": ">",
        },  # color outside whitelist
        {
            "fg": "white",
            "accent": "cyan",
            "dim": "gray",
            "rule": "<script>",
            "bullet": ">",
        },  # rule injection attempt
        {
            "fg": "white",
            "accent": "cyan",
            "dim": "gray",
            "rule": "=",
            "bullet": "\x1b[31m",
        },  # escape injection attempt
        {
            "fg": "white",
            "accent": "cyan",
            "dim": "gray",
            "rule": "=",
            "bullet": ">>",
        },  # multi-char bullet
    ],
)
def test_invalid_themes_rejected(bad):
    with pytest.raises(themes.ThemeError):
        themes.validate_theme(bad)


def test_valid_custom_theme_accepted():
    custom = {"fg": "black", "accent": "red", "dim": "gray", "rule": "#", "bullet": "+"}
    assert themes.validate_theme(custom) == custom


def test_paint_uses_only_fixed_ansi_map():
    out = themes.paint(themes.get_theme("void"), "accent", "hello")
    assert out.startswith("\033[")
    assert out.endswith("\033[0m")
    # no theme value can smuggle raw markup into the output
    assert "<script" not in out and "javascript" not in out


def test_paint_bad_role_rejected():
    with pytest.raises(themes.ThemeError):
        themes.paint(themes.get_theme("void"), "background", "x")


def test_rule_line_uses_theme_glyph():
    line = themes.rule_line(themes.get_theme("ember"))
    assert set(line) == {"~"}
    assert 8 <= len(line) <= 120

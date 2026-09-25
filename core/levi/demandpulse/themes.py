"""Myspace-style system-wide customization — safe and structured.

The directive: theming applies THROUGHOUT the product's surfaces (briefing
renderer, digest output, CLI), not just one page. Safe means: theme packs
are frozen dictionaries of whitelisted tokens — named colors from a fixed
ANSI map and rule/bullet characters from a fixed set. There is no path by
which raw HTML, JS, or arbitrary escape sequences can enter the output,
because values are validated against the whitelist before they are ever
used. Custom themes are welcome — they must pass the same validation.

Works on mobile terminals: plain ANSI + ASCII, no cursor games.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

THEME_SCHEMA_KEYS = ("fg", "accent", "dim", "rule", "bullet")

# Fixed ANSI map — the only colors that can ever reach the terminal.
ANSI_COLORS = {
    "black": "30",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
    "white": "37",
    "gray": "90",
    "bright_red": "91",
    "bright_green": "92",
    "bright_yellow": "93",
    "bright_blue": "94",
    "bright_magenta": "95",
    "bright_cyan": "96",
    "bright_white": "97",
}

# The only rule/bullet glyphs a theme may use.
RULE_CHARS = frozenset("=-~*#+-·—")
BULLET_CHARS = frozenset(">-*•+»")


class ThemeError(ValueError):
    """A theme pack failed validation — it is never applied."""


THEMES: Dict[str, Dict[str, str]] = {
    "void": {  # default: dark-first, the house style
        "fg": "bright_white",
        "accent": "bright_cyan",
        "dim": "gray",
        "rule": "=",
        "bullet": ">",
    },
    "paper": {  # light-terminal friendly
        "fg": "black",
        "accent": "blue",
        "dim": "gray",
        "rule": "-",
        "bullet": "-",
    },
    "ember": {  # warm alt
        "fg": "bright_white",
        "accent": "bright_yellow",
        "dim": "gray",
        "rule": "~",
        "bullet": "*",
    },
}


def list_themes() -> list:
    """Names of the bundled theme packs, sorted."""
    return sorted(THEMES)


def validate_theme(theme: Mapping[str, Any]) -> Dict[str, str]:
    """Validate a theme pack against the schema. Raises ThemeError on any
    unknown key, missing key, or value outside the whitelists. Returns a
    plain dict copy — the caller's object is never trusted as-is."""
    if not isinstance(theme, Mapping):
        raise ThemeError("theme must be a mapping")
    keys = set(theme.keys())
    if keys != set(THEME_SCHEMA_KEYS):
        raise ThemeError(
            f"theme keys must be exactly {THEME_SCHEMA_KEYS}, got {sorted(keys)}"
        )
    clean: Dict[str, str] = {}
    for key in THEME_SCHEMA_KEYS:
        value = theme[key]
        if not isinstance(value, str):
            raise ThemeError(f"theme[{key!r}] must be a string")
        if key in ("fg", "accent", "dim"):
            if value not in ANSI_COLORS:
                raise ThemeError(
                    f"theme[{key!r}]={value!r} not in color whitelist "
                    f"{sorted(ANSI_COLORS)}"
                )
        elif key == "rule":
            if len(value) != 1 or value not in RULE_CHARS:
                raise ThemeError(f"theme['rule']={value!r} not in {sorted(RULE_CHARS)}")
        else:  # bullet
            if len(value) != 1 or value not in BULLET_CHARS:
                raise ThemeError(
                    f"theme['bullet']={value!r} not in {sorted(BULLET_CHARS)}"
                )
        clean[key] = value
    return clean


def get_theme(name: str) -> Dict[str, str]:
    """Fetch and validate a bundled theme pack by name."""
    if name not in THEMES:
        raise ThemeError(f"unknown theme {name!r}; available: {list_themes()}")
    return validate_theme(THEMES[name])


def paint(theme: Mapping[str, str], role: str, text: str) -> str:
    """Colorize ``text`` for one of the fg/accent/dim roles.

    The theme must already be validated; ANSI codes come only from the
    fixed map, so no theme can inject arbitrary escapes.
    """
    valid = validate_theme(theme)
    if role not in ("fg", "accent", "dim"):
        raise ThemeError(f"paint role must be fg/accent/dim, got {role!r}")
    code = ANSI_COLORS[valid[role]]
    return f"\033[{code}m{text}\033[0m"


def rule_line(theme: Mapping[str, str], width: int = 64) -> str:
    """A horizontal rule in the theme's rule character."""
    valid = validate_theme(theme)
    return valid["rule"] * max(8, min(width, 120))

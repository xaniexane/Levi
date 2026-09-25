"""Structured theming — Myspace-style customization, safe by construction.

The Myspace doctrine: theming applies THROUGHOUT the platform, every
surface, not just profiles. This module is the seed of that: a
structured theme registry where a theme is a plain dict of declared
slots — never raw HTML/JS, never injected markup. Validation rejects
anything that looks like injection, and themes are local 0600 files.

Ternary where it fits: a theme slot has three states — a declared
value, ``"inherit"`` (take the surface default), or absent (slot
unused). Binary would force value-or-nothing; the third state is the
one the giants skip.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

__all__ = [
    "ThemeError",
    "active_theme",
    "default_theme",
    "list_themes",
    "save_theme",
    "validate_theme",
]

# ---------------------------------------------------------------------------
# Schema — declared slots only.
# ---------------------------------------------------------------------------

#: Every themeable slot. A theme may set any subset; unset slots are
#: absent (the third state next to value / "inherit").
SLOTS = (
    "background",
    "accent",
    "surface",
    "text",
    "font",
    "layout",
    "mood",
)

FONTS = ("system", "serif", "rounded", "mono")
LAYOUTS = ("cozy", "airy", "dense")
MOODS = ("calm", "playful", "noir", "dawn")

_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

#: Anything matching this is rejected outright — themes are data, never
#: markup or code.
_INJECTION_RE = re.compile(
    r"(<\s*/?\s*[a-zA-Z]|javascript\s*:|on\w+\s*=|&\s*#|{{|}}|\\u|\\x)",
    re.IGNORECASE,
)

INHERIT = "inherit"

_RECORD_MODE = 0o600


class ThemeError(ValueError):
    """Raised when a theme breaks the schema or looks like injection."""


def default_theme() -> Dict[str, str]:
    """The built-in default — calm, dark-first, declared."""
    return {
        "background": "#0d0f14",
        "accent": "#7dd3a8",
        "surface": "#161a23",
        "text": "#e8eaf0",
        "font": "system",
        "layout": "cozy",
        "mood": "calm",
    }


def validate_theme(theme: Mapping[str, Any]) -> Dict[str, str]:
    """Validate a theme mapping. Returns a clean plain-dict copy.

    Raises :class:`ThemeError` on: unknown slots, non-string values,
    bad colors, unknown font/layout/mood tokens, or anything matching
    the injection pattern. ``"inherit"`` is accepted for any slot.
    """
    if not isinstance(theme, Mapping):
        raise ThemeError("theme must be a mapping.")
    clean: Dict[str, str] = {}
    for slot, value in theme.items():
        if slot not in SLOTS:
            raise ThemeError("unknown theme slot: %r." % (slot,))
        if not isinstance(value, str):
            raise ThemeError("slot %r must be a string." % (slot,))
        if _INJECTION_RE.search(value):
            raise ThemeError(
                "slot %r looks like markup/code — themes are data, "
                "never injection." % (slot,)
            )
        if value == INHERIT:
            clean[slot] = value
            continue
        if slot in ("background", "accent", "surface", "text"):
            if not _COLOR_RE.match(value):
                raise ThemeError("slot %r must be a #rgb or #rrggbb color." % (slot,))
        elif slot == "font" and value not in FONTS:
            raise ThemeError("font must be one of %s." % (", ".join(FONTS),))
        elif slot == "layout" and value not in LAYOUTS:
            raise ThemeError("layout must be one of %s." % (", ".join(LAYOUTS),))
        elif slot == "mood" and value not in MOODS:
            raise ThemeError("mood must be one of %s." % (", ".join(MOODS),))
        clean[slot] = value
    return clean


def _theme_dir(home: Optional[Path] = None) -> Path:
    base = Path(home) if home is not None else Path.home()
    return base / ".levi" / "echoverse" / "themes"


def save_theme(home: Path, name: str, theme: Mapping[str, Any]) -> Path:
    """Save a validated theme locally (0600). Opt-in: caller passes home."""
    if not name or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name):
        raise ThemeError("theme name must be 1-64 chars of [A-Za-z0-9_-].")
    clean = validate_theme(theme)
    path = _theme_dir(home) / (name + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, _RECORD_MODE)
    return path


def list_themes(home: Optional[Path] = None) -> Dict[str, Dict[str, str]]:
    """All saved themes plus the built-in default."""
    out: Dict[str, Dict[str, str]] = {"default": default_theme()}
    d = _theme_dir(home)
    if d.is_dir():
        for path in sorted(d.glob("*.json")):
            try:
                out[path.stem] = validate_theme(
                    json.loads(path.read_text(encoding="utf-8"))
                )
            except (OSError, ValueError, ThemeError):
                continue  # a hand-edited broken file never breaks listing
    return out


def active_theme(home: Optional[Path] = None) -> Dict[str, str]:
    """The theme in force: saved 'active' theme, else the default."""
    saved = list_themes(home)
    return saved.get("active", saved["default"])

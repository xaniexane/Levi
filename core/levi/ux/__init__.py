"""Terminal UX effects kit for LEVI — stdlib-only, no curses, no third-party deps.

Every effect in :mod:`levi.ux.effects` is gated by :func:`effects_enabled`,
so output automatically degrades to plain readable text when stdout is not
a TTY or when the ``NO_COLOR`` environment variable is set: zero ANSI
escape codes, no cursor movement, no spinners.  A single glyph helper
(:func:`_unicode_ok`) keeps every character renderable, falling back to
ASCII-safe glyphs when the terminal encoding cannot represent them.
"""

from __future__ import annotations

from levi.ux.effects import (
    ProgressBar,
    Spinner,
    Table,
    banner,
    clear_status_line,
    color,
    confirm,
    effects_enabled,
    menu,
    meter,
    pause_for_key,
    rule,
    sparkline,
    status_line,
    typing_print,
)

from levi.ux.dynamic import (
    DynamicUIError,
    buttons,
    card,
    envelope,
    form,
    intent_action,
    progress,
    text,
    url_action,
    validate_payload,
)

__all__ = [
    "DynamicUIError",
    "ProgressBar",
    "Spinner",
    "Table",
    "banner",
    "buttons",
    "card",
    "clear_status_line",
    "color",
    "confirm",
    "effects_enabled",
    "envelope",
    "form",
    "intent_action",
    "menu",
    "meter",
    "pause_for_key",
    "progress",
    "rule",
    "sparkline",
    "status_line",
    "text",
    "typing_print",
    "url_action",
    "validate_payload",
]

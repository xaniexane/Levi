"""Myspace-style structured theming for every editor surface.

The directive: system-wide customization, applied THROUGHOUT — buffer,
gutter, command bar, tab strip, snippet row, file tree, status — not just
profiles. Safe by construction: themes are validated data (hex colors,
bounded numbers, plain strings). Raw HTML/JS/CSS injection is rejected
at validation time, never rendered. Works on mobile: no web views needed.

A theme styles named SURFACES; ``customize()`` lets the builder remix any
surface off a base theme — the Myspace instinct, rebuilt structured.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from levi.hicomb.highlight import TOKEN_KINDS

SURFACES = (
    "buffer",
    "gutter",
    "command_bar",
    "tab_strip",
    "snippet_row",
    "file_tree",
    "status",
)

UI_COLOR_KEYS = frozenset(
    {
        "background",
        "surface",
        "text",
        "muted",
        "accent",
        "accent2",
        "selection",
        "cursor",
        "line_highlight",
    }
)

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
# Anything that smells like markup, script, or style injection dies here.
DANGEROUS_RE = re.compile(
    r"<|>|javascript\s*:|data\s*:|vbscript\s*:|expression\s*\(|"
    r"url\s*\(|@import|script|on\w+\s*=",
    re.IGNORECASE,
)
MAX_NAME_LEN = 48
MAX_STRING_LEN = 64
# Theme names are identifiers, not free text: a tight charset kills
# template/markup injection at the front door, before DANGEROUS_RE.
NAME_RE = re.compile(r"^[A-Za-z0-9 _.\-]{1,48}$")


class ThemeError(ValueError):
    """A theme failed validation — rejected, never partially applied."""


@dataclass(frozen=True)
class Theme:
    name: str
    ui: dict  # UI_COLOR_KEYS -> #RRGGBB
    syntax: dict  # TOKEN_KINDS subset -> #RRGGBB
    font_scale: float = 1.0
    corner_radius: int = 8
    font_family: str = "monospace"
    surfaces: tuple = SURFACES

    def color_for(self, kind: str) -> str:
        """Syntax color for a token kind; falls back to text color."""
        return self.syntax.get(kind, self.ui["text"])

    def to_json(self) -> str:
        return json.dumps(
            {
                "name": self.name,
                "ui": self.ui,
                "syntax": self.syntax,
                "font_scale": self.font_scale,
                "corner_radius": self.corner_radius,
                "font_family": self.font_family,
                "surfaces": list(self.surfaces),
            },
            indent=2,
            sort_keys=True,
        )


def _check_name(value: str) -> str:
    if not isinstance(value, str) or not NAME_RE.match(value):
        raise ThemeError(f"name: must match [A-Za-z0-9 _.-]{{1,48}}: {value!r}")
    return value


def _check_hex(value: str, where: str) -> str:
    if not isinstance(value, str) or not HEX_RE.match(value):
        raise ThemeError(f"{where}: not a #RRGGBB color: {value!r}")
    return value.lower()


def _check_string(value: str, where: str, limit: int = MAX_STRING_LEN) -> str:
    if not isinstance(value, str) or len(value) > limit:
        raise ThemeError(f"{where}: bad string: {value!r}")
    if DANGEROUS_RE.search(value):
        raise ThemeError(f"{where}: rejected (markup/script injection): {value!r}")
    return value


def validate_theme(data: dict) -> Theme:
    """Validate raw theme data into an immutable Theme. Raises ThemeError."""
    if not isinstance(data, dict):
        raise ThemeError("theme must be a mapping")
    name = _check_name(data.get("name", ""))

    ui_raw = data.get("ui", {})
    if not isinstance(ui_raw, dict):
        raise ThemeError("theme.ui must be a mapping")
    unknown_ui = set(ui_raw) - UI_COLOR_KEYS
    if unknown_ui:
        raise ThemeError(f"unknown ui keys: {sorted(unknown_ui)}")
    missing_ui = UI_COLOR_KEYS - set(ui_raw)
    if missing_ui:
        raise ThemeError(f"missing ui keys: {sorted(missing_ui)}")
    ui = {k: _check_hex(ui_raw[k], f"ui.{k}") for k in UI_COLOR_KEYS}

    syn_raw = data.get("syntax", {})
    if not isinstance(syn_raw, dict):
        raise ThemeError("theme.syntax must be a mapping")
    unknown_syn = set(syn_raw) - set(TOKEN_KINDS)
    if unknown_syn:
        raise ThemeError(f"unknown syntax kinds: {sorted(unknown_syn)}")
    syntax = {k: _check_hex(v, f"syntax.{k}") for k, v in syn_raw.items()}

    font_scale = data.get("font_scale", 1.0)
    if not isinstance(font_scale, (int, float)) or not 0.5 <= font_scale <= 3.0:
        raise ThemeError(f"font_scale out of range: {font_scale!r}")
    corner_radius = data.get("corner_radius", 8)
    if not isinstance(corner_radius, int) or not 0 <= corner_radius <= 32:
        raise ThemeError(f"corner_radius out of range: {corner_radius!r}")
    font_family = _check_string(data.get("font_family", "monospace"), "font_family")

    surfaces = data.get("surfaces", list(SURFACES))
    if not isinstance(surfaces, (list, tuple)) or not surfaces:
        raise ThemeError("surfaces must be a non-empty list")
    bad = [s for s in surfaces if s not in SURFACES]
    if bad:
        raise ThemeError(f"unknown surfaces: {bad}")

    return Theme(
        name=name,
        ui=ui,
        syntax=syntax,
        font_scale=float(font_scale),
        corner_radius=corner_radius,
        font_family=font_family,
        surfaces=tuple(surfaces),
    )


def _builtin_void() -> dict:
    ui = {
        "background": "#0d1117",
        "surface": "#161b22",
        "text": "#e6edf3",
        "muted": "#7d8590",
        "accent": "#2f81f7",
        "accent2": "#a371f7",
        "selection": "#264f78",
        "cursor": "#e6edf3",
        "line_highlight": "#161b22",
    }
    syntax = {
        "keyword": "#ff7b72",
        "string": "#a5d6ff",
        "comment": "#7d8590",
        "number": "#79c0ff",
        "builtin": "#d2a8ff",
        "decorator": "#ffa657",
        "function": "#d2a8ff",
        "tag": "#7ee787",
        "attr": "#79c0ff",
        "variable": "#ffa657",
        "heading": "#ff7b72",
        "bold": "#e6edf3",
        "italic": "#e6edf3",
        "code": "#a5d6ff",
        "link": "#2f81f7",
    }
    return {"name": "void", "ui": ui, "syntax": syntax, "font_family": "monospace"}


def _builtin_paper() -> dict:
    ui = {
        "background": "#ffffff",
        "surface": "#f6f8fa",
        "text": "#1f2328",
        "muted": "#59636e",
        "accent": "#0969da",
        "accent2": "#8250df",
        "selection": "#b6e3ff",
        "cursor": "#1f2328",
        "line_highlight": "#f6f8fa",
    }
    syntax = {
        "keyword": "#cf222e",
        "string": "#0a3069",
        "comment": "#59636e",
        "number": "#0550ae",
        "builtin": "#8250df",
        "decorator": "#953800",
        "function": "#8250df",
        "tag": "#116329",
        "attr": "#0550ae",
        "variable": "#953800",
        "heading": "#cf222e",
        "bold": "#1f2328",
        "italic": "#1f2328",
        "code": "#0a3069",
        "link": "#0969da",
    }
    return {"name": "paper", "ui": ui, "syntax": syntax, "font_family": "monospace"}


def _builtin_dusk() -> dict:
    ui = {
        "background": "#1a1033",
        "surface": "#241a4d",
        "text": "#f5efff",
        "muted": "#9d8fd1",
        "accent": "#c678dd",
        "accent2": "#56b6c2",
        "selection": "#4b3a8f",
        "cursor": "#f5efff",
        "line_highlight": "#241a4d",
    }
    syntax = {
        "keyword": "#c678dd",
        "string": "#98c379",
        "comment": "#9d8fd1",
        "number": "#d19a66",
        "builtin": "#56b6c2",
        "decorator": "#e5c07b",
        "function": "#61afef",
        "tag": "#e06c75",
        "attr": "#d19a66",
        "variable": "#e5c07b",
        "heading": "#c678dd",
        "bold": "#f5efff",
        "italic": "#f5efff",
        "code": "#98c379",
        "link": "#61afef",
    }
    return {"name": "dusk", "ui": ui, "syntax": syntax, "font_family": "monospace"}


def _builtin_gbccard() -> dict:
    """The Hicomb Studio card theme: angular GBC geometry, card framing.

    Data lives in levi.hicomb.card (the visual canon); this is only the
    registration hook. Lazy import keeps themes importable standalone.
    """
    from levi.hicomb.card import gbc_card_theme_data

    return gbc_card_theme_data()


_BUILTINS = {
    "void": _builtin_void,
    "paper": _builtin_paper,
    "dusk": _builtin_dusk,
    "gbc-card": _builtin_gbccard,
}


def list_themes() -> list[str]:
    return sorted(_BUILTINS)


def get_theme(name: str) -> Theme:
    maker = _BUILTINS.get(name)
    if maker is None:
        raise ThemeError(f"unknown theme: {name!r} (have: {list_themes()})")
    return validate_theme(maker())


def customize(base: str | Theme, name: str, overrides: dict) -> Theme:
    """Myspace instinct, structured: remix any surface off a base theme.

    overrides may touch ui.*, syntax.*, font_scale, corner_radius,
    font_family, surfaces. Everything re-validates — an override that
    smuggles markup dies here, not on the phone.
    """
    theme = base if isinstance(base, Theme) else get_theme(base)
    data = {
        "name": name,
        "ui": dict(theme.ui),
        "syntax": dict(theme.syntax),
        "font_scale": theme.font_scale,
        "corner_radius": theme.corner_radius,
        "font_family": theme.font_family,
        "surfaces": list(theme.surfaces),
    }
    if not isinstance(overrides, dict):
        raise ThemeError("overrides must be a mapping")
    for key, value in overrides.items():
        if key in ("ui", "syntax"):
            if not isinstance(value, dict):
                raise ThemeError(f"override {key} must be a mapping")
            data[key].update(value)
        elif key in ("font_scale", "corner_radius", "font_family", "surfaces"):
            data[key] = value
        else:
            raise ThemeError(f"unknown override section: {key!r}")
    return validate_theme(data)


def export_theme(theme: Theme) -> str:
    """Portable JSON — sibling workstreams read the same shape."""
    return theme.to_json()


def theme_from_json(raw: str) -> Theme:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ThemeError(f"theme is not valid JSON: {exc}") from exc
    return validate_theme(data)

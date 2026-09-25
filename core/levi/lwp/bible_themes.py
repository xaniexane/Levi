"""Structured themes for L.W.P. reading/writing surfaces.

Myspace doctrine, applied throughout: every reading/writing surface gets
structured theming — on the manuscript page, on the bible page, on every
surface that follows. Themes are SAFE data (named palettes, layout knobs),
never raw HTML/JS injection — a writer can theme everything and can never
script anything. Opt-in: the writer picks a theme; the default is honest
about what it does. Local, offline, stdlib-only.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Themes as plain data — inspectable, shareable, never executable
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Theme:
    """One structured theme. All values are literal data."""

    name: str
    surface: str  # "reading" | "writing" | "all"
    background: str  # hex
    foreground: str  # hex
    accent: str  # hex
    font_scale: float = 1.0  # 0.8 - 1.6, user-chosen
    line_height: float = 1.5  # 1.0 - 2.5, user-chosen
    measure: int = 72  # max line width in characters
    density: str = "roomy"  # roomy | snug | dense (ternary, not cramped/comfy)


DENSITY_BLANK_LINES = {"roomy": 2, "snug": 1, "dense": 0}

PRESETS: Dict[str, Theme] = {
    "void": Theme(
        name="void",
        surface="all",
        background="#0b0e14",
        foreground="#e6e6e6",
        accent="#7aa2f7",
        font_scale=1.0,
        line_height=1.5,
        measure=72,
        density="roomy",
    ),
    "paper": Theme(
        name="paper",
        surface="reading",
        background="#faf6ef",
        foreground="#1a1a1a",
        accent="#8a5a2b",
        font_scale=1.0,
        line_height=1.6,
        measure=76,
        density="roomy",
    ),
    "sepia": Theme(
        name="sepia",
        surface="reading",
        background="#f4ecd8",
        foreground="#3b2f23",
        accent="#a0522d",
        font_scale=1.05,
        line_height=1.6,
        measure=72,
        density="roomy",
    ),
    "high_contrast": Theme(
        name="high_contrast",
        surface="all",
        background="#000000",
        foreground="#ffffff",
        accent="#ffff00",
        font_scale=1.15,
        line_height=1.7,
        measure=68,
        density="snug",
    ),
    "noir_desk": Theme(
        name="noir_desk",
        surface="writing",
        background="#101010",
        foreground="#d8d3c3",
        accent="#c9a227",
        font_scale=1.0,
        line_height=1.5,
        measure=70,
        density="snug",
    ),
    "romcom_desk": Theme(
        name="romcom_desk",
        surface="writing",
        background="#fff5f7",
        foreground="#4a2c35",
        accent="#e0608a",
        font_scale=1.0,
        line_height=1.6,
        measure=74,
        density="roomy",
    ),
}


def list_themes() -> List[str]:
    return sorted(PRESETS)


def get_theme(name: str) -> Theme:
    try:
        return PRESETS[name]
    except KeyError:
        raise KeyError(f"unknown theme {name!r}; known: {list_themes()}") from None


def custom_theme(base: str = "void", **overrides) -> Theme:
    """A writer's own theme, built from a preset — still plain data."""
    parent = get_theme(base)
    data = {f: getattr(parent, f) for f in parent.__dataclass_fields__}
    data.update({k: v for k, v in overrides.items() if k in data})
    return Theme(**data)


# ---------------------------------------------------------------------------
# Rendering: plain text laid out per the theme (mobile-safe by construction)
# ---------------------------------------------------------------------------


def render_text(text: str, theme: Theme | str) -> str:
    """Wrap and space plain text per the theme's measure/density.

    Returns plain text only — no markup, no scripts. A surface renders this
    with the theme's palette applied as styles, never by injecting content.
    """
    theme = get_theme(theme) if isinstance(theme, str) else theme
    blank = "\n" * DENSITY_BLANK_LINES[theme.density]
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    rendered = [textwrap.fill(p, width=theme.measure) for p in paragraphs]
    return ("\n" + blank + "\n").join(rendered)


def render_bible(bible, theme: Theme | str, only: Optional[str] = None) -> str:
    """Themed rendering of a LivingBible's confirmed canon for the reader.

    ``only``: "characters" | "relations" | "world_rules" | "timeline" | None.
    Confirmed entries render as canon; proposals render flagged as awaiting
    the writer — the press never presents a proposal as decided fact.
    """
    theme = get_theme(theme) if isinstance(theme, str) else theme
    kinds = ["characters", "relations", "world_rules", "timeline"]
    if only:
        if only not in kinds:
            raise ValueError(f"unknown section {only!r}")
        kinds = [only]
    blocks: List[str] = []
    for kind in kinds:
        table = getattr(bible, kind)
        lines = [f"== {kind.replace('_', ' ').upper()} =="]
        for entry in sorted(table.values(), key=lambda e: getattr(e, "order", e.id)):
            tag = {
                "proposed": "[proposed — awaiting you]",
                "confirmed": "[canon]",
                "rejected": "[rejected]",
            }.get(entry.status, "")
            if kind == "characters":
                lines.append(f"{entry.name} {tag}")
            elif kind == "relations":
                a = bible.characters.get(entry.source)
                b = bible.characters.get(entry.target)
                an = a.name if a else entry.source
                bn = b.name if b else entry.target
                lines.append(f"{an} —{entry.relation}→ {bn} {tag}")
            elif kind == "world_rules":
                lines.append(f"{entry.rule} {tag}")
            else:
                lines.append(f"[{entry.order}] {entry.summary} {tag}")
        blocks.append("\n".join(lines))
    return render_text("\n\n".join(blocks), theme)

"""Hicomb Studio's visual canon: the NFT card frame fused with Game Boy
Color geometry.

Visual grammar, read off Chauncey's originals (originals-first):
- The Legion card (media-generation-levi-legion-card-prototype): beveled
  corner armor on every panel, a nameplate title bar with corner cuts,
  stat zones along the bottom, matte numbering "CARD Nº LL-001 / 01/100".
- The matte card back ("042/1000"): near-black void, etched geometry,
  restrained numbering — the base surface of the studio.
- The NFT² chase card: holographic gradient reserved for the AI presence
  only — the one shiny thing in a matte world.
- Game Boy Color: angular geometry (border-radius 0 everywhere), a tight
  curated palette, chunky 2px frames, pixel-scale corner notches.

LAWS (machine-checked in tests/test_hicomb_studio.py):
  I5 GBC-GEOMETRY  the gbc-card theme has corner_radius == 0.
  I6 GBC-PALETTE   every color in the gbc-card theme is a member of
                   GBC_PALETTE (the curated set below).
"""

from __future__ import annotations

# Curated Game-Boy-Color-feel palette: void blacks, electric cyans from
# the Legion card's lightning, the matte grays of the card back, GBC-era
# brights, and the holo chase gradient stops (AI-only accents).
GBC_PALETTE = frozenset(
    {
        # void / matte card-back blacks
        "#05070c", "#0b0e14", "#11141c", "#161a24",
        # etched frame grays
        "#232936", "#2e3648", "#3d465e", "#49536b",
        # electric cyan (legion lightning)
        "#00e5ff", "#35f0ff", "#7df9ff", "#0aa6c2",
        # GBC brights
        "#f8b800", "#e83838", "#3868e8", "#38e86c",
        "#b838e8", "#e87838", "#f8f8f8", "#8890a8",
        # holo chase stops (AI presence only)
        "#ff5fd2", "#8a5fff", "#5fffd2", "#ffe95f",
        # text
        "#e8f6ff", "#9fb3cc", "#5c6b84",
    }
)

# Card-frame tokens consumed by the studio HTML + theme.
CARD_TOKENS = {
    "corner_cut_px": 10,  # beveled corner armor, like the Legion card
    "border_radius": 0,  # angular: no rounded edges, ever
    "frame_width_px": 2,  # chunky GBC frames
    "nameplate": "HICOMB STUDIO",
    "edition_stamp": "CARD Nº HC-042/1000",
    "series_line": "HICOMB SERIES • GENESIS-2026",
    "ai_holo": True,  # holo gradient reserved for the AI panel
}


def gbc_card_theme_data() -> dict:
    """Theme data dict for themes.validate_theme(). All colors in palette.

    The I5/I6 palette laws are enforced with explicit raises, not assert:
    asserts vanish under ``python -O`` and laws must hold regardless.
    """
    ui = {
        "background": "#05070c",
        "surface": "#0b0e14",
        "text": "#e8f6ff",
        "muted": "#5c6b84",
        "accent": "#00e5ff",
        "accent2": "#8a5fff",
        "selection": "#232936",
        "cursor": "#35f0ff",
        "line_highlight": "#11141c",
    }
    syntax = {
        "keyword": "#ff5fd2",
        "string": "#38e86c",
        "comment": "#5c6b84",
        "number": "#f8b800",
        "builtin": "#35f0ff",
        "decorator": "#e87838",
        "function": "#00e5ff",
        "tag": "#e83838",
        "attr": "#7df9ff",
        "variable": "#9fb3cc",
        "heading": "#ff5fd2",
        "bold": "#e8f6ff",
        "italic": "#9fb3cc",
        "code": "#5fffd2",
        "link": "#3868e8",
    }
    bad_ui = sorted({c for c in ui.values() if c not in GBC_PALETTE})
    if bad_ui:
        raise ValueError(f"ui colors outside GBC palette (I6): {bad_ui}")
    bad_syntax = sorted({c for c in syntax.values() if c not in GBC_PALETTE})
    if bad_syntax:
        raise ValueError(f"syntax colors outside GBC palette (I6): {bad_syntax}")
    return {
        "name": "gbc-card",
        "ui": ui,
        "syntax": syntax,
        "font_scale": 1.0,
        "corner_radius": 0,  # I5: angular
        "font_family": "monospace",
        "surfaces": [
            "buffer", "gutter", "command_bar", "tab_strip",
            "snippet_row", "file_tree", "status",
        ],
    }


def get_gbc_theme():
    """Validated immutable Theme (lazy import: themes.py imports this module)."""
    from levi.hicomb.themes import validate_theme

    return validate_theme(gbc_card_theme_data())

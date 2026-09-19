"""Radical user ownership of the interface: full visual re-skins.

Studied from: desktop-casualties-20260916/report.md [2. Winamp]

The studied shape: thousands of user-made full visual re-skins as
the product surface itself — the interface is not sacred chrome,
it's a canvas the community paints over completely, and the product
ships that as a first-class feature.

LEVI-native re-expression: a skin registry of theme descriptors —
named color roles, glyph sets, border styles, and layout densities —
with validation (every required role present, colors well-formed),
an apply mechanism against a preview scene, and a text-mode preview
renderer that shows what a skin *does* to a panel. Skins are data,
plain and inspectable.

Honest limits: this is a *descriptor* system, not a real GUI skin
engine — previews are text-mode mockups, color values are stored
as hex strings and never rendered to pixels, and there is no image
loading. The mechanism being preserved is community ownership of
the visual surface, expressed as data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

ORIGIN = "levi-revival/skins"

#: Roles every skin must define for a coherent surface.
REQUIRED_ROLES = ("background", "foreground", "accent", "border", "highlight")
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


class SkinError(Exception):
    """Raised for invalid skins, unknown names, or preview misuse."""


@dataclass
class Skin:
    """A user-made visual re-skin, as data."""

    name: str
    author: str
    colors: Dict[str, str]  # role -> "#rrggbb"
    glyphs: Dict[str, str] = field(default_factory=dict)  # e.g. {"play": ">"}
    border_style: str = "single"  # single | double | rounded | none
    density: str = "comfortable"  # compact | comfortable | spacious

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise SkinError("skin name may not be blank")
        missing = [r for r in REQUIRED_ROLES if r not in self.colors]
        if missing:
            raise SkinError(f"skin {self.name!r} missing roles: {missing}")
        for role, value in self.colors.items():
            if not _HEX_COLOR.match(value or ""):
                raise SkinError(f"bad color for {role}: {value!r} (want #rrggbb)")
        if self.border_style not in ("single", "double", "rounded", "none"):
            raise SkinError(f"unknown border style: {self.border_style!r}")
        if self.density not in ("compact", "comfortable", "spacious"):
            raise SkinError(f"unknown density: {self.density!r}")

    def contrast_note(self) -> str:
        """A heuristic luminance check: flag identical bg/fg pairs.

        This is a plain arithmetic heuristic over hex values, labeled
        as such — it is not a certified accessibility audit.
        """

        def lum(hexv: str) -> float:
            r, g, b = (int(hexv[i : i + 2], 16) for i in (1, 3, 5))
            return 0.299 * r + 0.587 * g + 0.114 * b

        bg, fg = self.colors["background"], self.colors["foreground"]
        if abs(lum(bg) - lum(fg)) < 40:
            return f"warning: {self.name!r} has low bg/fg separation (heuristic)"
        return f"{self.name!r}: bg/fg separation looks reasonable (heuristic)"


_BORDER_CHARS = {
    "single": ("┌", "┐", "└", "┘", "─", "│"),
    "double": ("╔", "╗", "╚", "╝", "═", "║"),
    "rounded": ("╭", "╮", "╰", "╯", "─", "│"),
    "none": (" ", " ", " ", " ", " ", " "),
}


class SkinRegistry:
    """The community gallery: install, inspect, apply, preview."""

    def __init__(self) -> None:
        self._skins: Dict[str, Skin] = {}
        self._active: Optional[str] = None

    def install(self, skin: Skin) -> None:
        key = skin.name.lower()
        if key in self._skins:
            raise SkinError(f"skin already installed: {skin.name!r}")
        self._skins[key] = skin

    def get(self, name: str) -> Skin:
        try:
            return self._skins[name.lower()]
        except KeyError:
            raise SkinError(f"no such skin: {name!r}") from None

    def list(self) -> List[str]:
        return sorted(s.name for s in self._skins.values())

    def by_author(self, author: str) -> List[str]:
        return sorted(s.name for s in self._skins.values() if s.author == author)

    def apply(self, name: str) -> Skin:
        """Make a skin the active one; returns it for rendering."""
        skin = self.get(name)
        self._active = skin.name.lower()
        return skin

    def active(self) -> Optional[Skin]:
        if self._active is None:
            return None
        return self._skins[self._active]

    def preview(self, name: str) -> str:
        """Text-mode mockup of a panel wearing the skin.

        Shows the roles, glyphs, and borders at work — a readable
        approximation, not pixels.
        """
        skin = self.get(name)
        tl, tr, bl, br, h, v = _BORDER_CHARS[skin.border_style]
        play = skin.glyphs.get("play", ">")
        stop = skin.glyphs.get("stop", "■")
        inner_w = 30
        top = tl + h * inner_w + tr
        mid1 = f"{v} now playing: {play} synth-wave mix{' ' * 2}{v}"
        mid2 = f"{v} bg {skin.colors['background']} fg {skin.colors['foreground']} {v}"
        mid3 = f"{v} accent {skin.colors['accent']} [{stop} stop]      {v}"
        bottom = bl + h * inner_w + br
        lines = [
            f"skin: {skin.name} by {skin.author} ({skin.density})",
            top,
            mid1[: inner_w + 2],
            mid2[: inner_w + 2],
            mid3[: inner_w + 2],
            bottom,
            skin.contrast_note(),
        ]
        return "\n".join(lines)

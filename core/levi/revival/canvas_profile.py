"""A profile as a user-themed creative canvas, not a fixed form.

Studied from: victims-of-giants-20260916-0017/report.md (Resurrection shortlist #8)

The mechanism: a profile is a blank canvas the owner decorates. They pick
a *skin* (named set of visual tokens — palette, texture, density) and
arrange *widgets* (named panels of content) in their own order. Nothing
about the layout is fixed by the platform; the platform only supplies
the vocabulary of skins and widget types, and keeps the arrangement
honest (one widget per slot, no orphan references).

Skins here are declarative data only — this module does not render HTML
or CSS. It guarantees the *configuration* is valid and portable, so any
renderer can consume it.

stdlib-only. No network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


ORIGIN = "levi-revival/canvas-profile"


# A small built-in vocabulary of skins and widget types. Users may add
# their own skins at runtime; the built-ins are just starting points.
BUILTIN_SKINS = {
    "void": {"palette": "dark-neon", "texture": "grid", "density": "airy"},
    "paper": {"palette": "ink-on-cream", "texture": "ruled", "density": "dense"},
    "ember": {"palette": "ember-red", "texture": "grain", "density": "cozy"},
}

BUILTIN_WIDGET_TYPES = {
    "about",
    "now",
    "shelf",  # things the owner recommends
    "guestbook",  # visitor messages
    "signal",  # a feed of short posts
    "shrine",  # a curated single-topic panel
}


@dataclass
class Widget:
    """One panel on the canvas."""

    widget_id: str
    widget_type: str
    title: str
    body: str = ""


@dataclass
class CanvasProfile:
    """A user-owned, themed profile canvas."""

    owner: str
    skins: Dict[str, Dict[str, str]] = field(default_factory=dict)
    active_skin: str = "void"
    widgets: List[Widget] = field(default_factory=list)
    custom_tokens: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, tokens in BUILTIN_SKINS.items():
            self.skins.setdefault(name, dict(tokens))
        if self.active_skin not in self.skins:
            self.active_skin = "void"

    # -- skins ---------------------------------------------------------
    def add_skin(self, name: str, tokens: Dict[str, str]) -> None:
        name = (name or "").strip().lower()
        if not name:
            raise ValueError("skin name must be non-empty")
        if not isinstance(tokens, dict) or not tokens:
            raise ValueError("skin tokens must be a non-empty mapping")
        if name in self.skins:
            raise ValueError(f"skin already exists: {name!r}")
        self.skins[name] = dict(tokens)

    def apply_skin(self, name: str) -> None:
        if name not in self.skins:
            raise KeyError(f"unknown skin: {name!r}")
        self.active_skin = name

    def tweak_token(self, key: str, value: str) -> None:
        """Override one token of the active skin without forking it."""
        if not key:
            raise ValueError("token key must be non-empty")
        self.custom_tokens[key] = value

    def effective_skin(self) -> Dict[str, str]:
        """Active skin tokens with the owner's tweaks layered on top."""
        merged = dict(self.skins[self.active_skin])
        merged.update(self.custom_tokens)
        return merged

    # -- widgets -------------------------------------------------------
    def add_widget(
        self, widget_id: str, widget_type: str, title: str, body: str = ""
    ) -> Widget:
        widget_id = (widget_id or "").strip()
        if not widget_id:
            raise ValueError("widget_id must be non-empty")
        if any(w.widget_id == widget_id for w in self.widgets):
            raise ValueError(f"duplicate widget_id: {widget_id!r}")
        if widget_type not in BUILTIN_WIDGET_TYPES:
            raise ValueError(f"unknown widget type: {widget_type!r}")
        widget = Widget(
            widget_id=widget_id, widget_type=widget_type, title=title, body=body
        )
        self.widgets.append(widget)
        return widget

    def remove_widget(self, widget_id: str) -> Widget:
        for i, w in enumerate(self.widgets):
            if w.widget_id == widget_id:
                return self.widgets.pop(i)
        raise KeyError(f"unknown widget: {widget_id!r}")

    def move_widget(self, widget_id: str, new_index: int) -> None:
        """Reorder the canvas: move a widget to an explicit position."""
        for i, w in enumerate(self.widgets):
            if w.widget_id == widget_id:
                widget = self.widgets.pop(i)
                break
        else:
            raise KeyError(f"unknown widget: {widget_id!r}")
        new_index = max(0, min(new_index, len(self.widgets)))
        self.widgets.insert(new_index, widget)

    # -- portability ---------------------------------------------------
    def to_dict(self) -> Dict:
        return {
            "owner": self.owner,
            "active_skin": self.active_skin,
            "skins": {k: dict(v) for k, v in self.skins.items()},
            "custom_tokens": dict(self.custom_tokens),
            "widgets": [
                {
                    "widget_id": w.widget_id,
                    "type": w.widget_type,
                    "title": w.title,
                    "body": w.body,
                }
                for w in self.widgets
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CanvasProfile":
        profile = cls(owner=data["owner"])
        profile.skins = {k: dict(v) for k, v in data.get("skins", {}).items()}
        if data.get("active_skin") in profile.skins:
            profile.active_skin = data["active_skin"]
        profile.custom_tokens = dict(data.get("custom_tokens", {}))
        profile.widgets = [
            Widget(
                widget_id=w["widget_id"],
                widget_type=w["type"],
                title=w["title"],
                body=w.get("body", ""),
            )
            for w in data.get("widgets", [])
        ]
        return profile


def blank_canvas(owner: str) -> CanvasProfile:
    """Create a fresh, undecorated canvas for an owner."""
    if not owner or not owner.strip():
        raise ValueError("owner must be non-empty")
    return CanvasProfile(owner=owner.strip())


def describe(profile: CanvasProfile) -> str:
    """One-line human summary of a canvas."""
    skin = profile.effective_skin()
    return (
        f"{profile.owner}'s canvas — skin {profile.active_skin!r} "
        f"({skin.get('palette', '?')}), {len(profile.widgets)} widget(s): "
        + ", ".join(f"{w.title} [{w.widget_type}]" for w in profile.widgets)
    )

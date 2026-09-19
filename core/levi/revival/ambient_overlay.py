"""ambient_overlay — a summon-anywhere scratch layer over whatever you run.

Studied from: revival-50-more-20260916-0009/report-part1.md [entry #16].

The studied shape: a hotkey-summoned overlay that appears above any
running application, taking the current screen and selection as implicit
context — a personal information layer that never asks you to switch
apps. LEVI's version:

* **Summon/suspend.** ``Overlay.summon(context)`` opens a session; the
  previous one suspends onto a stack instead of being destroyed, so a
  second hotkey press nests instead of clobbering. ``dismiss()`` pops
  back to whatever was underneath.
* **Implicit context.** ``ScreenContext`` carries what the overlay was
  summoned over: application name, window title, selected text, and a
  free-form note. Panels read this without the user retyping it.
* **Panels.** Small tools register under names (``scratch``,
  ``clip2note``, ``glance`` ship built-in); each panel is a plain
  function ``(session, args) -> str`` so new ones are one decorator.
* **Persistence.** Sessions serialize to plain dicts/JSON — the overlay
  survives a restart with its notes intact.

Honest limits: there is no real hotkey hook or screen scraping here —
``summon`` takes the context as an argument (a host would fill it in
from the OS). This module owns the session stack, context plumbing,
panels, and persistence.

This is an original, from-scratch implementation for LEVI. Not
artificial. Synthetic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

ORIGIN = "levi-revival/ambient_overlay"

PanelFn = Callable[["Session", Dict[str, Any]], str]


# ---------------------------------------------------------------------------
# Implicit context: what the overlay was summoned over
# ---------------------------------------------------------------------------


@dataclass
class ScreenContext:
    """The implicit context captured at summon time."""

    app: str = ""
    window: str = ""
    selection: str = ""
    note: str = ""

    def summary(self) -> str:
        bits = [f"app={self.app!r}"] if self.app else []
        if self.window:
            bits.append(f"window={self.window!r}")
        sel = self.selection
        if sel:
            bits.append(f"selection={sel[:60]!r}{'…' if len(sel) > 60 else ''}")
        return " ".join(bits) or "(no context)"


# ---------------------------------------------------------------------------
# Panels
# ---------------------------------------------------------------------------


@dataclass
class Session:
    """One overlay invocation: context + per-session scratch space."""

    context: ScreenContext
    notes: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)

    def jot(self, text: str) -> None:
        self.notes.append(text)


PANELS: Dict[str, PanelFn] = {}


def panel(name: str) -> Callable[[PanelFn], PanelFn]:
    """Register a panel under ``name``."""

    def deco(fn: PanelFn) -> PanelFn:
        PANELS[name] = fn
        return fn

    return deco


@panel("scratch")
def _p_scratch(session: Session, args: Dict[str, Any]) -> str:
    if "jot" in args:
        session.jot(args["jot"])
        return f"jotted ({len(session.notes)} notes)"
    return "\n".join(f"- {n}" for n in session.notes) or "(scratch is empty)"


@panel("clip2note")
def _p_clip2note(session: Session, args: Dict[str, Any]) -> str:
    """Turn the current selection into a note, with the app as provenance."""
    sel = session.context.selection.strip()
    if not sel:
        return "nothing selected"
    session.jot(f"[{session.context.app}] {sel}")
    return f"clipped {len(sel)} chars"


@panel("glance")
def _p_glance(session: Session, args: Dict[str, Any]) -> str:
    return f"context: {session.context.summary()} | notes: {len(session.notes)}"


# ---------------------------------------------------------------------------
# The overlay: summon stack + dispatch
# ---------------------------------------------------------------------------


class Overlay:
    """Hotkey-summoned session stack."""

    def __init__(self) -> None:
        self.stack: List[Session] = []
        self.dismissed_count = 0

    @property
    def current(self) -> Optional[Session]:
        return self.stack[-1] if self.stack else None

    def summon(self, context: Optional[ScreenContext] = None) -> Session:
        """Open a new session; the old one suspends underneath."""
        session = Session(context or ScreenContext())
        self.stack.append(session)
        return session

    def dismiss(self) -> Optional[Session]:
        """Close the top session, revealing the suspended one beneath."""
        if not self.stack:
            return None
        self.dismissed_count += 1
        return self.stack.pop()

    def run_panel(self, name: str, args: Optional[Dict[str, Any]] = None) -> str:
        """Run a panel against the current session."""
        session = self.current
        if session is None:
            raise RuntimeError("no session summoned")
        try:
            fn = PANELS[name]
        except KeyError:
            raise KeyError(f"no panel {name!r} (have: {sorted(PANELS)})") from None
        return fn(session, args or {})

    def depth(self) -> int:
        return len(self.stack)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def serialize(session: Session) -> Dict[str, Any]:
    return {
        "context": {
            "app": session.context.app,
            "window": session.context.window,
            "selection": session.context.selection,
            "note": session.context.note,
        },
        "notes": list(session.notes),
        "data": dict(session.data),
    }


def deserialize(blob: Dict[str, Any]) -> Session:
    ctx = blob.get("context", {})
    return Session(
        context=ScreenContext(
            app=ctx.get("app", ""),
            window=ctx.get("window", ""),
            selection=ctx.get("selection", ""),
            note=ctx.get("note", ""),
        ),
        notes=list(blob.get("notes", [])),
        data=dict(blob.get("data", {})),
    )


def dump_json(session: Session) -> str:
    return json.dumps(serialize(session), indent=2, sort_keys=True)


def load_json(text: str) -> Session:
    return deserialize(json.loads(text))

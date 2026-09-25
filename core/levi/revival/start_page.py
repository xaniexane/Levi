"""The composable start page: a user-owned command deck.

Studied from: victims-of-giants-20260916-0017 report.md
[Resurrection shortlist #20]

The studied shape: the iGoogle-style tabbed dashboard — the daily
entry point is a page the *user* composes from arbitrary widgets on
tabs they name, not a feed someone else assembles. The start page is a
command deck, not a consumption surface.

LEVI-native re-expression: a page of named tabs; each tab holds a grid
of widget instances. Widgets come from a small built-in registry
(clock, todo list, link shelf, note, quote) plus any caller-registered
type. The owner adds, removes, moves, and renames; layout is a simple
(grid row, column) placement with collision handling. The whole page
serializes to plain JSON for export and re-imports losslessly.

Honest limits: widgets are local and static — a clock shows the time
it was rendered, a todo list is a local list. No live data, no
network, no background refresh. The grid is coarse (positions are
integers), not a free-form canvas.
"""

from __future__ import annotations

import copy
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


ORIGIN = "levi-revival/start-page"


def _clock_render(config: Dict[str, Any]) -> str:
    return time.strftime(config.get("format", "%H:%M %Z"))


def _todo_render(config: Dict[str, Any]) -> str:
    items = config.get("items", [])
    done = sum(1 for i in items if i.get("done"))
    return f"{done}/{len(items)} done"


def _links_render(config: Dict[str, Any]) -> str:
    return (
        ", ".join(
            link.get("label", link.get("url", "?")) for link in config.get("links", [])
        )
        or "(no links)"
    )


def _note_render(config: Dict[str, Any]) -> str:
    text = config.get("text", "")
    return text if len(text) <= 120 else text[:117] + "..."


def _quote_render(config: Dict[str, Any]) -> str:
    quotes = config.get("quotes", [])
    if not quotes:
        return "(no quotes loaded)"
    return quotes[int(time.time() // 86400) % len(quotes)]


# Built-in widget types: name -> (default config factory, renderer)
_BUILTINS: Dict[str, tuple] = {
    "clock": (lambda: {"format": "%H:%M %Z"}, _clock_render),
    "todo": (lambda: {"items": []}, _todo_render),
    "links": (lambda: {"links": []}, _links_render),
    "note": (lambda: {"text": ""}, _note_render),
    "quote": (lambda: {"quotes": []}, _quote_render),
}


@dataclass
class WidgetInstance:
    id: str
    type: str
    title: str
    row: int
    col: int
    config: Dict[str, Any] = field(default_factory=dict)

    def render(self) -> str:
        if self.type in _BUILTINS:
            return _BUILTINS[self.type][1](self.config)
        return f"<{self.type}>"


class StartPageError(ValueError):
    pass


class StartPage:
    """A user-composed tabbed dashboard of arbitrary widgets."""

    def __init__(self, owner: str) -> None:
        self.owner = owner
        self.tabs: Dict[str, List[WidgetInstance]] = {"Home": []}
        self.active_tab = "Home"
        self._next_id = 1
        self._custom_types: Dict[str, Callable[[Dict[str, Any]], str]] = {}

    # --- tabs -----------------------------------------------------------
    def add_tab(self, name: str) -> None:
        if not name.strip():
            raise StartPageError("tab name cannot be empty")
        if name in self.tabs:
            raise StartPageError(f"tab {name!r} already exists")
        self.tabs[name] = []

    def rename_tab(self, old: str, new: str) -> None:
        if old not in self.tabs:
            raise StartPageError(f"no tab {old!r}")
        if new in self.tabs:
            raise StartPageError(f"tab {new!r} already exists")
        self.tabs[new] = self.tabs.pop(old)
        if self.active_tab == old:
            self.active_tab = new

    def remove_tab(self, name: str) -> None:
        if name not in self.tabs:
            raise StartPageError(f"no tab {name!r}")
        if len(self.tabs) == 1:
            raise StartPageError("cannot remove the last tab")
        del self.tabs[name]
        if self.active_tab == name:
            self.active_tab = next(iter(self.tabs))

    def switch(self, name: str) -> None:
        if name not in self.tabs:
            raise StartPageError(f"no tab {name!r}")
        self.active_tab = name

    # --- widget types ---------------------------------------------------
    def register_type(
        self, name: str, renderer: Callable[[Dict[str, Any]], str]
    ) -> None:
        """Register a caller-provided widget type (renderer is a function)."""
        if name in _BUILTINS:
            raise StartPageError(f"{name!r} is a built-in type")
        self._custom_types[name] = renderer

    def widget_types(self) -> List[str]:
        return sorted(list(_BUILTINS) + list(self._custom_types))

    # --- widgets --------------------------------------------------------
    def add_widget(
        self,
        wtype: str,
        title: str = "",
        tab: Optional[str] = None,
        row: int = 0,
        col: int = 0,
        config: Optional[Dict[str, Any]] = None,
    ) -> WidgetInstance:
        tab = tab or self.active_tab
        if tab not in self.tabs:
            raise StartPageError(f"no tab {tab!r}")
        if wtype not in _BUILTINS and wtype not in self._custom_types:
            raise StartPageError(f"unknown widget type {wtype!r}")
        default = copy.deepcopy(_BUILTINS[wtype][0]()) if wtype in _BUILTINS else {}
        merged = {**default, **(config or {})}
        wid = f"w{self._next_id}"
        self._next_id += 1
        inst = WidgetInstance(
            id=wid,
            type=wtype,
            title=title or wtype.title(),
            row=row,
            col=col,
            config=merged,
        )
        # collision: shift down until the (row, col) cell is free
        taken = {(w.row, w.col) for w in self.tabs[tab]}
        while (inst.row, inst.col) in taken:
            inst.row += 1
        self.tabs[tab].append(inst)
        return inst

    def remove_widget(self, wid: str, tab: Optional[str] = None) -> bool:
        tab = tab or self.active_tab
        widgets = self.tabs.get(tab, [])
        for i, w in enumerate(widgets):
            if w.id == wid:
                del widgets[i]
                return True
        return False

    def move_widget(
        self, wid: str, row: int, col: int, tab: Optional[str] = None
    ) -> WidgetInstance:
        tab = tab or self.active_tab
        inst = self.find(wid, tab)
        if inst is None:
            raise StartPageError(f"no widget {wid!r} on tab {tab!r}")
        inst.row, inst.col = max(0, row), max(0, col)
        return inst

    def find(self, wid: str, tab: Optional[str] = None) -> Optional[WidgetInstance]:
        tab = tab or self.active_tab
        for w in self.tabs.get(tab, []):
            if w.id == wid:
                return w
        return None

    def configure(
        self, wid: str, tab: Optional[str] = None, **updates: Any
    ) -> WidgetInstance:
        inst = self.find(wid, tab)
        if inst is None:
            raise StartPageError(f"no widget {wid!r}")
        inst.config.update(updates)
        return inst

    def deck(self, tab: Optional[str] = None) -> List[WidgetInstance]:
        """The tab's widgets in reading order (row, then column)."""
        tab = tab or self.active_tab
        return sorted(self.tabs.get(tab, []), key=lambda w: (w.row, w.col))

    def render_widget(self, wid: str, tab: Optional[str] = None) -> str:
        """Render a widget, including caller-registered custom types."""
        inst = self.find(wid, tab)
        if inst is None:
            raise StartPageError(f"no widget {wid!r}")
        if inst.type in _BUILTINS:
            return _BUILTINS[inst.type][1](inst.config)
        renderer = self._custom_types.get(inst.type)
        if renderer is not None:
            return renderer(inst.config)
        return f"<{inst.type}>"

    # --- persistence ----------------------------------------------------
    def to_json(self) -> str:
        return json.dumps(
            {
                "owner": self.owner,
                "active_tab": self.active_tab,
                "tabs": {name: [vars(w) for w in ws] for name, ws in self.tabs.items()},
            },
            indent=2,
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, data: str) -> "StartPage":
        obj = json.loads(data)
        page = cls(obj["owner"])
        page.active_tab = obj.get("active_tab", "Home")
        page.tabs = {}
        for name, widgets in obj["tabs"].items():
            page.tabs[name] = [WidgetInstance(**w) for w in widgets]
        ids = [
            int(w.id[1:])
            for ws in page.tabs.values()
            for w in ws
            if w.id.startswith("w") and w.id[1:].isdigit()
        ]
        page._next_id = max(ids, default=0) + 1
        return page

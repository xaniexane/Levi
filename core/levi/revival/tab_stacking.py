"""Stacking tabs into collapsible groups in the tab bar.

Studied from: desktop-casualties-20260916/report.md [1. Opera]

Functional description: tabs live on a bar, but related tabs can be dragged
into a stack — a named group that shows as one collapsed entry and expands
in place. Stacks can be renamed, collapsed/expanded, have tabs added or
pulled out (unstacking dissolves an empty stack), and tabs can be reordered
across stacks. The bar always renders a flat, honest view of what is open.

Pure Python, stdlib only. No provider branding. Not artificial — synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/tab-stacking"


@dataclass
class Tab:
    id: int
    title: str
    target: str


@dataclass
class Stack:
    id: int
    name: str
    tab_ids: List[int] = field(default_factory=list)
    collapsed: bool = True


class TabBar:
    """A tab bar with Opera-style collapsible stacks."""

    def __init__(self) -> None:
        self._tabs: Dict[int, Tab] = {}
        self._stacks: Dict[int, Stack] = {}
        self._order: List[Tuple[str, int]] = []  # ("tab"|"stack", id)
        self._next_tab = 1
        self._next_stack = 1
        self.active_tab: Optional[int] = None

    # -- tabs -----------------------------------------------------------
    def open(self, title: str, target: str) -> Tab:
        tab = Tab(self._next_tab, title, target)
        self._next_tab += 1
        self._tabs[tab.id] = tab
        self._order.append(("tab", tab.id))
        self.active_tab = tab.id
        return tab

    def close(self, tab_id: int) -> bool:
        tab = self._tabs.pop(tab_id, None)
        if tab is None:
            return False
        self._order = [e for e in self._order if e != ("tab", tab_id)]
        for stack in self._stacks.values():
            if tab_id in stack.tab_ids:
                stack.tab_ids.remove(tab_id)
                if not stack.tab_ids:
                    self._dissolve_stack(stack.id)
        if self.active_tab == tab_id:
            # fall back to the last visible tab on the bar
            self.active_tab = None
            for kind, eid in reversed(self._order):
                if kind == "tab":
                    self.active_tab = eid
                    break
                stack = self._stacks.get(eid)
                if stack and stack.tab_ids:
                    self.active_tab = stack.tab_ids[-1]
                    break
        return True

    def activate(self, tab_id: int) -> None:
        if tab_id not in self._tabs:
            raise KeyError(f"unknown tab: {tab_id}")
        self.active_tab = tab_id

    # -- stacks ----------------------------------------------------------
    def stack(self, name: str, tab_ids: List[int]) -> Stack:
        """Group existing top-level tabs into a new stack."""
        if len(tab_ids) < 2:
            raise ValueError("a stack needs at least 2 tabs")
        for tid in tab_ids:
            if tid not in self._tabs:
                raise KeyError(f"unknown tab: {tid}")
            if ("tab", tid) not in self._order:
                raise ValueError(f"tab {tid} is already stacked")
        stack = Stack(self._next_stack, name, list(tab_ids))
        self._next_stack += 1
        self._stacks[stack.id] = stack
        first = min(self._order.index(("tab", tid)) for tid in tab_ids)
        self._order = [e for e in self._order if e[0] != "tab" or e[1] not in tab_ids]
        self._order.insert(first, ("stack", stack.id))
        return stack

    def _dissolve_stack(self, stack_id: int) -> None:
        self._stacks.pop(stack_id, None)
        self._order = [e for e in self._order if e != ("stack", stack_id)]

    def add_to_stack(self, stack_id: int, tab_id: int) -> None:
        stack = self._stacks[stack_id]
        if tab_id not in self._tabs:
            raise KeyError(f"unknown tab: {tab_id}")
        self._order = [e for e in self._order if e != ("tab", tab_id)]
        for s in self._stacks.values():
            if tab_id in s.tab_ids:
                s.tab_ids.remove(tab_id)
                if not s.tab_ids:
                    self._dissolve_stack(s.id)
        stack.tab_ids.append(tab_id)

    def unstack(self, tab_id: int) -> None:
        """Pull one tab out of its stack back onto the bar."""
        for stack in self._stacks.values():
            if tab_id in stack.tab_ids:
                stack.tab_ids.remove(tab_id)
                idx = self._order.index(("stack", stack.id))
                self._order.insert(idx + 1, ("tab", tab_id))
                if not stack.tab_ids:
                    self._dissolve_stack(stack.id)
                return
        raise ValueError(f"tab {tab_id} is not in a stack")

    def collapse(self, stack_id: int) -> None:
        self._stacks[stack_id].collapsed = True

    def expand(self, stack_id: int) -> None:
        self._stacks[stack_id].collapsed = False

    def rename_stack(self, stack_id: int, name: str) -> None:
        if not name.strip():
            raise ValueError("stack name must be non-empty")
        self._stacks[stack_id].name = name.strip()

    def move(self, entry: Tuple[str, int], position: int) -> None:
        """Reorder a top-level bar entry (tab or stack)."""
        if entry not in self._order:
            raise ValueError(f"not a top-level entry: {entry}")
        self._order.remove(entry)
        self._order.insert(max(0, min(position, len(self._order))), entry)

    # -- views -----------------------------------------------------------
    def stack_of(self, tab_id: int) -> Optional[Stack]:
        for stack in self._stacks.values():
            if tab_id in stack.tab_ids:
                return stack
        return None

    def stacks(self) -> List[Stack]:
        return list(self._stacks.values())

    def tabs(self) -> List[Tab]:
        return list(self._tabs.values())

    def render(self) -> str:
        """Flat, honest view of the bar: collapsed stacks show a count."""
        parts = []
        for kind, eid in self._order:
            if kind == "tab":
                tab = self._tabs[eid]
                marker = "*" if eid == self.active_tab else " "
                parts.append(f"{marker}[{tab.title}]")
            else:
                stack = self._stacks[eid]
                if stack.collapsed:
                    parts.append(f"[{stack.name} x{len(stack.tab_ids)}]")
                else:
                    inner = ", ".join(self._tabs[t].title for t in stack.tab_ids)
                    parts.append(f"[{stack.name}: {inner}]")
        return " | ".join(parts) if parts else "(no tabs)"


def demo_tabs() -> Dict[str, object]:
    bar = TabBar()
    a = bar.open("inbox", "levi://mail/inbox")
    b = bar.open("drafts", "levi://mail/drafts")
    c = bar.open("build", "levi://build/status")
    s = bar.stack("mail", [a.id, b.id])
    collapsed = bar.render()
    bar.expand(s.id)
    expanded = bar.render()
    bar.unstack(b.id)
    return {
        "collapsed": collapsed,
        "expanded": expanded,
        "after_unstack": bar.render(),
        "stack_of_build": bar.stack_of(c.id).name if bar.stack_of(c.id) else None,
    }


if __name__ == "__main__":  # pragma: no cover
    import json

    print(json.dumps(demo_tabs(), indent=2))

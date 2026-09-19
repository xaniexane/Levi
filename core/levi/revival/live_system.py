"""LEVI's live image — a running system with no wall between program and machine.

Studied from: retired-software-revival-research-20260916-0004/report.md
[catalog #21] (Lisp Machines).

The studied capability shape: whole-system liveness — no boundary between
the system and the program, everything inspectable and patchable while it
runs, tagged types, garbage collection. This module is an original,
in-process expression of that shape: a ``LiveSystem`` that holds *tagged*
values on a visible simulated heap, keeps a registry of live function
definitions that can be *redefined at runtime* (hot patching with full
version history), and can be *inspected* at any moment to snapshot every
definition, binding, and heap statistic.

Honest limits, stated plainly: this is a teaching-scale *model* of a
tagged heap and its collector, not real hardware. Python's own garbage
collector does the actual memory management; the simulated refcounts here
exist so liveness is *visible* — you can watch cells get allocated,
referenced, released, and swept. Hot patching is real within this image:
redefining a function changes what ``call`` invokes, immediately, while
the old version stays in history. Nothing here touches the network; it is
local-first and stdlib-only.

Original, from-scratch implementation for LEVI. Not artificial. Synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

ORIGIN = "levi-revival/live-system"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class LiveSystemError(Exception):
    """Base class for live-image failures."""


class UnknownDefinition(LiveSystemError):
    """A call or redefinition named something the image doesn't hold."""

    def __init__(self, name: str):
        super().__init__(f"no live definition named {name!r}")
        self.name = name


class UnknownBinding(LiveSystemError):
    """A binding operation named a value the image doesn't hold."""

    def __init__(self, name: str):
        super().__init__(f"no live binding named {name!r}")
        self.name = name


class NotCallableDefinition(LiveSystemError):
    """``define`` was given something that cannot be called."""

    def __init__(self, name: str):
        super().__init__(f"definition {name!r} must be callable")
        self.name = name


# ---------------------------------------------------------------------------
# Tagged values
# ---------------------------------------------------------------------------


def tag_of(value: Any) -> str:
    """The type tag for a Python value, Lisp-machine style."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "list"
    if isinstance(value, tuple):
        return "tuple"
    if isinstance(value, dict):
        return "map"
    if isinstance(value, set):
        return "set"
    if callable(value):
        return "function"
    return "object"


@dataclass
class TaggedCell:
    """One slot on the simulated heap: a value, its tag, a refcount."""

    cell_id: int
    value: Any
    tag: str
    refcount: int = 0
    alive: bool = True


@dataclass
class Definition:
    """A live, patchable function definition with version history."""

    name: str
    doc: str = ""
    versions: List[Callable] = field(default_factory=list)

    @property
    def current(self) -> Callable:
        """The version that ``call`` invokes right now."""
        return self.versions[-1]

    @property
    def version(self) -> int:
        """1-based version number of the current definition."""
        return len(self.versions)


# ---------------------------------------------------------------------------
# The live image
# ---------------------------------------------------------------------------


class LiveSystem:
    """A running image: tagged heap + hot-patchable definitions + inspector.

    Everything in the image is inspectable while it runs (``inspect``),
    every definition is patchable while it runs (``redefine``), and the
    tagged heap's garbage is visibly collected (``gc``).
    """

    def __init__(self) -> None:
        self._heap: Dict[int, TaggedCell] = {}
        self._next_cell = 1
        self._swept_total = 0
        self._defs: Dict[str, Definition] = {}
        self._bindings: Dict[str, int] = {}  # name -> cell_id

    # -- tagged heap --------------------------------------------------------

    def alloc(self, value: Any) -> int:
        """Allocate a tagged cell on the heap; returns its cell id."""
        cell_id = self._next_cell
        self._next_cell += 1
        self._heap[cell_id] = TaggedCell(cell_id, value, tag_of(value))
        return cell_id

    def retain(self, cell_id: int) -> TaggedCell:
        """Add a simulated reference to a cell."""
        cell = self._cell(cell_id)
        cell.refcount += 1
        return cell

    def release(self, cell_id: int) -> TaggedCell:
        """Drop a simulated reference; never below zero."""
        cell = self._cell(cell_id)
        cell.refcount = max(0, cell.refcount - 1)
        return cell

    def gc(self) -> int:
        """Sweep every live cell with a zero refcount.

        Returns the number of cells swept this pass. The simulation is
        the point: Python reclaims the real memory; here you watch the
        *idea* of a tagged collector work.
        """
        swept = 0
        for cell_id, cell in list(self._heap.items()):
            if cell.alive and cell.refcount == 0:
                cell.alive = False
                del self._heap[cell_id]
                swept += 1
        self._swept_total += swept
        return swept

    def heap_stats(self) -> Dict[str, int]:
        """Live cells, swept total, and per-tag population."""
        tags: Dict[str, int] = {}
        for cell in self._heap.values():
            tags[cell.tag] = tags.get(cell.tag, 0) + 1
        return {"live": len(self._heap), "swept_total": self._swept_total, **tags}

    # -- live definitions (hot patching) ------------------------------------

    def define(self, name: str, fn: Callable, doc: str = "") -> Definition:
        """Install a live definition. Redefining keeps history instead."""
        if not callable(fn):
            raise NotCallableDefinition(name)
        if name in self._defs:
            return self.redefine(name, fn, doc)
        definition = Definition(name, doc, [fn])
        self._defs[name] = definition
        return definition

    def redefine(self, name: str, fn: Callable, doc: str = "") -> Definition:
        """Hot-patch a definition *while the image runs*.

        The new version takes effect for the very next ``call``; every
        old version stays in history and can be rolled back to.
        """
        if not callable(fn):
            raise NotCallableDefinition(name)
        definition = self._defs.get(name)
        if definition is None:
            raise UnknownDefinition(name)
        definition.versions.append(fn)
        if doc:
            definition.doc = doc
        return definition

    def rollback(self, name: str, version: int) -> Definition:
        """Roll a definition back to an earlier 1-based version.

        Implemented as a new version holding the old function — history
        is append-only, so the rollback itself is visible in the log.
        """
        definition = self._defs.get(name)
        if definition is None:
            raise UnknownDefinition(name)
        if not 1 <= version <= len(definition.versions):
            raise LiveSystemError(
                f"{name!r} has {len(definition.versions)} version(s); "
                f"cannot roll back to {version}"
            )
        definition.versions.append(definition.versions[version - 1])
        return definition

    def call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Invoke the *current* version of a live definition."""
        definition = self._defs.get(name)
        if definition is None:
            raise UnknownDefinition(name)
        return definition.current(*args, **kwargs)

    def definitions(self) -> List[str]:
        """Names of every live definition."""
        return list(self._defs.keys())

    def history(self, name: str) -> int:
        """How many versions a definition has seen."""
        definition = self._defs.get(name)
        if definition is None:
            raise UnknownDefinition(name)
        return len(definition.versions)

    # -- bindings -----------------------------------------------------------

    def bind(self, name: str, value: Any) -> str:
        """Bind a name to a tagged heap cell; returns the value's tag."""
        if name in self._bindings:
            self.release(self._bindings[name])
        cell_id = self.alloc(value)
        self.retain(cell_id)
        self._bindings[name] = cell_id
        return tag_of(value)

    def lookup(self, name: str) -> Any:
        """Read a bound value back out of the image."""
        cell_id = self._bindings.get(name)
        if cell_id is None:
            raise UnknownBinding(name)
        return self._heap[cell_id].value

    def unbind(self, name: str) -> None:
        """Drop a binding; the cell becomes collectable on the next gc."""
        cell_id = self._bindings.pop(name, None)
        if cell_id is None:
            raise UnknownBinding(name)
        self.release(cell_id)

    def bindings(self) -> Dict[str, str]:
        """Every bound name with its value's tag."""
        return {
            name: self._heap[cell_id].tag
            for name, cell_id in self._bindings.items()
            if cell_id in self._heap
        }

    # -- inspection ----------------------------------------------------------

    def inspect(self) -> Dict[str, Any]:
        """Snapshot the whole running image: defs, bindings, heap.

        The Lisp-machine promise — no wall between system and program —
        expressed as a plain dict: ask the image what it holds, and it
        tells you, while it runs.
        """
        return {
            "definitions": {
                name: {
                    "version": d.version,
                    "history": len(d.versions),
                    "doc": d.doc,
                }
                for name, d in self._defs.items()
            },
            "bindings": self.bindings(),
            "heap": self.heap_stats(),
        }

    def _cell(self, cell_id: int) -> TaggedCell:
        cell = self._heap.get(cell_id)
        if cell is None or not cell.alive:
            raise LiveSystemError(f"no live cell {cell_id}")
        return cell


__all__ = [
    "ORIGIN",
    "LiveSystemError",
    "UnknownDefinition",
    "UnknownBinding",
    "NotCallableDefinition",
    "tag_of",
    "TaggedCell",
    "Definition",
    "LiveSystem",
]

"""LEVI's outline-and-columns memory model: freeform capture, typed views.

Inspired by Ecco Pro (Arabesque Software, Windows PIM, 1993–1997;
acquired by NetManage, discontinued; cult following persists). The
ahead-of-its-time mechanism: a freeform *outline* fused with typed
spreadsheet-like columns — every item is both an outline node and a
database row; folders with multi-membership (one item visible in many
views); dynamic links.

Remix delta: Ecco's outline/column fusion reimagined as LEVI's memory
data model — not a PIM clone. Nodes are memories, not appointments;
folders are typed *lenses* so one memory appears under "Japan 2027" and
"expensive things to decide" at once; columns are deny-closed typed
(mistyped values rejected, never silently coerced). No calendar or
contacts integration; the link layer lives in revival.linkbase.

This is an original, from-scratch reimplementation for LEVI — no Ecco
code is used. ``Outline`` holds freeform nodes in a tree; ``Folder``
defines typed columns (TEXT/NUMBER/BOOLEAN/DATE with coercion) and holds
*members* — the same node may belong to many folders, so one memory
appears under "Japan 2027" and "expensive things to decide" at once.
``Store.query`` gives database-grade views over freeform capture. Deny-
closed: a node must exist to join a folder; a column must exist to take a
value; mistyped values are rejected, never coerced silently into the
wrong type.

Persistence: JSON under an explicit path (default ``~/.levi/ecco/``).

Honesty: LOAD-BEARING — the outline+columns hybrid as the memory data
model. What is NOT revived: Ecco's calendar/contacts integration and its
"dynamic links" (see revival.linkbase for the link layer).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Optional


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class EccoError(Exception):
    """Base class for outline/column failures."""


class UnknownNode(EccoError):
    """The node id does not exist in the outline."""


class UnknownFolder(EccoError):
    """The folder name does not exist."""


class UnknownColumn(EccoError):
    """The column is not defined on the folder."""


class TypeMismatch(EccoError):
    """The value cannot be coerced to the column's type."""


# ---------------------------------------------------------------------------
# Typed columns
# ---------------------------------------------------------------------------


class ColumnType:
    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"  # ISO YYYY-MM-DD

    ALL = (TEXT, NUMBER, BOOLEAN, DATE)


def coerce(coltype: str, value: Any) -> Any:
    """Coerce ``value`` to ``coltype`` or raise :class:`TypeMismatch`."""
    if coltype == ColumnType.TEXT:
        if isinstance(value, str):
            return value
        raise TypeMismatch(f"expected text, got {type(value).__name__}")
    if coltype == ColumnType.NUMBER:
        if isinstance(value, bool):
            raise TypeMismatch("expected number, got boolean")
        if isinstance(value, (int, float)):
            return value
        raise TypeMismatch(f"expected number, got {type(value).__name__}")
    if coltype == ColumnType.BOOLEAN:
        if isinstance(value, bool):
            return value
        raise TypeMismatch(f"expected boolean, got {type(value).__name__}")
    if coltype == ColumnType.DATE:
        if isinstance(value, date) and not isinstance(value, str):
            return value.isoformat()
        if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise TypeMismatch(f"invalid date {value!r}: {exc}") from exc
            return value
        raise TypeMismatch(f"expected ISO date YYYY-MM-DD, got {value!r}")
    raise ValueError(f"unknown column type {coltype!r}")


# ---------------------------------------------------------------------------
# Outline — the freeform tree
# ---------------------------------------------------------------------------


@dataclass
class Node:
    node_id: str
    text: str
    parent: Optional[str] = None
    children: list[str] = field(default_factory=list)


class Outline:
    """Freeform outline: every memory is a node in a tree."""

    def __init__(self):
        self._nodes: dict[str, Node] = {}
        self._roots: list[str] = []
        self._counter = 0

    def add_node(self, text: str, parent: Optional[str] = None) -> Node:
        if not text or not text.strip():
            raise ValueError("node text must be non-empty")
        if parent is not None and parent not in self._nodes:
            raise UnknownNode(parent)
        self._counter += 1
        node = Node(node_id=f"n{self._counter}", text=text.strip(), parent=parent)
        self._nodes[node.node_id] = node
        if parent is None:
            self._roots.append(node.node_id)
        else:
            self._nodes[parent].children.append(node.node_id)
        return node

    def get(self, node_id: str) -> Node:
        try:
            return self._nodes[node_id]
        except KeyError:
            raise UnknownNode(node_id) from None

    def children(self, node_id: str) -> list[Node]:
        return [self._nodes[c] for c in self.get(node_id).children]

    def roots(self) -> list[Node]:
        return [self._nodes[r] for r in self._roots]

    def path(self, node_id: str) -> list[Node]:
        """Root-to-node chain."""
        chain = []
        node = self.get(node_id)
        while node is not None:
            chain.append(node)
            node = self._nodes.get(node.parent) if node.parent else None
        return list(reversed(chain))

    def subtree(self, node_id: str) -> list[Node]:
        out = [self.get(node_id)]
        for child in self.children(node_id):
            out.extend(self.subtree(child.node_id))
        return out

    def move_node(self, node_id: str, new_parent: Optional[str]) -> None:
        node = self.get(node_id)
        if new_parent is not None:
            if new_parent not in self._nodes:
                raise UnknownNode(new_parent)
            if new_parent == node_id or any(
                n.node_id == new_parent for n in self.subtree(node_id)
            ):
                raise EccoError("cannot move a node under itself or its descendant")
        old_parent = node.parent
        if old_parent is None:
            self._roots.remove(node_id)
        else:
            self._nodes[old_parent].children.remove(node_id)
        node.parent = new_parent
        if new_parent is None:
            self._roots.append(node_id)
        else:
            self._nodes[new_parent].children.append(node_id)

    def delete_node(self, node_id: str, recursive: bool = False) -> None:
        node = self.get(node_id)
        if node.children and not recursive:
            raise EccoError(
                f"node {node_id!r} has children; pass recursive=True to delete"
            )
        for child in list(node.children):
            self.delete_node(child, recursive=True)
        if node.parent is None:
            self._roots.remove(node_id)
        else:
            self._nodes[node.parent].children.remove(node_id)
        del self._nodes[node_id]

    def __len__(self) -> int:
        return len(self._nodes)

    # -- (de)serialization ------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "counter": self._counter,
            "roots": self._roots,
            "nodes": {
                nid: {"text": n.text, "parent": n.parent, "children": n.children}
                for nid, n in self._nodes.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Outline":
        o = cls()
        o._counter = int(data.get("counter", 0))
        o._roots = list(data.get("roots", []))
        for nid, nd in data.get("nodes", {}).items():
            o._nodes[nid] = Node(
                node_id=nid,
                text=nd["text"],
                parent=nd.get("parent"),
                children=list(nd.get("children", [])),
            )
        return o


# ---------------------------------------------------------------------------
# Folders — typed-column views with multi-membership
# ---------------------------------------------------------------------------


class Folder:
    """A named view: typed columns + member node ids (multi-membership:
    one node may belong to many folders)."""

    def __init__(self, name: str):
        if not name or not name.strip():
            raise ValueError("folder name must be non-empty")
        self.name = name.strip()
        self.columns: dict[str, str] = {}
        self.members: list[str] = []
        self._cells: dict[tuple[str, str], Any] = {}

    def define_column(self, column: str, coltype: str) -> None:
        if coltype not in ColumnType.ALL:
            raise ValueError(f"unknown column type {coltype!r}")
        if not column or not column.strip():
            raise ValueError("column name must be non-empty")
        self.columns[column.strip()] = coltype

    def add_member(self, node_id: str) -> None:
        if node_id not in self.members:
            self.members.append(node_id)

    def remove_member(self, node_id: str) -> None:
        if node_id not in self.members:
            raise EccoError(f"node {node_id!r} is not a member of {self.name!r}")
        self.members.remove(node_id)
        for key in [k for k in self._cells if k[0] == node_id]:
            del self._cells[key]

    def set_cell(self, node_id: str, column: str, value: Any) -> None:
        if node_id not in self.members:
            raise EccoError(f"node {node_id!r} is not a member of folder {self.name!r}")
        if column not in self.columns:
            raise UnknownColumn(f"folder {self.name!r} has no column {column!r}")
        self._cells[(node_id, column)] = coerce(self.columns[column], value)

    def get_cell(self, node_id: str, column: str) -> Any:
        if column not in self.columns:
            raise UnknownColumn(f"folder {self.name!r} has no column {column!r}")
        return self._cells.get((node_id, column))

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "columns": self.columns,
            "members": self.members,
            "cells": {
                f"{nid}\x00{col}": val for (nid, col), val in self._cells.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Folder":
        f = cls(data["name"])
        f.columns = dict(data.get("columns", {}))
        f.members = list(data.get("members", []))
        for key, val in data.get("cells", {}).items():
            nid, col = key.split("\x00")
            f._cells[(nid, col)] = val
        return f


# ---------------------------------------------------------------------------
# Store — outline + folders, queryable, persistent
# ---------------------------------------------------------------------------


class Store:
    """The Ecco store: one outline, many folder views over it."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else Path.home() / ".levi" / "ecco"
        self.outline = Outline()
        self.folders: dict[str, Folder] = {}
        self._load()

    # -- persistence ------------------------------------------------------------
    def _file(self) -> Path:
        return self.path / "ecco.json"

    def _load(self) -> None:
        f = self._file()
        if not f.exists():
            return
        data = json.loads(f.read_text(encoding="utf-8"))
        self.outline = Outline.from_dict(data.get("outline", {}))
        self.folders = {
            fd["name"]: Folder.from_dict(fd) for fd in data.get("folders", [])
        }

    def save(self) -> Path:
        self.path.mkdir(parents=True, exist_ok=True)
        target = self._file()
        tmp = target.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {
                    "outline": self.outline.to_dict(),
                    "folders": [f.to_dict() for f in self.folders.values()],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        tmp.replace(target)
        return target

    # -- folders ------------------------------------------------------------------
    def add_folder(self, name: str) -> Folder:
        if name in self.folders:
            raise ValueError(f"folder {name!r} already exists")
        folder = Folder(name)
        self.folders[name] = folder
        return folder

    def folder(self, name: str) -> Folder:
        try:
            return self.folders[name]
        except KeyError:
            raise UnknownFolder(name) from None

    def file_node(self, node_id: str, folder_name: str) -> None:
        """File a node into a folder (multi-membership: file it anywhere)."""
        self.outline.get(node_id)  # deny-closed: node must exist
        self.folder(folder_name).add_member(node_id)

    # -- database-grade views -------------------------------------------------------
    def view(
        self, folder_name: str, sort_by: Optional[str] = None, reverse: bool = False
    ) -> list[dict]:
        """Every member as a row: ``{"id", "text", <columns...>}``."""
        folder = self.folder(folder_name)
        rows = []
        for nid in folder.members:
            try:
                node = self.outline.get(nid)
            except UnknownNode:
                continue  # node deleted; folder membership is stale — skip
            row: dict[str, Any] = {"id": nid, "text": node.text}
            for col in folder.columns:
                row[col] = folder.get_cell(nid, col)
            rows.append(row)
        if sort_by is not None:
            if sort_by not in folder.columns and sort_by not in ("id", "text"):
                raise UnknownColumn(sort_by)
            rows.sort(key=lambda r: (r[sort_by] is None, r[sort_by]), reverse=reverse)
        return rows

    def query(self, folder_name: str, where: Callable[[dict], bool]) -> list[dict]:
        """Filter a folder's rows with a predicate over the row dict."""
        return [row for row in self.view(folder_name) if where(row)]


__all__ = [
    "EccoError",
    "UnknownNode",
    "UnknownFolder",
    "UnknownColumn",
    "TypeMismatch",
    "ColumnType",
    "coerce",
    "Node",
    "Outline",
    "Folder",
    "Store",
]

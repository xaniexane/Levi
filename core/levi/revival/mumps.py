"""LEVI's persistent-global substrate: language–database fusion with LEVI's
own journaling.

Inspired by MUMPS (MGH, 1966–67 — Pappalardo, Greenes, Marble, in Octo
Barnett's lab; standardized from 1976 as NBS/ANSI/ISO 11756). The
ahead-of-its-time mechanism: *the language and the database are one
thing* — persistent hierarchical sparse arrays ("globals") are first-
class variables: ``^data`` is on disk the way ``data`` is in memory;
single universal datatype; ACID from the start. It never died — Epic and
Caché-based systems serve the bulk of US healthcare — but the fusion idea
is underused outside medicine.

Remix delta: MUMPS' fusion reimagined as LEVI's schemaless life-data
substrate — not a MUMPS clone. ``^person("mom","birthday")`` persists via
LEVI's own journaling (append-only journal + atomic snapshot + replay on
open; stdlib JSON, no database engine — hard-route law: no licensed DB,
redesign around it). Faithful where it matters: ``$DATA`` codes,
``$ORDER`` collation (numbers before strings), ``KILL`` subtree
semantics. Honestly narrower: values must be JSON-serializable,
single-process use documented, no transactions beyond atomic file
replacement.

This is an original, from-scratch reimplementation for LEVI — no MUMPS
code is used, and it is stdlib-only (JSON files, no database engine).
``Globals`` gives you persistent globals: ``^person("mom","birthday")``
just works and survives restarts; sparse, irregular life data needs no
schema and no ORM. Every mutation is appended to a journal; ``snapshot``
compacts; on open, the latest snapshot plus journal replay restores the
state — a crash between snapshots loses nothing.

Faithful MUMPS-isms kept: ``$DATA``-style :meth:`data` codes (0 absent, 1
value-only, 10 descendants-only, 11 both), ``$ORDER``-style
:meth:`order` (next subscript at a level, numbers collate before
strings), and ``KILL`` semantics (:meth:`kill` removes a subtree).

Honesty: LOAD-BEARING — with stated simplifications. Values must be
JSON-serializable (a ``TypeError`` otherwise — MUMPS's universal string
is not reproduced); collation is "numbers before strings, numerics
numerically" (not full MUMPS canonical ordering); there are no
transactions beyond atomic file replacement — concurrent writers from two
processes are NOT safe (documented; use one ``Globals`` per directory).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Iterator, Optional


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class GlobalsError(Exception):
    """Base class for globals failures."""


# ---------------------------------------------------------------------------
# Node model: {"v": value-or-None, "c": {subscript: node}}
# ---------------------------------------------------------------------------


def _new_node() -> dict:
    return {"v": None, "c": {}}


def _sub_key(sub: Any) -> str:
    if isinstance(sub, bool):
        raise TypeError("subscripts must be str, int, or float (not bool)")
    if isinstance(sub, (str, int, float)):
        return json.dumps(sub, sort_keys=True)
    raise TypeError(
        f"subscript must be str/int/float, got {type(sub).__name__}")


def _collation_key(key: str) -> tuple:
    sub = json.loads(key)
    if isinstance(sub, (int, float)) and not isinstance(sub, bool):
        return (0, float(sub), "")
    return (1, 0.0, str(sub))


def _require_jsonable(value: Any) -> None:
    try:
        json.dumps(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            f"mumps: global values must be JSON-serializable: {exc}") from exc


# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------


class Globals:
    """Persistent globals rooted at ``path``: ``globals.json`` (snapshot)
    plus ``journal.jsonl`` (append-only mutations)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self._snapshot_file = self.path / "globals.json"
        self._journal_file = self.path / "journal.jsonl"
        self._data: dict[str, dict] = {}
        self._recover()

    # -- recovery: snapshot + journal replay ----------------------------------------
    def _recover(self) -> None:
        if self._snapshot_file.exists():
            self._data = json.loads(
                self._snapshot_file.read_text(encoding="utf-8"))
        if self._journal_file.exists():
            for line in self._journal_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self._apply_entry(json.loads(line), journal=False)

    def _journal(self, entry: dict) -> None:
        entry = dict(entry)
        entry["ts"] = time.time()
        with self._journal_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _apply_entry(self, entry: dict, journal: bool = True) -> None:
        op = entry["op"]
        name, subs = entry["name"], tuple(entry["subs"])
        if op == "set":
            node = self._ensure(name, subs)
            node["v"] = entry["value"]
        elif op == "kill":
            self._kill_node(name, subs)
        else:
            raise GlobalsError(f"unknown journal op {op!r}")
        if journal:
            self._journal(entry)

    def snapshot(self) -> Path:
        """Compact: write the full state atomically, truncate the journal."""
        tmp = self._snapshot_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        tmp.replace(self._snapshot_file)
        self._journal_file.write_text("", encoding="utf-8")
        return self._snapshot_file

    # -- navigation ---------------------------------------------------------------------
    def _ensure(self, name: str, subs: tuple) -> dict:
        self._validate_name(name)
        node = self._data.setdefault(name, _new_node())
        for sub in subs:
            key = _sub_key(sub)
            node = node["c"].setdefault(key, _new_node())
        return node

    def _find(self, name: str, subs: tuple) -> Optional[dict]:
        node = self._data.get(name)
        if node is None:
            return None
        for sub in subs:
            node = node["c"].get(_sub_key(sub))
            if node is None:
                return None
        return node

    @staticmethod
    def _validate_name(name: str) -> None:
        if not isinstance(name, str) or not name:
            raise ValueError("global name must be a non-empty string")

    # -- the fusion: set / get / kill ---------------------------------------------------------
    def set(self, name: str, value: Any, *subs: Any) -> None:
        """``SET ^name(sub1,sub2)=value`` — persists immediately (journaled)."""
        _require_jsonable(value)
        for s in subs:
            _sub_key(s)  # fail-closed on bad subscripts
        _require_jsonable(list(subs))  # journal must round-trip
        self._apply_entry({"op": "set", "name": name,
                           "subs": list(subs), "value": value})

    def get(self, name: str, *subs: Any, default: Any = None) -> Any:
        """``$GET``: the value, or ``default`` when absent (never raises
        for missing nodes)."""
        node = self._find(name, subs)
        if node is None or node["v"] is None:
            return default
        return node["v"]

    def kill(self, name: str, *subs: Any) -> None:
        """``KILL``: remove a node and its entire subtree (journaled)."""
        self._validate_name(name)
        for s in subs:
            _sub_key(s)
        self._apply_entry({"op": "kill", "name": name, "subs": list(subs)})

    def _kill_node(self, name: str, subs: tuple) -> None:
        if not subs:
            self._data.pop(name, None)
            return
        parent = self._find(name, subs[:-1])
        if parent is not None:
            parent["c"].pop(_sub_key(subs[-1]), None)

    # -- $DATA / $ORDER --------------------------------------------------------------------------
    def data(self, name: str, *subs: Any) -> int:
        """``$DATA`` codes: 0 absent, 1 value-only, 10 descendants-only,
        11 value and descendants."""
        node = self._find(name, subs)
        if node is None:
            return 0
        has_v = node["v"] is not None
        has_c = bool(node["c"])
        return (1 if has_v else 0) + (10 if has_c else 0)

    def order(self, name: str, *subs: Any, direction: int = 1) -> Any:
        """``$ORDER``: the next subscript at this level after ``subs``
        (``direction=1`` forward, ``-1`` backward); ``None`` at the end."""
        if direction not in (1, -1):
            raise ValueError("direction must be 1 or -1")
        if subs:
            parent = self._find(name, subs[:-1])
            if parent is None:
                return None
            keys = sorted(parent["c"], key=_collation_key)
            if direction == -1:
                keys = list(reversed(keys))
            try:
                idx = keys.index(_sub_key(subs[-1]))
            except ValueError:
                # Start before/after the given subscript: find the neighbor.
                ordered = sorted(parent["c"], key=_collation_key)
                target = _collation_key(_sub_key(subs[-1]))
                cands = [k for k in ordered
                         if (_collation_key(k) > target if direction == 1
                             else _collation_key(k) < target)]
                return json.loads(cands[0]) if cands else None
            return json.loads(keys[idx + 1]) if idx + 1 < len(keys) else None
        node = self._data.get(name)
        if not node or not node["c"]:
            return None
        keys = sorted(node["c"], key=_collation_key)
        if direction == -1:
            keys = list(reversed(keys))
        return json.loads(keys[0])

    def children(self, name: str, *subs: Any) -> list[Any]:
        """Immediate subscripts at this level, in collation order."""
        node = self._find(name, subs)
        if node is None:
            return []
        return [json.loads(k) for k in sorted(node["c"], key=_collation_key)]

    def traverse(self, name: str) -> Iterator[tuple[tuple, Any]]:
        """Yield ``(subscripts, value)`` for every valued node, depth-first
        in collation order."""
        self._validate_name(name)
        root = self._data.get(name)
        if root is None:
            return
        stack: list[tuple[tuple, dict]] = [((), root)]
        while stack:
            subs, node = stack.pop()
            if node["v"] is not None:
                yield subs, node["v"]
            for key in sorted(node["c"], key=_collation_key, reverse=True):
                stack.append((subs + (json.loads(key),), node["c"][key]))

    def globals(self) -> list[str]:
        """Names of all resident globals."""
        return sorted(self._data)


__all__ = [
    "GlobalsError",
    "Globals",
]

"""BeOS live queries — queries that stay alive.

BeOS's filesystem kept *live queries*: a query was a standing question
over the index, and its result set updated itself as files were
created, changed, or removed — no re-running. ``live_system.py`` models
the Lisp-machine whole-system liveness; this module is the other
revival: the live-query index.

``LiveIndex`` holds records with stable ids. ``subscribe(predicate)``
returns a ``LiveQuery`` whose ``results`` always reflect the current
state: insert a matching record and it appears; update one out of the
predicate and it leaves; remove it and it's gone. Every change emits a
receipt ``(seq, op, id)`` so subscribers can audit what moved.

LAWS
----
1. **Predicates are deterministic.** A predicate is a pure function of
   the record — same record, same verdict, every time. Predicates that
   raise are treated as non-matching (and reported), never as fatal.
2. **Ids are stable.** Insert assigns the id once; updates and removes
   address it. No id is ever reused.
3. **Unsubscribe is total.** After ``unsubscribe``, the query receives
   nothing further and holds no reference to the index.
4. **Change receipts.** Every mutation appends ``(seq, op, id)`` to the
   index log and notifies subscribers in subscription order.

stdlib-only, local-first, no network.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

__all__ = [
    "LiveIndex",
    "LiveQuery",
    "QueryError",
    "Receipt",
]

Receipt = Tuple[int, str, str]  # (seq, op, id); op in insert|update|remove


class QueryError(Exception):
    """A live-query operation was refused."""


@dataclass
class LiveQuery:
    """A standing question over a ``LiveIndex``. ``results`` is always current."""

    _index: "LiveIndex"
    _qid: int
    name: str
    _results: List[str] = field(default_factory=list, repr=False)
    _active: bool = field(default=True, repr=False)
    predicate_errors: List[str] = field(default_factory=list)

    @property
    def active(self) -> bool:
        return self._active

    def results(self) -> List[Dict[str, Any]]:
        """Current matching records, in insertion order. Raises if unsubscribed."""
        if not self._active:
            raise QueryError(f"query {self.name!r} is unsubscribed")
        idx = self._index
        return [dict(idx._records[i]) for i in self._results if i in idx._records]

    def unsubscribe(self) -> None:
        """Stop receiving updates. Total: no further notifications, no leak."""
        if self._active:
            self._active = False
            self._index._drop(self._qid)
            self._results.clear()


class LiveIndex:
    """A record store with BeOS-style live queries."""

    def __init__(self) -> None:
        self._records: Dict[str, Dict[str, Any]] = {}
        self._retired: set = set()  # ids are never reused, even after remove
        self._order: List[str] = []
        self._queries: Dict[int, LiveQuery] = {}
        self._predicates: Dict[int, Callable[[Dict[str, Any]], bool]] = {}
        self._qids = itertools.count(1)
        self._seq = itertools.count(1)
        self.log: List[Receipt] = []

    # -- records ---------------------------------------------------------

    def insert(self, record: Dict[str, Any], id: Optional[str] = None) -> str:
        """Insert a record. Returns its stable id."""
        if not isinstance(record, dict):
            raise QueryError("record must be a dict")
        rid = id if id is not None else f"r{next(self._seq):06d}"
        if not str(rid).strip():
            raise QueryError("record id may not be blank")
        if rid in self._records or rid in self._retired:
            raise QueryError(f"duplicate record id {rid!r}: ids are never reused")
        stored = dict(record)
        stored["id"] = rid
        self._records[rid] = stored
        self._order.append(rid)
        self._emit("insert", rid)
        return rid

    def update(self, rid: str, changes: Dict[str, Any]) -> Dict[str, Any]:
        """Patch a record (``id`` itself is immutable)."""
        if rid not in self._records:
            raise QueryError(f"unknown record {rid!r}")
        if not isinstance(changes, dict):
            raise QueryError("changes must be a dict")
        rec = self._records[rid]
        for k, v in changes.items():
            if k == "id":
                continue
            rec[k] = v
        self._emit("update", rid)
        return dict(rec)

    def remove(self, rid: str) -> Dict[str, Any]:
        """Remove a record. The id is retired, never reused."""
        if rid not in self._records:
            raise QueryError(f"unknown record {rid!r}")
        rec = self._records.pop(rid)
        self._retired.add(rid)
        self._emit("remove", rid)
        return rec

    def get(self, rid: str) -> Dict[str, Any]:
        if rid not in self._records:
            raise QueryError(f"unknown record {rid!r}")
        return dict(self._records[rid])

    # -- queries ----------------------------------------------------------

    def subscribe(self, predicate: Callable[[Dict[str, Any]], bool],
                  name: str = "") -> LiveQuery:
        """Register a standing query. Initial results are computed at once."""
        if not callable(predicate):
            raise QueryError("predicate must be callable")
        qid = next(self._qids)
        query = LiveQuery(_index=self, _qid=qid,
                          name=name or f"query-{qid}")
        self._queries[qid] = query
        self._predicates[qid] = predicate
        self._refresh(query)
        return query

    def _drop(self, qid: int) -> None:
        self._queries.pop(qid, None)
        self._predicates.pop(qid, None)

    def _matches(self, query: LiveQuery, rec: Dict[str, Any]) -> bool:
        try:
            return bool(self._predicates[query._qid](rec))
        except Exception as exc:  # predicates that raise are non-matching
            note = f"{query.name}: predicate error on {rec.get('id')}: {exc}"
            if note not in query.predicate_errors:
                query.predicate_errors.append(note)
            return False

    def _refresh(self, query: LiveQuery) -> None:
        query._results = [rid for rid in self._order
                          if rid in self._records
                          and self._matches(query, self._records[rid])]

    def _emit(self, op: str, rid: str) -> None:
        seq = next(self._seq)
        self.log.append((seq, op, rid))
        # Notify in subscription order; a dead query never blocks the rest.
        for qid in sorted(self._queries):
            query = self._queries.get(qid)
            if query is None or not query.active:
                continue
            try:
                self._refresh(query)
            except Exception:
                continue

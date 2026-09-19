"""The Forge data store — LEVI-native embedded document store.

The SQLite-like for the LEVI dynasty's Forge: collections of documents,
queries, atomic writes, receipts on every write, a full audit trail.

LEVI's twist: **provenance on everything, nothing silent.** Every record
carries where it came from (``origin``) and every write returns a receipt
and lands in an append-only audit trail. A write without an origin is
refused — deny-closed, never half-written.

Storage: stdlib ``sqlite3`` (stdlib-first, local-first), WAL mode, at::

    <LEVI_HOME>/forge/data/<store-name>.db

Home is resolved at CALL time from ``LEVI_HOME`` (hermetic: tests can pin
a tmp dir) with ``~/.levi`` as the fallback.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

__all__ = [
    "StoreError",
    "Receipt",
    "ForgeStore",
    "store_home",
    "open_store",
]

_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_DOCID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")

_OPS = ("put", "delete", "drop-collection", "get")


class StoreError(Exception):
    """Deny-closed: malformed input, missing provenance, bad names — refused."""


def store_home(home: "str | os.PathLike[str] | None" = None) -> Path:
    """Resolve the forge data dir at call time (hermetic: LEVI_HOME respected)."""
    if home is not None:
        base = Path(home)
    else:
        override = os.environ.get("LEVI_HOME")
        base = Path(override) if override else Path(os.path.expanduser("~/.levi"))
    return base / "forge" / "data"


def _check_name(name: str, kind: str) -> str:
    if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
        raise StoreError(
            f"invalid {kind} name {name!r}: 1-64 chars of [A-Za-z0-9_-], "
            "starting alnum (keeps table names safe and portable)"
        )
    return name


def _check_doc_id(doc_id: str) -> str:
    if not isinstance(doc_id, str) or not _DOCID_RE.fullmatch(doc_id):
        raise StoreError(
            f"invalid doc id {doc_id!r}: 1-128 chars of [A-Za-z0-9_.:-], starting alnum"
        )
    return doc_id


def _check_origin(origin: str) -> str:
    # LEVI's twist: nothing enters the store without provenance.
    if not isinstance(origin, str) or not origin.strip():
        raise StoreError(
            "origin is required: every record carries provenance — "
            "pass who/what wrote this (e.g. 'forge/ci', 'ops-migration-12')"
        )
    if len(origin) > 256:
        raise StoreError("origin too long (max 256 chars)")
    return origin.strip()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_MISSING = object()  # sentinel: field not present in the document


def _json_equal(a: Any, b: Any) -> bool:
    """Exact JSON value equality: True != 1, None == None, no coercion."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    return type(a) is type(b) and a == b


# ---------------------------------------------------------------------------
# Receipt
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Receipt:
    """The immutable record of one store write. Every write is receipted."""

    receipt_id: str
    op: str  # put | delete | drop-collection
    store: str
    collection: str
    doc_id: str
    revision: int
    ts: str
    origin: str
    note: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "op": self.op,
            "store": self.store,
            "collection": self.collection,
            "doc_id": self.doc_id,
            "revision": self.revision,
            "ts": self.ts,
            "origin": self.origin,
            "note": self.note,
            "detail": dict(self.detail),
        }

    def render(self) -> str:
        lines = [
            f"receipt {self.receipt_id} — {self.op} {self.store}.{self.collection}/{self.doc_id}",
            f"revision: {self.revision}",
            f"origin: {self.origin}",
            f"ts: {self.ts}",
        ]
        if self.note:
            lines.append(f"note: {self.note}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

_SCHEMA_AUDIT = """
CREATE TABLE IF NOT EXISTS _audit (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL,
    store      TEXT NOT NULL,
    collection TEXT NOT NULL,
    op         TEXT NOT NULL,
    doc_id     TEXT NOT NULL,
    revision   INTEGER NOT NULL,
    origin     TEXT NOT NULL,
    receipt_id TEXT NOT NULL,
    detail     TEXT NOT NULL DEFAULT '{}'
)
"""

_SCHEMA_COLLECTION = """
CREATE TABLE IF NOT EXISTS "{table}" (
    doc_id     TEXT PRIMARY KEY,
    data       TEXT NOT NULL,
    revision   INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    origin     TEXT NOT NULL,
    note       TEXT NOT NULL DEFAULT ''
)
"""

_OPERATORS = {
    "$eq": "=",
    "$ne": "!=",
    "$gt": ">",
    "$gte": ">=",
    "$lt": "<",
    "$lte": "<=",
}


class ForgeStore:
    """An embedded document store: collections, documents, queries, audit.

    Usage::

        store = open_store("forge")
        rcpt = store.put("issues", "issue-1",
                         {"title": "ship it"}, origin="forge/cli")
        doc = store.get("issues", "issue-1")
        rows = store.query("issues", where={"title": "ship it"})
    """

    def __init__(self, name: str, home: "str | os.PathLike[str] | None" = None):
        _check_name(name, "store")
        self.name = name
        self.path = store_home(home) / f"{name}.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._txn_depth = 0  # >0 while inside transaction()
        with self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute(_SCHEMA_AUDIT)

    # -- internals ---------------------------------------------------------

    def _table(self, collection: str) -> str:
        _check_name(collection, "collection")
        return f"docs_{collection}"

    def _ensure_collection(self, collection: str) -> str:
        table = self._table(collection)
        self._conn.execute(_SCHEMA_COLLECTION.format(table=table))
        return table

    def _audit(
        self,
        collection: str,
        op: str,
        doc_id: str,
        revision: int,
        origin: str,
        receipt_id: str,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._conn.execute(
            "INSERT INTO _audit (ts, store, collection, op, doc_id, revision,"
            " origin, receipt_id, detail) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                _utcnow(),
                self.name,
                collection,
                op,
                doc_id,
                revision,
                origin,
                receipt_id,
                json.dumps(detail or {}, sort_keys=True),
            ),
        )

    def _write_receipt(
        self,
        op: str,
        collection: str,
        doc_id: str,
        revision: int,
        origin: str,
        note: str,
        detail: Optional[Dict[str, Any]] = None,
    ) -> Receipt:
        receipt = Receipt(
            receipt_id=f"ds-{uuid.uuid4().hex[:12]}",
            op=op,
            store=self.name,
            collection=collection,
            doc_id=doc_id,
            revision=revision,
            ts=_utcnow(),
            origin=origin,
            note=note or "",
            detail=detail or {},
        )
        self._audit(
            collection, op, doc_id, revision, origin, receipt.receipt_id, receipt.detail
        )
        return receipt

    def _atomic(self):
        """Savepoint wrapper so writes are atomic even when nested inside
        :meth:`transaction` (a plain ``with self._conn:`` would commit
        early and break the outer rollback)."""

        class _Savepoint:
            def __init__(self, conn, store):
                self.conn = conn
                self.store = store

            def __enter__(self):
                self.conn.execute("SAVEPOINT levi_ds")
                return self

            def __exit__(self, exc_type, exc, tb):
                if exc_type is None:
                    self.conn.execute("RELEASE levi_ds")
                else:
                    self.conn.execute("ROLLBACK TO levi_ds")
                    self.conn.execute("RELEASE levi_ds")
                # A standalone write (outside transaction()) must persist;
                # inside transaction() the outer frame owns the commit.
                if self.store._txn_depth == 0:
                    self.conn.commit()
                return False

        return _Savepoint(self._conn, self)

    # -- writes (atomic: doc row + audit row commit together) --------------

    def put(
        self,
        collection: str,
        doc_id: str,
        data: Dict[str, Any],
        origin: str,
        note: str = "",
    ) -> Receipt:
        """Insert or replace a document. Atomic. Receipted. Origin required."""
        table = self._table(collection)
        _check_doc_id(doc_id)
        _check_origin(origin)
        if not isinstance(data, dict):
            raise StoreError("put: data must be a JSON object (dict)")
        try:
            payload = json.dumps(data, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise StoreError(f"put: data is not JSON-serializable: {exc}")
        now = _utcnow()
        with self._atomic():  # one transaction: doc row + audit row, or neither
            self._ensure_collection(collection)
            cur = self._conn.execute(
                f'SELECT revision FROM "{table}" WHERE doc_id = ?', (doc_id,)
            )
            row = cur.fetchone()
            if row is None:
                revision = 1
                self._conn.execute(
                    f'INSERT INTO "{table}"'
                    " (doc_id, data, revision, created_at, updated_at, origin, note)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (doc_id, payload, revision, now, now, origin, note or ""),
                )
                op = "put"
            else:
                revision = int(row["revision"]) + 1
                self._conn.execute(
                    f'UPDATE "{table}" SET data = ?, revision = ?,'
                    " updated_at = ?, origin = ?, note = ? WHERE doc_id = ?",
                    (payload, revision, now, origin, note or "", doc_id),
                )
                op = "put"
            return self._write_receipt(
                op,
                collection,
                doc_id,
                revision,
                origin,
                note,
                {"bytes": len(payload.encode("utf-8"))},
            )

    def delete(
        self, collection: str, doc_id: str, origin: str, note: str = ""
    ) -> Receipt:
        """Delete a document. Atomic. The receipt + audit row keep what was
        deleted and where it came from — nothing is silent."""
        table = self._table(collection)
        _check_doc_id(doc_id)
        _check_origin(origin)
        with self._atomic():
            self._ensure_collection(collection)
            cur = self._conn.execute(
                f'SELECT revision, data FROM "{table}" WHERE doc_id = ?', (doc_id,)
            )
            row = cur.fetchone()
            if row is None:
                raise StoreError(f"delete: no such document {collection}/{doc_id}")
            self._conn.execute(f'DELETE FROM "{table}" WHERE doc_id = ?', (doc_id,))
            return self._write_receipt(
                "delete",
                collection,
                doc_id,
                int(row["revision"]),
                origin,
                note,
                {"deleted_data": row["data"]},
            )

    def drop_collection(self, collection: str, origin: str, note: str = "") -> Receipt:
        """Drop a whole collection. Receipted; the audit row records the
        count of documents destroyed so nothing vanishes silently."""
        table = self._table(collection)
        _check_origin(origin)
        with self._atomic():
            self._ensure_collection(collection)
            count = self._conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            self._conn.execute(f'DROP TABLE "{table}"')
            return self._write_receipt(
                "drop-collection",
                collection,
                "",
                0,
                origin,
                note,
                {"documents_destroyed": int(count)},
            )

    @contextmanager
    def transaction(self) -> Iterator["ForgeStore"]:
        """Run several writes atomically: all commit or none do.

        Writes use savepoints internally, so an exception here rolls the
        whole batch back — including writes that already "succeeded"."""
        self._txn_depth += 1
        if self._txn_depth == 1 and not self._conn.in_transaction:
            # Explicit BEGIN so inner savepoints nest inside THIS
            # transaction — without it, a savepoint RELEASE auto-commits.
            self._conn.execute("BEGIN")
        try:
            yield self
        except Exception:
            # Only the outermost frame owns the rollback; a nested
            # failure propagates up and the outermost frame rolls back.
            if self._txn_depth == 1:
                self._conn.rollback()
            raise
        else:
            if self._txn_depth == 1:
                self._conn.commit()
        finally:
            self._txn_depth -= 1

    # -- reads -------------------------------------------------------------

    @staticmethod
    def _doc_row(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "doc_id": row["doc_id"],
            "data": json.loads(row["data"]),
            "revision": int(row["revision"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "origin": row["origin"],  # provenance rides with every record
            "note": row["note"],
        }

    def get(self, collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
        table = self._table(collection)
        _check_doc_id(doc_id)
        self._ensure_collection(collection)
        cur = self._conn.execute(f'SELECT * FROM "{table}" WHERE doc_id = ?', (doc_id,))
        row = cur.fetchone()
        return self._doc_row(row) if row is not None else None

    def list_collections(self) -> List[str]:
        cur = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'docs_%'"
        )
        return sorted(r[0][5:] for r in cur.fetchall())

    def count(self, collection: str) -> int:
        table = self._table(collection)
        self._ensure_collection(collection)
        return int(self._conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])

    @staticmethod
    def _field_value(doc: Dict[str, Any], field_name: str) -> Any:
        """Resolve a field against the decoded document (dotted paths allowed;
        the provenance columns are addressable too)."""
        if field_name in (
            "doc_id",
            "revision",
            "origin",
            "created_at",
            "updated_at",
            "note",
        ):
            return doc[field_name]
        cur: Any = doc["data"]
        for part in field_name.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return _MISSING
            cur = cur[part]
        return cur

    @classmethod
    def _cond_holds(cls, doc: Dict[str, Any], field_name: str, cond: Any) -> bool:
        value = cls._field_value(doc, field_name)
        items = list(cond.items()) if isinstance(cond, dict) else [("$eq", cond)]
        for op, want in items:
            if op == "$contains":
                if not isinstance(value, str) or str(want) not in value:
                    return False
            elif op == "$eq":
                if value is _MISSING or not _json_equal(value, want):
                    return False
            elif op == "$ne":
                if value is _MISSING or _json_equal(value, want):
                    return False
            elif op in ("$gt", "$gte", "$lt", "$lte"):
                if (
                    value is _MISSING
                    or isinstance(value, bool)
                    or isinstance(want, bool)
                ):
                    return False
                try:
                    ok = {
                        "$gt": value > want,
                        "$gte": value >= want,
                        "$lt": value < want,
                        "$lte": value <= want,
                    }[op]
                except TypeError:
                    return False
                if not ok:
                    return False
            else:
                raise StoreError(
                    f"query: unknown operator {op!r} "
                    "(use $eq $ne $gt $gte $lt $lte $contains)"
                )
        return True

    def query(
        self,
        collection: str,
        where: Optional[Dict[str, Any]] = None,
        order: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Query documents.

        ``where`` maps field -> value (equality) or field -> {op: value}
        with op in ``$eq $ne $gt $gte $lt $lte $contains``. Fields may be
        dotted paths into the document (e.g. ``"meta.status"``) or the
        provenance columns ``doc_id``, ``revision``, ``origin``.
        ``order`` is ``"field"`` or ``"-field"`` for descending.

        Two-stage and exact: SQL prefilters with JSON semantics, then every
        surviving row is re-verified in Python against the decoded document
        (SQLite flattens JSON ``true``/``false`` to 1/0 — the Python pass
        restores exact types). Order/limit/offset apply after verification.
        """
        table = self._table(collection)
        self._ensure_collection(collection)
        if limit is not None and (not isinstance(limit, int) or limit < 0):
            raise StoreError("query: limit must be a non-negative int")
        if offset is not None and (not isinstance(offset, int) or offset < 0):
            raise StoreError("query: offset must be a non-negative int")

        # Stage 1 — coarse SQL prefilter (superset: never drops a real match).
        sql = f'SELECT * FROM "{table}"'
        params: List[Any] = []
        PROVENANCE_COLS = {
            "doc_id",
            "revision",
            "origin",
            "created_at",
            "updated_at",
            "note",
        }

        def col_expr(field_name: str) -> str:
            if field_name in PROVENANCE_COLS:
                return f'"{field_name}"'
            if not isinstance(field_name, str) or not re.fullmatch(
                r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*", field_name
            ):
                raise StoreError(f"query: bad field name {field_name!r}")
            # json_quote() gives a canonical JSON text both sides can meet on.
            return f"json_quote(json_extract(data, '$.{field_name}'))"

        clauses: List[str] = []
        for field_name, cond in (where or {}).items():
            expr = col_expr(field_name)
            items = list(cond.items()) if isinstance(cond, dict) else [("$eq", cond)]
            for op, value in items:
                if op == "$contains":
                    if field_name in PROVENANCE_COLS:
                        clauses.append(f"{expr} LIKE ? ESCAPE '\\'")
                    else:
                        clauses.append(
                            f"json_extract(data, '$.{field_name}') LIKE ? ESCAPE '\\'"
                        )
                    params.append(
                        "%" + str(value).replace("\\", "\\\\").replace("%", "\\%") + "%"
                    )
                elif op in ("$eq", "$ne"):
                    # bool-tolerant: SQLite reads JSON true/false as 1/0.
                    is_col = field_name in PROVENANCE_COLS
                    if is_col:
                        param = value
                    elif value is True:
                        param = "1"
                    elif value is False:
                        param = "0"
                    else:
                        param = json.dumps(value)
                    clauses.append(f"{expr} {'=' if op == '$eq' else '!='} ?")
                    params.append(param)
                elif op in ("$gt", "$gte", "$lt", "$lte"):
                    clauses.append(f"{expr} {_OPERATORS[op]} ?")
                    params.append(
                        value if field_name in PROVENANCE_COLS else json.dumps(value)
                    )
                else:
                    raise StoreError(
                        f"query: unknown operator {op!r} "
                        "(use $eq $ne $gt $gte $lt $lte $contains)"
                    )
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        rows = [self._doc_row(r) for r in self._conn.execute(sql, params)]

        # Stage 2 — exact Python verification on decoded documents.
        if where:
            rows = [
                d
                for d in rows
                if all(self._cond_holds(d, f, c) for f, c in where.items())
            ]

        # Order / limit / offset on verified rows.
        if order:
            desc = order.startswith("-")
            key = order[1:] if desc else order
            if key not in PROVENANCE_COLS and not re.fullmatch(
                r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*", key
            ):
                raise StoreError(f"query: bad order field {key!r}")
            rows.sort(
                key=lambda d: (
                    self._field_value(d, key) is _MISSING,
                    repr(self._field_value(d, key)),
                ),
                reverse=desc,
            )
        if offset:
            rows = rows[offset:]
        if limit is not None:
            rows = rows[:limit]
        return rows

    # -- audit trail -------------------------------------------------------

    def audit_trail(
        self,
        collection: Optional[str] = None,
        op: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Read the append-only audit trail. Nothing is ever removed from it."""
        if op is not None and op not in _OPS:
            raise StoreError(f"audit_trail: unknown op {op!r}")
        sql = "SELECT * FROM _audit"
        clauses, params = [], []
        if collection is not None:
            _check_name(collection, "collection")
            clauses.append("collection = ?")
            params.append(collection)
        if op is not None:
            clauses.append("op = ?")
            params.append(op)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY seq ASC"
        if limit is not None:
            if not isinstance(limit, int) or limit < 0:
                raise StoreError("audit_trail: limit must be a non-negative int")
            sql += f" LIMIT {limit}"
        cur = self._conn.execute(sql, params)
        return [
            {
                "seq": r["seq"],
                "ts": r["ts"],
                "store": r["store"],
                "collection": r["collection"],
                "op": r["op"],
                "doc_id": r["doc_id"],
                "revision": r["revision"],
                "origin": r["origin"],
                "receipt_id": r["receipt_id"],
                "detail": json.loads(r["detail"]),
            }
            for r in cur.fetchall()
        ]

    def close(self) -> None:
        self._conn.close()


def open_store(name: str, home: "str | os.PathLike[str] | None" = None) -> ForgeStore:
    """Open (creating if needed) a named forge data store."""
    return ForgeStore(name, home=home)

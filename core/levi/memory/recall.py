"""FTS5 + BM25 full-text recall for LEVI's local stores.

One portable ``recall.db`` indexes the memory store, the growth journal,
and any ad-hoc document sets — all through SQLite FTS5, which ships in
Python's stdlib ``sqlite3``. No dependencies, no network, no restructuring
of anyone else's schema: every source is read, never rewritten.

Honest-degradation contract (fail-closed, never raises on missing data):

- ``search()`` on a store whose index was never built returns ``([], "not-indexed")``.
- A source that is missing (no memory dir, no journal file) is skipped and
  counted in the index report instead of crashing the build.
- A malformed query returns ``([], "bad-query")`` instead of an exception.

Public API: :class:`RecallIndex` — ``index_all()`` / ``search()`` / ``rebuild()``.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5(
    doc_id UNINDEXED,
    source UNINDEXED,
    title,
    body,
    tags,
    tokenize = 'porter'
)
"""

# Reasons are short stable strings callers can branch on.
NOT_INDEXED = "not-indexed"
EMPTY_QUERY = "empty-query"
BAD_QUERY = "bad-query"
NO_DOCS = "no-documents-indexed"

# Markers used by snippet(); plain text so results render anywhere.
_SNIP_OPEN = "<<"
_SNIP_CLOSE = ">>"


@dataclass
class RecallResult:
    """One ranked hit from :meth:`RecallIndex.search`."""

    doc_id: str
    source: str
    title: str
    snippet: str
    score: float
    extra: Dict[str, str] = field(default_factory=dict)


class RecallIndex:
    """Read-only-until-you-say-so FTS5 index over LEVI's local stores.

    The index database lives at ``~/.levi/memory/recall.db`` (overrideable).
    LEVI_HOME is honored for the default; ``memory_dir`` override is used by
    tests. All failures are reported as ``(results, reason)`` tuples — the
    class never raises on missing/corrupt source data.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        memory_dir: Optional[Path] = None,
        journal_path: Optional[Path] = None,
    ) -> None:
        if db_path is not None:
            self.db_path = Path(db_path)
        else:
            import os

            home = Path(os.environ.get("LEVI_HOME", str(Path.home() / ".levi")))
            self.db_path = home / "memory" / "recall.db"
        self.memory_dir = Path(memory_dir) if memory_dir is not None else None
        self.journal_path = Path(journal_path) if journal_path is not None else None
        self.last_report: Dict[str, object] = {}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _has_table(self, conn: sqlite3.Connection) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type IN ('table','view')"
            " AND name = 'docs'"
        ).fetchone()
        return row is not None

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(_SCHEMA)

    def _touch_db_dir(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Indexing (writes)
    # ------------------------------------------------------------------

    def add_documents(
        self, docs: Sequence[Dict[str, str]], source: str = "adhoc"
    ) -> int:
        """Index a batch of ad-hoc documents. Returns the number indexed.

        Each doc is a mapping with at least ``doc_id`` and ``body``; ``title``
        and ``tags`` are optional. Bad entries are skipped, not fatal.
        """
        if not docs:
            return 0
        self._touch_db_dir()
        indexed = 0
        with self._connect() as conn:
            self._ensure_schema(conn)
            for doc in docs:
                if not isinstance(doc, dict):
                    continue
                doc_id = doc.get("doc_id")
                body = doc.get("body")
                if not isinstance(doc_id, str) or not doc_id.strip():
                    continue
                if not isinstance(body, str) or not body.strip():
                    continue
                title = doc.get("title") or ""
                tags = doc.get("tags") or ""
                if not isinstance(title, str):
                    title = str(title)
                if isinstance(tags, (list, tuple)):
                    tags = " ".join(str(t) for t in tags)
                elif not isinstance(tags, str):
                    tags = str(tags)
                try:
                    conn.execute("DELETE FROM docs WHERE doc_id = ?", (doc_id,))
                    conn.execute(
                        "INSERT INTO docs (doc_id, source, title, body, tags)"
                        " VALUES (?, ?, ?, ?, ?)",
                        (doc_id, source, title, body, tags),
                    )
                except sqlite3.Error:
                    continue
                indexed += 1
            conn.commit()
        return indexed

    def index_memory_store(self, limit: int = 5000) -> Dict[str, object]:
        """Index memory entries through the store's public API. Read-only.

        Never raises: a missing store or unreadable dir yields a zero-count
        report with a ``reason``.
        """
        report: Dict[str, object] = {"indexed": 0, "skipped": 0}
        try:
            from .store import MemoryStore

            store = MemoryStore(
                data_dir=self.memory_dir if self.memory_dir is not None else None
            )
            entries = store.list(limit=limit)
        except Exception as exc:  # store constructor/_load is fail-soft already
            report["reason"] = "memory-store-unavailable: %s" % exc
            return report
        docs = []
        for entry in entries:
            try:
                body = "%s %s" % (entry.content or "", entry.source or "")
                docs.append(
                    {
                        "doc_id": "memory:%s" % entry.id,
                        "title": "memory %s" % entry.memory_type.value,
                        "body": body,
                        "tags": entry.tags or [],
                    }
                )
            except Exception:
                report["skipped"] = int(report["skipped"]) + 1
        report["indexed"] = self.add_documents(docs, source="memory")
        return report

    def index_growth_journal(self, limit: int = 20000) -> Dict[str, object]:
        """Index growth journal lines (JSONL, append-only). Read-only."""
        report: Dict[str, object] = {"indexed": 0, "skipped": 0}
        path = self.journal_path
        if path is None:
            import os

            base = os.environ.get("LEVI_GROWTH_DIR")
            path = (
                Path(base).expanduser() if base else Path.home() / ".levi" / "growth"
            ) / ("journal.jsonl")
        if not path.exists():
            report["reason"] = "journal-not-found: %s" % path
            return report
        docs = []
        try:
            with path.open(encoding="utf-8") as fh:
                for line in fh:
                    if len(docs) >= limit:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except (ValueError, TypeError):
                        report["skipped"] = int(report["skipped"]) + 1
                        continue
                    if not isinstance(rec, dict):
                        report["skipped"] = int(report["skipped"]) + 1
                        continue
                    body = self._journal_body(rec)
                    if not body.strip():
                        report["skipped"] = int(report["skipped"]) + 1
                        continue
                    docs.append(
                        {
                            "doc_id": "journal:%s" % (rec.get("id") or "?"),
                            "title": "growth journal %s" % (rec.get("cycle") or ""),
                            "body": body,
                            "tags": "",
                        }
                    )
        except OSError as exc:
            report["reason"] = "journal-unreadable: %s" % exc
            return report
        report["indexed"] = self.add_documents(docs, source="journal")
        return report

    _JOURNAL_ID_KEYS = frozenset(
        {"id", "ts", "cycle_id", "memory_entry_id", "bus_published", "quiet"}
    )

    @classmethod
    def _journal_body(cls, rec: Dict[str, object]) -> str:
        # Generic: index every human-readable scalar/list value, skipping
        # id/timestamp plumbing. Unknown future keys still get indexed.
        parts = []
        for key, val in rec.items():
            if key in cls._JOURNAL_ID_KEYS:
                continue
            if isinstance(val, str) and val.strip():
                parts.append(val)
            elif isinstance(val, (list, tuple)):
                parts.extend(str(v) for v in val if isinstance(v, str) and v.strip())
            elif isinstance(val, (int, float, bool)):
                parts.append("%s=%s" % (key, val))
        return "\n".join(parts)

    def index_all(self) -> Dict[str, object]:
        """Index every known local source. Never raises."""
        report = {
            "memory": self.index_memory_store(),
            "journal": self.index_growth_journal(),
        }
        self.last_report = report
        return report

    def rebuild(self) -> Dict[str, object]:
        """Drop the index and build it fresh. Never raises."""
        try:
            if self.db_path.exists():
                self.db_path.unlink()
        except OSError:
            pass
        return self.index_all()

    # ------------------------------------------------------------------
    # Search (reads)
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        limit: int = 10,
        source: Optional[str] = None,
    ) -> Tuple[List[RecallResult], Optional[str]]:
        """Full-text search with BM25 ranking.

        Returns ``(results, reason)``. ``reason`` is ``None`` when results were
        produced normally, or one of the module constants when the call
        degraded honestly. Never raises.
        """
        if not isinstance(query, str) or not query.strip():
            return [], EMPTY_QUERY
        if not isinstance(limit, int) or limit < 1:
            limit = 10
        try:
            if not self.db_path.exists():
                return [], NOT_INDEXED
            with self._connect() as conn:
                if not self._has_table(conn):
                    return [], NOT_INDEXED
                count = conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
                if count == 0:
                    return [], NO_DOCS
                sql = (
                    "SELECT doc_id, source, title,"
                    " snippet(docs, 3, ?, ?, ' ... ', 20),"
                    " bm25(docs) AS rank"
                    " FROM docs WHERE docs MATCH ?"
                )
                params: List[object] = [_SNIP_OPEN, _SNIP_CLOSE, query]
                if source is not None:
                    sql += " AND source = ?"
                    params.append(source)
                sql += " ORDER BY rank LIMIT ?"
                params.append(limit)
                rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            # Malformed FTS5 query syntax — honest, not fatal.
            return [], BAD_QUERY
        except (sqlite3.Error, OSError):
            return [], NOT_INDEXED
        results = [
            RecallResult(
                doc_id=str(doc_id),
                source=str(src),
                title=str(title or ""),
                snippet=str(snippet or ""),
                score=float(rank),
            )
            for doc_id, src, title, snippet, rank in rows
        ]
        return results, None

    def stats(self) -> Dict[str, object]:
        """Index health summary. Never raises."""
        try:
            if not self.db_path.exists():
                return {"indexed": False, "documents": 0, "db": str(self.db_path)}
            with self._connect() as conn:
                if not self._has_table(conn):
                    return {"indexed": False, "documents": 0, "db": str(self.db_path)}
                count = conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
                by_source = {
                    row[0]: row[1]
                    for row in conn.execute(
                        "SELECT source, COUNT(*) FROM docs GROUP BY source"
                    ).fetchall()
                }
            return {
                "indexed": True,
                "documents": count,
                "by_source": by_source,
                "db": str(self.db_path),
            }
        except (sqlite3.Error, OSError):
            return {"indexed": False, "documents": 0, "db": str(self.db_path)}

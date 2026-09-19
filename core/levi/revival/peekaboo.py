"""Optical coincidence: the inverted index made physical, done with sets.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #10)

The load-bearing mechanism: invert the index. Instead of one card per
document listing its terms, keep one *term-record* per term listing the
documents where it occurs. To search, stack the term-records — the
positions that line up through the whole stack are the documents
containing every term. Boolean AND, computed by coincidence.

Here the stacking is set intersection, and the intermediate stack is
inspectable: :meth:`PeekABooDeck.stack` returns each stage of the
coincidence so you can watch the candidate set shrink as term-records
pile on — the digital light-table.

This is an original, from-scratch LEVI implementation — no historical
code is used or copied. Stdlib only, no network.

Honesty: the mechanism revived is term-record stacking as intersection.
Not revived: physical cards, punched positions, or capacity ceilings.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


ORIGIN = "levi-revival/peekaboo"


_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Document-derived word tokens: lowercase alphanumerics, in order,
    duplicates kept (the posting records positions too)."""
    return _TOKEN.findall(text.lower())


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PeekABooError(Exception):
    """Base class for peek-a-boo failures."""


class UnknownDocument(PeekABooError):
    """The document is not posted in the deck."""


# ---------------------------------------------------------------------------
# The deck: one term-record per term
# ---------------------------------------------------------------------------


class PeekABooDeck:
    """A file of term-records. Each record names one term and lists the
    documents where it occurs."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.docs: dict[str, str] = {}  # doc_id -> title
        self.records: dict[str, dict[str, list[int]]] = {}
        # term -> {doc_id: [positions]} — the punched positions on the card
        if self.path is not None:
            self._load()

    # -- persistence ------------------------------------------------------
    def _file(self) -> Path:
        assert self.path is not None
        return self.path / "peekaboo.json"

    def _load(self) -> None:
        f = self._file()
        if not f.exists():
            return
        data = json.loads(f.read_text(encoding="utf-8"))
        self.docs = dict(data.get("docs", {}))
        self.records = {
            term: {doc: list(pos) for doc, pos in postings.items()}
            for term, postings in data.get("records", {}).items()
        }

    def save(self) -> Path:
        """Persist the deck. Only meaningful when constructed with a path."""
        if self.path is None:
            raise PeekABooError("no path: this deck is in-memory only")
        self.path.mkdir(parents=True, exist_ok=True)
        target = self._file()
        tmp = target.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {"docs": self.docs, "records": self.records},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        tmp.replace(target)
        return target

    # -- posting: punch document positions onto term-records ---------------
    def post(self, doc_id: str, text: str, title: str = "") -> int:
        """Punch a document's term positions onto the term-records. Returns
        the number of distinct terms posted."""
        if not doc_id or not doc_id.strip():
            raise ValueError("doc_id must be non-empty")
        self.docs[doc_id] = title or doc_id
        seen: set[str] = set()
        for position, term in enumerate(tokenize(text)):
            postings = self.records.setdefault(term, {})
            postings.setdefault(doc_id, []).append(position)
            seen.add(term)
        return len(seen)

    def remove(self, doc_id: str) -> None:
        """Withdraw a document: erase its positions from every term-record."""
        if doc_id not in self.docs:
            raise UnknownDocument(doc_id)
        del self.docs[doc_id]
        for postings in self.records.values():
            postings.pop(doc_id, None)

    # -- reading a term-record ---------------------------------------------
    def term_record(self, term: str) -> list[str]:
        """The documents punched on one term's record, sorted."""
        return sorted(self.records.get(term, {}))

    def term_positions(self, term: str, doc_id: str) -> list[int]:
        """Where on the term-record a document's punches sit."""
        return list(self.records.get(term, {}).get(doc_id, []))

    def terms(self) -> list[str]:
        """Every term with a record on file."""
        return sorted(self.records)

    # -- stacking: the optical coincidence ----------------------------------
    def stack(self, terms: list[str]) -> dict:
        """Stack term-records in order and watch the coincidence shrink.

        Returns ``{"stages": [...], "coincidence": [...]}`` where each
        stage is ``{"term": t, "record": [...], "still_lit": [...]}`` —
        the documents that survive stacking that record on top of the
        ones below. ``still_lit`` is the set of positions where light
        shines through every card stacked so far."""
        stages = []
        lit: set[str] | None = None
        for term in terms:
            record = self.term_record(term)
            lit = set(record) if lit is None else (lit & set(record))
            stages.append(
                {
                    "term": term,
                    "record": record,
                    "still_lit": sorted(lit),
                }
            )
        return {"stages": stages, "coincidence": sorted(lit) if lit else []}

    def coincide(self, terms: list[str]) -> list[str]:
        """The coincidence directly: documents containing every term."""
        return self.stack(terms)["coincidence"]

    def doc_count(self) -> int:
        return len(self.docs)


__all__ = [
    "ORIGIN",
    "PeekABooError",
    "UnknownDocument",
    "PeekABooDeck",
    "tokenize",
]

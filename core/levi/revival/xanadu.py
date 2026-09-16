"""Xanadu/Memex revival: transclusion + associative trails.

Ted Nelson's Xanadu never copied text — it *transcluded* it: every quote
was a live pointer back to the original document and span, with full
provenance. Vannevar Bush's Memex added *trails*: associative paths a
reader could walk through linked documents.

Two parts, both JSON-persisted and stdlib-only:

(a) ``Transclusion`` — references as ``(doc_id, span)`` links.
    ``quote(doc_id, start, end)`` returns the referenced text *with
    provenance* — text is never handed out without attribution. A
    transclusion set tracks which documents quote which (``quoted_by`` /
    ``quotes``), so every document knows where it is being cited.

(b) ``Trail`` — an ordered sequence of document links with annotations.
    ``follow_trail(trail_id)`` walks the documents in order, yielding
    ``(doc, annotation)`` pairs. Trails persist as JSON under
    ``~/.levi/trails/`` (overridable for hermetic tests).

Additive RAG integration: ``trail_from_citations`` builds a trail from
the citation ids of a ``levi.rag`` ``ask()`` result, and
``ask_and_trail`` runs the pipeline and builds the trail in one call.
Both degrade honestly — if ``levi.rag`` is unavailable they say so
instead of faking citations.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple


# --------------------------------------------------------------------------
# Documents
# --------------------------------------------------------------------------


@dataclass
class Document:
    doc_id: str
    title: str
    text: str
    added_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def span(self, start: int, end: int) -> str:
        if not isinstance(start, int) or not isinstance(end, int):
            raise TypeError("xanadu: span bounds must be ints")
        if not (0 <= start < end <= len(self.text)):
            raise ValueError(
                "xanadu: span [%d:%d) out of range for document %r (len %d)"
                % (start, end, self.doc_id, len(self.text))
            )
        return self.text[start:end]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "text": self.text,
            "added_at": self.added_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Document":
        return cls(
            doc_id=data["doc_id"],
            title=data.get("title", data["doc_id"]),
            text=data["text"],
            added_at=data.get("added_at", ""),
        )


class DocStore:
    """Small persistent document corpus that transclusions point at."""

    def __init__(self, path: Optional[Path] = None):
        self._docs: Dict[str, Document] = {}
        self._path = Path(path) if path else None

    def add(self, doc_id: str, text: str, title: Optional[str] = None) -> Document:
        if not isinstance(doc_id, str) or not doc_id.strip():
            raise ValueError("xanadu: doc_id must be a non-empty string")
        if not isinstance(text, str) or not text:
            raise ValueError("xanadu: text must be a non-empty string")
        doc = Document(doc_id=doc_id, title=title or doc_id, text=text)
        self._docs[doc_id] = doc
        return doc

    def get(self, doc_id: str) -> Document:
        try:
            return self._docs[doc_id]
        except KeyError:
            raise KeyError("xanadu: unknown document %r" % doc_id)

    def list_docs(self) -> List[Document]:
        return list(self._docs.values())

    def save(self, path: Optional[Path] = None) -> Path:
        target = Path(path) if path else self._path
        if target is None:
            raise ValueError("xanadu: no path to save documents to")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                [d.to_dict() for d in self._docs.values()], indent=2, ensure_ascii=False
            ),
            encoding="utf-8",
        )
        tmp.replace(target)
        self._path = target
        return target

    @classmethod
    def load(cls, path: Path) -> "DocStore":
        store = cls(path=path)
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        for item in raw:
            doc = Document.from_dict(item)
            store._docs[doc.doc_id] = doc
        return store


# --------------------------------------------------------------------------
# Transclusion
# --------------------------------------------------------------------------


@dataclass
class Quote:
    """Referenced text WITH provenance. Never construct bare text from this."""

    text: str
    doc_id: str
    span: Tuple[int, int]
    title: str

    def citation(self) -> str:
        start, end = self.span
        return "“%s” — %s [%s:%d–%d]" % (self.text, self.title, self.doc_id, start, end)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "doc_id": self.doc_id,
            "span": [self.span[0], self.span[1]],
            "title": self.title,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Quote":
        span = data["span"]
        return cls(
            text=data["text"],
            doc_id=data["doc_id"],
            span=(int(span[0]), int(span[1])),
            title=data.get("title", data["doc_id"]),
        )


class Transclusion:
    """Transclusion engine: quote by reference, track who quotes whom."""

    def __init__(self, docs: DocStore):
        self.docs = docs
        # quoting doc_id -> set of quoted doc_ids
        self._quotes: Dict[str, set] = {}
        # quoted doc_id -> set of quoting doc_ids
        self._quoted_by: Dict[str, set] = {}

    def quote(self, doc_id: str, start: int, end: int) -> Quote:
        """Return the referenced text with provenance (never unattributed)."""
        doc = self.docs.get(doc_id)  # KeyError if unknown — honest
        return Quote(
            text=doc.span(start, end), doc_id=doc_id, span=(start, end), title=doc.title
        )

    def transclude(
        self, quoter_doc_id: str, target_doc_id: str, start: int, end: int
    ) -> Quote:
        """Record that ``quoter_doc_id`` quotes a span of ``target_doc_id``.

        The quote text stays owned by the target document; only the
        *link* is recorded. Both documents must exist.
        """
        self.docs.get(quoter_doc_id)
        q = self.quote(target_doc_id, start, end)
        self._quotes.setdefault(quoter_doc_id, set()).add(target_doc_id)
        self._quoted_by.setdefault(target_doc_id, set()).add(quoter_doc_id)
        return q

    def quotes(self, doc_id: str) -> List[str]:
        """Doc ids that ``doc_id`` transcludes."""
        return sorted(self._quotes.get(doc_id, ()))

    def quoted_by(self, doc_id: str) -> List[str]:
        """Doc ids that transclude ``doc_id``."""
        return sorted(self._quoted_by.get(doc_id, ()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quotes": {k: sorted(v) for k, v in self._quotes.items()},
            "quoted_by": {k: sorted(v) for k, v in self._quoted_by.items()},
        }

    @classmethod
    def from_dict(cls, docs: DocStore, data: Dict[str, Any]) -> "Transclusion":
        t = cls(docs)
        t._quotes = {k: set(v) for k, v in data.get("quotes", {}).items()}
        t._quoted_by = {k: set(v) for k, v in data.get("quoted_by", {}).items()}
        return t


# --------------------------------------------------------------------------
# Trails
# --------------------------------------------------------------------------


def _default_trail_dir() -> Path:
    return Path(os.path.expanduser("~")) / ".levi" / "trails"


@dataclass
class TrailStop:
    doc_id: str
    annotation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"doc_id": self.doc_id, "annotation": self.annotation}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrailStop":
        return cls(doc_id=data["doc_id"], annotation=data.get("annotation", ""))


class Trail:
    """An ordered associative path through documents, with annotations."""

    def __init__(self, trail_id: str, name: str):
        if not trail_id or not isinstance(trail_id, str):
            raise ValueError("xanadu: trail_id must be a non-empty string")
        self.trail_id = trail_id
        self.name = name or trail_id
        self.stops: List[TrailStop] = []
        self.created_at = datetime.now(timezone.utc).isoformat()

    def add_stop(self, doc_id: str, annotation: str = "") -> "Trail":
        if not isinstance(doc_id, str) or not doc_id:
            raise ValueError("xanadu: doc_id must be a non-empty string")
        self.stops.append(TrailStop(doc_id=doc_id, annotation=annotation))
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trail_id": self.trail_id,
            "name": self.name,
            "created_at": self.created_at,
            "stops": [s.to_dict() for s in self.stops],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Trail":
        t = cls(data["trail_id"], data.get("name", data["trail_id"]))
        t.created_at = data.get("created_at", t.created_at)
        t.stops = [TrailStop.from_dict(s) for s in data.get("stops", [])]
        return t


class TrailStore:
    """Persistent trail collection. Walk a trail with ``follow_trail``."""

    def __init__(self, docs: DocStore, trail_dir: Optional[Path] = None):
        self.docs = docs
        self.trail_dir = Path(trail_dir) if trail_dir else _default_trail_dir()
        self._trails: Dict[str, Trail] = {}
        self._load()

    def _path_for(self, trail_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in trail_id)
        return self.trail_dir / ("%s.json" % safe)

    def _load(self) -> None:
        if not self.trail_dir.is_dir():
            return
        for path in sorted(self.trail_dir.glob("*.json")):
            try:
                trail = Trail.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError, KeyError):
                continue  # skip unreadable trail files; never crash the store
            self._trails[trail.trail_id] = trail

    def create(self, trail_id: str, name: str) -> Trail:
        if trail_id in self._trails:
            raise ValueError("xanadu: trail %r already exists" % trail_id)
        trail = Trail(trail_id, name)
        self._trails[trail_id] = trail
        return trail

    def get(self, trail_id: str) -> Trail:
        try:
            return self._trails[trail_id]
        except KeyError:
            raise KeyError("xanadu: unknown trail %r" % trail_id)

    def list_trails(self) -> List[Trail]:
        return list(self._trails.values())

    def save(self, trail_id: str) -> Path:
        trail = self.get(trail_id)
        self.trail_dir.mkdir(parents=True, exist_ok=True)
        target = self._path_for(trail_id)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(trail.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        tmp.replace(target)
        return target

    def delete(self, trail_id: str) -> None:
        trail = self.get(trail_id)
        del self._trails[trail_id]
        try:
            self._path_for(trail_id).unlink()
        except OSError:
            pass

    def follow_trail(self, trail_id: str) -> Iterator[Tuple[Document, str]]:
        """Walk the trail in order, yielding (document, annotation) pairs.

        Raises ``KeyError`` for missing trails or missing documents —
        a trail never silently skips a broken link.
        """
        trail = self.get(trail_id)
        for stop in trail.stops:
            yield self.docs.get(stop.doc_id), stop.annotation


# --------------------------------------------------------------------------
# Additive RAG integration (lazy import, honest degradation)
# --------------------------------------------------------------------------


def trail_from_citations(
    store: TrailStore,
    trail_id: str,
    name: str,
    citations: List[str],
    annotations: Optional[Dict[str, str]] = None,
) -> Trail:
    """Build a trail from a list of cited doc ids (e.g. from rag ask())."""
    trail = store.create(trail_id, name)
    annotations = annotations or {}
    for doc_id in citations:
        trail.add_stop(doc_id, annotations.get(doc_id, ""))
    store.save(trail_id)
    return trail


def ask_and_trail(
    query: str,
    rag_store: Any,
    trail_store: TrailStore,
    trail_id: str,
    name: str,
    limit: int = 5,
) -> Tuple[Any, Trail]:
    """Run ``levi.rag`` ask() and turn its citations into a trail.

    Returns ``(ask_result, trail)``. If the rag module is unavailable,
    raises ``RuntimeError`` with a plain explanation — citations are
    never fabricated.
    """
    try:
        from levi.rag.pipeline import ask  # lazy import
    except ImportError as exc:
        raise RuntimeError(
            "xanadu: levi.rag is unavailable (%s); cannot build a trail "
            "from RAG citations" % exc
        )
    result = ask(query, rag_store, limit=limit, generate=False)
    if not result.citations:
        raise RuntimeError(
            "xanadu: rag ask() returned no citations for %r (notice: %s)"
            % (query, result.notice)
        )
    trail = trail_from_citations(trail_store, trail_id, name, result.citations)
    return result, trail


# --------------------------------------------------------------------------
# Demo
# --------------------------------------------------------------------------


def demo() -> None:
    """Ingest two docs, transclude a quote, build a trail, follow it."""
    docs = DocStore()
    docs.add(
        "memex-1945",
        "Wholly new forms of encyclopedias will appear, ready made with "
        "a mesh of associative trails running through them.",
        title="As We May Think (1945)",
    )
    docs.add(
        "xanadu-1965",
        "Let me introduce the word 'hypertext' to mean a body of written "
        "or pictorial material interconnected in such a complex way that "
        "it could not conveniently be presented on paper.",
        title="Complex Information Processing (1965)",
    )
    trans = Transclusion(docs)
    q = trans.transclude("xanadu-1965", "memex-1945", 0, 38)
    print("transclusion:", q.citation())
    print("xanadu-1965 quotes:", trans.quotes("xanadu-1965"))
    print("memex-1945 quoted by:", trans.quoted_by("memex-1945"))

    trails = TrailStore(docs)
    trail = trails.create("associative-trails", "How trails became hypertext")
    trail.add_stop("memex-1945", "Bush proposes associative trails through knowledge.")
    trail.add_stop("xanadu-1965", "Nelson names the interconnection: hypertext.")
    print("\nfollowing trail %r:" % trail.trail_id)
    for i, (doc, annotation) in enumerate(trails.follow_trail(trail.trail_id), 1):
        print("  %d. [%s] %s — %s" % (i, doc.doc_id, doc.title, annotation))


if __name__ == "__main__":
    demo()


__all__ = [
    "Document",
    "DocStore",
    "Quote",
    "Transclusion",
    "TrailStop",
    "Trail",
    "TrailStore",
    "trail_from_citations",
    "ask_and_trail",
    "demo",
]

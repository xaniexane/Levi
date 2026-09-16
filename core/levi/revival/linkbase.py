"""LEVI's memory link layer: separate, bidirectional, auto-maintained links.

Inspired by two dead hypermedia systems. Hyper-G (TU Graz / Hermann
Maurer, early–mid 1990s; commercialized as HyperWave): *links stored
separately from documents* in a link database — links were bidirectional
("bivisible, bifollowable"), auto-maintained (no dangling links), and
users could annotate documents they didn't own; built-in distributed
search. Microcosm (University of Southampton, 1989; Fountain et al.):
*open hypermedia* — linkbases separate from documents; specific, local,
and **generic** links (a term links everywhere it appears, in any
document); links dispatch applications. Both lost to the Web's embedded
one-way links.

Remix delta: open hypermedia reimagined as LEVI's *memory link layer* —
not a hypermedia-system clone. The link graph lives apart from
documents; renames auto-update links; deletions quarantine links (never
silently drop); generic links bind a term so every occurrence becomes a
live link — the assistant's glossary layer. Complementary to
revival.xanadu's trails by design: trails are journeys, linkbases are
territory. No distributed search, no application dispatching; the
load-bearing mechanism is bidirectionality with auto-maintenance.

This is an original, from-scratch reimplementation for LEVI — no
Hyper-G/Microcosm code is used. A ``LinkBase`` keeps the link graph
*apart from* the documents: links are first-class records with source,
target, kind, and note; every link is traversable in both directions;
renaming a document auto-updates its links; deleting a document
quarantines (never silently drops) the affected links; and *generic*
links bind a term to a target so every occurrence of the term — in any
document — becomes a live link (the assistant's glossary layer).

Relationship to :mod:`levi.revival.xanadu` — complementary, not
duplicative: xanadu's ``Trail`` is an *ordered associative path* through
documents (a walk you take); the linkbase is the *underlying bidirectional
web* (the graph you query: "what references this document?"). Trails are
journeys; linkbases are territory.

Persistence: JSON under an explicit path (default ``~/.levi/linkbase/``).

Honesty: LOAD-BEARING — bidirectional, auto-maintained links over local
documents. What is NOT revived: Hyper-G's distributed search and
Harmony client, Microcosm's application-dispatching viewers.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class LinkbaseError(Exception):
    """Base class for linkbase failures."""


class UnknownDocument(LinkbaseError):
    """The document is not registered in the linkbase."""


class UnknownLink(LinkbaseError):
    """No link with that id."""


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------


@dataclass
class Link:
    """One link, stored separately from the documents it connects."""

    link_id: str
    src: str
    dst: str
    kind: str = "ref"  # ref | generic | annotation
    note: str = ""
    created_at: float = field(default_factory=time.time)

    def other_end(self, doc_id: str) -> str:
        if doc_id == self.src:
            return self.dst
        if doc_id == self.dst:
            return self.src
        raise ValueError(f"document {doc_id!r} is not on link {self.link_id!r}")

    def to_dict(self) -> dict:
        return {
            "link_id": self.link_id,
            "src": self.src,
            "dst": self.dst,
            "kind": self.kind,
            "note": self.note,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Link":
        return cls(
            data["link_id"],
            data["src"],
            data["dst"],
            data.get("kind", "ref"),
            data.get("note", ""),
            data.get("created_at", 0.0),
        )


# ---------------------------------------------------------------------------
# LinkBase
# ---------------------------------------------------------------------------


class LinkBase:
    """The separate link layer over a registered document set."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else Path.home() / ".levi" / "linkbase"
        self.docs: dict[str, str] = {}  # doc_id -> title
        self._links: dict[str, Link] = {}
        self._dangling: dict[str, Link] = {}  # quarantined, never dropped
        self._generics: dict[str, dict] = {}  # term -> {"target", "note"}
        self._counter = 0
        self._load()

    # -- persistence ------------------------------------------------------------
    def _file(self) -> Path:
        return self.path / "linkbase.json"

    def _load(self) -> None:
        f = self._file()
        if not f.exists():
            return
        data = json.loads(f.read_text(encoding="utf-8"))
        self.docs = dict(data.get("docs", {}))
        self._counter = int(data.get("counter", 0))
        self._links = {d["link_id"]: Link.from_dict(d) for d in data.get("links", [])}
        self._dangling = {
            d["link_id"]: Link.from_dict(d) for d in data.get("dangling", [])
        }
        self._generics = dict(data.get("generics", {}))

    def save(self) -> Path:
        self.path.mkdir(parents=True, exist_ok=True)
        target = self._file()
        tmp = target.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {
                    "docs": self.docs,
                    "counter": self._counter,
                    "links": [l.to_dict() for l in self._links.values()],
                    "dangling": [l.to_dict() for l in self._dangling.values()],
                    "generics": self._generics,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        tmp.replace(target)
        return target

    # -- documents ------------------------------------------------------------------
    def register_doc(self, doc_id: str, title: str = "") -> None:
        if not doc_id or not doc_id.strip():
            raise ValueError("doc_id must be non-empty")
        self.docs[doc_id] = title or doc_id

    def rename_doc(self, old_id: str, new_id: str) -> int:
        """Rename a document: every link follows automatically (no
        dangling links). Returns the number of links updated."""
        if old_id not in self.docs:
            raise UnknownDocument(old_id)
        if not new_id or not new_id.strip():
            raise ValueError("new doc_id must be non-empty")
        if new_id in self.docs:
            raise ValueError(f"document {new_id!r} already registered")
        self.docs[new_id] = self.docs.pop(old_id)
        updated = 0
        for link in self._links.values():
            if link.src == old_id:
                link.src = new_id
                updated += 1
            if link.dst == old_id:
                link.dst = new_id
                updated += 1
        for term, gen in self._generics.items():
            if gen["target"] == old_id:
                gen["target"] = new_id
        return updated

    def delete_doc(self, doc_id: str) -> list[Link]:
        """Delete a document: affected links are quarantined to the
        dangling list (returned) — never silently dropped."""
        if doc_id not in self.docs:
            raise UnknownDocument(doc_id)
        del self.docs[doc_id]
        quarantined = [
            l for l in self._links.values() if l.src == doc_id or l.dst == doc_id
        ]
        for link in quarantined:
            del self._links[link.link_id]
            self._dangling[link.link_id] = link
        return quarantined

    def repair_dangling(self, link_id: str, new_target: str) -> Link:
        """Re-point a quarantined link at a live document."""
        try:
            link = self._dangling.pop(link_id)
        except KeyError:
            raise UnknownLink(link_id) from None
        if new_target not in self.docs:
            self._dangling[link_id] = link  # put it back; still quarantined
            raise UnknownDocument(new_target)
        # Re-point whichever end dangles (the deleted document's end).
        if link.src not in self.docs and link.dst not in self.docs:
            self._dangling[link_id] = link
            raise LinkbaseError("both ends of the link dangle; cannot repair")
        if link.src not in self.docs:
            link.src = new_target
        else:
            link.dst = new_target
        self._links[link_id] = link
        return link

    def dangling(self) -> list[Link]:
        return list(self._dangling.values())

    # -- links ------------------------------------------------------------------------
    def add_link(self, src: str, dst: str, kind: str = "ref", note: str = "") -> Link:
        """Create a link. Both documents must be registered (deny-closed);
        self-links are refused."""
        if src not in self.docs:
            raise UnknownDocument(f"link source {src!r} is not registered")
        if dst not in self.docs:
            raise UnknownDocument(f"link target {dst!r} is not registered")
        if src == dst:
            raise LinkbaseError("self-links are refused")
        if kind not in ("ref", "generic", "annotation"):
            raise ValueError(f"unknown link kind {kind!r}")
        self._counter += 1
        link = Link(link_id=f"l{self._counter}", src=src, dst=dst, kind=kind, note=note)
        self._links[link.link_id] = link
        return link

    def remove_link(self, link_id: str) -> None:
        try:
            del self._links[link_id]
        except KeyError:
            raise UnknownLink(link_id) from None

    def get_link(self, link_id: str) -> Link:
        try:
            return self._links[link_id]
        except KeyError:
            raise UnknownLink(link_id) from None

    # -- bidirectional traversal ------------------------------------------------------------
    def links_from(self, doc_id: str) -> list[Link]:
        self._require_doc(doc_id)
        return [l for l in self._links.values() if l.src == doc_id]

    def links_to(self, doc_id: str) -> list[Link]:
        self._require_doc(doc_id)
        return [l for l in self._links.values() if l.dst == doc_id]

    def neighbors(self, doc_id: str) -> list[str]:
        """Every document linked to ``doc_id`` in either direction —
        the "what references this document?" answer."""
        self._require_doc(doc_id)
        seen: dict[str, None] = {}
        for link in self._links.values():
            if link.src == doc_id:
                seen.setdefault(link.dst)
            elif link.dst == doc_id:
                seen.setdefault(link.src)
        return sorted(seen)

    def _require_doc(self, doc_id: str) -> None:
        if doc_id not in self.docs:
            raise UnknownDocument(doc_id)

    # -- generic links (Microcosm): a term links everywhere it appears ------------------------------
    def define_generic(self, term: str, target_doc: str, note: str = "") -> None:
        """Bind ``term`` to ``target_doc``: every occurrence of the term in
        any document becomes a live link to the target."""
        if not term or not term.strip():
            raise ValueError("term must be non-empty")
        if target_doc not in self.docs:
            raise UnknownDocument(target_doc)
        self._generics[term.strip()] = {"target": target_doc, "note": note}

    def undefine_generic(self, term: str) -> None:
        try:
            del self._generics[term]
        except KeyError:
            raise KeyError(f"no generic link for term {term!r}") from None

    def resolve_generic(self, term: str) -> Optional[str]:
        gen = self._generics.get(term)
        return gen["target"] if gen else None

    def scan_text(self, text: str) -> list[dict]:
        """Find every generic-link term occurring in ``text``: the
        glossary layer — ``[{"term", "target", "positions"}]``."""
        hits = []
        for term, gen in self._generics.items():
            positions = []
            start = 0
            while True:
                idx = text.find(term, start)
                if idx == -1:
                    break
                positions.append(idx)
                start = idx + len(term)
            if positions:
                hits.append(
                    {
                        "term": term,
                        "target": gen["target"],
                        "positions": positions,
                        "note": gen["note"],
                    }
                )
        return sorted(hits, key=lambda h: h["positions"][0])

    def link_count(self) -> int:
        return len(self._links)


__all__ = [
    "LinkbaseError",
    "UnknownDocument",
    "UnknownLink",
    "Link",
    "LinkBase",
]

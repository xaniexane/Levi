"""Callimachus's Pinakes: author/subject catalog with critical judgment.

History: the 3rd-c. BCE classified bibliography of Greek literature at
Alexandria — authors grouped by subject/genre, alphabetized, each entry with
title, incipit, biography, summary, provenance, and *authenticity notes*
(flagging spurious works). Whether it cataloged Alexandria's actual holdings
or Greek literature generally is disputed — don't overclaim.

In LEVI: :class:`Pinakes` is the judgment-laden catalog of your library.
Every entry carries provenance, a one-line critical judgment, an
authenticity note (authentic / disputed / spurious / unknown), and
cross-references — not a pile of PDFs but a curated scholarly instrument.
Finding and evaluating happen in one motion. Persists under
``~/.levi/methods/``.

Honesty: USEFUL PATTERN — the schema transfers cleanly; the 120 lost books
do not make your reading list Alexandria.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from . import _persist

AUTHENTICITY = ("authentic", "disputed", "spurious", "unknown")


@dataclass
class Entry:
    title: str
    author: str
    subject: str
    incipit: str = ""        # opening line / identifying hook
    biography: str = ""      # one-line author note
    summary: str = ""        # one-line critical judgment
    provenance: str = ""     # where this copy came from
    authenticity: str = "unknown"
    crossrefs: list[str] = field(default_factory=list)  # entry ids

    def validate(self) -> None:
        for attr in ("title", "author", "subject"):
            if not getattr(self, attr) or not getattr(self, attr).strip():
                raise ValueError(f"entry {attr} must be non-empty")
        if self.authenticity not in AUTHENTICITY:
            raise ValueError(f"authenticity must be one of {AUTHENTICITY}")


class Pinakes:
    """A classified, annotated bibliography — the catalog as criticism."""

    def __init__(self, store: str = "pinakes"):
        self._store = _persist.store_path(store)
        self.entries: dict[str, Entry] = {}
        self._next_id = 1
        self._load()

    def _load(self) -> None:
        data = _persist.load_json(self._store)
        if not data:
            return
        if not isinstance(data, dict) or "entries" not in data:
            raise _persist.CorruptStoreError(f"pinakes store {self._store} has bad shape")
        for eid, ed in data["entries"].items():
            entry = Entry(**ed)
            entry.validate()
            self.entries[eid] = entry
        self._next_id = int(data.get("next_id", len(self.entries) + 1))

    def save(self) -> None:
        _persist.save_json(
            self._store,
            {"entries": {eid: asdict(e) for eid, e in self.entries.items()},
             "next_id": self._next_id},
        )

    def add(self, entry: Entry) -> str:
        """Catalog a work. Returns its entry id (e.g. 'P-0001')."""
        entry.validate()
        eid = f"P-{self._next_id:04d}"
        self._next_id += 1
        self.entries[eid] = entry
        return eid

    def link(self, eid: str, other_eid: str) -> None:
        """Cross-reference two entries (bidirectional)."""
        for x in (eid, other_eid):
            if x not in self.entries:
                raise KeyError(f"no entry {x!r}")
        for a, b in ((eid, other_eid), (other_eid, eid)):
            if b not in self.entries[a].crossrefs:
                self.entries[a].crossrefs.append(b)

    def by_author(self, author: str) -> list[tuple[str, Entry]]:
        return [(eid, e) for eid, e in self.entries.items()
                if author.lower() in e.author.lower()]

    def by_subject(self, subject: str) -> list[tuple[str, Entry]]:
        return [(eid, e) for eid, e in self.entries.items()
                if subject.lower() in e.subject.lower()]

    def disputed(self) -> list[tuple[str, Entry]]:
        """Works flagged disputed or spurious — the authenticity audit."""
        return [(eid, e) for eid, e in self.entries.items()
                if e.authenticity in ("disputed", "spurious")]

    def annotated_list(self, subject: str | None = None) -> str:
        """Render the classified bibliography as text."""
        items = self.entries.items()
        if subject:
            items = [(eid, e) for eid, e in items if subject.lower() in e.subject.lower()]
        lines = [f"PINAKES — {len(list(items))} entries"]
        items = list(items)
        for eid, e in sorted(items, key=lambda kv: (kv[1].author.lower(), kv[1].title.lower())):
            lines.append(f"\n[{eid}] {e.title} — {e.author} ({e.subject})")
            if e.incipit:
                lines.append(f"  incipit: {e.incipit}")
            if e.summary:
                lines.append(f"  judgment: {e.summary}")
            lines.append(f"  authenticity: {e.authenticity}; provenance: {e.provenance or '—'}")
            if e.crossrefs:
                lines.append(f"  see also: {', '.join(e.crossrefs)}")
        return "\n".join(lines)

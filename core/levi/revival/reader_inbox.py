"""The Reader inbox: chronological reading pile with a quiet social layer.

Studied from: victims-of-giants-20260916-0017 / report.md [Resurrection
shortlist #1] (chronological RSS/Atom-style reader inbox with starring and a
share-with-notes quiet social layer; a user-controlled reading graph as an
anti-algorithm companion).

This is an original, from-scratch implementation for LEVI. The ``Reader``
holds a chronological list of ``Entry`` records (newest appended, read in
reverse arrival order — recency is the ONLY ranking signal; there is no
engagement ranking, no personalization model, no feed algorithm). Entries can
be starred (a personal mark of value, not a public metric). The quiet social
layer is ``share_with_notes(entry_id, recipient, note)``: a private forward
carrying the sender's note, visible only to its recipient — no public
broadcast, no like counts, no amplification mechanics.

The reading graph is the user's own record: which entries they read, starred,
shared, and from which source — a graph they own and can inspect, not a
profile an algorithm mines.

Honest limits:
- Entries are *added programmatically* (``add_entry``). This module parses no
  RSS/Atom over the network; a networked fetcher can push entries in later.
- "Quiet" is structural, not enforced by crypto: shares are addressed records,
  not public posts. It assumes the surrounding system does not republish them.
- No unread sync, no pagination cursors — ``unread()`` returns everything
  unread.

Public surface:
- ``Entry``, ``Share``, ``Reader``: ``add_entry``, ``star``/``unstar``,
  ``mark_read``, ``unread``, ``timeline``, ``share_with_notes``, ``shares_for``,
  ``reading_graph``, ``sources``.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

ORIGIN = "levi-revival/reader-inbox"


@dataclass
class Entry:
    """One item in the reading pile, in chronological arrival order."""

    id: int
    title: str
    source: str
    url: str = ""
    summary: str = ""
    added_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    read: bool = False
    starred: bool = False
    tags: tuple = ()


@dataclass(frozen=True)
class Share:
    """A private forward of an entry, carrying the sender's note."""

    id: int
    entry_id: int
    sender: str
    recipient: str
    note: str
    shared_at: str


class ReaderError(ValueError):
    """Raised when an entry or share reference is invalid."""


class Reader:
    """Chronological inbox. Newest-first is presentation; order is arrival."""

    def __init__(self) -> None:
        self._entries: Dict[int, Entry] = {}
        self._shares: Dict[int, Share] = {}
        self._next_entry = 1
        self._next_share = 1
        # reading graph edges: (actor, action, entry_id) in happened order
        self._events: List[tuple] = []

    # -- ingestion ---------------------------------------------------------

    def add_entry(
        self,
        title: str,
        source: str,
        url: str = "",
        summary: str = "",
        tags: Iterable[str] = (),
    ) -> Entry:
        if not title.strip():
            raise ReaderError("entry needs a non-empty title")
        entry = Entry(
            id=self._next_entry,
            title=title.strip(),
            source=source.strip() or "unknown",
            url=url.strip(),
            summary=summary.strip(),
            tags=tuple(t.strip() for t in tags if t.strip()),
        )
        self._entries[entry.id] = entry
        self._next_entry += 1
        self._events.append(("system", "added", entry.id))
        return entry

    def get(self, entry_id: int) -> Entry:
        try:
            return self._entries[entry_id]
        except KeyError:
            raise ReaderError(f"no entry #{entry_id}") from None

    # -- the anti-algorithm reading model ----------------------------------

    def mark_read(self, entry_id: int, who: str = "reader") -> Entry:
        entry = self.get(entry_id)
        entry.read = True
        self._events.append((who, "read", entry_id))
        return entry

    def star(self, entry_id: int, who: str = "reader") -> Entry:
        entry = self.get(entry_id)
        entry.starred = True
        self._events.append((who, "starred", entry_id))
        return entry

    def unstar(self, entry_id: int, who: str = "reader") -> Entry:
        entry = self.get(entry_id)
        entry.starred = False
        self._events.append((who, "unstarred", entry_id))
        return entry

    def timeline(self, limit: Optional[int] = None) -> List[Entry]:
        """All entries, newest first. Recency is the only rank."""
        ordered = sorted(
            self._entries.values(), key=lambda e: (e.added_at, e.id), reverse=True
        )
        return ordered[:limit] if limit is not None else ordered

    def unread(self) -> List[Entry]:
        """Everything unread, newest first."""
        return [e for e in self.timeline() if not e.read]

    def starred(self) -> List[Entry]:
        """Personal value marks, newest first."""
        return [e for e in self.timeline() if e.starred]

    # -- quiet social layer -------------------------------------------------

    def share_with_notes(
        self, entry_id: int, sender: str, recipient: str, note: str
    ) -> Share:
        entry = self.get(entry_id)
        if not sender.strip() or not recipient.strip():
            raise ReaderError("share needs a sender and a recipient")
        if not note.strip():
            raise ReaderError("shares carry a note; it cannot be empty")
        share = Share(
            id=self._next_share,
            entry_id=entry.id,
            sender=sender.strip(),
            recipient=recipient.strip(),
            note=note.strip(),
            shared_at=datetime.now(timezone.utc).isoformat(),
        )
        self._shares[share.id] = share
        self._next_share += 1
        self._events.append((sender.strip(), "shared", entry.id))
        return share

    def shares_for(self, recipient: str) -> List[Share]:
        """Shares addressed to one person. No public feed exists."""
        return [
            s
            for s in sorted(self._shares.values(), key=lambda s: s.shared_at)
            if s.recipient == recipient.strip()
        ]

    # -- user-owned reading graph -------------------------------------------

    def sources(self) -> Dict[str, int]:
        """Entry counts per source — the reader's own attention ledger."""
        return dict(Counter(e.source for e in self._entries.values()))

    def reading_graph(self) -> Dict[str, object]:
        """Everything this reader did, inspectable by the reader."""
        actions: Dict[str, Counter] = defaultdict(Counter)
        for actor, action, _entry_id in self._events:
            actions[actor][action] += 1
        return {
            "entries": len(self._entries),
            "sources": self.sources(),
            "starred_count": len(self.starred()),
            "shares_sent": len(self._shares),
            "actions_by_actor": {a: dict(c) for a, c in actions.items()},
        }

    def __len__(self) -> int:
        return len(self._entries)

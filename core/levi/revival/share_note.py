"""Share-with-note: annotation-first sharing; curation AND comment are the artifact.

Studied from: fallen-platforms-hunt-20260916/report.md (item 1: shared shelf)

The mechanism: sharing is not a button, it is a small written act. A share
pairs an item with a curator's note, and the note is required — a bare
forward without annotation is refused. The share record keeps the note's
revision history, so the curator's thinking over time is preserved as
part of the artifact, not overwritten. Likes and counts do not exist
here; the note is the value.

Honest limits: no identity or network layer; notes are plain text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


ORIGIN = "levi-revival/share-note"


@dataclass
class Share:
    share_id: str
    curator: str
    url: str
    title: str
    note_revisions: List[str] = field(default_factory=list)

    @property
    def note(self) -> str:
        return self.note_revisions[-1] if self.note_revisions else ""

    @property
    def revision_count(self) -> int:
        return len(self.note_revisions)


class ShareNotebook:
    """A curator's collection of annotated shares."""

    def __init__(self, curator: str) -> None:
        if not curator or not curator.strip():
            raise ValueError("curator must be non-empty")
        self.curator = curator
        self._shares: Dict[str, Share] = {}
        self._counter = 0

    # ------------------------------------------------------------------
    # Sharing (annotation-first: note is required)
    # ------------------------------------------------------------------
    def share(self, url: str, title: str, note: str) -> Share:
        if not url or not url.strip():
            raise ValueError("url must be non-empty")
        if not title or not title.strip():
            raise ValueError("title must be non-empty")
        if not note or not note.strip():
            raise ValueError("annotation-first sharing requires a note")
        self._counter += 1
        share = Share(
            share_id=f"sn-{self._counter}",
            curator=self.curator,
            url=url,
            title=title,
            note_revisions=[note],
        )
        self._shares[share.share_id] = share
        return share

    def revise_note(self, share_id: str, note: str) -> Share:
        share = self._get(share_id)
        if not note or not note.strip():
            raise ValueError("a revision cannot blank the note")
        share.note_revisions.append(note)
        return share

    def unshare(self, share_id: str) -> None:
        if share_id not in self._shares:
            raise KeyError(f"unknown share: {share_id!r}")
        del self._shares[share_id]

    # ------------------------------------------------------------------
    # Reading the notebook
    # ------------------------------------------------------------------
    def get(self, share_id: str) -> Share:
        return self._get(share_id)

    def annotated(self) -> List[Share]:
        """Every share, newest last — the curator's written trail."""
        return list(self._shares.values())

    def search_notes(self, query: str) -> List[Share]:
        q = query.strip().lower()
        return [
            s
            for s in self._shares.values()
            if q in s.note.lower() or q in s.title.lower()
        ]

    def notes_word_count(self) -> int:
        return sum(len(s.note.split()) for s in self._shares.values())

    def __len__(self) -> int:
        return len(self._shares)

    def _get(self, share_id: str) -> Share:
        try:
            return self._shares[share_id]
        except KeyError:
            raise KeyError(f"unknown share: {share_id!r}") from None

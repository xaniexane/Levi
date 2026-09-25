"""Your own traces, aggregated by you, owned by you.

Studied from: fallen-platforms-evening-20260916/report.md (4. FriendFeed).

The old mechanism: everything a person did across the web — posts,
photos, links, check-ins — flowed into one real-time shared stream,
with threaded comments under each item. The radical part wasn't the
aggregation; it was the ownership: the stream belonged to the person
whose traces it carried, exportable and erasable. LEVI's
reimplementation is that shape locally: a normalized entry log fed by
explicit ``ingest`` calls, threaded comments, full export, and a wipe
that requires a confirmation flag.

Honest limits: there is no live ingestion here — no webhooks, no API
polling, no network at all. Entries arrive when something calls
``ingest``. Comment threads cap at depth 3 (replies to replies to
replies); deeper replies are refused rather than flattened silently.
Timestamps are caller-supplied strings; ordering inside the stream is
by sequence number, which is the honest record of arrival order.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

ORIGIN = "levi-revival/lifestream"

MAX_DEPTH = 3  # comment thread depth cap


@dataclass
class Comment:
    comment_id: int
    entry_id: int
    author: str
    text: str
    parent_id: Optional[int] = None
    depth: int = 1


@dataclass
class Entry:
    entry_id: int
    seq: int
    source: str  # where the trace came from: "blog", "photos", ...
    kind: str  # what it is: "post", "photo", "link", ...
    text: str
    at: str = ""  # caller-supplied timestamp, opaque to the stream
    tags: List[str] = field(default_factory=list)
    key: str = ""  # idempotency key; repeat ingests with the same key win once
    comments: List[Comment] = field(default_factory=list)


class Lifestream:
    """One person's aggregated stream. ``owner`` is recorded on every
    export as a plain statement of whose traces these are."""

    def __init__(self, owner: str) -> None:
        if not owner.strip():
            raise ValueError("owner required")
        self.owner = owner.strip()
        self.entries: Dict[int, Entry] = {}
        self._keys: Dict[str, int] = {}
        self._next_entry = 0
        self._next_comment = 0
        self._seq = 0

    # -- feeding your own traces ------------------------------------------
    def ingest(
        self,
        source: str,
        kind: str,
        text: str,
        *,
        at: str = "",
        tags: Optional[List[str]] = None,
        key: str = "",
    ) -> Entry:
        """Add one trace. If ``key`` was already ingested, the original
        entry is returned unchanged (idempotent — re-feeds don't
        duplicate)."""
        if key and key in self._keys:
            return self.entries[self._keys[key]]
        if not source.strip() or not kind.strip():
            raise ValueError("source and kind required")
        if not text.strip():
            raise ValueError("text required")
        self._next_entry += 1
        self._seq += 1
        entry = Entry(
            entry_id=self._next_entry,
            seq=self._seq,
            source=source.strip().lower(),
            kind=kind.strip().lower(),
            text=text.strip(),
            at=at,
            tags=[t.strip().lower() for t in (tags or []) if t.strip()],
            key=key,
        )
        self.entries[entry.entry_id] = entry
        if key:
            self._keys[key] = entry.entry_id
        return entry

    # -- reading the stream -------------------------------------------------
    def stream(self, newest_first: bool = True) -> List[Entry]:
        ordered = sorted(self.entries.values(), key=lambda e: e.seq)
        return ordered[::-1] if newest_first else ordered

    def by_source(self, source: str) -> List[Entry]:
        s = source.strip().lower()
        return [e for e in self.stream(False) if e.source == s]

    def by_kind(self, kind: str) -> List[Entry]:
        k = kind.strip().lower()
        return [e for e in self.stream(False) if e.kind == k]

    def by_tag(self, tag: str) -> List[Entry]:
        t = tag.strip().lower()
        return [e for e in self.stream(False) if t in e.tags]

    # -- threaded comments ---------------------------------------------------
    def comment(
        self, entry_id: int, author: str, text: str, parent_id: Optional[int] = None
    ) -> Comment:
        entry = self._get(entry_id)
        if not author.strip():
            raise ValueError("author required")
        if not text.strip():
            raise ValueError("text required")
        depth = 1
        if parent_id is not None:
            parent = self._find_comment(entry, parent_id)
            depth = parent.depth + 1
            if depth > MAX_DEPTH:
                raise ValueError(f"thread depth capped at {MAX_DEPTH}")
        self._next_comment += 1
        comment = Comment(
            comment_id=self._next_comment,
            entry_id=entry_id,
            author=author.strip(),
            text=text.strip(),
            parent_id=parent_id,
            depth=depth,
        )
        entry.comments.append(comment)
        return comment

    def thread(self, entry_id: int) -> List[Dict[str, Any]]:
        """The comment tree as nested dicts (children under each
        comment's ``replies``)."""
        entry = self._get(entry_id)
        nodes: Dict[int, Dict[str, Any]] = {}
        roots: List[Dict[str, Any]] = []
        for c in entry.comments:
            nodes[c.comment_id] = {
                "comment_id": c.comment_id,
                "author": c.author,
                "text": c.text,
                "depth": c.depth,
                "replies": [],
            }
        for c in entry.comments:
            node = nodes[c.comment_id]
            if c.parent_id is None:
                roots.append(node)
            elif c.parent_id in nodes:
                nodes[c.parent_id]["replies"].append(node)
        return roots

    # -- ownership: export and erasure ----------------------------------------
    def export(self) -> Dict[str, Any]:
        """Everything, in plain data. This is what 'you own your stream'
        means here: nothing is held back, nothing needs permission."""
        return {
            "owner": self.owner,
            "entries": [
                {
                    "entry_id": e.entry_id,
                    "seq": e.seq,
                    "source": e.source,
                    "kind": e.kind,
                    "text": e.text,
                    "at": e.at,
                    "tags": e.tags,
                    "key": e.key,
                    "comments": [
                        {
                            "comment_id": c.comment_id,
                            "author": c.author,
                            "text": c.text,
                            "parent_id": c.parent_id,
                            "depth": c.depth,
                        }
                        for c in e.comments
                    ],
                }
                for e in self.stream(False)
            ],
        }

    def export_jsonl(self, path: str) -> int:
        """Write one JSON object per line: the stream header, then one
        line per entry. Returns the entry count."""
        data = self.export()
        lines = [json.dumps({"owner": data["owner"], "type": "header"})]
        lines += [json.dumps({"type": "entry", **e}) for e in data["entries"]]
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        return len(data["entries"])

    def wipe(self, confirm: bool = False) -> int:
        """Erase the whole stream. Requires ``confirm=True`` — erasure
        is never accidental. Returns the entry count removed."""
        if not confirm:
            raise ValueError("wipe requires confirm=True")
        removed = len(self.entries)
        self.entries.clear()
        self._keys.clear()
        return removed

    def stream_status(self) -> Dict[str, object]:
        return {
            "owner": self.owner,
            "entries": len(self.entries),
            "comments": sum(len(e.comments) for e in self.entries.values()),
            "sources": sorted({e.source for e in self.entries.values()}),
        }

    # -- internals -------------------------------------------------------------
    def _get(self, entry_id: int) -> Entry:
        try:
            return self.entries[entry_id]
        except KeyError:
            raise ValueError(f"no entry {entry_id}") from None

    @staticmethod
    def _find_comment(entry: Entry, comment_id: int) -> Comment:
        for c in entry.comments:
            if c.comment_id == comment_id:
                return c
        raise ValueError(f"no comment {comment_id} on entry {entry.entry_id}")

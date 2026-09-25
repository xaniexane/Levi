"""Public terminals — walk-up community message boards.

Studied from: dead-networks-20260916, report.md [Community Memory].

The mechanism, functionally: a walk-up public terminal in a record store
or supermarket, usable by non-technical passersby with no account and no
training. The terminal offers a small set of plain actions — browse
categories, keyword-search the community message base, post a notice /
offer / request — in a time-boxed anonymous session. Keyword search is
the whole retrieval model: simple, legible, and kind to strangers.

This module is a software analog of that pattern: ``MessageBase`` (the
community corpus with an inverted keyword index), ``Terminal`` (a
time-boxed walk-up session exposing browse/search/post), and a seeded
category vocabulary. No network, no accounts — the terminal is the
interface.

Honesty: retrieval is substring keyword matching over an inverted
index, a deliberate 1970s constraint — no ranking beyond recency, no
language understanding. Sessions are anonymous by design, so abuse
limiting is a posted-notice policy, not something this code enforces.
"""

from __future__ import annotations

import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

ORIGIN = "levi-revival/public-terminals"

CATEGORIES = ("notices", "offers", "requests", "events", "lost-found")

_WORD = re.compile(r"[a-z0-9]+")


def _words(text: str) -> Set[str]:
    return set(_WORD.findall(text.lower()))


@dataclass
class CommunityMessage:
    """One message on the board: someone's notice, offer, or request."""

    _seq = 0

    id: str = field(init=False)
    category: str = ""
    headline: str = ""
    body: str = ""
    posted_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        CommunityMessage._seq += 1
        self.id = f"msg{CommunityMessage._seq:05d}"

    def text(self) -> str:
        return f"{self.headline} {self.body}"


class MessageBase:
    """The community corpus with a plain keyword index."""

    def __init__(self) -> None:
        self.messages: Dict[str, CommunityMessage] = {}
        self.index: Dict[str, Set[str]] = defaultdict(set)

    def post(self, category: str, headline: str, body: str = "") -> CommunityMessage:
        """Pin a message to the board."""
        if category not in CATEGORIES:
            raise ValueError(f"category must be one of {CATEGORIES}")
        if not headline.strip():
            raise ValueError("headline must be non-empty")
        msg = CommunityMessage(
            category=category, headline=headline.strip(), body=body.strip()
        )
        self.messages[msg.id] = msg
        for word in _words(msg.text()):
            self.index[word].add(msg.id)
        return msg

    def search(self, query: str, limit: int = 20) -> List[CommunityMessage]:
        """Keyword search: messages matching the most query words, newest
        first. Legible and dumb on purpose."""
        wanted = _words(query)
        if not wanted:
            return []
        scores: Dict[str, int] = defaultdict(int)
        for word in wanted:
            for mid in self.index.get(word, ()):
                scores[mid] += 1
        ranked = sorted(
            scores,
            key=lambda mid: (scores[mid], self.messages[mid].posted_at),
            reverse=True,
        )
        return [self.messages[mid] for mid in ranked[:limit]]

    def browse(
        self, category: Optional[str] = None, limit: int = 20
    ) -> List[CommunityMessage]:
        msgs = list(self.messages.values())
        if category is not None:
            if category not in CATEGORIES:
                raise ValueError(f"category must be one of {CATEGORIES}")
            msgs = [m for m in msgs if m.category == category]
        msgs.sort(key=lambda m: m.posted_at, reverse=True)
        return msgs[:limit]

    def size(self) -> int:
        return len(self.messages)


class Terminal:
    """A walk-up terminal: no account, no training, a time-boxed session.

    A stranger walks up, gets a few plain actions, and the session ends —
    the next stranger starts fresh. The terminal is deliberately
    stateless between sessions.
    """

    def __init__(
        self,
        base: MessageBase,
        location: str = "terminal-1",
        session_seconds: float = 300.0,
    ) -> None:
        self.base = base
        self.location = location
        self.session_seconds = session_seconds
        self._session_start: Optional[float] = None

    # -- session ---------------------------------------------------------

    def begin_session(self) -> float:
        """Start a walk-up session; returns the session deadline."""
        self._session_start = time.time()
        return self._session_start + self.session_seconds

    def session_active(self) -> bool:
        if self._session_start is None:
            return False
        return time.time() - self._session_start < self.session_seconds

    def end_session(self) -> None:
        self._session_start = None

    def _require_session(self) -> None:
        if not self.session_active():
            raise RuntimeError("no active walk-up session; begin_session() first")

    # -- the plain actions a stranger gets -------------------------------

    def browse(
        self, category: Optional[str] = None, limit: int = 20
    ) -> List[CommunityMessage]:
        self._require_session()
        return self.base.browse(category, limit)

    def search(self, query: str, limit: int = 20) -> List[CommunityMessage]:
        self._require_session()
        return self.base.search(query, limit)

    def post(self, category: str, headline: str, body: str = "") -> CommunityMessage:
        self._require_session()
        return self.base.post(category, headline, body)

    def categories(self) -> List[str]:
        return list(CATEGORIES)

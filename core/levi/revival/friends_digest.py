"""Friends-locked posts + friends-page digest: audience control that means it.

Studied from: victims-of-giants-20260916-0017 report.md
[Resurrection shortlist #17]

The studied shape: per-post audience control (friends-locked posts)
paired with a friends page — a reverse-chron digest that only mutual
friends can see. The dead-web contract: friendship is mutual and
explicit, and the friends page is the social unit, not the algorithmic
feed.

LEVI-native re-expression: a friendship graph where edges require
mutual acceptance (request + accept; a request alone grants nothing),
posts carry an audience (public / friends / mutuals / named list), and
the digest is a plain reverse-chronological list of everything visible
to the viewer — no ranking, no engagement weighting, by design.

Honest limits: "friends" here means mutually accepted graph edges, not
verified real-world relationships. The digest is chronological, so a
busy poster can crowd it out — that is the documented trade-off of
refusing ranking.
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Set


ORIGIN = "levi-revival/friends-digest"


class Audience(str, Enum):
    PUBLIC = "public"  # anyone
    FRIENDS = "friends"  # mutual edges only
    MUTUALS = "mutuals"  # alias of friends kept for voice
    NAMED = "named"  # explicit handle list


@dataclass
class Post:
    id: int
    author: str
    body: str
    audience: Audience
    named: FrozenSet[str] = field(default_factory=frozenset)
    created: float = field(default_factory=time.time)
    edited: Optional[float] = None

    def edit(self, body: str) -> None:
        self.body = body
        self.edited = time.time()


class SocialGraph:
    """Mutual-gated friendships, locked posts, chronological digest."""

    def __init__(self) -> None:
        self._outgoing: Dict[str, Set[str]] = {}  # requests sent
        self._friends: Dict[str, Set[str]] = {}  # mutual edges
        self._posts: Dict[int, Post] = {}
        self._ids = itertools.count(1)

    # --- friendship -----------------------------------------------------
    def _set(self, table: Dict[str, Set[str]], person: str) -> Set[str]:
        return table.setdefault(person, set())

    def request(self, frm: str, to: str) -> bool:
        """Send a friend request. Returns False if already friends/requested."""
        if frm == to or to in self._set(self._friends, frm):
            return False
        pending = self._set(self._outgoing, frm)
        if to in pending:
            return False
        pending.add(to)
        return True

    def accept(self, person: str, frm: str) -> bool:
        """`person` accepts `frm`'s pending request; creates a mutual edge."""
        if frm in self._set(self._outgoing, person):
            return False
        pending = self._set(self._outgoing, frm)
        if person not in pending:
            return False
        pending.discard(person)
        self._set(self._friends, person).add(frm)
        self._set(self._friends, frm).add(person)
        return True

    def decline(self, person: str, frm: str) -> bool:
        pending = self._set(self._outgoing, frm)
        if person in pending:
            pending.discard(person)
            return True
        return False

    def unfriend(self, a: str, b: str) -> bool:
        removed = b in self._set(self._friends, a)
        self._set(self._friends, a).discard(b)
        self._set(self._friends, b).discard(a)
        return removed

    def friends_of(self, person: str) -> Set[str]:
        return set(self._set(self._friends, person))

    def are_friends(self, a: str, b: str) -> bool:
        return b in self._set(self._friends, a)

    # --- posts ----------------------------------------------------------
    def post(
        self,
        author: str,
        body: str,
        audience: Audience = Audience.FRIENDS,
        named: Optional[List[str]] = None,
    ) -> Post:
        if not body.strip():
            raise ValueError("post body cannot be empty")
        pid = next(self._ids)
        p = Post(
            id=pid,
            author=author,
            body=body,
            audience=audience,
            named=frozenset(named or []),
        )
        self._posts[pid] = p
        return p

    def visible_to(self, post: Post, viewer: str) -> bool:
        if viewer == post.author:
            return True
        if post.audience is Audience.PUBLIC:
            return True
        if post.audience in (Audience.FRIENDS, Audience.MUTUALS):
            return self.are_friends(post.author, viewer)
        if post.audience is Audience.NAMED:
            return viewer in post.named
        return False

    def digest(self, viewer: str, limit: int = 50) -> List[Post]:
        """Friends page: everything visible to viewer, newest first."""
        visible = [p for p in self._posts.values() if self.visible_to(p, viewer)]
        visible.sort(key=lambda p: (p.created, p.id), reverse=True)
        return visible[:limit]

    def wall(self, author: str, viewer: str, limit: int = 50) -> List[Post]:
        mine = [
            p
            for p in self._posts.values()
            if p.author == author and self.visible_to(p, viewer)
        ]
        mine.sort(key=lambda p: (p.created, p.id), reverse=True)
        return mine[:limit]

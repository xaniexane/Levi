"""hearth — identity-persistent community memory: the Hearth.

Studied from: revival-50-more-20260916-0009/report-part1.md (Section 19).

Load-bearing idea: persistent identities, topic threading, human host
roles — and the "you own your own words" norm *encoded as rules*:
authorship is immutable, edit history is visible, and even hosts may
not rewrite another member's words.

LEVI's take: ``Hearth`` holds ``Member``s with durable identities and
``Thread``s of ``Post``s. A post's author is set once and can never
change; ``edit`` is author-only and appends to a visible revision
history instead of overwriting. Hosts may flag and close threads, but
any attempt to edit, reattribute, or silently alter someone else's
words raises ``NormViolation`` — the norm is code, not etiquette.
Everything stays in-process and inspectable.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


ORIGIN = "levi-revival/hearth"


class NormViolation(Exception):
    """Someone tried to break the 'you own your own words' norm."""


@dataclass
class Member:
    """A persistent identity. Names are stable; handles don't get recycled."""

    name: str
    joined_at: float
    host: bool = False


@dataclass
class Post:
    id: str
    author: str  # immutable: set once, never reassigned
    body: str  # current text
    created_at: float
    revisions: List[Tuple[float, str]] = field(
        default_factory=list
    )  # (ts, body) snapshots, original first

    def __post_init__(self) -> None:
        self.revisions.append((self.created_at, self.body))

    def edit(self, by: str, new_body: str, now: Optional[float] = None) -> None:
        """Author-only edit. Every version stays visible in ``revisions``."""
        if by != self.author:
            raise NormViolation(f"{by!r} may not edit {self.author!r}'s words")
        ts = now if now is not None else time.time()
        self.body = new_body
        self.revisions.append((ts, new_body))


@dataclass
class Thread:
    id: str
    topic: str
    title: str
    opened_by: str
    opened_at: float
    posts: List[Post] = field(default_factory=list)
    closed: bool = False
    flagged: bool = False


class Hearth:
    """A community hearth: durable identities, owned words, host stewardship."""

    def __init__(self) -> None:
        self.members: Dict[str, Member] = {}
        self.threads: Dict[str, Thread] = {}
        self._posts: Dict[str, Post] = {}

    # -- membership ------------------------------------------------------

    def join(self, name: str, now: Optional[float] = None) -> Member:
        if name in self.members:
            raise NormViolation(f"identity {name!r} is already taken and persistent")
        member = Member(name=name, joined_at=now if now is not None else time.time())
        self.members[name] = member
        return member

    def make_host(self, name: str) -> Member:
        member = self._member(name)
        member.host = True
        return member

    # -- threads and posts ------------------------------------------------

    def open_thread(
        self, topic: str, title: str, by: str, now: Optional[float] = None
    ) -> Thread:
        self._member(by)  # must be a member to speak
        thread = Thread(
            id=uuid.uuid4().hex[:8],
            topic=topic,
            title=title,
            opened_by=by,
            opened_at=now if now is not None else time.time(),
        )
        self.threads[thread.id] = thread
        return thread

    def post(
        self, thread_id: str, author: str, body: str, now: Optional[float] = None
    ) -> Post:
        thread = self._thread(thread_id)
        self._member(author)
        if thread.closed:
            raise NormViolation("thread is closed; no new words may be added")
        post = Post(
            id=uuid.uuid4().hex[:8],
            author=author,
            body=body,
            created_at=now if now is not None else time.time(),
        )
        thread.posts.append(post)
        self._posts[post.id] = post
        return post

    def edit_post(
        self, post_id: str, by: str, new_body: str, now: Optional[float] = None
    ) -> Post:
        """The norm, enforced: only the author edits, history stays visible."""
        post = self._post(post_id)
        post.edit(by, new_body, now)
        return post

    def history(self, post_id: str) -> List[Tuple[float, str]]:
        """The full visible edit history: (ts, body) snapshots, original first."""
        return list(self._post(post_id).revisions)

    def reattribute(self, post_id: str, new_author: str, by: str) -> None:
        """Rewriting who said something is forbidden to everyone."""
        raise NormViolation(
            f"{by!r} attempted to reattribute {self._post(post_id).author!r}'s words "
            f"to {new_author!r}: authorship is immutable"
        )

    # -- host stewardship --------------------------------------------------

    def flag_thread(self, thread_id: str, by: str) -> Thread:
        self._require_host(by)
        thread = self._thread(thread_id)
        thread.flagged = True
        return thread

    def close_thread(self, thread_id: str, by: str) -> Thread:
        self._require_host(by)
        thread = self._thread(thread_id)
        thread.closed = True
        return thread

    def edit_as_host(self, post_id: str, by: str, new_body: str) -> None:
        """Hosts steward threads; they never rewrite members' words."""
        self._require_host(by)
        post = self._post(post_id)
        raise NormViolation(
            f"host {by!r} may flag or close, but never edit {post.author!r}'s words"
        )

    # -- internals ----------------------------------------------------------

    def _member(self, name: str) -> Member:
        try:
            return self.members[name]
        except KeyError:
            raise NormViolation(f"{name!r} is not a member of this hearth") from None

    def _thread(self, thread_id: str) -> Thread:
        try:
            return self.threads[thread_id]
        except KeyError:
            raise NormViolation(f"unknown thread {thread_id!r}") from None

    def _post(self, post_id: str) -> Post:
        try:
            return self._posts[post_id]
        except KeyError:
            raise NormViolation(f"unknown post {post_id!r}") from None

    def _require_host(self, name: str) -> Member:
        member = self._member(name)
        if not member.host:
            raise NormViolation(f"{name!r} is not a host")
        return member

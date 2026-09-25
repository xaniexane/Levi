"""CoSy conferencing: threaded topic conferences with experts as regulars.

Studied from: dead-networks-20260916/report.md (BIX)

The mechanism: a conference is a named room for one topic. Inside, posts
form threads — a post replies to another post, not to the room. Some
participants are designated experts: they are regulars, not moderators,
and the conference marks their posts as expert voice. Joining is
explicit; leaving keeps the archive. Threads can be listed, followed to
their roots, and searched.

Honest limits: local data structure only; no network, no real experts —
"expert" here is a role label assigned by the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional


ORIGIN = "levi-revival/cosy-conferencing"


@dataclass
class Member:
    handle: str
    expert: bool = False


@dataclass
class Post:
    post_id: str
    author: str
    body: str
    reply_to: Optional[str] = None
    expert_voice: bool = False


class Conference:
    """One threaded topic conference."""

    def __init__(self, name: str, topic: str = "") -> None:
        if not name or not name.strip():
            raise ValueError("conference name must be non-empty")
        self.name = name
        self.topic = topic
        self.members: Dict[str, Member] = {}
        self.posts: Dict[str, Post] = {}
        self._counter = 0

    # ------------------------------------------------------------------
    # Membership
    # ------------------------------------------------------------------
    def join(self, handle: str, expert: bool = False) -> Member:
        if not handle or not handle.strip():
            raise ValueError("handle must be non-empty")
        member = Member(handle=handle, expert=expert)
        self.members[handle] = member
        return member

    def leave(self, handle: str) -> None:
        self.members.pop(handle, None)

    def experts(self) -> List[Member]:
        return [m for m in self.members.values() if m.expert]

    # ------------------------------------------------------------------
    # Posting and threading
    # ------------------------------------------------------------------
    def post(self, handle: str, body: str, reply_to: Optional[str] = None) -> Post:
        if handle not in self.members:
            raise KeyError(f"{handle!r} is not a member of {self.name!r}")
        if not body or not body.strip():
            raise ValueError("post body must be non-empty")
        if reply_to is not None and reply_to not in self.posts:
            raise KeyError(f"unknown parent post: {reply_to!r}")
        self._counter += 1
        post = Post(
            post_id=f"post-{self._counter}",
            author=handle,
            body=body,
            reply_to=reply_to,
            expert_voice=self.members[handle].expert,
        )
        self.posts[post.post_id] = post
        return post

    def thread(self, post_id: str) -> List[Post]:
        """The reply chain from the thread root down to the post."""
        if post_id not in self.posts:
            raise KeyError(f"unknown post: {post_id!r}")
        chain: List[Post] = []
        current: Optional[Post] = self.posts[post_id]
        while current is not None:
            chain.append(current)
            current = self.posts.get(current.reply_to) if current.reply_to else None
        return list(reversed(chain))

    def replies(self, post_id: str) -> List[Post]:
        if post_id not in self.posts:
            raise KeyError(f"unknown post: {post_id!r}")
        return [p for p in self.posts.values() if p.reply_to == post_id]

    def roots(self) -> List[Post]:
        """Top-level posts — one per discussion thread."""
        return [p for p in self.posts.values() if p.reply_to is None]

    def expert_posts(self) -> List[Post]:
        return [p for p in self.posts.values() if p.expert_voice]

    def search(self, query: str) -> List[Post]:
        q = query.strip().lower()
        return [p for p in self.posts.values() if q in p.body.lower()]

    def __len__(self) -> int:
        return len(self.posts)

    def __iter__(self) -> Iterator[Post]:
        return iter(sorted(self.posts.values(), key=lambda p: p.post_id))

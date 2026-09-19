"""free_social_layer — a social layer whose stated price is nothing, and that is true.

Studied from: giant-patterns-hunt-20260916-0016/report.md [Sly-honest S1].

Load-bearing idea: zero-marginal-cost social. There is no remote service, no
ad auction, and no engagement ranking — because there is no behavioral
surplus to sell. A feed is strictly chronological among people you follow;
the only cost is your own storage, stated up front.

LEVI's take: ``FreeLayer`` is a local social graph. Users join, follow, post,
and read a chronological feed. ``Post`` carries no tracking fields and never
will. ``export()`` hands a user every post and follow as plain data — exit is
free because there was never a lock-in price to begin with.

Honest limits: no federation or sync — the graph lives on this device. Feed
ordering is chronological only; there is deliberately no discovery or
ranking engine.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Set

ORIGIN = "levi-revival/free-social-layer"

#: The stated price. It is also the true price.
STATED_PRICE = "nothing"


@dataclass
class Post:
    """A post. Carries no tracking fields: no views, no impressions, no ad ids."""

    id: int
    author: str
    body: str
    seq: int  # chronological sequence number, global across the layer


@dataclass
class FreeLayer:
    """A local, zero-marginal-cost social graph."""

    users: Set[str] = field(default_factory=set)
    follows: Dict[str, Set[str]] = field(default_factory=dict)
    posts: List[Post] = field(default_factory=list)
    _next_id: int = field(default=1, repr=False)
    _next_seq: int = field(default=1, repr=False)

    def join(self, user: str) -> None:
        """Join the layer. Costs nothing; there is no approval queue."""
        self.users.add(user)
        self.follows.setdefault(user, set())

    def follow(self, follower: str, followee: str) -> None:
        """Follow directly. No request/approval dance, no algorithmic gate."""
        for name in (follower, followee):
            if name not in self.users:
                raise KeyError(f"unknown user: {name!r}")
        self.follows[follower].add(followee)

    def unfollow(self, follower: str, followee: str) -> None:
        """Unfollow directly. Exit from any relationship is as easy as entry."""
        self.follows.get(follower, set()).discard(followee)

    def post(self, author: str, body: str) -> Post:
        """Publish a post. It appears in followers' feeds in chronological order."""
        if author not in self.users:
            raise KeyError(f"unknown user: {author!r}")
        if not body.strip():
            raise ValueError("post body must not be empty")
        entry = Post(id=self._next_id, author=author, body=body, seq=self._next_seq)
        self._next_id += 1
        self._next_seq += 1
        self.posts.append(entry)
        return entry

    def feed(self, user: str, limit: int = 50) -> List[Post]:
        """Chronological feed of posts by followed users (plus self).

        No ranking, no boosting, no demotion. Newest last read first: the
        list is in chronological order, oldest first.
        """
        if user not in self.users:
            raise KeyError(f"unknown user: {user!r}")
        visible = self.follows[user] | {user}
        return [p for p in self.posts if p.author in visible][:limit]

    def export(self, user: str) -> Dict:
        """Everything the layer knows about you, as plain data. Free exit."""
        if user not in self.users:
            raise KeyError(f"unknown user: {user!r}")
        return {
            "user": user,
            "follows": sorted(self.follows[user]),
            "posts": [
                {"id": p.id, "body": p.body, "seq": p.seq}
                for p in self.posts
                if p.author == user
            ],
        }

    def costs(self) -> Dict:
        """The true cost, stated plainly."""
        return {
            "money": 0.0,
            "currency": "USD",
            "tracking_fields": [],
            "ads_shown": 0,
            "data_sold": [],
            "storage": "local device only",
        }

    def save(self, path: str) -> None:
        """Persist the layer to local JSON. Still no network involved."""
        payload = {
            "users": sorted(self.users),
            "follows": {u: sorted(v) for u, v in self.follows.items()},
            "posts": [
                {"id": p.id, "author": p.author, "body": p.body, "seq": p.seq}
                for p in self.posts
            ],
            "next_id": self._next_id,
            "next_seq": self._next_seq,
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)

    @classmethod
    def load(cls, path: str) -> "FreeLayer":
        """Restore a layer saved with :meth:`save`."""
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        layer = cls(
            users=set(payload["users"]),
            follows={u: set(v) for u, v in payload["follows"].items()},
            posts=[Post(**p) for p in payload["posts"]],
        )
        layer._next_id = payload["next_id"]
        layer._next_seq = payload["next_seq"]
        return layer

"""portable_communities — a community you can pack up and leave with.

Studied from: giant-patterns-hunt-20260916-0016 (report.md [Additions 6]).
Load-bearing idea: full community export — structure, history, and
governance — so a community is never held hostage by its host. Leaving
is a first-class operation.

LEVI's take: ``Community`` holds channels with message history, members
with roles, and governance (rules + recorded decisions). ``export_bundle``
packs all of it into one portable dict with a SHA-256 manifest over every
section; ``import_bundle`` rebuilds it elsewhere and ``verify_bundle``
checks the manifest, so a receiving host can prove nothing was dropped
or altered in transit.

Honest limits: the bundle is data, not continuity — member identities
here are local handles, and import creates a faithful copy, not a live
migration of sessions or external integrations.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Dict, List


ORIGIN = "levi-revival/portable-communities"

ROLES = ("member", "moderator", "admin", "owner")


@dataclass
class Post:
    id: str
    author: str
    text: str
    ts: float


@dataclass
class Channel:
    name: str
    topic: str = ""
    posts: List[Post] = field(default_factory=list)


@dataclass
class Member:
    handle: str
    role: str = "member"
    joined_at: float = 0.0


@dataclass
class Rule:
    id: str
    text: str
    adopted_at: float
    adopted_by: str = ""


@dataclass
class Decision:
    id: str
    motion: str
    outcome: str  # passed | rejected | tabled
    decided_at: float
    votes_for: int = 0
    votes_against: int = 0


class Community:
    """A community with structure, history, governance — and an exit door."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.channels: Dict[str, Channel] = {}
        self.members: Dict[str, Member] = {}
        self.rules: Dict[str, Rule] = {}
        self.decisions: List[Decision] = []

    # -- structure ------------------------------------------------------------

    def add_channel(self, name: str, topic: str = "") -> Channel:
        if name in self.channels:
            raise ValueError(f"channel {name!r} already exists")
        ch = Channel(name=name, topic=topic)
        self.channels[name] = ch
        return ch

    def add_member(self, handle: str, role: str = "member") -> Member:
        if role not in ROLES:
            raise ValueError(f"role must be one of {ROLES}")
        m = Member(handle=handle, role=role, joined_at=time.time())
        self.members[handle] = m
        return m

    def set_role(self, handle: str, role: str) -> Member:
        if role not in ROLES:
            raise ValueError(f"role must be one of {ROLES}")
        m = self.members[handle]
        m.role = role
        return m

    # -- history --------------------------------------------------------------

    def post(self, channel: str, author: str, text: str) -> Post:
        if author not in self.members:
            raise KeyError(f"{author!r} is not a member")
        p = Post(
            id=f"p-{uuid.uuid4().hex[:8]}", author=author, text=text, ts=time.time()
        )
        self.channels[channel].posts.append(p)
        return p

    # -- governance -----------------------------------------------------------

    def adopt_rule(self, text: str, adopted_by: str = "") -> Rule:
        r = Rule(
            id=f"rule-{uuid.uuid4().hex[:8]}",
            text=text,
            adopted_at=time.time(),
            adopted_by=adopted_by,
        )
        self.rules[r.id] = r
        return r

    def record_decision(
        self, motion: str, outcome: str, votes_for: int = 0, votes_against: int = 0
    ) -> Decision:
        if outcome not in ("passed", "rejected", "tabled"):
            raise ValueError("outcome must be passed|rejected|tabled")
        d = Decision(
            id=f"d-{uuid.uuid4().hex[:8]}",
            motion=motion,
            outcome=outcome,
            decided_at=time.time(),
            votes_for=votes_for,
            votes_against=votes_against,
        )
        self.decisions.append(d)
        return d

    # -- portability: the exit door -------------------------------------------

    def export_bundle(self) -> dict:
        """Pack structure + history + governance into one portable bundle."""
        body = {
            "format": "levi-community-bundle/1",
            "name": self.name,
            "exported_at": time.time(),
            "channels": {n: asdict(c) for n, c in self.channels.items()},
            "members": {h: asdict(m) for h, m in self.members.items()},
            "rules": {i: asdict(r) for i, r in self.rules.items()},
            "decisions": [asdict(d) for d in self.decisions],
        }
        manifest = {
            section: _digest(body[section])
            for section in ("channels", "members", "rules", "decisions")
        }
        return {"manifest": manifest, "body": body}

    @classmethod
    def import_bundle(cls, bundle: dict) -> "Community":
        """Rebuild a community from a bundle. Raises on failed verification."""
        if not verify_bundle(bundle):
            raise ValueError("bundle failed integrity verification")
        body = bundle["body"]
        c = cls(body["name"])
        for n, ch in body["channels"].items():
            posts = [Post(**p) for p in ch.get("posts", [])]
            c.channels[n] = Channel(
                name=ch["name"], topic=ch.get("topic", ""), posts=posts
            )
        for h, m in body["members"].items():
            c.members[h] = Member(**m)
        for i, r in body["rules"].items():
            c.rules[i] = Rule(**r)
        c.decisions = [Decision(**d) for d in body.get("decisions", [])]
        return c


def _digest(obj: object) -> str:
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def verify_bundle(bundle: dict) -> bool:
    """Check a bundle's manifest against its body. True = intact."""
    try:
        manifest = bundle["manifest"]
        body = bundle["body"]
    except (KeyError, TypeError):
        return False
    for section in ("channels", "members", "rules", "decisions"):
        if section not in manifest or section not in body:
            return False
        if manifest[section] != _digest(body[section]):
            return False
    return True

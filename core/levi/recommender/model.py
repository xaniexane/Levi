"""Item / Goal schema. Topics are explicit weight maps, not embeddings."""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return "%s-%s" % (prefix, uuid.uuid4().hex[:8])


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:32]
    return slug or "item"


def parse_topics(spec: str) -> Dict[str, float]:
    """Parse ``"python:1.0,asyncio:0.6"`` (weight defaults to 1.0)."""
    topics: Dict[str, float] = {}
    for chunk in (spec or "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        name, _, weight = chunk.partition(":")
        name = name.strip().lower()
        if not name:
            raise ValueError("empty topic name in %r" % chunk)
        try:
            w = float(weight) if weight else 1.0
        except ValueError:
            raise ValueError("bad topic weight in %r" % chunk)
        if not (0.0 <= w <= 1.0):
            raise ValueError("topic weight must be in [0, 1]: %r" % chunk)
        topics[name] = w
    if not topics:
        raise ValueError("at least one topic is required")
    return topics


def _check_topics(topics: Dict[str, float], what: str) -> Dict[str, float]:
    if not isinstance(topics, dict) or not topics:
        raise ValueError("%s needs at least one topic" % what)
    cleaned = {}
    for name, weight in topics.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("%s has an empty topic name" % what)
        w = float(weight)
        if not (0.0 <= w <= 1.0):
            raise ValueError("%s topic %r weight must be in [0, 1]" % (what, name))
        cleaned[name.strip().lower()] = w
    return cleaned


@dataclass
class Item:
    """One recommendable thing. Topics say what it's *about*."""

    id: str
    title: str
    kind: str
    topics: Dict[str, float]
    text: str = ""
    attrs: Dict = field(default_factory=dict)
    added_at: str = ""

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("item title is required")
        if not self.kind.strip():
            raise ValueError("item kind is required")
        self.topics = _check_topics(self.topics, "item")
        if not self.added_at:
            self.added_at = now_iso()

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Dict) -> "Item":
        return cls(
            id=str(raw["id"]),
            title=str(raw["title"]),
            kind=str(raw["kind"]),
            topics=dict(raw.get("topics") or {}),
            text=str(raw.get("text", "")),
            attrs=dict(raw.get("attrs") or {}),
            added_at=str(raw.get("added_at", "")),
        )


@dataclass
class Goal:
    """A user-stated goal: what the user wants, in their own words."""

    id: str
    title: str
    topics: Dict[str, float]
    kind_filter: List[str] = field(default_factory=list)
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("goal title is required")
        self.topics = _check_topics(self.topics, "goal")
        self.kind_filter = [k.strip().lower() for k in self.kind_filter if k.strip()]

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Dict) -> "Goal":
        return cls(
            id=str(raw["id"]),
            title=str(raw["title"]),
            topics=dict(raw.get("topics") or {}),
            kind_filter=list(raw.get("kind_filter") or []),
            notes=str(raw.get("notes", "")),
        )


def check_rating(value: float) -> float:
    v = float(value)
    if not (1.0 <= v <= 5.0):
        raise ValueError("rating must be between 1 and 5")
    return v


def suggest_id(title: str, taken: set) -> str:
    base = _slug(title)
    candidate, n = base, 2
    while candidate in taken:
        candidate = "%s-%d" % (base, n)
        n += 1
    return candidate

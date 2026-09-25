"""roundtable — persistent topic-structured group memory.

Studied from: revival-50-more-20260916-0009/report-part1.md (Section 18).

Load-bearing idea: curated, persistent discussion areas organized by
topic; topics hold threads; each topic keeps a *community memory* — an
extractive summary of its most-referenced messages, so newcomers inherit
what the group already decided matters.

LEVI's take: ``RoundTable`` owns ``Topic``s; topics own ``Thread``s;
threads own ``Message``s. Messages can *reference* other messages
(agreeing, answering, building on them). ``community_memory(topic)``
ranks messages by reference count across the whole topic — the most
cited messages ARE the extractive summary — and returns them with their
citation counts. ``save``/``load`` make the memory persistent as plain
JSON. No accounts, no transport: the model is the memory discipline.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union


ORIGIN = "levi-revival/roundtable"


@dataclass
class Message:
    id: str
    author: str
    text: str
    ts: float
    references: List[str] = field(default_factory=list)  # message ids this one cites


@dataclass
class Thread:
    id: str
    title: str
    opened_by: str
    opened_at: float
    messages: List[Message] = field(default_factory=list)


@dataclass
class Topic:
    name: str
    description: str
    curator: str
    threads: Dict[str, Thread] = field(default_factory=dict)


@dataclass
class MemoryEntry:
    message_id: str
    author: str
    text: str
    citations: int
    thread_title: str


class RoundTable:
    """Curated persistent discussion areas with extractive community memory."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.topics: Dict[str, Topic] = {}

    # -- curation -------------------------------------------------------

    def add_topic(self, name: str, description: str, curator: str) -> Topic:
        if name in self.topics:
            raise ValueError(f"topic {name!r} already exists")
        topic = Topic(name=name, description=description, curator=curator)
        self.topics[name] = topic
        return topic

    def open_thread(
        self, topic_name: str, title: str, opened_by: str, now: Optional[float] = None
    ) -> Thread:
        topic = self._topic(topic_name)
        thread = Thread(
            id=uuid.uuid4().hex[:8],
            title=title,
            opened_by=opened_by,
            opened_at=now if now is not None else time.time(),
        )
        topic.threads[thread.id] = thread
        return thread

    def post(
        self,
        topic_name: str,
        thread_id: str,
        author: str,
        text: str,
        references: Optional[List[str]] = None,
        now: Optional[float] = None,
    ) -> Message:
        thread = self._thread(topic_name, thread_id)
        msg = Message(
            id=uuid.uuid4().hex[:8],
            author=author,
            text=text,
            ts=now if now is not None else time.time(),
            references=list(references or []),
        )
        thread.messages.append(msg)
        return msg

    # -- community memory: extractive ------------------------------------

    def community_memory(self, topic_name: str, n: int = 5) -> List[MemoryEntry]:
        """The topic's memory = its n most-referenced messages, cited.

        Extractive, not generative: what the group kept pointing at is
        what a newcomer should read first.
        """
        topic = self._topic(topic_name)
        citations: Dict[str, int] = {}
        index: Dict[str, Message] = {}
        thread_of: Dict[str, str] = {}
        for thread in topic.threads.values():
            for msg in thread.messages:
                index[msg.id] = msg
                thread_of[msg.id] = thread.title
                citations.setdefault(msg.id, 0)
                for ref in msg.references:
                    citations[ref] = citations.get(ref, 0) + 1
        ranked = sorted(
            (mid for mid in index if citations.get(mid, 0) > 0),
            key=lambda mid: (-citations[mid], index[mid].ts),
        )
        # If nothing is cited yet, the earliest messages seed the memory.
        if not ranked:
            ranked = sorted(index, key=lambda mid: index[mid].ts)[:n]
        return [
            MemoryEntry(
                message_id=mid,
                author=index[mid].author,
                text=index[mid].text,
                citations=citations.get(mid, 0),
                thread_title=thread_of[mid],
            )
            for mid in ranked[:n]
        ]

    def pulse(self, topic_name: str) -> Dict[str, int]:
        """One-line vitals: threads, messages, participants."""
        topic = self._topic(topic_name)
        authors = {m.author for t in topic.threads.values() for m in t.messages}
        return {
            "threads": len(topic.threads),
            "messages": sum(len(t.messages) for t in topic.threads.values()),
            "participants": len(authors),
        }

    # -- persistence ------------------------------------------------------

    def save(self, path: Union[str, Path]) -> Path:
        data = {
            "name": self.name,
            "topics": {
                name: {
                    "description": t.description,
                    "curator": t.curator,
                    "threads": {
                        tid: {
                            "title": th.title,
                            "opened_by": th.opened_by,
                            "opened_at": th.opened_at,
                            "messages": [
                                {
                                    "id": m.id,
                                    "author": m.author,
                                    "text": m.text,
                                    "ts": m.ts,
                                    "references": m.references,
                                }
                                for m in th.messages
                            ],
                        }
                        for tid, th in t.threads.items()
                    },
                }
                for name, t in self.topics.items()
            },
        }
        p = Path(path)
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return p

    @classmethod
    def load(cls, path: Union[str, Path]) -> "RoundTable":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        rt = cls(data["name"])
        for name, t in data["topics"].items():
            topic = rt.add_topic(name, t["description"], t["curator"])
            for tid, th in t["threads"].items():
                thread = Thread(
                    id=tid,
                    title=th["title"],
                    opened_by=th["opened_by"],
                    opened_at=th["opened_at"],
                )
                for m in th["messages"]:
                    thread.messages.append(Message(**m))
                topic.threads[tid] = thread
        return rt

    # -- internals --------------------------------------------------------

    def _topic(self, name: str) -> Topic:
        try:
            return self.topics[name]
        except KeyError:
            raise ValueError(f"unknown topic {name!r}") from None

    def _thread(self, topic_name: str, thread_id: str) -> Thread:
        topic = self._topic(topic_name)
        try:
            return topic.threads[thread_id]
        except KeyError:
            raise ValueError(f"unknown thread {thread_id!r}") from None

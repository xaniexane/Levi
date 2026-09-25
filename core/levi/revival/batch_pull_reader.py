"""Batch-pull reader: request topics, receive a compiled text bundle.

Studied from: dead-networks-20260916/report.md [StarText]

The studied shape: information-on-demand at 300 baud. A reader dials
in, requests topics, hangs up; the service compiles a text bundle from
those topics and the reader pulls it in one batch session — the
offline-reader/RSS pattern before either existed. Bandwidth is the
scarce resource, so everything is budgeted: page caps, character
budgets, pull-time estimates.

LEVI-native re-expression: a topic catalog, a request queue, and a
bundle compiler. `pull()` turns queued requests into a paged Bundle
with an honest transfer-time estimate at a configurable baud rate
(default 300). A `stream()` generator replays the bundle as chunks, so
downstream code can simulate the slow pull without any hardware.

Honest limits: baud timing is arithmetic (10 bits per character),
not a modem; the "service" is in-process, not dialed; estimates ignore
line noise, retries, and connect time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterator, List


ORIGIN = "levi-revival/batch-pull-reader"

# 300 baud, 8N1-ish: 10 bits per character is the classic estimate.
BITS_PER_CHAR = 10


@dataclass
class Topic:
    name: str
    fetch: Callable[[], str]
    max_chars: int = 4_000


@dataclass
class Page:
    number: int
    topic: str
    text: str


@dataclass
class Bundle:
    request_id: str
    pages: List[Page] = field(default_factory=list)
    baud: int = 300

    @property
    def chars(self) -> int:
        return sum(len(p.text) for p in self.pages)

    def estimate_seconds(self) -> float:
        """Honest arithmetic: chars * bits-per-char / baud."""
        if self.baud <= 0:
            raise ValueError("baud must be positive")
        return self.chars * BITS_PER_CHAR / self.baud

    def stream(self, chunk_chars: int = 40) -> Iterator[str]:
        """Replay the bundle as slow chunks, as a pull session would."""
        for page in self.pages:
            header = f"--- p{page.number} [{page.topic}] ---\n"
            body = header + page.text
            for i in range(0, len(body), chunk_chars):
                yield body[i : i + chunk_chars]


class BatchPullReader:
    """Catalog of topics, a request queue, and one-shot bundle pulls."""

    def __init__(self, baud: int = 300, page_chars: int = 1_000) -> None:
        if baud <= 0:
            raise ValueError("baud must be positive")
        self.baud = baud
        self.page_chars = page_chars
        self.catalog: Dict[str, Topic] = {}
        self._queue: List[str] = []
        self._pulls = 0

    def register(self, topic: Topic) -> None:
        self.catalog[topic.name] = topic

    def request(self, topic_name: str) -> None:
        if topic_name not in self.catalog:
            raise KeyError(f"unknown topic: {topic_name!r}")
        if topic_name not in self._queue:
            self._queue.append(topic_name)

    def cancel(self, topic_name: str) -> bool:
        if topic_name in self._queue:
            self._queue.remove(topic_name)
            return True
        return False

    @property
    def queued(self) -> List[str]:
        return list(self._queue)

    def pull(self) -> Bundle:
        """Compile the queue into a paged bundle and drain the queue."""
        self._pulls += 1
        bundle = Bundle(request_id=f"pull-{self._pulls:04d}", baud=self.baud)
        page_no = 0
        for name in self._queue:
            topic = self.catalog[name]
            text = topic.fetch()[: topic.max_chars]
            for i in range(0, max(len(text), 1), self.page_chars):
                page_no += 1
                bundle.pages.append(
                    Page(number=page_no, topic=name, text=text[i : i + self.page_chars])
                )
        self._queue.clear()
        return bundle

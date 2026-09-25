"""City freenet — the city as the interface.

Studied from: dead-networks-20260916, report.md [Cleveland Free-Net /
NPTN].

The mechanism, functionally: the whole service is shaped like a city —
districts as menus, local institutions as content. Its working core is
expert-volunteer Q&A with a 24-hour SLA: a resident asks a question,
it is routed to volunteers registered for the matching topic, and an
answer is owed within a day. Overdue questions get flagged and
re-routed instead of dying quietly. And the model is a franchise: a
city node can export its configuration as a template so the next city
starts from a working copy, not a blank page.

This module is a software analog of that pattern: ``CityNode`` (topics,
volunteers, a question queue with SLA tracking), ``Question`` (state
machine open -> answered, overdue detection, reroute), and
``export_template``/``from_template`` for the franchise mechanism. All
local, no network — the "franchise" is a serializable config.

Honesty: the 24-hour SLA is a deadline tracked in code; the module
cannot make a human answer — it can only flag, escalate, and reroute.
Topic matching is keyword-based, a heuristic, not expertise modeling.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

ORIGIN = "levi-revival/city-freenet"

SLA_SECONDS = 24 * 3600


@dataclass
class Volunteer:
    """An expert-volunteer: a person, their topics, their load."""

    name: str
    topics: Set[str] = field(default_factory=set)
    answered: int = 0


@dataclass
class Question:
    """One resident's question, with its SLA clock running."""

    _seq = 0

    id: str = field(init=False)
    topic: str = ""
    text: str = ""
    asked_by: str = ""
    asked_at: float = field(default_factory=time.time)
    assigned_to: Optional[str] = None
    answered_at: Optional[float] = None
    answer: str = ""
    reroutes: int = 0

    def __post_init__(self) -> None:
        Question._seq += 1
        self.id = f"q{Question._seq:05d}"

    @property
    def is_open(self) -> bool:
        return self.answered_at is None

    def overdue(self, now: Optional[float] = None) -> bool:
        now = now if now is not None else time.time()
        return self.is_open and (now - self.asked_at) > SLA_SECONDS


class CityNode:
    """One city's freenet: districts, volunteers, and the SLA queue."""

    def __init__(self, city: str, topics: Optional[List[str]] = None) -> None:
        self.city = city
        self.topics: Set[str] = set(topics or ())
        self.volunteers: Dict[str, Volunteer] = {}
        self.questions: Dict[str, Question] = {}

    # -- the franchise's raw material -------------------------------------

    def add_topic(self, topic: str) -> None:
        self.topics.add(topic.strip().lower())

    def register_volunteer(self, name: str, topics: List[str]) -> Volunteer:
        """A volunteer signs up for the topics they can answer."""
        name = name.strip()
        if not name:
            raise ValueError("volunteer name must be non-empty")
        known = {t.strip().lower() for t in topics}
        unknown = known - self.topics
        if unknown:
            raise ValueError(f"unknown topics for {self.city!r}: {sorted(unknown)}")
        vol = self.volunteers.get(name)
        if vol is None:
            vol = Volunteer(name=name)
            self.volunteers[name] = vol
        vol.topics |= known
        return vol

    # -- ask / route / answer ----------------------------------------------

    def ask(
        self,
        topic: str,
        text: str,
        asked_by: str = "resident",
        now: Optional[float] = None,
    ) -> Question:
        """A resident asks; the question is routed to a volunteer for the
        topic, least-loaded first."""
        topic = topic.strip().lower()
        if topic not in self.topics:
            raise ValueError(f"no such topic in {self.city!r}: {topic!r}")
        q = Question(
            topic=topic,
            text=text.strip(),
            asked_by=asked_by,
            asked_at=now if now is not None else time.time(),
        )
        self.questions[q.id] = q
        self._route(q)
        return q

    def _route(self, q: Question, exclude: Optional[str] = None) -> None:
        candidates = [
            v
            for v in self.volunteers.values()
            if q.topic in v.topics and v.name != exclude
        ]
        if not candidates:
            q.assigned_to = None
            return
        candidates.sort(key=lambda v: v.answered)
        q.assigned_to = candidates[0].name

    def answer(
        self, question_id: str, volunteer: str, answer: str, now: Optional[float] = None
    ) -> Question:
        q = self.questions.get(question_id)
        if q is None:
            raise KeyError(f"unknown question {question_id!r}")
        if not q.is_open:
            raise ValueError(f"question {question_id!r} already answered")
        q.answer = answer.strip()
        q.answered_at = now if now is not None else time.time()
        vol = self.volunteers.get(volunteer)
        if vol is not None:
            vol.answered += 1
        return q

    # -- the SLA: flag, escalate, reroute -----------------------------------

    def overdue_questions(self, now: Optional[float] = None) -> List[Question]:
        return [q for q in self.questions.values() if q.overdue(now)]

    def open_questions(self) -> List[Question]:
        return [q for q in self.questions.values() if q.is_open]

    def reroute_overdue(self, now: Optional[float] = None) -> List[Question]:
        """Overdue questions get a new volunteer (not the one who let the
        clock run out); returns the rerouted questions."""
        rerouted = []
        for q in self.overdue_questions(now):
            q.reroutes += 1
            self._route(q, exclude=q.assigned_to)
            rerouted.append(q)
        return rerouted

    def sla_stats(self, now: Optional[float] = None) -> Dict[str, float]:
        total = len(self.questions)
        answered = [q for q in self.questions.values() if not q.is_open]
        on_time = [q for q in answered if (q.answered_at - q.asked_at) <= SLA_SECONDS]
        return {
            "total": total,
            "open": len(self.open_questions()),
            "overdue": len(self.overdue_questions(now)),
            "answered": len(answered),
            "answered_on_time": len(on_time),
            "on_time_rate": (len(on_time) / len(answered)) if answered else 1.0,
        }

    # -- franchising: the next city starts from a working copy --------------

    def export_template(self) -> Dict:
        """A franchise packet: topics and volunteer roles, no people."""
        return {
            "city": self.city,
            "topics": sorted(self.topics),
            "roles": sorted({t for v in self.volunteers.values() for t in v.topics}),
        }

    @classmethod
    def from_template(cls, template: Dict, city: str) -> "CityNode":
        node = cls(city, topics=list(template.get("topics", ())))
        return node

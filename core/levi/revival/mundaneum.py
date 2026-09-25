"""Index facts and typed relations, not documents — with a query service.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #13)

Two load-bearing mechanisms, reimplemented from scratch:

1. **Relational indexing.** The store holds *facts* — (subject, relation,
   object, source) — with typed relations (``contradicts``, ``extends``,
   ``exemplifies``, ``causes``, ...). The collection answers questions;
   it doesn't just locate documents.

2. **The query service.** The user never touches the index. An
   intermediary — :class:`MundaneumService` — takes a question-shaped
   request, retrieves the relevant facts from across the store, and
   *synthesizes* a structured answer: supporting facts grouped by
   relation type, disagreements flagged where ``contradicts`` relations
   cross, every claim traceable to its source.

This is an original, from-scratch LEVI implementation — no historical
code is used or copied. Stdlib only, no network.

Honesty: the mechanisms revived are fact-level relational indexing and
the intermediary query-service. The synthesis is explicit assembly of a
sourced brief — it does not invent claims. Not revived: centralized
world-scale ambitions or any "paper internet" romance.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path


ORIGIN = "levi-revival/mundaneum"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MundaneumError(Exception):
    """Base class for mundaneum failures."""


class UnknownFact(MundaneumError):
    """No fact with that id."""


class UnknownRelation(MundaneumError):
    """The relation type is not registered."""


# ---------------------------------------------------------------------------
# Facts
# ---------------------------------------------------------------------------


@dataclass
class Fact:
    """One indexed fact: a typed relation between a subject and an object,
    always with a source."""

    fact_id: str
    subject: str
    relation: str
    obj: str
    source: str
    note: str = ""
    recorded_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "fact_id": self.fact_id,
            "subject": self.subject,
            "relation": self.relation,
            "object": self.obj,
            "source": self.source,
            "note": self.note,
            "recorded_at": self.recorded_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Fact":
        return cls(
            data["fact_id"],
            data["subject"],
            data["relation"],
            data["object"],
            data["source"],
            data.get("note", ""),
            data.get("recorded_at", 0.0),
        )


_RELATION_TYPES = (
    "is_a",
    "causes",
    "contradicts",
    "extends",
    "exemplifies",
    "precedes",
    "requires",
    "measured_as",
)


class Mundaneum:
    """The fact store: typed relations over subjects, every fact sourced."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.relations: dict[str, dict] = {
            name: {"inverse": None} for name in _RELATION_TYPES
        }
        self._facts: dict[str, Fact] = {}
        self._counter = 0
        if self.path is not None:
            self._load()

    # -- persistence ------------------------------------------------------
    def _file(self) -> Path:
        assert self.path is not None
        return self.path / "mundaneum.json"

    def _load(self) -> None:
        f = self._file()
        if not f.exists():
            return
        data = json.loads(f.read_text(encoding="utf-8"))
        self.relations = dict(data.get("relations", self.relations))
        self._counter = int(data.get("counter", 0))
        self._facts = {d["fact_id"]: Fact.from_dict(d) for d in data.get("facts", [])}

    def save(self) -> Path:
        """Persist the store. Only meaningful when constructed with a path."""
        if self.path is None:
            raise MundaneumError("no path: this store is in-memory only")
        self.path.mkdir(parents=True, exist_ok=True)
        target = self._file()
        tmp = target.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {
                    "relations": self.relations,
                    "counter": self._counter,
                    "facts": [fact.to_dict() for fact in self._facts.values()],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        tmp.replace(target)
        return target

    # -- relations ----------------------------------------------------------
    def define_relation(self, name: str, inverse: str | None = None) -> None:
        """Register a new typed relation. The built-ins cover the common
        analytic moves; define your own when they don't."""
        name = name.strip()
        if not name:
            raise ValueError("relation name must be non-empty")
        self.relations[name] = {"inverse": inverse}

    def relation_types(self) -> list[str]:
        return sorted(self.relations)

    # -- facts ---------------------------------------------------------------
    def record_fact(
        self, subject: str, relation: str, obj: str, source: str, note: str = ""
    ) -> Fact:
        """Index one fact. Relation must be a registered type; source is
        mandatory — an unsourced fact is not a fact, it's a rumor."""
        if relation not in self.relations:
            raise UnknownRelation(relation)
        for label, value in (("subject", subject), ("object", obj), ("source", source)):
            if not value or not value.strip():
                raise ValueError(f"{label} must be non-empty")
        self._counter += 1
        fact = Fact(
            fact_id=f"f{self._counter}",
            subject=subject.strip(),
            relation=relation,
            obj=obj.strip(),
            source=source.strip(),
            note=note,
        )
        self._facts[fact.fact_id] = fact
        return fact

    def get_fact(self, fact_id: str) -> Fact:
        try:
            return self._facts[fact_id]
        except KeyError:
            raise UnknownFact(fact_id) from None

    def facts_about(self, subject: str, relation: str | None = None) -> list[Fact]:
        """Every fact with this subject, optionally filtered to one
        relation type."""
        return [
            fact
            for fact in self._facts.values()
            if fact.subject == subject
            and (relation is None or fact.relation == relation)
        ]

    def relations_between(self, subject: str, obj: str) -> list[Fact]:
        """Every typed relation recorded between two subjects."""
        return [
            fact
            for fact in self._facts.values()
            if {fact.subject, fact.obj} == {subject, obj}
        ]

    def subjects(self) -> list[str]:
        return sorted({fact.subject for fact in self._facts.values()})

    def fact_count(self) -> int:
        return len(self._facts)


# ---------------------------------------------------------------------------
# The query service: the intermediary retrieves AND synthesizes
# ---------------------------------------------------------------------------


class Answer:
    """A synthesized brief: grouped supporting facts, contradictions
    flagged, every claim traceable to its source."""

    def __init__(
        self, about: str, grouped: dict[str, list[Fact]], conflicts: list[dict]
    ):
        self.about = about
        self.grouped = grouped
        self.conflicts = conflicts

    def render(self) -> str:
        lines = [f"What the index holds on {self.about!r}:"]
        if not self.grouped:
            lines.append("  (nothing recorded)")
        for relation in sorted(self.grouped):
            lines.append(f"  {relation}:")
            for fact in self.grouped[relation]:
                lines.append(f"    - {fact.obj}  [source: {fact.source}]")
        if self.conflicts:
            lines.append("  Where the index disagrees:")
            for conflict in self.conflicts:
                lines.append(
                    f"    ! {conflict['a'].obj!r} vs {conflict['b'].obj!r}"
                    f"  [sources: {conflict['a'].source} / {conflict['b'].source}]"
                )
        return "\n".join(lines)


class MundaneumService:
    """The intermediary. You ask; it retrieves across the whole store and
    synthesizes the answer. You never touch the index yourself."""

    def __init__(self, store: Mundaneum):
        self.store = store

    def answer(self, about: str, relations: list[str] | None = None) -> Answer:
        """Retrieve every fact about ``about`` (optionally limited to the
        given relation types) and synthesize a brief. Facts whose relation
        is ``contradicts`` are surfaced as disagreements, not buried."""
        facts = self.store.facts_about(about)
        if relations is not None:
            wanted = set(relations)
            facts = [f for f in facts if f.relation in wanted]
        grouped: dict[str, list[Fact]] = {}
        for fact in facts:
            grouped.setdefault(fact.relation, []).append(fact)
        conflicts = [
            {"a": a, "b": b}
            for a in grouped.get("contradicts", [])
            for b in grouped.get("contradicts", [])
            if a.fact_id < b.fact_id
        ]
        return Answer(about, grouped, conflicts)


__all__ = [
    "ORIGIN",
    "MundaneumError",
    "UnknownFact",
    "UnknownRelation",
    "Fact",
    "Mundaneum",
    "Answer",
    "MundaneumService",
]

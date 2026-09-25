"""Card data types, the read-only MemoryView protocol, and the local stub.

Cards never write to memory; they are derived, so there is no write loop.
``MemoryView`` is the read-only protocol the real memory must honor
(``end-to-middle-contract.md`` P2); ``DictMemoryView`` is the local stub
until that protocol is pinned.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Protocol, runtime_checkable

#: Closed relation set for card links.
RELATIONS = ("about", "decided-by", "supersedes", "cites", "contradicts")

#: Card kinds.
KINDS = ("entity", "topic", "decision")


@dataclass(frozen=True)
class Fact:
    """One memory fact as the card layer sees it."""

    id: str
    entity_id: str
    text: str
    seq: int = 0
    refers_to: tuple[str, ...] = ()
    conflicts_with: tuple[str, ...] = ()
    supersedes: str | None = None
    witness: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "refers_to", tuple(self.refers_to))
        object.__setattr__(self, "conflicts_with", tuple(self.conflicts_with))


@dataclass(frozen=True)
class Decision:
    """One consequential decision as the card layer sees it."""

    id: str
    entity_id: str
    summary: str
    receipt_id: str
    proof_handle: str = ""
    decider_entity_id: str = ""


@dataclass(frozen=True)
class Link:
    """Directed edge between cards; relation is from the closed set."""

    from_id: str
    to_id: str
    relation: str

    def __post_init__(self) -> None:
        if self.relation not in RELATIONS:
            raise ValueError(
                "cards: relation %r not in closed set %r" % (self.relation, RELATIONS)
            )

    def to_dict(self) -> dict[str, Any]:
        return {"from": self.from_id, "to": self.to_id, "relation": self.relation}


@dataclass(frozen=True)
class Card:
    """A derived view over one entity, topic, or decision.

    ``updated_at`` is a *logical* timestamp (the memory version at
    derivation), never wall-clock — cards stay byte-deterministic.
    """

    id: str
    kind: str
    title: str
    body: str
    links: tuple[Link, ...] = ()
    sources: tuple[str, ...] = ()
    version: int = 0
    updated_at: int = 0

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError("cards: kind %r not in %r" % (self.kind, KINDS))
        object.__setattr__(
            self,
            "links",
            tuple(
                sorted(
                    self.links,
                    key=lambda link: (link.from_id, link.to_id, link.relation),
                )
            ),
        )
        object.__setattr__(self, "sources", tuple(self.sources))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "body": self.body,
            "links": [link.to_dict() for link in self.links],
            "sources": list(self.sources),
            "version": self.version,
            "updated_at": self.updated_at,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


@runtime_checkable
class MemoryView(Protocol):
    """Read-only view over memory for card derivation."""

    def facts_about(self, entity_id: str) -> list[Fact]: ...
    def decisions_about(self, entity_id: str) -> list[Decision]: ...
    def entity_ids(self) -> list[str]: ...
    def entity_kind(self, entity_id: str) -> str: ...
    def entity_title(self, entity_id: str) -> str: ...
    def match(
        self, predicate: Callable[[Fact], bool], since_version: int
    ) -> list[Fact]: ...

    @property
    def version(self) -> int: ...


class DictMemoryView:
    """Local stub memory: facts/decisions keyed by entity, versioned.

    Mutations (add/remove/rename/merge) bump the logical ``version``;
    cards re-derive against it.
    """

    def __init__(self) -> None:
        self._facts: dict[str, Fact] = {}
        self._decisions: dict[str, Decision] = {}
        self._kinds: dict[str, str] = {}
        self._titles: dict[str, str] = {}
        self._seq = 0
        self._version = 0

    # -- protocol -------------------------------------------------------
    @property
    def version(self) -> int:
        return self._version

    def entity_ids(self) -> list[str]:
        ids = set(self._kinds) | {f.entity_id for f in self._facts.values()}
        ids |= {d.entity_id for d in self._decisions.values()}
        return sorted(ids)

    def entity_kind(self, entity_id: str) -> str:
        return self._kinds.get(entity_id, "entity")

    def entity_title(self, entity_id: str) -> str:
        return self._titles.get(entity_id, entity_id.replace("_", " "))

    def facts_about(self, entity_id: str) -> list[Fact]:
        return sorted(
            (f for f in self._facts.values() if f.entity_id == entity_id),
            key=lambda f: f.id,
        )

    def decisions_about(self, entity_id: str) -> list[Decision]:
        return sorted(
            (d for d in self._decisions.values() if d.entity_id == entity_id),
            key=lambda d: d.id,
        )

    def match(
        self, predicate: Callable[[Fact], bool], since_version: int
    ) -> list[Fact]:
        return sorted(
            (f for f in self._facts.values() if predicate(f) and f.seq > since_version),
            key=lambda f: f.id,
        )

    # -- mutations (test/stub surface) -----------------------------------
    def _bump(self) -> None:
        self._version += 1

    def set_entity(self, entity_id: str, kind: str = "entity", title: str = "") -> None:
        if kind not in KINDS:
            raise ValueError("cards: kind %r not in %r" % (kind, KINDS))
        self._kinds[entity_id] = kind
        if title:
            self._titles[entity_id] = title
        self._bump()

    def add_fact(self, fact: Fact) -> Fact:
        self._seq += 1
        stored = Fact(
            id=fact.id,
            entity_id=fact.entity_id,
            text=fact.text,
            seq=self._seq,
            refers_to=fact.refers_to,
            conflicts_with=fact.conflicts_with,
            supersedes=fact.supersedes,
            witness=fact.witness,
        )
        self._facts[stored.id] = stored
        self._bump()
        return stored

    def add_decision(self, decision: Decision) -> Decision:
        self._decisions[decision.id] = decision
        self._bump()
        return decision

    def remove_fact(self, fact_id: str) -> None:
        self._facts.pop(fact_id, None)
        self._bump()

    def remove_entity(self, entity_id: str) -> None:
        for fid in [f.id for f in self._facts.values() if f.entity_id == entity_id]:
            del self._facts[fid]
        for did in [d.id for d in self._decisions.values() if d.entity_id == entity_id]:
            del self._decisions[did]
        self._kinds.pop(entity_id, None)
        self._titles.pop(entity_id, None)
        self._bump()

    def rename_entity(self, old_id: str, new_id: str) -> None:
        for fid, fact in list(self._facts.items()):
            if fact.entity_id == old_id:
                self._facts[fid] = Fact(
                    id=fact.id,
                    entity_id=new_id,
                    text=fact.text,
                    seq=fact.seq,
                    refers_to=tuple(
                        new_id if r == old_id else r for r in fact.refers_to
                    ),
                    conflicts_with=fact.conflicts_with,
                    supersedes=fact.supersedes,
                    witness=fact.witness,
                )
        for did, dec in list(self._decisions.items()):
            if dec.entity_id == old_id:
                self._decisions[did] = Decision(
                    id=dec.id,
                    entity_id=new_id,
                    summary=dec.summary,
                    receipt_id=dec.receipt_id,
                    proof_handle=dec.proof_handle,
                    decider_entity_id=dec.decider_entity_id,
                )
        if old_id in self._kinds:
            self._kinds[new_id] = self._kinds.pop(old_id)
        if old_id in self._titles:
            self._titles[new_id] = self._titles.pop(old_id)
        self._bump()

    def merge_entities(self, src_id: str, dst_id: str) -> None:
        """Fold src's facts/decisions into dst; src's card disappears."""
        self.rename_entity(src_id, dst_id)
        # rename_entity already moved everything; drop src's kind/title
        # (rename moved them onto dst only if dst lacked them — keep dst's).
        self._bump()

    def fact(self, fact_id: str) -> Fact | None:
        return self._facts.get(fact_id)

    def all_facts(self) -> list[Fact]:
        return sorted(self._facts.values(), key=lambda f: f.id)

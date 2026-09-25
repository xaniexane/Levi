"""Rule / Fact / Budget / proof-tree data types for the prover.

Rules are data, not code: a rule is a head term plus body terms, an id,
and provenance. Facts are witnessed by construction — a fact without a
receipt id or observation stamp cannot be built, so unwitnessed leaves
are impossible in any proof tree.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .terms import Term, term_from_dict
from .unify import Subst


@dataclass(frozen=True)
class Rule:
    """A Horn-clause rule: ``head`` holds when every body term holds."""

    id: str
    head: Term
    body: tuple[Term, ...] = ()
    provenance: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("prover: Rule id must be a non-empty string")
        object.__setattr__(self, "body", tuple(self.body))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "head": self.head.to_dict(),
            "body": [b.to_dict() for b in self.body],
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class Fact:
    """A witnessed ground claim. ``witness`` is a receipt id or an
    observation stamp; empty witnesses are rejected at construction."""

    id: str
    term: Term
    witness: str

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("prover: Fact id must be a non-empty string")
        if not isinstance(self.witness, str) or not self.witness.strip():
            raise ValueError(
                "prover: Fact %r refused: witness stamp is required; "
                "unwitnessed leaves are impossible by construction" % (self.id,)
            )

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "term": self.term.to_dict(), "witness": self.witness}


@dataclass(frozen=True)
class Budget:
    """Search budget: depth, branch attempts, and wall-clock are all
    capped. Exceeding any cap is a receipted fault, never a hang."""

    max_depth: int = 32
    max_branches: int = 100_000
    max_ms: float = 5_000.0

    def __post_init__(self) -> None:
        if self.max_depth < 0 or self.max_branches < 0 or self.max_ms <= 0:
            raise ValueError("prover: Budget bounds must be non-negative")


@dataclass
class ProofNode:
    """One node of a proof tree.

    ``rule_used`` is a rule id for internal nodes, ``"fact:<id>"`` for
    leaves. ``witness`` is set on leaves only.
    """

    claim: Term
    rule_used: str | None
    subst: Subst
    children: list[ProofNode] = field(default_factory=list)
    witness: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim.to_dict(),
            "rule_used": self.rule_used,
            "subst": {k: v.to_dict() for k, v in self.subst.items()},
            "children": [c.to_dict() for c in self.children],
            "witness": self.witness,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProofNode:
        return cls(
            claim=term_from_dict(data["claim"]),
            rule_used=data["rule_used"],
            subst={k: term_from_dict(v) for k, v in data["subst"].items()},
            children=[cls.from_dict(c) for c in data["children"]],
            witness=data["witness"],
        )

    def to_json(self) -> str:
        """Canonical JSON: byte-identical for identical derivations."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def premises(self) -> set[str]:
        """Every premise id actually used in this tree (T4 completeness)."""
        found: set[str] = set()
        if self.rule_used:
            found.add(self.rule_used)
        for child in self.children:
            found |= child.premises()
        return found

    def leaves(self) -> list[ProofNode]:
        """Leaf nodes (facts); every leaf must carry a witness."""
        if not self.children:
            return [self]
        out: list[ProofNode] = []
        for child in self.children:
            out.extend(child.leaves())
        return out


@dataclass(frozen=True)
class ProofFault:
    """A receipted search fault: budget exhausted, never silence."""

    reason: str
    detail: str
    receipt_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "detail": self.detail,
            "receipt_id": self.receipt_id,
        }


@dataclass
class ProofOutcome:
    """Result of :func:`prove`: either a complete ``tree`` or a ``fault``."""

    tree: ProofNode | None = None
    fault: ProofFault | None = None
    audit: list[str] = field(default_factory=list)

    @property
    def proved(self) -> bool:
        return self.tree is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "proved": self.proved,
            "tree": self.tree.to_dict() if self.tree else None,
            "fault": self.fault.to_dict() if self.fault else None,
            "audit": list(self.audit),
        }

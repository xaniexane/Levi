"""Builder ranks: earned advancement, demotion on validated harm."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional

__all__ = [
    "Rank",
    "CAPABILITIES",
    "RANK_THRESHOLDS",
    "Builder",
    "has_capability",
    "advance",
    "demote",
]


class Rank(IntEnum):
    VISITOR = 0
    RESIDENT = 1
    BUILDER = 2
    ARCHITECT = 3


CAPABILITIES = {
    Rank.VISITOR: ("observe",),
    Rank.RESIDENT: ("observe", "propose"),
    Rank.BUILDER: ("observe", "propose", "build"),
    Rank.ARCHITECT: ("observe", "propose", "build", "create_region", "change_schema"),
}

# Validated contributions needed since last rank to advance one step.
RANK_THRESHOLDS = {
    Rank.VISITOR: 5,
    Rank.RESIDENT: 15,
    Rank.BUILDER: 40,
}


@dataclass
class Builder:
    """A builder identity. Rank is earned; receipts record every move."""

    agent_id: str
    rank: Rank = Rank.VISITOR
    contributions: int = 0
    receipts: List[Dict[str, Any]] = field(default_factory=list)

    def to_canonical(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "rank": int(self.rank),
            "contributions": self.contributions,
        }


def has_capability(builder: Builder, capability: str) -> bool:
    return capability in CAPABILITIES[builder.rank]


def _receipt(builder: Builder, now: Optional[float], **fields) -> None:
    entry = {"ts": time.time() if now is None else now, "agent_id": builder.agent_id}
    entry.update(fields)
    builder.receipts.append(entry)


def advance(
    builder: Builder,
    validated_work: int,
    peer_review: Callable[[int], bool],
    now: Optional[float] = None,
) -> bool:
    """Earn one rank step.

    Requires the rank's contribution threshold AND a passing peer
    review (SI review against schema + safety rungs, not popularity).
    Returns True when the rank moved.
    """
    if builder.rank == Rank.ARCHITECT:
        return False
    threshold = RANK_THRESHOLDS[builder.rank]
    if validated_work < threshold or not peer_review(validated_work):
        _receipt(
            builder,
            now,
            kind="advance_refused",
            work=validated_work,
            threshold=threshold,
        )
        return False
    old = builder.rank
    builder.rank = Rank(builder.rank + 1)
    builder.contributions += validated_work
    _receipt(
        builder,
        now,
        kind="advance",
        from_rank=old.name,
        to_rank=builder.rank.name,
    )
    return True


def demote(builder: Builder, reason: str, now: Optional[float] = None) -> None:
    """Demote one rank on a validated harmful addition."""
    old = builder.rank
    builder.rank = Rank(max(int(Rank.VISITOR), int(builder.rank) - 1))
    _receipt(
        builder,
        now,
        kind="demotion",
        from_rank=old.name,
        to_rank=builder.rank.name,
        reason=reason,
    )

"""Twin records: the unit of the lattice."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict

#: Valid twin kinds. ``one`` = the three All-in-One convergences;
#: ``seal`` = the creator-sealed camouflage arrangement.
KINDS = ("agent", "daemon", "shell", "one", "seal", "evolution")

#: The SER-21 duality: foreground acts, background shadows.
SIDES = ("fg", "bg")


def twin_id_for(kind: str, subject: str, side: str) -> str:
    """Stable twin id, e.g. ``agent:echo:fg``."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    if side not in SIDES:
        raise ValueError(f"side must be one of {SIDES}")
    return f"{kind}:{subject}:{side}"


def counterpart_side(side: str) -> str:
    return "bg" if side == "fg" else "fg"


@dataclass
class Twin:
    """A state mirror of one runtime entity.

    Twins never execute anything. They record: who the subject is, which
    side of the FG/BG duality this twin holds, who its counterpart is, the
    last known state, and when it last proved alive.
    """

    twin_id: str
    kind: str
    subject: str
    side: str
    pair_id: str
    state: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    promoted_at: float | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        if self.side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}")

    def heartbeat(self, state_update: Dict[str, Any] | None = None) -> None:
        self.last_heartbeat = time.time()
        if state_update:
            self.state.update(state_update)

    def age_since_heartbeat(self, now: float | None = None) -> float:
        return (time.time() if now is None else now) - self.last_heartbeat

    def is_stale(self, threshold_s: float, now: float | None = None) -> bool:
        return self.age_since_heartbeat(now) > threshold_s

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Twin":
        return cls(
            **{
                k: data[k]
                for k in (
                    "twin_id",
                    "kind",
                    "subject",
                    "side",
                    "pair_id",
                    "state",
                    "created_at",
                    "last_heartbeat",
                    "promoted_at",
                    "notes",
                )
            }
        )

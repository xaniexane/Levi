"""MOOD routing — the contract for handing a session to the decoy (L1).

THE POLICY IS CHAUNCEY'S CALL. This module does not decide who is
abusive. It cannot: there is no scoring, no heuristic, no model in this
file that labels a session. A session enters mood only when an explicit
routing decision exists — a :class:`PolicyEntry` naming that session,
recorded by Chauncey or his delegate.

``route_to_mood(session_id)`` raises :class:`PolicyRequiredError` unless
such an entry exists. That is the whole gate: no entry, no route, no
silent rerouting of real users (L1). Anything that *creates* a policy
entry lives outside this module, in Chauncey's hands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

__all__ = [
    "PolicyEntry",
    "PolicyError",
    "PolicyRequiredError",
    "Router",
]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PolicyError(Exception):
    """Base for routing-policy failures."""


class PolicyRequiredError(PolicyError):
    """No explicit routing decision exists for this session (L1).

    The session may NOT be handed to the decoy. Creating the decision
    is Chauncey's call — this module only enforces that the decision
    exists before routing happens.
    """


@dataclass(frozen=True)
class PolicyEntry:
    """An explicit routing decision. Immutable once recorded.

    ``decided_by`` names who made the call (Chauncey or his delegate);
    ``reason`` is the human reason, in plain words. Both are required —
    an anonymous or reasonless entry is rejected by :class:`Router`.
    """

    session_id: str
    decided_by: str
    reason: str
    at: str = field(default_factory=_utcnow)


class Router:
    """The routing gate. Decisions in, decoy out — nothing automatic."""

    def __init__(self) -> None:
        self._entries: Dict[str, PolicyEntry] = {}

    def record_decision(
        self,
        session_id: str,
        decided_by: str,
        reason: str,
        at: Optional[str] = None,
    ) -> PolicyEntry:
        """Record an explicit routing decision. Returns the entry.

        ``decided_by`` and ``reason`` must be non-empty: the module
        refuses anonymous routing decisions (L1, L9).
        """
        if not decided_by:
            raise PolicyError("decided_by is required: no anonymous decisions")
        if not reason:
            raise PolicyError("reason is required: no reasonless decisions")
        entry = PolicyEntry(
            session_id=session_id,
            decided_by=decided_by,
            reason=reason,
            at=at or _utcnow(),
        )
        self._entries[session_id] = entry
        return entry

    def revoke(self, session_id: str) -> bool:
        """Withdraw a routing decision. Returns True if one existed."""
        return self._entries.pop(session_id, None) is not None

    def has_decision(self, session_id: str) -> bool:
        return session_id in self._entries

    def route_to_mood(self, session_id: str) -> PolicyEntry:
        """Return the decision authorizing the decoy for this session.

        Raises :class:`PolicyRequiredError` when no explicit decision
        exists — the session stays on the real path. This is the gate
        that keeps real users out of the decoy (L1).
        """
        entry = self._entries.get(session_id)
        if entry is None:
            raise PolicyRequiredError(
                "no routing decision for session %r: the policy is "
                "Chauncey's call; refusing to reroute" % session_id
            )
        return entry

    @property
    def decisions(self) -> List[PolicyEntry]:
        return list(self._entries.values())

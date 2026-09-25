"""speechacts — conversation for action: the Coordinator.

Studied from: revival-50-more-20260916-0009/report-part2.md (Section 50).

Load-bearing idea: messages carry explicit speech acts — request, promise,
assert, declare — and every conversation is tracked through a commitment
state machine (requested -> promised -> fulfilled | declined) to completion.
Overdue promises surface instead of silently rotting.

LEVI's take: ``Conversation`` is the unit. A ``request`` opens a
``Commitment`` in state OPEN; only the addressee can move it — ``promise``
or ``decline`` — and only a promised commitment can be ``fulfill``ed.
Every transition is timestamped; ``overdue()`` names the promises past
their due line. Assertions and declarations are recorded as messages that
change shared understanding without opening commitments. No transport
here — this is the local model of the coordination discipline, so LEVI
can hold the shape of "who owes what to whom" in-process.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


ORIGIN = "levi-revival/speechacts"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SpeechActError(Exception):
    """Raised when a transition violates the commitment discipline."""


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------


class SpeechAct(str, Enum):
    """The explicit acts a message can carry."""

    REQUEST = "request"
    PROMISE = "promise"
    ASSERT = "assert"
    DECLARE = "declare"
    DECLINE = "decline"
    WITHDRAW = "withdraw"


class CommitmentState(str, Enum):
    """Where a commitment stands in the machine."""

    OPEN = "open"  # requested, not yet answered
    PROMISED = "promised"  # addressee committed, work outstanding
    FULFILLED = "fulfilled"  # completed
    DECLINED = "declined"  # refused; terminal
    WITHDRAWN = "withdrawn"  # requester pulled it back; terminal


@dataclass
class Message:
    """One uttered speech act inside a conversation."""

    id: str
    conversation_id: str
    sender: str
    act: SpeechAct
    content: str
    ts: float


@dataclass
class Commitment:
    """A tracked request moving through the state machine."""

    id: str
    conversation_id: str
    requester: str
    addressee: str
    description: str
    state: CommitmentState = CommitmentState.OPEN
    requested_at: float = 0.0
    promised_at: Optional[float] = None
    due_at: Optional[float] = None
    closed_at: Optional[float] = None
    evidence: str = ""


# ---------------------------------------------------------------------------
# Conversation
# ---------------------------------------------------------------------------


class Conversation:
    """Tracks messages and commitments for one conversation-for-action.

    The Coordinator's whole discipline, in-process: requests open
    commitments, the addressee promises or declines, promises are kept
    or flagged overdue. Asserts and declares are logged as shared
    understanding without opening commitments.
    """

    def __init__(self, conversation_id: Optional[str] = None) -> None:
        self.id = conversation_id or uuid.uuid4().hex[:12]
        self.messages: List[Message] = []
        self.commitments: Dict[str, Commitment] = {}

    # -- speech ---------------------------------------------------------

    def _utter(self, sender: str, act: SpeechAct, content: str, ts: float) -> Message:
        msg = Message(
            id=uuid.uuid4().hex[:12],
            conversation_id=self.id,
            sender=sender,
            act=act,
            content=content,
            ts=ts,
        )
        self.messages.append(msg)
        return msg

    def request(
        self,
        requester: str,
        addressee: str,
        description: str,
        due_in: Optional[float] = None,
        now: Optional[float] = None,
    ) -> Commitment:
        """Open a commitment: requester asks addressee to do something."""
        ts = now if now is not None else time.time()
        c = Commitment(
            id=uuid.uuid4().hex[:8],
            conversation_id=self.id,
            requester=requester,
            addressee=addressee,
            description=description,
            requested_at=ts,
            due_at=(ts + due_in) if due_in is not None else None,
        )
        self.commitments[c.id] = c
        self._utter(requester, SpeechAct.REQUEST, description, ts)
        return c

    def promise(
        self, commitment_id: str, by: str, now: Optional[float] = None
    ) -> Commitment:
        """The addressee commits. Only the addressee, only from OPEN."""
        c = self._get(commitment_id)
        if by != c.addressee:
            raise SpeechActError(f"only the addressee ({c.addressee}) can promise")
        if c.state is not CommitmentState.OPEN:
            raise SpeechActError(f"cannot promise a {c.state.value} commitment")
        ts = now if now is not None else time.time()
        c.state = CommitmentState.PROMISED
        c.promised_at = ts
        self._utter(by, SpeechAct.PROMISE, f"promises: {c.description}", ts)
        return c

    def decline(
        self,
        commitment_id: str,
        by: str,
        reason: str = "",
        now: Optional[float] = None,
    ) -> Commitment:
        """The addressee refuses. Terminal."""
        c = self._get(commitment_id)
        if by != c.addressee:
            raise SpeechActError(f"only the addressee ({c.addressee}) can decline")
        if c.state not in (CommitmentState.OPEN, CommitmentState.PROMISED):
            raise SpeechActError(f"cannot decline a {c.state.value} commitment")
        ts = now if now is not None else time.time()
        c.state = CommitmentState.DECLINED
        c.closed_at = ts
        self._utter(by, SpeechAct.DECLINE, reason or f"declines: {c.description}", ts)
        return c

    def fulfill(
        self,
        commitment_id: str,
        by: str,
        evidence: str = "",
        now: Optional[float] = None,
    ) -> Commitment:
        """Mark a promised commitment fulfilled. Only from PROMISED."""
        c = self._get(commitment_id)
        if by != c.addressee:
            raise SpeechActError(f"only the addressee ({c.addressee}) can fulfill")
        if c.state is not CommitmentState.PROMISED:
            raise SpeechActError(f"cannot fulfill a {c.state.value} commitment")
        ts = now if now is not None else time.time()
        c.state = CommitmentState.FULFILLED
        c.closed_at = ts
        c.evidence = evidence
        self._utter(by, SpeechAct.ASSERT, evidence or f"done: {c.description}", ts)
        return c

    def withdraw(
        self, commitment_id: str, by: str, now: Optional[float] = None
    ) -> Commitment:
        """The requester pulls the request back. Terminal."""
        c = self._get(commitment_id)
        if by != c.requester:
            raise SpeechActError(f"only the requester ({c.requester}) can withdraw")
        if c.state in (CommitmentState.FULFILLED, CommitmentState.DECLINED):
            raise SpeechActError(f"cannot withdraw a {c.state.value} commitment")
        ts = now if now is not None else time.time()
        c.state = CommitmentState.WITHDRAWN
        c.closed_at = ts
        self._utter(by, SpeechAct.WITHDRAW, f"withdraws: {c.description}", ts)
        return c

    def assert_(
        self, sender: str, content: str, now: Optional[float] = None
    ) -> Message:
        """Record shared understanding; opens no commitment."""
        return self._utter(
            sender, SpeechAct.ASSERT, content, now if now is not None else time.time()
        )

    def declare(
        self, sender: str, content: str, now: Optional[float] = None
    ) -> Message:
        """A declaration that changes the shared state by being said."""
        return self._utter(
            sender, SpeechAct.DECLARE, content, now if now is not None else time.time()
        )

    # -- reading the room ------------------------------------------------

    def pending(self) -> List[Commitment]:
        """Commitments still outstanding: open or promised."""
        return [
            c
            for c in self.commitments.values()
            if c.state in (CommitmentState.OPEN, CommitmentState.PROMISED)
        ]

    def overdue(self, now: Optional[float] = None) -> List[Commitment]:
        """Promised commitments past their due line. Surfaced, not silent."""
        ts = now if now is not None else time.time()
        return [
            c
            for c in self.commitments.values()
            if c.state is CommitmentState.PROMISED
            and c.due_at is not None
            and c.due_at < ts
        ]

    def log(self, act: Optional[SpeechAct] = None) -> List[Message]:
        """The message log, optionally filtered to one act."""
        if act is None:
            return list(self.messages)
        return [m for m in self.messages if m.act is act]

    def _get(self, commitment_id: str) -> Commitment:
        try:
            return self.commitments[commitment_id]
        except KeyError:
            raise SpeechActError(f"unknown commitment {commitment_id!r}") from None


def conversation_summary(conv: Conversation) -> Dict[str, int]:
    """One-line health of a conversation-for-action."""
    counts: Dict[str, int] = {s.value: 0 for s in CommitmentState}
    for c in conv.commitments.values():
        counts[c.state.value] += 1
    return counts

"""Voice-session signalling in the Jingle style.

Studied from: dead-networks-20260916 (Google Talk section of report.md).
Jingle carries voice call set-up as signalling over a chat channel: a
session is *initiated* with a content description (the voice codecs the
caller offers), *accepted* with the mutually agreeable terms, and later
*terminated*. Transport candidates (how to reach the other side) ride
alongside, but media itself flows out of band.

This module implements the signalling machinery, not any network I/O:
a codec-negotiation step, a session lifecycle state machine with typed
refusals, and candidate gathering. Anything that would send bytes over a
wire is left to the caller.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

__all__ = [
    "Codec",
    "SessionState",
    "SignallingError",
    "UnknownSession",
    "BadTransition",
    "NoCommonCodec",
    "negotiate_codecs",
    "Candidate",
    "JingleSession",
    "SessionManager",
]

ORIGIN = "levi-revival/jingle"


# ---------------------------------------------------------------------------
# Codecs and negotiation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Codec:
    """One offered voice codec: a name and a preference weight (higher = better)."""

    name: str
    preference: int = 0


def negotiate_codecs(offered: list[Codec], answered: list[Codec]) -> Codec:
    """Pick the highest-preference codec named by both sides.

    The responder's preference order decides between several common names
    (their preference reflects what they most want to use); the offerer's
    preference is the tie-breaker.
    """
    offer_map = {c.name.lower(): c for c in offered}
    common = [c for c in answered if c.name.lower() in offer_map]
    if not common:
        raise NoCommonCodec("no codec is offered by both sides")
    return max(
        common, key=lambda c: (c.preference, offer_map[c.name.lower()].preference)
    )


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


class SessionState(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    TERMINATED = "terminated"


class SignallingError(Exception):
    """Base class for voice-signalling failures."""


class UnknownSession(SignallingError):
    """No session exists under that id."""


class BadTransition(SignallingError):
    """The session is in a state that does not allow this action."""


class NoCommonCodec(SignallingError):
    """Codec negotiation failed: the two sides share no codec."""


@dataclass(frozen=True)
class Candidate:
    """One candidate path for media (e.g. host/port/protocol triple)."""

    kind: str  # e.g. "host", "relay"
    address: str
    port: int


@dataclass
class JingleSession:
    """One voice session, from initiation to termination."""

    session_id: str
    initiator: str
    responder: str
    state: SessionState = SessionState.PENDING
    offered_codecs: list[Codec] = field(default_factory=list)
    agreed_codec: Optional[Codec] = None
    candidates: list[Candidate] = field(default_factory=list)

    def add_candidate(self, candidate: Candidate) -> None:
        """Attach a media transport candidate while the session is live."""
        if self.state is SessionState.TERMINATED:
            raise BadTransition("cannot add candidates to a terminated session")
        self.candidates.append(candidate)


class SessionManager:
    """In-process manager of voice sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, JingleSession] = {}
        self._counter = 0

    # -- lifecycle --------------------------------------------------------
    def initiate(
        self, initiator: str, responder: str, codecs: list[Codec]
    ) -> JingleSession:
        """Open a pending session: initiator offers voice codecs."""
        if not codecs:
            raise SignallingError("initiation requires at least one offered codec")
        self._counter += 1
        session_id = f"jingle-{self._counter}"
        session = JingleSession(
            session_id=session_id,
            initiator=initiator,
            responder=responder,
            offered_codecs=list(codecs),
        )
        self._sessions[session_id] = session
        return session

    def accept(self, session_id: str, codecs: list[Codec]) -> Codec:
        """Responder answers: negotiate a common codec and activate the session."""
        session = self._get(session_id)
        if session.state is not SessionState.PENDING:
            raise BadTransition(f"session {session_id} is {session.state.value}")
        agreed = negotiate_codecs(session.offered_codecs, codecs)
        session.agreed_codec = agreed
        session.state = SessionState.ACTIVE
        return agreed

    def terminate(self, session_id: str) -> None:
        """End a session; terminated sessions cannot be revived."""
        session = self._get(session_id)
        session.state = SessionState.TERMINATED

    def get(self, session_id: str) -> JingleSession:
        return self._get(session_id)

    def active_sessions(self) -> list[JingleSession]:
        return [s for s in self._sessions.values() if s.state is SessionState.ACTIVE]

    def _get(self, session_id: str) -> JingleSession:
        try:
            return self._sessions[session_id]
        except KeyError:
            raise UnknownSession(f"no such session: {session_id!r}") from None

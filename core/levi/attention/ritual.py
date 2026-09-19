"""The answer-tone ritual: Bell 103's handshake as a local pairing ceremony.

The Bell 103 modems negotiated before they spoke: the answering station
raised its answer tone (2225/2025 Hz) — "I am here, and here is what I can
do" — and both ends settled on the best shared mode before any payload
moved. Higher-speed modems kept Bell 103 as the honest fallback.

This module is the ritual grammar, clean-roomed, without the tones:

    probe   initiator announces itself + capabilities (no secrets in the probe)
    answer  responder announces its capability set and names its terms
    confirm both commit to the intersection, or abort honestly naming the mismatch

Ordering is enforced: answer without probe, or confirm without answer,
raises. No payload moves before confirm. This is an ordering ritual, not
authentication — like SELCAL's chime, it is a summons, not an identity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

__all__ = ["probe", "answer", "confirm", "Probe", "Answer", "Session", "RitualError"]


class RitualError(Exception):
    """The ritual was performed out of order, or the terms did not meet."""


@dataclass(frozen=True)
class Probe:
    initiator: str
    capabilities: frozenset
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class Answer:
    responder: str
    capabilities: frozenset
    terms: str
    probe_initiator: str
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class Session:
    initiator: str
    responder: str
    shared: frozenset
    terms: str
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def probe(initiator: str, capabilities: List[str]) -> Probe:
    """Raise the call: 'I am here, and here is what I can do.'

    Capabilities are plain names. Never put secrets in the probe —
    the ritual is introduction, not confession.
    """
    if not initiator or not str(initiator).strip():
        raise RitualError("probe needs a named initiator")
    caps = frozenset(str(c).strip().lower() for c in capabilities if str(c).strip())
    if not caps:
        raise RitualError("probe must declare at least one capability")
    return Probe(initiator=str(initiator).strip(), capabilities=caps)


def answer(responder: str, probe_msg: Probe, capabilities: List[str], terms: str = "") -> Answer:
    """The answer tone: 'I am here, here is what I can do, here are my terms.'"""
    if not isinstance(probe_msg, Probe):
        raise RitualError("answer requires a probe first — no cold answers")
    if not responder or not str(responder).strip():
        raise RitualError("answer needs a named responder")
    caps = frozenset(str(c).strip().lower() for c in capabilities if str(c).strip())
    if not caps:
        raise RitualError("answer must declare at least one capability")
    return Answer(
        responder=str(responder).strip(),
        capabilities=caps,
        terms=str(terms).strip(),
        probe_initiator=probe_msg.initiator,
    )


def confirm(probe_msg: Probe, answer_msg: Answer) -> Session:
    """Commit to the intersection, or abort honestly naming the mismatch."""
    if not isinstance(probe_msg, Probe) or not isinstance(answer_msg, Answer):
        raise RitualError("confirm requires a probe and an answer, in order")
    if answer_msg.probe_initiator != probe_msg.initiator:
        raise RitualError(
            f"answer was for {answer_msg.probe_initiator!r}, not {probe_msg.initiator!r}"
        )
    shared = probe_msg.capabilities & answer_msg.capabilities
    if not shared:
        raise RitualError(
            f"no shared capability: {probe_msg.initiator} offers "
            f"{sorted(probe_msg.capabilities)}, {answer_msg.responder} offers "
            f"{sorted(answer_msg.capabilities)} — aborting honestly"
        )
    return Session(
        initiator=probe_msg.initiator,
        responder=answer_msg.responder,
        shared=shared,
        terms=answer_msg.terms,
    )

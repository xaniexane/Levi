"""Handshake engine — the answer-tone ritual rebuilt as a LEVI-native decision machine.

Clean-room rebuild of the *pattern* behind the Bell 103 (1962) modem
handshake, queued in the wave-019 hunt: two dumb devices negotiate a
shared language before saying anything real — tone, offer,
acknowledgment, then speech. The archive record describes the
*technique*; this module is original stdlib-only code re-implementing
the *idea* — never any artifact's text, never a paid anything.

An engine, so it is pure and stateless: both sides' capability lists
arrive with the input, and the verdict is deterministic — same inputs,
same verdict, every time. The ritual:

1. The responder emits an answer tone (it is listening).
2. The initiator offers its capabilities in preference order.
3. The responder keeps only the capabilities it also speaks.
4. The first shared capability in initiator-preference order is agreed;
   acknowledgment closes the ritual. With nothing shared, the channel
   closes politely — no common language, no half-agreement.

Input schema::

    {
        "initiator": {"id": "levi", "capabilities": ["text/v1", "text/v0"]},
        "responder": {"id": "relay", "capabilities": ["text/v0", "beep/v0"]},
    }

Verdict::

    {"agreed": "text/v0" | None, "initiator": id, "responder": id,
     "shared": [...], "offered": [...]}
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from levi.engines.base import Engine, EngineInputError, EngineResult, registry


def _validate_side(side: Any, name: str) -> Dict[str, Any]:
    if not isinstance(side, dict):
        raise EngineInputError(f"handshake: '{name}' must be a dict")
    sid = side.get("id")
    caps = side.get("capabilities")
    if not isinstance(sid, str) or not sid.strip():
        raise EngineInputError(f"handshake: '{name}.id' must be a non-empty str")
    if (
        not isinstance(caps, list)
        or not caps
        or not all(isinstance(c, str) and c.strip() for c in caps)
    ):
        raise EngineInputError(
            f"handshake: '{name}.capabilities' must be a non-empty list of non-empty str"
        )
    caps = [c.strip() for c in caps]
    if len(set(caps)) != len(caps):
        raise EngineInputError(f"handshake: '{name}.capabilities' must be unique")
    return {"id": sid.strip(), "capabilities": caps}


def _handshake(inputs: Dict[str, Any]) -> EngineResult:
    initiator = _validate_side(inputs.get("initiator"), "initiator")
    responder = _validate_side(inputs.get("responder"), "responder")

    trace: List[str] = [
        f"tone: responder '{responder['id']}' answers (listening)",
        f"offer: initiator '{initiator['id']}' proposes {initiator['capabilities']}",
    ]

    responder_set = set(responder["capabilities"])
    shared = [c for c in initiator["capabilities"] if c in responder_set]
    trace.append(f"filter: responder keeps {shared or '(none)'}")

    agreed: Optional[str] = shared[0] if shared else None
    if agreed is not None:
        trace.append(f"ack: agreed on '{agreed}' — channel open")
    else:
        trace.append("ack: no common language — channel closed politely")

    verdict = {
        "agreed": agreed,
        "initiator": initiator["id"],
        "responder": responder["id"],
        "shared": shared,
        "offered": initiator["capabilities"],
    }
    return EngineResult(
        engine_id="handshake",
        verdict=verdict,
        confidence=1.0,  # set intersection is certain, either way
        trace=trace,
    )


HANDSHAKE_ENGINE = Engine(
    id="handshake",
    name="Handshake",
    description=(
        "Capability negotiation between two parties: the initiator offers "
        "capabilities in preference order, the responder keeps the overlap, "
        "and the first shared capability in preference order is agreed — "
        "or the ritual closes politely with no common language."
    ),
    required=("initiator", "responder"),
    schema={
        "initiator": "{id:str, capabilities:[str]} (preference order)",
        "responder": "{id:str, capabilities:[str]}",
    },
    risk="info",
    handler=_handshake,
)

registry.register(HANDSHAKE_ENGINE)

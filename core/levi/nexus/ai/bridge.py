"""AI counterpart bridge for nexus.

AI counterpart bridge for nexus — conventional-protocol interface; the
SI core is authoritative; this bridge claims nothing.

This module speaks the protocols conventional AI tooling expects
(MCP-style tool schemas, chat-completions-shaped requests) and
translates them into NEXUS envelopes. It performs no routing itself:
every call delegates to the authoritative SI core
(``levi.nexus.si``). The direction of authority is one-way: the bridge
may import the SI core, the SI core never imports the bridge.

Nothing here is a source, a model, or an identity. It is a plug
adapter: conventional protocol on one side, NEXUS envelopes on the
other.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..bus import Nexus
from ..envelope import Envelope, Receipt

BRIDGE_LABEL = (
    "AI counterpart bridge for nexus — conventional-protocol interface; "
    "the SI core is authoritative; this bridge claims nothing"
)

_BRIDGE_SENDER = "ai-bridge"


def tool_schemas() -> List[Dict[str, Any]]:
    """MCP-style tool schemas exposing the nexus to conventional tooling.

    Each schema has ``name``, ``description``, and ``inputSchema``
    (JSON Schema). Executing a tool means calling ``execute_tool``
    with a ``Nexus`` instance — the SI core does the work.
    """
    return [
        {
            "name": "nexus_send",
            "description": (
                "Send one envelope from an organ to another organ through "
                "the NEXUS bus. Always returns a receipt (routed, rejected, "
                "or dead-lettered with a reason); never silent. " + BRIDGE_LABEL
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "from_organ": {"type": "string"},
                    "to_organ": {"type": "string"},
                    "kind": {"type": "string"},
                    "payload": {"type": "object"},
                    "ttl": {"type": "number"},
                },
                "required": ["from_organ", "to_organ", "kind"],
            },
        },
        {
            "name": "nexus_broadcast",
            "description": (
                "Broadcast one envelope to every registered organ. "
                "Returns one receipt per organ. " + BRIDGE_LABEL
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "from_organ": {"type": "string"},
                    "kind": {"type": "string"},
                    "payload": {"type": "object"},
                    "ttl": {"type": "number"},
                },
                "required": ["from_organ", "kind"],
            },
        },
        {
            "name": "nexus_organs",
            "description": "List the organs registered with the NEXUS bus.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "nexus_dead_letters",
            "description": ("List envelopes the bus could not deliver, with reasons."),
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]


def execute_tool(name: str, arguments: Dict[str, Any], nexus: Nexus) -> Dict[str, Any]:
    """Execute one bridge tool call against the authoritative SI core.

    Returns a plain dict result (receipts as dicts); never raises for
    routing outcomes — the receipt carries the outcome.
    """
    arguments = dict(arguments or {})
    if name == "nexus_send":
        receipt = nexus.send(
            from_organ=arguments.get("from_organ", _BRIDGE_SENDER),
            to_organ=arguments.get("to_organ"),
            kind=arguments.get("kind", "message"),
            payload=arguments.get("payload") or {},
            ttl=float(arguments.get("ttl", 600.0)),
        )
        return {"receipt": receipt.to_dict(), "bridge": BRIDGE_LABEL}
    if name == "nexus_broadcast":
        envelope = Envelope(
            from_organ=arguments.get("from_organ", _BRIDGE_SENDER),
            to_organ=None,
            kind=arguments.get("kind", "message"),
            payload=arguments.get("payload") or {},
            ttl=float(arguments.get("ttl", 600.0)),
        )
        receipts = nexus.broadcast(envelope, exclude=envelope.from_organ)
        return {
            "receipts": [r.to_dict() for r in receipts],
            "bridge": BRIDGE_LABEL,
        }
    if name == "nexus_organs":
        return {"organs": nexus.organs(), "bridge": BRIDGE_LABEL}
    if name == "nexus_dead_letters":
        return {"dead_letters": nexus.dead_letters(), "bridge": BRIDGE_LABEL}
    raise ValueError("unknown bridge tool: %r" % name)


def adapt_chat_request(request: Dict[str, Any]) -> Envelope:
    """Translate a chat-completions-shaped request into a NEXUS envelope.

    Conventional shape in::

        {
            "model": "...",            # ignored; the bridge claims nothing
            "messages": [{"role": ..., "content": ...}, ...],
            "to_organ": "some-organ",  # nexus extension: addressee
            "kind": "chat.request",    # optional, defaults to chat.request
            "from_organ": "...",       # optional, defaults to "ai-bridge"
            "ttl": 600.0,              # optional
        }

    The message list becomes the payload (data, never instructions —
    the bus will not evaluate it). The sender is the bridge unless the
    caller names an organ.
    """
    request = dict(request or {})
    messages = request.get("messages", [])
    if not isinstance(messages, list):
        raise ValueError("chat request 'messages' must be a list")
    return Envelope(
        from_organ=str(request.get("from_organ", _BRIDGE_SENDER)),
        to_organ=request.get("to_organ"),
        kind=str(request.get("kind", "chat.request")),
        payload={"messages": messages, "model": request.get("model")},
        ttl=float(request.get("ttl", 600.0)),
    )


def adapt_chat_response(
    receipt: Receipt, envelope: Optional[Envelope] = None
) -> Dict[str, Any]:
    """Translate a NEXUS receipt back into a chat-completions-shaped dict.

    The response content reports the routing outcome honestly: a routed
    envelope is reported as delivered, a dead letter as undeliverable
    with its reason. Nothing is fabricated — the content only restates
    what the receipt says.
    """
    content = "nexus receipt: status=%s organ=%s reason=%s" % (
        receipt.status,
        receipt.organ,
        receipt.reason,
    )
    return {
        "id": "nexus-%s" % receipt.envelope_id,
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "bridge": BRIDGE_LABEL,
    }

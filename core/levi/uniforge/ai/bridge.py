"""AI counterpart bridge for uniforge — conventional-protocol interface; the SI core is authoritative; this bridge claims nothing.

This module speaks the protocols conventional AI tooling expects
(MCP-style tool schemas, chat-completions-shaped messages) so external
agents can *describe* a forge run in their own idiom. It does not plan,
it does not execute, and it never invents authority it does not have:
every schema's description names the SI core as the actor, and every
adapter function marks its output as a rendering of core data.

The SI core (:mod:`levi.uniforge.si`) never imports this module.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List

BRIDGE_LABEL = (
    "AI counterpart bridge for uniforge — conventional-protocol interface; "
    "the SI core is authoritative; this bridge claims nothing"
)

#: Marker stamped on every adapter output so a completion can be proven
#: to have been rendered by this bridge (and not hallucinated).
_BRIDGE_MARKER = "uniforge-bridge-v1"


class BridgeError(Exception):
    """The bridge was asked to do something it honestly cannot."""


def tool_schemas() -> List[Dict[str, Any]]:
    """MCP-style tool schemas describing what the SI core can do.

    Descriptions, not capabilities: calling these through an external
    agent still routes through the SI core's planner and the forge law.
    """
    return [
        {
            "name": "uniforge.plan",
            "description": (
                "Ask the UniForge SI core to assemble a build plan "
                "(dry-run preview). The SI core is authoritative; this "
                "schema is a conventional-protocol description only."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "targets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Target ids: python-package, static-site, "
                            "android-apk-scaffold"
                        ),
                    },
                    "workdir": {
                        "type": "string",
                        "description": "Source root the plan builds from",
                    },
                },
                "required": ["targets"],
            },
        },
        {
            "name": "uniforge.build",
            "description": (
                "Ask the UniForge SI core to run a forge plan through "
                "Plan -> Preview -> Permission -> Execute -> Verify -> "
                "Receipt. Dry-run unless live=true; live runs still "
                "require explicit permission. The SI core is "
                "authoritative; this schema claims nothing."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "targets": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "workdir": {"type": "string"},
                    "live": {
                        "type": "boolean",
                        "description": "Execute for real (permission-gated)",
                    },
                },
                "required": ["targets"],
            },
        },
    ]


def plan_to_completion(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Render a plan dict as a chat-completions-shaped response.

    Pure formatting of core data — no model is consulted, and the
    marker proves provenance to :func:`completion_to_plan_request`.
    """
    lines = [
        "[%s] %s" % (_BRIDGE_MARKER, BRIDGE_LABEL),
        "Plan: %s" % plan.get("name", "?"),
        "Targets: %s" % ", ".join(plan.get("targets", [])),
        "Steps:",
    ]
    for s in plan.get("steps", []):
        lines.append(
            "  - [%s] %s (%s)"
            % (s.get("target", "?"), s.get("label", "?"), " ".join(s.get("argv", [])))
        )
    return {
        "id": "chatcmpl-" + uuid.uuid4().hex[:12],
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "uniforge-bridge",
        "bridge": BRIDGE_LABEL,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "\n".join(lines),
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def completion_to_plan_request(completion: Dict[str, Any]) -> Dict[str, Any]:
    """Recover a plan request from a bridge-rendered completion.

    Refuses completions that lack the bridge marker — the bridge will
    not launder text it did not render.
    """
    try:
        content = completion["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise BridgeError("not a chat-completions-shaped object: %s" % exc) from exc
    if _BRIDGE_MARKER not in content:
        raise BridgeError(
            "completion lacks the bridge marker: not rendered by this bridge"
        )
    targets: List[str] = []
    for line in content.splitlines():
        if line.startswith("Targets:"):
            targets = [
                t.strip() for t in line[len("Targets:") :].split(",") if t.strip()
            ]
    return {"targets": targets, "bridge": BRIDGE_LABEL}

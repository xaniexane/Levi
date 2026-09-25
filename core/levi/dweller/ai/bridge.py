"""AI counterpart bridge for dweller — conventional-protocol interface; the SI core is authoritative; this bridge claims nothing.

This module speaks the protocols conventional AI tooling expects
(MCP-style tool schemas, chat-completions-shaped messages) so external
agents can *describe* a grind in their own idiom. It does not queue, it
does not grind, and it never invents authority it does not have: every
schema's description names the SI core as the actor, and every adapter
function marks its output as a rendering of core data.

The SI core (:mod:`levi.dweller.si`) never imports this module.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List

BRIDGE_LABEL = (
    "AI counterpart bridge for dweller — conventional-protocol interface; "
    "the SI core is authoritative; this bridge claims nothing"
)

#: Marker stamped on every adapter output so a completion can be proven
#: to have been rendered by this bridge (and not hallucinated).
_BRIDGE_MARKER = "dweller-bridge-v1"


class BridgeError(Exception):
    """The bridge was asked to do something it honestly cannot."""


def tool_schemas() -> List[Dict[str, Any]]:
    """MCP-style tool schemas describing what the SI core can do.

    Descriptions, not capabilities: calling these through an external
    agent still routes through the SI core's grind engine and the
    labor law (sandbox, permission gate, receipt).
    """
    return [
        {
            "name": "dweller.grind",
            "description": (
                "Ask the Dweller SI core to grind a job "
                "(repo-sweep, crossref, or watch) under its sandbox, "
                "through the permission gate, with a receipt. The SI "
                "core is authoritative; this schema is a "
                "conventional-protocol description only."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["repo-sweep", "crossref", "watch"],
                    },
                    "params": {
                        "type": "object",
                        "description": "Runner params (paths must sit inside the job's sandbox root)",
                    },
                    "sandbox_root": {
                        "type": "string",
                        "description": "Sandbox the job may not leave",
                    },
                    "live": {
                        "type": "boolean",
                        "description": "Execute for real (permission-gated); default is dry-run",
                    },
                },
                "required": ["kind", "sandbox_root"],
            },
        },
        {
            "name": "dweller.jobs",
            "description": (
                "Ask the Dweller SI core to list queued jobs. Read-only "
                "listing; the SI core is authoritative and this schema "
                "claims nothing."
            ),
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "dweller.receipt",
            "description": (
                "Ask the Dweller SI core for a job's final receipt. Every "
                "job gets one, even failures. The SI core is "
                "authoritative; this schema claims nothing."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {"job_id": {"type": "string"}},
                "required": ["job_id"],
            },
        },
    ]


def job_to_completion(job: Dict[str, Any]) -> Dict[str, Any]:
    """Render a job dict as a chat-completions-shaped response.

    Pure formatting of core data — no model is consulted, and the
    marker proves provenance to :func:`completion_to_grind_request`.
    """
    lines = [
        "[%s] %s" % (_BRIDGE_MARKER, BRIDGE_LABEL),
        "Job: %s (%s)" % (job.get("id", "?"), job.get("kind", "?")),
        "State: %s" % job.get("state", "?"),
        "Sandbox: %s" % job.get("sandbox_root", "?"),
        "Steps:",
    ]
    for s in job.get("steps", []):
        lines.append(
            "  - [%s] %s (%s)"
            % (s.get("state", "?"), s.get("label", "?"), s.get("kind", "?"))
        )
    return {
        "id": "chatcmpl-" + uuid.uuid4().hex[:12],
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "dweller-bridge",
        "bridge": BRIDGE_LABEL,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "\n".join(lines)},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def completion_to_grind_request(completion: Dict[str, Any]) -> Dict[str, Any]:
    """Recover a grind request from a bridge-rendered completion.

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
    kind, sandbox = "", ""
    for line in content.splitlines():
        if line.startswith("Job:"):
            inner = line[len("Job:") :].strip()
            if "(" in inner and inner.endswith(")"):
                kind = inner[inner.index("(") + 1 : -1].strip()
        elif line.startswith("Sandbox:"):
            sandbox = line[len("Sandbox:") :].strip()
    return {"kind": kind, "sandbox_root": sandbox, "bridge": BRIDGE_LABEL}

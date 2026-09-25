"""Gate registry for the counsel-desk capability.

A gate registry: which actions require which approvals. Pure state machine,
no legal content. The attorney handoff is the terminal gate of every legal
workflow — a workflow cannot be marked complete until a licensed attorney
is named as reviewer.

Context keys understood by ``check``:
* ``owner_consent`` (bool) — the owner opted into the action.
* ``named_attorney`` (str|None) — the licensed attorney reviewing the work.
* ``chauncey_approval`` (bool) — Chauncey's explicit word for owner-gated
  decisions (external sources, content licensing, wording, release).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

# Intake verdicts: the ternary. QUARANTINE is the skipped third state
# between ACCEPT and REJECT — stored but not indexed, held for review.
VERDICT_ACCEPT = "accept"
VERDICT_QUARANTINE = "quarantine"
VERDICT_REJECT = "reject"

VERDICTS = (VERDICT_ACCEPT, VERDICT_QUARANTINE, VERDICT_REJECT)

ACTIONS: Dict[str, Dict[str, Any]] = {
    "intake_document": {
        "requires": ["owner_consent"],
        "terminal": False,
        "why": "Storing a document in the local vault is opt-in. "
        "Nothing is ingested without the owner's consent.",
    },
    "retrieve": {
        "requires": ["owner_consent"],
        "terminal": False,
        "why": "Searching the owner's corpus is opt-in. Consent for intake "
        "covers retrieval of the same vault.",
    },
    "run_ocr": {
        "requires": ["owner_consent"],
        "terminal": False,
        "why": "OCR runs only as a local system tool (e.g. tesseract). "
        "Cloud OCR is forbidden — see enable_cloud_ocr.",
    },
    "enable_cloud_ocr": {
        "requires": ["forbidden"],
        "terminal": False,
        "why": "PERMANENTLY DENIED. Privileged documents never leave the "
        "machine for any external OCR service. Local-only is physics.",
    },
    "use_external_source": {
        "requires": ["chauncey_approval"],
        "terminal": False,
        "why": "Any legal database, content feed, or hosted research source "
        "needs Chauncey's explicit word (destination, scope, account, "
        "copy, terms).",
    },
    "export_handoff_packet": {
        "requires": ["owner_consent", "named_attorney"],
        "terminal": False,
        "why": "A handoff packet is only meaningful addressed to a reviewer. "
        "Export names the attorney; the packet is a draft until reviewed.",
    },
    "mark_workflow_complete": {
        "requires": ["named_attorney"],
        "terminal": True,
        "why": "TERMINAL GATE. Every legal workflow ends in the attorney "
        "handoff. Without a named licensed attorney reviewer, the workflow "
        "is incomplete by definition — it does not finish, it waits.",
    },
}


def requirements(action: str) -> List[str]:
    """Approval keys an action requires. Unknown actions require nothing
    known — which is itself a signal: they are not registered."""
    entry = ACTIONS.get(action)
    if entry is None:
        return []
    return list(entry["requires"])


def is_registered(action: str) -> bool:
    return action in ACTIONS


def check(action: str, context: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Evaluate an action against the gate registry.

    Returns (allowed, missing). ``missing`` names the approvals not yet
    satisfied. An unknown action is denied with a single reason so that
    unregistered actions fail closed.
    """
    if action not in ACTIONS:
        return False, ["unregistered-action"]
    missing: List[str] = []
    for key in ACTIONS[action]["requires"]:
        if key == "forbidden":
            return False, ["forbidden"]
        value = context.get(key)
        if key == "named_attorney":
            if not value or not str(value).strip():
                missing.append(key)
        elif not value:
            missing.append(key)
    return (len(missing) == 0), missing


def require_attorney(packet: Dict[str, Any], attorney_name: str) -> Dict[str, Any]:
    """Name the licensed attorney reviewer on a handoff packet.

    Returns the updated packet. An empty name raises; the gate cannot be
    satisfied with a blank. Marking a workflow complete is only possible
    through this path — the name is the key, not a checkbox.
    """
    name = (attorney_name or "").strip()
    if not name:
        raise ValueError("named_attorney must be a non-empty name")
    packet = dict(packet)
    packet["named_attorney"] = name
    return packet

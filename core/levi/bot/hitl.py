"""HITL dialog handling for the LEVI bot (additive).

Lets the conversational bot present an automation :class:`GateRequest`
in chat and parse the human's reply back into a gate decision — so the
Permission step of the automation rail can happen in plain conversation.

This module only *presents*, *parses*, and *receipts*. It never executes
automation and never invents decisions: an unparseable reply is not a yes,
a dead responder is a denial, and every resolution is appended to
``hitl.jsonl`` — including denials.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from levi.automation.hitl import GateKind, GateRequest, describe_gate

_YES = re.compile(
    r"\b(yes|yeah|yep|approve|approved|ok|okay|go ahead|do it|confirmed)\b", re.I
)
_NO = re.compile(r"\b(no|nope|deny|denied|cancel|stop|don't|do not)\b", re.I)


def present_gate(request: GateRequest) -> str:
    """Render a gate request as a chat message in LEVI's voice."""
    lines = [
        "🙃 Hold up — I need your call on this.",
        f"Minion: {request.minion_id}",
        f"Plan: {request.prompt}",
        describe_gate(request.kind),
    ]
    if request.kind is GateKind.EDIT_APPROVE:
        lines.append("Reply with your edits, then 'approve' — or just 'approve'.")
    elif request.kind in (GateKind.APPROVAL, GateKind.CONFIRM):
        lines.append("Reply 'yes' to let it through, 'no' to stop it.")
    elif request.kind is GateKind.ACKNOWLEDGE:
        lines.append("Reply 'ack' when you've seen it.")
    elif request.kind is GateKind.DIALOG:
        lines.append("Talk to me — I'll take it from here.")
    return "\n".join(lines)


def parse_reply(text: str, request: GateRequest) -> Optional[Dict[str, object]]:
    """Parse a chat reply into a responder answer dict.

    Returns ``None`` when the reply carries no decision — the caller
    must ask again, never assume.
    """
    said = (text or "").strip()
    if not said:
        return None
    low = said.lower()

    if request.kind is GateKind.NOTIFICATION:
        return {"decision": "noted", "note": "notification seen in chat"}

    if request.kind is GateKind.ACKNOWLEDGE:
        if re.search(r"\b(ack|acknowledge|seen|got it|noted)\b", low):
            return {"decision": "acknowledged"}
        return None

    if request.kind is GateKind.EDIT_APPROVE:
        if _YES.search(said) and not _NO.search(said):
            # Anything before the approval counts as the human's edits.
            edited = re.sub(
                r"\b(approve|approved|yes|ok|okay)\b\.?\s*$", "", said, flags=re.I
            ).strip(" ,.-")
            answer: Dict[str, object] = {"decision": "approved"}
            if edited:
                answer = {
                    "decision": "edited",
                    "edited_payload": {"human_edits": edited},
                }
            return answer
        if _NO.search(said):
            return {"decision": "denied"}
        return None

    if _YES.search(said) and not _NO.search(said):
        return {"decision": "approved"}
    if _NO.search(said):
        return {"decision": "denied"}
    return None


def chat_responder(request: GateRequest, reply_text: str) -> Dict[str, object]:
    """A Responder that answers one gate from a single chat reply.

    Unparseable replies resolve to ``denied`` — fail closed, never
    presume consent.
    """
    parsed = parse_reply(reply_text, request)
    if parsed is None:
        return {"decision": "denied", "note": "reply carried no decision"}
    return parsed


# ---------------------------------------------------------------------------
# Gate receipts (hitl.jsonl) and fail-closed resolution
# ---------------------------------------------------------------------------

_KNOWN_DECISIONS = frozenset({"approved", "denied", "edited", "acknowledged", "noted"})


def _hitl_log_path() -> str:
    """Path to the append-only JSONL gate-decision log."""
    override = os.environ.get("LEVI_BOT_HOME")
    base = (
        os.path.join(override, "bot")
        if override
        else os.path.join(os.path.expanduser("~"), ".levi", "bot")
    )
    return os.path.join(base, "hitl.jsonl")


def record_gate_decision(
    request: GateRequest,
    decision: str,
    note: str = "",
    *,
    decided_by: str = "chat responder",
) -> Dict[str, Any]:
    """Append one HITL decision receipt to ``hitl.jsonl`` (best-effort).

    Every gate resolution — approval, denial, edit, ack, note — is
    receipted with the rail fields: what was planned (the gate prompt),
    what was approved (the decision + who decided), what executed
    (nothing — gates never execute), and the fail-closed verification.
    Never raises; a logging failure must not change a gate outcome.
    """
    fail_closed = decision in _KNOWN_DECISIONS
    entry: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "minion_id": request.minion_id,
        "kind": request.kind.value,
        "planned": request.prompt,
        "approved": decision,
        "decided_by": decided_by,
        "note": note,
        "executed": (
            "none — a gate records the human's decision; downstream "
            "automation may act only on approved/edited/acknowledged/noted"
        ),
        "verified": (
            "fail-closed check: %r is a known terminal decision" % (decision,)
            if fail_closed
            else "fail-closed check FAILED: unknown decision %r" % (decision,)
        ),
    }
    try:
        path = _hitl_log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return entry


def read_gate_log(limit: int = 20) -> list:
    """Read recent gate-decision receipts (newest last). Tolerates corruption."""
    path = _hitl_log_path()
    if not os.path.exists(path):
        return []
    records: list = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict):
                    records.append(rec)
    except OSError:
        return []
    return records[-limit:]


def resolve_gate(
    request: GateRequest,
    responder,
    *,
    decided_by: str = "responder",
) -> Dict[str, object]:
    """Resolve a gate through *responder*, fail-closed, and receipt it.

    ``responder`` is any callable taking the :class:`GateRequest` and
    returning an answer dict (see :func:`chat_responder` for the chat
    flavor). Fail-closed semantics:

    * the responder raises → ``denied`` (the error is receipted, not hidden)
    * the responder returns nothing / no ``decision`` key → ``denied``
    * the decision string is not a known terminal decision → ``denied``
    * ``NOTIFICATION`` kind → ``noted`` (it never blocks)

    The outcome is always receipted via :func:`record_gate_decision` —
    including denials. Returns the normalized answer dict.
    """
    note = ""
    try:
        answer = responder(request) or {}
    except Exception as exc:  # noqa: BLE001 - a dead responder must not open the gate
        answer = {}
        note = "responder failed (%s: %s) — gate denied" % (
            type(exc).__name__,
            exc,
        )
    if not isinstance(answer, dict):
        answer = {}
        note = (
            note + "; " if note else ""
        ) + "responder returned a non-dict answer — gate denied"

    if request.kind is GateKind.NOTIFICATION:
        decision = "noted"
    else:
        decision = str(answer.get("decision", "denied")).strip().lower()
        if decision not in _KNOWN_DECISIONS:
            note = (note + "; " if note else "") + (
                "unknown decision %r coerced to denied" % (answer.get("decision"),)
            )
            decision = "denied"

    reply_note = str(answer.get("note", "") or "")
    full_note = "; ".join(part for part in (reply_note, note) if part)
    resolved: Dict[str, object] = {"decision": decision, "note": full_note}
    if answer.get("edited_payload") is not None:
        resolved["edited_payload"] = answer["edited_payload"]
    record_gate_decision(request, decision, full_note, decided_by=decided_by)
    return resolved

"""Stationery: named reply templates with slots. DRAFTS ONLY.

Stationery composes drafts — it never sends. There is deliberately no
send path in this module: sending is a consequential action requiring
the user's explicit approval elsewhere, per the standing email
authority (exact text approved, never bulk).

Every draft carries its ``template_id`` and its slot fillings, so a
draft always explains which template produced it.
"""

from __future__ import annotations

from dataclasses import dataclass
from email.utils import parseaddr
from typing import Any, Dict, List, Optional

__all__ = ["Stationery", "compose", "sent_count"]

# Module-level invariant for T5: stationery has no send path, so this
# stays zero. It exists only so tests can assert the invariant.
sent_count = 0


@dataclass(frozen=True)
class Stationery:
    """A named template with ``{slots}``."""

    id: str
    subject: str
    body: str
    slots: tuple = ()


def _first_name(message: Dict[str, Any]) -> str:
    name, _addr = parseaddr(str(message.get("from", "")))
    return name.split()[0] if name else ""


def _slot_values(message: Dict[str, Any], extra: Dict[str, str]) -> Dict[str, str]:
    values = {
        "sender": str(message.get("from", "")),
        "subject": str(message.get("subject", "")),
        "first_name": _first_name(message),
    }
    values.update(extra)
    return values


def compose(
    template: Stationery,
    message: Dict[str, Any],
    slots: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Compose a draft from a stationery template. Returns a draft dict.

    The draft is labeled ``template-draft — NOT sent`` and records the
    template id and slot fillings. Nothing here sends anything.
    """
    fillings = _slot_values(message, slots or {})
    subject = template.subject.format_map(_SafeMap(fillings))
    body = template.body.format_map(_SafeMap(fillings))
    return {
        "kind": "template-draft — NOT sent",
        "template_id": template.id,
        "slot_fillings": {k: fillings.get(k, "") for k in template.slots},
        "in_reply_to": message.get("id", ""),
        "subject": subject,
        "body": body,
        "status": "draft",
    }


class _SafeMap(dict):
    """format_map that leaves unknown slots as literal ``{slot}``."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def default_stationery() -> List[Stationery]:
    return [
        Stationery(
            id="thanks",
            subject="Re: {subject}",
            body="You're very welcome, {first_name}.\n\n— template draft, not sent",
            slots=("sender", "subject", "first_name"),
        ),
        Stationery(
            id="ack",
            subject="Re: {subject}",
            body="Confirmed — noted on my side, {first_name}.\n\n— template draft, not sent",
            slots=("sender", "subject", "first_name"),
        ),
        Stationery(
            id="decline",
            subject="Re: {subject}",
            body=(
                "Thanks for thinking of me, {first_name} — I'll have to pass "
                "this time.\n\n— template draft, not sent"
            ),
            slots=("sender", "subject", "first_name"),
        ),
    ]

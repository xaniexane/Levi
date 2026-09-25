"""Canonical notices for the counsel-desk capability.

THE WORDING BELOW IS A DRAFT. The exact not-legal-advice language is a
legal-exposure surface and is GATED ON CHAUNCEY's word. Do not present this
text to any owner as final, and do not copy it into user-facing surfaces
until he has settled it.

What this module holds is document assembly (fixed text blocks + a handoff
packet seed), never legal conclusions or advice.
"""

from __future__ import annotations

from typing import Any, Dict, List

NOTICE_STATUS = "DRAFT-FOR-REVIEW — wording gated on Chauncey (2026-09-21)"

NOT_LEGAL_ADVICE_DRAFT = """\
[DRAFT — not final language. Exact wording is gated on the owner's review.]

THIS IS NOT LEGAL ADVICE.

The counsel-desk capability organizes and retrieves your own documents. It
does not advise you, does not recommend a course of action, does not assess
whether a document applies to your situation, whether it is enforceable,
or what any court or counterparty would do.

Nothing here creates an attorney-client relationship, and nothing here is
a substitute for review by a licensed attorney. Before acting on any
document this capability touches, consult a licensed attorney.
"""

# What the explainer/handoff is structurally forbidden from claiming.
NOT_ASSESSED = [
    "applicability of any document to your situation",
    "enforceability of any clause or agreement",
    "strategy, negotiation position, or what you should do",
    "likely outcomes, timelines, or counterparty behavior",
    "jurisdiction-specific requirements or deadlines",
]


def not_assessed_list() -> List[str]:
    """Fixed list of things the capability does not assess."""
    return list(NOT_ASSESSED)


def handoff_seed(
    doc_id: str,
    source_spans: List[Dict[str, Any]],
    what_was_done: str,
) -> Dict[str, Any]:
    """Assemble the draft attorney-handoff packet seed for analyzed material.

    This is document assembly only: it states what was analyzed, carries
    the draft notice, lists what was NOT assessed, and leaves the attorney
    field empty. A workflow packet without a named attorney is incomplete
    by definition (see ``levi.counsel.gates.require_attorney``).
    """
    return {
        "status": "draft",
        "doc_id": doc_id,
        "what_was_done": what_was_done,
        "source_spans": list(source_spans),
        "notice": NOT_LEGAL_ADVICE_DRAFT,
        "notice_status": NOTICE_STATUS,
        "not_assessed": not_assessed_list(),
        "named_attorney": None,  # must be filled before completion
        "workflow_complete": False,
    }

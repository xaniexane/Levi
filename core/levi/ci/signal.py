"""Verdict → growth-loop signal.

A counsel verdict is a hard-case judgment — exactly the kind of signal the
keeper's standing design note says should become growth-loop training
signal. :func:`export_verdict` banks the verdict into the growth journal
as a provisional, functional learning ("when X, counsel judged Y") so the
growth loop's harvest → reflect → consolidate cycle can pick it up.

Learnings are functional, never phenomenal — the phrasing here keeps them
that way so the growth guards have nothing to block. The signal carries
the verdict id and receipt linkage so the loop can corroborate, never
just believe.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from levi.growth import journal as growth_journal


def verdict_learning_text(verdict: Any, ruling_context: str = "") -> str:
    """Functional phrasing of the verdict for the growth loop."""
    agent = getattr(verdict, "agent_id", "") or verdict.minion_id
    text = (
        f"When agent {agent} (class {verdict.minion_class}) faced "
        f"'{verdict.case_fingerprint[:12]}', {verdict.counsel} counseled "
        f"'{verdict.ruling}'"
        + (f" with conditions: {'; '.join(verdict.conditions)}"
           if verdict.conditions else "")
    )
    divergence = getattr(verdict, "divergence", None)
    if divergence:
        text += (
            f"; the twin pair diverged (left held '{divergence['left_stance']}', "
            f"right held '{divergence['right_stance']}') and counsel resolved "
            f"it to '{divergence['resolution']}'"
        )
    if getattr(verdict, "escalate_to_keeper", False):
        text += "; counsel reached its ceiling and escalated to the keeper"
    text += (f". {ruling_context}" if ruling_context else "") + (
        ". Counsel advises; the agent pair decides."
    )
    return text


def export_verdict(
    verdict: Any,
    receipt: Optional[Dict[str, Any]] = None,
    ruling_context: str = "",
) -> Dict[str, Any]:
    """Append the verdict to the growth journal as training signal."""
    entry = {
        "kind": "counsel_verdict",
        "status": "provisional",
        "counsel": verdict.counsel,
        "minion_id": verdict.minion_id,
        "minion_class": verdict.minion_class,
        "case_fingerprint": verdict.case_fingerprint,
        "ruling": verdict.ruling,
        "learning": verdict_learning_text(verdict, ruling_context),
        "receipt_seq": receipt["seq"] if receipt else None,
        "receipt_hash": receipt["body_hash"] if receipt else None,
        "substrate": verdict.substrate.get("substrate", "local"),
        "source": "ci-counsel",
    }
    return growth_journal.append_entry(entry)

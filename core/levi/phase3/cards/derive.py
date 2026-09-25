"""Pure card derivation: ``card = derive(memory_state, entity_id)``.

Same memory state -> same card, always. Bodies are deterministic
template renders over fixed-order facts — no generative improvisation
in card bodies; the template render is the card's truth.
"""

from __future__ import annotations

from .types import Card, Decision, Fact, MemoryView


def card_id_for(entity_id: str) -> str:
    return "card:" + entity_id


def decision_card_id_for(decision_id: str) -> str:
    return "card:decision:" + decision_id


def summarize(facts: list[Fact], decisions: list[Decision]) -> str:
    """Honest-fallback narration: deterministic template, fixed order."""
    lines = ["Facts (%d):" % len(facts)]
    for f in facts:
        witness = " [witness %s]" % f.witness if f.witness else ""
        lines.append("- [%s] %s%s" % (f.id, f.text, witness))
    lines.append("Decisions (%d):" % len(decisions))
    for d in decisions:
        proof = " [proof %s]" % d.proof_handle if d.proof_handle else ""
        lines.append(
            "- [%s] %s (receipt %s)%s" % (d.id, d.summary, d.receipt_id, proof)
        )
    return "\n".join(lines)


def derive(entity_id: str, view: MemoryView) -> Card:
    """Derive the card for one entity/topic. Pure function of the view."""
    facts = view.facts_about(entity_id)  # fixed order: sorted by id
    decisions = view.decisions_about(entity_id)  # fixed order: sorted by id
    return Card(
        id=card_id_for(entity_id),
        kind=view.entity_kind(entity_id),
        title=view.entity_title(entity_id),
        body=summarize(facts, decisions),
        links=(),
        sources=tuple([f.id for f in facts] + [d.id for d in decisions]),
        version=view.version,
        updated_at=view.version,
    )


def derive_decision(decision: Decision, view: MemoryView) -> Card:
    """Derive the card for one consequential decision.

    The card carries the receipt id and the prover's proof handle — it is
    the human-readable face of the receipt.
    """
    body_lines = [
        "Decision: %s" % decision.summary,
        "Receipt: %s" % decision.receipt_id,
    ]
    if decision.proof_handle:
        body_lines.append("Proof: %s" % decision.proof_handle)
    body_lines.append("About: %s" % view.entity_title(decision.entity_id))
    return Card(
        id=decision_card_id_for(decision.id),
        kind="decision",
        title="Decision %s" % decision.id,
        body="\n".join(body_lines),
        links=(),
        sources=(decision.id,),
        version=view.version,
        updated_at=view.version,
    )

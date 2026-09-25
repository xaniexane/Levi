"""Proof-as-explanation: render a proof tree as a plain-speech "why" walk.

``explain`` walks the tree and states, for every step, which rule matched
and which receipt witnessed each leaf fact. This is the receipt's
evidence rendered readable — not a second system, and not a thought.
"""

from __future__ import annotations

from .rules import ProofNode, ProofOutcome


def explain(outcome: ProofOutcome) -> str:
    """Render ``outcome`` as plain speech.

    A proved claim becomes a "because ..." walk; a fault becomes the
    receipted incompleteness statement.
    """
    if outcome.fault is not None:
        f = outcome.fault
        if f.reason == "budget-exhausted":
            return "%s (receipt %s)" % (f.detail, f.receipt_id)
        return "unprovable: %s (receipt %s)" % (f.detail, f.receipt_id)
    assert outcome.tree is not None
    lines = ["claim: %r" % (outcome.tree.claim,), "because:"]
    _walk(outcome.tree, lines, 1)
    return "\n".join(lines)


def _walk(node: ProofNode, lines: list[str], depth: int) -> None:
    pad = "  " * depth
    if not node.children:
        lines.append(
            "%s- %r was witnessed by receipt %s (fact %s)."
            % (pad, node.claim, node.witness, _fact_id(node.rule_used))
        )
        return
    lines.append("%s- rule %r matched %r," % (pad, node.rule_used, node.claim))
    for child in node.children:
        _walk(child, lines, depth + 1)


def _fact_id(rule_used: str | None) -> str:
    if rule_used and rule_used.startswith("fact:"):
        return rule_used[len("fact:") :]
    return rule_used or "?"

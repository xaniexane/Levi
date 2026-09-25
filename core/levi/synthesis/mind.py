"""The mind: one reasoning entry point over the organism's two substrates.

Pipeline — brain-first, rules-verdict:

1. The native-brain weights continue the task text. That continuation is a
   raw proof-of-learning sample, labeled "not reasoning", heard as one
   proposal among others — never obeyed, never the verdict.
2. The rules engine deliberates (propose -> critique -> verdict) and decides.
3. The answer ships with ``substrate`` (which mind reasoned) and ``limits``
   (what each mind did and did not do).

``brain_policy="rules-only"`` never touches the weights (Reasoner with
``brain_chars=0``): fastest path, no torch needed. Any brain failure under
``"auto"`` degrades to an honest rules-only report — never an exception,
never a silent fallback.

HARD RAILS: no sentience/subjective-experience claims — the brain is a
continuation engine, the rules engine is a deliberator, and the report says
exactly that. See docs/SYNTHESIS.md for the full honesty contract.
"""

from __future__ import annotations

from typing import Any, Dict

ORIGIN = "levi-synthesis/mind"

BRAIN_POLICIES = ("auto", "rules-only")


def _reasoner(brain_policy: str):
    from levi.alpha.reason import Reasoner

    if brain_policy == "rules-only":
        return Reasoner(brain_chars=0)
    return Reasoner()


def ask(task: str, brain_policy: str = "auto") -> Dict[str, Any]:
    """Reason over ``task``.

    ``brain_policy`` is positional-or-keyword by contract with the Phase 2
    flagship, which calls ``ask(task, policy)`` as the deliberative partner
    to the scan-mind.

    Returns the Reasoner report unchanged: ``answer``, ``substrate``,
    ``limits``, ``proposals``, ``critiques``, ``verdict``, ``brain``.
    Raises ``ValueError`` on empty tasks or unknown policies.
    """
    if brain_policy not in BRAIN_POLICIES:
        raise ValueError(
            f"unknown brain_policy {brain_policy!r}; want one of {BRAIN_POLICIES}"
        )
    return _reasoner(brain_policy).reason(task)


def substrate(*, brain_policy: str = "auto") -> Dict[str, Any]:
    """What *would* reason — the substrate report without a deliberation."""
    if brain_policy not in BRAIN_POLICIES:
        raise ValueError(
            f"unknown brain_policy {brain_policy!r}; want one of {BRAIN_POLICIES}"
        )
    return _reasoner(brain_policy).substrate_report()


__all__ = ["ORIGIN", "BRAIN_POLICIES", "ask", "substrate"]

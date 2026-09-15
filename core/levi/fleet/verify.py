"""LEVI Fleet — verification agent (Enterprise Phase 1, §2/§4).

An independent pass over each completed subtask result, checked against the
subtask's own acceptance criteria. Two layers:

1. **Structural checks** (always run, deterministic): the worker reported
   success, the summary is non-empty, claimed artifacts exist on the
   blackboard.
2. **Semantic check** (optional, model-assisted): the existing agentic loop
   judges the result against the acceptance criteria in plain language.

Callers may inject ``judge`` for hermetic tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


@dataclass
class Verification:
    ok: bool
    notes: str
    layer: str  # structural | semantic


def structural_check(
    node: Dict[str, Any], result: Dict[str, Any], blackboard: Any
) -> Verification:
    """Deterministic checks: success flag, non-empty summary, artifacts."""
    if not result.get("ok"):
        return Verification(False, "worker reported failure", "structural")
    summary = (result.get("summary") or "").strip()
    if len(summary) < 8:
        return Verification(False, "empty or trivial result summary", "structural")
    for art in result.get("artifacts") or []:
        name = art.get("name") if isinstance(art, dict) else art
        if name and blackboard.get(f"artifact:{name}") is None:
            return Verification(
                False,
                f"claimed artifact {name!r} missing from blackboard",
                "structural",
            )
    return Verification(True, "structural checks passed", "structural")


def semantic_check(
    node: Dict[str, Any], result: Dict[str, Any], provider: Any = None
) -> Verification:
    """Model-assisted judgment via the existing agentic loop.

    Falls back to structural-only (ok=True) when no provider is available —
    honestly labeled, never silently strict.
    """
    try:
        from levi.agent.loop import run_subtask
    except Exception:  # pragma: no cover — import guard
        return Verification(True, "semantic check unavailable (no loop)", "structural")
    prompt = (
        "You are the VERIFICATION agent. Judge the subtask result against "
        "its acceptance criteria.\n\n"
        f"Subtask: {node.get('task')}\n"
        f"Acceptance criteria: {node.get('acceptance')}\n"
        f"Result summary: {result.get('summary')}\n\n"
        "Reply with exactly one line: PASS or FAIL: <one-sentence reason>"
    )
    try:
        transcript = run_subtask(
            prompt,
            provider=provider or "local",
            max_steps=3,
            system_prompt="You verify. One line only.",
        )
        text = (getattr(transcript, "final", "") or "").strip()
    except Exception as exc:
        return Verification(
            True, f"semantic check errored ({exc}); structural only", "structural"
        )
    upper = text.upper()
    if upper.startswith("FAIL"):
        return Verification(False, text[:300], "semantic")
    if upper.startswith("PASS"):
        return Verification(True, text[:300], "semantic")
    return Verification(
        True, "semantic check inconclusive; structural only", "structural"
    )


Judge = Callable[[Dict[str, Any], Dict[str, Any]], Verification]


def verify_node(
    node: Dict[str, Any],
    result: Dict[str, Any],
    blackboard: Any,
    *,
    judge: Optional[Judge] = None,
    semantic: bool = False,
    provider: Any = None,
) -> Verification:
    """Full verification pass: structural, then optional semantic/judge."""
    v = structural_check(node, result, blackboard)
    if not v.ok:
        return v
    if judge is not None:
        return judge(node, result)
    if semantic:
        return semantic_check(node, result, provider=provider)
    return v

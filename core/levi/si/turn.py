"""The SI turn: boundary -> judgment -> deliberation -> brain voice -> memory.

One assembled pass through every reachable design element, in
foundation-first order. Maximum agency means the turn *does the work*
(deliberates, judges, remembers) instead of describing what it would do.

Stdlib only at import time. The native brain is imported lazily and its
failures degrade to an honest report — never an exception, never faked.
No network anywhere in this module's path (proven by the blocked-network
test in ``tests/test_si_offline.py``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import refusal
from .refusal import Refusal

ORIGIN = "levi/si/turn"

# ---------------------------------------------------------------------------
# Honest boundary
# ---------------------------------------------------------------------------
# Standing law (Chauncey, 2026-09-22): for every turn the SI declares
# whether it can do the task honestly now or whether the task needs more
# training — and never fakes the latter. The declaration is heuristic and
# says so; uncertainty resolves toward honesty, never toward faking.

CAN_DO_NOW = "can-do-now"
NEEDS_MORE_TRAINING = "needs-more-training"
NEEDS_LIVE_DATA = "needs-live-data"

_LIVE_DATA = re.compile(
    r"\b(today'?s|current|right now|latest|breaking)\b.{0,30}"
    r"\b(news|price|stock|weather|score|headlines|rate)\b"
    r"|\b(what'?s|what is) the (news|weather|price|score)\b",
    re.IGNORECASE,
)

_DEEP_FLUENCY = re.compile(
    r"\b(write|draft|compose).{0,40}\b("
    r"novel|screenplay|essay|speech|poem|song|story|article|book)\b"
    r"|\b(graduate|phd|doctoral).{0,20}(thesis|dissertation|proof)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class BoundaryDeclaration:
    """Which side of the honest boundary this turn falls on."""

    state: str
    why: str
    heuristic: bool = True


def declare_boundary(task: str) -> BoundaryDeclaration:
    """Declare can-do-now vs needs-more-training vs needs-live-data.

    Heuristic, labeled as such per the law. Resolves toward honesty:
    anything the SI cannot do offline and untrained lands on the far
    side of the boundary, stated plainly.
    """
    text = task.strip()
    if _LIVE_DATA.search(text):
        return BoundaryDeclaration(
            state=NEEDS_LIVE_DATA,
            why=(
                "this asks for live information (news, prices, weather, "
                "scores). The SI is offline-first; it will not invent "
                "current facts. It can deliberate about the question's "
                "structure, but the facts need a live source."
            ),
        )
    if _DEEP_FLUENCY.search(text):
        return BoundaryDeclaration(
            state=NEEDS_MORE_TRAINING,
            why=(
                "this asks for fluent long-form composition, which needs "
                "trained-brain depth beyond the current weights (their "
                "samples are still garbled proof-of-learning output). The "
                "SI will give you its structural deliberation honestly "
                "instead of faking fluency."
            ),
        )
    return BoundaryDeclaration(
        state=CAN_DO_NOW,
        why=(
            "structural deliberation, local knowledge, and local action "
            "are inside what the SI can honestly do offline right now."
        ),
    )


# ---------------------------------------------------------------------------
# Brain voice (explicit-only, heard never obeyed)
# ---------------------------------------------------------------------------

def _brain_continuation(
    task: str, max_chars: int = 400
) -> Dict[str, Any]:
    """Exercise the native brain once; report honestly what happened."""
    try:
        from levi.brain import runtime as brain_runtime
    except Exception as exc:  # pragma: no cover - environment-dependent
        return {"ran": False, "note": f"brain unavailable (import): {exc}"}
    try:
        result = brain_runtime.run(
            "levi-native", task, max_new_chars=max_chars
        )
    except Exception as exc:
        return {"ran": False, "note": f"brain unavailable (run): {exc}"}
    continuation = ""
    if isinstance(result, dict):
        continuation = str(result.get("continuation", "") or "")
    if not continuation.strip():
        return {"ran": False, "note": "brain ran but returned no text"}
    return {"ran": True, "continuation": continuation, "note": "raw brain continuation"}


# ---------------------------------------------------------------------------
# The turn
# ---------------------------------------------------------------------------

def _deliberate(
    task: str, brain_text: Optional[str], brain_ran: bool
) -> Dict[str, Any]:
    """Propose -> critique -> verdict, preferring the full Reasoner.

    When the Reasoner is available it owns brain handling (its torch
    path). If our torch-free brain run succeeded where the Reasoner's
    did not, that is reconciled in ``limits`` — reported, never scored,
    never the winner.
    """
    try:
        from levi.alpha.reason import Reasoner

        receipt = Reasoner().reason(task)
        reasoner_brain = receipt.get("brain")
        if brain_ran and not reasoner_brain:
            receipt["limits"] = (
                (receipt.get("limits") or "")
                + " Native brain was also exercised separately through the "
                "torch-free runtime (raw continuation, heard never obeyed); "
                "the Reasoner's torch-based brain path is unavailable here."
            ).strip()
        return receipt
    except Exception:
        # Reasoner unavailable: run the raw deliberation core directly.
        from levi.alpha.si import deliberation as dl

        proposals = dl.propose(task, brain_continuation=brain_text)
        critiques = dl.critique(proposals)
        v = dl.verdict(proposals, critiques, "rules-engine")
        return {
            "answer": v["answer"],
            "substrate": v["substrate"],
            "limits": "Reasoner unavailable; raw deliberation core used.",
            "proposals": proposals,
            "critiques": critiques,
            "verdict": v,
            "brain": None,
        }


def _record_memory(task: str, receipt: Dict[str, Any], data_dir: Optional[str]) -> bool:
    """Record the turn locally. Nice-to-have: never breaks the turn."""
    try:
        from pathlib import Path

        from levi.memory.store import MemoryStore

        store = MemoryStore(Path(data_dir) if data_dir else None)
        store.add(
            text=f"SI turn: {task[:160]}",
            importance=0.4,
            tags=["si-turn", receipt.get("boundary", {}).get("state", "unknown")],
        )
        return True
    except Exception:
        return False


def run_turn(
    task: str,
    brain: bool = True,
    memory_dir: Optional[str] = None,
    brain_chars: int = 400,
) -> Dict[str, Any]:
    """Run one full SI turn. Returns the receipt.

    Order is the law: boundary first, then judgment, then deliberation.
    A refused turn returns its refusal with no deliberation theater.
    """
    task = (task or "").strip()
    boundary = declare_boundary(task)

    judged: Optional[Refusal] = refusal.judge(task)
    if judged is not None:
        receipt: Dict[str, Any] = {
            "task": task,
            "boundary": {"state": boundary.state, "why": boundary.why},
            "refused": True,
            "refusal_reason": judged.reason,
            "verdict": None,
            "brain": {"ran": False, "note": "not run: turn refused"},
            "memory_recorded": _record_memory(task, {"boundary": {"state": boundary.state}}, memory_dir),
        }
        return receipt

    brain_out: Dict[str, Any] = {"ran": False, "note": "brain disabled"}
    brain_text: Optional[str] = None
    if brain:
        brain_out = _brain_continuation(task, max_chars=brain_chars)
        if brain_out.get("ran"):
            brain_text = brain_out.get("continuation")

    deliberation = _deliberate(task, brain_text, bool(brain_out.get("ran")))
    verdict = deliberation.get("verdict", {})

    receipt = {
        "task": task,
        "boundary": {"state": boundary.state, "why": boundary.why},
        "refused": False,
        "refusal_reason": None,
        "verdict": {
            "chosen": verdict.get("chosen"),
            "score": verdict.get("score"),
            "answer": verdict.get("answer"),
            "substrate": deliberation.get("substrate"),
            "note": verdict.get("note"),
            "limits": deliberation.get("limits"),
        },
        "brain": {"ran": brain_out.get("ran", False), "note": brain_out.get("note")},
        "memory_recorded": False,
    }
    receipt["memory_recorded"] = _record_memory(task, receipt, memory_dir)
    return receipt


def format_turn(receipt: Dict[str, Any]) -> str:
    """Plain-words rendering of a turn receipt."""
    lines = [f"boundary: {receipt['boundary']['state']}", f"  {receipt['boundary']['why']}"]
    if receipt["refused"]:
        lines.append("")
        lines.append(receipt["refusal_reason"])
        return "\n".join(lines)
    v = receipt["verdict"]
    lines += [
        "",
        f"substrate: {v['substrate']}",
        f"verdict ({v['chosen']}, {v['score']}):",
        f"  {v['answer']}",
    ]
    if v.get("limits"):
        lines.append(f"limits: {v['limits']}")
    lines.append(f"brain: {receipt['brain']['note']}")
    return "\n".join(lines)

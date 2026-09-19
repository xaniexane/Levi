"""ser-18-core: the SER-18 world model and lifecycle engine (LEVI-native).

Canon role (ORGANISM_FORMS): "world model; defines universe, recursion
shells, depth limits".

Canon mapping (founder corpus: copilot-sweep/ser13-18-21-master-conversation.md):
  - SER-21 (World Model) -> SER-18 Core, Oracle, HyperCube, OmniPulse.
    Defines universe, recursion shells, depth limits, long-term goal weights.
  - SER-18 (Lifecycle Engine) -> OmniPulse, Eden, UniForge, Vector.
    18-phase cycle: birth -> expansion -> echo -> collapse -> rebirth -> stabilization.

The canonical name tables below are QUOTED from the founder's own spec
(verbatim, in order) — never invented here:

  SER-18 phases (18): Birth, Calibration, Expansion, Projection, Echo,
    Reflection, Inverse, Collapse, Rebirth, Stabilization, Integration,
    Mutation, Divergence, Convergence, Anti-Projection, Anti-Collapse,
    Preservation, Termination.
  SER-13 states (13): Forward, Inverse, Echo, Collapse, Rebirth,
    Projection, Reflection, Divergence, Convergence, Null, Meta,
    Anti-Meta, Hyper-Meta.

``seat()`` registers those tables into ``levi.cybrus.qid`` via the
fail-closed ``register_spec_tables`` gate (exact counts, non-empty
strings). Idempotent: re-seating identical tables is a no-op; different
tables are refused.

:class:`Lifecycle` runs the 18-phase cycle: advance, next, goto, with
fail-closed phase validation, dry-run purity (nothing advances on a dry
run), and a receipt for every transition. Unknown phase names are DATA —
reported in the receipt, never accepted.

The world-model surface (``world_model()``) reports the canonical
constants honestly: 21 shells x 315 forms x 13 states x 10^30 recursion
indices, matching the QID ranges in ``levi.cybrus.qid``. It describes
the defined universe; it does not claim to simulate one.

Ready-for-review by the keeper. Never claims his review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Canonical SER-18 lifecycle phases, verbatim from the founder's spec.
SER18_PHASES: List[str] = [
    "Birth",
    "Calibration",
    "Expansion",
    "Projection",
    "Echo",
    "Reflection",
    "Inverse",
    "Collapse",
    "Rebirth",
    "Stabilization",
    "Integration",
    "Mutation",
    "Divergence",
    "Convergence",
    "Anti-Projection",
    "Anti-Collapse",
    "Preservation",
    "Termination",
]

# Canonical SER-13 logic states, verbatim from the founder's spec.
SER13_STATES: List[str] = [
    "Forward",
    "Inverse",
    "Echo",
    "Collapse",
    "Rebirth",
    "Projection",
    "Reflection",
    "Divergence",
    "Convergence",
    "Null",
    "Meta",
    "Anti-Meta",
    "Hyper-Meta",
]

# World-model constants (SER-21 universe), matching levi.cybrus.qid ranges.
SER21_SHELLS = 21
SER18_FORMS = 315
SER13_LOGIC_STATES = 13
RECURSION_INDEX_MAX = 10**30

FORM_NAME = "ser-18-core"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def seat() -> Dict[str, Any]:
    """Register the canonical name tables into levi.cybrus.qid.

    Fail-closed: the qid gate itself validates exact counts (18/13) and
    non-empty strings. Refuses (ValueError) if tables are already seated
    with DIFFERENT names — the canon never silently swaps under a live
    organism.
    """
    from levi.cybrus import qid

    if qid.PHASE_NAMES and qid.STATE_NAMES:
        same = qid.PHASE_NAMES == SER18_PHASES and qid.STATE_NAMES == SER13_STATES
        return {
            "form": FORM_NAME,
            "status": "already-seated" if same else "refused",
            "reason": (
                "name tables already seated with identical canon names"
                if same
                else "qid tables hold different names; refusing to overwrite "
                "the seated canon"
            ),
            "phases": len(qid.PHASE_NAMES),
            "states": len(qid.STATE_NAMES),
            "at": _utcnow(),
        }
    qid.register_spec_tables(list(SER18_PHASES), list(SER13_STATES))
    return {
        "form": FORM_NAME,
        "status": "seated",
        "reason": "canonical SER-18/SER-13 name tables registered from founder spec",
        "phases": len(SER18_PHASES),
        "states": len(SER13_STATES),
        "at": _utcnow(),
    }


def world_model() -> Dict[str, Any]:
    """Report the defined universe. Descriptive only — never a simulation."""
    from levi.cybrus import qid

    return {
        "form": FORM_NAME,
        "shells": SER21_SHELLS,
        "forms_per_shell": SER18_FORMS,
        "logic_states": SER13_LOGIC_STATES,
        "recursion_index_max": RECURSION_INDEX_MAX,
        "qid_ranges": {
            "form": [qid.FORM_MIN, qid.FORM_MAX],
            "logic_state": [qid.LOGIC_STATE_MIN, qid.LOGIC_STATE_MAX],
            "recursion": [qid.RECURSION_MIN, qid.RECURSION_MAX],
        },
        "name_tables_seated": bool(qid.PHASE_NAMES and qid.STATE_NAMES),
        "honest_limit": (
            "this module defines the universe's address space and lifecycle "
            "phases; it does not simulate the universe"
        ),
    }


@dataclass
class Lifecycle:
    """The 18-phase lifecycle engine. Pure state machine over phase names."""

    phase: str = "Birth"
    history: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.phase not in SER18_PHASES:
            raise ValueError(
                f"unknown SER-18 phase {self.phase!r}; the canon holds exactly "
                f"these 18: {', '.join(SER18_PHASES)}"
            )

    def _receipt(
        self,
        status: str,
        reason: str,
        *,
        phase: Optional[str] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        return {
            "form": FORM_NAME,
            "status": status,
            "reason": reason,
            "phase": self.phase if phase is None else phase,
            "dry_run": dry_run,
            "at": _utcnow(),
        }

    def advance(self, *, dry_run: bool = False) -> Dict[str, Any]:
        """Move to the next phase (wraps Birth after Termination — the cycle)."""
        nxt = SER18_PHASES[(SER18_PHASES.index(self.phase) + 1) % len(SER18_PHASES)]
        if dry_run:
            return self._receipt(
                "dry-run",
                f"would advance {self.phase} -> {nxt}; nothing moved",
                phase=nxt,
                dry_run=True,
            )
        prev = self.phase
        self.phase = nxt
        self.history.append({"from": prev, "to": nxt, "at": _utcnow()})
        return self._receipt(
            "advanced", f"lifecycle advanced {prev} -> {nxt}", phase=nxt
        )

    def goto(self, phase: Any, *, dry_run: bool = False) -> Dict[str, Any]:
        """Jump to a named phase. Unknown names are rejected as data."""
        if not isinstance(phase, str) or phase not in SER18_PHASES:
            return self._receipt(
                "rejected",
                f"unknown SER-18 phase {phase!r}: treated as data, not accepted; "
                f"still at {self.phase}",
            )
        if dry_run:
            return self._receipt(
                "dry-run",
                f"would jump {self.phase} -> {phase}; nothing moved",
                phase=phase,
                dry_run=True,
            )
        prev = self.phase
        self.phase = phase
        self.history.append({"from": prev, "to": phase, "at": _utcnow()})
        return self._receipt(
            "advanced", f"lifecycle jumped {prev} -> {phase}", phase=phase
        )

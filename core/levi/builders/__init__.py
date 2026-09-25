"""LEVI builders — the economics-breaker (KFX2 milestone 1).

Prompt -> deterministic, locally-running project skeleton with NO
generation-credit meter and a bounded verify/retry cycle.

The paired mind: :class:`ScaffoldEngine` proposes, :class:`VerifyLoop`
verifies. The builder that breaks the credit-burn unit economics:

- No credits, no tokens, no meter — builds run on compute the owner owns.
  :class:`BuildLedger` records every operation at a hard-zero charge; there
  is no billing unit anywhere in this package, so there is nothing to bill
  a debugging loop through.
- The honest-retry law: generated code must compile and pass its generated
  smoke test before it is presented. Retries inside the bound are free by
  construction. Builder-caused fixes cost the owner nothing.
- The owner owns the runtime: the skeleton is stdlib-only Python that runs
  on the owner's machine. Nothing to export *from*, no backend held hostage.
- Offline-capable: no network calls in any core path. Same prompt always
  yields the same bytes (seeded determinism).

Doctrines encoded here: uproar (parity + exclusives), PLATFORM_CUT = 0.12
as a named constant (hook only — payments are owner-gated, never wired),
Myspace-style safe structured theming in every generated skeleton, the
ternary (VERIFIED / SELF_HEALED / OWNER_DECISION_NEEDED instead of a bare
pass/fail), no-free-core (entry mechanics are owner-gated, not free).

Product home — DECIDED by Chauncey 2026-09-21: ONE ENGINE, THREE DOORS.
This package is the single shared engine; all scaffold logic lives here
and nowhere else. Three thin surface doors in :mod:`levi.builders.doors`
adapt it without duplicating anything: ``standalone`` (general /
low-production / simple), ``hicomb`` (seasoned / complex dock), ``hub``
(developers / enterprise). A project scaffolded through one door opens
identically through the others — graduation is a change of surface,
never a rebuild.
"""

from __future__ import annotations

from levi.builders.economy import (
    PLATFORM_CUT,
    BuildLedger,
    LedgerEntry,
    OwnerGateRequired,
    collect_payment,
    marketplace_royalty,
)
from levi.builders.pipeline import BuildReport, build, refine_project
from levi.builders.planner import BuildPlan, plan as plan_build
from levi.builders.refine import RefineReport, refine
from levi.builders.scaffold import ScaffoldEngine
from levi.builders.verify import MAX_BUILDER_RETRIES, BuildOutcome, VerifyLoop

__all__ = [
    "PLATFORM_CUT",
    "MAX_BUILDER_RETRIES",
    "BuildLedger",
    "BuildOutcome",
    "BuildPlan",
    "BuildReport",
    "LedgerEntry",
    "OwnerGateRequired",
    "RefineReport",
    "ScaffoldEngine",
    "VerifyLoop",
    "build",
    "collect_payment",
    "marketplace_royalty",
    "plan_build",
    "refine",
    "refine_project",
]

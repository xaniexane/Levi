"""Orchestrator: pairs the proposer and verifier twins, keeps the ledger.

One call — ``build(prompt)`` — runs scaffold -> bounded verify -> ledger.
The owner gets a verified project directory or an honest
OWNER_DECISION_NEEDED report. Never a half-built claim, never a bill.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from typing import List, Optional

from levi.builders.economy import BuildLedger, LedgerEntry
from levi.builders.refine import RefineReport, refine
from levi.builders.scaffold import ScaffoldEngine
from levi.builders.verify import BuildOutcome, VerifyLoop, VerifyReport


@dataclass
class BuildReport:
    prompt: str
    outcome: BuildOutcome
    target_dir: str
    attempts: int
    repairs: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    diagnostics: str = ""
    ledger_entries: List[LedgerEntry] = field(default_factory=list)
    domain: str = ""
    plan_summary: str = ""

    @property
    def ok(self) -> bool:
        return self.outcome in (
            BuildOutcome.VERIFIED,
            BuildOutcome.SELF_HEALED,
        )


def build(
    prompt: str,
    workdir: Optional[str] = None,
    ledger: Optional[BuildLedger] = None,
    _fault_hook=None,
) -> BuildReport:
    """Build a project from a prompt. Deterministic, local, meter-free.

    Never deletes: retries overwrite the same generated paths, and
    pre-existing files in ``workdir`` are left alone. Supply an empty
    directory if you want exactly the generated tree and nothing else.

    ``_fault_hook`` is test-only fault injection (see ScaffoldEngine).
    """
    ledger = ledger or BuildLedger()
    engine = ScaffoldEngine(prompt, _fault_hook=_fault_hook)
    plan = engine.build_plan
    ledger.record(
        "scaffold",
        "prompt_sha256=%s app=%s domain=%s entities=%s modules=%d%s"
        % (
            engine.prompt_hash[:12],
            engine.app_slug,
            plan.domain,
            ",".join(engine.entities),
            len(plan.modules),
            " ambiguities=%d" % len(plan.ambiguities) if plan.ambiguities else "",
        ),
    )

    target = workdir or tempfile.mkdtemp(prefix="levi-build-")
    os.makedirs(target, exist_ok=True)
    report: VerifyReport = VerifyLoop().run(engine, target)

    for note in report.repairs:
        ledger.record("builder_retry", "%s (free by construction)" % note)
    ledger.record(
        "verify",
        "outcome=%s attempts=%d charged=0.00" % (report.outcome.value, report.attempts),
    )

    files: List[str] = []
    for root, _dirs, names in os.walk(target):
        for name in names:
            files.append(os.path.relpath(os.path.join(root, name), target))

    return BuildReport(
        prompt=prompt,
        outcome=report.outcome,
        target_dir=target,
        attempts=report.attempts,
        repairs=report.repairs,
        files=sorted(files),
        diagnostics=report.diagnostics,
        ledger_entries=ledger.entries(),
        domain=plan.domain,
        plan_summary="%s | entities=%s | modules=%d%s"
        % (
            plan.domain,
            ",".join(plan.entities),
            len(plan.modules),
            " | ambiguous: %s" % "; ".join(plan.ambiguities)
            if plan.ambiguities
            else "",
        ),
    )


def refine_project(
    workdir: str,
    change_request: str,
    ledger: Optional[BuildLedger] = None,
    _fault_hook=None,
) -> RefineReport:
    """Apply a change-scoped refinement to an existing built project.

    Change-scoped: only files that differ are rewritten, untouched files
    stay byte-identical, nothing is deleted, and the iteration is appended
    to the project's provenance. ``_fault_hook`` is test-only.
    """
    ledger = ledger or BuildLedger()
    ledger.record("refine", "change=%s" % change_request[:80])
    report = refine(workdir, change_request, _fault_hook=_fault_hook)
    ledger.record(
        "refine_verify",
        "outcome=%s added=%d changed=%d untouched=%d"
        % (
            report.outcome.value,
            len(report.files_added),
            len(report.files_changed),
            len(report.files_untouched),
        ),
    )
    return report

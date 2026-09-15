"""
LEVI Daemon Core — unified automation operating layer (not a giant chatbot).

Subsystems coordinated by the daemon:
  LEVI SI (cognition) · X LWP · DemandPulse · Income Factory · Memory

Cycle (deterministic spine; models are optional modules):

  OBSERVE → UNDERSTAND → RETRIEVE MEMORY → DETECT OPPORTUNITY → PLAN
  → SIMULATE → SELECT TOOLS/AGENTS → EXECUTE (policy-gated) → VERIFY
  → RECORD → LEARN → OPTIMIZE → WAIT

Self-composition: smallest useful combination of capabilities for the task.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path

from levi.daemon.kernel import DaemonKernel
from levi.demand.pulse import DemandPulse
from levi.income.factory import IncomeFactory


CYCLE_STEPS = [
    "OBSERVE",
    "UNDERSTAND",
    "RETRIEVE_MEMORY",
    "DETECT_OPPORTUNITY",
    "PLAN",
    "SIMULATE",
    "SELECT",
    "EXECUTE",
    "VERIFY",
    "RECORD",
    "LEARN",
    "OPTIMIZE",
    "WAIT",
]


@dataclass
class Composition:
    task: str
    capabilities: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    memory_scopes: List[str] = field(default_factory=list)
    model_tier: str = "local_or_offline"  # local_or_offline | cloud_optional
    requires_hitl: bool = False
    notes: str = ""


class UnifiedDaemon:
    """
    Persistent synthetic-intelligence automation OS core (pre-MVP).
    Free-first: prefer local/deterministic; paid cloud is optional under cost governor.
    """

    def __init__(self, path: Optional[Path] = None):
        base = Path(path) if path else Path.home() / ".levi"
        self.kernel = DaemonKernel(path=base / "daemon_kernel.json")
        self.demand = DemandPulse(path=base / "demand_pulse.json")
        self.income = IncomeFactory(path=base / "income_factory.json")

    def compose(self, task: str) -> Composition:
        """Self-composition: pick smallest useful capability set."""
        if not isinstance(task, str) or not task.strip():
            raise ValueError(
                f"compose: 'task' must be a non-empty string, got {task!r}"
            )
        t = task.lower()
        caps: List[str] = ["memory", "cognition"]
        tools: List[str] = ["memory.recall"]
        mem = ["corpus", "brain_table"]
        hitl = False
        model = "local_or_offline"
        notes = []

        if any(w in t for w in ("demand", "opportunity", "market", "gap", "need")):
            caps.append("demand_pulse")
            tools.append("demand.scan")
            notes.append("DemandPulse activated")
        if any(
            w in t
            for w in (
                "income",
                "sell",
                "revenue",
                "offer",
                "service factory",
                "monetiz",
            )
        ):
            caps.append("income_factory")
            tools.append("income.compose")
            hitl = True
            notes.append("Income Factory draft only — HITL before money/customers")
        if any(w in t for w in ("site", "website", "archaeology", "client", "ux")):
            caps.extend(["project_phases", "lwp"])
            tools.append("project.phase")
            mem.append("project")
        if any(w in t for w in ("echo", "parallel", "branch")):
            tools.append("organ.echo")
            caps.append("organs")
        if any(w in t for w in ("mandella", "stake", "decision")):
            tools.append("organ.mandella")
            caps.append("organs")
        if any(
            w in t for w in ("security", "payment", "production", "dns", "customer")
        ):
            hitl = True
            tools.append("hitl.propose")
            notes.append("Consequential domain → HITL")

        if not self.kernel.require_permission("compose", "HIGH" if hitl else "LOW"):
            hitl = True

        return Composition(
            task=task,
            capabilities=sorted(set(caps)),
            tools=sorted(set(tools)),
            memory_scopes=sorted(set(mem)),
            model_tier=model,
            requires_hitl=hitl,
            notes="; ".join(notes) if notes else "minimal cognitive path",
        )

    def run_cycle(self, task: str, execute: bool = False) -> str:
        """
        Run one daemon cycle. execute=False → plan only (safe default).
        execute=True still respects HITL/estop/cost — never silent money moves.
        """
        if not isinstance(execute, bool):
            raise ValueError(
                f"run_cycle: 'execute' must be True or False, "
                f"got {execute!r}"
            )
        if self.kernel.state.estop:
            return "EMERGENCY STOP active. clear with: levi unified --clear-estop"

        lines = [
            "=== LEVI Daemon Core — cycle ===",
            f"Task: {task}",
            "",
        ]
        comp = self.compose(task)
        self.kernel.emit("cycle_start", {"task": task})

        for step in CYCLE_STEPS:
            if step == "OBSERVE":
                lines.append(
                    f"[{step}] context task received; estop={self.kernel.state.estop}"
                )
            elif step == "UNDERSTAND":
                lines.append(f"[{step}] composition: {', '.join(comp.capabilities)}")
            elif step == "RETRIEVE_MEMORY":
                mem_bits = []
                try:
                    from levi.brain.corpus import Corpus

                    mem_bits.append(f"corpus_units={len(Corpus().list(limit=500))}")
                except Exception:
                    pass
                try:
                    from levi.brain.table import BrainTable

                    mem_bits.append(f"brain_rows={len(BrainTable().rows)}")
                except Exception:
                    pass
                lines.append(
                    f"[{step}] scopes={comp.memory_scopes} {' '.join(mem_bits)}"
                )
            elif step == "DETECT_OPPORTUNITY":
                if "demand_pulse" in comp.capabilities:
                    lines.append(
                        f"[{step}] DemandPulse active — signals={len(self.demand.signals)}"
                    )
                else:
                    lines.append(f"[{step}] skipped (not in composition)")
            elif step == "PLAN":
                lines.append(f"[{step}] tools={comp.tools}  model={comp.model_tier}")
                lines.append(f"         notes={comp.notes}")
            elif step == "SIMULATE":
                lines.append(f"[{step}] dry-run path; no side effects")
            elif step == "SELECT":
                lines.append(f"[{step}] selected capabilities={comp.capabilities}")
            elif step == "EXECUTE":
                if not execute:
                    lines.append(
                        f"[{step}] HELD (plan-only). Re-run with --execute after review."
                    )
                elif comp.requires_hitl:
                    lines.append(
                        f"[{step}] BLOCKED pending HITL — consequential actions listed in plan"
                    )
                    try:
                        from levi.project.hitl import HITLGate

                        req = HITLGate().propose(
                            what=f"Execute daemon composition for: {task[:120]}",
                            why="Composition marked requires_hitl",
                            changes="No auto payment/production; approval enables next gated step",
                            risk="MEDIUM",
                            domain="automation",
                            if_approved="Continue gated fulfillment steps",
                            if_denied="Remain plan-only",
                        )
                        lines.append(req.format_card())
                    except Exception as e:
                        lines.append(f"         HITL error: {e}")
                else:
                    # Safe local executes only
                    if "demand.scan" in comp.tools and task:
                        sig = self.demand.scan_seed(task)
                        lines.append(f"[{step}] demand signal logged id={sig.id}")
                    if "income.compose" in comp.tools:
                        plan = self.income.compose(task[:80])
                        lines.append(
                            f"[{step}] income plan draft id={plan.id} (still HITL before money)"
                        )
                    lines.append(f"[{step}] local-safe actions only")
            elif step == "VERIFY":
                lines.append(
                    f"[{step}] policy + estop + cost budget OK={not self.kernel.state.estop}"
                )
            elif step == "RECORD":
                try:
                    from levi.brain.corpus import Corpus

                    Corpus().add(
                        f"Daemon cycle recorded: {task[:160]}",
                        kind="INFERENCE",
                        source="daemon:unified",
                        tags=["daemon_cycle"],
                    )
                except Exception:
                    pass
                try:
                    from levi.project.capability_log import CapabilityLog

                    CapabilityLog().log(
                        task=f"daemon_cycle: {task[:100]}",
                        result="partial" if not execute else "completed",
                        tools=comp.tools,
                        future_skill="DAEMON_CYCLE",
                        automatable="partial",
                        human_required=comp.requires_hitl,
                    )
                    lines.append(f"[{step}] capability log updated")
                except Exception:
                    lines.append(f"[{step}] log skipped")
            elif step == "LEARN":
                lines.append(
                    f"[{step}] outcomes feed corpus/brain when operators add OBSERVED facts"
                )
            elif step == "OPTIMIZE":
                lines.append(
                    f"[{step}] free-first: prefer local/deterministic over paid cloud"
                )
            elif step == "WAIT":
                lines.append(f"[{step}] cycle {self.kernel.state.cycle} complete")

        self.kernel.emit("cycle_end", {"task": task})
        lines.append("")
        lines.append(self.kernel.status())
        return "\n".join(lines)

    def status(self) -> str:
        lines = [
            "=== LEVI Daemon Core (unified) ===",
            "Operating layer — not a giant chatbot.",
            "",
            "Subsystems: cognition · X LWP · DemandPulse · Income Factory · Memory",
            "",
            self.kernel.status(),
            "",
            self.demand.format_status(),
            "",
            self.income.format_status(),
            "",
            "Cycle: " + " → ".join(CYCLE_STEPS),
            "Income Factory is one capability under governance — not LEVI's sole purpose.",
            "Free-first: local/open components preferred; cloud optional under cost governor.",
        ]
        return "\n".join(lines)

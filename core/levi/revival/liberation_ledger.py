"""liberation_ledger — a local-first register of who holds your data.

Studied from: hostage-hunt-20260915/report.md (§Cross-cutting pattern — LEVI inversion).

The load-bearing idea: every service holding your data holds a little
bit of *you* hostage, and the ransom is invisible — export that
doesn't work, deletion that doesn't delete, formats that don't
transfer. The honest inversion is a ledger that scores the hostage
situation transparently (every component of the score shown, nothing
averaged into mystery) and turns escape into a checklist: export,
verify, migrate, delete — each step producing a receipt.

LEVI's take: ``ServiceEntry`` records what a service holds about you
and the facts that matter: can you export, in what format, can you
delete, does deletion actually purge, is there an API, are you
contractually locked. ``hostage_score`` combines transparent
components — each named, weighted, and shown — into a 0–100 score.
``liberation_plan`` turns the entry into ordered ``LiberationTask``
steps (export → verify → migrate → delete), skipping steps the
service makes impossible and flagging them honestly. Completing a
step records a ``Receipt`` — what was done, when, with what evidence
— so the escape is auditable.

Honest limits: the score is a heuristic over *declared* facts, not a
security audit — a service can claim deletion while keeping backups,
and the ledger can't see inside their datacenter. Verify receipts
against reality where you can.

This is an original, from-scratch implementation for LEVI.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

ORIGIN = "levi-revival/liberation-ledger"


# Each component: (weight, description). Weights sum to 100 so the
# score is a plain weighted sum — no hidden math.
SCORE_COMPONENTS = {
    "no_export": (25, "you cannot get your data out"),
    "proprietary_format_only": (15, "export exists but in a proprietary format"),
    "no_delete": (20, "you cannot delete your account/data"),
    "delete_keeps_copies": (15, "deletion leaves backups/copies behind"),
    "no_api": (10, "no programmatic access to your own data"),
    "contract_lock": (15, "contract or term penalizes leaving"),
}


@dataclass
class ServiceEntry:
    """Everything the ledger knows about one service holding your data."""

    name: str
    data_held: List[str] = field(default_factory=list)
    export_available: bool = False
    export_formats: List[str] = field(default_factory=list)
    delete_available: bool = False
    delete_purges: bool = False  # True only if deletion removes all copies
    has_api: bool = False
    contract_lock: bool = False
    notes: str = ""

    def score_breakdown(self) -> Dict[str, Dict[str, object]]:
        """Every component of the hostage score, shown, none hidden."""
        proprietary = self.export_available and not any(
            f.lower() in ("json", "csv", "xml", "zip", "mbox", "ical")
            for f in self.export_formats
        )
        flags = {
            "no_export": not self.export_available,
            "proprietary_format_only": proprietary,
            "no_delete": not self.delete_available,
            "delete_keeps_copies": self.delete_available and not self.delete_purges,
            "no_api": not self.has_api,
            "contract_lock": self.contract_lock,
        }
        breakdown = {}
        for component, (weight, description) in SCORE_COMPONENTS.items():
            breakdown[component] = {
                "applies": flags[component],
                "weight": weight,
                "points": weight if flags[component] else 0,
                "meaning": description,
            }
        return breakdown

    def hostage_score(self) -> int:
        """0 = free, 100 = fully held hostage. All components visible."""
        return sum(
            info["points"]
            for info in self.score_breakdown().values()  # type: ignore[misc]
        )

    def risk_band(self) -> str:
        score = self.hostage_score()
        if score >= 70:
            return "hostage"
        if score >= 40:
            return "sticky"
        if score > 0:
            return "mild"
        return "free"


@dataclass
class LiberationTask:
    """One step of the escape: export → verify → migrate → delete."""

    step: str  # export | verify | migrate | delete
    service: str
    action: str
    possible: bool = True
    blocker: str = ""
    done: bool = False
    receipt: Optional["Receipt"] = None


@dataclass
class Receipt:
    """Proof a liberation step happened: what, when, evidence."""

    service: str
    step: str
    completed_at: float = field(default_factory=time.time)
    evidence: str = ""
    detail: str = ""


def liberation_plan(entry: ServiceEntry) -> List[LiberationTask]:
    """Build the escape checklist for a service, honestly flagging blockers."""
    tasks = [
        LiberationTask(
            step="export",
            service=entry.name,
            action=f"export your data ({', '.join(entry.export_formats) or 'no format offered'})",
            possible=entry.export_available,
            blocker="" if entry.export_available else "service offers no export",
        ),
        LiberationTask(
            step="verify",
            service=entry.name,
            action="verify the export is complete and readable",
            possible=entry.export_available,
            blocker=""
            if entry.export_available
            else "nothing to verify without an export",
        ),
        LiberationTask(
            step="migrate",
            service=entry.name,
            action="move your data to your own storage or a freer service",
            possible=entry.export_available,
            blocker=""
            if entry.export_available
            else "cannot migrate what you cannot export",
        ),
        LiberationTask(
            step="delete",
            service=entry.name,
            action="delete your account and data at the service",
            possible=entry.delete_available,
            blocker="" if entry.delete_available else "service offers no deletion",
        ),
    ]
    return tasks


class LiberationLedger:
    """The local-first register: services, scores, plans, receipts."""

    def __init__(self) -> None:
        self._services: Dict[str, ServiceEntry] = {}
        self._receipts: List[Receipt] = []

    def register(self, entry: ServiceEntry) -> ServiceEntry:
        self._services[entry.name] = entry
        return entry

    def get(self, name: str) -> Optional[ServiceEntry]:
        return self._services.get(name)

    def ranked_by_hostage_score(self) -> List[Dict[str, object]]:
        ranked = sorted(
            self._services.values(), key=lambda e: e.hostage_score(), reverse=True
        )
        return [
            {
                "service": e.name,
                "score": e.hostage_score(),
                "band": e.risk_band(),
                "data_held": e.data_held,
            }
            for e in ranked
        ]

    def complete_task(self, task: LiberationTask, evidence: str = "") -> Receipt:
        """Mark a liberation step done and file its receipt."""
        if not task.possible:
            raise ValueError(
                f"cannot complete impossible step {task.step!r}: {task.blocker}"
            )
        receipt = Receipt(
            service=task.service,
            step=task.step,
            evidence=evidence,
            detail=task.action,
        )
        task.done = True
        task.receipt = receipt
        self._receipts.append(receipt)
        return receipt

    def receipts(self, service: Optional[str] = None) -> List[Receipt]:
        if service is None:
            return list(self._receipts)
        return [r for r in self._receipts if r.service == service]

    def liberation_status(self, service: str) -> Dict[str, object]:
        """How far the escape has gone: receipts filed vs steps possible."""
        plan = (
            liberation_plan(self._services[service])
            if service in self._services
            else []
        )
        done_steps = {r.step for r in self.receipts(service)}
        return {
            "service": service,
            "steps": [t.step for t in plan],
            "completed": sorted(done_steps),
            # fully free only when EVERY step is done: a blocked export
            # means you are not out yet, even if deletion is complete
            "fully_liberated": bool(plan) and all(t.done for t in plan),
        }

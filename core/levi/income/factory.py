"""
Income Factory — service / offer / automation composition.

Not the Software Factory (levi.factory.pipeline builds code through
idea→requirements→…→package). This one composes income-side service plans
and opportunities with HITL before payment, production, or customer contact.
Capability under LEVI, not the whole system. Never auto-charges money.
Produces plans that require HITL before payment, production, or customer contact.
"""

from __future__ import annotations

import json
import uuid
import warnings
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT = Path.home() / ".levi" / "income_factory.json"


@dataclass
class ServicePlan:
    id: str
    opportunity_title: str
    service: str
    offer_steps: List[str] = field(default_factory=list)
    automation_steps: List[str] = field(default_factory=list)
    requires_hitl: List[str] = field(default_factory=list)
    status: str = "draft"  # draft | awaiting_hitl | approved | rejected
    demand_signal_id: str = ""
    value_flags: List[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError(f"plan id must be a non-empty string, got {self.id!r}")
        if (
            not isinstance(self.opportunity_title, str)
            or not self.opportunity_title.strip()
        ):
            raise ValueError("plan opportunity_title must be a non-empty string")
        if not isinstance(self.service, str) or not self.service.strip():
            raise ValueError("plan service must be a non-empty string")
        if self.status not in ("draft", "awaiting_hitl", "approved", "rejected"):
            raise ValueError(
                f"plan status must be draft/awaiting_hitl/approved/rejected, "
                f"got {self.status!r}"
            )
        for name in ("offer_steps", "automation_steps", "requires_hitl", "value_flags"):
            steps = getattr(self, name)
            if not isinstance(steps, list) or not all(
                isinstance(s, str) for s in steps
            ):
                raise ValueError(f"plan {name} must be a list of strings")
        if not isinstance(self.demand_signal_id, str):
            raise ValueError(
                f"plan demand_signal_id must be a string, "
                f"got {type(self.demand_signal_id).__name__}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class IncomeFactory:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else DEFAULT
        self.plans: List[ServicePlan] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("top level must be an object")
            plans = raw.get("plans") or []
            if not isinstance(plans, list):
                raise ValueError("'plans' must be a list")
            self.plans = []
            for p in plans:
                if not isinstance(p, dict):
                    continue
                try:
                    self.plans.append(
                        ServicePlan(
                            **{
                                k: v
                                for k, v in p.items()
                                if k in ServicePlan.__dataclass_fields__
                            }
                        )
                    )
                except Exception:
                    continue  # one corrupt plan must not kill the rest
        except Exception as exc:
            warnings.warn(
                f"income factory file {self.path} is unreadable "
                f"({type(exc).__name__}); starting empty. "
                "Back up or delete the file to silence this warning.",
                UserWarning,
                stacklevel=3,
            )
            self.plans = []

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "plans": [p.to_dict() for p in self.plans[-50:]],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def compose(
        self,
        opportunity_title: str,
        service: str = "service modernization",
        demand_signal_id: Optional[str] = None,
    ) -> ServicePlan:
        """Compose a draft service plan. Never charges or contacts anyone."""
        if not isinstance(opportunity_title, str) or not opportunity_title.strip():
            raise ValueError(
                f"opportunity_title must be a non-empty string, "
                f"got {opportunity_title!r}"
            )
        if not isinstance(service, str) or not service.strip():
            raise ValueError(f"service must be a non-empty string, got {service!r}")
        if demand_signal_id is not None and not isinstance(demand_signal_id, str):
            raise ValueError(
                f"demand_signal_id must be a string or None, "
                f"got {type(demand_signal_id).__name__}"
            )
        # Extract signal id from title tag if present
        sig = (demand_signal_id or "").strip()
        title = opportunity_title
        if "[signal:" in title and not sig:
            try:
                sig = title.split("[signal:", 1)[1].split("]", 1)[0].strip()
            except Exception:
                pass
        value_flags: List[str] = []
        try:
            from levi.graph.symbiosis import value_check

            vc = value_check(title + " " + service)
            if "Flags" in vc or "Fabricated" in vc or "Pressure" in vc:
                value_flags.append("value_boundary_warning")
            if "Aligns" in vc or "value" in vc.lower():
                value_flags.append("value_aligned_signals")
        except Exception:
            pass
        plan = ServicePlan(
            id=str(uuid.uuid4())[:8],
            opportunity_title=title,
            service=service,
            offer_steps=[
                "Free assessment (preview only)",
                "Scoped proposal",
                "Delivery milestones",
                "Optional maintenance",
            ],
            automation_steps=[
                "Lead intake form (no auto-email until HITL)",
                "Analysis checklist",
                "Proposal draft generation",
                "Fulfillment checklist",
            ],
            requires_hitl=[
                "customer communication",
                "pricing",
                "payment collection",
                "production publish",
            ],
            status="draft",
            demand_signal_id=sig,
            value_flags=value_flags,
        )
        if not sig:
            # weak pair without demand evidence
            plan.offer_steps.insert(
                0, "⚠ No demand_signal_id — run DemandPulse before scaling this offer"
            )
        self.plans.append(plan)
        self._persist()
        try:
            from levi.brain.corpus import Corpus

            Corpus().add(
                f"Income draft {plan.id}: {plan.opportunity_title[:120]} signal={plan.demand_signal_id}",
                kind="INFERENCE",
                source=f"income:{plan.id}",
                tags=["income", "draft"],
            )
        except Exception:
            pass
        return plan

    def format_plan(self, plan: ServicePlan) -> str:
        lines = [
            f"=== Income Factory Plan [{plan.id}] ===",
            f"Opportunity: {plan.opportunity_title}",
            f"Service: {plan.service}  status={plan.status}",
            f"Demand signal: {plan.demand_signal_id or '(none — weak symbiosis)'}",
            f"Value flags: {plan.value_flags or ['—']}",
            "",
            "Offer:",
        ]
        for s in plan.offer_steps:
            lines.append(f"  · {s}")
        lines.append("Automation (gated):")
        for s in plan.automation_steps:
            lines.append(f"  · {s}")
        lines.append("HITL required before:")
        for s in plan.requires_hitl:
            lines.append(f"  ! {s}")
        lines.append("")
        lines.append("Income Factory is a capability — not LEVI's sole purpose.")
        return "\n".join(lines)

    def format_status(self) -> str:
        lines = ["=== Income Factory ===", f"plans={len(self.plans)}", ""]
        for p in self.plans[-5:]:
            lines.append(f"  [{p.id}] {p.status}  {p.opportunity_title[:50]}")
        if not self.plans:
            lines.append("  (none — compose after DemandPulse opportunity)")
        return "\n".join(lines)

    def symbiotic_check(self) -> str:
        """Other half: plans without demand evidence are incomplete."""
        lines = ["Symbiosis Income Factory → DemandPulse:", ""]
        if not self.plans:
            lines.append("No plans — compose after a DemandPulse opportunity.")
            return "\n".join(lines)
        try:
            from levi.demand.pulse import DemandPulse

            n = len(DemandPulse().opportunities)
            lines.append(f"Demand opportunities on file: {n}")
            if n == 0:
                lines.append("Plans exist without scored demand — pair is weak.")
                lines.append("  value: run demand --scan before scaling offers")
            else:
                lines.append("Demand half present — keep offers scoped to signals.")
        except Exception as e:
            lines.append(f"DemandPulse unavailable: {e}")
        lines.append("Forbidden: sell past evidence or fake scarcity.")
        return "\n".join(lines)

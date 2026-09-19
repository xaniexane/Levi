"""Shield through the legion service standard.

analyze -> quote -> deliver -> paid -> showcase, riding the shared
machinery (services.offering, bounty hunts/payment). Quotes ride the
founder price advisor; money rides the Cybrus gateway only and fails
closed; showcase admits only paid, receipted work and only with the
client's explicit consent.

Service types used (existing taxonomy — no new types needed):
- "cyber-audit" for the assessment engagement
- "cyber-hardening" for the hardening engagement

Hard boundaries (structural, not advisory):
- No authorization, no work: every stage re-checks the engagement
  authorization through the shield gate.
- A quote is never a charge; money moves only through the Cybrus
  money gateway, and with no rail registered it always refuses.
- The service plans and records defensive assessments. It performs
  no automated intrusion and ships no offensive capability.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Mapping, Optional

from levi.services.offering import (
    ServiceError,
    ServiceOffering,
    attach_analysis,
    deliver_service,
    offer_service,
    quote_service,
    showcase_service,
)
from levi.services.shield.authorization import require_authorization
from levi.services.shield.report import executive_summary

AUDIT_TYPE = "cyber-audit"
HARDENING_TYPE = "cyber-hardening"


def offer_shield(
    *,
    provider: str,
    title: str,
    client: str,
    auth_id: str,
    service_type: str = AUDIT_TYPE,
    problem: str = "",
    deadline: str = "",
    home: Optional[Path] = None,
) -> ServiceOffering:
    """Stage 1 — offer. Requires a live authorization first."""
    require_authorization(auth_id, home)
    if service_type not in (AUDIT_TYPE, HARDENING_TYPE):
        raise ServiceError(
            f"shield offers {AUDIT_TYPE} or {HARDENING_TYPE}, got {service_type!r}"
        )
    return offer_service(
        provider=provider,
        service_type=service_type,
        title=title,
        problem=problem or f"authorized security assessment for {client}",
        scope=f"authorization {auth_id}",
        deadline=deadline,
        client=client,
        home=home,
    )


def analyze_shield(
    offering: ServiceOffering,
    auth_id: str,
    plan: Mapping[str, object],
    *,
    home: Optional[Path] = None,
) -> ServiceOffering:
    """Stage 2 — analyze: record the assessment plan as the analysis."""
    require_authorization(auth_id, home)
    method = plan.get("method") or []
    findings = [
        {
            "finding": f"{m.get('name')} ({m.get('skill_id')})",
            "evidence": str(m.get("description") or ""),
            "severity": "info",
            "recommendation": "assess against this playbook within the authorized scope",
        }
        for m in method
    ]
    return attach_analysis(
        offering,
        subject=f"shield assessment plan {plan.get('plan_id')}",
        summary=(
            f"{plan.get('assessment_type')} assessment of "
            f"{', '.join(plan.get('targets') or [])} from the defensive playbook base"
        ),
        findings=findings,
        confidence=1.0,
        sensed_from="shield assessment planning",
        home=home,
    )


def quote_shield(
    offering: ServiceOffering,
    auth_id: str,
    *,
    giant_price: Optional[float] = None,
    strategy: str = "volume",
    home: Optional[Path] = None,
) -> ServiceOffering:
    """Stage 3 — quote via the founder price advisor. A quote, not a charge.

    ``giant_price`` is accepted only when the client supplies a real
    competitor number — the service never invents one.
    """
    require_authorization(auth_id, home)
    return quote_service(
        offering, giant_price=giant_price, strategy=strategy, home=home
    )


def deliver_shield(
    offering: ServiceOffering,
    auth_id: str,
    sealed_report: Mapping[str, object],
    *,
    confidence: float = 0.9,
    home: Optional[Path] = None,
) -> ServiceOffering:
    """Stage 4 — deliver: the sealed assessment report + hardening plan."""
    require_authorization(auth_id, home)
    evidence = [
        f"report {sealed_report.get('report_id')} sealed",
        f"findings: {len(sealed_report.get('findings') or [])}",
        f"hardening actions verified: {sealed_report.get('actions_verified')}/"
        f"{sealed_report.get('actions_total')}",
    ]
    return deliver_service(
        offering,
        solution=executive_summary(sealed_report),
        evidence=evidence,
        confidence=confidence,
        verification=(
            "sealed report; loop "
            + ("closed" if sealed_report.get("loop_closed") else "open")
        ),
        home=home,
    )


def pay_shield(
    offering: ServiceOffering,
    auth_id: str,
    *,
    authorized_by: str,
    home: Optional[Path] = None,
) -> Dict[str, object]:
    """Stage 5 — paid: plan, agree, and attempt settlement through the
    Cybrus gateway. Fail-closed: with no rail registered the gateway
    refuses and the refusal is recorded."""
    require_authorization(auth_id, home)
    from levi.bounty.hunts import BountyStore
    from levi.bounty.payment import (
        mark_delivered_for_payment,
        record_agreement,
        request_payment,
        settle_bounty,
    )

    store = BountyStore(home=home)
    bounty = store.get(offering.bounty_id)
    if bounty is None:
        raise ServiceError(f"bounty {offering.bounty_id} not found")
    request_payment(bounty)
    bounty = record_agreement(bounty, note="client agreed to shield terms")
    bounty = mark_delivered_for_payment(bounty)
    store.save(bounty)
    result = settle_bounty(bounty, authorized_by=authorized_by, note="shield settlement")
    return result


def showcase_shield(
    offering: ServiceOffering,
    auth_id: str,
    *,
    client_consent: bool = False,
    home: Optional[Path] = None,
):
    """Stage 6 — showcase: admits only paid, receipted work, and only
    with the client's explicit consent."""
    require_authorization(auth_id, home)
    if not client_consent:
        raise ServiceError(
            "showcase requires the client's explicit consent — refused"
        )
    return showcase_service(offering, home=home)

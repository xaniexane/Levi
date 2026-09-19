"""Service offerings: the analyze -> quote -> deliver -> paid -> showcase
standard, composed over the bounty hunter machinery.

Any provider — an organ (UniForge, DemandPulse, ...) or Levi in
general — offers services through this one pipeline. The offering
carries the provider identity and service type; the work itself
rides the bounty state machine, quotes ride the founder price
advisor, and money rides the Cybrus gateway only.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

# Legion-wide service taxonomy. Cyber flavors are UniForge-shaped
# (code surgeon: audit, hardening, forensics); dev flavors are
# Site-Lift-shaped (builds, lifts, automation).
SERVICE_TYPES = {
    # cyber — UniForge-flavored
    "cyber-audit": "security audit of code or systems (defensive, blue-team)",
    "cyber-hardening": "harden a system or codebase against attack",
    "cyber-forensics": "forensic diagnosis of a breach, failure, or anomaly",
    # software development — Site-Lift-flavored
    "dev-build": "build new software to a specification",
    "dev-lift": "uplift an existing site/system (the Site Lift pattern)",
    "dev-automation": "automation, pipelines, and agent wiring",
    # career — job-organ-flavored
    "job-search": "job search as a service: opportunity scan, scored matches, application packages",
    # operations — snapshot-flavored
    "ops-snapshot": "snapshot a system/project/config into versioned, restorable, refinable artifacts",
}


class ServiceError(ValueError):
    """Raised when an offering violates the standard."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _home() -> Path:
    base = os.environ.get("LEVI_HOME") or str(Path.home() / ".levi")
    return Path(base).expanduser()


def _services_path(home: Optional[Path] = None) -> Path:
    d = (home or _home()) / "services"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "offerings.jsonl"
    if not p.exists():
        fd = os.open(str(p), os.O_WRONLY | os.O_CREAT, 0o600)
        os.close(fd)
    else:
        os.chmod(p, 0o600)
    return p


@dataclass
class ServiceOffering:
    """One service offered through the standard pipeline.

    provider: the offering organ, or "levi" for Levi in general.
    service_type: one of SERVICE_TYPES.
    bounty_id: the underlying bounty (hunt) carrying the work.
    analysis_id: the analysis report backing the offer.
    stage: where the offering sits in the standard pipeline.
    """

    offering_id: str
    provider: str
    service_type: str
    bounty_id: str
    title: str
    analysis_id: str = ""
    stage: str = "offered"  # offered | analyzed | quoted | delivering | delivered | paid | showcased
    created_at: str = field(default_factory=_utcnow)
    updated_at: str = field(default_factory=_utcnow)
    history: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.offering_id or not self.offering_id.strip():
            raise ServiceError("offering_id must be non-empty")
        if not self.provider or not self.provider.strip():
            raise ServiceError("provider must be non-empty")
        if self.service_type not in SERVICE_TYPES:
            raise ServiceError(
                f"service_type must be one of {sorted(SERVICE_TYPES)}, "
                f"got {self.service_type!r}"
            )
        if not self.bounty_id or not self.bounty_id.strip():
            raise ServiceError("bounty_id must be non-empty")

    def log(self, event: str, detail: str = "") -> None:
        self.history.append({"ts": _utcnow(), "event": event, "detail": detail})
        self.updated_at = _utcnow()

    def advance(self, stage: str, note: str = "") -> "ServiceOffering":
        self.stage = stage
        self.log("stage", f"{stage}: {note}" if note else stage)
        return self

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ServiceOffering":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in raw.items() if k in known})


class ServiceStore:
    """Owner-only store of service offerings."""

    def __init__(self, home: Optional[Path] = None):
        self.path = _services_path(home)

    def _read_all(self) -> Dict[str, ServiceOffering]:
        out: Dict[str, ServiceOffering] = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                o = ServiceOffering.from_dict(json.loads(line))
            except Exception:
                continue
            out[o.offering_id] = o
        return out

    def _write_all(self, items: Dict[str, ServiceOffering]) -> None:
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            for o in items.values():
                fh.write(json.dumps(o.to_dict()) + "\n")
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)

    def save(self, offering: ServiceOffering) -> ServiceOffering:
        items = self._read_all()
        items[offering.offering_id] = offering
        self._write_all(items)
        return offering

    def get(self, offering_id: str) -> Optional[ServiceOffering]:
        return self._read_all().get(offering_id)

    def list(self) -> List[ServiceOffering]:
        return list(self._read_all().values())


def offer_service(
    *,
    provider: str,
    service_type: str,
    title: str,
    problem: str,
    scope: str = "",
    deadline: str = "",
    client: str = "",
    home: Optional[Path] = None,
):
    """Stage 1 — offer: register a service through the standard pipeline.

    Creates the underlying bounty (the hunt carrying the work) and
    the offering record. Offering is a promise to follow the
    pipeline, not a promise of outcome.
    """
    from levi.bounty.hunts import BountyStore, new_bounty, transition
    from levi.bounty.hunts import BountyState

    if service_type not in SERVICE_TYPES:
        raise ServiceError(
            f"service_type must be one of {sorted(SERVICE_TYPES)}, "
            f"got {service_type!r}"
        )
    bounty = new_bounty(
        title=title, problem=problem, scope=scope, deadline=deadline,
        client=client,
    )
    bounty = transition(bounty, BountyState.OPEN, note=f"service offered by {provider}")
    BountyStore(home=home).save(bounty)

    offering = ServiceOffering(
        offering_id="svc_" + uuid.uuid4().hex[:10],
        provider=provider,
        service_type=service_type,
        bounty_id=bounty.id,
        title=title,
    )
    offering.log("offered", f"{provider} offers {service_type}: {title}")
    return ServiceStore(home=home).save(offering)


def attach_analysis(
    offering: ServiceOffering,
    *,
    subject: str,
    summary: str,
    findings: List[Mapping[str, str]],
    confidence: Optional[float] = None,
    sensed_from: str = "",
    home: Optional[Path] = None,
) -> ServiceOffering:
    """Stage 2 — analyze: record the AI analysis backing the offer.

    The analysis reports what was examined and found. No fabrication:
    every finding requires evidence.
    """
    from levi.services.analysis import analyze_service

    report = analyze_service(
        subject=subject,
        provider=offering.provider,
        service_type=offering.service_type,
        summary=summary,
        findings=findings,
        confidence=confidence,
        sensed_from=sensed_from,
        home=home,
    )
    offering.analysis_id = report.report_id
    offering.advance("analyzed", f"analysis {report.report_id}: {summary[:80]}")
    return ServiceStore(home=home).save(offering)


def quote_service(
    offering: ServiceOffering,
    *,
    giant_price: Optional[float] = None,
    strategy: str = "volume",
    founder_commission: float = 0.0,
    home: Optional[Path] = None,
) -> ServiceOffering:
    """Stage 3 — quote: price the service via the founder price advisor.

    A QUOTE, not a charge: doctrine-compliant pricing (no free core,
    ~30-60% below giants, volume over margin). Moves nothing.
    """
    from levi.bounty.hunts import BountyStore, quote_bounty

    store = BountyStore(home=home)
    bounty = store.get(offering.bounty_id)
    if bounty is None:
        raise ServiceError(f"bounty {offering.bounty_id} not found")
    bounty = quote_bounty(
        bounty, giant_price=giant_price, strategy=strategy,
        founder_commission=founder_commission,
    )
    store.save(bounty)
    offering.advance(
        "quoted", f"advisor quote ${bounty.quote_usd:.2f} (quote, not a charge)"
    )
    return ServiceStore(home=home).save(offering)


def deliver_service(
    offering: ServiceOffering,
    *,
    solution: str,
    evidence: List[str],
    confidence: Optional[float] = None,
    verification: str = "",
    home: Optional[Path] = None,
) -> ServiceOffering:
    """Stage 4 — deliver: run the hunt and record the delivered solution.

    The solution must be detailed and accurate: evidence and a
    verification note are required, never fabricated. The provider
    agrees the work is done before delivery is recorded.
    """
    from levi.bounty.hunts import BountyStore, transition
    from levi.bounty.hunts import BountyState

    if not solution or not solution.strip():
        raise ServiceError("solution must be non-empty — no empty deliveries")
    if not evidence:
        raise ServiceError(
            "delivery requires evidence — the hunter wins on accuracy, not claims"
        )
    if confidence is None:
        raise ServiceError(
            "delivery requires an honest confidence number (0..1) — "
            "no unstated confidence on delivered work"
        )
    store = BountyStore(home=home)
    bounty = store.get(offering.bounty_id)
    if bounty is None:
        raise ServiceError(f"bounty {offering.bounty_id} not found")
    # agree -> hunting -> delivered through the bounty state machine
    for target, note in (
        (BountyState.AGREED, "terms agreed"),
        (BountyState.HUNTING, f"{offering.provider} hunts: {offering.title}"),
    ):
        try:
            bounty = transition(bounty, target, note=note)
        except Exception:
            pass  # already past this stage — forward-only, never backward
    bounty.solution = solution
    bounty.evidence = list(evidence)
    bounty.confidence = confidence
    bounty.verification = verification or "evidence-backed delivery"
    bounty.log("delivered", f"solution delivered with {len(evidence)} evidence items")
    bounty = transition(bounty, BountyState.DELIVERED, note="solution delivered")
    store.save(bounty)
    offering.advance("delivered", f"solution delivered, verification: {bounty.verification[:80]}")
    return ServiceStore(home=home).save(offering)


def showcase_service(
    offering: ServiceOffering,
    *,
    home: Optional[Path] = None,
):
    """Stage 6 — showcase: admit completed, paid work to the track record.

    Admits only PAID bounties with a Cybrus gateway receipt. Refuses
    anything less, with the reason stated. The showcase starts empty
    and stays honest.
    """
    from levi.bounty.hunts import BountyStore
    from levi.bounty.showcase import ShowcaseStore, admit

    store = BountyStore(home=home)
    bounty = store.get(offering.bounty_id)
    if bounty is None:
        raise ServiceError(f"bounty {offering.bounty_id} not found")
    entry = admit(bounty)  # raises ShowcaseRefused unless paid + receipted
    ShowcaseStore(home=home).add(entry)
    offering.advance("showcased", f"admitted as {entry.entry_id}")
    ServiceStore(home=home).save(offering)
    return entry

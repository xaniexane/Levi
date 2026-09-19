"""Match a Site Lift report to a tailored team pack and assemble the offer.

Given a LiftReport (levi.services.site_lift), match failed measured
findings -> the team pack whose crew covers the most gaps, then
assemble one offer object: report + crew + paper quote.

Deterministic: same report, same pack choice, same offer id, same
quote. Unmatched findings are reported as "no crew covers this" and
are NEVER silently dropped — the honest gap is part of the offer.

Paper-only money: the quote seam calls the founder price advisor
(quote, not a charge). Payment still rides the Cybrus gateway only;
this module moves nothing.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from levi.services.site_lift import GOALS, LiftReport
from levi.services.site_teams import PACK_ORDER, TeamError, get_pack, list_packs

# Crown regression checks re-run foundation/feature probes under a
# "c-reg:" prefix; match on the base id so a gap is counted once.
_REG_PREFIX = "c-reg:"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _home() -> Path:
    base = os.environ.get("LEVI_HOME") or str(Path.home() / ".levi")
    return Path(base).expanduser()


def _offers_dir(home: Optional[Path] = None) -> Path:
    d = (home or _home()) / "services" / "team_offers"
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class MatchFinding:
    check_id: str  # base id, "c-reg:" prefix stripped
    label: str
    goals: Tuple[str, ...]
    round_id: str
    evidence: str


@dataclass
class RoleCoverage:
    role_id: str
    role_title: str
    findings: List[MatchFinding] = field(default_factory=list)


@dataclass
class TeamMatch:
    report_id: str
    pack_id: str
    pack_title: str
    coverage: List[RoleCoverage] = field(default_factory=list)
    unmatched: List[MatchFinding] = field(default_factory=list)

    @property
    def covered_count(self) -> int:
        return sum(len(rc.findings) for rc in self.coverage)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def failed_findings(report: LiftReport) -> List[MatchFinding]:
    """Every failed MEASURED check in the report, de-duplicated by base
    check id. Attested checks are the keeper's attestations, not crew
    work — they never become findings."""
    seen: Dict[str, MatchFinding] = {}
    for rnd in report.rounds:
        for c in rnd.checks:
            if c.kind != "measured" or c.passed:
                continue
            base = c.check_id
            if base.startswith(_REG_PREFIX):
                base = base[len(_REG_PREFIX):]
            if base in seen:
                continue
            seen[base] = MatchFinding(
                check_id=base,
                label=c.label,
                goals=tuple(c.goals),
                round_id=rnd.round_id,
                evidence=c.evidence,
            )
    return list(seen.values())


def _pack_coverage_count(pack: Mapping[str, Any], findings: List[MatchFinding]) -> int:
    coverable = {cid for role in pack["roles"] for cid in role["covers"]}
    return sum(1 for f in findings if f.check_id in coverable)


def recommend_pack(report: LiftReport) -> str:
    """Pick the pack covering the most failed findings. Ties break in
    PACK_ORDER (most specific first, generic last). Deterministic."""
    findings = failed_findings(report)
    if not findings:
        return "generic"
    best: Optional[str] = None
    best_n = -1
    for pack in list_packs():
        n = _pack_coverage_count(pack, findings)
        if n > best_n:
            best_n = n
            best = pack["id"]
    return best or "generic"


def match_report(report: LiftReport, *, pack_id: Optional[str] = None) -> TeamMatch:
    """Match findings -> roles of the chosen pack.

    pack_id: explicit pack override (validated); None -> recommend.
    Raises TeamError on unknown pack_id.
    """
    chosen = pack_id or recommend_pack(report)
    pack = get_pack(chosen)  # raises TeamError on unknown
    findings = failed_findings(report)
    cover_by_role: Dict[str, List[MatchFinding]] = {
        role["id"]: [] for role in pack["roles"]
    }
    cover_index: Dict[str, str] = {}
    for role in pack["roles"]:
        for cid in role["covers"]:
            # first role in pack order wins a check id; pack order is
            # deterministic so coverage never flickers
            cover_index.setdefault(cid, role["id"])
    unmatched: List[MatchFinding] = []
    for f in findings:
        rid = cover_index.get(f.check_id)
        if rid is None:
            unmatched.append(f)
        else:
            cover_by_role[rid].append(f)
    coverage = [
        RoleCoverage(
            role_id=role["id"],
            role_title=role["title"],
            findings=cover_by_role[role["id"]],
        )
        for role in pack["roles"]
    ]
    return TeamMatch(
        report_id=report.report_id,
        pack_id=pack["id"],
        pack_title=pack["title"],
        coverage=coverage,
        unmatched=unmatched,
    )


# ---------------------------------------------------------------------------
# Offer assembly — report + crew as one offer object.
# ---------------------------------------------------------------------------


def report_hash(report: LiftReport) -> str:
    """Stable sha256 over the report's canonical JSON."""
    blob = json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class TeamOffer:
    offer_id: str  # deterministic: team_<pack>_<hash[:8]>
    report_id: str
    report_hash: str
    pack_id: str
    pack_title: str
    provider: str
    roles: List[Dict[str, Any]] = field(default_factory=list)
    unmatched: List[Dict[str, Any]] = field(default_factory=list)
    quote: Optional[Dict[str, Any]] = None  # paper only; None when not quoted
    created_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "TeamOffer":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in raw.items() if k in known})


def quote_pack(
    pack_id: str,
    *,
    giant_price: Optional[float] = None,
    strategy: str = "volume",
) -> Dict[str, Any]:
    """Paper quote for installing the crew, via the founder price
    advisor. A QUOTE, not a charge: advises doctrine-compliant pricing,
    moves nothing. Payment rides Cybrus only."""
    from levi.advisor.pricing import PricePlan, advise_price

    pack = get_pack(pack_id)
    if strategy not in ("volume", "margin"):
        raise TeamError(f"strategy must be volume|margin, got {strategy!r}")
    advice = advise_price(
        PricePlan(tier="entry", giant_price=giant_price, strategy=strategy)
    )
    return {
        "pack_id": pack["id"],
        "pack_title": pack["title"],
        "low_usd": advice.low,
        "high_usd": advice.high,
        "recommended_usd": advice.recommended,
        "rationale": list(advice.rationale),
        "note": "quote, not a charge — payment moves through the Cybrus "
        "gateway only",
    }


def assemble_offer(
    report: LiftReport,
    match: TeamMatch,
    *,
    quote: bool = True,
    giant_price: Optional[float] = None,
    strategy: str = "volume",
) -> TeamOffer:
    """Assemble the one offer: report + crew.

    Deterministic: same report bytes + same pack -> same offer_id.
    Unmatched findings ride along in the offer under `unmatched` so
    nothing is silently dropped.
    """
    pack = get_pack(match.pack_id)
    role_by_id = {r["id"]: r for r in pack["roles"]}
    roles: List[Dict[str, Any]] = []
    for rc in match.coverage:
        role = role_by_id[rc.role_id]
        roles.append(
            {
                "role_id": role["id"],
                "role_title": role["title"],
                "purpose": role["purpose"],
                "covers_findings": [
                    {
                        "check_id": f.check_id,
                        "label": f.label,
                        "evidence": f.evidence,
                    }
                    for f in rc.findings
                ],
                "install_checklist": list(role["checklist"]),
                "escalation": role["escalation"],
            }
        )
    h = report_hash(report)
    offer = TeamOffer(
        offer_id=f"team_{match.pack_id}_{h[:8]}",
        report_id=report.report_id,
        report_hash=h,
        pack_id=match.pack_id,
        pack_title=match.pack_title,
        provider=report.provider,
        roles=roles,
        unmatched=[
            {
                "check_id": f.check_id,
                "label": f.label,
                "goals": list(f.goals),
                "evidence": f.evidence,
                "note": "no crew covers this — site-build work or owner decision, "
                "not an installed crew member",
            }
            for f in match.unmatched
        ],
    )
    if quote:
        offer.quote = quote_pack(
            match.pack_id, giant_price=giant_price, strategy=strategy
        )
    return offer


def save_offer(offer: TeamOffer, *, home: Optional[Path] = None) -> Path:
    p = _offers_dir(home) / f"{offer.offer_id}.json"
    p.write_text(json.dumps(offer.to_dict(), indent=2), encoding="utf-8")
    return p


def load_offer(offer_id: str, *, home: Optional[Path] = None) -> Optional[TeamOffer]:
    p = _offers_dir(home) / f"{offer_id}.json"
    if not p.exists():
        return None
    return TeamOffer.from_dict(json.loads(p.read_text(encoding="utf-8")))

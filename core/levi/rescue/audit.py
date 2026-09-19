"""Act two — the rescue audit (Bar Rescue).

Checks are small probes over a walked site. The honesty laws are binding:

1. A finding ships ONLY with evidence. A probe that returns a finding
   with an empty evidence list has that finding DROPPED into
   ``dropped_hypotheses`` — it never reaches the report.
2. Scoring is deterministic: ``score = max(0, 100 − Σ severity weights)``
   with published weights. No invented sub-scores.
3. The walk is receipted: every fetch rides the forge browser surface;
   refusals are on the record.

A WalkContext is plain data (url → page record) built by the seam
(``seams.walk_invitation``) so the audit itself is pure and testable.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from . import ensure_home, rescue_home
from . import ledger as stone
from .intake import require_consent

#: Published severity weights — the whole scoring formula, no hidden knobs.
SEVERITY_WEIGHTS = {"critical": 25, "high": 15, "medium": 8, "low": 3}
SEVERITIES = tuple(SEVERITY_WEIGHTS)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Evidence:
    """One piece of proof behind a finding. No evidence → no finding."""

    kind: str  # e.g. "http-status", "page-text", "link-list", "form-fields"
    ref: str  # where it came from: the URL or artifact
    note: str  # what it shows, in plain words

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Finding:
    check_id: str
    title: str
    severity: str  # critical | high | medium | low
    evidence: List[Evidence]
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["evidence"] = [e.to_dict() for e in self.evidence]
        return d


@dataclass
class Check:
    """One audit probe. ``probe(walk)`` returns a Finding-dict or None."""

    id: str
    name: str
    severity: str
    probe: Callable[[Dict[str, Dict[str, Any]]], Optional[Dict[str, Any]]]

    def run(self, walk: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        return self.probe(walk)


# -- the standard check set -------------------------------------------------
# Every check reads ONLY what the walk actually saw. If the walk didn't
# see it, the check stays silent — it never invents.


def _check_reachable(walk):
    for url, page in walk.items():
        status = page.get("status")
        if status != 200:
            return {
                "title": "page does not answer cleanly",
                "severity": "high",
                "detail": "expected HTTP 200",
                "evidence": [
                    Evidence("http-status", url, "answered HTTP %s" % (status,))
                ],
            }
    return None


def _check_title(walk):
    for url, page in walk.items():
        title = (page.get("title") or "").strip()
        if not title:
            return {
                "title": "page has no title",
                "severity": "medium",
                "detail": "the browser tab / search listing shows nothing",
                "evidence": [
                    Evidence("page-text", url, "served HTML carries no <title>")
                ],
            }
    return None


def _check_heading(walk):
    for url, page in walk.items():
        text = page.get("text") or ""
        if not re.search(r"(?m)^#{1,2} |^(?:[A-Z][^\n]{2,80})$", text):
            # fall back to a structural read: any heading marker at all
            if "heading" not in (page.get("structure") or "") and not re.search(
                r"(?im)^(#+ .+|.+\n[=-]{3,})$", text
            ):
                return {
                    "title": "page has no clear top-level heading",
                    "severity": "low",
                    "detail": "visitors land with no headline telling them where they are",
                    "evidence": [
                        Evidence("page-text", url, "first 200 chars: %r" % text[:200])
                    ],
                }
    return None


_CONTACT_RE = re.compile(
    r"(\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})"
    r"|([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
)


def _check_contact(walk):
    for url, page in walk.items():
        text = page.get("text") or ""
        hits = sorted(set(_CONTACT_RE.findall(text)))
        flat = sorted({a or b for a, b in hits})
        if not flat:
            return {
                "title": "no contact info found on the site",
                "severity": "high",
                "detail": "no phone number or email address visible in walked pages",
                "evidence": [
                    Evidence(
                        "page-text",
                        url,
                        "walked %d page(s), zero phone/email matches" % len(walk),
                    )
                ],
            }
    return None


def _check_links(walk):
    dead = []
    for url, page in walk.items():
        for link in page.get("links") or []:
            target = link.get("target") if isinstance(link, dict) else link
            if not target:
                dead.append(url)
    if dead:
        return {
            "title": "links with no destination",
            "severity": "medium",
            "detail": "%d link marker(s) point nowhere" % len(dead),
            "evidence": [
                Evidence("link-list", u, "link marker without a target")
                for u in dead[:10]
            ],
        }
    return None


def _check_forms(walk):
    unnamed = []
    for url, page in walk.items():
        for form in page.get("forms") or []:
            flds = form.get("fields") if isinstance(form, dict) else []
            if not flds:
                unnamed.append(url)
    if unnamed:
        return {
            "title": "form with no named fields",
            "severity": "low",
            "detail": "a form exists but exposes no fields to fill",
            "evidence": [
                Evidence("form-fields", u, "form descriptor has zero fields")
                for u in unnamed[:10]
            ],
        }
    return None


DEFAULT_CHECKS: List[Check] = [
    Check("reachable", "Reachability", "high", _check_reachable),
    Check("has-title", "Page title", "medium", _check_title),
    Check("has-heading", "Top-level heading", "low", _check_heading),
    Check("contact-visible", "Contact info", "high", _check_contact),
    Check("links-resolve", "Link targets", "medium", _check_links),
    Check("forms-described", "Form fields", "low", _check_forms),
]


@dataclass
class AuditReport:
    id: str
    invitation_id: str
    business: str
    site_url: str
    score: int
    findings: List[Finding]
    dropped_hypotheses: List[Dict[str, Any]]
    receipts: List[Dict[str, Any]]
    audited_at: str = ""
    baseline: Optional[Dict[str, Any]] = None  # analytics baseline dict, if measured

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["findings"] = [f.to_dict() for f in self.findings]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditReport":
        data = dict(data)
        data["findings"] = [
            Finding(
                check_id=f["check_id"],
                title=f["title"],
                severity=f["severity"],
                evidence=[Evidence(**e) for e in f.get("evidence", [])],
                detail=f.get("detail", ""),
            )
            for f in data.get("findings", [])
        ]
        return cls(
            **{
                k: data.get(
                    k, [] if k in ("findings", "dropped_hypotheses", "receipts") else ""
                )
                for k in (
                    "id",
                    "invitation_id",
                    "business",
                    "site_url",
                    "score",
                    "findings",
                    "dropped_hypotheses",
                    "receipts",
                    "audited_at",
                    "baseline",
                )
            }
        )


def _next_id(home) -> str:
    state_path = rescue_home(home) / "state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        state = {}
    n = int(state.get("audit_counter", 0)) + 1
    state["audit_counter"] = n
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return "audit-%04d" % n


def _coerce_finding(check: Check, raw: Dict[str, Any]) -> Optional[Finding]:
    """Evidence law: no evidence → dropped, never shipped."""
    evidence = [
        e if isinstance(e, Evidence) else Evidence(**e)
        for e in (raw.get("evidence") or [])
    ]
    severity = raw.get("severity") or check.severity
    if severity not in SEVERITIES:
        severity = check.severity
    if not evidence:
        return None
    return Finding(
        check_id=check.id,
        title=str(raw.get("title") or check.name),
        severity=severity,
        evidence=evidence,
        detail=str(raw.get("detail") or ""),
    )


def run_audit(
    home,
    invitation_id: str,
    checks: List[Check],
    walk: Dict[str, Dict[str, Any]],
    receipts: Optional[List[Dict[str, Any]]] = None,
    baseline: Optional[Dict[str, Any]] = None,
) -> AuditReport:
    """Run the rescue audit. Consent is required; evidence is required.

    ``baseline`` is an optional analytics baseline dict (from
    ``analytics.baseline_from_walk``) — the measured before-state that
    the plan turns into targets and the reveal turns into deltas.
    """
    inv = require_consent(home, invitation_id)
    if not walk:
        raise ValueError("run_audit: empty walk — nothing was actually visited")
    if baseline is not None and hasattr(baseline, "to_dict"):
        baseline = baseline.to_dict()
    findings: List[Finding] = []
    dropped: List[Dict[str, Any]] = []
    for check in checks:
        try:
            raw = check.run(walk)
        except Exception as exc:  # a broken probe is not a finding
            dropped.append({"check_id": check.id, "reason": "probe error: %s" % exc})
            continue
        if raw is None:
            continue
        finding = _coerce_finding(check, raw)
        if finding is None:
            dropped.append(
                {
                    "check_id": check.id,
                    "reason": "dropped: finding carried no evidence",
                    "title": raw.get("title"),
                }
            )
        else:
            findings.append(finding)
    score = max(0, 100 - sum(SEVERITY_WEIGHTS[f.severity] for f in findings))
    report = AuditReport(
        id=_next_id(home),
        invitation_id=inv.id,
        business=inv.business,
        site_url=inv.site_url,
        score=score,
        findings=findings,
        dropped_hypotheses=dropped,
        receipts=list(receipts or []),
        audited_at=_now(),
        baseline=dict(baseline) if baseline else None,
    )
    path = ensure_home(home) / "audits" / ("%s.json" % report.id)
    path.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    stone.record(
        home,
        "audit.completed",
        inv.id,
        {
            "audit_id": report.id,
            "score": score,
            "findings": len(findings),
            "dropped": len(dropped),
        },
    )
    return report


def get_audit(home, audit_id: str) -> AuditReport:
    path = ensure_home(home) / "audits" / ("%s.json" % audit_id)
    return AuditReport.from_dict(json.loads(path.read_text(encoding="utf-8")))


__all__ = [
    "DEFAULT_CHECKS",
    "SEVERITIES",
    "SEVERITY_WEIGHTS",
    "AuditReport",
    "Check",
    "Evidence",
    "Finding",
    "get_audit",
    "run_audit",
]

"""Assessment planning and the findings register.

Assessment plans are drawn from the 823 defensive cyber playbooks
(``levi.skill.cyber_skills``): each assessment category maps to
playbook tags, resolved live at plan time so new playbooks register
automatically. The service plans the assessment and records findings
with evidence; evidence capture itself is operator-driven against the
authorized scope — the module performs no automated intrusion and
ships no offensive capability.

Every public entry requires a valid, unexpired authorization and
rejects out-of-scope targets.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Mapping, Optional

from levi.services.shield.authorization import (
    EngagementAuthorization,
    assert_in_scope,
    require_authorization,
)

# Assessment category -> playbook tags used to resolve method references.
CATEGORY_TAGS: Dict[str, List[str]] = {
    "wireless": ["wireless", "assessment"],
    "web-application": ["web", "appsec", "assessment"],
    "network": ["network", "assessment"],
    "configuration": ["hardening", "configuration"],
    "cloud": ["cloud", "assessment"],
    "email-security": ["phishing", "email", "defense"],
    "incident-readiness": ["incident-response", "tabletop", "readiness"],
}

SEVERITIES = ("critical", "high", "medium", "low", "info")


class AssessmentError(ValueError):
    """Raised when an assessment plan or finding is invalid."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _home() -> Path:
    base = os.environ.get("LEVI_HOME") or str(Path.home() / ".levi")
    return Path(base).expanduser()


def _findings_path(home: Optional[Path] = None) -> Path:
    d = (home or _home()) / "services" / "shield"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "findings.jsonl"
    if not p.exists():
        fd = os.open(str(p), os.O_WRONLY | os.O_CREAT, 0o600)
        os.close(fd)
    else:
        os.chmod(p, 0o600)
    return p


def _resolve_playbooks(category: str, limit: int = 6) -> List[Dict[str, str]]:
    """Resolve method references from the live cyber playbook registry."""
    from levi.skill.cyber_skills import CYBER_SKILLS

    wanted = CATEGORY_TAGS[category]
    scored = []
    for skill in CYBER_SKILLS:
        tags = [t.lower() for t in (skill.tags or [])]
        hits = sum(1 for w in wanted if w in tags)
        if hits:
            scored.append((hits, skill))
    scored.sort(key=lambda pair: (-pair[0], pair[1].id))
    out = []
    for _, skill in scored[:limit]:
        out.append(
            {
                "skill_id": skill.id,
                "name": skill.name,
                "description": skill.description,
            }
        )
    return out


def plan_assessment(
    auth_id: str,
    *,
    assessment_type: str,
    targets: List[str],
    objective: str = "",
    home: Optional[Path] = None,
) -> Dict[str, object]:
    """Build an assessment plan. Refuses without authorization, with an
    expired authorization, with a category outside the rules of
    engagement, or with any out-of-scope target."""
    auth: EngagementAuthorization = require_authorization(auth_id, home)
    if assessment_type not in auth.permitted_categories:
        raise AssessmentError(
            f"assessment type {assessment_type!r} is not in this engagement's "
            f"rules of engagement {auth.permitted_categories} — refused"
        )
    clean_targets = [assert_in_scope(auth, t) for t in targets]
    if not clean_targets:
        raise AssessmentError("at least one in-scope target is required")
    playbooks = _resolve_playbooks(assessment_type)
    if not playbooks:
        raise AssessmentError(
            f"no defensive playbooks resolve for {assessment_type!r} — "
            "the service plans only from its playbook knowledge base"
        )
    plan = {
        "plan_id": "plan_" + uuid.uuid4().hex[:10],
        "auth_id": auth.auth_id,
        "client": auth.client,
        "assessment_type": assessment_type,
        "targets": clean_targets,
        "objective": objective.strip(),
        "testing_windows": auth.testing_windows,
        "exclusions": auth.exclusions,
        "method": playbooks,
        "checklist": [
            "confirm scope and authorization with the client contact",
            "review the referenced playbooks before any evidence capture",
            "capture evidence only against the listed targets, inside the testing windows",
            "record every finding with evidence — no finding without evidence",
            "respect exclusions: " + (", ".join(auth.exclusions) if auth.exclusions else "none stated"),
            "report, then re-verify after hardening",
        ],
        "created_at": _utcnow(),
    }
    return plan


@dataclass
class Finding:
    """One recorded finding. Evidence is mandatory — the service never
    fabricates a finding."""

    finding_id: str
    auth_id: str
    plan_id: str
    target: str
    severity: str
    title: str
    evidence: str
    playbook_id: str
    status: str = "open"
    recorded_at: str = ""

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


class FindingsRegister:
    """Append-only findings store, owner-only permissions."""

    def __init__(self, home: Optional[Path] = None):
        self._path = _findings_path(home)

    def _read_all(self) -> List[Dict[str, object]]:
        out = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def record(
        self,
        auth_id: str,
        *,
        plan_id: str,
        target: str,
        severity: str,
        title: str,
        evidence: str,
        playbook_id: str,
        home: Optional[Path] = None,
    ) -> Finding:
        auth = require_authorization(auth_id, home)
        clean_target = assert_in_scope(auth, target)
        if severity not in SEVERITIES:
            raise AssessmentError(
                f"severity must be one of {SEVERITIES}, got {severity!r}"
            )
        if not title.strip():
            raise AssessmentError("finding title is required")
        if not evidence.strip():
            raise AssessmentError(
                "finding requires evidence — the service never records "
                "a finding without it"
            )
        finding = Finding(
            finding_id="find_" + uuid.uuid4().hex[:10],
            auth_id=auth.auth_id,
            plan_id=plan_id,
            target=clean_target,
            severity=severity,
            title=title.strip(),
            evidence=evidence.strip(),
            playbook_id=playbook_id.strip(),
            recorded_at=_utcnow(),
        )
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(finding.to_dict(), sort_keys=True) + "\n")
        return finding

    def list(self, auth_id: str = "") -> List[Finding]:
        rows = self._read_all()
        if auth_id:
            rows = [r for r in rows if r.get("auth_id") == auth_id]
        return [Finding(**r) for r in rows]

    def set_status(self, finding_id: str, status: str) -> Finding:
        if status not in ("open", "mitigating", "verified", "closed"):
            raise AssessmentError(f"unknown finding status {status!r}")
        rows = self._read_all()
        hit = None
        for row in rows:
            if row.get("finding_id") == finding_id:
                row["status"] = status
                hit = row
        if hit is None:
            raise AssessmentError(f"unknown finding {finding_id!r}")
        self._path.write_text(
            "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n",
            encoding="utf-8",
        )
        return Finding(**hit)


def findings_for_plan(
    plan: Mapping[str, object], home: Optional[Path] = None
) -> List[Finding]:
    plan_id = str(plan.get("plan_id", ""))
    return [f for f in FindingsRegister(home).list() if f.plan_id == plan_id]

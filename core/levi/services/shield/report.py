"""Sealed assessment report + receipt.

The report is the deliverable: scope, method (the playbooks used),
findings, the hardening plan, and verification status — sealed with a
hash chain so the client can confirm it has not been altered. Finish
well: every engagement closes with a receipt.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Mapping, Optional

from levi.services.shield.assess import Finding, FindingsRegister
from levi.services.shield.authorization import EngagementAuthorization, require_authorization
from levi.services.shield.harden import HardeningAction, HardeningStore


class ReportError(ValueError):
    """Raised when a report cannot be built or fails verification."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _home() -> Path:
    base = os.environ.get("LEVI_HOME") or str(Path.home() / ".levi")
    return Path(base).expanduser()


def _seal(body: Dict[str, object]) -> str:
    text = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_report(
    auth_id: str,
    plan: Mapping[str, object],
    *,
    home: Optional[Path] = None,
) -> Dict[str, object]:
    """Assemble and seal the engagement report."""
    auth: EngagementAuthorization = require_authorization(auth_id, home)
    findings: List[Finding] = FindingsRegister(home).list(auth.auth_id)
    actions: List[HardeningAction] = HardeningStore(home).list(auth.auth_id)

    findings_by_severity: Dict[str, int] = {}
    for f in findings:
        findings_by_severity[f.severity] = findings_by_severity.get(f.severity, 0) + 1
    verified = sum(1 for a in actions if a.status == "verified")
    open_findings = [f for f in findings if f.status in ("open", "mitigating")]

    body: Dict[str, object] = {
        "report_id": "shrep_" + uuid.uuid4().hex[:10],
        "auth_id": auth.auth_id,
        "client": auth.client,
        "scope_assets": auth.scope_assets,
        "testing_windows": auth.testing_windows,
        "exclusions": auth.exclusions,
        "assessment_type": plan.get("assessment_type"),
        "targets": plan.get("targets"),
        "method": [
            {"skill_id": m.get("skill_id"), "name": m.get("name")}
            for m in (plan.get("method") or [])
        ],
        "findings": [f.to_dict() for f in findings],
        "findings_by_severity": findings_by_severity,
        "hardening_actions": [a.to_dict() for a in actions],
        "actions_verified": verified,
        "actions_total": len(actions),
        "open_findings": len(open_findings),
        "loop_closed": len(findings) > 0 and len(open_findings) == 0,
        "built_at": _utcnow(),
    }
    sealed = dict(body)
    sealed["seal"] = _seal(body)

    d = (home or _home()) / "services" / "shield"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "reports.jsonl"
    if not p.exists():
        fd = os.open(str(p), os.O_WRONLY | os.O_CREAT, 0o600)
        os.close(fd)
    else:
        os.chmod(p, 0o600)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(sealed, sort_keys=True) + "\n")
    return sealed


def verify_report(sealed: Mapping[str, object]) -> bool:
    """Recompute the seal. Returns False on any tampering."""
    try:
        body = dict(sealed)
        claimed = body.pop("seal", None)
        return bool(claimed) and _seal(body) == claimed
    except Exception:
        return False


def executive_summary(sealed: Mapping[str, object]) -> str:
    counts = sealed.get("findings_by_severity") or {}
    parts = [f"{v} {k}" for k, v in sorted(counts.items())]
    return (
        f"Shield assessment for {sealed.get('client')}: "
        f"{len(sealed.get('findings') or [])} findings "
        f"({', '.join(parts) if parts else 'none'}); "
        f"{sealed.get('actions_verified')}/{sealed.get('actions_total')} "
        f"hardening actions verified; "
        f"loop {'closed' if sealed.get('loop_closed') else 'open'}."
    )

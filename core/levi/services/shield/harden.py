"""Hardening engine: findings -> prioritized strengthening actions -> verification.

Each action is typed (patch, configure, segment, monitor, train,
policy), linked to the defensive playbook that proves it, and
prioritized deterministically from severity and exposure. A finding
is closed only after every one of its actions is re-verified —
assess -> report -> harden -> verify, the loop the service promises.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Mapping, Optional

from levi.services.shield.assess import SEVERITIES, Finding, FindingsRegister
from levi.services.shield.authorization import require_authorization

ACTION_TYPES = ("patch", "configure", "segment", "monitor", "train", "policy")

# severity -> (default action types, base priority). Priority 1 is first.
_SEVERITY_ACTIONS: Dict[str, tuple] = {
    "critical": (("patch", "segment", "monitor"), 1),
    "high": (("patch", "configure", "monitor"), 2),
    "medium": (("configure", "monitor"), 3),
    "low": (("configure", "policy"), 4),
    "info": (("policy", "train"), 5),
}

_ACTION_GUIDANCE: Dict[str, str] = {
    "patch": "apply the vendor fix or upgrade; verify the vulnerable version is gone",
    "configure": "harden the configuration to the playbook baseline; diff before and after",
    "segment": "isolate the affected system or network path; validate the boundary",
    "monitor": "add detection and alerting for the weakness class; test the alert fires",
    "train": "brief the people involved; record the session",
    "policy": "write or update the governing rule; get it acknowledged",
}


class HardeningError(ValueError):
    """Raised when a hardening plan or verification is invalid."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _home() -> Path:
    base = os.environ.get("LEVI_HOME") or str(Path.home() / ".levi")
    return Path(base).expanduser()


def _actions_path(home: Optional[Path] = None) -> Path:
    d = (home or _home()) / "services" / "shield"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "hardening.jsonl"
    if not p.exists():
        fd = os.open(str(p), os.O_WRONLY | os.O_CREAT, 0o600)
        os.close(fd)
    else:
        os.chmod(p, 0o600)
    return p


@dataclass
class HardeningAction:
    action_id: str
    finding_id: str
    auth_id: str
    action_type: str
    title: str
    detail: str
    playbook_id: str
    priority: int
    status: str = "planned"
    verification: str = ""
    created_at: str = ""

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _playbook_name(skill_id: str) -> str:
    try:
        from levi.skill.cyber_skills import CYBER_SKILLS

        for skill in CYBER_SKILLS:
            if skill.id == skill_id:
                return skill.name
    except Exception:
        pass
    return skill_id


def build_hardening_plan(
    auth_id: str,
    findings: List[Finding],
    *,
    home: Optional[Path] = None,
) -> List[HardeningAction]:
    """Turn findings into prioritized, playbook-linked hardening actions."""
    auth = require_authorization(auth_id, home)
    if not findings:
        raise HardeningError("no findings — nothing to harden")
    actions: List[HardeningAction] = []
    for finding in findings:
        if finding.auth_id != auth.auth_id:
            raise HardeningError(
                f"finding {finding.finding_id} belongs to another engagement — refused"
            )
        if finding.status in ("verified", "closed"):
            continue
        types, base = _SEVERITY_ACTIONS[finding.severity]
        playbook_name = _playbook_name(finding.playbook_id)
        for i, action_type in enumerate(types):
            actions.append(
                HardeningAction(
                    action_id="hard_" + uuid.uuid4().hex[:10],
                    finding_id=finding.finding_id,
                    auth_id=auth.auth_id,
                    action_type=action_type,
                    title=f"{action_type}: {finding.title}",
                    detail=(
                        f"For finding {finding.finding_id} ({finding.severity}) "
                        f"on {finding.target}. {_ACTION_GUIDANCE[action_type]}. "
                        f"Method reference: {playbook_name} ({finding.playbook_id})."
                    ),
                    playbook_id=finding.playbook_id,
                    priority=base + (i > 0),
                    created_at=_utcnow(),
                )
            )
    actions.sort(key=lambda a: (a.priority, a.action_id))
    path = _actions_path(home)
    with path.open("a", encoding="utf-8") as fh:
        for action in actions:
            fh.write(json.dumps(action.to_dict(), sort_keys=True) + "\n")
    return actions


class HardeningStore:
    def __init__(self, home: Optional[Path] = None):
        self._path = _actions_path(home)

    def _read_all(self) -> List[Dict[str, object]]:
        out = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def _write_all(self, rows: List[Dict[str, object]]) -> None:
        self._path.write_text(
            "\n".join(json.dumps(r, sort_keys=True) for r in rows) + ("\n" if rows else ""),
            encoding="utf-8",
        )

    def list(self, auth_id: str = "") -> List[HardeningAction]:
        rows = self._read_all()
        if auth_id:
            rows = [r for r in rows if r.get("auth_id") == auth_id]
        return [HardeningAction(**r) for r in rows]

    def mark_applied(self, action_id: str) -> HardeningAction:
        return self._transition(action_id, "applied")

    def verify_action(
        self, auth_id: str, action_id: str, verification: str, home: Optional[Path] = None
    ) -> HardeningAction:
        """Re-verify a hardening action. Requires authorization and a
        real verification note — the loop closes on evidence, not claims."""
        require_authorization(auth_id, home)
        if not verification.strip():
            raise HardeningError(
                "verification requires a note describing what was re-checked"
            )
        rows = self._read_all()
        hit = None
        for row in rows:
            if row.get("action_id") == action_id:
                if row.get("auth_id") != auth_id:
                    raise HardeningError("action belongs to another engagement — refused")
                row["status"] = "verified"
                row["verification"] = verification.strip()
                hit = row
        if hit is None:
            raise HardeningError(f"unknown action {action_id!r}")
        self._write_all(rows)
        self._close_findings_if_verified(hit["finding_id"], home)
        return HardeningAction(**hit)

    def _transition(self, action_id: str, status: str) -> HardeningAction:
        rows = self._read_all()
        hit = None
        for row in rows:
            if row.get("action_id") == action_id:
                row["status"] = status
                hit = row
        if hit is None:
            raise HardeningError(f"unknown action {action_id!r}")
        self._write_all(rows)
        return HardeningAction(**hit)

    def _close_findings_if_verified(self, finding_id: str, home: Optional[Path] = None) -> None:
        rows = self._read_all()
        mine = [r for r in rows if r.get("finding_id") == finding_id]
        if mine and all(r.get("status") == "verified" for r in mine):
            FindingsRegister(home).set_status(finding_id, "verified")


def open_findings(auth_id: str, home: Optional[Path] = None) -> List[Finding]:
    """Findings still needing hardening work."""
    return [
        f
        for f in FindingsRegister(home).list(auth_id)
        if f.status in ("open", "mitigating")
    ]

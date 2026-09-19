"""Written authorization and rules of engagement — as hard gates, not suggestions.

Precedent: the cyber_conducting_wireless_network_penetration_test
playbook requires written authorization defining scope and testing
windows, plus rules of engagement. This module enforces that in code:
no authorization record, no assessment, no findings, no hardening.
Every public entry in this package calls :func:`require_authorization`
first. Expired or out-of-scope work is refused.

An authorization is an affirmative owner-side act: the exact
confirmation phrase plus a named signatory, a non-empty asset scope,
testing windows, and an expiry date. Records are sealed (hash-chained)
under the home directory with owner-only permissions.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

CONFIRMATION_PHRASE = "I AUTHORIZE THIS SECURITY ASSESSMENT"

# Assessment-only categories. Anything outside this list cannot be
# permitted — the service plans and records defensive assessments;
# it has no other mode.
ASSESSMENT_CATEGORIES = (
    "wireless",
    "web-application",
    "network",
    "configuration",
    "cloud",
    "email-security",
    "incident-readiness",
)


class AuthorizationError(ValueError):
    """Raised when authorization is missing, invalid, or expired."""


class ScopeViolation(AuthorizationError):
    """Raised when a target falls outside the authorized scope."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _home() -> Path:
    base = os.environ.get("LEVI_HOME") or str(Path.home() / ".levi")
    return Path(base).expanduser()


def _store_path(home: Optional[Path] = None) -> Path:
    d = (home or _home()) / "services" / "shield"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "authorizations.jsonl"
    if not p.exists():
        fd = os.open(str(p), os.O_WRONLY | os.O_CREAT, 0o600)
        os.close(fd)
    else:
        os.chmod(p, 0o600)
    return p


def _seal(record: Dict[str, object], prev: str) -> str:
    body = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((prev + body).encode("utf-8")).hexdigest()


def _load_all(home: Optional[Path] = None) -> List[Dict[str, object]]:
    p = _store_path(home)
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


@dataclass
class EngagementAuthorization:
    """Written authorization for one assessment engagement."""

    auth_id: str
    client: str
    authorized_contact: str
    contact_role: str
    scope_assets: List[str]
    testing_windows: List[str]
    permitted_categories: List[str]
    exclusions: List[str] = field(default_factory=list)
    authorized_by: str = ""
    granted_at: str = ""
    expires_at: str = ""
    seal: str = ""

    def expired(self) -> bool:
        return date.today().isoformat() > self.expires_at

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def grant_authorization(
    *,
    client: str,
    authorized_contact: str,
    contact_role: str,
    scope_assets: List[str],
    testing_windows: List[str],
    permitted_categories: List[str],
    exclusions: Optional[List[str]] = None,
    authorized_by: str,
    expires_at: str,
    confirmation: str,
    home: Optional[Path] = None,
) -> EngagementAuthorization:
    """Record written authorization. Refuses anything incomplete.

    ``confirmation`` must equal :data:`CONFIRMATION_PHRASE` exactly —
    the affirmative act that opens the gate. ``permitted_categories``
    must be a non-empty subset of :data:`ASSESSMENT_CATEGORIES`.
    ``expires_at`` must be a future YYYY-MM-DD date.
    """
    if confirmation != CONFIRMATION_PHRASE:
        raise AuthorizationError(
            "authorization requires the exact confirmation phrase — "
            "no implied or partial consent is accepted"
        )
    if not client.strip():
        raise AuthorizationError("client organization is required")
    if not authorized_contact.strip() or not contact_role.strip():
        raise AuthorizationError("authorized contact name and role are required")
    assets = [a.strip().lower() for a in scope_assets if a.strip()]
    if not assets:
        raise AuthorizationError("scope_assets must name at least one asset")
    windows = [w.strip() for w in testing_windows if w.strip()]
    if not windows:
        raise AuthorizationError("testing_windows must name at least one window")
    cats = [c.strip() for c in permitted_categories if c.strip()]
    if not cats:
        raise AuthorizationError("permitted_categories must name at least one category")
    bad = [c for c in cats if c not in ASSESSMENT_CATEGORIES]
    if bad:
        raise AuthorizationError(
            f"categories not permitted by this service: {bad} — "
            f"allowed: {list(ASSESSMENT_CATEGORIES)}"
        )
    if not authorized_by.strip():
        raise AuthorizationError("authorized_by signatory is required")
    try:
        exp = date.fromisoformat(expires_at)
    except ValueError:
        raise AuthorizationError("expires_at must be YYYY-MM-DD")
    if exp <= date.today():
        raise AuthorizationError("expires_at must be a future date")

    import uuid

    prev = "GENESIS"
    existing = _load_all(home)
    if existing:
        prev = str(existing[-1].get("seal", "GENESIS"))
    auth = EngagementAuthorization(
        auth_id="auth_" + uuid.uuid4().hex[:10],
        client=client.strip(),
        authorized_contact=authorized_contact.strip(),
        contact_role=contact_role.strip(),
        scope_assets=assets,
        testing_windows=windows,
        permitted_categories=cats,
        exclusions=[e.strip() for e in (exclusions or []) if e.strip()],
        authorized_by=authorized_by.strip(),
        granted_at=_utcnow(),
        expires_at=exp.isoformat(),
    )
    record = auth.to_dict()
    record.pop("seal")
    auth.seal = _seal(record, prev)
    with _store_path(home).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({**record, "seal": auth.seal}, sort_keys=True) + "\n")
    return auth


def get_authorization(auth_id: str, home: Optional[Path] = None) -> Optional[EngagementAuthorization]:
    for raw in _load_all(home):
        if raw.get("auth_id") == auth_id:
            data = dict(raw)
            data.pop("seal", None)
            auth = EngagementAuthorization(**data)
            auth.seal = str(raw.get("seal", ""))
            return auth
    return None


def require_authorization(auth_id: str, home: Optional[Path] = None) -> EngagementAuthorization:
    """Hard gate: return the authorization or refuse."""
    if not auth_id or not auth_id.strip():
        raise AuthorizationError(
            "no authorization supplied — this service never runs unauthorized"
        )
    auth = get_authorization(auth_id.strip(), home)
    if auth is None:
        raise AuthorizationError(f"unknown authorization {auth_id!r}")
    if auth.expired():
        raise AuthorizationError(
            f"authorization {auth.auth_id} expired {auth.expires_at} — "
            "renew written authorization before any further work"
        )
    return auth


def assert_in_scope(auth: EngagementAuthorization, target: str) -> str:
    """Refuse any target outside the authorized asset scope."""
    t = (target or "").strip().lower()
    if not t:
        raise ScopeViolation("empty target is never in scope")
    for asset in auth.scope_assets:
        if t == asset or t.endswith("." + asset):
            return t
    raise ScopeViolation(
        f"target {target!r} is outside the authorized scope "
        f"{auth.scope_assets} — scope violations are rejected, not warned"
    )

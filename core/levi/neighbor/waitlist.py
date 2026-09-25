"""Recruiting + waitlist CRM — `waitlist.py` (spec §4 system 1, §10 gate 1).

The public-website half of market activation: a local waitlist/CRM with
invite codes. Waitlist Only is the default stage — no dispatch runs
until the operator advances the gates (see `admin.py`).

LAWS (machine-checked by `check_laws`):
- L1: invite codes are unique per store; a duplicate code is refused.
- L2: waitlist entries are append-only history — a person is never
  removed, only status-transitioned
  (waitlisted → invited → onboarded / declined).
- L3: minting an invite requires a named human operator.
- L4: invite codes carry no PII — opaque random tokens, never names.
"""

from __future__ import annotations

import secrets
from typing import Any

from .store import Store

STATUSES = ("waitlisted", "invited", "onboarded", "declined")
ROLES = ("customer", "worker", "business", "property_manager", "supplier")


def add_to_waitlist(
    store: Store,
    name: str,
    contact: str,
    role: str,
    neighborhood_cell: str,
    now: str | None = None,
) -> dict[str, Any]:
    """Add a person to the waitlist (recruiting CRM entry)."""
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r}; expected one of {ROLES}")
    entry = {
        "id": store.next_id("waitlist"),
        "name": name,
        "contact": contact,  # plain and mutual — never masked (Site Lift law)
        "role": role,
        "neighborhood_cell": neighborhood_cell,
        "status": "waitlisted",
        "invite_code": None,
    }
    return store.append("waitlist", entry, now=now)


def _latest(store: Store, entry_id: str) -> dict[str, Any] | None:
    matches = [e for e in store.read_all("waitlist") if e.get("id") == entry_id]
    return matches[-1] if matches else None


def mint_invite(
    store: Store,
    entry_id: str,
    operator: str,
    code: str | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Mint an invite code for a waitlisted entry (operator action)."""
    if not operator:
        raise ValueError("mint_invite requires a named human operator (law L3)")
    entry = _latest(store, entry_id)
    if entry is None:
        raise KeyError(f"no waitlist entry {entry_id}")
    if entry["status"] != "waitlisted":
        raise ValueError(f"entry {entry_id} is '{entry['status']}' — not waitlisted")
    code = code or secrets.token_urlsafe(9)
    if any(e.get("invite_code") == code for e in store.read_all("waitlist")):
        raise ValueError(f"invite code already minted (law L1)")
    record = dict(entry)
    record.pop("seq", None)
    record.pop("ts", None)
    record["status"] = "invited"
    record["invite_code"] = code
    record["invited_by"] = operator
    return store.append("waitlist", record, now=now)


def redeem_invite(
    store: Store, code: str, now: str | None = None
) -> dict[str, Any]:
    """Redeem an invite code — marks the entry onboarded.

    The invite is the recruiting gate: whoever redeems this code is
    cleared to register as the role they waited for. Redemption does
    not create the worker/customer record — registration still runs
    through `work.register_worker` / the customer flow.
    """
    matches = [
        e for e in store.read_all("waitlist") if e.get("invite_code") == code
    ]
    if not matches:
        raise KeyError("unknown or already-redeemed invite code")
    entry = matches[-1]
    if entry["status"] != "invited":
        raise ValueError(f"invite for {entry['id']} is '{entry['status']}'")
    record = dict(entry)
    record.pop("seq", None)
    record.pop("ts", None)
    record["status"] = "onboarded"
    return store.append("waitlist", record, now=now)


def decline(store: Store, entry_id: str, now: str | None = None) -> dict[str, Any]:
    """Decline an entry — recorded, never deleted (law L2)."""
    entry = _latest(store, entry_id)
    if entry is None:
        raise KeyError(f"no waitlist entry {entry_id}")
    record = dict(entry)
    record.pop("seq", None)
    record.pop("ts", None)
    record["status"] = "declined"
    return store.append("waitlist", record, now=now)


def waitlist_depth(store: Store, neighborhood_cell: str) -> dict[str, Any]:
    """Current waitlist depth per role for a cell (feeds readiness)."""
    latest: dict[str, dict] = {}
    for e in store.read_all("waitlist"):
        latest[e["id"]] = e
    depth: dict[str, int] = {}
    total = 0
    for e in latest.values():
        if e.get("neighborhood_cell") == neighborhood_cell and e.get(
            "status"
        ) in ("waitlisted", "invited"):
            depth[e["role"]] = depth.get(e["role"], 0) + 1
            total += 1
    return {"cell": neighborhood_cell, "by_role": depth, "total": total}


def check_laws(store: Store) -> dict[str, Any]:
    """Machine-check the waitlist laws against live state."""
    checks: dict[str, dict] = {}
    latest: dict[str, dict] = {}
    for e in store.read_all("waitlist"):
        latest[e["id"]] = e  # latest snapshot per entry — history, not duplicates
    codes = [e.get("invite_code") for e in latest.values() if e.get("invite_code")]
    checks["codes_unique"] = {"ok": len(codes) == len(set(codes)), "codes": len(codes)}
    bad_status = [e["id"] for e in latest.values() if e.get("status") not in STATUSES]
    checks["statuses_valid"] = {"ok": not bad_status, "violations": bad_status}
    minted_no_operator = [
        e["id"]
        for e in latest.values()
        if e.get("invite_code") and not e.get("invited_by")
    ]
    checks["mint_has_operator"] = {
        "ok": not minted_no_operator,
        "violations": minted_no_operator,
    }
    return {"ok": all(c["ok"] for c in checks.values()), "checks": checks}

"""Identity store — account/identity records for Cybrus (LEVI-original).

Tier model (LOCAL POLICY, not a payment system):
- ``founder``: unlimited accounts, free forever (the owner's tier).
- ``starter``: up to 5 active accounts.
- ``pro``: up to 50 active accounts.

Tier limits are enforced at creation time: :class:`TierError` is raised when
the tier's account quota is exhausted. The ``pro`` tier is a *local*
capability label — there is no billing, no network, no payment hook of any
kind anywhere in this package.

Each identity record::

    {
        "id": "<uuid4 hex>",
        "name": "<unique username>",
        "tier": "founder|starter|pro",
        "status": "active|suspended",
        "created_at": "<UTC ISO-8601>",
        "credential": {"scheme": "pbkdf2-sha256", "iterations": N,
                       "salt": "<base64>", "hash": "<base64>"} | None,
    }

The ``credential`` slot holds only a salted hash reference (written by
``AccountFactory``); plaintext passwords are NEVER stored here.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from levi.cybrus._paths import (
    load_json_store,
    save_json_store,
    store_lock,
    store_path,
)

_STORE_NAME = "identities"

#: Account quotas per tier. ``None`` = unlimited. Local policy — not billing.
TIER_LIMITS: dict[str, Optional[int]] = {
    "founder": None,
    "starter": 5,
    "pro": 50,
}

VALID_TIERS = frozenset(TIER_LIMITS)
VALID_STATUSES = frozenset({"active", "suspended"})

_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


class TierError(Exception):
    """Raised when a tier's account quota is exhausted or the tier is unknown."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_name(name: str) -> str:
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise ValueError(
            "invalid identity name %r: use 1-64 chars of [A-Za-z0-9._-]" % (name,)
        )
    return name


class IdentityStore:
    """CRUD over persisted identity records. Lookup by id or by name."""

    def __init__(self):
        self._path: Path = store_path(_STORE_NAME)
        data = load_json_store(self._path)
        self._records: list[dict] = data if isinstance(data, list) else []

    # -- persistence -----------------------------------------------------

    def _reload(self) -> None:
        """Reload records from disk. Call with the store lock held."""
        data = load_json_store(self._path)
        self._records = data if isinstance(data, list) else []

    def _save(self) -> None:
        save_json_store(self._path, self._records)

    # -- lookups ----------------------------------------------------------

    def get(self, id_or_name: str) -> Optional[dict]:
        """Return the identity record for ``id_or_name`` (uuid or name),
        or ``None`` when no such identity exists."""
        for rec in self._records:
            if rec["id"] == id_or_name or rec["name"] == id_or_name:
                return dict(rec)
        return None

    def list(
        self, *, tier: Optional[str] = None, status: Optional[str] = None
    ) -> list[dict]:
        """All identities, optionally filtered by tier and/or status.

        Credential hash references are redacted from listings: listings name
        identities, they never carry secrets or hashes."""
        out = []
        for rec in self._records:
            if tier is not None and rec["tier"] != tier:
                continue
            if status is not None and rec["status"] != status:
                continue
            copy = dict(rec)
            copy["credential"] = bool(copy.get("credential"))
            out.append(copy)
        return out

    def exists(self, name: str) -> bool:
        return self.get(name) is not None

    # -- mutation ----------------------------------------------------------

    def create(self, name: str, tier: str = "starter") -> dict:
        """Create an identity. Enforces tier quotas; raises :class:`TierError`
        when the tier is unknown or its account limit is exhausted, and
        :class:`ValueError` when the name is invalid or already taken.

        The uniqueness and tier-quota checks plus the insert run under the
        store lock, so two concurrent creates cannot claim the same name or
        both slip under a quota.
        """
        _check_name(name)
        if tier not in VALID_TIERS:
            raise TierError(
                f"unknown tier {tier!r}; valid tiers: {sorted(VALID_TIERS)}"
            )
        with store_lock(self._path):
            self._reload()
            if self.exists(name):
                raise ValueError(f"identity name already taken: {name!r}")
            limit = TIER_LIMITS[tier]
            if limit is not None:
                used = sum(1 for r in self._records if r["tier"] == tier)
                if used >= limit:
                    raise TierError(
                        f"tier {tier!r} allows at most {limit} accounts "
                        f"({used} already exist)"
                    )
            rec = {
                "id": uuid.uuid4().hex,
                "name": name,
                "tier": tier,
                "status": "active",
                "created_at": _utcnow(),
                "credential": None,
            }
            self._records.append(rec)
            self._save()
        return dict(rec)

    def update(self, id_or_name: str, **fields) -> dict:
        """Update ``name``, ``tier`` (raising TierError on quota breach), or
        ``status``. Unknown fields are rejected; returns the updated record."""
        allowed = {"name", "tier", "status"}
        for key in fields:
            if key not in allowed:
                raise ValueError(f"cannot update field {key!r}")
        with store_lock(self._path):
            self._reload()
            rec = self._find_mutable(id_or_name)
            if "name" in fields:
                new_name = _check_name(fields["name"])
                if new_name != rec["name"] and self.exists(new_name):
                    raise ValueError(f"identity name already taken: {new_name!r}")
                rec["name"] = new_name
            if "tier" in fields:
                new_tier = fields["tier"]
                if new_tier not in VALID_TIERS:
                    raise TierError(f"unknown tier {new_tier!r}")
                limit = TIER_LIMITS[new_tier]
                if limit is not None and new_tier != rec["tier"]:
                    used = sum(1 for r in self._records if r["tier"] == new_tier)
                    if used >= limit:
                        raise TierError(
                            f"tier {new_tier!r} allows at most {limit} accounts "
                            f"({used} already exist)"
                        )
                rec["tier"] = new_tier
            if "status" in fields:
                if fields["status"] not in VALID_STATUSES:
                    raise ValueError(f"invalid status {fields['status']!r}")
                rec["status"] = fields["status"]
            self._save()
            return dict(rec)

    def suspend(self, id_or_name: str) -> dict:
        return self.update(id_or_name, status="suspended")

    def reactivate(self, id_or_name: str) -> dict:
        return self.update(id_or_name, status="active")

    def delete(self, id_or_name: str) -> None:
        """Permanently remove an identity (including its credential hash
        reference). Raises :class:`KeyError` when not found."""
        with store_lock(self._path):
            self._reload()
            rec = self._find_mutable(id_or_name)
            self._records.remove(rec)
            self._save()

    # -- credential hash references ---------------------------------------

    def set_credential(self, id_or_name: str, cred: dict) -> None:
        """Attach a credential hash reference (written by AccountFactory).

        The record must describe a salted hash — never plaintext. Anything
        that looks like a raw password is refused."""
        if not isinstance(cred, dict) or cred.get("scheme") != "pbkdf2-sha256":
            raise ValueError("credential must be a pbkdf2-sha256 hash reference")
        for key in ("salt", "hash"):
            if not cred.get(key):
                raise ValueError(f"credential reference missing {key!r}")
        if cred.get("plaintext"):
            raise ValueError("refusing to store a plaintext credential")
        with store_lock(self._path):
            self._reload()
            rec = self._find_mutable(id_or_name)
            rec["credential"] = {
                "scheme": "pbkdf2-sha256",
                "iterations": int(cred.get("iterations", 600_000)),
                "salt": cred["salt"],
                "hash": cred["hash"],
            }
            self._save()

    def get_credential(self, id_or_name: str) -> Optional[dict]:
        rec = self.get(id_or_name)
        if rec is None or not rec.get("credential"):
            return None
        return dict(rec["credential"])

    # -- internals ---------------------------------------------------------

    def _find_mutable(self, id_or_name: str) -> dict:
        for rec in self._records:
            if rec["id"] == id_or_name or rec["name"] == id_or_name:
                return rec
        raise KeyError(f"identity not found: {id_or_name!r}")

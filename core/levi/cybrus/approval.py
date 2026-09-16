"""Cybrus approval engine — the human-in-the-loop gate.

Flow: :meth:`request_approval` creates a ``pending`` entry; a human runs
``levi cybrus approve <id>`` (or ``deny``); :meth:`check` returns True only
when the entry's status is ``approved``. High-risk actions are blocked
until that happens — there is no programmatic way to skip the gate.

Pending entries expire after ``DEFAULT_TTL_SECONDS`` (24h); expiry is
applied lazily on every operation (``_sweep``) so no background process is
needed. Expired pendings can never be approved — a fresh request is
required.

Entries persist as JSON under ``~/.levi/cybrus/approvals.json``
(``LEVI_HOME`` override honored) via the shared ``_paths`` helpers.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

#: Pending approvals older than this are auto-expired (24 hours).
DEFAULT_TTL_SECONDS = 24 * 3600

#: Risks that must pass through the approval gate before execution.
GATED_RISKS = ("high", "critical")

_STORE_NAME = "approvals"


def _paths():  # noqa: D103 - private helper, see policy.py for rationale
    try:
        from levi.cybrus import _paths as _p

        return _p
    except ImportError:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "levi.cybrus._paths.standalone",
            Path(__file__).resolve().parent / "_paths.py",
        )
        if spec is None or spec.loader is None:  # pragma: no cover
            raise ImportError("cybrus _paths helper unavailable") from None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


class ApprovalEngine:
    """HITL approval ledger: request → (approve | deny | expire)."""

    def __init__(self) -> None:
        p = _paths()
        self._path: Path = p.store_path(_STORE_NAME)
        self._entries: List[Dict] = []
        with p.store_lock(self._path):
            self._reload()
            self._sweep_unlocked()

    # -- persistence -----------------------------------------------------

    def _reload(self) -> None:
        """Reload entries from disk. Call with the store lock held."""
        data = _paths().load_json_store(self._path)
        self._entries = data if isinstance(data, list) else []

    def _save(self) -> None:
        _paths().save_json_store(self._path, self._entries)

    # -- expiry ----------------------------------------------------------

    def _sweep_unlocked(self) -> None:
        """Auto-expire stale pendings. Call with the store lock held (it
        may persist); every public operation sweeps first so no background
        process is needed."""
        now = _utcnow()
        changed = False
        for entry in self._entries:
            if entry.get("status") != "pending":
                continue
            try:
                expires = datetime.fromisoformat(entry["expires_at"])
            except (KeyError, ValueError, TypeError):
                expires = now  # unparseable expiry → treat as expired
            if expires <= now:
                entry["status"] = "expired"
                changed = True
        if changed:
            self._save()

    # -- lookup ----------------------------------------------------------

    def _resolve(self, approval_id: str) -> Dict:
        """Find an entry by full id or unique id-prefix. Raises
        :class:`KeyError` when unknown, :class:`ValueError` when the prefix
        is ambiguous."""
        for entry in self._entries:
            if entry["id"] == approval_id:
                return entry
        matches = [
            entry for entry in self._entries if entry["id"].startswith(approval_id)
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(
                f"ambiguous approval id prefix {approval_id!r}: "
                f"{len(matches)} entries match"
            )
        raise KeyError(f"unknown approval id: {approval_id!r}")

    # -- the gate --------------------------------------------------------

    def request_approval(
        self,
        action: str,
        subject: str,
        resource: str,
        risk: str,
        details: Optional[Dict] = None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> Dict:
        """Create a ``pending`` approval entry. Returns the entry."""
        if risk not in GATED_RISKS + ("low", "medium"):
            raise ValueError(f"unknown risk level {risk!r}")
        now = _utcnow()
        expires = datetime.fromtimestamp(
            now.timestamp() + ttl_seconds, tz=timezone.utc
        )
        entry = {
            "id": uuid.uuid4().hex,
            "action": action,
            "subject": subject,
            "resource": resource,
            "risk": risk,
            "details": dict(details or {}),
            "status": "pending",
            "created_at": _iso(now),
            "expires_at": _iso(expires),
            "decided_at": None,
            "decided_by": None,
            "reason": "",
        }
        p = _paths()
        with p.store_lock(self._path):
            self._reload()
            self._entries.append(entry)
            self._save()
        return dict(entry)

    def approve(self, approval_id: str, by: str = "owner") -> Dict:
        """Approve a pending entry. Raises :class:`ValueError` when the
        entry is not pending (denied / expired entries can never be
        approved — request a fresh one).

        The decide-and-persist runs under the store lock with a fresh
        reload, so two concurrent approvers cannot interleave.
        """
        p = _paths()
        with p.store_lock(self._path):
            self._reload()
            self._sweep_unlocked()
            entry = self._resolve(approval_id)
            if entry["status"] != "pending":
                raise ValueError(
                    f"cannot approve entry {entry['id'][:8]}: "
                    f"status is {entry['status']!r}, not 'pending'"
                )
            entry["status"] = "approved"
            entry["decided_at"] = _iso(_utcnow())
            entry["decided_by"] = by
            self._save()
            return dict(entry)

    def deny(self, approval_id: str, reason: str = "", by: str = "owner") -> Dict:
        """Deny a pending entry. Denied entries stay blocked; a fresh
        request is required to retry."""
        p = _paths()
        with p.store_lock(self._path):
            self._reload()
            self._sweep_unlocked()
            entry = self._resolve(approval_id)
            if entry["status"] != "pending":
                raise ValueError(
                    f"cannot deny entry {entry['id'][:8]}: "
                    f"status is {entry['status']!r}, not 'pending'"
                )
            entry["status"] = "denied"
            entry["decided_at"] = _iso(_utcnow())
            entry["decided_by"] = by
            entry["reason"] = reason
            self._save()
            return dict(entry)

    def check(self, approval_id: str) -> bool:
        """The gate predicate: True **only** when the entry exists and its
        status is ``approved``. Pending, denied, and expired entries all
        return False — high-risk actions stay blocked.

        NOTE: this reports approval, not single-use consumption. Callers
        that must consume an approval exactly once (the gateway's
        ``authorize_execution`` / ``route_external``) use
        :meth:`consume_approved`, which matches and marks consumed
        atomically — ``check`` followed by a separate ``annotate`` would
        race under concurrency.
        """
        p = _paths()
        with p.store_lock(self._path):
            self._reload()
            self._sweep_unlocked()
            try:
                entry = self._resolve(approval_id)
            except (KeyError, ValueError):
                return False
            return entry.get("status") == "approved"

    def gate(
        self, action: str, subject: str, resource: str, risk: str
    ) -> Tuple[bool, Optional[str]]:
        """Convenience for callers: low/medium risk → ``(True, None)``
        (no gate); high/critical → create a pending approval and return
        ``(False, approval_id)``. The caller must then wait for a human to
        approve and re-check with :meth:`check`."""
        if risk in GATED_RISKS:
            entry = self.request_approval(action, subject, resource, risk)
            return False, entry["id"]
        return True, None

    # -- listing ---------------------------------------------------------

    def pending(self) -> List[Dict]:
        """All currently pending (non-expired) entries, oldest first."""
        p = _paths()
        with p.store_lock(self._path):
            self._reload()
            self._sweep_unlocked()
            return [
                dict(e)
                for e in sorted(self._entries, key=lambda e: e["created_at"])
                if e.get("status") == "pending"
            ]

    def list_all(self) -> List[Dict]:
        """Every entry, newest first (history view)."""
        p = _paths()
        with p.store_lock(self._path):
            self._reload()
            self._sweep_unlocked()
            return [
                dict(e)
                for e in sorted(
                    self._entries, key=lambda e: e["created_at"], reverse=True
                )
            ]

    def annotate(self, approval_id: str, **fields) -> Dict:
        """Merge *fields* into an entry's ``details`` dict and persist.

        Used by the gateway to mark an approval consumed (single-use
        grants): e.g. ``annotate(id, consumed_at=..., grant_id=...)``.
        Raises :class:`KeyError` when the id is unknown.
        """
        p = _paths()
        with p.store_lock(self._path):
            self._reload()
            entry = self._resolve(approval_id)
            details = entry.get("details")
            if not isinstance(details, dict):
                details = {}
                entry["details"] = details
            details.update(fields)
            self._save()
            return dict(entry)

    def consume_approved(self, action: str,
                         details: Optional[Dict] = None) -> Optional[Dict]:
        """Atomically find an ``approved``, unconsumed entry matching
        ``action`` and ``details`` and mark it consumed.

        Returns the entry (now carrying ``consumed_at``) or ``None`` when
        no such entry exists. The match-and-mark happens under the store
        lock with a fresh reload, so two concurrent consumers cannot both
        win the same approval — single-use is enforced even across
        processes. This is the primitive the gateway uses for
        ``authorize_execution`` and ``route_external``; a ``check()`` +
        separate ``annotate()`` sequence would race.
        """
        wanted = dict(details or {})
        p = _paths()
        with p.store_lock(self._path):
            self._reload()
            self._sweep_unlocked()
            for entry in self._entries:
                if entry.get("action") != action:
                    continue
                if entry.get("status") != "approved":
                    continue
                entry_details = entry.get("details")
                if not isinstance(entry_details, dict):
                    continue
                if not all(entry_details.get(k) == v for k, v in wanted.items()):
                    continue
                if entry_details.get("consumed_at"):
                    continue  # single-use: already consumed
                entry_details["consumed_at"] = _iso(_utcnow())
                self._save()
                return dict(entry)
        return None

"""Cybrus LEFT-GUARD — the watchful layer over the device trust registry.

The registry (``devices.py``) stores facts; this guard enforces the
ceremony. Chauncey's mandate: his phone + Chromebook trust registry,
new or unknown device = alert, trust that decays.

LAWS (L8: declared first, enforced by this module, machine-checked by
``tests/test_cybrus_device_guard.py``):

- I1 (L1/L3): an unknown device NEVER executes a device-bound privileged
  call. First sighting auto-enrolls it at ``untrusted`` AND raises an
  alert (a pending ``device.trust_grant`` approval + audit receipts).
- I2 (L5): trust PROMOTION consumes a single-use, human-approved
  ``device.trust_grant`` approval bound to ``{"device_id", "level"}``.
  No approval, no promotion — silently calling ``set_trust`` up raises
  ``TrustGrantError`` and the level does not move.
- I3 (L5): approvals are single-use. A replayed approval id promotes
  nothing.
- I4 (L1/L4/L12): every enrollment, trust request, grant, denial,
  challenge, decay, and revocation leaves an audit receipt carrying
  metadata only — never raw fingerprints.
- I5 (L10): trust DECAYS with staleness, never silently: a sweep demotes
  stale devices one rank per stale tier and receipts each demotion.
- I6 (anti-spoofing): a presented fingerprint that does not match the
  bound one demotes the device to ``untrusted`` and re-raises the alert.
- I7 (L3): demotion is never gated — fail-closed is always available.
- I8 (L5): expired (or denied) approvals grant nothing.

Decay policy: ``STALE_DEMOTE_1_DAYS`` (30) trusted→known,
``STALE_DEMOTE_2_DAYS`` (60) known→untrusted. Revocation is manual-only —
the guard never locks Chauncey out by deleting his phone for him; it
demotes and alerts, he decides.

This module never touches another organ's state (L9), never blocks on a
human — every method fails fast and names the resumable approval id
(L11) — and every refusal names its remedy (L6).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from levi.cybrus.approval import ApprovalEngine
from levi.cybrus.audit import AuditEngine
from levi.cybrus.devices import (
    DEVICE_TRUST_GRANT_ACTION,
    TRUST_LEVELS,
    DeviceTrust,
    TrustGrantError,
)

#: Staleness tiers for trust decay (days since last_seen).
STALE_DEMOTE_1_DAYS = 30  #: trusted -> known
STALE_DEMOTE_2_DAYS = 60  #: known -> untrusted

GUARD_ACTOR = "cybrus.left-guard"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class DeviceGuard:
    """Watchfulness over the device trust registry."""

    def __init__(
        self,
        trust: Optional[DeviceTrust] = None,
        approvals: Optional[ApprovalEngine] = None,
        audit: Optional[AuditEngine] = None,
    ) -> None:
        self.trust = trust or DeviceTrust()
        self.approvals = approvals or ApprovalEngine()
        self.audit = audit or AuditEngine()

    # -- first sighting: enroll + alert -----------------------------------

    def sighting(
        self,
        device_id: str,
        name: str,
        *,
        fingerprint: Optional[str] = None,
        level: str = "known",
    ) -> Tuple[Dict, str]:
        """An unknown (or untrusted) device showed up.

        Enrolls it at ``untrusted`` when new (fingerprint bound on first
        use), audits ``device.sighted``, and raises the alert: a pending
        ``device.trust_grant`` approval for *level* (reusing an existing
        pending one for the same device/level instead of spamming new
        ones). Returns ``(record, approval_id)`` — fail fast, never
        blocking (L11).

        The device stays ``untrusted`` until a human approves the
        approval and the promotion consumes it (I1/I2).
        """
        device_id = (device_id or "").strip()
        if not device_id:
            raise ValueError("device_id must be a non-empty string")
        record = self.trust.get(device_id)
        if record is None:
            record = self.trust.enroll(device_id, name, fingerprint=fingerprint)
            self.audit.append(
                "device.sighted",
                GUARD_ACTOR,
                {
                    "device_id": device_id,
                    "name": name,
                    "fingerprint_bound": bool(fingerprint),
                },
            )
        else:
            self.trust.touch(device_id)
        approval_id = self.request_trust(device_id, level)
        return self.trust.get(device_id) or record, approval_id

    def request_trust(self, device_id: str, level: str = "known") -> str:
        """Raise (or reuse) a pending ``device.trust_grant`` approval for
        *device_id* → *level*. Audits ``device.trust_requested``. Returns
        the approval id."""
        if level not in TRUST_LEVELS:
            raise ValueError(f"unknown trust level {level!r}")
        existing = self._pending_grant(device_id, level)
        if existing is not None:
            return existing["id"]
        entry = self.approvals.request_approval(
            DEVICE_TRUST_GRANT_ACTION,
            device_id,
            f"device:{device_id}",
            "high",
            # RED-1 exact-match law: the approval's details must be
            # EXACTLY what DeviceTrust.set_trust presents at consume
            # time ({"device_id", "level"}) — no extra keys, or the
            # approved ceremony can never complete. Human context
            # (the device name) rides in the audit record below, not
            # in the match-critical details.
            details={
                "device_id": device_id,
                "level": level,
            },
        )
        self.audit.append(
            "device.trust_requested",
            GUARD_ACTOR,
            {
                "device_id": device_id,
                "level": level,
                "approval_id": entry["id"][:8],
                "name": (self.trust.get(device_id) or {}).get("name", ""),
            },
        )
        return entry["id"]

    def _pending_grant(
        self, device_id: str, level: Optional[str] = None
    ) -> Optional[Dict]:
        for entry in self.approvals.pending():
            if entry.get("action") != DEVICE_TRUST_GRANT_ACTION:
                continue
            details = entry.get("details") or {}
            if details.get("device_id") != device_id:
                continue
            if level is not None and details.get("level") != level:
                continue
            return entry
        return None

    # -- the human gate ----------------------------------------------------

    def grant(self, device_id: str, level: str, approval_id: str) -> Dict:
        """Promote *device_id* to *level* on a human-approved approval.

        The approval must be approved (``levi cybrus approve <id>`` first);
        the promotion consumes it single-use inside
        :meth:`DeviceTrust.set_trust`. Replays, expired entries, and
        mismatched device/level all raise :class:`TrustGrantError` (I2/I3/I8).

        Demotions (rank decrease) never need an approval — fail-closed is
        never gated (I7).
        """
        current = (self.trust.get(device_id) or {}).get("trust", "untrusted")
        rank = {"untrusted": 0, "known": 1, "trusted": 2}
        if rank.get(level, 0) <= rank.get(current, 0):
            return self.trust.set_trust(device_id, level)
        if not self.approvals.check(approval_id):
            raise TrustGrantError(
                f"approval {approval_id[:8]} is not in approved state "
                "(pending, denied, or expired) — have a human approve it "
                "first, then retry."
            )
        return self.trust.set_trust(device_id, level)

    def deny(self, device_id: str, approval_id: str, reason: str = "") -> Dict:
        """Deny a pending trust grant for *device_id*. The device stays
        untrusted; the denial is audited."""
        entry = self.approvals.deny(approval_id, reason=reason)
        self.audit.append(
            "device.trust_denied",
            GUARD_ACTOR,
            {
                "device_id": device_id,
                "approval_id": approval_id[:8],
                "reason": reason,
            },
        )
        return entry

    # -- heartbeat / spoofing ----------------------------------------------

    def seen(
        self, device_id: str, *, fingerprint: Optional[str] = None
    ) -> Dict:
        """Device heartbeat. Refreshes ``last_seen``.

        When the device has a bound fingerprint and the presented one does
        NOT match, the device is demoted to ``untrusted`` immediately, the
        alert is re-raised, and ``device.fingerprint_mismatch`` is audited
        (I6). When no fingerprint is bound yet and one is presented, it is
        bound (trust on first use) and audited."""
        record = self.trust.touch(device_id)
        if record is None:
            raise KeyError(f"unknown device: {device_id!r}")
        if fingerprint:
            verdict = self.trust.fingerprint_matches(device_id, fingerprint)
            if verdict is False:
                self.trust.set_trust(device_id, "untrusted")
                approval_id = self.request_trust(device_id, "known")
                self.audit.append(
                    "device.fingerprint_mismatch",
                    GUARD_ACTOR,
                    {
                        "device_id": device_id,
                        "action": "demoted to untrusted; re-approval raised",
                        "approval_id": approval_id[:8],
                    },
                )
                return {
                    "device_id": device_id,
                    "status": "spoof_suspect",
                    "trust": "untrusted",
                    "approval_id": approval_id,
                }
            if verdict is None:
                self.trust.bind_fingerprint(device_id, fingerprint)
                self.audit.append(
                    "device.fingerprint_bound",
                    GUARD_ACTOR,
                    {"device_id": device_id},
                )
                return {"device_id": device_id, "status": "bound", "trust": record["trust"]}
        return {"device_id": device_id, "status": "seen", "trust": record["trust"]}

    def challenge(self, device_id: str, reason: str = "") -> Dict:
        """Challenge a device: demote to ``untrusted`` NOW (fail-closed,
        never gated — I7), audit ``device.challenged``, and re-raise the
        approval alert. Returns the new record + approval id."""
        record = self.trust.get(device_id)
        if record is None:
            raise KeyError(f"unknown device: {device_id!r}")
        self.trust.set_trust(device_id, "untrusted")
        approval_id = self.request_trust(device_id, "known")
        self.audit.append(
            "device.challenged",
            GUARD_ACTOR,
            {
                "device_id": device_id,
                "reason": reason,
                "approval_id": approval_id[:8],
            },
        )
        return {
            "record": self.trust.get(device_id),
            "approval_id": approval_id,
        }

    # -- trust decay --------------------------------------------------------

    def sweep_decay(self, now: Optional[datetime] = None) -> List[Dict]:
        """Demote stale devices, one rank per stale tier, with a receipt
        for each demotion (I5). ``trusted`` unseen for 30d → ``known``;
        ``known`` unseen for 60d → ``untrusted``. Revocation is manual-only
        (the guard never deletes Chauncey's phone for him).

        Returns the list of demotion receipts."""
        now = now or _utcnow()
        receipts: List[Dict] = []
        self.trust.refresh()  # read the latest heartbeats, not a stale cache
        for record in self.trust.list():
            last_seen = _parse_ts(record.get("last_seen"))
            if last_seen is None:
                continue
            stale_days = (now - last_seen).total_seconds() / 86400
            current = record.get("trust")
            target = None
            if current == "trusted" and stale_days >= STALE_DEMOTE_1_DAYS:
                target = "known"
            elif current == "known" and stale_days >= STALE_DEMOTE_2_DAYS:
                target = "untrusted"
            if target is None:
                continue
            self.trust.set_trust(record["id"], target)
            self.audit.append(
                "device.trust_decayed",
                GUARD_ACTOR,
                {
                    "device_id": record["id"],
                    "from": current,
                    "to": target,
                    "stale_days": round(stale_days, 1),
                },
            )
            receipts.append(
                {
                    "device_id": record["id"],
                    "from": current,
                    "to": target,
                    "stale_days": round(stale_days, 1),
                }
            )
        return receipts

    # -- revocation ----------------------------------------------------------

    def revoke(self, device_id: str, reason: str = "") -> bool:
        """Remove a device (sanctioned removal within the device domain).
        Audits ``device.revoked`` with the reason."""
        ok = self.trust.revoke(device_id)
        self.audit.append(
            "device.revoked",
            GUARD_ACTOR,
            {"device_id": device_id, "reason": reason},
        )
        return ok

    # -- registry/audit consistency -------------------------------------------

    def verify_consistency(self) -> List[Dict]:
        """Cross-check the registry against the audit log: every device
        sitting above ``untrusted`` must have a matching
        ``device.trust_granted`` receipt. A device whose trust exceeds
        what the receipts support was promoted outside the ceremony
        (e.g. direct file edit — the registry file is owner-only, but
        the guard assumes the *process* layer is the boundary and
        detects, rather than prevents, file-level tampering).

        Returns the list of inconsistent devices (empty = clean). Any
        inconsistency is audited as ``device.registry_inconsistent``
        (the alert) and returned for the human to rule on.
        """
        rank = {"untrusted": 0, "known": 1, "trusted": 2}
        granted: Dict[str, int] = {}
        for rec in self.audit.tail(100000):
            if rec.get("event") != "device.trust_granted":
                continue
            details = rec.get("details") or {}
            dev = details.get("device_id")
            to = details.get("to")
            if dev and to in rank:
                granted[dev] = max(granted.get(dev, 0), rank[to])
        self.trust.refresh()  # read the registry fresh — stale cache would
        # hide exactly the file-level tampering this check hunts.
        bad: List[Dict] = []
        for record in self.trust.list():
            current = record.get("trust", "untrusted")
            if rank.get(current, 0) > granted.get(record["id"], 0):
                bad.append(
                    {
                        "device_id": record["id"],
                        "trust": current,
                        "granted_to": granted.get(record["id"], 0),
                    }
                )
        if bad:
            self.audit.append(
                "device.registry_inconsistent",
                GUARD_ACTOR,
                {
                    "devices": [
                        {"device_id": b["device_id"], "trust": b["trust"]}
                        for b in bad
                    ],
                    "note": "trust exceeds audit receipts; human ruling required",
                },
            )
        return bad

    # -- reads -----------------------------------------------------------------

    def status(self, device_id: str) -> Optional[Dict]:
        """Public record + staleness + pending-grant info for one device."""
        record = self.trust.public_record(device_id)
        if record is None:
            return None
        last_seen = _parse_ts(record.get("last_seen"))
        record["stale_days"] = (
            round((_utcnow() - last_seen).total_seconds() / 86400, 1)
            if last_seen
            else None
        )
        pending = self._pending_grant(device_id)
        record["pending_approval_id"] = pending["id"] if pending else None
        return record

    def list(self) -> List[Dict]:
        """All devices with staleness, fingerprint material stripped."""
        return [
            self.status(record["id"])
            for record in self.trust.list()
            if self.status(record["id"]) is not None
        ]

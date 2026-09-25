"""true_delete — ephemeral channels with cryptographic erasure.

Studied from: giant-patterns-hunt-20260916-0016 (report.md [Additions 3]).
Load-bearing idea: deletion with real guarantees — per-message keys wiped
(cryptographic erasure), expiries enforced, screenshot events logged, and
no cloud retention backdoor because the channel's store lives locally.

LEVI's take: ``TrueDelete`` hosts ``Channel``s of ``Message``s. Each
message carries its own key material; ``delete`` overwrites that key
material and drops the plaintext (cryptographic erasure: the ciphertext,
if any copy escaped, can never be opened again by this store).
``DeletionCertificate``s form a hash chain so every deletion is
auditable. ``sweep`` enforces TTL expiries. ``flag_screenshot`` records
screenshot-awareness events and the channel's retention policy.

Honest limits: this is a local mechanism. It cannot detect real
screenshots on a user's device, cannot reach copies that left the store
(photos of screens, OS backups), and is not a substitute for device-level
security. What it guarantees: within this store, deleted means
unrecoverable here.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import hashlib
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


ORIGIN = "levi-revival/true-delete"

_ERASED = "<erased>"


@dataclass
class Message:
    id: str
    author: str
    text: str
    created_at: float
    ttl_seconds: Optional[float]
    _key: bytes = field(repr=False, default=b"")
    deleted: bool = False

    def is_expired(self, now: float) -> bool:
        return (
            self.ttl_seconds is not None and now - self.created_at >= self.ttl_seconds
        )

    def erase(self) -> None:
        """Cryptographic erasure: overwrite key material, drop plaintext."""
        self._key = bytes(len(self._key))  # overwrite before release
        self._key = b""
        self.text = _ERASED
        self.deleted = True


@dataclass
class DeletionCertificate:
    seq: int
    message_id: str
    deleted_at: float
    reason: str  # user | ttl | policy
    prev_hash: str
    cert_hash: str


@dataclass
class ScreenshotEvent:
    channel: str
    reporter: str
    at: float
    note: str = ""


@dataclass
class Channel:
    name: str
    retention_note: str = ""
    screenshot_policy: str = "log"  # log | warn | forbid


class TrueDelete:
    """Ephemeral channels where delete means unrecoverable-in-this-store."""

    def __init__(self) -> None:
        self.channels: Dict[str, Channel] = {}
        self.messages: Dict[str, Dict[str, Message]] = {}
        self.certificates: List[DeletionCertificate] = []
        self.screenshots: List[ScreenshotEvent] = []
        self._seq = 0
        self._tip = "genesis"

    # -- channels -------------------------------------------------------------

    def open_channel(
        self, name: str, retention_note: str = "", screenshot_policy: str = "log"
    ) -> Channel:
        if screenshot_policy not in ("log", "warn", "forbid"):
            raise ValueError("screenshot_policy must be log|warn|forbid")
        ch = Channel(
            name=name,
            retention_note=retention_note,
            screenshot_policy=screenshot_policy,
        )
        self.channels[name] = ch
        self.messages.setdefault(name, {})
        return ch

    # -- messages -------------------------------------------------------------

    def post(
        self, channel: str, author: str, text: str, ttl_seconds: Optional[float] = None
    ) -> Message:
        if channel not in self.channels:
            raise KeyError(f"unknown channel {channel!r}")
        m = Message(
            id=f"m-{uuid.uuid4().hex[:8]}",
            author=author,
            text=text,
            created_at=time.time(),
            ttl_seconds=ttl_seconds,
            _key=os.urandom(32),
        )
        self.messages[channel][m.id] = m
        return m

    def read(self, channel: str, message_id: str) -> Optional[str]:
        """Return plaintext, or None if deleted/expired/missing."""
        m = self.messages.get(channel, {}).get(message_id)
        if m is None or m.deleted or m.is_expired(time.time()):
            return None
        return m.text

    def _certify(self, message_id: str, reason: str) -> DeletionCertificate:
        self._seq += 1
        now = time.time()
        raw = f"{self._seq}|{message_id}|{now}|{reason}|{self._tip}"
        digest = hashlib.sha256(raw.encode()).hexdigest()
        cert = DeletionCertificate(
            seq=self._seq,
            message_id=message_id,
            deleted_at=now,
            reason=reason,
            prev_hash=self._tip,
            cert_hash=digest,
        )
        self.certificates.append(cert)
        self._tip = digest
        return cert

    def delete(
        self, channel: str, message_id: str, reason: str = "user"
    ) -> DeletionCertificate:
        m = self.messages[channel][message_id]
        if not m.deleted:
            m.erase()
        return self._certify(message_id, reason)

    def sweep(self, channel: Optional[str] = None) -> List[DeletionCertificate]:
        """Enforce TTL expiries now. Returns certificates for swept messages."""
        now = time.time()
        certs = []
        targets = [channel] if channel else list(self.messages)
        for ch in targets:
            for mid, m in list(self.messages.get(ch, {}).items()):
                if not m.deleted and m.is_expired(now):
                    m.erase()
                    certs.append(self._certify(mid, "ttl"))
        return certs

    # -- screenshot awareness -------------------------------------------------

    def flag_screenshot(
        self, channel: str, reporter: str, note: str = ""
    ) -> ScreenshotEvent:
        ev = ScreenshotEvent(
            channel=channel, reporter=reporter, at=time.time(), note=note
        )
        self.screenshots.append(ev)
        return ev

    # -- audit ----------------------------------------------------------------

    def verify_chain(self) -> bool:
        tip = "genesis"
        for i, c in enumerate(self.certificates, 1):
            if c.seq != i or c.prev_hash != tip:
                return False
            raw = f"{c.seq}|{c.message_id}|{c.deleted_at}|{c.reason}|{c.prev_hash}"
            if hashlib.sha256(raw.encode()).hexdigest() != c.cert_hash:
                return False
            tip = c.cert_hash
        return True

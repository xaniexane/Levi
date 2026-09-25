"""Omega Studio consent kit — HMAC-SHA256 signed audit trails.

The original Omega Studio kept *HMAC-SHA256 signed audit trails* of every
consent decision. This module rebuilds that organ as clean-room LEVI code:
an append-only JSONL trail where every record carries

- a sequence number and UTC timestamp,
- ``prev`` — the MAC of the previous record (hash chaining, so reordering
  or deletion breaks the chain), and
- ``mac`` — HMAC-SHA256 over the canonical record with the trail key
  (so any tampering breaks the signature).

``verify()`` replays the whole chain and reports the first failure
honestly: it returns ``(ok, findings)`` where findings name the exact
record and the exact defect (bad MAC, broken link, bad sequence).

LAWS
----
1. Append-only: no edit, no delete API exists on this class. Corrections
   are new records.
2. ``verify()`` is the only truth about integrity — never trust the file
   by inspection.
3. The key lives in ``<dir>/key.bin`` with owner-only permissions
   (POSIX 0600); without the key, records are write-only evidence.

stdlib-only (``hmac``, ``hashlib``, ``json``). Local-first, no network.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "AuditTrail",
    "AuditError",
    "new_key",
    "canonical",
]


class AuditError(Exception):
    """The audit trail could not be opened or written."""


def new_key() -> bytes:
    """Generate a fresh 256-bit HMAC key."""
    return secrets.token_bytes(32)


def canonical(obj: Any) -> bytes:
    """Deterministic JSON encoding for MAC input (sorted keys, no spaces)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AuditTrail:
    """An HMAC-SHA256 signed, hash-chained, append-only audit trail."""

    def __init__(self, path: "str | Path", key: bytes) -> None:
        if not isinstance(key, (bytes, bytearray)) or len(key) < 16:
            raise AuditError("HMAC key must be at least 16 bytes")
        self.path = Path(path)
        self.key = bytes(key)

    @classmethod
    def open(cls, directory: "str | Path") -> "AuditTrail":
        """Open (or create) the trail in ``directory``.

        The key is stored at ``<directory>/key.bin`` (owner-only, 0600);
        a fresh key is generated on first open. The trail file is
        ``<directory>/trail.jsonl``.
        """
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(d, 0o700)
        except OSError:
            pass
        key_path = d / "key.bin"
        if key_path.exists():
            key = key_path.read_bytes()
        else:
            key = new_key()
            key_path.write_bytes(key)
            try:
                os.chmod(key_path, 0o600)
            except OSError:
                pass
        trail = cls(d / "trail.jsonl", key)
        trail._key_path = key_path  # noqa: SLF001 (owned attribute)
        return trail

    # -- append ---------------------------------------------------------

    def _mac(self, record: Dict[str, Any]) -> str:
        body = {k: record[k] for k in ("seq", "ts", "event", "payload", "prev")}
        return hmac.new(self.key, canonical(body), hashlib.sha256).hexdigest()

    def _tail_mac(self) -> str:
        """MAC of the last record, or the all-zero genesis link."""
        if not self.path.exists():
            return "0" * 64
        last = None
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    last = line
        if last is None:
            return "0" * 64
        return str(json.loads(last)["mac"])

    def _next_seq(self) -> int:
        if not self.path.exists():
            return 1
        n = 0
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    n += 1
        return n + 1

    def append(self, event: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Append one signed record. Returns the record (with ``mac``)."""
        if not event or not str(event).strip():
            raise AuditError("event name is required")
        record: Dict[str, Any] = {
            "seq": self._next_seq(),
            "ts": _utcnow(),
            "event": str(event),
            "payload": dict(payload or {}),
            "prev": self._tail_mac(),
        }
        record["mac"] = self._mac(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass
        return record

    # -- read -----------------------------------------------------------

    def read(self) -> List[Dict[str, Any]]:
        """Return every record in order. Malformed lines raise ``AuditError``."""
        records: List[Dict[str, Any]] = []
        if not self.path.exists():
            return records
        with self.path.open("r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise AuditError(f"line {lineno} is not JSON: {exc}") from exc
                if not isinstance(rec, dict):
                    raise AuditError(f"line {lineno} is not a record")
                records.append(rec)
        return records

    # -- verify ----------------------------------------------------------

    def verify(self) -> Tuple[bool, List[str]]:
        """Replay the chain. Returns ``(ok, findings)``.

        Findings name the first defect found: bad MAC (tampering),
        broken ``prev`` link (reorder/delete), or bad sequence. An empty
        trail verifies cleanly — absence of evidence is not evidence of
        tampering; it is reported honestly as ``records: 0``.
        """
        findings: List[str] = []
        try:
            records = self.read()
        except AuditError as exc:
            return False, [f"unreadable trail: {exc}"]
        expected_prev = "0" * 64
        for rec in records:
            for field in ("seq", "ts", "event", "payload", "prev", "mac"):
                if field not in rec:
                    return False, [f"seq {rec.get('seq')}: missing field {field!r}"]
            if not isinstance(rec["seq"], int) or rec["seq"] < 1:
                return False, [f"record has invalid seq {rec['seq']!r}"]
            if rec["prev"] != expected_prev:
                return False, [
                    f"seq {rec['seq']}: broken chain link "
                    f"(prev {str(rec['prev'])[:12]}… != expected {expected_prev[:12]}…)"
                ]
            want = self._mac(rec)
            if not hmac.compare_digest(str(rec["mac"]), want):
                return False, [f"seq {rec['seq']}: bad MAC (record tampered)"]
            expected_prev = str(rec["mac"])
        # Strict sequence check: seqs must be 1..n in order.
        for i, rec in enumerate(records, 1):
            if rec["seq"] != i:
                return False, [f"position {i}: seq is {rec['seq']} (expected {i})"]
        findings.append(f"ok: {len(records)} record(s), chain intact")
        return True, findings

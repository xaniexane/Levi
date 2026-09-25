"""MOOD receipts — hash-chained evidence for every trip (L3, L7).

Each receipt commits the previous chain head::

    hash = sha256(prev | seq | session_id | kind | canonical(detail))

The chain starts at a fixed genesis head, so the very first receipt is
verifiable too. Records are append-only JSONL under the caller-supplied
home (``~/.levi/mood/receipts.jsonl``), files mode 0600. Every receipt
carries the MOOD tag (L7).

``verify()`` walks the chain and reports the first broken link. A single
altered byte breaks the chain — tampering is detectable, not preventable
(honest limit, stated here).
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from levi.mood.laws import ZONE

__all__ = [
    "GENESIS_HEAD",
    "Receipt",
    "ReceiptWriter",
    "mood_dir",
]

#: Fixed genesis head — the chain's trust anchor.
GENESIS_HEAD = "mood-genesis-" + "0" * 56

_RECORD_MODE = 0o600


def mood_dir(home: Path) -> Path:
    """``~/.levi/mood`` under the caller-supplied home."""
    return Path(home) / ".levi" / ZONE


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canonical(detail: Dict[str, Any]) -> str:
    return json.dumps(detail, sort_keys=True, separators=(",", ":"))


def _receipt_hash(
    prev: str, seq: int, session_id: str, kind: str, detail: Dict[str, Any]
) -> str:
    body = "%s|%d|%s|%s|%s" % (prev, seq, session_id, kind, _canonical(detail))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass
class Receipt:
    seq: int
    ts: str
    session_id: str
    kind: str
    detail: Dict[str, Any]
    prev: str
    hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone": ZONE,
            "mood": True,
            "seq": self.seq,
            "ts": self.ts,
            "session_id": self.session_id,
            "kind": self.kind,
            "detail": self.detail,
            "prev": self.prev,
            "hash": self.hash,
        }


class ReceiptWriter:
    """Append-only hash-chained receipt log (L3)."""

    def __init__(self, home: Path) -> None:
        self._path = mood_dir(home) / "receipts.jsonl"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text("", encoding="utf-8")
            os.chmod(self._path, _RECORD_MODE)
        self._head = self._load_head()

    # ------------------------------------------------------------------
    # Writing — every trip and escalation lands here (L3).
    # ------------------------------------------------------------------

    def write(
        self,
        session_id: str,
        kind: str,
        detail: Dict[str, Any],
        ts: Optional[str] = None,
    ) -> Receipt:
        """Append one receipt chaining the current head; return it."""
        seq = self._count()
        receipt = Receipt(
            seq=seq,
            ts=ts or _utcnow(),
            session_id=session_id,
            kind=kind,
            detail=dict(detail),
            prev=self._head,
            hash="",
        )
        receipt.hash = _receipt_hash(
            receipt.prev, receipt.seq, receipt.session_id, receipt.kind,
            receipt.detail,
        )
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt.to_dict()) + "\n")
        os.chmod(self._path, _RECORD_MODE)
        self._head = receipt.hash
        return receipt

    # ------------------------------------------------------------------
    # Verification — tampering breaks the chain (honest limit in docstring).
    # ------------------------------------------------------------------

    def verify(self) -> Tuple[bool, str]:
        """Walk the chain; return (ok, message)."""
        prev = GENESIS_HEAD
        for index, record in enumerate(self._iter()):
            if record["prev"] != prev:
                return False, "broken link at seq %d: prev mismatch" % index
            expected = _receipt_hash(
                record["prev"], record["seq"], record["session_id"],
                record["kind"], record["detail"],
            )
            if record["hash"] != expected:
                return False, "broken link at seq %d: hash mismatch" % index
            prev = record["hash"]
        return True, "chain ok (%d receipts)" % self._count()

    @property
    def head(self) -> str:
        return self._head

    @property
    def path(self) -> Path:
        return self._path

    def _iter(self) -> Iterator[Dict[str, Any]]:
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                yield json.loads(line)

    def _count(self) -> int:
        return sum(1 for _ in self._iter())

    def _load_head(self) -> str:
        head = GENESIS_HEAD
        for record in self._iter():
            head = record["hash"]
        return head

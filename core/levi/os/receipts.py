"""Hash-chained receipts for LEVI OS — evidence for every step (LAW 2).

Each receipt commits the previous chain head::

    hash = sha256(prev | seq | session_id | kind | canonical(detail))

The chain starts at a fixed genesis head, so the very first receipt is
verifiable too. Records are append-only JSONL under the caller-supplied
home (``~/.levi/os/receipts.jsonl``), files mode 0600.

``verify()`` walks the chain and reports the first broken link. A single
altered byte breaks the chain — tampering is detectable, not preventable
(honest limit, stated here).

Convention follows core/levi/mood/receipts.py (the repo's receipt shape);
the zone tag here is ``os``.
"""

from __future__ import annotations

import hashlib
import json
import os as _os  # stdlib — absolute import, never the levi.os package
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple

__all__ = [
    "GENESIS_HEAD",
    "Receipt",
    "ReceiptWriter",
    "os_dir",
    "read_receipts",
    "verify",
]

#: Fixed genesis head — the chain's trust anchor.
GENESIS_HEAD = "levios-genesis-" + "0" * 56

_RECORD_MODE = 0o600
ZONE = "os"


def os_dir(home: Path) -> Path:
    """``~/.levi/os`` under the caller-supplied home."""
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
            "seq": self.seq,
            "ts": self.ts,
            "session_id": self.session_id,
            "kind": self.kind,
            "detail": self.detail,
            "prev": self.prev,
            "hash": self.hash,
        }


class ReceiptWriter:
    """Append-only writer for one session's receipts."""

    def __init__(self, home: Path, session_id: str) -> None:
        if not session_id:
            raise ValueError("session_id is required")
        self._dir = os_dir(Path(home))
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / "receipts.jsonl"
        self._session_id = session_id
        self._seq = self._last_seq()
        self._prev = self._last_hash()

    def _last_seq(self) -> int:
        seq = 0
        for r in read_receipts(self._dir):
            if r.session_id == self._session_id:
                seq = max(seq, r.seq)
        return seq

    def _last_hash(self) -> str:
        prev = GENESIS_HEAD
        for r in read_receipts(self._dir):
            if r.session_id == self._session_id:
                prev = r.hash
        return prev

    def append(self, kind: str, detail: Dict[str, Any]) -> Receipt:
        """Write one receipt. Never raises on content — fails loudly on I/O."""
        if not kind:
            raise ValueError("kind is required")
        self._seq += 1
        receipt = Receipt(
            seq=self._seq,
            ts=_utcnow(),
            session_id=self._session_id,
            kind=kind,
            detail=dict(detail),
            prev=self._prev,
            hash=_receipt_hash(self._prev, self._seq, self._session_id, kind, detail),
        )
        with open(self._path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt.to_dict()) + "\n")
        _os.chmod(self._path, _RECORD_MODE)
        self._prev = receipt.hash
        return receipt

    @property
    def path(self) -> Path:
        return self._path


def read_receipts(os_home: Path) -> Iterator[Receipt]:
    """Yield every receipt in the JSONL log, in file order."""
    path = Path(os_home) / "receipts.jsonl"
    if not path.exists():
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            yield Receipt(
                seq=d["seq"],
                ts=d["ts"],
                session_id=d["session_id"],
                kind=d["kind"],
                detail=d["detail"],
                prev=d["prev"],
                hash=d["hash"],
            )


def verify(home: Path, session_id: Optional[str] = None) -> Tuple[bool, Optional[int]]:
    """Walk the chain; return (ok, broken_seq_or_None).

    When ``session_id`` is given, only that session's chain is checked.
    """
    prev = GENESIS_HEAD
    for r in read_receipts(os_dir(Path(home))):
        if session_id is not None and r.session_id != session_id:
            continue
        if r.prev != prev:
            return False, r.seq
        want = _receipt_hash(r.prev, r.seq, r.session_id, r.kind, r.detail)
        if r.hash != want:
            return False, r.seq
        prev = r.hash
    return True, None

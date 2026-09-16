"""Cybrus audit engine — append-only, hash-chained, tamper-evident log.

Every record carries ``prev`` (the previous record's hash) and ``hash``
(``sha256(prev + canonical_json(record))``). :meth:`verify` walks the
chain; any flipped byte — in a record *or* in a link — fails verification
at the exact record index where the chain breaks.

Writes are atomic appends (single ``os.write`` under ``O_APPEND`` +
``fsync``), the file is created owner-only (``0o600``), and the directory
is owner-only (``0o700``). There is no delete or rewrite API: the log is
append-only by construction.

Records persist as JSONL under ``~/.levi/cybrus/audit.jsonl``
(``LEVI_HOME`` override honored).
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# --- standalone-safe import of the sibling _paths helper -------------------
# Same rationale as policy.py: must work even while the package __init__
# is mid-flight on sibling engine modules.
def _paths():  # noqa: D103 - private helper
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


#: Hash of the imaginary record before the first real one.
GENESIS_PREV = "0" * 64


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(record: Dict) -> str:
    """Canonical JSON of a record (hash excluded): sorted keys, no
    whitespace. Both writer and verifier must use exactly this."""
    return json.dumps(record, sort_keys=True, separators=(",", ":"))


def _hash_record(prev_hash: str, record: Dict) -> str:
    body = {k: v for k, v in record.items() if k != "hash"}
    return hashlib.sha256((prev_hash + _canonical(body)).encode("utf-8")).hexdigest()


class AuditEngine:
    """Append-only hash-chained audit log."""

    def __init__(self) -> None:
        self._path: Path = _paths().cybrus_dir() / "audit.jsonl"
        # Ensure the file exists, owner-only, without truncating.
        if not self._path.exists():
            fd = os.open(self._path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
        else:
            os.chmod(self._path, 0o600)

    # -- writing ---------------------------------------------------------

    def _last_hash(self) -> Tuple[str, int]:
        """(hash, seq) of the last record, or (GENESIS_PREV, -1) when empty."""
        prev, seq = GENESIS_PREV, -1
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue  # verify() will flag it; don't crash appends
                    prev = rec.get("hash", prev)
                    seq = rec.get("seq", seq)
        except OSError:
            pass
        return prev, seq

    def append(self, event: str, actor: str, details: Optional[Dict] = None) -> Dict:
        """Append one record, hash-chained to its predecessor. Returns the
        record (including its hash). Atomic: single O_APPEND write + fsync."""
        prev_hash, last_seq = self._last_hash()
        record = {
            "seq": last_seq + 1,
            "ts": _utcnow_iso(),
            "event": event,
            "actor": actor,
            "details": dict(details or {}),
            "prev": prev_hash,
        }
        record["hash"] = _hash_record(prev_hash, record)
        blob = (_canonical(record) + "\n").encode("utf-8")
        fd = os.open(self._path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, blob)
            os.fsync(fd)
        finally:
            os.close(fd)
        return dict(record)

    # -- reading ---------------------------------------------------------

    def _read_all(self) -> List[Tuple[int, Optional[Dict]]]:
        """[(record_index, record or None when the line is unparseable)]."""
        out: List[Tuple[int, Optional[Dict]]] = []
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    idx = len(out)
                    try:
                        out.append((idx, json.loads(line)))
                    except json.JSONDecodeError:
                        out.append((idx, None))
        except OSError:
            pass
        return out

    def verify(self) -> Tuple[bool, Optional[int]]:
        """Walk the hash chain. Returns ``(True, None)`` when intact, else
        ``(False, first_bad_index)`` — the 0-based record index where the
        chain first breaks (bad hash, broken link, bad sequence number, or
        an unparseable line)."""
        expected_prev = GENESIS_PREV
        expected_seq = 0
        for idx, rec in self._read_all():
            if not isinstance(rec, dict):
                return False, idx
            if rec.get("seq") != expected_seq:
                return False, idx
            if rec.get("prev") != expected_prev:
                return False, idx
            if rec.get("hash") != _hash_record(rec.get("prev", ""), rec):
                return False, idx
            expected_prev = rec["hash"]
            expected_seq += 1
        return True, None

    def tail(self, n: int = 20) -> List[Dict]:
        """The last *n* parseable records, oldest first."""
        records = [rec for _, rec in self._read_all() if isinstance(rec, dict)]
        return [dict(rec) for rec in records[-n:]]

    def count(self) -> int:
        return len(self._read_all())

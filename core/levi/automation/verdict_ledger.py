"""Verdict ledger — append-only, hash-chained audit log for engine verdicts.

Every adjudicated verdict gets written down where it cannot be quietly
rewritten: entries chain by SHA-256 (each entry commits to the previous
entry's hash), and the ledger exposes no edit or delete API. Append and
verify are the whole vocabulary.

Laws (invariants):

- L1 append-only — there is no method that mutates or removes an entry.
- L2 chain integrity — ``verify()`` re-walks every link; any tampering
  with a stored entry breaks the chain and is reported, never hidden.
- L3 deterministic hashing — identical entry content always hashes
  identically (canonical JSON: sorted keys, compact separators).
- L4 load validates — opening a persisted ledger re-verifies the chain;
  a corrupt file is refused with a named error, never loaded silently.
- L5 sequencing — entry ``seq`` values are dense from 0; gaps are refused.

Persistence is an optional JSONL file (one entry per line). Writes are
atomic (temp file + rename). The default in-memory ledger never touches
the disk.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

GENESIS_HASH = "GENESIS"


class LedgerError(ValueError):
    """Raised when the ledger refuses input or detects corruption."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _entry_hash(
    seq: int, ts: str, source: str, verdict: Dict[str, Any], prev_hash: str
) -> str:
    body = _canonical(
        {
            "seq": seq,
            "ts": ts,
            "source": source,
            "verdict": verdict,
            "prev_hash": prev_hash,
        }
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Entry:
    """One immutable link in the chain."""

    seq: int
    ts: str
    source: str
    verdict: Dict[str, Any]
    prev_hash: str
    entry_hash: str = field(compare=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seq": self.seq,
            "ts": self.ts,
            "source": self.source,
            "verdict": self.verdict,
            "prev_hash": self.prev_hash,
            "entry_hash": self.entry_hash,
        }

    @staticmethod
    def from_dict(raw: Dict[str, Any]) -> "Entry":
        try:
            return Entry(
                seq=int(raw["seq"]),
                ts=str(raw["ts"]),
                source=str(raw["source"]),
                verdict=dict(raw["verdict"]),
                prev_hash=str(raw["prev_hash"]),
                entry_hash=str(raw["entry_hash"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise LedgerError(f"malformed ledger entry: {exc}") from exc


class VerdictLedger:
    """Append-only hash-chained log of engine verdicts."""

    def __init__(self, path: Optional[str] = None) -> None:
        self._entries: List[Entry] = []
        self._path = Path(path).expanduser() if path else None
        if self._path is not None and self._path.exists():
            self._load()

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def path(self) -> Optional[Path]:
        return self._path

    def record(self, verdict: Dict[str, Any], source: str = "") -> Entry:
        """Append one verdict. The verdict must be a JSON-serializable dict."""
        if not isinstance(verdict, dict):
            raise LedgerError(f"verdict must be a dict, got {type(verdict).__name__}")
        try:
            verdict_copy = json.loads(_canonical(verdict))
        except (TypeError, ValueError) as exc:
            raise LedgerError(f"verdict is not JSON-serializable: {exc}") from exc
        if not isinstance(source, str):
            raise LedgerError("source must be a string")
        seq = len(self._entries)
        prev_hash = self._entries[-1].entry_hash if self._entries else GENESIS_HASH
        ts = _utcnow()
        entry = Entry(
            seq=seq,
            ts=ts,
            source=source,
            verdict=verdict_copy,
            prev_hash=prev_hash,
            entry_hash=_entry_hash(seq, ts, source, verdict_copy, prev_hash),
        )
        self._entries.append(entry)
        if self._path is not None:
            self._save()
        return entry

    def get(self, seq: int) -> Entry:
        if not isinstance(seq, int) or not 0 <= seq < len(self._entries):
            raise LedgerError(f"no entry with seq {seq!r}")
        return self._entries[seq]

    def tail(self, n: int = 10) -> List[Entry]:
        if n <= 0:
            return []
        return list(self._entries[-n:])

    def find(self, ruling: str) -> List[Entry]:
        """All entries whose verdict carries the given ruling name."""
        return [e for e in self._entries if e.verdict.get("ruling") == ruling]

    def verify(self) -> Tuple[bool, List[str]]:
        """Re-walk the chain. Returns (ok, problems)."""
        problems: List[str] = []
        prev = GENESIS_HASH
        for index, entry in enumerate(self._entries):
            if entry.seq != index:
                problems.append(f"entry {index}: seq is {entry.seq}, expected {index}")
            if entry.prev_hash != prev:
                problems.append(
                    f"entry {index}: prev_hash does not match entry {index - 1}'s hash"
                )
            recomputed = _entry_hash(
                entry.seq,
                entry.ts,
                entry.source,
                entry.verdict,
                entry.prev_hash,
            )
            if recomputed != entry.entry_hash:
                problems.append(
                    f"entry {index}: entry_hash does not match content (tampered)"
                )
            prev = entry.entry_hash
        return (not problems, problems)

    def _save(self) -> None:
        assert self._path is not None
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self._path.parent), prefix=self._path.name + ".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                for entry in self._entries:
                    handle.write(_canonical(entry.to_dict()) + "\n")
            os.replace(tmp_name, self._path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def _load(self) -> None:
        assert self._path is not None
        entries: List[Entry] = []
        with self._path.open("r", encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except ValueError as exc:
                    raise LedgerError(
                        f"{self._path}:{lineno}: not valid JSON: {exc}"
                    ) from exc
                entries.append(Entry.from_dict(raw))
        self._entries = entries
        ok, problems = self.verify()
        if not ok:
            self._entries = []
            raise LedgerError(
                f"refusing to load corrupt ledger {self._path}: " + "; ".join(problems)
            )


__all__ = ["Entry", "LedgerError", "VerdictLedger", "GENESIS_HASH"]

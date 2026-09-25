"""Cybrus audit engine — append-only, hash-chained, tamper-evident log.

Every record carries ``prev`` (the previous record's hash) and ``hash``
(``sha256(prev + canonical_json(record))``). :meth:`verify` walks the
chain; any flipped byte — in a record *or* in a link — fails verification
at the exact record index where the chain breaks.

BLUE (RED-1) additions:
- **Truncation anchoring (L10):** the chain is forward-linked, so deleting
  the tail used to leave a shorter chain that still verified. Every
  append now also anchors ``{"count", "tip_hash"}`` in
  ``audit.state.json`` (owner-only, atomic write, under the same store
  lock as the append). :meth:`verify` fails closed when the log is
  shorter than the anchor, or the tip hash disagrees, or a non-empty log
  has no anchor at all. If an append finds the log shorter than the
  anchor, it first writes an in-band ``audit.tail_gap`` system record so
  the evidence survives in the tamper-evident log itself.
- **Payload scrubbing (L4):** :meth:`append` recursively redacts any
  string longer than 256 chars to ``{"__audit_redacted__",
  "sha256", "len"}`` — audit records carry metadata only, never
  payloads, never secrets. A caller-supplied ``purpose`` or
  ``payload_meta`` blob can no longer turn the audit trail into a
  covert exfiltration / secret-storage channel.

Honest limits: the anchor stops an attacker who can rewrite the LOG
(the tested attack). An attacker who can also rewrite
``audit.state.json`` can re-anchor a truncated log — full protection
needs an external anchor (e.g. the backup manifest's hash chain).
:meth:`reanchor` is the explicit operator escape hatch for legacy logs
written before anchoring existed; it audit-logs its own use.

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

#: Audit records carry metadata only (L4): any string longer than this in
#: a record's details is replaced by a sha256 digest + length descriptor.
#: Short human-readable fields (targets, reasons, ids) pass through
#: verbatim; unbounded caller-shaped blobs never reach the log.
MAX_DETAIL_STRING = 256

#: Store name (→ ``audit.state.json``) for the truncation anchor.
_STATE_STORE_NAME = "audit.state"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(record: Dict) -> str:
    """Canonical JSON of a record (hash excluded): sorted keys, no
    whitespace. Both writer and verifier must use exactly this."""
    return json.dumps(record, sort_keys=True, separators=(",", ":"))


def _hash_record(prev_hash: str, record: Dict) -> str:
    body = {k: v for k, v in record.items() if k != "hash"}
    return hashlib.sha256((prev_hash + _canonical(body)).encode("utf-8")).hexdigest()


def _scrub_value(value):
    """Recursively redact over-long strings (L4: metadata only).

    Any string longer than :data:`MAX_DETAIL_STRING` becomes
    ``{"__audit_redacted__": "overlong-string", "sha256": ..., "len": ...}``
    — the content never reaches the log, but its digest lets an operator
    confirm what was redacted without storing it.
    """
    if isinstance(value, str):
        if len(value) > MAX_DETAIL_STRING:
            return {
                "__audit_redacted__": "overlong-string",
                "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
                "len": len(value),
            }
        return value
    if isinstance(value, dict):
        return {k: _scrub_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub_value(v) for v in value]
    return value


class AuditEngine:
    """Append-only hash-chained audit log."""

    def __init__(self) -> None:
        p = _paths()
        self._path: Path = p.cybrus_dir() / "audit.jsonl"
        self._state_path: Path = p.store_path(_STATE_STORE_NAME)
        # Ensure the file exists, owner-only, without truncating.
        if not self._path.exists():
            fd = os.open(self._path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
        else:
            os.chmod(self._path, 0o600)

    # -- truncation anchor (BLUE, RED-1) ----------------------------------

    def _load_state(self) -> Optional[Dict]:
        """The ``{"count", "tip_hash"}`` anchor, or ``None`` when no
        anchor exists yet (fresh log, or legacy log predating anchors)."""
        try:
            data = _paths().load_json_store(self._state_path)
        except Exception:
            # Corrupt anchor: the file is quarantined by _paths; treat as
            # missing — verify() fails closed on a non-empty log, and the
            # next append re-anchors.
            return None
        if isinstance(data, dict) and isinstance(data.get("count"), int):
            return data
        return None

    def _save_state(self, count: int, tip_hash: str) -> None:
        _paths().save_json_store(
            self._state_path, {"count": count, "tip_hash": tip_hash}
        )

    # -- writing ---------------------------------------------------------

    def _scan(self) -> Tuple[str, int, int]:
        """(prev_hash, last_seq, count) over the parseable records."""
        prev, seq, count = GENESIS_PREV, -1, 0
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
                    count += 1
        except OSError:
            pass
        return prev, seq, count

    def _last_hash(self) -> Tuple[str, int]:
        """(hash, seq) of the last record, or (GENESIS_PREV, -1) when empty."""
        prev, seq, _ = self._scan()
        return prev, seq

    def _write_record_unlocked(
        self, event: str, actor: str, details: Dict, prev_hash: str, seq: int
    ) -> Dict:
        record = {
            "seq": seq,
            "ts": _utcnow_iso(),
            "event": event,
            "actor": actor,
            "details": _scrub_value(dict(details)),
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

    def append(self, event: str, actor: str, details: Optional[Dict] = None) -> Dict:
        """Append one record, hash-chained to its predecessor. Returns the
        record (including its hash). Atomic: single O_APPEND write + fsync.

        BLUE (RED-1):
        - details are scrubbed (L4): over-long strings become
          digest+length descriptors, never verbatim content.
        - the truncation anchor is updated under the store lock (L10).
        - if the log is shorter than the anchor (tail deleted
          out-of-band), an ``audit.tail_gap`` system record is written
          first, so the evidence survives in the tamper-evident log.
        """
        p = _paths()
        with p.store_lock(self._path):
            prev_hash, last_seq, count = self._scan()
            state = self._load_state()
            if state is not None and count < state["count"]:
                gap = self._write_record_unlocked(
                    "audit.tail_gap",
                    "audit-engine",
                    {
                        "expected_count": state["count"],
                        "found_count": count,
                        "note": (
                            "audit log shorter than the truncation anchor: "
                            "tail records were deleted out-of-band"
                        ),
                    },
                    prev_hash,
                    last_seq + 1,
                )
                prev_hash, last_seq, count = gap["hash"], gap["seq"], count + 1
            record = self._write_record_unlocked(
                event, actor, details or {}, prev_hash, last_seq + 1
            )
            self._save_state(count + 1, record["hash"])
            return record

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
        """Walk the hash chain, then check the truncation anchor.

        Returns ``(True, None)`` when intact, else ``(False,
        first_bad_index)`` — the 0-based record index where the chain
        first breaks (bad hash, broken link, bad sequence number, or an
        unparseable line), or the index where the anchored tail goes
        missing.

        BLUE (RED-1): after the chain walk, the record count and tip hash
        must match the ``audit.state.json`` anchor. A non-empty log with
        no anchor fails closed — use :meth:`reanchor` explicitly for
        legacy logs (the re-anchor is itself audit-logged).
        """
        p = _paths()
        with p.store_lock(self._path):
            records = self._read_all()
            expected_prev = GENESIS_PREV
            expected_seq = 0
            for idx, rec in records:
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
            n = len(records)
            tip = records[-1][1]["hash"] if records else GENESIS_PREV
            state = self._load_state()
            if state is None:
                if n == 0:
                    return True, None
                return False, 0  # unanchored non-empty log: fail closed
            if n != state["count"] or tip != state.get("tip_hash"):
                return False, n  # anchored tail is missing / diverged
            return True, None

    def reanchor(self) -> Dict:
        """Explicit operator escape hatch for legacy (pre-anchor) logs:
        rebuild the truncation anchor from the current file contents.

        The re-anchor is itself audit-logged (``audit.state_reanchored``)
        so the operation is visible in the tamper-evident trail. Fails
        closed: refuses when the chain itself does not verify.
        """
        p = _paths()
        with p.store_lock(self._path):
            records = self._read_all()
            expected_prev, expected_seq = GENESIS_PREV, 0
            for idx, rec in records:
                if (
                    not isinstance(rec, dict)
                    or rec.get("seq") != expected_seq
                    or rec.get("prev") != expected_prev
                    or rec.get("hash") != _hash_record(rec.get("prev", ""), rec)
                ):
                    raise ValueError(
                        "reanchor refused: the audit chain itself is broken "
                        f"(first bad index {idx}); repair the log, do not "
                        "re-anchor it"
                    )
                expected_prev, expected_seq = rec["hash"], expected_seq + 1
            n = len(records)
            tip = records[-1][1]["hash"] if records else GENESIS_PREV
            record = self._write_record_unlocked(
                "audit.state_reanchored",
                "audit-engine",
                {"count": n, "note": "operator re-anchored a legacy audit log"},
                tip,
                n,
            )
            self._save_state(n + 1, record["hash"])
            return {"count": n + 1, "tip_hash": record["hash"]}

    def tail(self, n: int = 20) -> List[Dict]:
        """The last *n* parseable records, oldest first."""
        records = [rec for _, rec in self._read_all() if isinstance(rec, dict)]
        return [dict(rec) for rec in records[-n:]]

    def count(self) -> int:
        return len(self._read_all())

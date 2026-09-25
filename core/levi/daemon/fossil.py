"""Fossil — the journal-compaction daemon.

LEVI's append-only JSONL journals (the growth journal, watchman events,
daemon state churn) grow forever. Fossil compacts them on a schedule:
entries older than a retention window are rolled into per-day digest
snapshots, and a compaction receipt records exactly what moved. Fossil never
deletes without a receipt — compaction is honest: original entry counts,
first/last timestamps, and per-kind tallies are preserved in the digest so
nothing the Archive might need is silently gone.

Retention is opt-in and deny-closed: ``compact_journal`` refuses missing
files, non-JSONL targets, and unparseable lines (a single corrupt line
aborts the run rather than compacting around it); ``dry_run=True`` is the
default.

There is no daemonize here — the long-run entry is
``python3 -m levi.daemon.fossil --apply`` inside the perpetual supervisor
(one_for_one child), or a plain ``run_once()`` call from cron.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

#: Timestamp fields we recognize inside a journal record, in order.
_TS_FIELDS = ("at", "ts", "timestamp", "time", "created")

#: Kind fields we recognize for the per-kind tallies.
_KIND_FIELDS = ("kind", "type", "event", "action")

DEFAULT_RECEIPTS_PATH = Path.home() / ".levi" / "fossil" / "receipts.jsonl"


@dataclass
class FossilConfig:
    """Targets and policy for one compaction pass."""

    targets: List[str] = field(default_factory=list)
    older_than_days: int = 30
    dry_run: bool = True
    receipts_path: str = str(DEFAULT_RECEIPTS_PATH)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CompactionReceipt:
    """Exactly what one compact_journal call did."""

    target: str
    dry_run: bool
    window_days: int
    kept: int
    compacted: int
    corrupt: int
    digest: Dict[str, Any]
    digest_path: str
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _parse_ts(record: Dict[str, Any]) -> Optional[datetime]:
    for key in _TS_FIELDS:
        raw = record.get(key)
        if not raw:
            continue
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    return None


def _kind_of(record: Dict[str, Any]) -> str:
    for key in _KIND_FIELDS:
        val = record.get(key)
        if val:
            return str(val)
    return "unknown"


def digest_records(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize a batch of compacted records into a digest.

    Groups by calendar day and by kind: counts, first/last timestamps, and
    up to three sample record ids per kind (never the full payload — the
    digest is a fossil, not a copy).
    """
    per_day: Dict[str, Dict[str, int]] = {}
    total = len(records)
    first: Optional[str] = None
    last: Optional[str] = None
    samples: Dict[str, List[str]] = {}
    for rec in records:
        kind = _kind_of(rec)
        dt = _parse_ts(rec)
        day = dt.date().isoformat() if dt else "undated"
        per_day.setdefault(day, {}).setdefault(kind, 0)
        per_day[day][kind] += 1
        ts = rec.get("at") or rec.get("ts") or rec.get("timestamp")
        if ts is not None:
            ts = str(ts)
            if first is None or ts < first:
                first = ts
            if last is None or ts > last:
                last = ts
        rid = str(rec.get("id") or rec.get("record_id") or rec.get("path") or "")[:80]
        if rid:
            bucket = samples.setdefault(kind, [])
            if len(bucket) < 3 and rid not in bucket:
                bucket.append(rid)
    return {
        "total": total,
        "per_day": per_day,
        "first_ts": first,
        "last_ts": last,
        "samples": samples,
    }


def compact_journal(
    path: str | Path,
    *,
    older_than_days: int = 30,
    dry_run: bool = True,
    now: Optional[datetime] = None,
) -> CompactionReceipt:
    """Compact one JSONL journal.

    Records with a recognized timestamp older than ``older_than_days`` are
    rolled into a digest snapshot; everything newer (and everything without
    a timestamp — Fossil never compacts what it cannot date) stays. On a
    real (non-dry) run the original file is rewritten atomically *after* the
    digest is safely on disk, and the receipt describes the whole move.

    Raises ``FileNotFoundError`` for missing files and ``ValueError`` for
    non-JSONL targets or corrupt lines — deny-closed, never half-compacted.
    """
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"fossil: no such journal: {target}")
    if target.suffix.lower() != ".jsonl":
        raise ValueError(f"fossil: not a JSONL journal: {target}")
    if older_than_days < 0:
        raise ValueError("fossil: older_than_days must be >= 0")

    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=older_than_days)

    recent: List[str] = []
    old_records: List[Dict[str, Any]] = []
    corrupt = 0
    for _lineno, line in enumerate(target.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            corrupt += 1
            continue
        if not isinstance(record, dict):
            corrupt += 1
            continue
        dt = _parse_ts(record)
        if dt is not None and dt < cutoff:
            old_records.append(record)
        else:
            recent.append(line)

    if corrupt:
        raise ValueError(
            f"fossil: {corrupt} corrupt line(s) in {target} — refusing to compact"
        )

    digest = digest_records(old_records)
    digest_path = target.with_suffix("").as_posix() + ".fossils.jsonl"
    receipt = CompactionReceipt(
        target=str(target),
        dry_run=dry_run,
        window_days=older_than_days,
        kept=len(recent),
        compacted=len(old_records),
        corrupt=0,
        digest=digest,
        digest_path=digest_path,
    )

    if dry_run or not old_records:
        return receipt

    # Real run: digest to disk first, then atomically rewrite the journal.
    digest_file = Path(digest_path)
    digest_file.parent.mkdir(parents=True, exist_ok=True)
    with digest_file.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps({"receipt": receipt.to_dict(), "digest": digest}, sort_keys=True)
            + "\n"
        )
    fd, tmp = tempfile.mkstemp(
        dir=str(target.parent), prefix=target.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for line in recent:
                fh.write(line + "\n")
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return receipt


def run_once(config: FossilConfig) -> List[CompactionReceipt]:
    """Compact every target in ``config``; receipts are recorded unless dry."""
    receipts: List[CompactionReceipt] = []
    for target in config.targets:
        receipts.append(
            compact_journal(
                target,
                older_than_days=config.older_than_days,
                dry_run=config.dry_run,
            )
        )
    if not config.dry_run and receipts:
        path = Path(config.receipts_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for receipt in receipts:
                fh.write(json.dumps(receipt.to_dict(), sort_keys=True) + "\n")
    return receipts


def _cli(argv: Optional[List[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="levi.daemon.fossil",
        description="Compact append-only JSONL journals into digest fossils.",
    )
    ap.add_argument("targets", nargs="*", help="JSONL journal paths to compact")
    ap.add_argument("--days", type=int, default=30, help="retention window in days")
    ap.add_argument(
        "--apply",
        action="store_true",
        help="actually rewrite journals (default is --dry-run)",
    )
    ap.add_argument("--receipts", default=str(DEFAULT_RECEIPTS_PATH))
    args = ap.parse_args(argv)

    if not args.targets:
        ap.error("at least one target journal is required")
    config = FossilConfig(
        targets=args.targets,
        older_than_days=args.days,
        dry_run=not args.apply,
        receipts_path=args.receipts,
    )
    for receipt in run_once(config):
        mode = "DRY-RUN" if receipt.dry_run else "COMPACTED"
        print(
            f"[{mode}] {receipt.target}: kept={receipt.kept} "
            f"compacted={receipt.compacted} -> {receipt.digest_path}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())

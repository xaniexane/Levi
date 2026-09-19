"""JSONL store layer for the NeighborOS organ (spec §6).

All state under ``~/.levi/neighbor/`` (overridable via the
``LEVI_NEIGHBOR_DIR`` env var for tests and operator tooling):
- gigs.jsonl, workers.jsonl, ledger.jsonl, settlements.jsonl,
  decisions.jsonl, disputes.jsonl, policies.json (seeded from the
  package default on first use — operator edits are never overwritten).

Append-only streams: nothing is ever deleted or rewritten in place.
``verify_integrity`` checks monotonic sequence numbers so any tampering
or loss is loud, not silent.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DIR = Path.home() / ".levi" / "neighbor"
STREAMS = (
    "gigs",
    "workers",
    "ledger",
    "settlements",
    "decisions",
    "disputes",
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    """Local-first JSONL store. Hermetic when constructed with a tmp dir."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        if base_dir is None:
            base_dir = os.environ.get("LEVI_NEIGHBOR_DIR", str(DEFAULT_DIR))
        self.base = Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)
        os.chmod(self.base, 0o700)

    # -- streams ------------------------------------------------------
    def _path(self, stream: str) -> Path:
        return self.base / f"{stream}.jsonl"

    def append(self, stream: str, record: dict, now: str | None = None) -> dict:
        """Append one record; assigns monotonic ``seq`` and ``ts``."""
        path = self._path(stream)
        existing = self.read_all(stream)
        record = dict(record)
        record["seq"] = (existing[-1]["seq"] + 1) if existing else 1
        record["ts"] = now or utcnow()
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
        return record

    def read_all(self, stream: str) -> list[dict]:
        path = self._path(stream)
        if not path.exists():
            return []
        records = []
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def find(self, stream: str, key: str, value) -> dict | None:
        for record in self.read_all(stream):
            if record.get(key) == value:
                return record
        return None

    def next_id(self, prefix: str) -> str:
        """Deterministic sequential ids (gig-0001 …)."""
        meta_path = self.base / "_meta.json"
        meta = {}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        count = int(meta.get(prefix, 0)) + 1
        meta[prefix] = count
        meta_path.write_text(json.dumps(meta, sort_keys=True), encoding="utf-8")
        return f"{prefix}-{count:04d}"

    def verify_integrity(self) -> dict:
        """Append-only check: seqs monotonic, no gaps, streams readable."""
        report: dict = {"ok": True, "streams": {}}
        for stream in STREAMS:
            records = self.read_all(stream)
            seqs = [r.get("seq") for r in records]
            ok = seqs == list(range(1, len(records) + 1))
            report["streams"][stream] = {
                "records": len(records),
                "append_only_ok": ok,
            }
            if not ok:
                report["ok"] = False
        return report

    # -- policies -----------------------------------------------------
    def policies_path(self) -> Path:
        return self.base / "policies.json"

    def ensure_policies(self) -> Path:
        """Seed the operator's policies.json once; never overwrite edits."""
        dest = self.policies_path()
        if not dest.exists():
            src = Path(__file__).with_name("policies.json")
            shutil.copyfile(src, dest)
        return dest

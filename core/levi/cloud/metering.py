"""Usage metering for LEVI-as-cloud (LEVI-original).

Append-only JSONL at ``LEVI_CLOUD_DIR`` / ``~/.levi/cloud/usage.jsonl``.
One record per served ``/v1/`` call:

    {"ts", "key_name", "key_prefix", "endpoint", "steps", "ok", "error"}

Only the key *prefix* is recorded — never a raw key. The log is the
owner's honest accounting of who used how much; there is no billing
attached (single-machine server, no payment rails by design).

``log_usage`` never raises: metering must not break a served request.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from levi.cloud.apikeys import cloud_dir


def usage_path() -> Path:
    return cloud_dir() / "usage.jsonl"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log_usage(
    *,
    key_name: str,
    key_prefix: str,
    endpoint: str,
    steps: int = 0,
    ok: bool = True,
    error: str | None = None,
) -> None:
    record = {
        "ts": _utcnow(),
        "key_name": key_name,
        "key_prefix": key_prefix,
        "endpoint": endpoint,
        "steps": int(steps),
        "ok": bool(ok),
        "error": error,
    }
    try:
        path = usage_path()
        with open(path, "a", encoding="utf-8") as fh:
            # Owner-only, like the key store.
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
            fh.write(json.dumps(record) + "\n")
    except OSError:
        pass


def read_usage(key_name: str | None = None, limit: int = 100) -> list[dict]:
    """Most recent ``limit`` records, optionally filtered by key name."""
    path = usage_path()
    if not path.exists():
        return []
    records: list[dict] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict):
                    records.append(rec)
    except OSError:
        return []
    if key_name:
        records = [r for r in records if r.get("key_name") == key_name]
    return records[-max(1, limit):]

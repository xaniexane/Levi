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
import re
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from levi.cloud.apikeys import cloud_dir


def usage_path() -> Path:
    return cloud_dir() / "usage.jsonl"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# Key-like substrings that must never land in the stored log verbatim —
# an exception message echoed into ``error`` could otherwise carry a raw
# bearer token. Conservative: anything matching is replaced wholesale.
# Note the 12-char ``levi_sk_XXXX`` *prefix* is intentionally log-safe
# (see apikeys._PREFIX_LEN) and is NOT redacted — only longer tokens,
# which can only be raw keys, are.
_SECRET_PATTERNS = (
    re.compile(r"levi_sk_[A-Za-z0-9_-]{5,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]+=*"),
    re.compile(r"(?i)\bapi[_-]?key\s*[:=]\s*\S+"),
)


def _redact(text: str) -> str:
    for pat in _SECRET_PATTERNS:
        text = pat.sub("[redacted]", text)
    return text


def log_usage(
    *,
    key_name: str | None,
    key_prefix: str | None,
    endpoint: str | None,
    steps: int = 0,
    ok: bool = True,
    error: str | None = None,
) -> None:
    # The whole body is fail-safe: metering must never break a served
    # request, whatever garbage arrives (bad types, hostile env vars,
    # unwritable disk).  Secret-like substrings are redacted before
    # anything is persisted.
    try:
        record = {
            "ts": _utcnow(),
            "key_name": _redact(str(key_name or "")),
            "key_prefix": _redact(str(key_prefix or "")),
            "endpoint": _redact(str(endpoint or "")),
            "steps": _safe_int(steps),
            "ok": bool(ok),
            "error": None if error is None else _redact(str(error))[:200],
        }
        path = usage_path()
        with open(path, "a", encoding="utf-8") as fh:
            # Owner-only, like the key store.
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
            fh.write(json.dumps(record) + "\n")
    except Exception:
        pass


def _safe_int(value) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, n)


def read_usage(key_name: str | None = None, limit: int = 100) -> list[dict]:
    """Most recent ``limit`` records, optionally filtered by key name.

    Bounded memory: the file is streamed once and only the matching tail
    (at most ``limit`` parsed records) is ever held.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        limit = 100
    limit = min(limit, 10_000)  # bound memory on a hostile/lazy caller
    try:
        path = usage_path()
    except OSError:
        return []
    if not path.exists():
        return []
    matches: deque = deque(maxlen=limit)
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
                if isinstance(rec, dict) and (
                    not key_name or rec.get("key_name") == key_name
                ):
                    matches.append(rec)
    except OSError:
        return []
    return list(matches)

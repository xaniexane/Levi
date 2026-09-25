"""Content addressing: sha256 over canonical JSON."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical(obj: Any) -> bytes:
    """Canonical bytes for any JSON-able object (sorted keys, no spaces)."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_json(obj: Any) -> str:
    """Content hash of a JSON-able object."""
    return sha256_hex(canonical(obj))

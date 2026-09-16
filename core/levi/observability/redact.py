"""Secret-safe redaction for observability records.

Every value that flows into the decision-trace corpus passes through here
before it is persisted or hashed. The rules:

* Keys that *name* a secret (password, token, api_key, ...) have their
  values replaced wholesale.
* Values that *look* like secrets (long opaque strings, ``sk-``/``xox-``
  style tokens, ``Bearer ...`` headers) are replaced even when the key
  name is innocent.
* ``params_hash()`` hashes the REDACTED canonical form, so a hash can
  never be reversed into a secret and identical redacted shapes collide
  honestly.

stdlib-only. Never raises on hostile input shapes.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict

REDACTED = "***REDACTED***"

# Key names that always denote a secret, regardless of the value.
_SECRET_KEY_RE = re.compile(
    r"password|passwd|pwd|secret|token|api[_-]?key|bearer|credential|"
    r"private[_-]?key|passphrase|auth|session[_-]?key|cookie|ssn|"
    r"account[_-]?number|card[_-]?number|otp|pin\b",
    re.IGNORECASE,
)

# Values shaped like issued secrets even when the key name is innocent:
#   - provider key prefixes (sk-, xoxb-/xoxp-/xoxa-, ghp_, gsk_, ...)
#   - long opaque blobs (base64/hex/url-safe, >= 24 chars)
#   - "Bearer <blob>" authorization headers
_SECRET_VALUE_RE = re.compile(
    r"^(?:"
    r"(?:sk|rk|gsk|ghp|gho|xox[bap])-"
    r"[A-Za-z0-9\-_]{8,}"
    r"|Bearer\s+[A-Za-z0-9\-_.~+/]+=*$"
    r"|[A-Za-z0-9+/=_-]{24,}"
    r")$"
)


def _looks_secret(value: str) -> bool:
    if len(value) < 8:
        return False
    return bool(_SECRET_VALUE_RE.match(value.strip()))


def redact(value: Any, _key: str = "") -> Any:
    """Recursively redact secrets from an arbitrary value.

    Dict keys are matched against the secret-key list; string values are
    additionally matched against the secret-shape list. Non-string
    scalars pass through untouched. Never raises.
    """
    try:
        if isinstance(value, dict):
            out: Dict[str, Any] = {}
            for k, v in value.items():
                ks = str(k)
                if _SECRET_KEY_RE.search(ks):
                    out[ks] = REDACTED
                else:
                    out[ks] = redact(v, ks)
            return out
        if isinstance(value, (list, tuple)):
            return [redact(v, _key) for v in value]
        if isinstance(value, str):
            if _SECRET_KEY_RE.search(_key) or _looks_secret(value):
                return REDACTED
            return value
        return value
    except Exception:
        return REDACTED


def canonical(params: Any) -> str:
    """Canonical JSON of the redacted params (sorted keys, tight separators)."""
    return json.dumps(
        redact(params), sort_keys=True, separators=(",", ":"), default=str
    )


def params_hash(params: Any) -> str:
    """SHA-256 over the redacted canonical form.

    The raw params are NEVER hashed: a hash of a secret is still a
    fingerprint an attacker can brute-force. Hashing the redacted form
    keeps the hash useful for dedup/correlation without leaking anything.
    """
    return hashlib.sha256(canonical(params).encode("utf-8")).hexdigest()

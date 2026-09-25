"""In-memory per-key rate limiting for LEVI-as-cloud (LEVI-original).

Token bucket per key prefix: each key gets ``per_minute`` requests per
60-second window (default 60, override with ``LEVI_CLOUD_RATE_PER_MIN``).
The owner master token is not rate-limited.

Exceeding the bucket answers ``429`` with a ``Retry-After`` header —
the client backs off, the server stays up. Buckets live only in
memory: a restart resets them, which is fail-open in the safe
direction for a single-machine server (no shared state to desync).
"""

from __future__ import annotations

import os
import threading
import time

DEFAULT_PER_MINUTE = 60


def per_minute_limit() -> int:
    try:
        value = int(os.environ.get("LEVI_CLOUD_RATE_PER_MIN", DEFAULT_PER_MINUTE))
    except (TypeError, ValueError):
        return DEFAULT_PER_MINUTE
    return max(1, value)


class RateLimiter:
    """Thread-safe token buckets keyed by an opaque bucket id."""

    def __init__(self, per_minute: int | None = None) -> None:
        if per_minute is None:
            per_minute = per_minute_limit()
        if (
            isinstance(per_minute, bool)
            or not isinstance(per_minute, int)
            or per_minute < 1
        ):
            raise ValueError(
                "per_minute must be an integer >= 1, got %r" % (per_minute,)
            )
        self.per_minute = per_minute
        self._buckets: dict[str, tuple[float, float]] = {}  # id -> (tokens, last_ts)
        self._lock = threading.Lock()

    def _refill(self, bucket_id: str, now: float) -> float:
        tokens, last = self._buckets.get(bucket_id, (float(self.per_minute), now))
        elapsed = max(0.0, now - last)
        tokens = min(
            float(self.per_minute), tokens + elapsed * (self.per_minute / 60.0)
        )
        return tokens

    def check(self, bucket_id: str) -> tuple[bool, float]:
        """Consume one token. Returns ``(allowed, retry_after_secs)``."""
        _validate_bucket_id(bucket_id)
        now = time.monotonic()
        with self._lock:
            tokens = self._refill(bucket_id, now)
            if tokens >= 1.0:
                self._buckets[bucket_id] = (tokens - 1.0, now)
                return True, 0.0
            # Time until the next token arrives.
            retry_after = (1.0 - tokens) / (self.per_minute / 60.0)
            self._buckets[bucket_id] = (tokens, now)
            return False, retry_after

    def reset(self, bucket_id: str) -> None:
        """Clear a bucket (e.g. after key rotation)."""
        _validate_bucket_id(bucket_id)
        with self._lock:
            self._buckets.pop(bucket_id, None)


def _validate_bucket_id(bucket_id: str) -> str:
    if not isinstance(bucket_id, str) or not bucket_id:
        raise ValueError("bucket_id must be a non-empty string")
    return bucket_id

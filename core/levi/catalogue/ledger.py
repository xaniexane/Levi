"""Usage ledger — free-tier metering per user, per entry, per period.

Periods are calendar months in UTC. ``record_use`` counts a use and
reports whether it fell inside the user's free quota. The ledger only
counts; it never invokes anything (Gateway Law).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Tuple


def current_period() -> str:
    """Current metering period: ``YYYY-MM`` in UTC."""
    now = datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


class UsageLedger:
    """In-memory per-user usage counts. Serialize via to_dict/from_dict."""

    def __init__(self) -> None:
        # (user_id, entry_id, period) -> uses
        self._uses: Dict[Tuple[str, str, str], int] = {}

    def uses(self, user_id: str, entry_id: str, period: str | None = None) -> int:
        return self._uses.get((user_id, entry_id, period or current_period()), 0)

    def record_use(
        self, user_id: str, entry_id: str, free_quota: int, period: str | None = None
    ) -> Dict:
        """Count one use. Returns whether it landed inside the free quota."""
        period = period or current_period()
        key = (user_id, entry_id, period)
        used_before = self._uses.get(key, 0)
        self._uses[key] = used_before + 1
        within_free = used_before < free_quota
        return {
            "user_id": user_id,
            "entry_id": entry_id,
            "period": period,
            "use_number": used_before + 1,
            "free_quota": free_quota,
            "within_free_quota": within_free,
            "free_remaining": max(0, free_quota - (used_before + 1)),
        }

    def reset_user(self, user_id: str) -> int:
        """Drop all ledger rows for a user. Returns rows removed."""
        doomed = [k for k in self._uses if k[0] == user_id]
        for k in doomed:
            del self._uses[k]
        return len(doomed)

    def to_dict(self) -> Dict:
        return {
            f"{u}\x1f{e}\x1f{p}": n for (u, e, p), n in self._uses.items()
        }

    @staticmethod
    def from_dict(raw: Dict) -> "UsageLedger":
        ledger = UsageLedger()
        for k, n in (raw or {}).items():
            parts = k.split("\x1f")
            if len(parts) == 3:
                ledger._uses[(parts[0], parts[1], parts[2])] = int(n)
        return ledger

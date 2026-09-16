"""Honest priority lane: burst passes for genuine contention.

A burst pass buys priority queueing during REAL contention — nothing else.
The scarce resource during a cool-down is the single half-open probe slot;
a pass reserves it. That is the entire mechanism.

What passes NEVER do (by design, and tested):
- They cannot open a circuit, manufacture contention, or change metering.
- Presenting a pass while circuits are closed changes nothing and consumes
  nothing — passes are worthless without genuine contention, on purpose.
- User-facing language never claims system overload: refusals say "cooling
  down after '<real reason>'" and name the priority pass explicitly. There
  is no overload theater.

Selling passes is outside this module (a payment provider does that); the
wallet records an operator ``note`` (e.g. a payment reference) per pass.
"""

from __future__ import annotations

import json
import os
import secrets
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from levi.governor.meter import governor_home


@dataclass
class BurstPass:
    pass_id: str = ""
    issued_at: float = 0.0
    expires_at: float = 0.0
    uses_total: int = 1
    uses_remaining: int = 1
    scope: str = "*"  # "*" or an exact scope like "provider:openai"
    note: str = ""  # operator note, e.g. a payment reference

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "BurstPass":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})

    def covers(self, scope: str) -> bool:
        return self.scope == "*" or self.scope == scope


class PassWallet:
    """Entitlement store for burst passes. Knows nothing about circuits."""

    def __init__(
        self,
        home: "str | os.PathLike[str] | None" = None,
        clock=time.time,
    ) -> None:
        self._dir = governor_home(home)
        self._file = self._dir / "passes.json"
        self._clock = clock
        self._passes: dict[str, BurstPass] = {}
        self._load()

    # -- persistence ----------------------------------------------------
    def _load(self) -> None:
        if not self._file.exists():
            return
        try:
            raw = json.loads(self._file.read_text(encoding="utf-8"))
            self._passes = {
                pid: BurstPass.from_dict(p)
                for pid, p in raw.items()
                if isinstance(p, dict)
            }
        except (json.JSONDecodeError, OSError, TypeError):
            self._passes = {}  # corrupt wallet: no passes honored, never crash

    def _save(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        tmp = self._file.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {pid: p.to_dict() for pid, p in self._passes.items()},
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        os.chmod(tmp, 0o600)
        os.replace(tmp, self._file)

    # -- issuing (the monetization seam) --------------------------------
    def issue(
        self,
        scope: str = "*",
        uses: int = 1,
        ttl_seconds: float = 86400.0,
        note: str = "",
    ) -> BurstPass:
        """Create a pass. Called when a pass is sold/granted (operator action)."""
        if uses <= 0:
            raise ValueError("uses must be positive")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        now = self._clock()
        bp = BurstPass(
            pass_id="bp_" + secrets.token_hex(8),
            issued_at=now,
            expires_at=now + ttl_seconds,
            uses_total=int(uses),
            uses_remaining=int(uses),
            scope=str(scope or "*"),
            note=str(note or ""),
        )
        self._passes[bp.pass_id] = bp
        self._save()
        return bp

    # -- redemption ------------------------------------------------------
    def get(self, pass_id: str) -> BurstPass | None:
        return self._passes.get(pass_id)

    def redeemable(self, pass_id: str, scope: str) -> tuple[bool, str]:
        bp = self._passes.get(pass_id)
        now = self._clock()
        if bp is None:
            return False, f"unknown pass '{pass_id}'"
        if now >= bp.expires_at:
            return False, f"pass '{pass_id}' expired"
        if bp.uses_remaining <= 0:
            return False, f"pass '{pass_id}' has no uses left"
        if not bp.covers(scope):
            return False, f"pass '{pass_id}' does not cover '{scope}'"
        return True, "ok"

    def redeem(self, pass_id: str, scope: str) -> tuple[bool, str]:
        """Consume one use. Only called during genuine contention."""
        ok, reason = self.redeemable(pass_id, scope)
        if not ok:
            return False, reason
        bp = self._passes[pass_id]
        bp.uses_remaining -= 1
        self._save()
        return True, "ok"

    def refund(self, pass_id: str, n: int = 1) -> None:
        bp = self._passes.get(pass_id)
        if bp is None:
            return
        bp.uses_remaining = min(bp.uses_total, bp.uses_remaining + max(n, 0))
        self._save()

    def list_active(self) -> list[BurstPass]:
        now = self._clock()
        return sorted(
            (
                p
                for p in self._passes.values()
                if p.expires_at > now and p.uses_remaining > 0
            ),
            key=lambda p: p.expires_at,
        )

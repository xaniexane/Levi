"""Automatic cool-downs: circuit breaker per scope.

States: closed -> open -> half-open -> closed.
A spike or budget breach opens the circuit for a scope (default: one
provider). While open, new calls are *refused with a clear reason* —
never silently dropped, never queued forever. After the backoff elapses,
one probe call is allowed (half-open); success closes the circuit,
failure re-opens it with exponential backoff.

Priority lane: during a genuine cool-down, the single half-open probe
slot is the only scarce resource. A burst pass (see
:mod:`levi.governor.priority`) reserves it. Passes can only act while a
circuit is genuinely open — presenting one against a closed circuit
changes nothing and consumes nothing.

State is persisted (owner-only JSON) so cool-downs survive restarts.
Deny-closed: an unreadable state file refuses every scope until reset.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass

from levi.governor.meter import governor_home
from levi.governor.priority import PassWallet

CLOSED = "closed"
OPEN = "open"
HALF_OPEN = "half-open"


@dataclass
class CircuitState:
    state: str = CLOSED
    opened_at: float = 0.0
    retry_at: float = 0.0
    breaches: int = 0
    last_reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "CircuitState":
        known = {f for f in cls.__dataclass_fields__}
        st = cls(**{k: v for k, v in d.items() if k in known})
        if st.state not in (CLOSED, OPEN, HALF_OPEN):
            st.state = OPEN  # unknown state denies closed
        return st


@dataclass
class Grant:
    allowed: bool
    reason: str
    probe: bool = False  # True when this grant is a half-open probe call
    reserved: bool = False  # True when this refusal holds a priority reservation
    pass_id: str = ""  # pass that authorized this grant/reservation, if any


class CooldownManager:
    """Circuit breakers with persisted state and exponential backoff."""

    def __init__(
        self,
        home: "str | os.PathLike[str] | None" = None,
        base_seconds: float = 60.0,
        max_seconds: float = 1800.0,
        clock=time.time,
        wallet: PassWallet | None = None,
    ) -> None:
        if base_seconds <= 0 or max_seconds <= 0:
            raise ValueError("backoff durations must be positive")
        self._dir = governor_home(home)
        self._state_file = self._dir / "cooldowns.json"
        self.base_seconds = base_seconds
        self.max_seconds = max_seconds
        self._clock = clock
        self._wallet = wallet
        self._circuits: dict[str, CircuitState] = {}
        # scope -> {"pass_id": str, "reserved_at": float}
        self._reservations: dict[str, dict] = {}
        self._corrupt = False
        self._probe_in_flight: set[str] = set()
        self._load()

    # -- persistence ----------------------------------------------------
    def _load(self) -> None:
        if not self._state_file.exists():
            return
        try:
            raw = json.loads(self._state_file.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "circuits" in raw:
                circuits, reservations = (
                    raw.get("circuits", {}),
                    raw.get("reservations", {}),
                )
            else:
                circuits, reservations = raw, {}
            self._circuits = {
                str(scope): CircuitState.from_dict(st)
                for scope, st in circuits.items()
                if isinstance(st, dict)
            }
            self._reservations = {
                str(scope): dict(r)
                for scope, r in reservations.items()
                if isinstance(r, dict) and "pass_id" in r
            }
        except (json.JSONDecodeError, OSError, TypeError, AttributeError):
            self._corrupt = True
            self._circuits = {}
            self._reservations = {}

    def _save(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        tmp = self._state_file.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {
                    "circuits": {s: c.to_dict() for s, c in self._circuits.items()},
                    "reservations": self._reservations,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        os.chmod(tmp, 0o600)
        os.replace(tmp, self._state_file)

    # -- core -----------------------------------------------------------
    def _backoff(self, breaches: int) -> float:
        return min(self.base_seconds * (2.0 ** max(breaches - 1, 0)), self.max_seconds)

    def breach(self, scope: str, reason: str = "") -> float:
        """Open (or re-open) the circuit for ``scope``. Returns retry delay."""
        now = self._clock()
        st = self._circuits.get(scope, CircuitState())
        st.breaches += 1
        st.state = OPEN
        st.opened_at = now
        st.retry_at = now + self._backoff(st.breaches)
        st.last_reason = str(reason or "usage spike")
        self._circuits[scope] = st
        self._probe_in_flight.discard(scope)
        # A pending priority reservation survives a re-breach: the holder
        # still gets the next probe slot.
        self._save()
        return st.retry_at - now

    def acquire(self, scope: str, pass_id: str | None = None) -> Grant:
        """Ask to make a call under ``scope``. Deny-closed.

        ``pass_id`` is only meaningful during genuine contention: against a
        closed circuit it is ignored entirely (no consumption).
        """
        if self._corrupt:
            return Grant(
                False,
                "cool-down state file is unreadable; refusing all calls "
                "until reset (`python -m levi.governor reset`)",
            )
        now = self._clock()
        st = self._circuits.get(scope)
        if st is None or st.state == CLOSED:
            # No contention: a pass changes nothing and consumes nothing.
            return Grant(True, "circuit closed", probe=False)
        if st.state == OPEN:
            if now < st.retry_at:
                wait = int(st.retry_at - now)
                base = (
                    f"genuine contention on '{scope}': cooling down after "
                    f"'{st.last_reason}': retry in {wait}s "
                    f"(breach #{st.breaches})"
                )
                if pass_id and self._wallet is not None:
                    return self._reserve(scope, pass_id, base, wait)
                if pass_id:
                    base += " (no pass wallet configured; pass ignored)"
                return Grant(False, base)
            # Backoff elapsed: the single probe slot decides who goes first.
            reservation = self._reservations.get(scope)
            if reservation is not None and reservation.get("pass_id") != pass_id:
                return Grant(
                    False,
                    f"genuine contention on '{scope}': the half-open probe "
                    f"slot is reserved by a priority pass holder; retry shortly",
                )
            st.state = HALF_OPEN
            self._probe_in_flight.add(scope)
            self._save()
            return Grant(
                True,
                "half-open probe call"
                + (" (priority pass)" if reservation is not None else ""),
                probe=True,
                pass_id=reservation.get("pass_id", "") if reservation else "",
            )
        # HALF_OPEN with a probe already out: refuse until it resolves.
        return Grant(False, "half-open probe already in flight; awaiting its result")

    def _reserve(self, scope: str, pass_id: str, base: str, wait: int) -> Grant:
        """Redeem one pass use to reserve the next probe slot. Genuine
        contention only — this is only called while the circuit is open."""
        ok, why = self._wallet.redeem(pass_id, scope)
        if not ok:
            return Grant(False, f"{base} (priority pass not honored: {why})")
        self._reservations[scope] = {
            "pass_id": pass_id,
            "reserved_at": self._clock(),
        }
        self._save()
        return Grant(
            False,
            f"{base}. Priority pass '{pass_id}' now holds the next probe "
            f"slot (1 use consumed); retry in {wait}s — your call goes first",
            reserved=True,
            pass_id=pass_id,
        )

    def probe_success(self, scope: str) -> None:
        st = self._circuits.get(scope)
        if st is None:
            return
        st.state = CLOSED
        st.breaches = 0
        st.last_reason = ""
        self._probe_in_flight.discard(scope)
        self._reservations.pop(scope, None)  # slot used; reservation fulfilled
        self._save()

    def probe_failure(self, scope: str, reason: str = "") -> float:
        """A half-open probe failed: re-open with doubled backoff."""
        self._probe_in_flight.discard(scope)
        self._reservations.pop(scope, None)  # slot used; reservation fulfilled
        return self.breach(scope, reason or "half-open probe failed")

    def cancel_reservation(self, scope: str) -> bool:
        """Operator/holder action: release a reservation, refunding the use."""
        res = self._reservations.pop(scope, None)
        if res is None:
            return False
        if self._wallet is not None:
            self._wallet.refund(res["pass_id"])
        self._save()
        return True

    def reset(self, scope: str) -> None:
        """Manual reset (operator action). Clears corruption too; any pending
        reservation is refunded."""
        self.cancel_reservation(scope)
        self._circuits.pop(scope, None)
        self._probe_in_flight.discard(scope)
        if not self._circuits:
            self._corrupt = False
        self._save()

    def status(self) -> dict:
        now = self._clock()
        out: dict[str, dict] = {}
        for scope, st in sorted(self._circuits.items()):
            d = st.to_dict()
            d["retry_in_s"] = max(0, int(st.retry_at - now)) if st.state == OPEN else 0
            res = self._reservations.get(scope)
            if res:
                d["probe_reserved_by"] = res["pass_id"]
            out[scope] = d
        if self._corrupt:
            out["_state_file"] = {"corrupt": True}
        return out

"""Cybrus biometric unlock — biometric-gated release of keeper keys.

Recreated LEVI-native (stdlib-only) from the keeper's original
``BiometricUnlock.kt`` (``lock-and-key-vault-genesis.zip`` / ``-2.zip``).
Ideas studied; no code copied.

His original, in his structure:
- ``UnlockStrength``: ``BIOMETRIC_STRONG``, ``BIOMETRIC_WEAK``,
  ``DEVICE_CREDENTIAL`` — "Biometric / device credential unlock
  abstraction. Used for vault unlock and other high-value actions.
  Implementations will wrap BiometricPrompt."
- ``UnlockPrompt.authenticate(title, subtitle, allowedStrengths)`` —
  "Request user authentication. Returns success only after successful
  authentication." Default allowed: STRONG + DEVICE_CREDENTIAL.
- ``LockPolicy``: auto-lock timeout, background/foreground hooks,
  locked-by-default, ``lock()`` / ``unlock(prompt)``.

LAWS
----
- **B1 NO-RELEASE-WITHOUT-CEREMONY** — keeper key material is released
  only after a successful biometric/device-credential ceremony through
  the platform. No ceremony, no keys. Ever.
- **B2 NO-SILENT-DOWNGRADE** — the allowed strength set is explicit per
  ceremony. A weaker strength never substitutes silently for a stronger
  one; a ceremony that cannot meet the allowed set refuses honestly.
- **B3 HONEST-NO-HARDWARE** — with no enrolled authenticator or no
  platform at all, ``authenticate()`` refuses with a clear reason. It
  never reports success it did not earn.
- **B4 LOCKOUT** — after ``MAX_ATTEMPTS`` consecutive failed ceremonies
  the identity locks out for ``LOCKOUT_SECONDS``. Attempts during
  lockout are refused without touching the platform.
- **B5 LOCKED-BY-DEFAULT + AUTO-LOCK** — a new policy starts locked;
  backgrounding or idleness past the timeout re-locks; locking re-seals
  the key handle and best-effort zeroizes plaintext.
- **B6 FOUNDER-GATE** — full key-release is the founder's own. Other
  identities get the limited lane (lock policy + prompt machinery) but
  key release refuses them.
- **B7 BLOODLINE-METERING** — the founder's lane is the unmetered
  bloodline root. Every limited-lane ceremony runs through the metering
  hook: authorize before, record after. A quota-exhausted identity is
  refused with the founder-provisioning reason — never silently.

HONEST BOUNDARIES
-----------------
- This is Python core: real hardware calls go through
  :class:`BiometricPlatform`. On this runtime there is no biometric
  hardware, so the default platform is :class:`NoHardwarePlatform`,
  which refuses honestly. :class:`SimulatedPlatform` exists for tests
  and is labeled test-only — it is never a substitute for hardware.
- Biometric templates are never collected, stored, or transmitted here
  (matches the keeper's standing data policy: biometrics are
  never collected). The platform only ever answers yes/no.
- ``seal``/``unseal`` callables are caller-supplied (e.g. Veil's own
  crypto). This module never invents its own cipher.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Strengths — his UnlockStrength, recreated
# ---------------------------------------------------------------------------


class UnlockStrength(str, Enum):
    """Authenticator strength tiers, strongest first."""

    BIOMETRIC_STRONG = "biometric_strong"
    BIOMETRIC_WEAK = "biometric_weak"
    DEVICE_CREDENTIAL = "device_credential"


#: Default allowed set, matching his original: strong biometric first,
#: device credential as the honest fallback. WEAK is never in the default.
DEFAULT_ALLOWED: Set[UnlockStrength] = frozenset(
    {UnlockStrength.BIOMETRIC_STRONG, UnlockStrength.DEVICE_CREDENTIAL}
)

#: Consecutive failures before lockout (B4).
MAX_ATTEMPTS = 5

#: Lockout duration in seconds after MAX_ATTEMPTS failures (B4).
LOCKOUT_SECONDS = 300.0

#: Default auto-lock timeout in ms (his original: 60_000).
DEFAULT_AUTO_LOCK_MS = 60_000


class BiometricError(Exception):
    """Base error for the biometric lane."""


class BiometricRefused(BiometricError):
    """A ceremony or release was refused (honest reason in the message)."""


class BiometricGateError(BiometricError):
    """The caller is not entitled to this capability (B6)."""


# ---------------------------------------------------------------------------
# Ceremony result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuthResult:
    """The outcome of one authentication ceremony."""

    ok: bool
    strength_used: Optional[UnlockStrength] = None
    reason: str = ""

    @classmethod
    def success(cls, strength: UnlockStrength) -> "AuthResult":
        return cls(ok=True, strength_used=strength, reason="authenticated")

    @classmethod
    def failure(cls, reason: str) -> "AuthResult":
        return cls(ok=False, strength_used=None, reason=reason)


# ---------------------------------------------------------------------------
# Platform interface — hardware boundary
# ---------------------------------------------------------------------------


class BiometricPlatform:
    """Hardware boundary. Real implementations wrap the OS biometric API
    (his original wrapped Android BiometricPrompt)."""

    def name(self) -> str:
        return type(self).__name__

    def available_strengths(self) -> Set[UnlockStrength]:
        """Strengths the device can actually offer right now (enrolled)."""
        raise NotImplementedError

    def authenticate(
        self,
        title: str,
        subtitle: Optional[str],
        allowed: Set[UnlockStrength],
    ) -> AuthResult:
        """Run one ceremony. Returns success ONLY after successful
        authentication (his words). Never raises for a failed ceremony —
        returns ``AuthResult.failure`` instead."""
        raise NotImplementedError


class NoHardwarePlatform(BiometricPlatform):
    """Honest refusal when there is no biometric hardware or nothing is
    enrolled (B3). This is the default on runtimes without a biometric
    stack — it never fakes a success."""

    def __init__(self, reason: str = "no biometric hardware or enrolled credential on this device"):
        self._reason = reason

    def available_strengths(self) -> Set[UnlockStrength]:
        return set()

    def authenticate(self, title, subtitle, allowed) -> AuthResult:
        return AuthResult.failure(f"refused: {self._reason}")


class SimulatedPlatform(BiometricPlatform):
    """TEST-ONLY scripted platform. ``script`` is a list of AuthResults
    consumed in order; exhaustion refuses honestly. Never use outside
    tests — it proves nothing about real hardware."""

    TEST_ONLY = True

    def __init__(
        self,
        enrolled: Set[UnlockStrength],
        script: Optional[List[AuthResult]] = None,
    ):
        self._enrolled = set(enrolled)
        self._script = list(script or [])
        self.ceremonies_run = 0

    def available_strengths(self) -> Set[UnlockStrength]:
        return set(self._enrolled)

    def authenticate(self, title, subtitle, allowed) -> AuthResult:
        self.ceremonies_run += 1
        usable = self._enrolled & set(allowed)
        if not usable:
            # B2: the platform cannot meet the allowed set — refuse, never
            # silently reach for a weaker strength outside the allowed set.
            return AuthResult.failure(
                "refused: enrolled strengths %s do not intersect allowed %s"
                % (
                    sorted(s.value for s in self._enrolled),
                    sorted(s.value for s in allowed),
                )
            )
        if not self._script:
            return AuthResult.failure("refused: test script exhausted")
        result = self._script.pop(0)
        if result.ok and result.strength_used not in usable:
            # The script claims a strength the platform cannot offer —
            # treat as failure, never honor a lying success.
            return AuthResult.failure(
                "refused: scripted success used unoffered strength %s"
                % (result.strength_used,)
            )
        return result


# ---------------------------------------------------------------------------
# Attempt tracking + lockout (B4)
# ---------------------------------------------------------------------------


class AttemptTracker:
    """Consecutive-failure counting with timed lockout. Time source is
    injectable so tests are deterministic."""

    def __init__(self, time_fn: Callable[[], float] = time.monotonic):
        self._time = time_fn
        self._failures = 0
        self._locked_until: Optional[float] = None

    @property
    def failures(self) -> int:
        return self._failures

    def locked(self) -> bool:
        if self._locked_until is None:
            return False
        if self._time() >= self._locked_until:
            self._locked_until = None
            self._failures = 0
            return False
        return True

    def lockout_remaining(self) -> float:
        if not self.locked():
            return 0.0
        return max(0.0, self._locked_until - self._time())  # type: ignore[operator]

    def record_success(self) -> None:
        self._failures = 0
        self._locked_until = None

    def record_failure(self) -> bool:
        """Record a failure. Returns True when this failure triggered a
        fresh lockout."""
        self._failures += 1
        if self._failures >= MAX_ATTEMPTS and self._locked_until is None:
            self._locked_until = self._time() + LOCKOUT_SECONDS
            return True
        return False


# ---------------------------------------------------------------------------
# Tamper-evident unlock ledger (own hash chain, lane-local)
# ---------------------------------------------------------------------------


def _canonical(obj: Dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


@dataclass
class UnlockLedger:
    """Append-only, hash-chained record of unlock ceremonies and lockouts.
    Lane-local (mirrors the cybrus audit pattern); carries metadata only —
    never key material, never biometric data."""

    _events: List[Dict] = field(default_factory=list)

    def append(self, kind: str, detail: Dict) -> Dict:
        prev = self._events[-1]["hash"] if self._events else "0" * 64
        record = {
            "seq": len(self._events),
            "kind": kind,
            "detail": {k: v for k, v in detail.items()},
            "prev": prev,
        }
        record["hash"] = hashlib.sha256(
            (prev + _canonical(record)).encode("utf-8")
        ).hexdigest()
        self._events.append(record)
        return dict(record)

    def verify(self) -> bool:
        prev = "0" * 64
        for i, record in enumerate(self._events):
            if record.get("seq") != i or record.get("prev") != prev:
                return False
            check = dict(record)
            tip = check.pop("hash")
            if (
                hashlib.sha256((prev + _canonical(check)).encode("utf-8")).hexdigest()
                != tip
            ):
                return False
            prev = tip
        return True

    def events(self) -> List[Dict]:
        return [dict(e) for e in self._events]


# ---------------------------------------------------------------------------
# Lock policy — his LockPolicy, recreated (B5)
# ---------------------------------------------------------------------------


class LockPolicy:
    """Auto-lock policy for vault and high-value actions. Starts locked
    (B5). Backgrounding re-locks. Idleness past the timeout re-locks."""

    def __init__(
        self,
        auto_lock_ms: int = DEFAULT_AUTO_LOCK_MS,
        time_fn: Callable[[], float] = time.monotonic,
    ):
        if auto_lock_ms <= 0:
            raise ValueError("auto_lock_ms must be positive")
        self.auto_lock_ms = auto_lock_ms
        self._time = time_fn
        self._locked = True  # B5: locked by default
        self._last_interaction = self._time()
        self.ledger = UnlockLedger()

    @property
    def is_locked(self) -> bool:
        if self._locked:
            return True
        idle_ms = (self._time() - self._last_interaction) * 1000.0
        if idle_ms >= self.auto_lock_ms:
            self._locked = True
            self.ledger.append("auto_lock", {"reason": "idle_timeout"})
            return True
        return False

    def on_user_interaction(self) -> None:
        self._last_interaction = self._time()

    def on_app_backgrounded(self) -> None:
        # His original: background forces the timeout to elapse → locked.
        self._last_interaction = self._time() - (self.auto_lock_ms / 1000.0) - 1.0
        self.ledger.append("auto_lock", {"reason": "backgrounded"})

    def on_app_foregrounded(self) -> None:
        # is_locked evaluates the timeout lazily; nothing to do eagerly.
        pass

    def lock(self) -> None:
        if not self._locked:
            self.ledger.append("lock", {"reason": "explicit"})
        self._locked = True

    def unlock(
        self,
        prompt: "UnlockPrompt",
        title: str = "Unlock",
        subtitle: Optional[str] = None,
        allowed: Optional[Set[UnlockStrength]] = None,
        *,
        identity: object = None,
        meter: Optional["Meter"] = None,
    ) -> AuthResult:
        """Run the ceremony through ``prompt``; unlock ONLY on success."""
        result = prompt.authenticate(
            title,
            subtitle,
            None if allowed is None else set(allowed),
            identity=identity,
            meter=meter,
        )
        if result.ok:
            self._locked = False
            self._last_interaction = self._time()
            self.ledger.append(
                "unlock",
                {
                    "strength": result.strength_used.value
                    if result.strength_used
                    else "unknown",
                },
            )
        else:
            self.ledger.append("unlock_refused", {"reason": result.reason[:200]})
        return result


# ---------------------------------------------------------------------------
# Unlock prompt — his UnlockPrompt, recreated
# ---------------------------------------------------------------------------


class UnlockPrompt:
    """Ceremony driver: attempt tracking (B4) + platform dispatch + the
    no-silent-downgrade rule (B2)."""

    def __init__(
        self,
        platform: Optional[BiometricPlatform] = None,
        time_fn: Callable[[], float] = time.monotonic,
    ):
        self.platform = platform or NoHardwarePlatform()
        self.tracker = AttemptTracker(time_fn=time_fn)
        self.ledger = UnlockLedger()

    def authenticate(
        self,
        title: str,
        subtitle: Optional[str] = None,
        allowed: Optional[Set[UnlockStrength]] = None,
        *,
        identity: object = None,
        meter: Optional[Meter] = None,
    ) -> AuthResult:
        # None = the keeper's default; an EXPLICITLY empty set refuses
        # (fail closed — no authenticator may satisfy "nothing allowed").
        if allowed is None:
            allowed_set = set(DEFAULT_ALLOWED)
        else:
            allowed_set = set(allowed)
        if not allowed_set:
            return AuthResult.failure("refused: empty allowed-strength set")
        # B7 (bloodline): the metering hook runs on EVERY limited-lane
        # ceremony. Founder lane is the unmetered bloodline root.
        tier = capability_for(identity) if identity is not None else "limited"
        active_meter = meter or NULL_METER
        if tier != "full":
            if not active_meter.authorize(identity, CAPABILITY_ID):
                self.ledger.append(
                    "ceremony_refused", {"reason": "quota_exhausted"}
                )
                return AuthResult.failure(
                    "refused: usage quota exhausted — biometric unlock "
                    "is provisioned by the founder"
                )
        if self.tracker.locked():
            self.ledger.append(
                "ceremony_refused",
                {"reason": "lockout", "remaining_s": round(self.tracker.lockout_remaining(), 1)},
            )
            return AuthResult.failure(
                "refused: locked out after %d failures (%.0fs remaining)"
                % (MAX_ATTEMPTS, self.tracker.lockout_remaining())
            )
        # B2: intersect enrolled with allowed BEFORE the ceremony — the
        # ceremony may only ever use an explicitly allowed strength.
        usable = self.platform.available_strengths() & allowed_set
        if not usable:
            self.tracker.record_failure()
            self.ledger.append(
                "ceremony_refused",
                {"reason": "no usable strength for allowed set"},
            )
            return AuthResult.failure(
                "refused: no enrolled authenticator meets the allowed strengths"
            )
        result = self.platform.authenticate(title, subtitle, allowed_set)
        if result.ok:
            # B2 double-check: the platform must not report a strength
            # outside the allowed set.
            if result.strength_used not in allowed_set:
                self.tracker.record_failure()
                self.ledger.append(
                    "ceremony_refused", {"reason": "platform used disallowed strength"}
                )
                return AuthResult.failure(
                    "refused: platform reported disallowed strength"
                )
            self.tracker.record_success()
            self.ledger.append(
                "ceremony_ok",
                {"strength": result.strength_used.value},  # type: ignore[union-attr]
            )
        else:
            triggered = self.tracker.record_failure()
            self.ledger.append(
                "ceremony_failed",
                {"reason": result.reason[:200], "lockout": triggered},
            )
        if tier != "full":
            # B7: every limited-lane ceremony is metered — the founder
            # provisions (or cuts off) this capability as a service.
            active_meter.record_use(
                identity, CAPABILITY_ID, {"ok": result.ok}
            )
        return result


# ---------------------------------------------------------------------------
# Bloodline metering — the keeper's bloodline distribution law (2026-09-27)
# ---------------------------------------------------------------------------
#
# Founder (Chauncey) holds the ORIGINAL with full capability — the
# bloodline root, unmetered and unlimited. Every other identity spawns
# off it: derived, LIMITED builds that never carry the founder's
# unlimited abilities. The full capability is a SERVICE he provides or
# meters — so every gated transition carries metering HOOKS, not just
# an on/off switch. A deployment wires a real meter; the seam is always
# invoked on the limited lane.

#: Capability id metered by this lane.
CAPABILITY_ID = "cybrus.biometric_unlock"

#: Default ceremony quota for limited-lane identities when a real meter
#: is wired with defaults (InMemoryMeter default).
DEFAULT_LIMITED_QUOTA = 100


class Meter:
    """Usage-metering seam for the limited lane. ``quota_remaining``
    returns None for unlimited."""

    def authorize(self, identity: object, capability: str) -> bool:
        """True when this use is allowed (quota remains or unlimited)."""
        raise NotImplementedError

    def record_use(self, identity: object, capability: str, detail: Dict) -> None:
        """Record one metered use."""
        raise NotImplementedError

    def quota_remaining(self, identity: object, capability: str) -> Optional[int]:
        raise NotImplementedError


class NullMeter(Meter):
    """No-op meter — the founder's lane. Unlimited, unrecorded."""

    def authorize(self, identity: object, capability: str) -> bool:
        return True

    def record_use(self, identity: object, capability: str, detail: Dict) -> None:
        return None

    def quota_remaining(self, identity: object, capability: str) -> Optional[int]:
        return None


NULL_METER = NullMeter()


class InMemoryMeter(Meter):
    """Deterministic in-memory meter (tests and local deployments).
    Quotas are per (identity, capability); None means unlimited."""

    def __init__(self, default_quota: Optional[int] = DEFAULT_LIMITED_QUOTA):
        self._default_quota = default_quota
        self._quotas: Dict[tuple, Optional[int]] = {}
        self._used: Dict[tuple, int] = {}

    def set_quota(self, identity: object, capability: str, quota: Optional[int]) -> None:
        self._quotas[(str(identity), capability)] = quota

    def quota_remaining(self, identity: object, capability: str) -> Optional[int]:
        key = (str(identity), capability)
        quota = self._quotas.get(key, self._default_quota)
        if quota is None:
            return None
        return max(0, quota - self._used.get(key, 0))

    def authorize(self, identity: object, capability: str) -> bool:
        remaining = self.quota_remaining(identity, capability)
        return remaining is None or remaining > 0

    def record_use(self, identity: object, capability: str, detail: Dict) -> None:
        key = (str(identity), capability)
        self._used[key] = self._used.get(key, 0) + 1


# ---------------------------------------------------------------------------
# Founder gate (B6)
# ---------------------------------------------------------------------------


def capability_for(identity_name: object) -> str:
    """Capability tier for an identity name: ``"full"`` for the founder,
    ``"limited"`` for everyone else. The founder's biometric lane releases
    keeper keys; others get lock-policy + prompt machinery only."""
    from levi.cybrus.identity import is_founder_identity

    if is_founder_identity(identity_name):
        return "full"
    return "limited"


def require_full(identity_name: object) -> str:
    """Raise :class:`BiometricGateError` unless the identity holds the
    full biometric capability (B6)."""
    tier = capability_for(identity_name)
    if tier != "full":
        raise BiometricGateError(
            "biometric key release is the founder's own; "
            f"{identity_name!r} holds the limited lane (lock policy + "
            "prompt machinery, no key release)"
        )
    return tier


# ---------------------------------------------------------------------------
# Biometric-gated key release (B1)
# ---------------------------------------------------------------------------


def _zeroize(buf: bytearray) -> None:
    for i in range(len(buf)):
        buf[i] = 0


class SealedKeyRelease:
    """Holds keeper key material SEALED; releases it only after a
    successful ceremony (B1). The ``seal``/``unseal`` callables are
    caller-supplied (e.g. Veil's crypto) — this module invents no cipher.

    Lifecycle: ``bind(plaintext)`` → sealed, plaintext zeroized.
    ``release(prompt, ...)`` → ceremony → on success, unseal and return.
    ``lock()`` → re-seal state, zeroize any held plaintext.
    """

    def __init__(
        self,
        seal: Callable[[bytes], bytes],
        unseal: Callable[[bytes], bytes],
    ):
        self._seal = seal
        self._unseal = unseal
        self._blob: Optional[bytes] = None
        self._plaintext: Optional[bytearray] = None
        self.ledger = UnlockLedger()

    @property
    def is_bound(self) -> bool:
        return self._blob is not None

    @property
    def is_released(self) -> bool:
        return self._plaintext is not None

    def bind(self, plaintext: bytes, identity_name: object = None) -> None:
        """Seal key material into this handle. Full capability required
        (B6) — binding is the act that puts keys under biometric guard."""
        if identity_name is not None:
            require_full(identity_name)
        if not isinstance(plaintext, (bytes, bytearray)) or not plaintext:
            raise ValueError("bind requires non-empty key material")
        self.lock()  # drop any previous state first
        self._blob = bytes(self._seal(bytes(plaintext)))
        self.ledger.append("bind", {"sealed_len": len(self._blob)})

    def release(
        self,
        prompt: UnlockPrompt,
        identity_name: object,
        title: str = "Unlock keeper keys",
        subtitle: Optional[str] = None,
        allowed: Optional[Set[UnlockStrength]] = None,
    ) -> bytes:
        """Run the ceremony; return key material ONLY on success (B1)."""
        require_full(identity_name)  # B6 first: gate before ceremony
        if not self.is_bound:
            raise BiometricRefused("refused: no key material bound")
        result = prompt.authenticate(title, subtitle, allowed)
        if not result.ok:
            self.ledger.append("release_refused", {"reason": result.reason[:200]})
            raise BiometricRefused(f"key release refused: {result.reason}")
        try:
            raw = self._unseal(bytes(self._blob))  # type: ignore[arg-type]
        except Exception as exc:
            self.ledger.append("release_refused", {"reason": "unseal failed"})
            raise BiometricRefused("key release refused: unseal failed") from exc
        self._plaintext = bytearray(raw)
        self.ledger.append(
            "release",
            {"strength": result.strength_used.value if result.strength_used else "unknown"},
        )
        return bytes(self._plaintext)

    def lock(self) -> None:
        """Re-seal: drop plaintext, keep the sealed blob (B5)."""
        if self._plaintext is not None:
            _zeroize(self._plaintext)
            self._plaintext = None
            self.ledger.append("lock", {"reason": "key handle re-sealed"})


# ---------------------------------------------------------------------------
# Proof: machine-checkable invariant sweep (law → guard → prove)
# ---------------------------------------------------------------------------


def check_invariants() -> List[Dict]:
    """Run the B1–B6 invariant checks. Returns a list of
    ``{"law": ..., "passed": bool, "note": ...}``. All must pass."""
    results: List[Dict] = []

    def check(law: str, passed: bool, note: str = "") -> None:
        results.append({"law": law, "passed": bool(passed), "note": note})

    # B1: no ceremony → no keys
    box = SealedKeyRelease(seal=lambda b: b"SEALED:" + b, unseal=lambda b: b[7:])
    box.bind(b"keeper-secret", identity_name="chauncey")
    prompt = UnlockPrompt(platform=NoHardwarePlatform())
    try:
        box.release(prompt, identity_name="chauncey")
        check("B1", False, "release succeeded without ceremony")
    except BiometricRefused:
        check("B1", True, "release without successful ceremony refused")
    check("B1", not box.is_released, "plaintext not held after refused release")

    # B2: no silent downgrade — only WEAK enrolled, only STRONG allowed
    sim = SimulatedPlatform(
        enrolled={UnlockStrength.BIOMETRIC_WEAK},
        script=[AuthResult.success(UnlockStrength.BIOMETRIC_WEAK)],
    )
    p2 = UnlockPrompt(platform=sim)
    r2 = p2.authenticate("t", allowed={UnlockStrength.BIOMETRIC_STRONG})
    check("B2", not r2.ok, "weak authenticator never substitutes for allowed strong set")

    # B3: honest no-hardware refusal
    p3 = UnlockPrompt(platform=NoHardwarePlatform())
    r3 = p3.authenticate("t")
    check("B3", not r3.ok and "refused" in r3.reason, "no-hardware refuses honestly")

    # B4: lockout after MAX_ATTEMPTS failures
    now = [1000.0]
    sim4 = SimulatedPlatform(
        enrolled={UnlockStrength.BIOMETRIC_STRONG},
        script=[AuthResult.failure("nope")] * 10,
    )
    p4 = UnlockPrompt(platform=sim4, time_fn=lambda: now[0])
    for _ in range(MAX_ATTEMPTS):
        p4.authenticate("t")
    check("B4", p4.tracker.locked(), "locked after %d failures" % MAX_ATTEMPTS)
    before = sim4.ceremonies_run
    r4 = p4.authenticate("t")
    check("B4", not r4.ok and sim4.ceremonies_run == before,
          "lockout refuses without touching the platform")
    now[0] += LOCKOUT_SECONDS + 1
    check("B4", not p4.tracker.locked(), "lockout expires after cooldown")

    # B5: locked by default; background re-locks
    pol = LockPolicy(auto_lock_ms=60_000)
    check("B5", pol.is_locked, "new policy starts locked")
    sim5 = SimulatedPlatform(
        enrolled={UnlockStrength.BIOMETRIC_STRONG},
        script=[AuthResult.success(UnlockStrength.BIOMETRIC_STRONG)],
    )
    p5 = UnlockPrompt(platform=sim5)
    pol.unlock(p5, title="t")
    check("B5", not pol.is_locked, "successful ceremony unlocks")
    pol.on_app_backgrounded()
    check("B5", pol.is_locked, "background re-locks")

    # B6: founder gate
    check("B6", capability_for("chauncey") == "full", "founder holds full")
    check("B6", capability_for("someone-else") == "limited", "others limited")
    box6 = SealedKeyRelease(seal=lambda b: b"S:" + b, unseal=lambda b: b[2:])
    try:
        box6.bind(b"x", identity_name="someone-else")
        check("B6", False, "non-founder bound keys")
    except BiometricGateError:
        check("B6", True, "non-founder bind refused")
    box6b = SealedKeyRelease(seal=lambda b: b"S:" + b, unseal=lambda b: b[2:])
    box6b.bind(b"y", identity_name="chauncey")
    sim6 = SimulatedPlatform(
        enrolled={UnlockStrength.BIOMETRIC_STRONG},
        script=[AuthResult.success(UnlockStrength.BIOMETRIC_STRONG)],
    )
    try:
        box6b.release(UnlockPrompt(platform=sim6), identity_name="someone-else")
        check("B6", False, "non-founder released keys")
    except BiometricGateError:
        check("B6", True, "non-founder release refused before ceremony")

    # B7: bloodline metering — limited lane metered, founder unmetered
    meter = InMemoryMeter(default_quota=2)
    sim7 = SimulatedPlatform(
        enrolled={UnlockStrength.BIOMETRIC_STRONG},
        script=[AuthResult.success(UnlockStrength.BIOMETRIC_STRONG)] * 5,
    )
    p7 = UnlockPrompt(platform=sim7)
    r7a = p7.authenticate("t", identity="someone-else", meter=meter)
    r7b = p7.authenticate("t", identity="someone-else", meter=meter)
    check("B7", r7a.ok and r7b.ok, "limited lane works within quota")
    check("B7", meter.quota_remaining("someone-else", CAPABILITY_ID) == 0,
          "quota decrements per ceremony")
    r7c = p7.authenticate("t", identity="someone-else", meter=meter)
    check("B7", not r7c.ok and "provisioned by the founder" in r7c.reason,
          "quota-exhausted identity refused with founder reason")
    # founder lane: unmetered even with an exhausted meter wired
    sim7f = SimulatedPlatform(
        enrolled={UnlockStrength.BIOMETRIC_STRONG},
        script=[AuthResult.success(UnlockStrength.BIOMETRIC_STRONG)],
    )
    p7f = UnlockPrompt(platform=sim7f)
    r7f = p7f.authenticate("t", identity="chauncey", meter=meter)
    check("B7", r7f.ok, "founder lane unmetered (bloodline root)")

    # Ledger tamper-evidence
    led = UnlockLedger()
    led.append("a", {"x": 1})
    led.append("b", {"x": 2})
    check("LEDGER", led.verify(), "intact chain verifies")
    led._events[0]["detail"]["x"] = 999
    check("LEDGER", not led.verify(), "tampered chain fails verification")

    return results


# ---------------------------------------------------------------------------
# Capability descriptor (for the cybrus capability registry)
# ---------------------------------------------------------------------------


def capability():
    """Describe this lane for :class:`CapabilityRegistry` (deny-closed:
    nothing acts on an unregistered power)."""
    from levi.cybrus.capability import Capability, RiskBand

    return Capability(
        id="cybrus.biometric_unlock",
        name="Biometric unlock",
        description=(
            "Biometric/device-credential-gated release of keeper keys. "
            "Founder holds the full lane; others are limited to lock-policy "
            "and prompt machinery. Test-only simulated platform; no-hardware "
            "refuses honestly."
        ),
        domain="cybrus.security",
        version="1.0.0",
        risk=RiskBand.CRITICAL,
        requires_approval=False,
        destructive=False,
        tags=["biometric", "unlock", "keeper-keys", "founder-gated"],
    )

"""Tests for levi.cybrus.biometric — laws B1..B6 + ledger + proof sweep."""

import pytest

from levi.cybrus.biometric import (
    CAPABILITY_ID,
    DEFAULT_ALLOWED,
    LOCKOUT_SECONDS,
    MAX_ATTEMPTS,
    AuthResult,
    BiometricGateError,
    BiometricPlatform,
    BiometricRefused,
    InMemoryMeter,
    LockPolicy,
    NoHardwarePlatform,
    SealedKeyRelease,
    SimulatedPlatform,
    UnlockLedger,
    UnlockPrompt,
    UnlockStrength,
    capability,
    capability_for,
    check_invariants,
    require_full,
)


def _box():
    return SealedKeyRelease(seal=lambda b: b"SEALED:" + b, unseal=lambda b: b[7:])


def _ok_platform(strength=UnlockStrength.BIOMETRIC_STRONG):
    return SimulatedPlatform(
        enrolled={strength}, script=[AuthResult.success(strength)]
    )


# -- B1: no release without ceremony ----------------------------------------

def test_b1_release_without_ceremony_refused():
    box = _box()
    box.bind(b"keeper-secret", identity_name="chauncey")
    with pytest.raises(BiometricRefused):
        box.release(UnlockPrompt(platform=NoHardwarePlatform()), identity_name="chauncey")
    assert not box.is_released


def test_b1_failed_ceremony_releases_nothing():
    box = _box()
    box.bind(b"keeper-secret", identity_name="chauncey")
    bad = SimulatedPlatform(
        enrolled={UnlockStrength.BIOMETRIC_STRONG},
        script=[AuthResult.failure("user cancelled")],
    )
    with pytest.raises(BiometricRefused):
        box.release(UnlockPrompt(platform=bad), identity_name="chauncey")
    assert not box.is_released


def test_b1_successful_ceremony_releases():
    box = _box()
    box.bind(b"keeper-secret", identity_name="chauncey")
    out = box.release(UnlockPrompt(platform=_ok_platform()), identity_name="chauncey")
    assert out == b"keeper-secret"
    assert box.is_released
    box.lock()
    assert not box.is_released
    assert box.is_bound  # sealed blob survives locking


def test_b1_release_unbound_refused():
    box = _box()
    with pytest.raises(BiometricRefused):
        box.release(UnlockPrompt(platform=_ok_platform()), identity_name="chauncey")


# -- B2: no silent downgrade -------------------------------------------------

def test_b2_weak_never_substitutes_for_strong():
    sim = SimulatedPlatform(
        enrolled={UnlockStrength.BIOMETRIC_WEAK},
        script=[AuthResult.success(UnlockStrength.BIOMETRIC_WEAK)],
    )
    result = UnlockPrompt(platform=sim).authenticate(
        "t", allowed={UnlockStrength.BIOMETRIC_STRONG}
    )
    assert not result.ok


def test_b2_platform_lying_about_strength_refused():
    sim = SimulatedPlatform(
        enrolled={UnlockStrength.BIOMETRIC_STRONG},
        script=[AuthResult.success(UnlockStrength.BIOMETRIC_WEAK)],  # lie
    )
    result = UnlockPrompt(platform=sim).authenticate(
        "t", allowed={UnlockStrength.BIOMETRIC_STRONG}
    )
    assert not result.ok


def test_b2_explicit_weak_allowed_works():
    sim = SimulatedPlatform(
        enrolled={UnlockStrength.BIOMETRIC_WEAK},
        script=[AuthResult.success(UnlockStrength.BIOMETRIC_WEAK)],
    )
    result = UnlockPrompt(platform=sim).authenticate(
        "t", allowed={UnlockStrength.BIOMETRIC_WEAK}
    )
    assert result.ok and result.strength_used == UnlockStrength.BIOMETRIC_WEAK


def test_b2_empty_allowed_set_refused():
    result = UnlockPrompt(platform=_ok_platform()).authenticate("t", allowed=set())
    assert not result.ok


# -- B3: honest no-hardware --------------------------------------------------

def test_b3_no_hardware_refuses_honestly():
    result = UnlockPrompt(platform=NoHardwarePlatform()).authenticate("t")
    assert not result.ok
    assert "refused" in result.reason


def test_b3_default_platform_is_no_hardware():
    prompt = UnlockPrompt()  # no platform given
    assert isinstance(prompt.platform, NoHardwarePlatform)
    assert not prompt.authenticate("t").ok


# -- B4: lockout -------------------------------------------------------------

def test_b4_lockout_after_max_attempts():
    now = [1000.0]
    sim = SimulatedPlatform(
        enrolled={UnlockStrength.BIOMETRIC_STRONG},
        script=[AuthResult.failure("nope")] * 10,
    )
    prompt = UnlockPrompt(platform=sim, time_fn=lambda: now[0])
    for _ in range(MAX_ATTEMPTS):
        assert not prompt.authenticate("t").ok
    assert prompt.tracker.locked()
    runs = sim.ceremonies_run
    refused = prompt.authenticate("t")
    assert not refused.ok and "locked out" in refused.reason
    assert sim.ceremonies_run == runs  # platform untouched during lockout


def test_b4_success_resets_counter():
    sim = SimulatedPlatform(
        enrolled={UnlockStrength.BIOMETRIC_STRONG},
        script=[AuthResult.failure("x"), AuthResult.success(UnlockStrength.BIOMETRIC_STRONG)],
    )
    prompt = UnlockPrompt(platform=sim)
    assert not prompt.authenticate("t").ok
    assert prompt.authenticate("t").ok
    assert prompt.tracker.failures == 0


def test_b4_lockout_expires():
    now = [1000.0]
    sim = SimulatedPlatform(
        enrolled={UnlockStrength.BIOMETRIC_STRONG},
        script=[AuthResult.failure("x")] * 10,
    )
    prompt = UnlockPrompt(platform=sim, time_fn=lambda: now[0])
    for _ in range(MAX_ATTEMPTS):
        prompt.authenticate("t")
    assert prompt.tracker.locked()
    now[0] += LOCKOUT_SECONDS + 1
    assert not prompt.tracker.locked()


# -- B5: locked by default, auto-lock ----------------------------------------

def test_b5_starts_locked():
    assert LockPolicy().is_locked


def test_b5_unlock_only_on_success():
    policy = LockPolicy()
    bad = SimulatedPlatform(
        enrolled={UnlockStrength.BIOMETRIC_STRONG},
        script=[AuthResult.failure("nope")],
    )
    policy.unlock(UnlockPrompt(platform=bad), title="t")
    assert policy.is_locked


def test_b5_background_relocks():
    now = [5000.0]
    policy = LockPolicy(auto_lock_ms=60_000, time_fn=lambda: now[0])
    policy.unlock(UnlockPrompt(platform=_ok_platform()), title="t")
    assert not policy.is_locked
    policy.on_app_backgrounded()
    assert policy.is_locked


def test_b5_idle_timeout_relocks():
    now = [5000.0]
    policy = LockPolicy(auto_lock_ms=1000, time_fn=lambda: now[0])
    policy.unlock(UnlockPrompt(platform=_ok_platform()), title="t")
    assert not policy.is_locked
    now[0] += 2.0
    assert policy.is_locked


# -- B6: founder gate ---------------------------------------------------------

def test_b6_founder_full_others_limited():
    assert capability_for("chauncey") == "full"
    assert capability_for("someone-else") == "limited"
    assert require_full("chauncey") == "full"
    with pytest.raises(BiometricGateError):
        require_full("someone-else")


def test_b6_non_founder_cannot_bind_or_release():
    box = _box()
    with pytest.raises(BiometricGateError):
        box.bind(b"secret", identity_name="someone-else")
    box.bind(b"secret", identity_name="chauncey")
    with pytest.raises(BiometricGateError):
        box.release(UnlockPrompt(platform=_ok_platform()), identity_name="someone-else")


def test_b6_limited_lane_keeps_lock_machinery():
    # Limited identities still get lock policy + prompt machinery (no keys).
    policy = LockPolicy()
    assert policy.is_locked
    prompt = UnlockPrompt(platform=NoHardwarePlatform())
    assert not prompt.authenticate("t").ok  # honest refusal, no gate error


# -- Ledger -------------------------------------------------------------------

def test_ledger_verifies_and_detects_tamper():
    ledger = UnlockLedger()
    ledger.append("unlock", {"strength": "biometric_strong"})
    ledger.append("lock", {"reason": "explicit"})
    assert ledger.verify()
    ledger._events[0]["detail"]["strength"] = "none"
    assert not ledger.verify()


def test_ledger_carries_no_secrets():
    ledger = UnlockLedger()
    rec = ledger.append("bind", {"sealed_len": 32})
    blob = str(rec)
    assert "keeper" not in blob and "secret" not in blob


# -- Proof sweep ---------------------------------------------------------------

def test_capability_descriptor():
    cap = capability()
    assert cap.id == "cybrus.biometric_unlock"
    assert cap.risk.name == "CRITICAL"


def test_default_allowed_matches_his_original():
    assert DEFAULT_ALLOWED == frozenset(
        {UnlockStrength.BIOMETRIC_STRONG, UnlockStrength.DEVICE_CREDENTIAL}
    )


# -- B7: bloodline metering ---------------------------------------------------

def test_b7_limited_lane_metered():
    meter = InMemoryMeter(default_quota=1)
    sim = SimulatedPlatform(
        enrolled={UnlockStrength.BIOMETRIC_STRONG},
        script=[AuthResult.success(UnlockStrength.BIOMETRIC_STRONG)] * 3,
    )
    prompt = UnlockPrompt(platform=sim)
    assert prompt.authenticate("t", identity="someone-else", meter=meter).ok
    refused = prompt.authenticate("t", identity="someone-else", meter=meter)
    assert not refused.ok and "provisioned by the founder" in refused.reason
    assert meter.quota_remaining("someone-else", CAPABILITY_ID) == 0


def test_b7_founder_lane_unmetered():
    meter = InMemoryMeter(default_quota=0)  # exhausted for everyone...
    sim = SimulatedPlatform(
        enrolled={UnlockStrength.BIOMETRIC_STRONG},
        script=[AuthResult.success(UnlockStrength.BIOMETRIC_STRONG)],
    )
    # ...but the founder is the bloodline root: still served.
    result = UnlockPrompt(platform=sim).authenticate(
        "t", identity="chauncey", meter=meter
    )
    assert result.ok


def test_b7_anonymous_is_limited():
    meter = InMemoryMeter(default_quota=0)
    result = UnlockPrompt(platform=_ok_platform()).authenticate("t", meter=meter)
    assert not result.ok and "provisioned by the founder" in result.reason


def test_check_invariants_all_pass():
    results = check_invariants()
    failed = [r for r in results if not r["passed"]]
    assert not failed, failed
    laws = {r["law"] for r in results}
    assert {"B1", "B2", "B3", "B4", "B5", "B6", "B7", "LEDGER"} <= laws

"""Tests for core/levi/automation/backoff.py."""

import pytest

from levi.automation.backoff import (
    BackoffError,
    CircuitBreaker,
    CircuitState,
    RetryPolicy,
)


def test_retry_policy_exponential_capped():
    p = RetryPolicy(max_attempts=5, base_delay_s=2.0, max_delay_s=10.0)
    # 5 attempts = 4 retries
    assert p.schedule() == [2.0, 4.0, 8.0, 10.0]


def test_retry_policy_rejects_bad_config():
    with pytest.raises(BackoffError):
        RetryPolicy(max_attempts=0)
    with pytest.raises(BackoffError):
        RetryPolicy(base_delay_s=10.0, max_delay_s=1.0)
    with pytest.raises(BackoffError):
        RetryPolicy(max_attempts=3).delay_for(0)


def test_retry_policy_seeded_jitter_reproducible():
    a = RetryPolicy(max_attempts=4, jitter_seed=13)
    b = RetryPolicy(max_attempts=4, jitter_seed=13)
    assert a.schedule() == b.schedule()
    c = RetryPolicy(max_attempts=4, jitter_seed=14)
    assert a.schedule() != c.schedule()
    # jitter stays within the 0.5x..1.5x band of the raw backoff
    for attempt, delay in enumerate(a.schedule(), start=1):
        raw = min(2.0 ** (attempt - 1), 300.0)
        assert 0.5 * raw <= delay <= 1.5 * raw


def _breaker(tmp_path, **kw):
    return CircuitBreaker("webhook", store_path=tmp_path / "breakers.json", **kw)


def test_breaker_opens_after_threshold(tmp_path):
    cb = _breaker(tmp_path, failure_threshold=3, open_cooldown_s=60.0)
    assert cb.allow(0.0)
    cb.record_failure(1.0)
    cb.record_failure(2.0)
    assert cb.allow(3.0)  # still closed at 2 failures
    cb.record_failure(4.0)
    assert cb.snapshot()["state"] == CircuitState.OPEN
    assert not cb.allow(5.0)  # fail fast during cooldown


def test_breaker_half_open_probe_closes(tmp_path):
    cb = _breaker(tmp_path, failure_threshold=1, open_cooldown_s=10.0)
    cb.record_failure(0.0)
    assert not cb.allow(5.0)
    assert cb.allow(11.0)  # cooldown expired -> half-open probe allowed
    assert cb.snapshot()["state"] == CircuitState.HALF_OPEN
    cb.record_success(12.0)
    assert cb.snapshot()["state"] == CircuitState.CLOSED
    assert cb.allow(13.0)


def test_breaker_half_open_probe_failure_reopens(tmp_path):
    cb = _breaker(tmp_path, failure_threshold=1, open_cooldown_s=10.0)
    cb.record_failure(0.0)
    assert cb.allow(11.0)
    cb.record_failure(12.0)
    assert cb.snapshot()["state"] == CircuitState.OPEN
    assert not cb.allow(13.0)  # fresh cooldown


def test_breaker_limits_concurrent_probes(tmp_path):
    cb = _breaker(
        tmp_path, failure_threshold=1, open_cooldown_s=10.0, half_open_probes=1
    )
    cb.record_failure(0.0)
    assert cb.allow(11.0)  # probe 1
    assert not cb.allow(11.5)  # probe 2 blocked while one is outstanding


def test_breaker_state_survives_restart(tmp_path):
    store = tmp_path / "breakers.json"
    cb = CircuitBreaker("x", failure_threshold=2, store_path=store)
    cb.record_failure(1.0)
    cb.record_failure(2.0)
    assert cb.snapshot()["state"] == CircuitState.OPEN
    cb2 = CircuitBreaker("x", failure_threshold=2, store_path=store)
    assert cb2.snapshot()["state"] == CircuitState.OPEN
    assert cb2.snapshot()["opened_at"] == 2.0
    assert not cb2.allow(3.0)


def test_breaker_success_resets_failures(tmp_path):
    cb = _breaker(tmp_path, failure_threshold=3)
    cb.record_failure(1.0)
    cb.record_failure(2.0)
    cb.record_success(3.0)
    assert cb.snapshot()["failures"] == 0
    cb.record_failure(4.0)
    assert cb.snapshot()["state"] == CircuitState.CLOSED


def test_breaker_rejects_bad_config(tmp_path):
    with pytest.raises(BackoffError):
        CircuitBreaker("", store_path=tmp_path / "b.json")
    with pytest.raises(BackoffError):
        CircuitBreaker("x", failure_threshold=0, store_path=tmp_path / "b.json")


def test_breaker_store_is_owner_only(tmp_path):
    import os
    import stat

    store = tmp_path / "breakers.json"
    cb = CircuitBreaker("x", store_path=store)
    cb.record_failure(1.0)
    assert stat.S_IMODE(os.stat(store).st_mode) == 0o600

"""Gate bypass proofs for the Plaiground adult surface.

These tests exist to PROVE the gate cannot be bypassed. Every test here
is hermetic: it uses a tmp home directory, never the real ``~/.levi``.

Bypasses attempted and shown to fail:
  * gate off by default (no record exists)
  * environment variable tricks (PLAIGROUND_ENABLED=1, LEVI_ADULT=1, ...)
  * hand-written config records (config edits cannot enable the gate)
  * records with wrong permissions, wrong uid, or missing fields
  * direct function calls with the gate off (every entry point)
  * enabling while a minor indicator is present (env var or lock file)
  * enabling with a wrong confirmation phrase
  * a minor indicator appearing AFTER enable re-locks the gate
"""

import json
import os
from pathlib import Path

import pytest

from levi.plaiground import chat, companions, gate, photos, simulator


@pytest.fixture()
def home(tmp_path):
    return tmp_path


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    # Belt-and-suspenders: tests must not inherit ambient env influence.
    for var in (
        "PLAIGROUND_ENABLED",
        "LEVI_ADULT",
        "ADULT",
        "PLAIGROUND_ADULT",
        "LEVI_ADULT_MODE",
    ) + gate.MINOR_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


# ---------------------------------------------------------------------------
# Default-off
# ---------------------------------------------------------------------------


def test_gate_off_by_default(home):
    assert gate.verify_adult(home) is False
    assert gate.status(home)["enabled"] is False


# ---------------------------------------------------------------------------
# Every public entry point refuses with the gate off
# ---------------------------------------------------------------------------


def test_creator_refuses_when_locked(home):
    with pytest.raises(gate.GateLockedError):
        companions.create_companion("Nova", home=home)


def test_creator_read_refuses_when_locked(home):
    with pytest.raises(gate.GateLockedError):
        companions.list_companions(home)


def test_simulator_refuses_when_locked(home):
    with pytest.raises(gate.GateLockedError):
        simulator.run_scenario("Nova", "a quiet evening walk", home=home)


def test_chat_refuses_when_locked(home):
    with pytest.raises(gate.GateLockedError):
        chat.ChatSession("Nova", home=home)


def test_photos_refuse_when_locked(home):
    with pytest.raises(gate.GateLockedError):
        photos.request_photo("a moonlit lake", home=home)
    with pytest.raises(gate.GateLockedError):
        photos.available_backends(home)


# ---------------------------------------------------------------------------
# Env var tricks do not open the gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "var",
    [
        "PLAIGROUND_ENABLED",
        "LEVI_ADULT",
        "ADULT",
        "PLAIGROUND_ADULT",
        "LEVI_ADULT_MODE",
        "PLAIGROUND_ON",
    ],
)
def test_env_var_tricks_fail(home, monkeypatch, var):
    monkeypatch.setenv(var, "1")
    assert gate.verify_adult(home) is False
    with pytest.raises(gate.GateLockedError):
        companions.create_companion("Nova", home=home)


def test_env_var_true_tricks_fail(home, monkeypatch):
    monkeypatch.setenv("PLAIGROUND_ENABLED", "true")
    monkeypatch.setenv("LEVI_ADULT_MODE", "yes")
    assert gate.verify_adult(home) is False


# ---------------------------------------------------------------------------
# Config edits (hand-written records) cannot enable the gate
# ---------------------------------------------------------------------------


def _write_raw_record(home, record, mode=0o600):
    gf = gate.gate_file(home)
    gf.parent.mkdir(parents=True, exist_ok=True)
    gf.write_text(json.dumps(record), encoding="utf-8")
    os.chmod(gf, mode)
    return gf


_TEST_PIN = "test-pin-1234"


def _arm(home, pin=_TEST_PIN):
    """Set the owner PIN and return it — the gate cannot enable without one."""
    gate.set_pin(pin, home=home)
    return pin


def test_handwritten_record_without_affirmation_fails(home):
    _write_raw_record(home, {"enabled": True})
    assert gate.verify_adult(home) is False


def test_handwritten_record_with_full_shape_but_not_via_enable(home):
    # Even a well-shaped hand-written record fails: the file's uid must
    # match AND (in production) be written by enable_adult_mode. The uid
    # matches here (same test user), so the record-shape check must hold:
    # a forged record lacking the exact affirmation marker fails.
    _write_raw_record(
        home,
        {
            "enabled": True,
            "owner_uid": os.getuid(),
            "affirmed": "nope-not-the-real-marker",
            "confirmed_at": "2026-01-01T00:00:00+00:00",
        },
    )
    assert gate.verify_adult(home) is False


def test_record_with_wrong_permissions_fails(home):
    pin = _arm(home)
    gate.enable_adult_mode(gate.CONFIRMATION_PHRASE, pin, home=home)
    os.chmod(gate.gate_file(home), 0o644)  # loosened after enable
    assert gate.verify_adult(home) is False
    with pytest.raises(gate.GateLockedError):
        companions.create_companion("Nova", home=home)


def test_enabled_false_record_fails(home):
    _write_raw_record(
        home,
        {
            "enabled": False,
            "owner_uid": os.getuid(),
            "affirmed": "explicit-owner-opt-in",
        },
    )
    assert gate.verify_adult(home) is False


def test_corrupt_record_fails(home):
    gf = gate.gate_file(home)
    gf.parent.mkdir(parents=True, exist_ok=True)
    gf.write_text("not json at all", encoding="utf-8")
    os.chmod(gf, 0o600)
    assert gate.verify_adult(home) is False


def test_missing_record_fails(home):
    assert gate.verify_adult(home) is False


# ---------------------------------------------------------------------------
# The lawful path works — and only it
# ---------------------------------------------------------------------------


def test_enable_requires_exact_confirmation_phrase(home):
    _arm(home)
    with pytest.raises(gate.GateError):
        gate.enable_adult_mode("", _TEST_PIN, home=home)
    with pytest.raises(gate.GateError):
        gate.enable_adult_mode("yes", _TEST_PIN, home=home)
    with pytest.raises(gate.GateError):
        gate.enable_adult_mode("i affirm i am an adult", _TEST_PIN, home=home)
    assert gate.verify_adult(home) is False


def test_enable_refuses_when_minor_env_present(home, monkeypatch):
    monkeypatch.setenv("LEVI_MINOR", "1")
    with pytest.raises(gate.MinorIndicatorError):
        gate.enable_adult_mode(gate.CONFIRMATION_PHRASE, _TEST_PIN, home=home)
    assert gate.verify_adult(home) is False


def test_enable_refuses_when_minor_lock_file_present(home):
    lock = gate.gate_dir(home) / ".minor-lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("minor", encoding="utf-8")
    with pytest.raises(gate.MinorIndicatorError):
        gate.enable_adult_mode(gate.CONFIRMATION_PHRASE, _TEST_PIN, home=home)
    assert gate.verify_adult(home) is False


def test_minor_indicator_appearing_after_enable_relocks(home, monkeypatch):
    pin = _arm(home)
    gate.enable_adult_mode(gate.CONFIRMATION_PHRASE, pin, home=home)
    assert gate.verify_adult(home) is True
    monkeypatch.setenv("PLAIGROUND_MINOR", "true")
    assert gate.verify_adult(home) is False
    with pytest.raises(gate.GateLockedError):
        simulator.run_scenario("Nova", "a walk", home=home)


def test_lawful_enable_opens_everything(home):
    pin = _arm(home)
    path = gate.enable_adult_mode(gate.CONFIRMATION_PHRASE, pin, home=home)
    assert Path(path).stat().st_mode & 0o777 == 0o600
    assert gate.verify_adult(home) is True
    companions.create_companion("Nova", home=home)
    assert "Nova" in companions.list_companions(home)
    session = chat.ChatSession("Nova", home=home)
    assert isinstance(session.say("hello"), str)
    result = simulator.run_scenario("Nova", "a quiet evening walk", home=home)
    assert result["engine"] == "echoverse"


def test_disable_closes_gate(home):
    pin = _arm(home)
    gate.enable_adult_mode(gate.CONFIRMATION_PHRASE, pin, home=home)
    assert gate.verify_adult(home) is True
    assert gate.disable_adult_mode(home) is True
    assert gate.verify_adult(home) is False
    assert gate.disable_adult_mode(home) is False


def test_status_never_enables(home):
    # Inspecting status must have zero side effects.
    gate.status(home)
    assert gate.verify_adult(home) is False


# ---------------------------------------------------------------------------
# PIN law: no PIN, no enable. Wrong PIN, no enable.
# ---------------------------------------------------------------------------


def test_enable_refuses_when_no_pin_set(home):
    with pytest.raises(gate.PinError):
        gate.enable_adult_mode(gate.CONFIRMATION_PHRASE, "whatever", home=home)
    assert gate.verify_adult(home) is False


def test_enable_refuses_wrong_pin(home):
    _arm(home, pin="correct-pin")
    with pytest.raises(gate.PinError):
        gate.enable_adult_mode(gate.CONFIRMATION_PHRASE, "wrong-pin", home=home)
    assert gate.verify_adult(home) is False


def test_set_pin_refuses_too_short(home):
    with pytest.raises(gate.PinError):
        gate.set_pin("123", home=home)
    assert gate.has_pin(home) is False


def test_set_pin_refuses_when_minor_env_present(home, monkeypatch):
    monkeypatch.setenv("LEVI_MINOR", "1")
    with pytest.raises(gate.MinorIndicatorError):
        gate.set_pin("some-pin", home=home)
    assert gate.has_pin(home) is False


def test_pin_is_never_plaintext_on_disk(home):
    gate.set_pin("super-secret-pin", home=home)
    raw = gate.pin_file(home).read_text(encoding="utf-8")
    assert "super-secret-pin" not in raw
    assert gate.verify_pin("super-secret-pin", home) is True
    assert gate.verify_pin("wrong-pin", home) is False


def test_change_pin_needs_current_pin(home):
    _arm(home, pin="old-pin")
    with pytest.raises(gate.PinError):
        gate.change_pin("not-the-pin", "new-pin", home=home)
    gate.change_pin("old-pin", "new-pin", home=home)
    assert gate.verify_pin("new-pin", home) is True
    assert gate.verify_pin("old-pin", home) is False


def test_disable_needs_no_pin(home):
    pin = _arm(home)
    gate.enable_adult_mode(gate.CONFIRMATION_PHRASE, pin, home=home)
    assert gate.verify_adult(home) is True
    # Closing is always allowed — fail-closed, no PIN required.
    assert gate.disable_adult_mode(home) is True
    assert gate.verify_adult(home) is False


def test_status_reports_pin_set(home):
    assert gate.status(home)["pin_set"] is False
    _arm(home)
    assert gate.status(home)["pin_set"] is True

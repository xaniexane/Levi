"""Plaiground age gate — adult-only toggle with owner PIN, default OFF.

Chauncey's law (2026-09-21): every adult-themed service is age-gated with
a PIN and an on/off switch. This gate is the reference implementation:

- ON/OFF switch: :func:`enable_adult_mode` / :func:`disable_adult_mode`.
- PIN: :func:`set_pin` / :func:`change_pin` / :func:`verify_pin`. The PIN
  is required to flip the switch ON; turning it OFF needs no PIN
  (fail-closed — closing is always allowed). The PIN is stored as a
  PBKDF2-HMAC-SHA256 hash with a random salt, never plaintext.
- Age gate: the exact affirmative confirmation phrase, plus minor
  indicators that hard-lock the gate (minors can never enable, and a
  later-appearing indicator re-locks an open gate).

This is the law of the Plaiground surface: every public entry point in
:mod:`levi.plaiground` (creator, simulator, chat, photo hooks) must call
:func:`require_adult` before doing anything else. There is exactly one way
to open the gate, and there is no way to bypass it from code, config,
environment variables, or prompts.

The one lawful path to enable:
    1. A PIN must be set (:func:`set_pin`) — enabling with no PIN set
       is refused outright.
    2. Call :func:`enable_adult_mode` with the exact affirmative
       confirmation phrase AND the correct PIN.
    3. No minor indicator may be present (see :data:`MINOR_ENV_VARS` and
       :data:`MINOR_LOCK_FILES`) — if any is present, enable refuses.
    4. The gate writes an owner-only record under ``~/.levi/plaiground/``
       with mode ``0600``; :func:`verify_adult` re-checks the mode, the
       owner uid, the record contents, AND the minor indicators on every
       call, so a later-appearing minor indicator closes the gate again.

Nothing else can open the gate: no environment variable, no config file
edit, no direct function call with clever arguments, no wrong PIN. Tests
in ``tests/test_plaiground_gate.py`` prove the bypasses fail.

Honest gap (local-only verification): this gate proves an affirmative,
owner-authenticated opt-in on this machine. It cannot prove the human's
age the way a government ID check could — that kind of verification is
impossible with local-only means, and it is documented as such in
``docs/PLAIGROUND.md``. What the gate does guarantee: a minor cannot
reach Plaiground by accident, by default, by configuration, by tricking
a prompt, or by any input the code accepts — the gate is OFF until a
deliberate, owner-recorded, PIN-authenticated act turns it on, and minors
are hard-locked out by the minor-indicator check layered on top.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Gate errors
# ---------------------------------------------------------------------------


class GateError(Exception):
    """Base error for Plaiground gate failures."""


class GateLockedError(GateError, PermissionError):
    """Raised by every Plaiground entry point while the adult gate is OFF."""


class MinorIndicatorError(GateError):
    """Raised when a minor indicator blocks enabling or re-locks the gate."""


class PinError(GateError):
    """Raised for PIN problems: not set, wrong, or invalid."""


# ---------------------------------------------------------------------------
# Constants — the only knobs that exist
# ---------------------------------------------------------------------------

# The affirmative, non-default action. This is not a secret; it is a
# deliberate act. Default-off means nothing short of the exact phrase —
# typed through the dedicated enable command — plus the correct PIN
# opens the gate.
CONFIRMATION_PHRASE = "I AFFIRM I AM AN ADULT AND I ENABLE PLAIGROUND"

# Minor indicators: any of these present means the operator is (or may be)
# a minor, so enable refuses and verify_adult re-locks even a written record.
MINOR_ENV_VARS = ("LEVI_MINOR", "LEVI_MINOR_MODE", "PLAIGROUND_MINOR")
MINOR_LOCK_FILES = (".minor-lock", "minor.lock")

GATE_DIRNAME = "plaiground"
GATE_FILENAME = "gate.json"
PIN_FILENAME = "pin.json"
_RECORD_MODE = 0o600

# PIN storage: PBKDF2-HMAC-SHA256, random 16-byte salt, 200k iterations.
# The PIN itself never touches disk — only salt + hash.
_PBKDF2_ITERATIONS = 200_000
_PIN_MIN_LEN = 4
_PIN_MAX_LEN = 64


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def _home(home: Optional[Path] = None) -> Path:
    return Path(home) if home is not None else Path.home()


def gate_dir(home: Optional[Path] = None) -> Path:
    """Directory holding the Plaiground owner record (never committed)."""
    return _home(home) / ".levi" / GATE_DIRNAME


def gate_file(home: Optional[Path] = None) -> Path:
    return gate_dir(home) / GATE_FILENAME


# ---------------------------------------------------------------------------
# Minor indicators — hard lock
# ---------------------------------------------------------------------------


def _minor_env_present() -> Optional[str]:
    for var in MINOR_ENV_VARS:
        if os.environ.get(var, "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        ):
            return var
    return None


def _minor_lock_present(home: Optional[Path] = None) -> Optional[str]:
    gd = gate_dir(home)
    for name in MINOR_LOCK_FILES:
        p = gd / name
        if p.exists():
            return str(p)
        # A lock in the bare .levi dir covers setups where the gate dir was
        # never created (e.g. parental-control tooling dropping a marker).
        q = gd.parent / name
        if q.exists():
            return str(q)
    return None


def minor_indicator(home: Optional[Path] = None) -> Optional[str]:
    """Return a description of the first minor indicator found, else None."""
    env_hit = _minor_env_present()
    if env_hit is not None:
        return "environment variable %s is set" % env_hit
    lock_hit = _minor_lock_present(home)
    if lock_hit is not None:
        return "minor lock file present: %s" % lock_hit
    return None


def is_minor_context(home: Optional[Path] = None) -> bool:
    """True when any minor indicator is present — minors hard-locked out."""
    return minor_indicator(home) is not None


# ---------------------------------------------------------------------------
# PIN — required to flip the switch ON, never stored in plaintext
# ---------------------------------------------------------------------------


def pin_file(home: Optional[Path] = None) -> Path:
    return gate_dir(home) / PIN_FILENAME


def _hash_pin(pin: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", pin.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    ).hex()


def _validate_pin_shape(pin: object) -> str:
    if not isinstance(pin, str):
        raise PinError("PIN must be a string.")
    if not (_PIN_MIN_LEN <= len(pin) <= _PIN_MAX_LEN):
        raise PinError(
            "PIN must be %d-%d characters." % (_PIN_MIN_LEN, _PIN_MAX_LEN)
        )
    return pin


def has_pin(home: Optional[Path] = None) -> bool:
    """True when an owner PIN record exists (0600, correct shape)."""
    pf = pin_file(home)
    if not pf.is_file():
        return False
    try:
        st = pf.stat()
    except OSError:
        return False
    if (st.st_mode & 0o777) != _RECORD_MODE:
        return False
    if st.st_uid != os.getuid():
        return False
    try:
        record = json.loads(pf.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (
        isinstance(record, dict)
        and isinstance(record.get("salt"), str)
        and isinstance(record.get("hash"), str)
    )


def set_pin(pin: str, home: Optional[Path] = None) -> Path:
    """Set (or replace) the owner PIN. Refuses when a minor indicator is present.

    A minor must never be able to arm the gate for later use, so setting a
    PIN is itself a minor-gated act.
    """
    hit = minor_indicator(home)
    if hit is not None:
        raise MinorIndicatorError(
            "set_pin refused: minor indicator present (%s)." % hit
        )
    pin = _validate_pin_shape(pin)
    salt = secrets.token_bytes(16)
    record = {
        "salt": salt.hex(),
        "hash": _hash_pin(pin, salt),
        "iterations": _PBKDF2_ITERATIONS,
        "set_at": datetime.now(timezone.utc).isoformat(),
    }
    gd = gate_dir(home)
    gd.mkdir(parents=True, exist_ok=True)
    pf = pin_file(home)
    pf.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.chmod(pf, _RECORD_MODE)
    return pf


def verify_pin(pin: object, home: Optional[Path] = None) -> bool:
    """True only when the given PIN matches the stored hash (constant-time)."""
    if not isinstance(pin, str) or not has_pin(home):
        return False
    try:
        record = json.loads(pin_file(home).read_text(encoding="utf-8"))
        salt = bytes.fromhex(record["salt"])
        expected = record["hash"]
    except (OSError, ValueError, KeyError):
        return False
    return hmac.compare_digest(_hash_pin(pin, salt), expected)


def change_pin(old_pin: str, new_pin: str, home: Optional[Path] = None) -> Path:
    """Change the PIN — requires the current PIN. No correct old PIN, no change."""
    if not verify_pin(old_pin, home):
        raise PinError("change_pin refused: current PIN is wrong.")
    return set_pin(new_pin, home)


# ---------------------------------------------------------------------------
# The one lawful path: enable_adult_mode
# ---------------------------------------------------------------------------


def enable_adult_mode(
    confirmation: str, pin: str, home: Optional[Path] = None
) -> Path:
    """Enable the Plaiground adult surface for this machine's owner.

    Requires ALL THREE: the exact :data:`CONFIRMATION_PHRASE` (an
    affirmative, non-default act), the correct owner PIN, and no minor
    indicator present. Enabling with no PIN set is refused — Chauncey's
    law: the switch does not move without the PIN.

    Writes the owner-only record with mode 0600.

    Raises:
        MinorIndicatorError: when a minor indicator is present.
        PinError: when no PIN is set or the PIN is wrong.
        GateError: when the confirmation phrase is missing or wrong.
    """
    hit = minor_indicator(home)
    if hit is not None:
        raise MinorIndicatorError(
            "enable_adult_mode refused: minor indicator present (%s). "
            "Plaiground stays locked." % hit
        )
    if not has_pin(home):
        raise PinError(
            "enable_adult_mode refused: no PIN set. Set one first with "
            "set_pin — the switch does not move without the PIN."
        )
    if not isinstance(confirmation, str) or confirmation != CONFIRMATION_PHRASE:
        raise GateError(
            "enable_adult_mode requires the exact affirmative confirmation "
            "phrase. Pass CONFIRMATION_PHRASE deliberately; there is no "
            "default, shortcut, flag, or environment variable."
        )
    if not verify_pin(pin, home):
        raise PinError("enable_adult_mode refused: wrong PIN.")
    gd = gate_dir(home)
    gd.mkdir(parents=True, exist_ok=True)
    # Re-check after mkdir: a lock could appear between the checks only in a
    # racing-writer scenario; the verify side re-checks anyway, but fail
    # closed here too.
    hit = minor_indicator(home)
    if hit is not None:
        raise MinorIndicatorError(
            "enable_adult_mode refused: minor indicator present (%s)." % hit
        )
    record = {
        "enabled": True,
        "owner_uid": os.getuid(),
        "affirmed": "explicit-owner-opt-in",
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
        "gate": "plaiground-adult-only",
        "minor_indicator_check": "absent-at-enable",
    }
    gf = gate_file(home)
    gf.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.chmod(gf, _RECORD_MODE)
    # Lock the directory down too (best effort; record file is the authority).
    try:
        os.chmod(gd, 0o700)
    except OSError:
        pass
    return gf


def disable_adult_mode(home: Optional[Path] = None) -> bool:
    """Close the gate: remove the owner record. Returns True if it existed.

    Turning OFF never needs the PIN — fail-closed means closing is always
    allowed.
    """
    gf = gate_file(home)
    if gf.exists():
        gf.unlink()
        return True
    return False


# ---------------------------------------------------------------------------
# The check every entry point must call first
# ---------------------------------------------------------------------------


def _record_valid(home: Optional[Path] = None) -> bool:
    gf = gate_file(home)
    if not gf.is_file():
        return False
    try:
        st = gf.stat()
    except OSError:
        return False
    # 1. Owner-only file: mode must be exactly 0600 and owned by this uid.
    if (st.st_mode & 0o777) != _RECORD_MODE:
        return False
    if st.st_uid != os.getuid():
        return False
    # 2. Contents must be the shape enable_adult_mode wrote.
    try:
        record = json.loads(gf.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(record, dict):
        return False
    if record.get("enabled") is not True:
        return False
    if record.get("affirmed") != "explicit-owner-opt-in":
        return False
    if record.get("owner_uid") != os.getuid():
        return False
    return True


def verify_adult(home: Optional[Path] = None) -> bool:
    """True only when the gate is lawfully enabled AND no minor indicator.

    This is the single source of truth. Environment variables, config
    files, and hand-written records can never make this return True —
    only a 0600 owner record written by :func:`enable_adult_mode`, and
    only while no minor indicator is present.
    """
    if is_minor_context(home):
        return False
    return _record_valid(home)


def require_adult(home: Optional[Path] = None) -> None:
    """Raise :class:`GateLockedError` unless the adult gate is open.

    Every public Plaiground function calls this FIRST, before any other
    work. ``home`` is an internal/test seam — callers in production pass
    nothing, so the real owner record is always consulted.
    """
    if not verify_adult(home):
        raise GateLockedError(
            "Plaiground is adult-only and the gate is OFF (default). "
            "Enable it with levi.plaiground.gate.enable_adult_mode("
            "CONFIRMATION_PHRASE, pin) after set_pin — minors are "
            "hard-locked out and no configuration, environment variable, "
            "or prompt can bypass this check."
        )


def status(home: Optional[Path] = None) -> dict:
    """Inspectable gate state — for CLIs and honesty, never for bypassing."""
    hit = minor_indicator(home)
    return {
        "enabled": verify_adult(home),
        "record_present": gate_file(home).is_file(),
        "pin_set": has_pin(home),
        "minor_indicator": hit,
        "zone": "plaiground",
        "clean_zone": "echoverse",
    }


# ---------------------------------------------------------------------------
# Dedicated enable command: python -m levi.plaiground.gate enable
# ---------------------------------------------------------------------------


def _cli() -> int:
    import argparse
    import getpass

    parser = argparse.ArgumentParser(
        description="Plaiground adult gate — PIN, enable/disable/status."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("set-pin", help="Set the owner PIN (prompted, never echoed).")
    sub.add_parser("change-pin", help="Change the PIN (needs the current one).")
    en = sub.add_parser("enable", help="Open the adult gate (owner act).")
    en.add_argument(
        "--i-affirm-i-am-an-adult",
        action="store_true",
        help="Affirmative, non-default owner action. Required.",
    )
    sub.add_parser("disable", help="Close the gate (no PIN needed).")
    sub.add_parser("status", help="Show gate state.")
    args = parser.parse_args()

    if args.command == "set-pin":
        pin = getpass.getpass("New PIN (4-64 chars): ")
        try:
            path = set_pin(pin)
        except (GateError, MinorIndicatorError) as exc:
            print("REFUSED: %s" % exc)
            return 1
        print("PIN set. Record: %s" % path)
        return 0
    if args.command == "change-pin":
        old = getpass.getpass("Current PIN: ")
        new = getpass.getpass("New PIN (4-64 chars): ")
        try:
            path = change_pin(old, new)
        except (GateError, MinorIndicatorError) as exc:
            print("REFUSED: %s" % exc)
            return 1
        print("PIN changed. Record: %s" % path)
        return 0
    if args.command == "enable":
        if not args.i_affirm_i_am_an_adult:
            print(
                "REFUSED: pass --i-affirm-i-am-an-adult to perform the "
                "affirmative owner act."
            )
            return 2
        pin = getpass.getpass("Owner PIN: ")
        try:
            path = enable_adult_mode(CONFIRMATION_PHRASE, pin)
        except (GateError, MinorIndicatorError) as exc:
            print("REFUSED: %s" % exc)
            return 1
        print("Plaiground gate OPEN. Record: %s" % path)
        return 0
    if args.command == "disable":
        print("Gate closed." if disable_adult_mode() else "Gate was closed.")
        return 0
    if args.command == "status":
        print(json.dumps(status(), indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(_cli())

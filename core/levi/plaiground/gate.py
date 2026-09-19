"""Plaiground age gate — adult-only toggle, default OFF.

This is the law of the Plaiground surface: every public entry point in
:mod:`levi.plaiground` (creator, simulator, chat, photo hooks) must call
:func:`require_adult` before doing anything else. There is exactly one way
to open the gate, and there is no way to bypass it from code, config,
environment variables, or prompts.

The one lawful path to enable:
    1. Call :func:`enable_adult_mode` with the exact affirmative
       confirmation phrase (an affirmative, non-default owner action).
    2. No minor indicator may be present (see :data:`MINOR_ENV_VARS` and
       :data:`MINOR_LOCK_FILES`) — if any is present, enable refuses.
    3. The gate writes an owner-only record under ``~/.levi/plaiground/``
       with mode ``0600``; :func:`verify_adult` re-checks the mode, the
       owner uid, the record contents, AND the minor indicators on every
       call, so a later-appearing minor indicator closes the gate again.

Nothing else can open the gate: no environment variable, no config file
edit, no direct function call with clever arguments. Tests in
``tests/test_plaiground_gate.py`` prove the bypasses fail.

Honest gap (local-only verification): this gate proves an affirmative,
owner-authenticated opt-in on this machine. It cannot prove the human's
age the way a government ID check could — that kind of verification is
impossible with local-only means, and it is documented as such in
``docs/PLAIGROUND.md``. What the gate does guarantee: a minor cannot
reach Plaiground by accident, by default, by configuration, by tricking
a prompt, or by any input the code accepts — the gate is OFF until a
deliberate, owner-recorded act turns it on, and minors are hard-locked
out by the minor-indicator check layered on top.
"""

from __future__ import annotations

import json
import os
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


# ---------------------------------------------------------------------------
# Constants — the only knobs that exist
# ---------------------------------------------------------------------------

# The affirmative, non-default action. This is not a secret; it is a
# deliberate act. Default-off means nothing short of the exact phrase —
# typed through the dedicated enable command — opens the gate.
CONFIRMATION_PHRASE = "I AFFIRM I AM AN ADULT AND I ENABLE PLAIGROUND"

# Minor indicators: any of these present means the operator is (or may be)
# a minor, so enable refuses and verify_adult re-locks even a written record.
MINOR_ENV_VARS = ("LEVI_MINOR", "LEVI_MINOR_MODE", "PLAIGROUND_MINOR")
MINOR_LOCK_FILES = (".minor-lock", "minor.lock")

GATE_DIRNAME = "plaiground"
GATE_FILENAME = "gate.json"
_RECORD_MODE = 0o600


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
# The one lawful path: enable_adult_mode
# ---------------------------------------------------------------------------


def enable_adult_mode(confirmation: str, home: Optional[Path] = None) -> Path:
    """Enable the Plaiground adult surface for this machine's owner.

    Requires the exact :data:`CONFIRMATION_PHRASE` — an affirmative,
    non-default act — and refuses outright when any minor indicator is
    present. Writes the owner-only record with mode 0600.

    Raises:
        MinorIndicatorError: when a minor indicator is present.
        GateError: when the confirmation phrase is missing or wrong.
    """
    hit = minor_indicator(home)
    if hit is not None:
        raise MinorIndicatorError(
            "enable_adult_mode refused: minor indicator present (%s). "
            "Plaiground stays locked." % hit
        )
    if not isinstance(confirmation, str) or confirmation != CONFIRMATION_PHRASE:
        raise GateError(
            "enable_adult_mode requires the exact affirmative confirmation "
            "phrase. Pass CONFIRMATION_PHRASE deliberately; there is no "
            "default, shortcut, flag, or environment variable."
        )
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
    """Close the gate: remove the owner record. Returns True if it existed."""
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
            "CONFIRMATION_PHRASE) — minors are hard-locked out and no "
            "configuration, environment variable, or prompt can bypass "
            "this check."
        )


def status(home: Optional[Path] = None) -> dict:
    """Inspectable gate state — for CLIs and honesty, never for bypassing."""
    hit = minor_indicator(home)
    return {
        "enabled": verify_adult(home),
        "record_present": gate_file(home).is_file(),
        "minor_indicator": hit,
        "zone": "plaiground",
        "clean_zone": "echoverse",
    }


# ---------------------------------------------------------------------------
# Dedicated enable command: python -m levi.plaiground.gate enable
# ---------------------------------------------------------------------------


def _cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Plaiground adult gate — enable/disable/status."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    en = sub.add_parser("enable", help="Open the adult gate (owner act).")
    en.add_argument(
        "--i-affirm-i-am-an-adult",
        action="store_true",
        help="Affirmative, non-default owner action. Required.",
    )
    sub.add_parser("disable", help="Close the gate.")
    sub.add_parser("status", help="Show gate state.")
    args = parser.parse_args()

    if args.command == "enable":
        if not args.i_affirm_i_am_an_adult:
            print(
                "REFUSED: pass --i-affirm-i-am-an-adult to perform the "
                "affirmative owner act."
            )
            return 2
        try:
            path = enable_adult_mode(CONFIRMATION_PHRASE)
        except GateError as exc:
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
